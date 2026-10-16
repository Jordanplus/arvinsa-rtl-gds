---
name: caravel-user-project-integration
description: 把設計放進 ChipFoundry Caravel 的 user_project_wrapper（2920 × 3520 µm，固定 DEF 範本 `FP_DEF_TEMPLATE`）時使用。症狀：`[WARNING PDN-0239] Ring shape falls outside the die bounds.`、`[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（範本本來就畫到 die 外，不要改）；precheck 的 `klayout_met_min_ca_density` 報 `li1.pd.1d`（0.4 min li1 ca pattern density，PDK 預設 `decap_3` 填滿空白）；`gpio_defines` 範本全是 `GPIO_MODE_INVALID`；Caravel 輸入腳位的 max slew 違規與 IO 路徑的 hold；韌體寫 `reg_mprj_xfer`（GPIO 設定傳送）後 user 輸出腳沒訊號、下拉消失，拉 `resetb` 救不回。涵蓋先定 block 位置再選 GPIO（0–14 右緣、15–23 上緣、24–37 左緣，Wishbone 在下緣靠左）、`wb_clk_i` 是管理用 CPU 的時脈、vccd1／vssd1 各只有一顆右側 pad 與 IR 的起算點、metal fill 由誰補與 `check_density.py` 的密度下限（`generate_fill`）、採用官方 wrapper SDC 前試算 input transition 與 IO 路徑的 hold、GPIO 設定傳送前寫回 user mode 的腳、下線規定對照表。precheck 的執行與結果判讀看 tapeout-precheck-caravel；pad、block、pin 的規劃與核准看 chip-floorplan-pin-planning。Use for integrating a design into the Caravel user_project_wrapper (fixed template, GPIO modes and transfer, power entry, li1 density, fill minimums, boundary SDC).
---

# 放進 Caravel user_project_wrapper

2026-10-15 從 `tapeout-precheck-caravel` 拆出（ADR-0021 決定 5）。這裡是設計放進 wrapper 的做法；precheck 怎麼跑、結果怎麼判斷看 `tapeout-precheck-caravel`；pad、block、pin 的規劃文件、核准與 checker 看 `chip-floorplan-pin-planning`（`CLAUDE.md` 規則 14）；IR 的檢查方式看 `pdn-ir-drop`；wrapper 的 IO constraint 寫法看 `timing-constraints-sdc` 規則 14、15。本 repo 實例：ADR-0019、ADR-0022、`pnr/user_project_wrapper/`、`docs/notes/caravel_precheck_phase7.md`、`docs/notes/caravel_gpio_xfer.md`、`docs/notes/caravel_reset_and_mgmt_clock.md`。

名詞：
- **Caravel**：ChipFoundry（2025 年接手 Efabless 的 sky130 共乘下線）的 harness 晶片。pad、電源與一顆管理用的 RISC-V 都做好了，使用者的設計放在 `user_project_wrapper` 裡。
- **precheck**：ChipFoundry 收件前的自動檢查。現在是 pip 套件 `cf-precheck`，由 `cf` 指令（pip 套件 `chipfoundry-cli`）用 Docker 呼叫。
- **flat 方式**：CPU 的 standard cell 與 SRAM macro 直接放在 wrapper 層繞線，不先把 SoC harden 成 macro（`project-plan.md` §5.5）。官方範例都是先 harden 成 macro。

## 規則（已驗證）

1. **先定 block 位置，再選 GPIO**（原 `tapeout-precheck-caravel` 規則 5；使用者 2026-10-12：「block擺放位置應該在後段開始前就應該先確認之後出pin決定好」）。Caravel 的 pad 與 wrapper 腳位位置都固定（`xor` 檢查 die 外那圈），能選的只有用哪幾支 GPIO、接什麼訊號、什麼模式，訊號也可以改走 logic analyzer 或 Wishbone。順序：
   - 依有時序要求的介面定 block 位置：Wishbone（含 `wb_clk_i`、`wb_rst_i`）與 logic analyzer 在下緣靠左 x = 0–870 µm；
   - 再依範本 DEF 的座標挑最近的 GPIO：0–14 在右緣（0–4 系統保留），15–23 在上緣，24–37 在左緣由上往下，37 在 y = 162 µm；
   - 最後才寫 wrapper RTL 的腳位對應與 `user_defines.v`。
   - 規劃文件、使用者核准、checker 與 hook 的做法在 `chip-floorplan-pin-planning`（ADR-0019 決定 13）。
2. **`wb_clk_i` 是管理用 CPU 的核心時脈**（原 `tapeout-precheck-caravel` 規則 6）：Caravel `verilog/rtl/caravel_clocking.v` 第 93–94 行，開機時是外部時脈 `ext_clk`（duty 由板子的振盪器決定），firmware 啟用 PLL 後是 `clock_div` 除頻的輸出（設計成 50% duty；除數 0 時直通 PLL）。所以：
   - 設計用 `wb_clk_i` 時，設計的週期就是管理端時脈的下限，要寫成使用限制（測試 firmware、板子）。本 repo：44 ns，管理端不能超過 22.7 MHz（ADR-0019 決定 15）。
   - duty cycle 與 jitter 沒有官方數字，`clock_uncertainty.sdc` 的假設要記成下線風險。
   - wrapper 的 IO constraint（clock source latency、Wishbone／LA delay、transition、負載）用 caravel_user_project 的 wrapper SDC 數值，做法與 OpenSTA 的 driving cell 陷阱看 `timing-constraints-sdc` 規則 14、15。
   - Phase 7 先在 RTL 選了 GPIO 8–20，到 floorplan 才發現離 block 2–3 mm，RTL、`user_defines.v`、testbench 與文件都要重做（ADR-0019 決定 10）。
3. **user area 的供電結構（vccd1／vssd1；CC2509，原始檔查證）**（原 `tapeout-precheck-caravel` 規則 7）：vccd1、vssd1 各只有一顆 pad，都在晶片右側（`def/chip_io.def` 第 17057、16653 行，換到 wrapper 座標約 y = 3290、1051）；電流經 Caravel 自己 5 µm 寬的 met4 ring，再由 `manual_power_connections` 的 met3 電源連接線接到 wrapper ring 的**左右兩側**（左 54、右 53 條，間距約 65 µm），上下兩邊沒有接點，caravel_core 的 PDN 不跨過 wrapper。所以：
   - wrapper 自己的電源 pin 不能當理想電源；IR 要把這段網路放進模型，電壓源放在 pad（本 repo `pnr/user_project_wrapper/ir_caravel.py` 與 `caravel_pwr/`，ADR-0019 決定 18）。壓降幾乎都在 pad 到 wrapper 邊緣的垂直傳導上，wrapper 內部只佔一小部分（本 repo 的分布在 ADR-0019 決定 18）。
   - 兩顆 pad 相距約 2.2 mm，block 放哪裡都至少離其中一顆遠，移 block 的改善有限。能改的是 wrapper 的 met4 strap（垂直方向與 Caravel ring 並聯）與電流本身（用 max power pattern 量，`pdn-ir-drop` 規則 12）。IR 用 slow corner 的 max power pattern 檢查，ff 電流加 ss 電阻的 worst-case 組合只當參考（ADR-0019 決定 19、20）。本 repo 移 block、改 met4 寬度與正式 run 的 IR 數字在 ADR-0019 決定 18–20。
   - 開新的 Caravel 設計時，在 pad 階段就照這條把供電結構列出來（`chip-floorplan-pin-planning` 規則 2）；Caravel 換版本時，用 `caravel_pwr/extract.py` 重抽、核對 blob hash。

4. **wrapper 頂層有標準 cell 時，空白區不能用 PDK 預設的 `decap_3` 填滿**（原 `tapeout-precheck-caravel` 規則 8；已驗證，2026-10-14，同一份設計只換 decap 的前後比較；ADR-0019 決定 24）：
   - **症狀**：precheck 的 `klayout_met_min_ca_density` FAIL，報表一堆 `li1.pd.1d`（「0.4 min li1 ca pattern density」）。每個帶 235/4 的 cell 各印一筆，其實是同一個整體數值；log 有 `li1_ca_density is <值>`，小於 0.4 就 FAIL（li1 超過 wrapper 面積的 60%）。
   - **原因**：`li1_ca_density = 1 − li1 面積 / 235/4 面積`，分母是整個 wrapper（10.28 mm²）。sky130 hd 的 `decap_3` 87% 是 li1，PDK 預設 `DECAP_CELL` 只有它；Fill Insertion 把空白全部填成 `decap_3` 時，本 repo 的 li1 75%。官方範例的 wrapper 只放 macro，關掉 fill（`RUN_FILL_INSERTION: false`），所以沒遇到。
   - **怎麼發現**：harden 後不用等 precheck，用 KLayout flat 算 li1（67/* 除 5、10、44，加 56/28）合併面積除以 235/4 合併面積，與 precheck 的計算方式相同（本 repo 兩份 layout 都對上 precheck 的值）；按 cell 拆就看得出是哪種 fill。
   - **怎麼繞過**：`DECAP_CELLS` 改 `sky130_ef_sc_hd__decap_12`（li1 52%），`FILL_CELLS` 加 `fill_8`、`fill_4`。timing、DRC、LVS 不變（Fill Insertion 在 detailed routing 之後），instance 與 harden 時間都大幅減少，precheck 的 BEOL 與 Magic 抽取也跑完了（同一天 VM 也加到 16 GiB，兩者沒有分開實驗，哪一個是必要的不知道；`tapeout-precheck-caravel` 規則 1）。本 repo 的前後數字（li1、instance 數、harden 時間）在 ADR-0019 決定 24。代價：`ef_decap_12` 沒有 .lib，漏電不進功耗報告（`signoff-criteria` knowledge S29）。只放 fill（li1 約 14%）會連邏輯旁的 decap 一起拿掉，而靜態 IR 看不到，不建議。li1 降低後還要過 tapeout 時的密度下限（li1 ≥ 35%，「待確認」的 fill 一項）。
   - **怎麼防止再發生**：`make precheck-caravel` 的 checker 要求 `klayout_met_min_ca_density` PASS；harden 時沒有自動檢查（要等 precheck 才抓得到，約 1 小時）。

### 提早檢查（流程回顧，ADR-0020，使用者決定）

2026-10-14 回顧（`docs/notes/flow_retro/retro_p6_7.md`）的結論之一：Phase 7 第一天的查證列出了 ChipFoundry 的檢查項目、密度上限與官方 SDC，但沒有套到自己的設計上算數字；單顆 vccd1 pad、IO pin 的 input transition 與 IO 路徑的 hold、li1 密度、precheck 那版 PDK 附的 SRAM、metal fill 誰補，全部在 harden 之後才發現，粗估重做約 2 天、3 項放寬。每項試算只要 10 分鐘到半天。使用者決定加下面三條（流程文件 4.1、4.5、4.6）。

5. **選定下線服務商時做下線規定對照表，需要對方回覆的問題當天送出**（原 `tapeout-precheck-caravel` 規則 9；提早檢查 A2）。
   - 做什麼：下線服務商 precheck 的每一項檢查（本專案是 ChipFoundry precheck 的 13 項）、wrapper 的 IO constraint（input transition、IO delay、clock source latency）、供電結構（pad 數量與位置，規則 3）、fill 由誰做與密度上下限（規則 4 與「待確認」的 fill 一項）、precheck image 的 PDK 與工具版本（`tapeout-precheck-caravel` 規則 1），逐條算出「對本設計是多少」，和本設計的 signoff 上限並排；版本不同的寫明以誰的結果為準，下線服務商會用到的 macro（例如 PDK 附的 SRAM）用它的 PDK 另取一份。需要下線服務商回覆的問題（已知 deck 問題、用 memory compiler 自己產生的 macro 的 Magic DRC 違規怎麼看、fill 誰做）在選定下線服務商當天送出，記下日期與回覆。
   - 通過條件：每一條有數字，或寫「待查，在哪一步查」；衝突在第一次 harden 前已列選項、由使用者決定；每個問題是「已送出（日期）」或「使用者決定不送（原話）」。
   - 為什麼：上面那段；本 repo 給 ChipFoundry 的 issue 到 Phase 7 結案仍是草稿，fill 也沒有書面確認，都列為下線前要做（ADR-0019 決定 26 與「後果」）。
   - 自動檢查：沒有（對照表與問題清單只是文件）。
6. **採用官方 wrapper SDC 時，第一次 harden 前先試算 input transition 與 IO 路徑的 hold**（原 `tapeout-precheck-caravel` 規則 10；提早檢查 C4）。
    - 做什麼：官方 SDC 的 input transition 和自己的 slew 上限並排比；用官方的 clock source latency（min／max）、min input delay 加上預估的 clock tree，算 IO 路徑的 hold 需要多少延遲，決定 hold margin 與 resizer 要看的 corner（`timing-constraints-sdc` 規則 14、15）。
    - 通過條件：有衝突的項目在 harden 前已列選項、由使用者決定。
    - 為什麼：官方 input transition 0.84–0.97 ns 超過本 repo 的 0.70／0.75 ns，`p7_floorplan4` netlist 上已量到 0.84 ns 卻沒拿去比，到試跑的 harden 才處理（ADR-0019 決定 14、16）；IO 路徑的 hold 在 ff 100°C −0.071 ns，官方 constraint 下 ff 要多延遲約 2.4 ns，多跑了 `p7_harden3`、`p7_harden4` 一輪（決定 17；經驗紀錄 2026-10-12）。試算約 10 分鐘到 1 小時（回顧推算）。
    - 自動檢查：沒有（IO pin 的 slew 在 harden 後由 `check_soc.py max_slew` 檢查，試算本身是人工）。

## 規則（已驗證，2026-10-15 問題總檢討後補寫，ADR-0021）

7. **Caravel 範本的 core ring 與腳位本來就畫到 die 外：`PDN-0239`、`GRT-0036` 是預期的警告，不要為了消警告改範本**（已驗證，2026-10-12，座標和官方範例 DEF 相同；原 `tapeout-precheck-caravel` 經驗紀錄 2026-10-12 兩列）。
   - 症狀：`OpenROAD.GeneratePDN` 報 `[WARNING PDN-0239] Ring shape falls outside the die bounds.`；global routing 起的每一步報 `[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（and 1000 similar warnings）。
   - 原因：core ring（4 組電源 × 2，寬 3.1 µm、offset 12.45 µm）最外到 x = −43.63 µm；固定範本 DEF 的腳位形狀一半在 die 外（例如 `io_oeb[0]` 在 x = 2921.2 µm、met3 從 −3.6 到 +3.6 µm，die 寬 2920 µm）。8 組 net 的 ring 座標與官方範例 `user_project_wrapper.def` 完全相同，官方範例的 precheck `xor` 是 PASS。
   - 怎麼發現：harden 的 metrics `flow__warnings__count:PDN-0239`、`flow__warnings__count:GRT-0036`；確認時把 ring 與腳位座標和 `pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def` 比。
   - 怎麼處理：不處理。改腳位或 ring 會讓 precheck 的 `xor` FAIL（die 外那圈要和官方空 wrapper 相同，見「待確認」的 `xor`）。
   - 怎麼防止再發生：wrapper 的 golden（`signoff/golden/user_project_wrapper/metrics.json`）記了這兩個警告的數量，`signoff/limits/user_project_wrapper.toml` 沒有把它們列為可有可無的 key，數量改變時 golden 比對會報；範本被改時 precheck 的 `xor` 會 FAIL。沒有逐座標比對 ring 與官方 DEF 的 checker。

## 規則（已驗證，2026-10-16 查證後補寫，ADR-0022）

8. **`user_defines.v` 設成 user mode 的每一支腳，management SoC 的韌體做 GPIO 設定傳送之前，都要先把 housekeeping 裡對應的暫存器寫回同樣的值；不需要傳送就不要傳送**（已驗證，2026-10-16：Caravel RTL 加本 repo 的 `user_defines.v` 與假的 management core，做前後比較的模擬；gate-level netlist 的 reset 值與 RTL 相同。使用者選「A：寫進文件與 skill (建議)」；ADR-0022、`docs/notes/caravel_gpio_xfer.md`）。
   - 名詞：GPIO 設定傳送是韌體寫 `reg_mprj_xfer` = 1（位址 `0x2600_0000`，Caravel `verilog/dv/caravel/defs.h` 第 66 行），housekeeping 把自己存的 38 支 pad 設定（`reg_mprj_io_<n>`）依序送進每支 pad 的控制電路，一次覆蓋全部 38 支。
   - **原因**：上電時每支 pad 用 `user_defines.v` 的值，但 housekeeping 自己存的那份 reset 值全是 management mode（Caravel `verilog/rtl/housekeeping.v` 第 1061–1072 行：GPIO 0、1、36、37 是 `0x1803`，3 是 `0x0801`，其他是 `0x0403`），而且只由 POR 重置（第 920–921、1031–1032 行）。韌體沒寫回的 user mode 腳，傳送後就變成 management mode。Caravel 的範例韌體是設好自己要用的腳就傳送（例如 `verilog/dv/caravel/mgmt_soc/uart/uart.c` 第 34–63 行），照著寫就會踩到。
   - **症狀**：傳送之後，user area 的輸出腳從晶片腳位消失；輸入腳仍送得到 user area，但 `user_defines.v` 設的下拉沒了，板子上沒接線的輸入會浮接（本 repo：`uart_tx`、`trap` 消失，`boot_mode` 失去下拉，boot ROM 的開機方式無法確定）。拉 `resetb` 不會恢復。
   - **怎麼發現**：repo 的 regression 看不到：`make regress-rtl-caravel` 的 testbench 直接拿 `user_project_wrapper` 當 DUT（`dv/tb/tb_soc.v` 第 114 行），沒有 management SoC 與 housekeeping。要讀 management SoC 的韌體：有寫 `reg_mprj_xfer` 的，逐支比對寫進 `reg_mprj_io_<n>` 的值和 `user_defines.v`，user mode 的每一支都要相同。晶片上，若 user 輸出腳量不到訊號、management SoC 從 LA 卻讀得到同一個訊號（本 repo 把 `uart_tx`、`trap` 也接到 LA，`rtl/caravel/user_project_wrapper.v` 第 170 行），可以排除 user 設計沒在跑，問題在 pad 設定。
   - **怎麼繞過**：
     - 韌體不需要改 pad 設定時，不要寫 `reg_mprj_xfer`。
     - 要傳送時，先把 user mode 的每一支寫回 `user_defines.v` 的值，再傳送。本設計 `reg_mprj_io_33`～`reg_mprj_io_37` 要寫的值在 `docs/notes/caravel_gpio_xfer.md`。
     - 已經傳錯時的恢復：重新上電；用正確的設定再傳一次；或用 bit-bang 模式把 `serial_resetn` 拉低一次（`reg_mprj_xfer` 依序寫 `0x2`、`0x6`、`0x0`；`housekeeping.v` 第 908–911、1137–1138 行），user mode 的腳就回到 user mode（模擬確認；依原始碼是 38 支全部回到開機預設）。bit-bang 不改 housekeeping 存的那份值（依原始碼，只有 POR 會重置），之後要再傳送仍要先寫回。拉 `resetb` 救不回來。
   - **怎麼防止再發生**：沒有自動檢查。原因：management SoC 的韌體不在 repo，repo 的 regression 也只模擬到 wrapper；2026-10-16 的 Caravel 模擬（`docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/`）是一次性的實驗，沒有接進 `make regress`。下一個要下線的 Caravel 專案再把這個實驗做成 self-checking 的 regression test，或用官方的全晶片模擬環境驗證（ADR-0022）。

## 待確認

### 已實跑 PASS，違反時會不會 FAIL 沒有實測

- `xor`（原始碼）：die（0–2920 × 0–3520 µm）外那一圈要和 caravel-lite 的空 wrapper 一樣，所以要用 `FP_DEF_TEMPLATE`（`openlane/user_project_wrapper/fixed_dont_change/user_project_wrapper.def`），core ring（寬 3.1 µm、offset 12.45 µm）不能改。
- `gpio_defines`：`verilog/rtl/user_defines.v` 的 GPIO 5–37 都要有值、不能是 `GPIO_MODE_INVALID`；範本全是 INVALID。
- `oeb`：CVC 在萃取 netlist 上追 `io_out`／`io_oeb` 的實際接線，和 GPIO 模式比；user output 模式要真的接 `io_out` 與 `io_oeb`。RTL 對了不代表 PASS。2026-10-14 本 repo 實跑 PASS（報表 `cvc.oeb.report` 逐支列出接線與模式，與 `user_defines.v` 一致）；接錯時會不會 FAIL 沒有實測。
- `klayout_met_min_ca_density` 的 met1–met4 ≤ 60%、met5 ≤ 76%：本 repo 都遠低於上限（m4 ca 0.73、m5 0.73），沒有遇過超標；li1 見規則 4，金屬密度的下限見下一節的 fill 一項。
- `xor`、`gpio_defines`：2026-10-14 本 repo 的 wrapper 實跑 PASS（`FP_DEF_TEMPLATE`、`user_defines.v` 照規則 1）；違反時會不會 FAIL 沒有實測。
- `FP_DEF_TEMPLATE` 已在本 repo 的 wrapper 正式使用（`pnr/user_project_wrapper/config.json`）。

### 還沒經實跑或 ChipFoundry 確認

- 官方範例的 flow 是 LibreLane 2.4.6（ChipFoundry fork `CI2511`）；LibreLane 3.0.14 支援 `FP_DEF_TEMPLATE`，舊的 `FP_PDN_*` 名稱會自動轉換。
- **metal fill 由誰補、補完之後的密度下限**（ADR-0019 決定 26 的查證與試跑；`docs/phase_exit/phase7.md` 已知限制 3；試跑紀錄在 main worktree 的 `runs/p7_review/fill_trial/README.md`，`runs/` 不進版控）。只做過一次，下線服務商那一側的做法是推論，所以放這裡、不放正式規則（`CLAUDE.md` 規則 3）。
  - 誰補：Efabless／ChipFoundry 在 tapeout 時對整顆 Caravel 補 metal fill（Caravel `Makefile` 的 `generate_fill`，`generate_fill.py` 用 `cif ostyle wafflefill(tiled)`）。Efabless 時代證據明確（efabless/caravel_user_project#169、efabless/mpw_precheck#141、efabless/caravel `27cbe49` `Makefile` 第 1138–1155 行）；ChipFoundry 沿用同一套腳本（chipfoundry/caravel `01fb61d`），但沒有文件明講（推論）。官方範例的 wrapper 關掉 fill（`RUN_FILL_INSERTION: false`，規則 4）。
  - 補完之後另有下限檢查 `check_density.py`：700 µm 的 window，li1 與金屬步進 350 µm、FOM 步進 70 µm；li1、met1–4 ≥ 35%、met5 ≥ 45%、FOM ≥ 33%，另看整顆平均。precheck 不跑這一項，只查上限（`klayout_met_min_ca_density`）。efabless/caravel#397 有全數位設計補完 fill 仍 FAIL。35%／45% 的出處是這支腳本，不是 sky130 PDK 的 periphery rules（ADR-0019 決定 26）。
  - 自己預估的方法：照 `generate_fill.py` 單獨補 wrapper（700 µm 區塊），再照 `check_density.py` 的 window 量（Magic `cif ostyle density`、`cif list cover`）。fill 很大時每個區塊分開量、再按 window 和 wrapper 相加，省記憶體；相加比一起量偏高（本 repo 實際量了一塊比對，700 µm 的 window 最多高 0.33 個百分點），對上限偏保守，對下限只有離下限不到這個差的 window 可能誤判。LibreLane nix-shell 的 Magic Tcl 沒有 `clock` 指令（`invalid command name "clock"`），計時改用 `exec date`。
  - 判斷不了的：die 右邊界與上邊界的 window（正式檢查用晶片座標，會含到 wrapper 外 Caravel 的區域）、ChipFoundry 實際的 fill 參數與版本、整顆晶片的平均。precheck 的 `met_min_ca_density` 報的 met4／met5 比只算 die 內的高 1.2–1.6 個百分點（推測：分母是 die 外框 `235/4`，分子含 die 外的電源環，沒有驗證）。
  - 本 repo 的結果：li1、met1–5 只剩 met2 一個 window 略低於下限，FOM 有 15 個 window 低於 33%，都在 SoC 與 SRAM 擠在一起的左下角；met4 最高的 window 貼近上限。數字在上面的試跑紀錄與 Phase 7 已知限制 3；要改善的方向是降低局部密度（沒試）。依使用者的選擇不自己加 fill，向 ChipFoundry 書面確認列為下線前要做（ADR-0019 決定 26）。
  - 自動檢查：沒有。下限檢查在 tapeout 才跑；harden 內的密度 checker 是 `tapeout-precheck-caravel` 規則 11 的待辦（ADR-0020 D5，下一個專案開始時做成 checker）。

## 用完後

1. 新的現象加進「經驗紀錄」，原因標明已驗證／推測。
2. 「待確認」的項目實跑或經下線服務商確認後搬進規則；同一現象出現兩次或用實驗確認才寫成規則（CLAUDE.md 規則 3）。
3. Caravel 換版本時，重抽供電結構（規則 3，`caravel_pwr/extract.py`）、重看 GPIO 位置與範本 DEF（規則 1、7），以及 housekeeping 的 GPIO 設定 reset 值與傳送方式（規則 8）。

## 經驗紀錄

2026-10-15 從 `tapeout-precheck-caravel` 的經驗紀錄搬來（ADR-0021 決定 5）。

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-12 | arvinsa-rtl-gds Phase 7 步驟 3–4 | 寫 wrapper RTL 時先選 GPIO 8–20（沒看位置），到 floorplan 才發現在右緣與上緣，離左下角的 block 2–3 mm；我原本用「慢速訊號加 buffer 就好」帶過 | 已驗證（範本 DEF 座標）；流程順序錯誤，使用者指出 | 改成 GPIO 33–37（左緣最下面）、`gpio_out` 只走 LA；RTL、`user_defines.v`、testbench 重做，regress-rtl caravel 30/30、neg 42/42；寫成規則 1（原 `tapeout-precheck-caravel` 規則 5） | ADR-0019 決定 10、12 |
| 2026-10-12 | `p7_floorplan4`（flat wrapper，跑到 global placement） | `OpenROAD.GeneratePDN` 報 `[WARNING PDN-0239] Ring shape falls outside the die bounds.` | 已驗證：Caravel 的 core ring（4 組電源 × 2，寬 3.1 µm、offset 12.45 µm）本來就畫到 die 外，最外到 x = -43.63 µm；8 組 net 的 ring 座標與官方範例 `user_project_wrapper.def` 完全相同，官方範例的 precheck XOR 是 PASS | 預期中的警告，不處理；之後 harden 的 checker 可以比對 ring 與官方 DEF 一致（還沒做） | ADR-0019；`runs/p7_floorplan4/21-openroad-generatepdn/` |
| 2026-10-12 | `p7_harden2`（wrapper 試跑的 harden） | 第 41 步 `RepairDesignPostGRT` 中止：`[ERROR RSZ-0074] failed to build tree from gloubal routes: found route to 1 pins, expected 0`，停在 `analog_io[9]` | 已驗證：沒接東西的 inout 腳位被 OpenROAD 同時算成 driver 和 load；官方範例沒開 `RUN_POST_GRT_DESIGN_REPAIR`，所以沒遇到 | `RSZ_DONT_TOUCH_RX` 設 `analog_io`；四項對策在 `librelane-run-debug` 已知陷阱 | `runs/p7_harden2/41-*` |
| 2026-10-12 | `p7_harden2` 第 38 步（hold 修完後的 STA） | tt corner 有 384 個 max slew 違規（soc_top 是 0）：`la_oenb`、`la_data_in` 各 128 支腳位、`wbs_adr_i`、`wbs_dat_i` 各 32 支，以及接在這兩組腳位上的第一顆 cell（64 個，多是 hold delay cell） | 已驗證：全部在 Caravel 直接驅動的 net 上，slew 是 Caravel SDC 給的 input transition（0.84–0.97 ns），超過本 repo 的上限 0.70／0.75 ns（ADR-0009）；官方範例的上限是 1.5 ns（`MAX_TRANSITION_CONSTRAINT`），所以不算違規。wrapper 內部修不掉 | 使用者決定「內部照舊，邊界另判」（ADR-0019 決定 16）：`check_soc.py max_slew` 只允許這些 pin，到 Caravel 的 transition + 0.05 ns；wrapper 的 `MAX_SLEW_VIOLATION_CORNERS` 改回預設；P80 | `runs/p7_harden2/38-*/checks.rpt` |
| 2026-10-12 | `p7_harden2`（wrapper 試跑的 harden）global routing 起的每一步 | `[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（and 1000 similar warnings） | 已驗證：固定範本 DEF 的腳位形狀一半在 die 外，例如 `io_oeb[0]` 在 x = 2921.2 µm、met3 從 −3.6 到 +3.6 µm，die 寬 2920 µm；官方設計就是這樣，precheck 的 `xor` 比的就是這圈 | 不用處理，不要為了消警告改腳位（會被 `xor` 抓） | `pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def` |
| 2026-10-12 | `p7_harden2` 第 51 步 `Odb.ReportDisconnectedPins` | `Found 327 disconnected pin(s), of which 0 are critical.`；soc_top 是 0，`check_soc.py disconnected` FAIL | 已驗證：全部是 wrapper 最上層沒用到的 Caravel 腳位：`analog_io` 29、`io_in` 35（用到的只有 GPIO 33／34／36）、`la_data_in`／`la_oenb` 各 128、`user_clock2`，加上沒有 cell 用到的 6 支電源腳位（只有 vccd1／vssd1 有 cell）；沒有 cell 的 pin 浮接 | `disconnected` 改成 wrapper 的檢查方式（`DESIGNS unused_ports`）：表上必須剛好是「不是 Wishbone、也不是 `pin_plan.toml` 輸入模式 GPIO 的輸入／inout 腳位」加「沒有 cell 用的電源腳位」，只在頂層、0 個 critical。四種植入錯誤（用到的輸入、cell pin、應該沒接的腳位被接上、critical 1）手動確認都 FAIL；正式 negative test 等 `neg_pnr` 支援 wrapper（步驟 8） | `pnr/soc_top/check_soc.py` |
| 2026-10-12 | `p7_harden2`（wrapper 試跑的 harden，從第 41 步接續後跑完） | signoff 只剩 1 條 hold 違規：`wbs_adr_i[4]` → `_21509_`，`max_ff_100C` −0.071、`max_ff_n40C` −0.043 ns；post-GRT 的 hold 修復修完估計 +0.058 ns | 已驗證（STA 報表）：官方 constraint 下 Caravel 輸入的 min input delay 0.79 ns 掛在 4.65 ns 的 latency，wrapper 暫存器在 5.57 ns 加內部約 2 ns 的 clock tree 取樣，ff 下資料要延遲約 2.4 ns；global routing 的估計對這條路徑樂觀約 0.1 ns。soc_top 沒有這類路徑 | `GRT_RESIZER_HOLD_SLACK_MARGIN` 0.2 ns（ADR-0019 決定 17）；試過把 ff_100C 加進 resizer 的 corner，`RepairDesignPostGRT` 壅塞失敗（`drv-timing-closure` 經驗紀錄）。驗證中（`p7_harden4`） | `runs/p7_harden2_out/attempt2_margin005/` |
| 2026-10-13 | `p7_harden2` layout 的 IR what-if（agent 讀 Caravel 原始碼、只重跑 IR 那一步） | 電壓源放在 wrapper ring 時 8.4 mV，加上 Caravel 的供電網路變成 104 mV（預設 toggle rate、worst-case 組合） | 已驗證（原始檔 blob hash 核對、對照組在 0.1% 內）：vccd1／vssd1 各一顆 pad、5 µm ring、met3 電源連接線只在左右兩側 | 規則 3（原 `tapeout-precheck-caravel` 規則 7）；met4 4.8 µm（決定 18）；改用 max power pattern、以 20 mV 為上限檢查（決定 20），p7_harden2 netlist、met4 4.8 µm 19.9 mV（40 ns 錄）| `pnr/user_project_wrapper/caravel_pwr/`、ADR-0019 決定 18–20 |
| 2026-10-15 | arvinsa-rtl-gds Phase 7 的 fill 試跑（第二輪 wrapper GDS，ADR-0019 決定 26） | precheck 只查密度上限；照 Caravel `generate_fill.py`（`wafflefill(tiled)`）單獨補 wrapper、照 `check_density.py` 量 700 µm 的 window：li1、met1–5 只剩 met2 一個 window 34.5%，FOM 15 個 window 低於 33%（最低 31.5%），都在 SoC 與 SRAM 擠在一起的左下角；met4 最高 59.7% 貼近上限。另外 precheck 的 `met_min_ca_density` 報的 met4／met5 比只算 die 內高 1.2–1.6 個百分點；LibreLane nix-shell 的 Magic Tcl 沒有 `clock` 指令（`invalid command name "clock"`） | 已驗證：fill 區塊分開量再相加，比一起量最多高 0.33 個百分點（實際量一塊比對）。推測：precheck 的分母是 die 外框（`235/4`），分子含 die 外的電源環 | 不自己加 fill；結果列為下線前要向 ChipFoundry 確認的項目。fill 很大（wrapper 1.2 GB）時每個區塊分開量再相加，省記憶體。只出現一次，不寫成規則；沒有自動檢查（下限檢查在 tapeout 才跑，ADR-0020 的 D5 留到下一個專案） | main worktree 的 `runs/p7_review/fill_trial/README.md`（腳本在同一目錄） |
| 2026-10-16 | arvinsa-rtl-gds Phase 7 結案後的查證（讀 Caravel 原始碼、gate-level netlist 與本 repo 的 SDC，沒有重跑） | ADR-0019 決定 8 寫 `wb_rst_i`「由管理用 SoC 在 `wb_clk_i` 下產生」，`caravel_io.sdc` 原本的註解（`76a5672` 第 22 行）也這樣寫；查證 Caravel 的 reset 實際怎麼產生、對 wrapper 有什麼影響 | (1) 已驗證（原始碼）：`wb_rst_i` 由 caravel_core 裡的 `caravel_clocking` 產生，是 3 顆 flop 的 reset synchronizer：POR、`resetb` pad、housekeeping 的 reset 暫存器或 SPI pass-through 任一個有效就立刻拉起（非同步）；全部放開後，在核心時脈的第 3 個下降緣放開；再經 `mgmt_protect` 反相成 `wb_rst_i`（Caravel `verilog/rtl/caravel_clocking.v` 第 51、101–112 行，`housekeeping.v` 第 254 行，`mgmt_protect.v` 第 232 行，`caravel_core.v` 第 410、444、531–534 行）。management SoC 只接收這個 reset，不產生它。(2) 已驗證（原始碼、SDC 與 STA 報表）：官方 SDC 的半週期 input delay（`pnr/user_project_wrapper/caravel_io.sdc` 第 27 行）由 STA 加在 clock source latency 上（同一個時脈的其他輸入也是這樣算，ADR-0019 第 74 行），對應「在下降緣放開」，所以 STA 只檢查放開；沒算到的是 reset 與時脈兩條路徑的延遲差，以及最多 2.2 ns 的 duty cycle 偏差（`pnr/soc_top/clock_uncertainty.sdc` 第 14、20 行的 duty 項只用在第 27–28 行的上升緣、下降緣交錯的路徑，`wb_rst_i` 參考上升緣，沒套到）。拉起是非同步的，STA 不檢查。(3) 已驗證（RTL）：`resetn = ~wb_rst_i` 也經組合邏輯接到 SRAM 的 `csb0`（`rtl/caravel/user_project_wrapper.v` 第 129 行，`rtl/bus/soc_bus.v` 第 229、241 行）。推論：reset 剛好在 CPU 寫 SRAM 時拉起，這筆寫入可能寫壞，`docs/spec/soc_spec.md` §4.9 的 RTL-RST-01（第 168 行）在晶片上不保證；本設計 reset 後韌體會重新載入 SRAM，沒有長期影響。(4) 已驗證（原始碼與 netlist）：pad 或 SPI 觸發的 reset 會把時脈選擇清回外部時脈；韌體已啟用 PLL 時，放開過程中核心時脈經一般的 `mux2_1` 切回 PLL（`verilog/gl/caravel_clocking.v` 第 386–393 行，RTL 第 55–66 行）。推論：切換時可能出現很短的時脈脈衝。(5) 推論：vccd1 比 Caravel 的 reset 晚上電時，wrapper 收不到 reset | 使用者 2026-10-16 選「B：修正＋紀錄影響 (建議)」：更正 ADR-0019 決定 8、14 的說法與 `caravel_io.sdc`、`rtl/caravel/wb_host_bridge.v` 的註解，`docs/spec/soc_spec.md` §4.9 加註記，行為與影響記進 ADR-0022 與筆記。不重新 harden：signoff 的 setup／hold 違規數都是 0，粗估 `wb_rst_i` 放開這條路徑的 slack 約 19–21 ns（推測）。下一個專案建議在 wrapper 內對 `wb_rst_i` 加 2 顆 flop 的同步器，讓拉起也變成同步的（業界常見做法；本專案不做）。推論沒有寫進正式規則（`CLAUDE.md` 規則 3）；沒有自動檢查（RTL 模擬是零延遲，模擬不出非同步拉起的問題） | `docs/notes/caravel_reset_and_mgmt_clock.md`、ADR-0022；Caravel 原始碼在 `.tools/caravel-lite/verilog/`（不進版控） |
| 2026-10-16 | arvinsa-rtl-gds Phase 7 結案後的查證（scratch 模擬：Caravel RTL＋本 repo 的 `user_defines.v`＋假的 management core；另讀 gate-level netlist） | 查證 management SoC 的韌體做 GPIO 設定傳送（`reg_mprj_xfer`）對 GPIO 33–37 的影響。只設 management UART 用的 GPIO 5、6 就傳送：`uart_tx`（37）、`trap`（35）到不了腳位，`uart_rx`（36）與 `boot_mode`（33、34）的輸入仍送得到 user area，33、34 的下拉沒了；先寫回 33–37 再傳送：維持 user mode；不傳送：一直是 user mode；用 bit-bang 把 `serial_resetn` 拉低一次：恢復；拉 `resetb`：沒有恢復 | 已驗證（模擬前後比較，加上 gate-level netlist 的 reset 值：33–35 是 `0x0403`、36–37 是 `0x1803`，與 RTL 相同，只由 POR 重置）：housekeeping 存的 GPIO 設定 reset 值全是 management mode，一次傳送覆蓋 38 支；本設計兩份值不同的只有 33–37。推測（只依原始碼，沒有模擬）：傳錯之後（腳在 management mode），management SoC 再打開 QSPI 時會從 36、37 推 pad，打開 SPI master 時會推 35（33 的 oeb 固定為 1，`caravel_core.v` 第 1336 行；`housekeeping.v` 第 778–799 行），36 可能和外部的 UART TX 打架；外部也可以經 housekeeping SPI 做同樣的 bit-bang 恢復。推論：這顆設計的 management SoC 韌體不需要做傳送 | 使用者 2026-10-16 選「A：寫進文件與 skill (建議)」：寫成規則 8；不做新的 checker，留給下一個要下線的專案（ADR-0022）。本專案不下線（ADR-0019 決定 1），韌體在外部 SPI flash，重燒就能修 | `docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/`、`docs/notes/caravel_gpio_xfer.md`、ADR-0022 |
