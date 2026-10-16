---
name: lvs-signoff
description: LVS 失敗、要驗證電源或訊號 pin 的實體連接、或處理 disconnected pin（layout 上沒接到任何線的 pin）時使用：`Odb.ReportDisconnectedPins` 沒有產生表格（log 只有 `Found 0 disconnected pin(s), of which 0 are critical.`）、Caravel wrapper 頂層報幾百個 disconnected pin 但 0 個 critical、disconnected pin 該是哪幾支（`pnr/picorv32_core/check_disconnected.py`、`check_soc.py disconnected`）、`IGNORE_DISCONNECTED_MODULES`。也包括 macro 在 LVS 中是 black box：macro 在最終 GDS 裡是空的、內容錯了或 LEF 的腳位位置錯了，LVS 照樣 PASS（要靠 XOR 與 `check_macro_gds.py`）。Use for LVS, macro black-box scope, physical pin connectivity and disconnected-pin checks.
---

# LVS 與連接性

PDN 產生看 `pdn-ir-drop`。目前經驗較少，邊用邊補。

## 規則（已驗證）

1. **black box 範圍**：`MAGIC_EXT_USE_GDS=false`（預設）時 macro 用 LEF 的 abstract view 萃取，LVS 只驗 macro pin 的連接，不驗內部。
   - 所以 macro 在最終 GDS 裡是空的或內容錯了，LVS 照樣 0 個錯誤。Phase 6 第一輪：OpenRAM 的 LEF 沒有 `FOREIGN`，KLayout 輸出的 GDS 裡 SRAM 沒有任何圖形，LVS、KLayout DRC、Magic DRC 位置比對都 PASS，只有 XOR 抓到。macro 的 layout 內容要另外查：XOR = 0，以及 `scripts/check_macro_gds.py`（最終 GDS 裡 macro 的每個 cell 與 macro 自己的 GDS 完全相同，`macro-qualification` 規則 1）。
   - 同理，LEF 的腳位位置錯了（兩支腳位的 RECT 對調）LVS 也看不到：它照 LEF 的位置接線，萃取出的 macro 只有腳位。LEF 與 GDS 的幾何要在 view QA 比（`check_macro_views.py pinpos`、`obs`；Phase 6 獨立審查 H1、H2）。
2. **disconnected pin**：
   - `Odb.ReportDisconnectedPins` 沒有 disconnected pin 時不產生表格，要讀 log 的 `Found 0 disconnected pin(s), of which 0 are critical.`；有表格時要看到表格最後一行的框線（確認表格有印完），並確認 `IGNORE_DISCONNECTED_MODULES` 仍是 sky130 預設 `[sky130_fd_sc_hd__conb_1]`（LibreLane 產生表格時跳過這些 cell 與 CTS dummy load，`pnr/picorv32_core/check_disconnected.py` 開頭的說明）。
   - **預期會有 disconnected pin 時，要比對「剛好是哪幾支」，不能只比數量**：metric `design__disconnected_pin__count` 只有數量。
     - 單獨 harden 的 core：`pnr/picorv32_core/check_disconnected.py`（`make harden-core` 經 `pnr/picorv32_core/run.sh` 呼叫），`picorv32` 必須剛好是 35 支沒用到的 PCPI 輸入（`ENABLE_PCPI=0`），沒有電源 pin、沒有其他列。
     - wrapper 頂層（Caravel `user_project_wrapper`）：固定腳位裡沒用到的一定會被報出來（Phase 7 `p7_harden2`：`Found 327 disconnected pin(s), of which 0 are critical.`，`caravel-user-project-integration` 經驗紀錄 2026-10-12）。表上必須剛好是「Wishbone 輸入與 `pin_plan.toml` 裡輸入模式 GPIO 的 `io_in` 以外的輸入／inout 腳位」，加上「沒有 cell 用到的電源腳位」，只在頂層、0 個 critical。輸出、用到的輸入或 cell pin 出現在表上，或預期沒接的腳位被接上，都 FAIL（`pnr/soc_top/check_soc.py disconnected`，`DESIGNS` 的 `unused_ports`；negative test C15，`make neg-pnr-caravel`）。
     - soc_top：必須是 0 個（同一列 `disconnected`；P15）。
3. **macro 沒用到的輸出**接 RTL 宣告的 wire，就不會被列為 disconnected pin（soc_top 的 `unused_sram_dout1`）。
4. **電源 pin 的實體連接**：從最終 DEF 刪掉 SRAM 電源環上的 via，單獨重跑 `Magic.SpiceExtraction` → `Netgen.LVS` → `Checker.LVS` 這幾個 step，必須 FAIL（P05：刪 8 個 via，LVS FAIL）。

## negative test

P05（電源 via）、P08（`csb1` 浮接，`check_soc.py port1_tieoff`）、P15（disconnected pin 的 log 改成有 1 個 critical pin，`check_soc.py disconnected`）、C15（wrapper 的 disconnected pin 清單把一支用到的 Wishbone 輸入換進來、拿掉一支預期沒接線的腳位，`make neg-pnr-caravel`）。案例的完整說明在 `pnr/soc_top/neg_pnr.py` 開頭。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | disconnected pin 表格不存在 | 已驗證：0 個時不寫表 | checker 改讀 log | `pnr/soc_top/check_soc.py` |
| 2026-10-10 | Phase 6 步驟 4b 第一輪 harden（`221822a`，兩個 CPU） | 最終 GDS 的 SRAM 是空的，LVS 0 個錯誤、signoff 只有 `design__xor_difference__count` FAIL | 已驗證：LVS 用 LEF 的 abstract view 萃取 macro（規則 1）；KLayout stream-out 因 LEF 沒有 `FOREIGN` 沒放進 SRAM 的圖形 | 規則 1 補說明；對策在 `macro-qualification`（Q13、`check_macro_gds.py`、P67、P68） | `docs/notes/openram_phase6_bringup.md` 步驟 4b 第一輪 |
| 2026-10-12 | Phase 7 `p7_harden2` 第 51 步 `Odb.ReportDisconnectedPins`（wrapper 的試跑 harden） | `Found 327 disconnected pin(s), of which 0 are critical.`，照 soc_top 的 PASS 條件（必須 0）FAIL | 已驗證：全部是 wrapper 頂層沒用到的 Caravel 腳位與沒有 cell 用的電源腳位 | `check_soc.py disconnected` 改成 wrapper 的 PASS 條件（`unused_ports`），C15；2026-10-15 寫進規則 2（`review_skills.md` Q9、R15） | `caravel-user-project-integration` 經驗紀錄 2026-10-12 |
