# 流程回顧：Phase 3.5、4、5，哪些事做得太晚才看

日期：2026-10-14。範圍：Phase 4（2026-10-04）、Phase 3.5（2026-10-04 晚～10-05）、Phase 5（2026-10-05 晚～10-08）。只讀檔案與 git，沒有跑 EDA 工具。時間都是從 commit 時間粗估（`git log --date=iso`），包含人不在機器前的時間。

## 結論（最重要的 5 項）

1. **SRAM 低溫讀取失敗：問題不在「把 −40°C 放進 signoff corner」，而在「選定 macro 之前沒有先在規格的整個 PVT 範圍做 SPICE 讀寫檢查」**。ss_n40C_1v60 是 Phase 4 為了標準元件的溫度反轉加的（10-04），讀取失敗是 Phase 3.5 特性化時才發現的（10-05）。正因為有這個 corner，才順帶發現 ss 25°C 1.60 V（不是 STA corner）也會讀錯。如果拿掉 corner，矽上的失敗還在，只是被藏起來。網表從 Phase 0 就在 PDK 裡，Phase 0 也已知道 OpenRAM 的矽量測只到 ≥ 1.7 V（`project-plan.md` 168 行），而 LibreLane 的 ss corner 是 1.60 V。所以這個風險最早在 Phase 0 讀資料就能看出來，Phase 1–3 跑大約半天的讀寫模擬就能確認。
2. **三次加長週期（40→42→43→44 ns），都由 ss_n40C 的 corner 決定**。拿掉這個 corner 的話，三次都會 PASS（ss_100C 分別是 +0.07、+0.47、+0.955 ns）。但造成差距的是標準元件與 clock tree 的溫度反轉，跟 SRAM 能不能動無關。該提早做的是：在 Phase 0 的規格裡由使用者明確決定操作溫度（Caravel 的規格是 Tj −40～100°C），並附上 corner 的代價（只重跑 STA 做 what-if）。
3. **CTS 把 SRAM 的 clock 延後去對齊 flip-flop**：Phase 4 就看到了，當時判定「沒有設定可以關」。直到 Phase 5 才用 OpenROAD 的 `-no_insertion_delay` 解決。這期間它造成了 Phase 4 的 hold 餘量 0.3 ns、Phase 3.5 的 42→43 ns（推測），以及 Phase 5 PicoRV32 harden FAIL 與 A–D 四組實驗。修好之後，週期和 0.3 ns 都沒有回頭重新評估。
4. **resizer 停不下來，前後發生 4 次**（Phase 3、3.5、4、5），到 Phase 5 才找到根因：resizer 會換上推不動負載的弱 cell。Phase 4 的繞法是「resizer 只看 9 個 corner」，結果 Phase 5 換上 Hazard3 後 setup 差 −4.158 ns。這其實是 library 的 QA：在 Phase 2 就能用 `check_weak_cells.py` 這種查表檢查（幾分鐘）抓到。
5. **放寬的依據只在一個設計上量過，換設計時沒有重新驗證**：IR 只判 nom_tt（依據是在 PicoRV32 量到的 11.46 mV）、resizer 用 0.6 ns 餘量代替 ss_n40C（依據是 PicoRV32 的 0.44 ns 差距）、golden 誤差（依據是 Phase 2 的 3 次 run）。這三項都在 Phase 5 換成 Hazard3 時失效，造成多一輪 PDN 修改、兩次重建 golden、兩輪 regress。

---

## 一、總表

「花了多少」是 harden 次數、regress 次數或 commit 時間（粗估）；「放寬」指門檻、誤差表、佔位值、餘量、已知限制、週期。

| # | 問題（白話） | 花了多少或放寬了什麼 | 什麼時候發現（Phase、commit） | 最早可以在哪裡發現、用什麼檢查 | 提早的成本 | 證據 |
|---|---|---|---|---|---|---|
| 1 | PDK 預建 SRAM 在低溫、ss 1.60 V 室溫時讀成前一次的值 | **放寬**：ss −40°C 用佔位 .lib（STA 在這個 corner 對 SRAM 沒有意義），列為頭號下線風險，帶過 Phase 3.5、4、5 共 3 個 Phase；Phase 6 要做 patch 0001、`clk1` 改 RTL（計畫估 2–3 天）。診斷當天先浪費 6 個各約 25 分鐘的模擬（探測節點名稱錯）；ss 25°C 1.60 V 是獨立審查才補上的 | Phase 3.5，2026-10-05 特性化 ss −40°C 時（`ccc536c`、`38e85cb`） | **Phase 0**：把供應商驗證過的範圍（OpenRAM 矽量測 ≥ 1.7 V、室溫；PDK .lib 只有 TT 的解析模型）和 signoff 的 PVT 對照，就能看到 1.60 V 與 −40°C 都沒人驗證過。**Phase 1–3**：對 PDK 附的網表做 PVT 讀寫 sweep，包含 corner 之間的溫度、連續兩次讀到不同值 | 對照資料約 1 小時。讀寫 sweep 第一次做約 0.5–1 天（修剪網表與 deck，Phase 3.5 在 10-04 晚上試跑）；現在有 repo 的腳本，約 1–2 小時（推估） | ADR-0010 72–105、176 行；`openram-macro-characterization` 經驗紀錄 224–225 行；`project-plan.md` 59、168 行；ADR-0018 19–24、46–49 行；`docs/phase_exit/phase6.md` 89–90 行 |
| 2 | SRAM 讀出資料在下一個上升緣後約 1 ns 就被拉回（廠商 .lib 沒有這條 hold 弧） | Phase 3.5 加了 `rising_edge` hold 弧。它加上 0.3 ns 的 hold 修復餘量，在 32 條 `rdata_q` 前各插一顆 delay cell，害 setup 差 −0.066 ns，**週期 42→43 ns**（使用者決定） | Phase 3.5 試跑，2026-10-04（ADR-0010 查證 5）；造成 FAIL 是在 harden 2（`3e9b011`） | 跟 #1 同一次讀寫模擬：看 dout 在 clock 兩個邊緣後的波形。Phase 3 就能把 hold 弧放進 padded.lib | 包含在 #1 的成本裡 | ADR-0010 27 行；ADR-0004 17–23 行；`docs/phase_exit/phase3_5.md` 64 行 |
| 3 | 溫度反轉 corner（`ss_n40C_1v60`）到 Phase 3 結尾的 criteria review 才發現，之後它決定了每一次加長週期 | **週期 40→42**：min_ss_n40C −0.42，ss_100C +0.07。**42→43**：min_ss_n40C −0.066，ss_100C +0.47。**43→44**：max_ss_n40C −0.381，ss_100C +0.955（harden 2）。另外帶出 ADR-0013 與 `RSZ_CORNERS` 的問題（#4）。picorv32_core 到現在仍只看 9 個 corner | Phase 3 結尾的 review（`d31b52b`，10-03 23:41），Phase 4 加入（`002dd1a`，10-04 09:31） | **Phase 0／1**：掃描 PDK 所有 .lib，比較同一電壓、不同溫度的延遲（`signoff-criteria` 第 95 行的規則就是這個，但這條規則是事後才寫的）。**Phase 2**：在第一份網表上只重跑 STA，比較有沒有這個 corner 時的最小週期，請使用者決定操作溫度 | 掃描 .lib 不到 1 小時；STA what-if 幾分鐘 | `docs/notes/signoff_criteria_soc_top.md` 26、112 行；ADR-0004 11、21、27 行；`drv-timing-closure` 經驗紀錄 117 行；`pnr/picorv32_core/config.json`（沒有 `STA_CORNERS`） |
| 4 | resizer 停不下來（換上推不動負載的弱 cell `a2111oi_1` 等） | 發生 4 次：Phase 3 soc_explore6（26 分鐘以上）、Phase 3.5 harden 1（75 分鐘，原因是 #6）、Phase 4 harden 1（35 分鐘以上）、Phase 5 harden 1（108 分鐘、92.9 GB）。**Phase 4 的繞法是放寬**：resizer 只看 9 個 corner，再用 setup 餘量 0.6 ns 和 max transition 0.70 ns 補 → Phase 5 Hazard3 在 ss_n40C 差 −4.158 ns（81 條）→ ADR-0013。Phase 5 從 harden 1 到修好（`2251c4a`）約 26 小時 | 根因在 Phase 5 找到（2026-10-06，ADR-0012）；Phase 4 那次是否同一原因，只是推測 | **Phase 2**（第一次把 resizer 的 slew 餘量調到 30%）：對 resizer 可用的每個 cell，在每個 signoff corner 和每種修復餘量下查表，確認推得動最小的 buffer（就是後來的 `check_weak_cells.py`）。**Phase 4** 遇到 15 個 corner 跑不完時，應該先找根因，不要直接減少 corner | 查表檢查幾分鐘（腳本現在已有）。Phase 4 找根因約半天（Phase 5 實際花的時間，包含單步重跑實驗） | ADR-0012 全文；`docs/notes/repair_design_loop.md` 114–120 行；ADR-0013 7–13、41 行；`multicorner-sta` 經驗紀錄 57 行 |
| 5 | CTS 把 SRAM 的 clock 延後去對齊 flip-flop（10 顆 `delaybuf`，下降緣比上升緣慢） | Phase 4 harden 2、3 看到，因為「LibreLane 的變數關不掉」，改成 **hold 修復餘量 0.3 ns**，列為已知限制 5。Phase 3.5 的 32 顆 hold delay cell 與 **42→43 ns** 有一部分來自它（推測：ADR-0016 實驗 D 拿掉對齊後，這 32 顆都不見了，但沒有在 42 ns 重跑過）。Phase 5 PicoRV32 harden 1 FAIL（−0.113），又做了 A–D 四組實驗。修好後 Hazard3 的 setup 從 +0.530 變 +1.116 ns | Phase 4，2026-10-04（`cts-clock-tree` 經驗紀錄 54 行）；Phase 5 才解決（`adac1a9`，10-07） | **Phase 3**（第一次帶 macro harden）：CTS 之後報出 macro clock pin 的上升緣與下降緣 latency，和 flip-flop 比較，並數 `delaybuf`。**Phase 4**：工具的設定關不掉時，要查到底層工具的指令選項（OpenROAD `clock_tree_synthesis -no_insertion_delay`），再決定是不是真的「沒有辦法」 | Phase 5 從實驗到寫好 plugin 約 2 小時（`c976976` 14:10 → `adac1a9` 16:09） | ADR-0016 全文；`docs/phase_exit/phase4.md` 98、167 行；`pnr/soc_top/config_hazard3.json` 188 行（0.3 ns 的理由仍寫著「sram0 clock delayed by CTS latency balancing」） |
| 6 | SRAM .lib 的延遲對負載斜率太大（等於 60–140 kΩ 的驅動能力），resizer 一直插 buffer | harden 1 跑了 75 分鐘才異常結束；單步重跑 4 種 .lib 才找到原因。**放寬**：延遲表改成不隨負載變化（每列取最大值） | Phase 3.5 harden 1（`ccc536c`，10-05） | **.lib 產生後、harden 前**：在 view QA 檢查 macro 輸出弧的等效驅動電阻（Δdelay／Δload），是否落在標準元件的範圍。目前只寫在 `gen_char_lib.py` 的註解裡，`check_macro_views.py` 沒有這項檢查（已用 grep 確認） | 檢查幾分鐘；寫腳本約 1 小時（推估） | ADR-0010 147–161 行；`ip/sram/char/gen_char_lib.py` 29–30 行 |
| 7 | IR：flow 只判 nom_tt，依據是在 PicoRV32 的 Phase 3 版圖量到的最壞組合 11.46 mV。供電點與切換活動也都是假設 | **放寬**：Phase 4 決定只判 nom_tt。Phase 5 獨立審查實測 Hazard3 最壞組合 25.75 mV，超過 20 mV → met5 1.6→4.8 µm、兩個 CPU 重新 harden、重建 golden、再跑兩輪 regress（`1dee974`→`71b1454`，約 14 小時，和修 checker 漏洞重疊）。Phase 7 才用 Caravel 真實的 pad（只從上側供電時 143 mV）和 max power pattern（預設切換率高估約 2.2 倍） | Phase 5 結尾（2026-10-08） | **Phase 4**：(a) 最壞組合 IR 從一開始就做成每次 harden 都判的 checker，不要只依靠一次研究的結果；(b) Caravel 的電源 pad 位置是公開、固定的資料，Phase 4 寫「Phase 7 才知道」，其實當時就能查；(c) 用 GL 模擬錄 max power pattern 的 VCD（Phase 4 已有 GL 模擬） | (a) 約半天（`ir_worst.py`）；(b) 查文件約 1–2 小時；(c) 寫 firmware 加錄 VCD 約半天（Phase 7 的經驗） | `docs/notes/ir_worst_case_soc_top.md` 7、36 行；ADR-0017 1–20 行；`docs/phase_exit/phase5.md` 95–111 行；ADR-0019 87、109 行 |
| 8 | golden 誤差的依據太少：Phase 2 只在 picorv32_core 跑了 3 次，結論是「只有 detailed routing 不可重現，而且只會改變連續量」 | Phase 4 regress 2 FAIL（繞線器中間各輪的 DRC 數）→ 誤差 ±100。Phase 5 Hazard3 harden 6、7 的 golden 比對 FAIL（61、11 個 metric）→ ADR-0015 再補 2 組約 23 分鐘的樣本，誤差放寬到 ±1310、cell 數 ±70。PicoRV32 暫用 Hazard3 的誤差，被審查抓到 → `5aaf036` 的 regress FAIL → 再補 2 次 harden 當樣本 → 再跑兩輪 regress | Phase 4（`c635ffb`）、Phase 5（`4d309de`、`5aaf036`） | **每個設計第一次建 golden 時**（soc_top 是 Phase 3，Hazard3 是 Phase 5 開頭）：同設定至少取 4 個樣本，並用單步重跑找出哪些步驟不可重現（第 41 步的 global routing 約 19% 會不同） | 每個設計多 2–3 次 harden，約 1–1.5 小時機器時間 | `docs/phase_exit/phase4.md` 75 行；ADR-0015 3–30 行；`docs/phase_exit/phase5.md` 37、217 行；`signoff-checker-qualification` 經驗紀錄 146、151 行 |
| 9 | 換成 Hazard3 時，沒有先單獨看它在各 corner 的時序 | Hazard3 harden 1–5 依序是：停不下來（#4）、−4.158、−0.381（→ 44 ns）、−1.131（繞線後才出現的差距 → ADR-0014）、PASS。**exit criteria 7b「flow 設定只需改 design 層」未達成**，使用者接受為與計畫不同 | Phase 5，10-06～10-07 | **Phase 5 開頭**：Hazard3 單獨合成並 harden（或至少在合成網表上跑 15 個 corner 的 STA），找出 ss_n40C 對 ss_100C 比例特別大的長路徑（這條差了 15%） | 一次單獨 harden 約 30–40 分鐘 | ADR-0013 7–13 行；ADR-0014 5–15 行；`docs/phase_exit/phase5.md` 52、119–129 行 |
| 10 | 獨立審查放在乾淨 checkout 的 regress **之後** | 每個 Phase 都在 regress 之後才找到 checker 漏洞：Phase 4 有 10 個（修完再跑 regress）、Phase 3.5 有 12 個（延到 Phase 5 開頭修）、Phase 5 有 8 個再加上 IR（再跑兩輪 regress）。每輪約 2 小時 | 各 Phase 結尾 | **寫好 checker 的時候**：在 regress 之前就請另一個 agent 去找漏洞（植入錯誤，確認 checker 抓得到） | 每批 checker 約 1 小時的 agent 時間 | `docs/phase_exit/phase4.md` 177–201 行；`phase3_5.md` 204–227 行；`phase5.md` 327–349 行 |
| 11 | regress 因為流程本身的問題 FAIL，只好重跑 | Phase 3.5：P17 改完沒有先跑（18/25 後 FAIL）。Phase 4：GL 模擬的時限是照 RTL 速度算的（regress 3 FAIL）。Phase 5：乾淨 checkout 裡沒有 xPack（`941e1cb`）。每次浪費約 0.5–2 小時 | 各 Phase 的乾淨 regress | 開跑之前：改過的 checker 先在現有的 run 上跑正常對照與 negative test；在乾淨 worktree 先跑 `env-check-flow`；時限用實測的 GL 速度乘上負載餘量 | 每項幾分鐘（規則已補進 `phase-exit-review`、`flow-regression-reproducibility` 規則 9） | `docs/phase_exit/phase3_5.md` 11、129 行；`phase4.md` 14–17、76 行；`phase5.md` 35、253 行 |
| 12 | 補償用的設定在原因消失後沒有回收 | 週期 44 ns（43 ns 的原因 #2、#5 已由 ADR-0016 消除；44 ns 的原因後來由 ADR-0014 處理）；hold 餘量 0.3 ns（原因是 #5）；PnR 的 max transition 0.70（原因是 resizer 看不到 ss_n40C，ADR-0013 寫「等這次 harden 的結果再評估」）。三項到現在都還在 config 裡。照斜率 0.45 ns／ns 推算，43 ns 時 PicoRV32 約 +0.34、Hazard3 約 +0.66 ns（**推算**，run 之間的浮動可達約 1 ns，要跑一次才知道） | 這次回顧 | **原因移除的那一刻**（ADR-0013、0016 定案時）：對每個補償設定做 what-if，看能不能拿掉 | 只重跑 STA 幾分鐘；確認一次 harden 約 30 分鐘 | `pnr/soc_top/config_hazard3.json` 53–54、188 行；`pnr/soc_top/pnr.sdc` 14 行；ADR-0013 36 行；ADR-0016 68 行；ADR-0004 11 行（斜率） |

### 放寬一覽（對應上表）

| 放寬 | 現況 | 上表 |
|---|---|---|
| 週期 40→42→43→44 ns | 仍是 44 ns，沒有回頭評估 | #3、#2、#5、#9、#12 |
| ss −40°C 的 SRAM 佔位 .lib | Phase 6 換成自產 macro 後解除 | #1 |
| SRAM 延遲用下限（tt／ff 10 ns、ss 15 ns）和 × 1.6 代替寄生量測 | 仍由下限決定週期；Phase 6 萃取後發現 × 1.6 不夠（實際 2.0 倍），靠下限才蓋住（ADR-0018 155 行） | 當時無法更早知道（見第三節） |
| dout0 transition 維持 0.5 ns（實測 1.1–1.3，後來是 2.2 ns） | 已知限制，what-if 仍 PASS | 當時無法更早知道 |
| dout0 `max_capacitance` 0.02756 → 0.05 pF | 有特性化的依據 | — |
| 延遲表不隨負載變化 | 偏保守 | #6 |
| resizer 只看 9 個 corner，用餘量 0.6／0.70 補 | Phase 5 改成也看 ss_n40C；0.70 還在 | #4、#12 |
| IR 只判 nom_tt | Phase 5 改判最壞組合，Phase 7 再改成慢 corner 加 max power pattern | #7 |
| golden 誤差（中間各輪 DRC 數 ±100→±1310、版圖數量 ±70 等） | 依實測樣本 × 5 | #8 |
| GRT-0229／GRT-0116 用有上限的重試繞過 | 根因沒有查 | 當時無法更早知道 |
| exit criteria 7b 改用 7a 當判準 | 使用者接受 | #9 |
| `neg-char` 不在 regress 裡 | 不變 | — |

---

## 二、使用者的例子：SRAM 低溫讀取失敗與 signoff corner

### 2.1 時間線（有證據的部分）

| 時間 | 事件 | 出處 |
|---|---|---|
| 10-03（Phase 0 計畫） | 已經知道：PDK 預建 SRAM 只附一份 TT 的解析模型 .lib；OpenRAM 的矽量測在 ≥ 1.7 V 才不出錯（室溫，1 KB 那顆）；電晶體級網表在 PDK 裡 | `project-plan.md` 59、168 行；ADR-0010 15 行 |
| 10-03（Phase 3） | 9 個 corner 全部用 padded.lib（假設值），ss 的 derate 1.5 | ADR-0007 8–31 行 |
| 10-03 23:41（Phase 3 結尾） | criteria review 發現溫度反轉：1.60 V 時 `dfxtp_1` 在 −40°C 比 100°C 慢 11%，PDK 有 ss_n40C_1v60 但沒用。**理由只跟標準元件有關** | `d31b52b`；`docs/notes/signoff_criteria_soc_top.md` 26 行 |
| 10-04 09:31（Phase 4） | 加入 ss_n40C_1v60 與 ff_100C_1v95，共 15 個 corner。SRAM 仍用 padded.lib，`*ss*` 的 derate 1.575 | `002dd1a`；ADR-0007 33–37 行 |
| 10-04 22:32 | Phase 3.5 開始：用 ngspice 量 PDK 的網表。5 個 PVT 就是 15 個 corner 裡的 5 組 PVT | `d60550f`；ADR-0010 35–40 行 |
| 10-05 | ss −40°C 每次讀取都錯。先跑的 6 個各約 25 分鐘的診斷模擬沒有波形（探測節點名稱錯）。再量 sense amp 內部節點：它沒有預充電，column mux 只有 NMOS。補測 tt −40°C、ss −40°C 1.70–1.95 V，都讀錯 | `openram-macro-characterization` 經驗紀錄 224–225 行；ADR-0010 72–100 行 |
| 10-05 14:01 | 用完整網表確認不是修剪網表造成的（ss −40°C 1.70 V 失敗方式相同；1.60 V 在 169.7 ns 報 Timestep too small） | `38e85cb`；ADR-0010 103 行 |
| 10-05 下午 | 獨立審查重算波形，發現 **ss 25°C 1.60 V 也全錯**（原本漏列）。「只有低溫才失敗」不成立 | `docs/phase_exit/phase3_5.md` 179 行；ADR-0010 101 行 |
| 10-05 | 使用者決定 5：ss −40°C 用佔位 .lib（setup／延遲用 ss 100°C 的數字，hold 弧取所有 PVT 最早的值 × 0.9），列為頭號下線風險。決定 8：25°C 的界線不再模擬 | ADR-0010 70 行；`phase3_5.md` 166–169 行 |
| 10-05～10-08（Phase 5） | 帶著佔位 .lib 收斂時序。ADR-0013 寫明：SRAM 路徑在 ss_n40C 的結果只代表佔位值 | ADR-0013 54–56 行 |
| 10-08～10-10（Phase 6） | 自產 macro 用預設設定也重現同樣的失敗 → `words_per_row = 1` 讀得對，但放不進 die → 網表 what-if 比較 W1／W2 → patch 0001（sense amp 輸入端預充電）→ tt 25°C 又讀錯（port 1 的 chip-select DFF 從沒被時脈鎖存）→ `clk1` 改接系統時脈（改 RTL）→ 7 個條件都讀對。萃取網表在 10-11 確認 | ADR-0018 19–24、33、46–52 行；`phase6.md` 89–90 行 |

確認與解決花的輪數：Phase 3.5 診斷約一天內做了 3 輪（6 個失敗的模擬、節點量測、完整網表）。後來審查又補了 1 個條件。Phase 6 修正走了 4 步（重現、wpr1、W1／W2 what-if、patch 加 `clk1`），再加 1 次萃取確認。

### 2.2 signoff corner 的組成，以及 SRAM .lib 在每個 corner 的來源

| PVT（× min／nom／max RC） | 何時、為什麼加入 | Phase 3–4：padded.lib | Phase 3.5–5：預建 macro 的 SPICE .lib | Phase 6：自產 macro |
|---|---|---|---|---|
| tt_025C_1v80 | LibreLane 預設 | 假設值，延遲 10 ns | 實測 × 1.6，padded 值當下限 | 實測 |
| ss_100C_1v60 | LibreLane 預設 | 假設值 × 1.575（Phase 4 起） | 實測 × 1.6，下限 15 ns | 實測 |
| ff_n40C_1v95 | LibreLane 預設 | 假設值 × 0.665 | 實測 | 實測 |
| **ss_n40C_1v60** | Phase 4（`002dd1a`），標準元件的溫度反轉 | 同 ss | **佔位值**（ss 100°C 的數字，hold 弧取最早的值） | 實測（讀得對） |
| ff_100C_1v95 | Phase 4，快的一側對稱補上 | 同 ff | 實測 | 實測 |

出處：`pnr/soc_top/config_hazard3.json` 137 行；ADR-0007；ADR-0010 108–145 行；`phase6.md` 54 行。

### 2.3 評估假設：「如果早知道低溫問題，一開始就不該建議把它放進 signoff corner」

**有證據支持的事實**：

1. **corner 是在知道讀取失敗之前加的，加的理由跟 SRAM 無關**（2.1 時間線：10-04 加入，10-05 才發現）。
2. **這個 corner 反而是讓問題被發現的原因**。Phase 3.5 是照 15 個 corner 裡的 5 組 PVT 去量。如果沒有 ss_n40C，只會量 tt、ss 100°C、ff，這三個都讀得對。ss 25°C 1.60 V 和 tt −40°C 1.60 V 是在診斷 ss −40°C 時順帶測到的，它們都不是 STA corner（ADR-0010 176 行：「ss 25°C 不是 STA corner，STA 完全看不到這個失敗」）。
3. **拿掉 corner，矽上的失敗不會消失**。corner 代表晶片實際的操作條件。這顆晶片放在 Caravel 上，規格是 VCCD 1.62–1.98 V、Tj −40～100°C（`signoff-criteria` 44 行；出處是 caravel-harness 的 maximum-ratings）。
4. **這個 corner 的確很貴，但貴在標準元件**。三次加長週期與 ADR-0013 都由 ss_n40C 決定（第一節 #3）。Hazard3 的 −4.16 ns 是乘除法單元的路徑，沒有經過 SRAM。這些代價和 SRAM 能不能讀無關。
5. **即使把規格縮到 ≥ 0°C，預建的 SRAM 還是會失敗**：ss 25°C 1.60 V 讀錯，ss 60°C 1.60 V 才正常，25–60°C 之間的界線沒有模擬（ADR-0010 101 行）。1.62 V（Caravel 最低供電）也沒有模擬。所以只限制溫度不夠，還要把最低電壓拉到約 1.7–1.8 V，這要看板子與 Caravel 的穩壓器能不能保證（沒有查證）。

**各種做法與代價**：

| 做法 | 效果 | 代價 | 評估 |
|---|---|---|---|
| A. 實際的做法：保留 corner，SRAM 給佔位 .lib，列為下線風險，Phase 6 修 | 風險看得到，最後在 Phase 6 解決 | 3 個 Phase 都帶著佔位值；預建 macro 的特性化與整合，Phase 6 又重做一次（`arvinsa-rtl-gds-flow.md` 170 行） | 可以用，但發現得太晚 |
| B. 拿掉 −40°C 的 corner（使用者的假設） | 週期大概能維持 40–43 ns（拿掉之後，三次加長時 ss_100C 都 PASS） | **矽上的讀取失敗還在**，而且 ss 25°C 1.60 V 的失敗會完全看不到；標準元件在 −40°C 的 setup 沒有檢查（Hazard3 差 4 ns）；等於把規格縮到不含 −40°C 卻沒有寫下來 | 不建議，除非同時做 C |
| C. 在規格上限制操作條件（例如只在實驗室室溫測，或 Tj ≥ 0°C 且 VDD ≥ 1.8 V） | 規格明確縮小後，拿掉 corner 才合理；能省下 #3 的週期代價 | 要由使用者決定；預建 SRAM 還要把電壓拉高，板子與 Caravel 能不能做到沒有查證；晶片的用途受限 | 測試晶片可以考慮，但必須在 Phase 0 決定，並把代價寫進 ADR |
| D. **選定 macro 與 corner 之前，先在規格的整個 PVT 範圍做 SPICE 讀寫功能 QA**（包含 corner 之間的溫度與最低電壓） | Phase 1–3 就知道預建 macro 不能用，直接改走自產加修讀取電路，或換別種 memory | 半天到一天（第一次做）；之後的 macro 只要 1–2 小時 | **建議**：成本最低，而且不影響規格 |
| E. 改用別種 memory（例如 flip-flop 或 latch 做的 RAM） | 不會有 sense amp 的問題 | 面積大很多（2 KB）；這個 repo 沒有評估過（**推測**） | 只列為選項 |

**結論**：不建議因為「macro 在某個 corner 不能動」就拿掉那個 corner。corner 應該由操作規格決定（做法 C，Phase 0 由使用者決定，附上代價）。macro 則要在選定之前，在整個規格範圍做功能 QA（做法 D）。使用者的直覺（「這件事應該更早知道」）是對的，只是該提早的是 macro 的 QA，不是 corner 的取捨。

### 2.4 照 repo 實際的時間線，提早做能省下什麼

| 提早到 | 做什麼 | 成本 | 會改變什麼 | 不會改變什麼 |
|---|---|---|---|---|
| Phase 0（10-03，寫計畫時） | 對照資料：OpenRAM 矽量測 ≥ 1.7 V、室溫；OpenRAM 預設特性化只做 0／25／100°C、1.7–1.9 V（ADR-0018 24 行）；PDK .lib 只有 TT。和 ss 1.60 V、Caravel Tj −40°C 比 → 標出「這些 PVT 沒有人驗證過」 | 約 1 小時 | 計畫會把「macro 的 PVT 讀寫檢查」排在 Phase 1–3，而不是 Phase 3.5 的「可選」（`project-plan.md` 428 行） | — |
| Phase 1–3（10-03） | 用 ngspice 對 PDK 網表做讀寫 sweep：tt／ss／ff × {−40, 0, 25, 60, 100}°C × {1.60, 1.62, 1.80, 1.95} V，連續讀到不同的值，並看 dout 在兩個 clock 邊緣後的波形 | 0.5–1 天（Phase 3.5 實際：10-04 晚上試跑，10-05 中午前完成 5 個 PVT 的特性化） | (1) Phase 3 就知道 ss −40°C、ss 25°C 1.60 V、tt −40°C 讀錯 → 在 Phase 3 決定「改走自產並修讀取電路」或「縮規格」，不用把佔位 .lib 帶過三個 Phase。(2) padded.lib 從 Phase 3 就有 hold 弧（#2），hold 與 CTS 對齊的交互作用會在 Phase 4 和 #5 一起出現，有機會一次處理（**推測**）。(3) 預建 macro 的特性化（Phase 3.5 約 19 小時）可以只做到 go／no-go，不用做完整的 .lib；`arvinsa-rtl-gds-flow.md` 170 行說「同樣的特性化與整合做了兩次」 | Phase 6 的讀取電路修正（patch 0001、`clk1`）照樣要做，只是提早；ss_n40C 帶來的週期與 resizer 代價（#3、#4）照樣存在，因為那是標準元件的問題 |

---

## 三、當時無法更早知道的項目

| 項目 | 理由 |
|---|---|
| GRT-0229、GRT-0116 隨機中止（Phase 3、5） | OpenROAD 的隨機錯誤，同一份輸入重跑 4 次裡有 2 次中止（`docs/notes/grt0229_repro.md` 24–31 行）。只有跑了才會遇到，而且根因在工具裡面。有上限的重試是合理的繞法（但根因一直沒查，見 `phase5.md` 284 行） |
| resizer 用第一個讀進來的 .lib（tt）挑 cell 尺寸 | 這是工具內部的行為，要用單步重跑加除錯輸出才看得到（ADR-0012 原因 2）。注意：通用的 library QA（#4 的查表檢查）不需要知道這個機制，所以「停不下來」本身是可以提早防的 |
| Hazard3 的 run 之間的變動，比 PicoRV32 大很多 | 這跟設計有關（第 41 步的 global routing 約 19% 不同），只有用 Hazard3 實際跑才量得到。可以提早的是「每個設計建 golden 時就取樣」（#8），不是數字本身 |
| 繞線後 setup 比 CTS 後的估計差約 1 ns（ADR-0014） | 要跑完整的 flow 才看得到；而且是 Hazard3 的長路徑才明顯。PicoRV32 在 Phase 4 沒有出現 |
| dout0 transition 兩個模型差 5 倍；× 1.6 是否涵蓋寄生 | 需要整顆版圖萃取後的網表才能回答。Phase 3.5 的萃取網表因為負值修正電容無法模擬，根因到 Phase 6 才確認（ADR-0010 已知限制 3、5；ADR-0018 決定 20） |
| 讀取失敗的電路機制（sense amp 沒有預充電、column mux 只有 NMOS） | OpenRAM 的 issue 沒有人回報過低溫或低電壓的讀取失敗（ADR-0018 23 行），要做 SPICE 才看得到。所以「失敗本身」只能靠模擬發現。但「沒有人驗證過這些 PVT」這個訊號，Phase 0 就有（見 2.4） |
| 多執行緒 detailed routing 不可重現 | Phase 2 第一次跑就量到了，而且花的成本小 |
| Hazard3 的功耗約為 PicoRV32 的兩倍 | 跟設計有關，要合成或 harden 後才知道。可以提早的是「IR 的依據不要沿用另一個設計」（#7） |

---

## 四、建議加進 `arvinsa-rtl-gds-flow.md` 的提早檢查

「現況」欄寫這個 repo 已經有的部分。多數項目的檢查本身已經存在，問題在於做的**時間點**太晚，或只寫在某個 skill 裡，沒有放在流程的步驟中。

| # | 放在哪個步驟 | 做什麼 | 通過條件 | 對應問題 | 現況 |
|---|---|---|---|---|---|
| E1 | 4.1 規格與計畫 | 操作條件（Tj 範圍、VDD 最低／最高）由使用者明確決定，寫進 ADR。corner 清單由它推出，並掃描 PDK 的 .lib 找溫度反轉 | ADR 寫明範圍與出處；每個 corner 都對應到規格的某個角落；有溫度反轉時，反轉 corner 也在清單裡 | #3、#1 | 溫度反轉的掃描寫在 `signoff-criteria` 95 行，但流程 4.1 沒有這一步 |
| E2 | 4.1，第一份網表出來之後（本 repo 是 Phase 2） | 對 corner 清單做代價 what-if：只重跑 STA，比較有沒有某個 corner 時的最小週期，交給使用者確認規格 | 每個「會決定週期」的 corner 都有代價數字，使用者確認過 | #3 | 沒有 |
| E3 | 4.1 選定 macro 之前（新增，放在 4.3 第 1 項之前） | 對照資料：供應商驗證過的 PVT 範圍（矽量測、memory compiler 預設的特性化 corner、廠商 .lib 是解析模型還是實測），和 E1 的規格範圍比較 | 規格裡的每個角落，要嘛有供應商資料，要嘛標成「未驗證 → 必須做 E4」 | #1 | 沒有 |
| E4 | 4.3 第 4 項，**移到 macro 選定之前**（go／no-go），不是整合之後 | 在規格範圍內的格點（含 corner 之間的溫度、最低供電，例如 1.62 V）做 SPICE 讀寫：連續讀到不同的值、寫之後馬上讀、未用的 port 照實際 SoC 的接法；同時記錄輸出在 clock 兩個邊緣後的波形 | 每個格點都讀寫正確；輸出在哪個邊緣之後會變化都寫進 .lib 的時序弧（例如 `rising_edge` hold）。有任何一點失敗，先請使用者決定（換 macro、修電路、縮規格），再整合 | #1、#2 | 4.3 第 4 項與 `hard-macro-integration` 規則 5 已經有「每個 corner 先證明功能」，但放在取得 macro 之後，而且只寫 STA corner 加「corner 之間的溫度」，沒有寫「選定之前」和「最低供電」 |
| E5 | 4.3 第 2 項 view QA | macro .lib 的輸出弧算等效驅動電阻（Δdelay／Δload），和標準元件的範圍比；也檢查延遲表是否單調 | 落在標準元件的範圍內（本 repo 的例子：60–140 kΩ 必須 FAIL，PDK 解析模型的約 5.6 kΩ 必須 PASS）；negative test 植入一份斜率過大的 .lib | #6 | `check_macro_views.py` 沒有這項（grep 確認） |
| E6 | 4.5 約束（第一次 harden 前） | library QA：在**所有 signoff corner** 與每種修復餘量下，跑 `check_weak_cells.py` 的查表檢查（不只 resizer 有看的 corner） | 列出的 cell 都已排除，或確認推得動最小的 buffer | #4 | 4.6 開跑前已經在檢查，但只看 resizer 的 corner；要提早到 4.5，並涵蓋 signoff corner |
| E7 | 4.5 | resizer 看的 corner 預設等於 signoff corner；要拿掉某個 corner，必須有根因（不能只因為「跑不完」）加上 what-if，並在每次 harden 後的 criteria review 檢查「最差 setup／hold 的 corner 有沒有在 resizer 的 corner 裡」 | 沒有拿掉；或拿掉的每個 corner 都有 ADR、what-if 與 criteria review 的檢查列 | #3、#4、#9 | `review_criteria.py` 沒有這一列（**推測**，沒有逐行讀程式碼確認） |
| E8 | 4.4 子區塊單獨 harden，**換 core 時必做** | 新 core 單獨合成並 harden（至少跑全部 signoff corner 的 STA），列出 ss 低溫對 ss 高溫比例最大的長路徑 | 在目標週期、所有 corner 都 PASS，或已知差多少，進 SoC 之前請使用者決定 | #9 | 4.4 寫的是「可選」，而且只用在估面積 |
| E9 | 4.6，第一次帶 macro 的 harden | CTS 之後報出每個 macro clock pin 的上升緣與下降緣 latency，和接收端 flip-flop 比；數 `delaybuf`。flow 的變數關不掉某個行為時，要查到底層工具的指令選項，再決定是不是真的沒辦法 | 沒有對齊用的 buffer 鏈（本 repo 的結構判斷：連續 ≤ 2 級）；半週期路徑兩個邊緣的 latency 差已經列出 | #5 | `hard-macro-integration` 規則 6、`check_soc.py cts_macro_latency` 已有；「查底層工具選項」這條還沒有寫成規則 |
| E10 | 4.5（power signoff 的方法），在第一次 harden 前定好 | IR 用載具晶片真實的電源 pad（查載具文件）、慢 corner、CPU max power pattern；每次 harden 都判，**不能依靠在另一個設計量到的比例** | 每次 harden 都有判定列；供電模型的出處是載具的文件，不是假設 | #7 | Phase 7 已改（ADR-0019 決定 18–20、`ir_worst.py`、`ir_pattern.py`）；流程 4.1 已補「pad 階段查電源進入點」 |
| E11 | 4.6 golden | 每個設計第一次建 golden 時，同設定至少取 4 個樣本（完整 harden，或從不可重現的步驟重跑），量出每類 metric 的最大差異，再訂誤差；不能暫用別的設計的誤差 | 誤差有 ≥ 4 個樣本當依據，記在 golden README | #8 | `signoff-checker-qualification` 規則 5 只寫「至少重跑一次」 |
| E12 | 每個 Phase（新增「放寬與補償登記表」，放在 4.9 和每次 harden 後的 criteria review） | 每一項放寬或補償（加長週期、餘量、誤差、佔位值、只判某個 corner）都登記：原因、依據的量測、在哪個設計量的、什麼情況要重新驗證、回收的條件。換設計、換 macro，或原因被修掉時，逐項 what-if | 登記表裡沒有「原因已經不在、卻還沒評估」的項目；依據的設計等於現在的設計 | #7、#12、#4、#8 | 沒有（各項散在 ADR 與 config 註解裡） |
| E13 | 4.8 regression 之前 | 改過的 checker 先在現有的 run 上跑正常對照與 negative test；乾淨 worktree 先跑 `env-check-flow`；**獨立的 checker 漏洞審查放在 regress 之前**；時限用實測速度訂 | 三項都做過才開 regress | #10、#11 | 前兩項已寫進 `phase-exit-review`、`flow-regression-reproducibility` 規則 9；審查目前排在 regress 之後 |

### 優先順序建議

- **新專案一開始就要做**：E1、E3、E4、E6。成本都在 1 天以內，對應的是這三個 Phase 最貴的問題（#1、#3、#4）。
- **流程規則上的修改**：E12（放寬登記表）與 E7（resizer 的 corner）。這兩項用來防止「依據只在一個設計上成立」這類問題再發生，這也是 Phase 5 大部分重工的來源。
- **只要改 checker**：E5、E11、E9 的「查底層工具選項」。

---

## 出處與限制

- 讀過的檔案：`project-plan.md`；`docs/phase_exit/phase3_5.md`、`phase4.md`、`phase5.md`、`phase6.md`（部分）；ADR-0004、0007、0010、0012–0018（0018、0019 只讀了相關段落）；`docs/notes/signoff_criteria_soc_top.md`、`ir_worst_case_soc_top.md`、`repair_design_loop.md`、`grt0229_repro.md`（開頭）；skill `openram-macro-characterization`、`cts-clock-tree`、`drv-timing-closure`、`multicorner-sta`、`pdn-ir-drop`、`signoff-checker-qualification`、`signoff-criteria`、`hard-macro-integration` 的相關段落與經驗紀錄；`arvinsa-rtl-gds-flow.md` 第 3–4 節；`git log` 全部 130 個 commit。
- 標為「推測」「推算」的地方：#5 的 42→43 ns 可以避免（ADR-0016 是在 44 ns 驗證的）；#12 的 43 ns slack（用 ADR-0004 的斜率線性推算）；E7 的 `review_criteria.py` 沒有該列；做法 E 的面積；第 2.4 節的時間估計；Phase 4 第 1 次 harden 停不下來是不是弱 cell 造成的（ADR-0013 41 行寫明「未確認」）。
- commit 時間只能粗估工作量，因為包含等待與休息的時間。
