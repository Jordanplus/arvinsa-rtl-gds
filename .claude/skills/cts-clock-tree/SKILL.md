---
name: cts-clock-tree
description: Clock tree（CTS）問題，或 setup／hold 違規可能是 clock 造成時使用：clock buffer 的 fanout／cap 違規、skew（metric 含 uncertainty 與 derate，彙總的 worst_hold 是各 corner 最不負的值）、clock 輸入 pin 到第一級 clock buffer 的長線 slew（`CTS_CLK_MAX_WIRE_LENGTH`）、CTS 把 macro 的 clock 延到與 flip-flop 對齊（`delaybuf_*`；`CTS_DELAY_BUFFER_DERATE_PCT` 關不掉，要 `-no_insertion_delay` 與 LibreLane plugin）造成 macro 輸入 hold、SRAM 半週期 setup 與讀出 hold 變差、hold delay cell 在 slow corner 吃掉 setup、先拆 launch／capture clock latency 再決定在 clock 端或 data 端修、第一次帶 macro 的 harden 就檢查 macro clock 的結構，以及設了沒作用的設定（`CTS_MAX_CAP`；PDK 的 `RT_CLOCK_MIN_LAYER` 沒生效，clock 走 met1／met2）。flow 的變數關不掉某個工具行為時，查到底層工具的指令選項再判斷。資料路徑的 DRV 看 drv-timing-closure。Use for CTS problems and clock-caused setup/hold violations (skew, macro clock latency balancing, rise/fall latency asymmetry on half-cycle paths) in OpenROAD/LibreLane.
---

# Clock tree（CTS）

資料路徑的 DRV 看 `drv-timing-closure`。目前經驗較少，邊用邊補。本 repo 實例：`pnr/picorv32_core/README.md`（試跑 #8、#9）、`pnr/soc_top/pin_order.cfg`、`pnr/soc_top/README.md` 的設定表（Phase 4）。

## 規則（已驗證）

1. `CTS_SINK_CLUSTERING_SIZE 8`：預設每顆末端 buffer 帶 10 顆 flop，之後加 dummy load（`clkload*`），fanout 變 11–12。
2. `CTS_DISTANCE_BETWEEN_BUFFERS 50`：H-tree 中段沒放 buffer 時，第 2 層一顆 buffer 帶 16 顆下游 buffer（fanout 16、cap 0.206 pF）；設 50 µm 後最大 fanout 9。
3. 沒有作用：`CTS_MAX_CAP`（CTS 後的 DEF 每個 byte 都相同）；`CTS_SINK_CLUSTERING_SIZE 9`（反而分成更多群）。怎麼發現：改設定後比較 CTS step 輸出的 DEF；**沒有自動檢查**（設了沒作用不影響正確性，只是浪費試跑），LibreLane 升版時再比一次。
4. **clock 輸入 port**：pin 到第一級 clock buffer 的線不在 resizer 修復範圍內（clock net）。pin 在左邊最下方時，660 µm 的線在 ss slew 0.92 ns；移到 flip-flop 重心附近的下邊中段後消失（soc_explore2 → 4）。
5. `clkload*` 的輸出不接東西，會出現在 STA 的 unannotated 清單，屬正常（見 `signoff-checker-qualification` 規則 4）。
6. **skew 的 metric 不是 skew 本身**：`clock__skew__worst_*` 與 `report_clock_skew` 都含 clock uncertainty（0.25 ns），也含 ±5% derate（launch 用 late、capture 用 early）。soc_top nom_tt 的 metric 是 0.93 ns：扣掉 uncertainty 後 0.68 ns，再扣掉 derate 的名目值約 0.51 ns（推算）。彙總值：`clock__skew__worst_hold` 取各 corner 的最大值（最不負），`clock__skew__worst_setup` 取最小值（LibreLane `common/metrics/library.py` 第 166–173 行）；要看最差的 corner，讀 `__corner:<name>` 的值（Phase 7 wrapper：彙總 −2.589，最差 max_ss_n40C −3.649 ns）。
7. **`CTS_APPLY_NDR` 的 `half`**：只在 clock tree 的前半層套用 non-default rule（OpenROAD `src/cts/README.md`），不是「leaf 以外全部」。sky130 的 CTS NDR 是 2 倍間距，線寬沒有加大。
8. **PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒有生效**（LibreLane 設定沒生效也沒有警告，CLAUDE.md 規則 10）
   - **症狀**：沒有錯誤或警告；clock net 幾乎都繞在 met1／met2（Phase 3 soc_top 的 clock 繞線段：met1 9750、met2 2901、met3 90、met4 7；這份統計沒有存進 repo，結論記在 `docs/notes/signoff_criteria_soc_top.md` 的 signal EM 列）。
   - **已知的事實**：PDK 的 `libs.tech/openlane/config.tcl` 第 158 行設了 `met3`，`runs/<tag>/resolved.json` 卻是 null；LibreLane 的 `scripts/openroad/common/set_routing_layers.tcl` 第 20–21 行只在這個環境變數存在時才限制 clock 的最低層。推測（讀原始碼，沒有實驗）：LibreLane `steps/common_variables.py` 宣告這個變數時沒有標 `pdk=True`，所以 PDK 的值沒有讀進來。
   - **怎麼發現**：看 `resolved.json` 的 `RT_CLOCK_MIN_LAYER`；或統計最終 DEF 裡 clock net 每一層的繞線。
   - **怎麼繞過**：要讓 clock 走 met3 以上，只能在專案 config 明確設定。**現況**：本 repo 的 config 都沒設，clock 走 met1／met2；clock net 的 EM 只有估算（同上筆記：上界約 0.39 mA，met1 最小線寬上限 0.85 mA rms）。使用者 2026-10-15 選「本專案不設，下專案一開始就設 (建議)」（ADR-0021 決定 8）：本 repo 已結案、不下線，不設（設了要重新 harden 三個設計、更新 golden 並重跑 regress）；**新專案的 config 第一版就明確設 `RT_CLOCK_MIN_LAYER`**（sky130 用 PDK 原意的 `met3`），第一次 harden 後看 `resolved.json` 確認不是 null。
   - **怎麼防止再發生：沒有自動檢查**。原因：沒有 checker 比對 PDK 設定與 `resolved.json`，要新寫，依 ADR-0021 決定 3、8 在下一個專案開始時做：`resolved.json` 的 `RT_CLOCK_MIN_LAYER` 是 null 就 FAIL，加植入錯誤（config 拿掉這個設定）。LibreLane 升版時重看 `resolved.json` 的這個值。
9. **duty cycle**：clock tree 本身造成的 rise／fall 延遲差（nom_ss 下 SRAM `clk0` 約 0.30 ns），STA 已經算到；clock 來源本身的 duty 偏差 STA 不知道，要靠 constraint（`signoff-criteria`）。
10. **CTS 會把 macro 的 clock 延到與 flip-flop 一樣晚**（latency 對齊）：soc_top 的 `sram0/clk0` 前面被插了一串 delay buffer（`delaybuf_*`，Phase 4 是 10 顆）。各項數字在 ADR-0016 與 `pnr/soc_top/README.md` 設定表，這裡只寫機制。
    - 後果一，SRAM 輸入腳的 hold 變差：SRAM .lib 的 hold 要求是保守的下限（ADR-0007、ADR-0010），post-CTS 修到正值，繞線後在 min_ff_n40C 變負（Phase 4 第 2、3 次 harden-soc）。當時用 `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 補（`drv-timing-closure` 規則 7，放寬清單 T16）。
    - 後果二，SRAM 在 falling edge launch 的半週期路徑變差：這串 `clkbuf_16` 的下降緣比上升緣慢，累積起來 SRAM clock 的下降緣 latency 比上升緣晚約 1 ns（min_ss_n40C，ADR-0016），半週期 setup 用的正是下降緣。
    - 後果三，SRAM 讀出的 hold 變差：hold 用上升緣，SRAM 的 clock 比讀出 flop 早，每條 `dout` 要插 hold delay cell，這些 cell 在 ss_n40C 再吃掉 setup（規則 12；Phase 5 PicoRV32 因此 setup FAIL，ADR-0016）。
    - **`CTS_DELAY_BUFFER_DERATE_PCT` 管不到這一步**：設 0 或 1，結果與預設完全相同，仍是 10 顆。
    - **關掉的方法**：`clock_tree_synthesis -no_insertion_delay`（OpenROAD `dcf36133`：`balanceMacroRegisterLatencies()` 只在 insertion delay 開啟時執行，而 `clock_tree_synthesis` 每次呼叫都把它重新打開，只有這個旗標能關）。LibreLane 3.0.14 的 `cts.tcl` 沒有對應的設定，本 repo 用 LibreLane plugin 換掉 CTS step（`pnr/librelane_plugin_arvinsa`，config `meta.substituting_steps`；ADR-0016）；不要為此改 LibreLane 本身，也不要把改工具行為的 Tcl 放進 SDC。關掉之後半週期 setup 改善、SRAM 輸入腳的 hold 變小，要確認仍為正（ADR-0016 的前後比較）。
    - **自動檢查**：`check_soc.py cts_macro_latency` 每次 harden 確認 config 有替換、log 有 plugin 印的那一行、netlist 沒有 `delaybuf_*`（negative test P52–P54）。
      **主要判斷是結構，不是名稱**（Phase 5 獨立審查後改）：從 `sram0/clk0` 往上數「只驅動下一級的 clock buffer」連續幾級，上限 2。有做 latency 對齊的兩個 run 是 11、12 級，沒做的是 0 級。
      - 名稱判斷的漏洞：把 `delaybuf_` 改名成別的名字就 PASS（P58）。
      - **比 clock tree 的總級數分不出來**：對齊就是讓 SRAM 的延遲等於 flip-flop，插的 delay buffer 取代了 tree 的級數，總級數一樣是 12。
      - step 目錄要容許 `-<n>` 字尾（重複的 step），P59、P60。
      **升版時**，LibreLane 或 OpenROAD 都要重看：`cts.tcl` 是否仍只呼叫一次 `clock_tree_synthesis`、這個旗標與 `balanceMacroRegisterLatencies()` 的條件是否還在、LibreLane 是否已經提供對應的設定（有的話改用設定，拿掉 plugin）。旗標沒傳到時，P53 的那一行會不見，`delaybuf_*` 也會回來。
11. **clock 輸入 pin 到 clock tree 根部的線**（接規則 4）：`CTS_CLK_MAX_WIRE_LENGTH` 預設 0，表示依 slew 算出來的長度，約 3.5 mm，所以 360 µm 的線不會被切開插 buffer。pin 的 driver 是 LibreLane 假設的 `inv_2`（`SYNTH_CLK_DRIVING_CELL` 預設），max_ss_n40C 的 slew 0.767 ns，超過 0.75 ns（Phase 4 第 4 次 harden-soc）。
    - 設定方式：`CTS_CLK_MAX_WIRE_LENGTH` 設一個長度（本 repo 150 µm），LibreLane `cts.tcl` 的 `repair_clock_nets` 依它把線切成幾段、插 buffer（讀原始碼得知）。
    - 效果沒有單獨實驗：第 5 次 harden 同時改了週期與 max transition，15 個 corner 全部通過，分不出是哪一項的作用。
12. **setup／hold 先從 clock 端找原因，再在 data 端補 delay**（後段常見的作法；ADR-0016 是一個實例）：
    - 先把違規路徑的 launch 與 capture clock latency 拆開看（`report_checks -format full_clock_expanded`），而且 setup 與 hold 各看一次、每個相關 corner 都看：兩端的 clock 差是否隨 corner 變號、上升緣與下降緣的 latency 是否差很多（半週期路徑 setup 用一個邊緣，hold 用另一個）。
    - 在 data 端補 hold 很貴：sky130 的 delay cell 與 buffer，ss_n40C 延遲是 ff_n40C 的 2.5–3.3 倍。ff 缺 0.3 ns，ss 的 setup 就付約 1 ns；OpenROAD 整顆晶片只用一種 hold buffer（hold 延遲 ÷ 面積最高的，sky130 是 `dlygate4sd3_1`），換成小 cell 會插好幾倍的數量（`drv-timing-closure` 經驗紀錄，`RSZ-0060`）。
    - 調 hold margin 或不讓 resizer 動某些 net，只會把 delay cell 換位置（同經驗紀錄的實驗 A、B）。
    - 一條 hold 違規若來自 clock 結構（macro latency 對齊、上升／下降緣不對稱、長線），先改 clock tree，再讓 resizer 補剩下的。
13. **第一次帶 macro 的 harden 就檢查 macro 的 clock 結構；flow 的變數關不掉某個工具行為時，查到底層工具的指令選項**（提早檢查 D4，流程回顧 ADR-0020；流程文件 4.6）。
    - 為什麼：Phase 4 就看到規則 10 的 10 顆 delay buffer，當時認定「LibreLane 沒有設定可以關」，改用 hold margin 0.3 ns 補、列為已知限制；Phase 5 才查到 OpenROAD 的 `-no_insertion_delay`，從實驗到寫好 plugin 約 2 小時（ADR-0016）。這期間它造成 Phase 4 的 hold margin 0.3 ns、Phase 5 PicoRV32 harden FAIL 與四組實驗；Phase 3.5 的 42 → 43 ns 可能也有一部分來自它（回顧 `retro_p35_5.md` #5，推測，沒有在 42 ns 重跑）。修好之後，週期與 0.3 ns 都沒有回頭評估（記進放寬清單，`signoff-criteria`「提早檢查」E1）。
    - 做什麼：CTS 之後，看每個 macro clock pin 上方有沒有對齊 latency 用的 buffer 鏈（用規則 10 的結構判斷，不靠名稱）；報出 macro clock pin 的上升緣與下降緣 latency，和 capture 端 flip-flop 比；列出半週期路徑（規則 12 的拆法）。flow 的變數管不到時，讀 flow 呼叫的工具指令（LibreLane 的 Tcl）與工具的指令說明，找有沒有選項，再決定是不是真的沒辦法；有選項就用 plugin 換掉那一步（`librelane-run-debug`），不改 LibreLane 本身。
    - 通過條件：沒有預期外的、用來對齊 latency 的 delay buffer，或已記錄決定；半週期路徑兩個邊緣的 latency 差已列出。
    - 自動檢查：本 repo 的 `check_soc.py cts_macro_latency`（P52–P54、P58–P60）；新設計要從第一次帶 macro 的 harden 就啟用同類的結構 checker。「查到底層工具選項」是做法，沒有自動檢查。

## 待補

useful skew（刻意讓個別 flop 的 clock 提早或延後來借時間；OpenROAD 有相關功能，沒有試）；SRAM 有內部 clock 延遲時，用 .lib 的 clock tree path 讓 CTS 對齊到內部（insertion delay，沒有試）；週期縮短時的 CTS 設定（Phase 4 的 25 ns 只在同一份 layout 重跑 STA，沒有重做 CTS）。skew 在 golden 比對中的誤差是 ±0.01 ns，實際跑出來的差異 ≤ 0.0002 ns（`signoff-checker-qualification` 規則 5）。

## 用完後 / 經驗紀錄

用完把新現象加進下表；第二次出現或已用實驗確認就搬進規則。

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | `clk` port slew 0.919 ns（max_ss） | 已驗證：pin 在左下角，到 `clkbuf_regs_0_clk` 約 660 µm | pin 移到下邊中段 | soc_explore4 無此違規 |
| 2026-10-03 | signoff 條件調查（核對 agent） | skew metric 含 uncertainty 與 derate；NDR half 的意義；`RT_CLOCK_MIN_LAYER` 沒有生效 | 已驗證（報告數字、`resolved.json`、DEF 統計） | 規則 6–9 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-04 | Phase 4 第 2、3 次 harden-soc | SRAM 輸入腳 hold 在 min_ff_n40C −0.088 ns；`CTS_DELAY_BUFFER_DERATE_PCT` 0 與 1 結果都與預設相同 | 已驗證：CTS 對齊 `sram0` 與 flip-flop 的 latency，插 10 顆 delay buffer | resizer hold margin 0.3 ns；規則 10；列為已知限制 | `pnr/soc_top/README.md` 設定表 |
| 2026-10-04 | Phase 4 第 4 次 harden-soc | `clk` pin 到第一顆 clock buffer 約 360 µm，max_ss_n40C slew 0.767 ns | 已驗證：預設依 slew 算出的分段長度約 3.5 mm，這段線沒有被切開 | `CTS_CLK_MAX_WIRE_LENGTH` 150（規則 11） | `pnr/soc_top/config.json` 註解 |
| 2026-10-05 | Phase 3.5 第 2 次 harden-soc | `sram0` → `rdata_q` 的 hold 檢查在 min_ss_n40C：`sram0/clk0` 2.78 ns、`rdata_q` 的 CLK 4.15 ns，差 1.37 ns（setup 時兩者只差 0.09 ns） | 推測（由 harden 3 的 min_ss_n40C 報告推算，harden 2 的報告已被覆蓋）：差值由兩部分組成，大約各半。一是比較的邊緣不同：setup 比的是 SRAM 的下降緣對 flop 的上升緣，hold 比的是兩邊的上升緣，SRAM clock 鏈的 rise／fall 差約 0.74 ns；二是 SRAM clock 那條 10 顆 delay buffer 的長鏈在 hold 分析取 early、flop 那側取 late，±5% OCV 約 0.7 ns（2026-10-05 獨立審查更正原本「只有 OCV」的說法） | 新的 SRAM hold arc 因此需要 delay cell；見 `drv-timing-closure` 同日紀錄 | ADR-0004 Phase 3.5 補充 |
| 2026-10-07 | Phase 5 第 5 次 harden-soc（Hazard3，44 ns） | 規則 10 的「後果二」成為最差 setup 路徑（PicoRV32 版 43 ns 的最差路徑也是這一類：`sram0` → `_21833_`，min_ss_n40C +0.384 ns）：`sram0` 在 falling edge launch → `_21021_`，min_ss_n40C slack +0.530 ns；`sram0/clk0` 3.80 ns、`_21021_/CLK` 3.13 ns，SRAM 晚 0.67 ns。Hazard3 版 SRAM clock 前插 9 顆 `delaybuf_*`（PicoRV32 版 10 顆）。另外 32 條 `sram_dout0` 各直接插 1 顆 hold buffer；PicoRV32 版的 hold buffer 插在 mux 之後、flop 的 D 之前（最差路徑上 `hold7854`，1.17 ns），不直接接在 `sram_dout0` 上。經過它的 hold slack min_ff_n40C +0.679 ns | 已驗證：路徑時序取自 signoff STA 報告與 OpenSTA 查詢。hold buffer 的來源是 ADR-0010 的 `rising_edge` arc；插在哪裡由 resizer 決定，兩個 CPU 不同的原因未查證 | 記錄；不處理（目前 PASS，規則 10 沒有可以關掉 delay buffer 的設定） | p5h3 worktree `runs/p5_h3_h5/57-openroad-stapostpnr/min_ss_n40C_1v60/max.rpt`、`runs/p5_h3_h5_signoff/criteria_review.md` |
| 2026-10-07 | Phase 5 PicoRV32 第 1 次 harden（`c976976`，44 ns）與接續實驗 D（p5h3 worktree `runs/exp_p_d`，從第 34 步接續到 `STAPostPNR`，13 分鐘） | 規則 10 的 10 顆 `delaybuf_*_clk`（`clkbuf_16`）：min_ss_n40C 每顆下降緣約 0.31、上升緣約 0.21 ns，SRAM `clk0` 下降緣 latency 3.81、上升緣 2.72 ns（ff 1.20／1.00）。半週期 setup 用下降緣（launch 變晚），讀出 hold 用上升緣（比讀出 flop 早 0.40 ns @ff），`sram_dout0` 32 條各插 1 顆 `dlygate4sd3_1`，signoff setup −0.113 ns | 已驗證：OpenROAD `dcf36133` `TritonCTS::balanceMacroRegisterLatencies()` 只在 insertion delay 開啟時執行；`clock_tree_synthesis` 每次呼叫都 `cts::set_insertion_delay true`，只有 `-no_insertion_delay` 能關；LibreLane 3.0.14 `cts.tcl` 沒有傳這個旗標的設定。實驗 D 用暫存 SDC（`PNR_SDC_FILE`，只在 `STEP_ID` 為 `OpenROAD.CTS` 時把 `clock_tree_synthesis` 包一層加上 `-no_insertion_delay`）：0 顆 delay buffer、`sram_dout0` 上 0 顆 hold buffer；signoff setup +0.765 ns（0 個違規），hold +0.079（flop 對 flop），SRAM 輸入腳 hold min_ff +0.197 → +0.093、setup 27 ns 以上；slew／cap／fanout 0 | Hazard3 同樣接續（`runs/exp_h_d`）：9 → 0 顆 delay buffer，setup +0.530 → +1.116 ns，hold +0.107 → +0.106，SRAM 輸入腳 hold +0.338 → +0.320。使用者決定用 repo 的 LibreLane plugin 換掉 CTS step（ADR-0016），規則 10、12 | `runs/exp_p_d/01-openroad-cts/openroad-cts.log`（`[EXP]` 行）、`runs/exp_h_d/` |
| 2026-10-08 | Phase 5 exit 的獨立審查；4 個 netlist（有做 latency 對齊的 `p5_h3_h8`、`p5_pico_h1`，沒做的兩個乾淨 regress） | `cts_macro_latency` 只認 `delaybuf_*`，改名後 PASS。比總級數：SRAM 12 級，flip-flop 最多 12 或 14 級，分不出來；比「只驅動下一級的 buffer 連續幾級」：11、12 對 0 | 已驗證：4 個 netlist 實際量過 | 規則 10 的 checker 改成結構判斷（上限 2），P58–P60 | `pnr/soc_top/check_soc.py sram_clock_chain` |
| 2026-10-10 | Phase 6 步驟 4b 第三輪（`ad184f5`，OpenRAM 產生的 SRAM，`clk1` 改接系統時脈） | ss −40°C 的 skew metric 大了 0.2–0.4 ns（PicoRV32 nom_ss_n40C hold −1.292 → −1.679、setup 0.936 → 1.168 ns），clock inverter 49 → 87（PicoRV32）、56 → 101（Hazard3）；最差 setup／hold 仍 PASS | 推測：`clk1` 成為新的 clock sink；沒有分開做實驗 | 記入 golden README 與 Phase 6 已知限制 5，沒有改設定 | `signoff/golden/soc_top/README.md`、`soc_top_hazard3/README.md`「與 Phase 5 golden 的差異」 |
| 2026-10-14 | Phase 7 Caravel wrapper（`f721cff` 起的正式 harden，只在現有的 run 上分析，沒有改設定做實驗） | hold skew metric nom_ss_n40C −3.598 ns（soc_top −1.540），葉端 latency 9.4–11.4 ns | 推測（沒讀 OpenSTA 原始碼）：約 2.7 ns 是 `report_clock_skew -hold` 把 clock source latency 的上下限差（Caravel SDC 的 5.57／4.65 ns，0.92 ns）與共同路徑的 derate（0.44 ns）算成扣分；真正影響 hold 的 skew −0.632 ns（soc_top −0.678）。已量到的：`wb_clk_i` 從 wrapper 邊緣到 clock root 約 1.9 ns、6 顆 buffer（max_ss_n40C 5.57 → 7.67 ns），Caravel 輸入路徑因此多了至少 312 顆 hold buffer | 沒改 checker；`review_criteria` 不要把 skew metric 當品質指標；下一顆設計讓 CTS root 靠近 clock 腳位（沒試）；列入 Phase 7 已知限制 | `runs/p7_skew_analysis/README.md`；`docs/phase_exit/phase7.md` |
| 2026-10-15 | ADR-0021 的修正（A6），讀原始碼 | 規則 8 的 `RT_CLOCK_MIN_LAYER`：PDK 的 `~/.ciel/sky130A/libs.tech/openlane/config.tcl` 第 158 行設 `met3`，LibreLane 的 `set_routing_layers.tcl` 第 20–21 行只在環境變數存在時使用 | 推測（只讀原始碼，沒有實驗）：LibreLane `librelane/steps/common_variables.py` 第 331 行宣告它時沒有 `pdk=True`（同檔其他 PDK 變數有），所以 PDK 的值沒讀進來 | 規則 8 補「怎麼發現」與「沒有自動檢查」；要不要在 config 設定交使用者決定 | `.tools/librelane/librelane/steps/common_variables.py`、`.../scripts/openroad/common/set_routing_layers.tcl` |
