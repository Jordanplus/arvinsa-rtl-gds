---
name: caravel-user-project-integration
description: 把設計放進 ChipFoundry Caravel 的 user_project_wrapper（2920 × 3520 µm，固定 DEF 範本 `FP_DEF_TEMPLATE`）時使用。症狀：`[WARNING PDN-0239] Ring shape falls outside the die bounds.`、`[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（範本本來就畫到 die 外，不要改）；precheck 的 `klayout_met_min_ca_density` 報 `li1.pd.1d`（0.4 min li1 ca pattern density，PDK 預設 `decap_3` 填滿空白）；`gpio_defines` 範本全是 `GPIO_MODE_INVALID`；Caravel 輸入腳位的 max slew 違規與邊界 hold。涵蓋先定 block 位置再選 GPIO（0–14 右緣、15–23 上緣、24–37 左緣，Wishbone 在下緣左段）、`wb_clk_i` 是管理用 CPU 的時脈、vccd1／vssd1 各只有一顆右側 pad 與 IR 的起算點、metal fill 由誰補與 `check_density.py` 的密度下限（`generate_fill`）、採用官方 wrapper SDC 前試算 input transition 與邊界 hold、選平台時的平台試算表。precheck 的執行與判定看 tapeout-precheck-caravel；pad、block、pin 的規劃與核准看 chip-floorplan-pin-planning。Use for integrating a design into the Caravel user_project_wrapper (fixed template, GPIO, power entry, li1 density, fill minimums, boundary SDC).
---

# 放進 Caravel user_project_wrapper

2026-10-15 從 `tapeout-precheck-caravel` 拆出（ADR-0021 決定 5）。這裡是設計放進 wrapper 的做法；precheck 怎麼跑、結果怎麼判看 `tapeout-precheck-caravel`；pad、block、pin 的規劃文件、核准與 checker 看 `chip-floorplan-pin-planning`（`CLAUDE.md` 規則 14）；IR 的判法看 `pdn-ir-drop`；邊界 SDC 的寫法看 `timing-constraints-sdc` 規則 14、15。本 repo 實例：ADR-0019、`pnr/user_project_wrapper/`、`docs/notes/caravel_precheck_phase7.md`。

名詞：
- **Caravel**：ChipFoundry（2025 年接手 Efabless 的 sky130 共乘下線）的載具晶片。pad、電源與一顆管理用的 RISC-V 都做好了，使用者的設計放在 `user_project_wrapper` 裡。
- **precheck**：ChipFoundry 收件前的自動檢查。現在是 pip 套件 `cf-precheck`，由 `cf` 指令（pip 套件 `chipfoundry-cli`）用 Docker 呼叫。
- **扁平放法**：CPU 的 standard cell 與 SRAM macro 直接放在 wrapper 層繞線，不先把 SoC harden 成 macro（`project-plan.md` §5.5）。官方範例都是先 harden 成 macro。

## 規則（已驗證）

1. **先定 block 位置，再選 GPIO**（原 `tapeout-precheck-caravel` 規則 5；使用者 2026-10-12：「block擺放位置應該在後段開始前就應該先確認之後出pin決定好」）。Caravel 的 pad 與 wrapper 腳位位置都固定（`xor` 檢查 die 外那圈），能選的只有用哪幾支 GPIO、接什麼訊號、什麼模式，訊號也可以改走 logic analyzer 或 Wishbone。順序：
   - 依有時序要求的介面定 block 位置：Wishbone（含 `wb_clk_i`、`wb_rst_i`）與 logic analyzer 在下緣左段 x = 0–870 µm；
   - 再依範本 DEF 的座標挑最近的 GPIO：0–14 在右緣（0–4 系統保留），15–23 在上緣，24–37 在左緣由上往下，37 在 y = 162 µm；
   - 最後才寫 wrapper RTL 的腳位對應與 `user_defines.v`。
   - 規劃文件、使用者核准、checker 與 hook 的做法在 `chip-floorplan-pin-planning`（ADR-0019 決定 13）。
2. **`wb_clk_i` 是管理用 CPU 的核心時脈**（原 `tapeout-precheck-caravel` 規則 6）：Caravel `verilog/rtl/caravel_clocking.v` 第 93–94 行，開機時是外部時脈 `ext_clk`（duty 由板子的振盪器決定），firmware 啟用 PLL 後是 `clock_div` 除頻的輸出（設計成 50% duty；除數 0 時直通 PLL）。所以：
   - 設計用 `wb_clk_i` 時，設計的週期就是管理端時脈的下限，要寫成使用限制（測試 firmware、板子）。本 repo：44 ns，管理端不能超過 22.7 MHz（ADR-0019 決定 15）。
   - duty cycle 與 jitter 沒有官方數字，`clock_uncertainty.sdc` 的假設要記成下線風險。
   - wrapper 邊界的約束（clock source latency、Wishbone／LA delay、transition、負載）用 caravel_user_project 的 wrapper SDC 數值，做法與 OpenSTA 的 driving cell 陷阱看 `timing-constraints-sdc` 規則 14、15。
   - Phase 7 先在 RTL 選了 GPIO 8–20，到 floorplan 才發現離 block 2–3 mm，RTL、`user_defines.v`、testbench 與文件都要重做（ADR-0019 決定 10）。
3. **user area 的供電結構（vccd1／vssd1；CC2509，原始檔查證）**（原 `tapeout-precheck-caravel` 規則 7）：vccd1、vssd1 各只有一顆 pad，都在晶片右側（`def/chip_io.def` 第 17057、16653 行，換到 wrapper 座標約 y = 3290、1051）；電流經 Caravel 自己 5 µm 寬的 met4 ring，再由 `manual_power_connections` 的 met3 跨接線接到 wrapper ring 的**左右兩側**（左 54、右 53 條，間距約 65 µm），上下兩邊沒有接點，caravel_core 的 PDN 不跨過 wrapper。所以：
   - wrapper 自己的電源 pin 不能當理想電源；IR 要把這段網路放進模型，供電點放在 pad（本 repo `pnr/user_project_wrapper/ir_caravel.py` 與 `caravel_pwr/`，ADR-0019 決定 18）。壓降幾乎都在 pad 到 wrapper 邊緣的垂直傳導上，wrapper 內部只佔一小部分（本 repo 的分布在 ADR-0019 決定 18）。
   - 兩顆 pad 相距約 2.2 mm，block 放哪裡都至少離其中一顆遠，移 block 的改善有限。能改的是 wrapper 的 met4 strap（垂直方向與 Caravel ring 並聯）與電流本身（用 max power pattern 量，`pdn-ir-drop` 規則 12）。IR 判定用慢 corner 的 max power pattern，ff 電流加 ss 電阻的最壞組合只當參考（ADR-0019 決定 19、20）。本 repo 移 block、改 met4 寬度與正式 run 的 IR 數字在 ADR-0019 決定 18–20。
   - 開新的 Caravel 設計時，在 pad 階段就照這條把供電模型列出來（`chip-floorplan-pin-planning` 規則 2）；Caravel 換版本時，用 `caravel_pwr/extract.py` 重抽、核對 blob hash。

4. **wrapper 頂層有標準 cell 時，空白區不能用 PDK 預設的 `decap_3` 填滿**（原 `tapeout-precheck-caravel` 規則 8；已驗證，2026-10-14，同一份設計只換 decap 的前後比較；ADR-0019 決定 24）：
   - **症狀**：precheck 的 `klayout_met_min_ca_density` FAIL，報表一堆 `li1.pd.1d`（「0.4 min li1 ca pattern density」）。每個帶 235/4 的 cell 各印一筆，其實是同一個整體數值；log 有 `li1_ca_density is <值>`，小於 0.4 就 FAIL（li1 超過 wrapper 面積的 60%）。
   - **原因**：`li1_ca_density = 1 − li1 面積 / 235/4 面積`，分母是整個 wrapper（10.28 mm²）。sky130 hd 的 `decap_3` 87% 是 li1，PDK 預設 `DECAP_CELL` 只有它；Fill Insertion 把空白全部填成 `decap_3` 時，本 repo 的 li1 75%。官方範例的 wrapper 只放 macro，關掉 fill（`RUN_FILL_INSERTION: false`），所以沒遇到。
   - **怎麼發現**：harden 後不用等 precheck，用 KLayout flat 算 li1（67/* 除 5、10、44，加 56/28）合併面積除以 235/4 合併面積，與 precheck 的算法相同（本 repo 兩份版圖都對上 precheck 的值）；按 cell 拆就看得出是哪種 fill。
   - **怎麼繞過**：`DECAP_CELLS` 改 `sky130_ef_sc_hd__decap_12`（li1 52%），`FILL_CELLS` 加 `fill_8`、`fill_4`。timing、DRC、LVS 不變（Fill Insertion 在 detailed routing 之後），instance 與 harden 時間都大幅減少，precheck 的 BEOL 與 Magic 抽取也跑完了（同一天 VM 也加到 16 GiB，兩者沒有分開實驗，哪一個是必要的不知道；`tapeout-precheck-caravel` 規則 1）。本 repo 的前後數字（li1、instance 數、harden 時間）在 ADR-0019 決定 24。代價：`ef_decap_12` 沒有 .lib，漏電不進功耗報告（`signoff-criteria` knowledge S29）。只放 fill（li1 約 14%）會連邏輯旁的 decap 一起拿掉，而靜態 IR 看不到，不建議。li1 降低後還要過 tapeout 時的密度下限（li1 ≥ 35%，「待確認」的 fill 一項）。
   - **防復發**：`make precheck-caravel` 的 checker 要求 `klayout_met_min_ca_density` PASS；harden 時沒有自動檢查（要等 precheck 才抓得到，約 1 小時）。

### 提早檢查（流程回顧，ADR-0020，使用者決定）

2026-10-14 回顧（`docs/notes/flow_retro/retro_p6_7.md`）的結論之一：Phase 7 第一天的查證列出了平台的檢查項目、密度上限與官方 SDC，但沒有套到自己的設計上算數字；單顆 vccd1 pad、邊界 transition 與 hold、li1 密度、precheck PDK 的預建 SRAM、metal fill 誰補，全部在 harden 之後才發現，粗估重做約 2 天、3 項放寬。每項試算只要 10 分鐘到半天。使用者決定加下面三條（流程文件 4.1、4.5、4.6）。

5. **選定下線平台時做平台試算表，需要平台回覆的問題當天送出**（原 `tapeout-precheck-caravel` 規則 9；提早檢查 A2）。
   - 做什麼：平台的每一項收件檢查（本平台是 precheck 的 13 項）、外殼的邊界 SDC（input transition、IO delay、clock source latency）、供電結構（pad 數量與位置，規則 3）、fill 由誰做與密度上下限（規則 4 與「待確認」的 fill 一項）、平台 image 的 PDK 與工具版本（`tapeout-precheck-caravel` 規則 1），逐條算出「對本設計是多少」，和本設計的 signoff 上限並排；版本不同的寫明誰的結果算判定，平台會用到的 macro（例如 PDK 預建 SRAM）用平台的 PDK 另取一份。需要平台回覆的問題（已知 deck 問題、自產 macro 的 Magic DRC 怎麼看、fill 誰做）在選定平台當天送出，記下日期與回覆。
   - 通過條件：每一條有數字，或寫「待查，在哪一步查」；衝突在第一次 harden 前已列選項、由使用者決定；每個問題是「已送出（日期）」或「使用者決定不送（原話）」。
   - 為什麼：上面那段；本 repo 給 ChipFoundry 的 issue 到 Phase 7 結案仍是草稿，fill 也沒有書面確認，都列為下線前要做（ADR-0019 決定 26 與「後果」）。
   - 自動防護：沒有（試算表與問題清單是文件）。
6. **採用官方邊界 SDC 時，第一次 harden 前先試算 input transition 與邊界 hold**（原 `tapeout-precheck-caravel` 規則 10；提早檢查 C4）。
    - 做什麼：官方 SDC 的 input transition 和自己的 slew 上限並排比；用官方的 clock source latency（min／max）、min input delay 加上預估的 clock tree，算邊界 hold 需要多少延遲，決定 hold 餘量與 resizer 要看的 corner（`timing-constraints-sdc` 規則 14、15）。
    - 通過條件：有衝突的項目在 harden 前已列選項、由使用者決定。
    - 為什麼：官方 input transition 0.84–0.97 ns 超過本 repo 的 0.70／0.75 ns，`p7_floorplan4` 網表上已量到 0.84 ns 卻沒拿去比，到探索 harden 才處理（ADR-0019 決定 14、16）；邊界 hold 在 ff 100°C −0.071 ns，官方約束下 ff 要多延遲約 2.4 ns，多跑了 `p7_harden3`、`p7_harden4` 一輪（決定 17；經驗紀錄 2026-10-12）。試算約 10 分鐘到 1 小時（回顧推算）。
    - 自動防護：沒有（邊界 slew 的判定在 harden 後由 `check_soc.py max_slew` 做，試算本身是人工）。

## 規則（已驗證，2026-10-15 問題總檢討後補寫，ADR-0021）

7. **Caravel 範本的 core ring 與腳位本來就畫到 die 外：`PDN-0239`、`GRT-0036` 是預期的警告，不要為了消警告改範本**（已驗證，2026-10-12，座標和官方範例 DEF 相同；原 `tapeout-precheck-caravel` 經驗紀錄 2026-10-12 兩列）。
   - 症狀：`OpenROAD.GeneratePDN` 報 `[WARNING PDN-0239] Ring shape falls outside the die bounds.`；global routing 起的每一步報 `[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（and 1000 similar warnings）。
   - 原因：core ring（4 組電源 × 2，寬 3.1 µm、offset 12.45 µm）最外到 x = −43.63 µm；固定範本 DEF 的腳位形狀一半在 die 外（例如 `io_oeb[0]` 在 x = 2921.2 µm、met3 從 −3.6 到 +3.6 µm，die 寬 2920 µm）。8 組 net 的 ring 座標與官方範例 `user_project_wrapper.def` 完全相同，官方範例的 precheck `xor` 是 PASS。
   - 怎麼發現：harden 的 metrics `flow__warnings__count:PDN-0239`、`flow__warnings__count:GRT-0036`；確認時把 ring 與腳位座標和 `pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def` 比。
   - 怎麼處理：不處理。改腳位或 ring 會讓 precheck 的 `xor` FAIL（die 外那圈要和官方空 wrapper 相同，見「待確認」的 `xor`）。
   - 防復發：wrapper 的 golden（`signoff/golden/user_project_wrapper/metrics.json`）記了這兩個警告的數量，`signoff/limits/user_project_wrapper.toml` 沒有把它們列為可有可無的 key，數量改變時 golden 比對會報；範本被改時 precheck 的 `xor` 會 FAIL。沒有逐座標比對 ring 與官方 DEF 的 checker。

## 待確認

### 已實跑 PASS，違反時會不會 FAIL 沒有實測

- `xor`（原始碼）：die（0–2920 × 0–3520 µm）外那一圈要和 caravel-lite 的空 wrapper 一樣，所以要用 `FP_DEF_TEMPLATE`（`openlane/user_project_wrapper/fixed_dont_change/user_project_wrapper.def`），core ring（寬 3.1 µm、offset 12.45 µm）不能改。
- `gpio_defines`：`verilog/rtl/user_defines.v` 的 GPIO 5–37 都要有值、不能是 `GPIO_MODE_INVALID`；範本全是 INVALID。
- `oeb`：CVC 在萃取網表上追 `io_out`／`io_oeb` 的實際接線，和 GPIO 模式比；user output 模式要真的接 `io_out` 與 `io_oeb`。RTL 對了不代表 PASS。2026-10-14 本 repo 實跑 PASS（報表 `cvc.oeb.report` 逐支列出接線與模式，與 `user_defines.v` 一致）；接錯時會不會 FAIL 沒有實測。
- `klayout_met_min_ca_density` 的 met1–met4 ≤ 60%、met5 ≤ 76%：本 repo 都遠低於上限（m4 ca 0.73、m5 0.73），沒有遇過超標；li1 見規則 4，金屬密度的下限見下一節的 fill 一項。
- `xor`、`gpio_defines`：2026-10-14 本 repo 的 wrapper 實跑 PASS（`FP_DEF_TEMPLATE`、`user_defines.v` 照規則 1）；違反時會不會 FAIL 沒有實測。
- `FP_DEF_TEMPLATE` 已在本 repo 的 wrapper 正式使用（`pnr/user_project_wrapper/config.json`）。

### 還沒經實跑或平台確認

- 官方範例的 flow 是 LibreLane 2.4.6（ChipFoundry fork `CI2511`）；LibreLane 3.0.14 支援 `FP_DEF_TEMPLATE`，舊的 `FP_PDN_*` 名稱會自動轉換。
- **metal fill 由誰補、補完之後的密度下限**（ADR-0019 決定 26 的查證與試跑；`docs/phase_exit/phase7.md` 已知限制 3；試跑紀錄在主目錄 `runs/p7_review/fill_trial/README.md`，`runs/` 不進版控）。只做過一次，平台的部分是推論，所以放這裡、不放規則本文（`CLAUDE.md` 規則 3）。
  - 誰補：整合方在 tapeout 時對整顆 Caravel 補 metal fill（Caravel `Makefile` 的 `generate_fill`，`generate_fill.py` 用 `cif ostyle wafflefill(tiled)`）。Efabless 時代證據強（efabless/caravel_user_project#169、efabless/mpw_precheck#141、efabless/caravel `27cbe49` `Makefile` 第 1138–1155 行）；ChipFoundry 沿用同一套腳本（chipfoundry/caravel `01fb61d`），沒有文件明講，證據中等（推論）。官方範例的 wrapper 關掉 fill（`RUN_FILL_INSERTION: false`，規則 4）。
  - 補完之後另有下限檢查 `check_density.py`：700 µm 視窗，li1 與金屬步進 350 µm、FOM 步進 70 µm；li1、met1–4 ≥ 35%、met5 ≥ 45%、FOM ≥ 33%，另看整顆平均。precheck 不跑這一項，只查上限（`klayout_met_min_ca_density`）。efabless/caravel#397 有全數位設計補完 fill 仍 FAIL。35%／45% 的出處是這支腳本，不是 sky130 PDK 的 periphery rules（ADR-0019 決定 26）。
  - 自己預估的方法：照 `generate_fill.py` 單獨補 wrapper（700 µm 區塊），再照 `check_density.py` 的視窗量（Magic `cif ostyle density`、`cif list cover`）。fill 很大時每個區塊分開量、再逐格和 wrapper 相加，省記憶體；相加比一起量偏高（本 repo 實量一塊，700 µm 視窗最多高 0.33 個百分點），對上限偏保守，對下限只有離下限不到這個差的視窗可能判錯。LibreLane nix-shell 的 Magic Tcl 沒有 `clock` 指令（`invalid command name "clock"`），計時改用 `exec date`。
  - 判斷不了的：die 右緣與上緣的視窗（正式檢查用晶片座標，會含到 Caravel 外殼的區域）、平台實際的 fill 參數與版本、整顆晶片的平均。precheck 的 `met_min_ca_density` 報的 met4／met5 比只算 die 內的高 1.2–1.6 個百分點（推測：分母是 die 外框 `235/4`，分子含 die 外的電源環，沒有驗證）。
  - 本 repo 的結果：li1、met1–5 只剩 met2 一個視窗略低於下限，FOM 有 15 個視窗低於 33%，都在 SoC 與 SRAM 擠在一起的左下角；met4 最高的視窗貼近上限。數字在上面的試跑紀錄與 Phase 7 已知限制 3；要改善的方向是降低局部密度（沒試）。依使用者的選擇不自己加 fill，向平台書面確認列為下線前要做（ADR-0019 決定 26）。
  - 自動防護：沒有。下限檢查在 tapeout 才跑；harden 內的密度 checker 是 `tapeout-precheck-caravel` 規則 11 的待辦（ADR-0020 D5，下一個專案開始時做成 checker）。

## 用完後

1. 新的現象加進「經驗紀錄」，根因標明已驗證／推測。
2. 「待確認」的項目實跑或經平台確認後搬進規則；同一現象出現兩次或用實驗確認才寫成規則（CLAUDE.md 規則 3）。
3. Caravel 換版本時，重抽供電結構（規則 3，`caravel_pwr/extract.py`）、重看 GPIO 位置與範本 DEF（規則 1、7）。

## 經驗紀錄

2026-10-15 從 `tapeout-precheck-caravel` 的經驗紀錄搬來（ADR-0021 決定 5）。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-12 | arvinsa-rtl-gds Phase 7 步驟 3–4 | 寫 wrapper RTL 時先選 GPIO 8–20（沒看位置），到 floorplan 才發現在右緣與上緣，離左下角的 block 2–3 mm；我原本用「慢速訊號加 buffer 就好」帶過 | 已驗證（範本 DEF 座標）；流程順序錯誤，使用者指出 | 改成 GPIO 33–37（左緣最下面）、`gpio_out` 只走 LA；RTL、`user_defines.v`、testbench 重做，regress-rtl caravel 30/30、neg 42/42；寫成規則 1（原 `tapeout-precheck-caravel` 規則 5） | ADR-0019 決定 10、12 |
| 2026-10-12 | `p7_floorplan4`（扁平 wrapper，跑到 global placement） | `OpenROAD.GeneratePDN` 報 `[WARNING PDN-0239] Ring shape falls outside the die bounds.` | 已驗證：Caravel 的 core ring（4 組電源 × 2，寬 3.1 µm、offset 12.45 µm）本來就畫到 die 外，最外到 x = -43.63 µm；8 組 net 的 ring 座標與官方範例 `user_project_wrapper.def` 完全相同，官方範例的 precheck XOR 是 PASS | 預期中的警告，不處理；之後 harden 的 checker 可以比對 ring 與官方 DEF 一致（還沒做） | ADR-0019；`runs/p7_floorplan4/21-openroad-generatepdn/` |
| 2026-10-12 | `p7_harden2`（wrapper 探索 harden） | 第 41 步 `RepairDesignPostGRT` 中止：`[ERROR RSZ-0074] failed to build tree from gloubal routes: found route to 1 pins, expected 0`，停在 `analog_io[9]` | 已驗證：沒接東西的 inout 腳位被 OpenROAD 同時算成 driver 和 load；官方範例沒開 `RUN_POST_GRT_DESIGN_REPAIR`，所以沒遇到 | `RSZ_DONT_TOUCH_RX` 設 `analog_io`；四項防護在 `librelane-run-debug` 已知陷阱 | `runs/p7_harden2/41-*` |
| 2026-10-12 | `p7_harden2` 第 38 步（hold 修完後的 STA） | tt corner 有 384 個 max slew 違規（soc_top 是 0）：`la_oenb`、`la_data_in` 各 128 支腳位、`wbs_adr_i`、`wbs_dat_i` 各 32 支，以及接在這兩組腳位上的第一顆 cell（64 個，多是 hold delay cell） | 已驗證：全部在 Caravel 直接驅動的 net 上，slew 是 Caravel SDC 給的 input transition（0.84–0.97 ns），超過本 repo 的上限 0.70／0.75 ns（ADR-0009）；官方範例的上限是 1.5 ns（`MAX_TRANSITION_CONSTRAINT`），所以不算違規。wrapper 內部修不掉 | 使用者決定「內部照舊，邊界另判」（ADR-0019 決定 16）：`check_soc.py max_slew` 只允許這些 pin，到 Caravel 的 transition + 0.05 ns；wrapper 的 `MAX_SLEW_VIOLATION_CORNERS` 改回預設；P80 | `runs/p7_harden2/38-*/checks.rpt` |
| 2026-10-12 | `p7_harden2`（wrapper 探索 harden）global routing 起的每一步 | `[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（and 1000 similar warnings） | 已驗證：固定範本 DEF 的腳位形狀一半在 die 外，例如 `io_oeb[0]` 在 x = 2921.2 µm、met3 從 −3.6 到 +3.6 µm，die 寬 2920 µm；官方設計就是這樣，precheck 的 `xor` 比的就是這圈 | 不用處理，不要為了消警告改腳位（會被 `xor` 抓） | `pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def` |
| 2026-10-12 | `p7_harden2` 第 51 步 `Odb.ReportDisconnectedPins` | `Found 327 disconnected pin(s), of which 0 are critical.`；soc_top 是 0，`check_soc.py disconnected` FAIL | 已驗證：全部是 wrapper 最上層沒用到的 Caravel 腳位：`analog_io` 29、`io_in` 35（用到的只有 GPIO 33／34／36）、`la_data_in`／`la_oenb` 各 128、`user_clock2`，加上沒有 cell 用到的 6 支電源腳位（只有 vccd1／vssd1 有 cell）；沒有 cell 的 pin 浮接 | `disconnected` 改成 wrapper 判法（`DESIGNS unused_ports`）：表上必須剛好是「不是 Wishbone、也不是 `pin_plan.toml` 輸入模式 GPIO 的輸入／inout 腳位」加「沒有 cell 用的電源腳位」，只在頂層、0 個 critical。四種植入錯誤（用到的輸入、cell pin、應該沒接的腳位被接上、critical 1）手動確認都 FAIL；正式 negative test 等 `neg_pnr` 支援 wrapper（步驟 8） | `pnr/soc_top/check_soc.py` |
| 2026-10-12 | `p7_harden2`（wrapper 探索 harden，從第 41 步接續後跑完） | signoff 只剩 1 條 hold 違規：`wbs_adr_i[4]` → `_21509_`，`max_ff_100C` −0.071、`max_ff_n40C` −0.043 ns；post-GRT 的 hold 修復修完估計 +0.058 ns | 已驗證（STA 報表）：官方約束下 Caravel 輸入的 min input delay 0.79 ns 掛在 4.65 ns 的 latency，wrapper 暫存器在 5.57 ns 加內部約 2 ns 的 clock tree 取樣，ff 下資料要延遲約 2.4 ns；global routing 的估計對這條路徑樂觀約 0.1 ns。soc_top 沒有這類路徑 | `GRT_RESIZER_HOLD_SLACK_MARGIN` 0.2 ns（ADR-0019 決定 17）；試過把 ff_100C 加進 resizer 的 corner，`RepairDesignPostGRT` 壅塞失敗（`drv-timing-closure` 經驗紀錄）。驗證中（`p7_harden4`） | `runs/p7_harden2_out/attempt2_margin005/` |
| 2026-10-13 | `p7_harden2` 版圖的 IR what-if（agent 讀 Caravel 原始碼、單步 IR） | 供電點放在 wrapper ring 時 8.4 mV，加上 Caravel 的供電網路變成 104 mV（預設切換率、最壞組合） | 已驗證（原始檔 blob hash 核對、對照組在 0.1% 內）：vccd1／vssd1 各一顆 pad、5 µm ring、跨接線只在左右兩側 | 規則 3（原 `tapeout-precheck-caravel` 規則 7）；met4 4.8 µm（決定 18）；改用 max power pattern 判 20 mV（決定 20），p7_harden2 網表、met4 4.8 µm 19.9 mV（40 ns 錄）| `pnr/user_project_wrapper/caravel_pwr/`、ADR-0019 決定 18–20 |
| 2026-10-15 | arvinsa-rtl-gds Phase 7 的 fill 試跑（第二輪 wrapper GDS，ADR-0019 決定 26） | precheck 只查密度上限；照 Caravel `generate_fill.py`（`wafflefill(tiled)`）單獨補 wrapper、照 `check_density.py` 量 700 µm 視窗：li1、met1–5 只剩 met2 一個視窗 34.5%，FOM 15 個視窗低於 33%（最低 31.5%），都在 SoC 與 SRAM 擠在一起的左下角；met4 最高 59.7% 貼近上限。另外 precheck 的 `met_min_ca_density` 報的 met4／met5 比只算 die 內高 1.2–1.6 個百分點；LibreLane nix-shell 的 Magic Tcl 沒有 `clock` 指令（`invalid command name "clock"`） | 已驗證：fill 區塊分開量再相加，比一起量最多高 0.33 個百分點（實量一塊比對）。推測：precheck 的分母是 die 外框（`235/4`），分子含 die 外的電源環 | 不自己加 fill；結果列為下線前要向平台確認的項目。fill 很大（wrapper 1.2 GB）時每個區塊分開量再相加，省記憶體。只出現一次，不寫成規則；沒有自動防護（下限檢查在 tapeout 才跑，ADR-0020 的 D5 留到下一個專案） | 主目錄 `runs/p7_review/fill_trial/README.md`（腳本在同一目錄） |
