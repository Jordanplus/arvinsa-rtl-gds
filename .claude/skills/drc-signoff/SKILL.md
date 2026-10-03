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

## 待補：金屬密度與金屬填補（density／metal fill）

晶圓廠要求每層金屬在每個視窗內的密度在一定範圍內（避免化學機械研磨不均），tapeout 必檢。現況（已查證，LibreLane 3.0.14）：
- `OpenROAD.FillInsertion` 放的是 standard cell filler（`FILL_CELLS` = `sky130_fd_sc_hd__fill_1/_2`），**不是金屬填補**。
- LibreLane 有 `KLayout.Density` step 與 `Checker.KLayoutDensity`（metric `klayout__density_error__count`），但 **Classic flow 沒有呼叫**（`librelane/flows/classic.py` 步驟清單中沒有）。
- Phase 7 走 Caravel 時，金屬填補與密度由平台流程處理（待確認）；macro-level 交付前至少要單步跑一次 `KLayout.Density` 了解現況。

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
