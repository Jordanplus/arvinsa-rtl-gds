# user_project_wrapper golden：Phase 7 Caravel wrapper 的 metrics

`make harden D=user_project_wrapper` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/user_project_wrapper.toml` 的 `[golden_tolerance]`（連續量）與 `[golden_layout_tolerance]`（會隨繞線變的數量與面積）列出的族群可以有誤差，`[golden_optional]` 列出的 key 可以只出現在一邊；違規數一律相同。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

**誤差還不是 wrapper 自己量的**：目前的誤差照抄 `soc_top_hazard3`（ADR-0015，`signoff/golden/soc_top_hazard3/README.md`「可重現性」）。使用者 2026-10-13 的選擇（ADR-0019 決定 22）：Phase 7 步驟 8 兩個乾淨 worktree 的 regress 跑完後，用它們對本檔的差異修正誤差。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden D=user_project_wrapper`（tag `user_project_wrapper`）的 `runs/user_project_wrapper_signoff/metrics.json`，原檔複製，沒有修改 |
| 日期／平台 | 2026-10-13（Phase 7 步驟 5g），Apple Silicon macOS（arm64） |
| 來源 run | Phase 7 第一次正式 harden，commit `f721cff`；log `runs/p7_harden_formal.log`。只有「沒有 golden 檔」一列 FAIL；signoff 上限、`check_soc.py` 13 項、`ir_worst.py`、`provenance.py`、`review_criteria.py` 全部 PASS。使用者 2026-10-13 事先選擇：「第一次正式 harden 直接建 (建議)」（ADR-0019 決定 22） |
| signoff criteria 檢查 | `runs/user_project_wrapper_signoff/criteria_review.md` |
| Caravel 的 IR（ADR-0019 決定 20） | 查證用（run guard 關掉）：max-power pattern 從 Caravel pad 算，最差 max_ss_100C win_5c 19.58 mV（上限 20）；正式的 `make ir-caravel` 在確認 harden 之後 |
| LibreLane／PDK／Hazard3／SRAM macro | 同 `env/versions.mk`；SRAM 是 `ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/` |
| flow 設定 | `pnr/user_project_wrapper/config.json` sha256 `271c6f7d6560dc374e932c16f4f190f672cdd7055600fe9c80890ac74020551e` |
| 本檔 sha256 | `b951552f3470b9942a0fdbb6cc0aba2ca4579588291dfb9e91b28bccb9bbc432` |

## 主要數字（與 `soc_top_hazard3` golden 比較；兩者是不同的設計，不逐項比對）

- metrics 455 個（soc_top_hazard3 441 個）。
- timing：最差 setup +0.548 ns（min_ss_n40C，半週期路徑 `u_soc.sram0` → `_20768_`；soc_top +0.656），最差 hold +0.187 ns（max_ff_100C；soc_top +0.126）。
- clock：hold skew metric nom_ss_n40C −3.598 ns（soc_top −1.540）；wb_clk_i 從 wrapper 邊緣經約 2 ns 的長線 buffer 到 block，兩個葉端 latency 差約 2 ns，成因沒有查（`criteria_review.md`）。
- cell：`design__instance__count__stdcell` 165,577，stdcell 面積 419,611 µm²，utilization 0.070（die 2920 × 3520 µm）；timing repair buffer 12,085，clock buffer 473，antenna diode 157；網表的 hold buffer 3,291（soc_top 2,783）。
- 繞線總長 837,043 µm；繞線 DRC 0。
- 功耗 18.20 mW（最後寫入的 corner max_ff_100C；soc_top 20.41）。
- IR：wrapper 內部（從 ring 上的 bridge 位置算）nom_tt 4.09 mV；`ir_worst.py` 判上限的 max_ss_100C 4.94 mV，ff 參考值 max_ff_100C 6.99 mV。
- max slew 違規 385 個／corner：全在 input port 驅動的 net（Caravel SDC 的外部 transition，ADR-0019 決定 16），內部 net 最差 0.576 ns（上限 0.75）。
- disconnected 327、unannotated 667（組成見上限檔）。
- Magic DRC 5,572,955 個，全部在 SRAM 框內、位置對得上 SRAM 單獨檢查；KLayout DRC 0、LVS 0、XOR 0、antenna 0。

## 可重現性

| run | 與本檔比較 |
|---|---|
| 正式 harden（commit `f721cff`） | 本檔來源 |
| `p7_exp_pl_dens`（`p7_harden5` 的設定 + density 50，從 global placement 重跑到 `STAPostPNR`；ADR-0019 決定 21） | 共有的 429 個逐值相同；本檔多 26 個是它沒跑的 IR、DRC、LVS、XOR 步驟 |

## 何時更新

與 `signoff/golden/soc_top_hazard3/README.md` 相同：升級工具或 PDK、修改 RTL、`config.json`、SDC、SRAM 產生檔、Caravel 固定段之後，golden 比對一定會 FAIL。更新步驟：確認 limits 與 `check_soc.py`、`review_criteria.py` 全部 PASS，逐項檢視差異，複製 metrics 並更新本表與 sha256，再跑一次確認 PASS。
