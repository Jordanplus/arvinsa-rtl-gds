# ci_sram_ref golden：LibreLane CI 的 `test_sram_macro`

`make ci-sram-ref`（`pnr/ci_sram_ref/run.sh`）在本機重跑 LibreLane 官方 CI 的 `test_sram_macro`（2 顆 1 KB SRAM macro、25 ns），再用 `pnr/ci_sram_ref/check_metrics.py` 比對兩份 golden：

- `upstream.metrics.json`：LibreLane 3.0.14 官方 CI 的結果，原檔未修改（出處見下表）。
- `local.metrics.json`：本機 2026-10-03 的結果（sha256 `1abe3a0f03ef3f4ce9f1b4c53b03440c4dc84553f17656dfa9a5314b540a1ef1`）。同一天連跑三次，307 個 metrics 完全相同。

## 出處

| 項目 | 值 |
|---|---|
| 來源 repo | [librelane/librelane-metrics](https://github.com/librelane/librelane-metrics)（LibreLane CI 上傳 metrics 的地方，見 LibreLane `.github/workflows/ci.yml` 的 `upload_metrics` job） |
| branch | `commit-f24e0ea5db2260719e9a0c7d51d07db74a87fa23`（= LibreLane 3.0.14 的 commit） |
| commit | `f9f2748bb6675853c669f1137d4127b94f30e764`（2026-09-06） |
| 檔案 | `sky130A-sky130_fd_sc_hd-test_sram_macro.metrics.json` |
| git blob sha | `6dc76c77fba854a8c683d9975474db50b14dbee6`（本地檔 `git hash-object` 相同，確認逐 byte 一致） |
| sha256 | `dfca2eaf27bb772057630d372fff103742154177a0e6468bf3d9ad3bbe76b2c5` |
| 設計來源 | librelane-ci-designs `9b3bebe834ccd972a5b4f10d82c32354f9a6a1ca`（LibreLane 3.0.14 的 `test/designs` submodule）的 `test_sram_macro/` |
| 執行平台 | GitHub Actions x86_64 Linux（本機是 Apple Silicon macOS，所以擺放、繞線細節可能不同） |

## 本機與官方的差異（2026-10-03，Apple Silicon macOS vs 官方 x86_64 Linux）

signoff 項目全部一致：LVS、繞線 DRC、KLayout DRC、power grid、antenna 都是 0；9 個 corner 的 setup／hold slack 與官方差距都在 0.01 ns 以內；Magic DRC 同為 532。
擺放與繞線細節不同：standard cell 7451 vs 7454、總線長 64489 vs 65305、detailed route 收斂的 iteration 數 4 vs 8。
因此官方本來就不是 0 的項目數字也不同：max slew violation 74 vs 70（多出來的是 fanout buffer／antenna diode 輸入端的 slew，與官方同性質）、max cap violation 2 vs 3。

第一版 checker 對這類項目用「本機 ≤ 官方」判定，結果 max slew 74 > 70 判 FAIL。查證後確認是平台差異，不是本機不穩定（兩次重跑 0 差異），所以改成下表的規則：跨平台只比 signoff 項目，其他全部改跟本機 golden 逐項完全比對。

## checker 規則（`check_metrics.py`）

| 類型 | 規則 | 為什麼 |
|---|---|---|
| must | LVS、route DRC、KLayout DRC、power grid、disconnected pin、antenna、unmapped cell、setup/hold violation 數 = 0；macro 數 = 2 | 官方結果這些都是 0，本機也必須是 0 |
| corner | 9 個 corner 的 setup／hold worst slack 都 ≥ 0，且 9 個都要有 | 缺 corner 也算 FAIL，避免 checker 沒檢查到卻 PASS |
| golden | 所有 metrics（307 個）與 `local.metrics.json` 完全相同，多或少一個 key 也 FAIL | 本機 flow 是 deterministic；工具、PDK、設定有任何變動都會被抓到，要 review 後才能更新 golden |
| info | Magic DRC、max slew／cap／fanout、unannotated net、面積、cell 數、wirelength、slack、IR drop、power 與官方對照 | 跨平台本來就有差，只列出不判定 |

checker 已用植入錯誤測過，以下每一種都會 FAIL 在對應的那一列：LVS=1、某 corner 的 setup/hold slack < 0、少一個 corner、少一個 must 項目、slew violation 多 1、wirelength 多 1、多一個或少一個 metric。

更新 `local.metrics.json` 的時機：升級 LibreLane／PDK 或改 flow 設定後，先確認 must／corner 全 PASS、檢視 golden 差異，再把新的 `runs/ci_sram_ref/metrics.json` 複製過來，並在這份 README 記錄原因與新的 sha256。
