# criteria review：soc_top（PicoRV32，Phase 6 步驟 4d，乾淨 worktree 的 `make regress-picorv32`，2026-10-11）

- run：`../arvinsa-rtl-gds-p6final_pico/runs/soc_top`，commit `4713c5f`，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: PASS`，`regress: PASS 28/28`

## 有沒有被執行

- 第一部分 6 項全部 PASS：config 41 個設定生效、78 個 step config 一致、uncertainty 那一行出現在 8 個時序步驟與 15 個 signoff corner、30,000 條路徑套用的 uncertainty 正確（setup 0.250、半週期 2.450、hold 0.250 ns）、corner 齊全、5 個 checker 都有結果行。
- soc-checks 全部 PASS（macro、placement、ir_sources、port1_tieoff、disconnected、cts_macro_latency、sta_setup、pulse_width、macro_gds、sram_lib、sram_drc_ref、magic_drc）；ir_worst PASS。
- golden 比對：435 個 metrics 全部逐值相同。
- 可重現性：最終網表與 DEF 的 sha256 和 4b 的確認 harden（`runs/soc_top`，commit `940e395`）相同；golden 來源（`ad184f5`）的網表 sha256 也相同；GDS 清除 BGNLIB／BGNSTR 的日期後 sha256 相同。
- 沒有 FAIL 列；「不分析的項目清單」沒有新增。

## 合不合理

數字與 4b 的確認 harden 完全相同，逐列判斷見 `runs/p6_3m_pico_signoff/criteria_review.md`，結論不變：

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer setup／hold 餘量 | ADR-0014、skill「resizer 的 slack margin」 | setup：PostCTS、PostGRT 都沒有違規可修，signoff +0.769 ns；hold：PostGRT +0.068 → signoff +0.082 ns（變好） | 依據仍成立 |
| hold 餘量的代價 | skill「hold 餘量」 | hold buffer 3,589 個，PostCTS 面積 +16.5 % | 依據仍成立 |
| slew 上限與餘量 | Phase 3 長線 slew 問題 | `set_max_transition` 0.70、15 個 corner max slew／cap／fanout 0 | 依據仍成立 |
| corner 清單（溫度反轉） | knowledge S 系列 | 最差 setup 在 min_ss_n40C_1v60（+0.769 ns） | 依據仍成立 |
| uncertainty（DCD 2.2 ns） | `clock_uncertainty.sdc` | 最差路徑是半週期路徑 `sram0 -> _21857_`，扣 2.45 ns 後 slack +0.769 ns；DCD 仍是假設 | 依據仍成立（DCD 仍是假設） |
| skew | skill 規則 4 | hold skew 去掉 uncertainty 後 nom_ff -0.479、nom_ss -1.429 ns，與 4b 相同 | 依據仍成立 |
| unannotated 上限（推導） | `signoff/limits/soc_top.toml` 的組成註解 | 與上限相同（golden 逐值相同） | 依據仍成立 |
| 最壞組合 IR（≤ 20 mV） | ADR-0017 | ir_worst PASS，與 4b 相同 | 依據仍成立 |

## 學習

- 自產 SRAM 版本的 PicoRV32 harden 在不同 worktree 也逐位元重現（網表、DEF 相同，GDS 只差日期）。
- 沒有新數字要寫進 knowledge 檔；沒有依據不成立的 criterion，沒有提案。
