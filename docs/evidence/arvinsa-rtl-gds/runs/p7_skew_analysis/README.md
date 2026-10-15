# wrapper hold skew −3.6 ns 的成因（2026-10-14，獨立 agent 唯讀分析；STA 腳本與 log 在 <claude-tmp>/skew_wrap/）
- 結論：skew metric −3.598 ns 中約 2.7 ns 是報表算法：Caravel SDC source latency 上下限差 0.92 ns 與共同路徑 5% derate 0.44 ns 被 report_clock_skew -hold 當成扣分，同一對 flop 的 hold check 卻是加分（CRPR）；實測，未讀 OpenSTA 原始碼確認（推測）。
- 影響 hold 的 skew（src − tgt + CRPR）：wrapper −0.632、soc_top_hazard3 −0.678 ns；名目 latency 分布寬度 0.628 對 0.651 ns。
- 那一對：launch _21607_ (382,324) → capture _20913_ (276,275)，共同到 clkbuf_4_6_0_wb_clk_i（early 8.810 / late 10.168，差 1.358 = CRPR）；capture 多一顆 leaf wire buffer wire8118（0.325 ns）。
- 真正多的：wb_clk_i (2.99, 0) → clkbuf_0 (516, 397)，約 910 µm、6 顆 buffer、early 1.807 ns（soc_top 2 顆、0.79 ns）。影響：各輸入最差 hold 路徑上的 hold cell wrapper 451 vs soc 139（多出 508 個中至少 312 個在 Caravel 輸入路徑，輸入沒有 CRPR 回補）；SRAM 半週期 setup 0.548 vs 0.656 ns，差全在 clock 端（duty 失真在 sink 約 0.57 vs 0.28 ns，歸因推測）。
- 建議（未實作）：review_criteria 不要用 clock__skew__worst_hold 當品質指標（改 src−tgt+CRPR 或 latency 分布寬度），規則化前先讀原始碼確認；查官方 caravel_user_project SDC 是否回補 Caravel 內部共同 clock 路徑（決定約 300 顆 hold buffer 是否必要）；下一顆設計讓 CTS root 靠近 wb_clk_i。
