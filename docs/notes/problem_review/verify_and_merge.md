# 四份問題回顧的反向驗證與合併建議清單（2026-10-15）

起因：使用者 2026-10-15：「review一下所有遇到的問題與檢討哪些是要寫進skill與流程裡的」。同目錄有四份審查報告（`review_p0_35.md`、`review_p4_5.md`、`review_p6_7.md`、`review_skills.md`）。本文件由沒參與實作、也沒參與那四份審查的 agent 寫，目的有三個：
1. 核對每一條「建議寫回」的事實根據。
2. 把四份報告去重，合併成一張表。
3. 列出報告裡錯誤或誇大的地方。

**做法**：
- 只讀 repo（HEAD `0d47a3d`）與 `git log`／`git show`，沒有跑 make、LibreLane 或 regress。除了本檔，沒有改任何檔案。
- 唯一的實驗：用 KLayout 無頭模式（`klayout -z`）列出最終 GDS 的層。腳本在 session scratchpad 的 `layers.py`，結果見第 2.2 節。
- 驗證分工：
  - 三份依 Phase 分段的報告，各交給一個 fork agent 逐條核對。fork agent 繼承本 session 的 context，同樣只讀。
  - `review_skills.md` 與下面三個重點，由本文件作者自己查。
  - Claude Code 的 skill 清單規則另請一個 agent 查官方文件。
- 行號以 `0d47a3d` 為準，簡寫成「檔名:行號」。`runs/` 不進版控。

判定代號：
- **CONFIRMED**：屬實。
- **PARTLY**：部分屬實，寫出哪裡不對。
- **REFUTED**：不屬實。

---

## 0. 結論

1. **四份報告的建議沒有一條不屬實（REFUTED 0 條）。** 不過約四分之一的建議有次數多算、漏看既有防護或範圍說太滿的情形。

   | 報告 | 建議數 | CONFIRMED | PARTLY | REFUTED |
   |---|---|---|---|---|
   | `review_p0_35.md` | 16 | 13 | 3（6、14、15） | 0 |
   | `review_p4_5.md` | 11 | 9 | 2（R1、R2） | 0 |
   | `review_p6_7.md` | 16 | 12 | 4（1、4、6、12） | 0 |
   | `review_skills.md` | 15 | 11 | 4（1、4、7、9） | 0 |
   | **合計** | **58** | **45** | **13** | **0** |

2. **三個重點**：
   - **skill 清單**：
     - 屬實：在本 session 收到的清單裡，`pdn-ir-drop`、`signoff-checker-qualification`、`signoff-criteria`、`tapeout-precheck-caravel`、`timing-constraints-sdc` 這 5 個只有名稱、沒有 description；`hard-macro-integration`、`openram-macro-characterization` 被截斷。
     - 但原因和報告推測的不同。Claude Code 官方文件寫明兩個上限：
       - 單份上限 1,536 字元（`skillListingMaxDescChars`）。兩份被截斷的都剛好停在第 1,535 字元，不是報告說的「約 1,000 字」。
       - 總預算是 context window 的 1%（`skillListingBudgetFraction`）。超過時，**最少被呼叫的 skill 先拿掉 description**，不是報告推測的「照字母順序」。
     - 因此有 3 份（tapeout 2,088、openram 2,729、hard-macro 1,715 字元）不論預算多少都一定被截斷。其餘哪幾份會消失，取決於這台機器上全域 skill 的數量與呼叫紀錄，換機器、換人就不同。
   - **latch-up 標記 81/14**：
     - 屬實，而且比報告說的嚴重。`soc_top.gds` 與 `user_project_wrapper.gds` 兩份交付 GDS 都是 KLayout 寫的，**都沒有 81/14 這一層**；同一 run 的 Magic GDS 有（實測見 2.2）。
     - 更重要的是，**整條 flow 沒有任何一個檢查會查「沒標記區域的 6 µm tap 規則」**：
       - Magic 的 tech 檔只實作 15 µm 的 LU.2／LU.3。
       - PDK 與 precheck 的 KLayout deck 都只是宣告了 `areaid_ld = polygons(81, 14)`，沒有規則用到它。
       - precheck 的 `magic_drc` 預設不跑。
     - 這是不是下線風險要看兩件事：整合方組 Caravel 全晶片 GDS 時會不會補標記；SkyWater 端的 DRC 會不會查 6 µm 規則。兩件都查不到原文，屬推測。依 `CLAUDE.md` 規則 13，要交使用者決定。
   - **regression 沒有逾時、開跑前不查磁碟**：屬實。
     - `scripts/regress.py:118` 的 `subprocess.run` 沒有 `timeout`。
     - `env/check_env.sh` 全檔只檢查 precheck VM 的記憶體（:115–125），不查本機磁碟與記憶體。
     - 唯一的機器資源防護是 `.claude/guard.json`（全域 hook，只在這台機器），而且它只在下指令那一刻數程序。
3. **合併後共 27 項**：A 群 7 項、B 群 12 項、C 群 8 項（第 3 節）。最重要的 6 項：
   - A1：description 縮短，加長度 checker。
   - A2：81/14 與 6 µm 規則的下線風險，交使用者決定。
   - B1：regression 的資源、逾時與磁碟。
   - A3：`floorplan-congestion` 沒有指向 pad／block／pin 核准流程。
   - A4：和後來的決定矛盾的規則。
   - A5：流程文件缺新專案必要的步驟。

---

## 1. 每條建議的驗證結果

### 1.1 `review_p0_35.md`（16 項）

| # | 主題 | 判定 | 依據與修正 |
|---|---|---|---|
| 1 | 延後的待辦收進下一步會讀的地方；81/14 先查證 | CONFIRMED | `drc-signoff/SKILL.md:46` 把「否則 6 µm 規則會大面積違規」以「（推論）」寫在規則本文；`docs/notes/signoff_criteria_soc_top.md:41`、`:118` 寫「Phase 7 確認」；`docs/phase_exit/`、`docs/decisions/`、`docs/relaxation_register.md` 都沒有 `81/14`。**報告漏看**：`signoff-criteria/SKILL.md:184–186` 本來就要求每次 signoff 逐條寫出「不分析的項目」，其中有 chip-level latch-up marker，但 `phase7.md` 沒有提 latch，各 `criteria_review.md` 也沒有。所以這不只是「只寫在筆記」，而是規則本文要求了、Phase 7 沒照做。實測結果見 2.2 |
| 2 | Phase 3 查到的 4 個設定靜默無效，補齊規則 10 的四項防護 | CONFIRMED | `drc-signoff:35`、`antenna-signoff:21`、`cts-clock-tree:19`、`timing-constraints-sdc:13` 都只寫了現象；`review_criteria.py:470–475` 只印 INFO；全 repo 沒有「設了 `PNR_SDC_FILE` 就要設 `SIGNOFF_SDC_FILE`」的 checker |
| 3 | RTL testbench 的兩種漏洞寫成通用經驗 | CONFIRMED（小修正） | `phase1.md:22–23` 兩輪各漏 10/20、10/23；`signoff-checker-qualification:79–133` 的漏洞類型表沒有這兩類。修正：漏掉的 10 個裡有幾個是測試被縮水（memtest 刪掉 March C−），不全是介面或順序錯誤；流程文件 1.2（:49）把 `dv/scripts/dvlib.py` 列為「可直接沿用」，程式會被帶走，缺的是「為什麼這樣做」的通則 |
| 4 | 偏離計畫時，寫明原本保護什麼、現在由誰保護 | CONFIRMED | `phase-exit-review` 規則 4（:18）只列章節名稱；`phase1.md:43`、`phase3.md:138–153` 兩次都屬實 |
| 5 | 實驗證據當下存進 repo | CONFIRMED | `3b08251` 的 commit 訊息（從 scratchpad 搬回 `docs/notes`）；`phase3_5.md:197–200`；`librelane-run-debug` 規則 6（:35）只管 run 目錄 |
| 6 | 補回「繞線前寄生估計」的 QA 與 `LAYERS_RC` 防護 | PARTLY | `retro_p0_3.md:80` 的 E5(b) 確實沒進 C2（`flow_retro/README.md:41`）。但「沒有 checker 確認 `LAYERS_RC` 有設」說得太滿：`pnr/soc_top/ir_worst.py:131–133` 在 `LAYERS_RC` 缺 ss／ff 項時會 FAIL，是 soc_top 的間接防護，只是不通用 |
| 7 | 特性化條件要涵蓋 SoC 的實際工作點 | CONFIRMED | `ADR-0010:140`（3.35 fF 低於 5 fF）、`:186–188`；`openram:59`（20 ns 判 FAIL、44 ns 才讀對） |
| 8 | ngspice `no such vector` 升為規則 | CONFIRMED | 只在 `openram-macro-characterization` 經驗紀錄 :229；description 沒有 |
| 9 | 會刪檔的 target 只刪自己的產出 | CONFIRMED，價值低 | 兩次事件都已修好（`Makefile:481–482`、`env/setup.md:71`、`keep_prev_run`） |
| 10 | LibreLane 內建 checker 沒設門檻就略過 | CONFIRMED，而且比報告更確定 | fork 實際讀到 `runs/user_project_wrapper.prev/flow.log:7919`：「Threshold for Threshold-surpassing long wires is not set. The checker will be skipped.」。Phase 7 仍被略過，根因已由 log 確認，不只是 `phase3.md` 的一句陳述 |
| 11 | 只改報告的植入案例要標明 | CONFIRMED，理由誇大 | 規則 7 確實沒寫；但 `phase3.md:166` 已知限制 7 已揭露 P07、P12、P15 只測 checker 本身，「看起來涵蓋得比實際多」說過頭 |
| 12 | `cts-clock-tree` 規則 13 補 dummy load 的例子 | CONFIRMED | `phase2.md:97`；skill 裡搜 `dummy_load` 是 0 次。`-dont_use_dummy_load` 這個 flag 名稱在 OpenROAD binary 裡沒有直接找到字面字串，寫入前要讀原始碼 |
| 13 | `rtl-synthesis-lint` 規則 1 補 config 的 `pdk::` 條件區塊 | CONFIRMED | `cpu_params.py:14`、`:91` 已判；規則 1（:12）沒寫 |
| 14 | 參考設計釘到工具 CI 用的那一版 | PARTLY，價值低 | `toolchain.md:61` 已寫明，流程文件 :52、:157 指向它；報告判「(e) 都沒有」不對 |
| 15 | 比較執行時間的實驗要單獨跑 | PARTLY | `ADR-0010:159` 原文是「應是機器負載」：只發生一次，也沒有單獨重跑的實驗。依 `CLAUDE.md` 規則 3 只能寫經驗紀錄，不能寫進規則本文 |
| 16 | RTL code coverage 與 EQY 範圍試跑（交使用者決定） | CONFIRMED | `flow_retro/README.md:53`、`retro_p0_3.md:85` |

### 1.2 `review_p4_5.md`（R1–R11）

| # | 主題 | 判定 | 依據與修正 |
|---|---|---|---|
| R1 | 長 run 與平行 run 的資源預算 | PARTLY | 規則本文確實沒有資源預算；`check_env.sh` 只在 :124 查 VM。「至少 6 次」核對後是**已驗證 5 次＋推測 1 次**（KLayout sig11，`tapeout-precheck-caravel:114` 原文標推測）。P5-14 列的「結案兩輪依序跑」是預防措施，不是事件。另外 `flow-regression-reproducibility:48`（規則 9）已有「同時跑會互相拖慢、逾時要單獨重跑」一句，報告漏看 |
| R2 | resizer（或任何 step）失控時自動停 | PARTLY | 4 次發生屬實（`librelane-run-debug:79`、`ADR-0010:149`、`:55`、`phase5.md:119`），正式 harden 沒有時間或記憶體上限也屬實。但「4 次都是人看到才停」不對：Phase 3.5 那次是工具 75 分鐘後自己異常結束，根因也不同（.lib 斜率）。另外 `librelane-run-debug:54` 已有「超過 10 分鐘就停」的人工判準 |
| R3 | 證據存在版控內或主目錄 | CONFIRMED | `phase4.md:84`、`:99`；`phase5.md:35`、`:119`；`ADR-0013:58`；`ADR-0018:97`；`chip-floorplan-pin-planning:23` |
| R4 | harden 包裝腳本在 flow FAIL 時也要跑 checker | CONFIRMED，引證有誤 | 流程文件 :256、:260 只要求 criteria review 在 PASS／FAIL 都做；1.5（:70）沒寫這項。本 repo 已修（`pnr/soc_top/run.sh:33`、`:93–99`）。但報告把 P43–P49、`test-review-hook` 當成這件事的 negative test 不對：它們測的是 criteria review 與 Stop hook，**沒有任何測試斷言 flow 結束碼不為 0 時 `check_signoff`／`check_soc` 照跑** |
| R5 | 版圖相關計數不要只比總數 | CONFIRMED | 上限檔寫死總數：`signoff/limits/soc_top.toml:41`=144、`picorv32_core.toml:36`=114、`user_project_wrapper.toml:59`=667；FAIL 歷史見 `phase4.md:100`、`phase5.md:123`、`:127` |
| R6 | 共用 flow 設定改了，每個變體都要重 harden | CONFIRMED | `core-migration-hazard3` 規則 22（:76–80）沒有；只在經驗紀錄 :111 與 `flow-regression:93` |
| R7 | EM checker 列為下一個專案做 | CONFIRMED（小修正） | repo 沒有 `-enable_em`；登記表 I12。但 `signoff-criteria:99`（規則 14）已寫明沒有工具比對。報告漏了更嚴重的一處：流程文件 :280 寫「power signoff（IR、EM、功耗）一律用 pattern」，讀起來像 EM 有在判 |
| R8 | 不在 regression 的 checker，收尾時確認最後在哪裡跑 | CONFIRMED | `phase5.md:177`、`:294`；登記表 S21 |
| R9 | `make py-check` 的範圍寫清楚 | CONFIRMED | `flow-regression` 規則 9（:46）沒列「跨模組 import 改名」；只在 `scripts/check_py_names.py:14–15` docstring |
| R10 | `neg_char` 平行案例的 race 補經驗紀錄 | CONFIRMED | 只在 `2251c4a` 的 commit 訊息 |
| R11 | 過期文字（`librelane-run-debug` 規則 5、pdn「待補」、core-migration「待補」） | CONFIRMED | `librelane-run-debug:32` 仍寫「只針對那一個訊息」「10 種情境」。`pnr/test_librelane_flow.sh` 有 14 個重試情境（:76–89），另有 1 個 `keep_prev_run` 檢查（:91–98）；本報告寫 15、`review_skills` 寫 14，差在有沒有算後者。第三節第 4 項的過期註解，除了 `config_hazard3.json:188`，`pnr/soc_top/config.json:162` 也有同一段，報告漏列 |

### 1.3 `review_p6_7.md`（16 項）

| # | 主題 | 判定 | 依據與修正 |
|---|---|---|---|
| 1 | regression 開跑前的資源檢查與卡住偵測 | PARTLY | 三次都有出處：`flow-regression:89`（10-07）、`:94`（10-10）、`:98`（10-15）。但 10-07 那次是單一 harden 被使用者另一個程式佔掉 17 GB，不是 regression 平行跑。「skill 規則與流程都沒有」說太滿（`flow-regression:48`、流程文件 1.4 第 65 行的 guard hook）。逾時與磁碟的部分本文件親自確認（2.3） |
| 2 | 「之後再處理」的決定當下寫進待辦 | CONFIRMED | `ADR-0018:91`、`:99`；`runs/p7_review/doc_check.md:31–32`。其中「`make openram-macro` 改過後沒有從頭跑過」仍是推測：主目錄 `runs/openram` 最新 log 是 10-10／10-11，worktree 沒有逐一翻 |
| 3 | 變數重名：補第三例，範圍擴大到模組層 | CONFIRMED | `git show cbf2c5e`（模組層 `for x, y, size, _ in pts` 蓋掉 SRAM 原點）；`signoff-checker-qualification:71–76` 規則 13 只寫「同一個函式」 |
| 4 | 決定改了，同一個 commit 標註被取代的前文 | PARTLY | Phase 6（`phase6.md:225–233`）與 Phase 7（`doc_check.md:7–12`）屬實；Phase 5 那 17 項（`phase5.md:311–314`）是判定說法不誠實、限制沒延續，不是同一類。實際是兩次，不是三次 |
| 5 | 引用的數字，證據先另存 | CONFIRMED | `doc_check.md:30`、`:46–53`；`ADR-0018:97`；`chip-floorplan-pin-planning:23`、`:67` |
| 6 | GDS 的 sha256 因日期不同 | PARTLY | 三次屬實（`openram_phase6_bringup.md:90`、`flow-regression:96`、`caravel_precheck_phase7.md:157`）。但「checker 要綁這一次的 sha1」已有自動防護（`check_precheck.py:14–24`、`neg_precheck.py:262` 的 `stale_results`），「GDS 用 XOR 比」已寫在 `openram-macro-characterization:113` 的規則本文。缺的只是 `flow-regression` 的規則文字 |
| 7 | Caravel fill 與金屬密度下限寫進「待確認」 | CONFIRMED | `tapeout-precheck-caravel:67` 規則 9 指向「待確認」，但「待確認」（:82–90）沒有 fill 這條，引用懸空；`drc-signoff:54–56` 沒提平台會補 fill |
| 8 | checker 要分得出「工具當掉」與「結果不對」 | CONFIRMED | `signoff/precheck/` 搜不到 `Signal number`／`Segmentation`／`Killed`；`runs/p7close2_h3_neg_precheck_ref_klayout_sig11.log` 存在 |
| 9 | 輸入腳位的 transition 要確認生效 | CONFIRMED | `timing-constraints-sdc:39` 規則 14 原文「低於上限的…沒有自動防護」 |
| 10 | 不在 regression 的 negative test 要對得回 checker 版本 | CONFIRMED（次數低估） | `openram_phase6_bringup.md:270`；Phase 5 N9–N16 是同一類（`review_p4_5` P5-29），合計兩次 |
| 11 | 流程文件 4.3 第 5 項補「新量法先在修剪網表跑完」 | CONFIRMED | `openram` 規則 27（:165）存在，流程文件 :210 沒指過去 |
| 12 | 換 macro 檢查單加「negative test 寫死的舊座標」 | PARTLY | `phase6.md:97`、`:173` 屬實；但 `hard-macro-integration` 規則 10（:63–67）已要求 positive run 印出 macro instance，新增的只是小補充。「同類兩次」的歸類偏寬 |
| 13 | 讀 harden run 的腳本都要過 run guard（自動檢查） | CONFIRMED | `signoff/scripts/neg_run_guard.py:36` 的 `STEPS` 是手寫清單（報告沒寫路徑，不在 `scripts/`） |
| 14 | Caravel 範本固定的 `PDN-0239`／`GRT-0036` 寫成規則 | CONFIRMED | 只在 `tapeout-precheck-caravel` 經驗紀錄 :104、:107 |
| 15 | CVC 的 HI-Z 警告只允許 black box 的輸出 | CONFIRMED | `tapeout-precheck-caravel:38`「沒有自動防護」；`check_precheck.py` 搜不到 `cvc` |
| 16 | （可選）長段工作前一次取得授權 | CONFIRMED | `ADR-0018:84–88` 決定 16 |

### 1.4 `review_skills.md`（15 項，第 6 節）

| # | 主題 | 判定 | 依據與修正 |
|---|---|---|---|
| 1 | description 縮短；`check_skills.py` 加長度上限 | PARTLY（現象屬實，機制推測錯） | 見 2.1。補充：`scripts/check_skills.py`（:6–20、:65–67）確實只查格式與存在，不查長度 |
| 2 | flow-regression 新增「資源與長時間工作」；逾時、磁碟、worktree 清理 | CONFIRMED | 見 2.3。`git worktree list` 本次量到 14 列（含主目錄，所以 13 個舊 worktree 屬實）；`runs/` 的 386 GB／176 GB 本文件沒有重量 |
| 3 | `floorplan-congestion` 規則 2、3 指向 pad／block／pin 規劃與核准 | CONFIRMED | `floorplan-congestion/SKILL.md` 搜 `chip-floorplan-pin-planning`、`pin_plan` 是 0 次；`規則 14` 唯一一次（:25）是指 `pdn-ir-drop` 規則 14，不是 `CLAUDE.md` 規則 14 |
| 4 | 9 條規則和後來的決定矛盾或過時 | PARTLY | 逐條見下 |
| 5 | `tapeout-precheck-caravel` 補「讀到舊報表」的四項防護等 | CONFIRMED | skill 搜 `stale`／`舊報表`／`讀到前一次` 是 0 次，`neg_precheck.py:22`、`:262` 有 `stale_results`；`:32` 規則 3 仍寫「並向 ChipFoundry 反映」 |
| 6 | 流程文件 F1–F7、G1–G12 | CONFIRMED（抽查） | F1：:207 仍寫「D1–D7」；F2：:248 把 0.6 ns 歸到 `multicorner-sta` 規則 3，但 0.6 ns 在 `drv-timing-closure` 規則 9（:29）；G1：流程文件搜 `VIOLATION_CORNERS` 0 次；G2：搜 `positive control` 0 次；G9：搜 `CVC`／`EXTRACT_ABSTRACT` 0 次 |
| 7 | R5–R24 升為規則 | PARTLY | 抽查：`RSZ-0064` 在 `drv-timing-closure` 只出現在經驗紀錄（:127、:128、:136），規則本文與 description 都沒有，屬實。R4（GDS sha256）的 XOR 部分已在 `openram:113` 規則本文。R11 與 `review_p0_35` 建議 8 是同一件事 |
| 8 | 「升版時要重看的綁定」清單；`TIMING_STEPS` 加未列入 step 就 FAIL | CONFIRMED | `review_criteria.py:72–74` 寫死 8 個 step ID；:325、:346 只對清單內缺少的 step 報「(no step)」，清單外新增的時序 step 不會被注意 |
| 9 | 2.2 表各缺項（`FALL=1`、`DRT_ANTENNA_REPAIR_MARGIN`、`SIGNOFF_SDC_FILE`、`LAYERS_RC`／`clkdlybuf4s*`／heuristic diode 進 `check_inputs.py`、`RT_CLOCK_MIN_LAYER`） | PARTLY | 屬實的部分：`check_inputs.py` 搜不到 `LAYERS_RC`、`clkdlybuf4s`、`RUN_HEURISTIC_DIODE_INSERTION`；`pnr/*/config*.json` 都沒設 `RT_CLOCK_MIN_LAYER`。不準確的部分：`clkdlybuf4s*` 已在 config 的 `EXTRA_EXCLUDED_CELLS` 排除（如 `pnr/picorv32_core/config.json:36–41`），缺的是「新 config 沒排除時會被抓到」的檢查；`LAYERS_RC` 有 `ir_worst.py:131–133` 的間接防護 |
| 10 | 推測移出規則本文 | CONFIRMED（抽查） | `drc-signoff:46`「（推論）」 |
| 11 | 漂移的數字；skill 不寫案例數 | CONFIRMED（抽查） | `neg_regress.py:86–105` 是 8 個情境；`neg_run_guard.py:36` 的 `STEPS` 有 16 項，而 `signoff-checker-qualification:18` 寫 14 個；`Makefile:57` 寫 `neg-precheck` 25 cases，`neg_precheck.py` 的案例表數到 31 列；`test-flow-retry` 見 R11。`neg-pin-plan` 的 25／26 本文件沒有重數 |
| 12 | 設計數字移出 skill；sky130 數字移進 knowledge | CONFIRMED（未逐條核） | 屬於 `CLAUDE.md` 規則 4 的整理 |
| 13 | `phase-exit-review` 加收尾時程、審查與 regress 並行、模板更新 | CONFIRMED | 規則 4（:18）仍寫「章節（Phase 3 的版本）」；經驗紀錄 :36、:39、:40 有三次「多輪 regress」 |
| 14 | 過時的「待補」「待驗證」節 | CONFIRMED（抽查） | 和 `review_p4_5` R11 重複 |
| 15 | `.claude/guard.json` 的漏洞（使用者決定） | CONFIRMED | `require_clean` 只有 `harden-(soc|core)`；`processes` 只認 `-m librelane --run-tag` 與 `run_eqy.py`，`neg-pnr` 用的 `librelane.steps run` 不在內 |

**建議 4 的逐條核對**：

| 條目 | 判定 | 兩邊原文 |
|---|---|---|
| Q1 `floorplan-congestion` 規則 2、3 | CONFIRMED | 見上表第 3 列 |
| Q2 `drv-timing-closure` 規則 9 | PARTLY | 標題「resizer 看不到的 corner，用 PnR 的餘量補」仍像現行規則；但同一條第一句已寫「soc_top 改成讓 resizer 也看 ss_n40C、setup 餘量改回 0.1 ns（ADR-0013）」（:28）。這是寫法容易誤讀，不是矛盾 |
| Q3 `multicorner-sta` 規則 3 第 3 點 | PARTLY | :23「做法：resizer 用原本的 corner」；同一規則最後一點已加條件：「上面『resizer 用原本的 corner』只在找過根因、做過 what-if、寫了 ADR 之後才用」。這是有條件的，不是否定 |
| Q5 `timing-constraints-sdc` 規則 5 | CONFIRMED | :16「只允許已知例外（`sram0/clk1` 沒有 clock…）」；`check_soc.py:53–58`「now none is allowed in soc_top」 |
| Q6 `pdn-ir-drop` 規則 12 | PARTLY | 規則 12 已改到「判 `max_ss_n40C_1v60` 與 `max_ss_100C_1v60`」（:39）；但「ff 照跑…EM 與紀錄用」與 repo 搜不到 `-enable_em` 不一致，屬實 |
| Q8 `signoff-criteria:215` | CONFIRMED | `checkers_ran` 列仍寫「`ir_worst.py`（最壞組合 IR）」 |
| Q9 `lvs-signoff` 規則 2 | CONFIRMED | :15 沒寫外殼頂層預期的斷線腳位；`check_disconnected.py` 實際在 `pnr/picorv32_core/` |

---

## 2. 三個重點的親自查證

### 2.1 skill 清單裡的 description（`review_skills.md` 第 0 節第 1 點、3.3）

**我在本 session 收到的清單**（照清單上的順序）：

| skill | description 字元數 | 清單裡的狀態 |
|---|---|---|
| antenna-signoff | 438 | 完整 |
| chip-floorplan-pin-planning | 1,116 | 完整 |
| core-migration-hazard3 | 867 | 完整 |
| cts-clock-tree | 780 | 完整 |
| drc-signoff | 629 | 完整 |
| drv-timing-closure | 1,453 | 完整 |
| dv-directed-tests | 318 | 完整 |
| floorplan-congestion | 462 | 完整 |
| flow-regression-reproducibility | 642 | 完整 |
| formal-equivalence-eqy | 741 | 完整 |
| gate-level-simulation | 482 | 完整 |
| hard-macro-integration | 1,715 | **截斷**：第 1,535 字元後接「…」（停在「SRAM 半週期讀出…」） |
| librelane-run-debug | 1,199 | 完整 |
| lvs-signoff | 210 | 完整 |
| multicorner-sta | 631 | 完整 |
| openram-macro-characterization | 2,729 | **截斷**：同樣在第 1,535 字元（停在「OpenRAM dev 的 .lib in…」） |
| pdn-ir-drop | 929 | **只有名稱** |
| phase-exit-review | 532 | 完整 |
| rtl-synthesis-lint | 228 | 完整 |
| signoff-checker-qualification | 1,243 | **只有名稱** |
| signoff-criteria | 1,197 | **只有名稱** |
| tapeout-precheck-caravel | 2,088 | **只有名稱** |
| timing-constraints-sdc | 515 | **只有名稱** |
| **合計** | **21,144** | |

- 字數用 Python 讀 YAML 開頭的 `description:` 量，不含欄名；`review_skills.md` 的 21,466 是用 `wc -m` 量整行，多了每份 14 個字元的「`description: `」與換行（23 × 14 = 322），兩者一致。
- 清單中這個專案的 skill 之前，還有 5 個使用者全域 skill（`claude-usage`、`colab`、`graphify`、`html-report`、`overnight-run`），都有 description；之後的內建 skill 有的有、有的沒有（例如 `anthropic-skills:docx`、`pdf` 只有名稱）。

**Claude Code 官方文件怎麼規定**（由一個 claude-code-guide agent 查，原文引用）：
- 單份上限：`https://code.claude.com/docs/en/skills.md` 寫「the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing」；`settings-reference.md` 的 `skillListingMaxDescChars` 預設 `1536`。這與實測的「第 1,535 字元加『…』」相符。
- 總預算：`settings-reference.md` 的 `skillListingBudgetFraction` 預設 `0.01`（context window 的 1%）。`skills.md` 寫「When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least」，並且「The listing always contains every skill name」。
- 可調：`skillListingBudgetFraction`、`skillListingMaxDescChars`、`skillOverrides`（`"name-only"`）；環境變數 `SLASH_COMMAND_TOOL_CHAR_BUDGET` 文件有提，但沒寫預設值。
- 查看：`/doctor` 給清單成本估算，`/context` 的 Skills 列是套用預算後的大小，超出預算時 `--debug` 的 log 有警告。文件沒寫哪個指令會列出被省略的 skill。

**結論**：
- 「5 個看不到、2 個被截斷」屬實，與本 session 所見完全一致。
- 報告的兩個推測都不對：
  - 截斷點是 1,536 字元的單份上限，不是「約 1,000 字」。
  - 被拿掉的是最少被呼叫的 skill，不是「照字母順序、後面的擠掉」。這也解釋了為什麼 515 字元的 `timing-constraints-sdc` 不見，532 字元的 `phase-exit-review` 卻還在。
- 影響比報告說的更廣：
  - `tapeout-precheck-caravel`、`openram-macro-characterization`、`hard-macro-integration` 超過 1,536 字元，換任何機器都一定被截斷，後段的錯誤訊息永遠看不到。
  - 其餘 skill 會不會消失，取決於使用者機器上的全域 skill 與呼叫紀錄。所以「合計控制在 N 字」只能壓低機率，不能保證；`make skill-check` 能確定擋下的只有單份 ≤ 1,536。
  - 1% 是以 context window 計，換成較小 context window 的模型時，看得到的 skill 會更少（推測，文件只說預算隨 context window 等比例變化）。

### 2.2 latch-up 標記 81/14（`review_p0_35.md` P3-10、建議 1）

**規則原文**：
- `drc-signoff/SKILL.md:43–46` 規則 7：「SkyWater 的預設規則是 tap 到 diffusion 6 µm。只有 `areaid.lowTapDensity`（81/14）覆蓋、而且距 padframe ≥ 50 µm 的區域，才能用 15 µm」；「Magic 寫 GDS 時會自動產生 81/14（top cell 外框內縮 250 µm）；KLayout 寫的 GDS 沒有」；「…否則 6 µm 規則會大面積違規（推論）」。
- `docs/notes/signoff_criteria_soc_top.md:41`：「Magic 完整 GDS DRC 在 SRAM 外 0 違規；tap 最壞約 13.1 µm（15 µm 規則）…KLayout 輸出的 GDS 沒有 81/14 標記…Phase 7 確認 81/14 覆蓋 soc_top」；:118 列為「Phase 7 才能處理的」。
- SkyWater 官方文件（`https://skywater-pdk.readthedocs.io/en/main/rules/layers.html`，WebFetch 讀取）：
  - Table C3 原文：「areaid.ld{81:14} | areaid low tap density | areaid.low | 6um tap to diff rule will not be checked in this region」。
  - 同頁還寫：「Should be used sparingly and only over the portion of the layout to remove DRC violations」「This layer is not to be used if a tapping solution can be found」「This layer will be reviewed during PDQC」。
  - GDS 層表原文：「Low tap density (15um between taps) area. Must be at least 50um from padframe」。
  - skill 對規則的描述正確。

**實驗**：KLayout 無頭模式（`klayout -z`）讀 GDS，列出所有 layer／datatype，並統計 81/x 各層的圖形與所在 cell。

| GDS | 寫出工具 | 81/14 | 81/x 其他層 |
|---|---|---|---|
| `arvinsa-rtl-gds-p7close2_h3/runs/soc_top_hazard3/final/gds/soc_top.gds` | KLayout（sha1 `9d3f249e…`，與 `final/klayout_gds/soc_top.klayout.gds` 相同） | **沒有** | 81/2（bitcell 內）、81/4（SRAM 各 cell）、81/23（`diode_2` 內） |
| `arvinsa-rtl-gds-p7close2_caravel/runs/user_project_wrapper/final/gds/user_project_wrapper.gds` | KLayout（sha1 `06b0ddc4…`，與 `klayout_gds/` 相同） | **沒有** | 同上 |
| 對照：`soc_top_hazard3/final/mag_gds/soc_top.magic.gds` | Magic | **有，1 個矩形，在 top cell `soc_top`**：(250, 250)–(744.25, 539.04) µm，die 是 (0, 0)–(1000, 800) | 同上 |

**三個額外發現**（四份報告都沒寫）：
1. **整條 flow 沒有任何檢查查 6 µm 規則。**
   - Magic 的 tech 檔（`~/.ciel/sky130A/libs.tech/magic/sky130A.tech`）只實作 15 µm：`ptap_missing`／`ntap_missing` 由 tap 長 15 µm 的範圍算出（:1566–1600），錯誤訊息是「N-diff distance to P-tap must be < 15.0um (LU.2)」（:4325–4330），而且只在 `full` variant 跑。81/14（`LOWTAPDENSITY`，:1393–1398）只在寫 GDS 時產生，DRC 不讀它。
   - 所以 `signoff_criteria_soc_top.md:41` 說的「Magic 完整 GDS DRC 在 SRAM 外 0 違規」，只證明了 15 µm 規則，沒有證明 6 µm 規則。
2. **precheck 也不查。**
   - PDK 的 `sky130A.lydrc:151`、`sky130A_mr.drc:235`，以及 precheck 用的 `.tools/cf-precheck-1.3.7/sky130A_mr.drc:248`，都只有宣告 `areaid_ld = polygons(81, 14)`，沒有任何規則用到它。
   - precheck 的 `magic_drc` 預設不跑（`signoff/precheck/README.md` 判定表第 1 列）。
3. **即使改用 Magic 寫 GDS，81/14 也只蓋 top cell 外框內縮 250 µm 的範圍。** soc_top 的外圈 250 µm 本來就不在標記內。所以「改回 Magic 輸出」不是完整的解法。

**是否構成下線風險（推測，未經 ChipFoundry 或 SkyWater 確認）**：
- 不確定的一：整合方組 Caravel 全晶片 GDS 時，會不會在 user 區域加 81/14。如果用 Magic 對全晶片 top 寫 GDS，會自動產生一個內縮 250 µm 的標記，可能涵蓋 user 區域。這要看平台實際的組裝流程，本文件查不到原文。
- 不確定的二：SkyWater 端（PDQC）的 latch-up 檢查是不是用 6 µm 規則判 user 區域。
- 標準元件 tap 的間距：`pnr/*/config*.json` 沒設 `FP_TAPCELL_DIST`，用的是 LibreLane 的 sky130 預設。`signoff_criteria_soc_top.md:41` 記的「tap 最壞約 13.1 µm」如果是 diffusion 到 tap 的距離，就超過 6 µm；如果是 tap 之間的距離，最遠的 diffusion 約一半。這段原文沒說是哪一種，本文件無法判斷。
- 結論：**是否真的缺：是**（交付 GDS 沒有 81/14，實測確認）。**是否構成風險：未知**，要先查平台規定。依 `CLAUDE.md` 規則 13，這是會影響下線判定的分岔，由使用者決定。可以列給使用者的選項：
  1. 問 ChipFoundry：user 區域的 latch-up 標記由誰加、用 6 µm 還是 15 µm 判。
  2. 在 wrapper GDS 自己加 81/14，要符合「距 padframe ≥ 50 µm」，而且官方說這層會在 PDQC 審。
  3. 寫一支用 6 µm 規則的 KLayout 檢查，量 soc_top 實際有多少違規，再決定。
- 同時應把它登記到 `docs/relaxation_register.md` 與 Phase 7 已知限制，並把 `drc-signoff` 規則 7 的「（推論）」改成本節實測的事實。

### 2.3 regression 沒有逾時、開跑前不查磁碟（`review_p6_7` 建議 1、`review_p4_5` R1、`review_skills` R2／R3）

| 位置 | 查到的內容 | 判定 |
|---|---|---|
| `scripts/regress.py:113–122` | 每個 target 用 `subprocess.run([make, "--no-print-directory", t], …)` 執行，**沒有 `timeout`**；開跑前只檢查 `MAKEFLAGS`、工作目錄乾淨、HEAD（:105–112），不檢查記憶體或磁碟 | CONFIRMED |
| `env/check_env.sh`（121 行） | 搜 `disk`、`df`、`free`、`memory` 都沒有；唯一的記憶體檢查是 lima VM ≥ 15 GB（:115–125，只給 `make precheck-caravel`） | CONFIRMED |
| `Makefile:159–160` `env-check-flow` | 只呼叫 `bash env/check_env.sh --flow` | CONFIRMED |
| 有逾時的地方 | 只有 gate-level 模擬：`dv/gl_soc/run_gl_soc.py:87`、`:192`、`:233` 的 `gl_timeout`；`pnr/librelane_flow.sh`、`pnr/soc_top/run.sh`、`signoff/eqy/run_eqy.py` 都沒有 | — |
| 唯一的資源防護 | `.claude/guard.json`（`~/.claude/hooks/guard-bash.py` 讀）：`max_concurrent: 2`、`min_free_gb: 4`。只在 Claude Code 下 Bash 指令那一刻數程序；不查磁碟；`neg-pnr` 用的 `librelane.steps run` 不在計數內；換機器或用 Codex 時不存在 | — |
| 本機現況 | `df -h`：資料磁碟 1.8 TiB，剩 564 GiB（70% 已用）；`git worktree list` 14 列 | 參考 |

結論：三份報告的說法屬實。規則本文只有 `flow-regression-reproducibility:48` 一句「同時跑會互相拖慢，逾時要單獨重跑」，這是事後判讀的提醒，不是開跑前的預算，也不是自動防護。

---

## 3. 合併後的建議清單（去重，依重要性排序）

- **出處簡寫**：「p035-N」＝`review_p0_35` 建議 N；「p45-RN」＝`review_p4_5`；「p67-N」＝`review_p6_7`；「sk-N」＝`review_skills` 第 6 節第 N 項，「sk-Qn／Rn／Fn／Gn」＝其內文編號。
- **「使用者決定」欄**依 `CLAUDE.md` 規則 13：
  - 新寫 checker、改 signoff 標準、改全域設定或 `CLAUDE.md`、可能構成下線風險的，標「要」。
  - 把已驗證的經驗升為規則、修正過時文字或引用，屬照規則做的維護，標「不用」。
- **工作量**都是估計，不含 regress 時間。

### A 群：會讓下一個專案直接出錯，或選不到 skill

| 編號 | 主題 | 合併自 | 驗證 | 寫到哪裡 | 使用者決定 | 工作量（估） |
|---|---|---|---|---|---|---|
| A1 | **skill description 超過上限、在清單裡消失**：3 份超過單份 1,536 字元一定被截斷；5 份因總預算被拿掉 | sk-1、sk-3.3(a)(b)(c)(d) | PARTLY（現象 CONFIRMED，機制改正，見 2.1） | 23 份 `SKILL.md` 的 `description`（確切錯誤訊息放前面、做法與設計數字移回本文、同一症狀只放在先看的那個 skill）；README skill 一節；`scripts/check_skills.py` 加單份 ≤ 1,536 字元與合計上限，並加植入錯誤（超長的一份）；`CLAUDE.md` 規則 5 補「description 有長度上限」 | 縮短：不用。新 checker 與 `CLAUDE.md` 規則 5 的修改：要。另一個選項是在專案 `.claude/settings.json` 調 `skillListingBudgetFraction`：要（改設定） | 5–7 |
| A2 | **最終 GDS 沒有 latch-up 標記 81/14，而且沒有任何檢查查 6 µm tap 規則** | p035-1（後半）、sk-2.2 drc:45、本文件 2.2 | CONFIRMED（實測），風險未知（推測） | 先查證（問平台、或寫 6 µm 的 KLayout 量測）；結果寫 ADR-0019 補充、`docs/relaxation_register.md`、Phase 7 已知限制；`drc-signoff` 規則 7 改成實測事實（Magic 只查 15 µm、deck 不用 `areaid_ld`、Magic 的標記內縮 250 µm）；`tapeout-precheck-caravel`「待確認」加一條 | **要**（下線風險） | 查證 2–4；之後依選項 |
| A3 | **`floorplan-congestion` 沒有指向 pad／block／pin 規劃與核准**，可能被選中後跳過 `CLAUDE.md` 規則 14 | sk-3、sk-Q1 | CONFIRMED | `floorplan-congestion` 規則 2、3 開頭與 description | 不用 | 0.5 |
| A4 | **規則和後來的決定矛盾或過時**，照舊規則做會走回頭路 | sk-4（Q2、Q3、Q5、Q6、Q8、Q9）、p45-R11 第 1 項、sk-Q16、sk-Q21 | PARTLY（Q2、Q3、Q6 已部分更新，屬寫法問題；Q5、Q8、Q9 CONFIRMED） | `timing-constraints-sdc` 規則 5（拿掉 clk1 例外）；`signoff-criteria:215`；`lvs-signoff` 規則 2（外殼預期的斷線腳位、`check_disconnected.py` 路徑）；`drv-timing-closure` 規則 9、`multicorner-sta` 規則 3 改標題與順序，經過移到 ADR；`pdn-ir-drop` 規則 12 寫明 EM 沒判；`librelane-run-debug` 規則 5（兩種重試、14＋1 情境）；`core-migration-hazard3` 規則 22 的引用改成規則 15 | 不用 | 3 |
| A5 | **流程文件（新專案入口）缺必要步驟或寫錯** | sk-6（F1–F7、G1–G12）、p45-R4、p67-11、p45-R7（流程 :280 的 EM 措辭） | CONFIRMED（抽查 F1、F2、G1、G2、G9） | `arvinsa-rtl-gds-flow.md`：4.5 加 `*_VIOLATION_CORNERS`（G1）；4.8／4.9 加「開結案 regress 前先跑 positive control」（G2）；4.7 加 EQY 三種靜默略過（G8）與 CVC／`EXTRACT_ABSTRACT`（G9）；4.6 與 1.5 加「flow FAIL 時 repo checker 與 criteria review 照跑」（p45-R4）；4.3 第 5 項指到 openram 規則 27（p67-11）；:280 改成「IR、功耗用 pattern；EM 目前沒有判定」；F1–F7 的數字與歸屬 | 不用 | 2–3 |
| A6 | **LibreLane 設定靜默無效、內建 checker 靜默略過，缺規則 10 的「怎麼發現」與「防復發」** | p035-2、p035-6、p035-10、sk-9（2.2 表的 `DRT_ANTENNA_REPAIR_MARGIN`、`SIGNOFF_SDC_FILE`、`LAYERS_RC`、`clkdlybuf4s*`、heuristic diode、`RT_CLOCK_MIN_LAYER`、KLayout 的 `floating_metal`） | CONFIRMED（`LAYERS_RC`、`clkdlybuf4s*` 為 PARTLY：已有 config 排除與 `ir_worst.py` 的間接防護） | 文字：`drc-signoff` 規則 5、`antenna-signoff` 規則 10、`cts-clock-tree` 規則 8、`timing-constraints-sdc` 規則 2、`drv-timing-closure` 規則 2，補「怎麼發現」，寫明「沒有自動防護」與原因，description 加變數名；`signoff-criteria`「已驗證的工具行為」加 `Checker.WireLength` 沒設門檻就略過（原文在 `runs/user_project_wrapper.prev/flow.log:7919`）；`RT_CLOCK_MIN_LAYER` 補一行決定。checker：`check_inputs.py` 加「設了 `PNR_SDC_FILE` 就要有 `SIGNOFF_SDC_FILE`」等列；`review_criteria.py:470` 從 INFO 改成判定 | 文字：不用。新 checker 列、`RT_CLOCK_MIN_LAYER` 的決定：要 | 文字 2；checker 3–4 |
| A7 | **EM 從沒判過**（via4 單一 cut 到 78%），登記表 I12 寫「下線前要做」 | p45-R7、sk-Q6、sk-F4 | CONFIRMED | 流程文件 4.6 列為「下一個專案開始時做成 checker」；`signoff-criteria` 規則 14 已寫明沒有工具比對（:99），不用重寫 | **要**（新 checker、signoff 範圍、可能的下線風險） | 文字 0.5；checker 4–8 |

### B 群：已重複發生，但目前只靠人記得

| 編號 | 主題 | 合併自 | 驗證 | 寫到哪裡 | 使用者決定 | 工作量（估） |
|---|---|---|---|---|---|---|
| B1 | **regression 的機器資源：平行數、記憶體、磁碟、逾時、卡住、舊 worktree 清理** | p67-1、p45-R1、sk-2、sk-R1–R3、sk-5.1、sk-15、sk-G4 | CONFIRMED（自動防護缺口，見 2.3）；次數 PARTLY（已驗證 5 次＋推測 1 次，其中 10-07 是外部程式佔記憶體） | `flow-regression-reproducibility` 新增一節「資源與長時間工作」，四項防護齊全，description 加 `No space left on device` 與「regress 卡住」；流程文件 4.8 加一點；`phase-exit-review` 收尾清單加「刪舊 worktree 或中間產物」；checker：`env-check-flow` 查剩餘磁碟、`regress.py` 每項逾時判 FAIL，各加植入錯誤（假的不結束 target）；`.claude/guard.json` 的計數範圍 | 規則文字：不用。新 checker：要。`guard.json`（使用者全域 hook 讀的設定）：要 | 文字 1.5；checker 4–6 |
| B2 | **resizer（或任何 step）失控時自動停** | p45-R2 | PARTLY（4 次屬實；其中 1 次是工具自己結束） | `librelane-run-debug` 規則本文（只寫現象與防護，不寫根因）；流程文件 4.6；包裝腳本的時間與記憶體上限加模擬情境 | 自動停：要 | 文字 1；自動化 3–4 |
| B3 | **實驗證據在做的當下存到不會被覆蓋或消失的地方** | p035-5、p45-R3、p67-5、p035-9（`make clean`、`run.sh` 刪檔，同一類） | CONFIRMED（Phase 3、3.5、4、5、6、7 都有） | `phase-exit-review` 規則 3 加一點（不能引用 scratchpad、會被下一次 harden 覆蓋的 `runs/<tag>_signoff/`、只在終端機看到的 `dmesg`；算式與輸入一起存）；`signoff-criteria`「每次 harden 後的檢查」對 knowledge 的證據路徑同樣要求；流程文件 4.9 | 不用 | 1 |
| B4 | **「之後再處理」的項目要追蹤**（81/14 就是這樣漏的） | p035-1（前半）、p67-2、p035 P2-14 | CONFIRMED | `phase-exit-review` 規則 1：收尾時掃本階段筆記與 skill 裡「Phase N 才能處理」「之後會加」的句子，並逐條對照 `signoff-criteria:184–186` 的「不分析的項目」；決定當下寫進 `runs/todo.md`；流程文件 4.9 | 規則文字：不用。改 `CLAUDE.md` 規則 11：要 | 1 |
| B5 | **新決定取代舊決定時同步前文；skill 不寫會變的案例數** | p67-4、sk-11、sk-Q10、p45-R11 | PARTLY（文件核對的同類問題是兩次，不是三次）；數字漂移 CONFIRMED | `phase-exit-review` 加規則；`CLAUDE.md` 規則 4 或 `phase-exit-review` 規則 9 加「skill 不寫案例數，指向腳本」；修正漂移的數字（`neg-regress` 8、run guard 16、`neg-precheck` 31、`test-flow-retry` 14＋1、D0–D8、K0–K8；`Makefile:57`） | 改 `CLAUDE.md`：要；其餘不用 | 2 |
| B6 | **不在 regression 裡的 negative test 會悄悄過期** | p45-R8、p67-10 | CONFIRMED（兩次：Phase 5 N9–N16、Phase 6 `ad184f5`） | `phase-exit-review` 規則 2：列出最後一次跑的 commit 與環境；checker：`check_inputs.py` 比對被測程式的 sha256 | 文字：不用。checker：要 | 文字 0.5；checker 2 |
| B7 | **版圖相關的計數寫死總數**（每次改 CTS 或換設計都假 FAIL） | p45-R5、sk-R18 | CONFIRMED（4 次 FAIL） | `signoff-checker-qualification` 規則 4 補「逐項分類、會隨版圖變的類別不寫死」；`check_signoff.py` 改成逐項分類 | checker 改法：要 | 文字 0.5；checker 3 |
| B8 | **共用 flow 設定改了，每個變體都要重 harden；換 core 時 IR 要重量** | p45-R6、sk-R8 | CONFIRMED | `core-migration-hazard3` 規則 22 加兩點；`flow-regression` 加一句 | 不用 | 0.5 |
| B9 | **checker 裡的變數重名**（三次，一次讓兩輪 regress 白跑） | p67-3 | CONFIRMED | `signoff-checker-qualification` 規則 13 補 `cbf2c5e` 這一例，範圍改成「同一作用域含模組層」；`py-check` 加 lint 並加植入錯誤 | lint checker：要 | 文字 0.5；checker 2 |
| B10 | **經驗紀錄已驗證或已出現兩次以上，升為規則本文** | sk-7（R4–R24）、p035-8（=sk-R11）、p67-14（=sk-R14）、p035-7、p035-3、p035-4、p035-13、p035 P35-24（GRT-0243） | CONFIRMED（抽查 RSZ-0064、no such vector、PDN-0239／GRT-0036） | 各 skill 規則本文與 description，優先順序：`RSZ-0064`／hold 進度表、SDC 生效看報表、RSZ-0074 三種原因對照表、`no such vector`、`PDN-0239`／`GRT-0036`、GDS sha256 比對（`flow-regression`）、特性化範圍涵蓋 SoC 工作點（`openram`）、RTL testbench 的兩種漏洞（`signoff-checker-qualification` 漏洞類型表）、偏離計畫時失去的保護（`phase-exit-review` 規則 4）、`pdk::` 條件區塊（`rtl-synthesis-lint`）、`GRT-0243`（`antenna-signoff`，Phase 3.5、5、6、7 都出現） | 不用 | 5–7 |
| B11 | **checker 的訊息分不出工具當掉與結果不對；其他已確認缺陷的防復發** | p67-8、p67-9、p67-13、p67-15、sk-5、sk-8、sk-9（`FALL=1` 加 `neg-char` 案例） | CONFIRMED | `signoff-checker-qualification` 漏洞類型表加一列；`tapeout-precheck-caravel` 補「讀到舊報表」的四項（`stale_results` 已存在，只缺文字）；checker：precheck 的當掉偵測、輸入 transition 生效、run guard 對 Makefile 的自我檢查、CVC HI-Z、`TIMING_STEPS` 清單外的 step 判 FAIL；`librelane-run-debug` 加「升版時要重看的綁定」清單 | 文字：不用。各新 checker：要 | 文字 2；checker 共 8–12 |
| B12 | **GDS 的 sha256 每次不同，不代表 flow 不可重現** | p67-6、sk-R4 | PARTLY（precheck 綁定已有 checker，XOR 已在 openram 規則本文） | 只補 `flow-regression` 的規則文字 | 不用 | 0.3 |

### C 群：文件整理

| 編號 | 主題 | 合併自 | 驗證 | 寫到哪裡 | 使用者決定 | 工作量（估） |
|---|---|---|---|---|---|---|
| C1 | 推測寫在規則本文，移回經驗紀錄或標明 | sk-10（1.3 表）、p035-1（`drc-signoff` 規則 7）、p035-15 | CONFIRMED（抽查） | 各 skill；ADR-0020 的提早檢查另放一節「使用者決定」 | 不用 | 2 |
| C2 | 設計數字移出 skill；sky130 數字移進 knowledge | sk-12、sk-3.2 | CONFIRMED（未逐條核） | 各 skill、`signoff-criteria` 與 knowledge、ADR、`pnr/*/README.md`。和 A1 一起做可以縮短 description | 不用 | 4–6 |
| C3 | 過時的「待補」「待驗證」節 | sk-14、p45-R11 第 2、3 項、sk-Q13、Q16–Q19 | CONFIRMED（抽查） | `pdn-ir-drop`、`floorplan-congestion`、`core-migration-hazard3`、`rtl-synthesis-lint`、`openram`、`chip-floorplan-pin-planning`（`pin_plan.toml` 沒有 `[power]` 節） | 不用。`config.json:162`、`config_hazard3.json:188` 的過期註解是程式碼：要 | 2 |
| C4 | `phase-exit-review` 模板與收尾清單更新到 Phase 7 | sk-13、sk-Q15、sk-R16、R17 | CONFIRMED | 規則 4 的章節清單；收尾清單加流程文件與 `AGENTS.md` 同步、清空 `runs/todo.md`、規則 10 稽核、worktree 清理 | 不用 | 1 |
| C5 | Caravel 的 fill 與密度下限寫進「待確認」，補規則 9 懸空的引用 | p67-7、sk-Q20 | CONFIRMED | `tapeout-precheck-caravel`「待確認」與 description；`drc-signoff:54–56` 指向它。風險已由 ADR-0019 決定 26 接受，只補文字 | 不用 | 0.5 |
| C6 | 小的方法提醒 | p035-11、p035-12、p035-14、p035-15、p45-R9、p45-R10、p67-12 | 各見 1.1–1.3（p035-14、15、p67-12 為 PARTLY） | p035-15 與 p45-R10 只寫經驗紀錄；其餘照各報告的位置 | 不用 | 2 |
| C7 | RTL code coverage 與 EQY 範圍試跑 | p035-16 | CONFIRMED | 流程文件 4.2 的選做項目 | **要**（報告本身就交使用者決定） | 0.5 |
| C8 | 長段工作前一次取得授權 | p67-16 | CONFIRMED | 流程文件第 2 節規則 13 摘要旁 | **要**（可選） | 0.3 |

**群數**：A 7 項、B 12 項、C 8 項，共 27 項。

**最重要的 6 項**：
1. **A1**：做法本身是照規則的維護。不改的話，`tapeout-precheck-caravel`、`signoff-criteria`、`signoff-checker-qualification` 在下一個專案也可能選不到。
2. **A2**：唯一一項可能直接影響下線的，要先查證再請使用者決定。
3. **B1**：已發生 5 次。2026-10-15 磁碟滿時，regress 卡住 87 分鐘沒報錯。
4. **A3**：會直接繞過 `CLAUDE.md` 規則 14 的核准。
5. **A4**：照舊規則做會走回頭路，例如在 soc_top 重新允許 `sram0/clk1` 例外。
6. **A5**：新專案從流程文件進來，`*_VIOLATION_CORNERS` 與 positive control 都找不到。

---

## 4. 四份報告中錯誤或誇大的地方

### `review_skills.md`
1. 0 節第 1 點與 3.3(a) 說截斷「大約在第 1,000 字處」：實際是第 1,535 字元，對應官方的 1,536 字元單份上限。
2. 3.3(a) 推測「清單照字母順序排，總長度預算用完之後，後面的 skill 就沒有 description」：官方文件寫的是最少被呼叫的先拿掉。所以合計字數控制不能保證所有 skill 都看得到，它還受全域 skill 與呼叫紀錄影響。
3. 3.3 建議「每份 ≤ 約 600 字」沒有依據；真正的硬上限是 1,536 字元。600 字只能當降低總量的目標。
4. 3.1 Q2、Q3 說「讀起來仍是現行規則」「被否定」：兩條規則內文都已加上取代說明或使用條件（`drv-timing-closure:28`、`multicorner-sta` 規則 3 最後一點），是寫法問題，不是矛盾。Q6 的規則 12 也已改成判兩個慢 corner。
5. 2.2 說 `clkdlybuf4s*`「`check_inputs.py`、`check_weak_cells.py` 都 grep 不到」：屬實，但三份 config 已用 `EXTRA_EXCLUDED_CELLS` 排除；缺的是「新 config 漏排除時會被抓到」，不是現在有風險。
6. Q10 的 `test-flow-retry`「14 種」，和 `review_p4_5` 的「15 個」都對，差在有沒有算 `keep_prev_run` 那一項。兩份都沒寫怎麼數。
7. 2.2 drc:45 把 81/14 只寫成「列為下次 chip-level 的確認項目」：低估了。本文件 2.2 的實測顯示，整條 flow 沒有任何檢查查 6 µm 規則，這一項應在本次 tapeout 前處理。

### `review_p0_35.md`
1. P3-10 寫「flow 的 Magic DRC（會查 LU 規則）」：Magic 只實作 15 µm 規則，從不查 6 µm 規則，所以 Magic 讀哪一份 GDS 都證明不了 6 µm 規則；Magic 的 81/14 也只蓋內縮 250 µm 的範圍。
2. 建議 1 沒注意到 `signoff-criteria:184–186` 已要求每次 signoff 列出「不分析的項目」（含 chip-level latch-up marker）。問題是 Phase 7 沒照做，不只是「只寫在筆記」。
3. P35-24 寫 `GRT-0243`「只出現一次、沒有影響」：`phase5.md:178`、`phase6.md:118`、`phase7.md:151` 都記到它再出現，應寫進 `antenna-signoff`。
4. P1-02 寫漏掉的 10 個「都是介面或順序錯誤」：其中幾個是測試被縮水（`phase1.md:23`）。
5. P1-01、P1-02 判「(e) 都沒有」太滿：流程文件 1.2（:49）把 `dvlib.py` 列為可直接沿用。
6. P0-03 判「(e) 都沒有」與建議 14 高估了：`toolchain.md:61` 已寫，流程文件指向它。
7. 建議 6「沒有 checker 確認 `LAYERS_RC`」忽略了 `ir_worst.py:131–133` 的間接防護。
8. 建議 11「看起來涵蓋得比實際多」：`phase3.md:166` 已揭露。
9. 建議 15 的根因是推論（`ADR-0010:159`「應是」），不是實驗確認，寫進規則本文會違反 `CLAUDE.md` 規則 3。

### `review_p4_5.md`
1. R1「至少 6 次、全部已驗證（一次推測）」：已驗證的是 5 次。P5-14 的「結案兩輪依序跑」是預防，不是事件。也漏了 `flow-regression:48` 已有的平行負載提醒。
2. R2「4 次都是人看到才停」：Phase 3.5 那次是工具自己異常結束（`ADR-0010:149`），根因也不同。`librelane-run-debug:54` 已有「超過 10 分鐘就停」的人工判準。
3. R4 把 P43–P49、`test-review-hook` 當成「flow FAIL 時照跑 checker」的 negative test：它們測的是別的東西，這件事目前沒有直接的 negative test。
4. R7 沒注意到 `signoff-criteria:99` 已寫明沒有工具比對，反而漏了流程文件 :280 讓人以為 EM 有在判的措辭。
5. 第三節第 4 項只列 `config_hazard3.json:188`，漏了 `pnr/soc_top/config.json:162` 的同一段註解。

### `review_p6_7.md`
1. 建議 1 把 10-07 單一 harden 被外部程式擠掉，算成「regression 資源不足」的一次；「skill 規則與流程文件都沒有」也說太滿（`flow-regression:48`、流程文件 1.4）。
2. 建議 4「同類三次」：Phase 5 的文件核對問題性質不同，實際是兩次。
3. P6-06／建議 6 說 precheck 綁 sha1 的做法只在筆記：`check_precheck.py:14–24` 與 `neg_precheck.py` 的 `stale_results` 已是自動防護；XOR 比對也已在 `openram:113` 規則本文。
4. 建議 10 說只發生一次：Phase 5 的 N9–N16 是同一類，合計兩次（本報告低估，方向和其他項相反）。
5. 建議 12 的「同類兩次」歸類偏寬：`hard-macro-integration` 規則 10 已涵蓋大部分。
6. P6-08②「`make openram-macro` 改過後沒有從頭跑過」仍是推測（worktree 沒有逐一翻），報告第 5 節自己有標，但第 3 節第 2 項寫成已驗證的三次之一。

---

## 附：查證指令與證據

- description 字數：用 Python 讀每份 `.claude/skills/*/SKILL.md` 開頭 YAML 的 `description:` 行，量 `len()`；截斷點用清單上最後幾個字在原文中的位置量（兩份都是 1,535）。
- 官方文件：`https://code.claude.com/docs/en/skills.md`、`https://code.claude.com/docs/en/settings-reference.md`（由 claude-code-guide agent 讀取並引用原文）。
- GDS 層：`cd .tools/librelane && nix-shell --run "klayout -z -rd gds=<abs> -r <scratchpad>/layers.py"`，對兩份交付 GDS 與一份 Magic GDS 各跑一次；交付 GDS 與 `klayout_gds/` 的 sha1 用 `shasum` 比對。
- SkyWater 規則：`https://skywater-pdk.readthedocs.io/en/main/rules/layers.html`（WebFetch，只讀到前 100,000 字元，Table C3 與 GDS 層表在其中）。
- Magic 規則：`~/.ciel/sky130A/libs.tech/magic/sky130A.tech:1393–1398`、`:1566–1600`、`:4321–4330`。
- deck：`~/.ciel/sky130A/libs.tech/klayout/drc/sky130A.lydrc:151`、`sky130A_mr.drc:235`、`.tools/cf-precheck-1.3.7/sky130A_mr.drc:248`（都只有宣告，沒有規則使用）。
- regression：`scripts/regress.py:100–122`、`env/check_env.sh:115–125`、`Makefile:159–160`、`.claude/guard.json`。
