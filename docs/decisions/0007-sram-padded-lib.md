# ADR-0007：SRAM macro 用保守的 padded.lib 做 STA

- 狀態：已採用（2026-10-03），Phase 3.5／Phase 6 用 OpenRAM SPICE 特性化的 .lib 取代。
- 背景：PDK 只附一份 TT 的 .lib（`sky130_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib`），由 OpenRAM 解析模型（analytical model）算出，沒有做 SPICE 特性化，數字明顯樂觀（`project-plan.md` §5.4、§6.2）。用它做 signoff，等於 SRAM 的時序沒有被檢查。

## 決策

用 `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_padded_lib.py` 從 PDK 原檔產生 `padded.lib`，只改時序數字，pin、電容、功耗、memory 描述原樣保留。9 個 STA corner 全部用這份 `padded.lib`（LibreLane `MACROS` 的 `lib: {"*": ...}`），再用 `STA_EXTRA_CORNER_TCL_FILE` 依 corner 對 `sram0` 加 derate。

| 項目 | PDK 原值 | padded.lib | 依據 |
|---|---|---|---|
| clk0 下降緣 → dout0 延遲 | 0.383–0.529 ns（隨負載） | 10.000–10.146 ns（整張表平移，保留原本隨負載變化的斜率） | 見下方「dout0 延遲」 |
| dout0 轉換時間 | 0.002–0.016 ns | ≥ 0.5 ns | 原值比任何 standard cell 輸出都快，不合理；0.5 ns 是保守假設 |
| 輸入 setup（din0、addr0、wmask0、csb0、web0；port 1 的 addr1、csb1） | 0.103 ns | 1.0 ns | 工程假設，原值的約 10 倍 |
| 輸入 hold（同上） | −0.056 ns | 0.5 ns | 工程假設。macro 內部的 clock 有緩衝延遲，pin 上的 hold 需求通常是正的 |
| minimum_period（clk0、clk1） | 1.956 ns | 30 ns | ≥ 矽量測的 1/34 MHz = 29.4 ns |
| min_pulse_width（clk0、clk1） | 0.978 ns | 12 ns | 工程假設；40 ns、50% duty 時高低各 20 ns |
| addr0、wmask0、addr1 的 pin max_transition | 0.04 ns | 0.5 ns | 0.04 ns 剛好等於這份 .lib 表格 index 的最大值，不是量測到的限制，sky130 standard cell 實際上驅動不到；改成與這份 .lib 自己的 `default_max_transition`（0.5 ns，其他輸入 pin 適用）一致 |

### dout0 延遲

- 矽量測：OpenRAM 團隊 ISCAS'23 論文，1 KB 1rw1r macro 在 ≥ 1.7 V、兩個 port 同時讀時，< 34 MHz 不出錯（`project-plan.md` §5.4 與其引用）。
- 推論（不是量測值）：這個 macro 在 clock 下降緣後讀出資料，下一個上升緣接住。34 MHz 時半個週期是 14.7 ns，所以當時的「下降緣 → 資料穩定」不超過約 14.7 ns。2 KB 的 bitline 比 1 KB 長一倍，可能更慢。
- 決定：TT 用 10 ns；`*ss*` corner 再乘 1.5（15 ns，涵蓋上面的 14.7 ns）；`*ff*` corner 的最短延遲乘 0.7。
- 對 40 ns 設計的意義：dout0 → `rdata_q` 是半週期路徑（下降緣送出、上升緣接收），可用 20 ns；ss corner 扣掉 15 ns 後，留給繞線與 `rdata_q` 的 setup 約 5 ns。

## corner 與 derate

- `lib: {"*": [padded.lib]}`：9 個 corner 都有 SRAM 的時序模型。少了任何一個 corner 的 .lib，LibreLane 會把 macro 當 black box 且不報錯（`project-plan.md` §6.2）。
- `pnr/soc_top/sta_extra_corner.tcl`：`*ss*` → `set_timing_derate -late -cell_delay 1.5`、`*ff*` → `set_timing_derate -early -cell_delay 0.7`，只套在 `sram0`。
- 限制：這個 hook 只在 LibreLane 的 STA step 生效（`librelane/scripts/openroad/sta/corner.tcl` 第 59–61 行），placement／CTS／resizer 最佳化時看不到 derate。所以 PnR 是用 TT 等級的 padded 數字收斂，signoff STA 再用 derate 後的數字判定。這個 hook 是實驗性功能，必須有 negative test 證明它真的有作用（P04：derate 設 10 → setup 必須 FAIL）。

## 已知殘餘風險

1. 所有數字都是假設，不是特性化結果。Phase 3.5／6 用 OpenRAM SPICE 特性化產生 TT／SS／FF .lib 後取代。
2. FF corner 仍是 TT 的表格乘 0.7，SRAM 輸出到下一級 flop 的 hold 分析可能偏樂觀。目前 dout0 的路徑是半週期（下降緣送、上升緣收），hold 餘量約半個週期，影響有限。
3. 功耗數字沿用解析模型，IR drop 分析中 SRAM 的電流不可信。

## 出處

`project-plan.md` §5.1、§5.4、§6.2；`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_padded_lib.py`；PDK 原檔 `$PDK_ROOT/sky130A/libs.ref/sky130_sram_macros/lib/sky130_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib`（ciel hash 見 `env/versions.mk`）。
