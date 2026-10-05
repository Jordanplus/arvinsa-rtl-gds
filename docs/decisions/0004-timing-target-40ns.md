# ADR-0004：silicon 時序目標 40 ns，25 ns 為 stretch goal

- 狀態：已採用（2026-10-03）
- 背景：預建 SRAM 的 .lib 是 OpenRAM 解析模型（產生 log：`Analytical model enabled`），clk→dout 只有 0.38–0.53 ns，明顯樂觀；OpenRAM 論文對 1 KB macro 的矽量測為 < 34 MHz。
- 決策：`CLOCK_PERIOD = 40 ns`；RTL 模擬 clock 也用 40 ns；SRAM 讀出加一級 register。
- 出處：project-plan.md §5.4、§6.2。

## Phase 4 補充（2026-10-04）：soc_top 改 42 ns

- Phase 4 加嚴了 signoff 條件：SRAM derate 乘進 OCV（ss 1.575）、半週期路徑加 duty cycle 預算（假設 45/55%）、加溫度反轉 corner `ss_n40C_1v60`（`docs/notes/signoff_criteria_soc_top.md`）。
- 結果：40 ns 時，`sram0` 在下降緣送出 `dout0`、`rdata_q` 在上升緣接收的半週期路徑，min_ss_n40C 差 0.42 ns；ss 100 °C 剩 +0.07 ns（min_ss_100C，第 4 次 harden）；其他路徑都有餘量（不含 SRAM 的路徑在 max_ss_n40C 還有 +8.9 ns）。這條路徑的 slack 每 1 ns 週期只變 0.45 ns（半週期扣掉 5% 的 duty cycle 偏差），最小週期約 41 ns。
- 使用者決定（2026-10-04）：soc_top 改 **42 ns**，不放寬任何假設或檢查。SRAM 的 10 ns 本身是假設值（ADR-0007），Phase 3.5／6 用 OpenRAM 特性化取代後，再回頭檢討週期。
- 25 ns（stretch goal）：同一份版圖做 STA what-if，25 ns 時 SRAM 路徑差約 7 ns，不含 SRAM 的路徑也差 1.8 ns（ss 100 °C）到 4.7 ns（ss −40 °C）。在目前的 SRAM 假設下做不到。
- picorv32_core（Phase 2 的單獨 harden，沒有 SRAM）維持 40 ns。
- RTL 與 gate-level 模擬的 testbench clock 仍是 40 ns：模擬只看 cycle，不檢查時序，週期數值不影響結果。

## Phase 3.5 補充（2026-10-05）：soc_top 改 43 ns

- Phase 3.5 換上 SPICE 特性化的 SRAM .lib（ADR-0010），多了一條 dout0 的 `rising_edge` hold 弧：資料在 clock 上升緣後 0.64 ns（ff，× 0.9）就開始變化。
- post-CTS 的 hold 修復有 0.3 ns 額外餘量（`PL_RESIZER_HOLD_SLACK_MARGIN`），為了這條弧在每個 `rdata_q` 的 D 前各插了一顆 delay cell（`dlygate4sd3`，ss −40°C 約 1.17 ns）。推算不插的話 ff 的 hold 仍有約 +0.18 ns（hold slack 減 delay cell 延遲，沒有拿掉 cell 重跑）。
- 這顆 cell 也在 SRAM 讀出的半週期路徑上：42 ns 時 min_ss_n40C 的 setup 差 0.066 ns（Phase 3.5 第 2 次 `make harden-soc`，commit `3e9b011`），ss 100°C 從 +0.79 降到 +0.47 ns。
- 使用者決定（2026-10-05）：soc_top 改 **43 ns**，不動任何檢查或餘量。另兩個選項沒有採用：把 resizer 的 hold 餘量降到 0.15 ns（全域設定，Phase 4 是因為 SRAM 輸入 pin 的 hold 才調到 0.3）；ss −40°C 的 SRAM 路徑不判 setup（放寬檢查）。
- picorv32_core 維持 40 ns；模擬的 testbench clock 不變（同上一節）。
