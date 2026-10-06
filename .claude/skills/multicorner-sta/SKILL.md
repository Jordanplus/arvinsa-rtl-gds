---
name: multicorner-sta
description: 增減 STA corner（PVT 與 RC）、在 LibreLane 設定 corner 與每個 corner 都會執行的 hook、做時序 what-if（只重跑 STA：改週期、duty cycle、uncertainty、derate）、從 STA 結果推最小週期，繞線前量 resizer 看不到的 corner（`STAMidPNR` 只看預設 corner，`PNR_CORNERS` 沒設就只有 nom_tt；flow 中途 state 裡其他 corner 的 metrics 是 placement 前的舊值），或 corner 增加後 PnR 時間暴增時使用。PnR 不納入的 corner 為什麼不能只靠餘量補看 drv-timing-closure；corner 清單怎麼定看 signoff-criteria。Use when configuring multi-corner STA in LibreLane (adding PVT corners, per-corner hooks and reports), running STA what-if experiments, deriving the minimum clock period, or when more corners slow down PnR.
---

# 多 corner STA：設定、hook、what-if 與最小週期

條件設多少看 `signoff-criteria`；SDC 怎麼寫看 `timing-constraints-sdc`；違規怎麼修看 `drv-timing-closure`。本 repo 實例：`pnr/soc_top/config.json`（`STA_CORNERS`、`LIB`、`RSZ_CORNERS`）、`pnr/soc_top/sta_extra_corner.tcl`、`pnr/soc_top/neg_pnr.py`（P01–P04、P22–P25、P30：某個 corner 的 STA 讀到別的 PVT 的 SRAM .lib，`check_soc.py sram_lib` 必須 FAIL）。

名詞：
- **PVT corner**：製程（tt／ss／ff）、溫度、電壓的組合，對應一份 .lib，例如 `ss_n40C_1v60`。
- **RC corner**：繞線寄生的 min／nom／max。LibreLane 的 corner 名稱是 `<RC>_<PVT>`，例如 `max_ss_100C_1v60`。
- **what-if**：不重跑 PnR，只用同一份版圖重算 STA，看某個條件改變後 slack 怎麼變。

## 規則（已驗證）

1. **在 design config 設 `LIB` 會取代 LibreLane 對 sky130 的整組 STA 預設**（`librelane/config/pdk_compat.py`：只有沒設 `LIB` 時才產生 `LIB`、`STA_CORNERS`、`DEFAULT_CORNER`、`TIMING_VIOLATION_CORNERS`）。所以加 corner 時三個要一起設，而且 5 個 PVT 全部列出。確認方式：`--only Verilator.Lint` 跑幾秒，看 `runs/<tag>/resolved.json`。新 corner 名稱要符合 `LAYERS_RC`（`*tt*`、`*ss*`、`*ff*`）與 RCX 規則（`nom_*`、`min_*`、`max_*`）的萬用字元。
2. **哪個 step 用哪組 corner**（`librelane/steps/openroad.py`）：resizer 類 step 用 `RSZ_CORNERS`（沒設就用 `STA_CORNERS`），CTS 用 `CTS_CORNERS`，其他 OpenROAD step 用 `PNR_CORNERS`，signoff STA 用 `STA_CORNERS`。只設 `PNR_CORNERS` 管不到 resizer。設定了用哪組 corner，也不代表演算法的每個決策都看了那些 corner：OpenROAD resizer 換尺寸時只用第一個讀進來的 .lib 評估（Phase 5 實驗 D），修違規要用對應 corner 的資料判斷，見 `drv-timing-closure` 規則 11。
   - **`PNR_CORNERS` 沒設時只用 `DEFAULT_CORNER` 一個**（353–355 行 `PNR_CORNERS or [DEFAULT_CORNER]`）。變數說明（212 行）寫「沒設就用 PDK 的 `STA_CORNERS`」，和程式不符；sky130 也沒有設它。所以 placement、global routing、`STAMidPNR` 等 step 只看 nom_tt（Phase 5：`STAMidPNR` 的 log 只讀 nom_tt 的 .lib）。寫 config 註解或判斷「哪一步看過哪個 corner」時以程式為準。
3. **corner 變多，PnR 會變慢，post-GRT 修復可能停不下來**：
   - 9 → 15 個 corner 時，多數 step 慢 1.6–2 倍。
   - `OpenROAD.RepairDesignPostGRT` 卻從 31 秒變成 35 分鐘以上沒結束。同一份輸入 state 只把 resizer 改回 9 個 corner 單步重跑，58 秒完成；9 個再加 1 個 `max_ss_n40C` 也是 4 分鐘以上不結束（`docs/phase_exit/phase4.md` 收斂過程第 1 次）。
   - 做法：resizer 用原本的 corner，新加的 corner 只在 signoff STA 判定；signoff 若在新 corner 出現 slew／cap 違規，再另外處理。
   - 這個做法的 setup 部分 Phase 5 證實不夠：resizer 看不到的 corner 用其他 corner 的餘量代替，長路徑會漏掉（`drv-timing-closure` 規則 9、11）。只給 signoff 看的 corner，在繞線前就要用規則 8 量一次。soc_top Phase 5 起 resizer 也看 ss_n40C（ADR-0013）；要讓 resizer 看新 corner，先跑弱 cell 檢查（`drv-timing-closure` 規則 10），它會列出那個 corner 要多排除的 cell。
4. **每個 corner 的 hook**（`STA_EXTRA_CORNER_TCL_FILE`）：
   - LibreLane 的 STA step 在每個 corner 讀完 SDC 之後 source 它（`scripts/openroad/sta/corner.tcl` 59–61 行），變數 `$corner_name` 是 corner 名稱；resizer、CTS 看不到。
   - 適合放 instance derate（例如 macro 只有一份 .lib 時依 corner 加 derate；有每個 PVT 的 .lib 就不需要，ADR-0010）與 LibreLane 沒有輸出的報告。
   - 報告寫法：`puts "%OL_CREATE_REPORT <name>.rpt"`，接著 report 指令，最後 `puts "%OL_END_REPORT"`，LibreLane 會存成 `<step>/<corner>/<name>.rpt`。
   - SDC 是在全域範圍執行的（`base.sdc` 自己就用 `::clock_port`），所以 SDC 裡設的變數 hook 讀得到，可用來把 SDC 的預算（例如 duty cycle）帶進 hook 的判定。
5. **兩種 what-if**：
   - 快速探索：寫一個單 corner 的 `sta` 腳本，讀 .lib、最終網表、SPEF、SDC，約 10 秒（`signoff-criteria` 規則 1：要用 LibreLane 的 `sta` binary）。
   - 正式證據：用 `python3 -m librelane.steps run --id OpenROAD.STAPostPNR` 單步重跑全部 corner，只換 config 的 `SIGNOFF_SDC_FILE` 或 `STA_EXTRA_CORNER_TCL_FILE` 的複本（`neg_pnr.py` 的 `sta_rerun()`）。SDC 複本要把 `source` 的檔案展開（`flat_sdc()`），因為 `[info script]` 會指到複本所在的目錄。
6. **最小週期要從關鍵路徑推，不能用 `report_clock_min_period`**（它排除半週期路徑，`signoff-criteria` 規則 8）：
   - 整週期路徑：slack 隨週期 1:1 變化。
   - 半週期路徑（一個 edge 送、相反 edge 收）：可用時間是半個週期扣掉 duty cycle 偏差，slack 每 1 ns 週期只變 0.5 −（duty 偏差比例）ns。
   - T_min = T −（slack ÷ 斜率），取所有路徑類型中最大的。
7. **PnR 中途的 STA（`STAMidPNR`）只分析 `PNR_CORNERS`，沒設就只有 `DEFAULT_CORNER`（規則 2）**。flow 中途 `state_out.json` 裡非 tt corner 的 timing／DRV metrics，是 placement 前的 `STAPrePNR` 寫的舊值，一路沿用到 `STAPostPNR` 才被覆蓋（Phase 5：第 38 步 state 的 nom_ss_n40C setup −15.5 ns 來自第 12 步；第 37 步之後實際是 −7.3 ns）。所以中途不要用 state 的 metrics 判斷非 tt corner；某一步自己量到什麼，看該步的 `or_metrics_out.json`（`librelane-run-debug` 規則 4）。決策要看 `STAPostPNR`；繞線前要看某個 corner，用規則 8。
8. **繞線前量 resizer 看不到的 corner**（Phase 5 實作並用來比較兩個單步重跑）：
   - 用 `librelane-run-debug` 規則 3 的 `eject` 匯出一個 resizer step（例如 `OpenROAD.ResizerTimingPostCTS`），config 複本的 `RSZ_CORNERS` 加上要看的 corner，匯出的環境就會讀那些 corner 的 .lib 與每個 corner 的 RC。
   - 把 `run.sh` 最後一行換成自己的 Tcl：`source $::env(SCRIPTS_DIR)/openroad/common/io.tcl` 之後設 `::env(CURRENT_ODB)` 為要量的 ODB（`_env.tcl` 會先設成這一步的輸入，要在 source 之後蓋掉），再 `read_current_odb`、`set_propagated_clock [all_clocks]`、`source .../common/set_rc.tcl`、`estimate_parasitics -placement`，每個 corner 用 `worst_slack -corner <c> -max/-min` 與 `total_negative_slack -corner <c> -max/-min`（LibreLane `sta/corner.tcl` 的寫法）。OpenROAD `dcf36133` 的 `report_worst_slack` 沒有 `-corner`（`STA-0562`）。
   - 這是 placement 階段的估計，只用來比較「同一個量法下」兩份 ODB 的差別。Phase 5 的對照組：這個量法 ss_n40C −7.32 ns，繞線後 signoff −4.16 ns。

## 已知陷阱

| 陷阱 | 對策 | 出處 |
|---|---|---|
| 只設 `PNR_CORNERS`，以為 resizer 也跟著改 | 用 `RSZ_CORNERS`（規則 2） | Phase 4 讀 `openroad.py` |
| 照變數說明以為 `PNR_CORNERS` 沒設就等於 `STA_CORNERS`（soc_top config 的 `//STA_CORNERS` 註解曾這樣寫） | 程式是只用 `DEFAULT_CORNER`（規則 2）；以程式為準 | Phase 5 讀 `openroad.py` 353–355 行與 `STAMidPNR` 的 log |
| 拿 flow 中途 `state_out.json` 的非 tt corner metrics 當「這一步之後」的結果 | 那是 `STAPrePNR` 的舊值（規則 7）；看該步的 `or_metrics_out.json`，或用規則 8 自己量 | Phase 5 第 2 次 harden 分析 |
| 只設 `LIB`：`STA_CORNERS`、`DEFAULT_CORNER` 不會再由 LibreLane 自動產生（讀 `pdk_compat.py` 的條件得知，沒有實跑只設 `LIB` 的情況） | 三個一起設，跑 lint-only 確認 `resolved.json`（規則 1） | Phase 4 |
| 在檔尾再 `create_clock` 同名 clock 來改波形，可能改掉掛在原 clock 上的約束（依 SDC 語意推測，未實測） | 改波形時直接編輯原本那一行（`neg_pnr.py` 的 `CREATE_CLOCK`） | Phase 4 設計 P22–P24 時 |

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | soc_top Phase 4 第 1 次 harden（15 corner） | `RepairDesignPostGRT` 35 分鐘以上沒結束；取樣看到每加一顆 buffer 就重做一次增量 global routing | 已驗證（單步重跑對照）：resizer 看 15 corner 時才發生；推測：溫度反轉 corner 的違規量讓修復走到很慢的路徑 | `RSZ_CORNERS` = 原本 9 個（規則 3） | `runs/p4_harden_soc_1_stopped/`（本機） |
| 2026-10-06 | Phase 5 第 2 次 harden-soc（Hazard3，`2251c4a`，`../arvinsa-rtl-gds-p5h3`） | `Setup violations found in the following corners: max_ss_n40C_1v60, min_…, nom_…`（max −4.158 ns、81 條）；resizer 看得到的 ss_100C +0.955 | 已驗證：ss_n40C 不在 `RSZ_CORNERS`（規則 3 的做法），resizer 看不到；細節在 `drv-timing-closure` 經驗紀錄。單步重跑 `ResizerTimingPostCTS` 加 3 個 ss_n40C corner（規則 8 量）：ss_n40C setup −7.32 → +0.33 ns，但 ss_n40C hold 變 −0.26 ns（SRAM 讀出暫存器） | ADR-0013：`RSZ_CORNERS` 加 ss_n40C、setup 餘量 0.1 ns；第 3 次 harden ss_n40C setup −0.381 ns（9 條），週期改 44 ns（ADR-0004） | `runs/p5_h3_harden2.log`、`drv-timing-closure` 經驗紀錄 |
| 2026-10-06 | 回頭看規則 7 的舊說法（Phase 3「`STAMidPNR` 在 ss 報 7761 個 slew 違規」） | — | 已驗證：`STAMidPNR` 只看 `DEFAULT_CORNER`（規則 2），所以那不是它量的；推測：是 `STAPrePNR` 留在 state 裡的值（Phase 3 的 run 已刪，無法確認） | 規則 7 改寫 | `librelane/steps/openroad.py` 353–355 行 |
| 2026-10-04 | 單 corner `sta` 實驗（Phase 3 網表） | 半週期路徑套上 2.25 ns 的下降緣→上升緣 uncertainty 後，ss slack 0.83 ns；`report_check_types -min_pulse_width -min_period` 只列每種檢查最差的一個 pin | 已驗證 | 用於 `check_soc.py pulse_width` 的解析 | Phase 4 exit review |
