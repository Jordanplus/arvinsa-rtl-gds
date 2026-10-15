---
name: floorplan-congestion
description: 決定 die／core 尺寸與使用率（utilization）、placement 目標密度（`PL_TARGET_DENSITY_PCT`、log 的 `GPL-0052 Placement target density`），或遇到繞線壅塞（congestion）、某條線大幅繞路、macro 旁的窄 row（`PDN-0179 Unable to repair all channels`）、GCell 溢位時使用；定 die 尺寸時先做 floorplan 試跑（整顆設計加 macro 只跑到 PDN、global placement、global routing）。新的頂層設計、搬動 macro 或 IO pin 之前，先照 chip-floorplan-pin-planning 規劃 pad、block 位置與 pin 並取得使用者核准（`CLAUDE.md` 規則 14）；本 skill 只管核准之後 die 內的擺放細節（site 格點、halo、`IO_PIN_ORDER_CFG`）。macro 的 view QA 看 macro-qualification，電源網路看 pdn-ir-drop。Use for die size, utilization, placement density and routing congestion or detours in OpenROAD, after the chip-level pad, block and pin plan is approved.
---

# Floorplan、IO pin 與繞線壅塞

**floorplan**：決定 die 與 core 尺寸、macro 擺在哪裡與朝哪個方向、IO pin 排在哪條邊。**繞線壅塞（routing congestion）**：某一區需要的繞線軌道超過可用數量，router 只好繞遠路或放棄。macro 的 view QA 看 `macro-qualification`，view 來源與介面清單看 `hard-macro-integration`；電源網路看 `pdn-ir-drop`。本 repo 實例：ADR-0006（含 Phase 3 補充）、`pnr/soc_top/config.json`、`pnr/soc_top/pin_order.cfg`。

## 規則（已驗證）

1. **die 尺寸**：用前一階段實測的 standard cell 面積估（ADR-0006：soc_top ≈ PicoRV32 單獨 harden 面積 × 1.152），定義清楚「使用率」的分母（logic 區 = core 面積 − macro 與保留區），並寫下重新檢討的條件。
2. **macro 位置**：
   - **先規劃、經核准再擺**：新的頂層設計或搬動 macro／block 之前，先照 `chip-floorplan-pin-planning` 把 pad、block 位置與 pin 寫進 `pnr/<design>/pin_plan.toml` 並取得使用者核准（`CLAUDE.md` 規則 14，ADR-0019 決定 13）。核准前改 config 的 `MACROS` 位置會被 hook 擋下、`make pin-plan` FAIL；本規則以下只管核准之後的擺放細節。legacy 設計（`soc_top`、`picorv32_core`）不需要規劃。
   - 座標對齊 site 格點（sky130 hd：0.46 × 2.72 µm，從 core 原點算）。
   - macro 的 halo 要嘛留出夠寬的 row，要嘛蓋過 core 邊界；約 6 µm 的窄 row 會讓 PDN 報 `PDN-0179 Unable to repair all channels`（soc_explore1）。
   - macro 的 pin 面向 logic 區。
3. **IO pin**：哪個訊號走哪一支腳位或 GPIO 屬於 pin 指定，同樣先經 `chip-floorplan-pin-planning` 的規劃與核准（規則 2 第一點）；外殼固定腳位的設計（Caravel）用 `FP_DEF_TEMPLATE`，不用 `IO_PIN_ORDER_CFG`（`pnr/user_project_wrapper/config.json`）。自己排腳位的設計：`IO_PIN_ORDER_CFG` + `ERRORS_ON_UNMATCHED_IO = "both"`。clock pin 要靠近 flip-flop 重心：pin 到第一級 clock buffer 的線不在 resizer 修復範圍內（soc_explore2：660 µm → ss slew 0.92 ns）。
4. **判讀繞路**：違規線的「繞線長度 ÷ 端點直線距離」遠大於 1 就是繞路。從最終 DEF 的 NETS 段讀該線各層長度與範圍（soc_top：端點相距 117 µm、繞線 353 µm，往東繞到 SRAM 下方）。
5. **全域 congestion 報告看不到局部繞路**：soc_top 的 global routing 總使用率 35%、overflow 0，但 L 形 logic 區轉角仍有繞路。

6. **placement 目標密度**：LibreLane 沒設 `PL_TARGET_DENSITY_PCT` 時自動算目標密度（soc_top 是 68%，看 global placement log 的 `GPL-0052 Placement target density`）。macro 佔掉大半、logic 區是 L 形時，這會把 cell 擠在轉角而留下大片空間；設成接近「logic 區實際使用率 + 一些餘裕」（soc_top：約 48% → 設 55%）後轉角繞路消失，max slew 從最差 1.42 ns 變成 0 個違規（soc_explore10）。

7. **定 die 尺寸時就做 floorplan 試跑：整顆設計加 macro，只跑到 PDN、global placement、global routing**（提早檢查 D1，流程回顧 ADR-0020；流程文件 4.4）。這條是使用者決定的做法，放在本節是為了保持規則編號；它的效益是回顧推算的，沒有實驗確認（`review_skills.md` 1.3 說明）。
   - 為什麼：Phase 3 為了 ss corner 的 max slew 跑了約 8 次探索 run，signoff 的 max transition 一度放寬到 1.0 ns 又撤回（ADR-0009），根因是規則 6 的目標密度；SRAM 上方的窄 row（規則 2 的 `PDN-0179`）也是試跑才看到。回顧推算這些在 Phase 2 定 `DIE_AREA` 時（ADR-0006）跑一次到 global routing（10–20 分鐘）就看得到。
   - 做什麼：看三件事：PDN 有沒有窄 row 錯誤；global placement log 的 `GPL-0052 Placement target density` 和 logic 區實際使用率差多少；global routing 的溢位。出 floorplan 圖（`scripts/plot_floorplan.py`）給使用者看。同一個試跑也做 IR（`pdn-ir-drop` 規則 14）。
   - 通過條件：沒有窄 row 錯誤、溢位 0、目標密度不高於「logic 區使用率＋約定的餘裕」（餘裕由使用者決定）。
   - 限制：只在繞完線才出現的局部熱點看不到（規則 5；Phase 7 wrapper 的 55% → 50%，ADR-0019 決定 21）。
   - 自動防護：PDN 錯誤會讓試跑直接失敗；密度與溢位的判定目前沒有自動防護，下一個專案開始時做成 checker。

## 待驗證

目前沒有。原本兩項在 2026-10-15 清掉（`review_skills.md` Q18）：
- ADR-0006 的備案（logic 區使用率 > 65% 或 global routing 溢位時 die 改 1000 × 900）到 Phase 7 都沒有觸發，soc_top 維持 1000 × 800（`pnr/soc_top/config.json`）。
- 目標密度 55% 之後一直用在 soc_top 兩個 CPU 的正式 harden（`pnr/soc_top/config.json`、`config_hazard3.json`）；wrapper 因繞完線才出現的局部熱點改成 50%（ADR-0019 決定 21，經驗紀錄 2026-10-13）。

## 用完後

更新「經驗紀錄」；floorplan 改動時同步更新 ADR-0006 與 `pnr/*/README.md`。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `PDN-0179 Unable to repair all channels` | 已驗證：SRAM 上方 6 µm row | halo 蓋過 core 邊界 | ADR-0006 補充 |
| 2026-10-03 | soc_top 正式 run 1 | ss slew 1.42 ns 的線繞線 353 µm（端點距離 117 µm） | 已驗證：繞路；推測：L 形轉角壅塞 | 降低 placement 密度實驗中 | `drv-timing-closure` 經驗紀錄 |
| 2026-10-03 | soc_explore10／11 | 目標密度 55%／50% 後轉角繞路消失，DRV 全 0 | 已驗證 | 採用 55% | `pnr/soc_top/README.md` |
| 2026-10-03 | soc_top（clk pin 在下緣中段 x = 547.63 µm） | `RepairDesignPostGRT` 隨機報 `GRT-0229 ... (79, 0) usage=65534`，(79, 0) 正好是 clk pin 的 GCell | 推測：die 邊緣的 clk pin 加上 CTS NDR 讓 global router 的用量計算出錯；尚未用「移動 clk pin」實驗確認 | 先用有上限的重試；之後可試把 clk pin 移開一格比較 | `pnr/soc_top/README.md` 已知限制 4 |
| 2026-10-13 | Phase 7 wrapper `p7_harden5`、`p7_exp_pl_pad`、`p7_exp_pl_dens` | 全晶片 global routing 使用率約 2%、溢位 0，一條內部 net 仍被擠去繞路（signoff slew 0.779 ns）；那一欄約 15 條 met2 軌道被 51 條內部 net 占了 12–15 條。cell padding 2：繞線總長 +26%、slew 違規更多；目標密度 55% → 50%：繞路消失，繞線總長 +0.2% | 已驗證（同一份輸入只改一個設定）：局部熱點，全域報告看不到（規則 5 第 2 次）；padding 讓熱點更多 | 採用 50%（ADR-0019 決定 21，`drv-timing-closure` 規則 13） | `runs/p7_exp_pl_pad`、`runs/p7_exp_pl_dens`（本機） |
