# signoff criteria 檢查：Hazard3 第 8 次 harden

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3`（commit `9ef0be7`，flow 設定與第 5–7 次相同；這個 commit 加了 ADR-0015 的 golden 誤差），2026-10-07
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 整體結果：`harden-soc: PASS`（Hazard3 版第一次）

## 有沒有被執行

腳本 5 項都 PASS（41 個設定、78 個 step config、8 個時序 step 與 15 個 corner 的 uncertainty、corner 齊全、4 個 checker 都有結果行）。

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完 | — | setup／hold 15 個 corner 都 PASS（最差 +0.530／+0.107 ns）；DRC、LVS、slew、cap、antenna 都是 0 |
| `check_signoff.py` | PASS | — | golden 440 個 metric 完全相同，沒有用到 ADR-0015 的誤差或可選 key |
| `sram_drc_alone`、`check_soc.py`、`check_inputs.py --resolved`、`provenance.py` | 全部 PASS | — | — |

這次第 41 步的 global routing（線長 1,146,421 µm）與 detailed routing 都與 golden 相同，所以 metric 完全一樣。

「不分析的項目清單」：這次沒有寫，Phase 5 exit review 時要逐條寫。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| golden 比對（ADR-0015 的誤差） | 4 組 run 的最大差異約 5 倍 | 這次完全相同，誤差沒有被用到 | 資料不足：這次沒有驗證到誤差本身；要等之後出現差異的 run |
| `RUN_POST_GRT_RESIZER_TIMING` 與它的餘量 | ADR-0014 | 修完 +0.002 → signoff +0.530 ns | 依據仍成立 |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10 | hold +0.275 → +0.107 ns | 依據仍成立 |
| uncertainty：半週期路徑的 DCD 預算 | `docs/notes/signoff_criteria_soc_top.md` | 最差仍是 `sram0` 下降緣 → `_21021_`，+0.530 ns | 依據仍成立；44 ns 能 PASS 取決於這個假設 |
| corner、slew、skew、unannotated 125 | 第 5 次的判斷 | 與第 5 次相同 | 與第 5 次相同 |

## 學習

- 這次與 golden 完全相同，沒有新的數字要寫進 knowledge 檔（與第 5 次的校準列相同）。
- 可重現性的統計：第 5–8 次 harden 裡，第 5、8 次完全相同，第 6 次第 41 步不同，第 7 次 detailed routing 不同；golden README 的可重現性表加一列。
- 下游驗證（EQY、gate-level 模擬、negative test）現在可以開始。
