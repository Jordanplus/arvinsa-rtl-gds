---
name: phase-exit-review
description: 一個 Phase（階段）收尾時使用：對照 project-plan.md 的 exit criteria 整理證據、寫 docs/phase_exit/phase<N>.md、列出與計畫不同的做法與帶到下一階段的已知限制、請沒參與實作的 agent 做獨立審查、記錄使用者決定，以及收尾後的 README、記憶、skill 回寫與推送。Use when closing a project phase: exit criteria evidence, deviations from plan, known limitations, independent review, and user decisions.
---

# Phase exit review 與獨立審查

本 repo 實例：`docs/phase_exit/phase0.md`–`phase3.md`。checker 的品質規則看 `signoff-checker-qualification`；端到端 run 怎麼跑看 `flow-regression-reproducibility`。

## 規則（已驗證）

1. **exit criteria 照抄 `project-plan.md` §8**，再加上前一階段 exit review 帶過來的項目（「已知限制」與「留到下一階段」逐條對照；Phase 2 延到 Phase 3 的來源追溯，到 Phase 3 收尾才發現還沒做，`signoff-checker-qualification` 規則 9）。
2. **證據只來自乾淨 checkout 的端到端 run**：寫明 commit、開始與結束時間、exit code、跑了幾次、前幾次為什麼沒跑完。開發目錄補跑的結果不算（`flow-regression-reproducibility` 規則 2）。
3. **每個數字都要對得回證據檔，而且用對 metric 的意思**：
   - Phase 3 文件核對找到 6 個寫錯的數字或事實（案例數、clock skew、使用率、cell 組成、最長線的來源、密度）。
   - 容易誤讀的彙總值：`power__total` 是最後寫入的 corner；`clock__skew__worst_setup` 是各 corner 的最小值；DRV 計數是各 corner 的最大值（`librelane-run-debug` 規則 4）。
4. **章節**（Phase 3 的版本）：結論與執行紀錄 → exit criteria 表（每列：結果、證據）→ signoff metrics → 面積與時序 → 怎麼收斂 → 可重現性（每個 run 與 golden 比對）→ checker qualification（每個植入錯誤：植入、預期的 checker、結果、與計畫的差異）→ 本階段找到並修正的 checker 問題 → 與計畫不同的地方（編號）→ 已知限制（編號，每條寫為什麼不影響本次結果，或缺什麼）→ 使用者決定 → 獨立審查 → 交付物。
5. **獨立審查用兩個沒參與實作的 agent**：一個逐條核對文件與證據（數字、說法），一個找 checker 漏洞（要做實驗，不能只讀程式）。審查找到的問題：修正並重跑，或列為已知限制並寫理由；沒有重跑就不能寫「已修正」。
6. **要使用者決定的事**（放寬或收緊門檻、接受風險、改計畫）：用選擇題問，選項附建議與理由；答案連同日期寫進「使用者決定」，並同步到相關文件。
7. **寫法**：給人看的內容用白話與 IC 業界術語，名詞第一次出現就解釋；數字附出處；推測要標明（使用者的全域規則）。
8. **收尾**：README 的狀態行與 roadmap、專案記憶、各 skill 的經驗紀錄與規則回寫。推送只在使用者明確要求時做，兩個 remote 都推並用 `git ls-remote` 確認；repo 是 public，推送前檢查本機絕對路徑與機密。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | Phase 3 收尾 | Phase 2 延過來的來源追溯差點漏做 | 已驗證：沒有逐條對照上一階段的限制 | 規則 1 | `docs/phase_exit/phase3.md` |
| 2026-10-04 | Phase 3 獨立審查 | 文件 6 個數字或事實寫錯；5 個 checker 漏洞 | 已驗證（重新核對證據與實驗） | 文件更正；漏洞列為已知限制 12–16，Phase 4 開頭修 | `docs/phase_exit/phase3.md`、`docs/notes/phase3_review/` |
