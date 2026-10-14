# 流程回顧：Phase 0–3 哪些事看得太晚（2026-10-14）

**結論（最重要的 5 項）**
1. **signoff 條件到 Phase 3 收尾才推導**（`d31b52b`，10-03 23:41）。Phase 2、3 是用 LibreLane／PDK 預設值收斂並判 PASS 的。加嚴之後，40 ns 就不過了，週期改成 42 ns；15 個 corner 全交給 resizer 時它跑不完，只好讓 resizer 只看 9 個。這個缺口一路影響到 Phase 5（ss −40°C 差 4.16 ns，週期再改 44 ns）。應該在任何 harden 之前推導，並在 Phase 2 單獨 harden CPU 時，就讓 resizer 用完整的 corner 清單跑一次。
2. **你舉的 SRAM 例子：「一開始就不該放 ss −40°C corner」這個假設不成立。** 這個 corner 是 10-03 為了標準元件的溫度反轉，以及 Caravel 的接面溫度 −40°C 而建議的，10-04 加入，跟 SRAM 無關。SRAM 讀取失敗是 10-05 才發現的，而且正因為特性化照著 STA corner 跑了 ss −40°C 才發現。這顆 SRAM 在 ss 25°C 1.60 V、tt −40°C 1.60 V（都不是 corner）也會讀錯，拿掉 corner 只是讓 STA 看不到，晶片照樣壞。
3. **該提早的是「macro 驗證過的條件」對「晶片要操作的條件」。** 計畫第一版（`73f7524` §5.4）就寫了矽量測只到 ≥1.7 V，比 ss corner 的 1.60 V 還高，這個落差在 Phase 0 就看得到。再用 PDK 附的 SPICE 網表，在每個 PVT 做一次讀寫功能模擬（推算約半天），就能在選 macro 時直接決定自產並修讀取電路，不用把特性化與整合做兩次（Phase 3.5 約 19 小時，量的那顆 macro 後來被換掉）。
4. **IR 的供電模型與電流模型分四個 Phase 才修完**（Phase 4 一側供電 → Phase 5 met5 加寬 → Phase 6 浮接電流 → Phase 7 Caravel 真實供電與 max power pattern）。Phase 3 的 0.3 mV 是「PDN pin 全當理想電源」算出來的，當時沒人懷疑。Caravel 從計畫第一天就是首選平台，Phase 3 做 floorplan 時就能用 pad 位置與 gate-level 模擬的切換活動估 IR。
5. **工具預設值與 standard cell library 的 QA 做得太晚。** Phase 0 的參考設計已有 74 個 max slew 違規，當成「與官方相符」只列不判。Phase 2 花了 9 輪才找到寄生估計表沒啟用、弱 cell 沒排除這些根因。同類的弱 cell 問題在 Phase 5 讓 resizer 失控 108 分鐘、記憶體用到 92.9 GB。

範圍：Phase 0–3（10-03 08:15 → 10-04 02:46，約 18.5 小時，commit 時間推算）。多數代價出現在 Phase 3.5–7，表中跨 Phase 的部分都有標明。時間全部從 `git log --date=iso` 的 commit 時間粗估，不是實際工時。

---

## 1. 處理很久或放寬要求的項目

| # | 問題（白話） | 花了多少（時間、輪數）或放寬了什麼 | 什麼時候發現（Phase、commit） | 最早可以在哪裡發現、用什麼檢查 | 提早的成本 | 證據 |
|---|---|---|---|---|---|---|
| 1 | **signoff 條件晚推導**：Phase 2、3 用的 corner、IR 上限、uncertainty 都是 LibreLane／PDK 預設，沒有說明各項成分。缺的有 duty cycle 預算、min pulse width、溫度反轉 corner、IO hold，IR 上限 90 mV 也和 ss corner 的 1.60 V 不一致 | Phase 4：harden-soc 跑了 5 次（08:31 → 11:53，約 3.5 小時），`make regress` 跑了 4 次。**放寬**：週期 40 → 42 ns（使用者決定）；resizer 只看 9 個 corner（`RSZ_CORNERS`）；「nom_tt setup ≥ 週期 10%」降為只報告。Phase 2、3 的 exit PASS 事後看來用的條件不足 | Phase 3 收尾，`d31b52b`（10-03 23:41）的 signoff criteria 調查 | **Phase 0／1，任何 harden 之前**：依晶片規格（Caravel VCCD 1.62–1.98 V、Tj −40～100°C）推出 corner 清單、IR 預算、DCD、pulse width、IO 約束。流程文件 4.5 已經寫「第一次 harden 前」，但沒有強制，而且 4.4 子區塊 harden 排在它前面 | 低。當時是 3 個 agent 調查加 3 個 agent 核對，`d31b52b` 在 Phase 3 最後一小時內完成（推算 1–2 小時） | `docs/notes/signoff_criteria_soc_top.md` 21–44；`docs/phase_exit/phase3.md` 169–177；`docs/phase_exit/phase4.md` 39–42、96–99；ADR-0004 8–14 |
| 2 | **resizer 看不到溫度反轉 corner**：15 個 corner 全給 resizer 時 `RepairDesignPostGRT` 跑不完，改成只給 9 個，ss −40°C 只在 signoff 判 | **放寬**：靠「ss 100°C 多留 0.6 ns」代替。Phase 5 Hazard3 版的長路徑在 ss −40°C 差 4.16 ns（81 條違規），連帶做了 ADR-0013、0014、0016，週期 43 → 44 ns（10-07 00:14 → 17:31，約 17 小時，其中一部分是 Hazard3 本身的因素）。Phase 7 決定 17 再遇到一次：resizer 加 ff_100C 後壅塞失敗 | Phase 4 第 1 次 harden-soc（`cf021df` 前後，10-04）；長路徑的後果在 Phase 5（`d00214d`） | **Phase 2 單獨 harden PicoRV32 時**，用完整的 15 corner（PVT 清單先由 #1 決定）跑 resizer，記錄每一步的執行時間與記憶體。跑不完就在那時決定「沒給 resizer 的 corner 怎麼保護」 | 低。單獨 harden 一次約 15 分鐘（`phase2.md` 31），多一兩輪 | `.claude/skills/multicorner-sta/SKILL.md` 57；ADR-0013 6–12；ADR-0004 25–28；ADR-0019 決定 17（73–76 行） |
| 3 | **SRAM 在低溫與 ss 低電壓讀出前一次的值**（你舉的例子，跨 Phase 3.5–6）。附帶：PDK 的 .lib 是解析模型，padded.lib 沒有 dout0 的 hold 弧（實際在上升緣後約 1 ns 就被拉回），Phase 3、4 的 STA 完全沒檢查這條 hold | Phase 3.5 約 19 小時（`d60550f` 10-04 22:32 → `e16465b` 10-05 17:49），量的是後來被換掉的 macro。**放寬**：ss −40°C 用佔位 .lib，那個 corner 的 STA PASS 不代表 SRAM 能動；列為「頭號下線風險」，直到 Phase 6（10-11）才解除。特性化與整合做了兩次（流程文件 4.3） | Phase 3.5，10-05（`ccc536c`）；hold 弧是 10-04 Phase 3.5 試跑時發現 | **Phase 0 選 macro 時**：（a）列出 macro 驗證過的條件（矽量測 ≥1.7 V、室溫；OpenRAM 預設特性化只有 0／25／100°C、1.7–1.9 V），和晶片的操作範圍比。計畫 §5.4 第一版就有 ≥1.7 V 這項，低於 ss corner 的 1.60 V。（b）用 PDK 附的電晶體級網表（`libs.ref/sky130_sram_macros/spice/`），在每個 PVT 與 corner 之間的溫度做讀寫功能模擬；序列要包含「連續兩次讀到相反值」 | 中低（推算約半天）：修剪網表加讀寫序列，TT 一次約 7 分鐘（`.tran 100p`），完整網表光讀檔就超過 35 分鐘。5–7 個條件可以平行跑 | ADR-0010 15、26–28、72–105、176；`project-plan.md` 166（`73f7524` 已有）；ADR-0018 19–24、46–49；`docs/phase_exit/phase6.md` 7 |
| 4 | **IR 的供電模型與電流模型**：Phase 3 的 0.306 mV 是把 PDN 的所有 pin 當成理想電源算的，電流用 OpenSTA 的預設切換率 | 分四個 Phase 修：Phase 4 IR 研究（16 種組合，4 種供電模型差 100 倍）；Phase 5 Hazard3 最壞組合 25.75 mV，met5 1.6 → 4.8 µm、重建 golden（ADR-0017）；Phase 6 兩個 ff corner 都跑、加浮接電流；Phase 7 Caravel 真實供電「只從上側」143 mV、met4 改 4.8 µm，一度訂成對板子的供電要求 ≥1.65 V，改用 max power pattern 後才取消（決定 18–20，10-13 00:03 → 02:11）。**推測、未驗證**：預設切換率高估約 2.2 倍，Phase 5 的 met5 加寬若當時就用 pattern 電流，可能不需要 | 供電模型：Phase 4（`07d6d8e`，10-04）；Caravel 供電：Phase 7（`a200073`）；pattern 電流：Phase 7（`c64b3bf`） | **Phase 3 floorplan（流程 4.1／4.5）**：Caravel 從計畫第一版就是首選平台（§5.5），電源 pad 位置那時就查得到。gate-level 模擬在 Phase 3 已經可以跑（`make gl-soc`），可以錄 CPU max power pattern 的 VCD 給 IR 用 | 中低：Phase 7 一晚做完供電點模型與 pattern 錄波（推算幾小時） | `docs/phase_exit/phase3.md` 37、55、165；`.claude/skills/pdn-ir-drop/SKILL.md` 76；ADR-0017 1–12；ADR-0019 決定 18–20（81–117 行） |
| 5 | **工具預設值沒有驗證**：Phase 0 的參考設計（`test_sram_macro`）max slew 違規 74、max cap 2，因為和官方相符就只列不判。Phase 2 才查到根因：繞線前的寄生估計表沒啟用（`LAYERS_RC` 在 LibreLane 原始碼裡被註解掉，估計值 0.08 對實際 0.178 fF/µm）、slew 只修一次、CTS 末端 fanout | Phase 2 試跑 9 次（約 12:37 → 16:45，約 4 小時），第 1 次 slew 違規 5544 個 | Phase 2，`4c1a955` | **Phase 0 重跑參考設計時**：參考設計的每個 DRV 違規都要查出原因，不能只比對「和官方一樣」；比對繞線前估計與繞線後萃取的線電容 | 低：參考設計小，多查一兩輪（推算 1–2 小時） | `signoff/golden/ci_sram_ref/README.md` 24–36；`docs/phase_exit/phase2.md` 33–42；`pnr/picorv32_core/README.md` 44–67 |
| 6 | **standard cell library 的弱 cell**：驅動力弱到推最小的 buffer 就超過 slew 上限的 cell，resizer 照樣會用。Phase 2 先遇到 `clkdlybuf4s25_1`；Phase 5 遇到 `a2111oi_1`，resizer 在同一點無限插 buffer | Phase 5：`RepairDesignPostGPL` 跑了 108 分鐘、記憶體 92.9 GB（機器 24 GB）。從停掉到修好的 commit 約一天（10-05 22:12 → `2251c4a` 10-06 22:57，含夜間） | 第一次：Phase 2；第二次：Phase 5（ADR-0012） | **library QA，在每次改 slew 上限或餘量時跑**：每個 corner、每個 resizer 可用的 cell，查表確認推 resizer 最小 buffer 的輸入電容時 slew 不超過上限（現在的 `pnr/check_weak_cells.py`）。注意：用 Phase 3 的設定（0.75 ns、30%，上限 0.525 ns）時 `a2111oi_1` 是 0.501 ns，抓不到；Phase 4 把 PnR 上限改成 0.70 ns（上限 0.49 ns）時跑一次就會抓到 | 很低：查表腳本跑幾秒 | ADR-0012 6–12、24；`docs/notes/repair_design_loop.md`；`pnr/picorv32_core/README.md` 44 |
| 7 | **placement 目標密度與 L 形 logic 區**：LibreLane 自動算出 68%，cell 擠在 SRAM 轉角，線大幅繞路（端點相距 117 µm、繞了 353 µm） | Phase 3 為 ss corner 的 max slew 跑了約 8 次（explore2–11 加正式 run 1；17:14 → 23:06 這段的大半，推算 3–4 小時）。**放寬又撤回**：signoff max transition 一度放寬到 1.0 ns（ADR-0009）。Phase 7 又遇到一次：wrapper 密度 55 → 50%（決定 21） | Phase 3（`654c303` 之前的試跑） | **Phase 2 決定 DIE_AREA 時**（ADR-0006）：用整顆 SoC 加 macro 跑到 PDN 與 global placement，看 `GPL-0052` 的目標密度和 logic 區實際使用率差多少，以及 global routing 的壅塞。順便也會抓到 SRAM 上方窄 row 的 `PDN-0179` | 低：只跑到 global routing 一輪（推算 10–20 分鐘） | ADR-0009 3、12–28；ADR-0006 38–42；`.claude/skills/floorplan-congestion/SKILL.md` 21；ADR-0019 決定 21（118 行） |
| 8 | **macro clock 的 CTS 結構**：OpenROAD CTS 為了讓 `sram0/clk0` 和 flip-flop 的 latency 對齊，在前面插了 10 顆 delay buffer，上升緣與下降緣延遲不同。結果是 SRAM 的半週期 setup 變差，讀出端的 hold 也要補 | Phase 4：SRAM 輸入 hold 在 min_ff_n40C −0.088 ns，resizer hold 餘量改 0.3 ns，hold buffer 多 984 顆。Phase 3.5：0.3 ns 餘量在每個 `rdata_q` 前插了 delay cell，半週期 setup 不夠，週期 42 → 43 ns。Phase 5：自訂 CTS step（ADR-0016），兩份 golden 重建 | Phase 4（cts-clock-tree 經驗紀錄 10-04）；根因在 Phase 5（`adac1a9`）確認 | **Phase 3 第一次整合 macro 時**：看 CTS 在 macro clock pin 前插了什麼、macro 的 rise／fall latency 和 flip-flop 差多少，並找出半週期路徑。Phase 3 調查時已量到 clk0 的 rise／fall latency 差約 0.30 ns（nom_ss），只是沒追下去。現在有 `check_soc.py cts_macro_latency`（P58）。delay buffer 在 Phase 3 版圖裡是否已經存在，**未查證** | 低：讀一次 CTS 報告與 STA 路徑（推算不到 1 小時） | ADR-0016 3–12；`.claude/skills/cts-clock-tree/SKILL.md` 54；ADR-0004 17–22；`docs/notes/signoff_criteria_soc_top.md` 80 |
| 9 | **最終 GDS 裡 macro 有沒有內容，沒有自動 checker**：Phase 3 只手動確認一次「161 個 SRAM cell 都接得到」，LVS 又把 SRAM 當 black box | Phase 6：自產 macro 的 LEF 沒有 `FOREIGN`，KLayout 輸出的 SRAM 是空的，LVS 照樣 PASS（XOR 差異幾百萬才看出來），多跑一次 harden，再補 checker（`3ceca55`、P67–P69） | Phase 3 時就知道沒有 checker（exit 第 1 項）；出事在 Phase 6（10-10） | **Phase 3 第一次整合 macro 時**就寫成 checker：最終 GDS 裡的 macro 要和 macro 自己的 GDS 相同（現在的 `scripts/check_macro_gds.py`） | 低：一支 checker 加 negative test（推算 1–2 小時） | `docs/phase_exit/phase3.md` 21；`project-plan.md` 384；流程文件 4.3 第 2 點 |
| 10 | **RTL → 合成網表沒有 formal，firmware 也沒用到部分功能**：計畫的 L4 是證明 RTL 對最終網表等價，但 Yosys 會重新編碼狀態機，所以做不到。另外 `rdcycleh`／`rdinstreth`、bus-error IRQ 從沒被任何測試用過 | **放寬**：EQY 改成證明合成網表對最終網表（Phase 3），到 Phase 7 都沒變。Phase 2 植入的 3 個錯誤 GL 模擬抓不到，Phase 4 才補 directed 測試 | 覆蓋缺口：Phase 2 的植入錯誤；formal 範圍：Phase 3（合成 log 的 `Recoding FSM`） | **Phase 1**：RTL regression 量 code coverage（line／toggle／FSM，Verilator 的 coverage 功能），沒用到的功能當場補測試或記錄原因；拿 CPU 試一次 EQY RTL 對合成網表，確認 formal 涵蓋到哪裡，再定 L4 的範圍 | 低：coverage 約 1 小時，EQY 試跑約 1 小時（推算） | `docs/phase_exit/phase2.md` 102–106；`docs/phase_exit/phase3.md` 140、178–181；`docs/phase_exit/phase4.md` 84–90；`signoff/eqy/README.md` 19 |
| 11 | **golden 比對的誤差一修再修**：同樣設定重跑結果不同（多執行緒 detailed routing，後來 global routing 也會） | Phase 2 第一次 `make phase2` 判 FAIL；Phase 4 `make regress` 第 2 次 FAIL（每次約 2 小時）；Phase 5 ADR-0015（harden 6、7 的 golden FAIL），之後改用 4 次 run 定誤差；Phase 7 決定 22 | Phase 2（`4c1a955`）起，每換一個設計就遇到一次 | **部分可提早**：建 golden 時先用同一設定重跑至少 4 次（含一次乾淨 checkout），依每一類 metric 實際的差異定誤差，不要只對「這次剛好不同」的那幾類給。但新的不可重現來源（Phase 5 的 global routing）要等設計變大才出現 | 中：每個設計多 2–3 次 harden（PicoRV32 約 15 分鐘一次，SoC 約 20 分鐘一次） | `docs/phase_exit/phase2.md` 44–56；`.claude/skills/flow-regression-reproducibility/SKILL.md` 82；ADR-0015 1–12；`71b1454` |
| 12 | **乾淨 checkout 才出現的問題**：`gl-soc` 沒有依賴 `fw`；新的 negative test 腳本加進 `make phase3` 前沒單獨跑過；Phase 5 的 xPack 不在 worktree | Phase 3 的 `make phase3` 跑 4 次才 PASS，第 2、3 次就是這兩個問題（00:01 → 00:50 修正，加上重跑，每次最長 91 分鐘）；Phase 5 一次 regress FAIL | Phase 3 收尾（`acbc126`、`53529c6`）；Phase 5（`7348fab`） | 每加一個 target，先在乾淨 worktree 單獨跑一次再放進長 regression。現在已經寫進 skill（`phase-exit-review` positive control、`make py-check`、dev fixture） | 很低 | `docs/phase_exit/phase3.md` 9–13、135–136；`.claude/skills/signoff-checker-qualification/SKILL.md` 136–137 |
| 13 | **下線平台的 precheck deck 比 flow 用的 deck 新**（跨 Phase 7）：OpenRAM bitcell 在 precheck 報 `MR_mcon.CON.10`、`MR_licon.SP.6`，這是 2026-05 拿掉豁免造成的，專案開始前就已經生效 | **放寬（有比對）**：`klayout_feol`／`klayout_beol` 只允許這兩條規則，而且要和預建 macro 一致（ADR-0019 決定 5）。影響小，當天就定案 | Phase 7（10-12） | Phase 0：平台已經選定時，拿含預建 SRAM 的最小設計跑一次官方 precheck | 中：Apple Silicon 要架 VM 與 Rosetta（Phase 7 步驟 2 約 1.5 小時：`f316425` → `cc60b85`）。**影響小，優先度低** | ADR-0019 決定 3–5（16–27 行）；`.claude/skills/tapeout-precheck-caravel/SKILL.md` description |

### 第 3 項（SRAM 低溫）的時間順序與因果

| 時間 | 事件 | 出處 |
|---|---|---|
| 10-03 08:15 | 計畫第一版寫明：1 KB macro 的矽量測只在 ≥1.7 V 不出錯，PDK 的 .lib 是解析模型 | `73f7524` 的 `project-plan.md` 166 |
| 10-03 23:41 | signoff criteria 調查建議加 `ss_n40C_1v60`、`ff_100C_1v95`。理由：1.60 V 下多數標準元件低溫反而比較慢（`dfxtp_1` CLK→Q 在 ss −40°C 比 ss 100°C 慢 11%），而且 Caravel Tj 是 −40～100°C。**理由跟 SRAM 無關** | `d31b52b`；`docs/notes/signoff_criteria_soc_top.md` 26；`.claude/skills/signoff-criteria/SKILL.md` 44 |
| 10-04 10:17 | 15 個 corner 進入 config（Phase 4） | `cf021df` |
| 10-04 | 40 ns 不過、改 42 ns。原因是標準元件在 ss −40°C 較慢，加上 DCD 預算與 derate；這時 SRAM 用的還是 padded.lib 的假設值，跟讀取失敗無關 | ADR-0004 8–12 |
| 10-04 | 使用者決定用 ngspice 量 PDK 網表，**5 個 PVT 照 STA corner 選**，所以包含 ss −40°C | ADR-0010 33–40 |
| 10-05 | ss −40°C 1.60 V 每次讀取都錯；ss 25°C 1.60 V、tt −40°C 1.60 V、ss −40°C 1.70–1.95 V 也錯。改用佔位 .lib，列為頭號下線風險 | ADR-0010 72–105；`ccc536c` |
| 10-08 | 自產 macro 在 sense amp 輸入端加預充電，7 個條件都讀對 | ADR-0018 決定 8；`docs/phase_exit/phase6.md` 7 |

**評估「一開始就不該放進 signoff corner」**：
- **不成立。** corner 代表晶片實際要操作的條件（Caravel Tj −40°C、VCCD 最低 1.62 V），不是為了 SRAM 加的。拿掉它，SRAM 的問題仍在。標準元件的溫度反轉也會沒人檢查：Hazard3 的長路徑在 ss −40°C 差 4.16 ns，在 ss 100°C 卻是 +1.48 ns（ADR-0013 第 2 點），沒有這個 corner，這種錯誤會直接做到晶片上。
- **SRAM 的失敗不限於 −40°C**：ss 25°C 1.60 V 也失敗（界線在 25–60°C 之間）。即使把操作溫度限縮到 0–85°C 也救不回來，要嘛 VDD 最低到 1.7 V 以上（但 Caravel 最低 1.62 V），要嘛修電路。
- **這個 corner 實際的作用**：它讓 SRAM 特性化去量 ss −40°C，才在下線前發現問題。它的代價是 ss −40°C 成為限制週期的 corner（40 → 42 ns，主要來自標準元件），以及一段時間用佔位 .lib。
- **比較好的提早做法**：Phase 0 選 macro 之前，先比「macro 驗證過的範圍」與「晶片的操作範圍」。這個落差在計畫第一版就看得到。不夠的部分，用 PDK 附的 SPICE 網表在所有 PVT 做讀寫功能模擬。若 10-03 就知道結果，可以直接選「自產並修讀取電路」（流程文件 4.3 已經這樣建議），省掉 Phase 3.5 對預建 macro 的特性化，以及「預建 → 自產」的第二次整合（推算省 1–2 天）。Phase 6 曾考慮的 `words_per_row = 1` 放不進 1000 × 800 µm 的 die（ADR-0018 47 行），所以提早知道也會影響 Phase 2 的 DIE_AREA。

---

## 2. 看起來很晚、但當時無法更早知道的

| 項目 | 為什麼無法更早 | 出處 |
|---|---|---|
| `GRT-0229` 隨機中止 | OpenROAD 的隨機錯誤：同一份輸入單步重跑 4 次，只中止 2 次。第一次乾淨 checkout 就遇到，算是早的；有上限的重試是合理處理，根因在 OpenROAD 裡 | `docs/notes/grt0229_repro.md`；`docs/phase_exit/phase3.md` 70–74 |
| 每個新設計的不可重現來源 | Phase 0 的參考設計連跑 3 次完全相同；`RepairDesignPostGRT` 的 global routing 不可重現要到 Hazard3 才出現（27 次中 5 次不同）。只能每個設計各自量（見 #11 的「部分可提早」） | ADR-0015 6–10 |
| resizer 換尺寸時只看第一個讀進來的 .lib（tt） | OpenROAD 內部行為，要到 Phase 5 單步重跑才查到。#6 的弱 cell 查表能擋住症狀，但機制本身無法預知 | ADR-0012 9 |
| Hazard3 長路徑在 ss −40°C 的大幅退化 | 依設計而定（`or4` 鏈每顆約 2 ns）。可以提早的是 #2「resizer 看得到所有 corner」這個流程問題，不是這條路徑本身 | ADR-0013 第 2–3 點 |
| 繞線後的估計對長路徑偏樂觀（ADR-0014） | 差距隨設計大小與路徑長度變大，PicoRV32 時不明顯。現在靠每次 harden 後的 criteria review 抓 | ADR-0014 6–12 |
| clock jitter 與 duty cycle 的數值 | 到 Phase 7 也沒有平台資料，仍是假設，列為下線風險 | ADR-0019 決定 15（64 行） |
| SI、dynamic IR、aging | 開源工具不分析，只能用 uncertainty 的成分涵蓋 | `docs/notes/signoff_criteria_soc_top.md` 30、39 |
| 第一次跑就失敗、當場修好的工具問題：abstract DRC 的 `nwell.4` 假錯誤、Magic GDS 有 13 個 top cell、SRAM 上方窄 row 的 `PDN-0179` | 各在一次試跑內找到並修好，提早也省不了多少。`PDN-0179` 若照 #7 做 floorplan 試跑會順便抓到 | `pnr/soc_top/README.md` 試跑紀錄 94–96 |
| SRAM 的 Magic DRC 不是 0、LVS 是 black box | 計畫就已知道（R3），照 §6.3 設計的方式處理，不算太晚 | `project-plan.md` §6.3、§9 R3 |
| Caravel 邊界的細節（`analog_io` inout 造成 `RSZ-0074`、Wishbone 輸入的 hold） | 要有 wrapper 與邊界決定（clock 用 `wb_clk_i`、腳位怎麼對應）才會出現，這些到 Phase 7 才定（ADR-0019 決定 8–10、14） | ADR-0019 決定 14、17 |
| 金屬密度不足 | Phase 3 就測到並記錄，正確地延到平台 fill 處理 | `docs/phase_exit/phase3.md` 164 |

---

## 3. 建議加進 `arvinsa-rtl-gds-flow.md` 的提早檢查

「已有」表示流程文件已經寫了，要改的是位置或強制方式。數字門檻標「建議」的是我的提議，需要使用者決定。

| # | 放在哪個步驟 | 做什麼 | 通過條件 | 對應問題 |
|---|---|---|---|---|
| E1 | **4.1 規格與計畫**（新增） | 寫一張「操作範圍對照表」：晶片要操作的 VDD 範圍與接面溫度（來自平台規格），對照每個 macro／IP 驗證過的條件（矽量測、廠商特性化 corner），以及 standard cell library 的特性化 PVT | 每個 macro 驗證過的範圍都涵蓋操作範圍；沒涵蓋的列成「選定前要 SPICE 確認」，由使用者決定 | #3 |
| E2 | **4.3 第 4 點，移到「選定 macro 之前」**（已有，改位置） | 用廠商或 PDK 附的電晶體級網表，在每個 STA PVT、corner 之間的溫度（例如 ss 25°C 最低 VDD）做讀寫功能模擬，序列包含連續兩次讀到相反值。修剪網表要先在一個點和完整網表對照 | 所有條件讀寫正確，才把這顆 macro 寫進計畫；FAIL 時先列選項（換 macro、自產並修電路、改規格） | #3 |
| E3 | **4.5，排到 4.4 之前並強制**（已有文字，沒有強制） | signoff 條件（corner 清單、IR 預算、DCD 與 jitter、pulse width、IO 約束的來源）在**任何** harden 之前推導，包括子區塊單獨 harden | `signoff/limits/<tag>.toml` 每一列都寫明出處；`make harden-*` 開頭檢查 limits 檔存在、corner 清單等於規格推出來的清單（建議做成 `check_inputs.py` 的一列，加 negative test） | #1 |
| E4 | **4.4 子區塊單獨 harden**（新增） | resizer 用完整的 STA corner 清單跑一次，記錄每個修復步驟的時間與記憶體 | 跑完，或在那時由使用者決定「沒給 resizer 的 corner 怎麼保護」並記成 ADR（不要用固定餘量代替長路徑，ADR-0013 第 3 點） | #2 |
| E5 | **4.0 環境，重跑參考設計時**（擴充 `make ci-sram-ref`） | 把參考設計當成工具預設值的 QA：（a）每個 DRV 違規都查出原因；（b）比對繞線前估計與繞線後萃取的線電容；（c）用規劃的 slew 上限與餘量，對 library 跑弱 cell 查表（`check_weak_cells.py`，所有 signoff corner） | （a）違規 0，或每個都有原因；（b）估計對萃取的比例落在約定範圍內（建議 ±30%，需決定）；（c）排除後沒有弱 cell。之後改 slew 上限、餘量或 corner 時重跑（c）；harden 前的 `weak_cells` 檢查已有 | #5、#6 |
| E6 | **4.4 定 die 尺寸時**（新增） | 整顆 SoC 加 macro，只跑到 PDN、global placement 與 global routing | PDN 沒有窄 row 錯誤；`GPL-0052` 目標密度不高於 logic 區使用率加約定餘裕；global routing 溢位為 0。出 floorplan 圖（`scripts/plot_floorplan.py`）給使用者看 | #7 |
| E7 | **4.1 供電規劃加 4.2 之後**（部分已有：4.1 有供電進入點） | IR 模型在 floorplan 試跑時就成立：供電點來自平台的真實 pad；gate-level 模擬一能跑，就錄 CPU max power pattern 的 VCD 當電流 | floorplan 試跑的 IR（pattern 電流、兩個慢 corner、真實供電點）≤ 預算；預設切換率的結果只當參考。IR 結果比預算小 100 倍以上時，先檢查供電模型 | #4 |
| E8 | **4.6 第一次整合 macro 的 harden 後**（新增） | 檢查 macro clock：CTS 在 macro clock pin 前插了什麼、macro 的 rise／fall latency 與 flip-flop 的差、半週期路徑有哪些 | 沒有預期外的 latency 對齊 buffer，或已記錄決定；`check_soc.py cts_macro_latency` 這類結構 checker 從第一次整合就啟用 | #8 |
| E9 | **4.3 第 2 點**（已有 `check_macro_gds.py`） | 強調：第一次整合任何 macro 時就啟用「最終 GDS 的 macro 等於 macro 自己的 GDS」，不要等出事；手動確認不算 | checker PASS，negative test（清空 macro、改一個方塊）FAIL | #9 |
| E10 | **4.2 RTL 驗證**（新增） | RTL regression 量 code coverage（line、toggle、FSM）；用一個區塊試 EQY RTL 對合成網表 | 沒用到的功能都有 directed 測試，或記錄原因；L4 formal 的範圍依試跑結果寫進計畫，不要等到網表階段才縮小 | #10 |
| E11 | **4.6 建 golden 時**（部分已有：skill 有誤差規則） | 同一設定至少重跑 4 次（含一次乾淨 checkout），依每一類 metric 的實際差異定誤差 | 4 次彼此都在誤差內；誤差表寫明每一類用了幾個樣本 | #11 |
| E12 | **4.0 環境，平台已選定時**（新增，優先度低） | 拿含選定 macro 的最小設計跑一次平台官方 precheck | 除了已知、可解釋的規則外全部 PASS；已知的規則先定判定方式 | #13 |

E3、E4、E5 的成本最低、影響最大，建議優先放進流程。E1、E2 直接回答使用者的例子。

---

## 附：方法與限制
- 只讀檔案與 git，沒有跑任何 EDA 工具，也沒有修改受版控的檔案。
- 時間全部從 commit 時間推算。commit 是在工作做完後才建立，中間有夜間與平行工作，所以只能看量級。
- 標「推算」「推測」「未查證」的不是量測結果，主要有：#4 的 met5 加寬是否必要、#8 的 delay buffer 在 Phase 3 是否已存在、各項「提早的成本」。
