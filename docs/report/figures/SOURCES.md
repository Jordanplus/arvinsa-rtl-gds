# 實際成果圖的資料來源

這份清單涵蓋 layout 截圖與數據圖（`layout_*.png`、`floorplan_pin_plan.png`、`timing_wrapper_corners.png`、`density_fill_trial.png`、`ir_drop_map.png`、`phase_metrics.png`），以及 2026-10-16 新增的三張圖（第 11–13 節）：`overview_flow_*` 是示意圖，但每個框都對到流程文件與設定檔；`caravel_chip_*`、`caravel_clock_power_*` 的內容都來自外部的 Caravel 原始檔，所以一起列出。同目錄的其他示意圖（`flow_*`、`checkers_*`、`roadmap_*` 等）不在這份清單，出處寫在 `scripts/diagrams.py` 各圖的 `_note`。

- 產生日期：2026-10-15。
- 2026-10-15 產生之後，worktree 與 `runs/` 都已刪除（ADR-0021 決定 7）。下面引用的報告類檔案收在 `docs/evidence/`（路徑對照與收錄狀態見 `docs/evidence/references.md`）；GDS、DEF 等 layout 檔沒有收，要重畫時先在乾淨 checkout 重跑對應的 regress。
- 資料來源：正式結案 run（commit `2b04451`）的三個乾淨 worktree，路徑都在 `~/claude_prjs/` 下：
  - `arvinsa-rtl-gds-p7close2_caravel`：Caravel wrapper。
  - `arvinsa-rtl-gds-p7close2_h3`：Hazard3 SoC。
  - `arvinsa-rtl-gds-p7close2_pico`：PicoRV32。
- 腳本在 `scripts/`。共用的路徑與配色在 `common.py`，matplotlib 用系統的 python3。
- 圖上的英文說明與數字都由腳本從下列檔案讀出，或寫在腳本裡並附出處。

## layout 截圖（1–5）

### 產生方式

```sh
cd docs/report/figures/scripts
./render_layouts.sh <raw_dir>        # KLayout 無頭輸出原始 PNG（LibreLane nix-shell 裡的 klayout）
python3 layout_figs.py <raw_dir>     # 加上 µm 座標軸、標題、block 外框；轉成調色盤 PNG 以控制檔案大小
```

### 截圖工具的設定

- `gds_shot.py` 只顯示這些繪圖層：nwell、diff/tap、poly、licon、li1、mcon、met1–met5、via–via4。
- 其餘的層全部隱藏：prBoundary、areaid、pin、label、text 等。
- 要截的範圍明確傳入，長寬比與輸出像素一致，所以圖上的座標軸等於傳入的範圍。
- 每張原始圖旁邊的 `<png>.json` 記錄顯示了哪些層、top cell 名稱與它的外框。

### 輸入的 GDS

| 圖 | GDS | sha1（前 12 碼） |
|---|---|---|
| 1、2 | `p7close2_caravel/runs/user_project_wrapper/final/gds/user_project_wrapper.gds` | `06b0ddc46c54`（與 precheck 受檢的 `06b0ddc4…` 相同，`runs/p7_review/fill_trial/README.md` 第 3 行） |
| 3 | `p7close2_h3/runs/soc_top_hazard3/final/gds/soc_top.gds` | `9d3f249ebfe5` |
| 4 | `ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/openram/arv_sram_2kbyte_1rw1r_32x512_8.gds` | `e44ac320bc8f` |
| 5 | `p7close2_pico/runs/picorv32_core/final/gds/picorv32.gds` | `25c1b4902811` |

### 每張圖

1. **`layout_wrapper_full.png`**：wrapper 全圖，分兩欄，截圖範圍 (−60, −60)–(2980, 3580) µm。
   - (a) 顯示所有繪圖層。空的 row 都填了 decap 與 fill cell，met1 的電源軌（藍色）蓋滿整個 die。
     - decap 與 fill 的數量來自 `final/def/user_project_wrapper.def` 的 COMPONENTS 統計：`sky130_ef_sc_hd__decap_12` 543,617 顆。
     - fill_1／fill_2／fill_4 合計 425,550 顆（144,511 + 142,288 + 138,751）。
     - tap cell 140,477 顆。
   - (b) 只顯示 met2–met5。訊號繞線只在 SoC 周圍，met4／met5 的電源 strap 鋪滿整個 die。
   - 紅框是 SRAM，位置 (350.98, 413.44)，取自 `pnr/user_project_wrapper/pin_plan.toml` 第 22 行；大小 694.27 × 428.415 µm，取自 macro GDS 的外框。
   - 綠框是 SoC 邏輯 cell 的範圍，x ≤ 861.12、y ≤ 522.24 µm。
     - 計算方式：同一份 DEF 中，扣掉 decap、fill、tap 與 SRAM 後剩 25,100 顆 cell。框的上界取這些 cell 位置的第 99 百分位。
     - 也有少數 cell 在 die 邊緣，最遠到 (2911, 3506)。
2. **`layout_wrapper_soc_zoom.png`**：左下角放大，截圖範圍 (−20, −20)–(1180, 940) µm。
   - 隱藏 met4、via4、met5，讓 cell 與 met1–met3 的繞線看得清楚。
   - SRAM 框的來源同上。
3. **`layout_soc_top_hazard3.png`**：Hazard3 版 soc_top 全圖，1000 × 800 µm，顯示所有繪圖層。
   - SRAM 位置 (290.72, 353.6)，取自 `pnr/soc_top/config_hazard3.json` 第 101–104 行。
   - die 大小與 instance 數 92,321 取自該 run 的 `final/metrics.json`：`design__die__bbox`、`design__instance__count`。
   - slack +0.656／+0.126 ns 取自同一份 metrics（`timing__setup__ws`、`timing__hold__ws`），也與 README.md 第 49 行相同。
4. **`layout_sram_macro.png`**：SRAM macro。
   - (a) 整顆 macro，隱藏 met2／met4：met2 的 bitline 在整張圖的縮放下會把 bitcell array 蓋成一整塊洋紅色，所以隱藏。
   - (b) 40 × 25 µm 的放大，範圍 (128, 98)–(168, 123)，顯示所有繪圖層。
   - block 外框是 macro GDS 裡各子 cell instance 的外框，用 KLayout 讀 GDS 列出：
     - bitcell array：`capped_replica_bitcell_array` (139.3, 101.8)–(556.5, 368.2)。
     - port 0 位址：`port_address`，含 row decoder 與 wordline driver，(75.3, 106.1)–(138.2, 361.7)。
     - port 1 位址：`port_address_0`，(557.6, 108.2)–(620.5, 363.8)。
     - port 0 資料：`port_data`，(139.2, 47.4)–(547.8, 101.8)。
     - port 1 資料：`port_data_0`，(139.5, 368.2)–(550.9, 404.1)。
     - 控制邏輯：`control_logic_rw`、`control_logic_r`。
     - DFF：`data_dff`、`wmask_dff`、`col_addr_dff`。
   - 子電路的內容取自 macro 的 `.sp`：
     - `port_data` 有 precharge、column mux、sense amp、sense precharge、write driver、write mask and。
     - `port_data_0` 沒有 write driver。
     - 128 rows × 128 cols：`.sp` 第 966、1570 行；words_per_row 4：第 967 行。
   - 規格（512 × 32、write_size 8、1RW + 1R）取自 `ip/sram/openram/configs/arv_sram_2kbyte_1rw1r_32x512_8.py` 第 5–10 行。
5. **`layout_picorv32_core.png`**：picorv32_core 全圖，533.575 × 544.295 µm。
   - 9 個 corner、setup +6.175 ns、hold +0.039 ns，取自該 run 的 `final/metrics.json`，與 `docs/phase_exit/phase2.md` 第 13 行相同。

## 6. `floorplan_pin_plan.png`

產生指令：

```sh
python3 scripts/plot_floorplan.py runs/p7_floorplan4/28-openroad-globalplacement/user_project_wrapper.def \
  docs/report/figures/floorplan_pin_plan.png --plan pnr/user_project_wrapper/pin_plan.toml --dpi 100 \
  --title "user_project_wrapper floorplan and pin plan (run p7_floorplan4, global placement; approved 2026-10-12)"
```

- 用 repo 的 `scripts/plot_floorplan.py` 重新產生，沒有沿用舊圖。
- 輸入是 `runs/p7_floorplan4` 跑到 global placement 的 DEF，也就是使用者 2026-10-12 核准時看的同一個 run。
  - 當時看的圖是 `runs/layout_png/p7_floorplan4_modules.png`，見 `docs/decisions/0019-phase7-caravel-precheck.md` 第 67 行。
  - 這次用同一支腳本、同一份 DEF 與規劃重畫，只把 dpi 降到 100（2000 × 2510 px）。
- 圖上各模組的 cell 數，例如 CPU 9309 顆，是 global placement 當時的數字，不是最終 netlist 的數字。
- 左下角幾個小模組（test control、boot ROM、GPIO）的標籤互相重疊。這是 `plot_floorplan.py` 的排版，沒有改。

## 7. `timing_wrapper_corners.png`

產生指令：`python3 scripts/timing_wrapper_corners.py`

- 資料：`p7close2_caravel/runs/user_project_wrapper/final/metrics.json` 的 `timing__setup__ws__corner:*` 與 `timing__hold__ws__corner:*`，15 個 corner。
- 最差 setup +0.548 ns 在 `min_ss_n40C_1v60`，最差 hold +0.187 ns 在 `max_ff_100C_1v95`。
- 與 README.md 第 56 行的「+0.548／+0.187 ns」相同。

## 8. `density_fill_trial.png`

產生指令：`python3 scripts/density_fill_trial.py`

- 資料：`runs/p7_review/fill_trial/nofill/density.log` 與 `withfill/density.log`。
- window 的計算方式與 `runs/p7_review/fill_trial/aggregate.py` 相同：
  - 700 µm 見方的 density window；li1 與金屬步進 350 µm，FOM 步進 70 µm。
  - die 邊緣的 window 依它在 die 內的面積加權。
  - 下限：li1、met1–4 35%，met5 45%，FOM 33%。
- 腳本會印出每層的整塊平均、最低的 window 密度與超出範圍的 window 數。已核對與 `nofill/density.md`、`withfill/density.md` 逐項相同，例如：
  - 補 fill 後 FOM 有 15/1386 個 window 低於下限，最低 31.5%，在 (210, 140)。
  - 補 fill 後 met2 有 1/63 個 window 低於下限，34.8%，在 (0, 0)。
- (b)、(c) 是補 fill 後 FOM 與 met2 每個 window 的密度，畫在 window 中心；紅框是低於下限的 window。

## 9. `ir_drop_map.png`

產生指令：`python3 scripts/ir_drop_map.py`

- 資料：`p7close2_caravel/runs/ir_caravel/ir_caravel/`。
  - `results.json`：取 `drops` 中 VDD 加 GND 合計最大的組合，是 `max_ss_100C_1v60` 的 window `5c`：11.92 + 7.65 = 19.56 mV，與 README.md 第 56 行相同。
  - 該組合的 `step/net-vccd1.csv`、`step/net-vssd1.csv`：每個 instance 電源腳一列，各 1,140,379 列。
  - `vsrc/*.vsrc`：電壓源在 Caravel 唯一的 vccd1 pad (3046.49, 3302.77–3353.03) 與 vssd1 pad (3046.49, 1063.77–1114.03)。
- 壓降一律用 1.60 V − 節點電壓計算，單位 mV；每 20 µm 一格，取格內最大值。
  - 腳本會檢查 CSV 的最大壓降與 `results.json` 的值相差小於 0.01 mV：VDD 11.916、GND 7.649。

## 10. `phase_metrics.png`

產生指令：`python3 scripts/phase_metrics.py`

只用 repo 文件中的數字。每個數字的出處列在腳本裡，也印在圖的右下角：

| 面板 | 數字 | 出處 |
|---|---|---|
| (a) 週期 | P2 40 ns（picorv32_core 單獨） | README.md:15 |
| | P3 40 ns | README.md:16 |
| | P4 42 ns | README.md:24 |
| | P3.5 43 ns | README.md:32 |
| | P5 44 ns | README.md:39 |
| | P6 44 ns | docs/phase_exit/phase6.md:61 |
| | P7 44 ns | docs/phase_exit/phase7.md:60 |
| (b) 最差 setup／hold slack | P2 +6.175／+0.039 ns（picorv32_core，9 corner） | docs/phase_exit/phase2.md:13 |
| | P4 +0.313／+0.082 ns（soc_top PicoRV32，15 corner） | docs/phase_exit/phase4.md:42 |
| | P5 +1.114／+0.109 ns（Hazard3） | README.md:40 |
| | P6 +0.656／+0.126 ns（Hazard3） | README.md:49 |
| | P7 +0.548／+0.187 ns（wrapper） | README.md:56 |
| (c) IR（VDD + GND） | P4 8.07 mV（strap 只從一端供電、nom_tt） | README.md:25；docs/phase_exit/phase4.md:113 |
| | P5 14.13 mV（ff 電流 + ss 金屬電阻） | README.md:41 |
| | P6 15.91 mV | README.md:49 |
| | P7 19.56 mV（Caravel pad、max power pattern） | README.md:56 |
| (d) 結案 regress | P4 `make regress` 25/25、123 分鐘 | README.md:27 |
| | P3.5 25/25、136 分鐘 | README.md:34 |
| | P5 21/21、109 分鐘；`regress-picorv32` 26/26、124 分鐘 | README.md:43 |
| | P6 23/23、126 分鐘；28/28、196 分鐘 | README.md:52 |
| | P7 `regress-caravel` 18/18、476 分鐘；`regress-picorv32` 31/31、248 分鐘；`make regress` 30/30、211 分鐘 | README.md:60 |
| (e) 植入錯誤案例數 | P1 33 | README.md:14 |
| | P3 44（PnR 20 + EQY 11 + GL 4 + 來源追溯 9，四項相加） | README.md:19 |
| | P4 163 | README.md:27；docs/phase_exit/phase4.md:149 |
| | P3.5 164 | README.md:34；docs/phase_exit/phase3_5.md:122 |

- 橫軸照結案日期排：Phase 4（2026-10-04，phase4.md:3）在 Phase 3.5（2026-10-05，phase3_5.md:3）之前。
- Phase 5–7 的文件只列各 suite 的案例數（例如 phase5.md:62–66、phase6.md:156–166），沒有寫總數，所以 (e) 沒有畫 Phase 5–7。
- (c) 各 Phase 的 IR 模型不同（見 `pdn-ir-drop` skill 第 57 行），數字不能直接比較，只表示檢查用的值逐次變嚴。

## 11. `overview_flow_zh.png`、`overview_flow_en.png`

產生指令（圖的定義是 `scripts/diagrams.py` 的 `OVERVIEW`）：

```sh
cd docs/report/figures/scripts
DIAG_ONLY=overview_flow python3 diagrams.py zh en
```

- 產生日期：2026-10-16。和同目錄的其他示意圖一樣，用 arvinsa-draw-diagram 的 `engine.py` 畫：`diagrams.py` 的 `build()` 寫出 `diagrams/overview_flow_<lang>.json`，再由 engine 輸出 PNG 與 SVG。
- 和 `flow_*.png`（§4.1 的九格步驟圖）不同：這張照資料流動的方向畫，標出每一步的工具與產出的檔案，LibreLane 內部的步驟照執行順序編號 1–8。
- 圖上只有設定值（corner 數、IR 上限、工具版本），沒有量測結果；每個框的內容與出處如下。

### 每個框的出處

| 框 | 內容 | 出處 |
|---|---|---|
| 輸入：RTL 與 firmware | Hazard3／PicoRV32 SoC；firmware 用 gcc 編譯 | `rtl/`、`fw/`；報告 §2 的表 |
| 輸入：pad／block／pin 規劃 | `pin_plan.toml`，使用者核准，`make pin-plan` 檢查 | `CLAUDE.md` 規則 14；`Makefile` 第 473 行 |
| 輸入：PDK | sky130A、`sky130_fd_sc_hd` 的 `.lib`、LEF、GDS、規則 deck | `pnr/user_project_wrapper/config.json` 的 `LIB`；報告 §2 |
| 輸入：規格與 constraint | `project-plan.md`、ADR、SDC（`pnr.sdc`／`signoff.sdc`）、`signoff/limits/*.toml` | config 的 `PNR_SDC_FILE`、`SIGNOFF_SDC_FILE`；`arvinsa-rtl-gds-flow.md` §4.5 |
| RTL 驗證 | Verilator lint、Yosys 合成檢查、Icarus＋Verilator self-checking 測試、植入錯誤 | `rtl/scripts/lint.sh`、`rtl/scripts/synth_check.sh`；`Makefile` 的 `phase1`（第 282 行）；流程文件 §4.2 |
| SRAM macro | OpenRAM 產生；用 ngspice 做 characterization，產生 5 個 PVT 的 `.lib`；view QA（`check_macro_views.py`） | 流程文件 §4.3；ADR-0018；`CLAUDE.md` 規則 12 |
| harden 的框 | LibreLane 3.0.14 Classic flow，`make harden` | config 的 `meta.flow`；`Makefile` 第 341 行；開跑前的 `check_inputs.py` 見 `pnr/soc_top/run.sh` 第 14 行 |
| 1–8 的步驟與工具 | 合成（Yosys）→ floorplan、macro placement、PDN → placement＋resizer → CTS → global／detailed routing、antenna、fill cell → RC 萃取（OpenRCX）→ STA（OpenSTA）、IR（PSM）→ GDS 輸出（Magic、KLayout）、DRC、XOR、LVS（Netgen） | LibreLane 3.0.14 `librelane/flows/classic.py` 的 `Steps`（第 40–121 行） |
| 4 CTS 的 plugin | `OpenROAD.CTS` 換成 `Arvinsa.CTSNoInsertionDelay` | config 的 `meta.substituting_steps`；`pnr/librelane_plugin_arvinsa/__init__.py`；ADR-0016 |
| 6 SPEF（3 種 RC） | 每個 RCX corner 一份 SPEF；corner 名稱的 nom／min／max | `librelane/steps/openroad.py` 的 `class RCX`；config 的 `STA_CORNERS` |
| 7 的 15 個 corner、SDF | 5 個 PVT × 3 種 RC；`OpenROAD.STAPostPNR` 輸出 SDF，本專案沒有拿它做時序模擬 | config 的 `STA_CORNERS`；`librelane/steps/openroad.py` 的 `STAPostPNR`；報告 §5 Phase 4「PG netlist 的 gate-level 模擬」 |
| 8 的 GDS | Magic 與 KLayout 各輸出一份，`final/` 用 KLayout 的 | config 的 `PRIMARY_GDSII_STREAMOUT_TOOL` |
| EQY 不在 LibreLane 裡 | `Yosys.EQY` 在步驟清單裡，但 `RUN_EQY` 預設關閉，本 repo 用自己的 `make eqy-soc`／`eqy-caravel` | `librelane/flows/classic.py` 第 255–258 行；`Makefile` 第 307 行（`eqy-soc`）、第 192 行（`eqy-caravel`） |
| repo 的 signoff checker | `check_signoff.py`、`check_soc.py`、`review_criteria.py`、run guard | `pnr/soc_top/run.sh`；流程文件 §4.6；報告 §4.2 |
| gate-level 模擬 | RTL 與最終 netlist 每個 cycle 比對；也跑 PG netlist | `Makefile` 的 `gl-soc`、`gl-soc-powered`、`gl-caravel`；流程文件 §4.7 |
| IR（max power pattern） | 在最終 netlist 上 dump VCD，wrapper 從 Caravel 的 pad 起算，上限 20 mV；Hazard3 版 `soc_top` 用同一個 pattern（`ir-soc`） | `Makefile` 的 `ir-caravel`（第 205 行）、`ir-soc`（第 214 行）；README.md 第 56 行 |
| Caravel 整合 | wrapper 用同一條流程再跑一次 | README.md 第 79 行（`make harden D=user_project_wrapper`） |
| ChipFoundry precheck | `cf-precheck` 1.3.7，結果 PASS | 報告 §2、§6.4；`Makefile` 的 `precheck-caravel`（第 259 行）；ADR-0019 決定 5 |
| 下線 | 本專案沒有做 | ADR-0019 決定 1 |
| 一鍵 regression（3 條） | `make regress`、`regress-picorv32`、`regress-caravel`；依序跑 RTL 驗證到 IR（`regress-picorv32` 的 IR 只在 harden 裡檢查）與 precheck（只有 `regress-caravel`）；只認乾淨 worktree | `scripts/regress.py` 的 `TARGET_LISTS`（第 72–82 行）；報告 §4.3 |

### 排版的做法

- 橫式：報告 PDF 的建置只在圖的高寬比 ≤ 0.8 時給 100% 頁寬，所以排成 6 列、每列最多 4 格。中文版 1321 × 1013 pt，英文版 1363 × 1000 pt；縮到 16 cm 頁寬時，框內的字約相當於 6 pt，和 `soc_caravel_*.png` 差不多。
- 同一列的左右順序由 graphviz 決定，不是 `rows` 寫的順序。engine 會把每一列的中間那格（第 len//2 格）和下一列的中間那格用看不見的邊連起來，所以 `rows` 把每列想放在最左邊的框（`rtl`、`rtlv`、`synth`、`rt`、`chk`、`caravel`）寫在中間的位置。
- 跨框的箭頭（輸入 → LibreLane、RTL 驗證 → LibreLane、LibreLane → repo signoff → 晶片層級）畫成框對框：改成指到某一格時，那一列的最後一格會被拉到最左邊。
- LibreLane 框的標題保持很短，從 SRAM 指到第 2 步的箭頭才不會穿過標題文字。

### 讀資料時注意到的事（第 11 節）

1. LibreLane 的 Classic flow 也有 `Yosys.EQY`，但 `RUN_EQY` 預設是 `False`，本 repo 沒有打開；圖上的 EQY 是 repo 自己的 `signoff/eqy/run_eqy.py`，比對合成 netlist 與最終 netlist。
2. `OpenROAD.STAPostPNR` 會輸出 SDF，但本專案沒有做 SDF 時序模擬（計畫的 L5 寫「SDF 只作參考」）。
3. 圖上的 fill 是 fill cell 與 decap（`OpenROAD.FillInsertion`），不是 metal fill；wrapper 的 metal fill 只做過試跑（報告 §6.5）。

## Caravel 原始檔（12、13 共用）

- 版本：caravel-lite tag `2024.09.12-1`，commit `5593d992bbeb5608b7524bc279d91237371612f1`。
- 取得方式：從 precheck 用的 docker image `chipfoundry/mpw_precheck` 複製 `/opt/caravel`。
  - 這份原始檔不在 repo 裡。重畫前放到 `.tools/caravel-lite/`（git 不追蹤，和其他外部工具一樣），取得指令寫在 `scripts/caravel_chip.py` 的說明。
  - 其中 `def/chip_io.def` 的 git blob 是 `9af4f4037af382bb01eb3ff256e4a251a585ce6a`，和 `pnr/user_project_wrapper/caravel_pwr/README.md` 第 13 行核對過的 ChipFoundry CC2509 版本相同。
- 下面寫「Caravel」的路徑都相對於這份原始檔。報告引用時寫成「Caravel（caravel-lite 2024.09.12-1）`verilog/rtl/xxx.v` 第 N 行」。
- 原始檔只讀，沒有執行裡面的程式。
- 產生日期：2026-10-16。

## 12. `caravel_chip_zh.png`、`caravel_chip_en.png`

產生指令：

```sh
cd docs/report/figures/scripts
python3 caravel_chip.py --caravel <caravel-lite 2024.09.12-1 的目錄>   # 不給時讀環境變數 CARAVEL_SRC，再沒有就讀 .tools/caravel-lite
python3 caravel_chip.py --lang zh                                      # 只畫一種語言
```

- 腳本是 `scripts/caravel_chip.py`，用系統的 python3 與 matplotlib，路徑沿用 `common.py`。
- 輸出 6.6 × 8.4 吋、220 dpi（1452 × 1854 px），A4 頁寬內不必縮小。
- 中文版字型用 Heiti TC。Heiti TC 沒有粗體，所以本設計用到的 pad 標籤（全是英數字）改用 DejaVu Sans Bold；英文版全部用 DejaVu Sans。

### 腳本讀的資料

| 圖上的東西 | 檔案 | 讀法 |
|---|---|---|
| 晶片外框 3588 × 5188 µm | Caravel `def/caravel.def` 第 6 行 `DIEAREA` | 單位 1000 dbu/µm |
| 63 顆 pad 與 4 個角落 cell 的位置 | Caravel `def/chip_io.def` 第 15830–17467 行（COMPONENTS） | 依 cell 名稱挑出 pad；外框 = placement 座標 + LEF SIZE（E／W 方向寬高對調） |
| 每顆 pad 接的訊號或電源名稱 | Caravel `def/caravel.def` 第 1927–2180 行（PINS，63 支封裝腳位） | 封裝腳位的中心點落在哪顆 pad 的外框裡，那顆 pad 就是這支腳位 |
| 類比電源環的 3 個切斷點 | Caravel `def/chip_io.def` 第 16297、16363、17279 行（`sky130_ef_io__disconnect_vdda_slice_5um`） | 5 µm 寬，圖上畫成粗黑線 |
| wrapper 位置 (333.24, 1247.5) | Caravel `def/caravel_core.def` 第 400775 行 `mprj` (121740 1037000)，加上 `def/caravel.def` 第 1921 行 caravel_core 的原點 (211.5, 210.5) | |
| housekeeping、caravel_clocking、simple_por、xres_buf 的位置 | Caravel `def/caravel_core.def` 第 400396、387159、401897、401898 行 | 同上加原點 |
| PLL、mgmt_protect 的虛線框 | Caravel `def/caravel_core.def` 第 4366–402626 行（COMPONENTS） | 這兩個模組在 caravel_core 裡已經打平，沒有自己的外框；取名稱開頭是 `pll.`、`mgmt_buffers.` 的標準元件，畫出它們原點的第 10–90 百分位範圍 |
| SRAM 位置 (350.98, 413.44)（wrapper 座標） | `pnr/user_project_wrapper/pin_plan.toml` 第 22 行 | |
| 本設計用的 GPIO 33–37 與訊號名稱 | `pnr/user_project_wrapper/pin_plan.toml` 第 32–59 行 | |
| met3 電源連接線（左右兩排紅色短線） | `pnr/user_project_wrapper/caravel_pwr/bridges.txt`（214 條，取自 efabless/caravel `27cbe49c` 的 `lef/manual_power_connections.lef`，見同目錄 README.md 第 11–20 行） | caravel_core 座標加原點 |
| Wishbone 腳位 106 支、wrapper 下緣 x 2.99–623.53 µm | `pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def` 第 3815–4238 行（第 3818 行 `wb_clk_i` 在 x 2.99，第 4186 行 `wbs_dat_o[31]` 在 x 623.53） | 名稱開頭是 `wb_` 或 `wbs_` 的腳位 |

### 寫在腳本裡的數字

| 數字 | 出處 |
|---|---|
| GPIO 與管理用訊號 pad 80 × 210.965 µm | sky130A `sky130_ef_io.lef` 第 3691 行（`sky130_ef_io__gpiov2_pad_wrapped`） |
| 電源 pad 75 × 197.965 µm | sky130A `sky130_ef_io.lef`，例如第 5482 行（`vccd_lvc_clamped3_pad`） |
| `resetb` pad 75 × 200 µm | sky130A `sky130_fd_io.lef` 第 177309 行（`sky130_fd_io__top_xres4v2`） |
| 角落 cell 200 × 204 µm | sky130A `sky130_ef_io.lef` 第 1940 行 |
| 切斷 cell 5 × 197.965 µm | sky130A `sky130_ef_io.lef` 第 2457 行 |
| housekeeping 410.23 × 550.95、caravel_clocking 100 × 100、simple_por 63.72 × 41.69、xres_buf 20 × 17 µm | efabless/caravel `27cbe49c` 的 `lef/<名稱>.lef` 第 9 行（三份 DEF 和 caravel-lite 的相同，所以 LEF 對應同一份 layout） |
| wrapper 2920 × 3520 µm | efabless/caravel `27cbe49c` `lef/user_project_wrapper.lef` 第 9 行；repo `fixed_dont_change/user_project_wrapper.def` 第 6 行相同 |
| SRAM 694.27 × 428.415 µm（框照完整數字畫；框內文字寫「約 694 × 428 µm」，因為完整數字放不進框） | 本檔第 1 張圖的說明（SOURCES.md 第 48 行，取自 macro GDS 的外框） |
| SoC 邏輯框 x ≤ 861.12、y ≤ 522.24 µm（wrapper 座標） | 本檔第 1 張圖的說明（SOURCES.md 第 49 行：扣掉 decap、fill、tap 與 SRAM 後，cell 位置的第 99 百分位）。這張圖上畫成示意框 |
| 電源 pad 的電壓與用途（圖例） | efabless/caravel `27cbe49c` `docs/source/pinout.rst` 第 312–382 行；Caravel `verilog/rtl/chip_io.v` 第 19–26 行、`caravel_core.v` 第 433–440 行 |
| 每個 net 左 54、右 53 條電源連接線 | `pnr/user_project_wrapper/caravel_pwr/README.md` 第 20 行；`bridges.txt` 依 x 分組：左側兩排各 54 條、右側兩排各 53 條（兩個 net 各一排） |
| 管理用 CPU 是 VexRiscv | Caravel `verilog/gl/caravel_core.v` 第 20207 行起的線名 `soc.core.VexRiscv.*` |

### 腳本內建的檢查（不成立就停下，不出圖）

- 63 支封裝腳位，每一支都恰好落在一顆 pad 的外框裡，每顆 pad 最多一支。
- 沒有接封裝腳位的只有 4 個角落 cell。
- 切斷 cell 剛好 3 個。

### 圖上哪些是示意

- SoC 邏輯框：取上面的第 99 百分位範圍，不是真正的模組邊界。
- PLL 與 mgmt_protect 的虛線框：只是標準元件原點的第 10–90 百分位範圍。PLL 的 99 顆元件原點其實散在 x 1994–3066 µm，框外還有元件。
- 管理用 SoC 沒有畫框：它在 caravel_core 裡已經打平，元件名稱大多沒有階層 prefix，畫不出邊界。

## 13. `caravel_clock_power_zh.png`、`caravel_clock_power_en.png`

產生指令（圖的定義是 `scripts/diagrams.py` 的 `CARAVEL_IO`，name = caravel_clock_power）：

```sh
cd docs/report/figures/scripts
DIAG_ONLY=caravel_clock_power python3 diagrams.py zh en
```

- 輸出 `diagrams/caravel_clock_power_{zh,en}.json` 與 `caravel_clock_power_{zh,en}.png/.svg`，引擎與其他架構圖相同（arvinsa-draw-diagram 的 `engine.py`），選項 `--rows`、`--ranksep 0.3`、`--no-concentrate`、`--row-minlen 1`。
- 節點顏色代表路徑：藍是 clock，橘是 reset，紫是 clock 與 reset 都經過的 block，紅是 vccd1／vssd1 電源，灰是只做設定或共用訊號的 Caravel block，綠是本設計。標題第二行（英文版第二、三行）寫了這個對照。
- 標題每行結尾是 graphviz 的 `\l`（靠左對齊），兩行才會都從左邊開始。
- `user_clock2` 沒有單獨畫節點，寫在 mgmt_protect 那一格裡並註明本設計未用。
- 引擎把 cluster 標題一律靠左。管理區、供電網路與 wrapper 三個標題前面加了不換行空白（U+00A0），把標題移開穿過 cluster 上緣的連線；英文版的供電網路標題縮短成「Caravel supply network」。這是照目前的排版調的，節點或連線改了以後要重新打開 PNG 檢查。

### 每個節點的出處

| 節點 | 內容 | 出處 |
|---|---|---|
| clock pad | 下緣；外部 CMOS 時脈輸入，不是接石英 | Caravel `verilog/rtl/caravel.v` 第 57 行；`chip_io.v` 第 288 行；位置見第 12 節的圖 |
| resetb pad | 下緣；低電位有效；3.3 V XRES pad，內建 glitch filter；上拉開啟 | Caravel `caravel.v` 第 58 行；`chip_io.v` 第 301–304、318 行 |
| vccd1／vssd1 pad | 右緣各一顆，相距約 2.2 mm | Caravel `def/chip_io.def` 第 17057、16653 行；`.claude/skills/caravel-user-project-integration/SKILL.md` 規則 3（第 27 行） |
| PLL | `digital_pll` 的參考輸入 `osc` 接 clock pad 的 `clock_core` | Caravel `caravel_core.v` 第 546 行 |
| housekeeping | 開機時 `pll_ena <= 0`、`pll_bypass <= 1`；韌體寫暫存器啟用 PLL、清掉 bypass（housekeeping SPI 位址 0x08／0x09，從 Wishbone 是 0x2610_000C／0x2610_0010）；reset 暫存器（SPI 位址 0x0b）產生 `ext_reset` | Caravel `housekeeping.v` 第 1040–1041、1097–1131、1043、1107–1108、509–519 行；`verilog/dv/caravel/defs.h` 第 122–125 行 |
| xres_buf | 3.3 V 的 `rstb_h` 轉成 1.8 V 的 `rstb_l` | Caravel `caravel_core.v` 第 1390–1399 行；`xres_buf.v` 第 16–19 行 |
| simple_por | 上電重置，實際電路延遲約 15 ms，輸出 `porb_l` 給 caravel_clocking | Caravel `simple_por.v` 第 35–45 行；`caravel_core.v` 第 1377–1387、523 行 |
| caravel_clocking | `caravel_clk`：開機時（`ext_clk_sel` = `pll_bypass` = 1）是 `ext_clk`；PLL 啟用後是 `pll_clk` 經 `clock_div` 除頻 | Caravel `caravel_clocking.v` 第 49、55–79、93–95 行；`caravel_core.v` 第 524、532、594 行 |
| | `resetb_async = porb & resetb & (!ext_reset)` | `caravel_clocking.v` 第 51 行 |
| | `caravel_rstn`（= `resetb_sync`）：3 位元移位暫存器在 `core_clk` 下降緣移位，放開後第 3 個下降緣變高 | `caravel_clocking.v` 第 101–112 行；`caravel_core.v` 第 534 行 |
| 管理用 SoC | 收到同一組 `caravel_clk` 與 `caravel_rstn` | Caravel `caravel_core.v` 第 281–282 行 |
| mgmt_protect | `user_clock = caravel_clk & mprj_logic1[1]`、`user_reset = (~caravel_rstn) & mprj_logic1[0]`、`user_clock2 = caravel_clk2 & mprj_logic1[2]`；`mprj_logic1` 是 vccd1 區的 tie-high 輸出（固定為 1） | Caravel `mgmt_protect.v` 第 232–234、122–128 行 |
| | 接到 wrapper 的 `wb_clk_i`、`wb_rst_i`、`user_clock2` | Caravel `caravel_core.v` 第 408–410、443–444、468 行 |
| Caravel 的 met4 ring | 5 µm 寬 | `caravel-user-project-integration` SKILL.md 規則 3（第 27 行）；ADR-0019 第 82 行 |
| met3 電源連接線 | 只接 wrapper ring 的左右兩側，每個 net 左 54、右 53 條 | 同上；`pnr/user_project_wrapper/caravel_pwr/README.md` 第 20 行 |
| wrapper core ring | vccd1／vssd1 | `pnr/user_project_wrapper/config.json` 第 65–77 行 |
| soc_top | `clk = wb_clk_i`、`resetn = ~wb_rst_i`、電源接 vccd1／vssd1 | `rtl/caravel/user_project_wrapper.v` 第 125–129 行 |
| | 週期 44 ns | `pnr/user_project_wrapper/config.json` 第 53–55 行 |
| | IR 從 pad 起算 19.56 mV，上限 20 mV | repo 根目錄的 `README.md` 第 56 行；本檔第 9 張圖的說明 |
| user_clock2 | 本設計未用 | `rtl/caravel/user_project_wrapper.v` 第 175 行 |

### 讀資料時注意到的事（第 12、13 節）

1. **`wb_rst_i` 不是管理用 CPU 產生的**：它和 CPU 收到的 reset 是同一個 `caravel_rstn`，只經過 mgmt_protect 反相（Caravel `caravel_clocking.v` 第 101–112 行、`mgmt_protect.v` 第 232 行）。拉起是非同步的，只有放開時對齊時脈的下降緣。
   - ADR-0019 決定 8（第 31 行）寫「由管理用 SoC 在 `wb_clk_i` 下產生」，`rtl/caravel/wb_host_bridge.v` 第 25 行註解寫「synchronous to clk」，兩處都和原始碼不同。第 13 節的圖照原始碼畫。
2. **GPIO 36、37 的 pad 比 wrapper 下緣還低**：pad 在 y 1124–1204 與 908–988 µm，wrapper 從 y 1247.5 開始，所以這兩支 pad 在管理區旁邊（Caravel `def/caravel.def` 第 2056–2075 行）。wrapper 上對應的腳位仍在 wrapper 左緣（`fixed_dont_change/user_project_wrapper.def`），中間由 Caravel 的 GPIO 控制電路接過去。

## 讀資料時注意到的事

1. **GND 的 CSV 電壓以 1.60 V 為基準**：`net-vssd1.csv` 的節點電壓在 1.592–1.597 V，不在 0 V 附近。
   - PSM 解 vssd1 時供電值也設成 1.60 V：`irdrop.rpt` 中 vssd1 的「Supply voltage : 1.60e+00 V」。
   - 網路是線性的，所以 1.60 − V 就是 GND 端的 IR drop。最大值 7.649 mV 與報表、`results.json` 一致。
   - 直接讀 CSV 的人要注意這一點。
2. **SRAM 在 IR 的 CSV 裡只有一個電源節點**：`u_soc.sram0` 的 vccd1、vssd1 各只有一列，位置在 macro 中心 (698.1, 627.6)。
   - 所以 macro 內部的壓降分布看不到，熱圖上 SRAM 框裡只有一個點。
   - 這是 PSM 對 macro 的建模方式（推測，沒有查證）。
3. **wrapper 的 IR 從 pad 起算，所以遠離 SoC 的地方也有壓降**：VDD 壓降的中位數 7.57 mV，最小 3.07 mV。
   - 原因是電流要先經過 Caravel 的 ring 與電源連接線才到 wrapper（`pdn-ir-drop` skill 第 48 行）。
   - 壓降最大的點在 SoC 左下角：VDD (424.6, 68.0)、GND (270.7, 141.4)，都在離 pad 最遠的那一側。
4. **補 fill 前 FOM 的整塊平均 41.1% 高於下限，但 SoC 一帶的 window 最低只有 19.4%**，在 (350, 210)。補 fill 後剩下的 15 個低於下限的 window 也都在 SRAM 下方這一帶，與 `runs/p7_review/fill_trial/README.md` 的結論一致。
5. 補 fill 後 met4 最高的 window 密度 59.7%，距離上限 60% 只差 0.3 個百分點（fill_trial README 已註明）。
