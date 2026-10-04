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
4. **IR drop 門檻是「VDD 降壓 + GND 抬升」的合計**：預算 = 最低供電 − slow corner 的特性化電壓（Caravel 1.62 V − 1.60 V = 20 mV，使用者決定 2026-10-04；Phase 3 以前是 5% VDD = 90 mV、只看 VDD）。LibreLane 的 `ir__drop__worst` 只有 VDD 那一個 net（它只取 `irdrop.rpt` 的第一筆），所以判定用 `check_signoff.py` 的 `[max_sum]` 把 `design_powergrid__drop__worst__net:<VDD>` 與 `<GND>` 相加。SRAM 的電流來自解析模型，不可信（ADR-0007 限制 3）。
5. **LibreLane 的 IR 是怎麼算的**（`irdrop.tcl`、OpenROAD PSM `ir_solver.cpp`）：
   - 只做 static。
   - 電流用 nom_tt 的 SPEF 加上 OpenSTA 的預設 activity，電壓取 lib 的 1.8 V。
   - 金屬電阻優先用 `set_layer_rc`（也就是 nom_tt 的 `LAYERS_RC`），tech LEF 的 RPERSQ 只是備援（415–463 行）。所以不是最大電阻的 corner；ss 的 met1 電阻約大 30%。
   - 沒有 `VSRC_LOC_FILES` 時，PDN 的所有 pin 形狀都當成理想電壓源（507–527 行），結果只代表「上層供電理想時，block 內 rail 的壓降」。soc_top 的 pin 是整條 met5／met4 strap，這樣算出 0.3 mV，不能當 signoff 依據。
   - **這版 OpenROAD（2026-02-17）只要 net 有 pin，`-source_type`（FULL／BUMPS／STRAPS）就被忽略**，一律用 pin 形狀（log：`Generate source nodes from bterms`）；只有給 `-vsrc` 檔時才只用檔案裡的點（Phase 4 實驗）。
   - **`-vsrc` 檔格式**：每行 `x_um,y_um,size_um,voltage`，逗號分隔（空白分隔報 `PSM-0075`）；以 (x, y) 為中心、邊長 size 的正方形內的最上層節點變成理想電源。LibreLane 的 `VSRC_LOC_FILES = {net: file}` 就是傳這個；給了它，電壓取檔案第 4 欄。
10. **macro-level 的供電模型要明講假設**（`docs/notes/ir_worst_case_soc_top.md`）：soc_top 實測（mV，VDD＋GND 合計，nom_tt／ff 電流＋ss 電阻）：所有 pin 理想 0.56／0.75、met5 每 34 µm 一點 1.1／1.5、每條 strap 一側一點 8.2／11.5、整顆一點 48／67。細的 PDN（1.6 µm strap、153 µm pitch、單一 cut 的 via5）對供電點數非常敏感。signoff 用「每條 strap 一側一點」，並用 `check_soc.py ir_sources` 確認每個點真的落在該 net 的 strap 上（點位寫死在檔案，PDN 一改就可能偏掉）。真正的接點在 chip-level 決定，那時要重算，並一起看 EM。
11. **沒有一個真實 corner 同時是最大電流與最大電阻**：電流最大是 ff（高電壓），金屬電阻最大是 ss。上限可以用「ff 的 lib 與電壓＋ss 的 `LAYERS_RC`」人為組合跑一次（只當上限用），或用 ff 的結果 × R_ss/R_ff 估算（via 電阻不隨 corner 變，所以估算偏高）。
6. **`set_pdnsim_inst_power` 是疊加**，不是取代：STA 算出的功耗與使用者給的值都用 `+=` 加到節點上（844–878 行）。要模擬功耗變成 k 倍，給 (k−1)×P；`irdrop.rpt` 的 Total power 這時與實際注入的電流對不上。
7. **metric 名稱的陷阱**：`design_powergrid__drop__average__net:*` 存的是平均**電壓**（約 1.79996），不是壓降。ground bounce（GND net 的 `drop__worst`）要自己加進判定（規則 4）。
8. **EM**：`analyze_power_grid -enable_em -em_outfile` 可以輸出每段電源線的電流（OpenROAD dcf36133 `src/psm/README.md`），再自己和 tech LEF 的 DCCURRENTDENSITY／ACCURRENTDENSITY 比對（例如 met1 2.8／6.1 mA/µm；mcon 0.36、via 0.29 mA/cut）。LibreLane 沒有開這個選項。
9. **decap 的擺放**：`filler_placement` 會把 cell 依寬度由大到小排序，再從最寬的開始貪婪填空（`FillerPlacement.cpp` 104–106、251–280），與 `DECAP_CELLS` 在清單中的位置無關。在 `FILL_CELLS` 加入更寬的 fill 會搶走 decap 的位置；要更多 decap，就在 `DECAP_CELLS` 加更寬的 decap（decap_8、decap_12）。

## 待補

改 PDN（例如 pitch ×4）後重跑 IR 的 negative test（需要整個 flow；目前 P07 只在 checker 層驗證 `[max_sum]`，P26 驗證供電點位置的檢查）。

## 待補（Gemini 審查與規劃 §7.2 指出的缺口）

- **`VSRC_LOC_FILES`**（電源接入點位置）：Phase 4 已設成「每條 met5 strap 一側一點」（規則 10）；Phase 7 Caravel 時改成 wrapper 的實際接點。
- **動態功耗**：目前 OpenSTA 用預設切換率估功耗；要準確需用模擬產生的切換活動（VCD／SAIF）。
- **EM**（electromigration，電流密度過高造成金屬線劣化）：flow 沒有檢查。Phase 4 研究做過一次（`docs/notes/ir_worst_case_soc_top.md`）：一側供電時最高是 via4 的 32%，單點供電時單一 via4 cut 超過上限（3.3 vs 2.49 mA）。
- **IR 的 negative test**：P07 只在 checker 層（Phase 4：VDD 降壓與 GND 抬升各植入 11 mV，單看任一個都在 20 mV 內、合計 22 mV 必須 FAIL）；改 PDN 後重跑 IR 需要整個 flow。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | neg-pnr P05 | 拿掉 macro 電源設定後 PSM 仍 `All shapes on net vccd1 are connected` | 已驗證：電源網路 DEF 不變 | P05 改用刪 via + LVS | `pnr/soc_top/neg_pnr.py` |
| 2026-10-03 | signoff 條件調查（核對 agent） | 規則 3 原本把 `Checker.PowerGridViolations` 與 PSM 的連接檢查寫成同一件事 | 已驗證（讀 `pdn.tcl`、`checker.py`、`ir_solver.cpp`） | 改寫規則 3，新增規則 5–9 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-04 | Phase 4 IR 研究（agent，Phase 3 版圖） | `-source_type STRAPS` 跑出來仍是 0.306 mV；4 種供電模型差 100 倍 | 已驗證：net 有 pin 時 PSM 用 pin 形狀、忽略 `-source_type`；`-vsrc` 才生效 | 規則 4、5、10、11；signoff 改一側供電＋`[max_sum]` | `docs/notes/ir_worst_case_soc_top.md`、`docs/notes/ir_study/` |
