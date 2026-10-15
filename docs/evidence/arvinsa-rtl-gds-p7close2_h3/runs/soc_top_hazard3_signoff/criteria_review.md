# criteria review：soc_top_hazard3（Phase 7 結案 regress 第二輪的第三次執行，乾淨 worktree `p7close2_h3`，2026-10-15）

run：worktree `arvinsa-rtl-gds-p7close2_h3` 的 `runs/soc_top_hazard3`，commit `2b04451`（審查修正後；soc_top 的 RTL、config、SDC 從 Phase 6 結案 `4713c5f` 起沒有改，`2b04451` 改的是 checker、negative test、註解與文件），`make regress` 的 `harden-soc`，52.5 分鐘，console `runs/p7close2_regress_hazard3.console`（主目錄）。

這是第二輪 Hazard3 regress 的第三次執行：
- 第一次：`neg-pnr` 在磁碟滿時卡住，手動停掉（`runs/p7close2_regress_hazard3.enospc.console`）。那次的 harden-soc 也 PASS，criteria review 寫過，這次的 run 目錄把它覆蓋了。
- 第二次：`neg-precheck` 的比對基準步驟 KLayout Signal 11（`runs/p7close2_regress_hazard3.sig11.console`）。
- 這一次：前面 20 項都 PASS，包括 `neg-precheck` 31/31。期間同時在跑的只有 fill 試跑的 Magic（約 2.5 GB），沒有其他 regress。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：
- config_applied：42 個設定
- step_config：78 個步驟
- uncertainty：8 個時序步驟、15 個 signoff corner
- uncertainty_applied：50,670 條路徑
- signoff_corners：15 個
- checkers_ran

最後一行：`criteria-review: PASS`。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- `check_signoff.py`：golden 441 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` PASS：
  - max_slew：15 個 corner 都沒有違規。
  - Magic DRC：4,770,846 個，全部在 SRAM 框內，位置都對得上 SRAM 單獨檢查時的違規。
- `ir_worst.py` PASS：max_ss_100C 12.48 mV、max_ss_n40C 11.89 mV（上限 20 mV）。pattern IR 由同一條 regress 之後的 `make ir-soc` 判。
- `provenance.py --verify`：開始與結束都是 `2b04451`，工作樹乾淨。沒有重試（沒有 `retries.txt`）。

「不分析的項目清單」：沒有新增。

## 合不合理

metrics 與 golden（Phase 6 結案）逐值相同，實測與第一輪（`../arvinsa-rtl-gds-p7close_h3/runs/soc_top_hazard3_signoff/criteria_review.md`）一樣，判斷沿用：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold 餘量 | setup +0.656 ns（min_ss_n40C，SRAM 半週期路徑），hold +0.126 ns（min_ff_n40C）；GRT 後 hold 修復結束 +0.133 ns，到 signoff 差 0.007 ns（餘量 0.05 ns） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −1.540 ns | 依據需補充（同第一輪：含共同路徑的悲觀量，推測，沒讀 OpenSTA 原始碼） |
| IR | 預設切換率、慢 corner 12.48 mV | 依據仍成立；判定值是 `make ir-soc` 的 max power pattern |

## 學習

- 審查後的 checker 修正沒有改到 flow 的輸出。soc_top_hazard3 在乾淨 worktree 第五次逐值重現：Phase 6 兩次、Phase 7 第一輪一次、第二輪兩次（第一次執行與這一次）。
- 只有一條 regress 在跑時，harden 52.5 分鐘；第一輪三條平行時是 30.8 分鐘。這次比較慢，推測是和 fill 試跑的 Magic 搶 CPU，沒有確認。
- knowledge 檔不追加新的數字。
