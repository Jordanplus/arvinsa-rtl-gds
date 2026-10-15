# 23 個 skill 與流程文件的一致性審查（2026-10-15）

起因：使用者 2026-10-15：「主要目的是把完整走過一次，先review一下所有遇到的問題與檢討哪些是要寫進skill與流程裡的」。另外三份報告依 Phase 分段審查（同目錄的 `review_p*.md`）；這一份是**橫向稽核**：23 個 `.claude/skills/*/SKILL.md`（經驗紀錄共 260 列）與 `arvinsa-rtl-gds-flow.md`（下稱「流程文件」）的一致性。

**做法**：
- 主審查者讀了 `CLAUDE.md`、整份流程文件、README「Claude Code skills」一節，核對 `scripts/regress.py`、`Makefile`、`.claude/guard.json`、`.claude/settings.json`，跑了 `make skill-check`（PASS 23 skills）。
- 23 個 skill 分 5 組，交給 5 個沒參與實作的 agent 逐份完整讀（含經驗紀錄），用 grep 核對引用的檔案、target、negative test 案例是否存在。
- 主審查者再做跨 skill 比對、流程文件對照，並抽查各組的關鍵論斷：timing-constraints-sdc 規則 5、`check_soc.py` 第 53–58 行、`neg_regress.py` 的情境數、`neg_macro_views.py` 的案例 ID、signoff-criteria 第 138 與 215 行、drv-timing-closure 規則 9 與 12、`pin_plan.toml` 的節、`neg_precheck.py` 的 `stale_results`、floorplan-congestion 規則 2–3。抽查的都屬實。
- 只讀，沒有改 repo 檔案（本報告除外），沒有跑 EDA 工具。

**行號**：以本 commit（`0d47a3d`）的 `.claude/skills/<name>/SKILL.md` 為準，簡寫成 `<skill>:行號`。

---

## 0. 結論

1. **5 個 skill 的 description 在 skill 清單裡完全看不到，另有 2 個被截斷。** 這是最嚴重的問題。
   - 完全看不到的：`pdn-ir-drop`、`signoff-checker-qualification`、`signoff-criteria`、`tapeout-precheck-caravel`、`timing-constraints-sdc`。
   - 被截斷的：`hard-macro-integration`、`openram-macro-characterization`，大約在第 1,000 字處被截掉，後段的錯誤訊息都看不到。
   - 依據：這次審查的 6 個 agent（主審查者與 5 個分段 agent）各自收到的 skill 清單，都是這個狀態。
   - 23 份 description 合計 21,466 字。最長的 openram 有 2,742 字，tapeout-precheck-caravel 有 2,101 字。
   - 推測：清單有總長度上限，太長的 description 把後面的擠掉了。確切的上限沒查。
   - 後果：Claude 只靠 description 決定要不要讀 skill（README 第 154 行），所以上面 5 個 skill 等於選不到，`CLAUDE.md` 規則 5 的前提失效。
   - `make skill-check` 只檢查格式與索引，不檢查長度。
2. **經驗紀錄有 44 列（17%）在規則本文沒有對應**，其中 13 列在 `flow-regression-reproducibility`（共 21 列）。
   - 這 13 列幾乎都是 regression 的資源問題：同時跑幾條、記憶體、磁碟、worktree、卡住，大部分已驗證。
   - 2026-10-15 的「磁碟滿了，regress 不報錯而是卡住」就是這類問題。
3. **有 9 條規則和後來的決定矛盾或已過時**，例如：
   - `drv-timing-closure` 規則 9（用餘量補 resizer 看不到的 corner）
   - `multicorner-sta` 規則 3 第 3 點
   - `timing-constraints-sdc` 規則 5（`sram0/clk1` 例外）
   - `pdn-ir-drop` 規則 4、10、12 與「待補」節
   - `signoff-criteria` 第 138、215 行
   - `floorplan-congestion` 規則 2、3：沒指向 `CLAUDE.md` 規則 14 的 pad／block／pin 核准流程，和規則 14 有實質衝突。
4. **工具缺陷的四項防護**（`CLAUDE.md` 規則 10）：檢查約 162 個缺陷或意外行為，四項齊全的約 61 個（約 38%）。
   - 最常缺的是「防復發」：沒寫「沒有自動防護」，或 repo 其實有 checker 卻沒寫出名稱。
   - 第二常缺的是確切訊息沒寫進 description。
   - 綁在 step 名稱或 log 措辭的防護有 8 處，散在 4 支程式裡，沒有一份「升版時要重看」的清單。
5. **流程文件與 skill**：
   - 規則號引用 35 處全部對得上。
   - 但有 6 處過時，另有 12 項 skill 裡的重要步驟，流程文件沒提（新專案最容易漏的，例如 LibreLane 預設 setup 只判 tt corner）。
6. **完全沒有 skill 涵蓋的重大任務**：機器資源與長時間工作的管理，包括同時跑幾條、記憶體、磁碟、worktree 清理、卡住偵測。
   - 目前有 13 個舊 worktree，光 `runs/` 就有約 386 GB；主目錄的 `runs/` 另有 176 GB。
   - 建議併進 `flow-regression-reproducibility`，不另建新的 skill。

---

## 1. 經驗紀錄該升為規則的（`CLAUDE.md` 規則 3）

### 1.1 各 skill 的經驗紀錄統計

「沒對應」是指規則本文、已知陷阱、negative test 節都找不到對應的規則。

| skill | 列數 | 根因推測／未標 | 沒對應 |
|---|---|---|---|
| openram-macro-characterization | 38 | 2 | 4 |
| drv-timing-closure | 25 | 1（多列是「已驗證＋推測」） | 2 |
| signoff-checker-qualification | 28 | 1 | 0 |
| flow-regression-reproducibility | 21 | 2 | **13** |
| librelane-run-debug | 17 | 1 | 4 |
| formal-equivalence-eqy | 17 | 0 | 2 |
| tapeout-precheck-caravel | 14 | 2 | **6** |
| drc-signoff | 12 | 0（2 列部分推測） | 0 |
| cts-clock-tree | 10 | 3 | 2 |
| phase-exit-review | 9 | 0 | 1 |
| core-migration-hazard3 | 8 | 0 | 2 |
| timing-constraints-sdc | 8 | 0 | 1 |
| signoff-criteria | 8 | 0 | 0 |
| hard-macro-integration | 7 | 1 | 2 |
| gate-level-simulation | 7 | 0 | 0 |
| pdn-ir-drop | 6 | 1 | 1 |
| floorplan-congestion | 5 | 1 | 1 |
| multicorner-sta | 5 | 0 | 2 |
| chip-floorplan-pin-planning | 5 | 0 | 0 |
| antenna-signoff | 4 | 0 | 1 |
| dv-directed-tests | 3 | 0 | 0 |
| lvs-signoff | 2 | 0 | 0 |
| rtl-synthesis-lint | 1 | 0 | 0 |
| **合計** | **260** | 約 15 | **44** |

另外，`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` 有 33 列實測校準資料。它不是經驗紀錄，沒有計入上表。

### 1.2 跨 skill 出現兩次以上、或已驗證，但規則本文沒有的

| # | 現象 | 出處（skill:行，日期） | 為什麼算確認 | 建議的規則（一句話） |
|---|---|---|---|---|
| R1 | **同時跑太多重工作，記憶體耗盡**，工作被系統中止 | flow-regression:89（10-07）、:94（10-10）；tapeout-precheck-caravel:112（10-14，VM OOM）；openram:249（10-09，ngspice 記憶體壓縮）；drv:126（10-05，92.9 GB） | :94 有前後比較：兩個 CPU 各 `-j 4` 時被中止，改成一次一個 CPU、`-j 2` 就跑完；ADR-0018 決定 17 使用者選「依序跑兩輪」。Phase 7 又三條平行跑（:97、:98），等於教訓沒留在規則裡 | 開長 regression 前，先算同時執行的 LibreLane run 總數（各條 harden，加上 `neg-pnr` 的 `-j`）與 EQY 數，依機器記憶體訂上限，上限數字記在 ADR；先看有沒有別的大程式在跑；被系統中止的工作不自動重開 |
| R2 | **磁碟滿了，工具不報錯而是卡住**，EQY 寫檔失敗被誤判成「沒抓到植入錯誤」 | flow-regression:98（10-15） | 已驗證：每個 regress worktree 的中間產物 40–70 GB；舊 worktree 合計約 650 GB（當時），本審查量到 13 個 worktree 的 `runs/` 約 386 GB | 開跑前檢查剩餘空間 ≥ 條數 × 單條峰值（`env-check-flow` 做成 checker）；`regress.py` 每一項要有逾時，逾時判 FAIL；舊 worktree 的中間產物先清掉 |
| R3 | **長時間工作逾時或卡住沒有變成 FAIL** | openram:248（10-09，`TimeoutExpired` 沒轉成 checker FAIL）；flow-regression:98（regress 某一項卡住 87 分鐘沒有進度） | 兩次都已驗證；`scripts/regress.py` 第 118 行的 `subprocess.run` 沒有 timeout | 每個會跑很久的 checker 或 regress 項目都要有逾時；逾時的例外要轉成 FAIL，並印出 FAIL 那一行（這個通則寫進 `signoff-checker-qualification` 的漏洞類型表） |
| R4 | **GDS 的 sha256 每次不同，不代表 flow 不可重現** | flow-regression:96（10-11）；openram 規則 20 一帶的同類現象（PYTHONHASHSEED，另一個原因） | 已驗證：把 BGNLIB／BGNSTR 的日期清零後 sha256 相同（三個設計） | 比對版圖是否重現時，比網表與 DEF 的 sha256；GDS 用 XOR，或清掉日期記錄再比 |
| R5 | **SDC 印出來不代表生效**（uncertainty 等） | timing-constraints-sdc:59（10-08）；multicorner-sta:62（10-08）；signoff-criteria:265（10-08） | 三處記同一件事；已驗證：刪掉報表裡的 uncertainty 後，舊檢查仍 PASS；防護 `review_criteria.py uncertainty_applied` 與 negative test P56 都存在 | 寫成 timing-constraints-sdc 的獨立規則：「約束有沒有生效，看 STA 報表的路徑分解，不看 SDC 有沒有被讀」，並寫出 P56 |
| R6 | **`RSZ-0064 Unable to repair all hold checks` 只代表 hold 沒修到餘量，不代表有違規** | drv:127（10-06）、:128（10-07）、:136（10-12） | 出現 3 次；:136 讀了 `RepairHold.cc`，最後 +0.298 < 0.3 ns 餘量，TNS 0 | 看到 RSZ-0064，先看修復表最後的 WNS 與 signoff hold；WNS ≥ 0 只表示沒達到餘量。一併寫進 description |
| R7 | **OpenROAD hold 修復的進度表看起來像卡住**；`hold_buffer` 的 metric 只是最後一步的值 | drv:132（10-07）、:136（10-12） | 已驗證（讀原始碼加一次完整 run） | 併入 drv 規則 7：Iteration 數的是 endpoint；Buffers 欄會因 journal 復原而掉回去；RSZ-0032 與 `design__instance__count__hold_buffer` 都不能當總數 |
| R8 | **換 core 後 IR 的依據要重量；改了兩個 CPU 共用的 flow 設定，兩個 CPU 都要重新 harden** | core-migration:111、:112（10-07、10-08）；pdn:82（10-08） | IR 已出現兩次（nom_tt 18.28 mV PASS，最壞組合 25.75 mV）；共用設定有實驗 D 與 ADR-0016 | core-migration 規則 22 補兩點：IR（指向 pdn 規則 12）、共用 flow 設定改了兩個 CPU 都重新 harden |
| R9 | **RSZ-0074 有三種不同原因**，分散在三個 skill | librelane:93（inout 腳位）、:94（同一個 run tag 接續）；drv:140（繞線後 ECO）；tapeout-precheck-caravel:105（`analog_io`） | 三種都已驗證 | 在 librelane-run-debug 已知陷阱放一張對照表：`expected 0`、`3 pins, expected 4`、繞線後 ECO 各對應哪個原因與哪個 skill |
| R10 | **GRT-0229 接續之後，結果不保證和 golden 逐項相同** | librelane:89（10-07／08）、:92（10-08） | 已驗證：3 次接續中 2 次逐項相同，1 次有 14 個連續量落在誤差內 | librelane 規則 5 加一句：接續後的 run 要靠 golden 誤差（ADR-0015）判，不能要求逐項相同 |
| R11 | **長模擬跑到結尾才報 `no such vector`** | openram:229（10-05） | 已驗證：6 個各約 25 分鐘的模擬全部白跑 | 長模擬前，先用同一份 deck 跑 1 ns，確認每個 `wrdata`／`meas` 的節點都存在 |
| R12 | **cell padding 讓局部繞線熱點變多** | floorplan:47（10-13）；drv:143（10-13） | 已驗證：同一份輸入只改一個設定，繞線長度 +26% | floorplan 規則 6 加：「不要用 cell padding 解局部繞路，用 placement 目標密度」 |
| R13 | **diode 數跟著繞線變** | antenna:38（10-07）；flow-regression:88；signoff-checker-qualification:163、:167 | 已驗證（三次 harden） | antenna-signoff 加一句並指到 signoff-checker-qualification 規則 5：diode 數給誤差，違規數必須是 0 |
| R14 | **Caravel 範本的 ring 與腳位本來就在 die 外**：`PDN-0239`、`GRT-0036` 是預期警告 | tapeout-precheck-caravel:104、:107（10-12） | 已驗證：座標和官方 DEF 相同 | tapeout-precheck-caravel 已知陷阱：不要為了消這兩個警告改腳位（XOR 會 FAIL）；兩個代號寫進 description |
| R15 | **外殼頂層有預期的斷線腳位** | tapeout-precheck-caravel:108（10-12）；lvs-signoff:27 | 已驗證，negative test C15 存在 | lvs-signoff 規則 2 補：外殼頂層的斷線表必須剛好是「沒用到的輸入／inout，加上沒有 cell 的電源腳位」（`check_soc.py unused_ports`） |
| R16 | **收尾時程至少兩輪乾淨 regress，再加一輪審查後的修正** | phase-exit-review:36、:39、:40 | 出現三次 | 寫進 phase-exit-review 規則 |
| R17 | **獨立審查和 regress 同時跑，可以省一輪等待** | phase-exit-review:38、:42 | 出現兩次 | 同上 |
| R18 | **上限檔裡寫好的組成（例如沒有寄生的 net 數），換設計後要重數** | signoff-checker-qualification:161 ①；core-migration 規則 22 | 已驗證 | signoff-checker-qualification 規則 4 加一句「換設計或換 core 後用新 run 重數」 |
| R19 | **dev fixture 會被 Stop hook 當成 harden** | flow-regression:95（10-11） | 已驗證：`require_criteria_review.py` 把有 `result.txt` 的 `runs/*_signoff/` 都當成 harden | flow-regression 規則 6 加：fixture 用完就刪，輸出另存在不叫 `*_signoff` 的目錄 |
| R20 | **設計有靠 amend 重試才證明的分區時，植入常數類的錯誤會讓位置檢查判錯** | formal-equivalence-eqy:96（10-14） | 已驗證 | 寫進 negative test 節：這類設計只植入會走重試的錯誤，並說明 wrapper 只留 `nand2_comb_to_nor2` 的原因 |
| R21 | **用腳本改 Verilog 時，跳脫名稱結尾的空白不能去掉** | formal-equivalence-eqy:91；gate-level 規則 4 是同類的網表編輯陷阱 | 已驗證 | 併入 gate-level-simulation 規則 4 |
| R22 | **被 `run.sh` source 的函式裡，`grep` 找不到東西會讓整支腳本中斷** | librelane:91（10-08） | 已驗證，`make test-flow-retry` 抓到 | 寫進 librelane 已知陷阱：可能找不到的 `grep` 要加 `\|\| true`（呼叫端開了 `set -euo pipefail`） |
| R23 | **`report_check_types -min_pulse_width` 每種檢查只列最差的一個 pin** | multicorner:61（10-04） | 已驗證；`check_soc.py pulse_width` 依賴這個行為 | 寫進 signoff-criteria「已驗證的工具行為」 |
| R24 | **macro .lib 裡沒把握的假設（例如輸出 transition）偏樂觀**，出現兩次 | openram:232（Phase 3.5：slack +0.38 → +0.03）；openram 規則 29 的 Phase 7 結果（+0.548 → +0.151） | 兩次都量過 | openram 規則 29 加通則：沒把握的 .lib 假設，先用只重跑 STA 的 what-if 量它對 slack 的影響 |

### 1.3 反向：推測的內容寫在規則本文（違反規則 3）

| skill:行 | 內容 | 建議 |
|---|---|---|
| drv-timing-closure:59（規則 12 最後一點） | 「GRT 寄生估計比 signoff 保守，所以 0.025 ns 夠」寫成通則，只根據 Hazard3；同一規則第 56 行與 knowledge 第 86 列都有反例（PicoRV32 樂觀 ≥ 0.14 ns） | 刪掉通則，只留「每次用 criteria review 確認差距沒有變號」 |
| drv-timing-closure:37（規則 10） | 「是不是同一個迴圈當時沒有確認」 | 移回經驗紀錄 |
| multicorner-sta:52（已知陷阱） | 「依 SDC 語意推測，未實測」 | 移到經驗紀錄，或實測一次 |
| multicorner-sta:17（規則 1） | 放在「規則（已驗證）」，但同檔第 51 行說只讀了程式，沒實跑 | 標成「讀原始碼，未實跑」 |
| formal-equivalence-eqy:70 | 「推測與 `insbuf off` 的別名處理有關，尚未查證」 | 移回經驗紀錄 |
| librelane-run-debug:59 | 「其他幾次『修復不結束』推測同類」 | 移回經驗紀錄 |
| gate-level-simulation:34（規則 9） | 「看起來 OpenSTA 依 SDC 的時脈週期換算（推測，沒讀原始碼）」 | 移回經驗紀錄，或讀原始碼確認 |
| openram:76（規則 14） | 「插在輸出 net 上是推論」 | 標註，或移回經驗紀錄 |
| openram:157（規則 25） | 「另一個 port 的 wordline 也開著，可能寫不進去」，被當成不採用某個做法的理由 | 實測一次，或標成推測 |
| openram:169（規則 27） | 「兩者的關聯是推測」 | 同上 |
| openram:186–198 | 整節「開工前查證（原始碼查證，尚未實跑）」：部分已搬進規則 17–21，剩下的沒標明哪些已驗證 | 拆成「已實跑」與「仍未驗證」兩類 |
| drc-signoff:20–21、46（規則 2、7） | 157.28 µm 是不是 Magic 分塊大小（推測）；licon.14 的比例「計算沒有存檔」；「否則 6 µm 規則會大面積違規（推論）」 | 推測的部分移到經驗紀錄；沒有存檔的數字刪掉 |
| cts-clock-tree:34–35（規則 11） | 寫成「設 150 µm 後 CTS 會把這段線切開」，同條又說「效果沒有單獨實驗」 | 改寫成「設定方式」，不寫效果 |
| cts-clock-tree:17、42 | derate 名目值 0.51 ns 是推算；42 → 43 ns「可能」來自它 | 標明推算，影響小 |
| pdn-ir-drop:34（規則 11） | 「via 電阻不隨 corner 變，所以估算偏高」沒附證據 | 補出處，或標成推測 |
| tapeout-precheck-caravel:24（規則 1） | 「減少 instance 數」能解決 OOM，但同一天 VM 也加到 16 GiB，兩件事沒分開實驗 | 改寫成「兩者一起做才 PASS，哪個是必要的沒分開測」 |
| knowledge:23（S10） | 放在「已驗證的製程事實」，卻寫「這個關係是推論，沒有出處」 | 依 knowledge README 第 18 行，移到「待確認」 |
| knowledge:94 | 「推測約 2.7 ns 是 source latency，沒讀 OpenSTA 原始碼確認」 | 移到「待確認」 |

**說明**：多個 skill 的「提早檢查」規則（ADR-0020 的 A1–E3）是流程回顧之後由使用者決定的做法，效益是推算的，不是實驗結果。它們屬於使用者決定，可以留在規則本文；但 signoff-checker-qualification 規則 11、12 和 floorplan-congestion 規則 7 直接放在「規則（已驗證）」標題下。建議學 tapeout-precheck-caravel，另外放一節「提早檢查（ADR-0020，使用者決定）」。

---

## 2. 工具缺陷的四項防護（`CLAUDE.md` 規則 10）

### 2.1 總數

| 分組 | 檢查的缺陷數 | 四項齊全 | 最常缺的項目 |
|---|---|---|---|
| openram、rtl、lvs、dv、antenna、floorplan、gate-level | 約 43 | 約 18 | 防復發沒寫；確切訊息沒進 description |
| drv、signoff-criteria、multicorner | 25 | 5 | 防復發缺（repo 其實有 checker 卻沒寫出名稱，例如 `check_signoff.py [corners]`、P45） |
| signoff-checker-qualification、tapeout、chip-floorplan、phase-exit | 23 | 10 | 症狀沒進 description |
| librelane、flow-regression、EQY、hard-macro | 36 | 18 | flow-regression 0 個齊全 |
| core、pdn、cts、drc、sdc | 35 | 10 | 防復發缺 |
| **合計** | **約 162** | **約 61（38%）** | |

### 2.2 有缺項、影響較大的（只列會靜默量錯，或已經發生過的）

| skill:行 | 工具 | 缺陷 | 缺的項目 | 建議 |
|---|---|---|---|---|
| tapeout-precheck-caravel（缺整條） | cf-precheck `runner.py` | 讀到前一次 run 的報表也判 PASS | 症狀、怎麼發現、繞過、防復發都沒寫在 skill。其實已有防護：`signoff/precheck/README.md` 第 16 行、`neg_precheck.py` 的 `stale_results`（第 22、262 行）；`phase7.md` 的規則 10 稽核表說「寫在 TPC 規則 3」，不正確 | 寫成 tapeout 的一條規則，四項齊全，並寫進 description |
| flow-regression:98 | 磁碟／STA／EQY | 磁碟滿時 STA 停住、CPU 0%、不報錯；EQY 寫檔失敗被誤判成植入錯誤沒被抓到 | description 沒有 `No space left on device`；「沒有自動防護」只寫在經驗紀錄 | 見 R2、R3 |
| openram:36–37 | ngspice | `.meas` 的 `FALL=1` 從 t=0 起算，會靜默量錯 | 怎麼發現、防復發都缺 | 最需要 checker：量測值和波形的對應用植入錯誤證明（`neg-char` 加一個案例） |
| openram:34 | ngspice | `.tran` 的 TSTEP 會壓住最大步長 | 怎麼發現、防復發缺 | 寫明「沒有自動防護」與原因，或在 deck 產生器檢查 |
| antenna:21 | LibreLane | `DRT_ANTENNA_REPAIR_MARGIN` 宣告了卻沒使用（`drt.tcl:105`），設了也靜默沒效果 | 防復發缺 | 寫明沒有自動防護；`chip.py` 的行號已從 44–45 變成 45–46 |
| antenna:14 | LibreLane | heuristic diode insertion 造成大量 diode 與 GRT 不收斂 | 沒有 checker 確認 `RUN_HEURISTIC_DIODE_INSERTION` 是關的 | `check_inputs.py` 的 config 檢查加一項 |
| drv:16 | PDK | `drc_exclude` 漏了 `clkdlybuf4s*` | 怎麼發現、防復發都缺；`check_inputs.py`、`check_weak_cells.py` 都 grep 不到 | 加進弱 cell 檢查 |
| drv:17 | LibreLane | 沒設 `LAYERS_RC` 時，繞線前電容估計只有實際的一半 | 防復發缺（`config_applied` 只確認設定有套用，不檢查有沒有設） | 加進 `check_inputs.py` |
| drv:14、multicorner:17 | LibreLane | sky130 預設 setup 只判 tt、slew／cap 不判；設了 `LIB` 就不再自動產生 STA corner | 防復發其實有（`check_signoff.py [corners]`），skill 沒寫出 | 寫出 checker 名稱 |
| cts:14、drv:87 | LibreLane | `CTS_MAX_CAP` 沒有作用（DEF 逐 byte 相同） | 兩個 skill 都有，description 都沒有；防復發缺 | 寫明沒有自動防護 |
| cts:19、knowledge:50 | LibreLane 3 | PDK 的 `RT_CLOCK_MIN_LAYER` 沒生效 | 規則寫「必須在專案 config 明確設定」，但 `pnr/*/config.json` 都沒設，也沒有記錄「不設」的決定（只有 `signoff_criteria_soc_top.md:38` 做了 EM 估算） | 補一行決定，或在 config 設定 |
| sdc:13 | LibreLane | 沒設 `SIGNOFF_SDC_FILE` 時，signoff 改讀 pnr.sdc | 防復發：`review_criteria.py:470` 只印 INFO，不判 FAIL | 改成判 FAIL，加 negative test |
| sdc:26–28 | OpenSTA | latency 沒加 `-source` 會變成 ideal；`-clock_path` 無效；重定義 clock 後 inter-clock uncertainty 仍在 | 怎麼發現、防復發缺 | 寫明沒有自動防護 |
| signoff-criteria:84 | OpenSTA | propagated clock 下 `-clock_path` 無效 | 規則寫「要寫 checker」，repo 裡沒有這支 | 做 checker，或改寫成「沒有自動防護」 |
| pdn:29、:30 | PSM／LibreLane | `set_pdnsim_inst_power` 是疊加；`drop__average` 存的是電壓 | 防復發缺 | 寫明 |
| drc:35 | LibreLane → KLayout | `floating_metal`／`topcell`／`threads` 參數名對不上，浮接金屬檢查開不起來 | 繞過與防復發都缺 | 寫明沒有自動防護，或用 plugin 修 |
| drc:45 | KLayout streamout | 不產生 81/14（latch-up 標記） | 只有推論；Phase 7 組裝後沒有確認紀錄 | 列為下次 chip-level 的確認項目 |
| rtl:12 | Yosys | 忽略 `defparam` | `cpu_params.py:75–83` 有 checker，但找不到對應的植入錯誤案例 | 補 negative test |
| tapeout:36、:37 | Netgen／cf-precheck | bitcell 元件命名對不上；`lvs_config.json` 路徑規則 | 沒有確切錯誤訊息，也沒有防復發 | 補訊息原文，寫明防護 |

### 2.3 綁在 flow 會變的東西上的防護（step 名稱、step 編號、log 措辭）

| 位置 | 綁什麼 | 失效時的方向 |
|---|---|---|
| `pnr/librelane_flow.sh:47–48、55` | step 目錄名稱 `*-openroad-repairdesignpostgrt\|*-openroad-resizertimingpostgrt`；log 原文 `^\[ERROR GRT-0229\] ... usage=65534`、`^\[ERROR GRT-0116\]` | 安全方向：不重試，harden FAIL。但 `test-flow-retry` 用的是模擬 log，升版改了措辭時抓不到 |
| `signoff/scripts/review_criteria.py:72–74` `TIMING_STEPS` | 寫死 LibreLane 的 step ID | step 改名時會報「(no step)」；**升版後新增的時序 step 會被靜默略過** |
| `pnr/soc_top/check_soc.py:623、629、667–668、691、800` | `*-odb-reportdisconnectedpins`、`Found (\d+) disconnected pin\(s\)`、`\d+-openroad-cts`、`*-openroad-stapostpnr`、`*-magic-drc` | 找不到就 FAIL，不會靜默 PASS |
| `pnr/soc_top/neg_pnr.py` P55（約 1570 行起） | 中止的 step 目錄編號比較小、沒有後綴 | 升版時要重看 |
| `signoff/eqy/run_eqy.py` | EQY log 措辭 `found constant ... bit` | `wdata3_stuck0` 只靠這一條被抓到，措辭一改它就會 FAIL，所以有防護 |
| `ip/sram/openram/gen_macro.py:72–78` | OpenRAM／Magic／Netgen 的 log 措辭 | 少了任何一行就 FAIL |
| chip-floorplan-pin-planning 規則 4 | `--to Odb.ApplyDEFTemplate`、`OpenROAD.GlobalPlacement` | skill 有交代升版時重看 |
| pdn-ir-drop:27 | 「怎麼發現」看 log 原文「Generate source nodes from bterms」 | 只影響人工查；P26–P28 不綁 |

`CLAUDE.md` 規則 10 要求「工具升版時，逐條重看這些防護是否還成立」，但這些綁定散在 4 支程式與 3 個 skill，沒有一份清單。**建議**：在 librelane-run-debug 加一節「升版時要重看的綁定」，列出上表，並要求升版時用真的 log 重跑 `test-flow-retry` 的情境。`review_criteria.py` 的 `TIMING_STEPS` 再加一項檢查：run 裡有名稱含 resizer 或 timing、但不在清單內的 step，就判 FAIL。

---

## 3. 規則內容的品質

### 3.1 互相矛盾或已過時

| # | skill:行 | 問題 | 依據 |
|---|---|---|---|
| Q1 | floorplan-congestion:12–18（規則 2、3） | 講 macro 位置與 IO pin，完全沒提 `CLAUDE.md` 規則 14、`chip-floorplan-pin-planning`、`pin_plan.toml` 與核准（grep 0 次）；description 也寫「IO pin 擺放、macro 位置」，可能被選中後就跳過核准 | `CLAUDE.md` 規則 14（2026-10-12） |
| Q2 | drv-timing-closure:28–32（規則 9） | 標題「resizer 看不到的 corner，用 PnR 的餘量補」與 setup 0.6 ns、slew 0.70 ns 兩點，讀起來仍是現行規則；規則 15 已規定預設看全部 corner，config 也已改成 0.1 | `docs/relaxation_register.md:36、39`（T12 已被取代、T15 原因已不在）；ADR-0013 |
| Q3 | multicorner-sta:23（規則 3 第 3 點） | 「做法：resizer 用原本的 corner」，被同一規則第 4、5 點與 drv 規則 15 否定 | 同上 |
| Q4 | drv-timing-closure:56 對 :59（規則 12） | 前一點說 GRT 估計不一定比 signoff 悲觀，後一點說比較保守所以 0.025 ns 夠 | 見 1.3 |
| Q5 | timing-constraints-sdc:16（規則 5） | 「只允許已知例外（`sram0/clk1` 沒有 clock，port 1 接地）」 | `check_soc.py:53–58`：Phase 6 起 soc_top 不允許任何例外，wrapper 只允許 29 支 `analog_io` |
| Q6 | pdn-ir-drop:21、33、36、39（規則 4、10、12） | 規則 4 寫 SRAM 電流來自解析模型（Phase 6 已改用 SPICE 量測）；規則 10 寫「chip-level 時要重算」（Phase 7 已從 pad 起算）；規則 12 先寫已被取代的「判最壞組合」，又寫「ff 照跑供 EM 用」（`ir_worst.py` 沒開 `-enable_em`，EM 從沒判過） | ADR-0018 決定 10–15；ADR-0019 決定 19、20；`phase7.md:216` |
| Q7 | pdn-ir-drop:64–73（兩節「待補」） | `VSRC_LOC_FILES` 用未來式，其實已做完；動態功耗用 VCD 已由決定 20、25 完成；「P61 是最壞組合」已過時；EM 列了兩次 | ADR-0019 決定 18、20、25 |
| Q8 | signoff-criteria:138、179、215 | 138 行說「soc_top 排在 Phase 7 步驟 8」還沒改成 pattern（`make ir-soc` 已存在）；215 行說 `ir_worst.py` 判最壞組合（現在判兩個慢 corner）；179 行實作範本的 IR 列缺 `ir_pattern.py` | ADR-0019 決定 19、25；`Makefile:213` |
| Q9 | lvs-signoff 規則 2 | 只寫「0 個時不寫表格」，沒寫外殼頂層預期有斷線腳位；`check_disconnected.py` 沒給路徑（實際在 `pnr/picorv32_core/`） | tapeout:108；`check_soc.py:632–663` |
| Q10 | 數字跟著程式變了，skill 沒跟上 | flow-regression:22 寫 `neg-regress` 5 個情境，實際 8 個；flow-regression:37 與 signoff-checker-qualification:18 寫 run guard 管 14 個下游步驟，實際 16 個（65 個案例），另外 `make_project.py:68` 也呼叫 run guard；chip-floorplan:41 寫 `neg-pin-plan` 25 個案例，實際 26 個；librelane:32 寫 `test-flow-retry` 10 種情境，實際 14 種；hard-macro:19 寫 Q1–Q20，但沒有 Q18；hard-macro:71 只列到 Q13；EQY 規則 4 的案例數與時間還是 Phase 4 的；openram:126 寫 D1–D7，實際 D0–D8；`Makefile:57` 的 help 寫 `neg-precheck` 25 cases，實際 31 個 | `scripts/neg_regress.py`、`neg_run_guard.py`、`neg_pin_plan.py`、`test_librelane_flow.sh`、`neg_macro_views.py`、`neg_openram.py`、`neg_precheck.py` |
| Q11 | flow-regression 規則 2、陷阱:59 | worktree 要設的環境變數只寫 `LIBRELANE_DIR`、`XPACK_DIR`，缺 `PRECHECK_DECK`、`PRECHECK_WORK`、lima VM；規則本文也沒提 `regress-picorv32`、`regress-caravel` | `env/check_env.sh:108–125`；流程文件 4.8 第 294 行 |
| Q12 | tapeout-precheck-caravel:32（規則 3）、:82–90 | 寫「並向 ChipFoundry 反映」，實際仍是草稿沒送（規則 9 第 69 行的說法才對）；「待確認（還沒實跑）」節裡的 oeb、xor、gpio_defines 已實跑 PASS（只是負向沒測）；`FP_DEF_TEMPLATE` 已正式使用 | ADR-0019 決定 6、26 |
| Q13 | chip-floorplan-pin-planning:67（經驗紀錄處理欄） | 說要把供電模型寫進 `pin_plan.toml` 並重新核准，但檔案沒有 `[power]` 節，`phase7.md` 已知限制也沒列 | `pnr/user_project_wrapper/pin_plan.toml` 只有 pads、block、gpio、pin、rtl、governs、approval |
| Q14 | chip-floorplan-pin-planning:23（規則 2） | 證據路徑在 session scratchpad，已經沒了；6.87／143 mV 是 ff 電流加 ss 電阻的組合，決定 19 起只當參考，卻寫在規則與 description 裡 | `CLAUDE.md` 規則 2「證據路徑」 |
| Q15 | phase-exit-review:8、18（規則 4） | 本 repo 實例只寫到 `phase0`–`phase4.md`；章節清單還是 Phase 3 版，沒有後來加的「Skill 分析」「規則 10 稽核」「流程回顧」 | `docs/phase_exit/phase7.md` |
| Q16 | core-migration-hazard3:8、77、91、109 | 「Phase 5 進行中」「待補：exit review」已過時；規則 22 引用「drv 規則 9、11」，實際應該是規則 15；經驗紀錄第 109 列寫「修正方式待使用者決定」，ADR-0012 已決定 | `docs/phase_exit/phase5.md` |
| Q17 | rtl-synthesis-lint:8、19、規則 4 | 週期寫到 43 ns（現在 44 ns），時間順序也亂了；待補「Hazard3（SystemVerilog）的讀入方式」前提不對，原始碼是 `.v`；499 個 lint 警告是 PicoRV32 版的數字 | `pnr/soc_top/config.json:28` |
| Q18 | floorplan-congestion:32–33（待驗證） | 兩項都已過時：die 尺寸已定案；55% 已用了多次，wrapper 改成 50% | ADR-0019 決定 21 |
| Q19 | openram:98、112、202、207 | 「checker 在 Phase 6 步驟 3 建立」（`read_check.py` 已存在）；sha256 重產比對的條件已滿足，checker 還沒做；「Phase 6」的待補已過時 | `ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/` |
| Q20 | drc-signoff:51–57（density 節） | 沒同步 ADR-0019 決定 26：fill 由整合方在 tapeout 時補；fill 試跑的 FOM 有 15 個視窗低於 33% | tapeout:115 |
| Q21 | signoff-checker-qualification:23、128 | 規則 5 仍寫「至少重跑一次」，和規則 11 的「4 個樣本」不一致；表格寫 `neg-ir`，實際 target 是 `neg-ir-soc`／`neg-ir-caravel` | `Makefile:235、238` |
| Q22 | gate-level-simulation:34（規則 9） | 「時脈用 signoff 的週期（testbench 預設 40 ns）」容易讀成 signoff 週期是 40 ns（實際 44 ns） | `dv/tb/tb_soc.v:53` |
| Q23 | 有規則、但沒有對應的經驗紀錄列 | librelane:49、:53；openram 規則 17、24、27 的部分內容 | `CLAUDE.md` 規則 2 |

### 3.2 設計專屬數字寫在規則本文（違反 `CLAUDE.md` 規則 4）

只列例子長到蓋過規則的情況：

| skill:行 | 內容 | 建議 |
|---|---|---|
| pdn-ir-drop:35–43（規則 12） | 一條規則約 1,800 字，一串 `p7_harden2` 的 mV、mW 數字 | 數字移到 ADR-0019 或 `pnr/*/README.md`，規則只留判法與連結 |
| drv-timing-closure:28–32（規則 9）、規則 7 | Phase 4／5 的經過與 buffer 數 | 同上；規則 9 改寫成「拿掉 corner 的例外程序」 |
| cts-clock-tree:21–32（規則 10） | 一串實測值 | 同上 |
| drc-signoff:16–24（規則 2） | 4,665,810、5,579,161、14,166… | 同上 |
| gate-level-simulation 規則 6、8 | 每次 run 的秒數、mdworker 個數 | 移到 `dv/gl_soc/README.md` |
| openram 規則 4、10、15、25、27、29 | 24 GB 機器、20 小時、−2.8 mW、slack +0.548 → +0.151… | 例子縮成一句加 ADR 連結 |
| librelane-run-debug:63–65 | 整節「時間預估」是本設計的實測時間 | 移到 `pnr/*/README.md` |
| formal-equivalence-eqy 規則 4、5 | 每個設計的分區數、秒數；2639／2382 顆 `dfxtp` | 同上 |
| tapeout-precheck-caravel:51–52、59（規則 7、8） | 本設計的 IR 分布與密度數字 | Caravel 的供電結構可以留（下一顆 Caravel 設計用得到），本設計的 mV 數字移出 |
| chip-floorplan-pin-planning:23、:51 | mV 數字、component 數 | 同上 |
| rtl-synthesis-lint:8、規則 4 | 週期與 slack、499 個警告 | 同上 |
| signoff-criteria「IR 用多大的電流」第 2、4、6 項 | 一串 mW 與 mV | 移到 knowledge 或 ADR |
| **signoff-criteria SKILL.md 混 sky130 數字、knowledge 混非製程內容** | SKILL.md 第 18 行說只放和製程無關的方法，卻留著 ss 比 tt 小 37%、met1 EM 電流、met4／met5 方塊電阻等 sky130 數字；knowledge 的 S21（OpenROAD 演算法）、S24（Magic 計數）、S25、S27、S28（OpenRAM macro 與 ngspice gmin），以及校準表裡的 net 名稱 `_21021_`、`hold7844`、golden 誤差 | sky130 數字移進 knowledge；非製程內容移到對應 skill 或 ADR（knowledge README 第 24 行） |

### 3.3 description

**(a) 長度與被擠掉**（本次 6 個 agent 收到的 skill 清單；字數由 `grep '^description:'` 量出）：

| skill | 字數 | 清單裡的狀態 |
|---|---|---|
| openram-macro-characterization | 2,742 | 被截斷（「OpenRAM dev 的 .lib in…」之後看不到，規則 24–28 的錯誤訊息都沒了） |
| tapeout-precheck-caravel | 2,101 | **整段沒有** |
| hard-macro-integration | 1,728 | 被截斷 |
| drv-timing-closure | 1,466 | 完整 |
| signoff-checker-qualification | 1,256 | **整段沒有** |
| librelane-run-debug | 1,212 | 完整 |
| signoff-criteria | 1,210 | **整段沒有** |
| chip-floorplan-pin-planning | 1,129 | 完整 |
| pdn-ir-drop | 942 | **整段沒有** |
| timing-constraints-sdc | 528 | **整段沒有** |
| 其他 13 個 | 223–880 | 完整 |
| **合計** | **21,466** | |

推測：清單照字母順序排，總長度預算用完之後，後面的 skill 就沒有 description；只有 phase-exit-review（545 字）和 rtl-synthesis-lint（241 字）夠短，還擠得進去。確切的預算規則沒查。

**(b) 重要錯誤訊息沒進 description 的**（逐條 grep 核對過）：

- **pdn**：`PSM-0069`、`PSM-0075`
- **cts**：`CTS_DELAY_BUFFER_DERATE_PCT` 無效、`CTS_MAX_CAP` 無效、`RT_CLOCK_MIN_LAYER` 沒生效
- **drc**：`The layout has multiple top cells in Layout.top_cell`、`416 Magic DRC errors found - deferred`、`floating_metal` 參數對不上
- **sdc**：`There is 1 unclocked register/latch pin`、`Reading design constraints file at .../pnr.sdc`、`set_clock_latency` 沒加 `-source`
- **drv**：`Setup violations found in the following corners`、`RSZ-0064`、`RSZ-0032`、`RSZ-0038`、`GRT-0116`
- **multicorner**：`STA-0562`、設了 `LIB` 之後 corner 預設消失
- **signoff-criteria**：沒有任何工具訊息，Stop hook 擋下時的訊息也沒有
- **flow-regression**：`No space left on device`、regress 某一項卡住、同時跑幾條被中止、GDS sha256 不同、`regress-caravel`
- **EQY**：`found constant ... bit`、`KeyError: 'sram0'`
- **tapeout**：`PDN-0239`、`GRT-0036`、讀到舊報表、預建 SRAM 另外報的三條規則名
- **chip-floorplan**：Phase 7 審查後 `check_pin_plan.py` 的新錯誤訊息（ADR 同一行要有原話、日期與 `plan_sha256`）
- **openram**：`no such vector`、`INP2M`、`Analytical model enabled`、`FALL=1`
- **gate-level**：`Unable to bind`、`dangling input port`、`wall-clock timeout`
- **antenna**：`Inserted N diodes`、`DRT_ANTENNA_REPAIR_MARGIN`
- **lvs**：`Found 0 disconnected pin(s)`
- **rtl**：`Recoding FSM`、`defparam`
- **floorplan**：`PDN-0179`

另外，librelane-run-debug 的 description 為了避開 YAML，把 `gloubal routes: found route` 寫成 `gloubal routes found route`，複製去 grep 會對不上。

**(c) 重疊**：

| 重複的內容 | 出現在哪幾個 skill |
|---|---|
| 「最終 GDS 的 macro 是空的」 | hard-macro、drc、lvs |
| 「nwell.6／psdm.1、依名稱排除」 | openram、drc |
| 「internal_power outside」 | openram、hard-macro |
| 「resizer 的 corner 預設等於 signoff corner」 | drv、multicorner、signoff-criteria |
| IR 與 max power pattern | pdn、signoff-criteria、chip-floorplan |
| GPIO 與 block 位置 | chip-floorplan、tapeout |
| IO pin 與 macro 位置 | floorplan-congestion、chip-floorplan（floorplan-congestion 沒有指向 chip-floorplan，見 Q1） |

這些重複佔掉了預算。

**(d) 太短**：lvs-signoff（223 字）、rtl-synthesis-lint（241 字）只寫情況，沒有任何確切訊息。

**建議的 description 寫法**：
- 每份 ≤ 約 600 字，全部合計控制在可以完整顯示的範圍。確切的上限要在 Claude Code 實測，這裡只是推測。
- 先寫確切錯誤訊息與情況，不寫做法細節與設計數字。
- 同一個症狀只放在「先看」的那個 skill。
- `scripts/check_skills.py` 加長度上限（單份與合計），並加一個超長的植入錯誤。

---

## 4. 流程文件與 skill、Makefile、`regress.py` 的一致性（`CLAUDE.md` 規則 8）

### 4.1 已核對、對得上的

- 流程文件與 README 引用的「`<skill>` 規則 N」共 35 處（程式抽出 32 處，加上人工核對的 3 處）逐一對照，全部指到正確的規則。
- `hard-macro-integration` 第 8、10 項與 `signoff-criteria`「PVT corner」一列也對得上。
- 19 條提早檢查（A1–E3）每一條都有對應的 skill 規則：
  - A1、A3、C1、E1 → signoff-criteria
  - A2、C4、D5 → tapeout-precheck-caravel
  - B1、B3、B4 → hard-macro-integration
  - B2 → openram
  - C2、C3 → drv
  - D1 → floorplan-congestion
  - D2 → pdn-ir-drop
  - D3 → core-migration-hazard3
  - D4 → cts-clock-tree
  - E2、E3 → signoff-checker-qualification
- `scripts/regress.py` 的 `TARGET_LISTS`（hazard3 30 項、picorv32 31 項、caravel 18 項）和 Makefile 的 `regress`、`regress-picorv32`、`regress-caravel` 一致，所有 target 都存在。

### 4.2 流程文件過時或和程式不符

| # | 流程文件位置 | 問題 | 依據 |
|---|---|---|---|
| F1 | 4.3 第 3 項（第 207 行） | 寫 negative test「D1–D7」「K0–K6」，實際是 D0–D8a、K0–K8（K7 sky130_fd_io 名稱、K8 deck 解析，Phase 6 審查 H5） | `ip/sram/openram/neg_openram.py:149–298` |
| F2 | 4.5 C3（第 248 行） | 把「ss −40°C 用 0.6 ns 餘量代替」歸到 `multicorner-sta` 規則 3；0.6 ns 其實在 `drv-timing-closure` 規則 9 | drv:29 |
| F3 | 1.5（第 70 行） | `ir_worst.py`（最壞情況的靜態 IR）已過時，現在判兩個慢 corner | ADR-0019 決定 19 |
| F4 | 4.7（第 280–281 行） | IR 判定只寫 Caravel 的 `make ir-caravel`，soc_top 的 `make ir-soc` 只在 4.8 出現；「power signoff（IR、EM、功耗）一律用 pattern」讀起來像 EM 有在判，其實從沒判過 | `phase7.md:216` |
| F5 | 4.8（第 291–292 行） | `regress-picorv32` 只說「換成 core-stock、另加 harden-core…」，沒說它還拿掉了 `regress-rtl-caravel`、`neg-rtl-caravel`、`ir-soc`、`neg-ir-soc`；`regress-caravel` 的描述沒列 `pin-plan`、`neg-pin-plan`、`neg-precheck` | `scripts/regress.py:62–72` |
| F6 | 4.6（第 256 行） | `check_inputs.py` 的檢查項沒有 `inout_dont_touch`（Phase 7 RSZ-0074 的防護） | librelane:93 |
| F7 | `Makefile:57`、`scripts/regress.py` docstring | help 寫 `neg-precheck` 25 cases（實際 31 個）；docstring 列輸出目錄時漏了 `runs/regress_caravel` | `neg_precheck.py` |

### 4.3 skill 裡有、流程文件該提而沒提的重要步驟

| # | skill 規則 | 為什麼新專案需要 | 建議放在流程文件 |
|---|---|---|---|
| G1 | drv-timing-closure 規則 1：四個 `*_VIOLATION_CORNERS = ["*"]` | LibreLane 的 sky130 預設 setup 只判 tt、slew／cap 不判，新專案最容易漏 | 4.5 |
| G2 | phase-exit-review 規則 2、signoff-checker-qualification 規則 13：開結案 regress 前，先在現有 run 上跑 positive control | 已發生兩次，各浪費一輪 regress；流程文件全文找不到「positive control」 | 4.8、4.9 |
| G3 | phase-exit-review 規則 8、9：逐一對照每個 skill 有沒有寫回（`git diff --stat`）、README 與 description 同步、`make skill-check`；Phase 7 另做了規則 10 的工具缺陷稽核 | 4.9 只寫「經驗寫回 skill」 | 4.9 |
| G4 | flow-regression 經驗紀錄 89、94、98 與 `phase7.md` 已知限制 20：同時幾條、記憶體、磁碟、沒有逾時 | 已經發生 4 次 | 4.8（新增「資源」一點） |
| G5 | drv 規則 12：`RUN_POST_GRT_RESIZER_TIMING` | 換 core 後的長路徑 setup | 4.6 |
| G6 | timing-constraints-sdc 規則 2、14：設了 `PNR_SDC_FILE` 就一定要設 `SIGNOFF_SDC_FILE`；driving cell 會蓋掉 input transition | 4.5 C4 只講要比 transition 的數值 | 4.5 |
| G7 | multicorner-sta 規則 8：繞線前量 resizer 看不到的 corner | C3 的 what-if 該怎麼做 | 4.5 C3 加連結 |
| G8 | formal-equivalence-eqy 規則 3、5：常數 bit 一律 FAIL、flip-flop 種類的結構比對、clock 接線追蹤 | EQY 會靜默略過的三種情況，是新專案最需要知道的 | 4.7 |
| G9 | tapeout-precheck-caravel 規則 4、6：SRAM 在 LVS 是 black box（`EXTRACT_ABSTRACT`）、CVC 的 HI-Z 判讀、`lvs_config.json` 路徑；`wb_clk_i` 週期是管理端時脈的下限 | 流程文件全文找不到 CVC、`EXTRACT_ABSTRACT` | 4.7 下線預檢 |
| G10 | antenna-signoff 規則 1：macro LEF 從 SPICE 補 `ANTENNAGATEAREA`（P06） | view QA 的一部分 | 4.3 第 2 項 |
| G11 | gate-level-simulation 規則 6：牆鐘時限用 gate-level 的速度算 | 每顆設計都會遇到 | 4.7 |
| G12 | dv-directed-tests 的核心做法：漏掉的植入錯誤 → 找缺口 → directed 測試 → 在網表植入錯誤證明抓得到 | 4.2、4.7 只列了 skill 名稱 | 4.7 |

### 4.4 流程文件有、skill 沒有對應規則的

| 流程文件位置 | 內容 | 缺在哪個 skill |
|---|---|---|
| 4.8 第 294 行 | 乾淨 worktree 要設 `PRECHECK_DECK` | flow-regression 規則 2 只寫 `LIBRELANE_DIR`、`XPACK_DIR`（Q11） |
| 4.8 第 292 行 | 三條 regress 各在一個乾淨 worktree 跑，外部共用目錄依 checkout 分開；`regress-caravel` 只跑外殼自己的 negative test（ADR-0019 決定 25） | flow-regression 沒提 `regress-caravel` |
| 1.4 第 65 行 | 全域 hook `guard-bash.py`：同時最多 2 個 LibreLane／EQY、可用記憶體至少 4 GB | 沒有 skill 提到這組 hook 與它的漏洞（見 5.2） |
| 4.6 第 281 行 | IR 判定前核對 VCD 的時脈週期等於 `CLOCK_PERIOD` | gate-level 規則 9 有，pdn-ir-drop 沒指過去（輕微） |

---

## 5. 沒有 skill 涵蓋的重大任務類型

### 5.1 盤點

| 任務類型 | 目前散在哪裡 | 狀況 | 建議 |
|---|---|---|---|
| **機器資源與長時間工作的管理**：同時跑幾條 LibreLane／EQY、`-j` 加總、記憶體、磁碟、worktree 建立與清理、卡住偵測、Claude Code 背景指令的 2 小時上限 | flow-regression 規則 5、9、10、陷阱 66（只有 PID 等待與 Spotlight）；經驗紀錄 89、94、97、98；gate-level 規則 6；openram 規則 4；`.claude/guard.json`（只在本機）；`phase7.md` 已知限制 20 | 規則本文沒有並行上限、磁碟、清理、逾時；已經發生 4 次以上（10-07、10-10、10-14、10-15） | **併進 flow-regression-reproducibility**，加一節「資源與長時間工作」，description 同步。不另建 skill，因為觸發情境和 regression 重疊，另建只會再多佔 description 預算 |
| **worktree 的生命週期** | flow-regression 名詞節與規則 5 只講建立；流程文件 1.1、第 37 行提醒舊 worktree 會讓舊版 skill 出現在清單裡 | 本審查量到 13 個舊 worktree（p5final、p5h3、p6close、p6final、p7close、p7close2），`runs/` 合計約 386 GB（其中 p5h3 一個就 102 GB）；主目錄 `runs/` 176 GB | 同上一節：結案 regress 的證據存好之後就刪 worktree（`git worktree remove`），或至少刪掉 negative test 的中間產物；Phase 收尾清單（phase-exit-review）加一項 |
| **skill 本身的維護**：description 預算、規則內數字跟程式漂移 | phase-exit-review 規則 8、9；`make skill-check` | 3.3 的 description 被擠掉、Q10 的數字漂移，兩者都沒有 checker | 不用新 skill：`check_skills.py` 加長度檢查；在 `CLAUDE.md` 規則 4 或 phase-exit-review 加一句「skill 不寫 negative test 的案例數，指向腳本的清單」 |
| 使用者決定與 ADR 的寫法（`CLAUDE.md` 規則 13） | `CLAUDE.md` 規則 13 | 已有規則，每份 ADR 都照做 | 不需要 skill |
| 下線平台的 VM／Docker（lima） | tapeout-precheck-caravel 規則 1 | 已涵蓋，只缺 VM ≥ 15 GB 的檢查名稱（`env/check_env.sh:115–125`） | 補進 tapeout 規則 1 |

### 5.2 `.claude/guard.json`（全域 hook，只在使用者這台機器）的漏洞

供參考，由使用者決定要不要改：
- `require_clean` 只比對 `harden-(soc|core)`，所以 `make harden-caravel` 與 `make harden D=user_project_wrapper` 不會被擋。不過 run 結束時來源追溯仍會判 FAIL（`pnr/soc_top/run.sh:78–80`），所以只是「比較晚才知道」。
- `max_concurrent: 2` 只在下 Bash 指令那一刻數程序，而且只認 `python -m librelane --run-tag` 與 `run_eqy.py` 兩種：
  - `make regress` 之後才產生的 LibreLane 程序不會被數到，所以 Phase 7 同時開三條 regress 時沒有被擋。
  - `neg-pnr` 用的是 `python3 -m librelane.steps run`（`neg_pnr.py:316`，預設 `-j 4`），完全不在計數範圍內。

---

## 6. 建議寫回（依重要性排序）

| # | 目標檔 | 內容 | 理由 |
|---|---|---|---|
| 1 | 全部 23 份 `SKILL.md` 的 `description`；`scripts/check_skills.py`；README skill 一節 | 縮短 description（每份 ≤ 約 600 字，確切錯誤訊息放前面，設計數字與做法移回本文，同一症狀只放在主 skill）；`check_skills.py` 加單份與合計長度上限，加一個超長的植入錯誤 | 5 個 skill 在清單裡整段看不到、2 個被截斷，Claude 選不到它們，`CLAUDE.md` 規則 5 的前提失效（3.3） |
| 2 | `flow-regression-reproducibility` 新增一節「資源與長時間工作」；`scripts/regress.py`；`env/check_env.sh`；`neg_regress.py`；流程文件 4.8 | 並行上限（LibreLane run 總數、EQY 數，依記憶體訂，數字放 ADR）；開跑前檢查剩餘磁碟空間（`env-check-flow`）；每個 regress 項目都有逾時並判 FAIL；舊 worktree 與中間產物的清理；並為以上各項加 negative test | R1–R3：已發生 4 次，最近一次 10-15 讓一條 regress 白跑、另一條卡住 87 分鐘；目前 13 個舊 worktree 約 386 GB |
| 3 | `floorplan-congestion` 規則 2、3 與 description | 開頭加：「新的頂層設計或搬動 macro／pin 之前，先照 `chip-floorplan-pin-planning` 規劃並取得核准（`CLAUDE.md` 規則 14）」 | 目前完全沒提，可能被選中後跳過核准（Q1） |
| 4 | `drv-timing-closure` 規則 9、12；`multicorner-sta` 規則 3；`timing-constraints-sdc` 規則 5；`pdn-ir-drop` 規則 4、10、12 與待補；`signoff-criteria` 第 138、179、215 行；`lvs-signoff` 規則 2 | 改成和最後的決定一致：規則 9 改寫成「拿掉 corner 的例外程序」，經過移到 ADR；刪掉規則 12 的錯誤通則；拿掉 clk1 例外；IR 只寫慢 corner 加 pattern，並寫明 EM 沒判；寫上外殼預期的斷線腳位 | 9 條規則和 ADR-0013、0018、0019 矛盾，照舊規則做會走回頭路（Q2–Q9） |
| 5 | `tapeout-precheck-caravel` 與 description；`docs/phase_exit/phase7.md` 的規則 10 稽核表 | 新增「讀到舊報表」缺陷的四項（`stale_results`）；`PDN-0239`／`GRT-0036` 是預期警告；VM ≥ 15 GB 的 env 檢查；cf-precheck 版本釘定的 checker 名稱；修正「向 ChipFoundry 反映」；「待確認」節分成「已實跑、負向沒測」與「沒跑」 | 已確認的工具缺陷沒進 skill；稽核表的說法和 skill 對不上（2.2、Q12） |
| 6 | `arvinsa-rtl-gds-flow.md` | F1–F7 的修正；G1–G12 的補充，優先 G1（`*_VIOLATION_CORNERS`）、G2（先跑 positive control 再開 regress）、G3（收尾的寫回清單）、G4（資源）、G8（EQY 的三種靜默略過） | 流程文件是新專案的入口，這些是新專案最容易漏的（4.2、4.3） |
| 7 | 各 skill 規則本文（R5–R24） | 升為規則，優先：R6／R7（RSZ-0064 與 hold 進度表）、R5（SDC 有沒有生效看報表）、R8（換 core 時 IR 要重量、共用設定兩個 CPU 都重跑）、R9（RSZ-0074 三種原因的對照表）、R4（GDS sha256） | 都已驗證或出現兩次以上，留在經驗紀錄下次不會被讀到（`CLAUDE.md` 規則 3） |
| 8 | `librelane-run-debug` 新增「升版時要重看的綁定」一節；`review_criteria.py` | 列出 2.3 的 8 處綁定；`TIMING_STEPS` 加「run 裡有沒列入的時序 step 就 FAIL」；升版時用真的 log 重跑 retry 的情境 | `CLAUDE.md` 規則 10 要求升版時重看，但目前沒有清單；`TIMING_STEPS` 會靜默漏掉新增的 step |
| 9 | 2.2 表中各 skill | 補四項的缺項，優先會靜默量錯的：ngspice `FALL=1`（加 `neg-char` 案例）、`DRT_ANTENNA_REPAIR_MARGIN`、`SIGNOFF_SDC_FILE` 從 INFO 改成判 FAIL、`LAYERS_RC`／`clkdlybuf4s*`／heuristic diode 加進 `check_inputs.py`；`RT_CLOCK_MIN_LAYER` 補一個決定 | 規則 10 要求每個確認過的缺陷都有防復發，或寫明沒有 |
| 10 | 1.3 表中各處 | 推測移回經驗紀錄，或標明；ADR-0020 的提早檢查另放一節「使用者決定」 | `CLAUDE.md` 規則 3：推測不進規則本文 |
| 11 | Q10 列的各 skill、`Makefile:57`、`regress.py` docstring；`CLAUDE.md` 規則 4 或 phase-exit-review 規則 9 | 修正漂移的數字（neg-regress 8 個情境、run guard 16 個步驟、neg-pin-plan 26 個、neg-precheck 31 個、test-flow-retry 14 種、沒有 Q18、D0–D8、K0–K8、EQY 案例數）；並訂一條規則：skill 不寫案例數，改成指向腳本的清單 | 同一類漂移出現 9 次，每次 Phase 收尾都會再發生 |
| 12 | 3.2 表中各 skill；signoff-criteria 與 knowledge | 設計數字移到 ADR 或 `pnr/*/README.md`；sky130 數字從 SKILL.md 移到 knowledge；knowledge 裡的非製程內容移出 | `CLAUDE.md` 規則 4；數字太多會蓋過規則，也佔 description 預算 |
| 13 | `phase-exit-review` | 加：收尾時程至少兩輪乾淨 regress 加一輪修正（R16）；審查和 regress 同時跑（R17）；收尾清單加流程文件與 AGENTS.md 同步、清空 `runs/todo.md`、規則 10 稽核、worktree 清理；章節模板與 phase 清單更新到 Phase 7 | Q15；規則 8、11 沒進這個 skill |
| 14 | 過時的「待補」「待驗證」節：pdn、floorplan、core-migration、rtl、openram、chip-floorplan（`[power]` 沒寫進 `pin_plan.toml`，Q13） | 刪掉已做完的；沒做的寫進已知限制 | Q7、Q13、Q16–Q19 |
| 15 | `.claude/guard.json`（全域 hook 讀的設定，由使用者決定） | `require_clean` 加入 `harden-caravel` 與 `harden D=`；並行計數納入 `librelane.steps run` 與 regress 產生的程序 | 5.2；只在本機，屬使用者的全域設定 |

---

## 附錄：本審查用到的核對指令（可重跑）

- description 長度：`for f in .claude/skills/*/SKILL.md; do grep -m1 '^description:' $f | wc -m; done`
- 規則號引用：用 Python 從流程文件與 README 抽出「`<skill>` 規則 N」，對照各 `SKILL.md` 以「N. 」開頭的行（35 處全部對得上）。
- regress 清單：`python3 scripts/regress.py --cpu {hazard3,picorv32,caravel} --list`，以及 `Makefile` 的 target 列表。
- worktree 與磁碟：`git worktree list`（14 列，含主目錄）；`du -sh ../arvinsa-rtl-gds-*/runs`（13 個合計約 386 GB）；`du -sh runs`（176 GB）。
- `make skill-check`：PASS 23 skills（只檢查格式與索引，不檢查長度與內容）。
