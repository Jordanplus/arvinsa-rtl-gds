---
name: lvs-signoff
description: LVS 失敗、macro 在 LVS 中是 black box、要驗證電源或訊號 pin 的實體連接、或處理斷線 pin（disconnected pins）時使用。Use for LVS, macro black-box scope, physical pin connectivity and disconnected-pin checks.
---

# LVS 與連接性

PDN 產生看 `pdn-ir-drop`。目前經驗較少，邊用邊補。

## 規則（已驗證）

1. **black box 範圍**：`MAGIC_EXT_USE_GDS=false`（預設）時 macro 用 LEF 抽象圖萃取，LVS 只驗 macro pin 的連接，不驗內部。
2. **斷線 pin**：`Odb.ReportDisconnectedPins` 沒有斷線時不產生表格，要讀 log 的 `Found 0 disconnected pin(s), of which 0 are critical.`；有表格時要檢查結尾框線（表格完整），並確認 `IGNORE_DISCONNECTED_MODULES` 仍是 sky130 預設（`check_soc.py`、`check_disconnected.py`）。
3. **macro 未用的輸出**接 RTL 具名 wire 就不算斷線（soc_top 的 `unused_sram_dout1`）。
4. **電源 pin 的實體連接**：從最終 DEF 刪掉 SRAM 電源環上的 via，單步重跑 `Magic.SpiceExtraction` → `Netgen.LVS` → `Checker.LVS`，必須 FAIL（P05：刪 8 個 via，LVS FAIL）。

## negative test

P05（電源 via）、P08（`csb1` 浮接，`check_soc.py port1_tieoff`）、P15（斷線 pin 的 log 改成有 1 個 critical pin，`check_soc.py disconnected`）。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | 斷線 pin 表格不存在 | 已驗證：0 個時不寫表 | checker 改讀 log | `pnr/soc_top/check_soc.py` |
