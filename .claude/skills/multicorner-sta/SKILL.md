---
name: multicorner-sta
description: 增減 STA corner（PVT 與 RC）、在 LibreLane 設定 corner 與每個 corner 都會執行的 hook、做時序 what-if（只重跑 STA：改週期、duty cycle、uncertainty、derate）、從 STA 結果推最小週期，或 corner 增加後 PnR 時間暴增時使用。PnR 不納入的 corner 怎麼用餘量補看 drv-timing-closure；corner 清單怎麼定看 signoff-criteria。Use when configuring multi-corner STA in LibreLane (adding PVT corners, per-corner hooks and reports), running STA what-if experiments, deriving the minimum clock period, or when more corners slow down PnR.
---

# 多 corner STA：設定、hook、what-if 與最小週期

條件設多少看 `signoff-criteria`；SDC 怎麼寫看 `timing-constraints-sdc`；違規怎麼修看 `drv-timing-closure`。本 repo 實例：`pnr/soc_top/config.json`（`STA_CORNERS`、`LIB`、`RSZ_CORNERS`）、`pnr/soc_top/sta_extra_corner.tcl`、`pnr/soc_top/neg_pnr.py`（P01–P04、P22–P25、P30：拿掉 nom_ff 的 SRAM derate，`check_soc.py sram_derate` 必須 FAIL）。

名詞：
- **PVT corner**：製程（tt／ss／ff）、溫度、電壓的組合，對應一份 .lib，例如 `ss_n40C_1v60`。
- **RC corner**：繞線寄生的 min／nom／max。LibreLane 的 corner 名稱是 `<RC>_<PVT>`，例如 `max_ss_100C_1v60`。
- **what-if**：不重跑 PnR，只用同一份版圖重算 STA，看某個條件改變後 slack 怎麼變。

## 規則（已驗證）

1. **在 design config 設 `LIB` 會取代 LibreLane 對 sky130 的整組 STA 預設**（`librelane/config/pdk_compat.py`：只有沒設 `LIB` 時才產生 `LIB`、`STA_CORNERS`、`DEFAULT_CORNER`、`TIMING_VIOLATION_CORNERS`）。所以加 corner 時三個要一起設，而且 5 個 PVT 全部列出。確認方式：`--only Verilator.Lint` 跑幾秒，看 `runs/<tag>/resolved.json`。新 corner 名稱要符合 `LAYERS_RC`（`*tt*`、`*ss*`、`*ff*`）與 RCX 規則（`nom_*`、`min_*`、`max_*`）的萬用字元。
2. **哪個 step 用哪組 corner**（`librelane/steps/openroad.py`）：resizer 類 step 用 `RSZ_CORNERS`（沒設就用 `STA_CORNERS`），CTS 用 `CTS_CORNERS`，其他 OpenROAD step 用 `PNR_CORNERS`，signoff STA 用 `STA_CORNERS`。只設 `PNR_CORNERS` 管不到 resizer。
3. **corner 變多，PnR 會變慢，post-GRT 修復可能停不下來**：
   - 9 → 15 個 corner 時，多數 step 慢 1.6–2 倍。
   - `OpenROAD.RepairDesignPostGRT` 卻從 31 秒變成 35 分鐘以上沒結束。同一份輸入 state 只把 resizer 改回 9 個 corner 單步重跑，58 秒完成；9 個再加 1 個 `max_ss_n40C` 也是 4 分鐘以上不結束（`docs/phase_exit/phase4.md` 收斂過程第 1 次）。
   - 做法：resizer 用原本的 corner，新加的 corner 只在 signoff STA 判定；signoff 若在新 corner 出現 slew／cap 違規，再另外處理。
4. **每個 corner 的 hook**（`STA_EXTRA_CORNER_TCL_FILE`）：
   - LibreLane 的 STA step 在每個 corner 讀完 SDC 之後 source 它（`scripts/openroad/sta/corner.tcl` 59–61 行），變數 `$corner_name` 是 corner 名稱；resizer、CTS 看不到。
   - 適合放 instance derate（例如 macro 依 corner 加 derate）與 LibreLane 沒有輸出的報告。
   - 報告寫法：`puts "%OL_CREATE_REPORT <name>.rpt"`，接著 report 指令，最後 `puts "%OL_END_REPORT"`，LibreLane 會存成 `<step>/<corner>/<name>.rpt`。
   - SDC 是在全域範圍執行的（`base.sdc` 自己就用 `::clock_port`），所以 SDC 裡設的變數 hook 讀得到，可用來把 SDC 的預算（例如 duty cycle）帶進 hook 的判定。
5. **兩種 what-if**：
   - 快速探索：寫一個單 corner 的 `sta` 腳本，讀 .lib、最終網表、SPEF、SDC，約 10 秒（`signoff-criteria` 規則 1：要用 LibreLane 的 `sta` binary）。
   - 正式證據：用 `python3 -m librelane.steps run --id OpenROAD.STAPostPNR` 單步重跑全部 corner，只換 config 的 `SIGNOFF_SDC_FILE` 或 `STA_EXTRA_CORNER_TCL_FILE` 的複本（`neg_pnr.py` 的 `sta_rerun()`）。SDC 複本要把 `source` 的檔案展開（`flat_sdc()`），因為 `[info script]` 會指到複本所在的目錄。
6. **最小週期要從關鍵路徑推，不能用 `report_clock_min_period`**（它排除半週期路徑，`signoff-criteria` 規則 8）：
   - 整週期路徑：slack 隨週期 1:1 變化。
   - 半週期路徑（一個 edge 送、相反 edge 收）：可用時間是半個週期扣掉 duty cycle 偏差，slack 每 1 ns 週期只變 0.5 −（duty 偏差比例）ns。
   - T_min = T −（slack ÷ 斜率），取所有路徑類型中最大的。
7. **PnR 中途的 STA（`STAMidPNR`）在非 tt corner 報上千個 slew 違規，不代表 signoff 有問題**：Phase 3 最後 signoff 是 0，同一步也報 7761 個（ss）；這些是 placement 階段的估計。決策要看 `STAPostPNR`。

## 已知陷阱

| 陷阱 | 對策 | 出處 |
|---|---|---|
| 只設 `PNR_CORNERS`，以為 resizer 也跟著改 | 用 `RSZ_CORNERS`（規則 2） | Phase 4 讀 `openroad.py` |
| 只設 `LIB`：`STA_CORNERS`、`DEFAULT_CORNER` 不會再由 LibreLane 自動產生（讀 `pdk_compat.py` 的條件得知，沒有實跑只設 `LIB` 的情況） | 三個一起設，跑 lint-only 確認 `resolved.json`（規則 1） | Phase 4 |
| 在檔尾再 `create_clock` 同名 clock 來改波形，可能改掉掛在原 clock 上的約束（依 SDC 語意推測，未實測） | 改波形時直接編輯原本那一行（`neg_pnr.py` 的 `CREATE_CLOCK`） | Phase 4 設計 P22–P24 時 |

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | soc_top Phase 4 第 1 次 harden（15 corner） | `RepairDesignPostGRT` 35 分鐘以上沒結束；取樣看到每加一顆 buffer 就重做一次增量 global routing | 已驗證（單步重跑對照）：resizer 看 15 corner 時才發生；推測：溫度反轉 corner 的違規量讓修復走到很慢的路徑 | `RSZ_CORNERS` = 原本 9 個（規則 3） | `runs/p4_harden_soc_1_stopped/`（本機） |
| 2026-10-04 | 單 corner `sta` 實驗（Phase 3 網表） | 半週期路徑套上 2.25 ns 的下降緣→上升緣 uncertainty 後，ss slack 0.83 ns；`report_check_types -min_pulse_width -min_period` 只列每種檢查最差的一個 pin | 已驗證 | 用於 `check_soc.py pulse_width` 的解析 | Phase 4 exit review |
