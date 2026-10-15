# criteria review：picorv32_core（Phase 7 結案 regress 第二輪的重跑，乾淨 worktree `p7close2_pico`，2026-10-15）

- run：worktree `arvinsa-rtl-gds-p7close2_pico` 的 `runs/picorv32_core`，commit `2b04451`，沒有重試；`make regress-picorv32` 的 `harden-core`（20.8 分鐘），console `runs/p7close2_regress_picorv32.console`（主目錄）
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-core: PASS`

第二輪 PicoRV32 regress 第一次在 `neg-eqy-core` 因磁碟滿 FAIL（`runs/p7close2_regress_picorv32.enospc.console`）。那一次的 harden-core 也 PASS、325 個逐值相同；這次的 run 目錄覆蓋了它。

## 有沒有被執行

- 腳本各項都 PASS：config 13 個設定生效、77 個 step config 一致、9 個 corner 共 18,000 條路徑的 uncertainty 都是 0.25 ns、corner 齊全、4 個 checker 都有結果行。
- `check_signoff.py` PASS：golden 325 個 metrics **全部逐值相同**（0 個在誤差內、0 個不同）。
- `provenance.py --verify`：開始與結束都是 `2b04451`，工作樹乾淨。沒有 FAIL 列。

## 三次結案 run 的比較

| run | 在誤差內的 metrics | 繞線 |
|---|---|---|
| 第一輪（`84fe505`） | 29 個 | 708,675 µm、134,167 個 via |
| 第二輪第一次（`2b04451`，之後磁碟滿） | 0 個 | 708,673 µm、134,168 個 via |
| 第二輪重跑（`2b04451`，這次） | 0 個 | 708,673 µm、134,168 個 via（與 golden 相同） |

輸入相同；第一輪的差異來自多執行緒 detailed routing 的不可重現（Phase 5 已知限制），三次中出現一次。

## 合不合理

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| resizer hold 餘量 0.1 ns | signoff 最差 +0.039 ns（min_ff_n40C_1v95） | 依據仍成立 |
| resizer setup 餘量 | signoff 最差 +6.175 ns（max_ss_100C_1v60） | 依據仍成立 |
| golden 誤差（ADR-0015） | 0 個在誤差內 | 依據仍成立；不可重現是偶發的（三次一次），誤差表需要保留 |
| 其他（slew、corner、uncertainty、上限檔） | 與第一輪相同 | 依據仍成立 |

## 學習

- 「目前為止逐值相同」不能當作可以拿掉誤差的依據（支持 ADR-0019 決定 26 對 wrapper 的處理）。沒有新的製程數字，knowledge 檔不追加。
