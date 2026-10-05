---
name: cts-clock-tree
description: Clock tree（CTS）問題時使用：clock buffer 的 fanout／cap 違規、skew（metric 含 uncertainty 與 derate）、clock 輸入 pin 到第一級 clock buffer 的長線 slew（`CTS_CLK_MAX_WIRE_LENGTH`）、clock pin 擺放、CTS 把 macro 的 clock 延到與 flip-flop 對齊（插 delay buffer）造成 macro 輸入 hold 變差。資料路徑的 DRV 看 drv-timing-closure。Use for CTS problems (clock buffer fanout/cap, skew, clock-pin wire slew, clock pin placement, macro clock latency balancing) in OpenROAD/LibreLane.
---

# Clock tree（CTS）

資料路徑的 DRV 看 `drv-timing-closure`。目前經驗較少，邊用邊補。本 repo 實例：`pnr/picorv32_core/README.md`（試跑 #8、#9）、`pnr/soc_top/pin_order.cfg`、`pnr/soc_top/README.md` 的設定表（Phase 4）。

## 規則（已驗證）

1. `CTS_SINK_CLUSTERING_SIZE 8`：預設每顆末端 buffer 帶 10 顆 flop，之後加 dummy load（`clkload*`），fanout 變 11–12。
2. `CTS_DISTANCE_BETWEEN_BUFFERS 50`：H-tree 中段沒放 buffer 時，第 2 層一顆 buffer 帶 16 顆下游 buffer（fanout 16、cap 0.206 pF）；設 50 µm 後最大 fanout 9。
3. 沒有作用：`CTS_MAX_CAP`（CTS 後 DEF 逐 byte 相同）；`CTS_SINK_CLUSTERING_SIZE 9`（反而分成更多群）。
4. **clock 輸入 port**：pin 到第一級 clock buffer 的線不在 resizer 修復範圍內（clock net）。pin 在左邊最下方時，660 µm 的線在 ss slew 0.92 ns；移到 flip-flop 重心附近的下邊中段後消失（soc_explore2 → 4）。
5. `clkload*` 的輸出不接東西，會出現在 STA 的 unannotated 清單，屬正常（見 `signoff-checker-qualification` 規則 4）。
6. **skew 的 metric 不是 skew 本身**：`clock__skew__worst_*` 與 `report_clock_skew` 都含 clock uncertainty（0.25 ns），也含 ±5% derate（launch 用 late、capture 用 early）。soc_top nom_tt 的 metric 是 0.93 ns：扣掉 uncertainty 後 0.68 ns，再扣掉 derate 的名目值約 0.51 ns（推算）。
7. **`CTS_APPLY_NDR` 的 `half`**：只在 clock tree 的前半層套用 non-default rule（OpenROAD `src/cts/README.md`），不是「leaf 以外全部」。sky130 的 CTS NDR 是 2 倍間距，線寬沒有加大。
8. **PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒有生效**：`resolved.json` 為 None。soc_top 的 clock 繞線段：met1 9750、met2 2901、met3 90、met4 7。要讓 clock 走粗金屬，必須在專案 config 明確設定。
9. **duty cycle**：clock tree 本身造成的 rise／fall 延遲差（nom_ss 下 SRAM `clk0` 約 0.30 ns），STA 已經算到；clock 來源本身的 duty 偏差 STA 不知道，要靠約束（`signoff-criteria`）。
10. **CTS 會把 macro 的 clock 延到與 flip-flop 一樣晚**（latency 對齊）：soc_top 的 `sram0/clk0` 前面被插了 10 顆 delay buffer（`delaybuf_*`）。
    - 後果一，SRAM 輸入腳的 hold 變差：SRAM .lib 要求 0.5 ns（ADR-0007 的值，ADR-0010 沿用為下限；實測 TT 為 0.20–0.24 ns）。post-CTS 的 hold 修到 +0.100 ns，繞線後在 min_ff_n40C 變成 −0.088 ns（Phase 4 第 2、3 次 harden-soc）。後來用 `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 補過去（`drv-timing-closure`）。
    - 後果二，SRAM 下降緣送出的半週期路徑也比較吃緊。
    - **`CTS_DELAY_BUFFER_DERATE_PCT` 管不到這一步**：設 0 或 1，結果與預設完全相同，仍是 10 顆。目前沒有找到可以關掉的設定（`docs/phase_exit/phase4.md` 已知限制 5）。
11. **clock 輸入 pin 到 clock tree 根部的線**（接規則 4）：`CTS_CLK_MAX_WIRE_LENGTH` 預設 0，表示依 slew 算出來的長度，約 3.5 mm，所以 360 µm 的線不會被切段。pin 的 driver 是 LibreLane 假設的 `inv_2`（`SYNTH_CLK_DRIVING_CELL` 預設），max_ss_n40C 的 slew 0.767 ns，超過 0.75 ns（Phase 4 第 4 次 harden-soc）。
    - 設 150 µm 後，CTS（LibreLane `cts.tcl` 的 `repair_clock_nets`）會把這段線切開加 buffer。
    - 第 5 次 harden 同時改了週期與 max transition，15 個 corner 全部通過；這一項的效果沒有單獨實驗。

## 待補

怎麼關掉或縮短 macro 的 latency 對齊（規則 10；`CTS_DELAY_BUFFER_DERATE_PCT` 無效）；週期縮短時的 CTS 設定（Phase 4 的 25 ns 只在同一份版圖重跑 STA，沒有重做 CTS）。skew 在 golden 比對中的誤差是 ±0.01 ns，實測差異 ≤ 0.0002 ns（`signoff-checker-qualification` 規則 5）。

## 用完後 / 經驗紀錄

用完把新現象加進下表；第二次出現或已用實驗確認就搬進規則。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore2 | `clk` port slew 0.919 ns（max_ss） | 已驗證：pin 在左下角，到 `clkbuf_regs_0_clk` 約 660 µm | pin 移到下邊中段 | soc_explore4 無此違規 |
| 2026-10-03 | signoff 條件調查（核對 agent） | skew metric 含 uncertainty 與 derate；NDR half 的意義；`RT_CLOCK_MIN_LAYER` 沒有生效 | 已驗證（報告數字、`resolved.json`、DEF 統計） | 規則 6–9 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-04 | Phase 4 第 2、3 次 harden-soc | SRAM 輸入腳 hold 在 min_ff_n40C −0.088 ns；`CTS_DELAY_BUFFER_DERATE_PCT` 0 與 1 結果都與預設相同 | 已驗證：CTS 對齊 `sram0` 與 flip-flop 的 latency，插 10 顆 delay buffer | resizer hold 餘裕 0.3 ns；規則 10；列為已知限制 | `pnr/soc_top/README.md` 設定表 |
| 2026-10-04 | Phase 4 第 4 次 harden-soc | `clk` pin 到第一顆 clock buffer 約 360 µm，max_ss_n40C slew 0.767 ns | 已驗證：預設的切段長度約 3.5 mm，這段線沒有被切 | `CTS_CLK_MAX_WIRE_LENGTH` 150（規則 11） | `pnr/soc_top/config.json` 註解 |
| 2026-10-05 | Phase 3.5 第 2 次 harden-soc | `sram0` → `rdata_q` 的 hold 檢查在 min_ss_n40C：`sram0/clk0` 2.78 ns、`rdata_q` 的 CLK 4.15 ns，差 1.37 ns（setup 時兩者只差 0.09 ns） | 已驗證（hold 報告）：SRAM clock 那條 10 顆 delay buffer 的長鏈在 hold 分析取 early、flop 那側取 late，±5% OCV 放大了差距 | 新的 SRAM hold 弧因此需要 delay cell；見 `drv-timing-closure` 同日紀錄 | ADR-0004 Phase 3.5 補充 |
