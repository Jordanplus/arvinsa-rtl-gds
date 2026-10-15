# signoff criteria 檢查：Hazard3 第 6 次 harden

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3`（commit `d6f3074`，週期 44 ns，與第 5 次相同的 flow 設定；這個 commit 加了 Hazard3 golden、上限 125、新版 `review_criteria.py`），2026-10-07
- 目的：golden 規則「再跑一次確認新 golden PASS」（`signoff-checker-qualification` 規則 6），也讓下游驗證的 commit 檢查能通過
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 第一次用新版腳本：INFO 列印出兩次修復各自修完的值、用最後一次算差距，也標出半週期路徑，輸出符合預期

## 有沒有被執行

腳本 5 項都 PASS：41 個設定都進了 `resolved.json`、78 個 step 的 config 一致；`clock_uncertainty.sdc` 的那一行出現在 8 個時序 step（含 `ResizerTimingPostGRT`）與 15 個 signoff corner；corner 齊全；4 個 checker 都有結果行。

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完 | — | setup／hold 15 個 corner 都 PASS（最差 +0.556／+0.109 ns）；DRC、LVS、slew、cap 都是 0 |
| `check_signoff.py` | FAIL（62 列） | 全部是 golden 比對：440 個 metric 中 293 個相同、86 個在誤差內、61 個不同（另 1 列是摘要） | **都不是設計問題**，是 flow 的結果不能重現，見下面的「golden 比對」列 |
| `sram_drc_alone`、`check_soc.py`、`check_inputs.py --resolved`、`provenance.py` | 全部 PASS | — | — |

不同的 61 個 metric：
- 數量與面積（規則不給誤差）：antenna diode 94（golden 100）、stdcell 30,469（30,474）、timing repair buffer 11,085（11,088）、fill cell、面積、utilization、繞線 net 數。
- 連續量超出誤差：`nom_ss_n40C`、`*_ss_100C` 的 setup／hold slack 與 skew（差 0.01–0.03 ns）、線長、global routing 的 via 與線長。
- key 不同：沒有 `route__drc_errors__iter:7`、`route__wirelength__iter:7`（detailed routing 少一輪），沒有 `flow__warnings__count:RSZ-0062`（這次繞線後的 setup 修復全部修完）。

**分歧從哪裡開始（已驗證）**：逐步比對 DEF，第 41 步（`RepairDesignPostGRT`）以前都相同。第 41 步修完的 DEF 也相同，log 一直到最後一次 `global_route -congestion_iterations 50` 的結果之前都相同；那次 global routing 的總線長第 5 次 1,146,421 µm、第 6 次 1,146,538 µm，routing guide 不同。後面的 antenna 修補（找到 109 對 103 個違規、插 22 對 26 顆 diode）、`ResizerTimingPostGRT`、detailed routing 跟著改變。

**是隨機的（已驗證）**：用第 6 次第 41 步自己的 `state_in.json` 與 `config.json` 單步重跑 4 次，4 次的 guide 與總線長都和第 5 次（golden）相同。第 4、5 次 harden 的這一步也相同（實驗 A 用第 4 次的前 43 步，結果與第 5 次一樣）。到目前 7 次裡 1 次不同。之後（使用者決定「先量頻率，再跑第 7 次」）又單步重跑 20 次：16 次與 golden 相同，其餘 4 次分成 3 種結果；合計 27 次裡 22 次相同（約 81%），沒有出現 GRT-0229。

**可能的關聯（推測）**：同一步的 global routing 也會隨機中止（`GRT-0229`，usage=65534，同一份輸入 4 次 2 次；`librelane-run-debug` 已知陷阱）。這次 3 個 harden 都沒有發生 GRT-0229。兩者是不是同一個原因，沒有驗證。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| golden：數量與面積不給誤差、第 41 步以前的結果必須相同 | `signoff-checker-qualification` 規則 5：不可重現的只有多執行緒 detailed routing（PicoRV32 版 Phase 4：regress 第 2 次送進 detailed routing 的 ODB 與第 1 次逐 byte 相同，第 1、3、4 次 434 個 metric 與 golden 完全相同） | 第 41 步最後的 global routing 7 次裡 1 次不同，之後的 cell 數、diode 數都改變 | **依據不成立**（對 Hazard3 版）：detailed routing 以前也有不能重現的一步。要怎麼處理提給使用者（見「學習」） |
| `RUN_POST_GRT_RESIZER_TIMING`、`GRT_RESIZER_SETUP_SLACK_MARGIN` 0.025 ns | ADR-0014 | 修完 +0.041 ns（66 個違規 endpoint，全修完）→ signoff +0.556 ns；第 5 次 +0.002 → +0.530 | 依據仍成立（第 2 次觀察）：global routing 估計比 signoff 保守約 0.5 ns |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10 | hold 修完 +0.275 → signoff +0.109 ns（差 0.166）；第 41 步以前相同，所以 hold buffer 仍是 2,739 顆 | 依據仍成立 |
| uncertainty：半週期路徑的 DCD 預算 2.2 ns | `docs/notes/signoff_criteria_soc_top.md` | 最差 setup 仍是 `sram0` 下降緣送出 → `_21021_`，+0.556 ns（第 4、5 次 +0.552、+0.530） | 依據仍成立；44 ns 能 PASS 取決於這個假設（同第 5 次） |
| corner 清單、slew 上限、skew、unannotated 125 | 第 5 次的判斷 | 最差在 ss_n40C；slew 違規 0；skew metric ff −0.594／ss −1.262；unannotated 125 PASS | 與第 5 次相同 |

## 學習

已寫入（未 commit，等使用者決定）：
- `knowledge/sky130A_sky130_fd_sc_hd.md`：第 6 次的修完到 signoff 差距與半週期 slack。
- 經驗紀錄：`flow-regression-reproducibility`、`librelane-run-debug`、`signoff-checker-qualification`（第 41 步 global routing 偶發不一致）。

提給使用者決定：
1. **golden 怎麼面對這個不一致**：(a) 維持現行規則，再跑一次 harden，期待和 golden 相同（7 次裡 6 次相同）；(b) 先調查原因與發生條件再決定；(c) 改 golden 規則讓這類差異可以 PASS（要寫 ADR，`check_signoff.py` 目前拒絕數量與面積的誤差）。
2. 下游驗證（EQY、gate-level 模擬、negative test）都要等 harden PASS 才能跑。
