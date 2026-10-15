# 佐證報告（2026-10-15 清理前收錄）

這個 repo 跑 Phase 0–7，是為了寫技術報告（`docs/report/`）和建立流程（`arvinsa-rtl-gds-flow.md`、`.claude/skills/`）。run 的產出都在 `runs/` 與結案 regression 用的 worktree，兩者都不進版控。2026-10-15 依使用者決定把重要的佐證報告收進這裡，然後刪掉所有 worktree 與 `runs/`（ADR-0021 決定 7）：

> 「我們跑這些主要是出技術報告跟建立流程，相關重要資料與數據報告給技術流程都收錄後，就都不需要了」
> 「主要是重要的佐證報告才收」

## 怎麼找文件引用的檔案

ADR、exit review、golden README、skill 裡寫的 `runs/…` 或 `../arvinsa-rtl-gds-<名稱>/runs/…`，路徑原樣保留在這個目錄底下：

| 文件裡寫的 | 收錄位置 |
|---|---|
| `runs/x`（主目錄） | `arvinsa-rtl-gds/runs/x` |
| `../arvinsa-rtl-gds-p8wb_h3/runs/x`（worktree） | `arvinsa-rtl-gds-p8wb_h3/runs/x` |
| `../arvinsa-rtl-gds-p7precheck/<專案>/x`（precheck 工作目錄） | `arvinsa-rtl-gds-p7precheck/<專案>/x` |

每個被引用的路徑有沒有收錄，查 [references.md](references.md)，狀態分四種：
- 已收錄；
- 目錄只收了其中的報告；
- 未收錄（大型產物）；
- 清理前就已不存在。

## 收了什麼

由 `scripts/collect_evidence.py`（`make collect-evidence`）收集，共 677 個文字檔與圖，6.8 MB。每個文字檔都 ≤ 512 KB。repo 是 public，文字檔裡的家目錄路徑在複製時改寫成 `~`（例如 `~/claude_prjs/arvinsa-rtl-gds-p8wb_h3/…`），Claude session 的暫存路徑改寫成 `<claude-session-tmp>`，其他暫存路徑改寫成 `<tmp>`（這些路徑含使用者名稱），其他內容沒有改。

1. 文件直接引用的報告檔、log 與圖（例如經使用者核准的 floorplan 圖 `runs/layout_png/p7_floorplan4_modules.png`）。
2. 文件引用的目錄：
   - 小型實驗目錄（≤ 20 個檔、≤ 2 MB）收其中全部的腳本與 log；
   - 其他目錄只收最上層的報告。
3. 每個 checkout 的每次 harden 的判定與 criteria review：`runs/*_signoff/` 的 `result.txt`、`signoff.txt`、`criteria_review.md`、`soc_checks.txt`、`ir_worst.txt`、`provenance*.txt` 等。
4. 每條 regression 的 `summary.md`、主目錄 `runs/` 最上層的 console 與筆記，例如流程回顧 `runs/p7_review/retro_*.md`。
5. precheck 各次執行的結果摘要（`precheck_run.txt` 等）。

## 沒收什麼、要的話怎麼重新產生

GDS、DEF、網表、SPICE 輸出、波形，以及整個 LibreLane run 目錄（每個數 GB）都沒有收。它們由 commit 重新產生：
- 在乾淨的 checkout 跑 `make regress`、`make regress-picorv32`、`make regress-caravel`。乾淨 worktree 要設的環境變數見 `arvinsa-rtl-gds-flow.md` 4.8。
- `f02a1a0` 的那一輪 regress（結果提交於 `7e54b4e`，ADR-0021「後果」）證明四個設計的 metrics 都和 golden 逐值相同。

報告裡的版圖截圖與圖表在 `docs/report/figures/`，各圖的來源在 `docs/report/figures/SOURCES.md`。

## 以後的專案

專案結束、要清掉 `runs/` 與 worktree 前，照 `flow-regression-reproducibility` 規則 16「專案結束的清理」做：
1. 確認 worktree 沒有只存在那裡的修改；
2. `make collect-evidence`，用 `git add -n` 確認檔數；
3. 提交之後才刪。

腳本在 `runs/` 已經不在時拒絕執行，避免清理後重跑把所有引用都列成不存在。
