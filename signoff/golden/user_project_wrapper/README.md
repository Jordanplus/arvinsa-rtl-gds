# user_project_wrapper golden：Phase 7 Caravel wrapper 的 metrics

`make harden D=user_project_wrapper` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/user_project_wrapper.toml` 的 `[golden_tolerance]`（連續量）與 `[golden_layout_tolerance]`（會隨繞線變的數量與面積）列出的那幾類 metric 可以有誤差，`[golden_optional]` 列出的 key 可以只出現在一邊；違規數一律相同。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

**誤差沿用 `soc_top_hazard3` 的值**（ADR-0015，`signoff/golden/soc_top_hazard3/README.md`「可重現性」），不改成要求每個值都完全相同。使用者 2026-10-14 選「維持 hazard3 的值，寫明理由 (建議)」（ADR-0019 決定 26），理由：
- wrapper 的比較（見「可重現性」）每個值都完全相同，量不出誤差該多大；
- 誤差要涵蓋的不可重現步驟（GRT 後的重新 global routing、多執行緒 detailed routing）是同一套 flow 的，wrapper 也有；第一輪結案 regress（`84fe505`）中 `picorv32_core` 從 Phase 5 起每個值一直都完全相同，第一次有 29 個 metrics 落在誤差內（detailed routing 繞線 +2 µm），所以「到目前每個值都完全相同」不代表以後不會差；
- 樣本全在同一台 Apple Silicon Mac，換機器要重新量（放寬清單 G05、G06）。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden D=user_project_wrapper`（tag `user_project_wrapper`）的 `metrics.json`，原檔複製，沒有修改。現在這版來自 `7eff65a` 的 harden（signoff 目錄另存 `runs/p7_decap_signoff/metrics.json`）；建立時那版來自 `f721cff`（`runs/p7_formal_signoff/`） |
| 更新（2026-10-14，Phase 7 步驟 7） | decap 改 `ef_decap_12`（ADR-0019 決定 24）後的 harden，commit `7eff65a`，log `runs/p7_harden_decap.log`，signoff 目錄另存 `runs/p7_decap_signoff`。只有 golden 6 列 FAIL；與前一版 golden 的差異 15 個 metrics，全部由 decap／fill 的改變解釋（`runs/p7_decap_signoff/criteria_review.md`）：fill 類 instance 2,608,464 → 974,801、leakage −0.011 mW（`ef_decap_12` 沒有 .lib，漏電不計）、IR 平均值與最差值的小變化；timing、DRC、LVS、XOR、antenna 每個值都完全相同 |
| 日期／平台 | 2026-10-13 建立（Phase 7 步驟 5g）、2026-10-14 更新（步驟 7），Apple Silicon macOS（arm64） |
| 建立時的來源 run | Phase 7 第一次正式 harden，commit `f721cff`；log `runs/p7_harden_formal.log`。只有「沒有 golden 檔」一列 FAIL；limits 檔的比對、`check_soc.py` 13 項、`ir_worst.py`、`provenance.py`、`review_criteria.py` 全部 PASS。使用者 2026-10-13 事先選擇：「第一次正式 harden 直接建 (建議)」（ADR-0019 決定 22） |
| signoff criteria 檢查 | `runs/p7_formal_signoff/criteria_review.md`（來源 run 的 signoff 目錄另存在這裡；`runs/user_project_wrapper_signoff` 之後會被新的 harden 覆蓋） |
| Caravel 的 IR（ADR-0019 決定 20） | 非正式的（run guard 關掉，不列入 signoff 證據）：max-power pattern 從 Caravel pad 算，最差 max_ss_100C win_5c 19.58 mV（上限 20）。正式的 `make ir-caravel` 在確認重跑（`f4ea9de`）上跑：同樣 19.58 mV，PASS（`runs/p7_formal_ir.log`）。decap 改版後（`550869c`）：19.56 mV，PASS（`runs/p7_formal2_ir.log`） |
| LibreLane／PDK／Hazard3／SRAM macro | 同 `env/versions.mk`；SRAM 是 `ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/` |
| flow 設定 | `pnr/user_project_wrapper/config.json` sha256 `1647a164727c72cd14d9038520f4bc5ee1c37269075b69473f2d9a3a7196d593`（2026-10-14 只改了 `//RUN_IRDROP_REPORT` 的註解，設定值與 `2604dc81…` 相同；建立時 `271c6f7d…`，差在 `DECAP_CELLS`、`FILL_CELLS`） |
| 本檔 sha256 | `6d75c98cadad25b1545e36e14b9a5b9439a67c7a7d781a7ffd832bf360292c34`（建立時 `b951552f…`） |

## 主要數字（與 `soc_top_hazard3` golden 比較；兩者是不同的設計，不逐項比對）

- metrics 455 個（soc_top_hazard3 441 個）。
- timing：最差 setup +0.548 ns（min_ss_n40C，半週期路徑 `u_soc.sram0` → `_20768_`；soc_top +0.656），最差 hold +0.187 ns（max_ff_100C；soc_top +0.126）。
- clock：hold skew metric nom_ss_n40C −3.598 ns（soc_top −1.540），最差的 corner 是 max_ss_n40C −3.649 ns；彙總的 `clock__skew__worst_hold` 是各 corner 取最大（最不負）的 −2.589 ns，不是最差值。這次只在現有的 run 上分析、沒有改設定做實驗（`runs/p7_skew_analysis/README.md`，2026-10-14）：其中約 2.7 ns 來自 `report_clock_skew -hold` 的計算方式，把 Caravel 的 clock source latency 上下限差（0.92 ns）與共同路徑的 derate（0.44 ns）算成扣分（**推測**，沒讀 OpenSTA 原始碼確認）；真正影響 hold 的 skew 是 −0.632 ns（soc_top −0.678 ns）。wrapper 多出來的是 `wb_clk_i` 從 wrapper 邊緣到 clock root 的長線，約 1.9 ns、6 顆 buffer（max_ss_n40C 5.57 → 7.67 ns）。
- cell：`design__instance__count__stdcell` 165,577，stdcell 面積 419,611 µm²，utilization 0.070（die 2920 × 3520 µm）；timing repair buffer 12,085，clock buffer 473，antenna diode 157；netlist 的 hold buffer 3,291（soc_top 2,783）。
- 繞線總長 837,043 µm；繞線 DRC 0。
- fill：543,617 個 `sky130_ef_sc_hd__decap_12` 與 fill_1／2／4／8 共 428,280 個（`design__instance__count__class:fill_cell` 974,801），row 兩端的 endcap 2,904 個 `decap_3`；li1 密度 39.9%（precheck `li1.pd.1d` 上限 60%，ADR-0019 決定 24）。建立時 Fill Insertion 放了 2,458,784 個 `decap_3`（加上 endcap，netlist 共 2,461,688 個；ADR-0019 決定 24 用後者），li1 75.1%。
- 功耗 18.19 mW（最後寫入的 corner max_ff_100C；soc_top 20.41）；leakage 0.740 mW 不含 `ef_decap_12`（沒有 .lib）。建立時 18.20 mW。
- IR：wrapper 內部（從 ring 上的 bridge 位置算）nom_tt 4.09 mV；`ir_worst.py` 拿來和上限比的 max_ss_100C 4.94 mV，ff 參考值 max_ff_100C 6.99 mV。
- max slew 違規 385 個／corner：全在 input port 驅動的 net（Caravel SDC 的外部 transition，ADR-0019 決定 16）。內部 net 最差 0.576 ns（上限 0.75）是 `p7_exp_pl_dens` 的量測（ADR-0019 決定 21，上限暫降到 0.50 ns 的 OpenSTA 實驗）；正式 run 的 timing metrics 與它每個值都完全相同，但沒有在正式 run 上重新量。
- disconnected 327、unannotated 667（組成見 limits 檔）。
- Magic DRC 5,572,955 個，全部在 SRAM 範圍內、位置對得上 SRAM 單獨檢查；KLayout DRC 0、LVS 0、XOR 0、antenna 0。

## 可重現性

| run | 與本檔比較 |
|---|---|
| 正式 harden（commit `f721cff`） | 建立時的來源（之後由 `7eff65a` 取代） |
| 確認重跑（commit `f4ea9de`，只改了 golden 與 EQY 腳本，flow 的輸入相同；`runs/p7_harden_confirm.log`，signoff 目錄另存 `runs/p7_confirm_signoff`） | 455 個全部完全相同，`harden-soc: PASS` |
| decap 改版後的確認重跑（commit `550869c`，`runs/p7_harden_decap_confirm.log`，signoff 目錄另存 `runs/p7_decap_confirm_signoff`） | 455 個全部完全相同，`harden-soc: PASS` |
| decap 改 `ef_decap_12` 的 harden（commit `7eff65a`） | 本檔現在的來源；與建立時的版本 440 個完全相同、10 個在誤差內、5 個不同，全部是 decap／fill 改變的結果 |
| 結案 regress 第一輪（commit `84fe505`，乾淨 worktree `p7close_caravel`，與另外兩條 regress 同時跑；審查後修了 checker，不當正式證據） | 455 個全部完全相同，`harden-soc: PASS` |
| 結案 regress 第二輪（commit `2b04451`，乾淨 worktree `p7close2_caravel`，與另外兩條 regress 同時跑，期間磁碟一度只剩 0.8 GiB；Phase 7 的正式證據） | 455 個全部完全相同，`harden-soc: PASS`（286.6 分鐘） |
| `p7_exp_pl_dens`（`p7_harden5` 的設定 + density 50，從 global placement 重跑到 `STAPostPNR`；ADR-0019 決定 21） | 對建立時的版本：共有的 429 個完全相同（本檔多 26 個是它沒跑的 IR、DRC、LVS、XOR 步驟）。對現在的版本（`ef_decap_12`）：425 個相同，4 個不同（fill 與 instance 數、leakage、power），都是 decap 改變的結果 |

## 何時更新

與 `signoff/golden/soc_top_hazard3/README.md` 相同：升級工具或 PDK、修改 RTL、`config.json`、SDC、SRAM 由腳本產生的檔案、Caravel 固定段之後，golden 比對一定會 FAIL。更新步驟：確認 limits 與 `check_soc.py`、`review_criteria.py` 全部 PASS，逐項檢視差異，複製 metrics 並更新本表與 sha256，再跑一次確認 PASS。
