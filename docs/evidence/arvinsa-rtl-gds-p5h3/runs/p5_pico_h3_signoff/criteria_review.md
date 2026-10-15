# signoff criteria 檢查：PicoRV32，ADR-0016 正式 harden（第 2 次重跑）

- run：`../arvinsa-rtl-gds-p5h3/runs/p5_pico_h3`（跑的時候 tag 是 `soc_top`，之後改名）（commit `2caad0e`：自訂 CTS step `Arvinsa.CTSNoInsertionDelay`，GRT-0229 重試含 `ResizerTimingPostGRT`），2026-10-07；log `runs/p5_pico_harden3.log`，約 24 分鐘，沒有觸發重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `.claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: FAIL`（只剩 unannotated 上限與 golden 比對）

## 有沒有被執行

腳本 5 項都 PASS（40 個設定、78 個 step config、8 個時序 step 與 15 個 corner 的 uncertainty（CTS 是 `35-arvinsa-ctsnoinsertiondelay`）、corner 齊全、4 個 checker 都有結果行）。

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完 | — | setup／hold 15 個 corner 都 PASS（最差 +0.765／+0.079 ns）；DRC、LVS、slew、cap、antenna 都是 0 |
| `check_signoff.py` | FAIL | `timing__unannotated_net__count` 118 ≠ 133 | **criteria 問題**：118 = 75 個 CTS dummy load（`clkload*`）+ 32 個 `sram0/dout1` + 11 個 tie cell 沒接的輸出（10 個 `conb_1` 用 LO、1 個用 HI），15 個 corner 都是 118；結構與 133 相同，CTS 改了，dummy load 從 90 變 75 |
| 同上 | FAIL | golden：261 相同、31 在誤差內、144 不同 | 預期：golden 是 Phase 4 的 43 ns 舊設定 |
| `check_soc.py` | PASS | — | 含新的 `cts_macro_latency`（0 顆 `delaybuf_*`） |
| `sram_drc_alone`、`check_inputs.py --resolved`、`provenance.py` | PASS | — | — |

「不分析的項目清單」：Phase 5 exit review 時逐條寫。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| uncertainty：半週期路徑 DCD 預算 2.2 ns | `docs/notes/signoff_criteria_soc_top.md` | 最差仍是 `sram0` 下降緣 → `_21875_`，+0.765 ns（第 1 次 −0.113） | 依據仍成立；ADR-0016 拿回 0.88 ns |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10 後果一 | post-CTS +0.300 → GRT 後 +0.069 → signoff +0.079 ns | hold PASS；SRAM 輸入腳的 hold 在接續實驗 D 是 +0.093 ns（這次的 setup／hold 與實驗 D 相同，SRAM 輸入腳沒有另外量） |
| `RUN_POST_GRT_RESIZER_TIMING` | ADR-0014 | 這次沒有 setup 違規要修，只修 hold | 依據仍成立 |
| `timing__unannotated_net__count` 133 | Phase 4 版圖 | 118，組成相同 | 上限要改成 118（criteria 問題） |
| corner、slew、skew | Phase 4 | slew／cap／fanout 0 | 依據仍成立 |

## 學習

- 寫進 knowledge 檔：ADR-0016 正式 harden 的數字（與接續實驗 D 相同）、unannotated 118 的組成。
- hold buffer 3,563 顆，post-CTS stdcell 面積 +16.6%（與第 1 次相同量級）。
