# arvinsa-rtl-gds

以全開源 EDA 工具鏈建立一條可重複執行、有 regression test 的 RTL-to-GDS 流程，
並以開源 RISC-V SoC（含 SRAM macro）當 test vehicle，一路跑到 signoff（DRC／LVS／STA PASS）。

An open-source RTL-to-GDS flow on SkyWater sky130A using LibreLane and OpenRAM SRAM macros,
with RISC-V cores (PicoRV32, then Hazard3) as test vehicles. Documentation is written in Traditional Chinese.

## 專案狀態

**實作中（2026-10-04）：Phase 0–4 完成，下一步 Phase 5（Phase 3.5 可選）。** 完整規劃見 [project-plan.md](project-plan.md)。

- Phase 0：Nix、LibreLane 3.0.14、sky130A PDK 已安裝；LibreLane 官方的 SRAM 參考設計在本機重跑，signoff 全 PASS。紀錄見 [docs/phase_exit/phase0.md](docs/phase_exit/phase0.md)。
- Phase 1：PicoRV32 SoC 的 RTL、firmware、RTL 模擬 regression 完成。正向測試 26/26 PASS（Icarus、Verilator），33 項植入錯誤都在預期的 checker FAIL；經兩輪獨立 testbench qualification review。紀錄見 [docs/phase_exit/phase1.md](docs/phase_exit/phase1.md)。
- Phase 2：PicoRV32 單獨 harden 到 GDS（40 ns）。DRC、LVS 為 0，9 個 corner 的 setup／hold 與 slew／cap／fanout 全部 PASS；上游 ISA 測試在最終網表上 PASS，RTL 與 GL 的 bus transaction 逐筆相同；soc_top 的 `DIE_AREA` 定為 1000 × 800 µm（ADR-0006）。紀錄見 [docs/phase_exit/phase2.md](docs/phase_exit/phase2.md)。
- Phase 3：SoC 整合預建的 2 KB SRAM macro，harden 到 GDS（1000 × 800 µm，40 ns）。
  - 9 個 corner 的 setup／hold 與 slew／cap 全部 PASS；LVS、KLayout DRC、XOR 為 0；SRAM 外框以外的 Magic DRC 為 0。
  - EQY 證明合成網表與最終網表等價（RTL 到合成網表這一段還沒有 formal 證明）。13 支 gate-level 模擬測試裡，RTL 與網表每個 cycle 都相同。
  - 植入錯誤全部在預期的 checker FAIL：PnR 20 個、EQY 11 個、gate-level 模擬 4 個、來源追溯 9 個。
  - `make phase3` 在乾淨 checkout 從頭到尾跑完 PASS。這是第四次：第一次遇到 OpenROAD 的隨機錯誤，用有上限的重試繞過；第二、三次分別是少宣告 firmware 依賴、一個植入案例編譯不過，都已修正。
  - signoff 條件本身的缺口（clock duty cycle、IR 預算等）列為 Phase 4 待辦。
  - 紀錄見 [docs/phase_exit/phase3.md](docs/phase_exit/phase3.md)。
- Phase 4：signoff 收斂與一鍵 regression。
  - soc_top 收斂在 42 ns：25 ns、40 ns 在加嚴的條件下做不到，使用者決定改 42 ns；SRAM 的時序仍是假設值（ADR-0007）。
  - 15 個 corner（加上溫度反轉）的 setup／hold 與 slew／cap 全部 PASS；IR 的 VDD 降壓加 GND 抬升 8.07 mV（上限 20 mV）。
  - EQY 另外比對 flip-flop 種類與 clock 接線；帶電源網表的 gate-level 模擬 15/15 PASS；補 2 支 directed 測試。
  - `make regress` 一個指令跑完 Phase 1–4 的全部檢查。第 4 次在乾淨 checkout 25/25 PASS（123 分鐘），163 個植入錯誤全部在預期的 checker FAIL。前 3 次重跑的原因：依獨立審查修改 checker、多執行緒繞線的中間數字不同、gate-level 模擬的時限太緊。
  - 重現性只在同一台機器驗證過。
  - 紀錄見 [docs/phase_exit/phase4.md](docs/phase_exit/phase4.md)。

## 快速開始

```bash
make help          # 所有 target
make env-check     # 檢查本機工具、釘版 IP、toolchain.md 是否最新
make smoke         # 環境檢查、Python 名稱檢查、lint、firmware、RTL 模擬 smoke（約 30 秒）
make phase1        # Phase 1 完整檢查（約 4 分鐘）
make phase2        # Phase 2 完整檢查：LibreLane harden + GL regression（約 24 分鐘，需要 flow 環境）
make phase3        # Phase 3 完整檢查：SoC 與 core 的 harden、EQY、GL 模擬與全部植入錯誤（約 91 分鐘，需要 flow 環境）
make regress       # 全部檢查一次跑完（Phase 1–4，依序執行、第一個 FAIL 就停；約 2–2.5 小時，需要 flow 環境）
```

`make regress` 的結果在 `runs/regress/`：`summary.md`（每個 target 的 PASS／FAIL 與時間）、`junit.xml`、每個 target 的 log。
它會先刪掉 `runs/regress/`，並由每個 harden 步驟重新產生自己的 run；下游步驟只接受同一個 commit 產生、且 PASS 的 run。
工作目錄有未提交的修改時，來源追溯（provenance）會判 FAIL，所以請在乾淨的 checkout 上執行。

第一次在新機器上建 flow 環境的步驟見 [env/setup.md](env/setup.md)。

## 技術組合

| 項目 | 選擇 |
|---|---|
| PDK | SkyWater sky130A，標準元件庫 `sky130_fd_sc_hd` |
| RTL-to-GDS flow | [LibreLane](https://github.com/librelane/librelane) 3.x（Classic flow），內含 Yosys、OpenROAD、Magic、KLayout、Netgen |
| SRAM | 先用 PDK 內附的預建 OpenRAM macro（2 KB，`sky130_sram_2kbyte_1rw1r_32x512_8`），後期改用 [OpenRAM](https://github.com/VLSIDA/OpenRAM) 自產 |
| RISC-V core | 先用 [PicoRV32](https://github.com/YosysHQ/picorv32)，再換 [Hazard3](https://github.com/Wren6991/Hazard3)，證明流程可以換 core |
| 模擬 | Verilator、Icarus Verilog |
| Firmware | riscv64-elf-gcc（rv32） |
| 執行環境 | Apple Silicon macOS + Nix；OpenRAM 需要 x86_64 Linux |

完整的工具與版本清單見 [toolchain.md](toolchain.md)，釘版值以 `env/versions.mk` 為準。

## 為什麼不是 SkyWater 90nm

原本的目標是 SkyWater 90nm FD-SOI（SKY90-FD）。查證後發現它的開源版本無法使用：
主 repo 停在實驗性預覽並已於 2026-02 封存，標準元件庫 repo 裡沒有任何 cell，
OpenRAM、LibreLane、OpenROAD 也都不支援這個製程。
因此改用同為 SkyWater 的 sky130A，並讓流程設定與 PDK 無關，日後取得 sky90 PDK 時可以替換。
查證細節與出處見 project-plan.md 第 1 章。

## 階段路線圖

| Phase | 內容 | 狀態 |
|---|---|---|
| 0 | 環境建置：Nix、LibreLane、sky130A PDK；重跑 LibreLane 官方 SRAM 範例當 golden 參考 | 完成（2026-10-03） |
| 1 | SoC RTL 與 firmware、RTL 模擬 regression | 完成（2026-10-03） |
| 2 | 單獨 harden PicoRV32，打通流程並取得面積與時序實測值 | 完成（2026-10-03） |
| 3 | 整合預建 SRAM macro | 完成（2026-10-04） |
| 3.5 | （可選）用 OpenRAM 做 SPICE characterization，校正 SRAM 時序模型 | 未開始 |
| 4 | Signoff 收斂、單一指令跑完整 regression、補齊文件 | 完成（2026-10-04） |
| 5 | 換成 Hazard3 | 未開始 |
| 6 | 用 OpenRAM 自產的 SRAM 取代預建 macro | 未開始 |
| 7 | （可選）chip-level 整合，例如 ChipFoundry Caravel | 未開始 |

各階段的 exit criteria 與工時估計見 project-plan.md 第 8 章。

## 驗證方式

- **分層 regression test**：lint、RTL 模擬、gate-level 模擬、PnR signoff、equivalence check、post-layout 模擬。
- **Signoff 門檻**：多個 STA corner 的 setup 與 hold 全部 PASS：PicoRV32 單獨 harden 是 9 個（tt／ss／ff 三種 library corner × 三種繞線寄生 RC），soc_top 另加兩個溫度反轉的 PVT，共 15 個，
  另有 DRC、LVS、antenna、IR drop 等 metrics 門檻。
- **Bug injection**：刻意植入錯誤，確認對應的 checker 確實會 FAIL，避免 checker 永遠 PASS 卻抓不到問題。

細節見 project-plan.md 第 6、7 章。

## Claude Code skills（流程經驗庫）

`.claude/skills/` 放了 19 個 Claude Code skill，每個對應 RTL-to-GDS 流程中一項重大任務。skill 是一份工作說明（`SKILL.md`）：在這個 repo 裡用 Claude Code 做到相關任務時會自動載入，照裡面的步驟、PASS 條件與已知陷阱做事。

**經驗怎麼累積**：每個 `SKILL.md` 的結尾都有「經驗紀錄」表。每次做完該任務，把新遇到的現象寫一列：日期、run、原文訊息、根因（標明已驗證或推測）、處理方式、證據路徑。同一個現象出現兩次以上，或根因已經用實驗確認，才從紀錄搬進規則本文。這顆設計的具體數字（設定理由、試跑紀錄）留在 repo 文件，skill 只放可以帶到下一顆設計的規則與指向 repo 文件的連結。規則見 [CLAUDE.md](CLAUDE.md)。Phase 0 的環境建置不做成 skill。

| skill | 一句用途 | 優先 |
|---|---|---|
| [librelane-run-debug](.claude/skills/librelane-run-debug/SKILL.md) | 跑、接續、單步重跑 LibreLane，讀 step 目錄、log 與 metrics | 1 |
| [signoff-checker-qualification](.claude/skills/signoff-checker-qualification/SKILL.md) | checker 與 golden 的設計，用植入錯誤證明 checker 抓得到 | 1 |
| [drv-timing-closure](.claude/skills/drv-timing-closure/SKILL.md) | 9 個 corner 的 setup／hold 與 slew／cap／fanout 收斂 | 1 |
| [hard-macro-integration](.claude/skills/hard-macro-integration/SKILL.md) | SRAM 等 hard macro 的整合清單 | 2 |
| [drc-signoff](.claude/skills/drc-signoff/SKILL.md) | DRC、GDS 輸出、XOR，macro 內部 DRC 的對照基準 | 2 |
| [formal-equivalence-eqy](.claude/skills/formal-equivalence-eqy/SKILL.md) | EQY 等價證明與已知漏洞 | 2 |
| [antenna-signoff](.claude/skills/antenna-signoff/SKILL.md) | antenna 檢查與修復，macro 沒有 antenna 資料時的處理 | 2 |
| [cts-clock-tree](.claude/skills/cts-clock-tree/SKILL.md) | clock tree 與 clock pin | 3 |
| [pdn-ir-drop](.claude/skills/pdn-ir-drop/SKILL.md) | 電源網路與 IR drop | 3 |
| [lvs-signoff](.claude/skills/lvs-signoff/SKILL.md) | LVS、macro black box、實體連接、斷線 pin | 3 |
| [gate-level-simulation](.claude/skills/gate-level-simulation/SKILL.md) | 網表模擬、RTL 與網表 lockstep、X 處理 | 3 |
| [floorplan-congestion](.claude/skills/floorplan-congestion/SKILL.md) | die 尺寸、macro 位置、IO pin、placement 密度、繞線壅塞與繞路 | 2 |
| [timing-constraints-sdc](.claude/skills/timing-constraints-sdc/SKILL.md) | SDC 時序約束、PnR 與 signoff 約束分開、未受約束路徑的檢查 | 2 |
| [rtl-synthesis-lint](.claude/skills/rtl-synthesis-lint/SKILL.md) | Yosys 合成設定、狀態機重新編碼、lint、latch、邏輯深度 | 3 |
| [signoff-criteria](.claude/skills/signoff-criteria/SKILL.md) | signoff 條件的數值怎麼推導：uncertainty 成分、duty cycle、derate、corner、IR／EM／SI 預算、PDK 規則，以及工具沒分析的項目怎麼補 | 1 |
| [flow-regression-reproducibility](.claude/skills/flow-regression-reproducibility/SKILL.md) | 一鍵 regression、乾淨 checkout 驗證、來源追溯（commit、LibreLane、PDK 內容）、下游拒絕過期的 run、長 run 期間怎麼開發 | 1 |
| [multicorner-sta](.claude/skills/multicorner-sta/SKILL.md) | 增減 STA corner、每個 corner 的 hook 與報告、只重跑 STA 的 what-if、從路徑推最小週期、corner 變多時 PnR 變慢 | 2 |
| [dv-directed-tests](.claude/skills/dv-directed-tests/SKILL.md) | 從漏掉的植入錯誤找出沒被測到的功能，寫 directed firmware 測試補上，再用植入錯誤證明抓得到 | 2 |
| [phase-exit-review](.claude/skills/phase-exit-review/SKILL.md) | Phase 收尾：exit criteria 與證據、與計畫不同的地方、已知限制、獨立審查、使用者決定 | 1 |

優先 1 經驗最多、最常重用；優先 3 目前經驗較少，內容會在之後的 Phase 補齊。`floorplan-congestion`、`timing-constraints-sdc`、`rtl-synthesis-lint` 是 2026-10-03 請 Gemini 3.8 Flash（Antigravity CLI）審查「還漏了哪些任務」後補上的；審查同時建議的 `openram-macro-characterization`（Phase 3.5／6）、`core-migration-hazard3`（Phase 5）、`tapeout-precheck-caravel`（Phase 7）會在進入那個 Phase 時建立。`signoff-criteria` 是 2026-10-03 討論「clock 沒有 PLL，那 clock 從哪來」時，發現 signoff 條件多數沿用預設值、沒有推導，依使用者要求新增。最後 4 個是 Phase 4（2026-10-04）依使用者要求，分析 Phase 4 的重大任務後新增：一鍵 regression 與來源追溯、多 corner STA、directed 測試補缺口、Phase exit review；Phase 4 的其他任務（checker 漏洞、L5 模擬、IR、EQY、DRC 位置比對、signoff 條件）寫回既有的 skill。

### librelane-run-debug：LibreLane 執行與除錯

- **何時用**：跑 LibreLane、run 失敗找原因、從中間 step 接續、只重跑一個 step（驗證設定或做 negative test）。
- **內容**：nix-shell 呼叫方式與路徑規則；`--from` 接續；`python3 -m librelane.steps run` 單步重跑與串接；step 目錄的 `-1` 字尾、ODB 會快取 LEF、STA hook 只在 STA 生效、log 緩衝、`pkill` 誤殺、post-GRT 修復跑不完等陷阱；各步驟時間。
- **不含**：設定值該設多少、怎麼判 PASS（看各主題的 skill）。

### signoff-checker-qualification：checker、golden 與植入錯誤

- **何時用**：寫或改任何 PASS／FAIL checker、建立或更新 golden、處理 run 之間不可重現的差異、用 negative test（植入錯誤）證明 checker 有效。
- **內容**：只認明確 PASS、型別嚴格、來源追溯；golden 的誤差只給 detailed routing 會變的族群；植入點必須只命中一處、必須在預期的 checker 以預期原因 FAIL；已知的 checker 漏洞類型（工具靜默略過、檢查範圍比名稱小、植入沒生效、工具快取）。
- **實例**：`signoff/scripts/check_signoff.py`、`signoff/golden/*/README.md`、各 `neg_*.py`。

### drv-timing-closure：時序與 DRV 收斂

- **何時用**：9 corner STA 有 setup／hold 違規，或 max slew／cap／fanout 違規；訂時序目標、corner 判定、PnR 與 signoff 的 SDC。
- **內容**：corner 判定設定；DRV 收斂清單（排除延遲 cell、`LAYERS_RC`、post-GRT 修復與餘裕、長線切段）；退回過的做法與原因；違規的判讀方法；實作與簽核分開的 SDC；先找根因（例如繞路）再考慮放寬上限，放寬需使用者決定（ADR-0009：曾放寬到 1.0 ns，找到根因後撤回）。
- **negative test**：P01–P04（單步重跑 STA）。

### hard-macro-integration：hard macro 整合

- **何時用**：把 SRAM／IP macro 放進設計，或換一顆 macro（例如 Phase 6 的 OpenRAM 自產 SRAM）。
- **內容**：各 view 的來源與產生（GDS、antenna LEF、padded .lib、blackbox、模擬模型，每個產生檔都要能檢查是否過期）；擺放與 halo；未用 port 的 tie-off；整合清單逐項連到其他 skill。
- **實例**：`pnr/soc_top/`、`ip/sram/`、ADR-0006／0007／0008。

### drc-signoff：DRC、GDS 輸出、XOR

- **何時用**：Magic／KLayout DRC、GDS 輸出、XOR；含 macro 時 DRC 不為 0、abstract DRC 大量報錯、GDS 多個 top cell。
- **內容**：abstract DRC 的 `nwell.4` 假錯誤與改用完整 GDS；macro 內部 DRC 的判定方式（外框外為 0；框內每個違規都要落在 macro 單獨檢查時同規則違規的位置，Phase 3 只比規則種類會漏掉新的違規）；Magic GDS 多 top cell 時改用 KLayout 輸出；報告檔大小與時間。
- **negative test**：P10（植入 DRC 違規）、P11（XOR）。

### formal-equivalence-eqy：formal equivalence

- **何時用**：用 EQY 證明網表等價、EQY 當機或分區證不出來、設計 EQY 的 negative test。
- **內容**：目前可用的組合（合成網表 vs 最終網表）與必要設定（stack、`$scopeinfo`、`insbuf off`）；判定規則，包括 EQY 對「對應到常數的 bit」不證明的漏洞；RTL 對網表尚未解決的問題（狀態機重新編碼、上電未定值的暫存器）。
- **negative test**：`neg_eqy.py` 在 picorv32_core 植入 10 種、soc_top 7 種錯誤（不重複的共 13 種），FAIL 的位置必須在植入點附近；EQY 的 `sat` 證不到 flip-flop 本身，另加 sequential cell 結構比對。

### antenna-signoff：antenna

- **何時用**：antenna 違規、diode 插入、macro 的 LEF 沒有 antenna 資料、diode 造成 fanout／slew 副作用。
- **內容**：從 macro 的 SPICE 算閘極面積補進 LEF；用 tech LEF 的比例估允許長度；不要用 heuristic diode insertion 的原因；diode 算進 fanout 的對策；要用不同 LEF 驗證時直接用 openroad 讀 LEF＋DEF。
- **negative test**：P06。

### cts-clock-tree：clock tree

- **何時用**：clock buffer 的 fanout／cap 違規、skew、clock 輸入 port 的 slew、clock pin 擺放。
- **內容**：`CTS_SINK_CLUSTERING_SIZE`、`CTS_DISTANCE_BETWEEN_BUFFERS` 的作用與試過無效的設定；clock pin 到第一級 buffer 的線不在 resizer 修復範圍內；待補 macro clock pin 的平衡。

### pdn-ir-drop：電源網路與 IR drop

- **何時用**：PDN 產生失敗、macro 電源怎麼接、IR drop 分析與門檻。
- **內容**：`PDN-0179` 窄 row 問題與 halo 對策；為什麼關掉 macro grid 設定不會斷開 SRAM 電源；PSM 只查電源網路本身；IR drop 門檻是 VDD 降壓 + GND 抬升合計（soc_top 20 mV）；macro-level 的供電模型要明講假設（一側供電）；最大電流與最大電阻不在同一個 corner；待補改 PDN 後重跑 IR 的 negative test。

### lvs-signoff：LVS 與連接性

- **何時用**：LVS 失敗、macro 在 LVS 中是 black box、驗證電源或訊號 pin 的實體連接、斷線 pin。
- **內容**：black box 的驗證範圍；斷線 pin 表格只在有斷線時才產生；未用輸出接具名 wire；刪 via 重跑萃取與 LVS 的驗證方法。
- **negative test**：P05、P08。

### gate-level-simulation：gate-level 模擬

- **何時用**：網表 regression、RTL 與網表比對、GL 模擬的 X 處理、cell 模型設定與速度。
- **內容**：sky130 模型的 define；bus trace 比對與 lockstep 兩種做法及 X 規則；證明比對真的有跑；GL 模擬看不到 firmware 沒用到的功能，要靠 formal 補；各測試時間。

### floorplan-congestion：floorplan 與繞線壅塞

- **何時用**：決定 die／core 尺寸、macro 位置與方向、IO pin 擺放、placement 密度；遇到繞線壅塞、大幅繞路、窄 row、GCell 溢位。
- **內容**：die 尺寸的估算與使用率定義（ADR-0006）；macro 座標對齊格點、halo 與窄 row 的 PDN 問題；clock pin 的位置；用 DEF 判讀繞路（繞線長度 ÷ 端點距離）；全域 congestion 報告看不到局部繞路；placement 目標密度的設定（soc_top 從自動的 68% 降到 55% 解決了轉角繞路）。

### timing-constraints-sdc：時序約束

- **何時用**：寫或改 SDC（clock、IO delay、例外路徑、derate、max transition／fanout）、區分 PnR 與 signoff 的約束、檢查有沒有未受約束的路徑。
- **內容**：LibreLane `base.sdc` 已提供的約束清單；新 SDC 先 `source` base.sdc 再改；用單步重跑 STA 驗證約束只改了想改的；macro derate 的 hook；`check_setup` 的未受約束路徑檢查與已知例外（`check_soc.py sta_setup`）。
- **negative test**：P01–P03、P13。

### signoff-criteria：signoff 條件的推導

- **何時用**：決定或檢討任何 signoff 條件的數值，例如 clock uncertainty、duty cycle、OCV derate、PVT corner、IO delay、IR drop 上限、EM、SI、max transition／cap／fanout、antenna、density、latch-up；或要說明某個工具沒分析的效應用哪一筆 margin 涵蓋。
- **內容**：
  - 每個條件的四個問題：防什麼、怎麼算、預設值出處、工具有沒有分析。
  - 推導前要先有的輸入：clock 來源的 jitter 與 duty、供電範圍、溫度、外部介面時序。
  - 19 條已驗證的工具行為，例如：inter-clock uncertainty 會取代一般值；skew metric 含 uncertainty 與 derate；fmax 報告排除半週期路徑；instance derate 取代 global；IR 只用 nom_tt；KLayout deck 不含 latch-up。
  - 各條件的推導公式。
  - 每次 signoff 都要列出的「不分析項目」清單。
- **實例**：`docs/notes/signoff_criteria_soc_top.md`（soc_top 的缺口與 Phase 4 待辦）。
- **negative test**：每個推導出來的條件都要有植入錯誤的案例，例如 duty cycle 60% 必須 FAIL。

### rtl-synthesis-lint：合成與 lint

- **何時用**：Yosys 合成設定、狀態機重新編碼、被常數化的暫存器、lint 警告、latch、為時序目標調整合成。
- **內容**：harden 參數與 SoC instance 一致的檢查；LibreLane 合成固定跑 `fsm` 重新編碼（影響 RTL 對網表的 formal）；X 語意下的常數化；LibreLane lint 警告的來源與鎖定方式；待補 25 ns 的合成策略。


### flow-regression-reproducibility：一鍵 regression、可重現性與來源追溯

- **何時用**：建立或執行 `make regress`／`make phase<N>`、在乾淨 checkout 驗證、檢查一個 run 是哪個 commit 與哪版工具產生的、讓下游步驟拒絕過期或沒 PASS 的 run、長時間 run 期間繼續開發。
- **內容**：regression 的結構（依序、第一個 FAIL 就停、log／摘要／JUnit、最後再確認 commit 沒變）；來源追溯要涵蓋 LibreLane clone 的內容與 PDK 檔案內容（參考值從下載的壓縮檔算）；下游的 run 檢查與它的 negative test；用另一個 worktree 開發；拿舊 run 測新 checker 的方法與限制；golden 與 commit 的先後。
- **實例**：`scripts/regress.py`、`signoff/scripts/provenance.py`、`run_guard.py`、`neg_provenance.py`、`neg_run_guard.py`。

### multicorner-sta：多 corner STA

- **何時用**：增減 PVT／RC corner、在 LibreLane 設 corner 與每個 corner 的 hook、只重跑 STA 做 what-if（週期、duty cycle、uncertainty、derate）、推最小週期、corner 變多後 PnR 變慢。
- **內容**：設 `LIB` 會取代 LibreLane 的整組預設；resizer／CTS／其他 step 各自讀哪個 corner 變數；15 個 corner 讓 post-GRT 修復停不下來的實例與處理；hook 裡加 derate 與輸出報告；兩種 what-if 的做法；半週期路徑的最小週期算法。
- **實例**：`pnr/soc_top/config.json`、`sta_extra_corner.tcl`、`neg_pnr.py`（P01–P04、P22–P25）。

### dv-directed-tests：directed 測試補驗證缺口

- **何時用**：植入錯誤沒被抓到、或 formal 範圍沒涵蓋某段時，找出沒被用到的功能並補 directed firmware 測試。
- **內容**：缺口從漏掉的植入錯誤找；先讀 RTL 確認實際行為；編譯器會改寫非對齊存取（要用 inline assembly 並看反組譯）；寫明測不到的部分；新測試要登記的地方；在網表植入對應錯誤證明新測試抓得到。
- **實例**：`fw/tests/counters/`、`fw/tests/buserr/`、`dv/gl_soc/neg_gl_soc.py`。

### phase-exit-review：Phase exit review 與獨立審查

- **何時用**：一個 Phase 收尾。
- **內容**：exit criteria 加上一階段帶過來的項目；證據只用乾淨 checkout 的 run；數字逐一對證據、注意容易誤讀的彙總 metric；章節結構；兩個獨立審查 agent（文件核對、找 checker 漏洞）；使用者決定的記錄；收尾的 README、記憶、skill 回寫與推送規則。
- **實例**：`docs/phase_exit/phase*.md`。
## 授權

本 repo 的內容以 [Apache License 2.0](LICENSE) 授權。
之後引入的第三方元件保留各自的授權，例如 PicoRV32 為 ISC，Hazard3 與 sky130 PDK 為 Apache-2.0。
