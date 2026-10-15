# Phase 6、7 問題總檢討：每個遇到的問題現在被捕捉在哪裡、還缺什麼

審查者：沒有參與 Phase 6、7 實作的 agent，2026-10-15，HEAD `0d47a3d`（只讀檔案與 git，沒有跑 EDA 工具或 make；只寫本檔）。
使用者 2026-10-15 的要求：「主要目的是把完整走過一次，先review一下所有遇到的問題與檢討哪些是要寫進skill與流程裡的」。

## 摘要

**讀了哪些來源**：
- `docs/phase_exit/phase6.md`、`phase7.md`（收斂過程、本階段找到並修正的 checker 問題、與計畫不同的地方、已知限制、獨立審查、規則 10 稽核表）。
- `docs/decisions/0018-openram-self-generated-macro.md`、`0019-phase7-caravel-precheck.md`、`0020-flow-shift-left.md`；`docs/notes/openram_phase6_bringup.md`、`docs/notes/caravel_precheck_phase7.md`；`docs/relaxation_register.md`。
- `runs/p7_review/`（`doc_check.md`、`checker_holes.md`、`chipfoundry_fill.md`、`doc_fixes.md`、`fill_trial/README.md`；`runs/` 不進版控）。
- `git log`：Phase 5 結案（`ea075ae`，2026-10-08 15:39）之後到 2026-10-15 11:22（`0d47a3d`）的 48 個 commit 與 commit 訊息（Phase 6 從 `1a28c50` 到 `98f49b7` 14 個，Phase 7 從 `f316425` 到 `0d47a3d` 34 個）。
- 23 個 skill 的 `SKILL.md`：規則本文，以及經驗紀錄中日期在 2026-10-08～10-15 的 106 列。
- `arvinsa-rtl-gds-flow.md`（流程文件）全文；`docs/notes/flow_retro/README.md`、`retro_p6_7.md`（只用來標重疊，不重做）。

**結果**：
- 問題共 **95 個**（Phase 6：45、Phase 7：50；同一件事只列一次，重複出現的寫在同一列）。
- 現在捕捉到的程度（每個問題取最強的那一層）：
  - skill 規則本文或流程文件，**而且有自動防護**（checker 或 negative test）：**43**
  - skill 規則本文或流程文件，沒有自動防護（或已寫明「沒有自動防護」與原因）：**32**
  - 只在 skill 經驗紀錄：**14**
  - 都沒有（只在 ADR、exit review、筆記或 commit 訊息）：**6**
- **建議寫回 16 項**（第 3 節，依重要性排序；第 16 項是可選）。其餘 79 個問題結論「不用動」：大多數已經有規則、checker 與 negative test，或根因只是推測（依 CLAUDE.md 規則 3 只能留在經驗紀錄）。
- 和 ADR-0020 的 19 條提早檢查（A1–E3）重疊的有 **23 個問題**（第 4 節）；這些的「太晚才看」已由 ADR-0020 處理，本檔只檢查它們的症狀與防護有沒有寫到。16 項建議寫回中，第 7 項（fill 與金屬密度，A2／D5 只寫了「要查」，沒寫查到的結果）與第 12 項（B4 換 macro 檢查單沒寫到的一種）和 ADR-0020 部分重疊，其餘都是 ADR-0020 沒涵蓋的。

**最重要的發現**（細節在第 3 節）：
1. **regression 對本機資源不足沒有任何防護，而這是同一類現象第三次發生**（Phase 5 OOM、Phase 6 兩個 `neg-pnr` 同時跑被系統中止、Phase 7 磁碟滿與 swap 下 KLayout 當掉）；目前只在經驗紀錄與 exit review 已知限制 20，流程文件與 skill 規則都沒有。
2. **「之後再處理」的項目沒有被追蹤**，出現三次：Phase 6 決定「選定 macro 後修 DRC」卻漏進待辦（多跑一輪 harden）、`make openram-macro` 改過後沒有從頭完整跑過（ADR-0018 第 99 行，之後找不到執行紀錄）、Phase 7 `timing-constraints-sdc` 規則 14 寫「Phase 7 會加的比對」結案時沒加。回顧報告提過（`retro_p6_7.md` E14），但沒有進 ADR-0020 的 19 條。
3. **改 checker 時變數名稱互相覆蓋，實際是第三次**：`signoff-checker-qualification` 規則 13 只記了 Phase 6 的 `files` 與 Phase 7 的 `defines`，漏了 Phase 7 的 `cbf2c5e`（`check_soc.py` 模組層迴圈變數 `x, y` 蓋掉 SRAM 原點）。
4. **文件與決定不同步**：Phase 5、6、7 的文件核對每次都找到一批「後面的決定改了，前面的文字沒標」，沒有對應的規則。
5. **證據沒有留存**：OOM 的 `dmesg`、scratchpad 裡的量測、licon.14 容許面積的計算、knowledge 檔引用的 signoff 目錄被下一次 harden 覆蓋，審查都無法核對；`librelane-run-debug` 規則 6 只管 run 目錄。

**讀法**：
- 「捕捉」欄的代號照使用者的分類：(a) skill 規則本文、(b) 只在 skill 經驗紀錄、(c) 流程文件的哪一節、(d) 自動防護（checker 或 negative test）、(e) 都沒有。
- 「代價」從 commit 時間與文件寫的 run 時間估，**commit 間隔只是上限，不是實際工時**，都標「估計」。
- 「根因」照原始文件的標記：已驗證／推測。
- 〔ADR-0020 xx〕標出和 19 條提早檢查重疊的項目。
- 行號以 HEAD `0d47a3d` 為準；`runs/` 下的檔案不進版控。出處欄的「筆記」：Phase 6 表指 `docs/notes/openram_phase6_bringup.md`，Phase 7 表指 `docs/notes/caravel_precheck_phase7.md`。

---

## 1. Phase 6（OpenRAM 自產 SRAM，2026-10-08～10-12）

| 編號 | Phase | 問題（白話） | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 出處 |
|---|---|---|---|---|---|---|---|---|---|
| P6-01 | 6 | OpenRAM 官方只支援 x86_64 Linux 的 nix 環境；本機 macOS 用 `use_nix=False` 加本機工具，Colab 跑官方環境對照；Colab 已在 devShell 時 `use_nix=True` 報 `could not find a flake.nix file` | 環境、平台 | 10-08 一天內完成環境、產生、DRC／LVS（估計，含 P6-02～05） | 已驗證 | (a) `openram-macro-characterization` 規則 21；ADR-0018 決定 1 | 無 | 不用動 | ADR-0018:11–16、:31；筆記 `openram_phase6_bringup.md`:45–51 |
| P6-02 | 6 | `make sky130-install` 少複製 cell（`cp $?` 只複製比目標新的檔）卻 exit 0，產生時才報 `Custom cell pin names do not match spice file` | 工具缺陷 | 數十分鐘（估計） | 已驗證 | (a) 同 skill 規則 19；(d) `check_install.py`、`neg-openram` I1–I4 | 無 | 不用動 | 筆記:20（表第 1 項）；`phase6.md`:159、:298 |
| P6-03 | 6 | OpenRAM 的 log 有 `ERROR ... LVS mismatch`，exit code 仍是 0，GDS／LEF／.lib 照常輸出 | 工具缺陷 | 小（當天發現） | 已驗證 | (a) 規則 18；(c) 4.3 第 1 項；(d) `gen_macro.judge`、`neg-openram` O1–O8 | 無 | 不用動 | 筆記:21（表第 2 項）；`phase6.md`:158、:297 |
| P6-04 | 6 | 新版 PDK（`8afc834`）把 bitcell 元件改名、改萃取規則，OpenRAM 的 LVS 45 個 cell 不一致；macro 的產生與 DRC／LVS 改用 OpenRAM 釘的 2022 PDK | 工具與 PDK 版本 | 數小時（估計，含對照實驗） | 已驗證（只換 PDK 的對照） | (a) 規則 17；登記表 S16；precheck PDK 同樣命名 → (a) `tapeout-precheck-caravel` 規則 4 | 無 | 不用動 | ADR-0018 決定 5（:35–40）；筆記:22（表第 3 項） |
| P6-05 | 6 | 同一份設定連跑兩次，GDS 的 met2／met3／via2 繞線不同；要固定 `PYTHONHASHSEED=0` | 工具缺陷 | 小 | 已驗證 | (a) 規則 20；自動防護寫明「沒有」與原因 | 無（「沒有自動防護」已寫原因，符合規則 10） | 不用動 | `phase6.md`:300；ADR-0018:40 |
| P6-06 | 6、7 | GDS 檔頭（BGNLIB／BGNSTR）存日期，同一版圖每次產生的 sha256 都不同：OpenRAM 重產（10-08）、乾淨 worktree 重跑 harden（10-11）、precheck 受檢 GDS 的 sha1（10-14）三次 | 工具行為 | 每次各花一段時間逐 byte 比對（估計 < 1 小時／次） | 已驗證（清掉日期後 sha256 相同） | (a) `openram-macro-characterization` 規則 20（只寫 macro 產生）；(b) `flow-regression-reproducibility` 經驗紀錄 2026-10-11；precheck 的做法只在筆記 | harden 可重現性與「checker 綁 GDS 時」的做法沒有進 `flow-regression-reproducibility` 規則；出現三次，已驗證 | 見第 3 節第 6 項 | 筆記:90；筆記 `caravel_precheck_phase7.md`:157；`flow-regression-reproducibility` SKILL.md:96 |
| P6-07 | 6 | OpenRAM 自己的 DRC 不是 full 規則：Magic full 多 4 種錯誤（met2.2、met3.2、via2.2、nwell.5a）；sky130 產生器固定會出的版圖錯誤 | 工具缺陷 | 數小時（估計，含 patch 0002） | 已驗證 | (a) 規則 22；(c) 4.3 第 3 項；(d) `macro_drc.py`、`neg-openram` D1–D8 | 無 | 不用動 | ADR-0018 決定 6（:41–44）；`phase6.md`:296 |
| P6-08 | 6、7 | **決定「之後再處理」的項目沒有被追蹤**：①決定 6「選定 macro 後只修那一顆」漏進待辦，選定的 macro 仍有 met2.2 13、nwell.5a 10，到第二輪 harden 才一起處理；②`make openram-macro` 改成檢查 .lib 範本後「還沒有從頭完整跑過一次」，之後的 exit review 與登記表都找不到後續執行紀錄（推測一直沒跑）；③Phase 7 `timing-constraints-sdc` 規則 14 寫「Phase 7 第 5 項加一列比對腳位 slew」，結案時沒加，文件核對才發現 | 流程順序 | ①第二輪 harden（兩個 CPU）白跑，`3ceca55`→`ad184f5` 約 3.5 小時（估計，含 patch 0002–0004 與兩次 2 KB 重產 45＋51 分鐘）；②未知；③多一個防護缺口與一輪修正 | 已驗證（原文寫明「待辦清單漏了這一項」） | (e)：流程文件與 skill 都沒有「延後的決定要進待辦」；CLAUDE.md 規則 11 只規定待辦的位置與格式。回顧 `retro_p6_7.md` E14 提過，ADR-0020 沒收 | 出現三次，已驗證；沒有任何規則 | 見第 3 節第 2 項 | ADR-0018:91、:99；`runs/p7_review/doc_check.md`:31–32（S36）；`retro_p6_7.md`:31、:84 |
| P6-09 | 6 | 自產 macro 照預設設定（words per row 4）也在 ss −40°C、ss 25°C、tt −40°C（1.60 V）讀成前一次的值；words per row 1 讀得對但 446.99 × 1152.58 µm 放不進 die；改用 sense amp 輸入端預充電（patch 0001） | 規格或假設（macro 電路） | 約 1 天（10-08，回顧估計） | 已驗證（對照組重現 ADR-0010） | (a) `openram-macro-characterization` 規則 13；`hard-macro-integration` 規則 5、8；(c) 4.3 第 0、4 項 | 無（「選定前就做」已由 B1 寫進流程） | 不用動〔ADR-0020 A1、B1〕 | ADR-0018 決定 3、7、8（:33、:45–49）；筆記:103–201 |
| P6-10 | 6 | patch 0001 讓 `port_data` 多一支 `p_en_bar`，bank 的 `get_pin` 報 `Should use a pin iterator since more than one pin` | 工具缺陷（OpenRAM） | 小 | 已驗證 | (a) 規則 23（description 有錯誤訊息） | 無 | 不用動 | `openram-macro-characterization` 經驗紀錄 2026-10-08（SKILL.md:243） |
| P6-11 | 6 | SRAM 閒置 port 1 的 `clk1` 接 0：chip-select DFF 從不鎖存、沒有 reset，上電可能讓一列 wordline 一直開著；從 Phase 1 的 RTL 就存在（預建 macro 同電路），Phase 5 結案的 SoC 有上電風險 | 規格或假設（未用 port 的接法） | 探針實驗數小時（估計）；RTL 改一條線 | 已驗證（探針＋單一變因實驗） | (a) `hard-macro-integration` 規則 3；(c) 4.3 第 4 項；(d) `check_soc.py port1_tieoff`、`neg-pnr` P65 | 無 | 不用動〔ADR-0020 B1：未用 port 照實際接法〕 | ADR-0018 決定 9（:50–53）；筆記:217–251 |
| P6-12 | 6 | port 1 永遠不選時 sense amp 浮接、上下同時導通，漏出穿透電流（ff 100°C 最大 5.34 mW），不在 .lib 裡 | 規格或假設 | 包含在 P6-13 | 已驗證（探針） | (a) 規則 25；`pdn-ir-drop` 規則 12；(d) `neg-pnr` P77；登記表 I10 | 無 | 不用動 | ADR-0018 決定 11（:56–60）、已知限制（:146） |
| P6-13 | 6 | SRAM 功耗與漏電量法換了 5 次（修剪＋外插 → 完整網表 → `.ic`＋快速量法 → DC 工作點不可行 → 量測窗加絕對門檻、gmin），問題幾乎都在 −40°C | 量測方法 | 約 2 天（10-09～10-10；使用者：「一顆2KB SRAM不可能要搞兩天」） | 已驗證 | (a) 規則 25、27、28；(d) `neg-char` N17–N21 | 流程文件 4.3 第 5 項沒有寫規則 27（新量法先在修剪網表把所有 corner 跑過，最冷的先跑），下一個專案從流程文件進來時看不到；回顧 E7 提過，ADR-0020 沒收 | 見第 3 節第 11 項 | ADR-0018 決定 10–15（:54–82，:69 使用者原話）；`retro_p6_7.md`:35、:77 |
| P6-14 | 6 | `sramchar.run` 的逾時 `subprocess.TimeoutExpired` 沒轉成 FAIL，`make openram-power` 4 小時後中斷卻沒有 `power: FAIL` 行 | checker 漏洞（工具沒跑完） | 約 4 小時的 run（估計） | 已驗證 | (b) `openram-macro-characterization` 經驗紀錄 2026-10-09（SKILL.md:248）；程式已改 | 一般原則已在 `signoff-checker-qualification` 規則 1（工具沒跑完一律 FAIL） | 不用動 | 同左 |
| P6-15 | 6 | 2 KB 完整網表 5 個 PVT 同時跑 ngspice，每步慢 10–40 倍、CPU 只有約 64%（記憶體壓縮；每個 run 約 4.2 GB） | 資源不足 | 一次重跑（估計數小時） | 已驗證 | (a) 規則 4 與 description | 無 | 不用動 | 同 skill 經驗紀錄 SKILL.md:249 |
| P6-16 | 6 | ngspice 的 DC 解讓沒寫過的 bitcell 停在 `Q = Q_bar`（半穩態）；DC 工作點量漏電不收斂；−40°C 量測窗不平（節點耦合到地以下慢慢回升） | 工具行為（ngspice） | 包含在 P6-13 | 已驗證 | (a) 規則 25（`.ic`、不要用 DC 工作點、量測窗判準）；(d) N20 | 無 | 不用動 | ADR-0018 決定 13、14（:66–75） |
| P6-17 | 6 | ngspice 的 `gmin` 蓋過單顆 bitcell 漏電（13.1 pS 不隨溫度變） | 工具行為 | 包含在 P6-13 | 已驗證（gmin 掃描） | (a) 規則 28；(d) `power.cell_gmin_problem()`、N21 | 無 | 不用動 | ADR-0018 決定 15（:76–82） |
| P6-18 | 6 | OpenRAM dev 的 .lib internal_power 是 1e9–1e11（上游 issue #294 未修）；`make openram-macro` 的 view QA 原本檢查原始 .lib，2 KB 一定 FAIL | 工具缺陷 | 小 | 已驗證 | (a) 規則 24；(d) `gen_char_lib.py` 拒收、`neg-openram` L1–L2、`neg-macro-views` Q1 | 無 | 不用動 | ADR-0018 決定 17（:101）、已知限制（:156）；`phase6.md`:299 |
| P6-19 | 6 | 1RW 在釘住的 OpenRAM 產不出 DRC／LVS 乾淨的 sky130 layout | 工具缺陷 | 試產一次（估計 1 小時） | 已驗證（實跑一次） | (a) 規則 26；登記表 S22 | 無 | 不用動 | ADR-0018 決定 11（:59–60） |
| P6-20 | 6 | OpenRAM LEF 的 `DATABASE MICRONS 2000` 讓 OpenROAD 丟掉整份 LEF（`ODB-0205`、`ODB-0292`），floorplan 試跑失敗 | 工具行為 | 一次 floorplan 試跑（估計數分鐘） | 已驗證 | (a) `hard-macro-integration` 清單第 0 項與 description；(d) `neg-macro-views` Q12 | 無 | 不用動 | 筆記:367；`phase6.md`:302 |
| P6-21 | 6 | OpenRAM dev 的網表沒有 `*.PININFO`，`gen_antenna_lef` 取不到輸入腳位；新版 Verilog 模型的 `mem` 宣告位置變了，`gen_sim_model` 的搬移會誤刪 | 工具輸出改變 | 小 | 已驗證 | (a) `hard-macro-integration` 規則 1（SKILL.md:36）；(b) 經驗紀錄 2026-10-10 | 無 | 不用動 | 筆記:366 |
| P6-22 | 6 | OpenRAM 的 LEF 沒有 `FOREIGN`，LibreLane 的 KLayout stream-out 沒有合併 macro 的 GDS，最終 GDS 裡 SRAM 是空的；log 卻印 `All LEF cells have matching GDS cells`。Phase 0 對預建 macro 檢查過 `FOREIGN`，換 macro 時沒重查 | 工具缺陷；換東西時舊檢查沒重套 | 第一輪 harden（兩個 CPU）白跑，`221822a` 13:02 → `3ceca55` 13:55（估計約 1 小時） | 已驗證（單步重跑 `KLayout.StreamOut`） | (a) `hard-macro-integration` 清單第 0 項、規則 10；`lvs-signoff` 規則 1；(c) 4.3 第 2、6 項；(d) Q13、`check_macro_gds.py`、P67、P68 | 無 | 不用動〔ADR-0020 B4〕 | 筆記:370–376；`phase6.md`:94、:301 |
| P6-23 | 6 | SRAM 是空的時，`check_soc.py magic_drc` 的 SRAM 框內 0 個違規仍 PASS（比對的集合是空的） | checker 漏洞 | 同上（同一輪發現） | 已驗證 | (a) `signoff-checker-qualification` 漏洞類型表「比對的對象是空的」；(d) `DRC_IN_MIN_FRAC`、P69 | 無 | 不用動〔ADR-0020 B4〕 | 筆記:375；`phase6.md`:172 |
| P6-24 | 6 | SRAM 真的進了 GDS 後，flow 的 KLayout deck 才在 SRAM 裡報 27 個（nwell.6、psdm.1、m2.2）；預建 macro 是 0，因為 deck 依名稱 `*sky130_sram_*kbyte_*` 排除；Magic deck 與 OpenRAM 都沒報 | 工具行為（deck 依名稱排除）；換東西時舊檢查沒重套 | 第二輪 harden（兩個 CPU）白跑，併入 P6-08①的 3.5 小時 | 已驗證（改名後重跑、讀 deck 原文） | (a) `drc-signoff` 規則 5、6；`openram-macro-characterization` 規則 22；(c) 4.3 第 3 項；(d) `macro_klayout_drc.py`、`neg-openram` K0–K8 | 無 | 不用動〔ADR-0020 B1、B4〕 | ADR-0018 決定 17（:93–94）；`phase6.md`:95、:303 |
| P6-25 | 6 | patch 0003 把 DFF 拉開後，DFF 的 M3 clk 軌與超出邊界的井、implant 斷開（OpenRAM LVS 不一致、KLayout nwell.2a、nsdm.1） | 工具行為（OpenRAM 版圖靠緊貼相接） | 一次 2 KB 重產 45 分鐘（估計） | 已驗證 | (a) 規則 22 | 無 | 不用動 | ADR-0018 決定 17（:95） |
| P6-26 | 6 | Magic 在晶片裡畫的 licon.14 框比 SRAM 單獨檢查長 60–90 nm → 加進位置比對的 100 nm 容許清單（能藏新違規的面積 0.65% → 3.32%） | 工具行為；放寬 | 小；放寬一項 | 已驗證 | (a) `drc-signoff` 規則 2；(d) `neg-pnr` P09、P21；登記表 D03 | 比例的計算沒有存檔（見 P7-39） | 不用動（存檔問題見第 3 節第 5 項） | ADR-0018 決定 17（:97）；`phase6.md`:305 |
| P6-27 | 6 | Magic DRC 每 157.28 µm 切開錯誤框，框數隨陣列位置變；「≤ 預建」改成比合併後的區域（面積容許 0.05%） | 工具行為；放寬 | 半天（估計，含背景 agent 查證） | 已驗證（合併後 XOR 0）；157.28 µm 是不是分塊大小是推測 | (a) `drc-signoff` 規則 2；(c) 4.3 第 3 項；(d) `neg-openram` D5、D8、D8a | 無 | 不用動 | ADR-0018 決定 19（:117–120）；`phase6.md`:304 |
| P6-28 | 6 | 只改 layout 的 patch 讓 OpenRAM 輸出的網表子電路順序與檔頭改變，sha256 不同，特性化的來源檢查會判不同 | 工具行為 | 小 | 已驗證（97 個子電路逐字相同） | (a) `openram-macro-characterization` 規則 22（SKILL.md:129）；(d) `neg-openram` C3–C5、`neg-pnr` P70；登記表 S17 | 無 | 不用動 | ADR-0018 決定 17（:99–100） |
| P6-29 | 6 | `run_eqy.py` 的網表解析只認 `sky130_` 開頭的 cell：換成自產 macro 後 SRAM 的 clock 來源檢查從步驟 4a 起沒執行，PicoRV32 `eqy-soc` 照樣 PASS，直到 negative test 以 `KeyError: 'sram0'` 中止 | checker 漏洞；換東西時舊檢查沒重套 | 步驟 4c 約 5 小時中的一部分（`940e395` 18:10 → `4713c5f` 23:28，估計） | 已驗證 | (a) `formal-equivalence-eqy` 規則 5 第二點、`hard-macro-integration` 規則 10；(c) 4.7、4.3 第 6 項；(d) `run_eqy.py` 要求 `MACROS` 的 instance 被解析到 | 無 | 不用動〔ADR-0020 B4〕 | 筆記:412；`phase6.md`:171 |
| P6-30 | 6 | OpenROAD `repair_timing` 對調等價輸入（`RSZ-0043 Swapped pins`），EQY 報 `conflicting matches for gold bit`、0 個分區 | 工具行為 | 包含在 P6-29 的 5 小時 | 已驗證（排除前後各跑一次） | (a) `formal-equivalence-eqy` 規則 6；(c) 4.7；(d) `neg-eqy-soc` `o21ai_swap` | 無 | 不用動 | ADR-0018 決定 18（:104–106）；`phase6.md`:307 |
| P6-31 | 6 | negative test 本身的問題：`din5_stuck0` 的植入程式弄壞跳脫名稱；`o21ai_swap` 的分區因 EQY `opt` 共用 OR 而落在植入點以外，挑案例要避開共用 | negative test 設計 | 數小時（估計，含使用者兩次選擇） | 已驗證 | (b) `formal-equivalence-eqy` 經驗紀錄 2026-10-10（SKILL.md:91、92、95）；程式 `partition_reads()` | 無（規則 3 已要求斷言抓到的機制） | 不用動 | ADR-0018 決定 18（:107–109） |
| P6-32 | 6 | `neg-pnr` P05 把 SRAM 外框寫死成預建 macro 的座標，換成自產 macro 後只拿掉 4 個多餘的 via，LVS 不會 FAIL（植入沒有生效） | checker 漏洞（negative test 綁舊 macro） | 一次 `neg-pnr`（估計 25 分鐘） | 已驗證 | (e)：只在 exit review 與筆記；`signoff-checker-qualification`「植入沒有生效」的 P05 例子是 Phase 3 的另一個原因；`hard-macro-integration` 規則 10 只提「用舊名稱或前綴認東西的腳本」 | 「negative test 寫死舊 macro 的座標或尺寸」沒寫進換 macro 檢查單 | 見第 3 節第 12 項 | `phase6.md`:97、:173；筆記:411 |
| P6-33 | 6 | dev fixture 自己寫了 `result.txt`，Stop hook 把它當成 harden，要求 criteria review | 流程工具的誤判 | 小 | 已驗證 | (b) `flow-regression-reproducibility` 經驗紀錄 2026-10-11（SKILL.md:95） | 無（只出現一次，處理方式已寫） | 不用動 | 同左 |
| P6-34 | 6 | 獨立審查找到 7 個 checker 漏洞（H1–H7：LEF／GDS 腳位位置、OBS、範本來源、macro DRC 只比總數、deck 名稱排除只防 SRAM、GDS 指紋太粗、power 表只讀第一個數字與 NaN） | checker 漏洞 | `4713c5f` 兩輪 regress 作廢；修正 `e19ef5a` 08:45 → `37c99b4` 14:38（估計約 6 小時） | 已驗證（植入實驗＋對照組） | (a) `signoff-checker-qualification` 漏洞類型表；(c) 4.8 E3；(d) Q14–Q20、P71–P76、K7、K8、C6、C7 | 無 | 不用動〔ADR-0020 E3〕 | `phase6.md`:235–249；ADR-0018 決定 19 |
| P6-35 | 6、7 | 修審查漏洞時新變數蓋掉同函式後面要用的名稱，`check_inputs.py --resolved` 對每個 run 都 FAIL：Phase 6 `files`（結案 regress 兩輪 FAIL）、Phase 7 `defines`（開 regress 前的 positive control 抓到） | checker 漏洞（修正時引入） | Phase 6：兩輪 regress 共 76 分鐘白跑；Phase 7：小 | 已驗證 | (a) `signoff-checker-qualification` 規則 13、漏洞類型表；`phase-exit-review` 規則 2；(d) `neg-pnr` P00、C00 | 第三個同類例子沒記（見 P7-25） | 見 P7-25 | `phase6.md`:179–186；`phase7.md`:194 |
| P6-36 | 6 | SRAM 版圖萃取到 Phase 6 最後才做：讀出時間是電路圖的 2.0 倍（假設 × 1.6），dout0 transition .lib 寫 0.5 ns、實際 1.4–2.2 ns；使用者選不改 .lib | 量測順序；放寬 | 試跑約 3 小時；放寬 3 項；Phase 7 wrapper 換成實際 transition 後 setup +0.548 → +0.151 ns | 已驗證 | (a) `openram-macro-characterization` 規則 10、29；(c) 4.3 第 5 項（B2）；登記表 S04、S07、S08、S20 | 無 | 不用動〔ADR-0020 B2、E1〕 | ADR-0018 決定 20（:122–128）；`phase7.md`:113 |
| P6-37 | 6 | Magic 階層式萃取放負值修正電容，攤平後 263 個節點總電容為負，ngspice `Timestep too small` | 工具缺陷 | 包含在 P6-36 | 已驗證 | (a) 規則 10；(d) `extract_sram.py`、`neg-char` N22 | 無 | 不用動 | `phase6.md`:308 |
| P6-38 | 6 | `neg-char` 不在 regress 裡；`ad184f5` 改了 `check_char_lib.py` 的來源檢查之後 `neg-char` 沒有重跑，只有 regress 裡的 `neg-openram` C1–C5 涵蓋（結案時才在主 checkout 補跑 22/22） | 流程（regression 範圍） | 結案補跑約 40 分鐘（估計） | 已驗證 | (c) 4.8「不在 regression 裡、要另外跑的」；登記表 S21 | 規定「改了才跑」但沒有任何東西提醒「改了」：checker 改了而 negative test 的結果過期時沒有 FAIL | 見第 3 節第 10 項 | 筆記:270；`phase6.md`:117 |
| P6-39 | 6 | `clk1` 接時脈後 ss −40°C 的 clock skew metric 大 0.2–0.4 ns，clock inverter 49 → 87 | 工具行為（推測） | 無（最差 setup／hold 仍 PASS） | 推測（沒有分開實驗） | (b) `cts-clock-tree` 經驗紀錄 2026-10-10 | 推測不能進規則 | 不用動 | `phase6.md`:209、:280 |
| P6-40 | 6、7 | detailed routing 對 SRAM 25 支腳位報 `DRT-0418 ... has no pins on routing grid`（預建 macro 沒有），最終 DRC／LVS 0；Phase 7 wrapper 同樣 25 次 | 工具行為 | 無 | 推測（腳位沒對齊繞線格點，沒查） | (b) `hard-macro-integration` 經驗紀錄 2026-10-10（SKILL.md:85）；已知限制 | 推測不能進規則 | 不用動 | `phase6.md`:210；`phase7.md`:118 |
| P6-41 | 6 | golden README 把 `power__total` 的增加歸因錯了，也沒說它是最後寫入的 corner 的值 | 文件與實作不一致 | 文件修正 | 已驗證 | (a) `librelane-run-debug` 規則 4；`phase-exit-review` 規則 3 | 無 | 不用動 | `phase6.md`:228–229 |
| P6-42 | 6 | IR 最壞組合只判 max_ff_n40C，自產 SRAM 讓 max_ff_100C 的功耗高約 10%，port 1 浮接電流也沒算 → 兩個 ff corner 都跑、加浮接電流（Phase 7 又改成慢 corner，見 P7-19） | 規格或假設；放寬的依據只在一個設計量過 | 一次實測＋改 checker（估計數小時） | 已驗證 | (a) `pdn-ir-drop` 規則 12；(d) P77、P78 | 無 | 不用動〔ADR-0020 C1、E1〕 | ADR-0018 決定 19（:116）；`phase6.md`:252 |
| P6-43 | 6 | Colab 的 `colab exec` 約 1 小時後回 401／404，CLI 刪掉本機紀錄但 VM 還在伺服器上 | 環境（外部服務） | 一次 Colab 產生作廢（估計 1 小時） | 已驗證 | (a) 全域 `/colab` skill（`~/.claude/skills/colab/SKILL.md`:89，不在本 repo） | 無 | 不用動 | 筆記:94 |
| P6-44 | 6 | 本 repo 腳本的小錯：`make openram-setup` 遇到 `uv venv` 建的 venv 沒有 pip；`macro_drc.py` 輸出路徑是相對路徑，Magic 找不到 Tcl 檔（checker 判 FAIL，沒有誤判 PASS） | 人為操作（腳本） | 小 | 已驗證 | (e)：只在筆記；程式已修 | 都是大聲的失敗，修完不會再出現 | 不用動 | 筆記:88、:101 |
| P6-45 | 6 | 使用者 10-10：「這一輪浪費太多時間」，要求先規劃再做，一次決定步驟 4–5 的事先授權範圍（哪些可直接做、哪些一定要問） | 流程（決策方式） | 前一輪的等待與來回（估計數小時） | 已驗證（使用者原話） | (e)：只在 ADR-0018 決定 16；使用者的 auto-memory「決策一次問完」（不在 repo，其他專案帶不過去） | 「長段工作開始前一次取得事先授權」沒寫進流程 | 見第 3 節第 16 項（可選） | ADR-0018 決定 16（:84–88） |

---

## 2. Phase 7（Caravel wrapper 與 ChipFoundry precheck，2026-10-12～10-15，含結案期間）

| 編號 | Phase | 問題（白話） | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 出處 |
|---|---|---|---|---|---|---|---|---|---|
| P7-01 | 7 | `cf precheck` 一定用 Docker 跑只有 linux/amd64 的官方 image；本機 arm64 改用 lima VM＋Rosetta（colima 要從 GitHub release 下載，只有約 80 KB/s） | 平台規定、環境 | 環境建置約 1–2 小時（`f316425` 08:46 → `cc60b85` 10:21，估計） | 已驗證 | (a) `tapeout-precheck-caravel` 規則 1；登記表 D12 | 無 | 不用動 | 筆記 `caravel_precheck_phase7.md`:14–19、:84 |
| P7-02 | 7 | 容器每次 `pip install --upgrade cf-precheck`，不同天跑版本可能不同 | 平台行為 | 小 | 已驗證（讀 cf-cli 原始碼） | (a) 規則 1；(d) `neg-precheck` `other_version` | 無 | 不用動 | 筆記:16；`phase7.md`:320 |
| P7-03 | 7 | precheck 的新 deck（2026-05 拿掉 `areaid.ce` 的豁免）在任何 OpenRAM bitcell（包括 PDK 預建 SRAM）報 `MR_licon.SP.6`、`MR_mcon.CON.10`；官方結果仍是 FAIL，exit 條件改成比對預建 SRAM 的位置 | 平台規定；放寬 | 判定 checker 與 negative test（步驟 6，估計半天）；放寬一項（登記表 D08） | 已驗證（比對兩份 deck 與 commit diff） | (a) 規則 2、3；(c) 4.7「下線預檢」；(d) `make precheck-check`、`neg-precheck` | 無 | 不用動〔ADR-0020 B1、A2〕 | ADR-0019 決定 5（:21–27）；筆記:65–80 |
| P7-04 | 7 | deck 用 deep 模式，違規掛在哪一層 cell 隨 macro 而不同，兩顆 macro 的 bitcell array 位置差 (5.61, 9.32) µm；「同一個 cell、同一個相對位置」照字面做不到，改成展開到相對 array 原點的位置 | 工具行為 | 包含在 P7-03 | 已驗證 | (a) 規則 3；description | 無 | 不用動 | ADR-0019:26；`tapeout-precheck-caravel` 經驗紀錄 2026-10-14 |
| P7-05 | 7 | 寫 wrapper RTL 時先選 GPIO 8–20，沒看 pad 位置；到 floorplan 才發現離 block 2–3 mm，使用者指出流程順序錯了 | 流程順序 | RTL、`user_defines.v`、testbench 重做，約 1.5 小時（`ccdc21d` 09:51 → `8654670` 11:22，估計）；另建四層強制 | 已驗證 | CLAUDE.md 規則 14；(a) `chip-floorplan-pin-planning` 規則 1、`tapeout-precheck-caravel` 規則 5；(c) 4.1；(d) `make pin-plan`、`neg-pin-plan` 26 個、hook `require_pin_plan.py` | 無 | 不用動 | ADR-0019 決定 10、13（:36–37、:53–58） |
| P7-06 | 7 | 出 floorplan 圖時：停在 PDN 的 DEF 還沒有範本腳位；停在套用範本時 cell 沒有位置，要跑到 global placement | 工具行為（step 順序） | 4 次試跑（估計 < 1 小時） | 已驗證 | (a) `chip-floorplan-pin-planning` 規則 4 與 description | 無 | 不用動 | 同 skill 經驗紀錄（SKILL.md:65–66） |
| P7-07 | 7 | Caravel 固定範本本來就畫到 die 外，每次都報 `PDN-0239 Ring shape falls outside the die bounds` 與 `GRT-0036 Pin ... is outside die area`（and 1000 similar） | 工具行為（預期警告） | 小（查證一次） | 已驗證（座標與官方範例 DEF 相同，官方 precheck XOR PASS） | (b) `tapeout-precheck-caravel` 經驗紀錄 2026-10-12（SKILL.md:104、107） | 下一顆 Caravel 設計看到同樣的警告時，description 搜不到這兩個代號 | 見第 3 節第 14 項 | 同左 |
| P7-08 | 7 | 沒接東西的 inout `analog_io` 被 OpenROAD 同時算成 driver 與 load，`RepairDesignPostGRT` 中止於 `RSZ-0074` | 工具缺陷 | 一次 harden 中止在第 41 步（`p7_harden2` 78 分鐘，估計） | 已驗證（讀原始碼、前後各跑一次） | (a) `librelane-run-debug` 已知陷阱與 description；(d) `check_inputs.py inout_dont_touch`、P79 | 無 | 不用動 | `phase7.md`:94、:324 |
| P7-09 | 7 | `inout_dont_touch` 只看向量的 bit 0（審查 H8） | checker 漏洞 | 修正併入 P7-37 | 已驗證（植入實驗） | (a) 漏洞類型表「向量只檢查一個 bit」；(d) P79 `bit0` | 無 | 不用動 | `runs/p7_review/checker_holes.md`:22、:128–136 |
| P7-10 | 7 | OpenSTA 對設了 driving cell 的腳位忽略 `set_input_transition`（不管順序），log 沒有警告 | 工具行為 | 對照實驗（估計 1 小時） | 已驗證（對照實驗） | (a) `timing-constraints-sdc` 規則 14；(d) `check_soc.py max_slew` 反向檢查、C80d（只涵蓋高於 slew 上限的腳位） | **低於上限的腳位**（`wb_clk_i`、`io_in` 等）的 transition 有沒有生效，沒有自動防護（已知限制 8） | 見第 3 節第 9 項 | ADR-0019:63；`phase7.md`:222、:325 |
| P7-11 | 7 | 自己跑 STA 實驗時把 `CLOCK_PERIOD` 設成整數 44，Tcl 整數除法讓 input delay 變 8（LibreLane 傳 8.8） | 人為操作 | 小 | 已驗證 | (b) `timing-constraints-sdc` 經驗紀錄 2026-10-12（SKILL.md:61） | 只出現一次 | 不用動 | 同左 |
| P7-12 | 7 | Caravel 官方 SDC 的 input transition（0.84–0.97 ns）超過本 repo 的 slew 上限（0.70／0.75 ns），每個 corner 384 個違規；改成邊界另判 | 平台規定；放寬 | 約 3 小時（`c7d3d2a` → `2c0fed6`，含 RSZ-0074，估計）；放寬一項 | 已驗證 | (a) `tapeout-precheck-caravel` 規則 10、`timing-constraints-sdc` 規則 15；(c) 4.5 C4；(d) `max_slew`、C80a–d；登記表 T10 | 無 | 不用動〔ADR-0020 C4、A2〕 | ADR-0019 決定 16（:68–72） |
| P7-13 | 7 | Caravel 輸入路徑在 ff 100°C hold −0.071 ns：官方約束下 ff 要多延遲約 2.4 ns；GRT 後的 hold 估計樂觀約 0.1 ns；改 GRT hold 餘量 0.2 ns | 平台規定；放寬 | 約 3.5 小時（`d1a7888` 20:32 → `6287a50` 00:03，含 `p7_harden3`、`p7_harden4` 137 分鐘，估計） | 已驗證 | (a) `tapeout-precheck-caravel` 規則 10；(c) 4.5 C4、C3；(d) signoff STA 15 個 corner；登記表 T14 | 無 | 不用動〔ADR-0020 C4、C3〕 | ADR-0019 決定 17（:73–79） |
| P7-14 | 7 | `RSZ_CORNERS` 加 3 個 ff_100C 後，resizer 不再放大 17 顆 `a221oi_1`，改插長串 buffer（4759 顆），global routing 壅塞失敗（`GRT-0116`，溢位 771） | 工具行為 | 包含在 P7-13 | 推測以外的部分已驗證（單步重跑兩邊相同）；不放大的原因沒找到 | (b) `drv-timing-closure` 經驗紀錄 2026-10-12（SKILL.md:137） | 根因沒找到，不能寫規則（規則 10 稽核已寫明沒有自動防護） | 不用動 | ADR-0019:76；`phase7.md`:327 |
| P7-15 | 7 | hold 修復的進度表到第 60 列後看似停住；`RSZ-0032` 的 hold buffer 計數低報（journal restore 歸零） | 工具行為 | 小（判讀時間） | 已驗證 | (a) `librelane-run-debug` 已知陷阱與 description | 無（已寫明沒有自動防護：criteria review 數網表） | 不用動 | `phase7.md`:334；`drv-timing-closure` 經驗紀錄（SKILL.md:136） |
| P7-16 | 7 | 已跑完的 run 用同一個 tag 加 `--from` 接續，讀到修改時間最新的 state，`EST-0026` 後 `RSZ-0074 ... found route to 3 pins, expected 4` | 工具行為（LibreLane） | 一次接續作廢（估計 < 30 分鐘） | 已驗證（讀 LibreLane 原始碼） | (a) `librelane-run-debug` 規則 2、已知陷阱、description | 無（只在手動接續時發生，已寫沒有自動防護） | 不用動 | `phase7.md`:326 |
| P7-17 | 7 | wrapper 有 327 支沒用到的 Caravel 腳位，`Odb.ReportDisconnectedPins` 列出來，soc_top 的判法（必須 0）FAIL | 平台規定 | 小 | 已驗證 | (c) 1.5（`check_soc.py` 的 wrapper 判法）；(d) `neg-pnr --cpu caravel` C15；(b) `tapeout-precheck-caravel` 經驗紀錄 | 無 | 不用動 | `phase7.md`:187 |
| P7-18 | 7 | Caravel 給 user area 的 vccd1／vssd1 各只有一顆 pad，只從 wrapper 左右兩側接進來；ADR 只寫「供電從 core ring 進來」，IR 到 harden 後才量出 104 mV | 平台規定；流程順序 | 約 1 天（Caravel 原始碼查證、5 種供電模型、4 種 met4 寬度、5 個 block 位置，估計） | 已驗證（原始檔核對） | (a) `chip-floorplan-pin-planning` 規則 2、`tapeout-precheck-caravel` 規則 7、`pdn-ir-drop` 規則 14；(c) 4.1、4.4 D2 | 無 | 不用動〔ADR-0020 A2、D2〕 | ADR-0019 決定 11、18（:51、:81–97） |
| P7-19 | 7 | IR 判法一天內改三次（ff 電流＋ss 電阻 → 慢 corner → CPU max power pattern），中途訂了「板子供電 ≥ 1.65 V」又取消；最後餘量 0.44 mV | 規格或假設（signoff 條件太晚定） | 約 1 天（10-12 夜～10-13 02:11，估計）；`ir_worst.py`、`ir_caravel.py`、`ir_pattern.py` 改寫 | 已驗證 | (a) `signoff-criteria`「IR 用多大的電流」、`pdn-ir-drop` 規則 12、14；(c) 4.5 C1、4.7；(d) `neg-ir-soc`、`neg-ir-caravel` | 無 | 不用動〔ADR-0020 C1、D2〕 | ADR-0019 決定 18–20（:81–116） |
| P7-20 | 7 | OpenROAD PSM 的供電點放在 Caravel 跨接線的位置時，讀完供電點檔就 Signal 11，沒有錯誤訊息 | 工具缺陷 | 小（改放點） | 推測（沒查原始碼、沒縮小重現） | (b) `pdn-ir-drop` 經驗紀錄 2026-10-13；description 有症狀；(d) `ir_sources`（C26）只檢查點的位置；登記表 I09 | 推測不能進規則 | 不用動 | ADR-0019:94；`phase7.md`:229、:330 |
| P7-21 | 7 | testbench 遇到 `vcd` 開頭的 plusarg 會從時間 0 傾印整個 testbench 到 `wave.vcd`，指定的錄波 VCD 是 0 bytes | 工具行為（testbench 撞名） | 一次錄波（估計 30 分鐘） | 已驗證 | (a) `gate-level-simulation` 規則 9 與 description；(d) `neg-ir-soc` `stray_dump` | 無 | 不用動 | `phase7.md`:188、:333 |
| P7-22 | 7 | 第一次錄波用 testbench 的 40 ns 時脈（signoff 44 ns），原以為差 10%、實際 2%；判定 checker 不比 VCD 的週期與 `CLOCK_PERIOD`（審查 H2） | checker 漏洞 | 重錄一次；修正併入 P7-37 | 已驗證 | (a) `gate-level-simulation` 規則 9、`pdn-ir-drop` 規則 14；(c) 4.7；(d) `ir_pattern.check_inputs()`、`neg-ir` `period` | 無 | 不用動 | ADR-0019:109；`checker_holes.md`:16 |
| P7-23 | 7 | 最後一次 slew 修復後重新 global routing，把一條內部 net 擠去繞路（0.779 ns），之後沒有步驟再檢查 slew；四種修法不收斂，placement 密度 55 → 50% | 工具行為；放寬 | 約半天、6 個實驗 run（ADR 寫的） | 已驗證 | (a) `drv-timing-closure` 規則 13、`floorplan-congestion` 規則 5；(d) `max_slew`、P80、C80a；登記表 T20 | 無 | 不用動（floorplan 試跑看不到，已寫成 D1 的限制） | ADR-0019 決定 21（:118–139） |
| P7-24 | 7 | 繞線後 ECO 在釘版 OpenROAD 做不到（寄生來源沒實作，`RSZ-0074`；增量 detailed routing 違規停在約 5600 條） | 工具缺陷 | 包含在 P7-23 | 已驗證 | (a) `drv-timing-closure` 規則 13 與 description | 無（已寫明工具限制、沒有自動防護） | 不用動 | ADR-0019:128；`phase7.md`:329 |
| P7-25 | 7 | `check_soc.py` 的 wrapper `ir_sources` 迴圈在模組層用 `x, y`，蓋掉從 DEF 讀到的 SRAM 位置，`magic_drc` 把 5,572,955 個 SRAM 內的違規全判成框外（FAIL，沒有誤判 PASS） | checker 漏洞（變數重名） | 一次 harden 的判定錯誤與查證（`cbf2c5e` 10-13 05:07，估計 1 小時） | 已驗證（commit 訊息：改名後 0 outside） | (e)：只在 `phase7.md` 與 commit 訊息；`signoff-checker-qualification` 規則 13 只列 Phase 6 `files`、Phase 7 `defines`，沒有這一例，而且只講「同一個函式」 | 同類第三次；規則 13 的範圍（同一函式）比實際（模組層迴圈）小；`py-check` 看不出重新賦值 | 見第 3 節第 3 項 | `phase7.md`:183；`git show cbf2c5e` |
| P7-26 | 7 | 好網表也有分區證不出來：pin swap 加上 EQY 前處理的共用，切分點遺失邏輯關係（`_10122_.B`）；用 amend 重試一次 | 工具行為 | 約 6 小時（`f721cff` 10:46 → `f4ea9de` 16:57，含 P7-27，估計） | 已驗證 | (a) `formal-equivalence-eqy` 規則 7；(c) 4.7；(d) `nand2_comb_to_nor2` | 無 | 不用動 | ADR-0019 決定 23（:155–163） |
| P7-27 | 7 | amend 重試的第一版把 flip-flop 併進分區，`sat` 變空洞證明，植入的 nand2 → nor2 被判 PASS；negative test 的 `REQUIRE` 擋下 | checker 漏洞 | 包含在 P7-26 | 已驗證 | (a) `formal-equivalence-eqy` 規則 7（含規則 5）；(d) `nand2_flop_to_nor2` | 無 | 不用動 | `phase7.md`:184 |
| P7-28 | 7 | golden 建立後 HEAD 改變，run guard 要求 harden 的 commit 等於 HEAD，正式的 eqy／gl／ir 要等下一次確認 harden | 流程（來源追溯） | 每次多一次確認 harden（182–240 分鐘，估計） | 已驗證 | (a) `flow-regression-reproducibility` 規則 7 | 無 | 不用動 | ADR-0019:149 |
| P7-29 | 7 | wrapper 的 golden 誤差量不出來（四組比較都逐值相同），沿用 hazard3 的值 | 規格或假設；放寬 | 無 | 已驗證 | (a) `signoff-checker-qualification` 規則 11；(c) 4.6 E2；登記表 G05、G06 | 無 | 不用動〔ADR-0020 E2〕 | `phase7.md`:166 |
| P7-30 | 7 | precheck 判定 checker 的第一版有 4 個漏洞（舊報表配新 GDS 判 PASS、版本、沒有座標值的項目、比對基準的來源） | checker 漏洞 | 補檢查與 10 個案例（估計數小時） | 已驗證（cf-precheck `runner.py` 第 23–31 行） | (a) `tapeout-precheck-caravel` 規則 3；(d) `neg-precheck` `stale_results` 等 | 無 | 不用動〔ADR-0020 E3：這次就是寫完就審〕 | `phase7.md`:185 |
| P7-31 | 7 | precheck 實際用的 PDK（`3e0e31dc`）裡的預建 SRAM 另有 10 個 nsdm／psdm 違規，比對基準本身 FAIL；改成只比允許的規則 | 平台規定 | 包含在 P7-32 的 14 小時 | 已驗證 | (a) `tapeout-precheck-caravel` 規則 3、description；(d) `ref_other_rule`、`ref_extra_rule`；登記表 D09 | 無 | 不用動〔ADR-0020 A2〕 | ADR-0019 決定 24（:169、:172） |
| P7-32 | 7 | wrapper 的空白被 PDK 預設 `decap_3` 填滿，li1 密度 75%（precheck 上限 60%）；246 萬個 decap 也是 VM OOM 的主要原因 | 平台規定；工具預設值 | 步驟 7 整段約 14 小時（`1f9d3d9` 01:46 → `c84355d` 15:37，含原本就要跑的 precheck，估計）；多兩次 harden | 已驗證（前後比較） | (a) `tapeout-precheck-caravel` 規則 8、11；(c) 4.6 D5、4.7；(d) `make precheck-check`（harden 內沒有，ADR-0020 已排到下一個專案） | harden 內的密度 checker 已排在下一個專案（ADR-0020 決定 2） | 不用動〔ADR-0020 D5〕 | ADR-0019 決定 24（:164–193） |
| P7-33 | 7 | VM 10 GiB 時 KLayout BEOL 與兩次 Magic 抽取被 OOM kill，`klayout_beol failed (stat=-9)`、LVS `extraction did not complete successfully`、`OEB FAILED (stat=5)` | 資源不足（平台 VM） | 包含在 P7-32 | 已驗證（`dmesg`；原文沒存檔） | (a) `tapeout-precheck-caravel` 規則 1（四項防護齊全）與 description；(d) `env/check_env.sh` 檢查 ≥ 15 GB | `dmesg` 原文沒存（見 P7-39） | 不用動（存證見第 3 節第 5 項） | 筆記:124–131；`phase7.md`:321 |
| P7-34 | 7 | SRAM 當 black box 時，LVS 的 CVC 報 74 個 HI-Z 輸入（SRAM `dout0` 與接在上面的 `buf_4`），沒有自動判定；SRAM 以外如果真的有浮接輸入也不會被抓 | checker 缺口 | 無（這次查證確認全是 SRAM） | 已驗證 | (a) `tapeout-precheck-caravel` 規則 4；登記表 D07 | 沒有自動防護 | 見第 3 節第 15 項 | 筆記:146–148；`phase7.md`:226 |
| P7-35 | 7 | 金屬密度低於下限（met1 18.1%、met2 1.6%…），precheck 只查上限；fill 由誰補到結案審查才查（Efabless 證據強、ChipFoundry 中等）；限時 fill 試跑後 FOM 15 個視窗、met2 1 個視窗低於下限 | 平台規定 | 查證 30 分鐘＋試跑約 91 分鐘；未解決，列為下線前事項 | 已驗證（試跑）；ChipFoundry 是否照做是推論 | (b) `tapeout-precheck-caravel` 經驗紀錄 2026-10-15（SKILL.md:115）；(c) 4.1 A2、4.6 D5；`drc-signoff` SKILL.md:54–56 只寫下限數字；登記表 D14 | `tapeout-precheck-caravel` 規則 9 寫「fill 由誰做與密度上下限（規則 8 與「待確認」）」，但「待確認」一節沒有 fill 這一條；`drc-signoff` 說「chip-level 一定要補 fill」，沒說 Caravel 是整合方在 tapeout 時補、補完另有下限檢查 | 見第 3 節第 7 項 | `runs/p7_review/chipfoundry_fill.md` 結論 1–4；`fill_trial/README.md`；`phase7.md`:215 |
| P7-36 | 7 | 需要 ChipFoundry 回覆的問題（bitcell 兩條規則、自產 SRAM 的 Magic DRC、fill）一直沒送出 | 流程（平台溝通） | 延後到下線前（等待時間沒平行化） | 已驗證 | (a) `tapeout-precheck-caravel` 規則 9；(c) 4.1 A2 | 無 | 不用動〔ADR-0020 A2〕 | ADR-0019 決定 6、26 |
| P7-37 | 7 | 獨立審查找到 8 個 checker 漏洞（H1–H8）與 1 個防護缺口（邊界 slew 沒比 SDC 的值） | checker 漏洞 | 修正 `84fe505` 16:52 → `2b04451` 23:49（估計約 7 小時）＋三條 regress 重跑 | 已驗證（植入實驗＋對照組） | (a) 漏洞類型表 7 類；(c) 4.8 E3；(d) A4、`period`、`one_window`、`nan_drop`、P81、`results_after_tz`、`no_tz`、`verification_*`、P79 `bit0`、C80d | 無 | 不用動〔ADR-0020 E3〕 | `checker_holes.md`；ADR-0019 決定 26（:214–223） |
| P7-38 | 5、6、7 | **文件與決定不同步**：後面的決定改了，前面的文字沒標（決定 19 的 50 mV、流程文件寫「上限是板子的供電要求」、決定 12 的密度 55%）；不同條件的數字放在一起比（「8.4 → 45 mV」）；ADR 的選項與實作的偏離沒說明（A44）。Phase 5 文件核對 17 項、Phase 6 44 列中 11 錯 8 誤導、Phase 7 110 列中 5 錯 23 誤導 | 文件與實作不一致 | 每個 Phase 收尾一輪修正（估計 1–2 小時／次） | 已驗證（三次文件核對） | (a) `phase-exit-review` 規則 3（數字對得回證據、metric 的意思）、規則 5（請 agent 核對） | 只有「收尾時抓」，沒有「改決定的當下同步標註前文」的規則；「比較的兩個數字要同條件」也沒寫 | 見第 3 節第 4 項 | `runs/p7_review/doc_check.md`:7–33；`phase6.md`:225–233；`phase-exit-review` 經驗紀錄 2026-10-08 |
| P7-39 | 6、7 | **證據沒有留存**：VM OOM 的 `dmesg` 原文只在終端機看過；ADR 決定 18–21 的開發量測與 chip-floorplan 的 9.77／20.65／39.2 mV 只在已消失的 scratchpad；licon.14 容許面積比例的計算沒存檔；knowledge 檔引用的 `runs/user_project_wrapper_signoff/` 被下一次 harden 覆蓋；Phase 6 加下限後重判的 run 目錄被覆蓋 | 人為操作（證據管理） | 審查 4 列「無法核對」（P7）、Phase 6 審查也無法核對比例 | 已驗證 | (a) `librelane-run-debug` 規則 6 只管「重跑覆蓋 run 目錄」；`phase-exit-review` 規則 3 要求數字對得回證據，但沒說證據要放在不會被覆蓋的地方 | 沒有「寫進 ADR／knowledge 的數字，證據要先另存到不會被覆蓋的路徑」的規則 | 見第 3 節第 5 項 | `doc_check.md`:30、:46–53；ADR-0018:97；`signoff-checker-qualification` 經驗紀錄（SKILL.md:169） |
| P7-40 | 7 | `ir_caravel.py`／`ir_pattern.py` 自己不呼叫 run guard、不要求三個 window 都在（審查 H3）；`flow-regression-reproducibility`「用完後」第 2 條（新的下游步驟要加進 `run_guard.py` 與 `neg_run_guard.py` 的 `STEPS`）沒被做到 | checker 漏洞；規則沒被遵守 | 修正併入 P7-37 | 已驗證 | (a) `flow-regression-reproducibility`「用完後」第 2 條；(d) `neg-run-guard` 加 IR 兩支（65 個） | 規則靠人記得；沒有東西檢查「讀 harden run 的腳本都有 guard」 | 見第 3 節第 13 項 | `checker_holes.md`:17、:72–80 |
| P7-41 | 5、6、7 | **regression 對本機資源不足沒有防護**：①Phase 6 兩個 CPU 的 `neg-pnr` 各 `-j 4` 同時跑（8 個 LibreLane），被系統以記憶體不足中止；②Phase 7 第二輪三條 regress 平行時磁碟只剩 0.8 GiB：PicoRV32 在 `neg-eqy-core` 報 `OSError: [Errno 28] No space left on device` FAIL，Hazard3 的 `neg-pnr` P32 的 `sta` CPU 0%、87 分鐘沒有進度、沒報錯也沒逾時；之前 Phase 留下 11 個 worktree 約 650 GB 中間產物（每條 regress 40–70 GB） | 資源不足；regression 不可重現 | Phase 6：一次中止＋改成依序跑；Phase 7：Hazard3 卡 87 分鐘、兩條整條重跑（PicoRV32 248 分鐘、Hazard3 第二次），結案從預計約 08:00 延到 11:21（估計約 3–4 小時） | 已驗證（磁碟剩餘量、中間產物大小）；STA 卡住的機制沒查 | (b) `flow-regression-reproducibility` 經驗紀錄 2026-10-10、2026-10-15（SKILL.md:94、98）；exit review 已知限制 20；機器層的全域 hook 限「同時 2 個 LibreLane、可用記憶體 4 GB」（流程文件 1.4，只在這台機器） | 同類第三次（另有 Phase 5 10-07 的 OOM），已驗證，卻沒有規則、流程文件沒提、description 沒有 `No space left on device`；`env-check-flow` 不查磁碟；`scripts/regress.py` 各項沒有逾時（`grep timeout` 無結果） | 見第 3 節第 1 項 | `phase7.md`:33、:234；`flow-regression-reproducibility` SKILL.md:94、98 |
| P7-42 | 7 | swap 7.6／9.2 GB 時本機 KLayout 0.30.7 跑 precheck deck 當掉（`ERROR: Signal number: 11`），`neg-precheck` 的 FAIL 訊息是「the reference's klayout_feol report has no item」，看不出是工具當掉 | 工具缺陷；checker 訊息誤導 | Hazard3 第二次執行作廢，等到第三次（估計約 2.5 小時等待） | 推測（記憶體壓力；只出現一次，沒重現） | (b) `tapeout-precheck-caravel` 經驗紀錄 2026-10-15（SKILL.md:114）；exit review 已知限制 20 | 根因推測，不能進規則；但「checker 把工具當掉講成報表沒有項目」是可以直接修的診斷問題 | 見第 3 節第 8 項 | `phase7.md`:34；`runs/p7close2_h3_neg_precheck_ref_klayout_sig11.log` |
| P7-43 | 7 | `picorv32_core` 從 Phase 5 起一直逐值相同，第一輪結案 regress 卻有 29 個 metric 落在誤差內，第二輪又逐值相同 | regression 不可重現 | 無（誤差吸收） | 推測（負載重時多執行緒 detailed routing 順序不同） | (b) `flow-regression-reproducibility` 經驗紀錄 2026-10-14；(a) `signoff-checker-qualification` 規則 5、11 | 無 | 不用動 | `phase7.md`:162、:166 |
| P7-44 | 7 | `sky130_ef_sc_hd__decap_12` 沒有 .lib，漏電不進功耗報告 | 工具／PDK 限制 | 0.011 mW 的漏電沒算 | 已驗證 | (a) `tapeout-precheck-caravel` 規則 8；knowledge S29；登記表 D15 | 無 | 不用動 | ADR-0019:184 |
| P7-45 | 7 | Caravel 的 PLL jitter 與 duty cycle 沒有官方數字，維持假設、寫成使用限制（管理端時脈 ≤ 22.7 MHz） | 平台規定（資料不足） | 無 | 已驗證（查不到數字） | (a) `tapeout-precheck-caravel` 規則 6；登記表 T07 | 無 | 不用動 | ADR-0019 決定 15（:64–66） |
| P7-46 | 7 | wrapper 的 hold skew metric −3.598 ns：彙總的 `clock__skew__worst_hold` 是各 corner 最不負的值；約 2.7 ns 是報表算法的扣分 | 工具行為（metric 意思） | 分析約半天（估計） | 彙總值已驗證（LibreLane 原始碼）；2.7 ns 推測 | (a) `cts-clock-tree` 規則 6、`phase-exit-review` 規則 3；(b) 推測部分在 `cts-clock-tree` 經驗紀錄 | 無 | 不用動 | `phase7.md`:117、:335 |
| P7-47 | 7 | `wb_clk_i` 從 wrapper 邊緣到 clock root 約 1.9 ns（6 顆 buffer），Caravel 輸入路徑多了至少 312 顆 hold buffer、半週期 setup 少約 0.11 ns | 工具行為（clock pin 位置固定） | 無（仍 PASS） | 已驗證（唯讀分析） | (a) `cts-clock-tree` 規則 11、13 | 無（下一顆設計讓 CTS root 靠近 clock 腳位，沒試） | 不用動 | `phase7.md`:84、:221 |
| P7-48 | 7 | precheck 有幾項只看過 PASS，沒有植入錯誤確認會 FAIL（`oeb` 接錯、`xor`、`gpio_defines`） | checker 覆蓋缺口 | 無 | 已驗證 | (a) `tapeout-precheck-caravel`「待確認」；登記表 D13 | 已登記；官方工具的項目，本 repo 只能補植入案例 | 不用動 | `phase7.md`:226 |
| P7-49 | 7 | 扁平放法（standard cell 直接在 wrapper 層）沒有官方範例；官方範例關掉 fill，所以 li1 問題（P7-32）沒有前例 | 平台規定（沒有前例） | 無 | 已驗證 | (a) `tapeout-precheck-caravel` 規則 8（「官方範例的 wrapper 只放 macro」） | 無 | 不用動 | ADR-0019 決定 2（:15）；筆記:138 |
| P7-50 | 7 | 給使用者的選項說明寫錯：「amend 只增加真實邏輯，證明比原本更嚴」，實際輸入是 flip-flop 時會空洞證明，是實作後的 negative test 才發現 | 人為操作（選項查證不足） | 小（實作階段發現） | 已驗證 | (b) `formal-equivalence-eqy` 經驗紀錄 2026-10-13（SKILL.md:94）；CLAUDE.md 規則 13 已要求先查證 | 無 | 不用動 | ADR-0019:160 |

---

## 3. 建議寫回（依重要性排序）

每項寫：目標檔、寫什麼、為什麼可以帶到下一個專案、是否符合 CLAUDE.md 規則 3／4／10。

### 1. regression 開跑前的資源檢查與「卡住」偵測（P7-41，相關 P6-15、P7-33、P7-42）

- **寫到哪裡、寫什麼**：
  - `flow-regression-reproducibility` 新增規則：「平行跑多條 regression（或多個 `-j` 的 negative test）前，先估資源：同時執行的 LibreLane／EQY／ngspice 個數 × 每個的記憶體，要小於實體記憶體；每條 regression 的磁碟峰值 × 條數，要小於剩餘空間（先量一次峰值，記在 repo 文件）。清掉舊 worktree 的 negative test 中間產物。跑的時候看各項耗時與 log 的修改時間；寫檔失敗後，工具可能停住而不報錯。」四項防護照 CLAUDE.md 規則 10 寫：
    - 症狀：`OSError: [Errno 28] No space left on device`、`echo: write error: No space left on device`；STA 程序 CPU 0%、`sta.log` 不再更新；系統以記憶體不足中止背景工作。
    - 怎麼發現：`df`、各項的耗時與 log 修改時間。
    - 怎麼繞過：依序跑或降低 `-j`；清中間產物。
    - 防復發：見下面兩個 checker。
  - 同一個 skill 的 `description` 加這兩個錯誤訊息與「regression 卡住」。
  - 流程文件 4.8：加一行「平行跑前的資源檢查」，指到該規則。
  - 新增 checker（建議，加 negative test）：
    - `env-check-flow` 檢查剩餘磁碟 ≥ 設定值（例如每條 regression 的峰值 × 條數）。
    - `scripts/regress.py` 每一項加逾時，或「log 多久沒更新就判 FAIL」；植入一個永遠不結束的假 target，確認會 FAIL。
- **為什麼通用**：任何在單機跑長 regression 的專案都會遇到；這次的代價是結案延後約 3–4 小時（估計）。設計專屬的數字（每條 40–70 GB、24 GB 機器）依規則 4 放 repo 文件，skill 只寫「先量、再乘條數」。
- **符合規則 3**：記憶體不足（Phase 5 10-07、Phase 6 10-10）與磁碟滿（Phase 7 10-15）都已驗證，同類出現三次。STA 為什麼停住沒查，規則只寫症狀，不寫它的原因。

### 2. 「之後再處理」的決定，當下寫進待辦，收尾時逐條結清（P6-08）

- **寫到哪裡、寫什麼**：
  - `phase-exit-review` 新增規則：「每個『之後再做』『選定後再修』『Phase N 會加』的決定，在決定的同一個 commit 寫進 `runs/todo.md`。exit review 列出還沒結的項目：每一項要嘛做完附證據，要嘛寫進已知限制或放寬與補償登記表。skill 或文件裡寫『之後會加的防護』，結案時 grep 出來逐條確認。」
  - 流程文件 4.9 加一行，並在第 2 節規則 11 的摘要旁註明。
  - CLAUDE.md 規則 11 是否加一句，由使用者決定（CLAUDE.md 是使用者的規則，本審查只建議）。
  - 本 repo 現在就該結清的一項：`make openram-macro` 改過後從頭完整跑一次（ADR-0018 第 99 行；或寫進登記表）。
- **為什麼通用**：這是流程的漏接，和工具無關；三次的代價都是多跑一輪或多一個防護缺口。回顧報告的 E14 提過，但不在 ADR-0020 的 19 條裡。
- **符合規則 3**：出現三次，都已驗證（原文寫明漏了）。

### 3. 變數重名：補第三個例子，範圍擴大到模組層，加自動防護（P7-25、P6-35）

- **寫到哪裡、寫什麼**：
  - `signoff-checker-qualification` 規則 13：
    - 補 Phase 7 `cbf2c5e` 這一例：模組層的 `for x, y, ... in pts` 蓋掉前面從 DEF 讀到的 `x, y`。
    - 範圍從「同一個函式」改成「同一個作用域，含模組層的迴圈變數」。
  - 自動防護（建議）：`make py-check` 加一項，抓「同一作用域裡已賦值、之後還會被讀的名稱，又被迴圈或賦值改掉」；或在 `py-check` 裡跑現成的 lint（例如 pylint 的 `redefined-outer-name`、`redefined-variable-type`，先試誤報率）。negative test：把 `cbf2c5e` 之前的寫法放進植入案例，要 FAIL。
- **為什麼通用**：長的判定腳本裡，後面的列用前面算好的變數很常見；三次都是 checker 被改壞，其中一次讓兩輪 regress 白跑。
- **符合規則 3**：同類三次，都已驗證。

### 4. 決定改了，同一個 commit 標註被取代的前文；比較數字時條件要相同（P7-38）

- **寫到哪裡、寫什麼**：
  - `phase-exit-review` 新增規則（或放在規則 3 之下）：
    - 新決定取代舊決定時，在同一個 commit 做兩件事：在舊決定的段落加「已被決定 N 取代」；grep 舊數字與舊說法出現的其他文件（skill、流程文件、golden README、knowledge 檔），一起改。
    - 兩個數字放在一起比較時，寫明兩邊的條件（corner、電流來源、供電模型、版圖版本），條件不同就不比。
    - ADR 的實作和選項內容不同時，在實作段說明偏離。
  - 流程文件 4.9 加一行。
- **為什麼通用**：每個 Phase 收尾的文件核對都在修同一類錯（Phase 5 17 項、Phase 6 19 列、Phase 7 28 列），都是決定改了、前面沒同步。在決定的當下改，成本最低。
- **符合規則 3**：同類三次，都已驗證（三份核對報告）。

### 5. 寫進 ADR／knowledge／exit review 的數字，證據先另存到不會被覆蓋的路徑（P7-39、P6-26、P7-33）

- **寫到哪裡、寫什麼**：
  - `phase-exit-review` 規則 3 加一點：
    - 引用的證據不能放在下一次 harden 會覆蓋的目錄（`runs/<tag>_signoff/`、`runs/<design>/`）或 scratchpad。先複製到另存目錄（本 repo 的做法是 `runs/p7_formal_signoff/` 這種），引用另存的路徑。
    - 工具當掉、OOM 這類只在終端機看到的訊息（例如 VM 的 `dmesg`）要存成檔。
    - 計算出來的比例或門檻，連同算式與輸入一起存。
  - `signoff-criteria`「每次 harden 後的檢查」：knowledge 檔的證據路徑同樣要求另存。
  - 可選：`signoff/precheck/run_precheck.sh` 跑完後自動把 VM 的 `dmesg` 存進結果目錄。
- **為什麼通用**：審查與之後的專案只能核對有留下來的證據。Phase 6、7 的審查各有幾列因此判「無法核對」。
- **符合規則 3**：同類多次（Phase 6 licon.14 比例與 run 目錄被覆蓋、Phase 7 `dmesg`、scratchpad、knowledge 路徑），都已驗證。`librelane-run-debug` 規則 6 只涵蓋 run 目錄，這條補的是文件引用的那一端。

### 6. GDS 的 sha256 會因日期不同：可重現性比對與綁定 GDS 的 checker 怎麼做（P6-06）

- **寫到哪裡、寫什麼**：
  - `flow-regression-reproducibility` 新增規則（從經驗紀錄 2026-10-11 搬上來）：
    - 比較兩次 harden 的版圖是否相同：網表、DEF 比 sha256；GDS 用 XOR，或把 BGNLIB／BGNSTR 清零後再比，不要因為 GDS 的 sha256 不同就判不可重現。
    - 反過來，checker 把結果綁到某個 GDS 時（precheck 的 `input_file_hash`、`gds.info`），要綁這一次的 sha1。同一個版圖重新 harden 後 sha1 也會變，不能拿上一次 harden 的結果代替。
  - 寫明自動防護的現況：regress 比 metrics；`check_macro_gds.py` 逐圖形比對，不受日期影響（`phase6.md`:310 已寫）。
- **為什麼通用**：任何用 GDS 雜湊做來源追溯或可重現性比對的流程都會遇到。
- **符合規則 3**：出現三次（OpenRAM 重產、乾淨 worktree 重跑、precheck），都已驗證。

### 7. Caravel 的 fill 與金屬密度下限寫進「待確認」，補上規則 9 的懸空引用（P7-35）

- **寫到哪裡、寫什麼**：
  - `tapeout-precheck-caravel`「待確認」加一條：
    - metal fill 由整合方在 tapeout 時對整顆 Caravel 補（`generate_fill.py`，`wafflefill(tiled)`）。Efabless 時代證據強；ChipFoundry 沿用同一套腳本，沒有文件明講，證據中等。
    - 補完之後另有下限檢查（`check_density.py`：700 µm 視窗，li1、met1–4 ≥ 35%、met5 ≥ 45%、FOM ≥ 33%），precheck 不跑這一項。
    - 自己預估的方法：照 `generate_fill.py` 單獨補 wrapper，再照 `check_density.py` 量；fill 很大時每個區塊分開量再相加，省記憶體。
    - 本 repo 的試跑數字留在 `runs/p7_review/fill_trial/README.md` 與 Phase 7 已知限制 3（規則 4）。
  - `description` 加 `check_density.py`、`generate_fill`、「金屬密度下限」。
  - `drc-signoff` 第 54–56 行的「chip-level 一定要補 fill」加一句：放進共乘外殼（Caravel）時，fill 可能由平台補，先查平台規定（指到 `tapeout-precheck-caravel`）。
- **為什麼通用**：任何用共乘平台的設計都要先知道 fill 誰做、補完有沒有下限檢查。下限沒過要回頭改設計（Efabless 時代有全數位設計卡在這一步）。
- **符合規則 3**：只出現一次，而且 ChipFoundry 的部分是推論，所以放「待確認」（讀過原始碼、還沒經平台確認），不放規則本文。和 ADR-0020 A2、D5 重疊，但這兩條只寫了「要查」，沒有寫查到的結果。

### 8. checker 要分得出「工具當掉」與「結果不對」（P7-42）

- **寫到哪裡、寫什麼**：
  - `signoff/precheck/` 跑 deck 的腳本與 `check_precheck.py` 的比對基準列：報表沒有項目時，先掃同一步的 log 有沒有 `Signal number`、`Segmentation fault`、`Killed`，有就印「工具當掉（見 <log>）」並 FAIL。negative test：植入一份含 `Signal number: 11` 的 log、報表為空，FAIL 訊息要指出當掉。
  - `signoff-checker-qualification` 漏洞類型表加一列：「FAIL 的訊息分不出工具當掉與結果不對」。
  - KLayout 當掉本身維持在 `tapeout-precheck-caravel` 經驗紀錄（根因是推測，只出現一次）。
- **為什麼通用**：所有包外部工具的 checker 都會遇到。訊息誤導時，人會先去查設計，浪費時間。
- **符合規則 3**：不寫 KLayout 當掉的原因，只改 checker 的診斷訊息，所以不受「推測不能進規則」限制。

### 9. 低於 slew 上限的輸入腳位，也要確認 SDC 的 transition 有生效（P7-10）

- **寫到哪裡、寫什麼**：
  - 在 harden 的 signoff 加一個 checker：對每個有 `set_input_transition` 的輸入腳位，在每個 STA corner 讀出腳位實際的 slew（OpenSTA 對 port 查 slew），要等於 SDC 的值（±0.05 ns）。negative test：保留 driving cell，讓 transition 被蓋掉，要 FAIL。
  - `timing-constraints-sdc` 規則 14 的「防復發」改成這個 checker 的名稱；現在寫的是「低於上限的沒有自動防護」。
- **為什麼通用**：任何沿用 `base.sdc`（對所有輸入設 driving cell）再加外殼 transition 的設計都會被同一個 OpenSTA 行為影響，而且沒有警告。
- **符合規則 10**：OpenSTA 的行為已用對照實驗驗證；這是補上規則 10 要求的防復發。

### 10. 不在 regression 裡的 negative test，結果要對得回 checker 的版本（P6-38）

- **寫到哪裡、寫什麼**：
  - `neg-char`（以及其他不在 regress 裡的 negative test）跑完時，記下被測程式（`sramchar.py`、`gen_char_lib.py`、`check_char_lib.py`、`power.py`、`extract_sram.py`）的 sha256。
  - `harden-soc` 開頭的 `check_inputs.py` 比對：現在的程式和上次 `neg-char` PASS 時不同，就 FAIL 並提示要重跑。negative test：改一行 `check_char_lib.py`，要 FAIL。
  - 流程文件 4.8「不在 regression 裡、要另外跑的」加一句：由這個檢查提醒，不靠人記得。
- **為什麼通用**：跑得慢的 negative test 常被排除在 regression 外，checker 一改，它的結果就默默過期。
- **符合規則 3**：Phase 6 已驗證一次（`ad184f5` 之後沒有重跑）。這是加 checker，不是加 skill 規則。

### 11. 流程文件 4.3 第 5 項補上「新量測方法先在修剪網表跑完所有 corner」（P6-13）

- **寫到哪裡、寫什麼**：流程文件 4.3 第 5 項加一句：新的量測方法（功耗、漏電、新的序列）先在修剪網表把每個 PVT 跑一次，最冷的先跑，所有 checker PASS 之後才上完整網表；完整網表只用來驗證一次（`openram-macro-characterization` 規則 27）。
- **為什麼通用**：下一個專案從流程文件進來，看不到 skill 的規則 27 就會重演約 2 天的來回。
- **符合規則 3**：規則 27 已在 skill 本文（使用者 2026-10-10 要求），這裡只是讓流程文件指到它。

### 12. 換 macro 檢查單加上「negative test 寫死的舊 macro 座標與尺寸」（P6-32）

- **寫到哪裡、寫什麼**：
  - `hard-macro-integration` 規則 10「做什麼」：搜尋用舊名稱或前綴認東西的腳本之外，也搜尋 negative test 與 checker 裡寫死的 macro 外框、座標、尺寸，改成從 config 與 LEF 讀。
  - 補一列經驗紀錄（Phase 6 P05：只拿掉 4 個多餘的 via，LVS 不會 FAIL）。
  - 流程文件 4.3 第 6 項同步一句。
- **為什麼通用**：換 macro 時，植入案例會悄悄失效（植入點不在新 macro 上）。如果 negative test 本身沒有斷言「植入點確實在 macro 上」，就抓不到。
- **符合規則 3**：同一類（checker 綁舊 macro 的特徵）已有 EQY 只認 `sky130_` 開頭這一例，加上這次共兩次，都已驗證。

### 13. 「讀 harden run 的腳本都要過 run guard」做成自動檢查（P7-40）

- **寫到哪裡、寫什麼**：在 `neg-run-guard`（或 `py-check`）加一項自我檢查：Makefile 裡每個吃 harden run 的 target（參數含 `runs/<design>` 或 `RUN=`）都要在 `neg_run_guard.py` 的 `STEPS` 裡，少了就 FAIL。
- **為什麼通用**：`flow-regression-reproducibility`「用完後」第 2 條已經是規則，但 Phase 7 新增 IR 判定時沒做到，是獨立審查才抓到。靠人記得的規則，換一個人或下一個專案就會漏。
- **符合規則 3**：只改 checker。

### 14. Caravel 範本固定會出現的警告寫成規則（P7-07）

- **寫到哪裡、寫什麼**：`tapeout-precheck-caravel` 規則 5 或「待確認」加一條：`PDN-0239 Ring shape falls outside the die bounds`、`GRT-0036 Pin ... is outside die area` 是範本本來就畫到 die 外造成的（座標與官方範例相同，官方 precheck `xor` PASS），不要為了消除警告改腳位或 ring（會被 `xor` 抓）。`description` 加這兩個代號。
- **為什麼通用**：任何 Caravel 設計的每次 harden 都會出現上千行這種警告，第一次看到的人會花時間追。
- **符合規則 3**：根因已用官方 DEF 對照驗證。

### 15. CVC 的 HI-Z 警告只允許 black box macro 的輸出（P7-34）

- **寫到哪裡、寫什麼**：`make precheck-check` 加一列：讀 `logs/cvc.log` 的 HI-Z 清單，每一個 net 都要是 `EXTRACT_ABSTRACT` 的 macro 輸出腳位，或只由這些輸出驅動的 cell 輸入；其他就 FAIL。negative test：在報告裡多放一個非 SRAM 的 net，要 FAIL。`tapeout-precheck-caravel` 規則 4 的防復發改成這一列。
- **為什麼通用**：LVS 把 macro 當 black box 是常見做法，這類警告每次都有，真正浮接的輸入會被淹沒在裡面。
- **符合規則 3**：只改 checker；74 個的組成已驗證。優先度低：precheck 的 LVS 本身已判 PASS。

### 16.（可選）長段工作開始前先一次取得事先授權（P6-45）

- **寫到哪裡、寫什麼**：流程文件第 2 節規則 13 的摘要旁加一句做法：進入多步驟、會跑很久的階段之前，先列出「可以直接照 skill 做的」與「一定要先問的」（例如改週期、放寬 signoff 條件、讓 checker 變寬），請使用者一次決定，寫進 ADR（本 repo 範例：ADR-0018 決定 16）。
- **為什麼通用**：等待使用者回覆是長流程的主要停頓之一。使用者的 auto-memory 有「決策一次問完」，但它不在 repo 裡，其他專案帶不過去。
- **符合規則 3**：只出現一次，是作法建議，不是規則；所以列為可選，要不要寫由使用者決定。

---

## 4. 和 ADR-0020 19 條提早檢查重疊的問題

這些問題「太晚才看」的部分已由 ADR-0020 寫進流程文件與 skill。本審查核對過它們的症狀與防護都寫在規則或經驗紀錄裡；除了 P7-35（第 3 節第 7 項）以外，沒有另外的寫回建議。

| ADR-0020 | 重疊的問題 |
|---|---|
| A1 操作範圍對照表 | P6-09 |
| A2 平台試算表 | P7-03、P7-12、P7-18、P7-31、P7-35、P7-36 |
| B1 選定 macro 前的 go／no-go | P6-09、P6-11、P6-24、P7-03 |
| B2 特性化前先萃取 | P6-36 |
| B4 換 macro 檢查單 | P6-22、P6-23、P6-24、P6-29（另見第 3 節第 12 項：P6-32 是 B4 沒寫到的一種） |
| C1 harden 前定好 signoff 條件（含 IR 判法） | P6-42、P7-19 |
| C3 resizer 的 corner | P7-13 |
| C4 外殼邊界約束先試算 | P7-12、P7-13 |
| D1 floorplan 試跑 | P7-23（試跑看不到，已寫成 D1 的限制） |
| D2 IR 在 floorplan 試跑就成立 | P7-18、P7-19 |
| D5 外殼第一次探索 harden 就跑平台檢查 | P7-32、P7-33、P7-35 |
| E1 放寬與補償登記表 | P6-36、P6-42 |
| E2 golden 誤差至少 4 個樣本 | P7-29 |
| E3 新 checker 寫完就審查 | P6-34、P7-30、P7-37 |

合計 23 個問題（Phase 6：9 個，Phase 7：14 個；有些對到兩條以上）。A3、B3、C2、D3、D4 這五條的來源是 Phase 0–5，Phase 6、7 沒有對應的新問題。

**回顧報告提過、但沒進 19 條的建議**（`retro_p6_7.md` 第 3 節）：E7（新量法先在修剪網表跑完）→ 本檔第 3 節第 11 項；E14（延後的決定進待辦）→ 本檔第 3 節第 2 項。

---

## 5. 查證方式與限制

- 只讀檔案、grep 與 `git log`／`git show`，沒有跑 EDA 工具或 make。「目前捕捉在哪」每一格都用 `git grep` 核對過 skill 與流程文件的原文（例如：`No space left`、`磁碟` 只出現在經驗紀錄與 exit review；`cbf2c5e`、`ir_sources` 不在 `signoff-checker-qualification`；`待辦` 不在流程文件第 4 節；`scripts/regress.py` 沒有 `timeout`；`tapeout-precheck-caravel`「待確認」沒有 fill 這一條）。
- 時間都從 commit 時間與 ADR 記的 run 時間估，commit 間隔包含等待與其他工作，只能當上限。
- 「`make openram-macro` 改過後一直沒有從頭完整跑過」（P6-08②）的依據是：在 `docs/`、`.claude/`、登記表都找不到後續執行紀錄。`runs/` 裡的 log 沒有逐一翻查，所以這一點是推測。
- `runs/` 不進版控，引用的 `runs/...` 檔案在本機存在（2026-10-15）。
- 每個問題只列一次：同一現象在兩個 Phase 都出現的，寫在一列，Phase 欄寫兩個（例如 P6-06、P6-35、P7-38、P7-39、P7-41）。
