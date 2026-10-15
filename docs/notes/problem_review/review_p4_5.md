# 問題回顧：Phase 4、5 遇到的每一個問題，現在被捕捉在哪裡（2026-10-15）

起因：使用者 2026-10-15：「主要目的是把完整走過一次，先review一下所有遇到的問題與檢討哪些是要寫進skill與流程裡的」。本文件只涵蓋 Phase 4（2026-10-04 08:31–21:23）與 Phase 5（2026-10-05 20:22–10-08 15:39）。審查者沒有參與實作；只讀檔案與 git，沒有跑 EDA 工具或 make。

**讀過的來源**：`docs/phase_exit/phase4.md`、`phase5.md`；ADR-0011–0017，ADR-0007 的 Phase 4 補充、ADR-0009；`git log` 從 `9eca68d`（10-04 08:31）到 `ea075ae`（10-08 15:39）共 61 個 commit 的完整訊息（其中 10 個屬於同時進行的 Phase 3.5，`d60550f`–`e16465b`，只取與 Phase 4／5 有關的部分）；23 個 skill 中日期為 10-04 到 10-08 的經驗紀錄（扣掉 Phase 3.5 的列，約 95 列）與相關規則本文；`arvinsa-rtl-gds-flow.md`（以下稱「流程文件」）；`docs/relaxation_register.md`（以下稱「登記表」）；`docs/notes/flow_retro/README.md`、`retro_p35_5.md`（ADR-0020 的 19 條提早檢查 A1–E3）。捕捉狀態都用 grep 對過檔案內容。

**結果**：
- 問題共 **62 個**（Phase 4：29、Phase 5：33）。同一件事只列一次；Phase 3 的漏洞（Phase 4 開頭修的已知限制 12–16）與 Phase 3.5 的項目不列，除非在 Phase 4／5 又出現。
- 依「最強的那一層捕捉」分類：
  - 規則本文（或流程文件）＋自動防護（checker、negative test、hook）：**36**
  - 只有規則本文或流程文件，沒有自動防護：**19**
  - 只在經驗紀錄、exit review、ADR 或登記表：**6**
  - 都沒有：**1**
- 判定有缺口、建議寫回的：**11 項**（見最後一節）。其餘 51 個「不用動」。
- 和 ADR-0020 的 19 條提早檢查重疊的：**20 個**（表中「重疊」欄）。這些的「太晚才看」已由 ADR-0020 處理，本文件不重做，只核對捕捉位置。

**主要發現（白話）**：
1. Phase 4、5 的工具缺陷與 checker 漏洞，絕大多數已寫成 skill 規則並有 negative test；CLAUDE.md 規則 10 在 Phase 5 中途（10-07）才建立，之後補寫得很完整。
2. 真正沒被捕捉的，多半是**跨 Phase 重複出現、但每次只寫進經驗紀錄**的現象：機器資源（記憶體、Spotlight、磁碟、平行數）造成的假 FAIL 或被系統停掉；實驗證據放在 session 暫存或沒進版控的 worktree；resizer 失控每次都靠人發現（26–108 分鐘後）。
3. 幾個在本 repo 已修好、但新專案會重寫的東西（`run.sh` 在 flow FAIL 時也要跑 checker），只寫在本 repo 的程式與 skill 的一段說明，流程文件沒有要求。

**欄位說明**：
- 捕捉位置的代號：(a) skill 規則本文；(b) 只在 skill 經驗紀錄；(c) 流程文件；(d) 自動防護（checker、negative test、hook）；(e) 都沒有。登記表、ADR、exit review 另外寫明。
- 「代價」從 commit 時間與 exit review 推算，含等待時間，只能看量級，**都是估計**。
- 「根因」：已驗證＝有單步重跑、對照實驗或讀原始碼確認；推測＝文件自己標為推測或沒有實驗。

---

## 一、Phase 4（2026-10-04）

| 編號 | Phase | 問題（白話） | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P4-01 | 4 | Phase 4 加嚴 signoff 條件（SRAM derate 1.575、半週期路徑的 duty cycle 預算、加入 ss −40°C）後，40 ns 不過，改 42 ns；25 ns 的目標做不到 | 規格／假設（signoff 條件太晚定） | 週期 +2 ns（登記表 T01、T04）；第 4 次 harden 後請使用者決定 | 已驗證（同一份版圖只重跑 STA） | (a) `signoff-criteria`「提早檢查」；(c) 流程 4.5 C1、4.1 A3；登記表 T01、T04 | 無（C1 的 checker 已排到下一個專案） | 不用動 | C1、A3 | phase4.md 36–42；ADR-0004 Phase 4 補充；`e5b7a4b` |
| P4-02 | 4 | OpenSTA 對 macro 設的 instance derate 會取代全域 derate，SRAM 的 ss ×1.5 沒有乘上 5% OCV | 工具意外行為 | 小（使用者決定改 1.575，P04 改植入值） | 已驗證（OpenSTA `sdc/Sdc.cc` 626–662） | (a) `signoff-criteria` 規則 5、`timing-constraints-sdc` 規則 4；(d) P04、P30 | 無；Phase 3.5 起改每個 PVT 一份 .lib，這條只在用 derate 時適用 | 不用動 | — | ADR-0007 第 33–37 行 |
| P4-03 | 4 | resizer 看 15 個 corner 時 `RepairDesignPostGRT` 35 分鐘以上停不下來；改成只看 9 個 corner，ss −40°C 用 setup 餘量 0.6 ns 與 PnR max transition 0.70 ns 補（根因當時沒查） | 工具缺陷＋流程（沒找根因就減 corner） | 第 1 次 harden 35+ 分鐘；留下 3 項補償（登記表 T11、T12、T15），T15 至今「原因已不在、還沒評估」；Phase 5 的 −4.158 ns 由它而來（P5-06） | Phase 4 的那次是推測（ADR-0013 第 41 行「推測是弱 cell 迴圈，未確認」）；同類的 Phase 5 已驗證 | (a) `multicorner-sta` 規則 3、`drv-timing-closure` 規則 8、9、14、15；`librelane-run-debug` 已知陷阱（15 個 corner 那列）；(c) 流程 4.5 C2、C3；(d) `check_weak_cells.py`（P40–P42）；登記表 T11–T13、T15 | 「最差 corner 在不在 resizer 清單」沒有 checker（ADR-0020 已列為下一個專案做）；失控本身沒有自動停（見 P5-05） | 併入建議 R2 | C2、C3、E1 | phase4.md 96–100、166；`cf021df`；ADR-0013 第 41 行 |
| P4-04 | 4 | CTS 在 `sram0/clk0` 前插 10 顆 delay buffer 對齊 flip-flop 的 latency；`CTS_DELAY_BUFFER_DERATE_PCT` 設 0 或 1 都管不到，當時判定「沒有設定可以關」，改用 hold 餘量 0.3 ns | 工具意外行為＋判斷錯誤（只看 flow 的變數，沒查底層工具指令） | Phase 4 第 2、3 次 harden（約 1 小時）；hold 餘量 0.3 ns 留到現在（T16）；Phase 5 PicoRV32 harden FAIL 與實驗 A–D（約 2 小時，`c976976`→`adac1a9`） | 已驗證（ADR-0016 實驗 D、OpenROAD `balanceMacroRegisterLatencies()`） | (a) `cts-clock-tree` 規則 10、12、13，`hard-macro-integration` 規則 6；(c) 流程 4.6 D4；(d) `check_soc.py cts_macro_latency`（P52–P54、P58–P60）；登記表 T16、T19 | 補償 0.3 ns 沒回收（登記表已標）；`config_hazard3.json` 第 188 行的註解仍寫「sram0 clock delayed by CTS latency balancing」 | 不用動（註解過期列在第三節） | D4、E1 | phase4.md 98、167；ADR-0016；`d767e54`、`e052848` |
| P4-05 | 4 | clock 輸入 pin 到第一顆 clock buffer 約 360 µm，LibreLane 預設不切這段線，max_ss_n40C slew 0.767 ns | 工具預設值 | 小（與週期、max transition 同一次修，效果沒單獨實驗） | 已驗證（預設切段長度約 3.5 mm） | (a) `cts-clock-tree` 規則 4、11；(d) signoff STA 的 max slew 判定（P03） | 無 | 不用動 | — | `cts-clock-tree` 經驗紀錄第 60 行；`e5b7a4b` |
| P4-06 | 4、5 | 實驗與失敗 run 的證據沒保存：第 4 次 harden 的 resizer log 沒留，原因只能推測；agent 做的 RTL 對合成網表 EQY 實驗只在暫存目錄；Phase 5 `941e1cb` 的 regress log 沒存、92.9 GB 只是當時看到的數字；ADR-0013–0016 的證據指向沒進版控的 `../arvinsa-rtl-gds-p5h3/runs/` | 流程（證據保存） | 結論只能標「推測」或「紀錄沒有保存」（phase4.md 99、186；phase5.md 35、119）；換機器後 ADR 的出處打不開 | 已驗證（文件自己寫明沒保存） | (a) `librelane-run-debug` 規則 6（只涵蓋 LibreLane run：`keep_prev_run`、引用的數字先寫進 ADR）；CLAUDE.md 規則 13（查證過程寫進筆記，10-09 才有） | agent 實驗、手動觀察的數字、regress console log、session 暫存的結果沒有規則；Phase 6（licon.14 的面積計算沒存，ADR-0018 決定 17）、Phase 7（IR 量測只存在 session，`chip-floorplan-pin-planning` 第 23 行）在規則 13 之後仍發生 | 建議 R3 | — | phase4.md 84、99、186；phase5.md 35、119、347；ADR-0013 第 58 行 |
| P4-07 | 4 | LibreLane 的 IR 把 PDN 的 pin 形狀全當理想電源（0.3 mV，任何門檻都 PASS），而且只看 VDD；PSM 在 net 有 pin 時忽略 `-source_type` | 工具意外行為（被測的模型太樂觀） | IR 研究約 1 小時（agent）；供電模型改一側 | 已驗證（16 種組合單步重跑；`ir_solver.cpp`） | (a) `pdn-ir-drop` 規則 4、5、10，description 有「IR drop 結果小得不合理」；`signoff-checker-qualification` 漏洞類型「判定只看一半的量」「被測的模型本身太樂觀」；(c) 流程 4.4 D2；(d) `[max_sum]` P07、P29，`ir_sources` P26–P28 | 「結果比預算小 100 倍要先查模型」沒有 checker（ADR-0020 已列） | 不用動 | D2 | phase4.md 48–49、72；`07d6d8e`；`pdn-ir-drop` 經驗紀錄第 81 行 |
| P4-08 | 4 | IR 的供電位置用「每條 strap 一側一點」的假設；Caravel 的 pad 位置是公開資料，卻寫成「Phase 7 才知道」 | 規格／假設 | IR 分四個 Phase 才修完（Phase 7 只從上側供電 143 mV） | 已驗證（回顧 `retro_p35_5.md` #7） | (a) `chip-floorplan-pin-planning` 規則 2、`pdn-ir-drop` 規則 12、14；(c) 流程 4.1（pad 階段查電源進入點）、4.4 D2；(d) `make pin-plan`（規劃要核准）、`ir_pattern.py`／`ir_caravel.py` | 無 | 不用動 | A2、D2 | phase4.md 165；ADR-0017 第 64 行 |
| P4-09 | 4 | EQY 的 `sat` strategy 對含 flip-flop 的分區是空洞證明：`dfxtp` 換成會 reset 的 `dfrtp`，18100/18100 個分區照樣證明通過 | 工具缺陷 | 小（agent 實驗時順帶發現） | 已驗證（初始狀態約束本身無解） | (a) `formal-equivalence-eqy` 規則 5、description；(d) `run_eqy.py sequential_cells`，`flop_async_reset`、`flop_q_inverted` | 無 | 不用動 | — | phase4.md 71；`07d6d8e` |
| P4-10 | 4 | flip-flop 與 SRAM 的 clock 接線沒有人檢查：EQY 先 `formalff -clk2ff`，只比 cell 種類的結構比對也看不到 CLK 接反相 clock | checker 漏洞（審查第 1 項） | 修正加 regress 重跑（見 P4-27） | 已驗證（審查者植入） | (a) `formal-equivalence-eqy` 規則 5；漏洞類型「前處理把要檢查的東西抹掉」；(d) `clock_sources`，`flop_clk_inverted`、`clk0_inverted` | 無 | 不用動 | E3 | phase4.md 192；`6367393` |
| P4-11 | 4 | RTL 對合成網表的 EQY 做不到：4 種植入有 2 種照樣 PASS；只用 PDR 時好設計也證不完 | 工具限制 | agent 實驗約半天以內（推測）；不採用 | 已驗證（實驗紀錄沒保存，見 P4-06） | (a) `formal-equivalence-eqy`「RTL vs 網表：尚未解決」；(c) 流程 4.7 限制；登記表 V01 | 無 | 不用動 | — | phase4.md 84 |
| P4-12 | 4 | Magic DRC 位置比對：同一個錯誤在晶片裡畫得比 SRAM 單獨檢查長，最多 85 nm，要給容許值；之後審查發現 100 nm 套到 30 種規則，li.3 看不到新違規的面積從 0.9% 變 6.5% | 工具行為＋checker 漏洞（審查第 10 項） | 小 | 已驗證 | (a) `drc-signoff` 規則 2（第 14–16 行）；漏洞類型「容許值套到不需要的類別」；(d) `DRC_POS_TOL_RULES`、P21；登記表 D03 | 無 | 不用動 | E3 | phase4.md 63、201；`drc-signoff` 經驗紀錄第 84 行 |
| P4-13 | 4 | negative test 本身沒證明它宣稱的事：P21 第一版植入的錯誤連舊 checker 也抓得到；加「只有被植入的列 FAIL」後 P09、P14 各多一列；P21、P23 只看第一個問題；neg-eqy 的位置範圍把整條 bus 算進去 | checker qualification | 小（各自修正） | 已驗證 | (a) `signoff-checker-qualification` 規則 7（舊 checker 會漏、牽動多列、看全部問題、位置檢查要分得出案例）；`drc-signoff` 第 61 行；(d) neg_eqy 交叉檢查、P21 | 無 | 不用動 | E3 | phase4.md 73–74、198 |
| P4-14 | 4 | Phase 4 審查找到的流程類 checker 漏洞：`make regress` 只在結尾讀 HEAD、`make -i` 造成假 PASS、provenance 只比 PDK_ROOT 字串（symlink）、`[max_sum]` 接受負項、IR 電壓源的大小與位置沒檢查、golden 摘要列永遠 PASS | checker 漏洞 | 與 P4-10 同一次修（`6367393`），加一輪 regress | 已驗證（審查者實驗） | (a) `flow-regression-reproducibility` 規則 1、3；漏洞類型表 6 種（第 92–97 行）；(d) `neg_regress.py`、`neg_provenance.py`、P27–P29 | 無 | 不用動 | E3 | phase4.md 190–201 |
| P4-15 | 4 | 下游步驟單獨執行時不檢查工作目錄是否乾淨（審查第 5 項，刻意不修） | checker 範圍（已知限制） | 無 | 已驗證 | 登記表 V09；phase4.md 已知限制 9 | 刻意保留（開發時要能用未 commit 的修改測試），`make regress` 有頭尾檢查 | 不用動 | — | phase4.md 171 |
| P4-16 | 4 | `make py-check` 只看同一個檔案內的名稱；從別的模組 import 的名稱改名，要到執行時才發現（審查第 9 項，不修） | checker 範圍 | 無（還沒出事） | 已驗證（讀程式） | phase4.md 已知限制 10；`signoff-checker-qualification` 經驗紀錄第 157 行（b） | `flow-regression-reproducibility` 規則 9 列了 py-check 看不到的寫法，沒列這一項 | 建議 R9 | — | phase4.md 172 |
| P4-17 | 4 | golden 要求繞線器中間各輪的 DRC 數完全相同，多執行緒 detailed routing 讓 `route__drc_errors__iter:2` 從 11 變 14，乾淨 regress 第 2 次 FAIL | checker 設計（誤差分類） | 一輪 regress 約 30 分鐘後 FAIL，重跑約 2 小時（`signoff-checker-qualification` 規則 5） | 已驗證（第 45 步輸入逐 byte 相同） | (a) `signoff-checker-qualification` 規則 5、11；(c) 流程 4.6 E2；(d) P31；登記表 G02 | 無 | 不用動 | E2 | phase4.md 16、75、209 |
| P4-18 | 4 | gate-level 模擬的牆鐘時限照 RTL 速度算（餘裕約 2 倍），Spotlight 索引 `runs/` 拉高負載，乾淨 regress 第 3 次在 `gl-soc-powered` FAIL；預跑時與 neg-pnr、EQY 同跑也有 3 支逾時 | 環境＋設定錯誤 | 一輪 regress（約 1–1.5 小時，16/25 後 FAIL） | 已驗證（單獨重跑 PASS） | (a) `gate-level-simulation` 規則 6；`flow-regression-reproducibility` 規則 9、已知陷阱（Spotlight，第 66 行）；程式 `gl_timeout` | 時限本身已修；「負載造成假 FAIL」是跨 Phase 的共同問題，見 P5-14 | 併入建議 R1 | — | phase4.md 17、76；`b7860b7` |
| P4-19 | 4 | 函式改名時漏改 neg-pnr P11 的呼叫，預跑 20 分鐘後才 `NameError` | 人為操作失誤 | 預跑抓到，省下一輪約 2 小時 | 已驗證 | (a) `flow-regression-reproducibility` 規則 9；(d) `make py-check`（regress 第 2 個 target） | 無 | 不用動 | — | `72e5433`；`flow-regression-reproducibility` 經驗紀錄第 81 行 |
| P4-20 | 4 | 開發用的假 run：整個目錄做成 symlink 時下游讀到舊 run 的 `_signoff`；長 run 期間改主目錄，結束時來源追溯 FAIL；neg_provenance 從 HEAD clone，新檔還沒 commit 時 positive control FAIL | 環境／流程 | 小 | 已驗證 | (a) `flow-regression-reproducibility` 規則 5、6；最後一項只有 (b) 第 78 行 | 最後一項是一次性的小事 | 不用動 | — | `flow-regression-reproducibility` 經驗紀錄 78–80 |
| P4-21 | 4 | neg-eqy `clk0_inverted`：EQY 以名稱衝突拒絕，但位置範圍不走 clock net，判「沒在植入點 FAIL」 | checker 錯誤（假 FAIL） | 小（預跑抓到） | 已驗證 | (a) `formal-equivalence-eqy` negative test 一節（clock net 只往回找來源）；(d) neg_eqy 交叉檢查 | 無 | 不用動 | — | `c635ffb`；`formal-equivalence-eqy` 經驗紀錄第 85 行 |
| P4-22 | 4 | 帶電源網表模擬：tap cell 的 Verilog model 多宣告 VPB／VNB，Icarus 報 13270 行 `dangling input port` | library 不一致（LEF 對 Verilog model） | 小 | 已驗證 | (a) `gate-level-simulation` 規則 8；(d) `log_scan` 白名單只放這個 cell 的兩個 port | 無 | 不用動 | — | phase4.md 88；`gate-level-simulation` 經驗紀錄第 53 行 |
| P4-23 | 4 | directed 測試 `buserr`：GCC 把已知非對齊的存取拆成 byte 存取；第二版又假設 PicoRV32 會擋下非對齊寫入，實際照寫 | 規格／假設錯誤 | 小（兩版） | 已驗證（讀 `picorv32.v`、反組譯） | (a) `dv-directed-tests` 規則 2、3、6；(d) `neg_gl_soc.py` 的 3 個植入 | 無 | 不用動 | — | phase4.md 91；`dv-directed-tests` 經驗紀錄 28–29 |
| P4-24 | 4、5 | 「沒有寄生資料的 driver 數」的上限寫死總數：Phase 4 寫「剛好 134」實際 133（CTS dummy load 少一顆）；Phase 5 從 PicoRV32 抄到 Hazard3（133 對 125），ADR-0016 改 CTS 後又變 126／118 | checker 設計（版圖相關的計數寫成固定值） | 4 次 harden 在這一列 FAIL、每次人工重數組成（Phase 5 第 5、10 次 harden FAIL 的原因之一） | 已驗證 | (a) `signoff-checker-qualification` 規則 4（寫出組成）、`core-migration-hazard3` 規則 22；(d) `check_signoff.py` 的上限（會 FAIL）；登記表 V07 | checker 只比總數：CTS 或 flow 一改就假 FAIL、要人工重數；組成本身沒有被逐項檢查 | 建議 R5 | — | phase4.md 100；phase5.md 123、127；`d6f3074`、`1d13775` |
| P4-25 | 4 | Phase 4 結案時 skill 寫回不完整（`cts-clock-tree`、`drv-timing-closure` 是使用者結案後問才補）；一個 skill 的 description 不是合法 YAML；README 的 skill 說明停在 Phase 3 | 流程（文件與實作不一致） | 結案後補一輪（約 1 小時，`1482872`→`8d15cc8`） | 已驗證 | (a) `phase-exit-review` 規則 8、9，CLAUDE.md 規則 5；(d) `make skill-check` | 無 | 不用動 | — | phase4.md 159；`phase-exit-review` 經驗紀錄第 37 行 |
| P4-26 | 4 | exit 文件核對找到 13 項寫錯、19 項不準、4 項找不到證據 | 文件與證據不一致 | 約 30 分鐘（`ba2b1bc`） | 已驗證 | (a) `phase-exit-review` 規則 3、5 | 無 | 不用動 | — | phase4.md 181–187 |
| P4-27 | 4 | 乾淨 checkout 的 `make regress` 跑 4 次才結案：第 1 次 PASS 後才做獨立審查，修完 checker 再跑時又遇到 P4-17、P4-18 | 流程順序（審查排在 regress 之後） | 3 輪多出的 regress，約 4–5 小時 | 已驗證 | (a) `signoff-checker-qualification` 規則 12、`phase-exit-review` 規則 10；(c) 流程 4.8 E3 | 審查紀錄齊不齊沒有 checker（ADR-0020 已列） | 不用動 | E3 | phase4.md 12–19 |
| P4-28 | 4、5 | EM（電流密度造成的金屬劣化）沒有 flow 檢查：Phase 4 研究單點供電時 via4 超過上限；Phase 5 最壞組合 via4 達 78%（單一 cut），只在 what-if 量過 | 簽核範圍的缺口 | 還沒造成重工；下線風險 | 已驗證（研究與 what-if 的量測） | (a) `signoff-criteria` 規則 14、`pdn-ir-drop` 規則 8 與「待補」；登記表 I12（「下線前要做」）；ADR-0017 限制 | 沒有 checker，流程文件也沒把它列成「下一個專案開始時做成 checker」 | 建議 R7 | — | ADR-0017 第 66 行；`docs/notes/ir_worst_case_soc_top.md` |
| P4-29 | 4 | 停掉一個 run 時誤殺了同時在跑 openroad 的 agent | 人為操作失誤 | 小 | 已驗證 | (a) `librelane-run-debug` 已知陷阱第 61 行（用 process group 停） | 無 | 不用動 | — | `librelane-run-debug` 第 61 行 |

## 二、Phase 5（2026-10-05 晚～10-08）

| 編號 | Phase | 問題（白話） | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P5-01 | 5 | Hazard3 上游測試要 newlib 工具鏈，Homebrew 的沒有；Yosys `chparam` 放在 `hierarchy` 之後報 `core_haddr_d` 沒有 driver | 環境／工具用法 | 小（前置調查） | 已驗證 | (a) `core-migration-hazard3` 規則 2、11；`make xpack-fetch` | 無 | 不用動 | — | ADR-0011 查證 7；`core-migration-hazard3` 經驗紀錄第 105 行 |
| P5-02 | 5 | AHB 讀取時 `hwdata` 沒有驅動，轉成 native bus 後 `bus_assert` FAIL | 整合錯誤 | 小 | 已驗證 | (a) `core-migration-hazard3` 規則 16；(d) `bus_assert`、H01–H04 | 無 | 不用動 | — | `core-migration-hazard3` 經驗紀錄第 106 行 |
| P5-03 | 5 | Hazard3 與 PicoRV32 的行為差異讓測試 FAIL：`mtval` 固定 0、中斷是準位且只進 1 次、CPI 小使 `min_cycles` 不成立；firmware 錯誤變體用了 PicoRV32 的 `start.o`，S01、M01 漏網 | 規格／假設錯誤 | 小（各改期望值） | 已驗證 | (a) `core-migration-hazard3` 規則 8、10、14、18、19；(d) `regress-rtl`、`neg-rtl` | 無 | 不用動 | — | `core-migration-hazard3` 經驗紀錄第 107 行 |
| P5-04 | 5 | rvcpp（Hazard3 的指令集模擬器）沒有 `fence`、CSR 是全功能設定、`rvfi_intr` 含 exception、trace 結尾長度差 | 工具限制 | 小（`rvcpp_fence.patch`） | 已驗證 | (a) `core-migration-hazard3` 規則 20；(d) `core-hazard3` 的逐指令比對與 `EXTENSION_M=0` 植入 | 無 | 不用動 | — | phase5.md 47；`core-migration-hazard3` 經驗紀錄第 108 行 |
| P5-05 | 5 | resizer 無窮迴圈（第 4 次發生）：OpenROAD 用第一個讀進來的 tt .lib 評估換尺寸，把 ss 違規的 `a2111oi_2` 換成更弱的 `a2111oi_1`，長線修復在同一點一直插 buffer；跑 108 分鐘、記憶體 92.9 GB 才停；`ps` 的 RSS 只顯示 418 MB | 工具缺陷 | 從第 1 次 harden 到修好約 26 小時（含等待）；機器 24 GB 被拖垮 | 已驗證（單步重跑、實驗 A–D、讀 `RepairDesign.cc`） | (a) `drv-timing-closure` 規則 10、11、14 與 description；`librelane-run-debug` 已知陷阱第 59 行；(c) 流程 4.5 C2；(d) `check_weak_cells.py`（P40–P42） | 弱 cell 檢查只查 resizer 的 corner（ADR-0020 已列）；它是必要條件不是充分條件（PicoRV32 也有 `a2111oi_1` 卻沒進迴圈，原因沒查）；**失控時沒有自動停**，4 次都是人發現（26–108 分鐘） | 建議 R2 | C2 | ADR-0012；phase5.md 119；`docs/notes/repair_design_loop.md` |
| P5-06 | 5 | resizer 只看 9 個 corner，用 0.6 ns 餘量代替 ss −40°C；Hazard3 的乘除法長路徑在 ss 100°C +1.48 ns、ss −40°C −4.16 ns（81 條） | 補償的依據只在 PicoRV32 量過 | 一次 harden＋單步實驗（約 1.5 小時）；另排除 6 種 ss −40°C 的弱 cell | 已驗證（單步重跑 −7.32 → +0.33 ns） | (a) `drv-timing-closure` 規則 9、11、15，`multicorner-sta` 規則 3、8，`core-migration-hazard3` 規則 22；(c) 流程 4.5 C3、E1；登記表 T11–T13 | criteria review 沒有「最差 corner 在不在 resizer 清單」這列（ADR-0020 已列） | 不用動 | C3、E1、D3 | ADR-0013；phase5.md 120 |
| P5-07 | 5 | `STAMidPNR` 只量 `DEFAULT_CORNER`（`PNR_CORNERS` 沒設時），state 裡其他 corner 的 metrics 是 placement 前的舊值；LibreLane 的變數說明與程式不符，soc_top config 註解與 Phase 3 的一個說法都因此寫錯 | 工具文件與實作不一致 | 分析時誤判一次（−15.5 ns 其實是舊值） | 已驗證（讀 `openroad.py` 353–355、step log） | (a) `multicorner-sta` 規則 2、7、已知陷阱；`librelane-run-debug` 規則 4 | 這是讀資料的陷阱，沒有自動防護也合理 | 不用動 | — | `d00214d`；`librelane-run-debug` 經驗紀錄第 85 行 |
| P5-08 | 5 | 43 ns 剩 −0.381 ns，改 44 ns 後反而 −1.131 ns：週期一變 placement 與修復 buffer 鏈跟著變（run 之間差約 1 ns）；CTS 後的 setup 估計在長路徑偏樂觀，差距在繞線後才出現；繞線後 global routing 的估計也不一定悲觀（PicoRV32 半週期路徑樂觀 ≥ 0.14 ns） | 工具行為 | 週期 +1 ns（T03）；第 4 次 harden 與實驗 A、B（約 4 小時，`1292ca4`→`3a28d54`） | 已驗證（只差一步的接續實驗） | (a) `drv-timing-closure` 規則 12、「退回過的做法」；`signoff-criteria`（resizer 餘量從最後一次修復推導）；登記表 T03 | 修完到 signoff 的差距只在 `review_criteria.py` 印成 INFO，不判定；目前合理 | 不用動 | A3、D3 | ADR-0014；ADR-0004 Phase 5 補充 |
| P5-09 | 5 | `pnr/soc_top/run.sh` 在 LibreLane FAIL 時直接結束，Hazard3 第 2–4 次 harden 的 repo checker（上限檔、`check_soc.py`）都沒跑，沒人發現 | 流程腳本錯誤 | 3 次 harden 的 checker 結果缺；上限檔抄錯（P4-24）晚發現 | 已驗證（讀 `run.sh` 79–81 行） | (a) `signoff-criteria`「每次 harden 後的檢查」第 202、206 行，CLAUDE.md 規則 9；(d) Stop hook、`test-review-hook`、P43–P49；(c) 流程 4.6「跑完（PASS 或 FAIL）」只寫要做 criteria review | 流程文件 1.5 說 `run.sh` 每個新設計要重寫，但流程文件沒要求「flow FAIL 時 repo 的 checker 與 criteria review 照跑」；新專案的 `run.sh` 可能重犯 | 建議 R4 | — | `0b67b76`；phase5.md 245–248 |
| P5-10 | 5 | `review_criteria.py` 綁 flow 的步驟：開了 `RUN_POST_GRT_RESIZER_TIMING` 後，setup 差距仍拿 `ResizerTimingPostCTS` 算，印出無意義的「−0.418」 | checker 錯誤 | 小 | 已驗證 | (a) 漏洞類型「checker 綁死 step 名稱」；`signoff-criteria` 經驗紀錄第 264 行；(d) P49 | 無 | 不用動 | — | `d6f3074` |
| P5-11 | 5 | `RSZ-0032 Inserted N hold buffers` 的 N 不是總數（log 寫 11，網表多 2700）；golden 的 hold buffer metric 是 0 | 工具 metric 缺陷 | 小 | 已驗證（Phase 7 查到 `RepairHold.cc` 的根因） | (a) `librelane-run-debug` 已知陷阱第 60 行、`drv-timing-closure` 規則 7；(d) `review_criteria.py` 數網表 | 無 | 不用動 | — | `drv-timing-closure` 經驗紀錄第 132 行 |
| P5-12 | 5 | Hazard3 第 6、7 次 harden 與 golden 不同（61、11 個 metric）：第 41 步 global routing 偶發不同（27 次裡 5 次）、detailed routing 多一輪 antenna 修補多插 diode，cell 數與面積跟著變 | 工具不可重現 | 2 次 harden＋2 組接續 run（各約 23 分鐘），約 4 小時（`d6f3074`→`9ef0be7`） | 已驗證（逐步比對 DEF、單步重跑量頻率） | (a) `signoff-checker-qualification` 規則 5、11；(c) 流程 4.6 E2；(d) `[golden_layout_tolerance]` P50、P51；登記表 G03 | 無；`DRT_THREADS=1` 沒試（已知限制） | 不用動 | E2 | ADR-0015 |
| P5-13 | 5 | 改名後的 run，每一步的 `state_in.json` 仍是舊目錄的絕對路徑，不能直接單步重跑 | 工具行為 | 小 | 已驗證 | (a) `librelane-run-debug` 規則 6 最後一點 | 無 | 不用動 | — | `514f723` |
| P5-14 | 4–7 | 機器資源造成的假 FAIL 或工作被停：Phase 5 第 7 次 harden 在 detailed routing 被 Claude Code 停掉（使用者另一個程式佔 17 GB）；結案兩輪 regress 改成依序跑（平行時 neg-eqy 與 gate-level 模擬負載疊加）；同類還有 P4-18、Phase 6 neg-pnr 被系統以記憶體不足中止、Phase 7 磁碟滿與 KLayout 在 swap 7.6 GB 時 SIGSEGV | 環境 | 每次一個 harden 或一輪 regress（0.5–2 小時） | 已驗證（Phase 4、5、6 各次）；Phase 7 KLayout 那次推測 | (b) `flow-regression-reproducibility` 經驗紀錄 89、93、94、97、98 行；(a) 只有 Spotlight（已知陷阱）與 GL 時限（`gate-level-simulation` 規則 6）；(d) 本機全域 hook（同時最多 2 個 LibreLane／EQY、至少 4 GB 可用記憶體，流程 1.4：只在這台機器） | 規則本文沒有「長 run 與平行 run 的資源預算」；換機器或用 Codex 時沒有任何防護；被停或逾時先查資源的判斷只寫在 GL 一處 | 建議 R1 | — | `flow-regression-reproducibility` 經驗紀錄 89、93；phase5.md 25 |
| P5-15 | 5 | neg-eqy `reset_b_tied1` 假 FAIL：checker 把常數 `1'1` 當名稱，被接成常數的腳往兩邊走遍整棵 reset 樹（1,449 個名稱），交叉檢查發現它接受別的案例的 FAIL | checker 錯誤 | 約 1–2 小時（推測，`c976976`） | 已驗證 | (a) `formal-equivalence-eqy` negative test 一節（常數不算名稱、只往上游追）；(d) 交叉檢查 | 無 | 不用動 | — | phase5.md 251；`c976976` |
| P5-16 | 5 | `reset_b_tied1` 宣稱「只有證明抓得到」，實際是名稱衝突就拒絕（0 個分區）；改用 tie cell 或繞過同步器也一樣 | negative test 宣稱與事實不符（審查第 5 項） | 小 | 已驗證（三種植入各跑一次） | (a) `formal-equivalence-eqy`「改到 reset 連接的錯誤一律落在 (c)」、`signoff-checker-qualification` 規則 7「斷言抓到它的機制」；(d) `REQUIRE` | 無 | 不用動 | E3 | phase5.md 337 |
| P5-17 | 5 | 為 Hazard3 改的 flow 設定（ADR-0013、0014、44 ns）拿回去跑 PicoRV32，setup −0.113 ns FAIL | 流程（共用 flow 設定的設計變體） | 一次 harden＋實驗 A–D（與 P4-04 同一段） | 已驗證（根因是 CTS latency 對齊，ADR-0016） | (b) `core-migration-hazard3` 經驗紀錄第 111 行（「改 flow 設定後兩個 CPU 都要重新 harden」）；`flow-regression-reproducibility` 經驗紀錄（`3c37bff`）；(d) `check_inputs.py cpu_config` 要求兩份 config 只差 RTL、`make regress-picorv32` 在結案時會跑 | 規則本文沒有；防線只在結案的 regress，開發中改設定時不會提醒 | 建議 R6 | D3（相關） | `c976976`；ADR-0016 背景 |
| P5-18 | 5 | OpenROAD 整顆晶片只用一種 hold buffer（`dlygate4sd3_1`）；排除它就 `RSZ-0060 Max buffer count reached`；在 data 端補 hold 時 ss 延遲是 ff 的 2.5–3.3 倍 | 工具行為 | 實驗 C1、C2（各約 16 分鐘） | 已驗證（`RepairHold::findHoldBuffer`） | (a) `drv-timing-closure` 規則 7（寫明「沒有自動防護」與原因）、`cts-clock-tree` 規則 12；knowledge S21 | 無（規則 10 的四項都有） | 不用動 | — | ADR-0016 實驗 C；phase5.md 292 |
| P5-19 | 5 | 隨機的 GRT-0229 出現在第二個位置（`ResizerTimingPostGRT`），重試規則只認 `RepairDesignPostGRT`，兩次正式 harden 都中止 | 工具缺陷＋checker 綁 step 名稱 | 2 次 harden 白跑（約 1 小時） | 已驗證（單步重跑 1/4 中止） | (a) `librelane-run-debug` 規則 5、已知陷阱第 52 行；漏洞類型「checker 綁死 step 名稱」；(d) `test-flow-retry` | 規則 5 的文字過期（見第三節） | 建議 R11（只改文字） | — | `2caad0e`；phase5.md 126 |
| P5-20 | 5 | 用 repo 的 plugin 換掉 CTS step 後，手動跑 flow 沒把 `pnr/` 放進 `PYTHONPATH`：`Could not replace 'OpenROAD.CTS' ...` | 工具用法 | 小 | 已驗證 | (a) `librelane-run-debug` 規則 1 與 description；`pnr/librelane_flow.sh` 已設 | flow 一開始就停，不會產生錯的結果，不需要 checker | 不用動 | — | `62114d6` |
| P5-21 | 5 | GRT-0229 重試後，同一個 step 有兩個目錄（中止的沒有 `state_out.json`），`review_criteria.py` 讀到中止那次的 log，PicoRV32 的 neg-pnr P49 沒抓到（54/55） | checker 漏洞 | 約 3 小時（`1d13775`→`941e1cb`，含下游驗證） | 已驗證 | (a) `librelane-run-debug` 已知陷阱第 49 行、漏洞類型第 87 行；(d) P55 | 無 | 不用動 | — | phase5.md 249–250 |
| P5-22 | 5 | 乾淨 checkout 沒有 `.tools/` 下的 xPack，`core-hazard3` 在第 6 個 target FAIL；`env-check-flow` 沒檢查；之後審查發現 xPack 檢查只比版本字串 | 環境＋checker 漏洞 | 一輪 regress 的前幾分鐘 | 已驗證 | (a) `flow-regression-reproducibility` 規則 2、已知陷阱第 59 行；漏洞類型「只檢查版本字串」；(d) `env-check-flow`、`neg-regress xpack_fake` | 無 | 不用動 | — | phase5.md 35、252–254；`7348fab` |
| P5-23 | 5 | Phase 5 審查的其他 checker 漏洞：uncertainty 只確認 SDC 印了那一行（報表全刪仍 PASS，0.25 又等於預設值）；`cts_macro_latency` 靠名稱；誤差表的保護字缺 `floating`、`warning` 且接受萬用字元；Stop hook 不涵蓋 `harden-core` 與當掉；PicoRV32 暫用 Hazard3 的誤差；`test-flow-retry` 沒測兩道重試條件 | checker 漏洞 | 與 P5-24 同一輪修正與兩輪 regress | 已驗證（審查者逐項做壞輸入） | (a) 漏洞類型第 111–117、124 行；`timing-constraints-sdc` 經驗紀錄第 59 行；(d) P56–P60、P50／P51 變體、`test-review-hook` 12/12、`grtreal`／`grtdone` | 無 | 不用動 | E3、E2 | phase5.md 327–349 |
| P5-24 | 5 | Phase 4「flow 只判 nom_tt 的 IR」的依據（最壞組合 11.46 mV）只在 PicoRV32 量過；Hazard3 最壞組合 25.75 mV 超過 20 mV，via4 EM 78% | 補償的依據只在一個設計量過 | met5 1.6 → 4.8 µm、兩個 CPU 重 harden、重建 golden、再兩輪 regress：約 14 小時（`7348fab`→`71b1454`） | 已驗證（同方法重測；PDN what-if 與 harden 相差 0.01 mV） | (a) `pdn-ir-drop` 規則 12、13，`signoff-criteria`「依據要在這個設計上重量」，`core-migration-hazard3` 經驗紀錄第 112 行；(c) 流程 E1、D2；(d) `ir_worst.py` P61、P62（之後再改為慢 corner 與 pattern）；登記表 I03、I04 | 無 | 不用動 | E1、D2、C1 | ADR-0017；phase5.md 95–111 |
| P5-25 | 5 | `ResizerTimingPostGRT` 的增量 global routing 隨機報 `GRT-0116 Global routing finished with congestion`，總溢位只有 2 | 工具缺陷 | 樣本 4 中止、補跑一次（約 30 分鐘） | 已驗證（單步重跑 4 次都通過） | (a) `librelane-run-debug` 已知陷阱第 53 行（症狀、發現、繞過、防復發四項都有）與 description；(d) `test-flow-retry` 的 `cong`、`congbig` | 無 | 不用動 | — | phase5.md 256–257 |
| P5-26 | 5 | 加 GRT-0116 重試時，新的 `grep` 在沒有壅塞列的 log 上回傳 1，呼叫端的 `set -euo pipefail` 讓整支腳本結束 | 腳本錯誤 | 小（`test-flow-retry` 當場抓到） | 已驗證 | (b) `librelane-run-debug` 經驗紀錄第 91 行；(d) `test-flow-retry` | 只出現一次，防線（模擬情境測試）已在 | 不用動 | — | phase5.md 258 |
| P5-27 | 5 | 依審查把 PicoRV32 的版圖誤差清空後，第一次量到 run 之間的差異（diode ±1 等 10 個 metric），PicoRV32 regress FAIL，要再補樣本、跑第三輪 | 流程（清空誤差前沒排量樣本） | 第三輪 regress 約 4 小時＋補樣本約 1 小時 | 已驗證 | (a) `signoff-checker-qualification` 規則 11；`phase-exit-review` 經驗紀錄第 40 行（清空誤差要預期多一輪） | 無（規則 11 要求一開始就 ≥ 4 個樣本，這件事就不會發生） | 不用動 | E2 | phase5.md 37、217、368 |
| P5-28 | 5 | exit criteria「flow 設定只需改 design 層」沒達成：換 core 迫使 4 項 flow 設定、週期、plugin、checker 都改 | 規格／計畫假設錯誤 | 使用者接受為與計畫不同 | 已驗證 | (a) `core-migration-hazard3` 規則 22、23；(c) 流程 4.4 D3 | 無 | 不用動 | D3 | phase5.md 52、363–366 |
| P5-29 | 5 | `neg-char`（SRAM 特性化的植入錯誤）不在 regress 裡，Phase 5 新增的 N9–N16 只在主目錄跑過，沒在乾淨 checkout 跑過 | 流程（regression 範圍外的 checker） | 還沒出事；風險推測 | 已驗證（文件自述） | 登記表 S21；(c) 流程 4.8「不在 regression 裡、要另外跑的」；phase5.md 已知限制 10 | 沒有規則要求 Phase 收尾時對「不在 regression 的 checker」確認最後一次在哪個 commit、哪個環境跑過 | 建議 R8 | — | phase5.md 177、240、294 |
| P5-30 | 5 | met5 加寬後，Magic 在 SRAM 框內報的 DRC 框數 4,665,810 → 4,746,079（上方金屬改變），golden 比對 FAIL | 工具行為 | 小（位置比對確認全部對得上） | 已驗證 | (a) `pdn-ir-drop` 規則 13 最後一點；knowledge S24；(b) `drc-signoff` 經驗紀錄第 86 行；(d) `check_soc.py magic_drc` 位置比對 | 無 | 不用動 | — | ADR-0017 第 59 行 |
| P5-31 | 5 | exit 文件核對找到 17 項：7 項判定的說法不誠實、Phase 3.5 的限制沒延續、證據引用開發 worktree 的 run、`power__total` 沒寫是哪個 corner | 文件與證據不一致 | 約半小時 | 已驗證 | (a) `phase-exit-review` 規則 1、2、3 | 無 | 不用動 | — | phase5.md 311–325 |
| P5-32 | 5 | 補償的原因被修掉後設定沒有回收：週期 44 ns、hold 餘量 0.3 ns（原因是 P4-04）、PnR max transition 0.70 ns（原因是 P4-03） | 流程（補償沒回收） | 推算 43 ns 時 PicoRV32 約 +0.34、Hazard3 約 +0.66 ns（推算，`retro_p35_5.md` #12） | 推測（沒有跑 what-if） | (a) `signoff-criteria`「提早檢查」E1；(c) 流程 E1；登記表 T03、T15、T16（狀態「原因已不在、還沒評估」） | 捕捉已足夠；what-if 本身還沒做，屬於待辦，不是寫回 | 不用動（待辦由使用者決定是否做 what-if） | E1 | 登記表 T15、T16；ADR-0013 決定 3 |
| P5-33 | 5 | `neg_char.py` 的平行案例同時產生共用的修剪網表，互相覆蓋（race） | checker 錯誤 | 小 | 已驗證（commit 訊息） | (e) 只在 `2251c4a` 的 commit 訊息；程式已改成平行前先產生一次 | 沒照 CLAUDE.md 規則 2 寫經驗紀錄 | 建議 R10 | — | `2251c4a` |

## 三、審查時順帶發現的文件與實作不一致（不計入 62 個問題）

這些不是 Phase 4／5 當時遇到的問題，是本次 grep 核對時看到的過期文字，建議一次改掉（建議 R11）：
1. `librelane-run-debug` 規則 5（第 32 行）：寫「只針對那一個訊息」、`make test-flow-retry`「跑 10 種情境」。現在重試涵蓋 GRT-0229 與 GRT-0116（總溢位 ≤ 10）兩種，`pnr/test_librelane_flow.sh` 是 15 個情境。
2. `pdn-ir-drop`「待補（Gemini 審查…）」第 68–69 行：仍寫「Phase 7 Caravel 時改成 wrapper 的實際接點」「目前 OpenSTA 用預設切換率估功耗」；Phase 7 已改成從 pad 起算與 max power pattern（同一檔規則 12）。
3. `core-migration-hazard3`「待補」第 91 行：仍寫「Phase 5 尚未完成的部分：…乾淨 checkout 的 regression、exit review」，Phase 5 已在 2026-10-08 結案。
4. `pnr/soc_top/config_hazard3.json` 第 188 行 `//PL_RESIZER_HOLD_SLACK_MARGIN` 的理由仍是「sram0 clock delayed by CTS latency balancing」，ADR-0016 之後這個原因已不在（登記表 T16 已標「原因部分已不在」；config 註解是程式碼，改不改由使用者決定）。

## 四、建議寫回（依重要性排序）

每一項都核對過 CLAUDE.md 規則 3（同一現象出現兩次以上或根因已用實驗確認，才寫進規則本文）、規則 4（設計數字留在 repo 文件）、規則 10（工具缺陷的防護要有四項）。R7、R2 的自動防護要新寫程式，依 CLAUDE.md 規則 13 要先由使用者決定。

**R1. 長 run 與平行 run 的資源預算（寫進 `flow-regression-reproducibility` 規則本文，新的一條；流程文件 4.8 加一句指過去）**
- 寫什麼：開長 run 或平行 run 之前，先估每個工作的記憶體與磁碟（例如一次 soc_top run 約 4 GB 磁碟、LibreLane 修復步驟 1–2 GB、完整網表的 ngspice 約 4.2 GB），由可用記憶體與磁碟決定平行數；`runs/` 與 worktree 排除在 Spotlight 索引外；工作被系統停掉、逾時或工具異常結束時，先看當時的記憶體、swap、磁碟與 load，單獨重跑確認，再判斷是不是設計或工具問題。能自動化的部分：`env-check-flow`（或 `regress.py` 開頭）檢查可用記憶體與磁碟是否高於門檻，低於就在第 1 分鐘 FAIL。
- 依據：同一類現象至少 6 次，跨 4 個 Phase（P4-18 兩次、P5-14 兩次、Phase 6 neg-pnr 被中止、Phase 7 磁碟滿），全部已驗證（Phase 7 KLayout SIGSEGV 一次推測）。現在只在經驗紀錄，加上一支只在這台機器的全域 hook（流程文件 1.4 明說換機器或用 Codex 時不存在）。
- 為什麼可帶到下一個專案：開源 flow 跑在個人電腦或小 VM 是常態，資源不足造成的假 FAIL 每一次都要花一輪 regress 才看出來；這條規則與設計無關。

**R2. resizer（或任何 step）失控時自動停（`librelane-run-debug` 規則本文新增一條；流程文件 4.6 的 harden 加一句；建議新增自動防護）**
- 寫什麼（照規則 10 的四項）：症狀：某一步的時間遠超過同一設計上次的時間、physical footprint 一直漲、CPU 使用率低、最後只報 `failed with an unexpected error`。怎麼發現：harden 的包裝腳本每分鐘取該 step 程序的 physical footprint 與已跑時間（`vmmap --summary` 或 `top -stats mem`，不要用 RSS）。怎麼繞過：超過上限（例如上次 golden 該步時間的 N 倍、或記憶體超過實體記憶體的一半）就停掉、保留 run，照 `drv-timing-closure` 規則 10 單步重跑找 net。防復發：`test-flow-retry` 類的模擬測試加一個「step 一直不結束」的情境，確認包裝腳本會停。
- 依據：resizer 停不下來發生 4 次（Phase 3 soc_explore6、Phase 3.5、Phase 4、Phase 5），4 次都是人看到才停，花 26–108 分鐘，Phase 5 那次把 24 GB 的機器拖到 92.9 GB；弱 cell 檢查是必要條件不是充分條件（`drv-timing-closure` 規則 10 自己寫的）。現在只有「可能失控的實驗一定要監看記憶體」（`librelane-run-debug` 規則 3），正式 harden 沒有。現象已出現 4 次，可以進規則本文；Phase 3、4 的根因是推測，規則只寫現象與防護，不寫根因。
- 為什麼可帶到下一個專案：工具失控的根因每次可能不同（弱 cell、macro .lib 斜率、corner 數），但「長時間無進展就自動停並保留證據」對任何工具都成立。

**R3. 證據要保存在版控內或主目錄（`phase-exit-review` 規則 3 加一點；`signoff-checker-qualification` 規則 8 的獨立審查也適用）**
- 寫什麼：ADR、exit review、skill 經驗紀錄引用的每個數字，出處必須是 (1) 進版控的檔案（實驗腳本與摘要放 `docs/notes/<主題>/`，像 `docs/notes/ir_study/phase5/` 那樣），或 (2) 主目錄 `runs/` 下的檔案並註明「不進版控」；session 暫存目錄、之後會刪的 worktree、只在對話裡看到的數字都不能當出處。agent 的實驗在下結論之前，先把指令與輸出摘要存進 `docs/notes/`。regress 的 console log 存進 `runs/`，exit review 引用前確認檔案存在。
- 依據：已驗證的發生至少 7 次：Phase 3.5 run 被刪、neg-char log 沒存；Phase 4 第 4 次 harden 的 resizer log、agent 的 RTL EQY 實驗；Phase 5 `941e1cb` 的 log、92.9 GB；Phase 6 licon.14 面積計算；Phase 7 IR 量測只在 session。CLAUDE.md 規則 13（10-09）之後 Phase 6、7 仍發生，表示規則 13 的「查證過程寫進筆記」不夠具體。`librelane-run-debug` 規則 6 只涵蓋 LibreLane run。
- 為什麼可帶到下一個專案：結論標成「推測」或出處打不開，下一個人就無法沿用；這和設計無關。

**R4. harden 的包裝腳本在 flow FAIL 時也要跑全部 repo checker 與 criteria review（流程文件 4.6「開跑前／怎麼跑」加一句，並在 1.5「要依新設計重做的」那一點註明）**
- 寫什麼：新設計重寫 `pnr/<design>/run.sh` 時，LibreLane FAIL 也要照跑上限檔、設計專屬 checker 與 `review_criteria.py`，整體判定仍是 FAIL；要有 negative test（本 repo P43–P49、`test-review-hook`）。
- 依據：已驗證（Phase 5 Hazard3 第 2–4 次 harden 的 checker 都沒跑，`signoff-criteria` 第 202 行）。本 repo 已修，但流程文件 1.5 規定 `run.sh` 每個新設計重做，新專案照流程文件做時不會讀到這條（目前只寫在 `signoff-criteria` 一段說明與本 repo 的 `run.sh`）。
- 為什麼可帶到下一個專案：flow FAIL 的 run 正是最需要 checker 告訴你「還有哪些別的問題」的時候。

**R5. 版圖相關的計數不要只比總數，要逐項分類（`signoff-checker-qualification` 規則 4 補一段；本 repo 的 checker 是否改由使用者決定）**
- 寫什麼：「不是 0」的計數（沒有寄生資料的 driver、斷線 pin），checker 要把每一個列出來、依組成分類（CTS dummy load、macro 沒用的輸出、tie cell 沒用的輸出、沒用的 port），任何不屬於已知類別的就 FAIL；會隨版圖變的類別（CTS dummy load 數）和 CTS 自己報的數量比，不寫死。
- 依據：已驗證 4 次（Phase 4 「剛好 134」實際 133；Phase 5 抄 PicoRV32 的 133 給 Hazard3 的 125；ADR-0016 改 CTS 後 126、118），每次都讓 harden FAIL、要人工重數（`check_signoff.py` 現在仍比總數，登記表 V07）。
- 為什麼可帶到下一個專案：每個設計都會有這類計數，寫死總數只會在每次改 CTS 或換設計時假 FAIL，而真正多出來的一個未知 driver 反而被「重數一次」的手續蓋過去。

**R6. 共用 flow 設定的設計變體：改設定後每個變體都重 harden（`core-migration-hazard3` 規則 22 加一點；`flow-regression-reproducibility` 加一句）**
- 寫什麼：為一個變體（例如新 core）改的 flow 設定，若其他變體共用同一份設定，改完就在每個變體上 harden 一次，不要等結案的 regression。
- 依據：Phase 5 為 Hazard3 改的設定讓 PicoRV32 FAIL（−0.113 ns），根因由 ADR-0016 的實驗確認（規則 3 的「根因已用實驗確認」）；現在只在兩個 skill 的經驗紀錄。
- 為什麼可帶到下一個專案：多個變體（不同 core、不同 macro、不同 corner 組合）共用一份 flow 設定很常見，一邊調好會讓另一邊壞。

**R7. EM 的 checker 列為「下一個專案開始時做成 checker」（流程文件 4.6 signoff 清單加一項；`signoff-criteria` 規則 14 加「自動防護：沒有」的寫法）**
- 寫什麼：電源網路的 EM 用 `analyze_power_grid -enable_em -em_outfile` 輸出每段電流，與 tech LEF 的電流密度上限比，含 via 個別比對；電流用與 IR 相同的 max power pattern。依 ADR-0020 決定 2 的寫法，先寫進流程、標明目前沒有自動防護。
- 依據：Phase 4 研究單點供電時 via4 超過上限、Phase 5 最壞組合 via4 78%（ADR-0017），flow 從沒有檢查；登記表 I12 列為「下線前要做」，但流程文件沒有這一步。這是新 checker，依 CLAUDE.md 規則 13 由使用者決定要不要做、何時做。
- 為什麼可帶到下一個專案：sky130 預設 PDN 的 via 只有一個 cut（knowledge S23），任何較大的設計都可能碰到，而 LibreLane 預設不檢查。

**R8. 不在 regression 裡的 checker，Phase 收尾時要確認最後一次在哪裡跑（`phase-exit-review` 規則 2 加一點）**
- 寫什麼：exit review 列出不在 regression 的 target（本 repo：`neg-char`、`ci-sram-ref`、`sram-extract` 等），寫出每一個最後一次跑的 commit 與環境；程式在那之後改過，就在乾淨 checkout 補跑。
- 依據：`neg-char` N9–N16 從 Phase 5 起只在主目錄跑過（phase5.md 已知限制 10，登記表 S21）。還沒出事，風險是推測，所以只建議寫進 `phase-exit-review` 的做法，不加 checker。
- 為什麼可帶到下一個專案：跑很久的 negative test 常被移出 regression，沒人追蹤就會悄悄壞掉。

**R9. `make py-check` 的範圍寫清楚（`flow-regression-reproducibility` 規則 9 補一句）**
- 寫什麼：它只看同一個檔案內的名稱，從別的模組 import 的名稱改名看不到；改了共用模組的函式名稱時，對每個 import 它的腳本跑一次 `python3 -c "import <模組>"` 或該腳本的最短案例。
- 依據：Phase 4 審查第 9 項（讀程式確認），phase4.md 已知限制 10；規則 9 已列出其他看不到的寫法，只缺這一項。只改說明，不加 checker。

**R10. neg_char 平行案例的 race 補一列經驗紀錄（`openram-macro-characterization` 或 `signoff-checker-qualification` 的經驗紀錄）**
- 寫什麼：平行跑的 negative test 案例若共用一個產生出來的中間檔，要在分支之前產生一次。
- 依據：只出現一次（`2251c4a`），依規則 3 只寫經驗紀錄；目前只在 commit 訊息，沒照 CLAUDE.md 規則 2 記錄。

**R11. 過期文字一次改掉（第三節 1–3 項；第 4 項由使用者決定）**
- `librelane-run-debug` 規則 5、`pdn-ir-drop`「待補」、`core-migration-hazard3`「待補」。改 skill 時依 CLAUDE.md 規則 5 同步 README 與 `make skill-check`。

## 五、和 ADR-0020（A1–E3）重疊的項目

| 本文件 | ADR-0020 | 說明 |
|---|---|---|
| P4-01 | C1、A3 | 加嚴後 40 ns 不過 |
| P4-03 | C2、C3、E1 | 15 corner 跑不完就減 corner；補償沒回收 |
| P4-04 | D4、E1 | CTS 對齊 macro latency；hold 0.3 ns |
| P4-07 | D2 | IR 模型太樂觀 |
| P4-08 | A2、D2 | 供電位置假設 |
| P4-10、P4-12、P4-13、P4-14 | E3 | 審查在收尾才找到 |
| P4-17 | E2 | golden 中間輪 DRC 數 |
| P4-27 | E3 | regress 跑 4 次 |
| P5-05 | C2 | 弱 cell |
| P5-06 | C3、E1、D3 | resizer 沒看 ss −40°C |
| P5-08 | A3、D3 | 43 → 44 ns |
| P5-12 | E2 | Hazard3 golden 不可重現 |
| P5-16 | E3 | 審查第 5 項 |
| P5-17 | D3（相關） | ADR-0020 沒涵蓋「舊變體也要重 harden」，見 R6 |
| P5-23 | E3、E2 | 審查的 6 項漏洞 |
| P5-24 | E1、D2、C1 | IR 依據只在 PicoRV32 量 |
| P5-27 | E2 | 清空誤差後多一輪 |
| P5-28 | D3 | flow 設定只改 design 層沒達成 |
| P5-32 | E1 | 補償沒回收 |

共 20 個問題（P4-10、12、13、14 各算一個）。這些的「何時該看」已由 ADR-0020 寫進流程；本文件確認它們的捕捉位置都在，沒有另外的寫回建議（R2 是失控時的自動停，和 C2 的弱 cell 查表是不同的防線）。

## 限制

- 只讀檔案與 git，沒有重跑任何工具；所有「代價」都是從 commit 時間與文件推算。
- Phase 3.5 與 Phase 4 在 10-04 晚上時間重疊；Phase 3.5 的問題（SRAM 特性化、`.lib` 斜率、P17）由另一份回顧處理，本文件沒有列。
- 「最強的那一層捕捉」的分類是審查者的判斷：例如 P5-26 只有經驗紀錄，但 `test-flow-retry` 會抓到同類錯誤，所以算「有自動防護」。
