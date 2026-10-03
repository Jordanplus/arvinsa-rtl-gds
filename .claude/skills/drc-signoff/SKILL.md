---
name: drc-signoff
description: 處理 Magic／KLayout DRC、GDS 輸出（streamout）與 XOR，或設計含 macro 而 DRC 數量不為 0、abstract DRC 出現大量錯誤、GDS 有多個 top cell 時使用。Use for DRC, GDS streamout and XOR signoff, especially with hard macros.
---

# DRC、GDS 輸出與 XOR signoff

antenna 看 `antenna-signoff`；LVS 看 `lvs-signoff`。本 repo 實例：`pnr/soc_top/check_soc.py`（magic_drc 列）、`signoff/waivers/soc_top/sram_magic_drc_baseline.json`、`pnr/soc_top/README.md`。

## 規則（已驗證）

1. **abstract 與完整 GDS DRC**：
   - abstract（`MAGIC_DRC_USE_GDS=false`）會在每條 standard cell row 報 `nwell.4`（soc_top 416 個、LibreLane CI SRAM 參考設計 532 個），因為 abstract cell 沒有 tap → 假錯誤。
   - 完整 GDS（預設）在 macro 外是 0。所以「abstract DRC = 0」（`project-plan.md` §6.3 原案）的前提不成立，改用完整 GDS。
2. **macro 內部 DRC**：
   - 標準規則對 SRAM bitcell 會報大量違規（2 KB SRAM 約 466 萬個，bitcell 用 SRAM 專用規則）。
   - 設 `ERROR_ON_MAGIC_DRC=false`，由自寫 checker 取代：macro 外框外 = 0；框內只能出現 macro 單獨檢查時也有的規則種類；總數由 golden 鎖定（`magic__drc_error__count`）。
   - macro 單獨檢查與放進設計後檢查，同一個錯誤被切成不同的框（5,579,161 vs 4,665,810，30 種規則相同），不能逐框比對。
3. **GDS 輸出**：Magic 的 GDS 可能多出 top cell（soc_top：13 個；SRAM 子 cell 改名成 `T2_*` 放進設計，原名的 160 個又沒有引用地寫出一次），`KLayout.Render` 因此失敗 → 設 `PRIMARY_GDSII_STREAMOUT_TOOL=klayout`。確認方法：從 top cell 走得到所有 macro cell（自寫 GDS 結構解析），且 KLayout XOR = 0。
4. **代價**：完整 GDS DRC 約 4.5 分鐘；`drc.magic.rpt` 約 190 MB、`drc.magic.lyrdb` 約 1 GB；解析報告 7 秒。
5. **兩套 deck 涵蓋的範圍不同**：

   | 規則 | Magic（`sky130A.tech`，完整 GDS） | KLayout（`sky130A_mr.drc`，LibreLane 傳參） |
   |---|---|---|
   | FEOL／BEOL 幾何 | 有 | 有 |
   | latch-up（LU.2／LU.3）、`nwell.4` | 有 | **沒有** |
   | nsdm／psdm 的寬度、間距、包覆 | 有 | **沒有**：557–633、639–729 行只在 `sram_exclude=true` 時跑，LibreLane 沒開 |
   | off-grid、角度 | — | 有 |
   | 浮接金屬 | — | **開不起來**：LibreLane 傳 `floating_metal`，deck 讀 `$floating_met`；`topcell`、`threads` 也對不上（deck 讀 `$top_cell`、`$thr`，實際只用 4 threads） |
   | density、antenna | 沒有 | 沒有 |

   所以「KLayout DRC = 0」不代表 latch-up、implant、density 合格。這些要看 Magic 完整 GDS DRC，density 則屬 chip-level。
6. **SRAM 在 KLayout deck 的處理**：依 cell 名稱（`-*sky130_sram_*kbyte_*`）排除 SRAM 的只有 `nwell.6`（299–326 行）；其他 SRAM 相容規則靠 `areaid:ce`（81/2）切換數值。Phase 6 換 macro 時，cell 名稱與 81/2 標記都要確認。
7. **latch-up 的區域標記**：
   - SkyWater 的預設規則是 tap 到 diffusion 6 µm。只有 `areaid.lowTapDensity`（81/14）覆蓋、而且距 padframe ≥ 50 µm 的區域，才能用 15 µm（skywater-pdk `rules/layers.html`）。
   - Magic 寫 GDS 時會自動產生 81/14（top cell 外框內縮 250 µm）；KLayout 寫的 GDS 沒有。
   - soc_top 的 primary GDS 是 KLayout 寫的，所以 chip-level 組裝時要確認 81/14 有覆蓋 soc_top，否則 6 µm 規則會大面積違規（推論）。
8. **不適用的規則**：m1–m4 的 slotting（.11／.12）與 m*.13 最大密度是銅後段（CU）專用，sky130 是鋁後段，不必檢查。

## 金屬密度與金屬填補（density／metal fill）

晶圓廠要求每層金屬在每個 700 µm 視窗內的密度在一定範圍內（避免化學機械研磨不均），tapeout 必檢。現況（已查證，LibreLane 3.0.14）：
- `OpenROAD.FillInsertion` 放的是 standard cell filler 與 decap，**不是金屬填補**。
- `KLayout.Filler`、`KLayout.Density`、`Checker.KLayoutDensity` 只在 Chip flow，而且 sky130A 的 PDK config 沒有提供它們需要的腳本，會被略過。Classic flow 完全不檢查 density。
- 規則數值：下限 35%（met5 45%）只寫在 PDK 的 Magic `check_density.py`；tech LEF 只有上限 70%。
- ChipFoundry 的 cf-precheck 只檢查上限（`met_min_ca_density.lydrc`）。它的 `metal_check` 是「不得使用 via4／met5」的檢查，不是密度。
- soc_top 實測（KLayout，700 µm 視窗）：met1 25.8%、met2 14.3%、met3 7.8%、met4 3.5%、met5 2.6%，遠低於下限，chip-level 一定要補 fill。視窗是否可以超出 die 邊界的慣例會影響最低值（li1 的最低值是 33.2% 還是 36.4%），量之前要先定義。
- macro-level 不判 density。但 macro 若畫了禁止 fill 的區域（cmmX waffleDrop），該區的密度要自己達標：SkyWater 的 (mX.-) 規則旗標是 RC，對 IP 等級是必須遵守的。

## negative test（`pnr/soc_top/neg_pnr.py`）

P10：GDS 在 (2, 2) µm（SRAM 外框外）加一條 0.05 µm 寬的 met2，同一份 GDS 分別重跑：
- `KLayout.DRC` → `Checker.KLayoutDRC` FAIL。
- `Magic.DRC`（完整 GDS，約 4 分鐘）→ `check_soc.py magic_drc` FAIL：框外 1 個違規，框內 4,665,810 不變。

`ERROR_ON_MAGIC_DRC=false` 之後 LibreLane 不再替 Magic DRC 判 FAIL，取代它的自寫 checker 一定要有自己的植入錯誤；P10 第一版只測了 KLayout，說明卻寫兩個都測（經驗紀錄）。

P11：只改 KLayout 那份 GDS → `Checker.XOR` FAIL。

## 用完後

更新「經驗紀錄」；macro 換版本或 PDK 升版時重做 macro 單獨的 DRC baseline（`check_soc.py --make-drc-baseline`）。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | `416 Magic DRC errors found - deferred`（全是 nwell.4） | 已驗證：完整 GDS 模式為 0 | 改完整 GDS + SRAM 外框 checker | `runs/drc_gds_exp` |
| 2026-10-03 | soc_explore2 | `The layout has multiple top cells in Layout.top_cell` | 已驗證：Magic GDS 13 個 top cell | `PRIMARY_GDSII_STREAMOUT_TOOL=klayout` | `pnr/soc_top/README.md` |
| 2026-10-03 | neg-pnr P10 | 說明寫 Magic 與 KLayout DRC 都會 FAIL，程式只斷言 KLayout；自寫的 magic_drc checker 沒有被植入錯誤測過 | 已驗證（讀程式） | 補 Magic.DRC 單步重跑；結果 `[FAIL] magic_drc: 1 violations outside the SRAM outline` | `runs/neg_pnr/P10/run.log` |
| 2026-10-03 | signoff 條件調查（核對 agent） | KLayout deck 不含 LU／implant，傳參變數名對不上；81/14 只在 Magic GDS；cf-precheck 只檢查 density 上限 | 已驗證（讀 deck、PDK 文件、cf-precheck 原始碼） | 規則 5–8、density 一節 | `docs/notes/signoff_criteria_soc_top.md` |
