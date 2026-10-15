# criteria review：picorv32_core（ADR-0021 寫回後的確認 regress，乾淨 worktree `p8wb_pico`，2026-10-15）

- run：worktree `arvinsa-rtl-gds-p8wb_pico` 的 `runs/picorv32_core`，commit `f02a1a0`，沒有重試；`make regress-picorv32` 的 `harden-core`（15.6 分鐘），console `runs/p8wb_regress_picorv32.console`（主目錄）
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-core: PASS`

這次 regress 的目的是確認新的 `regress.py`（開跑前的磁碟檢查、每個 target 的逾時）在真實 regress 上不會誤判。harden-core 的逾時上限是 max(30, 21 × 3) = 63 分（`REF_MIN`），沒有觸發。同時在跑的是 `p8wb_caravel` 的 `make regress-caravel`。

## 有沒有被執行

- 腳本各項都 PASS：config 13 個設定生效、77 個 step config 一致、9 個 corner 共 18,000 條路徑的 uncertainty 都是 0.25 ns、corner 齊全、4 個 checker 都有結果行。除了寫 `criteria_review.md` 的路徑，整份與 Phase 7 結案 regress（`../arvinsa-rtl-gds-p7close2_pico/runs/picorv32_core_signoff/criteria_review.txt`）逐字相同。
- `check_signoff.py` PASS：golden 325 個 metrics **全部逐值相同**（0 個在誤差內、0 個不同）。
- `disconnected-pins: PASS`；`cpu_params` 沒有 FAIL 列。
- `provenance.py --verify`：開始與結束都是工作樹乾淨。沒有 FAIL 列。

## 合不合理

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| resizer hold 餘量 0.1 ns | signoff 最差 +0.039 ns（min_ff_n40C_1v95） | 依據仍成立 |
| resizer setup 餘量 | signoff 最差 +6.175 ns（max_ss_100C_1v60） | 依據仍成立 |
| golden 誤差（ADR-0015） | 0 個在誤差內 | 依據仍成立；Phase 7 第一輪曾有 29 個在誤差內（多執行緒 detailed routing 不可重現），這次是 Phase 7 以來四次中第三次逐值相同，誤差表仍要保留 |
| 其他（slew、corner、uncertainty、上限檔） | 與 Phase 7 結案相同 | 依據仍成立 |

## 學習

- `f02a1a0` 沒有改到 flow 的輸出。沒有新的製程數字，knowledge 檔不追加。
