# 問題回顧：Phase 0、1、2、3、3.5 遇到的每一個問題，現在被捕捉在哪裡（2026-10-15）

起因：使用者 2026-10-15：「主要目的是把完整走過一次，先review一下所有遇到的問題與檢討哪些是要寫進skill與流程裡的」。本文件只涵蓋 Phase 0（2026-10-03 08:15–11:45）、Phase 1（10-03 08:45–12:37）、Phase 2（10-03 12:37–17:14）、Phase 3（10-03 17:14–10-04 02:46）、Phase 3.5（10-04 22:32–10-05 17:49）。審查者沒有參與實作；只讀檔案與 git，沒有跑 EDA 工具或 make。

**讀過的來源**：`docs/phase_exit/phase0.md`、`phase1.md`、`phase2.md`、`phase3.md`、`phase3_5.md`；ADR-0001–0010（含 ADR-0004、0006、0007 的補充）；`git log` 從 `73f7524`（10-03 08:15）到 `e16465b`（10-05 17:49）中屬於這五個 Phase 的 33 個 commit 的完整訊息（Phase 4 的 `9eca68d`–`96d8ef7` 不列，只在交叉引用時讀）；23 個 skill 中日期為 10-02 到 10-05 的經驗紀錄共 118 列（含少數同日屬於 Phase 4、5 的列）與相關規則本文；`arvinsa-rtl-gds-flow.md`（以下稱「流程文件」）；`docs/relaxation_register.md`（以下稱「登記表」）；`docs/notes/flow_retro/README.md`、`retro_p0_3.md`、`retro_p35_5.md`（ADR-0020 的 19 條提早檢查 A1–E3）；另外為了核對捕捉位置讀了 `docs/notes/signoff_criteria_soc_top.md`、`dv/README.md`、`toolchain.md`、`env/setup.md`、`signoff/scripts/review_criteria.py`。捕捉狀態都用 grep 對過檔案內容。

**結果**：
- 問題共 **90 個**（Phase 0：6、Phase 1：6、Phase 2：15、Phase 3：39、Phase 3.5：24）。同一件事只列一次；跨 Phase 重複出現的放在第一次出現的 Phase，表中寫明後來在哪裡再發生。
- 依「最強的那一層捕捉」分類（以 skill 與流程文件為準；只在本 repo 的程式或設計文件有、skill 與流程沒寫的，算「都沒有」，表中註明 repo 有 checker）：
  - (d) 規則本文或流程文件，加上自動防護（checker、negative test）：**36**
  - (a)／(c) 只有 skill 規則本文或流程文件，沒有自動防護：**42**
  - (b) 只在 skill 經驗紀錄：**3**
  - (e) skill 與流程都沒有：**9**
- 判定有缺口的：**19 個**，合併成 **16 項建議寫回**（見最後一節）。其餘 71 個「不用動」。
- 和 ADR-0020 的 19 條提早檢查重疊的：**19 個**（表中「重疊」欄）。這些「太晚才看」的部分已由 ADR-0020 處理，本文件不重做，只核對捕捉位置；其中 2 個（P2-02、P2-04）在 ADR-0020 合併時漏了一部分，列為建議 6、12。

**主要發現（白話）**：
1. Phase 2、3 的工具問題（DRV 收斂、DRC、antenna、EQY、GRT-0229）與 Phase 3、3.5 的 checker 漏洞，絕大多數已寫成 skill 規則，多數有 negative test。
2. 沒被捕捉的集中在三類：
   - **Phase 1 的 RTL testbench 經驗**：兩輪獨立植入錯誤各漏掉 43–50%，對策（測試被縮水也要 FAIL、介面協定要有 monitor）只寫在本 repo 的 `dv/README.md`，skill 與流程文件 4.2 都沒有通用寫法（P1-01、P1-02）。
   - **「延到之後處理」的項目靠記憶**：Phase 3 筆記寫「Phase 7 確認 latch-up 標記 81/14 覆蓋 soc_top」，Phase 7 沒做，exit review、ADR、登記表都找不到；而且這條還以「推論」的形式寫在 `drc-signoff` 規則本文（P3-10）。偏離計畫時原本保護的東西沒人接（P1-03）、實驗證據沒當下存進 repo（P35-19）也是同一類：事情做了，但沒寫進下一步一定會讀的地方。
   - **Phase 3 收尾查到的 LibreLane 設定靜默無效**（KLayout deck 傳參名稱對不上、`DRT_ANTENNA_REPAIR_MARGIN` 沒用、`RT_CLOCK_MIN_LAYER` 沒生效、`SIGNOFF_SDC_FILE` 沒設時改讀 PnR 的 SDC）：寫成了規則，但 CLAUDE.md 規則 10 要的「怎麼發現、防復發」與 description 的症狀都沒補（P3-11）。規則 10 是 10-07 才建立的，Phase 3 的工具缺陷沒有回頭補齊。
3. 另一份同日審查（`review_p4_5.md`）也獨立找到「實驗證據放在 session 暫存」這類問題，和本文件 P35-19 一致。

**怎麼讀這張表**：
- 「捕捉」欄的代號：(a) skill 規則本文、(b) 只在 skill 經驗紀錄、(c) 流程文件、(d) 自動防護（checker 或 negative test）、(e) 都沒有。
- 「代價」從文件與 commit 時間估，標「估」的是推算。
- 「重疊」欄是 ADR-0020 的提早檢查編號（定義在 `docs/notes/flow_retro/README.md` 33–51 行）。
- 行號是 2026-10-15 `main`（`0d47a3d`）的行號。

---

## 問題總表

### Phase 0：環境

| 編號 | Phase | 問題 | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P0-01 | 0 | 本機到 GitHub 只有 45–175 KB/s：Nix 官方安裝程式低於 250 KB/s 就中止（`curl: (28) Operation too slow`）；ciel 下載 PDK 單連線、不能續傳 | 環境 | 使用者第一次安裝失敗；改寫安裝與 PDK 下載約 1–2 小時（估：`b8d1f82` 08:56 → `b2cdd8c` 09:14、`b798488` 11:45） | 已驗證（量到速度） | (c) `env/setup.md` §2、§3；流程文件 4.0（157 行）列 `make nix-install`、`make pdk-fetch` | 無；環境依 CLAUDE.md 規則 6 不做 skill | 不用動 | — | phase0.md 17、19、27；`b2cdd8c` |
| P0-02 | 0（Phase 1 時發生） | `make clean` 刪掉整個 `runs/`，連進行中的 `runs/flow_setup/` 一起刪。Phase 3.5 再發生同類事：`run.sh` 重跑前 `rm -rf` 上一次的 run（P35-06） | 人為操作／腳本刪檔範圍 | flow_setup 重跑（估 <1 小時）；Phase 3.5 失去 harden 1 的 log | 已驗證 | (e) 只有 `env/setup.md` 71（make clean 的範圍）；`librelane-run-debug` 規則 6 只管 `run.sh` | 「會刪檔的 target 或腳本只刪自己的產出」沒有通用寫法；已發生第 2 次，符合 CLAUDE.md 規則 3 | 建議 9 | — | phase0.md 28；`f5ab58f`；phase3_5.md 63、170 |
| P0-03 | 0 | CI 參考設計原本釘的 librelane-ci-designs commit 不是 LibreLane 3.0.14 自己測試用的那一版 | 規格／假設錯誤 | 小（改釘版） | 已驗證 | (e) 只在 `toolchain.md` 61 | 流程文件 4.0 只寫「用 LibreLane 官方範例重跑一次」，沒寫要用哪一版 | 建議 14 | — | phase0.md 29；`f5ab58f` |
| P0-04 | 0 | 參考設計 `test_sram_macro` 有 74 個 max slew、2 個 max cap 違規，只比「和官方一樣」就不查原因；本機 74、官方 CI 70，是平台差異 | checker 判法／工具預設值 QA | Phase 2 多跑 9 輪試跑（約 4 小時，見 P2-01–P2-04） | 已驗證（本機連跑 3 次相同） | (a) `drv-timing-closure` 規則 14；(c) 流程文件 4.0（159–162 行）；登記表 D16、G06 | 自動防護已列為下一個專案做（ADR-0020 決定 2） | 不用動 | C2 | phase0.md 30；retro_p0_3.md #5 |
| P0-05 | 0／1 | PDK 預建 SRAM 的 Verilog 行為模型在 Icarus 13 編不過（`mem` 先使用後宣告） | IP 與模擬器相容 | 小（`cab6313`） | 已驗證 | (a) `hard-macro-integration` 清單第 1 項 view 表「模擬」列、`gate-level-simulation` 規則 4；(d) `env-check` 檢查模擬副本、`check_inputs.py sim_model`（P64） | 無 | 不用動 | — | `cab6313` |
| P0-06 | 0 | 本機工具限制：macOS GNU make 3.81 不支援 `.SHELLFLAGS`、bash 3.2；Verilator `--binary` 需要的 C++ 編譯器原本沒列進 env-check；flow 內 Yosys 0.62、Verilator 5.044 比本機舊 | 環境 | 小 | 已驗證 | (c) ADR-0005、`toolchain.md` 30–31、59；(d) `make env-check` | 無 | 不用動 | — | ADR-0005；`f5ab58f`；phase0.md 34 |

### Phase 1：SoC RTL、firmware、RTL 模擬

| 編號 | Phase | 問題 | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P1-01 | 1 | testbench qualification 第 1 輪：沒參與撰寫的 agent 植入 20 個錯誤，`regress-rtl` 漏 10 個，例如 firmware 測試主體被跳過仍印 PASS、Boot ROM loader 不驗 checksum、unmapped 位址的回應沒有測試 | checker 漏洞 | 補 `min_cycles`、新測試，neg-rtl 8 → 20（估 1–2 小時，`fb2dedd` 之前） | 已驗證 | 本 repo 有 checker（`test_ctrl` 的 `min_cycles`、`coverage`，`dv/README.md` 68–76），但 (e) skill 與流程都沒有通用寫法：`signoff-checker-qualification` 規則 8 只寫「Phase 1 兩輪」 | 「self-checking 測試被縮水或跳過仍判 PASS」不在漏洞類型表；流程文件 4.2（185–190 行）只要求 self-checking 與 neg-rtl | 建議 3 | E3 的正面例子（Phase 1 寫完就審） | phase1.md 16–22；`fb2dedd` 訊息；dv/README.md 68–76、160 |
| P1-02 | 1 | 第 2 輪：23 個植入錯誤漏 10 個，都是只看最終輸出看不出來的介面或順序錯誤：SRAM 一筆交易存取兩次、IRQ 線晚放 40 cycle、UART 除數 reset 值錯（Boot ROM 又寫一次所以蓋掉）、先寫 DONE 再寫 SIG、UART stall 路徑沒走到 | checker 漏洞 | 4 個新 checker（`sram_port`、`irq_line`、`uart_div`、`coverage`）、2 支新測試，neg-rtl 20 → 33（`fb2dedd` 11:23 → `b1c818d` 12:37，約 1.2 小時） | 已驗證（每個錯誤在兩個模擬器重跑） | 同上：本 repo 有 checker，(e) skill 與流程沒有 | 「只比最終結果，中間的介面錯誤互相掩蓋」沒寫成漏洞類型；「接 macro 的介面要有腳位層的協定 monitor」也沒寫 | 建議 3 | — | phase1.md 23–39；`b1c818d`；dv/README.md 15–17、139–148 |
| P1-03 | 1、3 | 與計畫不同時，原本那一項保護的東西沒人接：Phase 1 的 spec 把 R02 從 memtest 改成 bootrom_march，memtest 的 SRAM 上半部沒有測試保護（第 1 輪審查才補 `R02_memtest`）；Phase 3 的 P07、P12 從「改版圖」變成「只改 metrics」，EQY 從 RTL 對網表縮成合成網表對最終網表，共 13 項與計畫不同 | 流程／計畫偏離 | Phase 1：1 個 coverage 洞（審查抓到）；Phase 3：RTL → 合成網表這段到 Phase 7 都沒有 formal（登記表 V01） | 已驗證 | (e)：`phase-exit-review` 規則 4 只列「與計畫不同的地方」這個章節，沒要求寫失去的保護；登記表 E1 管放寬，沒管「檢查方式改了」 | 偏離計畫時沒有「原本保護什麼、現在誰保護」的欄位；第 2 次發生 | 建議 4 | — | phase1.md 43；phase3.md 99–112、140–152；登記表 V01 |
| P1-04 | 1 | Boot ROM loader 拒收錯誤封包（F23、F24）只有 negative test 抓得到：正確結果是 DONE = fail code，spec 不允許當正向測試 | 規格限制 | 無 | 已驗證 | (c) 流程文件 4.2 的 neg-rtl；(d) `neg-rtl` L01–L03 在 `make regress` 第 1 組 | 無 | 不用動 | — | phase1.md 25、48；soc_spec.md 200–204 |
| P1-05 | 1（Phase 5 發作） | `sram_cov` 用精確次數、`min_cycles` 約為實測的 90%，跟程式綁死；Phase 5 換 Hazard3 後 CPI 變小，memtest 等 3 支早於 `min_cycles` 而 FAIL | checker 脆弱 | Phase 5 重量 cycle 數 | 已驗證 | (a) `core-migration-hazard3` 規則 10、18 | 無 | 不用動 | — | phase1.md 50；core-migration-hazard3 經驗紀錄 107 |
| P1-06 | 1 | 其他限制：negative test 只在 Icarus 跑（Verilator 是 2-state，沒有 `x_check`）；Python 3.11 只檢查語法；上游 `test_rvf` N/A（沒有 riscv-formal）；spec「第一步寫 DIV」要具體化 | 已知限制／規格模糊 | 小 | 已驗證 | (e) 只在 phase1.md | 都是本設計的限制，沒有可帶走的新規則 | 不用動 | — | phase1.md 44、51–54 |

### Phase 2：單獨 harden PicoRV32

| 編號 | Phase | 問題 | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P2-01 | 2 | resizer 把驅動很弱的 clock delay cell `clkdlybuf4s25_1` 當一般 buffer 用（PDK 排除清單漏列） | 工具預設值／library | P2-01–P2-04 合計 9 次試跑，約 4 小時（retro 估），第 1 次 slew 違規 5544 | 已驗證 | (a) `drv-timing-closure` 規則 2.1、10、14；(d) `check_weak_cells.py`（P40–P42，只查 `RSZ_CORNERS`） | 「所有 signoff corner」的查表已列為 C2，下一個專案做 | 不用動 | C2 | phase2.md 35–37；retro_p0_3.md #5、#6 |
| P2-02 | 2 | LibreLane 對 sky130 的繞線前寄生表 `LAYERS_RC` 在原始碼裡被註解掉，估計的線電容只有實際的一半（0.08 對 0.178 fF/µm），resizer 修得不夠 | 工具缺陷（flow 預設值） | 同上 | 已驗證 | (a) `drv-timing-closure` 規則 2.2；(c) 流程文件 4.0 的例子；登記表 T17 | ① CLAUDE.md 規則 10 的「怎麼發現」「防復發」沒寫（沒有 checker 確認 `LAYERS_RC` 有設，也沒寫明「沒有自動防護」）；② retro 的 E5(b)「比對繞線前估計與繞線後萃取的線電容」在合併成 C2 時掉了（retro_p0_3.md 80 對 flow_retro/README.md 41） | 建議 6 | C2（部分漏收） | phase2.md 38；pnr/picorv32_core/README.md 44–67 |
| P2-03 | 2 | slew／cap 修復只在 CTS 前做一次，之後 hold buffer 與繞線又加負載；開 `RUN_POST_GRT_DESIGN_REPAIR`（LibreLane 標為 experimental）加 30% 餘量 | 工具預設值 | 同上 | 已驗證 | (a) `drv-timing-closure` 規則 2.3–2.4、`librelane-run-debug` 已知陷阱（experimental 選項）；(d) `check_signoff.py` 每個 corner 的 slew／cap 上限 | 無 | 不用動 | — | phase2.md 39、98 |
| P2-04 | 2 | CTS 末端 dummy load 讓 fanout 超過 10、H-tree 中段沒放 buffer（fanout 16）；dummy load 在 LibreLane 3.0.14 關不掉（OpenROAD 有 `-dont_use_dummy_load`），當時接受為已知限制 | 工具預設值 | 同上 | 已驗證（設定前後比較） | (a) `cts-clock-tree` 規則 1–3；規則 13 有通則「flow 變數關不掉時查底層工具選項」 | `-dont_use_dummy_load` 在 skill 裡找不到；它是規則 13 那個模式更早的一次（Phase 2 就知道有選項、選擇接受），規則 13 的「為什麼」只舉 Phase 4 的例子 | 建議 12 | D4（後半，部分漏收） | phase2.md 40、97 |
| P2-05 | 2 | 試過排除 `buf_1`：resizer 改用 `dlygate4sd3_1` 當 buffer，ss setup −3.54 ns，退回 | 退回的做法 | 1 次試跑 | 已驗證 | (a) `drv-timing-closure`「退回過的做法」 | 無 | 不用動 | — | phase2.md 42 |
| P2-06 | 2 | LibreLane 對 sky130 預設 setup 只判 tt、max slew 與 max cap 不判；不設 `*_VIOLATION_CORNERS` 會漏掉 ss 的違規 | 工具意外行為 | 試跑 #4 才發現 | 已驗證（LibreLane 原始碼行號） | (a) `drv-timing-closure` 規則 1、`timing-constraints-sdc` 規則 9；(d) `check_signoff.py` 逐 corner 判、P04（ss setup） | 無 | 不用動 | — | phase2.md 69 |
| P2-07 | 2 | 多執行緒 detailed routing 不可重現：第一次 `make phase2` 有 71 個 metric 極小差異，golden 比對 FAIL | 工具行為／checker 判法 | 1 次 `make phase2`（23.5 分鐘）；之後各 Phase 的 golden 問題見 E2 | 已驗證（逐步比對 DEF） | (a) `signoff-checker-qualification` 規則 5、11；(c) 流程文件 4.6 E2；(d) P31、P50、P51；登記表 G01–G06 | 「樣本數 ≥ 4」的自動檢查已列為下一個專案做 | 不用動 | E2 | phase2.md 44–56 |
| P2-08 | 2 | `cpu_params.py` 的漏洞：看不到 `defparam`、`` `ifdef SYNTHESIS `` 分支、config 的 `pdk::` 條件區塊，也不比 harden run 實際用的參數 | checker 漏洞 | 獨立審查 47 個植入；修正後 14/14 | 已驗證 | (a) `rtl-synthesis-lint` 規則 1（defparam、SYNTHESIS）、`signoff-checker-qualification` 規則 3（比 `resolved.json`）；(d) 每次 harden 跑 `cpu_params.py --resolved` | config 的 `pdk::`／`scl::` 條件區塊會依 PDK 換參數，skill 沒寫 | 建議 13 | — | phase2.md 70、79 |
| P2-09 | 2 | `check_signoff.py` 接受 inf／1e30 slack、`false` 當 0、誤差設成 inf、誤差套到 count／area、corner 名單重複 | checker 漏洞 | 獨立審查；50/50 | 已驗證 | (a) `signoff-checker-qualification` 規則 1、2、5；(d) `check_signoff.py` 的型別與誤差檢查、P12、P31、P50 | 無 | 不用動 | — | phase2.md 72、81 |
| P2-10 | 2、3 | 斷線 pin 表被截斷時 checker 判 PASS（Phase 2）；0 個斷線時 LibreLane 根本不產生表（Phase 3） | checker 漏洞／工具行為 | 小 | 已驗證 | (a) `signoff-checker-qualification` 規則 1、`lvs-signoff` 規則 2；(d) P15 | 無 | 不用動 | — | phase2.md 82；lvs-signoff 經驗紀錄 27 |
| P2-11 | 2、3 | 計畫要求 unannotated net = 0，實際 114（Phase 2）／134（Phase 3），都是沒接繞線的 driver；LibreLane 的 filtered 版本只認頂層 port | 規格假設／工具檢查範圍 | 小 | 已驗證（逐項列組成） | (a) `signoff-checker-qualification` 規則 4、漏洞類型「工具的檢查範圍比名稱小」；(d) 上限檔「剛好 N 個」；登記表 V07 | 無 | 不用動 | — | phase2.md 83、89；phase3.md 143 |
| P2-12 | 2 | 上游 testbench 對 3 個網表錯誤仍印 `ALL TESTS PASSED`，只有 RTL 對網表的 bus trace 比對抓到；另 3 個（`rdcycleh`／`rdinstreth` 高半部、bus-error IRQ）firmware 從沒用到，gate-level 模擬全漏 | 驗證覆蓋缺口 | Phase 3 提前做 EQY 也補不到（P3-16），Phase 4 才補 directed 測試 | 已驗證（定向測試確認功能上看得見） | (a) `dv-directed-tests` 規則 1、`gate-level-simulation` 規則 2、5、`signoff-checker-qualification` 漏洞類型「覆蓋不到的功能」；(d) `counters`、`buserr` 與 `neg_gl_soc.py` 的案例；登記表 V01、V06 | 「事後從漏掉的植入錯誤找缺口」已寫；「事先量 RTL code coverage」（retro P03 E10，ADR-0020 沒收進 19 條）沒進流程 | 建議 16 | retro E10（不在 19 條） | phase2.md 73、102–107；retro_p0_3.md #10 |
| P2-13 | 2、3、3.5 | 每個 Phase 的 exit review 都有寫錯的數字或事實：Phase 2 寫「唯一一次 make phase2 PASS」其實 FAIL、hold buffer 成因與 `power__total` 機制寫錯；Phase 3 寫錯 6 個；Phase 3.5 寫錯 6、不準確 11、找不到證據 5 | 文件與實作不一致 | 每次一輪文件審查與更正 | 已驗證 | (a) `phase-exit-review` 規則 2、3、5 | 無（文件核對已是固定步驟） | 不用動 | — | phase2.md 84；phase3.md 208；phase3_5.md 176–202 |
| P2-14 | 2 → 3 | 延到下一階段的來源追溯與 `make harden D=<design>`，到 Phase 3 收尾才發現還沒做 | 流程順序 | Phase 3 收尾補做 `provenance.py`、`neg_provenance.py` | 已驗證 | (a) `phase-exit-review` 規則 1、`signoff-checker-qualification` 規則 9 | 規則只要求對照 exit review 的「已知限制」與「留到下一階段」；寫在 `docs/notes/` 筆記裡的「之後處理」不在對照範圍（P3-10 就是這樣漏掉的） | 建議 1 | — | phase2.md 91；phase3.md 133；phase-exit-review 經驗紀錄 34 |
| P2-15 | 2 | hold 修復餘量 0.1 ns 讓 resizer 插 2230 顆 hold buffer、約 11% 面積（真正違規的路徑很少） | 工具行為（代價） | 面積 | 已驗證 | (a) `drv-timing-closure` 規則 7 | 無 | 不用動 | — | phase2.md 96 |

### Phase 3：整合預建 SRAM

| 編號 | Phase | 問題 | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P3-01 | 3 | SRAM 離 die 邊 25 µm，上方只剩約 6 µm 的 row，PDN 報 `PDN-0179 Unable to repair all channels`（ADR-0006 的 DIE_AREA 只用面積比估，沒做 floorplan 試跑） | 工具行為／流程順序 | 1 次試跑 | 已驗證 | (a) `floorplan-congestion` 規則 2、7、`hard-macro-integration` 經驗紀錄 81；(c) 流程文件 4.4 D1；(d) PDN 錯誤讓 flow 停 | 無 | 不用動 | D1 | phase3.md 61；ADR-0006 42 |
| P3-02 | 3 | global placement 自動目標密度 68%，cell 擠在 L 形 logic 區轉角繞路（端點 117 µm、繞線 353 µm），ss 有 max slew 違規；中途把 signoff max transition 放寬到 1.0 ns，找到根因後撤回 | 工具預設值／流程順序 | 約 8 次探索 run，3–4 小時（retro 估）；放寬一次又撤回 | 已驗證（55%、50% 兩組都 0） | (a) `floorplan-congestion` 規則 4–7、`drv-timing-closure` 規則 2.6、5；(c) 流程文件 4.4 D1；登記表 T06、T20 | 密度判定的 checker 已列為下一個專案做 | 不用動 | D1、E1 | phase3.md 65–69；ADR-0009 |
| P3-03 | 3 | `RUN_HEURISTIC_DIODE_INSERTION` 對全設計 > 90 µm 的線插 diode，共 10,231 顆，global routing 10 分鐘以上不收斂 | 工具行為 | 1 次試跑 | 已驗證 | (a) `antenna-signoff` 規則 3 與 description | 無 | 不用動 | — | phase3.md 62；ADR-0008 12 |
| P3-04 | 3 | PDK SRAM 的 LEF 沒有 `ANTENNAGATEAREA`，antenna 檢查看不到接到 SRAM 輸入的線，「antenna = 0」只是看不到 | macro view 缺陷 | ADR-0008（從 SPICE 算閘極面積） | 已驗證 | (a) `antenna-signoff` 規則 1、`hard-macro-integration` view 表；(d) `check_inputs.py antenna_lef`（P18）、P06 | 無 | 不用動 | — | ADR-0008 4；phase3.md 37 |
| P3-05 | 3 | antenna repair 在 resizer 之後才加 diode，diode 的 pin 也算 fanout：一顆 buffer 帶 10 個負載再加 1 顆 diode = 11 | 工具行為 | PnR fanout 收到 8 | 已驗證 | (a) `antenna-signoff` 規則 4；ADR-0009 第 2 點 | 無 | 不用動 | — | ADR-0009 33；drv-timing-closure 經驗紀錄 120 |
| P3-06 | 3 | clk pin 在左下角，到第一級 clock buffer 660 µm，ss slew 0.92 ns（clock net 不在 resizer 修復範圍）；Phase 4 同類再現（360 µm） | 工具行為／floorplan | 1 次試跑 | 已驗證 | (a) `cts-clock-tree` 規則 4、11、`floorplan-congestion` 規則 3；(d) signoff 的 slew 上限 | 無 | 不用動 | — | cts-clock-tree 經驗紀錄 57、60 |
| P3-07 | 3 | Magic 輸出的 GDS 有 13 個 top cell，`KLayout.Render` 失敗；改由 KLayout 輸出 GDS | 工具缺陷 | 1 次試跑 | 已驗證 | (a) `drc-signoff` 規則 3 與 description；(d) XOR、`check_soc.py macro_gds` | 無（輸出工具改了的後果見 P3-10） | 不用動 | — | phase3.md 63；drc-signoff 經驗紀錄 80 |
| P3-08 | 3 | abstract DRC 每條 row 報 `nwell.4`（416 個假錯誤），計畫 §6.3「abstract DRC = 0」的前提不成立 | 工具行為／計畫假設 | 1 次試跑 | 已驗證 | (a) `drc-signoff` 規則 1 與 description | 無 | 不用動 | — | phase3.md 64、141 |
| P3-09 | 3 | SRAM 在標準規則下有數百萬個 Magic DRC 違規，只好 `ERROR_ON_MAGIC_DRC=false`，改用自寫 checker；第一版只比規則種類，SRAM 框內多一個同種類錯誤照樣 PASS（審查找到） | checker 漏洞 | Phase 4 改比位置 | 已驗證（假報告實驗） | (a) `drc-signoff` 規則 2；(d) P10、P21、P69；登記表 D01–D03 | 無 | 不用動 | — | phase3.md 141、190 |
| P3-10 | 3 → 7 | latch-up 區域標記 81/14：Magic 寫 GDS 會自動加，KLayout 不會；soc_top 與 Caravel wrapper 的最終 GDS 都由 KLayout 輸出（P3-07）。Phase 3 筆記寫「Phase 7 確認 81/14 覆蓋 soc_top」，Phase 7 的 exit review、ADR-0019、登記表都沒有這一項 | 流程順序（延後的待辦遺失）；可能的下線風險 | 未知：一直沒查證 | 推測：「沒有標記的區域適用 6 µm tap 規則、會大面積違規」是推論；flow 的 Magic DRC（會查 LU 規則）讀的是 Magic 自己輸出、有標記的那份 GDS，還是交付的 KLayout GDS，也沒查 | (a) `drc-signoff` 規則 7（本文寫「推論」，不符合 CLAUDE.md 規則 3）、`signoff-criteria` 163 行；筆記 `signoff_criteria_soc_top.md` 41、118；(e) `docs/phase_exit/`、`docs/decisions/`、登記表 grep `81/14` 都沒有結果 | ① 延後的待辦只寫在筆記，被漏掉；② 推論寫在規則本文 | 建議 1 | — | signoff_criteria_soc_top.md 41、118；drc-signoff 43–46 |
| P3-11 | 3 | Phase 3 收尾的 signoff 條件調查查到 4 個 LibreLane 設定靜默無效：KLayout DRC 的傳參名稱對不上（`floating_metal` 對 deck 的 `$floating_met`，浮接金屬檢查開不起來；`topcell`、`threads` 也對不上）；`DRT_ANTENNA_REPAIR_MARGIN` 宣告了但沒用；PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒生效（clock 實際走 met1／met2）；`SIGNOFF_SDC_FILE` 沒設時 signoff STA 改讀 `PNR_SDC_FILE` | 工具缺陷（flow 設定靜默無效） | 小（當時都繞過或記錄） | 已驗證（讀原始碼、`resolved.json`、sta.log） | (a) `drc-signoff` 規則 5（35 行）、`antenna-signoff` 規則 10、`cts-clock-tree` 規則 8、`timing-constraints-sdc` 規則 2 | CLAUDE.md 規則 10 的四項不齊：沒有「怎麼發現」與「防復發（或寫明沒有自動防護與原因）」；`cts-clock-tree`、`antenna-signoff`、`timing-constraints-sdc` 的 description 沒有這幾個變數名。`review_criteria.py` 只把兩份 SDC 的 max transition 印成 INFO（470–475 行），不判 | 建議 2 | — | drc-signoff 經驗紀錄 82；cts-clock-tree 經驗紀錄 58；antenna-signoff 經驗紀錄 37；timing-constraints-sdc 經驗紀錄 55 |
| P3-12 | 3 | §7.2 的「最長線 ≤ 門檻」沒訂門檻；LibreLane 的 `Checker.WireLength` 因為沒設門檻而略過、不報錯（最長線 619.53 µm 只由 golden 鎖住） | 工具意外行為（內建 checker 靜默略過） | 小 | 已驗證（phase3.md 的陳述；本次沒有重看 log） | (e) 只在 phase3.md | LibreLane 內建 checker 沒設門檻就略過，skill 沒寫；`review_criteria.py` 的 `checkers_ran` 只看 repo 自己的 checker | 建議 10 | — | phase3.md 37、150 |
| P3-13 | 3 | `RepairDesignPostGRT` 隨機報 `GRT-0229 ... (79, 0) usage=65534` 中止（同一份輸入 2/4）；explore3 只跑一次就把它歸因到 `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH`，後來證實不對 | 工具缺陷；錯誤歸因 | 第一次 `make phase3` 中止；4 次單步重跑 | 隨機性已驗證；機制（clk pin 所在 GCell、CTS NDR）推測 | (a) `librelane-run-debug` 規則 5、已知陷阱與 description；(d) `pnr/librelane_flow.sh` 有上限的重試、`make test-flow-retry`；登記表 G07 | 規則 10 四項齊全；根因實驗（移動 clk pin）沒做，推測正確地留在經驗紀錄 | 不用動 | — | phase3.md 70–74、168；docs/notes/grt0229_repro.md；floorplan-congestion 經驗紀錄 46 |
| P3-14 | 3 | LibreLane console 折行，`GRT-0229 ... usage=65534` 被拆成兩行，單行 regex 永遠對不到，重試永遠不會發生（模擬測試前讀碼發現） | checker 漏洞／工具輸出格式 | 小 | 已驗證 | (a) `librelane-run-debug` 已知陷阱、`signoff-checker-qualification` 漏洞類型「比對的文字被輸出格式拆開」；(d) `test-flow-retry` | 無 | 不用動 | — | signoff-checker-qualification 85 行 |
| P3-15 | 3 | `RepairDesignPostGRT` 單執行緒 13–26 分鐘不結束（explore6 修復餘量 50%、explore8 長線 120 µm）；Phase 5 才確認同類現象的根因是弱 cell | 工具缺陷 | 2 次試跑各停在 13–26 分鐘 | 這兩次是推測同一機制（當時沒記記憶體） | (a) `drv-timing-closure` 規則 10、退回過的做法；`librelane-run-debug` 已知陷阱 | 無（推測已標明） | 不用動 | C2 | librelane-run-debug 經驗紀錄 79；ADR-0009 18、20 |
| P3-16 | 3 | EQY 做不到 RTL 對網表：Yosys 把狀態機重新編碼（`cpu_state` 8 → 6 bit），上電值未定的暫存器被換成常數；L4 範圍縮成合成網表對最終網表 | 工具行為／計畫假設 | RTL → 合成網表這段到 Phase 7 都沒有 formal（登記表 V01） | 已驗證（合成 log `Recoding FSM`） | (a) `rtl-synthesis-lint` 規則 2、3、`formal-equivalence-eqy` 規則 1；(c) 流程文件 4.7 的「限制」 | retro P03 E10「先拿一個區塊試 EQY RTL 對合成網表、再定 L4 範圍」沒收進流程 | 建議 16 | retro E10（不在 19 條） | phase3.md 140、178–181；rtl-synthesis-lint 經驗紀錄 25 |
| P3-17 | 3 | EQY 切分步驟在 8 MB stack 下 SIGSEGV（returncode −11） | 工具與環境 | 小 | 已驗證 | (a) `formal-equivalence-eqy` 規則 2、`toolchain.md` 57；(d) `run_eqy.py` 自己設 `ulimit` | 無 | 不用動 | — | formal-equivalence-eqy 經驗紀錄 80 |
| P3-18 | 3 | EQY 把對應到常數的 bit 當成已對應、不證明：輸出被植入卡 0 時，15,136 個分區照樣全部證明通過 | 工具靜默略過 | 小 | 已驗證 | (a) `formal-equivalence-eqy` 規則 3、description、`signoff-checker-qualification` 漏洞類型表第 1 列；(d) `found constant` 即 FAIL、`wdata3_stuck0` | 無 | 不用動 | — | phase3.md 127 |
| P3-19 | 3 | EQY 的證明步驟只在「卡成常數」的錯誤上驗證過；反相器、mux 對調都在切分時就因名稱矛盾被拒，沒走到證明 | negative test 範圍不足 | Phase 4 補 nand2 → nor2 類案例 | 已驗證 | (a) `signoff-checker-qualification` 規則 7「斷言抓到它的機制」、`formal-equivalence-eqy` 的 negative test；(d) `neg_eqy.py REQUIRE` | 無 | 不用動 | — | phase3.md 159–163 |
| P3-20 | 3 | 植入沒有生效，或植入點不是 checker 讀到的值：P05（`PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路逐字相同，PSM 只查電源網路自己的 shape）、P06（換 LEF 後 `CheckAntennas` 仍讀 ODB 裡的舊資料；找 step 目錄還挑到 `-1` 字尾的那次）、P13（`unset_output_delay` 沒刪掉，或刪了 `check_setup` 仍當作有設）、P03（被後讀的 SDC 蓋掉，推測） | checker 漏洞（negative test 本身） | 每案各重寫一次 | 已驗證（P03 推測） | (a) `signoff-checker-qualification` 規則 7、漏洞類型「植入沒有生效」「工具快取了舊資料」、`antenna-signoff` 規則 5、`timing-constraints-sdc` 規則 6、`librelane-run-debug` 已知陷阱 | 無 | 不用動 | — | phase3.md 99–107、128–130；signoff-checker-qualification 經驗紀錄 146–149 |
| P3-21 | 3 | P10 的說明寫 KLayout 與 Magic DRC 都會 FAIL，程式只斷言 KLayout；取代 `ERROR_ON_MAGIC_DRC` 的自寫 checker 沒被植入錯誤測過 | 文件與實作不一致 | 收尾自查補 Magic DRC 重跑 | 已驗證 | (a) `signoff-checker-qualification` 規則 7（說明與程式一致、自寫 checker 取代工具判定時要有自己的植入錯誤）、`drc-signoff` 的 negative test 一節 | 無 | 不用動 | — | phase3.md 104、131 |
| P3-22 | 3 | 多數 PnR negative test 在檔案副本上植入、只重跑 checker；P07、P12、P15 改的是報告或 metrics，只測 checker 本身，不是從版圖或合成植入（計畫原本是放大 PDN pitch、讓輸出變常數） | negative test 範圍 | 已知限制 | 已驗證 | (a) `signoff-checker-qualification` 規則 7「每個 checker 至少一個真錯誤」 | 沒有規則要求「優先在產生資料的源頭植入；只改報告的案例標明只測 checker 本身，總表分開計數」 | 建議 11 | — | phase3.md 101、106、166 |
| P3-23 | 3 | neg-pnr 的假 run 沒有 STA 結果，`sta_setup` 永遠 FAIL，「整體 FAIL」斷言沒作用，也沒有 positive control；neg-eqy 不檢查 FAIL 的位置（審查找到，已知限制 15、16） | checker 漏洞 | Phase 4 開頭修 | 已驗證 | (a) `signoff-checker-qualification` 規則 7（假 run 先有 positive control、確認 FAIL 位置）；(d) P00、`neg_eqy.py` 位置交叉檢查 | 無 | 不用動 | — | phase3.md 191–192 |
| P3-24 | 3 | 下游步驟（EQY、gate-level 模擬）只看 `signoff.txt`：soc 專用檢查或輸入一致性 FAIL 的 run 也會被拿去用；也不確認 run 是現在這個 commit 產生的 | checker 漏洞 | Phase 3 收尾、Phase 4 修 | 已驗證 | (a) `signoff-checker-qualification` 規則 3、`flow-regression-reproducibility` 規則 4；(d) `run_guard.py`、`neg-run-guard` | 無 | 不用動 | — | phase3.md 132、182–186 |
| P3-25 | 3 | 來源追溯只比 LibreLane clone 的 commit 與 PDK 的 hash 字串：改了 clone 裡的 `base.sdc` 照樣 PASS | checker 漏洞 | Phase 4 修 | 已驗證（審查實測） | (a) `flow-regression-reproducibility` 規則 3；(d) `neg-provenance` | 無 | 不用動 | — | phase3.md 187–189 |
| P3-26 | 3 | `make gl-soc`、`neg-gl-soc` 沒宣告依賴 `fw`；開發目錄有舊 firmware，只有乾淨 checkout 會出錯 | 流程（建置依賴） | 第二次 `make phase3` 白跑（估約 40 分鐘） | 已驗證 | (a) `signoff-checker-qualification` 規則 10、`gate-level-simulation` 規則 7、`flow-regression-reproducibility` 已知陷阱 | 無 | 不用動 | — | phase3.md 135；`acbc126` |
| P3-27 | 3 | `neg_gl_soc.py` 借用 EQY 的植入程式，`wire` 宣告在使用之後，Yosys 接受、Icarus 編譯失敗；腳本沒單獨跑過就加進 `make phase3`（Phase 3.5 的 P17、Phase 6 的 `check_inputs.py` 再發生「改完沒先跑」） | 流程（新 checker 沒先跑） | 第三次 `make phase3` 白跑（`acbc126` 00:01 → `53529c6` 00:50，約 50 分鐘） | 已驗證 | (a) `signoff-checker-qualification` 規則 7、10、`flow-regression-reproducibility` 規則 9、`phase-exit-review` 規則 2 | 無 | 不用動 | — | phase3.md 136；`53529c6` |
| P3-28 | 3（Phase 6 發現） | `check_setup` 把「`sram0/clk1` 沒有 clock」（port 1 的 clock 接 0）列為唯一允許的例外；Phase 6 證實 OpenRAM 未用 port 的 clock 接常數時 chip-select 不會被鎖存，wordline 可能一直開著 | 規格／假設錯誤（例外清單掩蓋了真問題） | Phase 6 改 RTL（`clk1` 接系統時脈） | 已驗證（Phase 6 SPICE） | (a) `hard-macro-integration` 清單第 3 項；(c) 流程文件 4.3 第 0、4 項（未用 port 照實際接法模擬）；(d) `check_soc.py port1_tieoff`（P65） | 無 | 不用動 | — | phase3.md 151；ADR-0018 決定 9 |
| P3-29 | 3 | signoff 條件到 Phase 3 收尾才推導：半週期路徑沒有 duty cycle 預算、沒有 min pulse width 檢查、IR 上限 90 mV 與 ss corner 1.60 V 隱含的 20 mV 不一致、沒跑溫度反轉 corner、IO hold 等於沒檢查 | 流程順序 | Phase 4 週期 40 → 42 ns 等（retro 估：harden 5 次約 3.5 小時、regress 4 次） | 已驗證（nom_ss duty 59% 時 slack −0.022 ns） | (a) `signoff-criteria`、`timing-constraints-sdc` 規則 7；(c) 流程文件 4.5 C1；(d) 部分：P22–P25（pulse width、duty） | C1 的 checker 已列為下一個專案做 | 不用動 | C1、A1 | phase3.md 158、169–177；signoff-criteria 經驗紀錄 258–259 |
| P3-30 | 2、3 | IR 0.29／0.306 mV 是把 PDN 所有 pin 當理想電源、用 OpenSTA 預設切換率算的，比任何門檻小幾百倍，當時沒人懷疑 | checker 模型太樂觀 | 分四個 Phase 才修完（retro #4） | 已驗證（Phase 4 研究） | (a) `pdn-ir-drop` 規則 10、`signoff-checker-qualification` 漏洞類型「被測的模型本身太樂觀」；(c) 流程文件 4.4 D2；(d) 現在的 `ir_worst.py`、`ir-soc`；登記表 I01 | 無 | 不用動 | D2 | phase2.md 92；phase3.md 55、165 |
| P3-31 | 2、3 | LibreLane 的彙總 metric 容易誤讀：`power__total` 是最後寫入的 corner（max_ff）；`clock__skew__worst_setup` 是各 corner 的最小值；skew metric 含 uncertainty 與 derate | 工具意外行為 | 文件寫錯，審查更正 | 已驗證（讀 LibreLane 原始碼） | (a) `librelane-run-debug` 規則 4、`cts-clock-tree` 規則 6、`phase-exit-review` 規則 3 | 無 | 不用動 | — | phase2.md 29；phase3.md 53 |
| P3-32 | 3 | Classic flow 不檢查金屬密度；實測 met1–met5 都低於下限 | 工具範圍 | 延到平台 fill | 已驗證 | (a) `drc-signoff`「金屬密度」一節；(c) 流程文件 4.6 D5；登記表 D14 | D5 的 checker 已列為下一個專案做 | 不用動 | D5 | phase3.md 164 |
| P3-33 | 3 | 最終 GDS 裡 macro 有沒有內容沒有自動 checker（「161 個 SRAM cell 都接得到」是一次性手動檢查），LVS 又把 SRAM 當 black box；Phase 6 SRAM 真的變空 | checker 缺口 | Phase 6 白跑一輪 harden | 已驗證 | (a) `hard-macro-integration` 清單第 0 項（`FOREIGN`）、第 10 項、`lvs-signoff` 規則 1；(c) 流程文件 4.3 第 2、6 項；(d) `check_soc.py macro_gds`（P67–P69） | 無 | 不用動 | B4 | phase3.md 21；retro_p0_3.md #9 |
| P3-34 | 3 | OpenSTA 對 instance 設的 derate 會取代 global derate，不是相乘：SRAM 的 ss × 1.5 實際上沒乘到 ±5% OCV | 工具意外行為 | Phase 4 改 1.575／0.665 | 已驗證（OpenSTA 原始碼） | (a) `signoff-criteria` 已驗證的工具行為 5、`timing-constraints-sdc` 規則 4；(d) P04 | 無 | 不用動 | — | ADR-0007 33–37；`d31b52b` |
| P3-35 | 3 | 廠商只給一份 TT 解析 .lib：padded.lib 同一份套到 FF（SRAM 輸出的 hold 偏樂觀）；instance derate 只在 STA step 生效，PnR 與 resizer 看不到 | 規格假設 | 已知限制，Phase 3.5 取代 | 已驗證 | (a) `drv-timing-closure` 規則 6、`multicorner-sta` 規則 4、`librelane-run-debug` 已知陷阱、`hard-macro-integration` view 表；登記表 S01、S02、T18 | 無 | 不用動 | — | ADR-0007 29–31、42 |
| P3-36 | 3 | signoff 條件調查 agent 的 22 項論述有部分錯誤（把 skew metric 當真值、`-clock_path` 的建議無效、hold 預設判 FAIL 的 corner 寫錯），由獨立核對 agent 實測推翻 | 人為（agent）錯誤 | 3 個調查加 3 個核對 agent | 已驗證 | (b) `signoff-criteria` 經驗紀錄 260；原則已在 CLAUDE.md 規則 3 與全域規則（重要結論交獨立 agent 反向驗證） | 已有上位規則 | 不用動 | — | signoff-criteria 經驗紀錄 260 |
| P3-37 | 3 | Makefile 沒有 `.NOTPARALLEL`，`make -j phase3` 會互相刪檔 | 流程 | 沒發生（審查指出） | 已驗證（讀程式） | (a) `flow-regression-reproducibility` 規則 1 | 無 | 不用動 | — | phase3.md 186 |
| P3-38 | 3、3.5 | `pkill -f <字串>` 誤殺：Phase 3 誤殺 eqyB；Phase 3.5 用 `pkill -f 'ngspice -b deck.sp'` 把另一個參考模擬一起砍掉 | 人為操作 | 各重跑一次 | 已驗證 | (a) `librelane-run-debug` 已知陷阱（兩列）、`flow-regression-reproducibility` 規則 10 | 無 | 不用動 | — | openram-macro-characterization 經驗紀錄 227 |
| P3-39 | 2、3 | LibreLane 執行的小陷阱：`cd` 進 LibreLane 後 `$PWD` 變了、找不到 config；list 參數經 nix-shell 引號會變形；Magic 讀 SRAM GDS 印 `[E] ... Unknown layer/datatype` 不會讓 flow 失敗；`deferred` 是延後報錯 | 工具使用 | 各 1 次試跑 | 已驗證 | (a) `librelane-run-debug` 規則 1、已知陷阱 | 無 | 不用動 | — | librelane-run-debug 經驗紀錄 78 |

### Phase 3.5：SRAM .lib 改用 SPICE 實測

| 編號 | Phase | 問題 | 類別 | 代價（估計） | 根因 | 目前捕捉在哪 | 缺口 | 建議寫回 | 重疊 | 出處 |
|---|---|---|---|---|---|---|---|---|---|---|
| P35-01 | 3.5 | PDK 預建 2 KB SRAM 在 ss −40°C、tt −40°C 1.60 V、ss 25°C 1.60 V 讀成前一次的值（sense amp 沒有預充電、column mux 只有 NMOS） | 規格／假設錯誤（macro 已驗證的範圍不涵蓋操作範圍） | 放寬：ss −40°C 用佔位 .lib，頭號下線風險帶過 3 個 Phase；特性化與整合做兩次（Phase 3.5 約 19 小時量的 macro 後來被換掉，retro 估） | 已驗證（量內部節點、完整網表對照） | (a) `openram-macro-characterization` 規則 13、`hard-macro-integration` 第 5、8 項；(c) 流程文件 4.1 A1、4.3 第 0 項；登記表 S09、S10 | B1 是選擇前的模擬，沒有自動防護，已知 | 不用動 | A1、B1 | ADR-0010 72–105；phase3_5.md 49–55 |
| P35-02 | 3.5 | 整理結果時把 ss 25°C 1.60 V（全部 bit 錯）和 ss 25°C 1.80 V（只有修剪的 bit 錯）混在一起，漏列室溫失敗，獨立審查重算波形才發現 | 人為錯誤 | 下線風險範圍一度低估 | 已驗證 | (a) `openram-macro-characterization` 規則 13（每一列寫完整的製程、溫度、電壓）；`phase-exit-review` 經驗紀錄 38 | 無 | 不用動 | — | phase3_5.md 179；ADR-0010 101 |
| P35-03 | 3.5 | SRAM 的 dout 在上升緣後約 1 ns 就被拉回，PDK .lib 與 padded.lib 只有下降緣那條弧，STA 從沒檢查讀出端的 hold | macro view 缺陷 | 新增 `rising_edge` hold 弧（連帶 P35-07） | 已驗證（波形） | (a) `openram-macro-characterization` 規則 7、12、`drv-timing-closure` 規則 6；(d) P32 | 無 | 不用動 | B1 | ADR-0010 27；openram-macro-characterization 經驗紀錄 221 |
| P35-04 | 3.5 | SRAM .lib 延遲表的負載斜率等於 60–140 kΩ 的 driver，`RepairDesignPostGPL` 跑 75 分鐘後 `failed with an unexpected error` | macro view 缺陷 | 一次 harden（75 分鐘）＋4 種 .lib 單步重跑；放寬：延遲表不隨負載變化（登記表 S11） | 已驗證（單步重跑） | (a) `openram-macro-characterization` 規則 14、`drv-timing-closure` 規則 10、`hard-macro-integration` 第 9 項；(c) 流程文件 4.3 第 2 項 B3 | B3 的 checker 已列為下一個專案做 | 不用動 | B3 | ADR-0010 147–161；`3e9b011` |
| P35-05 | 3.5 | OpenROAD 經 LibreLane 執行時 log 有緩衝，step log 74 分鐘沒更新、看起來像卡住 | 工具行為 | 判斷是否卡住多花時間 | 已驗證（`sample`） | (a) `librelane-run-debug` 已知陷阱（輸出緩衝、診斷是不是卡住兩列） | 無 | 不用動 | — | librelane-run-debug 經驗紀錄 81 |
| P35-06 | 3.5 | `run.sh` 重跑前 `rm -rf` 上一次的 run：harden 1 的 log 在 harden 2 開跑時被刪，harden 2 的報告被 harden 3 覆蓋，文件只能寫「數字來自當時的報告」 | 流程（證據保存） | 證據遺失 | 已驗證 | (a) `librelane-run-debug` 規則 6；(d) `keep_prev_run`、`test-flow-retry` 的情境 | 通用的「刪檔範圍」見 P0-02 | 不用動 | — | phase3_5.md 63–64、170、200 |
| P35-07 | 3.5 | 新的 hold 弧加上 resizer hold 餘量 0.3 ns，在每個 `rdata_q` 前插 delay cell；它也在 SRAM 半週期 setup 路徑上，min_ss_n40C −0.066 ns，週期 42 → 43 ns | 工具行為／設定互相衝突 | 放寬：週期 +1 ns（登記表 T02） | 已驗證（hold 報告）；「不插時 ff hold 仍 +0.18 ns」是推算 | (a) `drv-timing-closure` 規則 7、`cts-clock-tree` 規則 12、13；登記表 T02、T16、T19 | 週期沒回頭評估已在登記表 T03 列出 | 不用動 | D4（推測一部分）、A3、E1 | ADR-0004 17–23；drv-timing-closure 經驗紀錄 125 |
| P35-08 | 3.5 | ngspice 的速度與語法陷阱：完整網表光解析就 35 分鐘以上（`INP2M`）；`.tran 10p` 壓住最大步長（33 對 7 分鐘）；bus 節點 `bad v() syntax`；`meas ... FALL=1` 從 t=0 起算 | 工具行為 | 試跑階段各一次 | 已驗證 | (a) `openram-macro-characterization` 規則 4、5、6 與 description | 無 | 不用動 | — | openram-macro-characterization 經驗紀錄 219–220 |
| P35-09 | 3.5 | ss −40°C 診斷：6 個各約 25 分鐘的模擬全部在最後才報 `Error: no such vector xsram.xbank0.xport_data0.bl_0`，沒有波形（子電路的 port 節點要用上一層的網路名稱；`wrdata` 到模擬結束才檢查名稱） | 工具行為／操作 | 約 25 分鐘到 2.5 小時（估；沒記是否平行跑） | 已驗證 | (b) 只在 `openram-macro-characterization` 經驗紀錄 229 | 根因已用實驗確認，依 CLAUDE.md 規則 3 可升為規則；description 沒有 `no such vector` | 建議 8 | — | openram-macro-characterization 經驗紀錄 229；retro_p35_5.md #1 |
| P35-10 | 3.5 | Magic 沒設 `PDK_ROOT` 時找不到 tech 檔，仍 exit 0 且沒有輸出 | 工具缺陷（exit code 不可信） | 小 | 已驗證 | (a) `openram-macro-characterization` 規則 8；(c) 流程文件 4.3 第 1 項（不能只看 exit code） | 無 | 不用動 | — | openram-macro-characterization 經驗紀錄 222 |
| P35-11 | 3.5 | Magic 萃取的 SRAM 網表不能模擬（singular matrix；處理後仍 `Timestep too small`）；只換萃取 bitcell 後寫入失敗。Phase 6 查到是階層式輸出的負值修正電容，寫入失敗沒重現 | 工具缺陷 | Phase 3.5 未解，Phase 6 解 | Phase 3.5 未解；Phase 6 已驗證 | (a) `openram-macro-characterization` 規則 10；(d) `extract_sram.py` 負值電容檢查、`neg-char` N22 | 無 | 不用動 | B2 | ADR-0010 已知限制 3、4；openram-macro-characterization 經驗紀錄 225–226 |
| P35-12 | 3.5 | 走線寄生只用「換萃取 bitcell」的試驗定 × 1.6；dout0 transition 電路圖與萃取 bitcell 差 5 倍、無法判斷，維持 0.5 ns。Phase 6 整顆萃取是 2.0 倍、transition 實際 1.4–2.2 ns | 規格假設 | 放寬：登記表 S04、S07；Phase 7 wrapper setup 只剩 +0.151 ns（retro） | 已驗證（Phase 6） | (a) `openram-macro-characterization` 規則 10、29；(c) 流程文件 4.3 第 5 項 B2；登記表 S04、S07 | 無 | 不用動 | B2、E1 | phase3_5.md 41–47、73–83；ADR-0010 已知限制 2、5 |
| P35-13 | 3.5 | 其他 PVT 的搜尋以 tt 結果為中心，ss／ff 的真值在範圍外；舊做法每往外移一次就從頭二分，預估 ss 最小週期要近 20 小時 | 量測方法 | 避免約 20 小時（預估） | 已驗證（用假模擬器比對新舊版） | (a) `openram-macro-characterization` 規則 15 | 無 | 不用動 | — | openram-macro-characterization 經驗紀錄 233；`1a32e3c` |
| P35-14 | 3.5 | 特性化 negative test 的問題：N6 要替換的字串在新 .lib 裡已不存在，植入什麼都沒做；N7 抓到的原因不對；`gen_char_lib --check` 只比 `char.json` 裡有的 PVT，少一個 PVT 時舊 .lib 留著不會被發現 | checker 漏洞 | 各重寫一次 | 已驗證 | (a) `signoff-checker-qualification` 規則 7、漏洞類型「植入沒有生效」、`openram-macro-characterization` 規則 11、16；(d) N6–N8 | 無 | 不用動 | — | phase3_5.md 126–128 |
| P35-15 | 3.5 | P17 的植入程式 `open(f, "w").write(edit_once(open(f).read(), ...))` 先清空檔案再讀；改寫後沒先跑就開乾淨 checkout 的 regress，第 19 個 target（約 80 分鐘後）才 FAIL | 流程（改完沒先跑）／程式錯誤 | regress 1 不算數，多跑一輪 regress（136 分鐘） | 已驗證 | (a) `flow-regression-reproducibility` 規則 9、`phase-exit-review` 規則 2；(d) `make py-check`（含自我測試） | 無 | 不用動 | — | phase3_5.md 11、129；`6316ea9` |
| P35-16 | 3.5 | 收尾的獨立審查找到 12 個 checker 漏洞，9 個在特性化流程：`sram_lib` 只認一種 log 訊息、`char.json` 的 PVT 紀錄可對調、產生器公式沒有獨立驗證、來源欄位沒人查、NaN 被 `max()` 吞掉、替換次數只數總和、二分只在探到的點檢查單調、快取不確認 ngspice 成功、部分失敗留下新舊混合；延到 Phase 5 開頭修 | checker 漏洞 | Phase 5 開頭修，N9–N16、P33–P36 | 已驗證（審查做出壞輸入實測） | (a) `openram-macro-characterization` 規則 16、`signoff-checker-qualification` 漏洞類型表多列與規則 12；(c) 流程文件 4.8 E3；(d) `check_char_lib.py`、N9–N16、P33–P36 | 審查紀錄的 checker 已列為下一個專案做 | 不用動 | E3 | phase3_5.md 204–227 |
| P35-17 | 3.5 | 等長 regress 的腳本三次出錯：`pgrep -f` 比到自己的 shell、macOS `pgrep` 用反斜線加直線寫「或」其實是字面的直線、`regress: PASS` 比到 regress-rtl 那一行；背景指令 2 小時到期 | 人為／工具 | 提早結束或等不到 | 已驗證 | (a) `flow-regression-reproducibility` 規則 10 | 無 | 不用動 | — | flow-regression-reproducibility 經驗紀錄 84 |
| P35-18 | 3.5 | 攤平 .lib 的單步重跑 98 秒對 52 秒，原本歸因於 .lib，審查指出是同時跑的機器負載 | 量測方法（實驗互相干擾） | 結論一度寫錯 | 已驗證（審查） | (b) 只在 `openram-macro-characterization` 規則 14 的括號註記；`gate-level-simulation` 規則 6 只管牆鐘時限 | 「比較執行時間的實驗要單獨跑，或對照組同時跑」沒寫成通則 | 建議 15 | — | phase3_5.md 63、189；ADR-0010 159 |
| P35-19 | 3、3.5 | 文件引用的實驗輸出沒保存：Phase 3 的 GRT-0229 重現證據原本只在 session scratchpad（`3b08251` 才搬進 `docs/notes/`）；Phase 3.5 的 what-if 輸出、N5–N8 的 log 沒存，審查列為「找不到證據」後重跑 | 流程（證據保存） | 重跑 what-if 與 N5–N8（估 1 小時內） | 已驗證 | (e)：`librelane-run-debug` 規則 6 只管 run 目錄；`phase-exit-review` 規則 3 要求數字對得回證據，沒說證據要在什麼時候、存到哪裡 | 第 2 次發生（Phase 3、3.5）；`review_p4_5.md` 在 Phase 4、5 也找到同類 | 建議 5 | — | phase3_5.md 197–202；`3b08251` 訊息 |
| P35-20 | 3.5（Phase 6 再發生） | 特性化的條件沒涵蓋 SoC 實際的工作點，STA 外插也不警告：hold 弧只在 20 ns 週期量（10–16 ns 時比 .lib 早變化）；讀取失敗只在 20 ns 判定；最終版圖 dout0 最小負載 3.35 fF 低於特性化的 5 fF（`min_capacitance` 沿用 PDK 的 1.72 fF）；`max_capacitance` 從 0.02756 放寬到 0.05 pF 沒寫進文件（審查找到）。Phase 6 又遇到：萃取網表在 ss −40°C 用 20 ns 週期判 FAIL，改用 SoC 的 44 ns 才讀對 | 量測方法／規格假設 | 已知限制（登記表 S06、S12） | Phase 6 那次已驗證；最小負載的影響是推算 | (a) 部分：`openram-macro-characterization` 規則 10 最後一點（週期）、規則 14（`max_capacitance`）、「待補」列了 hold 弧和週期有關；登記表 S06、S12 | 「量測的週期、負載、slew 範圍要涵蓋 SoC 實際值」沒有一條通則；負載下限沒寫 | 建議 7 | — | ADR-0010 已知限制 11–13；phase3_5.md 152–154、186；openram-macro-characterization 規則 10 |
| P35-21 | 3.5 | 計畫假設 OpenRAM 只能在 x86 Linux（Colab 或 Lima）跑，所以 Phase 3.5 改用本機 ngspice；Phase 6 才發現 macOS 原生就能跑 | 規格／假設錯誤 | 影響小（本機 ngspice 反而避開 OpenRAM 特性化的缺陷） | 已驗證（Phase 6） | (a) `openram-macro-characterization` 規則 21、「開工前查證」的平台一點 | 無 | 不用動 | — | ADR-0010 11；ADR-0018 |
| P35-22 | 3.5 | OpenRAM 自己的 SPICE 特性化有方法缺陷：setup/hold 只量輸入 DFF、`cell_rise` 抄 `cell_fall`、`min_pulse_width` 取週期一半、預設沒有走線 RC | 工具缺陷 | 自寫特性化（代價：要用植入錯誤證明量得對） | 已驗證（讀原始碼） | (a) `openram-macro-characterization` 規則 3、9 | 無 | 不用動 | — | ADR-0010 16–22 |
| P35-23 | 3.5 | `neg-char` 的 N1–N4 要跑 ngspice（約 22 分鐘），不在 `make regress`；改特性化腳本要手動跑 | 流程限制 | 已知限制 | 已驗證 | (c) 流程文件 4.8「不在 regression 裡、要另外跑的」（293 行）；登記表 S21 | 無 | 不用動 | — | phase3_5.md 148 |
| P35-24 | 3.5 | 新的 `GRT-0243` 警告：antenna 修補時有一條 net 用 diode 修不掉；修補後與繞線後的檢查都是 0 個違規 | 工具警告 | 無 | 已驗證（golden README） | (e) 只在 golden README | 只出現一次、沒有影響 | 不用動 | — | phase3_5.md 149 |

---

## 和 ADR-0020（19 條提早檢查）重疊的項目

共 19 個：P0-04（C2）、P2-01（C2）、P2-02（C2，部分漏收）、P2-04（D4 後半，部分漏收）、P2-07（E2）、P3-01（D1）、P3-02（D1、E1）、P3-15（C2）、P3-29（C1、A1）、P3-30（D2）、P3-32（D5）、P3-33（B4）、P35-01（A1、B1）、P35-03（B1）、P35-04（B3）、P35-07（D4、A3、E1）、P35-11（B2）、P35-12（B2、E1）、P35-16（E3）。另外 P1-01 是 E3 的正面例子：Phase 1 在 checker 寫完時就做了兩輪獨立審查（不計入 19）。

核對結果：
- 這 19 個的「做太晚」都已寫進流程文件第 4 節與對應 skill，能做成 checker 的都標了「下一個專案開始時做成 checker」。不重複建議。
- **P2-02**：retro_p0_3.md 的 E5 有三點，(b)「比對繞線前估計與繞線後萃取的線電容」在合併成 C2 時沒有保留（`flow_retro/README.md` 41 行、流程文件 4.0 的 159–162 行只有 DRV 原因與弱 cell）。見建議 6。
- **P2-04**：「flow 變數關不掉時查底層工具選項」（D4 後半）的第一次其實在 Phase 2（dummy load），規則 13 只寫了 Phase 4 那次。見建議 12。
- retro P03 的 E10（RTL code coverage、EQY RTL 對合成網表試跑）被列為「優先度較低、留在報告裡」，沒進 19 條；P2-12、P3-16 是它的來源。見建議 16（交使用者決定要不要收）。

---

## 建議寫回（依重要性排序）

依 CLAUDE.md 規則 13，下面每一項都是提案，改不改由使用者決定。規則 3：只有已發生兩次以上或根因已用實驗確認的才寫進規則本文；其餘寫經驗紀錄。

1. **延後處理的待辦要收進下一步一定會讀的地方；latch-up 標記 81/14 先查證**（P3-10、P2-14）
   - 目標與內容：
     - `phase-exit-review` 規則 1 補一句：「帶到下一階段的項目」除了 exit review 的已知限制，也要掃本階段新增或修改的 `docs/notes/` 筆記中「Phase N 才能處理」「之後確認」這類句子，收進 exit review 的已知限制或登記表。
     - `drc-signoff` 規則 7 第 3 點（「否則 6 µm 規則會大面積違規（推論）」）在查證前移到經驗紀錄，規則本文只留已驗證的兩點。
     - 登記表加一列「81/14 標記沒確認」，狀態「待查」。
     - 查證本身（交付的 KLayout GDS 有沒有 81/14、flow 的 Magic DRC 是在哪一份 GDS 上查 LU 規則）會影響下線判定，屬於規則 13 的分岔：先查清楚，結果與處理方式由使用者決定。
   - 理由：延後的事情第 2 次差點或已經漏掉（Phase 2 → 3 的來源追溯靠收尾對照才補上；這一次在筆記裡，到 Phase 7 結案都沒人看到）。任何多 Phase 的專案都會有「先記著、之後處理」，只寫在筆記就會掉。

2. **Phase 3 收尾查到的 LibreLane 設定靜默無效，補齊 CLAUDE.md 規則 10 的防護**（P3-11）
   - 目標與內容：`drc-signoff` 規則 5、`antenna-signoff` 規則 10、`cts-clock-tree` 規則 8、`timing-constraints-sdc` 規則 2 各補「怎麼發現」（例：`resolved.json` 裡該變數是 None、sta.log 的 `Reading design constraints file at` 讀的是哪份、deck 原文的變數名）與「防復發」。`SIGNOFF_SDC_FILE` 的那一條可以做成 checker：`check_inputs.py` 加一列「設了 `PNR_SDC_FILE` 就必須設 `SIGNOFF_SDC_FILE`」加一個植入錯誤；另外三條寫明「沒有自動防護，LibreLane 升版時逐條對照原始碼」。三個 description 加上變數名。
   - 理由：同一版 LibreLane 的新專案一定會再遇到；規則 10 是 10-07 才建立的，Phase 3 的工具缺陷沒有回頭補齊。

3. **RTL testbench qualification 的兩種漏洞寫成通用經驗**（P1-01、P1-02）
   - 目標與內容：`signoff-checker-qualification` 漏洞類型表加兩列：
     - 「測試被縮水或跳過仍判 PASS」：每支測試宣告它要做的動作並由 checker 計數（例如 SRAM 每個 word 的讀寫次數、UART stall 次數、cycle 下限）；精確計數換 core 要重量（`core-migration-hazard3` 規則 10）。
     - 「只比最終結果，中間的介面錯誤互相掩蓋」：macro 與周邊的腳位層協定 monitor（每筆交易只存取一次、handshake 時序、reset 值）。例：UART 除數 reset 值錯，Boot ROM 又寫一次所以輸出正常。
     - 流程文件 4.2 的 PASS 條件加一句：RTL testbench 也要做獨立的植入錯誤審查。
   - 理由：Phase 1 兩輪各漏掉 43–50%（10/20、10/23），已用植入錯誤確認。對策目前只在本 repo 的 `dv/README.md`，換專案不會被讀到。

4. **偏離計畫時寫明失去的保護**（P1-03）
   - 目標與內容：`phase-exit-review` 規則 4 的「與計畫不同的地方」每一項加兩點：原本那一項保護什麼、現在由誰保護；沒有替代的列成已知限制並登記到登記表。
   - 理由：Phase 1（R02 改測試後 memtest 上半部沒人保護）、Phase 3（P07、P12 改成只測 checker、EQY 範圍縮小）兩次。改檢查方式本身不是放寬，所以目前登記表不會收到它。

5. **實驗證據在做的當下存進 repo**（P35-19；P35-06 是同類）
   - 目標與內容：`phase-exit-review` 規則 3 補一句（或流程文件 4.9）：文件要引用的實驗輸出（單步重跑、what-if、negative test 的 log）做的當下就存到 `runs/<實驗名>/`（大檔、不進版控）或 `docs/notes/<主題>/`（小檔、進版控）；session scratchpad 會消失，`run.sh` 會覆蓋同 tag 的 run。
   - 理由：Phase 3、3.5 各一次，另一份審查（`review_p4_5.md`）在 Phase 4、5 也找到同類。

6. **補回「繞線前寄生估計」的 QA，並補 `LAYERS_RC` 的防護**（P2-02）
   - 目標與內容：`drv-timing-closure` 規則 14 與流程文件 4.0 的 C2 加回 retro E5(b)：在參考設計上比較繞線前估計與繞線後萃取的每層線電容，差超過約定比例就查（比例由使用者決定）。規則 2.2 補「防復發」：`check_inputs.py` 確認 `LAYERS_RC` 有設，或寫明「沒有自動防護，靠 golden 與這項 QA」。
   - 理由：Phase 2 的 9 輪試跑裡，這個根因最難找（估計值只差在 flow 原始碼的一行註解）。換 PDK 或 LibreLane 版本時，同類問題只有這種比較抓得到。

7. **特性化的條件要涵蓋 SoC 實際的工作點**（P35-20）
   - 目標與內容：`openram-macro-characterization` 加一條規則（或擴充規則 13、14）：量測用的週期、輸出負載、input slew 範圍要涵蓋 SoC 實際值（從 STA 報告取最小、最大負載與 slew，週期用 SoC 的 signoff 週期）；`.lib` 的 `min_capacitance`／`max_capacitance` 設成特性化的範圍；超出範圍時 STA 外插、不警告。
   - 理由：Phase 3.5 有三項已知限制屬於這類（hold 弧和週期有關、最小負載低於範圍、讀取失敗只在 20 ns 判定），Phase 6 又因為用 20 ns 週期判讀取而得到假的 FAIL；已發生兩次。

8. **ngspice 探測節點名稱的陷阱升為規則**（P35-09）
   - 目標與內容：`openram-macro-characterization` 規則 6 加第三個陷阱：子電路的 port 節點要用上一層的網路名稱，`wrdata` 到模擬結束才檢查名稱；長模擬前先用同一份 deck 跑 1 ns 確認每個探測節點存在。description 加 `no such vector`。
   - 理由：根因已用實驗確認（符合規則 3）；一次浪費 6 個各約 25 分鐘的模擬，任何用 ngspice 量 macro 內部節點的專案都會遇到。

9. **會刪檔的 target 只刪自己的產出**（P0-02、P35-06）
   - 目標與內容：`flow-regression-reproducibility` 已知陷阱加一列：`make clean` 刪了進行中的 `runs/flow_setup/`、`run.sh` 重跑刪了上一次失敗的 run；對策是刪檔範圍限自己的產出、重跑先搬走（`keep_prev_run`）。
   - 理由：兩次，形式不同但同一類，每次都失去要用的東西。

10. **LibreLane 內建 checker 沒設門檻就略過**（P3-12）
    - 目標與內容：先在現有 run 的 log 確認 `Checker.WireLength` 略過時的原文訊息，寫進 `signoff-criteria` 經驗紀錄；確認後在「已驗證的工具行為」加一條，並考慮讓 criteria review 第一部分列出這次被略過的 `Checker.*` step。
    - 理由：和 P2-06（預設只判 tt）同一類「內建判定靜默不做」，新設計沒有逐一設門檻就會以為有檢查。根因目前只有 phase3.md 的一句陳述，所以先寫經驗紀錄。

11. **只改報告的植入要標明**（P3-22）
    - 目標與內容：`signoff-checker-qualification` 規則 7 加一點：植入點優先放在產生資料的源頭（版圖、網表、設定）；只改報告或 metrics 的案例標明「只測 checker 本身」，在 exit review 的總表分開計數。
    - 理由：Phase 3 有 3 個案例屬於這種（P07、P12、P15），總表把它們和真的從版圖植入的案例算在一起，看起來涵蓋得比實際多。

12. **`cts-clock-tree` 規則 13 補上 dummy load 的例子**（P2-04）
    - 目標與內容：規則 13 的「為什麼」加 Phase 2 的例子；經驗紀錄記「OpenROAD 有 `-dont_use_dummy_load`，LibreLane 3.0.14 沒有對應變數，當時接受限制，沒有試 plugin」（選項是否存在，寫入前先讀 OpenROAD 原始碼確認）。
    - 理由：讓「flow 變數關不掉就接受限制」這個模式有兩個例子，下一次比較容易認出來。

13. **`rtl-synthesis-lint` 規則 1 補 config 條件區塊**（P2-08）
    - 內容：「LibreLane config 的 `pdk::`／`scl::` 條件區塊會依 PDK 換參數，參數一致的 checker 遇到就 FAIL」（Phase 2 獨立審查的案例已驗證）。
    - 理由：規則 1 已寫 defparam 與 SYNTHESIS，這是同一個 checker 的第三種漏洞，換 PDK 的專案會碰到。

14. **流程文件 4.0：參考設計要釘到工具版本自己 CI 用的那一版**（P0-03）
    - 內容：例如 LibreLane 的 `test/designs` submodule 指向的 commit。
    - 理由：成本極低，換工具版本時就不會拿錯參考。

15. **比較執行時間的實驗要單獨跑**（P35-18）
    - 目標與內容：`librelane-run-debug` 規則 3 加一點：要比較不同輸入的執行時間時，各自單獨跑，或把所有對照組同時跑；只有部分同時跑時，時間差可能是機器負載。
    - 理由：根因已由審查確認；單步重跑比時間是本 repo 找 resizer 問題的主要手段，負載干擾會讓結論錯。

16. **（交使用者決定）RTL code coverage 與 EQY 範圍試跑**（P2-12、P3-16；retro P03 E10）
    - 目標與內容：流程文件 4.2 加選做項目：RTL regression 量 line、toggle、FSM coverage（Verilator 的 coverage 功能），沒用到的功能補 directed 測試或寫原因；計畫 formal 範圍前，先拿一個區塊試 EQY RTL 對合成網表。
    - 理由：Phase 2 的 3 個 gate-level 漏網錯誤、Phase 3 的 EQY 範圍縮小，到 Phase 7 都只靠事後補。ADR-0020 把它列為優先度較低、沒收進 19 條，所以要不要收是使用者的決定。

---

## 附：方法與限制

- 只讀檔案與 git，沒有跑任何 EDA 工具或 make，沒有修改本文件以外的檔案。
- 時間從 commit 時間與 exit review 的紀錄推算，只能看量級；commit 是工作做完才建立，中間有夜間與平行工作。
- 「捕捉狀態」以 skill 與流程文件為準。本 repo 程式裡已有防護、但 skill 與流程沒寫的（P1-01、P1-02），算「都沒有」，因為下一個專案讀不到。
- 標「推測」「推算」「估」的不是量測結果，主要有：P3-10 的 latch-up 影響與 Magic DRC 讀哪份 GDS、P3-13 的 GRT-0229 機制、P3-15 是否與 Phase 5 同一機制、P35-07 的 delay cell 是否部分來自 CTS 對齊、各項時間。
