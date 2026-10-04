# ADR-0004：silicon 時序目標 40 ns，25 ns 為 stretch goal

- 狀態：已採用（2026-10-03）
- 背景：預建 SRAM 的 .lib 是 OpenRAM 解析模型（產生 log：`Analytical model enabled`），clk→dout 只有 0.38–0.53 ns，明顯樂觀；OpenRAM 論文對 1 KB macro 的矽量測為 < 34 MHz。
- 決策：`CLOCK_PERIOD = 40 ns`；RTL 模擬 clock 也用 40 ns；SRAM 讀出加一級 register。
- 出處：project-plan.md §5.4、§6.2。

## Phase 4 補充（2026-10-04）：soc_top 改 42 ns

- Phase 4 加嚴了 signoff 條件：SRAM derate 乘進 OCV（ss 1.575）、半週期路徑加 duty cycle 預算（假設 45/55%）、加溫度反轉 corner `ss_n40C_1v60`（`docs/notes/signoff_criteria_soc_top.md`）。
- 結果：40 ns 時，`sram0` 在下降緣送出 `dout0`、`rdata_q` 在上升緣接收的半週期路徑，min_ss_n40C 差 0.42 ns；ss 100 °C 剩 +0.08 ns；其他路徑都有餘量（不含 SRAM 的路徑在 max_ss_n40C 還有 +8.9 ns）。這條路徑的 slack 每 1 ns 週期只變 0.45 ns（半週期扣掉 5% 的 duty cycle 偏差），最小週期約 41 ns。
- 使用者決定（2026-10-04）：soc_top 改 **42 ns**，不放寬任何假設或檢查。SRAM 的 10 ns 本身是假設值（ADR-0007），Phase 3.5／6 用 OpenRAM 特性化取代後，再回頭檢討週期。
- 25 ns（stretch goal）：同一份版圖做 STA what-if，25 ns 時 SRAM 路徑差約 7 ns，不含 SRAM 的路徑也差 1.8 ns（ss 100 °C）到 4.7 ns（ss −40 °C）。在目前的 SRAM 假設下做不到。
- picorv32_core（Phase 2 的單獨 harden，沒有 SRAM）維持 40 ns。
- RTL 與 gate-level 模擬的 testbench clock 仍是 40 ns：模擬只看 cycle，不檢查時序，週期數值不影響結果。
