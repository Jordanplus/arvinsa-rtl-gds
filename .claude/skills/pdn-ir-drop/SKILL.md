---
name: pdn-ir-drop
description: 電源網路（PDN）產生失敗、macro 電源怎麼接、或 IR drop（供電線上的電壓降）分析與門檻時使用。Use for PDN generation errors, macro power hookup, and IR drop analysis/limits.
---

# PDN 與 IR drop

電源 pin 的實體連接驗證看 `lvs-signoff`。目前經驗較少，邊用邊補。

## 規則（已驗證）

1. **`PDN-0179 Unable to repair all channels`**：macro 與 core 邊界之間留下窄 row（約 6 µm），放不下 strap 去接這些 row 的電源軌。對策：讓 macro 的 halo 蓋過 core 邊界，不留 row（soc_explore1，ADR-0006 補充）。
2. **macro 電源**：core 的 met5 strap 跨過 SRAM 的 met4 電源環時，pdngen 本來就會打 via；所以 `PDN_CONNECT_MACROS_TO_GRID=false` 或拿掉 `PDN_MACRO_CONNECTIONS`，產生的電源網路逐字相同（P05 第一版）。
3. **PSM（`Checker.PowerGridViolations`）只查電源網路本身的 shape 是否連通**，不查 macro 電源 pin 有沒有接上；實體連接要靠 LVS。
4. **IR drop 門檻**：≤ 5% VDD（`check_signoff.py` 的 `[max]` 表，`ir__drop__worst ≤ 0.09`）。SRAM 的電流來自解析模型，不可信（ADR-0007 限制 3）。

## 待補

`VSRC_LOC_FILES` 未設的警告意義；改 PDN（例如 pitch ×4）後重跑 IR 的 negative test（需要整個 flow，目前 P07 只在 checker 層驗證 `[max]` 規則）。

## 待補（Gemini 審查與規劃 §7.2 指出的缺口）

- **`VSRC_LOC_FILES`**（電源接入點位置）：未設時 LibreLane 警告 IR drop 結果可能不準，「不是整顆晶片下線可以忽略」。macro-level 目前沒設；Phase 7 Caravel 時要依 wrapper 的電源接點設定。
- **動態功耗**：目前 OpenSTA 用預設切換率估功耗；要準確需用模擬產生的切換活動（VCD／SAIF）。
- **EM**（electromigration，電流密度過高造成金屬線劣化）：目前沒有檢查。
- **IR 的 negative test**：P07 只在 checker 層（metrics 改成 0.2 V）；改 PDN 後重跑 IR 需要整個 flow。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | neg-pnr P05 | 拿掉 macro 電源設定後 PSM 仍 `All shapes on net vccd1 are connected` | 已驗證：電源網路 DEF 不變 | P05 改用刪 via + LVS | `pnr/soc_top/neg_pnr.py` |
