# ADR-0016：CTS 不做 macro 的 latency 對齊（`clock_tree_synthesis -no_insertion_delay`）

- 狀態：已採用（2026-10-07，使用者決定「自訂 CTS step」）；兩個 CPU 的正式 harden（`2caad0e`）確認，結果與接續實驗相同
- 背景：PicoRV32 在 ADR-0013／0014 的新設定（44 ns）下第 1 次 harden（`c976976`），signoff setup FAIL：min_ss_n40C −0.113 ns、nom_ss_n40C −0.012 ns，9 個違規 endpoint，全部是 SRAM 讀出的半週期路徑（`sram0` 下降緣送出、flop 上升緣接收）。路徑上 mux 前、後各有 1 顆 hold delay cell（`dlygate4sd3_1`，ss_n40C 1.42、1.15 ns）。ADR-0014 把「`sram_dout0` 上的 hold buffer」列為已知限制，這次變成 FAIL。

## 原因（已驗證）

1. **CTS 在 `sram0/clk0` 前插了 10 顆 delay buffer**（`delaybuf_*_clk`，`clkbuf_16`）：OpenROAD 的 CTS 把 macro 的 clock pin 分到另一棵 tree，再插 delay buffer，讓它的 latency 跟 flip-flop 一樣（`TritonCTS::balanceMacroRegisterLatencies()`，OpenROAD `dcf36133`；`cts-clock-tree` 規則 10）。
2. **這串 buffer 的上升緣、下降緣延遲不同**：min_ss_n40C 每顆下降緣約 0.31 ns、上升緣約 0.21 ns，`sram0/clk0` 下降緣 latency 3.81 ns、上升緣 2.72 ns（差 1.08）；ff_n40C 1.20／1.00 ns。
   - 半週期 setup 用 SRAM 的**下降緣**：送出變晚。
   - 讀出的 hold 用 SRAM 的**上升緣**：比讀出 flop 的 clock 早（min_ff 0.40 ns），再加 hold uncertainty 0.25 ns，`sram_dout0` 32 條各要 1 顆 hold delay cell。
3. **在 data 端補 hold 很貴**：sky130 的 delay cell 與 buffer，ss_n40C 延遲是 ff_n40C 的 2.5–3.3 倍（`.lib` 插值）。ff 只缺不到 0.3 ns，ss 就付 1.4 ns 以上。
4. **讀出 flop 自己繞回自己的路徑**（Q → mux → D，保持原值）：CRPR 已扣掉 0.133 ns，hold uncertainty 0.25 ns 加上修復餘量 0.3 ns，mux 後也插了 1 顆；不插時 signoff hold 仍有 +0.08 ns（推算）。這一項本 ADR 不處理。

## 試過、不採用的做法（都從同一個 run 的第 36 步接續，`drv-timing-closure` 經驗紀錄）

| 實驗 | 改了什麼 | 結果 |
|---|---|---|
| A | `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 → 0.1 | 同樣兩顆（同名），−0.114 ns |
| B | `RSZ_DONT_TOUCH_RX=^sram_dout0` | 兩顆改插在 mux 後，−0.043 ns，2 個 max slew 違規 |
| C1、C2 | `EXTRA_EXCLUDED_CELLS` 加 `dlygate4sd3_1`（C2 再加其他 delay cell） | OpenROAD 只挑一種 hold buffer（hold 延遲 ÷ 面積最高的）；換成小的之後要插 14,000 顆以上，`RSZ-0060 Max buffer count reached`，第 37 步就停 |

## 實驗 D（PicoRV32，p5h3 worktree `runs/exp_p_d`，從第 34 步接續到 signoff STA）

只在 CTS 那一步讓 `clock_tree_synthesis` 多帶 `-no_insertion_delay`（實驗用暫存 SDC 包一層；正式做法見下面的決策）：

| | 原版（第 1 次 harden） | 實驗 D |
|---|---|---|
| `delaybuf_*` | 10 | 0 |
| `sram_dout0` 上直接接的 hold delay cell | 32 | 0 |
| hold buffer 總數 | 3,572 | 3,563 |
| 最差 setup | −0.113 ns（9 個違規） | **+0.765 ns**（min_ss_n40C，仍是 SRAM 半週期路徑） |
| 最差 hold | +0.080 ns | +0.079 ns（flop 對 flop） |
| SRAM 輸入腳 hold（min_ff） | +0.197 ns | +0.093 ns |
| SRAM 輸入腳 setup | 27 ns 以上 | 27 ns 以上 |
| slew／cap／fanout 違規 | 0 | 0 |

Hazard3（`runs/exp_h_d`，第 8 次 harden 第 34 步接續，同樣的暫存 SDC）：

| | 第 8 次 harden | 實驗 D |
|---|---|---|
| `delaybuf_*` | 9 | 0 |
| `sram_dout0` 上直接接的 hold delay cell | 32 | 0 |
| hold buffer 總數 | 2,739 | 2,721 |
| 最差 setup | +0.530 ns | **+1.116 ns**（min_ss_n40C，SRAM 半週期路徑） |
| 最差 hold | +0.107 ns | +0.106 ns |
| SRAM 輸入腳 hold（min_ff） | +0.338 ns | +0.320 ns |
| slew／cap／fanout 違規 | 0 | 0 |

## 正式 harden（commit `2caad0e`，p5h3 worktree `runs/p5_pico_h3`、`runs/p5_h3_h10`）

用自訂 CTS step 從頭跑：PicoRV32 setup +0.765／hold +0.079 ns，Hazard3 +1.116／+0.106 ns，與接續實驗 D 相同；DRC、LVS、slew、cap、antenna 都是 0；`check_soc.py` `cts_macro_latency` PASS（0 顆 `delaybuf_*`）。unannotated 上限依新的 clock tree 改成 118／126（CTS dummy load 75／82），兩個 golden 從這兩個 run 重建。第一次正式 harden（`adac1a9`）兩個 CPU 都在 `ResizerTimingPostGRT` 遇到已知的隨機 GRT-0229 而中止，重試規則因此擴大到這一步（`docs/notes/grt0229_repro.md`）。

## 確認 harden 與下游驗證（commit `1d13775`，2026-10-07）

- harden-soc：兩個 CPU 都 PASS，golden 完全相同（PicoRV32 436、Hazard3 434）。PicoRV32 第 44 步遇到 GRT-0229，從該步接續一次後完成。
- 下游：`eqy-soc` 兩個都 PASS；`neg-eqy-soc` 9/9、13/13；`gl-soc`、`gl-soc-powered` 各 15/15；`neg-gl-soc` 8/8；`neg-pnr` 第一次 PicoRV32 54/55（P49：重試留下的中止目錄頂替了完成那次的 log，`review_criteria.py` 的漏洞），修正並加 P55 後兩個都 56/56。

## 決策

1. repo 加一個 LibreLane plugin `pnr/librelane_plugin_arvinsa`：step `Arvinsa.CTSNoInsertionDelay` 繼承 `OpenROAD.CTS`（設定、輸出、metric 都相同），只換 Tcl：`cts_no_insertion_delay.tcl` 把 OpenROAD 的 `clock_tree_synthesis` 包一層、每次呼叫加 `-no_insertion_delay`，印一行 `[INFO] arvinsa: ...`，再 source LibreLane 原本的 `cts.tcl`。LibreLane 本身不改（`provenance.py` 檢查它沒有被修改）。
2. 兩份 config 的 `meta.substituting_steps` 把 `OpenROAD.CTS` 換成它；`pnr/librelane_flow.sh` 把 `pnr/` 放進 `PYTHONPATH`（LibreLane 會自動載入名稱是 `librelane_plugin_*` 的模組，`librelane/plugins.py`）。
3. 不用「放在 `pnr.sdc` 包一層」：做得到（實驗 D 就是這樣做），但 SDC 應該只放約束。
4. 檢查：`check_soc.py` `cts_macro_latency`：config 有這個替換、run 裡只有這個 CTS step、它的 log 有那一行、最終網表沒有 `delaybuf_*`。negative test P52（網表多一顆 `delaybuf_0_clk`）、P53（log 沒有那一行）、P54（config 沒有替換）。`review_criteria.py` 依 `substituting_steps` 找 CTS step 的目錄。

## 影響與限制

- SRAM 輸入腳的 hold：PicoRV32 變緊（+0.197 → +0.093 ns @min_ff），Hazard3 幾乎不變（+0.338 → +0.320）：當初加 `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 就是為了這些 pin（`cts-clock-tree` 規則 10 後果一），之後要看它在正式 harden 的值。
- 半週期路徑 setup 仍取決於 DCD 預算 2.2 ns（`docs/notes/signoff_criteria_soc_top.md`）。
- 讀出 flop 自己繞回的路徑上仍有 1 顆 hold delay cell（原因 4），沒有處理。
- LibreLane 升版時要確認 `cts.tcl` 仍只呼叫一次 `clock_tree_synthesis`、OpenROAD 仍有 `-no_insertion_delay`（P53 抓得到旗標沒有帶到）。
- useful skew（刻意讓個別 flop 的 clock 提早或延後來借時間）沒有試。

## 出處

- p5h3 worktree `runs/p5_pico_h1_signoff/criteria_review.md`（PicoRV32 第 1 次 harden）
- `runs/exp_p_hm01`、`exp_p_dtdout`、`exp_p_c1`、`exp_p_c2`、`exp_p_d`、`exp_h_d`（p5h3 worktree）
- skill `cts-clock-tree`、`drv-timing-closure` 的經驗紀錄
