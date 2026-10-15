# 流程回顧：Phase 6–7（哪些事太晚才看、應該提早）

**結論（最重要的 5 項）**
1. **Caravel 的「收件規定與外殼條件」在 Phase 7 開工查證時只讀到「有哪些檢查項目」，沒有往下算到對我們設計的影響**：單顆 vccd1 pad 的供電路徑、`decap_3` fill 讓 li1 密度 75%、官方邊界 SDC 的 input transition 超過我們的 slew 上限、邊界路徑的 hold、預建 SRAM 在 precheck PDK 另有違規、metal fill 由誰補，全部到 harden 之後才發現。合計粗估約 2 天的重做（IR 約 1 天、li1 密度約 14 小時含兩次 harden），和 3 項放寬（邊界 slew 例外、hold 用 margin 代替 resizer 看 ff_100C、比對基準不比其他規則）。這些在 Phase 7 第一天的查證或第一次探索 harden 後就能用 1–3 小時的檢查看到。
2. **IR 的判法在 Phase 7 一天內改了三次（最壞組合 → 慢 corner → max power pattern）**，根因是 Phase 4–5 定 IR 門檻時沒有先問「這個預算保護什麼、電流該從哪裡來」，業界做法（max power pattern 的切換活動）是使用者在 Phase 7 才提出。最後只剩 0.44 mV 餘量（19.56 mV，上限 20 mV）。
3. **Phase 6 換 macro 時，Phase 0 已經做過的檢查沒有重新套用**：Phase 0 就確認過預建 SRAM 的 LEF 有 `FOREIGN`（`docs/phase_exit/phase0.md:20`），自產 macro 卻到第一輪 harden 才發現沒有，最終 GDS 的 SRAM 是空的；flow 的 KLayout deck 也到第二輪 harden 才對 macro 跑。三輪 harden 有兩輪白跑。
4. **SRAM 的版圖萃取（含寄生）在 Phase 6 最後才做，.lib 因此沒有更新，變成放寬**：dout0 transition .lib 寫 0.5 ns、實際 1.4–2.2 ns；到 Phase 7 wrapper 上，換成實際值後 setup 從 +0.548 降到 +0.151 ns，餘量已經很薄。萃取若在特性化之前做（約 3 小時），.lib 一開始就會含寄生。
5. **你的例子（低溫讀取失敗）**：拿掉 −40°C corner 解決不了，因為預建 SRAM 在室溫 ss 25°C 1.60 V 也讀錯，而那不是 STA corner；Caravel 規格本來就要求 −40～100°C。該提早的是「選 macro 時在每個 signoff PVT 先做讀寫功能檢查」，Phase 3 就做的話，會直接走自產並修讀取電路（Phase 6 實際只花約 1 天），省掉 Phase 3.5 那一輪用佔位 .lib 的特性化與時序收斂。詳見第 4 節。

範圍：Phase 6（2026-10-08 到 10-12 00:00，`98f49b7`）與 Phase 7（2026-10-12 08:46 `f316425` 到現在）。時間從 commit 時間與 ADR 寫的 run 時間粗估，**commit 間隔只是上限，不是實際工時**。標「推測」的是沒有實驗或原文支持的判斷。Phase 3.5–5 的根因（例如 −40°C corner 何時加入、Phase 5 的 IR 判法）屬另一份回顧，這裡只寫它們在 Phase 6–7 造成的影響。

---

## 1. 問題總表

「提早的成本」是我的估計（依實際做同一件事花的時間），不是量測。

| # | 問題（白話） | 花了多少或放寬了什麼 | 什麼時候發現（Phase、commit） | 最早可以在哪裡發現、用什麼檢查 | 提早的成本 | 證據 |
|---|---|---|---|---|---|---|
| 1 | 外殼的 GPIO 先選了 8–20，沒看位置，離 SoC 2–3 mm | RTL、`user_defines.v`、testbench 重做，RTL regression 30/30 與 negative test 42/42 重跑；commit 間隔約 1.5 小時（`ccdc21d` 09:51 → `8654670` 11:22）；另外建了四層強制機制 | Phase 7 步驟 4 floorplan，`e825f9a`（10-12） | Phase 7 步驟 3 寫 RTL 前：讀範本 DEF 的腳位座標，先定 block 位置再選 GPIO（現在已是 CLAUDE.md 規則 14） | 約 15–30 分鐘讀 DEF | ADR-0019:36–38；`chip-floorplan-pin-planning` SKILL.md:64 |
| 2 | Caravel 給 user area 的電源只有一顆 vccd1 pad、一顆 vssd1 pad，只從 wrapper 左右兩側接進來；我們假設「從 core ring 整圈進來」，IR 到 harden 後才量出 104 mV（上限 20） | 約 1 天：Caravel 原始碼查證、5 種供電模型、4 種 met4 寬度、5 個 block 位置的 what-if；met4 strap 1.6 → 4.8 µm；中途訂了「板子供電 ≥ 1.65 V」的使用要求，隔天又取消（重做） | 探索 run `p7_harden2` 之後（10-12 夜，`ade5130`、`a200073` 10-13） | Phase 7 步驟 4（pad 階段）：讀 Caravel 的 `manual_power_connections.lef`、`chip_io.def`，在 floorplan 狀態（PDN 已產生）就建供電模型跑一次 IR | 約半天（原始碼查證加單步 IR） | ADR-0019:51（決定 11 只寫「供電從 core ring 進來」）、:82–97；`chip-floorplan-pin-planning` SKILL.md:67–68（「約一天」） |
| 3 | IR 判法一天內改三次：最壞組合（ff 電流＋ss 電阻）→ 慢 corner → CPU max power pattern 的實際切換活動 | `ir_worst.py`、`ir_caravel.py`、`ir_pattern.py` 改寫，negative test 9＋7 個；soc_top 也改用 pattern（步驟 8）。OpenSTA 預設切換率高估約 2.2 倍。最後 19.56 mV，**餘量 0.44 mV**。pattern 的已知限制（沒有 Wishbone 主機端存取、零延遲模擬不含 glitch、「最耗電」是三段取最大，不是證明）變成放寬 | Phase 7（使用者 10-13 問「你的2,3我們為什麼抓這麼保守」「一般IR都會用CPU max power pattern去做不是嗎」），`c64b3bf` | 第一次定 IR 門檻時（本 repo Phase 4–5，`signoff-criteria`）：寫清楚預算保護哪個 corner 的什麼（慢 corner 的 setup），電流、電壓、電阻取同一個 corner；電流用 max power pattern 的 VCD | 約半天（maxpower firmware 加錄波，Phase 7 實際在一個晚上做完） | ADR-0019:99–104、:106–116；`pdn-ir-drop` SKILL.md:77；`runs/p7_formal2_ir.log` |
| 4 | Caravel 官方 SDC 的 input transition（0.84–0.97 ns）超過我們的 slew 上限（0.70／0.75 ns） | **放寬**：邊界 net 允許到「外部 transition + 0.05 ns」，每個 corner 385 個違規列為例外；時間少（commit 間隔約 3 小時，`c7d3d2a` → `2c0fed6`，其中也含 RSZ-0074 的處理） | 探索 run `p7_harden2` 第 38 步（10-12） | Phase 7 步驟 4 採用官方 SDC 時（決定 14）：把官方 input transition 表和 ADR-0009 的上限並排比。當時已在 `p7_floorplan4` 網表上量到 `wbs_dat_i` 0.84 ns，只是沒拿去比上限 | 約 10 分鐘 | ADR-0019:63（已量到 0.84 ns）、:68–72 |
| 5 | Caravel 輸入路徑的 hold（−0.071 ns，在 ff_100C）：官方約束下要在 ff 多延遲約 2.4 ns | `p7_harden3`（resizer 加 ff_100C → 插 4759 顆 buffer、壅塞失敗）、單步實驗、`p7_harden4` 137 分鐘；commit 間隔約 3.5 小時（`d1a7888` 20:32 → `6287a50` 00:03）。**放寬**：resizer 仍不看 ff_100C，用 GRT 後 hold 餘量 0.2 ns 代替；resizer 不放大 `a221oi_1` 的原因沒查到 | `p7_harden2` signoff（10-12） | Phase 7 步驟 4：用官方 SDC 的 source latency（min 4.65／max 5.57 ns）、min input delay 0.79 ns 加上預估 clock tree，手算邊界 hold 需求；或在第一次探索 run 的 CTS 之後先跑邊界 STA | 約 1 小時；餘量大概還是會選 0.2 ns（推測），省下的是 `p7_harden3/4` 一輪 | ADR-0019:73–79；`drv-timing-closure` SKILL.md:127 |
| 6 | precheck 的新 KLayout deck 對 OpenRAM bitcell 報兩條規則（`MR_licon.SP.6`、`MR_mcon.CON.10`），PDK 預建 SRAM 也一樣 | 時間不多（Phase 7 第一天就刻意跑了）。**放寬**：exit 條件改成「官方 13 項中 11 項 PASS，另兩項只允許這兩條、位置和預建 SRAM 一致」，官方結果仍是 FAIL；為此寫了 `check_precheck.py`、`rdb_flatten.py`、25 個 negative test，獨立審查又補 4 個漏洞 | Phase 7 步驟 1，`f316425`（10-12） | Phase 3 選 SRAM 時，或 Phase 6 步驟 2 產生 macro 時：用目標平台的 deck 對 macro 單獨跑。deck 的改動是 2026-05-07，比本專案開工早 | 約 10–20 分鐘；能改變的是：更早定 exit 條件、更早送 ChipFoundry issue（至今仍是草稿）。換 SRAM 種類（例如不用 bitcell 的 RAM）是否值得，沒評估過（推測不會換） | 筆記 `caravel_precheck_phase7.md`:40–45、:65–80；ADR-0019:21–27、:28 |
| 7 | precheck 用的 PDK（`3e0e31dc`）裡的預建 SRAM 另有 10 個 nsdm／psdm 違規，flow 的 PDK（`8afc834`）那顆沒有 | **放寬**：比對基準只比允許的兩條規則，其他規則不列入（決定 24 甲）；checker 改寫、negative test 改成兩個案例 | Phase 7 步驟 7，官方 image 第一次跑 wrapper（10-14） | Phase 7 步驟 2 裝好 precheck PDK 時（10-12，下載 47 分鐘）：用 precheck 的 PDK 那顆 SRAM 當比對基準跑一次 deck。更早：Phase 0 就列出「flow 的 PDK／工具版本」與「平台 image 的 PDK／工具版本」對照（Magic 8.3.623 vs 8.3.471、KLayout 0.30.7 vs 0.29.12、PDK `8afc834` vs `3e0e31dc`） | 約 10 分鐘（deck 跑一顆 SRAM）；版本對照約 30 分鐘 | ADR-0019:22、:169、:172；筆記:18、:140；ADR-0019「後果」:219 |
| 8 | wrapper 的空白區被 PDK 預設的 `decap_3` 填滿，li1 密度 75%（precheck 上限 60%）；246 萬個 decap 也讓 VM（10 GiB）跑 BEOL、LVS、OEB 時被 OOM 砍掉 | 步驟 7 整段約 14 小時（`1f9d3d9` 01:46 → `c84355d` 15:37，含原本就要跑的第一次官方 precheck）：多一次正式 harden（182 分鐘）、一次確認 harden（182 分鐘）、官方 precheck 83＋49＋53 分鐘、golden 與正式 EQY／gate-level／IR 重跑 | Phase 7 步驟 7，官方 image 第一次跑 wrapper（10-14） | Phase 7 步驟 5 第一次探索 harden（`p7_harden2`，10-12）之後：在探索 GDS 上跑 precheck 的密度檢查（本機 84 秒）或整套 precheck 一次（83 分鐘）。線索在第一天就有：筆記第 2 節列了密度上限，官方範例 `RUN_FILL_INSERTION: false` | 約 1.5 小時（整套 precheck 一次，順便確認 VM 記憶體夠不夠） | ADR-0019:164–193；筆記:31、:122–138；`tapeout-precheck-caravel` SKILL.md:55–60（「harden 時沒有自動檢查」） |
| 9 | 金屬密度低於下限（met2 1.6%、met3 0.8% 等），precheck 只查上限；fill 由誰補到結案審查才查 | **沒有解決，列為下線前要做**：限時 2 小時的 fill 試跑還沒做、ChipFoundry 沒書面確認；下限檢查不在 precheck 裡，失敗要回頭改設計（Efabless 時代有全數位設計卡在這一步） | 低於下限從 Phase 3 就知道（「chip-level 一定要補 metal fill」）；fill 規定 10-14 才查（`runs/p7_review/chipfoundry_fill.md`） | Phase 7 步驟 1 查平台時，或更早在 §5.5 選平台時：查清「fill 誰補、補完有沒有下限檢查、數字多少」 | 約 30 分鐘查證（實際就是 30 分鐘） | `docs/phase_exit/phase3.md`:164；筆記:31；ADR-0019:210、:213；`chipfoundry_fill.md` 結論 1–4 |
| 10 | 需要平台回覆的問題一直沒送：OpenRAM bitcell 規則的 issue、自產 SRAM 的 Magic DRC（約 220 萬個違規）下線時怎麼處理、fill 書面確認 | **放寬**（靠「不下線」這個範圍決定延後）：三項都列為「下線前要做」 | 陸續在 10-12、10-14 | 選定平台時（§5.5，10-03）就送；回覆的等待時間不在我們手上 | 擬稿約 1 小時；效益是等待時間平行化 | ADR-0019:28、:220；`docs/notes/chipfoundry_issue_draft.md` |
| 11 | 自產 SRAM 的 LEF 沒有 `FOREIGN`，LibreLane 輸出的最終 GDS 裡 SRAM 是空的（XOR 差 569 萬），log 卻寫 `All LEF cells have matching GDS cells`；LEF 單位 2000 讓 OpenROAD 丟掉整份 LEF（`ODB-0205`） | 第一輪 harden（兩個 CPU）白跑；floorplan 試跑失敗一次。Phase 0 已確認過預建 SRAM 的 LEF 有 `FOREIGN`，上游 2025-07 才補上，等於已知問題沒套到新 macro | Phase 6 步驟 4a、4b（10-10，`221822a` → `3ceca55`） | Phase 6 步驟 2 產生 macro 時（10-08）：把 Phase 0 對預建 macro 做過的每一項檢查（FOREIGN、Verilog 模型一致）原樣套到新 macro；現在由 view QA（CLAUDE.md 規則 12，10-09 建立）做 | 幾分鐘 | `docs/phase_exit/phase0.md`:20；`project-plan.md`:59；`phase6.md`:92–94；`hard-macro-integration` SKILL.md:61、:63 |
| 12 | macro 內的 DRC：Magic full 規則在步驟 2 就看到 4 種新錯誤，決定「選定 macro 後再修」，待辦卻漏了；flow 的 KLayout deck 到第二輪 harden 才對 SRAM 報 27 個（nwell.6、psdm.1、m2.2） | 第二輪 harden 白跑；patch 0002–0004（2 KB 重產 45＋51 分鐘、小 macro 多次）。**放寬**：Magic licon.14 加進 100 nm 容許清單，能藏新違規的面積從 SRAM 的 0.65% 變 3.32% | Phase 6 步驟 4b 第二輪（10-10，`3ceca55` → `ad184f5`） | Phase 6 步驟 2（10-08）：macro 產生後立刻用 flow 簽核用的每一套 deck（Magic、KLayout，以及平台 deck，見 #6）單獨跑；「之後再修」的項目當下寫進待辦 | 幾分鐘到 20 分鐘 | ADR-0018:41–44、:91–97；`openram-macro-characterization` SKILL.md:248 |
| 13 | 換成自產 macro 後，EQY 的網表解析只認 `sky130_` 開頭的 cell，SRAM 的 clock 來源檢查從 4a 到 4c 一直被略過，照樣 PASS | 沒有誤放錯誤版圖，但 4a–4c 之間這項檢查是空的；發現時 negative test 以 `KeyError: 'sram0'` 中止 | Phase 6 步驟 4c（10-10） | 換 macro 的當下：每支 checker 在 positive run 上確認「macro instance 有被解析到、比對的對象不是空的」 | 約 1 小時（跑一輪 positive control） | ADR-0018:109；`phase6.md`:171 |
| 14 | 自產 SRAM 讀取失敗的修正：低溫與 ss 1.60 V 讀成前一次的值（patch 0001 在 sense amp 輸入端加預充電），以及閒置 port 1 的 `clk1` 接 0 時 chip-select DFF 從不鎖存 | 約 1 天（10-08 一天內：3a 重現、3b `words_per_row=1` 57.6 分鐘、電路圖 what-if、3p1 小 macro、3p2 38.9 分鐘、探針實驗）；比計畫寫的「另加 2–3 天」少。`clk1` 的問題從 Phase 1 的 RTL 就存在（預建 macro 同一套電路），Phase 5 結案的 SoC 有上電風險 | 低溫失敗：Phase 3.5（10-05）；`clk1`：Phase 6 步驟 3p2（10-08） | 低溫：Phase 3 選 macro 時在每個 signoff PVT 加 ss 25°C 跑讀寫功能檢查（見第 4 節）；`clk1`：Phase 1／3 接 tie-off 時，讀 macro 的控制邏輯，找「沒有 reset、靠時脈清除的狀態」 | 功能檢查：修剪網表每個 PVT 幾分鐘到幾十分鐘；控制邏輯 review 約 1 小時 | ADR-0018:45–53；筆記 `openram_phase6_bringup.md`:103–251；ADR-0010:70、:82、:176 |
| 15 | SRAM 的版圖萃取（含走線寄生）到 Phase 6 最後才做：讀出時間是電路圖的 2.0 倍（Phase 3.5 假設 1.6 倍），dout0 transition 實際 1.4–2.2 ns、.lib 寫 0.5 ns | **放寬**：使用者選「不改 .lib，寫進已知限制」（重產要再 6–8 小時）；延遲靠 .lib 下限蓋住，`min_pulse_width` 對萃取讀出時間只剩約 10%。Phase 7 wrapper 換成實際 transition 後 setup **+0.548 → +0.151 ns** | Phase 6 步驟 5d（10-11，`904e18e`，獨立審查提醒後限時 3 小時試跑） | Phase 6 步驟 3（特性化之前）：先做萃取試跑，能模擬就直接用萃取網表特性化。Phase 3.5 的限制 2、3 已指定 Phase 6 處理 | 約 3 小時（萃取試跑實際時間）＋每個 PVT 32–43 分鐘的平面網表模擬 | ADR-0018:122–128、:155；`phase6.md`:199–205；`runs/p7_exit_draft/dout0_whatif.md` |
| 16 | SRAM 功耗與漏電的量法換了 5 次（修剪＋外插 → 完整網表 → `.ic`＋快速量法 → DC 工作點（不可行）→ 量測窗＋絕對門檻、gmin），問題幾乎都出在 −40°C | 約 2 天（10-09 到 10-10；使用者：「一顆2KB SRAM不可能要搞兩天」）。**放寬**：漏電不是穩態值（tt 可能偏低 26% 以上）、−40°C 的 gmin 偏差未知、平穩度只放行 ≤ 10 nW 的下降 | Phase 6 步驟 3e（10-09） | 每個新量法開長時間 run 之前：先在修剪網表把 5 個 PVT 都跑一次（現在是 skill 規則 27），−40°C 先跑 | 約 1 小時 | ADR-0018:54–82（:69 使用者原話）；`openram-macro-characterization` SKILL.md:240–247 |
| 17 | 獨立審查放在 Phase 收尾：Phase 6 找到 7 個 checker 漏洞、Phase 7 找到 8 個加 1 個缺口，修完都要整套 regression 重跑 | Phase 6：`4713c5f` 兩輪 regression 作廢、`904e18e` 兩輪因修漏洞時弄壞 `check_inputs.py` 而 FAIL，到 `85bfa75` 才結案；Phase 7：`84fe505` 三條 regression 要重跑（Hazard3 157 分鐘；wrapper 光 harden 在三條同跑時就 236 分鐘，整條約 6 小時） | 兩個 Phase 的結案前 | 每支新 checker 寫完、第一次正式 harden 之前，就請獨立 agent 找「該 FAIL 卻 PASS」的漏洞；結案時只審最後改過的部分 | 每批 1–2 小時 agent 時間；省下一輪完整 regression（約 3–4 小時機器時間） | `phase6.md`:41–43、:179–186；ADR-0019:206–209；`runs/p7_review/checker_holes.md` |

### 1.1 從表上看出的三個共同根因

- **外殼與平台的條件只讀了「規則名稱」，沒有算到「對我們的數字」**（#2、#4、#5、#7、#8、#9）：Phase 7 第一天的查證（筆記第 1–6 節）列出了 13 項檢查、密度上限、官方 SDC，但沒有把它們套到我們的設計上試算。每一項試算都只要 10 分鐘到半天。
- **換掉 macro 或換掉判法時，舊的檢查沒有全部重新套用**（#11、#12、#13）：Phase 0 的 `FOREIGN` 檢查、flow 的 KLayout deck、EQY 的 macro 解析，換成自產 SRAM 後都沒有立刻重跑。
- **「做得到但很慢」的量測被排到最後，最後只能寫成已知限制**（#3、#15、#16）：IR 的實際電流、SRAM 的版圖寄生、−40°C 的 SPICE 收斂，都是越晚做越沒有空間改 .lib 或設計，只能放寬。

---

## 2. 當時無法更早知道的項目

這些是工具缺陷、工具在特定版圖上的行為，或外部本來就沒有資料；提早做也看不到，或看到了也只能用同樣方式處理。

| 項目 | 為什麼無法更早知道 | 證據 |
|---|---|---|
| 內部 net 的 slew 0.779 ns，最後 placement 密度 55% → 50% | 工具行為：最後一次 slew 修復之後重新 global routing，把一條原本 78 µm 直線的 net 擠去繞路，之後沒有步驟再檢查 slew。只在特定版圖的局部熱點出現（全晶片使用率約 2%），要繞完才看得到。soc_top 以前用同一個設定解過同類問題（ADR-0009），但沒有數據時先降密度沒有依據。花了約半天、6 個實驗 run | ADR-0019:118–139；`drv-timing-closure` SKILL.md:128–133 |
| `RSZ-0074`：沒接的 inout `analog_io` 讓 resizer 中止 | OpenROAD 把沒接東西的 inout 同時當 driver 與 load；官方範例沒開 GRT 後修復，所以沒有前例。一次 harden 中止在第 41 步，接續即可 | `tapeout-precheck-caravel` SKILL.md:85 |
| resizer 加 ff_100C 後不放大 `a221oi_1`、改插長串 buffer | 同一份輸入單步重跑兩邊數字相同，查到時限為止沒找到原因 | ADR-0019:76 |
| EQY 的 1 個分區證不出來（OpenROAD 對調等價輸入加上 EQY 前處理的共用） | 只有在實際網表上才出現；amend 重試的第一版還造成空洞證明，是 negative test 抓到的 | ADR-0019:155–163 |
| OpenRAM 自身的缺陷：internal_power 寫成 1e11、LVS 失敗仍 exit 0、新 PDK 元件改名讓 LVS 不一致、`PYTHONHASHSEED`、1RW 產不出乾淨版圖 | 第一次產生 macro（10-08 當天）就遇到，已經是最早的時間點 | `openram-macro-characterization` SKILL.md:231–241 |
| Magic DRC 每 157.28 µm 切開錯誤框，框數隨陣列位置變，macro DRC 改比合併後的區域（面積容許 0.05%） | 工具的報告方式，要拿兩顆不同位置的陣列比才看得出來 | ADR-0018:117–120 |
| OpenROAD PSM 直接用 Caravel 跨接線位置當供電點時 Signal 11 | 工具崩潰，原因沒查到，改用 wrapper ring 與 strap 的交點 | ADR-0019:94 |
| Caravel 的 clock jitter 與 duty cycle | 官方沒有數字（PLL jitter 查不到），只能維持假設、記成下線風險與使用限制（管理端時脈 ≤ 22.7 MHz） | ADR-0019:64–66 |
| wrapper 的 golden 誤差暫用 Hazard3 soc_top 的值 | 誤差要多台機器、多次重跑才量得出來；wrapper 三組比較都逐值相同，量不出大小 | ADR-0019:211 |
| 扁平放法（標準 cell 直接放在 wrapper 層）沒有官方範例 | 官方範例都是先 harden 成 macro 再放進 wrapper；#8 的 fill 問題部分源於此（官方範例關掉 fill） | ADR-0019:15；筆記:58、:138 |

---

## 3. 建議加進流程（`arvinsa-rtl-gds-flow.md`）的提早檢查

已經在流程裡的不重複列：pad 階段先查電源進入點（4.1）、每個 corner 的 macro 功能確認（4.3 第 4 項）、flow 的 KLayout deck 跑整顆 macro（4.3 第 3 項）、power signoff 用 max power pattern（4.7）。下面是還沒寫進去、或寫了但放的步驟太晚的。

| # | 放在哪個步驟 | 做什麼 | 通過條件 | 對應的問題 |
|---|---|---|---|---|
| E1 | 4.1 規格與計畫（選定下線平台時） | **平台試算表**：把平台的每一項收件檢查、外殼邊界 SDC、供電結構、fill 規定逐條列出，每條寫「對我們的設計算出來是多少」：例如官方 input transition 對我們的 slew 上限、邊界 hold 需要多少延遲、電源 pad 數與位置、fill 誰補與補完的下限、密度上下限。算不出來的寫成待查並排進第一次 floorplan | 每一條都有數字或明確的「待查＋在哪一步查」；有衝突的（例如 transition 超過上限）在第一次 harden 前已列選項請使用者決定 | #2、#4、#5、#8、#9 |
| E2 | 4.0 環境與釘版 | **flow 與平台的版本對照**：PDK hash、Magic、KLayout、Netgen、DRC deck 的版本，flow 一欄、平台 image 一欄；不同的地方寫明誰的結果算數 | 對照表存在，且平台用的 macro（例如 PDK 預建 SRAM）已用平台的 PDK 版本另外取一份 | #7 |
| E3 | 4.1 規格與計畫（選定平台時） | **需要平台回覆的問題當天送出**：例如自產 macro 的 DRC 怎麼看、已知 deck 問題、fill 由誰做；記下送出日期與回覆 | 問題清單每條都有「已送出（日期）」或「使用者決定不送（原話）」 | #6、#9、#10 |
| E4 | 4.3 macro 第 3 項（產生或選定 macro 後立刻） | **用目標平台的 deck 單獨檢查 macro**，不只 flow 的 deck；違規要能解釋，並在選 macro 時就決定 exit 條件怎麼寫 | 0 個違規；或每條違規都有根因、比對基準（例如和平台自己的預建 macro 位置相同），並經使用者決定 | #6、#7、#12 |
| E5 | 4.3 macro（選 macro 時，早於定 corner 清單） | **選 macro 前在每個 signoff PVT 與「corner 之間」的點（例如 ss 25°C 最低電壓）做讀寫功能檢查**，並 review 未用 port 的控制邏輯（有沒有沒 reset、靠時脈清除的狀態，浮接會不會漏電）。現行 4.3 第 4 項有功能確認，但放在「取得 macro 之後」；要提前到選擇階段，結果影響要不要選這顆 macro | 每個 PVT 讀寫正確；做不到的 PVT 由使用者在「修電路／換 macro／把那個條件寫成使用限制」中選一個，記 ADR | #14 |
| E6 | 4.3 macro 第 5 項（特性化之前） | **先做版圖萃取試跑**（平面輸出、檢查負值電容），能模擬就用萃取網表特性化；只用電路圖時，寄生倍數要用萃取量到的值，不用假設 | 萃取網表在 tt、ss 最慢、ss −40°C 讀寫正確；.lib 的延遲與 transition 不低於萃取值 | #15 |
| E7 | 4.3 macro 第 5 項（每個新量測方法） | **新量法先在修剪網表把每個 PVT（最冷的先跑）跑一次**，確認收斂與量測窗穩定，再開完整網表的長時間 run（skill 規則 27 已有，流程文件沒有） | 5 個 PVT 的試跑都 PASS 平穩度與收斂檢查 | #16 |
| E8 | 4.3 換 macro 時（view QA 之後） | **換 macro 檢查單**：前面 Phase 對舊 macro 做過的每一項檢查（例如 Phase 0 的 `FOREIGN`）逐條重跑；每支 checker 在 positive run 上確認 macro instance 有被讀到（比對對象不是空的） | 舊檢查清單逐條 PASS；每支 checker 的 positive run 印出 macro instance 名稱 | #11、#13 |
| E9 | 4.5 約束與 signoff 條件（第一次 harden 前） | **IR 判法一次定清楚**：預算保護什麼（慢 corner 的 setup）、電流電壓電阻取同一個 corner、電流來源是 max power pattern 的 VCD（firmware 在 RTL 階段就寫好）、供電點從真實 pad 起算；最壞組合只當參考 | `signoff/limits` 的 IR 列寫明 corner、電流來源、供電點模型三項與出處；soc 與外殼用同一套 | #2、#3 |
| E10 | 4.5 約束（採用外殼官方 SDC 時） | **邊界約束的試算**：官方 input transition 與自己的 slew 上限並排比；用 source latency min／max、input delay、預估 clock tree 算邊界 hold 需要的延遲，決定 hold 餘量與 resizer 要看的 corner | 衝突項目在 harden 前已有使用者決定；第一次 harden 的邊界 hold、slew 沒有意外 | #4、#5 |
| E11 | 4.6 第一次探索 harden 之後（外殼設計） | **對探索 GDS 跑一次平台的完整收件檢查（查證用）**，順便量 VM 記憶體；至少跑密度檢查（本機 KLayout 約 1.5 分鐘）。fill／decap cell 的選擇依結果決定 | 除了已知、已決定的項目，其他全 PASS；VM 記憶體峰值低於配置的 80% | #8 |
| E12 | 4.6 harden 的 signoff（每次） | **把平台的密度上下限做成 harden 內的 checker**（li1 上限、金屬下限依 E1 的結論），不要等 precheck（約 1 小時）才知道 | 密度在平台上下限內；下限若由平台 fill 處理，checker 印出依據與確認狀態 | #8、#9 |
| E13 | 4.8／4.9（每支新 checker 寫完時） | **新 checker 寫完就做獨立的漏洞審查**（植入錯誤＋對照組），不要只在 Phase 收尾審；收尾時只審最後改過的 checker | 每支新 checker 有獨立審查紀錄與 negative test；收尾審查沒有新的高、中嚴重度漏洞 | #17 |
| E14 | 全程（`runs/todo.md`） | 決定「之後再修」的項目，在決定的同時寫進待辦 | 每個「延後處理」的決定在待辦裡有一列 | #12 |

---

## 4. 使用者的例子：低溫讀取失敗，Phase 6 的部分

**修正花了多少**：
- 讀取失敗的重現、比較兩種修法、版圖 patch、2 KB 重產與 7 個條件的讀取確認，全部在 2026-10-08 一天內完成（ADR-0018 決定 3、7、8、9 都是 10-08；筆記 `openram_phase6_bringup.md`:103–251）。計畫原本估「修讀取電路另加 2–3 天」（`project-plan.md` §8 Phase 6），實際約 1 天。
- 修讀取電路時順便發現 `clk1` 接 0 的上電風險（patch 改變了 SPICE 的初始解才暴露），這個問題從 Phase 1 的 RTL 就在，預建 macro 同樣有（ADR-0018:50–53、已知限制:143）。
- 真正花時間的是修完之後的事：功耗與漏電量法約 2 天（#16，問題多在 −40°C）、macro DRC 修正與兩輪白跑的 harden（#11、#12）、萃取到最後才做（#15）。

**如果 Phase 3 選 macro 時就做所有 PVT 的功能檢查，會不會改變選擇**：
- 會看到的結果：預建 2 KB SRAM 在 ss −40°C、tt −40°C，**以及 ss 25°C 1.60 V（室溫）**都讀成前一次的值（ADR-0010:82–85；Phase 6 步驟 3a 用同一支程式重現）。
- **拿掉 −40°C corner 不會讓它變安全**：ss 25°C 1.60 V 不是 STA corner 也會錯；而 Caravel 的規格本來就是 Tj −40～100°C、VCCD 最低 1.62 V（`signoff-criteria` SKILL.md:44，Phase 3 `d31b52b` 就寫了），−40°C corner 本身是對的。問題不在「把 −40°C 放進 signoff」，而在「放進去之前沒有確認 macro 在那裡能動」，結果 Phase 3.5–5 的 ss_n40C 時序收斂有一部分是對著佔位 .lib 做的（ADR-0013:54）。
- 選擇會怎麼變（推測）：「2 KB OpenRAM SRAM」這個大方向大概不變（專案要學 SRAM macro 整合，不用 bitcell 的 RAM 面積與性質不同，沒有評估過）；會變的是「先用預建、Phase 6 再自產」的順序。Phase 6 已經證明預設設定的自產 macro 也會讀錯（ADR-0018:19–23），所以一定要修電路，而修電路只有自產做得到。若 Phase 3 就知道，合理的選擇是直接自產並修讀取電路，省掉 Phase 3.5 對預建 macro 的整套特性化與 Phase 3.5–5 對佔位 .lib 的收斂；流程文件已把這點寫成建議（`arvinsa-rtl-gds-flow.md` 4.3 開頭：「同樣的特性化與整合做了兩次」）。
- 對 Phase 6–7 的持續影響：−40°C 仍是最緊的 corner。wrapper 與 soc_top 的最差 setup 都在 min_ss_n40C 的 SRAM 半週期路徑（`phase7.md`:57、`phase6.md`:65），換上萃取量到的 dout0 transition 後 wrapper 只剩 +0.151 ns（#15）。所以「選 macro 時就做每個 PVT 的功能檢查」之外，E6（特性化前先萃取）對下一顆設計一樣重要。

---

## 5. 查證方式與限制

- 只讀檔案與 git，沒有跑 EDA 工具。來源：ADR-0018、ADR-0019、`docs/phase_exit/phase6.md`、`phase7.md`（草稿）、兩份筆記、`runs/todo.md`、`runs/p7_review/`、`runs/p7_exit_draft/`、各 skill 的經驗紀錄、`git log`。
- 時間都是從 commit 時間與 ADR 記的 run 時間粗估；commit 間隔包含等待與其他工作，只能當上限。
- `runs/` 不進版控，引用的 `runs/...` 檔案（例如 `runs/todo.md` 的 met4 1.6 µm pattern IR 28.25 mV）沒有 commit 可以追溯。
- 「提早的成本」與「會不會改變選擇」是推測，依據是同一件事在本專案實際花的時間。
