---
name: pdn-ir-drop
description: 電源網路（PDN）與 IR drop（供電線上的電壓降）的問題時使用。常見症狀：`PDN-0179 Unable to repair all channels`（macro 旁的窄 row）、IR 步驟 `PSM-0069` 中止（電源沒接通）、`PSM-0075 Expected four values on line`（電壓源位置檔格式）、PSM 讀完電壓源位置檔就 Signal 11、IR 結果小得不合理（沒給 `VSRC_LOC_FILES`，PDN pin 全被當成理想電源）或大得不合理、flow 的 nom_tt IR PASS 但 slow corner 或 max power pattern 超過上限（`ir_worst.py`、`make ir-soc`、`make ir-caravel`）。涵蓋 IR 的檢查方式（VDD 與 VSS 兩端 IR drop 的合計、預算保護的 slow corner、CPU max power pattern 的 switching activity、電壓源從晶片的真實 pad 起算、.lib 沒有的 macro 電流）、定 die 的 floorplan 試跑就做 IR、改 PDN 前的 what-if（strap 加寬或增加密度、`PDN_HWIDTH`）、macro 電源怎麼接、decap 怎麼放，以及 EM（目前沒有檢查）。電源 pin 的實體連接看 lvs-signoff；IR 上限怎麼推導看 signoff-criteria。Use for PDN generation errors, static IR drop analysis and limits (voltage-source locations, slow corner with max power pattern), macro power hookup, decap placement and EM (not checked yet) in OpenROAD/LibreLane.
---

# PDN 與 IR drop

電源 pin 的實體連接驗證看 `lvs-signoff`；IR drop 預算與「IR 用多大的電流」的推導看 `signoff-criteria`。

## 規則（已驗證）

1. **`PDN-0179 Unable to repair all channels`**：macro 與 core 邊界之間留下窄 row（約 6 µm），放不下 strap 去接這些 row 的電源軌。對策：讓 macro 的 halo 蓋過 core 邊界，不留 row（soc_explore1，ADR-0006 補充）。
2. **macro 電源**：core 的 met5 strap 跨過 SRAM 的 met4 電源環時，pdngen 本來就會打 via；所以 `PDN_CONNECT_MACROS_TO_GRID=false` 或拿掉 `PDN_MACRO_CONNECTIONS`，產生的電源網路逐字相同（P05 第一版）。
3. **電源連接由四個不同的檢查負責，範圍都不一樣**：
   - `Checker.PowerGridViolations`：看的是 PDN 產生時 `check_power_grid` 的結果（`pdn.tcl` 35–49）。它只涵蓋 placement 之前的 grid、tap、endcap、macro，而且到 flow 結束才出現錯誤；說明文字還寫「you may ignore these if LVS passes」（`checker.py` 327–341）。
   - IR 步驟的 PSM 連接檢查：這是實體連接，不通過時該步立即失敗（`PSM-0069`）。P05 第一版看到的 `All shapes on net vccd1 are connected` 就是這一項。
   - LVS：實體連接。
   - `Odb.ReportDisconnectedPins`：只看 ITerm 有沒有接到 net，是邏輯連接（`disconnected_pins.py` 27–33）。

   macro 的電源 pin 實體上有沒有接上，真正的證據是 PSM 與 LVS。
4. **IR drop 門檻是 VDD 與 VSS 兩端 IR drop 的合計**（VSS 端 IR drop：電流流過地線金屬電阻，讓 VSS 電位上升的量）：預算 = 最低供電 − slow corner 做 characterization 的電壓（Caravel 1.62 V − 1.60 V = 20 mV，使用者決定 2026-10-04；Phase 3 以前是 5% VDD = 90 mV、只看 VDD）。LibreLane 的 `ir__drop__worst` 只有 VDD 那一個 net（它只取 `irdrop.rpt` 的第一筆），所以檢查時用 `check_signoff.py` 的 `[max_sum]` 把 `design_powergrid__drop__worst__net:<VDD>` 與 `<GND>` 相加。macro 的電流要來自量測，不能用解析估計：PDK 附的 SRAM，.lib 功耗是解析值（ADR-0007 限制 3）；Phase 6 用 OpenRAM 產生的 SRAM 改用 SPICE 量的讀寫能量與漏電（ADR-0018 決定 10–15）；.lib 沒有的電流見規則 12。
5. **LibreLane 的 IR 是怎麼算的**（`irdrop.tcl`、OpenROAD PSM `ir_solver.cpp`）：
   - 只做 static。
   - 電流用 nom_tt 的 SPEF 加上 OpenSTA 的預設 activity，電壓取 lib 的 1.8 V。
   - 金屬電阻優先用 `set_layer_rc`（也就是 nom_tt 的 `LAYERS_RC`），tech LEF 的 RPERSQ 只是備援（415–463 行）。所以不是最大電阻的 corner；ss 的 met1 電阻約大 30%。
   - 沒有 `VSRC_LOC_FILES` 時，PDN 的所有 pin 形狀都當成理想電壓源（507–527 行），結果只代表「上層供電理想時，block 內 rail 的壓降」。soc_top 的 pin 是整條 met5／met4 strap，這樣算出 0.3 mV，不能當 signoff 依據。
   - **這版 OpenROAD（2026-02-17）只要 net 有 pin，`-source_type`（FULL／BUMPS／STRAPS）就被忽略**，一律用 pin 形狀（log：`Generate source nodes from bterms`）；只有給 `-vsrc` 檔時才只用檔案裡的點（Phase 4 實驗）。
   - **`-vsrc` 檔格式**：每行 `x_um,y_um,size_um,voltage`，逗號分隔（空白分隔報 `PSM-0075 Expected four values on line`）；以 (x, y) 為中心、邊長 size 的正方形內的最上層節點變成理想電源。LibreLane 的 `VSRC_LOC_FILES = {net: file}` 就是傳這個；給了它，電壓取檔案第 4 欄。
6. **`set_pdnsim_inst_power` 是疊加**，不是取代：STA 算出的功耗與使用者給的值都用 `+=` 加到節點上（844–878 行）。要模擬功耗變成 k 倍，給 (k−1)×P；`irdrop.rpt` 的 Total power 這時與實際注入的電流對不上。
7. **metric 名稱的陷阱**：`design_powergrid__drop__average__net:*` 存的是平均**電壓**（約 1.79996），不是壓降。VSS 端 IR drop（GND net 的 `drop__worst`）要自己加進檢查（規則 4）。
8. **EM**：`analyze_power_grid -enable_em -em_outfile` 可以輸出每段電源線的電流（OpenROAD dcf36133 `src/psm/README.md`），再自己和 tech LEF 的 DCCURRENTDENSITY／ACCURRENTDENSITY 比對（例如 met1 2.8／6.1 mA/µm；mcon 0.36、via 0.29 mA/cut）。LibreLane 沒有開這個選項。
   - **本 repo 目前沒有檢查 EM**：`ir_worst.py`、`ir_pattern.py`、`ir_caravel.py` 都沒開 `-enable_em`（2026-10-15 搜尋 repo 確認）；ff corner 的 IR 照跑只印 `[INFO]`，不讀電流密度。量過的只有 Phase 4 研究（單點供電時單一 via4 cut 3.3 mA，超過上限 2.49 mA，`docs/notes/ir_worst_case_soc_top.md`）與 Phase 5 的 what-if（via4 以單一 cut 計 78%，met5 加寬後 18%，ADR-0017）。
   - 記在放寬清單 I12（列為下線前要做）、`docs/phase_exit/phase7.md` 已知限制 4。
   - 自動檢查：沒有。新 checker 依 ADR-0021 決定 3 留到下一個專案開始時做（照 ADR-0020 決定 2 的做法：這次只寫進流程與 skill）。**範圍**（使用者 2026-10-15 選「電源網路 EM (建議)」，ADR-0021 決定 8）：PDN 的 strap 與 via，用 `analyze_power_grid -enable_em` 輸出每段的電流，和 tech LEF 的電流密度上限（DCCURRENTDENSITY／via 每 cut）比對；電流用 CPU max power pattern，在 ff 與 ss corner 都要檢查；植入錯誤至少有「strap 改窄」與「via 改成單一 cut」兩種。訊號線（含 clock）的 EM 不在範圍，OpenROAD 沒有現成檢查，仍只用估算（`cts-clock-tree` 規則 8）。
9. **decap 怎麼放**：`filler_placement` 會把 cell 依寬度由大到小排序，再從最寬的開始貪婪填空（`FillerPlacement.cpp` 104–106、251–280），與 `DECAP_CELLS` 在清單中的位置無關。在 `FILL_CELLS` 加入更寬的 fill 會搶走 decap 的位置；要更多 decap，就在 `DECAP_CELLS` 加更寬的 decap（decap_8、decap_12）。
10. **電壓源位置要明講是假設，checker 也要擋住比假設樂觀的設定**（Phase 4 獨立審查：電壓源大小改 2000 µm 或移到 strap 中間，原本都 PASS；`check_soc.py ir_sources` 現在要求大小 ≤ strap 寬度、soc_top 的點在 strap 左端，P27、P28）。
    - 細的 PDN（1.6 µm strap、153 µm pitch、單一 cut 的 via5）對電壓源的點數非常敏感：同一份 soc_top layout，「所有 pin 理想」「met5 每 34 µm 一點」「每條 strap 一側一點」「整顆一點」四種電壓源位置差約 100 倍（數字在 `docs/notes/ir_worst_case_soc_top.md`）。
    - 點位寫死在檔案，PDN 一改就可能偏掉，所以每次 harden 由 `check_soc.py ir_sources` 確認每個點真的落在該 net 的 strap 上。
    - 電壓源位置要從晶片的真實 pad 起算（規則 12 最後一點，Phase 7 已做到）；block 層級的「每條 strap 一側一點」只是 pad 位置未知時的假設。
11. **沒有一個真實 corner 同時是最大電流與最大電阻**：電流最大是 ff（高電壓），金屬電阻最大是 ss。上限可以用「ff 的 lib 與電壓＋ss 的 `LAYERS_RC`」人為組合跑一次（只當上限用），或用 ff 的結果 × R_ss/R_ff 估算。後者偏高是推論，沒有實驗比較：本 repo 的 run 沒有設 `VIAS_R`（`runs/user_project_wrapper/resolved.json` 是 null，2026-10-15 查），via 電阻沒有逐 corner 的值，乘上金屬電阻的比例會把 via 那段也放大。**這個組合不是拿來和上限比的值**：IR drop 預算保護的是 slow corner 的 setup，檢查要用 slow corner 自己的電流、電壓、電阻（規則 12；怎麼決定見 `signoff-criteria`「IR 用多大的電流」）。
12. **IR 只在預算所保護的 slow corner、用 CPU max power pattern 的電流檢查；不能只檢查 nom_tt**（ADR-0019 決定 19、20、25）：
    - **檢查什麼**：預算保護 slow corner 的 setup（規則 4），所以電流、電壓、金屬電阻都取同一個 slow corner。本 repo 兩個 slow corner（`max_ss_n40C_1v60`、`max_ss_100C_1v60`）都跑、取較大值，就不必判斷哪個電流大（Phase 6 用 OpenRAM 產生的 SRAM 讓 100°C 的電流變大）。電流來自讓 CPU 滿負載的 firmware（`fw/tests/maxpower` 三段）在最終 netlist gate-level 模擬 dump 出的 switching activity（`gate-level-simulation` 規則 9），不是 OpenSTA 的預設 toggle rate（Phase 7 實際比較，預設 toggle rate 高估約 2.2 倍，ADR-0019 決定 20）。
    - **不再用的檢查方式**：只檢查 nom_tt（Phase 4 接受；Phase 5 換 Hazard3 後證實不夠）、「ff 電流＋ss 電阻」的 worst-case 組合（Phase 5 起檢查它；Phase 7 改掉，因為它拿 ff 的電流比 slow corner 的預算，兩個保守假設疊在一起）。經過與數字在 ADR-0019 決定 19、20 與 `docs/phase_exit/phase5.md`；worst-case 組合現在只印成 `[INFO]` 當參考。
    - **checker**：`make ir-soc`（`pnr/soc_top/ir_pattern.py`，用 run 自己的電壓源位置）與 `make ir-caravel`（`pnr/user_project_wrapper/ir_caravel.py`，含 Caravel 供電網路），接在 harden 與 gate-level 模擬之後：每段 VCD、兩個 slow corner 取最大值 ≤ 預算，寫 `results.json`。檢查前先核對輸入（`ir_pattern.check_inputs()`，Phase 7 審查 H2、H3）：run guard、window 剛好是 5a／5b／5c、每段 VCD 的 clock 週期等於 run 的 `CLOCK_PERIOD`、VCD 標到全部 pin。negative test `make neg-ir-soc`／`neg-ir-caravel`（案例清單在 `pnr/soc_top/neg_ir.py`），兩支 checker 也在 `neg-run-guard` 裡。
    - **harden 內的早期檢查**：`pnr/soc_top/ir_worst.py` 每次 harden 用預設 toggle rate 在兩個 slow corner 檢查。它比 pattern 悲觀，所以照舊列入 PASS／FAIL；pattern 是多一道檢查，沒有放寬任何東西（ADR-0019 決定 25）。做法：用 run 自己的 `OpenROAD.IRDropReport` 設定，換成該 corner 的 `DEFAULT_CORNER`、1.60 V 電壓源、該 corner 的 ss `LAYERS_RC`、SRAM 換成「漏電加上 port 1 浮接電流」的 .lib 複本，兩個取較大值檢查 `[max_sum]`。它也確認該 corner 的設定真的套用了（log 讀的是該 PVT 的 .lib 與 SRAM 的複本、沒有 tt、電壓源是 1.60 V）；negative test `neg_pnr.py` P61、P62、P77（缺 ss 100°C 的浮接電流）、P78（上限在兩個 slow corner 之間，要用較大的那個判 FAIL）。ff corner 照跑、印 `[INFO]`，只當紀錄，**不檢查 EM**（規則 8）。各設計實際跑出來的值在 `docs/phase_exit/phase7.md` 的 signoff 表。
    - **設計換了，就要重新驗證「在哪個 corner 檢查」的依據**。依據是在別的設計上量的，不能沿用（`signoff-criteria`）。
    - **macro 的電流若有不在 .lib 裡的部分**（例如 SRAM 沒用到的 port 的浮接電流），IR 檢查要另外加上，加在該 macro 的位置、用對應 PVT 的值。Phase 6 PicoRV32 在 ff 100°C 加上後，最大壓降從邏輯區移到 SRAM 上（`docs/phase_exit/phase6.md` 第 75 行、ADR-0018 第 116、146 行）。
    - **電壓源要從真實的 pad 起算**（Phase 7，ADR-0019 決定 18）：Caravel 的 vccd1／vssd1 各只有一顆 pad（右側），經 5 µm met4 ring 與 wrapper ring 左右兩側的 met3 電源連接線才到 wrapper；只把 wrapper ring 當電壓源，同條件下低估約 9 倍（`docs/phase_exit/phase7.md` 第 246 行）。做法：把 Caravel 電源網路的形狀加進 IR 用的 DEF 複本、電壓源放在 pad，並做對照組（同一份 ODB、電壓源放回原處，結果要與原本相同，容許 DEF 轉 ODB 來回約 0.01% 的差，本 repo 用 0.1%）。
13. **改 PDN 前先做 what-if，不必每個候選都完整 harden**（Phase 5，方法已驗證）：
    - 取完成 layout 在 IR 步驟的輸入 ODB，刪掉電源 net 的 special wiring 與電源 pin 的形狀。
    - 用 LibreLane 自己的 `pdn_cfg.tcl` 加 `pdngen` 依候選值重新產生：單獨重跑 `OpenROAD.GeneratePDN`，只換 Tcl script。
    - 依新的 strap 位置重新產生電壓源位置檔，跑同樣的 IR。
    - 先用**現行**設定重新產生，必須和原 layout 的 SPECIALNETS 逐行相同、IR 完全一樣，方法才可信。
    - 每個候選約 25 秒。預測準確：what-if 估 14.14 mV，完整 harden 實際跑出來 14.13 mV。
    - 腳本與結果：`docs/notes/ir_study/phase5/`。
    - 實驗結論（sky130，一側供電，pitch 約 153 µm）：
      - 壓降主要在 met5 strap 本身，從電壓源一路到最遠端；
      - 用掉同樣的 met5 金屬量時，**加寬 strap 比增加 strap 密度有效**（4.8 µm 寬：14.14 mV；用同樣金屬量增加 strap 數量：15.62 mV），加寬還讓交叉點的 via4 從 1 個 cut 變 3 個，EM 從 78% 降到 18%；
      - 只改 met4 最多降到 22.65 mV。
    - 加寬 met5 後，時序幾乎不變；standard cell 的 placement 會小幅改變（PicoRV32 有 150 個 metric 改變）。SRAM 內的 Magic DRC 計數也會變，但位置仍全部對得上 SRAM 單獨檢查（`drc-signoff`）。
14. **IR 在 floorplan 試跑時就要成立：電壓源從真實 pad 起算、在 slow corner 檢查，gate-level 模擬能跑之後電流改用 max power pattern**（提早檢查 D2，流程回顧 ADR-0020；流程文件 4.4）。
    - 為什麼：本 repo 的 IR 模型分四個 Phase 才修完：Phase 3 的 0.3 mV 是把 PDN 的 pin 全當理想電源（規則 5）；Phase 4 一側供電；Phase 5 Hazard3 超過上限、met5 加寬（ADR-0017）；Phase 7 才用 Caravel 的真實 pad 與 max power pattern（規則 12，ADR-0019 決定 18–20）。Caravel 從計畫第一版就是首選平台，pad 位置那時就查得到；gate-level 模擬在 Phase 3 已經能跑（回顧 `retro_p0_3.md` #4）。
    - 做什麼：定 die 的 floorplan 試跑（`floorplan-congestion` 規則 7）跑到 PDN 之後就做一次 IR：電壓源位置用 pad 規劃時決定的位置（`chip-floorplan-pin-planning` 規則 2）、在預算保護的 slow corner 檢查（規則 12）。那時還沒有 netlist 可以 dump pattern 的 VCD，先用預設 toggle rate 當早期估計；gate-level 模擬能跑之後，改用 CPU max power pattern 的 VCD。
    - 通過條件：≤ 預算。結果比預算小 100 倍以上時，先檢查電壓源位置的設定（多半是電源 pin 被當成理想電源），不要當成 PASS。
    - 自動檢查：試跑沒有自動檢查（harden 內的 `ir_worst.py` 與 pattern IR 的 checker 要完整 harden 之後才有）；比預算小 100 倍以上要先查電壓源位置，這點目前沒有自動檢查，下一個專案開始時做成 checker。

## 已知限制（沒有自動檢查的部分）

- **EM 沒有檢查**：見規則 8。
- **「PDN 變細就會 FAIL」沒有 end-to-end 的 negative test**（真的改 PDN、產生完整 layout 再重跑 IR）：現有的都在 checker 層：P07、P29 驗證 `[max_sum]`，P26–P28 驗證電壓源的位置與大小，P61、P62、P77、P78 驗證 `ir_worst.py` 的 corner，`neg-ir-soc`／`neg-ir-caravel` 驗證 pattern IR 的輸入與檢查結果。改 PDN（例如 pitch ×4）後重跑 IR 的案例需要一份完整 layout，規則 13 的方法每次約 25 秒加一次完整 layout，沒有做成 regression。
- **只做 static IR**：開源 flow 沒有 dynamic IR（`signoff-criteria` 的 dynamic IR 一列；放寬清單 I12）。pattern 本身的限制（沒有 Wishbone 主機端的存取、零延遲模擬不含 glitch、三段取最大不是證明）見 ADR-0019 決定 20 與放寬清單 I08。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | neg-pnr P05 | 拿掉 macro 電源設定後 PSM 仍 `All shapes on net vccd1 are connected` | 已驗證：電源網路 DEF 不變 | P05 改用刪 via + LVS | `pnr/soc_top/neg_pnr.py` |
| 2026-10-03 | signoff 條件調查（核對 agent） | 規則 3 原本把 `Checker.PowerGridViolations` 與 PSM 的連接檢查寫成同一件事 | 已驗證（讀 `pdn.tcl`、`checker.py`、`ir_solver.cpp`） | 改寫規則 3，新增規則 5–9 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-04 | Phase 4 IR 研究（agent，Phase 3 layout） | `-source_type STRAPS` 跑出來仍是 0.306 mV；4 種電壓源位置差 100 倍 | 已驗證：net 有 pin 時 PSM 用 pin 形狀、忽略 `-source_type`；`-vsrc` 才生效 | 規則 4、5、10、11；signoff 改一側供電＋`[max_sum]` | `docs/notes/ir_worst_case_soc_top.md`、`docs/notes/ir_study/` |
| 2026-10-08 | Phase 5 exit 的獨立審查、IR 重新量測（乾淨 regress layout `7348fab`） | Hazard3 的 nom_tt 18.28 mV，flow 判 PASS；worst-case 組合 25.75 mV 超過 20 mV，via4 EM 78% | 已驗證：用 Phase 4 研究的方法重跑，nom_tt 和 flow 逐位相同 | 規則 12：加 `ir_worst.py`，每次 harden 檢查 worst-case 組合（Phase 7 改成 slow corner，ADR-0019 決定 19） | `docs/notes/ir_study/phase5/`、`docs/phase_exit/phase5.md` |
| 2026-10-08 | PDN what-if（Hazard3 layout）與加寬後的 harden（`1dee974`） | 16 個候選：met5 1.6 → 4.8 µm 時 14.14 mV（完整 harden 14.13）；用同樣金屬量增加 strap 密度 15.62；只改 met4 最好 22.65 | 已驗證：用現行設定重新產生，DEF 與 IR 完全相同 | 規則 13；兩份 config 都改 `PDN_HWIDTH` 4.8（ADR-0017） | 同上 |
| 2026-10-13 | Phase 7 wrapper 的 IR（`p7_harden2` layout，ADR-0019 決定 18） | 電壓源直接放在 Caravel met3 電源連接線落在 wrapper ring 的位置時，OpenROAD PSM 讀完電壓源位置檔就當掉（`Signal 11`），沒有錯誤訊息 | 推測（沒有查 PSM 原始碼，也沒有縮小重現）：點的位置剛好在 ring 的邊上或兩層金屬的交界，對不到單一節點 | 改放在 ring 左右兩側與每條 met5 strap 的交點；`check_soc.py ir_sources` 檢查每個點都在「strap × ring 側」上（C26）。沒有自動檢查能區分「PSM 當掉」與其他失敗：IR 步驟中止時 harden FAIL，要看 log 最後一行 | ADR-0019 決定 18；`pnr/user_project_wrapper/vsrc/` |
| 2026-10-15 | Phase 0–7 問題總檢討（ADR-0021，`docs/notes/problem_review/verify_and_merge.md` A4、A7、C1–C3） | 規則 4 仍寫 SRAM 電流是解析值；規則 10 寫「chip-level 時要重算」；規則 12 先寫已被取代的 worst-case 組合檢查方式、又寫 ff「供 EM 用」，但 repo 沒有任何腳本開 `-enable_em`；兩節「待補」的 `VSRC_LOC_FILES`、VCD 功耗已做完 | 已驗證（`review_skills.md` 3.1 Q6、Q7；`verify_and_merge.md` 1.4 Q6；repo 搜不到 `enable_em`） | 規則 4、10、12 改成現行的檢查方式；規則 8 寫明 EM 沒有檢查；規則 11 的「via 電阻不隨 corner 變」補出處並標推論；兩節「待補」改成「已知限制」 | 本檔 |
