# ADR-0004：silicon 時序目標 40 ns，25 ns 為 stretch goal

- 狀態：已採用（2026-10-03）
- 背景：預建 SRAM 的 .lib 是 OpenRAM 解析模型（產生 log：`Analytical model enabled`），clk→dout 只有 0.38–0.53 ns，明顯樂觀；OpenRAM 論文對 1 KB macro 的矽量測為 < 34 MHz。
- 決策：`CLOCK_PERIOD = 40 ns`；RTL 模擬 clock 也用 40 ns；SRAM 讀出加一級 register。
- 出處：project-plan.md §5.4、§6.2。
