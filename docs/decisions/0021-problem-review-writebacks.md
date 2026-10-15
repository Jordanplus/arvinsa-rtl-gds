# ADR-0021：Phase 0–7 問題總檢討的寫回；latch-up 標記先量再決定；先做兩支最急的 checker

- 狀態：已採用（2026-10-15，Phase 7 結案之後）。
- 範圍：skill、`arvinsa-rtl-gds-flow.md`、README、`scripts/check_skills.py`、`scripts/regress.py`、`env/check_env.sh` 與對應的 negative test；不改已完成的設計與 golden。
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
   - C1–C6，含縮短 23 份 description（只改文字）。

   README 的 skill 一節同步，跑 `make skill-check`。
2. **「先量再決定 (建議)」**：寫一支用 6 µm 規則的 KLayout 檢查，量 `soc_top_hazard3` 與 wrapper 實際有多少違規，結果再交使用者決定：問 ChipFoundry、自己加標記，或列為已知限制。
3. **「先做兩項最急的 (建議)」**：
   - A1：`scripts/check_skills.py` 加 description 長度上限（單份與合計），並加植入錯誤；
   - B1：`env-check-flow` 檢查磁碟剩餘空間，`scripts/regress.py` 每項加逾時並判 FAIL，各加 negative test。

   其他需要新 checker 的項目（A6 的 `check_inputs.py` 列、A7 EM、B2 step 失控自動停、B6、B7、B9、B11）照 ADR-0020 決定 2 的做法，寫進流程與 skill，標明「目前沒有自動防護」。
4. **「提交，不推送 (建議)」**：報告與審查筆記提交進 repo。

## 後果

- 改了 `scripts/regress.py` 與 `env/check_env.sh`，依 `phase-exit-review` 規則 2，要在乾淨 worktree 重跑受影響的 regression 才算完成。
- latch-up 的量測結果與使用者的處理決定，補在本 ADR。
