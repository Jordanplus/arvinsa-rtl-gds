# criteria review：soc_top_hazard3（Phase 6 結案 regress，乾淨 worktree 的 `make regress`，2026-10-11）

- run：`../arvinsa-rtl-gds-p6close_h3/runs/soc_top_hazard3`，commit `85bfa75`，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 整體結果：`harden-soc: PASS`，`regress: PASS 23/23`

## 有沒有被執行

- 第一部分全部 PASS（config_applied、step_config、uncertainty、uncertainty_applied、signoff_corners、checkers_ran）。
- signoff、soc-checks（macro、placement、ir_sources、port1_tieoff、disconnected、cts_macro_latency、sta_setup、pulse_width、macro_gds、sram_lib、sram_drc_ref、magic_drc）、soc-inputs（含修正後的 `resolved` 列）、ir-worst、provenance 都有結果行，全部 PASS。Hazard3 的 detailed routing log 有 1 次 `GRT-0243`（有 diode 的 net 修不了 antenna），與 4d 相同；最終 antenna 違規 0。
- golden 比對：441 個 metrics 全部逐值相同，0 個在誤差內、0 個不同。
- 可重現性：最終網表與 DEF 的 sha256 和 4d 的結案 run（`4713c5f`）相同；GDS 把 BGNLIB／BGNSTR 的日期清成零後 sha256 相同。`4713c5f` 到 `85bfa75` 只改 checker、文件與萃取試跑的腳本，沒有動 flow 設定。
- 沒有 FAIL 列；「不分析的項目清單」沒有新增。
- 前一次結案 regress（`904e18e`）在 soc-inputs 的 `resolved` 列 FAIL，是 checker 的 bug（變數重複使用），不是設計或 criteria 的問題；已修正並在 neg-pnr P00 加對照（見 `docs/phase_exit/phase6.md`）。

## 合不合理

數字與 4d 的結案 harden 完全相同，結論不變：

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer setup／hold 餘量 | ADR-0014、skill「resizer 的 slack margin」 | setup：最後一次修復（PostGRT）+0.031 → signoff +0.656 ns（變好）；hold：PostGRT +0.133 → signoff +0.126 ns，差距 0.007 < 0.05 ns | 依據仍成立 |
| hold 餘量的代價 | skill「hold 餘量」 | hold buffer 2,783 個，PostCTS 面積 +13.5 % | 依據仍成立 |
| slew 上限與餘量 | Phase 3 長線 slew 問題 | `set_max_transition` 0.70、15 個 corner max slew／cap／fanout 0 | 依據仍成立 |
| corner 清單（溫度反轉） | knowledge S 系列 | 最差 setup 在 min_ss_n40C_1v60（+0.656 ns），低溫比 100°C 差 | 依據仍成立 |
| uncertainty（DCD 2.2 ns） | `clock_uncertainty.sdc` | 最差路徑是半週期路徑 `sram0 -> _21042_`，扣 2.45 ns 後 slack +0.656 ns；DCD 仍是假設 | 依據仍成立（DCD 仍是假設） |
| skew | skill 規則 4 | hold skew 去掉 uncertainty 後 nom_ff -0.438、nom_ss -1.290 ns，與 4b、4d 相同 | 依據仍成立 |
| unannotated 上限（推導） | `signoff/limits/soc_top_hazard3.toml` 的組成註解 | 與上限相同（golden 逐值相同） | 依據仍成立 |
| 最壞組合 IR（≤ 20 mV） | ADR-0017 | ir_worst PASS，與 4b、4d 相同 | 依據仍成立 |

## 學習

- 自產 SRAM 版本的 soc_top_hazard3 harden 跨 `4713c5f` → `85bfa75` 仍逐位元重現（網表、DEF 相同，GDS 只差日期）。
- 沒有新數字要寫進 knowledge 檔；沒有依據不成立的 criterion，沒有提案。
