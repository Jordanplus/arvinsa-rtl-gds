# signoff criteria 檢查：Hazard3 第 4 次 harden

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3`（commit `1292ca4`，週期 44 ns），2026-10-07
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 說明：這次 run 是在 `run.sh` 修改前跑的，LibreLane FAIL 後 checker 都沒跑；以下 checker 結果是 2026-10-07 事後在 worktree 裡補跑的（`LIBRELANE_DIR` 指向主 repo 的 LibreLane clone，與 harden 時相同）。

## 有沒有被執行

腳本 5 項都 PASS：
- config 的 40 個設定都進了 `resolved.json`，77 個 step 的 config 都一致。
- `clock_uncertainty.sdc` 的值（setup 0.25、hold 0.25、半週期 setup 2.45、DCD 2.20 ns）出現在 7 個時序 step 與 15 個 signoff corner。
- signoff corner = `STA_CORNERS` 的 15 個。
- 4 個 checker 都有結果行。

各 checker 的結果：

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | FAIL | `max_ss_n40C_1v60`、`nom_ss_n40C_1v60` setup 違規 | 設計問題（時序收斂，見下一節） |
| `check_signoff.py` | FAIL（5 列） | `timing__setup_vio__count` 27；兩個 ss_n40C corner 的 setup ws | 設計問題 |
| | | `timing__unannotated_net__count` 125 ≠ 133 | **criteria 問題**：133 是 PicoRV32 的組成（90 clkload + 32 `sram0/dout1` + 11 tie）。Hazard3 是 81 clkload + 32 `sram0/dout1` + 12 tie = 125，結構相同，只是 clock tree 的 dummy load 少 9 個。上限檔是從 PicoRV32 複製的，沒有為 Hazard3 重新推導 |
| | | golden 不存在 | 預期內：Hazard3 的 golden 還沒建立 |
| `check_soc.py` | PASS | — | — |
| `check_inputs.py --resolved` | PASS | — | — |
| `provenance.py`（開始、結束） | PASS、PASS | — | — |

這次發現：`run.sh` 在 LibreLane FAIL 時直接結束，第 2、3、4 次 harden 的 repo checker 都沒跑。已修（`run.sh`、`review_criteria.py` 的 `checkers_ran`、`neg_pnr.py` P48）。

「不分析的項目清單」：這次沒有寫，Phase 5 exit review 時要逐條寫。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns | ADR-0013：0.6 ns 會擋住 hold 修復，所以改 0.1。skill 的推導方法：餘量 = 實測的 post-CTS 到 signoff 差距 × 安全係數 | setup 修完 +0.112 ns → 插完 hold buffer 後 −0.161 ns（繞線前估計）→ signoff −1.131 ns（max_ss_n40C），差距 1.243 ns；第 3 次是 0.578 ns。差距大部分在繞線之後（0.97 ns），hold buffer 佔 0.27 ns | **依據不成立**：餘量遠小於實測差距。但調大會擋住 hold 修復（ADR-0013 實驗 1），不能單純調大 |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10：SRAM 輸入腳的 hold 繞線後變負 | hold 修完 +0.275 → signoff 最差 +0.109 ns（差 0.166；PicoRV32 差 0.227）；代價是 2,739 顆 hold buffer，post-CTS stdcell 面積 +13.4% | 依據仍成立（餘量大於實測差距）。代價記錄在 knowledge 檔 |
| `pnr.sdc` `set_max_transition 0.70`、`DESIGN_REPAIR_MAX_SLEW_PCT` 30 | ADR-0013 第 3 點：0.70 是為了 resizer 看不到 ss_n40C 而設，當時說好跑完 harden 再評估 | resizer 現在看得到 ss_n40C；最差路徑的修復 buffer 64 顆、22.3 ns（約一半的到達時間） | 資料不足：要用單步實驗比較 slew 上限改回 0.75 前後的 ss_n40C setup 與 slew |
| `DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 µm | Phase 2／3：SRAM 輸入長線與 slew | 單步實驗：拿掉只少 79 顆 buffer，ss_n40C setup −0.161 → −0.255 ns（在 run 之間的浮動內） | 不是這次 FAIL 的原因；原本的依據沒有重新驗證 |
| corner 清單（含 ss_n40C） | Phase 4、ADR-0013：溫度反轉 | 最差是 max_ss_n40C −1.131，ss_100C 最差 +1.11 ns | 依據仍成立 |
| uncertainty 各成分 | `docs/notes/signoff_criteria_soc_top.md` | 值都有套用；jitter 0.15 與 duty cycle 55% 仍是假設值（Phase 7 才有 Caravel clock 的規格） | 依據仍成立，但假設仍是假設。半週期路徑的 slack 這次沒有量，腳本也還沒報，列為改進項 |
| skew（無 criterion，只看數字） | 規則 4 | metric ff_n40C −0.594 → 扣掉 uncertainty −0.344 ns（仍含 derate）；flop 之間的 latency 分佈約 0.2 ns（繞線前估計） | 不是這次 setup FAIL 的原因（路徑兩端的 skew 只佔 0.07 ns） |
| `timing__unannotated_net__count` = 133 | PicoRV32 的組成 | Hazard3 125（見上一節） | **依據不成立**：這個數字是設計結構推導出來的，換 CPU 要重新推導 |
| `CLOCK_PERIOD` 44 ns | ADR-0004 Phase 5 補充：第 3 次差 0.381 ns | 第 4 次反而差到 −1.131 ns；週期一變，placement 與 buffer 鏈也跟著變，run 之間差約 1 ns | **依據不成立**：多 1 ns 在 run 之間的浮動內 |

## 學習

已寫入：
- `knowledge/sky130A_sky130_fd_sc_hd.md`「實測校準資料」：兩個 CPU 的 post-CTS 到 signoff 差距、hold buffer 代價、最差路徑組成、clock latency 分佈、長線上限實驗。
- `signoff-criteria` 經驗紀錄：LibreLane FAIL 時 checker 沒跑；上限檔從另一個 CPU 複製；setup 餘量違反推導方法。
- `drv-timing-closure` 經驗紀錄：第 4 次 harden 與長線上限實驗。

提給使用者決定（都還沒改）：
1. **setup 餘量與 hold 修復的衝突**：差距大部分出現在繞線之後。候選做法是開 `RUN_POST_GRT_RESIZER_TIMING`，讓 resizer 在 global routing 後用繞線估計的寄生再修一次 setup（LibreLane 標為實驗性、可能變慢，`flows/classic.py` 159–163 行），先用單步實驗量效果。
2. **slew 上限**：單步實驗比較 `set_max_transition` 0.70 與 0.75（PDK 預設）。
3. **`timing__unannotated_net__count`**：建立 Hazard3 golden 時，依 Hazard3 的組成重新推導並寫明。
4. **週期**：在 1、2 有結果之前，不建議再加週期。
5. **腳本改進**：`review_criteria.py` 加報半週期路徑（sram0 下降緣送出）的 slack，才能判斷 DCD 預算。
