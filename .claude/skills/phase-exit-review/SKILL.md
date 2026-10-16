---
name: phase-exit-review
description: 一個 Phase（階段）收尾時使用：對照 project-plan.md 的 exit criteria 整理證據（只用乾淨 checkout 的最後一次 run）、寫 docs/phase_exit/phase<N>.md、追延後的項目（筆記裡「Phase N 才能處理」「之後會加」）、證據存到不會被覆蓋或消失的地方、與計畫不同時寫明原本防範什麼、現在由誰防範、已知限制引用放寬清單、決定改了要標出被取代的舊段落、開結案 regress 前先讓最後改過的 checker 在現有 run 上跑 positive control、排結案時程（至少兩輪乾淨 regress 加一輪修正，審查與 regress 同時進行）、請沒參與實作的 agent 獨立審查（找 checker 漏洞只審最後改過的）、記錄使用者決定，以及收尾清單（skill、README、流程文件與 AGENTS.md 同步，規則 10 稽核，清空 runs/todo.md，清理舊 worktree；專案結束清掉 runs/ 前用 make collect-evidence 把引用的佐證報告收進 docs/evidence/，推送）。Use when closing a project phase (exit criteria evidence, deviations from plan, known limitations, independent review, user decisions, skill and README write-back).
---

# Phase exit review 與獨立審查

本 repo 實例：`docs/phase_exit/phase0.md`–`phase7.md`（章節以 `phase7.md` 為準，規則 4）。checker 的品質規則看 `signoff-checker-qualification`；end-to-end run 怎麼跑看 `flow-regression-reproducibility`。

## 規則（已驗證）

1. **exit criteria 照抄 `project-plan.md` §8**，再加上前一階段 exit review 帶過來的項目（「已知限制」與「留到下一階段」逐條對照，**也包含再前一個階段沒結的項目**（Phase 5 漏了 Phase 3.5 的限制 1–15）；每一條「沒變」要在新設計上重新量過才算，不能照抄（Phase 5：IR「供電位置是假設」原本寫沒變，重新量過，Hazard3 已超過上限）；Phase 2 延到 Phase 3 的來源追溯，到 Phase 3 收尾才發現還沒做，`signoff-checker-qualification` 規則 9）。
   - **延後的項目要追到結**：收尾時，在本階段新增或改過的筆記、ADR 與 skill 裡找「Phase N 才能處理」「之後會加」「之後確認」「選定後再修」這類句子：先 `git diff --name-only <上一階段結案 commit> HEAD -- docs .claude/skills` 列出檔案，再對它們 `grep -n -E "Phase ?[0-9.]+ ?(才|再|會|確認|處理)|之後(會|再|確認|處理)|留到|待(補|確認|驗證)"`（2026-10-15 對 `docs/notes/signoff_criteria_soc_top.md` 試過，下面這例的兩行都找得到）。逐條對照：做完的附證據，沒做的列入已知限制或放寬清單；也逐條對照 `signoff-criteria`「不分析的項目清單」。這類決定在做出的當下就寫進 `runs/todo.md`，不要只寫在筆記。
     - 例：latch-up 標記 81/14 在 `signoff_criteria_soc_top.md:41`、`:118` 寫「Phase 7 確認」「Phase 7 才能處理」，到 Phase 7 結案都沒人對照，交付的 GDS 沒有這一層（`docs/notes/problem_review/verify_and_merge.md` 2.2）。Phase 6 另有三件延後的決定沒進待辦，其中一件讓第二輪 harden 白跑（`review_p6_7.md` P6-08）。
2. **證據只來自乾淨 checkout 從頭跑到底的 run**：寫明 commit、開始與結束時間、exit code、跑了幾次、前幾次為什麼沒跑完。main worktree 補跑的結果不算（`flow-regression-reproducibility` 規則 2）。
   - **開結案 regress 之前，最後改過的每支 checker 都要先在現有的 run 上跑一次 positive control**（沒植入時必須 PASS），植入錯誤的案例也要跑。兩次都是改了沒跑就開 regress：Phase 3.5 的 P17 改寫後先清空檔案再讀，Phase 6 的 `check_inputs.py --resolved` 對每個 run 都 FAIL。各浪費一輪 regress（Phase 6 兩輪共 76 分鐘）。
   - **不在 regression 裡的 negative test 與 target**（本 repo 是 `arvinsa-rtl-gds-flow.md` 4.8「不在 regression 裡、要另外跑的」，例如 `neg-char`、`ci-sram-ref`）：exit review 列出每一個最後一次跑的 commit、環境（main worktree 或乾淨 worktree）與結果；被測的程式在那之後改過，就在乾淨 checkout 補跑。兩次：Phase 5 起 `neg-char` N9–N16 只在 main worktree 跑過（放寬清單 S21）；Phase 6 `ad184f5` 改了 `check_char_lib.py` 之後沒有重跑，結案才補跑（`docs/notes/openram_phase6_bringup.md:270`）。目前沒有自動檢查：沒有東西比對被測程式與最後一次 PASS 時的版本；照 ADR-0020 決定 2 的做法，ADR-0021 決定 3 把它留到下一個專案做成 checker（例如 harden 開頭比對被測程式的 sha256）。
3. **每個數字都要對得回證據檔，而且用對 metric 的意思**：
   - Phase 3 文件核對找到 6 個寫錯的數字或事實（案例數、clock skew、使用率、cell 組成、最長線的來源、密度）。
   - 容易誤讀的彙總值：`power__total` 是最後寫入的 corner；`clock__skew__worst_setup` 是各 corner 的最小值，`clock__skew__worst_hold` 是各 corner 的最大值（最不負，不是最差）；DRV 計數是各 corner 的最大值（`librelane-run-debug` 規則 4）。
   - **證據在做的當下存到不會被覆蓋或消失的地方**，文件引用的就是那個路徑：小檔與實驗腳本放 `docs/notes/<主題>/`（進版控）；大檔放 main worktree 的 `runs/<實驗名>/`（不進版控，引用時註明）。`runs/` 不進版控，清理前要把文件引用到的報告類證據收進 repo 的 `docs/evidence/`（`make collect-evidence`，規則 9）；GDS、DEF、netlist、整個 run 目錄不收，靠 commit 重跑產生（使用者 2026-10-15：「主要是重要的佐證報告才收」，ADR-0021 決定 7）。不能引用：session scratchpad（session 結束就消失）；會被下一次 harden 覆蓋的 `runs/<tag>_signoff/`、`runs/<design>/`（先複製成另一個名稱，例如本 repo 的 `runs/p7_formal_signoff/`）；收尾後會刪的 worktree（規則 9 清理前先複製）；只在終端機看到的訊息（例如 precheck VM 的 `dmesg`，要存成檔）。算出來的比例或門檻，算式與輸入一起存。Phase 3、3.5、4、5、6、7 都發生過（`verify_and_merge.md` B3）：Phase 6 licon.14 容許面積比例的計算沒存檔；Phase 7 VM OOM 的 `dmesg` 只在終端機、開發量測只在已消失的 scratchpad、knowledge 檔引用的 `runs/user_project_wrapper_signoff/` 被下一次 harden 覆蓋，審查因此 4 列無法核對（`runs/p7_review/doc_check.md`、`review_p6_7.md` P7-39）。
4. **章節**（Phase 7 的版本，`docs/phase_exit/phase7.md`）：結論 → 正式 run（commit、開始與結束時間、exit code、跑了幾次、前幾次為什麼不算）→ exit criteria 表（每列：結果、證據）→ signoff 結果 → 收斂過程 → 帶進本階段的項目（前幾階段的已知限制逐條，規則 1）→ 可重現性（每個 run 與 golden 比對；不在 regression 裡的 target 最後一次在哪裡跑，規則 2）→ checker qualification（每個植入錯誤：植入、預期的 checker、結果、與計畫的差異）→ 本階段找到並修正的 checker 問題 → 與計畫不同的地方（編號）→ 已知限制（編號，每條寫為什麼不影響本次結果，或缺什麼；放寬項目引用放寬清單，規則 10）→ 獨立審查（文件核對、找 checker 漏洞；有做流程回顧也放這裡）→ 使用者決定 → Skill 分析（規則 8，含規則 10 稽核：本階段每個工具缺陷的四項對策齊不齊）→ 交付物。
   - **與計畫不同的地方，每一項寫兩點**：原本那一項防範什麼（哪一類錯誤會被抓到）、現在改由誰防範（哪支 checker 或哪個測試）。沒有替代的，列入已知限制並記進放寬清單；改檢查方式本身不算放寬，放寬清單不會自動收到它。兩次：Phase 1 改了 R02 的測試後，memtest 的上半部就沒有測試涵蓋了（`phase1.md:43`）；Phase 3 P07、P12 改成只測 checker、EQY 範圍縮小（`phase3.md:138–153`）（`review_p0_35.md` 建議 4）。
5. **獨立審查用兩個沒參與實作的 agent**：一個逐條核對文件與證據（數字、說法），一個找 checker 漏洞（要做實驗，不能只讀程式）。審查找到的問題：修正並重跑，或列為已知限制並寫理由；沒有重跑就不能寫「已修正」。
6. **要使用者決定的事**（放寬或收緊門檻、接受風險、改計畫）：用選擇題問，選項附建議與理由；答案連同日期寫進「使用者決定」，並同步到相關文件。
7. **寫法**：給人看的內容用白話與 IC 業界術語，名詞第一次出現就解釋；數字附出處；推測要標明（使用者的全域規則）。
8. **分析本階段的重大任務，沒有對應 skill 的就新建**（使用者 2026-10-04：「這個 phase 4 的重要任務也要分析建立對應的skill」）：列出本階段做過的重大任務，逐一對照既有 skill；涵蓋得到的寫進該 skill，涵蓋不到的新建（Phase 4 新建了 `flow-regression-reproducibility`、`multicorner-sta`、`dv-directed-tests` 與本 skill）。新建或改名時同步更新 README 的 skill 一節與 `CLAUDE.md`。
   - **對照方法**：先看每個 skill 的經驗紀錄有沒有本階段的列（`git diff --stat <上一階段結案 commit> HEAD -- .claude/skills`）；再拿 exit 文件的「收斂過程」與設計的設定表逐項找對應的 skill。沒有更新的 skill 要說得出理由。Phase 4 第一輪只從任務清單對照，漏了 CTS（SRAM clock 的 latency 對齊、clock pin 線切段）與 resizer 的 margin，使用者結案後再問才補上。
9. **收尾清單**（Phase 7 的版本）：
   - README 的狀態行與 roadmap、專案記憶。
   - 各 skill 的經驗紀錄與規則回寫；有改到的 skill，README 的說明與 `SKILL.md` 的 `description` 也要跟著改，並跑 `make skill-check`（使用者 2026-10-04：「skill更新時README說明也要更新」）。
   - 流程文件 `arvinsa-rtl-gds-flow.md` 同步：本階段流程的步驟、順序、checker 或 negative test 有改，同一個 commit 更新它；`AGENTS.md` 只指回 `CLAUDE.md` 與流程文件，確認沒有另寫規則（`CLAUDE.md` 規則 8）。
   - 規則 10 稽核：本階段每個工具缺陷，逐條確認症狀、怎麼發現、怎麼繞過、怎麼防止再發生四項都有，寫在 exit review 的「Skill 分析」（`CLAUDE.md` 規則 10；例：`phase7.md`「規則 10 稽核」）。
   - 清空 `runs/todo.md`（`CLAUDE.md` 規則 11）；清空前確認還沒結的項目都已進 exit review 的已知限制或放寬清單（規則 1）。
   - 舊 worktree 與 negative test 中間檔案的清理：先把引用的證據複製到 main worktree（規則 3），再照 `flow-regression-reproducibility` 規則 16 做（刪 worktree 前列出目錄與大小請使用者確認）。專案結束、要清掉 `runs/` 與所有 worktree 時，先跑 `make collect-evidence` 把報告類證據收進 `docs/evidence/` 並提交（規則 3）。
   - 推送只在使用者明確要求時做，兩個 remote 都推並用 `git ls-remote` 確認；repo 是 public，推送前檢查本機絕對路徑與機密。
10. **收尾的 checker 漏洞審查只審本 Phase 最後改過的 checker；其他 checker 在寫完時就審過**（提早檢查 E3，流程回顧 ADR-0020；做法在 `signoff-checker-qualification` 規則 12）。
    - 為什麼：審查都排在收尾，Phase 4 到 7 每次都找到 7–12 個漏洞（Phase 7 是 8 個加 1 個缺口），修完要整套 regression 重跑，經驗紀錄的 Phase 5、6 兩列就是這樣多跑的輪數。
    - 做法：收尾時先列出本 Phase 新增或改過的 checker，確認每支都有寫完時的審查紀錄；沒有的補做審查，最後改過的（審查之後又改的）再審一次。文件核對（規則 5 的第一個 agent）照舊全部做。
    - 已知限制裡的每一項放寬或補償，引用放寬清單（`docs/relaxation_register.md`，`signoff-criteria`「提早檢查」E1；ADR-0020 決定 3），並核對放寬清單的「依據的設計」是不是本 Phase 的設計（規則 1 的「沒變要重新量過」）。

11. **決定改了，舊段落要標成已被取代、其他文件一起改；比較數字要同條件；skill 不寫會變的數字**（`docs/notes/problem_review/verify_and_merge.md` B5；`review_p6_7.md` 建議 4、`review_skills.md` Q10）：
    - 新決定取代舊決定時，在同一個 commit：舊決定的段落標「已被 ADR-xxxx 決定 N 取代」；grep 舊數字與舊說法出現的其他文件（skill、流程文件、golden README、knowledge 檔、exit review），一起改。ADR 的實作和選項內容不同時，在實作段說明偏離。兩次：Phase 6 文件核對（`phase6.md:225–233`）、Phase 7 文件核對（`runs/p7_review/doc_check.md:7–33`，例如被取代的 50 mV 上限、密度 55% 的前文沒標）。
    - 兩個數字放在一起比時，寫明兩邊的條件（corner、電流來源、電壓源位置、layout 版本）；條件不同就不比，或寫明不同在哪（Phase 7 的「8.4 → 45 mV」是不同條件的兩個數字，`review_p6_7.md` P7-38）。
    - skill 與流程文件不寫會隨程式變的數字（negative test 的案例數、情境數、下游步驟數），改成指向腳本裡的清單或 make target 的總結行（例如 `neg-run-guard: PASS <n>/<n>`）。`review_skills.md` Q10 找到 9 處數字已經對不上（例如 `flow-regression-reproducibility` 寫 `neg-regress` 5 個情境，實際 8 個）。收尾時對改過的 skill 再 grep 一次「個案例」「個情境」。
12. **收尾的順序與時程**：
    - 順序：最後改過的 checker 先在現有的 run 上跑 positive control 與植入錯誤（規則 2）→ 開結案 regress → regress 執行期間做獨立審查（規則 5；審查只讀、只做幾分鐘的實驗，不動 regress 的 worktree）→ 修正 → 修正版先套進已跑完的 worktree、在它自己的 run 上跑 positive control → 再開下一輪。審查與 regress 同時進行出現兩次，各省一輪等待（經驗紀錄 2026-10-05：約 1 小時；2026-10-14）。
    - 時程：至少預留兩輪乾淨 regress，再加一輪審查後的修正（出現三次：Phase 4 跑了 4 次、Phase 5 三輪、Phase 7 兩輪加修正；經驗紀錄 2026-10-04、2026-10-08、2026-10-14）。同時跑幾條 regress，依 `flow-regression-reproducibility` 規則 13、14 先算記憶體與磁碟。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | Phase 3 收尾 | Phase 2 延過來的來源追溯差點漏做 | 已驗證：沒有逐條對照上一階段的限制 | 規則 1 | `docs/phase_exit/phase3.md` |
| 2026-10-04 | Phase 3 獨立審查 | 文件 6 個數字或事實寫錯；5 個 checker 漏洞 | 已驗證（重新核對證據與實驗） | 文件更正；漏洞列為已知限制 12–16，Phase 4 開頭修 | `docs/phase_exit/phase3.md`、`docs/notes/phase3_review/` |
| 2026-10-04 | Phase 4 收尾 | 乾淨 checkout 的 `make regress` 跑了 4 次才 PASS：第 1 次 PASS 後依審查修 checker；第 2 次多執行緒繞線的中間數字不同；第 3 次 gate-level 模擬被 Spotlight 負載拖過 wall-clock 時限 | 已驗證：後兩個是前幾次乾淨 run 剛好沒遇到的不可重現與負載問題 | 結案證據只用最後一次（規則 2），前幾次寫明為什麼不算；改比對規則先問使用者（規則 6）；時程要預留至少兩次完整 regression | `docs/phase_exit/phase4.md` |
| 2026-10-04 | Phase 4 結案後整理 skill 說明（使用者：「skill更新時README說明也要更新」） | 本 skill 的 `description` 含「英文冒號＋空格」，不是合法的 YAML；README 的 skill 說明多處停在 Phase 3（案例數、corner 數、待補項目）；drv-timing-closure 把 LibreLane 預設會判 FAIL 的 corner 寫錯 | 已驗證：`yaml.safe_load` 解析失敗；獨立 agent 逐一對照 SKILL.md 與程式碼 | 新增 `make skill-check`（放進 smoke）、CLAUDE.md 規則 5、本 skill 規則 9；README 改成「依情況找 skill」表＋流程位置圖＋每個 skill 的說明；盲測：只看 description，24 個情況的第一選擇都對 | `scripts/check_skills.py` |
| 2026-10-05 | Phase 3.5 收尾 | 乾淨 checkout 的 `make regress` 跑 2 次：第 1 次 neg-pnr P17 FAIL（植入程式先清空檔案再讀；改寫後沒先跑）。獨立審查在 regress 2 執行期間進行（只讀、只做幾秒的實驗）：文件漏列一個讀取失敗條件（室溫），其他 21 項更正；checker 漏洞 12 個，獨立重算確認沒有 false pass（實際有錯、checker 卻判 PASS） | 已驗證 | regress 1 不算數並寫明原因；審查與 regress 同時進行省下約 1 小時；漏洞依使用者決定列為已知限制、下一個 Phase 開頭修；頭號風險的範圍擴大要直接告訴使用者 | `docs/phase_exit/phase3_5.md` |
| 2026-10-08 | Phase 5 收尾 | 兩輪乾淨 regress 都 PASS 後，獨立審查仍找到：文件 17 項（結論的說法不誠實、Phase 3.5 限制沒延續、證據引用開發 worktree 的 run）、checker 漏洞 8 個；再重新量 IR，Hazard3 的 worst-case 組合 25.75 mV 超過上限。三件事都要使用者決定，修完之後還要重 harden、重建 golden、再跑兩輪 regress | 已驗證：IR 用 Phase 4 方法重測，PDN 用 what-if | 規則 1 補：上一階段帶過來的「假設成立」也要在新設計上重新量，不能只抄過來（IR 在 Phase 4 是「沒變」，在 Phase 5 其實變差）；時程要預留「審查後修正、再跑一輪」 | `docs/phase_exit/phase5.md` |
| 2026-10-08 | Phase 5 收尾的時程 | 乾淨 regress 跑了三輪才結案：`7348fab`（PASS，之後獨立審查找到 8 個漏洞與 IR 超標）、`5aaf036`（修正後；PicoRV32 因 layout 誤差清空而 FAIL）、`71b1454`（量樣本、訂誤差、加 GRT-0116 重試後兩輪都 PASS）。從第一次 PASS 到結案約一天，其中兩輪 regress 共約 4 小時、補樣本約 1 小時 | 已驗證 | 獨立審查要在第一輪乾淨 regress 之後馬上做，時程預留「修正 → 重新 harden 與建 golden → 再兩輪 regress」；清空誤差這類決定要預期會多一輪量樣本 | `docs/phase_exit/phase5.md`「正式 run」 |
| 2026-10-11 | Phase 6 結案 regress 第 1 次（`904e18e`） | 兩輪都在 harden-soc FAIL：`check_inputs.py` 的 `resolved` 列對每個 run 都 FAIL；layout 與 golden 逐項相同。獨立審查的修正（`37c99b4`）改了這支 checker，之後只跑過植入錯誤的案例（照樣「抓到」），沒跑過完整 harden | 已驗證：修正版在兩個 worktree 的 run 上 PASS，舊版讓新的 P00 FAIL | 和 Phase 3.5 的 P17 同類（改了沒跑就開 regress），第二次出現，寫進規則 2；checker 修正見 `signoff-checker-qualification` | `docs/phase_exit/phase6.md`「本階段找到並修正的 checker 問題」6、`runs/p6close_attempt1/` |
| 2026-10-14 | Phase 7 結案（第一輪 `84fe505`：Hazard3 30/30、wrapper 18/18、PicoRV32 31/31） | 審查在第一輪 regress 期間做（只讀、幾分鐘內的實驗），找到 8 個漏洞與文件 28 列問題；使用者選全部修正、三條重跑。修正後先把 patch 套進已跑完的 worktree、在它自己的 run 上跑 positive control，抓到一個修正時改壞的 checker（第二次同類）。使用者另外要求流程回顧（哪些事太晚才看），三個 agent 分段回顧後寫成 19 條提早檢查（ADR-0020） | 已驗證 | 規則 2 的做法再次有效（patch 套進舊 worktree 跑，避開跨 worktree 的路徑差異）；審查與 regress 同時跑省一輪等待 | `docs/phase_exit/phase7.md`、`docs/notes/flow_retro/` |
| 2026-10-15 | Phase 0–7 問題總檢討（ADR-0021） | 四份審查與反向驗證找到本 skill 該補的：延後的項目漏接（latch-up 標記 81/14）、證據放在會消失的地方（Phase 3–7 都有）、決定改了前文沒同步（兩次）、與計畫不同時沒寫哪一類錯誤因此不再被檢查（兩次）、不在 regression 裡的 negative test 過期（兩次）、收尾時程與並行（三次、兩次）、章節與收尾清單停在 Phase 3 | 已驗證（`docs/notes/problem_review/verify_and_merge.md` 1.1 第 4、5 項，1.2 R3、R8，1.3 第 2、4、5、10 項，1.4 第 13 項，2.2） | 規則 1–4、9 補充，新增規則 11、12；改 `CLAUDE.md` 規則 11 與新 checker 由使用者另外決定（ADR-0021） | `docs/notes/problem_review/`、ADR-0021 |
