# criteria review：soc_top（PicoRV32，ADR-0021 寫回後的確認 regress，乾淨 worktree `p8wb_pico`，2026-10-15）

run：worktree `arvinsa-rtl-gds-p8wb_pico` 的 `runs/soc_top`，commit `f02a1a0`（問題總檢討的寫回；soc_top 的 RTL、config、SDC 從 Phase 6 結案起沒有改，`f02a1a0` 改的是 skill、文件、`scripts/check_skills.py`、`scripts/regress.py` 與 `scripts/neg_regress.py`），`make regress-picorv32` 的 `harden-soc`，33.6 分鐘，console `runs/p8wb_regress_picorv32.console`（主目錄）。

目的是確認新的 `regress.py`（開跑前的磁碟檢查、每個 target 的逾時）在真實 regress 上不會誤判。harden-soc 的逾時上限是參考時間 53 分 × 3 = 159 分（`REF_MIN`），沒有觸發。同時在跑的是 `p8wb_caravel` 的 `make regress-caravel`。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：
- config_applied：41 個設定
- step_config：78 個步驟
- uncertainty：8 個時序步驟、15 個 signoff corner
- uncertainty_applied：30,000 條路徑
- signoff_corners：15 個
- checkers_ran

最後一行：`criteria-review: PASS`。除了寫 `criteria_review.md` 的路徑，整份與 Phase 7 結案 regress（`../arvinsa-rtl-gds-p7close2_pico/runs/soc_top_signoff/criteria_review.txt`）逐字相同。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- `check_signoff.py`：golden 435 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` PASS：
  - max_slew：15 個 corner 都沒有違規。
  - Magic DRC：SRAM 框外 0 個；框內 4,770,846 個，全部對得上 SRAM 單獨檢查時的違規。
- `ir_worst.py` PASS：max_ss_100C 5.02 mV（上限 20 mV）。
- `provenance.py --verify`：開始與結束都是工作樹乾淨。沒有重試。

「不分析的項目清單」：沒有新增。

## 合不合理

metrics 與 golden 逐值相同，判斷沿用 Phase 7 結案時的 review：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold | setup 各 ss corner +0.769 ns（min_ss_n40C）起；hold +0.082 ns（min_ff_n40C_1v95） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −1.679 ns | 依據需補充（同前：含共同路徑悲觀量，推測，沒讀 OpenSTA 原始碼） |
| IR | 慢 corner 5.02 mV | 依據仍成立；pattern IR（ADR-0019 決定 25）只做在 Hazard3 版 |

## 學習

- `f02a1a0` 沒有改到 flow 的輸出；PicoRV32 SoC 在乾淨 worktree 第四次逐值重現。knowledge 檔不追加新的數字。
