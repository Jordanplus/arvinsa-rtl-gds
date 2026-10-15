# criteria review：soc_top_hazard3（Phase 6 步驟 4d，乾淨 worktree 的 `make regress`，2026-10-11）

- run：`../arvinsa-rtl-gds-p6final_h3/runs/soc_top_hazard3`，commit `4713c5f`，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: PASS`，`regress: PASS 23/23`

## 有沒有被執行

- 第一部分 6 項全部 PASS：config 42 個設定生效、78 個 step config 一致、uncertainty 那一行出現在 8 個時序步驟與 15 個 signoff corner、50,670 條路徑套用的 uncertainty 正確（setup 0.250、半週期 2.450、hold 0.250 ns）、corner 齊全、5 個 checker 都有結果行。
- soc-checks 全部 PASS（macro、placement、ir_sources、port1_tieoff、disconnected、cts_macro_latency、sta_setup、pulse_width、macro_gds、sram_lib、sram_drc_ref、magic_drc）；ir_worst PASS。
- golden 比對：441 個 metrics 全部逐值相同。4c 的 commit 只改 EQY 與 neg-pnr 腳本，沒有動 flow 設定，所以這是同一份輸入在另一個 worktree 重跑。
- 可重現性：最終網表與 DEF 的 sha256 和 4b 的確認 harden（`runs/soc_top_hazard3`，commit `940e395`）相同；golden 來源（`ad184f5`）的網表 sha256 也相同；GDS 的 sha256 不同，但把 BGNLIB／BGNSTR 記錄（只存日期）清成零後 sha256 相同，差異只在寫檔時間。
- 沒有 FAIL 列；「不分析的項目清單」沒有新增。

## 合不合理

數字與 4b 的確認 harden 完全相同，逐列判斷見 `runs/p6_3m_h3_signoff/criteria_review.md`，結論不變：

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer setup／hold 餘量 | ADR-0014、skill「resizer 的 slack margin」 | setup：最後一次修復（PostGRT）+0.031 → signoff +0.656 ns（變好）；hold：PostGRT +0.133 → signoff +0.126 ns，差距 0.007 < 0.05 ns | 依據仍成立 |
| hold 餘量的代價 | skill「hold 餘量」 | hold buffer 2,783 個，PostCTS 面積 +13.5 % | 依據仍成立 |
| slew 上限與餘量 | Phase 3 長線 slew 問題 | `set_max_transition` 0.70、15 個 corner max slew／cap／fanout 0 | 依據仍成立 |
| corner 清單（溫度反轉） | knowledge S 系列 | 最差 setup 在 min_ss_n40C_1v60（+0.656 ns），低溫比 100°C 差 | 依據仍成立 |
| uncertainty（DCD 2.2 ns） | `clock_uncertainty.sdc` | 最差路徑是半週期路徑 `sram0 -> _21042_`，扣 2.45 ns 後 slack +0.656 ns；DCD 仍是假設 | 依據仍成立（DCD 仍是假設） |
| skew | skill 規則 4 | hold skew 去掉 uncertainty 後 nom_ff -0.438、nom_ss -1.290 ns，與 4b 相同 | 依據仍成立 |
| unannotated 上限（推導） | `signoff/limits/soc_top_hazard3.toml` 的組成註解 | 與上限相同（golden 逐值相同） | 依據仍成立 |
| 最壞組合 IR（≤ 20 mV） | ADR-0017 | ir_worst PASS，與 4b 相同 | 依據仍成立 |

## 學習

- 自產 SRAM 版本的 Hazard3 harden 在不同 worktree 也逐位元重現（網表、DEF 相同，GDS 只差日期）。
- 沒有新數字要寫進 knowledge 檔；沒有依據不成立的 criterion，沒有提案。
