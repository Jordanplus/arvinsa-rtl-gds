# criteria review：soc_top（Phase 6 確認 harden，2026-10-10）

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS（config_applied、step_config、uncertainty、uncertainty_applied、signoff_corners、checkers_ran）。最後一行：`criteria-review: PASS`。

這是 golden、SRAM DRC 參考檔與 unannotated 上限重建後（commit `940e395`）的確認 harden。`harden-soc: PASS`：signoff PASS、soc-checks PASS（含 `sram_drc_ref` 對新參考檔、`magic_drc`、`macro_gds`、`port1_tieoff`、`sta_setup`）、ir_worst PASS。

golden 比對：435 個 metrics 全部逐值相同（0 個落在容許誤差內、0 個只在一邊）。同一份輸入（第三輪 `ad184f5` 與這次只差 signoff 的檔案）兩次 harden 結果完全相同，沒有 flow 不可重現的問題。

沒有 FAIL 列；「不分析的項目清單」這次沒有新增。

## 合不合理

數字與第三輪完全相同，逐列判斷見 `runs/p6_3m_pico_signoff/criteria_review.md`，結論不變：

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer setup／hold 餘量 | ADR-0014、skill「resizer 的 slack margin」 | 與第三輪相同（見上） | 依據仍成立 |
| hold 餘量的代價 | skill「hold 餘量」 | 與第三輪相同 | 依據仍成立 |
| slew 上限與餘量 | Phase 3 長線 slew 問題 | 15 個 corner max slew／cap／fanout 0 | 依據仍成立 |
| corner 清單（溫度反轉） | knowledge S 系列 | 最差 setup 仍在 min_ss_n40C_1v60 | 依據仍成立 |
| uncertainty（DCD 2.2 ns） | `clock_uncertainty.sdc` | 最差半週期路徑 slack 與第三輪相同；DCD 仍是假設 | 依據仍成立（DCD 仍是假設） |
| skew | skill 規則 4 | 與第三輪相同 | 依據仍成立 |
| unannotated 上限（推導） | `signoff/limits/soc_top.toml` 的組成註解 | 與上限相同（15 個 corner） | 依據仍成立 |
| 最壞組合 IR（≤ 20 mV） | ADR-0017 | 與第三輪相同 | 依據仍成立 |

## 學習

- 自產 SRAM 版本的 harden 可完全重現（兩次 435 個 metrics 逐值相同），golden 不需要容許誤差就能比對。
- 沒有新數字要寫進 knowledge 檔；沒有依據不成立的 criterion，沒有提案。
