# criteria review：soc_top_hazard3（Phase 7 結案 regress，乾淨 worktree `p7close_h3`，2026-10-14）

run：worktree `arvinsa-rtl-gds-p7close_h3` 的 `runs/soc_top_hazard3`，commit `84fe505`（Phase 7 步驟 8；soc_top 的 RTL、config、SDC 從 Phase 6 結案 `4713c5f` 起沒有改，改的是 checker：`check_soc.py` 的 max_slew 等列、EQY 的 amend 重試、`make ir-soc`），`make regress` 的 `harden-soc`，console `runs/p7close_regress_hazard3.console`（主目錄）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：config_applied 42 個設定、step_config 78 個步驟、uncertainty（8 個時序步驟、15 個 signoff corner）、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran。最後一行：`criteria-review: PASS`。

`harden-soc: PASS`：
- `check_signoff.py`：golden 441 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` PASS（含 Phase 7 加的 max_slew 列：soc_top 沒有邊界例外，0 個違規）；Magic DRC 4,770,846 個全部在 SRAM 框內。
- `ir_worst.py` PASS：max_ss_100C 12.48 mV（上限 20 mV）；pattern IR 由同一條 regress 之後的 `make ir-soc` 判。
- `provenance.py --verify`：開始與結束都是 `84fe505`，工作樹乾淨。

「不分析的項目清單」：沒有新增（`ef_decap_12` 只用在 wrapper，soc_top 的 fill 仍是 `decap_3`）。

## 合不合理

metrics 與 golden（Phase 6 結案）逐值相同，各 criterion 的實測與判斷沿用 Phase 6 結案的 criteria review（`../arvinsa-rtl-gds-p6final_h3/runs/soc_top_hazard3_signoff/criteria_review.md`）：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold 餘量 | setup +0.656 ns（min_ss_n40C，SRAM 半週期路徑）、hold +0.126 ns（min_ff_n40C） | 依據仍成立；dout0 transition 的 what-if 在 wrapper 上另量（Phase 6 限制 1，exit review） |
| skew metric | hold skew metric nom_ss_n40C −1.540 ns | 依據需補充：Phase 7 的分析（`runs/p7_skew_analysis/README.md`，主目錄）顯示這個 metric 把共同路徑的悲觀量算成扣分，真正影響 hold 的 skew 約 −0.68 ns；未讀 OpenSTA 原始碼確認，暫不改 checker |
| IR | 預設切換率、慢 corner 12.48 mV | 依據仍成立；ADR-0019 決定 25 起另由 `make ir-soc` 以 max-power pattern 判 |

## 學習

- soc_top_hazard3 在乾淨 worktree 第三次逐值重現（Phase 6 兩次、Phase 7 一次），Phase 7 的 checker 改動沒有改到 flow 的輸出。knowledge 檔不追加新的數字。
- 與 wrapper 的 harden 同時跑（另一個 worktree），golden 仍逐值相同。
