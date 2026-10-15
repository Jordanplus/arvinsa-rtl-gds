# criteria review：soc_top（PicoRV32，Phase 7 結案 regress，乾淨 worktree `p7close_pico`，2026-10-14）

run：worktree `arvinsa-rtl-gds-p7close_pico` 的 `runs/soc_top`，commit `84fe505`（PicoRV32 SoC 的 RTL、config、SDC 從 Phase 6 結案 `4713c5f` 起沒有改；Phase 7 改的是 checker），`make regress-picorv32` 的 `harden-soc`，console `runs/p7close_regress_picorv32.console`（主目錄）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：config_applied 41 個設定、step_config 78 個步驟、uncertainty、uncertainty_applied 30,000 條路徑、signoff_corners 15 個、checkers_ran。最後一行：`criteria-review: PASS`。

`harden-soc: PASS`：golden 435 個 metrics 全部逐值相同；`check_soc.py` PASS（含 Phase 7 的 max_slew 列）；`ir_worst.py` PASS（max_ss_100C 5.02 mV，上限 20 mV）；`provenance.py --verify` 開始與結束都是 `84fe505`。

「不分析的項目清單」：沒有新增。

## 合不合理

metrics 與 golden（Phase 6 結案）逐值相同，判斷沿用 Phase 6 結案的 criteria review（`../arvinsa-rtl-gds-p6final_pico/runs/soc_top_signoff/criteria_review.md`）：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold | setup 各 ss corner +0.769（min_ss_n40C）起；hold +0.082 ns (min_ff_n40C_1v95) | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −1.679 ns | 依據需補充：同 soc_top_hazard3 的說明，metric 含共同路徑悲觀量（Phase 7 分析，`runs/p7_skew_analysis/README.md`，主目錄；未讀原始碼確認） |
| IR | 慢 corner 5.02 mV | 依據仍成立；pattern IR（決定 25）只做在 Hazard3 版 |

## 學習

- PicoRV32 SoC 在乾淨 worktree 再次逐值重現；Phase 7 的 checker 改動沒有改到 flow 的輸出。knowledge 檔不追加新的數字。
