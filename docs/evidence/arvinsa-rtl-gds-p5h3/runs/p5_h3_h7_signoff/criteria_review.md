# signoff criteria 檢查：Hazard3 第 7 次 harden

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3`（commit `4d309de`，flow 設定與第 5、6 次相同），2026-10-07
- 目的：使用者決定「先量頻率，再跑第 7 次」，確認 golden 可重現（第一次被系統記憶體不足中止，`mflux` 結束後重開）
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`

## 有沒有被執行

腳本 5 項都 PASS（41 個設定、78 個 step config、8 個時序 step 與 15 個 corner 的 uncertainty、corner 齊全、4 個 checker 都有結果行）。

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完 | — | setup／hold 15 個 corner 都 PASS（最差 +0.529／+0.107 ns）；DRC、LVS、slew、cap、antenna 都是 0 |
| `check_signoff.py` | FAIL（12 列） | golden 比對：440 個 metric 中 335 個相同、94 個在誤差內、11 個不同（另 1 列是摘要） | **不是設計問題**，是 detailed routing 不能重現，見下 |
| `sram_drc_alone`、`check_soc.py`、`check_inputs.py --resolved`、`provenance.py` | 全部 PASS | — | — |

不同的 11 個 metric：antenna diode 101（golden 100）、antenna cell 數與面積、stdcell 30,475（30,474）與面積、fill cell 數與面積、utilization 兩個、`global_route__vias`（9 對 72；第 44 步兩次都是 160,112，第 46 步 detailed routing 改寫成這個值，推測是繞線後 antenna 修補的增量 global routing 只算新增的 via，未查證）。

**分歧從哪裡開始（已驗證）**：
- 第 41 步這次與 golden 相同（global routing 線長 1,146,421 µm、guide 相同），第 44 步以前的 DEF 全部相同。
- 第 46 步 detailed routing 開始不同。這一步內的 antenna 修補：第 1、2 輪兩次 run 完全相同（找到 70 個違規、插 95 顆；找到 5 個、插 5 顆）；第 2 輪後重繞，golden run 剩 0 個，第 7 次剩 1 個，所以多跑第 3 輪、多插 1 顆 diode。兩次最後都是 0 個違規。
- detailed routing 用 10 個執行緒（7 分 51 秒），是已知不能重現的一步（`signoff-checker-qualification` 規則 5）。PicoRV32 版的 golden 只看過它改變中間輪的 DRC 數，這次第一次改變了數量類的 metric。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| golden：數量、面積不給誤差；key 集合必須相同 | `signoff-checker-qualification` 規則 5：detailed routing 的差異只會出現在連續量與中間輪 DRC | 第 6 次：第 41 步 global routing 不同（27 次裡 5 次）→ 61 個 metric 不同；第 7 次：detailed routing 後的 antenna 修補多一輪 → diode、cell 數、面積不同 | **依據不成立**（對 Hazard3 版）：兩個不能重現的來源都會改變數量。三次 harden 只有 1 次與 golden 完全相同（第 5 次本身） |
| `RUN_POST_GRT_RESIZER_TIMING` 與它的餘量 | ADR-0014 | 修完 +0.002 → signoff +0.529（與第 5 次幾乎相同，第 44 步以前完全相同） | 依據仍成立（第 3 次觀察） |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10 | hold +0.275 → +0.107 | 依據仍成立 |
| uncertainty：半週期路徑的 DCD 預算 | 同第 5 次 | 最差仍是 `sram0` 下降緣 → `_21021_`，+0.529 ns | 依據仍成立；44 ns 能 PASS 取決於這個假設 |

## 學習

- 寫入經驗紀錄（`flow-regression-reproducibility`、`signoff-checker-qualification`）：detailed routing 的差異會經由繞線後的 antenna 修補改變 diode 數與 cell 數。
- 2026-10-07 稍後補齊（使用者問「第七次有 review 與需要更新的嗎」才發現漏了）：knowledge 檔的第 7 次校準數據、同設定 run 之間的差異；`antenna-signoff`（diode 數跟著繞線走）、`librelane-run-debug`（run 改名後 `state_in.json` 的路徑失效）、`flow-regression-reproducibility`（第一次被系統記憶體不足中止）、`core-migration-hazard3` 規則 22（換 core 要重新量可重現性）、`drv-timing-closure`（規則 12 第 3、4 次觀察）。
- 提給使用者決定：golden 對 Hazard3 版要怎麼處理（改規則、讓 flow 可重現、或其他），決定後寫 ADR。決定前下游驗證（EQY、gate-level 模擬、negative test）無法開始，因為它們要求 harden PASS。
