---
name: floorplan-congestion
description: 決定 die／core 尺寸與使用率（utilization）、macro 位置與方向、IO pin 擺放、placement 目標密度，或遇到繞線壅塞（congestion）、某條線大幅繞路、macro 旁的窄 row（PDN 接不到）、GCell 溢位時使用。macro 的 view 看 hard-macro-integration，電源網路看 pdn-ir-drop。Use for floorplanning (die size and utilization, macro placement, IO pins, placement density) and routing congestion/detour problems in OpenROAD.
---

# Floorplan、IO pin 與繞線壅塞

**floorplan**：決定 die 與 core 尺寸、macro 擺在哪裡與朝哪個方向、IO pin 排在哪條邊。**繞線壅塞（routing congestion）**：某一區需要的繞線軌道超過可用數量，router 只好繞遠路或放棄。macro 的 view 與介面清單看 `hard-macro-integration`；電源網路看 `pdn-ir-drop`。本 repo 實例：ADR-0006（含 Phase 3 補充）、`pnr/soc_top/config.json`、`pnr/soc_top/pin_order.cfg`。

## 規則（已驗證）

1. **die 尺寸**：用前一階段實測的 standard cell 面積估（ADR-0006：soc_top ≈ PicoRV32 單獨 harden 面積 × 1.152），定義清楚「使用率」的分母（logic 區 = core 面積 − macro 與保留區），並寫下重新檢討的條件。
2. **macro 位置**：
   - 座標對齊 site 格點（sky130 hd：0.46 × 2.72 µm，從 core 原點算）。
   - macro 的 halo 要嘛留出夠寬的 row，要嘛蓋過 core 邊界；約 6 µm 的窄 row 會讓 PDN 報 `PDN-0179 Unable to repair all channels`（soc_explore1）。
   - macro 的 pin 面向 logic 區。
3. **IO pin**：`IO_PIN_ORDER_CFG` + `ERRORS_ON_UNMATCHED_IO = "both"`。clock pin 要靠近 flip-flop 重心：pin 到第一級 clock buffer 的線不在 resizer 修復範圍內（soc_explore2：660 µm → ss slew 0.92 ns）。
4. **判讀繞路**：違規線的「繞線長度 ÷ 端點直線距離」遠大於 1 就是繞路。從最終 DEF 的 NETS 段讀該線各層長度與範圍（soc_top：端點相距 117 µm、繞線 353 µm，往東繞到 SRAM 下方）。
5. **全域 congestion 報告看不到局部繞路**：soc_top 的 global routing 總使用率 35%、overflow 0，但 L 形 logic 區轉角仍有繞路。

6. **placement 目標密度**：LibreLane 沒設 `PL_TARGET_DENSITY_PCT` 時自動算目標密度（soc_top 是 68%，看 global placement log 的 `GPL-0052 Placement target density`）。macro 佔掉大半、logic 區是 L 形時，這會把 cell 擠在轉角而留下大片空間；設成接近「logic 區實際使用率 + 一些餘裕」（soc_top：約 48% → 設 55%）後轉角繞路消失，max slew 從最差 1.42 ns 變成 0 個違規（soc_explore10）。

## 待驗證

- ADR-0006 的備案：logic 區太擠時 die 改 1000 × 900 µm。
- 密度 55% 在之後的 run（detailed routing 不可重現）是否穩定：正式 run 與 `make phase3` 的第二次 harden 會提供兩個樣本。

## 用完後

更新「經驗紀錄」；floorplan 改動時同步更新 ADR-0006 與 `pnr/*/README.md`。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `PDN-0179 Unable to repair all channels` | 已驗證：SRAM 上方 6 µm row | halo 蓋過 core 邊界 | ADR-0006 補充 |
| 2026-10-03 | soc_top 正式 run 1 | ss slew 1.42 ns 的線繞線 353 µm（端點距離 117 µm） | 已驗證：繞路；推測：L 形轉角壅塞 | 降低 placement 密度實驗中 | `drv-timing-closure` 經驗紀錄 |
| 2026-10-03 | soc_explore10／11 | 目標密度 55%／50% 後轉角繞路消失，DRV 全 0 | 已驗證 | 採用 55% | `pnr/soc_top/README.md` |
| 2026-10-03 | soc_top（clk pin 在下緣中段 x = 547.63 µm） | `RepairDesignPostGRT` 隨機報 `GRT-0229 ... (79, 0) usage=65534`，(79, 0) 正好是 clk pin 的 GCell | 推測：die 邊緣的 clk pin 加上 CTS NDR 讓 global router 的用量計算出錯；尚未用「移動 clk pin」實驗確認 | 先用有上限的重試；之後可試把 clk pin 移開一格比較 | `pnr/soc_top/README.md` 已知限制 4 |
