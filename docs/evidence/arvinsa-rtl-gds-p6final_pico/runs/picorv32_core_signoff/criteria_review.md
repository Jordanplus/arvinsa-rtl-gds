# criteria review：picorv32_core（Phase 6 步驟 4d，乾淨 worktree 的 `make regress-picorv32`，2026-10-11）

- run：`../arvinsa-rtl-gds-p6final_pico/runs/picorv32_core`，commit `4713c5f`，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-core: PASS`

## 有沒有被執行

- 腳本 5 項都 PASS：config 13 個設定生效、77 個 step config 一致、9 個 corner 共 18,000 條路徑的 uncertainty 都是 0.25 ns（core 沒有自己的 SDC，所以沒有 `uncertainty` 那一列）、corner 齊全、4 個 checker 都有結果行。
- `check_signoff.py` PASS：golden 325 個 metrics 全部逐值相同。
- core 不含 SRAM，Phase 6 沒有改它的輸入：`criteria_review.txt` 的每一列與 Phase 5 結案那次（`../arvinsa-rtl-gds-p5final_pico/runs/picorv32_core`）完全相同；網表與 DEF 的 sha256 相同，GDS 清除 BGNLIB／BGNSTR 的日期後 sha256 相同。
- 沒有 FAIL 列。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer hold 餘量 0.1 ns | skill「resizer 的 slack margin」 | 最後一次修復（PostCTS）+0.100 → signoff +0.039 ns，差距 0.061 < 0.1 ns | 依據仍成立 |
| resizer setup 餘量 | 同上 | 沒有 setup 違規可修；signoff 最差 +6.175 ns（max_ss_100C_1v60） | 依據仍成立 |
| hold 餘量的代價 | skill「hold 餘量」 | hold buffer 2,230 個，PostCTS 面積 +13.1 %，與 Phase 5 相同 | 依據仍成立 |
| slew 上限 | PDK 預設（core 沒有自訂） | `set_max_transition` 未設、slew 修復 20 %／30 %，與 Phase 5 相同 | 依據仍成立 |
| corner 清單 | `STA_CORNERS`（9 個） | 最差 setup 在 max_ss_100C_1v60；core 的最差路徑是 I/O 路徑 `resetn -> mem_la_addr[30]` | 依據仍成立 |
| uncertainty 0.25 ns | `CLOCK_UNCERTAINTY_CONSTRAINT` | 9000 條路徑沒有半週期路徑，DCD 不適用 | 依據仍成立 |
| 上限檔（`signoff/limits/picorv32_core.toml`） | Phase 2 為這顆 core 推導 | golden 逐值相同 | 依據仍成立 |

## 學習

- core 的 harden 跨 Phase 5 與 Phase 6 的 commit 仍逐位元重現（網表、DEF 相同，GDS 只差日期）。
- 沒有新的製程數字；沒有依據不成立的 criterion，沒有提案。
