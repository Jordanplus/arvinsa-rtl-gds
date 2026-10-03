---
name: pdn-ir-drop
description: 電源網路（PDN）產生失敗、macro 電源怎麼接、或 IR drop（供電線上的電壓降）分析與門檻時使用。Use for PDN generation errors, macro power hookup, and IR drop analysis/limits.
---

# PDN 與 IR drop

電源 pin 的實體連接驗證看 `lvs-signoff`。目前經驗較少，邊用邊補。

## 規則（已驗證）

1. **`PDN-0179 Unable to repair all channels`**：macro 與 core 邊界之間留下窄 row（約 6 µm），放不下 strap 去接這些 row 的電源軌。對策：讓 macro 的 halo 蓋過 core 邊界，不留 row（soc_explore1，ADR-0006 補充）。
2. **macro 電源**：core 的 met5 strap 跨過 SRAM 的 met4 電源環時，pdngen 本來就會打 via；所以 `PDN_CONNECT_MACROS_TO_GRID=false` 或拿掉 `PDN_MACRO_CONNECTIONS`，產生的電源網路逐字相同（P05 第一版）。
3. **電源連接由四個不同的檢查負責，範圍都不一樣**：
   - `Checker.PowerGridViolations`：看的是 PDN 產生時 `check_power_grid` 的結果（`pdn.tcl` 35–49）。它只涵蓋擺放之前的 grid、tap、endcap、macro，而且延後到 flow 結束才報錯；說明文字還寫「you may ignore these if LVS passes」（`checker.py` 327–341）。
   - IR 步驟的 PSM 連接檢查：這是實體連接，不通過時該步立即失敗（`PSM-0069`）。P05 第一版看到的 `All shapes on net vccd1 are connected` 就是這一項。
   - LVS：實體連接。
   - `Odb.ReportDisconnectedPins`：只看 ITerm 有沒有接到 net，是邏輯連接（`disconnected_pins.py` 27–33）。

   macro 的電源 pin 實體上有沒有接上，真正的證據是 PSM 與 LVS。
4. **IR drop 門檻**：≤ 5% VDD（`check_signoff.py` 的 `[max]` 表，`ir__drop__worst ≤ 0.09`）。SRAM 的電流來自解析模型，不可信（ADR-0007 限制 3）。這個門檻和 corner 電壓不一致：ss 的 1.60 V 對 Caravel 最低供電 1.62 V，只隱含 20 mV 的預算。推導方法見 `signoff-criteria`，本設計的檢討見 `docs/notes/signoff_criteria_soc_top.md`。
5. **LibreLane 的 IR 是怎麼算的**（`irdrop.tcl`、OpenROAD PSM `ir_solver.cpp`）：
   - 只做 static。
   - 電流用 nom_tt 的 SPEF 加上 OpenSTA 的預設 activity，電壓取 lib 的 1.8 V。
   - 金屬電阻優先用 `set_layer_rc`（也就是 nom_tt 的 `LAYERS_RC`），tech LEF 的 RPERSQ 只是備援（415–463 行）。所以不是最大電阻的 corner；ss 的 met1 電阻約大 30%。
   - 沒有 `VSRC_LOC_FILES` 時，PDN 的所有 pin 形狀都當成理想電壓源（507–527 行），結果只代表「上層供電理想時，block 內 rail 的壓降」。
6. **`set_pdnsim_inst_power` 是疊加**，不是取代：STA 算出的功耗與使用者給的值都用 `+=` 加到節點上（844–878 行）。要模擬功耗變成 k 倍，給 (k−1)×P；`irdrop.rpt` 的 Total power 這時與實際注入的電流對不上。
7. **metric 名稱的陷阱**：`design_powergrid__drop__average__net:*` 存的是平均**電壓**（約 1.79996），不是壓降。另外 ground bounce（vssd1 的 `drop__worst`）沒有任何門檻。
8. **EM**：`analyze_power_grid -enable_em -em_outfile` 可以輸出每段電源線的電流（OpenROAD dcf36133 `src/psm/README.md`），再自己和 tech LEF 的 DCCURRENTDENSITY／ACCURRENTDENSITY 比對（例如 met1 2.8／6.1 mA/µm；mcon 0.36、via 0.29 mA/cut）。LibreLane 沒有開這個選項。
9. **decap 的擺放**：`filler_placement` 會把 cell 依寬度由大到小排序，再從最寬的開始貪婪填空（`FillerPlacement.cpp` 104–106、251–280），與 `DECAP_CELLS` 在清單中的位置無關。在 `FILL_CELLS` 加入更寬的 fill 會搶走 decap 的位置；要更多 decap，就在 `DECAP_CELLS` 加更寬的 decap（decap_8、decap_12）。

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
| 2026-10-03 | signoff 條件調查（核對 agent） | 規則 3 原本把 `Checker.PowerGridViolations` 與 PSM 的連接檢查寫成同一件事 | 已驗證（讀 `pdn.tcl`、`checker.py`、`ir_solver.cpp`） | 改寫規則 3，新增規則 5–9 | `docs/notes/signoff_criteria_soc_top.md` |
