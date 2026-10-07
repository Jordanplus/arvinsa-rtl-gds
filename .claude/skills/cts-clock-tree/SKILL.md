---
name: cts-clock-tree
description: Clock tree（CTS）問題，或 setup／hold 違規可能是 clock 造成時使用：clock buffer 的 fanout／cap 違規、skew（metric 含 uncertainty 與 derate）、clock 輸入 pin 到第一級 clock buffer 的長線 slew（`CTS_CLK_MAX_WIRE_LENGTH`）、clock pin 擺放、CTS 把 macro 的 clock 延到與 flip-flop 對齊（`delaybuf_*`，關掉用 `-no_insertion_delay` 與 LibreLane plugin）造成 macro 輸入 hold、SRAM 半週期 setup 與讀出 hold 變差、hold delay cell 在慢 corner 吃掉 setup、先拆 launch／capture clock latency 再決定在 clock 端或 data 端修。資料路徑的 DRV 看 drv-timing-closure。Use for CTS problems and clock-caused setup/hold violations (skew, macro clock latency balancing, rise/fall latency asymmetry on half-cycle paths) in OpenROAD/LibreLane.
---

# Clock tree（CTS）

資料路徑的 DRV 看 `drv-timing-closure`。目前經驗較少，邊用邊補。本 repo 實例：`pnr/picorv32_core/README.md`（試跑 #8、#9）、`pnr/soc_top/pin_order.cfg`、`pnr/soc_top/README.md` 的設定表（Phase 4）。

## 規則（已驗證）

1. `CTS_SINK_CLUSTERING_SIZE 8`：預設每顆末端 buffer 帶 10 顆 flop，之後加 dummy load（`clkload*`），fanout 變 11–12。
2. `CTS_DISTANCE_BETWEEN_BUFFERS 50`：H-tree 中段沒放 buffer 時，第 2 層一顆 buffer 帶 16 顆下游 buffer（fanout 16、cap 0.206 pF）；設 50 µm 後最大 fanout 9。
3. 沒有作用：`CTS_MAX_CAP`（CTS 後 DEF 逐 byte 相同）；`CTS_SINK_CLUSTERING_SIZE 9`（反而分成更多群）。
4. **clock 輸入 port**：pin 到第一級 clock buffer 的線不在 resizer 修復範圍內（clock net）。pin 在左邊最下方時，660 µm 的線在 ss slew 0.92 ns；移到 flip-flop 重心附近的下邊中段後消失（soc_explore2 → 4）。
5. `clkload*` 的輸出不接東西，會出現在 STA 的 unannotated 清單，屬正常（見 `signoff-checker-qualification` 規則 4）。
6. **skew 的 metric 不是 skew 本身**：`clock__skew__worst_*` 與 `report_clock_skew` 都含 clock uncertainty（0.25 ns），也含 ±5% derate（launch 用 late、capture 用 early）。soc_top nom_tt 的 metric 是 0.93 ns：扣掉 uncertainty 後 0.68 ns，再扣掉 derate 的名目值約 0.51 ns（推算）。
7. **`CTS_APPLY_NDR` 的 `half`**：只在 clock tree 的前半層套用 non-default rule（OpenROAD `src/cts/README.md`），不是「leaf 以外全部」。sky130 的 CTS NDR 是 2 倍間距，線寬沒有加大。
8. **PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒有生效**：`resolved.json` 為 None。soc_top 的 clock 繞線段：met1 9750、met2 2901、met3 90、met4 7。要讓 clock 走粗金屬，必須在專案 config 明確設定。
9. **duty cycle**：clock tree 本身造成的 rise／fall 延遲差（nom_ss 下 SRAM `clk0` 約 0.30 ns），STA 已經算到；clock 來源本身的 duty 偏差 STA 不知道，要靠約束（`signoff-criteria`）。
10. **CTS 會把 macro 的 clock 延到與 flip-flop 一樣晚**（latency 對齊）：soc_top 的 `sram0/clk0` 前面被插了 10 顆 delay buffer（`delaybuf_*`）。
    - 後果一，SRAM 輸入腳的 hold 變差：SRAM .lib 要求 0.5 ns（ADR-0007 的值，ADR-0010 沿用為下限；實測 TT 為 0.20–0.24 ns）。post-CTS 的 hold 修到 +0.100 ns，繞線後在 min_ff_n40C 變成 −0.088 ns（Phase 4 第 2、3 次 harden-soc）。後來用 `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 補過去（`drv-timing-closure`）。
    - 後果二，SRAM 下降緣送出的半週期路徑變差：這串 `clkbuf_16` 的下降緣比上升緣慢（min_ss_n40C 每顆約 0.31 對 0.21 ns，10 顆加上 tree 共差 1.08 ns），半週期 setup 用的正是下降緣。
    - 後果三，SRAM 讀出的 hold 變差：hold 用上升緣，SRAM 比讀出 flop 早（min_ff 0.40 ns），每條 `dout` 要插 hold delay cell，在 ss_n40C 每顆再吃掉 1.1–1.4 ns 的 setup（規則 12）。PicoRV32 44 ns：setup −0.113 ns。
    - **`CTS_DELAY_BUFFER_DERATE_PCT` 管不到這一步**：設 0 或 1，結果與預設完全相同，仍是 10 顆。
    - **關掉的方法**：`clock_tree_synthesis -no_insertion_delay`（OpenROAD `dcf36133`：`balanceMacroRegisterLatencies()` 只在 insertion delay 開啟時執行，而 `clock_tree_synthesis` 每次呼叫都把它重新打開，只有這個旗標能關）。LibreLane 3.0.14 的 `cts.tcl` 沒有對應的設定，本 repo 用 LibreLane plugin 換掉 CTS step（`pnr/librelane_plugin_arvinsa`，config `meta.substituting_steps`；ADR-0016）；不要為此改 LibreLane 本身，也不要把改工具行為的 Tcl 放進 SDC。PicoRV32 接續實驗：0 顆 delay buffer，setup −0.113 → +0.765 ns，hold 不變，SRAM 輸入腳 hold +0.197 → +0.093 ns（要確認仍為正）。
    - **防護**：`check_soc.py cts_macro_latency` 每次 harden 確認 config 有替換、log 有 plugin 印的那一行、網表沒有 `delaybuf_*`（negative test P52–P54）。LibreLane 或 OpenROAD 升版時要重看：`cts.tcl` 是否仍只呼叫一次 `clock_tree_synthesis`、這個旗標與 `balanceMacroRegisterLatencies()` 的條件是否還在、LibreLane 是否已經提供對應的設定（有的話改用設定，拿掉 plugin）。旗標沒傳到時，P53 的那一行會不見，`delaybuf_*` 也會回來。
11. **clock 輸入 pin 到 clock tree 根部的線**（接規則 4）：`CTS_CLK_MAX_WIRE_LENGTH` 預設 0，表示依 slew 算出來的長度，約 3.5 mm，所以 360 µm 的線不會被切段。pin 的 driver 是 LibreLane 假設的 `inv_2`（`SYNTH_CLK_DRIVING_CELL` 預設），max_ss_n40C 的 slew 0.767 ns，超過 0.75 ns（Phase 4 第 4 次 harden-soc）。
    - 設 150 µm 後，CTS（LibreLane `cts.tcl` 的 `repair_clock_nets`）會把這段線切開加 buffer。
    - 第 5 次 harden 同時改了週期與 max transition，15 個 corner 全部通過；這一項的效果沒有單獨實驗。
12. **setup／hold 先從 clock 端找原因，再在 data 端補 delay**（後段常見的作法；ADR-0016 是一個實例）：
    - 先把違規路徑的 launch 與 capture clock latency 拆開看（`report_checks -format full_clock_expanded`），而且 setup 與 hold 各看一次、每個相關 corner 都看：兩端的 clock 差是否隨 corner 變號、上升緣與下降緣的 latency 是否差很多（半週期路徑 setup 用一個邊緣，hold 用另一個）。
    - 在 data 端補 hold 很貴：sky130 的 delay cell 與 buffer，ss_n40C 延遲是 ff_n40C 的 2.5–3.3 倍。ff 缺 0.3 ns，ss 的 setup 就付約 1 ns；OpenROAD 整顆晶片只用一種 hold buffer（hold 延遲 ÷ 面積最高的，sky130 是 `dlygate4sd3_1`），換成小 cell 會插好幾倍的數量（`drv-timing-closure` 經驗紀錄，`RSZ-0060`）。
    - 調 hold 餘量或不讓 resizer 動某些 net，只會把 delay cell 換位置（同經驗紀錄的實驗 A、B）。
    - 一條 hold 違規若來自 clock 結構（macro latency 對齊、上升／下降緣不對稱、長線），先改 clock tree，再讓 resizer 補剩下的。

## 待補

useful skew（刻意讓個別 flop 的 clock 提早或延後來借時間；OpenROAD 有相關功能，沒有試）；SRAM 有內部 clock 延遲時，用 .lib 的 clock tree path 讓 CTS 對齊到內部（insertion delay，沒有試）；週期縮短時的 CTS 設定（Phase 4 的 25 ns 只在同一份版圖重跑 STA，沒有重做 CTS）。skew 在 golden 比對中的誤差是 ±0.01 ns，實測差異 ≤ 0.0002 ns（`signoff-checker-qualification` 規則 5）。

## 用完後 / 經驗紀錄

用完把新現象加進下表；第二次出現或已用實驗確認就搬進規則。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | `clk` port slew 0.919 ns（max_ss） | 已驗證：pin 在左下角，到 `clkbuf_regs_0_clk` 約 660 µm | pin 移到下邊中段 | soc_explore4 無此違規 |
| 2026-10-03 | signoff 條件調查（核對 agent） | skew metric 含 uncertainty 與 derate；NDR half 的意義；`RT_CLOCK_MIN_LAYER` 沒有生效 | 已驗證（報告數字、`resolved.json`、DEF 統計） | 規則 6–9 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-04 | Phase 4 第 2、3 次 harden-soc | SRAM 輸入腳 hold 在 min_ff_n40C −0.088 ns；`CTS_DELAY_BUFFER_DERATE_PCT` 0 與 1 結果都與預設相同 | 已驗證：CTS 對齊 `sram0` 與 flip-flop 的 latency，插 10 顆 delay buffer | resizer hold 餘裕 0.3 ns；規則 10；列為已知限制 | `pnr/soc_top/README.md` 設定表 |
| 2026-10-04 | Phase 4 第 4 次 harden-soc | `clk` pin 到第一顆 clock buffer 約 360 µm，max_ss_n40C slew 0.767 ns | 已驗證：預設的切段長度約 3.5 mm，這段線沒有被切 | `CTS_CLK_MAX_WIRE_LENGTH` 150（規則 11） | `pnr/soc_top/config.json` 註解 |
| 2026-10-05 | Phase 3.5 第 2 次 harden-soc | `sram0` → `rdata_q` 的 hold 檢查在 min_ss_n40C：`sram0/clk0` 2.78 ns、`rdata_q` 的 CLK 4.15 ns，差 1.37 ns（setup 時兩者只差 0.09 ns） | 推測（由 harden 3 的 min_ss_n40C 報告推算，harden 2 的報告已被覆蓋）：兩個成分大約各半。一是比較的邊緣不同：setup 比的是 SRAM 的下降緣對 flop 的上升緣，hold 比的是兩邊的上升緣，SRAM clock 鏈的 rise／fall 差約 0.74 ns；二是 SRAM clock 那條 10 顆 delay buffer 的長鏈在 hold 分析取 early、flop 那側取 late，±5% OCV 約 0.7 ns（2026-10-05 獨立審查更正原本「只有 OCV」的說法） | 新的 SRAM hold 弧因此需要 delay cell；見 `drv-timing-closure` 同日紀錄 | ADR-0004 Phase 3.5 補充 |
| 2026-10-07 | Phase 5 第 5 次 harden-soc（Hazard3，44 ns） | 規則 10 的「後果二」成為最差 setup 路徑（PicoRV32 版 43 ns 的最差路徑也是這一類：`sram0` → `_21833_`，min_ss_n40C +0.384 ns）：`sram0` 下降緣送出 → `_21021_`，min_ss_n40C slack +0.530 ns；`sram0/clk0` 3.80 ns、`_21021_/CLK` 3.13 ns，SRAM 晚 0.67 ns。Hazard3 版 SRAM clock 前插 9 顆 `delaybuf_*`（PicoRV32 版 10 顆）。另外 32 條 `sram_dout0` 各直接插 1 顆 hold buffer；PicoRV32 版的 hold buffer 插在 mux 之後、flop 的 D 之前（最差路徑上 `hold7854`，1.17 ns），不直接接在 `sram_dout0` 上。經過它的 hold slack min_ff_n40C +0.679 ns | 已驗證：路徑時序取自 signoff STA 報告與 OpenSTA 查詢。hold buffer 的來源是 ADR-0010 的 `rising_edge` 弧；插在哪裡由 resizer 決定，兩個 CPU 不同的原因未查證 | 記錄；不處理（目前 PASS，規則 10 沒有可以關掉 delay buffer 的設定） | p5h3 worktree `runs/p5_h3_h5/57-openroad-stapostpnr/min_ss_n40C_1v60/max.rpt`、`runs/p5_h3_h5_signoff/criteria_review.md` |
| 2026-10-07 | Phase 5 PicoRV32 第 1 次 harden（`c976976`，44 ns）與接續實驗 D（p5h3 worktree `runs/exp_p_d`，從第 34 步接續到 `STAPostPNR`，13 分鐘） | 規則 10 的 10 顆 `delaybuf_*_clk`（`clkbuf_16`）：min_ss_n40C 每顆下降緣約 0.31、上升緣約 0.21 ns，SRAM `clk0` 下降緣 latency 3.81、上升緣 2.72 ns（ff 1.20／1.00）。半週期 setup 用下降緣（送出變晚），讀出 hold 用上升緣（比讀出 flop 早 0.40 ns @ff），`sram_dout0` 32 條各插 1 顆 `dlygate4sd3_1`，signoff setup −0.113 ns | 已驗證：OpenROAD `dcf36133` `TritonCTS::balanceMacroRegisterLatencies()` 只在 insertion delay 開啟時執行；`clock_tree_synthesis` 每次呼叫都 `cts::set_insertion_delay true`，只有 `-no_insertion_delay` 能關；LibreLane 3.0.14 `cts.tcl` 沒有傳這個旗標的設定。實驗 D 用暫存 SDC（`PNR_SDC_FILE`，只在 `STEP_ID` 為 `OpenROAD.CTS` 時把 `clock_tree_synthesis` 包一層加上 `-no_insertion_delay`）：0 顆 delay buffer、`sram_dout0` 上 0 顆 hold buffer；signoff setup +0.765 ns（0 個違規），hold +0.079（flop 對 flop），SRAM 輸入腳 hold min_ff +0.197 → +0.093、setup 27 ns 以上；slew／cap／fanout 0 | Hazard3 同樣接續（`runs/exp_h_d`）：9 → 0 顆 delay buffer，setup +0.530 → +1.116 ns，hold +0.107 → +0.106，SRAM 輸入腳 hold +0.338 → +0.320。使用者決定用 repo 的 LibreLane plugin 換掉 CTS step（ADR-0016），規則 10、12 | `runs/exp_p_d/01-openroad-cts/openroad-cts.log`（`[EXP]` 行）、`runs/exp_h_d/` |
