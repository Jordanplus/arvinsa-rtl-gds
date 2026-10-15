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

## 後果

- 改了 `scripts/regress.py`，依 `phase-exit-review` 規則 2，要在乾淨 worktree 重跑受影響的 regression 才算完成。
- **latch-up 的量測結果**（2026-10-15，`docs/notes/latchup/`）：
  - 照 15 µm 規則（有 81/14 時），soc_top 與 wrapper 都是 0；
  - 照預設的 6 µm 規則，SRAM 外約 7% 的 diffusion 面積離同型 tap 太遠：wrapper 有 113,280 µm² NMOS、178,820 µm² PMOS，幾乎全在標準元件與 decap 區；
  - PDK 給 LibreLane 的 `FP_TAPCELL_DIST` 是 13 µm，本來就照 15 µm 規則放 tap。

  使用者 2026-10-15 選「記錄＋問平台，不改設計 (建議)」，處理方式：
  - 寫進 Phase 7 已知限制 21 與放寬登記表 D10；
  - 併進 ChipFoundry 問題草稿（user area 的 81/14 由誰加、用 6 µm 還是 15 µm 判）；
  - 量測腳本寫進 `drc-signoff`，下一個專案在 floorplan 試跑時就量。

  不改設計，不重跑 regress。
