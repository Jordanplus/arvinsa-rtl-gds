# criteria review：user_project_wrapper（Phase 7 確認 harden，2026-10-13）

run：`runs/user_project_wrapper`，commit `f4ea9de`（golden 已建 `7e55852`、EQY amend 重試 `f4ea9de`；`config.json`、SDC、RTL 與第一次正式 harden `f721cff` 相同），log `runs/p7_harden_confirm.log`，全部 240 分鐘（16:5x–20:45）。目的：建 golden 與改 checker 產生新 commit 後，讓 run guard 的「harden 的 commit = HEAD」成立，才能跑正式的 eqy／gl／ir（ADR-0019 決定 22）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS，而且與第一次正式 harden（`runs/p7_formal_signoff/criteria_review.txt`）逐行相同：config_applied 55 個設定、step_config 78 個步驟、uncertainty、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran。最後一行：`criteria-review: PASS`。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 都沒有 FAIL 列：

- `check_signoff.py`：golden 455 個 metrics 全部逐值相同（0 個落在誤差內、0 個只出現在一邊、0 個不同）。其餘上限列與第一次正式 harden 相同。
- `check_soc.py` 13 項全部 PASS；Magic DRC 5,572,955 個全部在 SRAM 框內，位置對得上 SRAM 單獨檢查。
- `ir_worst.py` PASS：max_ss_100C 4.94 mV、max_ff_100C 參考值 6.99 mV。
- `provenance.py --verify` PASS：開始與結束都是 `f4ea9de`，工作樹乾淨，LibreLane `f24e0ea`、PDK `8afc8346`。

「不分析的項目清單」：這次沒有新增。

## 合不合理

所有 metrics 與第一次正式 harden 逐值相同，各 criterion 的實測與判斷沿用 `runs/p7_formal_signoff/criteria_review.md`「合不合理」一表，結論不變：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold 餘量、hold 的代價、slew 上限、corner 清單、uncertainty、上限檔推導的數字 | 與 `f721cff` 逐值相同（setup +0.548 ns、hold +0.187 ns、hold buffer 3,291、內部 slew 最差 0.576 ns、disconnected 327、unannotated 667） | 依據仍成立（DCD 仍是假設） |
| skew | hold skew metric −3.598 ns，同上次 | 資料不足：成因列入步驟 8 待查 |
| golden 容許誤差 | 第二次 harden 455 個全部相同，沒有用到任何誤差 | 資料不足：同一台機器、同一個 tree 的兩次 run 可重現；乾淨 worktree 的兩輪仍在步驟 8 |
| power signoff 的切換活動 | 正式的 `make ir-caravel` 接著跑（網表與查證時相同，預期 19.58 mV） | 依據仍成立；餘量 2% 的提醒不變 |

## 學習

- wrapper 的 harden 在同一台機器上完全可重現：`f721cff` 與 `f4ea9de` 兩次（中間只改了 golden 與 EQY 腳本，沒有改 flow 的輸入）455 個 metrics 逐值相同。knowledge 檔不追加新的數字（與 2026-10-13 已記的列相同）。
- harden 時間：240 分鐘（上次 249）。
- 沒有新的工具行為，沒有依據不成立的 criterion，沒有提案。
