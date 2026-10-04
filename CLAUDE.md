# arvinsa-rtl-gds：給 Claude Code 的專案規則

## 流程 skill 與經驗累積

`.claude/skills/` 有 19 個流程 skill（清單與每個的說明在 README「Claude Code skills」一節）。

1. 做到 skill 涵蓋的任務（LibreLane 執行除錯、checker／golden、時序與 DRV、macro 整合、DRC、EQY、antenna、CTS、PDN／IR、LVS、gate-level 模擬、floorplan 與壅塞、SDC 約束、合成與 lint、signoff 條件的推導、一鍵 regression 與來源追溯、多 corner STA、directed 測試補缺口、Phase exit review）時，先讀對應的 `SKILL.md`，照裡面的規則與已知陷阱做。
2. 任務做完，把新遇到的現象追加到該 skill 的「經驗紀錄」表：日期、run、原文訊息、根因（標明已驗證或推測）、處理、證據路徑。推測的根因不能寫進規則本文。
3. 同一現象出現兩次以上，或根因已用實驗確認（設定前後比較、單步重跑、negative test），才從經驗紀錄搬進規則本文。
4. 這顆設計的具體數字放 repo 文件（`pnr/*/README.md`、ADR、exit review）；skill 只放可以帶到下一顆設計的規則，與指向 repo 文件的連結。
5. 新增、合併、改名 skill，或 skill 的規則、陷阱、適用範圍有改動時，同一個 commit 同步更新：README 的 skill 一節（「依情況找 skill」表、索引、該 skill 的說明），以及該 `SKILL.md` 開頭的 `description`（Claude 只靠這段決定要不要讀這個 skill，要寫出會遇到的情況與錯誤訊息；不能有「英文冒號＋空格」，否則不是合法的 YAML）。改完跑 `make skill-check`（格式與索引齊全；內容是否一致仍要自己核對）。
6. Phase 0 的環境建置不做成 skill。
7. 進入 Phase 3.5／6（OpenRAM 自產 SRAM 與特性化）、Phase 5（換 Hazard3）、Phase 7（Caravel 下線預檢）時，先建立對應的 skill（`openram-macro-characterization`、`core-migration-hazard3`、`tapeout-precheck-caravel`），再開始工作。
