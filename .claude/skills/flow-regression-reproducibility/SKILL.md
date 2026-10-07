---
name: flow-regression-reproducibility
description: 建立或執行一鍵 regression（`make regress`、`make phase<N>`）、在乾淨 checkout 驗證端到端結果、做來源追溯（哪個 commit、哪版 LibreLane／PDK 產生了這個 run，內容有沒有被改）、讓下游步驟拒絕過期或沒 PASS 的 run、在長時間 run 期間繼續開發或等待它結束（用 PID）、用舊 run 測新 checker（dev fixture），長 regression 開跑前的快速檢查與預跑（`make py-check`、dev fixture），或長 regression 中途因機器負載 FAIL 時使用。同樣設定重跑結果不同、golden 該給多少誤差看 signoff-checker-qualification；錯誤時有時無看 librelane-run-debug。Use when building or running the end-to-end regression, verifying it on a clean checkout, tracking provenance, guarding downstream steps against stale runs, or developing during a long run.
---

# 一鍵 regression、可重現性與來源追溯

checker 本身怎麼設計、golden 怎麼比，看 `signoff-checker-qualification`；LibreLane 怎麼跑，看 `librelane-run-debug`。本 repo 實例：`scripts/regress.py`、`signoff/scripts/provenance.py`、`signoff/scripts/run_guard.py`、`signoff/scripts/neg_provenance.py`、`signoff/scripts/neg_run_guard.py`、`env/pdk_content.sha256`。

名詞：
- **regression**：把全部檢查依序跑一遍，每一項只認明確的 PASS。
- **乾淨 checkout**：從某個 commit 重新取出的目錄，沒有開發目錄裡忽略版控的建置產物（`fw/build/`、`runs/`）。本 repo 用 `git worktree add --detach <目錄> <commit>`，再 `git submodule update --init`。
- **來源追溯（provenance）**：記錄並檢查一個 run 用的是哪個 commit、哪版工具與 PDK，而且當時沒有未提交的修改。
- **下游步驟**：使用 harden 結果的步驟（EQY、gate-level 模擬、PnR 的 negative test）。

## 規則（已驗證）

1. **一鍵 regression 的結構**（`scripts/regress.py`）：
   - 每個 target 各自一次 `make <target>`，依相依順序排（後面的要用前面的結果），第一個 FAIL 就停。
   - 只認 exit code 0；每支腳本自己也只在 PASS 時回 0。
   - 每個 target 的完整輸出存成 log，另外輸出摘要表與 JUnit XML。
   - **開始前**：工作目錄必須乾淨、`MAKEFLAGS` 不能有 `-i`（子 make FAIL 也回 0）、`-n`／`-q`／`-t`（什麼都沒跑），並記下 HEAD；**結束時** HEAD 必須相同。只靠 `provenance-final` 時，它只比 harden 的紀錄：harden 之前的 target 可能跑在別的 commit 上（Phase 4 獨立審查）。`make neg-regress` 用假的 make 測這些拒絕條件（5 個情境，2 秒）。
   - 最後一個 target 是 `provenance-final`：HEAD 等於每個 harden run 記錄的 commit，而且工作目錄仍然乾淨，證明中間的步驟都在同一個 commit 上跑。
   - Makefile 加 `.NOTPARALLEL:`：多個 target 共用並會刪除 `runs/` 下的目錄，`make -j` 會互相刪檔。
2. **只有乾淨 checkout 從頭跑到底才算驗證過**（`signoff-checker-qualification` 規則 10）：Phase 3 的 `make phase3` 跑了 4 次才在乾淨 checkout 跑完；前 3 次分別卡在隨機的工具錯誤、漏宣告 `fw` 依賴、植入腳本產生 Icarus 不收的網表。開發目錄都沒發現後兩個。LibreLane clone 不在版控內，worktree 用 `LIBRELANE_DIR` 指向主目錄的 `.tools/librelane`。
3. **來源追溯要涵蓋實際被執行或讀取的東西**（`provenance.py`）：
   - repo：HEAD、工作目錄乾淨（含未追蹤檔）、submodule 在記錄的 commit。
   - LibreLane：clone 的 commit 等於釘版，而且 clone 的 `git status --porcelain` 為空。只比 commit 時，改了 clone 裡的 `base.sdc` 照樣 PASS（Phase 3 獨立審查實測）。
   - PDK：版本目錄名稱只是 hash 字串，不保證內容沒被改。要對 flow 讀的目錄算內容 sha256（每個目錄一個摘要：排序後的「相對路徑＋檔案 sha256」），參考值要從**下載的壓縮檔**算（壓縮檔 sha256 已釘），不要從安裝好的目錄算；537 MB、2109 個檔，約 1 秒。
   - 再檢查 run 的 `resolved.json` 裡每個 PDK 路徑都落在有檢查內容的目錄，否則多讀一個沒檢查的檔不會被發現。
   - **路徑要解開 symlink 再比**：run 的 PDK_ROOT 解開後必須就是被檢查內容的那一份安裝；resolved.json 裡經 `~/.ciel/sky130A` symlink 指到的檔也算 PDK 路徑。只比字串時，另一份同名版本目錄、或經 symlink 讀範圍外的檔都 PASS（Phase 4 獨立審查；`neg_provenance.py resolved_other_install`、`resolved_symlink`）。
   - 開始與結束各檢查一次：結束時 HEAD 不變、目錄仍乾淨，flow 後段讀的 limits、golden 才是 commit 裡的版本。
4. **下游步驟要確認 run 能用**（`run_guard.py`）：
   - `<run>_signoff/result.txt` 是 harden 的**整體**判定 PASS。
   - `provenance.json` 的 `repo_head` 等於現在的 HEAD。只看 `result.txt` 時，commit 新的 RTL 後單獨跑 `make eqy-soc` 仍會拿舊網表 PASS。
   - 檢查之前先刪掉自己的輸出目錄：被拒絕時不能留下上一次的 PASS 結果讓人誤讀。
   - negative test：每個下游步驟 × 3 種壞 run（不是 PASS、別的 commit、沒有紀錄）＋ positive control（PASS 且是 HEAD 的 run 要通過檢查、再因為缺檔而 FAIL，證明檢查不是永遠拒絕）。`neg_run_guard.py` 共 37 個案例（9 個下游步驟），3 秒。
5. **長時間 run 期間不要改主工作目錄**：harden 結束時的來源追溯會因為未提交的修改判 FAIL。要邊跑邊開發，就另開 worktree 與分支（`git worktree add -b dev ../<repo>-dev HEAD`），commit 在分支上，run 結束後在主目錄 `git merge --ff-only dev`。
6. **拿舊 run 測試新寫的 checker**（dev fixture）：
   - 下游檢查會拒絕舊 commit 的 run，所以開發測試要另建一個假的 run 目錄：真目錄，裡面每個檔案 symlink 到舊 run，`<run>_signoff/` 寫 PASS 與現在的 HEAD。
   - 不能把整個 run 目錄做成一個 symlink：腳本用 `Path.resolve()` 會跟著 symlink 找到舊 run 真正的 `_signoff` 目錄（Phase 4 實測，被正確拒絕）。
   - fixture 只用來測程式，結果不能當 signoff 證據；證據只來自規則 2 的乾淨 run。
7. **golden 與 commit 的先後**：更新 golden 的那個 run 一定來自更新前的 commit，所以那個 run 自己永遠不會通過下游檢查。流程是：harden（golden 比對 FAIL、其他檢查 PASS）→ 逐項檢視差異 → commit 新 golden → 乾淨 checkout 跑完整 regression，由它證明新 golden 可重現。
8. **`make -n` 不是完全不執行**：recipe 裡有 `$(MAKE)` 的那一行在 `-n` 下仍會執行（子 make 繼承 `-n`，只印出指令）。測 dispatch 用的 target 時要確認子 make 確實只有印。
9. **長 regression 之前，先把會在中途才出錯的東西提前抓**：
   - Python 只在執行到那一行時才報 `NameError`。重構時改了函式名稱，漏改的呼叫要等那個案例跑到才 FAIL（Phase 4：neg-pnr 的 P11 在 20 分鐘後才 FAIL）。`make py-check`（`scripts/check_py_names.py`）在幾秒內找出「讀到但檔案內沒定義的名稱」，排在 `make regress` 第 2 個 target，也在 `make smoke` 裡。它也找「寫檔前先清空」：`open(f, "w").write(... open(f).read() ...)` 先執行 `open(f, "w")` 把檔案清空，再讀，讀到空字串（Phase 3.5：neg-pnr 的 P17 在 regress 第 19 個 target、約 80 分鐘後才 FAIL）。Phase 5 擴大到同一行的任何順序、`with`、`h = open(p, "w")` 之後在 `h.close()` 前又開同一路徑、`file=`、`io.open`；路徑別名、另一種寫法組出的路徑、在 helper 函式裡讀，仍看不到。
   - 改過的下游步驟先在 dev fixture（規則 6）上全部跑一次，再開始乾淨 checkout 的長 run；這次預跑找到 P11，省掉一次約 2 小時的重跑。改過的 negative test 也一樣：Phase 3.5 改寫了 P17 卻沒先跑，乾淨 checkout 的 regress 第 1 次因此 FAIL（「已知陷阱」同一列第 2 次發生）。
   - 預跑時多個步驟同時跑會互相拖慢，有牆鐘時限的步驟（GL 模擬）可能逾時；逾時的要單獨重跑確認（`gate-level-simulation` 規則 6）。
10. **等長時間 run 結束，用 PID，不用字串比對**：
    - `pgrep -f <字串>` 也會比到等待腳本自己的 shell（它的命令字串含同一個字串），等待永遠不結束，或把多個 PID 交給 `kill`。macOS 的 `pgrep` 用 extended regex，`a\|b` 是字面的 `|`，不是「或」（要寫 `a|b`）。
    - 從 log 判斷結果時比對整行的開頭：`regress: PASS` 也會比到 `[regress] regress-rtl: PASS ... regress: PASS 30/30` 那一行，要比 `regress: PASS <n>/<n>` 或 `^\[regress\] <target>: `。
    - 做法：開跑時記下 PID（`$!`），`while ps -p <pid> >/dev/null; do sleep 60; done`，結束後再讀 log 的總結行。Claude Code 的背景指令有時限（最長 2 小時），超過就以同一個 PID 重新等待，不要重開 run。

## 已知陷阱

| 陷阱 | 對策 | 出處 |
|---|---|---|
| 開發目錄有舊的建置產物，缺依賴的 target 在開發目錄照樣 PASS | 乾淨 checkout 跑；對每個忽略版控的目錄 grep 誰在讀它 | 第二次 `make phase3`（`gl-soc` 沒依賴 `fw`） |
| 新寫或改寫的 negative test 沒單獨跑過就加進 phase target | 先單獨跑完一次（規則 9） | 第三次 `make phase3`（`neg_gl_soc.py`）；Phase 3.5 `make regress` 第 1 次（neg-pnr P17） |
| 來源追溯只比版本字串 | 比內容（規則 3） | Phase 3 獨立審查 |
| 下游拿過期的 run | `run_guard.py`（規則 4） | Phase 3 獨立審查 |
| 長 run 中改了檔案，結束時來源追溯 FAIL | 另開 worktree（規則 5） | Phase 4 |
| 函式改名後漏改的呼叫，要跑到那一案才 `NameError` | `make py-check`（規則 9） | Phase 4 預跑（neg-pnr P11） |
| 一次乾淨 run 與 golden 完全相同，就當作流程可重現 | 不可重現的那一步（多執行緒 detailed routing）產生的 metrics 先逐一分類（`signoff-checker-qualification` 規則 5）；完全相同可能只是剛好 | Phase 4 regress 1 434/434 相同，regress 2 有 1 個中間數字不同而 FAIL |
| macOS 的 Spotlight 會索引 `runs/` 裡幾 GB 的報告檔：平常占兩個核心，多個 worktree 同時有新 run 時開到約 10 個 `mdworker`（load 17–21） | 有牆鐘時限的步驟要留足餘裕（`gate-level-simulation` 規則 6）；長 run 時注意 `mds` 的 CPU；可把 repo 與 worktree 排除在索引外（系統設定 → Spotlight，使用者決定） | Phase 4（`ps` 觀察；regress 3 因此 FAIL） |

## 用完後

1. 新的現象寫進「經驗紀錄」；同一現象兩次或實驗確認後搬進規則。
2. 加了新的下游步驟，就把它加進 `run_guard.py` 的使用者與 `neg_run_guard.py` 的 `STEPS`。
3. 換 PDK 版本：重新產生 `env/pdk_content.sha256`（`provenance.py --make-pdk-content <out> --from-tarballs .tools/pdk-cache/sky130-<hash>`），並更新 `toolchain.md`。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | Phase 4 開發 | `neg_provenance.py` 的 positive control FAIL：clone 裡沒有 `env/pdk_content.sha256` | 已驗證：negative test 從 HEAD clone，新檔還沒 commit | 先在本機 commit（不推）再測 | `runs/neg_provenance/clean.log` |
| 2026-10-04 | Phase 4 開發 | dev fixture 整個 symlink 到舊 run，下游檢查仍讀到舊 run 的 `_signoff` | 已驗證：`Path.resolve()` 跟著 symlink | fixture 改成真目錄＋逐檔 symlink（規則 6） | `dv/gl_soc/run_gl_soc.py` |
| 2026-10-04 | Phase 4 第 1 次 harden-soc | 要在 run 期間改文件與測試 | 已驗證：結束時的來源追溯會 FAIL | 另開 worktree `p4dev`（規則 5） | `git worktree list` |
| 2026-10-04 | Phase 4 預跑（dev fixture） | `[FAIL] P11: expected FAIL at case error: NameError("name 'gds_add_met2' is not defined")`，`neg-pnr: FAIL 26/27` | 已驗證：`gds_add_met2` 改成 `gds_add_box` 時漏改 P11 | 改呼叫；新增 `make py-check`，對修正前的檔案確認會 FAIL；單獨重跑 P11 PASS | `runs/dev5_neg_pnr.log` |
| 2026-10-04 | Phase 4 `make regress` 第 2 次 | 12/25 PASS 後 harden-soc FAIL（golden 一個中間輪 DRC 數 11 → 14），第 1 次同設定是 434/434 相同 | 已驗證：多執行緒 detailed routing 不可重現，這次波及繞線器中間各輪的 DRC 數 | 給誤差（使用者決定），補 P31，乾淨 checkout 跑第 3 次 | `signoff/golden/soc_top/README.md` |
| 2026-10-04 | Phase 4 `make regress` 第 3 次 | 16/25 PASS 後 gl-soc-powered FAIL（一支 gate-level 測試超過牆鐘時限）；harden-soc 這次 434/434 與 golden 相同，另有一次已知的 GRT-0229 重試 | 已驗證：Spotlight 負載＋gate-level 時限照 RTL 速度算 | `gl_timeout`，乾淨 checkout 跑第 4 次 | `runs/p4_regress_clean3.log` |
| 2026-10-05 | Phase 3.5 乾淨 checkout 的 `make regress` | 等待腳本三次出錯：`pgrep -f` 比到自己的 shell、`\|` 沒有「或」的作用、`regress: PASS` 比到 regress-rtl 那一行而提早結束；另有一次背景指令 2 小時到期 | 已驗證（`pgrep -f 'x\|sleep 30'` 找不到 `sleep 30`，`'x|sleep 30'` 找得到） | 規則 10：用 PID 等待，比對整行開頭 | `runs/p35_regress_clean1.log` |
| 2026-10-05 | Phase 3.5 `make regress` 第 1 次（乾淨 checkout，`38e85cb`） | 18/25 PASS 後 neg-pnr FAIL 32/33：`[FAIL] P17: expected FAIL at case error: RuntimeError('injection point not found: the dout0 rising_edge arc')`；P17 目錄裡複製的 tt .lib 是 0 byte | 已驗證：`open(f, "w").write(edit_once(open(f).read(), ...))` 先清空再讀；`ccc536c` 改寫 P17 後沒有先跑過 | P17 先讀再寫；`make py-check` 加這個寫法的檢查（舊版 neg_pnr.py 第 756 行被抓到、自我測試改錯時 FAIL）；P00＋P17 在 regress 1 的 run 上 2/2；乾淨 checkout 重跑 | `scripts/check_py_names.py`、`pnr/soc_top/neg_pnr.py` |
| 2026-10-07 | Phase 5 Hazard3：實驗 A（從第 4 次 run 第 43 步之後接續）與第 5 次 harden（從頭跑） | 兩者到第 43 步為止的設定相同（第 5 次多的設定只影響第 44 步），`ResizerTimingPostGRT` 的修復結果與 signoff STA 數字完全相同 | 已驗證：這兩次從頭跑與從 checkpoint 接續的結果一樣，detailed routing 也剛好相同；多執行緒繞線仍不保證每次相同（`signoff-checker-qualification` 規則 5） | 單步實驗可以從 checkpoint 接續，再用完整 harden 確認 | `runs/p5_h3_exp_postgrt_slew/`；p5h3 worktree `runs/p5_h3_h5/` |
| 2026-10-07 | Phase 5 Hazard3 第 6 次 harden（`d6f3074`，flow 設定與第 5 次相同） | golden 比對 61 個 metric 不同（antenna diode 94 對 100、stdcell 30,469 對 30,474、`iter:7` 的 key 不見），signoff 全部 PASS | 已驗證：逐步比對 DEF，第 41 步 `RepairDesignPostGRT` 修完的 DEF 相同、log 到最後一次 `global_route` 的結果之前都相同，那次 global routing 的線長與 guide 不同（1,146,538 對 1,146,421 µm）；用第 6 次自己的輸入單步重跑 4 次都與第 5 次相同，第 4、5 次 harden 也相同，7 次裡 1 次不同。推測與同一步隨機中止的 `GRT-0229` 同源，未驗證 | detailed routing 以前也有偶發不能重現的一步；處理方式提給使用者 | p5h3 worktree `runs/soc_top_hazard3_signoff/criteria_review.md`；單步重跑 `rerun41`（session 暫存，未保存） |
