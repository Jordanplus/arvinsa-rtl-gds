# arvinsa-rtl-gds：給 Claude Code 的專案規則

## 流程 skill 與經驗累積

`.claude/skills/` 有 21 個流程 skill（清單與每個的說明在 README「Claude Code skills」一節）。

1. 做到 skill 涵蓋的任務（LibreLane 執行除錯、checker／golden、時序與 DRV、macro 整合、DRC、EQY、antenna、CTS、PDN／IR、LVS、gate-level 模擬、floorplan 與壅塞、SDC 約束、合成與 lint、signoff 條件的推導、一鍵 regression 與來源追溯、多 corner STA、directed 測試補缺口、Phase exit review、SRAM macro 的 SPICE 特性化、把 CPU 換成 Hazard3）時，先讀對應的 `SKILL.md`，照裡面的規則與已知陷阱做。
2. 任務做完，把新遇到的現象追加到該 skill 的「經驗紀錄」表：日期、run、原文訊息、根因（標明已驗證或推測）、處理、證據路徑。推測的根因不能寫進規則本文。
3. 同一現象出現兩次以上，或根因已用實驗確認（設定前後比較、單步重跑、negative test），才從經驗紀錄搬進規則本文。
4. 這顆設計的具體數字放 repo 文件（`pnr/*/README.md`、ADR、exit review）；skill 只放可以帶到下一顆設計的規則，與指向 repo 文件的連結。
5. 新增、合併、改名 skill，或 skill 的規則、陷阱、適用範圍有改動時，同一個 commit 同步更新：README 的 skill 一節（「依情況找 skill」表、索引、該 skill 的說明），以及該 `SKILL.md` 開頭的 `description`（Claude 只靠這段決定要不要讀這個 skill，要寫出會遇到的情況與錯誤訊息；不能有「英文冒號＋空格」，否則不是合法的 YAML）。改完跑 `make skill-check`（格式與索引齊全；內容是否一致仍要自己核對）。
6. Phase 0 的環境建置不做成 skill。
7. 進入 Phase 3.5／6（OpenRAM 自產 SRAM 與特性化）、Phase 5（換 Hazard3）、Phase 7（Caravel 下線預檢）時，先建立對應的 skill（`openram-macro-characterization`、`core-migration-hazard3`、`tapeout-precheck-caravel`），再開始工作。`openram-macro-characterization` 已在 Phase 3.5 開始時建立，Phase 6 沿用並補上 OpenRAM 自產的規則；`core-migration-hazard3` 已在 Phase 5 開始時建立。
8. 這個 repo 也是使用者其他 IC 專案沿用的流程來源（使用者 2026-10-04：開新專案時請 Claude Code 或 Codex「使用 arvinsa-rtl-gds 這個 repo 的流程」）。在別的專案用到這裡的 skill，通用的新經驗寫回這裡的 `SKILL.md` 與 README（規則 5），不要把 skill 複製到新專案；只屬於新設計的數字留在新專案。完整流程在 [`arvinsa-rtl-gds-flow.md`](arvinsa-rtl-gds-flow.md)（新專案的入口；README 只放簡易版並指過去，使用者 2026-10-09）：流程的步驟、順序、checker 或 negative test 有改，同一個 commit 更新它。Codex 從 `AGENTS.md` 進來，它只指回本檔與流程文件，不另寫規則。
9. 每次 harden 跑完（PASS 或 FAIL），回報結果之前，先照 `signoff-criteria` 的「每次 harden 後的檢查」做：讀 `runs/<tag>_signoff/criteria_review.txt`，寫 `criteria_review.md`（有沒有被執行、合不合理、學習），學到的數字寫進該製程的 knowledge 檔（使用者 2026-10-07）。Claude Code 由專案的 Stop hook（`.claude/hooks/require_criteria_review.py`）強制；Codex 沒有 hook，照本條自行遵守。
10. **skill 的重要任務是防工具的缺陷**（使用者 2026-10-07）。工具（LibreLane、OpenROAD、Yosys／EQY、Magic、KLayout、Netgen、模擬器）的缺陷或意外行為，依規則 3 確認之後，要在對應的 skill 寫成防護，以下四項都要有：
    - **症狀**：確切的錯誤訊息或現象，也寫進該 skill 的 `description`，之後遇到時才找得到這個 skill。
    - **怎麼發現**：看哪個 log、哪個 checker 的哪一列。
    - **怎麼繞過**：設定、repo 的 plugin、有上限的重試，或流程上的避開方式。不改釘版的工具本身。
    - **防復發**：能抓到它再次出現的 checker 或 negative test。做不到的話，寫明「沒有自動防護」和原因。

    防護不能綁在 flow 會變的東西上，例如 step 名稱、step 編號、log 措辭。工具升版時，逐條重看這些防護是否還成立。只寫一列經驗紀錄不算完成。
11. **待辦清單與進度顯示**（使用者 2026-10-07）：
    - 目前 Phase 的待辦清單放在 `runs/todo.md`。
      - 不進版控：勾選時不能弄髒 working tree，因為 harden 與 regress 都要求乾淨的 tree。
      - 格式：`- [ ]` 待辦、`- [~]` 進行中、`- [x]` 完成。
    - Phase 開始時，依 `project-plan.md` §8 建立清單；之後每開始或完成一項就更新。
    - Phase exit review 寫完後清空。
    - Claude Code 狀態列的第二行由 `scripts/progress.py` 顯示，透過 `.claude/statusline-progress` 呼叫；`--json` 給 `/progress` 進度面板。內容是待辦剩幾項，以及執行中工作的進度百分比。這些百分比只是給人看的估計，signoff 不讀它們。
12. **自建或收到的 macro 都要先做 view QA，才能交給 flow**（使用者 2026-10-09）：不限 OpenRAM，任何 memory compiler、廠商 IP、先前 harden 的區塊都一樣。
    - 用 `scripts/check_macro_views.py` 檢查每個交付檔的內容（名稱、腳位與方向、.lib 數值與面積、LEF 尺寸對 GDS 外框），細節在 `hard-macro-integration` 清單第 0 項。
    - 產生 macro 的 Makefile target 要把這一步接在產生之後（`make openram-macro` 已接）；整合中的 macro 用 `make macro-views`。
    - FAIL 的 view 不能直接用：修正或替換後重跑到 PASS，做法與原因記進該 macro 的 README 或 ADR。
    - 這個 QA 自己的 negative test 是 `make neg-macro-views`（在 `make regress` 裡）；新的 view 錯誤類型要加一個植入錯誤的 case。
13. **要做選擇時：先查證、列選項，由使用者決定，再實作**（使用者 2026-10-09）。適用於新 Phase 開始、改變已定的決定，以及工作中出現會影響規格、量測方法、signoff 標準、時程或範圍的分岔（例如 2026-10-09 的 port 1 漏電：.lib 填哪個值、要不要改成 1RW）。
    - **先查證**：讀程式碼、網表、log、上游原始碼與 issue，必要時做小實驗，確認根因與每個選項的實際代價。引用要附出處並核對原文；推測要標明。
    - **列選項**：每個選項寫做法、代價（時間、風險、影響範圍）與依據，標出建議的那一個並說明理由。查證不足以判斷時，「先查清楚某件事再決定」本身也可以是選項。
    - **由使用者決定**：等使用者選。有業界標準做法、而且不影響上述各項的，照標準做法做，回報時說明。
    - **再實作**：照選定的做；決定、依據與使用者的原話和日期寫進 ADR（`docs/decisions/`）或該 macro 的 README，查證過程寫進對應的筆記。
