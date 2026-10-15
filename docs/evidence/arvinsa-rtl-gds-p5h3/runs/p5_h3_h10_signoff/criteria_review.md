# signoff criteria 檢查：Hazard3，ADR-0016 正式 harden（第 10 次 harden）

- run：`../arvinsa-rtl-gds-p5h3/runs/p5_h3_h10`（跑的時候 tag 是 `soc_top_hazard3`，之後改名）（commit `2caad0e`），2026-10-07；log `runs/p5_h3_harden10.log`，約 28 分鐘，沒有觸發重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `.claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: FAIL`（只剩 unannotated 上限與 golden 比對）

## 有沒有被執行

腳本 5 項都 PASS（41 個設定、78 個 step config、8 個時序 step 與 15 個 corner 的 uncertainty、corner 齊全、4 個 checker 都有結果行）。

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完 | — | setup／hold 15 個 corner 都 PASS（最差 +1.116／+0.106 ns）；DRC、LVS、slew、cap、antenna 都是 0 |
| `check_signoff.py` | FAIL | `timing__unannotated_net__count` 126 ≠ 125 | **criteria 問題**：126 = 82 個 CTS dummy load + 32 個 `sram0/dout1` + 12 個 tie cell 沒接的輸出（11 用 LO、1 用 HI），15 個 corner 都是 126；結構相同，dummy load 81 → 82 |
| 同上 | FAIL | golden：264 相同、97 在誤差內、72 不同 | 預期：CTS 改了，版圖與 timing 都變（例如 setup +0.530 → +1.116） |
| `check_soc.py` | PASS | — | 含 `cts_macro_latency` |
| `sram_drc_alone`、`check_inputs.py --resolved`、`provenance.py` | PASS | — | — |

「不分析的項目清單」：Phase 5 exit review 時逐條寫。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| uncertainty：半週期路徑 DCD 預算 2.2 ns | `docs/notes/signoff_criteria_soc_top.md` | 最差仍是 `sram0` 下降緣 → `_21031_`，+1.116 ns | 依據仍成立 |
| `RUN_POST_GRT_RESIZER_TIMING` | ADR-0014 | 修完 +0.074 → signoff 最差 +1.116（不同路徑） | 依據仍成立 |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10 | post-CTS +0.293 → signoff +0.106 ns | 依據仍成立；SRAM 輸入腳 hold 在接續實驗 D 是 +0.320 ns |
| `timing__unannotated_net__count` 125 | 第 5 次 harden 推導 | 126，組成相同 | 上限要改成 126 |
| golden 誤差（ADR-0015） | 第 5–8 次 harden | 72 個不同：設計改了，不是誤差的問題 | golden 要重建，可重現性要重新量 |

## 學習

- 寫進 knowledge 檔：ADR-0016 正式 harden 的數字、unannotated 126 的組成。
- hold buffer 2,721 顆，post-CTS stdcell 面積 +13.3%。
