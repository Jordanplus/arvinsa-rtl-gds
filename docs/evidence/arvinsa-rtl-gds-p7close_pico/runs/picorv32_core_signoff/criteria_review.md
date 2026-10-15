# criteria review：picorv32_core（Phase 7 結案 regress 第一輪，乾淨 worktree `p7close_pico`，2026-10-14）

- run：worktree `arvinsa-rtl-gds-p7close_pico` 的 `runs/picorv32_core`，commit `84fe505`，沒有重試；`make regress-picorv32` 的 `harden-core`（16.8 分鐘），console `runs/p7close_regress_picorv32.console`（主目錄）
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-core: PASS`

## 有沒有被執行

- 腳本 5 項都 PASS：config 13 個設定生效、77 個 step config 一致、9 個 corner 共 18,000 條路徑的 uncertainty 都是 0.25 ns、corner 齊全、4 個 checker 都有結果行。
- `check_signoff.py` PASS：golden 325 個 metrics 中 **296 個逐值相同、29 個在誤差內**、0 個不同。Phase 5、Phase 6 結案時都是 325 個逐值相同。
- `provenance.py --verify`：開始與結束都是 `84fe505`，工作樹乾淨。沒有 FAIL 列。

## 29 個在誤差內的 metrics

全部對得回 detailed routing 的一個小差異（Phase 5 已知限制「多執行緒 detailed routing 的結果不完全可重現」，`docs/phase_exit/phase5.md`）：

| 類別 | golden → 這次 |
|---|---|
| 繞線 | `route__wirelength` 708,673 → 708,675 µm（+2）；`route__vias` 134,168 → 134,167（−1） |
| hold slack | 各 corner 差 10⁻⁷–10⁻⁶ ns，例如最差 `min_ff_n40C_1v95` +0.0390894 → +0.0390892 ns |
| 功耗 | `power__total` 11.88488 → 11.88498 mW（+0.0008%） |
| IR（nom_tt） | 0.28789 → 0.28790 mV 等 |

- cell 數、面積、setup slack、DRC／LVS／antenna 都逐值相同，只有繞線與受繞線寄生影響的數字變了。
- 推測（沒有做實驗）：這次與另外兩條 regress、三個審查 agent 同時跑，機器負載很重，多執行緒 detailed routing 的執行順序不同；Phase 5 量過同一現象。沒有看 DEF 的差異位置。

## 合不合理

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| resizer hold 餘量 0.1 ns | 最後一次修復（PostCTS）+0.100 → signoff +0.039 ns，差 0.061 < 0.1 ns | 依據仍成立 |
| resizer setup 餘量 | 沒有 setup 違規可修；signoff 最差 +6.175 ns（max_ss_100C_1v60） | 依據仍成立 |
| golden 誤差（ADR-0015） | 差異遠小於誤差（slack 10⁻⁶ ns 對 0.32 ns；繞線 +2 µm） | 依據仍成立；誤差表確實需要，這次是 picorv32_core 第一次用到 |
| 其他（slew、corner、uncertainty、上限檔） | 與 Phase 6 結案的 review 相同（`../arvinsa-rtl-gds-p6final_pico/runs/picorv32_core_signoff/criteria_review.md`） | 依據仍成立 |

## 學習

- picorv32_core 從 Phase 5 起一直逐值重現，這次第一次出現 detailed routing 的小差異，被誤差表吸收。這是 wrapper golden 誤差「維持 hazard3 的值、不改成逐值相同」（ADR-0019 決定 26）的一個實例：同一套 flow 的不可重現步驟在另一顆設計上也會出現。
- 沒有新的製程數字，knowledge 檔不追加。
