# ADR-0020：流程回顧的 19 條提早檢查寫進流程文件與 skill；放寬與補償登記表從本專案開始

- 狀態：已採用（2026-10-14，Phase 7 結案期間）。
- 範圍：`arvinsa-rtl-gds-flow.md`（其他專案沿用的流程，CLAUDE.md 規則 8）與對應的 skill；不改本專案已完成的設計。
- 查證：`docs/notes/flow_retro/`（三個沒參與實作的 agent 分 Phase 0–3、3.5–5、6–7 回顧，只讀檔案與 git；主 agent 抽查關鍵出處）。

## 背景

使用者 2026-10-14：「我覺得還要花一些時間探討，這整套流程從頭到現在，有沒有哪些我們處理很久或必須放寬要求的，是因為有些我們做到太後面才開始看，但是那些其實應該早一點就開始考慮的。例如lib/pdk 的QA，如果很早知道OpenSRAM在低溫的問題，也許一開始就不該建議放到signoff corner」。

回顧的結論（細節與證據在 `docs/notes/flow_retro/README.md`）：
- 使用者的例子：拿掉 ss −40°C corner 解決不了。這個 corner 是為了標準元件的溫度反轉與 Caravel 的 Tj −40°C 加的（10-04），SRAM 讀取失敗是因為特性化照 corner 跑了 ss −40°C 才在 10-05 發現；同一顆 SRAM 在 ss 25°C 1.60 V（不是 STA corner）也讀錯。該提早的是「選 macro 之前，在晶片的整個操作範圍做 SPICE 讀寫」；計畫第一版就寫了這類 macro 的矽量測只到 ≥1.7 V，比 ss corner 的 1.60 V 高。
- 共同模式：signoff 條件太晚定；平台、library、macro 的 QA 太晚；平台規定只讀了項目名稱、沒有算到自己的數字；放寬的依據只在一個設計上量過；換東西時舊檢查沒有重套。

## 決定

使用者 2026-10-14 的三個選擇：
1. 「全部 19 條 (建議)」：19 條提早檢查（README 的 A1–A3、B1–B4、C1–C4、D1–D5、E1–E3）依流程步驟寫進 `arvinsa-rtl-gds-flow.md`，對應的 skill 加規則（CLAUDE.md 規則 5：README 的 skill 一節、`description` 同步）。
2. 「這次只寫進流程，checker 留到下一個專案 (建議)」：能做成自動 checker 的幾條（例如 C1 harden 前檢查 limits 出處與 corner 清單、D5 平台密度上下限）這次不做，流程文件寫明「目前沒有自動防護」，下一個專案開始時做。理由：Phase 7 在收尾，加 checker 要擴大範圍、延後 regress 重跑。
3. 「現在建第一版 (建議)」：放寬與補償登記表（E1）從本專案開始，整理 ADR-0001–0019 與各 exit review 既有的放寬；Phase 7 exit review 的已知限制引用它。

## 後果

- 下一個專案從 4.1 規格與計畫就要做操作範圍對照表、平台試算表、macro 的 go／no-go；這些在本專案都是事後才做的。
- 自動防護缺口：19 條中能自動化的部分，到下一個專案開始前都只靠流程文件與 skill。
