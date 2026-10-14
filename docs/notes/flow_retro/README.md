# 流程回顧：哪些事做到太後面才看（Phase 0–7，2026-10-14）

起因：使用者 2026-10-14：「這整套流程從頭到現在，有沒有哪些我們處理很久或必須放寬要求的，是因為有些我們做到太後面才開始看，但是那些其實應該早一點就開始考慮的。例如 lib/pdk 的 QA，如果很早知道 OpenSRAM 在低溫的問題，也許一開始就不該建議放到 signoff corner。」

做法：三個沒參與實作的 agent 分段讀 ADR、exit review、筆記、skill 經驗紀錄與 `git log`，不跑工具。三份報告在本目錄：
- `retro_p0_3.md`：Phase 0–3，13 個問題、11 個「當時無法更早知道」。
- `retro_p35_5.md`：Phase 3.5–5，12 個問題、8 個當時無法更早知道。
- `retro_p6_7.md`：Phase 6–7，17 個問題、10 個當時無法更早知道。

時間都從 commit 時間粗估，只能看量級。「提早的成本」與「省下多少」是推測，依據是同一件事在本專案實際花的時間。主 agent 抽查了關鍵出處：計畫第一版的 SRAM 矽量測 ≥1.7 V（`project-plan.md` 第 166 行，`73f7524` 就有）、ss −40°C corner 在 10-04 加入（`002dd1a`、`cf021df`）、讀取失敗在 10-05 決定處理（ADR-0010 第 3 行）、Caravel Tj −40～100 °C（`signoff-criteria` 第 44 行），都對得上。

## 使用者的例子：低溫讀取失敗與 signoff corner

三份報告的結論相同：**「一開始就不該把 ss −40°C 放進 signoff corner」不成立，該提早的是「選 macro 之前，在晶片要操作的整個範圍檢查 macro 能不能動」。**
- ss −40°C corner 是為了標準元件的溫度反轉與 Caravel 的 Tj −40°C 加的（10-03 建議、10-04 加入），跟 SRAM 無關。
- SRAM 讀取失敗在 10-05 發現，正是因為特性化照 STA corner 跑了 ss −40°C。同一顆 SRAM 在 ss 25°C 1.60 V（室溫，不是 STA corner）也讀錯；拿掉 corner 只是 STA 看不到，矽上照樣壞。
- 落差在 Phase 0 就看得到：計畫寫了這類 macro 的矽量測只到 ≥1.7 V，比 ss corner 的 1.60 V 高。用 PDK 附的 SPICE 網表在每個 PVT 做讀寫模擬，推算約半天到一天。
- 若 Phase 3 選 macro 時就知道（推測）：「2 KB OpenRAM SRAM」的方向大概不變，但會直接自產並修讀取電路，省掉 Phase 3.5 對預建 macro 的整套特性化（約 19 小時）與 Phase 3.5–5 對佔位 .lib 的時序收斂。
- 另外：三次加長週期（40 → 42 → 43 → 44 ns）都由 ss −40°C 決定，原因是標準元件與 clock tree 的溫度反轉；操作溫度應在 Phase 0 由使用者明確決定，並附「只重跑 STA」的代價 what-if。

## 三份共同的模式

1. **signoff 條件太晚定**：Phase 2、3 用工具預設值判 PASS，Phase 3 收尾才推導；IR 的判法到 Phase 7 才定清楚（一天改三次，最後餘量 0.44 mV）。
2. **平台、library、macro 的 QA 太晚**：參考設計的 74 個 slew 違規只列不判（Phase 2 花 9 輪找根因）；弱 cell 讓 resizer 失控 4 次，Phase 5 才找到；macro 的 PVT 功能、平台 deck 的違規、萃取寄生都在整合之後才看。
3. **平台規定只讀了項目名稱，沒有算到自己的數字**：Caravel 的單顆 vccd1 pad、邊界 transition 與 hold、fill 的 li1 密度、precheck PDK 的預建 SRAM、metal fill 誰補，全部 harden 之後才發現（粗估重做約 2 天、3 項放寬），每項試算 10 分鐘到半天。
4. **放寬的依據只在一個設計上量過**：IR 只判 nom_tt、resizer 用固定餘量代替 ss −40°C、golden 誤差，換成 Hazard3 時三項都失效。
5. **換東西時舊檢查沒有重套**：換 macro 時 Phase 0 檢查過的 `FOREIGN` 沒查，最終 GDS 的 SRAM 是空的；EQY 只解析 `sky130_` 開頭的 cell，SRAM 的檢查被跳過照樣 PASS。

## 合併後的提早檢查（19 條，三份報告的 E 編號對照在括號裡）

| # | 放在流程的哪一步 | 做什麼 | 通過條件 | 對應的代價 | 來源 |
|---|---|---|---|---|---|
| A1 | 4.1 規格與計畫 | **操作範圍對照表**：晶片的 VDD 範圍與 Tj（平台規格）由使用者決定、記 ADR；corner 清單由它推出（含溫度反轉掃描）；對照每個 macro／IP 與 standard cell library 已驗證的範圍 | 每個 corner 對應到規格；沒被驗證涵蓋的範圍列成「選定前要確認」 | SRAM 讀取失敗、三次加長週期 | P03 E1；P35 E1、E3 |
| A2 | 4.1，選定下線平台時 | **平台試算表**：每項收件檢查、外殼邊界 SDC、供電結構（pad 數與位置）、fill 與密度上下限、平台的 PDK 與工具版本，逐條算出對本設計的數字；衝突在第一次 harden 前請使用者決定；需要平台回覆的問題當天送出 | 每條有數字或「待查＋在哪一步查」 | Phase 7 的 IR、slew、hold、li1、預建 SRAM、fill | P67 E1、E2、E3、E10；P03 E12 |
| A3 | 4.1，第一份網表之後 | **corner 代價 what-if**：只重跑 STA，列出每個「決定週期」的 corner 代價，請使用者確認規格 | 使用者確認過 | 三次加長週期 | P35 E2 |
| B1 | 4.3，**選定 macro 之前**（go／no-go） | 在規格範圍的格點（STA PVT、corner 之間的溫度、最低供電）做 SPICE 讀寫（連續讀相反值、未用 port 照實際接法）；用**平台的 DRC deck** 單獨檢查 macro | 全部讀寫正確、違規可解釋；否則先列選項（換 macro、修電路、縮規格） | SRAM 讀取失敗、特性化與整合做兩次、precheck 的兩條規則 | P03 E2；P35 E4；P67 E4、E5 |
| B2 | 4.3，特性化之前 | 先試版圖萃取（平面輸出、檢查負值電容），寄生倍數用量到的值 | 萃取網表讀寫正確；.lib 不低於萃取值 | dout0 transition 放寬（wrapper setup 只剩 +0.151 ns） | P67 E6 |
| B3 | 4.3 view QA | macro .lib 的輸出等效驅動電阻與延遲表單調性，和標準元件的範圍比 | 落在範圍內；植入錯誤的 .lib 要 FAIL | Phase 3.5 的 .lib 斜率問題 | P35 E5 |
| B4 | 4.3，換 macro 時 | **換 macro 檢查單**：前面對舊 macro 做過的檢查逐條重跑；每支 checker 在 positive run 印出讀到的 macro instance（比對對象不是空的） | 逐條 PASS | 空 SRAM 的 GDS、EQY 略過 SRAM、兩輪白跑的 harden | P67 E8；P03 E9 |
| C1 | 4.5，**任何 harden 之前**（含子區塊） | signoff 條件先推導並強制：limits 每一列有出處、corner 清單等於 A1 推出的；IR 判法一次定清楚（保護什麼、同一個 corner、max power pattern、真實 pad） | `make harden` 開頭檢查（建議做成 checker 加 negative test） | 40 → 42 ns、IR 改三次 | P03 E3；P35 E10；P67 E9 |
| C2 | 4.0／4.5 | **library 與工具預設值 QA**：參考設計的每個 DRV 違規都要有原因；弱 cell 查表涵蓋**所有 signoff corner** | 違規 0 或都有原因；排除後沒有弱 cell | Phase 2 的 9 輪、resizer 失控 4 次 | P03 E5；P35 E6 |
| C3 | 4.5 | resizer 看的 corner 預設等於 signoff corner；要拿掉需有根因、what-if 與 ADR，每次 criteria review 檢查最差 corner 是否在 resizer 的清單裡 | 沒拿掉，或每個都有 ADR 與檢查列 | Phase 5 setup −4.158 ns | P03 E4；P35 E7 |
| C4 | 4.5，外殼設計 | 用官方邊界 SDC 先試算：input transition 對 slew 上限、邊界 hold 需要的延遲 | 衝突在 harden 前有使用者決定 | Phase 7 決定 16、17 | P67 E10 |
| D1 | 4.4 定 die 時 | 只跑到 PDN、global placement、global routing：看窄 row、目標密度、溢位，出 floorplan 圖 | 沒有窄 row、溢位 0 | Phase 3 約 8 輪密度、max transition 放寬又撤回 | P03 E6 |
| D2 | 4.4 floorplan 試跑 | IR 在 floorplan 試跑就成立：真實 pad、慢 corner、能跑 gate-level 時就用 pattern | ≤ 預算；結果比預算小 100 倍以上先查模型 | IR 分四個 Phase 才修完 | P03 E7 |
| D3 | 4.4 換 core 時 | 新 core 單獨 harden，所有 signoff corner 的 STA | 目標週期 PASS 或已知差距並經使用者決定 | Phase 5 換 Hazard3 | P35 E8 |
| D4 | 4.6 第一次帶 macro 的 harden | macro clock 的結構檢查（CTS 有沒有插對齊 buffer、半週期路徑兩邊緣的 latency）；flow 變數關不掉時查到底層工具的指令選項 | 沒有預期外的對齊 buffer，或已記錄決定 | CTS 延後 SRAM clock（Phase 4 → 5） | P03 E8；P35 E9 |
| D5 | 4.6 外殼設計的第一次探索 harden | 對探索 GDS 跑平台完整收件檢查（查證用）並量 VM 記憶體；平台的密度上下限做成 harden 內的 checker | 除了已決定的項目全 PASS | li1 75%、VM OOM、等 precheck 1 小時才知道 | P67 E11、E12 |
| E1 | 全程 | **放寬與補償登記表**：每項放寬（加長週期、餘量、誤差、佔位值、只判某 corner、延後處理）記錄原因、依據的量測、在哪個設計量的、何時要重驗、回收條件；換設計或換 macro 時逐項 what-if | 沒有「原因已不在卻沒評估」或「依據不是現在的設計」的項目 | 放寬依據只在一個設計上量過 | P35 E12；P67 E14 |
| E2 | 4.6 建 golden | 同設定至少 4 個樣本（含一次乾淨 checkout）定誤差，記樣本數 | 樣本彼此在誤差內 | golden 誤差兩次重建 | P03 E11；P35 E11 |
| E3 | 4.8／4.9 | **新 checker 寫完就做獨立漏洞審查**（植入錯誤＋對照組），不只在 Phase 收尾；收尾只審最後改過的 | 每支新 checker 有審查紀錄與 negative test | 每個 Phase 收尾都找到 5–8 個漏洞、多跑一輪 regress | P35 E13；P67 E13 |

另外：P03 E10（RTL 的 code coverage、EQY 的 RTL 對合成網表試跑）優先度較低，留在報告裡。

## 優先順序（三份報告的共同建議）

- **新專案一開始就做，成本都在 1 天以內**：A1、A2、B1、C1、C2。對應的是整個專案最貴的幾件事（SRAM 讀取失敗、三次加長週期、Phase 7 的平台問題、resizer 失控）。
- **流程制度**：E1（放寬登記表）、C3（resizer 的 corner）、E3（checker 寫完就審查）。
- **只改 checker 或 skill**：B3、B4、D4、D5、E2。

## 當時無法更早知道的（三份合計 29 項，例如）

`GRT-0229` 隨機中止、多執行緒 detailed routing 的小差異、GRT 重繞造成的內部 net slew、`RSZ-0074`、OpenROAD resizer 只看 tt 的內部行為、OpenRAM 自身的缺陷、Caravel PLL 的 jitter 沒有官方數字、開源工具不分析的 SI。細節在三份報告。
