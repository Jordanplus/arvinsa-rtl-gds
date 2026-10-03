---
name: cts-clock-tree
description: Clock tree synthesis（CTS）相關問題：clock buffer 的 fanout／cap 違規、skew、clock 輸入 port 的 slew、clock pin 擺放、macro clock pin 的平衡時使用。Use for CTS, clock buffer fanout/cap, skew, clock port slew and clock pin placement.
---

# Clock tree（CTS）

資料路徑的 DRV 看 `drv-timing-closure`。目前經驗較少，邊用邊補。本 repo 實例：`pnr/picorv32_core/README.md`（試跑 #8、#9）、`pnr/soc_top/pin_order.cfg`。

## 規則（已驗證）

1. `CTS_SINK_CLUSTERING_SIZE 8`：預設每顆末端 buffer 帶 10 顆 flop，之後加 dummy load（`clkload*`），fanout 變 11–12。
2. `CTS_DISTANCE_BETWEEN_BUFFERS 50`：H-tree 中段沒放 buffer 時，第 2 層一顆 buffer 帶 16 顆下游 buffer（fanout 16、cap 0.206 pF）；設 50 µm 後最大 fanout 9。
3. 沒有作用：`CTS_MAX_CAP`（CTS 後 DEF 逐 byte 相同）；`CTS_SINK_CLUSTERING_SIZE 9`（反而分成更多群）。
4. **clock 輸入 port**：pin 到第一級 clock buffer 的線不在 resizer 修復範圍內（clock net）。pin 在左邊最下方時，660 µm 的線在 ss slew 0.92 ns；移到 flip-flop 重心附近的下邊中段後消失（soc_explore2 → 4）。
5. `clkload*` 的輸出不接東西，會出現在 STA 的 unannotated 清單，屬正常（見 `signoff-checker-qualification` 規則 4）。

## 待補

macro clock pin 的插入延遲平衡（soc_top 有 `delaybuf_0_clk`）、skew 在 golden 中的誤差範圍、25 ns 目標下的 CTS 設定。

## 用完後 / 經驗紀錄

用完把新現象加進下表；第二次出現或已用實驗確認就搬進規則。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | `clk` port slew 0.919 ns（max_ss） | 已驗證：pin 在左下角，到 `clkbuf_regs_0_clk` 約 660 µm | pin 移到下邊中段 | soc_explore4 無此違規 |
