# criteria review：soc_top（PicoRV32，Phase 7 結案 regress 第二輪的重跑，乾淨 worktree `p7close2_pico`，2026-10-15）

run：worktree `arvinsa-rtl-gds-p7close2_pico` 的 `runs/soc_top`，commit `2b04451`，`make regress-picorv32` 的 `harden-soc`，30.6 分鐘，與 wrapper 的 regress 同時跑，console `runs/p7close2_regress_picorv32.console`（主目錄）。

這是第二輪 PicoRV32 regress 的重跑：第一次在第 30 項 `neg-eqy-core` 因磁碟滿 FAIL（`runs/p7close2_regress_picorv32.enospc.console`，`flow-regression-reproducibility` 經驗紀錄 2026-10-15）。那一次的 harden 也 PASS、435 個逐值相同；這次的 run 目錄把它覆蓋了。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：config_applied 41 個設定、step_config 78 個步驟、uncertainty、uncertainty_applied 30,000 條路徑、signoff_corners 15 個、checkers_ran。最後一行：`criteria-review: PASS`。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- golden 435 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` PASS（含審查後修正的 max_slew 列）。
- `ir_worst.py` PASS：max_ss_100C 5.02 mV，上限 20 mV。
- `provenance.py --verify`：開始與結束都是 `2b04451`，工作樹乾淨；沒有重試（沒有 `retries.txt`）。

「不分析的項目清單」：沒有新增。

## 合不合理

metrics 與 golden（Phase 6 結案）逐值相同，與第一輪（`../arvinsa-rtl-gds-p7close_pico/runs/soc_top_signoff/criteria_review.md`）的實測一樣，判斷沿用：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold | setup 各 ss corner +0.769 ns（min_ss_n40C）起；hold +0.082 ns（min_ff_n40C_1v95） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −1.679 ns | 依據需補充（同第一輪：含共同路徑悲觀量，推測，沒讀 OpenSTA 原始碼） |
| IR | 慢 corner 5.02 mV | 依據仍成立；pattern IR（決定 25）只做在 Hazard3 版 |

## 學習

- 審查後的 checker 修正沒有改到 flow 的輸出；PicoRV32 SoC 在乾淨 worktree 第三次逐值重現（第一輪、第二輪兩次）。knowledge 檔不追加新的數字。
