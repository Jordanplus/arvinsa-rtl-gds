# criteria review：soc_top_hazard3（ADR-0021 寫回後的確認 regress，乾淨 worktree `p8wb_h3`，2026-10-15）

run：worktree `arvinsa-rtl-gds-p8wb_h3` 的 `runs/soc_top_hazard3`，commit `f02a1a0`（問題總檢討的寫回；soc_top 的 RTL、config、SDC 從 Phase 6 結案 `4713c5f` 起沒有改，`f02a1a0` 改的是 skill、文件、`scripts/check_skills.py`、`scripts/regress.py` 與 `scripts/neg_regress.py`），`make regress` 的 `harden-soc`，33.4 分鐘，console `runs/p8wb_regress_hazard3.console`（主目錄）。

這次 regress 的目的是確認新的 `regress.py`（開跑前的磁碟檢查、每個 target 的逾時）在真實 regress 上不會誤判。harden-soc 的逾時上限是參考時間 53 分 × 3 = 159 分（`REF_MIN`），33.4 分鐘沒有觸發。同時在跑的是 `p8wb_caravel` 的 `make regress-caravel`。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：
- config_applied：42 個設定
- step_config：78 個步驟
- uncertainty：8 個時序步驟、15 個 signoff corner
- uncertainty_applied：50,670 條路徑
- signoff_corners：15 個
- checkers_ran

最後一行：`criteria-review: PASS`。除了寫 `criteria_review.md` 的路徑，整份與 Phase 7 結案 regress（`../arvinsa-rtl-gds-p7close2_h3/runs/soc_top_hazard3_signoff/criteria_review.txt`）逐字相同。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- `check_signoff.py`：golden 441 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` PASS：
  - max_slew：15 個 corner 都沒有違規。
  - Magic DRC：SRAM 框外 0 個；框內 4,770,846 個，全部對得上 SRAM 單獨檢查時的違規。
- `ir_worst.py` PASS：max_ss_100C 12.48 mV、max_ss_n40C 11.89 mV（上限 20 mV）。pattern IR 由同一條 regress 之後的 `make ir-soc` 判。
- `provenance.py --verify`：開始與結束都是工作樹乾淨、submodule 在記錄的 commit。沒有重試。

「不分析的項目清單」：沒有新增。

## 合不合理

metrics 與 golden 逐值相同，判斷沿用 Phase 7 結案時的 review：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold 餘量 | setup +0.656 ns（min_ss_n40C，SRAM 半週期路徑），hold +0.126 ns（min_ff_n40C）；GRT 後 hold 修復結束 +0.133 ns，到 signoff 差 0.007 ns（餘量 0.05 ns） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −1.540 ns | 依據需補充（同前：含共同路徑的悲觀量，推測，沒讀 OpenSTA 原始碼） |
| IR | 預設切換率、慢 corner 12.48 mV | 依據仍成立；判定值是 `make ir-soc` 的 max power pattern |

## 學習

- `f02a1a0` 沒有改到 flow 的輸出。soc_top_hazard3 在乾淨 worktree 第六次逐值重現。
- 兩條 regress 平行時 harden 33.4 分鐘，與 Phase 7 第一輪三條平行的 30.8 分鐘相近；上次單條 52.5 分鐘是和 fill 試跑搶 CPU 的推測更可信，但仍沒確認。
- knowledge 檔不追加新的數字。
