# criteria review：user_project_wrapper（Phase 7 第一次正式 harden，2026-10-13）

run：`runs/user_project_wrapper`，commit `f721cff`（ADR-0019 決定 21：`PL_TARGET_DENSITY_PCT` 50；wrapper 上限檔第一版），log `runs/p7_harden_formal.log`，LibreLane 10:46–14:41（3 小時 55 分），全部 249 分鐘。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS（config_applied 55 個設定、step_config 78 個步驟、uncertainty、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran）。最後一行：`criteria-review: PASS`。

`harden-soc: FAIL`，原因只有一列：

| checker | FAIL 列 | 設計問題還是 criteria 問題 |
|---|---|---|
| `check_signoff.py` | `golden file: run=<missing>`（`signoff/golden/user_project_wrapper/metrics.json`） | 都不是：wrapper 還沒有 golden。使用者 2026-10-13 選「第一次正式 harden 直接建 (建議)」：只有這一列 FAIL、本檢查合理時，用這次的 metrics 建 golden |

其他 checker：

- `check_signoff.py`：其餘全部 PASS。上限檔是 wrapper 第一版（`f721cff`），兩個依設計結構推導的數字都等於推導值：`design__disconnected_pin__count` 327（321 個訊號 port + 6 個電源 port）、`timing__unannotated_net__count` 667（在 `p7_exp_pl_dens` 推導）。KLayout DRC、LVS、XOR、antenna、max cap／fanout、繞線 DRC 都是 0。內部 IR（`ir_vdd_drop_plus_gnd_rise`）4.09 mV；`ir_caravel_vdd_drop_plus_gnd_rise` 是 INFO 列，由 `make ir-caravel` 判（P81）。
- `check_soc.py` 13 項全部 PASS：max slew 15 個 corner 共 5,775 個違規，全在 input port 驅動的 net 上（Caravel SDC 給的外部 transition，最多比它大 0.001 ns）；Magic DRC 5,572,955 個全部在 SRAM 框內、位置都對得上 SRAM 單獨檢查。
- `ir_worst.py` PASS：從 wrapper 的 ring 算，判上限的 slow corner max_ss_100C 4.94 mV（上限 20）；ff 電流 + port 1 浮接電流 + ss 金屬電阻的參考值 max_ff_100C 6.99 mV。
- `provenance.py --verify` PASS：開始與結束都是 `f721cff`，LibreLane 3.0.14、PDK `8afc8346`。

可重現性（不是 golden 比對，是建 golden 前的確認）：這次與 `p7_exp_pl_dens`（同樣的設定，只是當時 density 50 還沒 commit）共有的 429 個 metrics 逐值相同。這次多出的 26 個是 `p7_exp_pl_dens` 沒有跑的 IR、DRC、LVS、XOR 步驟。

「不分析的項目清單」：這次沒有新增。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| setup 餘量（`GRT_RESIZER_SETUP_SLACK_MARGIN` 0.025 ns） | ADR-0014；本 skill「resizer 的 slack margin」 | `ResizerTimingPostGRT` 修完 +0.047 → signoff +0.548 ns（min_ss_n40C）：global routing 估計仍比 signoff 保守 0.50 ns，與 soc_top Hazard3 的 0.5 ns 相同 | 依據仍成立 |
| hold 餘量（`PL_RESIZER_HOLD_SLACK_MARGIN` 0.3、`GRT_RESIZER_HOLD_SLACK_MARGIN` 0.2 ns） | ADR-0014；本 skill「hold 餘量」 | post-CTS +0.292 → post-GRT +0.207 → signoff +0.187 ns（max_ff_100C）；最後一次修復到 signoff 只差 0.020 ns | 依據仍成立 |
| hold 餘量的代價 | `drv-timing-closure` 規則 7 | hold buffer 3,291 顆（soc_top Hazard3 2,783，+18%）；post-CTS stdcell 面積 +8.6%。多出的部分與下面的 skew 一起看 | 依據仍成立（代價比 soc_top 高，原因見 skew 列） |
| slew 上限（PnR `set_max_transition` 0.70、`DESIGN_REPAIR_MAX_SLEW_PCT` 30、`GRT_DESIGN_REPAIR_MAX_SLEW_PCT` 40；signoff 0.75 ns） | Phase 3 長線 slew；ADR-0019 決定 21 | 內部 net 最差 0.576 ns（max_ss_n40C，比 0.75 少 0.17 ns；在 `p7_exp_pl_dens` 用降低上限的方法量，這次與它逐值相同）；違規只剩 input port 的外部 transition。最差 setup 路徑上沒有 repair buffer | 依據仍成立 |
| corner 清單（溫度反轉） | knowledge「溫度反轉」 | 最差 setup 在 min_ss_n40C_1v60（ss −40°C 三個 +0.548／+0.639／+0.741，ss 100°C 最差 +1.118 ns）；最差 hold 在 max_ff_100C_1v95 | 依據仍成立 |
| uncertainty（setup 0.25、hold 0.25、DCD 2.2 ns） | `clock_uncertainty.sdc` | 最差路徑就是半週期路徑 `u_soc.sram0` → `_20768_`，扣 2.45 ns 後 +0.548 ns（soc_top Hazard3 +0.656）。送出端 clock 6.01 ns（soc_top 4.25）。DCD 仍是假設（Caravel 的 clock 來源 duty cycle 沒有查證） | 依據仍成立（DCD 仍是假設） |
| skew（規則 4：metric 換算成名目值） | 本 skill 規則 4 | hold skew metric nom_ss_n40C −3.598 ns，扣掉 hold uncertainty −3.348 ns（仍含 5% derate）；soc_top Hazard3 −1.540／−1.290 ns。報表：source latency `_21607_/CLK` 9.389、target `_20913_/CLK` 11.379 ns，CRPR 1.358。wb_clk_i 進來時已是 5.57 ns（Caravel SDC 的外部 latency，兩端相同），pin 到 block 約 2 ns 的長線 buffer（`wire8111`–`wire8116`）是兩端共用。target 端經過 12 級 clock buffer 與一顆繞線後插入的 `wire8118`。p7_harden5 是 −3.590，所以這是 wrapper 的穩定特性，不是這次 run 的偶發 | 資料不足：兩個葉端的 latency 差約 2 ns 的成因（tree 不平衡的位置）沒有查，launch 端路徑要另開 STA，超過限時。hold 與 setup 都過，代價是 hold buffer 多 18%。列入步驟 8 待查 |
| 上限檔依設計結構推導的數字 | `signoff/limits/user_project_wrapper.toml` | disconnected 327、unannotated 667 都是為 wrapper 推導（不是抄 soc_top 的 152），這次逐值相同；unannotated 的 CTS 假負載數隨 placement 變，density 50 的 run 已重推 | 依據仍成立 |
| golden 容許誤差 | `[golden_tolerance]` 借用 soc_top_hazard3（ADR-0015） | 還沒在 wrapper 量過；本次與 `p7_exp_pl_dens` 429 個 metrics 逐值相同，至少這一次可重現 | 資料不足：照使用者 2026-10-13 的選擇，步驟 8 兩個乾淨 worktree 跑完後修正 |
| power signoff 的切換活動 | ADR-0019 決定 20（CPU 最大功耗 pattern，44 ns，slow corner，上限 20 mV） | 這次最終網表錄的 max-power pattern（`fw/tests/maxpower` 三段 5a／5b／5c，44 ns，73,872 個 pin 全部標註），從 Caravel 的 pad 算（查證用，run guard 關掉；正式的 `make ir-caravel` 在確認 harden 之後）：最差 max_ss_100C win_5c 19.58 mV（VDD 11.93 + GND 7.65），餘量 0.42 mV；`p7_harden5` 是 19.71 mV。vectorless 45.57 mV（`p7_harden5` 45.87），pattern ÷ vectorless 0.43，與上次相同 | 依據仍成立；餘量只有 2%，placement 或 cell 分布改變就可能超過，之後每次 harden 都要看這一列 |

## 學習

- knowledge 檔追加：wrapper 的 setup／hold 修復到 signoff 的差距、hold buffer 數、clock latency 與 skew、pattern IR（見 `.claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` 2026-10-13 的列）。
- density 55 → 50 的 run 可重現：實驗 run 與正式 run 共有的 429 個 metrics 相同，所以實驗 run 的 slew 餘量量測可以直接當正式 run 的數字用。
- 沒有新的工具行為。沒有依據不成立的 criterion，沒有提案；skew 成因列為步驟 8 待查。
