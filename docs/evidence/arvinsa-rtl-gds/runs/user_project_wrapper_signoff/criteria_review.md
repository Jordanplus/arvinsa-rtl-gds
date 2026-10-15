# criteria review：user_project_wrapper（Phase 7 步驟 7，decap 改版後的確認 harden，2026-10-14）

run：`runs/user_project_wrapper`，commit `550869c`（只比 `7eff65a` 多了新 golden、ADR 與 knowledge 檔；flow 的輸入相同），log `runs/p7_harden_decap_confirm.log`，11:38–14:40，約 182 分鐘（前 50 分鐘與查證用 precheck 同時跑）。目的：golden 更新產生新 commit 後，讓 run guard 的「harden 的 commit = HEAD」成立，才能跑正式的 eqy／gl／ir 與 `make precheck-caravel`（ADR-0019 決定 22 的前例）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS，與 `7eff65a` 那次（`runs/p7_decap_signoff/criteria_review.txt`）相同：config_applied 57 個設定、step_config 78 個步驟、uncertainty、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran。`criteria-review: PASS`。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：

- `check_signoff.py`：golden 455 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` 13 項 PASS；`ir_worst.py` PASS（max_ss_100C 4.94 mV）；`provenance.py --verify` PASS（開始與結束都是 `550869c`，工作樹乾淨）。

「不分析的項目清單」：與 `7eff65a` 那次相同（含 `ef_decap_12` 的漏電）。

## 合不合理

所有 metrics 與 `7eff65a` 逐值相同，各 criterion 的判斷沿用 `runs/p7_decap_signoff/criteria_review.md`，結論不變。precheck 的 li1 密度在查證用 precheck（同一版圖 `7eff65a`）已實跑 PASS（`klayout_met_min_ca_density`），正式判定接著跑。

## 學習

- decap 改版後同樣可重現：兩次 harden 455 個 metrics 逐值相同。
- 與查證用 precheck（Rosetta VM，6 CPU）同時跑時，harden 時間沒有明顯增加（182 分鐘，和單獨跑那次相同）；本機 swap 維持 727 MB。
- 沒有新的工具行為，沒有依據不成立的 criterion。knowledge 檔不追加新的數字。
