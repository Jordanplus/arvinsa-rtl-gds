---
name: lvs-signoff
description: LVS 失敗、macro 在 LVS 中是 black box（macro 在最終 GDS 裡是空的或內容錯了，LVS 照樣 PASS）、要驗證電源或訊號 pin 的實體連接、或處理斷線 pin（disconnected pins）時使用。Use for LVS, macro black-box scope, physical pin connectivity and disconnected-pin checks.
---

# LVS 與連接性

PDN 產生看 `pdn-ir-drop`。目前經驗較少，邊用邊補。

## 規則（已驗證）

1. **black box 範圍**：`MAGIC_EXT_USE_GDS=false`（預設）時 macro 用 LEF 抽象圖萃取，LVS 只驗 macro pin 的連接，不驗內部。
   - 所以 macro 在最終 GDS 裡是空的或內容錯了，LVS 照樣 0 個錯誤。Phase 6 第一輪：OpenRAM 的 LEF 沒有 `FOREIGN`，KLayout 輸出的 GDS 裡 SRAM 沒有任何圖形，LVS、KLayout DRC、Magic DRC 位置比對都 PASS，只有 XOR 抓到。macro 的版圖內容要另外查：XOR = 0，以及 `scripts/check_macro_gds.py`（最終 GDS 裡 macro 的每個 cell 與 macro 自己的 GDS 完全相同，`hard-macro-integration` 清單）。
   - 同理，LEF 的腳位位置錯了（兩支腳位的 RECT 對調）LVS 也看不到：它照 LEF 的位置接線，萃取出的 macro 只有腳位。LEF 與 GDS 的幾何要在 view QA 比（`check_macro_views.py pinpos`、`obs`；Phase 6 獨立審查 H1、H2）。
2. **斷線 pin**：`Odb.ReportDisconnectedPins` 沒有斷線時不產生表格，要讀 log 的 `Found 0 disconnected pin(s), of which 0 are critical.`；有表格時要檢查結尾框線（表格完整），並確認 `IGNORE_DISCONNECTED_MODULES` 仍是 sky130 預設（`check_soc.py`、`check_disconnected.py`）。
3. **macro 未用的輸出**接 RTL 具名 wire 就不算斷線（soc_top 的 `unused_sram_dout1`）。
4. **電源 pin 的實體連接**：從最終 DEF 刪掉 SRAM 電源環上的 via，單步重跑 `Magic.SpiceExtraction` → `Netgen.LVS` → `Checker.LVS`，必須 FAIL（P05：刪 8 個 via，LVS FAIL）。

## negative test

P05（電源 via）、P08（`csb1` 浮接，`check_soc.py port1_tieoff`）、P15（斷線 pin 的 log 改成有 1 個 critical pin，`check_soc.py disconnected`）。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | 斷線 pin 表格不存在 | 已驗證：0 個時不寫表 | checker 改讀 log | `pnr/soc_top/check_soc.py` |
| 2026-10-10 | Phase 6 步驟 4b 第一輪 harden（`221822a`，兩個 CPU） | 最終 GDS 的 SRAM 是空的，LVS 0 個錯誤、signoff 只有 `design__xor_difference__count` FAIL | 已驗證：LVS 用 LEF 抽象圖萃取 macro（規則 1）；KLayout stream-out 因 LEF 沒有 `FOREIGN` 沒放進 SRAM 的圖形 | 規則 1 補說明；防護在 `hard-macro-integration`（Q13、`check_macro_gds.py`、P67、P68） | `docs/notes/openram_phase6_bringup.md` 步驟 4b 第一輪 |
