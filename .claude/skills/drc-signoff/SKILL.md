---
name: drc-signoff
description: Magic／KLayout DRC、GDS 輸出（streamout）、XOR 時使用，尤其設計含 SRAM 等 macro：DRC 數不為 0、abstract DRC 報大量 `nwell.4`、macro 內部 DRC 怎麼判（與 macro 單獨檢查比違規位置）、GDS 有多個 top cell（`KLayout.Render` 失敗）、兩套 deck 涵蓋的規則不同（latch-up、浮接金屬）、換了自產或改名的 macro 後 KLayout DRC 在 macro 裡報 nwell.6／psdm.1（deck 依名稱 `*sky130_sram_*kbyte_*` 排除 SRAM cell）、macro 在 GDS 裡是空的而 Magic DRC 位置比對仍 PASS、metal density 與 fill。antenna、LVS 另有 skill。Use for DRC (Magic/KLayout), GDS streamout and XOR signoff with hard macros, macro-internal DRC baselines and metal density (sky130).
---

# DRC、GDS 輸出與 XOR signoff

antenna 看 `antenna-signoff`；LVS 看 `lvs-signoff`。本 repo 實例：`pnr/soc_top/check_soc.py`（magic_drc 列）、`signoff/waivers/soc_top/sram_magic_drc_baseline.json`、`pnr/soc_top/README.md`。

## 規則（已驗證）

1. **abstract 與完整 GDS DRC**：
   - abstract（`MAGIC_DRC_USE_GDS=false`）會在每條 standard cell row 報 `nwell.4`（soc_top 416 個、LibreLane CI SRAM 參考設計 532 個），因為 abstract cell 沒有 tap → 假錯誤。
   - 完整 GDS（預設）在 macro 外是 0。所以「abstract DRC = 0」（`project-plan.md` §6.3 原案）的前提不成立，改用完整 GDS。
2. **macro 內部 DRC**：
   - 標準規則對 SRAM bitcell 會報大量違規（2 KB SRAM 約 466 萬個，bitcell 用 SRAM 專用規則）。
   - 設 `ERROR_ON_MAGIC_DRC=false`，由自寫 checker 取代（`check_soc.py` magic_drc）：macro 外框外 = 0；框內**每一個**錯誤框都必須落在 macro 單獨檢查的報告中、**同規則**的框的聯集內（報告平移到 instance 位置，每個框放大容許值 δ）。
   - **只比規則種類不夠**（Phase 3 的做法）：外框內多一個已有規則的新錯誤（例如頂層 PDN 與 macro 圖形部分重疊，Magic 報的 `can't abut or partially overlap` 正好在 baseline 裡），checker 照樣 PASS，只剩 golden 總數擋，而改設計時 golden 一定重建。KLayout 不能補位：sky130 deck 對 `areaid:ce` 內的形狀有 22 處豁免。
   - macro 單獨檢查與放進設計後檢查，同一個錯誤被切成不同的框（5,579,161 vs 4,665,810，30 種規則相同），所以比「面積」不比「框」：先找完全相同的框，剩下的看是否被同規則框的聯集蓋住。
   - **δ 只給量到需要的規則**（Phase 4 獨立審查）：100 nm 原本對 30 種規則都放寬，li.3 看不到新違規的面積從 SRAM 的 0.9% 變 6.5%。改成只有 li.5、diff/tap.9（`DRC_POS_TOL_RULES`）；golden run 仍是 0 個無法解釋的框（14,166 個在聯集內）。換 macro 要重新量：Phase 6 的自產 SRAM 在晶片裡有 195 個 licon.14 框比 macro 單獨檢查長 60–90 nm（兩個 CPU 相同），加進清單是使用者的決定（ADR-0018 決定 17），因為它讓 checker 變寬（licon.14 看不到新違規的面積從 SRAM 的 0.65% 變 3.32%；這個比例的計算沒有存檔）。
   - **比對的對象不能是空的**：框內違規至少要是 macro 單獨檢查的一半（`check_soc.py magic_drc`，P69）。Phase 6 第一輪 harden 的 SRAM 在最終 GDS 裡是空的（LEF 沒有 `FOREIGN`），框內 0 個違規，「每個違規都找得到」照樣成立而 PASS；只有 XOR 抓到（`signoff-checker-qualification`「比對的對象是空的」、`hard-macro-integration` 清單）。
   - **δ 用一個已知乾淨的 run 量出來**：Phase 3 的 run 中 4,651,644 個框完全相同、13,935 個在聯集內、231 個（li.5、diff/tap.9）只多出最多 85 nm（同一個錯誤畫得比較長），δ 取 100 nm。
   - **macro 單獨的報告每次重新產生**（`pnr/soc_top/sram_drc_alone.py`：用 run 自己的 Magic.DRC 設定，只把 `DESIGN_NAME` 換成 macro，約 2.5 分鐘、寫出約 1.5 GB），並與審查過的規則數量（`signoff/waivers/`）比對。兩次產生的報告逐 byte 相同（Phase 4 實測），所以可以當固定參考。位置比對約 20 秒（兩份報告共約 450 MB）。
3. **GDS 輸出**：Magic 的 GDS 可能多出 top cell（soc_top：13 個；SRAM 子 cell 改名成 `T2_*` 放進設計，原名的 160 個又沒有引用地寫出一次），`KLayout.Render` 因此失敗 → 設 `PRIMARY_GDSII_STREAMOUT_TOOL=klayout`。確認方法：從 top cell 走得到所有 macro cell（自寫 GDS 結構解析），且 KLayout XOR = 0。
4. **代價**：完整 GDS DRC 約 4.5 分鐘；`drc.magic.rpt` 約 190 MB、`drc.magic.lyrdb` 約 1 GB；解析報告 7 秒。
5. **兩套 deck 涵蓋的範圍不同**：

   | 規則 | Magic（`sky130A.tech`，完整 GDS） | KLayout（`sky130A_mr.drc`，LibreLane 傳參） |
   |---|---|---|
   | FEOL／BEOL 幾何 | 有 | 有 |
   | latch-up（LU.2／LU.3）、`nwell.4` | 有 | **沒有** |
   | nsdm／psdm 的寬度、間距、包覆 | 有 | 有：`sram_exclude` 的兩個分支（557–633、639–729 行）跑同一組規則（nsdm.1–6a、psdm.1–6a、`nsdm_psdm_overlap`），`true` 只是先排除名稱符合 `*sky130_sram_*kbyte_*` 的 cell；LibreLane 用預設 `false`，全部形狀都查（Phase 3 誤讀成只在 `true` 時跑，Phase 6 在自產 SRAM 裡報 psdm.1 22 個才更正） |
   | off-grid、角度 | — | 有 |
   | 浮接金屬 | — | **開不起來**：LibreLane 傳 `floating_metal`，deck 讀 `$floating_met`；`topcell`、`threads` 也對不上（deck 讀 `$top_cell`、`$thr`，實際只用 4 threads） |
   | density、antenna | 沒有 | 沒有 |

   所以「KLayout DRC = 0」不代表 latch-up、density 合格。latch-up 要看 Magic 完整 GDS DRC，density 則屬 chip-level。
6. **SRAM 在 KLayout deck 的處理**：依 cell 名稱（`-*sky130_sram_*kbyte_*`）無條件排除 SRAM 的只有 `nwell.6`（299–326 行）；nsdm／psdm 只在 `sram_exclude=true` 時排除（規則 5）；其他 SRAM 相容規則靠 `areaid:ce`（81/2）切換數值。換 macro 時，cell 名稱與 81/2 標記都要確認。
   - Phase 6 實測：自產 macro（`arv_sram_*`）不符合排除樣式，flow 的 KLayout DRC 在 SRAM 裡報 27 個（nwell.6 4、psdm.1 22、m2.2 1），都是真的錯誤（預建 macro 改名成不符合樣式後重跑仍是 0），用 OpenRAM patch 修掉（ADR-0018 決定 17）。
   - 所以 macro 的 KLayout DRC 要在 macro 單獨時、用 flow 同一份 deck 與參數跑，要求 0（`ip/sram/openram/macro_klayout_drc.py`，接在 `make openram-macro`）；名稱符合排除樣式時 checker 直接 FAIL，否則一部分規則看不到（`neg-openram` K6）。Magic deck 沒有依名稱排除，只比 Magic 會漏掉這類錯誤（步驟 2 只用 Magic 比過）。
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

- **補比對粒度的漏洞時，植入的錯誤要選「舊 checker 會漏」的那一種**：規則必須是 macro 單獨時也有的，否則只比種類的舊 checker 也會抓到，等於沒測到漏洞。Magic 把整顆 SRAM 範圍當 core 區：在空白處畫一條 0.05 µm 寬的 li1 線，報的是 `li.c1`（core 區 li 寬度），SRAM 單獨時沒有這個規則；改成兩塊相距 0.1 µm 的 0.5 µm li1 方塊，報 `li.3`（li 間距），SRAM 單獨時也有（P21）。植入點要先用 KLayout 確認附近沒有 li1／licon／mcon／diff／poly／tap。

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
| 2026-10-04 | Phase 3 獨立審查（找 checker 漏洞） | 假報告在 SRAM 外框內多加一個 `li.1` 錯誤，`check_soc.py magic_drc` 仍 PASS | 已驗證（審查 agent 實驗）：checker 只比規則種類 | 規則 2 補「比位置」；位置比對證實本次 0 個無法解釋；修正與 P10b（外框內植入）列入 Phase 4 | `docs/phase_exit/phase3.md` 已知限制 14 |
| 2026-10-04 | Phase 4 位置比對 | 嚴格的「被同規則框聯集蓋住」在已知乾淨的 run 上有 231 個框不通過 | 已驗證：同一個錯誤在 soc_top 裡畫得比較長，最多 85 nm | δ = 100 nm（規則 2） | `pnr/soc_top/check_soc.py` `DRC_POS_TOL` |
| 2026-10-04 | neg-pnr P21 第一版 | 植入的 li1 細線被報成 `li.c1`，SRAM 單獨時沒有這個規則 | 已驗證：SRAM 範圍在 Magic 是 core 區 | 改兩塊方塊 → `li.3`（negative test 一節） | `runs/neg_pnr_dev/P21/run.log`（本機） |
| 2026-10-08 | Phase 5 `PDN_HWIDTH` 4.8 的兩次 harden（`1dee974`） | Magic DRC 總數 4,665,810 → 4,746,079（兩個 CPU 相同），golden 比對 FAIL | 已驗證：`check_soc.py magic_drc` PASS，框外 0；框內每一個都對得上 SRAM 單獨檢查時的位置（4,735,395 個框完全相同）。總數變多推測是加寬的 met5 跨過 SRAM 的方式改變了 Magic 的分割或計數，沒有逐規則比對 | 新 golden 採用新總數；判斷 macro 內 DRC 時靠位置比對，不要只看總數 | `signoff/golden/soc_top_hazard3/README.md` |
| 2026-10-10 | Phase 6 步驟 4b 第二輪 harden（`3ceca55`，自產 SRAM 真的進了最終 GDS） | flow 的 KLayout DRC 在 SRAM 裡報 27 個：nwell.6 4、psdm.1 22、m2.2 1；預建 macro 是 0 | 已驗證：deck 依名稱排除 `*sky130_sram_*kbyte_*`，自產 macro 名稱不符合；預建 macro 改名後重跑仍是 0，所以 27 個是自產 macro 真的錯誤（根因見 ADR-0018 決定 17） | OpenRAM patch 0002–0004 修到 0；`macro_klayout_drc.py`＋K0–K6；規則 6 | `docs/notes/openram_phase6_bringup.md` 步驟 4b 第二輪、3m |
| 2026-10-10 | Phase 6 步驟 4b 第二輪 harden | `check_soc.py magic_drc` 在 SRAM 框內有 195 個 licon.14 框不在同規則框的聯集內，比 SRAM 單獨檢查長 60–90 nm（y = 157.255 µm 一列，兩個 CPU 相同） | 已驗證（位置比對的輸出）：同一個錯誤在晶片裡被切成比較長的框，和 Phase 4 的 li.5、diff/tap.9 同類 | 使用者選加進 100 nm 容許清單（ADR-0018 決定 17）；規則 2 | `runs/p6_3m_*_signoff/soc_checks.txt` |
| 2026-10-11 | Phase 6 結案前寫回 skill，讀 deck 原文 | 規則 5 原本寫 KLayout 沒有 nsdm／psdm 規則（只在 `sram_exclude=true` 時跑），但 Phase 6 flow（預設 `false`）在 SRAM 裡報了 psdm.1 | 已驗證（`sky130A_mr.drc` 553–700 行）：`if SRAM_EXCLUDE` 的兩個分支輸出同一組規則，`true` 只是改用排除 SRAM 名稱後的圖層 | 規則 5 的表與結論、knowledge S15、README、`docs/notes/signoff_criteria_soc_top.md` 更正；這個錯誤是低估 KLayout 的涵蓋範圍，沒有讓任何 checker 變寬 | `sky130A_mr.drc` 第 553–700 行 |
