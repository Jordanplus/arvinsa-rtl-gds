# ADR-0021：Phase 0–7 問題總檢討的寫回；latch-up 標記先量再決定；先做兩支最急的 checker

- 狀態：已採用（2026-10-15，Phase 7 結案之後）。
- 範圍：skill、`arvinsa-rtl-gds-flow.md`、README、`scripts/check_skills.py`、`scripts/regress.py`、`scripts/neg_regress.py`、`.claude/settings.json` 的 `skillOverrides` 與對應的 negative test；不改已完成的設計與 golden。
- 查證：`docs/notes/problem_review/`。四個沒參與實作的 agent 分段審查（`review_p0_35.md`、`review_p4_5.md`、`review_p6_7.md`、`review_skills.md`）；第五個 agent 反向驗證並合併（`verify_and_merge.md`）。完整技術報告在 `docs/report/`。

## 背景

使用者 2026-10-15：「流主要目的是把完整走過一次，先review一下所有遇到的問題與檢討哪些是要寫進skill與流程裡的」。

審查結果：
- Phase 0–7 共 247 個問題。依現在最強的捕捉層：
  - 115 個有 skill 規則或流程文件，加上自動防護；
  - 93 個只有規則或流程文件；
  - 23 個只在經驗紀錄；
  - 16 個只在 ADR、筆記或 commit 訊息。
- 四份報告共 58 條建議：45 條屬實、13 條部分屬實、0 條不屬實。合併成 27 項，分三群：
  - A 群 7 項：會讓下一個專案直接出錯，或選不到 skill；
  - B 群 12 項：已重複發生，但只靠人記得；
  - C 群 8 項：文件整理。

兩項比預期嚴重（`verify_and_merge.md` 2.1、2.2）：
- **skill 的 description 被截斷或整段消失**：
  - 單份超過 1,536 字元會被截斷：`tapeout-precheck-caravel` 2,088 字元、`openram-macro-characterization` 2,729 字元、`hard-macro-integration` 1,715 字元；
  - 所有 description 合計受 context window 1% 的預算限制，超過時最少被使用的 skill 先失去 description；
  - 審查時有 5 個 skill 在清單裡只剩名稱。
- **latch-up 標記**：交付的 GDS（KLayout 寫出）沒有 `areaid.lowTapDensity`（81/14）。另外：
  - Magic 的 DRC 只實作 15 µm 的 LU.2／LU.3；
  - PDK 與 precheck 的 KLayout deck 只宣告這一層，沒有任何規則用到它；
  - 所以整條 flow 沒有任何檢查查預設的 6 µm tap 到 diffusion 規則。

  是否構成下線風險不確定，要看平台組全晶片時會不會加標記、SkyWater 怎麼判（推測）。

## 決定

使用者 2026-10-15 的四個選擇：
1. **「全部做，一次提交 (建議)」**：不需要使用者決定的維護項目全部寫回：
   - A3–A5、A6 的文字；
   - B3、B8、B10、B12；
   - B4、B5 的文字部分（`phase-exit-review` 的規則；不改 `CLAUDE.md`）；
   - C1–C6，含縮短 23 份 description（只改文字）。

   README 的 skill 一節同步，跑 `make skill-check`。
2. **「先量再決定 (建議)」**：寫一支用 6 µm 規則的 KLayout 檢查，量 `soc_top_hazard3` 與 wrapper 實際有多少違規，結果再交使用者決定：問 ChipFoundry、自己加標記，或列為已知限制。
3. **「先做兩項最急的 (建議)」**：
   - A1：`scripts/check_skills.py` 加 description 長度上限（單份與合計），並加植入錯誤；
   - B1：`env-check-flow` 檢查磁碟剩餘空間，`scripts/regress.py` 每項加逾時並判 FAIL，各加 negative test。

   實作（2026-10-15）：磁碟檢查沒有放進 `env-check-flow`，而是放在 `scripts/regress.py` 開跑前的拒絕條件（`REGRESS_MIN_FREE_GB`，預設 100 GiB）。理由：它和既有的「工作樹不乾淨就拒絕」放在同一處，`make neg-regress` 可以用假的 make 植入（`low_disk`），而且單獨跑 `make env-check-flow` 時不需要大量磁碟。逾時是參考時間 × 3、至少 30 分鐘，逾時後砍整個程序群組，log 寫 `regress: TIMEOUT`（`timeout` 案）。長度檢查見決定 6。

   其他需要新 checker 的項目（A6 的 `check_inputs.py` 列、A7 EM、B2 step 失控自動停、B6、B7、B9、B11）照 ADR-0020 決定 2 的做法，寫進流程與 skill，標明「目前沒有自動防護」。
4. **「提交，不推送 (建議)」**：報告與審查筆記提交進 repo。
5. **description 超過單份上限的三個 skill 依功能拆分**。使用者 2026-10-15 先說「3個描述太長的skill表示應該再依據功能分拆」，再選定拆法：
   - `tapeout-precheck-caravel`，「拆成兩個 (建議)」：
     - 原名保留跑與判定 precheck（Docker／VM、deck 版本、bitcell 兩條規則、LVS black box、舊報表、VM 記憶體）；
     - 新建 `caravel-user-project-integration`：wrapper 範本、GPIO／pin 選擇、`wb_clk_i`、供電結構與 IR 起算點、decap／li1、fill 與密度下限、邊界 SDC 試算、平台試算表。
   - `openram-macro-characterization`，「拆成三個」：
     - 原名保留 SPICE 特性化與 `.lib`；
     - 新建 `openram-macro-generation`：用 OpenRAM 產生 macro，包括釘版 PDK、patch、DRC／LVS、可重現、讀取電路修正、1RW 限制；
     - 新建 `sram-layout-extraction`：版圖萃取與萃取網表的模擬。
   - `hard-macro-integration`，「拆成兩個 (建議)」：
     - 新建 `macro-qualification`：選定前的 go／no-go、view QA、`.lib` 驅動能力、換 macro 檢查單；`CLAUDE.md` 規則 12 改指向它；
     - 原名保留接進 flow 的做法。

   skill 從 23 個變成 27 個。`CLAUDE.md` 規則 1、7、12，README 的 skill 一節，流程文件，以及其他 skill 的引用同步修改。

6. **skill 分成 Middle-end、Backend、Package 三段，各一個入口**。
   - 背景：拆分後 27 份 description 合計 20,475 字元，仍超過清單預算（context window 的 1%）。
   - 使用者 2026-10-15：「整個流程可以分成Middle-end，backend，package 三大部分，每一部分各自搜尋相關的skill」，接著選定：
     - 「3 個入口 skill＋子 skill 只列名稱 (建議)」：新建 `middle-end-flow`、`backend-flow`、`package-flow`，description 寫該段最常見的情況與錯誤訊息，本文是「情況／錯誤訊息 → 子 skill（檔案路徑）」對照表。專案 `.claude/settings.json` 用 `skillOverrides` 把子 skill 設成 `name-only`，名稱與檔案不動（官方文件 skills.md「Override skill visibility from settings」、settings-reference `skillOverrides`；name-only 的 skill 能否用 Skill 工具呼叫，文件沒寫，所以入口寫明每個子 skill 的路徑，讓 Claude 直接讀檔）。
     - 「獨立，保留描述 (建議)」：`signoff-checker-qualification`、`flow-regression-reproducibility`、`phase-exit-review` 跨段共用，不歸任何一段，照舊列描述，三個入口都指向它們。
     - 「照初稿 (建議)」：
       - Middle-end：`rtl-synthesis-lint`、`dv-directed-tests`、`core-migration-hazard3`、`timing-constraints-sdc`、`formal-equivalence-eqy`、`macro-qualification`、`openram-macro-generation`、`openram-macro-characterization`、`sram-layout-extraction`；
       - Backend：`floorplan-congestion`、`hard-macro-integration`、`pdn-ir-drop`、`cts-clock-tree`、`drv-timing-closure`、`multicorner-sta`、`antenna-signoff`、`drc-signoff`、`lvs-signoff`、`gate-level-simulation`、`signoff-criteria`、`librelane-run-debug`；
       - Package：`chip-floorplan-pin-planning`、`caravel-user-project-integration`、`tapeout-precheck-caravel`。
   - 自動防護：`make skill-check` 檢查每個子 skill 剛好出現在一個入口的對照表、`skillOverrides` 與分段一致、清單上會出現描述的 skill（入口與共用）合計長度。

7. **佐證報告收進 repo，之後刪掉所有 worktree 與 `runs/`**。
   - 背景：確認 regress 跑完後，17 個 worktree 加主目錄 `runs/` 約 710 GB，磁碟剩 364 GiB。repo 文件引用了 307 個 `runs/` 或 worktree 路徑，`runs/` 不進版控，刪掉之後這些引用就找不到。
   - 使用者 2026-10-15：「我們跑這些主要是出技術報告跟建立流程，相關重要資料與數據報告給技術流程都收錄後，就都不需要了」，接著補充：「主要是重要的佐證報告才收」。
   - 做法：
     - 刪之前確認沒有只存在 worktree 的修改：p7close_caravel 的 41 個修改檔都和 main 歷史的某一版相同；p7close_h3 有 10 個檔和 main 任何一版都不同，逐行查過，新增的內容 main 都已改寫收錄（wrapper 誤差那段是結案前的草稿，被 ADR-0019 決定 26 取代）。
     - 新增 `scripts/collect_evidence.py`（`make collect-evidence`）。收錄範圍：
       - 文件直接引用的報告檔；
       - 每次 harden 的判定與 criteria review；
       - regression 摘要與 console；
       - 被引用的小型實驗目錄（≤ 20 個檔、≤ 2 MB）的腳本與 log；
       - precheck 結果。

       收錄位置是 `docs/evidence/<checkout 目錄名>/runs/…`，保留路徑。單檔上限 512 KB（放寬到 4 MB 會多出 319 個大型 log、壓縮後 40 MB，不划算）。共 677 個檔、6.8 MB。`docs/evidence/references.md` 列出每個被引用路徑的收錄狀態。
     - 不收 GDS、DEF、網表、SPICE 輸出、整個 LibreLane run 目錄：它們由 commit 重跑產生，`f02a1a0` 的 regress 已證明四個設計的 metrics 逐值重現。
     - ChipFoundry 問題草稿還沒定案，搬到 `docs/notes/chipfoundry_issue_draft.md`。
     - 保留執行環境：`.tools/`、precheck 工作目錄的 `pdks/`、`cup_example/`、`run_precheck.sh`，以及 Docker／lima 的 image。
   - 結果（2026-10-15）：
     - 收錄提交為 `35fbb16`，之後刪掉 17 個 worktree、主目錄 `runs/`（只留 `todo.md`），以及 precheck 工作目錄裡 6 個執行結果目錄；
     - 磁碟剩餘從約 351 GiB 增加到 1,106 GiB，約釋放 750 GiB；
     - 刪除 worktree 的指令被 Claude Code 自動模式的安全檢查擋下，由使用者把指令送來確認後才執行。
   - 流程寫回（決定 7）：`flow-regression-reproducibility` 規則 16「專案結束的清理」、`phase-exit-review` 規則 3 與 9、`signoff-criteria` 的 knowledge 出處、流程文件 4.9、README。原規則要求把大型證據另存到主目錄 `runs/<實驗名>/`，但沒寫到 `runs/` 本身也會被清掉。

8. **剩下的四個待決事項**。使用者 2026-10-15 說「做給我決策吧」，選定：
   - `RT_CLOCK_MIN_LAYER`（A6，`cts-clock-tree` 規則 8）：「本專案不設，下專案一開始就設 (建議)」。
     - 本 repo 已結案、不下線，設了要重新 harden 三個設計、更新 golden 並重跑 regress（約 10 小時），run 也已刪除。
     - 新專案的 config 第一版就設（sky130 用 `met3`）；checker 留到下一個專案：`resolved.json` 是 null 就 FAIL。
   - EM checker 的範圍（A7，`pdn-ir-drop` 規則 8）：「電源網路 EM (建議)」。
     - 範圍是 PDN 的 strap 與 via：用 `analyze_power_grid -enable_em` 輸出每段的電流，對 tech LEF 的上限比對；電流用 CPU max power pattern，ff 與 ss corner 都判；植入錯誤至少有「strap 改窄」與「via 改成單一 cut」。
     - 理由：本專案唯一量到超標的是 via4，而且工具已經有。訊號線 EM 不在範圍。
   - ChipFoundry 問題草稿（ADR-0019 決定 6）：「先不送，保留草稿 (建議)」。
     - 本專案不下線，下一個真的要下線的專案再送，送之前先確認 deck 是否已修正。
   - 推送：「兩個 remote 都推 (建議)」。

## 後果

- 改了 `scripts/regress.py`，依 `phase-exit-review` 規則 2，在 `f02a1a0` 的乾淨 worktree 重跑了三條 regression（2026-10-15，兩條同時跑），全部 PASS：
  - Hazard3 `make regress` 30/30（174 分鐘，worktree `p8wb_h3`）；
  - PicoRV32 `make regress-picorv32` 31/31（223 分鐘，`p8wb_pico`）；
  - wrapper `make regress-caravel` 18/18，含 ChipFoundry precheck（428 分鐘，`p8wb_caravel`）。

  四次 harden 的 metrics 都和 golden 逐值相同（soc_top_hazard3 441、soc_top 435、picorv32_core 325、wrapper 455），criteria review 除了路徑與 Phase 7 結案逐字相同，所以這次的寫回沒有改到 flow 的輸出。三條都通過開跑前的磁碟檢查（開跑時剩約 551 GiB，跑完剩 364 GiB），沒有一項逾時：實際耗時最多是逾時上限的 35%（`neg-gl-soc` 10.6／30 分、`neg-eqy-core` 50.0／144 分）。跑完後三個 worktree 的 `runs/` 分別是 52、68、28 GB，在 `flow-regression-reproducibility` 規則 14 估計的範圍內。console 在主目錄 `runs/p8wb_regress_*.console`，每次 harden 的 criteria review 在各 worktree 的 `runs/*_signoff/criteria_review.md`。
- **latch-up 的量測結果**（2026-10-15，`docs/notes/latchup/`）：
  - 照 15 µm 規則（有 81/14 時），soc_top 與 wrapper 都是 0；
  - 照預設的 6 µm 規則，SRAM 外約 7% 的 diffusion 面積離同型 tap 太遠：wrapper 有 113,280 µm² NMOS、178,820 µm² PMOS，幾乎全在標準元件與 decap 區；
  - PDK 給 LibreLane 的 `FP_TAPCELL_DIST` 是 13 µm，本來就照 15 µm 規則放 tap。

  使用者 2026-10-15 選「記錄＋問平台，不改設計 (建議)」，處理方式：
  - 寫進 Phase 7 已知限制 21 與放寬登記表 D10；
  - 併進 ChipFoundry 問題草稿（user area 的 81/14 由誰加、用 6 µm 還是 15 µm 判）；
  - 量測腳本寫進 `drc-signoff`，下一個專案在 floorplan 試跑時就量。

  不改設計，不重跑 regress。
