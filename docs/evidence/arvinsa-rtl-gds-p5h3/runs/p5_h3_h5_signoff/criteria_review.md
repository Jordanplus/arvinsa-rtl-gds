# signoff criteria 檢查：Hazard3 第 5 次 harden

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3`（commit `3a28d54`，週期 44 ns，開 `RUN_POST_GRT_RESIZER_TIMING`），2026-10-07
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 這是第一次用新的 `run.sh`：LibreLane 跑完後，repo 的 checker 與 criteria 檢查都由 harden 自己執行，不是事後補跑。

## 有沒有被執行

腳本 5 項都 PASS：
- config 的 41 個設定（多了 `RUN_POST_GRT_RESIZER_TIMING`）都進了 `resolved.json`，78 個 step 的 config 都一致。
- `clock_uncertainty.sdc` 的值（setup 0.25、hold 0.25、半週期 setup 2.45、DCD 2.20 ns）出現在 7 個時序 step 與 15 個 signoff corner。
- signoff corner = `STA_CORNERS` 的 15 個。
- 4 個 checker 都有結果行。

各 checker 的結果：

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完（Flow complete） | — | setup／hold 15 個 corner 都 PASS；slew、cap、繞線 DRC、LVS、KLayout DRC、Magic illegal overlap 都是 0。Magic DRC 4,665,810 個，與第 2–4 次相同，由 `check_soc.py` 判定 |
| `check_signoff.py` | FAIL（2 列） | `timing__unannotated_net__count` 125 ≠ 133 | **criteria 問題**（第 4 次已找到）：133 是 PicoRV32 的組成，Hazard3 是 81 clkload + 32 `sram0/dout1` + 12 tie = 125。建 Hazard3 golden 時重新推導 |
| | | golden 不存在 | 預期內：Hazard3 的 golden 還沒建立 |
| `sram_drc_alone` | PASS | — | — |
| `check_soc.py` | PASS（10 項） | — | Magic DRC：SRAM 外 0 個，SRAM 內的都在單獨跑 SRAM 時的違規位置上；pulse width 15 個 corner 都 PASS |
| `check_inputs.py --resolved` | PASS | — | — |
| `provenance.py`（開始、結束） | PASS、PASS | — | — |

「不分析的項目清單」：這次沒有寫，Phase 5 exit review 時要逐條寫。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| `RUN_POST_GRT_RESIZER_TIMING`，`GRT_RESIZER_SETUP_SLACK_MARGIN` 0.025 ns（預設） | ADR-0014：差距大部分在繞線之後；實驗 A | `ResizerTimingPostGRT` 找到 65 個違規 endpoint，拿掉 12 顆 buffer、放大 54 個 cell，沒有新增 buffer，面積 +0.0%；修完 +0.002 ns（剩 1 個，`RSZ-0062`）→ signoff +0.530 ns。數字與實驗 A 完全相同（前 43 步相同，這一步可以重現） | 依據仍成立。global routing 寄生估計比 signoff 保守 0.53 ns，0.025 ns 的預設餘量足夠 |
| `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns | ADR-0013；第 4 次判定「依據不成立」 | CTS 後修完 +0.112 ns。腳本算的「差距 −0.418」是拿 CTS 後的估計比 signoff，沒有計入後面那一步，這個數字沒有意義（見「學習」的腳本改進） | 依據的問題已由 ADR-0014 處理：CTS 後的 setup 餘量不再需要涵蓋繞線的差距，0.1 可以維持 |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10：SRAM 輸入腳的 hold 繞線後變負 | hold 修完 +0.275 → signoff 最差 +0.107 ns（min_ff_n40C，差 0.168；第 4 次差 0.166）；2,739 顆 hold buffer，post-CTS stdcell 面積 +13.4% | 依據仍成立 |
| （同上，新發現的代價） | ADR-0010：SRAM 在 clk0 上升緣後約 1 ns 把 `dout0` 拉回 0，`.lib` 加了 `rising_edge` 時序弧讓 STA 檢查接收端的 hold | 32 條 `sram_dout0` 每條都直接插了 1 顆 `dlygate4sd3_1`（PicoRV32 版的 hold buffer 插在 mux 之後、flop 的 D 之前，最差路徑上 1.17 ns；這段是 2026-10-07 稍後更正的）。signoff 經過這顆的 hold slack：min_ff_n40C +0.679、min_ss_n40C +1.180 ns。它在最差 setup 路徑上佔 1.44 ns（ss_n40C） | 依據仍成立：hold 檢查是真的。這顆 buffer 換成延遲較小的 cell 能不能同時滿足 hold 餘量：資料不足 |
| `pnr.sdc` `set_max_transition 0.70`、`DESIGN_REPAIR_MAX_SLEW_PCT` 30 | ADR-0013 第 3 點、ADR-0014 決策 3 | 最差路徑已經不是長的 buffer 鏈；slew 違規 0 | 資料不足：ADR-0014 說之後在 A 的基礎上評估，現在沒有迫切理由 |
| corner 清單（含 ss_n40C） | Phase 4、ADR-0013：溫度反轉 | 最差 setup 是 ss_n40C 三個 corner（+0.530／+0.584／+0.636），ss_100C 是 +1.113 | 依據仍成立 |
| uncertainty：半週期路徑的 DCD 預算 2.2 ns（duty cycle 55% 的假設） | `docs/notes/signoff_criteria_soc_top.md`；Caravel clock 規格要 Phase 7 才有 | **最差 setup 路徑現在是半週期路徑**：`sram0` 下降緣（22 ns）送出 → `_21021_` 上升緣（44 ns）收，扣了 2.45 ns（DCD 2.2 + 0.25），slack +0.530。SRAM 讀出（clk→dout0）15.76 ns 就佔掉一半的週期 | 依據仍成立，但 **44 ns 能 PASS 取決於這個假設**：duty cycle 若比 55% 更差，這條路徑會先 FAIL。Phase 7 拿到 Caravel 的 clock 規格要先回來查這條 |
| skew（無 criterion，只看數字） | 規則 4 | 最差路徑兩端：`sram0/clk0` 3.80 ns，`_21021_/CLK` 3.13 ns，SRAM 晚 0.67 ns，對這條路徑是不利的方向。原因是 CTS 在 SRAM clock 前插了 9 顆 delay buffer（`cts-clock-tree` 規則 10 的「後果二」）。metric：ff_n40C −0.590 → 扣掉 uncertainty −0.340 ns；ss_n40C −1.249 → −0.999 ns（都仍含 derate） | 規則 10 預測的後果這次成為最差路徑。沒有找到關掉這個步驟的設定（規則 10），目前不處理 |
| `timing__unannotated_net__count` = 133 | PicoRV32 的組成 | 125 | **依據不成立**（第 4 次已判定）：建 golden 時改 |
| `CLOCK_PERIOD` 44 ns | ADR-0004 Phase 5 補充 | 全部 corner PASS，最差 +0.530 ns | 依據仍成立。餘量只有一次 run 的資料 |

## 學習

已寫入：
- `knowledge/sky130A_sky130_fd_sc_hd.md`「實測校準資料」：第 5 次的修完到 signoff 差距、`ResizerTimingPostGRT` 的動作、半週期路徑的組成、`sram_dout0` hold buffer。
- `signoff-criteria` 經驗紀錄：腳本的兩個缺口（見下面的提案 1、2）。
- `drv-timing-closure`、`cts-clock-tree` 經驗紀錄：第 5 次 harden。
- ADR-0014 狀態改成已確認。

提給使用者決定（都還沒改）：
1. **腳本改進：setup 差距要算最後一次修復**。`review_criteria.py` 只讀 `ResizerTimingPostCTS`，開了 `RUN_POST_GRT_RESIZER_TIMING` 後，要改成也報 `ResizerTimingPostGRT` 的修完值與差距。
2. **腳本改進：最差路徑要標出是否為半週期路徑**。現在的 INFO 印「arrival 21.81 ns」，這是從下降緣（22 ns）算起，看不出是半週期路徑，也沒有印扣掉的 2.45 ns uncertainty。改成印出送出端的邊緣與套用的 uncertainty，並另外報半週期路徑的最差 slack（第 4 次的提案 5）。
3. **建 Hazard3 golden**：`timing__unannotated_net__count` 依 Hazard3 的組成改成 125，並寫明推導。
4. **`sram_dout0` 的 hold buffer**：要不要用實驗看換小一點的延遲 cell（或讓 resizer 對這 32 條用較小的 hold 餘量）能不能拿回最差 setup 路徑上的部分 1.44 ns。目前餘量 +0.530 ns 是 PASS 的，不急。
