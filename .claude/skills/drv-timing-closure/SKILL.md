---
name: drv-timing-closure
description: 9 個 corner 的 STA 出現 setup／hold 違規，或 max slew／max cap／max fanout（DRV）違規，要調 resizer、長線修復、cell 排除、寄生估計等設定時使用；也用於設定時序目標、corner 判定與 signoff SDC。Use for setup/hold and slew/cap/fanout closure across corners in LibreLane/OpenROAD.
---

# 時序與 DRV 收斂（9 corner）

**DRV**（design rule violation，電性規則違規）= max slew（訊號轉換太慢）、max cap（負載電容太大）、max fanout（一條線接太多負載）。setup／hold 修復和 DRV 修復用同一組 resizer，會互相牽動，所以放在同一個 skill。clock tree 本身看 `cts-clock-tree`；antenna diode 的副作用看 `antenna-signoff`。

本 repo 實例與數字：`pnr/picorv32_core/README.md`（Phase 2，9 次試跑）、`pnr/soc_top/README.md`（Phase 3）、ADR-0009。

## 規則（已驗證）

1. **先設判定**：`SETUP_VIOLATION_CORNERS`、`HOLD_VIOLATION_CORNERS`、`MAX_SLEW_VIOLATION_CORNERS`、`MAX_CAP_VIOLATION_CORNERS` = `["*"]`。LibreLane 對 sky130 預設只判 tt（`librelane/config/pdk_compat.py` 第 320 行），會漏掉 ss 的 setup 違規（Phase 2 試跑 #4）。
2. **DRV 收斂清單（依實際有效的順序）**
   1. `EXTRA_EXCLUDED_CELLS` 排除 `clkdlybuf4s25_1/_2`、`clkdlybuf4s50_1/_2`：PDK 排除清單漏了，resizer 會拿延遲 cell 當一般 buffer。
   2. `LAYERS_RC`：沒設時繞線前的電容估計只有實際的一半（0.08 vs 0.178 fF/µm）；值取自 `pdk_compat.py` 262–296 行。
   3. `RUN_POST_GRT_DESIGN_REPAIR = true`，`GRT_DESIGN_REPAIR_MAX_SLEW_PCT` 30–40（50 會讓這步跑不完，見已知陷阱）。
   4. `DESIGN_REPAIR_MAX_SLEW_PCT` 30（預設 20）。
   5. `DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 µm：大面積或細長 L 形 logic 區的長線；同時減少 antenna diode（soc_explore2 → 4：slew 50 → 20、diode 224 → 61、fanout 7 → 0）。
   6. 殘留的少數違規若是繞路：降低 `PL_TARGET_DENSITY_PCT`（soc_top：68% → 55%，16 → 0，見 `floorplan-congestion`）。
3. **判讀違規**：讀 `*-openroad-stapostpnr/<corner>/checks.rpt` 的 max slew／fanout 段，依 driver 歸併成「幾條線」，再對照 `*-odb-reportwirelength/wire_lengths.csv` 的長度、driver cell、線上有沒有 diode 或 hold buffer。
4. **實作與簽核分開的約束**：`PNR_SDC_FILE` 給 PnR（可比簽核更嚴），`SIGNOFF_SDC_FILE` 只給 `OpenROAD.STAPostPNR`。兩者都 `source $::env(SCRIPTS_DIR)/base.sdc` 再改一兩項。驗證方式：同一份版圖只重跑 STAPostPNR，確認只有預期的項目改變（setup／hold 數字不變）。
5. **先找根因，再考慮放寬 signoff 上限**：殘留的少數 DRV 先查是不是繞路（`floorplan-congestion` 規則 4）。soc_top 曾經放寬到 1.0 ns（使用者決定），後來查到根因是 L 形轉角壅塞，把 `PL_TARGET_DENSITY_PCT` 從自動的 68% 降到 55% 後，0.75 ns 下全部乾淨，放寬就撤回了（ADR-0009）。真的要放寬時須由使用者決定並寫 ADR；依據可用 sky130_fd_sc_hd .lib（`default_max_transition` 1.5 ns、最嚴的 pin 1.0 ns），0.75 ns 來自 PDK 的 OpenLane 預設（`libs.tech/openlane/sky130_fd_sc_hd/config.tcl` 63 行）。
6. **macro 時序**：padded.lib 給 9 corner 共用；derate 只在 STA 生效，PnR 用 TT 等級的數字收斂（ADR-0007）。SRAM 讀出是半週期路徑（下降緣送出、上升緣接收）。
7. **hold**：hold buffer 約 2200–2500 顆，由 `PL_RESIZER_HOLD_SLACK_MARGIN` 決定。
8. **corner 變多時，resizer 用的 corner 要另外控制**：resizer 讀 `RSZ_CORNERS`（不是 `PNR_CORNERS`）。soc_top 加溫度反轉 corner 後，resizer 看 15 個 corner 時 post-GRT 修復停不下來，改回原本 9 個就正常（`multicorner-sta` 規則 2、3）。只給 signoff 看的 corner，要確認 signoff 在那些 corner 的 DRV 也是 0。

## 退回過的做法

| 做法 | 結果 | 出處 |
|---|---|---|
| 排除 `buf_1`、`clkbuf_1` | resizer 改用 `dlygate4sd3_1` 當 buffer，ss setup −3.54 ns | Phase 2 試跑 #4 |
| `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 µm | soc_explore3 在 clk pin 的 GCell 報 `GRT-0229 ... usage=65534` 中止。**原本歸因到這個設定是錯的**：之後發現不設也有一半機率出現（`librelane-run-debug` 規則 5），所以這個設定到底有沒有用，還沒有可靠的實驗 | soc_explore3；`make phase3` 第一次 |
| `GRT_DESIGN_REPAIR_MAX_SLEW_PCT` 50 | post-GRT 修復單執行緒 26 分鐘以上不結束 | soc_explore6 |
| `DESIGN_REPAIR_MAX_WIRE_LENGTH` 120 µm | 同上，13 分鐘以上不結束 | soc_explore8 |
| `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH` 400 µm | 結果與不設完全相同（GRT 估計時那些線還沒那麼長） | soc_explore9 |
| `CTS_MAX_CAP` | 沒有作用（CTS 後 DEF 逐 byte 相同） | Phase 2 試跑 #7 |

## 已知限制

detailed routing 之後才出現的 slew 違規，LibreLane Classic flow 沒有修復步驟（post-GRT 修復當下的 Remaining 已經是 0）。可能方向：detailed routing 後的 ECO 修復（OpenROAD 有，LibreLane 沒有對應 step）、改 floorplan。

## 待補：detailed routing 之後的修復（post-route ECO）

**ECO**（engineering change order）：在已繞好線的版圖上只做局部修改（換 cell 尺寸、插 buffer、局部重繞），不整個重跑。LibreLane Classic flow 在 detailed routing 之後沒有 DRV／timing 修復步驟；OpenROAD 本身可以在繞線後做 `repair_design`／`repair_timing` 再做增量繞線（推測，尚未在本專案驗證）。Phase 4（25 ns）之前要評估：寫一個讀最終 ODB → 修復 → 增量 detailed routing → 重跑 signoff 的腳本，並用 negative test 證明它有效。SDC 的寫法與 PnR／signoff 分開的原則已移到 `timing-constraints-sdc`。

## negative test（單步重跑 `OpenROAD.STAPostPNR` + 對應 checker，`pnr/soc_top/neg_pnr.py`）

P01 setup uncertainty 30 ns → `Checker.SetupViolations`；P02 hold uncertainty 5 ns → `Checker.HoldViolations`；P03 signoff SDC 加 `set_max_transition 0.05` → `Checker.MaxSlewViolations`（P01–P03 都從 run 實際用的 signoff SDC 開始改，否則 signoff.sdc 的設定會蓋掉植入）；P04 SRAM derate 10 → setup FAIL 且 hook 有印出 derate。

## 用完後

更新「經驗紀錄」；設定值變動時同步 `pnr/*/README.md` 的「設定與理由」與試跑紀錄；LibreLane 升版時重新確認行號與預設值。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore7、9 | ss corner 16 個 pin 停在 0.78–0.97 ns；post-GRT 修復時 Remaining 已是 0 | 已驗證：違規在 detailed routing 之後才出現；推測：繞線繞路使負載高於估計 | 使用者決定 signoff 用 1.0 ns（ADR-0009） | `runs/soc_explore7/*stapostpnr*/max_ss_100C_1v60/checks.rpt` |
| 2026-10-03 | soc_explore7 | max fanout 11（10 負載 + 1 diode） | 已驗證：antenna repair 在 resizer 之後才加 diode | `pnr.sdc` 把 PnR fanout 收到 8 | ADR-0009 |
| 2026-10-03 | soc_top 正式 run 1（+ `pnr.sdc` fanout 8） | signoff 上限 1.0 ns 下仍有 ss slew 1.42 ns；每換一個設定，都是不同的少數幾條線變差 | 已驗證：最差兩條線大幅繞路（端點距離約 117 µm，繞線 353 µm，往東繞到 SRAM 下方；另一條 636 µm），都在 L 形 logic 區的轉角附近。推測：轉角繞線壅塞（global placement 目標密度 0.68，logic 區整體只用了約 48%） | 試降低 `PL_TARGET_DENSITY_PCT`（soc_explore10／11） | `runs/soc_top/final/def/soc_top.def` NETS `_03575_`、`net750` |
| 2026-10-03 | soc_explore10／11 | `PL_TARGET_DENSITY_PCT` 55／50 後 9 corner 的 slew／cap／fanout 全 0，0.75 ns 下也是 0 | 已驗證（兩組都是 0） | 採用 55，撤回 1.0 ns 放寬 | `runs/sdc075_10`、ADR-0009 |
| 2026-10-03 | `make phase3` 第一次 | `RepairDesignPostGRT` 隨機 GRT-0229（同一份輸入 2/4） | 已驗證隨機；機制推測見 `librelane-run-debug` | 更正「退回過的做法」表中 explore3 的歸因 | `pnr/soc_top/README.md` 已知限制 4 |
