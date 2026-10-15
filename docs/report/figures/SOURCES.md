# 實際成果圖的資料來源

這份清單涵蓋版圖截圖與數據圖（`layout_*.png`、`floorplan_pin_plan.png`、`timing_wrapper_corners.png`、`density_fill_trial.png`、`ir_drop_map.png`、`phase_metrics.png`）。同目錄的其他圖（`flow_*`、`checkers_*`、`roadmap_*` 等示意圖）不在這份清單。

- 產生日期：2026-10-15。
- 資料來源：正式結案 run（commit `2b04451`）的三個乾淨 worktree，路徑都在 `~/claude_prjs/` 下：
  - `arvinsa-rtl-gds-p7close2_caravel`：Caravel wrapper。
  - `arvinsa-rtl-gds-p7close2_h3`：Hazard3 SoC。
  - `arvinsa-rtl-gds-p7close2_pico`：PicoRV32。
- 腳本在 `scripts/`。共用的路徑與配色在 `common.py`，matplotlib 用系統的 python3。
- 圖上的英文說明與數字都由腳本從下列檔案讀出，或寫在腳本裡並附出處。

## 版圖截圖（1–5）

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
   - (b) 只顯示 met2–met5。訊號走線只在 SoC 周圍，met4／met5 的電源 strap 鋪滿整個 die。
   - 紅框是 SRAM，位置 (350.98, 413.44)，取自 `pnr/user_project_wrapper/pin_plan.toml` 第 22 行；大小 694.27 × 428.415 µm，取自 macro GDS 的外框。
   - 綠框是 SoC 邏輯 cell 的範圍，x ≤ 861.12、y ≤ 522.24 µm。
     - 算法：同一份 DEF 中，扣掉 decap、fill、tap 與 SRAM 後剩 25,100 顆 cell。框的上界取這些 cell 位置的第 99 百分位。
     - 也有少數 cell 在 die 邊緣，最遠到 (2911, 3506)。
2. **`layout_wrapper_soc_zoom.png`**：左下角放大，截圖範圍 (−20, −20)–(1180, 940) µm。
   - 隱藏 met4、via4、met5，讓 cell 與 met1–met3 的走線看得清楚。
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
- 圖上各模組的 cell 數，例如 CPU 9309 顆，是 global placement 當時的數字，不是最終網表的數字。
- 左下角幾個小模組（test control、boot ROM、GPIO）的標籤互相重疊。這是 `plot_floorplan.py` 的排版，沒有改。

## 7. `timing_wrapper_corners.png`

產生指令：`python3 scripts/timing_wrapper_corners.py`

- 資料：`p7close2_caravel/runs/user_project_wrapper/final/metrics.json` 的 `timing__setup__ws__corner:*` 與 `timing__hold__ws__corner:*`，15 個 corner。
- 最差 setup +0.548 ns 在 `min_ss_n40C_1v60`，最差 hold +0.187 ns 在 `max_ff_100C_1v95`。
- 與 README.md 第 56 行的「+0.548／+0.187 ns」相同。

## 8. `density_fill_trial.png`

產生指令：`python3 scripts/density_fill_trial.py`

- 資料：`runs/p7_review/fill_trial/nofill/density.log` 與 `withfill/density.log`。
- 視窗的算法與 `runs/p7_review/fill_trial/aggregate.py` 相同：
  - 700 µm 視窗；li1 與金屬步進 350 µm，FOM 步進 70 µm。
  - die 邊緣的格子依它在 die 內的面積加權。
  - 下限：li1、met1–4 35%，met5 45%，FOM 33%。
- 腳本會印出每層的整塊平均、最低視窗與超出範圍的視窗數。已核對與 `nofill/density.md`、`withfill/density.md` 逐項相同，例如：
  - 補 fill 後 FOM 有 15/1386 個視窗低於下限，最低 31.5%，在 (210, 140)。
  - 補 fill 後 met2 有 1/63 個視窗低於下限，34.8%，在 (0, 0)。
- (b)、(c) 是補 fill 後 FOM 與 met2 每個視窗的密度，畫在視窗中心；紅框是低於下限的視窗。

## 9. `ir_drop_map.png`

產生指令：`python3 scripts/ir_drop_map.py`

- 資料：`p7close2_caravel/runs/ir_caravel/ir_caravel/`。
  - `results.json`：取 `drops` 中 VDD 加 GND 合計最大的組合，是 `max_ss_100C_1v60` 的 window `5c`：11.92 + 7.65 = 19.56 mV，與 README.md 第 56 行相同。
  - 該組合的 `step/net-vccd1.csv`、`step/net-vssd1.csv`：每個 instance 電源腳一列，各 1,140,379 列。
  - `vsrc/*.vsrc`：供電點在 Caravel 唯一的 vccd1 pad (3046.49, 3302.77–3353.03) 與 vssd1 pad (3046.49, 1063.77–1114.03)。
- 壓降一律用 1.60 V − 節點電壓計算，單位 mV；每 20 µm 一格，取格內最大值。
  - 腳本會斷言 CSV 的最大壓降與 `results.json` 的值相差小於 0.01 mV：VDD 11.916、GND 7.649。

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
| (c) IR（VDD + GND） | P4 8.07 mV（一側供電、nom_tt） | README.md:25；docs/phase_exit/phase4.md:113 |
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
- (c) 各 Phase 的 IR 模型不同（見 `pdn-ir-drop` skill 第 57 行），數字不能直接比較，只表示判定值逐次變嚴。

## 讀資料時注意到的事

1. **GND 的 CSV 電壓以 1.60 V 為基準**：`net-vssd1.csv` 的節點電壓在 1.592–1.597 V，不在 0 V 附近。
   - PSM 解 vssd1 時供電值也設成 1.60 V：`irdrop.rpt` 中 vssd1 的「Supply voltage : 1.60e+00 V」。
   - 網路是線性的，所以 1.60 − V 就是 GND 抬升。最大值 7.649 mV 與報表、`results.json` 一致。
   - 直接讀 CSV 的人要注意這一點。
2. **SRAM 在 IR 的 CSV 裡只有一個電源節點**：`u_soc.sram0` 的 vccd1、vssd1 各只有一列，位置在 macro 中心 (698.1, 627.6)。
   - 所以 macro 內部的壓降分布看不到，熱圖上 SRAM 框裡只有一個點。
   - 這是 PSM 對 macro 的建模方式（推測，沒有查證）。
3. **wrapper 的 IR 從 pad 起算，所以遠離 SoC 的地方也有壓降**：VDD 壓降的中位數 7.57 mV，最小 3.07 mV。
   - 原因是電流要先經過 Caravel 的 ring 與跨接線才到 wrapper（`pdn-ir-drop` skill 第 43 行）。
   - 最壞點在 SoC 左下角：VDD (424.6, 68.0)、GND (270.7, 141.4)，都在離 pad 最遠的那一側。
4. **補 fill 前 FOM 的整塊平均 41.1% 高於下限，但 SoC 一帶的視窗最低只有 19.4%**，在 (350, 210)。補 fill 後剩下的 15 個低於下限的視窗也都在 SRAM 下方這一帶，與 `runs/p7_review/fill_trial/README.md` 的結論一致。
5. 補 fill 後 met4 的最高視窗 59.7%，距離上限 60% 只差 0.3 個百分點（fill_trial README 已註明）。
