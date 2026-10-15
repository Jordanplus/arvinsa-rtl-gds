# Phase 7 exit review：Hazard3 SoC 放進 Caravel，ChipFoundry precheck PASS

日期：2026-10-15　結論：**PASS**（只做到 precheck，不下線；下線前要處理的事項見「已知限制」1–6）

**一段話摘要**：
- Hazard3 SoC 與自產 SRAM 用扁平放法放進 ChipFoundry Caravel 的使用者區 `user_project_wrapper`：CPU 與周邊的 standard cell、SRAM macro 直接在 wrapper 層擺放與繞線，不先 harden 成 macro（ADR-0019 決定 2）。
- 只做到 precheck（ChipFoundry 收件前的自動檢查）PASS，不下線（決定 1）。官方 image 的 13 項中 11 項 PASS；`klayout_feol`／`klayout_beol` 只剩 OpenRAM bitcell 的兩條規則，而且每個違規位置都和 PDK 預建 SRAM 單獨檢查時相同（決定 5）。
- wrapper 完成和 soc_top 同一套 signoff：15 個 corner 的 STA、DRC、LVS、antenna、EQY、gate-level 模擬，IR 改成從 Caravel 的 pad 起算、用 CPU 最耗電的測試程式（max power pattern）的實際切換活動判 20 mV（決定 18–20）。
- 流程上新增「先規劃 pad、block 位置與 pin，經使用者核准才寫 RTL 與 harden」，用 checker、hook、skill、流程文件四層強制（決定 13，CLAUDE.md 規則 14）。

ADR：`docs/decisions/0019-phase7-caravel-precheck.md`（決定 1–26）；流程回顧 ADR-0020。查證筆記：`docs/notes/caravel_precheck_phase7.md`。

Exit criteria 出處：`project-plan.md` §8 Phase 7。
- exit 條件原文：「ChipFoundry 收件前的自動檢查（precheck）PASS。**ADR-0019 決定 5**：官方 image 的 13 項中 11 項 PASS；`klayout_feol`／`klayout_beol` 只允許 OpenRAM bitcell 的 `MR_licon.SP.6`、`MR_mcon.CON.10`，而且與 PDK 預建 macro 一致」。
- 內容欄：「把 SoC 放進 ChipFoundry Caravel 的使用者區……採扁平放法……2026-10-12 更新（ADR-0019）：CPU 改用 Hazard3（自產 SRAM），只做到 precheck、不下線」。

一併帶進本階段的項目：Phase 6 已知限制 1–9（`docs/phase_exit/phase6.md`），其中第 9 項展開成 Phase 5 已知限制 1、3–8、11 與 Phase 3.5 已知限制 5–7、13、14；另外逐條補上 Phase 5 已知限制 12 的子項（Phase 6 只寫「其他沒變」）。處理結果見「帶進本階段的項目」。

## 正式 run

正式證據是**第二輪**：獨立審查（見「獨立審查」）後修了 checker，在 `2b04451` 的三個新的乾淨 worktree 重跑（ADR-0019 決定 25、26，使用者 2026-10-14「三條分開、平行跑 (建議)」、「全部修正，三條 regress 重跑 (建議)」）：
- 建立方式：`git worktree add --detach` 加 `git submodule update --init --recursive`，開始時沒有修改或未追蹤的檔案。
- `.tools/` 不在 git 裡，用 `LIBRELANE_DIR`、`XPACK_DIR`、`PRECHECK_DECK` 指向主 checkout 已安裝的版本，`env-check-flow` 會檢查。precheck 用主機上同一個 lima VM，每個 worktree 用自己的 precheck 目錄（`PRECHECK_DIR`）。
- 三條同時開跑，本機記憶體 24 GB。

| regression | commit | 時間 | exit code | 結果 | 證據 |
|---|---|---|---|---|---|
| `make regress-caravel`（wrapper，18 項） | `2b04451` | 2026-10-14 約 23:54 – 10-15 07:50，476 分鐘 | 0 | **18/18 PASS** | worktree `p7close2_caravel` 的 `runs/regress_caravel/summary.md`、`junit.xml`；console `runs/p7close2_regress_caravel.console` |
| `make regress-picorv32`（31 項） | `2b04451` | 2026-10-15 約 05:01–09:09，248 分鐘（重跑，見下） | 0 | **31/31 PASS** | worktree `p7close2_pico` 的 `runs/regress_picorv32/summary.md`；console `runs/p7close2_regress_picorv32.console` |
| `make regress`（Hazard3 soc_top，30 項） | `2b04451` | 2026-10-15 約 07:51–11:21，211 分鐘（第三次執行，見下） | 0 | **30/30 PASS** | worktree `p7close2_h3` 的 `runs/regress/summary.md`；console `runs/p7close2_regress_hazard3.console` |

第二輪有兩條重跑，都是本機資源問題，不是設計或 checker 的問題（`flow-regression-reproducibility`、`tapeout-precheck-caravel` 經驗紀錄 2026-10-15）：
- **磁碟滿**（約 03:33）：三條同時跑加上舊 worktree 的 negative test 中間產物，磁碟只剩 0.8 GiB。PicoRV32 在第 30 項 `neg-eqy-core` 寫檔失敗 FAIL（`OSError: [Errno 28] No space left on device`，console `runs/p7close2_regress_picorv32.enospc.console`）；Hazard3 的 `neg-pnr` 在 P32 的 STA 停住、CPU 0%、沒有報錯也沒有逾時，05:00 手動停掉（`runs/p7close2_regress_hazard3.enospc.console`）。wrapper 同時在跑，它的 `flow.log`、`warning.log` 沒有 `No space left`，455 個 metrics 與 golden 逐值相同，判斷沒受影響。清掉舊 worktree 的 negative test 中間產物（只留 ≤ 1 MB 的 log 與報表，`runs/cleanup_2026-10-15.txt`）後剩 630 GiB。
- **KLayout Signal 11**（05:25，Hazard3 第二次執行）：`neg-precheck` 的比對基準步驟 KLayout 0.30.7 當掉（`runs/p7close2_h3_neg_precheck_ref_klayout_sig11.log`），當時三條同時跑、swap 7.6／9.2 GB。第三次執行時只剩這一條在跑，同一項 31/31 PASS。記憶體壓力是推測的原因，沒有做實驗確認。
- 重跑都從頭開始（`make regress` 不接續），乾淨 worktree 與 commit 不變。

第一輪（`84fe505`，2026-10-14，三條都 PASS：Hazard3 30/30、wrapper 18/18、PicoRV32 31/31）不當結案證據：審查後改了 checker 與 negative test，第一輪跑的是修正前的版本。它的結果仍拿來比對可重現性（見「可重現性」），criteria review 在 `p7close_{h3,caravel,pico}/runs/*_signoff/`。

- **重試**：第二輪 4 次 harden 都沒有重試（沒有 `retries.txt`）。
- **golden 比對**：wrapper 455 個、Hazard3 soc_top 441 個、PicoRV32 soc_top 435 個、picorv32_core 325 個，全部逐值相同。
- **每次 harden 的 criteria review**（CLAUDE.md 規則 9）：
  - `p7close2_h3/runs/soc_top_hazard3_signoff/criteria_review.md`（第三次執行後重寫）；
  - `p7close2_caravel/runs/user_project_wrapper_signoff/criteria_review.md`；
  - `p7close2_pico/runs/soc_top_signoff/criteria_review.md`；
  - `p7close2_pico/runs/picorv32_core_signoff/criteria_review.md`（含三次結案 run 的比較）。

之前在主 checkout 的正式結果（`550869c`，run guard 開著，ADR-0019 決定 24）：確認 harden PASS（golden 455 個逐值相同）、`eqy-caravel` 16149/16149、`gl-caravel` 16/16、`ir-caravel` 19.56 mV、`precheck-caravel` PASS。結案證據以上表的乾淨 worktree 為準；`550869c` 的結果與它比對見「可重現性」。

## Exit criteria

| # | 項目 | 結果 | 證據 |
|---|---|---|---|
| 1 | precheck：官方 image 13 項中 11 項 PASS | **PASS**：第二輪 `precheck-caravel`（98.6 分鐘，cf-precheck 1.3.7）11 項 pass、`magic_drc` skip；GDS sha1 `06b0ddc4…` 與 run 的 GDS 相同，來源 run 過 run guard | `make precheck-caravel`（`signoff/precheck/check_precheck.py`）；`neg-precheck` 31/31 |
| 2 | `klayout_feol`／`klayout_beol` 只有 `MR_licon.SP.6`、`MR_mcon.CON.10`，與 PDK 預建 macro 一致 | **PASS**：FEOL 3 項 16,900 個、BEOL 264 項 50,184 個位置，全部在 SRAM 框內、預建 SRAM 單獨檢查也有（與 `550869c` 相同） | 同上；比對方法見決定 5 的實作 |
| 3 | CPU 用 Hazard3、自產 SRAM，扁平放法 | PASS：`u_soc` 的 standard cell 與 `u_soc.sram0` 直接在 wrapper 層；RTL 模擬 32/32、植入錯誤 42/42（Caravel build） | `rtl/caravel/`；`regress-rtl-caravel`、`neg-rtl-caravel` |
| 4 | pad、block 位置、pin 先規劃並經使用者核准（決定 13） | PASS：`pnr/user_project_wrapper/pin_plan.toml` 使用者 2026-10-12 核准（「可以」）；`make pin-plan` PASS、`neg-pin-plan` 26/26 | `scripts/check_pin_plan.py`；`.claude/hooks/require_pin_plan.py` |
| 5 | wrapper 的 signoff（和 soc_top 同一套） | **PASS**：`harden-caravel` PASS（golden 455 個逐值相同）、`eqy-caravel` 16149/16149、`gl-caravel` 16/16、`ir-caravel` 19.56 mV（上限 20 mV） | 「signoff 結果」 |
| 6 | 帶進本階段的項目 | 見「帶進本階段的項目」 | — |

## signoff 結果（44 ns）

| 項目 | wrapper（`user_project_wrapper`） | Hazard3 soc_top（對照） |
|---|---|---|
| setup 最差 | +0.548 ns（min_ss_n40C_1v60；SRAM 半週期路徑 `u_soc.sram0` → `_20768_`） | +0.656 ns（min_ss_n40C_1v60） |
| hold 最差 | +0.187 ns（max_ff_100C_1v95） | +0.126 ns（min_ff_n40C_1v95） |
| hold skew metric（nom_ss_n40C） | −3.598 ns（含報表算法的悲觀量，見已知限制） | −1.540 ns |
| die | 2920 × 3520 µm（Caravel 固定） | 800,000 µm² |
| standard cell | 165,577 顆、419,611 µm²（使用率 7.0%） | 30,406 顆、240,768 µm² |
| flip-flop | 2,238 | 2,152 |
| hold buffer（網表） | 3,291 | 2,783 |
| `power__total`（最後寫入的 corner max_ff_100C） | 18.19 mW（leakage 0.740 mW 不含 `ef_decap_12`） | 20.41 mW |
| 繞線長度 | 837,043 µm | 813,737 µm |
| IR：harden 內 `ir_worst.py`（預設切換率、慢 corner、供電點在 wrapper ring） | 4.94 mV（max_ss_100C） | 12.48 mV（max_ss_100C） |
| IR：max power pattern（決定 20、25；上限 20 mV） | 19.56 mV（從 Caravel pad 起算，與 `550869c`、第一輪相同） | 4.67 mV（max_ss_100C win_5c，`make ir-soc`，第二輪同值） |
| fill | `ef_decap_12` 543,617 個、fill 428,280 個；li1 密度 39.9% | `decap_3` |
| DRC（繞線、KLayout）／LVS／XOR／antenna | 全部 0 | 全部 0 |
| Magic DRC | 5,572,955，全部在 SRAM 框內、對得上 SRAM 單獨檢查的位置 | 4,770,846，同左 |
| max slew 違規 | 每個 corner 385 個，全在 Caravel 直接驅動的邊界 net（決定 16）；內部 net 最差 0.576 ns | 0 |
| EQY／gate-level 模擬 | PASS（16149/16149 個分區，2,238 個 flip-flop 種類相同）／16 | PASS／16 + 16（含電源接腳版） |

數字的出處與讀法：
- 出處：兩次 harden 的 `final/metrics.json`（與 `signoff/golden/{user_project_wrapper,soc_top_hazard3}/metrics.json` 逐值相同）、`criteria_review.txt`、`soc_checks.txt`、`ir_worst.txt`；pattern IR 是 `make ir-caravel`／`make ir-soc` 的 `results.json`。
- `power__total` 是 LibreLane 最後寫入的 corner，不是最大值（`librelane-run-debug` 規則 4）。
- wrapper 的 setup 比 soc_top 少 0.108 ns：差距在 clock 端，`wb_clk_i` 從 wrapper 邊緣到 clock root 約 1.9 ns（6 顆 buffer，`runs/p7_skew_analysis/README.md`）。
- wrapper 的 pattern IR 比 soc_top 大很多，是因為從 Caravel 的 pad 起算：電流經 Caravel 自己的 met4 ring 與跨接線才到 wrapper（決定 18），wrapper 內部只占 2–5 mV。

## 收斂過程

依時間順序（每一步的決定在 ADR-0019）：
1. **查證與環境**（步驟 1–2）：`cf precheck` 一定用 Docker 跑官方 image，image 只有 amd64；本機用 lima VM（vz＋Rosetta）跑，官方範例 19 分鐘 11 項 PASS（決定 3、4）。precheck 新版 deck 拿掉了 SRAM 核心區的豁免，PDK 預建 SRAM 也報 `MR_licon.SP.6`、`MR_mcon.CON.10`，訂出決定 5 的判法。
2. **wrapper RTL**（步驟 3）：Wishbone slave 驅動 host write port，`host_en` reset 值 1（決定 9）；clock／reset 接 `wb_clk_i`／`wb_rst_i`（決定 8）。
3. **規劃與 floorplan**（步驟 4）：第一次選 GPIO 8–20 沒先看 pad 位置，使用者指出流程順序錯了；改成先定 block 位置（左下角，決定 12）再選 GPIO 33–37（決定 10），並用四層機制強制（決定 13）。邊界時序用官方 Caravel 的數值、不用 multicycle（決定 14）；clock 的 jitter 與 duty 維持假設、記成下線風險（決定 15）。
4. **harden 探索**（步驟 5a–5c）：
   - `RSZ-0074`：resizer 把 inout 的 `analog_io` 同時算成 driver 與 load，加 `RSZ_DONT_TOUCH_RX` 與 checker `inout_dont_touch`（P79）。
   - Caravel 輸入的 transition 0.84–0.97 ns 超過 slew 上限，內部照舊、邊界另判（決定 16）。
   - Caravel 輸入路徑 hold −0.071 ns：GRT 後的 hold 餘量 0.05 → 0.2 ns；`RSZ_CORNERS` 加 ff_100C 的版本壅塞失敗，退回（決定 17）。
5. **IR**（步驟 5e）：照 Caravel 真實的供電網路量，wrapper 只從左右兩側接、兩顆 pad 相距 2.2 mm，最壞組合 104 mV；met4 strap 1.6 → 4.8 µm（決定 18）、改用慢 corner 判（決定 19）、改用 max power pattern 的實際切換活動判 20 mV（決定 20），`p7_harden5` 19.71 mV。
6. **內部 net slew**（步驟 5e）：最後一次 slew 修復後重新 global routing 把一條 net 擠去繞路，0.779 ns；試過四種修法不收斂，placement 密度 55 → 50%（決定 21）。
7. **正式 harden 與 golden**（步驟 5f–5g）：`f721cff` 只缺 golden，直接建（決定 22）；EQY 1/16149 個分區沒證明，加 amend 重試（決定 23；第一版把 flip-flop 併進分區造成空洞證明，negative test 抓到後修正）；確認 harden `f4ea9de` 逐值相同，正式 eqy／gl／ir PASS。
8. **precheck 判定 checker**（步驟 6）：`check_precheck.py`、`rdb_flatten.py`，獨立 agent 審查後補 4 項（版本、`gds.info`、無座標值項目、比對基準來源），`neg-precheck` 24 個案例（結案時 31 個）。
9. **官方 precheck**（步驟 7）：第一次 li1 密度 75%（`decap_3` fill，上限 60%），BEOL／LVS／OEB 因 VM 10 GiB 被 OOM 砍掉；改 `ef_decap_12` 與 fill、VM 16 GiB、比對基準只比允許規則（決定 24）。`7eff65a` harden、`550869c` 確認 harden，正式 precheck PASS。
10. **regress 整合**（步驟 8）：soc_top 也改用 pattern IR（`make ir-soc`）；wrapper 只對它特有的判斷植入錯誤；`make regress-caravel` 含 precheck（決定 25）。三個乾淨 worktree 平行跑。
11. **結案審查與第二輪**（步驟 8）：第一輪（`84fe505`）三條都 PASS，期間兩個獨立 agent 審查找到 8 個 checker 漏洞與 1 個防護缺口，全部修正、各加 negative test（決定 26）；修正時新變數蓋掉既有變數（`defines`），開 regress 前的 positive control 抓到。第二輪（`2b04451`）因磁碟滿與 KLayout 當掉重跑兩條，全部 PASS。之後用 Caravel 的 fill 做法試跑 wrapper 的 fill 後密度（決定 26）。

## 帶進本階段的項目

狀態：**已解決**；**部分處理**（剩下的寫在同一列）；**重新量過**（限制還在，已在 wrapper 上量過）；**macro 本身**（SRAM macro 的性質，Phase 7 用同一顆：`git diff --stat 85bfa75 HEAD -- ip/sram` 沒有輸出，`check_soc.py macro_gds` 169 個 cell 相同）；**沒量**（寫明原因）。

### Phase 6 已知限制

| # | 限制 | Phase 7 結果 |
|---|---|---|
| 1 | SRAM .lib 沒有走線寄生，靠下限蓋住；dout0 transition 寫 0.5 ns，實際 1.4–2.2 ns | **重新量過**：wrapper 上把 dout0 transition 改成量到的值，最差 setup +0.548 → **+0.151 ns**（min_ss_n40C；soc_top 同法 +0.37），仍 MET，hold 不變（`runs/p7_exit_draft/dout0_whatif.md`）。`min_pulse_width` 最差 slack 9.32 ns。重新特性化留到下線前（決定 1） |
| 2 | port 1 浮接的穿透電流不在 .lib 裡 | 重新量過：`ir_worst.py` 與 pattern IR 都加上（ss 100°C +0.151 mW）；flow 的 `power__total` 仍不含 |
| 3 | .lib 的漏電不是穩態值 | macro 本身，沒變。另外 `ef_decap_12` 沒有 .lib，漏電不進報告 |
| 4 | macro DRC 的面積容許 0.05% | 重新量過：wrapper 的 SRAM 外 0 個；框內 5,572,955 個全部對得上 SRAM 單獨檢查 |
| 5 | clock skew 變大，推測是 `clk1` | **部分處理**：wrapper 的 hold skew metric −3.598 ns，唯讀分析（`runs/p7_skew_analysis/README.md`）：約 2.7 ns 是報表算法（Caravel 的 source latency 差 0.92 ns 加共同路徑 derate，被算成扣分；推測，沒讀 OpenSTA 原始碼）；真正影響 hold 的 skew wrapper −0.632、soc_top −0.678 ns。`clk1` 的推測仍沒做實驗 |
| 6 | `DRT-0418`（SRAM 25 支腳位不在繞線格點上） | 重新量過：wrapper 同樣 25 次、全在 `u_soc.sram0`；最終 DRC、LVS 0。根因沒查 |
| 7 | `neg-char` 不在 regress 裡 | 沒變；Phase 7 沒改 `ip/sram`，Phase 6 結案的 22/22 仍適用 |
| 8 | OpenRAM 的已知問題 | macro 本身，沒變。precheck 的新 deck 另外找到 bitcell 的兩條規則（已知限制） |
| 9 | 照舊帶到後續階段的 | 見下兩表 |

### Phase 5、Phase 3.5 已知限制（Phase 6 第 9 項）

| # | 限制 | Phase 7 結果 |
|---|---|---|
| 5-1 | duty cycle 與 jitter 是假設 | **部分處理**：查了 Caravel 的時脈來源（開機時外部時脈、之後 PLL 經 `clock_div`），沒有官方 duty 與 jitter 數字，維持假設、記成下線風險，並寫明使用限制：管理端時脈 ≤ 22.7 MHz（決定 15） |
| 5-3 | IR 的供電位置是假設；EM 沒有檢查 | **供電位置已解決**：從 Caravel 真實的 pad 與跨接線起算（決定 18），慢 corner、max power pattern 判 20 mV（決定 19、20）。**EM 沒量**（已知限制） |
| 5-4 | 不可重現的步驟 | 重新量過：wrapper 三組比較都是 455 個逐值相同（見「可重現性」），全部在同一台機器；`DRT_THREADS=1` 沒試 |
| 5-5 | GRT-0229、GRT-0116 只用重試繞過 | 重新確認：Phase 7 的正式 harden 都沒有重試；`p7_harden3` 的 GRT-0116 是真的壅塞（溢位 771），不在重試範圍 |
| 5-6 | golden 誤差內的改變抓不到 | 沒變：wrapper 的誤差沿用 hazard3 的值（決定 26，「維持 hazard3 的值，寫明理由 (建議)」），理由見「可重現性」；誤差內的改變仍抓不到 |
| 5-7 | ADR-0016 留下的項目（SRAM 輸入腳 hold 等） | 重新量過：wrapper 的 SRAM 輸入腳最差 hold（ff_n40C）min RC +0.21 ns（`u_soc.sram0/addr0[6]`），soc_top Phase 6 +0.28 ns（`runs/p7_exit_draft/sram_sta.md`） |
| 5-8 | RepairHold 只用一種 hold buffer | 沒變：wrapper 網表 3,159 顆 `dlygate4sd3_1`；決定 17 的餘量 0.2 ns 讓 Caravel 輸入路徑多插延遲 cell |
| 5-11 | 沒有分析的項目 | 沒變；另加 Phase 7 的：`RSZ_CORNERS` 加 ff_100C 後 resizer 不放大 `a221oi_1`（決定 17） |
| 3.5-5／6／7 | Monte Carlo、修剪、只在 tt 驗誤差 | macro 本身，沒變 |
| 3.5-13 | hold 弧與週期 | 沒變：wrapper 週期仍 44 ns |
| 3.5-14 | dout0 最小負載低於特性化範圍 5 fF | 重新量過：wrapper min RC 4.3 fF（max RC 4.8 fF），最大 27.9 fF（`runs/p7_exit_draft/sram_sta.md`）；仍低於 5 fF |
| LVS | LVS 中 SRAM 是 black box | 重新確認：precheck 的 LVS 也把 SRAM 當 black box（決定 7，ChipFoundry 自己的 SRAM 範例也這樣做），`Circuits match uniquely`；代價是 CVC 報 74 個 HI-Z 輸入，全部來自 SRAM 的 `dout0` 與接在上面的 `buf_4`（已知限制） |

### Phase 5 已知限制 12 的子項（Phase 6 只寫「其他沒變」，這裡逐條補）

| # | 限制 | Phase 7 結果 |
|---|---|---|
| 4-6 | EQY 只證組合邏輯；RTL → 合成網表沒有 formal | 重新確認：`eqy-caravel` 16149/16149，2,238 個 flip-flop 種類相同、2,240 個 clock pin 同源；RTL → 網表靠 gate-level lockstep 模擬。amend 重試的限制見已知限制 |
| 4-7 | `counters` 測試抓不到計數器高半部卡 0 | 沒變（測試缺口，與擺放無關） |
| 4-9 | 下游步驟單獨執行時不檢查工作目錄是否乾淨 | 沒變；wrapper 的 5 個下游步驟加進 `neg-run-guard`（結案時 65 個案例），檢查的仍只有 commit |
| 4-10 | `py-check` 只檢查同一檔案的名稱 | 沒變；91 個檔案 PASS |
| 4-12、X1 | golden 只在同一台機器比對過 | 沒變、沒量：wrapper 的 run 全在同一台 Mac（已知限制） |
| 金屬密度 | 金屬密度沒有下限 checker，實測低於下限 | **重新量過，仍低於下限**：precheck 的密度檢查只查上限（li1–met4 ≤ 60%、met5 ≤ 76%），PASS。wrapper 的覆蓋率 li1 39.9%、met1 18.1%、met2 1.6%、met3 0.8%、met4 26.7%、met5 27.3%，都低於 Phase 3 寫的下限（met1–4 35%、met5 45%）。使用者 2026-10-14 選「加一個限時試跑預估 fill 後密度」（決定 26）：用 Caravel 的 fill 做法單獨補 wrapper，li1 與金屬只剩 met2 一個視窗 34.5%，FOM 有 15 個視窗低於 33%（最低 31.5%），都在左下角 SoC 與 SRAM 一帶（`runs/p7_review/fill_trial/README.md`）。下限檢查在 tapeout 時才跑，列為已知限制 3 |
| `flop_async_reset` | neg-eqy 的位置範圍在大扇出 net 上很大 | 沒變；wrapper 的 neg-eqy 只有 1 個案例，不含這個 |
| GRT-0243 | antenna 修補有一條 net 修不掉 | 重新量過：wrapper 同樣 1 次，最終 antenna 0 |
| X2 | IR 只做 static | **部分處理**：電流改用 max power pattern 的實際切換活動（決定 20）；仍是 static，沒有 dynamic IR |

## 可重現性

| 比較 | 結果 |
|---|---|
| wrapper：第二輪乾淨 worktree（`2b04451`）、第一輪乾淨 worktree（`84fe505`）各與 golden（`550869c` 確認 harden，來源 `7eff65a`） | 455 個逐值相同（兩組） |
| wrapper：`f4ea9de` 與 `f721cff`；`550869c` 與 `7eff65a` | 455 個逐值相同（兩組） |
| Hazard3 soc_top：乾淨 worktree 與 golden（Phase 6 結案） | 441 個逐值相同（Phase 6 兩次、Phase 7 第一輪、第二輪第一次與第三次執行） |
| PicoRV32 soc_top | 435 個逐值相同（第一輪、第二輪兩次） |
| PicoRV32 picorv32_core | 第一輪 29 個在誤差內、其餘逐值相同（detailed routing 繞線 708,675 µm、134,167 個 via，golden 708,673 µm、134,168 個）；第二輪兩次 325 個全部逐值相同 |
| 重試 | 沒有 |

- wrapper 的 run 全部在同一台 Apple Silicon Mac；三條 regress 同時跑的負載讓 wrapper harden 從單獨跑的 182 分鐘拉長到 236 分鐘（第一輪）、286.6 分鐘（第二輪，另有磁碟壓力），結果不變。
- **golden 誤差**（決定 22 留到結案判斷，決定 26 定案）：wrapper 沿用 hazard3 的誤差，不改成逐值相同。wrapper 四組比較（`f721cff`→`f4ea9de`、`7eff65a`→`550869c`、`550869c`→`84fe505`、`550869c`→`2b04451`）都逐值相同，量不出誤差該多大；誤差要涵蓋的步驟（GRT 後的重新 global routing、多執行緒 detailed routing）wrapper 也有。`picorv32_core` 從 Phase 5 起一直逐值相同，第一輪卻有 29 個落在誤差內、第二輪兩次又逐值相同：不可重現是偶發的，「到目前都逐值相同」不能當拿掉誤差的依據。樣本全在同一台機器（登記表 G05、G06）。

## Checker qualification（本階段新增）

| negative test | 植入的錯誤 | 預期的 checker | 結果 |
|---|---|---|---|
| `neg-precheck`（31 個案例，2 個 positive control） | 其他項目 FAIL 或缺項、`magic_drc` FAIL、報表屬於別的 GDS（`input_file_hash`、`gds.info`）、cf-precheck 版本不同、報表早於 `project.json`、狀態與項目不一致、別的 top cell、違規掛在 GDS 沒有的 cell 或沒有座標值、SRAM 有兩顆、項目數與 `.total` 不同、多一條規則、違規在 SRAM 外、一個 bitcell 違規移 0.1 µm、比對基準是另一版 deck 或另一顆 macro、比對基準的其他規則（`ref_extra_rule` 要 PASS、`ref_other_rule` 要 FAIL）；審查後加的時間戳時區（H6）與正式來源（H7）6 個 | `check_precheck.py` | 第二輪三條都 31/31（Hazard3 是第三次執行；第二次執行時 KLayout 當掉，見「正式 run」） |
| `neg-pin-plan`（26 個案例） | checker 16 個（含審查後加的 A4：自己重算 digest）：沒核准、ADR 沒有原話、核准後規劃改了、保留的 GPIO、同一支 GPIO 用兩次、距離超過上限沒寫理由、範本沒有的 GPIO、`user_defines.v` 模式、wrapper 的腳位常數、config 的 SRAM 位置、沒用範本 DEF、新設計沒有規劃；hook 10 個：核准前擋下受管轄檔案的編輯、只改週期放行、legacy 設計放行等 | `check_pin_plan.py` | 26/26 |
| `neg-pnr --cpu caravel`（9 個案例） | C00 positive（含 magic_drc 的 SRAM 原點）、C09 SRAM 移位、C15 腳位表、C26 供電點、C80a–c 邊界 slew（超過外部 transition + 0.05、內部違規、計數對不上）、C80d（SDC 的 transition 沒生效，審查後加）、P79 `analog_io` don't-touch（含 `bit0`） | `check_soc.py`、`check_inputs.py` | 9/9 |
| `neg-pnr` P79–P81（soc_top） | inout don't-touch（含 `bit0`）、內部 slew 違規（P80）、`judged_by` 的上限列（P81，含不存在或不在 regress 的 target） | `check_inputs.py`、`check_soc.py max_slew`、`check_signoff.py` | `neg-pnr` 82/82（Hazard3、PicoRV32） |
| `neg-ir-soc`（12 個）、`neg-ir-caravel`（10 個） | 上限在最差值上下 0.01 mV、少一個視窗 × corner、某一列 FAIL、沒有 VCD、VCD 沒標註（scope 改名）、錄波時多一個 `vcd` 開頭的 plusarg、韌體沒標的視窗、Caravel 跨接線或 pad strap 少一條；審查後加的只給一個視窗（H3）、錄波週期不同（H2）、NaN（H4） | `ir_pattern.py`、`ir_caravel.py`、錄波 | soc 12/12；caravel 10/10 |
| `neg-eqy-soc` `nand2_comb_to_nor2`、`nand2_flop_to_nor2`；wrapper `nand2_comb_to_nor2` | 走 amend 重試後仍證不出來、flip-flop 驅動的輸入不能被 amend | `run_eqy.py` 的重試 | Hazard3 16/16、PicoRV32 12/12；wrapper 1/1 |
| `neg-gl-soc --cpu caravel`（1 例 `mcycleh13_stuck1`） | 網表的一個 bit 卡 1 | gate-level lockstep 比對 | 1/1 |
| `neg-run-guard`（65 個，含 wrapper 的 5 個下游步驟與審查後加的 IR 兩支） | harden 的 commit ≠ HEAD 等 | `run_guard.py` | 65/65 |

## 本階段找到並修正的 checker 問題

1. **`check_soc.py` 的迴圈變數蓋掉 SRAM 原點**（`cbf2c5e`）：wrapper 的 `ir_sources` 迴圈在模組層用 `x, y`，蓋掉從 DEF 讀到的 SRAM 位置；`magic_drc` 拿最後一個供電點當 SRAM 外框，把 5,572,955 個 SRAM 內的違規全部判成框外（FAIL，沒有誤判 PASS）。改名後 PASS；`neg-pnr --cpu caravel` C00 要求 wrapper 的 positive run 的 magic_drc PASS。
2. **EQY amend 重試的第一版會給出空洞證明**（決定 23）：把 flip-flop 輸出也寫成 amend，flip-flop 併進分區，`sat` 對含 flip-flop 的分區是空洞證明，植入的 nand2 → nor2 被判 PASS。negative test 的 `REQUIRE` 擋下；改成只對組合邏輯驅動的輸入寫規則，被 amend 的分區有 sequential cell 就 FAIL。
3. **precheck 判定的 4 個漏洞**（步驟 6 的獨立 agent 審查）：舊報表配新 GDS 會判 PASS（cf-precheck `runner.py` 第 23–31 行確認）、cf-precheck 版本、沒有座標值的項目、比對基準的來源。補上 `gds.info`、版本、項目數與比對基準 `input.sha1` 檢查與 10 個案例。
4. **比對基準的其他規則**（決定 24）：precheck PDK `3e0e31dc` 的預建 SRAM 另有 10 個 nsdm／psdm 違規，原本的判法讓比對基準本身 FAIL；改成只比允許的規則，並加 `ref_other_rule` 確認設計的同一條規則不會被放過。
5. **`disconnected` 對 wrapper 的判法**（`d1a7888`）：Caravel 固定腳位中沒用到的 327 個會被列出；改成必須剛好等於規劃中沒用的輸入腳位加上沒有 cell 的電源腳位。
6. **錄波撞名**（`stray_dump`）：`tb_soc.v` 遇到 `vcd` 開頭的 plusarg 會把整個 testbench 從時間 0 傾印到 `wave.vcd`，視窗自己的 `$dumpfile` 被忽略；`run_gl_soc.py --record-window` 檢查並 FAIL，`neg-ir-soc` 的案例。

獨立審查找到的 8 個漏洞與 1 個防護缺口（H1–H8、slew）見「獨立審查」。

修審查漏洞時，在開第二輪結案 regress 之前抓到的：

7. **修 H8 時新加的變數蓋掉 `resolved` 列的預期值**：`check_inputs.py` 為了展開 `analog_io` 的範圍，新增變數 `defines`（`` `define `` 巨集的值），蓋掉同一個函式後面 `resolved` 列要比對的 `VERILOG_DEFINES`，每一次 harden 的 `check_inputs --resolved` 都會 FAIL。依 `phase-exit-review` 規則 2，開 regress 前先把修正套進已跑完的 `p7close_h3` worktree、在它自己的 run 上跑 positive control 才抓到；變數改名後三種 CPU 都 PASS。和 Phase 6 的 `files`（「本階段找到並修正的 checker 問題」6）同一類，第二次出現。

## 與計畫不同的地方

1. **CPU 改用 Hazard3**（決定 2）：計畫 §8 原寫 PicoRV32（Phase 5 之前寫的），已同步。
2. **只做到 precheck，不下線**（決定 1）。
3. **exit 條件的判法**（決定 5）：官方結果的 `klayout_feol`／`klayout_beol` 仍是 FAIL，PASS 是本 repo 依「只有兩條規則、位置與預建 SRAM 相同」判的。
4. **precheck 在本機 lima VM 跑**，不是 colima（決定 4，下載速度的關係；同樣 vz＋Rosetta）。
5. **IR 的判法改了三次**（決定 18–20）：從 Caravel pad 起算；慢 corner 判；電流用 max power pattern。soc_top 也改用 pattern（決定 25）。Phase 5 的「每次 harden 判最壞組合」由決定 19 取代。
6. **flow 設定**：wrapper 的 GRT hold 餘量 0.2 ns（決定 17）、placement 密度 50%（決定 21）、met4 strap 4.8 µm（決定 18）、`ef_decap_12` fill（決定 24）、`RSZ_DONT_TOUCH_RX`。
7. **slew 上限的邊界例外**（決定 16）與 **EQY 的 amend 重試**（決定 23）。
8. **wrapper 的 negative test 只植入它特有的判斷**（決定 25）。
9. **流程新增 pad／block／pin 規劃的強制**（決定 13，CLAUDE.md 規則 14）。

## 已知限制（帶到後續階段）

每一項的放寬依據與重新驗證條件登記在 `docs/relaxation_register.md`（括號內是登記表的編號，ADR-0020）。

**下線前一定要處理的**（Phase 7 不下線，決定 1）：
1. **precheck 的判法**（決定 5、24）：官方結果的 `klayout_feol`／`klayout_beol` 仍是 FAIL，PASS 是本 repo 依「只有兩條規則、位置與預建 SRAM 相同」判的；ChipFoundry 收不收不知道，issue 草稿沒有送出（決定 6、26）。Magic DRC（選用項目）沒跑，自產 SRAM 在完整規則下約 220 萬個違規，ChipFoundry 怎麼看要問。
2. **SRAM .lib 沒有走線寄生**（S04、S07）：dout0 transition 改成量到的值後，wrapper 最差 setup +0.548 → **+0.151 ns**（min_ss_n40C，仍 MET）；萃取量到 2.0 倍，× 1.6 不夠；dout0 最小負載 4.3 fF，低於特性化範圍 5 fF。下線前用平面萃取網表重新特性化（決定 1）。
3. **金屬密度**：wrapper 的覆蓋率 met1 18.1%、met2 1.6%、met3 0.8%、met4 26.7%、met5 27.3%，低於 tapeout 時的下限檢查（`check_density.py`：li1、met1–4 ≥ 35%、met5 ≥ 45%，700 µm 區塊）；precheck 只查上限。查證（`runs/p7_review/chipfoundry_fill.md`）：fill 由 ChipFoundry 在 tapeout 時對整顆 Caravel 補（證據中等，沒有文件明講）。**fill 試跑**（決定 26，`runs/p7_review/fill_trial/README.md`）：照 Caravel 的 `generate_fill.py`（`wafflefill(tiled)`）單獨補 wrapper，再照 `check_density.py` 的 700 µm 視窗量。li1、met1–5 除了 met2 的 (0, 0) 視窗 34.5% 以外都到下限以上；FOM 有 15 個視窗低於 33%（最低 31.5%）。補不起來的都在左下角 SoC 與 SRAM 一帶。met4 最高視窗 59.7%，貼近上限 60%。die 右緣與上緣的視窗、ChipFoundry 實際的 fill 參數判斷不了。要向 ChipFoundry 書面確認（決定 26）；要改善的話，方向是降低左下角的局部密度（沒試）。
4. **EM 沒有檢查**：flow 從來沒判 EM；ff corner 的 IR 照跑只印 INFO。
5. **pattern IR 的餘量只有 0.44 mV**（19.56 mV，上限 20 mV；第二輪 `ir-caravel` 同值）；pattern 沒有 Wishbone 主機端的存取、零延遲模擬不含 glitch、「最耗電」是三段取最大不是證明（I08）；板子在 pad 端最低 1.62 V 是假設（I02）。
6. **使用限制**（決定 9、10、15）：管理端時脈 ≤ 22.7 MHz（44 ns）；`host_en` 的 reset 值是 1，管理用韌體一定要寫 0 才放開 CPU；`gpio_out` 只走 LA，從晶片外看不到；PLL jitter 與 duty cycle 是假設（T07）。

**Phase 7 的判法或繞過，不影響這次結果但要知道的**：
7. **clock skew**：hold skew metric −3.598 ns 中約 2.7 ns 是報表算法（推測，沒讀 OpenSTA 原始碼）；真正多出來的是 `wb_clk_i` 到 clock root 約 1.9 ns，Caravel 輸入路徑多了至少 312 顆 hold buffer、SRAM 半週期 setup 少約 0.11 ns。最差 setup／hold 仍 PASS。下一顆設計讓 CTS root 靠近 clock 腳位（沒試）。
8. **邊界 slew 另判**（決定 16）：Caravel 直接驅動的 net 可到「外部 transition + 0.05 ns」；低於上限的輸入腳位（`wb_clk_i`、`io_in` 等）的 transition 有沒有生效沒有自動防護（`timing-constraints-sdc` 規則 14）。`io_in`／`io_out`／`io_oeb` 的邊界時序是 20% delay 的假設（T09）。
9. **resizer 沒看 ff_100C**，靠 GRT 後 hold 餘量 0.2 ns（決定 17）；加 ff_100C 時 resizer 不放大 `a221oi_1` 的原因沒找到。
10. **placement 密度 50% 是繞過**（決定 21）：最後一次 slew 修復後的重新 global routing 會擠出繞路；繞線後 ECO 在釘版 OpenROAD 做不到（`RSZ-0074`）。
11. **EQY 的 amend 重試**（決定 23）：只對組合邏輯驅動的輸入；`_10122_.B` 每次都靠重試才證得出來。RTL → 合成網表仍沒有 formal，靠 gate-level lockstep 模擬。
12. **wrapper 只植入它特有的判斷**（決定 25）：共用 checker 在 wrapper 上的特殊組合沒有逐一植入；pin-plan 只比 localparam 的值、不查 RTL 有沒有用它（審查 G1，RTL 模擬會抓到）；CVC 的 HI-Z 沒有自動判定（74 個全是 SRAM 的 `dout0`）；precheck 的 `oeb`、`xor`、`gpio_defines` 只看過 PASS。
13. **golden 誤差沿用 hazard3**（G05，決定 26）：wrapper 四組比較都逐值相同，量不出誤差；樣本全在同一台 Mac（G06）。picorv32_core 第一輪第一次落在誤差內（29 個，detailed routing 多 2 µm 繞線），第二輪兩次又逐值相同。
14. **`ef_decap_12` 沒有 .lib**（決定 24）：漏電不進功耗報告；li1 密度在 harden 內沒有自動檢查，要等 precheck（ADR-0020 的 D5 留到下一個專案）。
15. **PSM 在 Caravel 跨接線的位置放供電點會 Signal 11**（決定 18），改放在 ring 與 strap 的交點，原因沒查。
16. **工具版本**：本機與官方 image 的 Magic、KLayout、Netgen、PDK 都不同；`make regress-caravel` 依賴 lima VM 與網路，容器每次升級 cf-precheck（版本不同時 checker 會 FAIL）。
17. **扁平放法沒有官方範例**（決定 2）：ChipFoundry 收件時會不會有額外要求不知道（推測的風險）。
18. **依據不是 wrapper 的放寬**（登記表第一類）：PnR max transition 0.70 ns（T15）與 post-CTS hold 餘量 0.3 ns（T16）的原因已經不在、沒有重新評估；週期 44 ns 沒有在 wrapper 上反推最小週期（T03）；PnR 修復參數（T17）、Magic DRC 位置容許 100 nm（D03）、讀出 flip-flop 自迴路的 hold cell（O01）。
19. **提早檢查的自動防護**（ADR-0020）：19 條中能自動化的部分（harden 前檢查 limits 出處與 corner 清單、平台密度上下限等）到下一個專案開始前只靠流程文件與 skill。
20. **regress 對本機資源不足沒有防護**（2026-10-15，第二輪）：磁碟滿時 `neg-pnr` 的 STA 會停住不報錯，`scripts/regress.py` 各項沒有逾時，只能人看 console；KLayout 在記憶體壓力下當掉時 `neg-precheck` FAIL 的訊息是「報表沒有項目」，看不出是工具當掉。現在的做法是開 regress 前確認磁碟空間、清掉舊 worktree 的 negative test 中間產物（每個 worktree 40–70 GB）、三條平行時留意 swap（`flow-regression-reproducibility`、`tapeout-precheck-caravel` 經驗紀錄）。

**照舊帶到後續**：Phase 6 已知限制 3（.lib 漏電不是穩態值）、4（macro DRC 面積容許 0.05%）、6（`DRT-0418`）、7（`neg-char` 不在 regress 裡）、8（OpenRAM 的已知問題）；Phase 5 已知限制 4（不可重現的步驟）、5（GRT 只用重試繞過）、8（只用一種 hold buffer）、11（沒有分析的項目）；Phase 3.5 已知限制 5–7、13（Monte Carlo、修剪、只在 tt 驗誤差、hold 弧與週期）；LVS 中 SRAM 是 black box；Phase 4 已知限制 7、9、10（計數器高半部、下游不檢查工作目錄、`py-check` 範圍）；IR 只做 static（沒有 dynamic IR）。

## 獨立審查（2026-10-14）

兩個沒參與實作的 agent，在第一輪結案 regress（`84fe505`）執行期間審查（只讀，實驗限在幾分鐘內的 checker 與單步工具）。報告：`runs/p7_review/doc_check.md`、`checker_holes.md`，實驗在 `runs/p7_review/holes/`。

### 文件核對

核對 110 列：正確 78、錯誤 5、說法不完整會誤導 23、無法核對 4。正式結果本身（precheck、EQY、gate-level、pattern IR、golden、negative test 的案例數）都對得回證據；問題集中在後面的決定改了、前面的文字沒同步，以及不同條件的數字放在一起比。例如：
- ADR-0019 決定 19 的 50 mV 上限沒標「已被決定 20 取代」，流程文件也還寫「上限是板子的供電要求」；
- 「只用 wrapper ring 會低估 5 倍以上（8.4 → 45 mV）」兩個數字條件不同，同條件是 4.94 → 45.56 mV（約 9 倍）；
- golden README 的 clock 一列還寫「成因沒查」，彙總的 `clock__skew__worst_hold`（−2.589 ns）是各 corner 最不負的值，不是最差值（LibreLane `library.py` 第 166–167 行）；
- knowledge 檔引用的 `runs/user_project_wrapper_signoff/` 已被下一次 harden 覆蓋；
- `timing-constraints-sdc` 規則 14 寫「Phase 7 會加的比對」結案時沒有加。

28 列全部修正（清單：`runs/p7_review/doc_fixes.md`）；最後一項是真的防護缺口，和 checker 漏洞一起處理。

### 找 checker 漏洞

確認 8 個漏洞與 1 個缺口，每一個都有植入實驗與對照組；這次交付的版圖都不受影響（審查者逐一查過正式結果）。使用者 2026-10-14 選「全部修正，三條 regress 重跑 (建議)」（ADR-0019 決定 26）：

| # | 漏洞（植入後 checker 仍 PASS） | 修正 | negative test |
|---|---|---|---|
| H1 | pin 規劃改了以後，自己用 `--digest` 重算 `plan_sha256` 就算「已核准」 | ADR 要有一行同時寫原話、日期與完整的 digest | `neg-pin-plan` A4 |
| H2 | IR 的 VCD 用別的週期錄（時間 × 1.1），全部 PASS，IR 少 0.38 mV（正式餘量 0.44 mV） | 從 VCD 量 clock 週期 = `CLOCK_PERIOD`；錄波週期從 `CLOCK_PERIOD` 取 | `neg-ir` `period` |
| H3 | IR 判定不呼叫 run guard、不要求三個 window 都在 | `ir_pattern.check_inputs()` | `neg-ir` `one_window`；`neg-run-guard` 加兩支 |
| H4 | IR 的 NaN 排在第二個 corner 時被 `max()` 略過 | 非有限數值 FAIL | `neg-ir` `nan_drop` |
| H5 | `judged_by` 填任何字串都能把上限變成 INFO | 必須是 Makefile 裡、而且在 regress 清單裡的 target | P81 兩個子案例 |
| H6 | precheck 的時間戳丟掉時區再比 | 換成 UTC，沒有時區就 FAIL | `neg-precheck` `results_after_tz`、`no_tz` |
| H7 | 查證用（沒過 run guard）或沒有來源檔的 precheck 專案也判 PASS | 要求正式來源；查證用要 `--verification`，結論標明 | `neg-precheck` 4 例 |
| H8 | `inout_dont_touch` 只看向量的 bit 0 | 每個 bit 都要被涵蓋 | P79 `bit0` |
| slew | Caravel 輸入腳位的 slew 沒和 SDC 設定值比（driving cell 蓋掉 transition 時 PASS） | 高於上限的腳位每個 bit 都要以 SDC 的值出現（每個 corner 320 個） | C80d |

G1（pin-plan 只比 localparam 的值，不查 RTL 有沒有用它）判為覆蓋缺口：testbench 寫死的 GPIO 會在 RTL 模擬抓到，沒有修，列為已知限制。漏洞類型寫進 `signoff-checker-qualification`（7 類）。

### 流程回顧（使用者 2026-10-14 另外要求）

使用者問「這整套流程從頭到現在，有沒有哪些我們處理很久或必須放寬要求的，是因為有些我們做到太後面才開始看」。三個 agent 分段回顧 Phase 0–7（`docs/notes/flow_retro/`），合併成 19 條提早檢查，使用者選全部寫進流程文件與 skill、checker 留到下一個專案、放寬與補償登記表現在建（ADR-0020；登記表 `docs/relaxation_register.md`，90 列）。使用者舉的例子（低溫讀取失敗是否表示不該放 ss −40°C corner）三份報告結論一致：拿掉 corner 解決不了（同一顆 SRAM 在 ss 25°C 1.60 V 也讀錯，Caravel 規格也要求 −40°C），該提早的是選 macro 之前在整個操作範圍做 SPICE 讀寫。

## 使用者決定

ADR-0019 有每個決定的選項、理由與使用者原話。本階段的決定：
1. 2026-10-12：「做到 precheck PASS，不下線 (建議)」、「Hazard3 (建議)」、「先查清楚再決定 (建議)」（決定 1–3）。
2. 2026-10-12：「本機 colima＋Rosetta (建議)」（決定 4）；「其他全 PASS＋這兩條比對預建 (建議)」（決定 5）；「我擬稿，你自己決定發不發 (建議)」（決定 6；結案時仍未送出，決定 26）。
3. 2026-10-12：「wb_clk_i／wb_rst_i (建議)」、「Wishbone slave (建議)」（決定 8、9）；「5 支放 GPIO 33–37，gpio_out 只走 LA (建議)」（決定 10）；「沿用 soc_top 的設定 (建議)」（決定 11）；「左下角，靠近 Wishbone (建議)」（決定 12）。
4. 2026-10-12：「要想個辦法確保之後一定會先探討pad & pin location」，「四層都做 (建議)」、「新建 chip-floorplan-pin-planning」（決定 13）；pin 規劃核准「可以」。
5. 2026-10-12：「官方數值，不用 multicycle (建議)」（決定 14）；「維持假設，記成下線風險 (建議)」（決定 15）；「內部照舊，邊界另判 (建議)」（決定 16）；「加 ff_100C＋餘量 0.2 (建議)」→「回 12 corner＋餘量 0.2 (建議)」（決定 17）。
6. 2026-10-13：「不移 block＋met4 4.8＋供電要求 (建議)」（決定 18）；「用慢 corner 判 (建議)」（決定 19）；「一般IR都會用CPU max power pattern去做不是嗎」、「這才是正確的評估IR 的方式」、「回到 20 mV，時脈改 44 ns 再錄 (建議)」、「那我們還是採用pattern 評估做法」（決定 20）。
7. 2026-10-13：「採用 50%，進正式 harden (建議)」（決定 21）；「第一次正式 harden 直接建 (建議)」（決定 22）；「沒證明時自動 amend 重試一次 (建議)」（決定 23）。
8. 2026-10-14：「都選建議的」（決定 24）；「只做 wrapper 特有的部分 (建議)」、「三條分開、平行跑 (建議)」、「放進 regress-caravel (建議)」（決定 25）。
9. 2026-10-14（結案審查）：「全部修正，三條 regress 重跑 (建議)」；「先查 ChipFoundry 的 fill 規定再決定」→ 查證後「加一個限時試跑預估 fill 後密度」；「維持 hazard3 的值，寫明理由 (建議)」（golden 誤差）；「還沒送，維持草稿 (建議)」（ChipFoundry issue）（ADR-0019 決定 26）。
10. 2026-10-14（流程回顧）：「全部 19 條 (建議)」、「這次只寫進流程，checker 留到下一個專案 (建議)」、「現在建第一版 (建議)」（ADR-0020）。

## Skill 分析（`phase-exit-review` 規則 8）

本階段新建 2 個 skill：`tapeout-precheck-caravel`（Phase 7 開始時，CLAUDE.md 規則 7）、`chip-floorplan-pin-planning`（決定 13，CLAUDE.md 規則 14）。其他的寫回（`git diff --stat 98f49b7 HEAD -- .claude/skills`，19 個檔）：

| 任務 | skill | 寫回 |
|---|---|---|
| Caravel 整合、precheck 環境與判定、decap／li1、VM 記憶體、CVC、平台試算 | `tapeout-precheck-caravel`（新建） | 規則 1–11、經驗紀錄 14 列（含結案時的 KLayout 當掉與 fill 試跑） |
| pad、block、pin 的規劃與核准、電源進入點 | `chip-floorplan-pin-planning`（新建） | 規則 1–2 等、核准要記在 ADR（審查 H1）；經驗紀錄 5 列 |
| hold、slew、resizer corner、密度 50%、繞線後 ECO 做不到 | `drv-timing-closure` | 規則 13（重繞擠出繞路）、14、15（提早檢查 C2、C3）；經驗紀錄 8 列 |
| 邊界 SDC、driving cell 讓 `set_input_transition` 失效 | `timing-constraints-sdc` | 規則 14、15；防護改成部分自動（C80d） |
| IR 從 pad 起算、慢 corner、max power pattern、輸入核對 | `pdn-ir-drop`、`signoff-criteria`、`gate-level-simulation` | 規則 12、14；signoff-criteria「IR 用多大的電流」；gate-level 規則 9（錄波週期、撞名）；PSM Signal 11 經驗紀錄 |
| EQY 的 amend 重試與空洞證明 | `formal-equivalence-eqy` | 規則 7；經驗紀錄 3 列 |
| `--from` 接續、`RSZ-0074`、hold 計數 | `librelane-run-debug` | 規則 2 更正；已知陷阱 |
| skew metric 的彙總值、wb_clk_i 長線 | `cts-clock-tree` | 規則 6 補彙總值（LibreLane 原始碼已核對）、規則 13（提早檢查 D4）；經驗紀錄（2.7 ns 是推測） |
| 審查找到的漏洞、變數重名 | `signoff-checker-qualification` | 漏洞類型表 7 類、規則 11–13；經驗紀錄 |
| 結案、流程回顧 | `phase-exit-review`、`flow-regression-reproducibility` | 規則 10（登記表、審查時間點）；經驗紀錄各 1 列 |
| 流程回顧的 19 條提早檢查（ADR-0020） | `hard-macro-integration`、`openram-macro-characterization`、`signoff-criteria`、`multicorner-sta`、`floorplan-congestion`、`core-migration-hazard3` 等 12 個 | 各加一條提早檢查規則，流程文件同步 |

沒有更新的 skill 與理由：
- `drc-signoff`：precheck 的 deck、li1 密度與 fill 試跑寫在 `tapeout-precheck-caravel`（fill 與密度下限是平台在 tapeout 時做的，只出現一次，先寫經驗紀錄）；Magic／KLayout 的 DRC 判讀沒有新現象。
- `lvs-signoff`：SRAM black box 與 CVC 的 HI-Z 寫在 `tapeout-precheck-caravel` 規則 4；flow 的 LVS 做法沒變。
- `antenna-signoff`：結果 0，`GRT-0243` 同 Phase 6。
- `rtl-synthesis-lint`、`dv-directed-tests`：wrapper 的 RTL 與測試沿用既有做法（lint 57 個變體 0 警告）。
- `openram-macro-characterization`：Phase 7 沒有改 macro，只加了提早檢查 B2。

### 規則 10 稽核：本階段的工具缺陷與防護

| 工具缺陷或意外行為 | 症狀寫在 | 怎麼發現 | 怎麼繞過 | 防復發 |
|---|---|---|---|---|
| cf-precheck deck 拿掉 SRAM 核心區的豁免，OpenRAM bitcell 報 `MR_mcon.CON.10`、`MR_licon.SP.6` | `tapeout-precheck-caravel` 規則 3 | precheck 報表；macro 單獨跑 deck | 決定 5 的判法（位置與預建 SRAM 相同） | `make precheck-check`、`neg-precheck` |
| precheck 讀到前一次 run 的報表也會判 PASS（cf-precheck `runner.py`） | 同上；`signoff/precheck/README.md` | 步驟 6 的審查 | 比對 `logs/gds.info` | `stale_results` |
| 容器每次 `pip install --upgrade cf-precheck` | 同上規則 1 | `project.json` 的版本 | 釘版判定 | `other_version` |
| VM 記憶體不夠時 BEOL、LVS、OEB 被 OOM kill（`stat=-9`） | 同上規則 1 | VM 的 `dmesg` | VM 16 GiB、減少 instance | precheck-check 會 FAIL（看不出原因）；`env-check` 檢查 ≥ 15 GB |
| PDK 預設 `decap_3` 填滿讓 li1 75% | 同上規則 8 | `klayout_met_min_ca_density` | `ef_decap_12` 與 fill | precheck-check；harden 內沒有（ADR-0020 D5 留到下一個專案） |
| precheck PDK 的預建 SRAM 另有 nsdm／psdm 違規 | 同上規則 3 | checker 的比對基準列 | 只比允許的規則 | `ref_other_rule`、`ref_extra_rule` |
| OpenROAD 把沒接的 inout 同時算成 driver 與 load（`RSZ-0074`） | `librelane-run-debug` 已知陷阱 | flow 中止 | `RSZ_DONT_TOUCH_RX` | P79（含 bit0） |
| OpenSTA 對設了 driving cell 的腳位忽略 `set_input_transition` | `timing-constraints-sdc` 規則 14 | 報表的腳位 slew | `caravel_base.sdc` 暫停 driving cell | C80d（高於上限的腳位）；低於上限的沒有自動防護 |
| LibreLane `--from` 沒給 `--with-initial-state` 時用修改時間最新的 state | `librelane-run-debug` 規則 2 | `EST-0026`、`RSZ-0074` | 給 `--with-initial-state` | 沒有自動防護（只在手動接續時發生），寫成已知陷阱 |
| `RSZ_CORNERS` 加 ff_100C 後 resizer 不放大 `a221oi_1`、改插長串 buffer | `drv-timing-closure` 經驗紀錄 | `GRT-0116` 溢位 | GRT 後 hold 餘量 0.2 ns（決定 17） | 沒有自動防護（根因沒找到，不能寫成規則） |
| 最後一次 slew 修復後重新 global routing 把 net 擠去繞路 | `drv-timing-closure` 規則 13 | `check_soc.py max_slew` | 密度 55 → 50% | P80、C80a |
| 繞線後 ECO 在釘版 OpenROAD 做不到（`RSZ-0074`、增量繞線不收斂） | 同上 | 實驗 | 不做繞線後 ECO | 沒有自動防護（工具限制） |
| PSM 供電點在外殼跨接線位置時 Signal 11 | `pdn-ir-drop` 經驗紀錄 | IR 步驟中止 | 放在 ring 與 strap 的交點 | `ir_sources`（C26）檢查點的位置；當掉本身沒有專門的防護 |
| OpenROAD 對調等價輸入後，EQY 在共用的 net 切開，分區證不出來 | `formal-equivalence-eqy` 規則 7 | EQY 的 unproved 分區 | 一次 amend 重試 | `nand2_comb_to_nor2` |
| amend 把 flip-flop 併進分區，`sat` 變空洞證明 | 同上 | negative test 的 `REQUIRE` | 只 amend 組合邏輯、分區有 sequential cell 就 FAIL | `nand2_flop_to_nor2`、`nand2_to_nor2` |
| `tb_soc.v` 遇到 `vcd` 開頭的 plusarg 整個 testbench 傾印到 `wave.vcd` | `gate-level-simulation` 規則 9 | 錄波的 VCD 是 0 bytes | plusarg 不用 `vcd` 開頭 | `neg-ir` `stray_dump` |
| hold 修復的 `RSZ-0032` 計數會低報（journal restore 把計數歸零） | `librelane-run-debug` 已知陷阱 | 數網表的 `hold*` instance | 數網表，不讀 log | 沒有自動防護（只影響報告的數字，criteria review 數網表） |
| `report_clock_skew -hold` 把 source latency 差與共同路徑 derate 算成扣分 | `cts-clock-tree` 經驗紀錄 | skew metric 與 hold slack 對不上 | 不把 skew metric 當品質指標 | 推測，沒讀 OpenSTA 原始碼，不寫成規則 |

## 交付物

- **wrapper 設計**：`rtl/caravel/`（`user_project_wrapper`、Wishbone host bridge、`user_defines.v`）、`pnr/user_project_wrapper/`（config、`pin_plan.toml`、`caravel_io.sdc`、`fixed_dont_change/`、Caravel 供電資料 `caravel_pwr/`、`ir_caravel.py`）。
- **precheck**：`signoff/precheck/`（`check_precheck.py`、`rdb_flatten.py`、`run_deck.py`、`run_precheck.sh`、`neg_precheck.py`、README）、`make precheck-deck`、`make precheck-caravel`。
- **規劃**：`scripts/check_pin_plan.py`、`scripts/neg_pin_plan.py`、`scripts/plot_floorplan.py`、`.claude/hooks/require_pin_plan.py`。
- **IR**：`pnr/soc_top/ir_pattern.py`、`neg_ir.py`、`fw/tests/maxpower`、`dv/gl_soc/vcd_window.v`、`run_gl_soc.py --record-window`。
- **checker 與 regress**：`check_soc.py`（max_slew、wrapper 的 disconnected、ir_sources、magic_drc）、`check_inputs.py inout_dont_touch`、`check_signoff.py` 的 judged_by、`run_eqy.py` 的 amend 重試、`scripts/regress.py --cpu caravel`、`env/check_env.sh` 的 VM 檢查。
- **golden 與上限**：`signoff/golden/user_project_wrapper/`、`signoff/limits/user_project_wrapper.toml`。
- **文件**：ADR-0019、`docs/notes/caravel_precheck_phase7.md`、新 skill `tapeout-precheck-caravel`、`chip-floorplan-pin-planning`，CLAUDE.md 規則 14。
