---
name: phase-exit-review
description: 一個 Phase（階段）收尾時使用：對照 project-plan.md 的 exit criteria 整理證據（只用乾淨 checkout 的最後一次 run）、寫 docs/phase_exit/phase<N>.md、列出與計畫不同的做法與帶到下一階段的已知限制、請沒參與實作的 agent 做獨立審查、記錄使用者決定，以及收尾時分析本階段任務是否需要新 skill、逐一對照每個 skill 與 README 有沒有寫回、推送規則。Use when closing a project phase (exit criteria evidence, deviations from plan, known limitations, independent review, user decisions, skill and README write-back).
---

# Phase exit review 與獨立審查

本 repo 實例：`docs/phase_exit/phase0.md`–`phase4.md`。checker 的品質規則看 `signoff-checker-qualification`；端到端 run 怎麼跑看 `flow-regression-reproducibility`。

## 規則（已驗證）

1. **exit criteria 照抄 `project-plan.md` §8**，再加上前一階段 exit review 帶過來的項目（「已知限制」與「留到下一階段」逐條對照，**也包含再前一個階段沒結的項目**（Phase 5 漏了 Phase 3.5 的限制 1–15）；每一條「沒變」要在新設計上重新量過才算，不能照抄（Phase 5：IR「供電位置是假設」原本寫沒變，實測 Hazard3 已超過上限）；Phase 2 延到 Phase 3 的來源追溯，到 Phase 3 收尾才發現還沒做，`signoff-checker-qualification` 規則 9）。
2. **證據只來自乾淨 checkout 的端到端 run**：寫明 commit、開始與結束時間、exit code、跑了幾次、前幾次為什麼沒跑完。開發目錄補跑的結果不算（`flow-regression-reproducibility` 規則 2）。
3. **每個數字都要對得回證據檔，而且用對 metric 的意思**：
   - Phase 3 文件核對找到 6 個寫錯的數字或事實（案例數、clock skew、使用率、cell 組成、最長線的來源、密度）。
   - 容易誤讀的彙總值：`power__total` 是最後寫入的 corner；`clock__skew__worst_setup` 是各 corner 的最小值；DRV 計數是各 corner 的最大值（`librelane-run-debug` 規則 4）。
4. **章節**（Phase 3 的版本）：結論與執行紀錄 → exit criteria 表（每列：結果、證據）→ signoff metrics → 面積與時序 → 怎麼收斂 → 可重現性（每個 run 與 golden 比對）→ checker qualification（每個植入錯誤：植入、預期的 checker、結果、與計畫的差異）→ 本階段找到並修正的 checker 問題 → 與計畫不同的地方（編號）→ 已知限制（編號，每條寫為什麼不影響本次結果，或缺什麼）→ 使用者決定 → 獨立審查 → 交付物。
5. **獨立審查用兩個沒參與實作的 agent**：一個逐條核對文件與證據（數字、說法），一個找 checker 漏洞（要做實驗，不能只讀程式）。審查找到的問題：修正並重跑，或列為已知限制並寫理由；沒有重跑就不能寫「已修正」。
6. **要使用者決定的事**（放寬或收緊門檻、接受風險、改計畫）：用選擇題問，選項附建議與理由；答案連同日期寫進「使用者決定」，並同步到相關文件。
7. **寫法**：給人看的內容用白話與 IC 業界術語，名詞第一次出現就解釋；數字附出處；推測要標明（使用者的全域規則）。
8. **分析本階段的重大任務，沒有對應 skill 的就新建**（使用者 2026-10-04：「這個 phase 4 的重要任務也要分析建立對應的skill」）：列出本階段做過的重大任務，逐一對照既有 skill；涵蓋得到的寫回該 skill，涵蓋不到的新建（Phase 4 新建了 `flow-regression-reproducibility`、`multicorner-sta`、`dv-directed-tests` 與本 skill）。新建或改名時同步更新 README 的 skill 一節與 `CLAUDE.md`。
   - **對照方法**：先看每個 skill 的經驗紀錄有沒有本階段的列（`git diff --stat <上一階段結案 commit> HEAD -- .claude/skills`）；再拿 exit 文件的「收斂過程」與設計的設定表逐項找對應的 skill。沒有更新的 skill 要說得出理由。Phase 4 第一輪只從任務清單對照，漏了 CTS（SRAM clock 的 latency 對齊、clock pin 線切段）與 resizer 餘量，使用者結案後再問才補上。
9. **收尾**：README 的狀態行與 roadmap、專案記憶、各 skill 的經驗紀錄與規則回寫；有改到的 skill，README 的說明與 `SKILL.md` 的 `description` 也要跟著改，並跑 `make skill-check`（使用者 2026-10-04：「skill更新時README說明也要更新」）。推送只在使用者明確要求時做，兩個 remote 都推並用 `git ls-remote` 確認；repo 是 public，推送前檢查本機絕對路徑與機密。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | Phase 3 收尾 | Phase 2 延過來的來源追溯差點漏做 | 已驗證：沒有逐條對照上一階段的限制 | 規則 1 | `docs/phase_exit/phase3.md` |
| 2026-10-04 | Phase 3 獨立審查 | 文件 6 個數字或事實寫錯；5 個 checker 漏洞 | 已驗證（重新核對證據與實驗） | 文件更正；漏洞列為已知限制 12–16，Phase 4 開頭修 | `docs/phase_exit/phase3.md`、`docs/notes/phase3_review/` |
| 2026-10-04 | Phase 4 收尾 | 乾淨 checkout 的 `make regress` 跑了 4 次才 PASS：第 1 次 PASS 後依審查修 checker；第 2 次多執行緒繞線的中間數字不同；第 3 次 gate-level 模擬被 Spotlight 負載拖過牆鐘時限 | 已驗證：後兩個是前幾次乾淨 run 剛好沒遇到的不可重現與負載問題 | 結案證據只用最後一次（規則 2），前幾次寫明為什麼不算；改比對規則先問使用者（規則 6）；時程要預留至少兩次完整 regression | `docs/phase_exit/phase4.md` |
| 2026-10-04 | Phase 4 結案後整理 skill 說明（使用者：「skill更新時README說明也要更新」） | 本 skill 的 `description` 含「英文冒號＋空格」，不是合法的 YAML；README 的 skill 說明多處停在 Phase 3（案例數、corner 數、待補項目）；drv-timing-closure 把 LibreLane 預設的判定 corner 寫錯 | 已驗證：`yaml.safe_load` 報錯；獨立 agent 逐一對照 SKILL.md 與程式碼 | 新增 `make skill-check`（放進 smoke）、CLAUDE.md 規則 5、本 skill 規則 9；README 改成「依情況找 skill」表＋流程位置圖＋每個 skill 的說明；盲測：只看 description，24 個情況的第一選擇都對 | `scripts/check_skills.py` |
| 2026-10-05 | Phase 3.5 收尾 | 乾淨 checkout 的 `make regress` 跑 2 次：第 1 次 neg-pnr P17 FAIL（植入程式先清空檔案再讀；改寫後沒先跑）。獨立審查在 regress 2 執行期間進行（只讀、只做幾秒的實驗）：文件漏列一個讀取失敗條件（室溫），其他 21 項更正；checker 漏洞 12 個，獨立重算確認沒有假 PASS | 已驗證 | regress 1 不算數並寫明原因；審查與 regress 同時進行省下約 1 小時；漏洞依使用者決定列為已知限制、下一個 Phase 開頭修；頭號風險的範圍擴大要直接告訴使用者 | `docs/phase_exit/phase3_5.md` |
| 2026-10-08 | Phase 5 收尾 | 兩輪乾淨 regress 都 PASS 後，獨立審查仍找到：文件 17 項（判定說法不誠實、Phase 3.5 限制沒延續、證據引用開發 worktree 的 run）、checker 漏洞 8 個；再實測 IR，Hazard3 最壞組合 25.75 mV 超過上限。三件事都要使用者決定，修完之後還要重 harden、重建 golden、再跑兩輪 regress | 已驗證：IR 用 Phase 4 方法重測，PDN 用 what-if | 規則 1 補：上一階段帶過來的「假設成立」也要在新設計上重新量，不能只抄過來（IR 在 Phase 4 是「沒變」，在 Phase 5 其實變差）；時程要預留「審查後修正、再跑一輪」 | `docs/phase_exit/phase5.md` |
| 2026-10-08 | Phase 5 收尾的時程 | 乾淨 regress 跑了三輪才結案：`7348fab`（PASS，之後獨立審查找到 8 個漏洞與 IR 超標）、`5aaf036`（修正後；PicoRV32 因版圖誤差清空而 FAIL）、`71b1454`（量樣本、訂誤差、加 GRT-0116 重試後兩輪都 PASS）。從第一次 PASS 到結案約一天，其中兩輪 regress 共約 4 小時、補樣本約 1 小時 | 已驗證 | 獨立審查要在第一輪乾淨 regress 之後馬上做，時程預留「修正 → 重新 harden 與建 golden → 再兩輪 regress」；清空誤差這類決定要預期會多一輪量樣本 | `docs/phase_exit/phase5.md`「正式 run」 |
