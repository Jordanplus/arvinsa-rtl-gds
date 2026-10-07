# arvinsa-rtl-gds

以全開源 EDA 工具鏈建立一條可重複執行、有 regression test 的 RTL-to-GDS 流程，
並以開源 RISC-V SoC（含 SRAM macro）當 test vehicle，一路跑到 signoff（DRC／LVS／STA PASS）。

An open-source RTL-to-GDS flow on SkyWater sky130A using LibreLane and OpenRAM SRAM macros,
with RISC-V cores (PicoRV32, then Hazard3) as test vehicles. Documentation is written in Traditional Chinese.

## 專案狀態

**實作中（2026-10-05）：Phase 0–4 與 Phase 3.5 完成，Phase 5（換 Hazard3）進行中。** 完整規劃見 [project-plan.md](project-plan.md)。

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
- Phase 3.5：SRAM 的時序改用 SPICE 實測（本機 ngspice 量 PDK 附的電晶體級網表，ADR-0010）。
  - 5 個 PVT 各一份 .lib，由量測結果的 JSON 產生並檢查沒過期；加上 dout0 在 clock 上升緣後就開始變化的 hold 弧。
  - 延遲、setup、週期都仍由原本保守的下限決定；新的 hold 弧讓 soc_top 週期 42 → 43 ns（使用者決定）。
  - **頭號下線風險**：這顆 SRAM 在 ss 1.60 V 的 −40°C 與 25°C 讀取失敗（讀成前一次的值，sense amp 的設計問題），ss −40°C corner 用佔位 .lib，Phase 6 自產 macro 要修正。
  - `make regress` 第 2 次在乾淨 checkout 25/25 PASS（136 分鐘），soc_top 439 個 metric 與 golden 完全相同，164 個植入錯誤全部在預期的 checker FAIL。第 1 次因一個植入程式的 bug FAIL，已修正。
  - 獨立審查更正了文件，並找到 12 個 checker 漏洞（沒有一個造成假 PASS），Phase 5 開頭修。
  - 紀錄見 [docs/phase_exit/phase3_5.md](docs/phase_exit/phase3_5.md)。

## 快速開始

```bash
make help          # 所有 target
make env-check     # 檢查本機工具、釘版 IP、toolchain.md 是否最新
make smoke         # 環境檢查、Python 名稱檢查、lint、firmware、RTL 模擬 smoke（約 30 秒）
make phase1        # Phase 1 完整檢查（約 4 分鐘）
make phase2        # Phase 2 完整檢查：LibreLane harden + GL regression（約 24 分鐘，需要 flow 環境）
make phase3        # Phase 3 完整檢查：SoC 與 core 的 harden、EQY、GL 模擬與全部植入錯誤（約 91 分鐘，需要 flow 環境）
make regress       # Hazard3 版 SoC 的全部檢查一次跑完（Phase 5 起的主要設計；依序執行、第一個 FAIL 就停；需要 flow 環境）
make regress-picorv32  # PicoRV32 版 SoC 的全部檢查（Phase 1–4 的 make regress，約 2–2.5 小時）
```

`make regress` 的結果在 `runs/regress/`（`make regress-picorv32` 在 `runs/regress_picorv32/`）：`summary.md`（每個 target 的 PASS／FAIL 與時間）、`junit.xml`、每個 target 的 log。
個別 target 用 `CPU=picorv32`（預設）或 `CPU=hazard3` 選 SoC 的 CPU，例如 `make harden-soc CPU=hazard3`（run 在 `runs/soc_top_hazard3/`）。
它會先刪掉自己的結果目錄，並由每個 harden 步驟重新產生自己的 run；下游步驟只接受同一個 commit 產生、且 PASS 的 run。
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
| 3.5 | （可選）用 SPICE 實測 SRAM macro 的時序，取代假設值。2026-10-04 改為本機 ngspice 直接量 PDK 附的網表（ADR-0010） | 完成（2026-10-05） |
| 4 | Signoff 收斂、單一指令跑完整 regression、補齊文件 | 完成（2026-10-04） |
| 5 | 換成 Hazard3 | 進行中 |
| 6 | 用 OpenRAM 自產的 SRAM 取代預建 macro | 未開始 |
| 7 | （可選）chip-level 整合，例如 ChipFoundry Caravel | 未開始 |

各階段的 exit criteria 與工時估計見 project-plan.md 第 8 章。

## 驗證方式

- **分層 regression test**：lint、RTL 模擬、gate-level 模擬、PnR signoff、equivalence check、post-layout 模擬。
- **Signoff 門檻**：多個 STA corner 的 setup 與 hold 全部 PASS：PicoRV32 單獨 harden 是 9 個（tt／ss／ff 三種 library corner × 三種繞線寄生 RC），soc_top 另加兩個溫度反轉的 PVT，共 15 個，
  另有 DRC、LVS、antenna、IR drop 等 metrics 門檻。
- **Bug injection**：刻意植入錯誤，確認對應的 checker 確實會 FAIL，避免 checker 永遠 PASS 卻抓不到問題。
- **每次 harden 後檢查 signoff criteria**：`review_criteria.py` 確認自己訂的條件這次真的有生效（LibreLane FAIL 時 checker 也照跑），再由 Claude 依 skill `signoff-criteria` 判讀條件合不合理，寫 `runs/<tag>_signoff/criteria_review.md`。專案的 Claude Code Stop hook 沒看到這份檢查，就不讓 Claude 回報 harden 結果。

細節見 project-plan.md 第 6、7 章。

## Claude Code skills（流程經驗庫）

`.claude/skills/` 放了 21 個 Claude Code skill，每個對應 RTL-to-GDS 流程中的一類任務。skill 是一份工作說明（`SKILL.md`），內容是已驗證的規則、已知陷阱、植入錯誤的案例（negative test），以及每次使用後追加的經驗紀錄。

**Claude 怎麼挑 skill**：每次對話開始時，Claude 只看得到每個 skill 開頭的 `description`，也就是一段「什麼情況用」的說明。判斷和手上的任務相關，才讀整份 `SKILL.md`。所以 `description` 要寫出會遇到的情況與錯誤訊息。這一節是給人看的索引：先用「依情況找 skill」查，再看每個 skill 的說明。

**只在本 repo 生效**：這些 skill 放在專案層，只有在這個 repo 裡用 Claude Code 才看得到。在其他專案使用的方法見本節最後「在其他專案使用」。

**經驗怎麼累積**：
- 每個 `SKILL.md` 結尾有「經驗紀錄」表。每次做完該任務，就把新遇到的現象寫一列：日期、run、原文訊息、根因（標明已驗證或推測）、處理方式、證據路徑。
- 同一個現象出現兩次以上，或根因已經用實驗確認，才從紀錄搬進規則本文。
- 這顆設計的具體數字（設定理由、試跑紀錄）留在 repo 文件；skill 只放可以帶到下一顆設計的規則，和指向 repo 文件的連結。
- 製程相關的知識依製程分類：`signoff-criteria/knowledge/<製程>.md` 累積 PDK 事實與每次 harden 量到的校準資料，下一顆同製程設計用它來定 criteria。
- skill 的規則、陷阱或適用範圍有改，同一個 commit 就要更新本節該 skill 的說明，以及該 `SKILL.md` 的 `description`。`make skill-check` 會檢查格式與索引是否齊全，但內容是否一致仍要人檢查。

規則見 [CLAUDE.md](CLAUDE.md)。Phase 0 的環境建置不做成 skill。

### 依情況找 skill

| 遇到的情況 | 先看 | 再看 |
|---|---|---|
| 要跑 LibreLane、從中間 step 接續、只重跑一個 step、重跑時保留上一次的 run | librelane-run-debug | — |
| run 失敗、錯誤時有時無（例如 `GRT-0229`）、某一步很久不結束或記憶體一直漲 | librelane-run-debug | drv-timing-closure（resizer 停不下來：推最小負載就超標的弱 cell、slew 餘量、post-GRT 修復的設定）、multicorner-sta（corner 太多）、openram-macro-characterization（macro .lib 的負載斜率） |
| STA 有 setup／hold 違規 | drv-timing-closure | multicorner-sta（哪個 corner、只重跑 STA 試）、timing-constraints-sdc（約束有沒有寫錯）、cts-clock-tree（macro 的 clock 被延後） |
| hold delay cell 卡在 setup 吃緊的路徑上、半週期路徑、launch 與 capture 的 clock 差隨 corner 變號 | cts-clock-tree | drv-timing-closure（hold 修復本身） |
| max slew／cap／fanout 違規 | drv-timing-closure | floorplan-congestion（繞路）、antenna-signoff（diode 增加 fanout）、cts-clock-tree（clock net） |
| 修某個 corner 的違規；換 PnR／sizing 工具或升版；改 corner、library 或修復餘量 | drv-timing-closure（規則 11：用違規 corner 的資料判斷修法，工具有沒有做到要用對照實驗確認；規則 10：弱 cell 檢查） | multicorner-sta（哪個 step 用哪組 corner） |
| signoff 才在 resizer 看不到的 corner 出現 setup 違規；繞線前想看某個 corner 的 slack | drv-timing-closure（規則 9、11：用別的 corner 加餘量代替，長路徑會漏） | multicorner-sta（規則 8：繞線前怎麼量；規則 7：flow 中途 state 的 metrics 可能是舊值） |
| CTS 後修完 setup，signoff 卻在長路徑 setup 違規；想調大 setup 餘量或加週期 | drv-timing-closure（規則 12：先量差距落在哪一段，繞線後才出現的就開 `RUN_POST_GRT_RESIZER_TIMING`） | signoff-criteria（`review_criteria.py` 印出每次修復到 signoff 的差距） |
| harden 跑完（PASS 或 FAIL）、要回報結果前；自己訂的 signoff criteria 有沒有生效、還合不合理；Stop hook 說要寫 `criteria_review.md` | signoff-criteria（每次 harden 後的檢查；knowledge 檔依製程分類） | drv-timing-closure（修法）、multicorner-sta（corner） |
| 要決定週期，或從 slack 推最小週期 | multicorner-sta | signoff-criteria |
| 要定 clock uncertainty、derate、corner、IR 上限、max transition 這類數值 | signoff-criteria | timing-constraints-sdc（寫進 SDC）、pdn-ir-drop（IR） |
| 寫或改 SDC；STA 報 unconstrained endpoint | timing-constraints-sdc | — |
| 增減 PVT corner、每個 corner 要多做事（hook）、corner 變多後 PnR 變慢 | multicorner-sta | drv-timing-closure |
| 決定 die 尺寸與使用率、macro 位置、IO pin、placement 密度；繞線壅塞或繞遠路 | floorplan-congestion | hard-macro-integration |
| 放進或換一顆 SRAM／IP macro；macro 的 .lib 只有 TT 或只是解析模型 | hard-macro-integration（整合清單） | 清單上連到的各 signoff skill、multicorner-sta、openram-macro-characterization（用 SPICE 實測取代） |
| SRAM macro 的時序要用 SPICE 量、產生每個 corner 的 .lib；macro 在某些 corner 讀出前一次的值；換上新 .lib 後 repair_design 跑很久；ngspice 讀大網表很慢、報 `bad v() syntax`；從 GDS 萃取寄生電容、萃取網表報 singular matrix | openram-macro-characterization | signoff-criteria（量到的數字加多少餘量）、hard-macro-integration（換上新 .lib） |
| PDN 產生失敗、macro 電源怎麼接、IR drop（包括小得不合理）、EM | pdn-ir-drop | floorplan-congestion（macro 旁的窄 row）、lvs-signoff（實體連接）、signoff-criteria（IR 預算） |
| DRC 不為 0、macro 內部的 DRC 怎麼判、GDS 有多個 top cell、XOR、金屬密度 | drc-signoff | — |
| antenna 違規、macro 的 LEF 沒有 antenna 資料 | antenna-signoff | drv-timing-closure（長線修復） |
| LVS 失敗、斷線 pin、電源 pin 有沒有真的接上 | lvs-signoff | pdn-ir-drop |
| 合成設定、lint 警告、狀態機被重新編碼（formal 因此對不上） | rtl-synthesis-lint | formal-equivalence-eqy |
| 證明兩份網表等價、EQY 當機或證不出來 | formal-equivalence-eqy | — |
| 網表模擬、RTL 與網表比對、X、模擬逾時 | gate-level-simulation | flow-regression-reproducibility（機器負載） |
| gate-level 模擬或 formal 的植入錯誤沒被抓到、某個功能從沒被測到 | dv-directed-tests | gate-level-simulation |
| signoff checker（PnR、STA、DRC、來源追溯……）的植入錯誤沒被抓到 | signoff-checker-qualification | 該 checker 所屬主題的 skill |
| 寫或改任何 PASS／FAIL checker；建立或更新 golden；同樣設定重跑結果不同（連 cell 數、diode 數都變） | signoff-checker-qualification | flow-regression-reproducibility、librelane-run-debug（哪一步不可重現） |
| 一鍵 regression、乾淨 checkout 驗證、查 run 是哪個 commit 與哪版工具產生的、長 run 期間繼續開發或等它結束 | flow-regression-reproducibility | signoff-checker-qualification |
| 把 SoC 的 CPU 換成 Hazard3（AHB5）：wrapper、匯流排轉接、設定參數、中斷與 reset、上游測試與 ISS 比對、PnR 設定與上限檔要不要重做 | core-migration-hazard3 | dv-directed-tests、gate-level-simulation（驗證改法）、hard-macro-integration（SRAM 介面）、drv-timing-closure（時序收斂） |
| 一個 Phase 收尾 | phase-exit-review | — |

### 在流程中的位置

```
換 CPU core ............................ core-migration-hazard3
RTL：合成、lint ........................ rtl-synthesis-lint
 └ floorplan、macro、IO pin ............ floorplan-congestion、hard-macro-integration
    └ PDN .............................. pdn-ir-drop
       └ placement、resizer ............ drv-timing-closure、floorplan-congestion（密度）
          └ CTS ........................ cts-clock-tree
             └ routing、antenna ........ drv-timing-closure、antenna-signoff、floorplan-congestion（繞路）
                └ signoff
                   ├ STA ............... multicorner-sta、timing-constraints-sdc、drv-timing-closure
                   ├ DRC、XOR、密度 .... drc-signoff
                   ├ LVS、連接性 ....... lvs-signoff
                   └ IR、EM ............ pdn-ir-drop

驗證（網表出來之後）
 ├ 等價證明 ............................ formal-equivalence-eqy
 └ 網表模擬 ............................ gate-level-simulation、dv-directed-tests

PnR 各步驟用的 SDC 與 corner .......... timing-constraints-sdc、multicorner-sta

signoff 條件的數值從哪來 ............... signoff-criteria
每次 harden 後檢查 criteria ............. signoff-criteria（Stop hook 強制）
macro 的時序模型（.lib）從哪來 ......... openram-macro-characterization
貫穿全程 ............................... librelane-run-debug（執行與除錯）
                                         signoff-checker-qualification（checker、golden、植入錯誤）
                                         flow-regression-reproducibility（regression、來源追溯）
                                         phase-exit-review（階段收尾）
```

### 索引

「適用範圍」說明換到別的設計時哪些內容可以直接用：「通用」是不限工具的方法；「LibreLane／OpenROAD」是同一套開源流程都適用；「sky130」是這個 PDK 的數值、規則名稱或 cell 名稱。經驗多寡看各 `SKILL.md` 的經驗紀錄表。

| skill | 一句話 | 適用範圍 |
|---|---|---|
| [librelane-run-debug](.claude/skills/librelane-run-debug/SKILL.md) | 跑、接續、單步重跑 LibreLane，查失敗與卡住 | LibreLane 3 |
| [signoff-checker-qualification](.claude/skills/signoff-checker-qualification/SKILL.md) | checker 與 golden 的設計，用植入錯誤證明 checker 抓得到 | 通用 |
| [drv-timing-closure](.claude/skills/drv-timing-closure/SKILL.md) | 多 corner 的 setup／hold 與 slew／cap／fanout 收斂 | LibreLane／OpenROAD；cell 名稱是 sky130 |
| [hard-macro-integration](.claude/skills/hard-macro-integration/SKILL.md) | SRAM 等 hard macro 的整合清單 | LibreLane；SRAM 細節是 sky130 |
| [openram-macro-characterization](.claude/skills/openram-macro-characterization/SKILL.md) | 用 SPICE 實測 SRAM macro 的時序、產生每個 corner 的 .lib | 方法通用；ngspice、Magic 的細節是 sky130 |
| [drc-signoff](.claude/skills/drc-signoff/SKILL.md) | DRC、GDS 輸出、XOR、macro 內部 DRC、金屬密度 | 多為 sky130；位置比對方法通用 |
| [formal-equivalence-eqy](.claude/skills/formal-equivalence-eqy/SKILL.md) | EQY 等價證明、它會靜默略過的情況與補法 | Yosys／EQY |
| [antenna-signoff](.claude/skills/antenna-signoff/SKILL.md) | antenna 檢查與修復，macro 沒有 antenna 資料時的處理 | OpenROAD；數值是 sky130 |
| [cts-clock-tree](.claude/skills/cts-clock-tree/SKILL.md) | clock tree、clock pin、macro 的 clock latency、clock 造成的 setup／hold | OpenROAD／LibreLane |
| [pdn-ir-drop](.claude/skills/pdn-ir-drop/SKILL.md) | 電源網路、IR drop、供電點模型、EM | OpenROAD／LibreLane |
| [lvs-signoff](.claude/skills/lvs-signoff/SKILL.md) | LVS、macro black box、實體連接、斷線 pin | LibreLane（Magic、Netgen） |
| [gate-level-simulation](.claude/skills/gate-level-simulation/SKILL.md) | 網表模擬、RTL 與網表 lockstep、X、帶電源網表、時限 | Icarus＋sky130 模型；lockstep 方法通用 |
| [floorplan-congestion](.claude/skills/floorplan-congestion/SKILL.md) | die 尺寸、macro 位置、IO pin、placement 密度、壅塞與繞路 | OpenROAD；格點是 sky130 |
| [timing-constraints-sdc](.claude/skills/timing-constraints-sdc/SKILL.md) | SDC 時序約束、PnR 與 signoff 約束分開、未受約束路徑 | OpenSTA／LibreLane |
| [signoff-criteria](.claude/skills/signoff-criteria/SKILL.md) | signoff 條件的數值怎麼推導，工具沒分析的項目怎麼補；每次 harden 後檢查 criteria 有沒有被執行、合不合理 | 推導與檢查方法通用；製程知識依製程分類（目前 sky130＋LibreLane） |
| [rtl-synthesis-lint](.claude/skills/rtl-synthesis-lint/SKILL.md) | Yosys 合成設定、狀態機重新編碼、lint、latch | Yosys／LibreLane |
| [flow-regression-reproducibility](.claude/skills/flow-regression-reproducibility/SKILL.md) | 一鍵 regression、乾淨 checkout、來源追溯、長 run 期間怎麼開發 | 方法通用；實作是 LibreLane／Nix |
| [multicorner-sta](.claude/skills/multicorner-sta/SKILL.md) | 增減 corner、每個 corner 的 hook、只重跑 STA 的 what-if、最小週期 | LibreLane／OpenSTA |
| [dv-directed-tests](.claude/skills/dv-directed-tests/SKILL.md) | 從漏掉的植入錯誤找缺口，寫 directed 測試補上並證明有效 | 通用；例子是 RISC-V firmware |
| [phase-exit-review](.claude/skills/phase-exit-review/SKILL.md) | Phase 收尾：證據、限制、獨立審查、使用者決定、skill 回寫 | 通用 |
| [core-migration-hazard3](.claude/skills/core-migration-hazard3/SKILL.md) | 把 CPU 從 PicoRV32 換成 Hazard3（AHB5）：介面、參數、中斷與 reset、驗證資產 | Hazard3 細節；換 core 的檢查方法通用 |

### 各 skill 說明

#### librelane-run-debug：LibreLane 執行與除錯

- **何時用**：跑 LibreLane、從中間 step 接續、只重跑一個 step（驗證設定或做 negative test）、run 失敗找原因、某一步很久不結束、錯誤時有時無、重跑時保留上一次的 run。
- **重點**：
  - 單步重跑用 `python3 -m librelane.steps run`，改的是 config 與 state 的複本，原 run 不動。
  - 錯誤要先證明是隨機的（同一份輸入重跑 3–4 次，有過有不過），才能加重試；重試只針對那一個訊息，而且有次數上限。只跑一次就把錯誤歸因到某個設定不可靠：`GRT-0229` 原本被誤認為是某個設定造成的。
  - 判斷是不是卡住：log 有緩衝，要看 CPU 時間、記憶體與 call stack（`sample`）。記憶體要看 physical footprint，`ps` 的 RSS 不算被換到 swap 的部分，會嚴重低估；CPU 使用率低、swap 一直增加，就是記憶體失控，要馬上停（Phase 5 一個 step 用到 92.9 GB，機器只有 24 GB）。
  - 要在某一步的工具指令裡加除錯輸出時，用 `python3 -m librelane.steps eject` 把那一步匯出成獨立 script 再改；可能失控的實驗要加記憶體上限自動停。
  - 重跑會覆蓋同名的 run：Phase 3.5 第 1 次 harden 的 log 就因此不見。Phase 5 起 `run.sh` 把上一次的 run 搬成 `<dir>.prev`（只留一層），要保存更多次就自己改名；改名後各步的 `state_in.json` 仍指向舊路徑，單步重跑前要在複本裡換掉。
  - 常見陷阱：重跑的 step 目錄多 `-1` 字尾、從中間接續後之後每一步的編號都多 1（checker 不要寫死 step 編號）、ODB 會快取 LEF、STA hook 只在 STA 生效、console 輸出會折行。
  - metrics 的彙總值：DRV 計數是各 corner 的最大值；`power__total` 是最後寫入的 corner，不是 nom_tt。state 的 metrics 會沿用前面步驟的值，flow 中途 `state_out.json` 的數字不一定是那一步量的，要看該步的 `or_metrics_out.json`。log 的 `RSZ-0032 Inserted N hold buffers` 不是總數，要數網表。
- **不在這裡**：設定值該設多少、怎麼判 PASS，看各主題的 skill。
- **本 repo 實例**：`pnr/*/run.sh`、`pnr/librelane_flow.sh`（GRT-0229 重試，negative test `make test-flow-retry`）、`pnr/soc_top/neg_pnr.py` 的 `rerun()`。

#### signoff-checker-qualification：checker、golden 與植入錯誤

- **名詞**：checker 是判 PASS／FAIL 的程式或規則；golden 是確認過正確的一次 run 的完整 metrics，之後每次逐項比對；negative test（bug injection）是故意植入錯誤，確認 checker 真的 FAIL。
- **何時用**：新寫或修改任何 checker（signoff metrics、DV、EQY、自寫腳本）；建立或更新 golden；決定 golden 比對哪些 metric 可以有誤差；同樣設定重跑結果不同；設計植入錯誤的案例。
- **重點**：
  - 只認明確 PASS：缺一個 metric、表格被截斷、工具沒跑完都是 FAIL。型別要嚴格：`false` 不是 0；slack 是 1e30 代表沒有受約束的路徑。
  - golden 的誤差依「這個數字是哪一步產生的」分類，不要等出過差異才給。不可重現那一步（多執行緒 detailed routing）之後算出來的數字分三類：隨繞線微小變動的連續量（slack、skew、線長、via、功耗、IR）給很小的誤差；繞線器中間各輪的 DRC 數這類中間過程數字給大誤差（等於不比數值）；計數、面積、最終 DRC、LVS 一律完全相同。
  - 不可重現的步驟也會改變數量時（Phase 5 Hazard3：global routing 偶發不同、detailed routing 多插 diode）：先找到分歧的那一步、量出發生頻率，收集足夠樣本，再把會跟著繞線變的數量與面積放進另一個誤差表（約實測最大差異的 5 倍），每輪與個別 warning 的 key 列為可選。違規、錯誤類的計數仍一律完全相同，由 checker 拒絕任何碰到它們的誤差設定（ADR-0015）。
  - 每個 checker 至少要有一個植入錯誤，加一個沒植入時必須 PASS 的對照。斷言寫成「FAIL 的列剛好是這幾列」，而且要看全部問題，不能只看第一個。
  - 每個植入錯誤必須在**預期的** checker、以預期的原因 FAIL，FAIL 的位置要和植入點有關。修 checker 漏洞時，要證明舊 checker 會漏、新的會抓。
  - 附一張已知 checker 漏洞類型表，例如工具靜默略過、檢查範圍比名稱小、植入沒生效、只看有沒有不看大小或位置、產生器的公式沒有獨立驗證、斷言分不出 FAIL 的原因。新 checker 要逐條對照。
- **本 repo 實例**：`signoff/scripts/check_signoff.py`、`signoff/limits/`、`signoff/golden/*/README.md`、`pnr/soc_top/check_soc.py`、各 `neg_*.py`。

#### drv-timing-closure：時序與 DRV 收斂

- **名詞**：DRV（design rule violation，電性規則違規）指 max slew（訊號轉換太慢）、max cap（負載電容太大）、max fanout（一條線接太多負載）。
- **何時用**：多 corner STA 有 setup／hold 違規或 DRV 違規；要調 resizer、長線修復、cell 排除、繞線前的寄生估計；resizer 跑很久停不下來。
- **重點**：
  - LibreLane 對 sky130 預設只在 tt 判 setup FAIL，slew／cap 不判；先把四個 `*_VIOLATION_CORNERS` 都設 `["*"]`。
  - DRV 收斂清單，依實際有效的順序：排除延遲 cell、設 `LAYERS_RC`、開 post-GRT 修復、長線切段；剩下少數違規先查是不是繞路。
  - resizer 只看 `RSZ_CORNERS`。它看不到的 corner 用 PnR 的餘量補（setup 餘量、比 signoff 嚴的 max transition），但這只是補償，不是證明。Phase 5 證實 setup 的補償對長路徑不夠：corner 之間的延遲差和路徑長度成比例，Hazard3 一條長路徑在 ss_100C 有 +1.48 ns，signoff 在 ss_n40C 卻是 −4.16 ns。換 CPU 或改週期後，繞線前就要量一次只給 signoff 看的 corner。
  - resizer 停不下來、記憶體一直漲：OpenROAD 的 `repair_design` 修 driver 的 slew 時，可能把它換成更弱的尺寸（Phase 5：`a2111oi_2` 被換成 `a2111oi_1`）；換完若弱到連一顆最小 buffer 的輸入電容都推不動，長線修復會在同一位置無限插 buffer（Phase 5 單步重跑確認）。PDK 的 `no_synth.cells` 只擋合成，resizer 照樣會用裡面的弱 `_1`。slew 餘量越大、resizer 的 corner 越慢，會出事的 cell 越多。用除錯輸出找出那條 net；本 repo 把 `a2111oi_1` 加進 `EXTRA_EXCLUDED_CELLS`（ADR-0012），並在 harden 前用 .lib 查表檢查 resizer 可用的每個 cell（`pnr/check_weak_cells.py`）。macro 的 .lib 也曾讓這一步停不下來，換上新的先單步重跑確認時間。
  - 修哪個 corner 的違規，就用那個 corner 的資料判斷修法的影響。工具不一定做到：OpenROAD resizer 在 ss 100°C 抓到違規，卻用第一個讀進來的 tt .lib 挑尺寸（只改讀取順序，挑的尺寸就不同）。所以修完要在違規的 corner 確認被改的 cell 真的變好；換工具、升版或改 corner 設定時，用「只改 library 讀取順序或預設 corner」的對照實驗確認工具有沒有看對 corner。這條寫成規則而不只寫在腳本，是為了換工具或流程時也會重新驗證。流程設定也會讓工具看不到違規的 corner：用另一個 corner 加餘量代替，就是沒有用違規那個 corner 的資料。
  - macro 的 .lib 要每個 PVT 一份，resizer 才看得到 macro 在慢 corner 的延遲；只靠 STA hook 加 derate 時，PnR 看不到。OpenRAM SRAM 的 .lib 要有 dout 在上升緣後開始變化的時序弧，STA 才會檢查接收 flop 的 hold。
  - CTS 後修完 setup，signoff 卻在長路徑違規：先量「修完 → 繞線前 → signoff」差距落在哪一段。繞線後才出現的，開 `RUN_POST_GRT_RESIZER_TIMING`，讓 resizer 用 global routing 估計的寄生再修一次（Phase 5 Hazard3：−1.131 → +0.530 ns，只換尺寸與拿掉 buffer）。不要調大 CTS 後的 setup 餘量（會擋住 hold 修復），也不要靠加週期（run 之間差約 1 ns）。
  - 放寬 signoff 上限之前先找根因；真的要放寬，由使用者決定並寫 ADR。
  - detailed routing 之後才出現的違規，Classic flow 沒有修復步驟。
  - 附「退回過的做法」表，避免再試沒用的設定。
- **不在這裡**：SDC 寫法看 timing-constraints-sdc；corner 設定看 multicorner-sta；clock tree 看 cts-clock-tree；數值怎麼定看 signoff-criteria。
- **本 repo 實例**：`pnr/picorv32_core/README.md`、`pnr/soc_top/README.md` 的設定表、ADR-0009、ADR-0010、ADR-0012、ADR-0013、ADR-0014、`pnr/check_weak_cells.py`、`docs/notes/repair_design_loop.md`。negative test：P01–P04、P32、P40–P42。

#### hard-macro-integration：hard macro 整合

- **何時用**：把 SRAM、IP 這類已完成版圖的區塊放進設計，或換一顆 macro（例如 Phase 6 的 OpenRAM 自產 SRAM）；macro 的 .lib 只有 TT、或只是解析模型（沒做 SPICE 特性化）。
- **重點**：
  - 每種 view 的來源：GDS、補上 antenna 資料的 LEF、每個 PVT 一份的 .lib（SPICE 實測，Phase 3.5 起）、合成用的 blackbox、修正過的模擬模型。每個產生出來的檔都要能檢查是否過期。
  - .lib 少給一個 corner 時，那個 corner 會把 macro 當 black box，而且不報錯。所以 .lib 要每個 PVT 一份（用 SPICE 實測產生，看 openram-macro-characterization）；只有廠商的單一 TT 解析 .lib 時，暫時用一份保守的 padded .lib 給全部 corner，再用 STA hook 對 macro 加 derate（multicorner-sta）。
  - macro 的行為模型不能放進合成的檔案清單，合成用 blackbox；`VDD_NETS`／`GND_NETS` 要和 macro 的電源 pin 同名。
  - 未用的 port 要 tie-off，checker 要檢查實際接的值。
  - STA 的每個 corner 只能讀到一份 macro .lib：`LIB`、`EXTRA_LIBS` 也會被讀進每個 corner。檢查要打開 STA 讀的每個 .lib 看誰定義了 macro cell，並比完整路徑。
  - macro 在每個 STA corner 都要先證明功能正確：PDK 這顆 SRAM 在低溫、以及 ss 1.60 V 室溫時會讀出前一次的值；corner 之間的溫度 STA 看不到，要另外模擬。不能動的 corner 仍要給一份標明 PLACEHOLDER 的佔位 .lib（否則被當 black box），並列為下線風險。
  - 整合清單逐項連到各 signoff skill（時序、antenna、DRC、LVS、模擬、EQY）。
- **本 repo 實例**：`pnr/soc_top/config.json`、`ip/sram/`、`pnr/soc_top/check_inputs.py`、ADR-0006／0007／0008／0010。negative test：P08、P09、P14、P16–P20、P30、P32。

#### openram-macro-characterization：SRAM macro 的 SPICE 特性化

- **名詞**：特性化是用電路模擬量出 macro 的延遲、setup/hold、最小週期，寫成 STA 讀的 .lib；解析模型是 OpenRAM 不跑模擬、用公式估出來的 .lib。
- **何時用**：macro 的 .lib 只是解析模型或只有一個 corner，要用 SPICE 實測取代；要產生每個 PVT 的 .lib；macro 在某些 corner 讀出前一次的值；ngspice 讀大網表很慢、輸出 bus 節點時報 `bad v() syntax`；要從 GDS 萃取寄生電容；Phase 6 用 OpenRAM 自產 macro。
- **重點**：
  - 先判斷廠商 .lib 是不是解析模型：延遲表每一列相同、最小週期是延遲乘固定倍數。sky130 PDK 附的 SRAM .lib 全部是這種。
  - 量 macro 隨附的網表（和 GDS 同一顆電路），不要用重新產生的電路代替。
  - OpenRAM 自己的 SPICE 特性化有缺陷：setup/hold 只量輸入端那顆 DFF、只量第一個 corner、rise 抄 fall、pulse width 取週期一半、預設沒有走線 RC。
  - 2 KB 完整網表在 ngspice 光讀檔就超過 35 分鐘，要修剪成只留第一／最後一列與行，並和完整網表比對一次；模擬步長也要用小步長驗證。
  - OpenRAM SRAM 的 dout 在上升緣後約 1 ns 就開始變化，廠商 .lib 沒有這條時序弧，STA 不會檢查接收端的 hold；新 .lib 要加上。
  - setup/hold 要在整顆 macro 上量：內部 clock buffer 讓 setup 變負、hold 變大，只量 DFF 的 hold 少算約 0.3 ns。
  - Magic 沒設 `PDK_ROOT` 時會 exit 0 但沒有輸出，要檢查輸出檔。萃取網表的基板網路 VSUBS 與被修剪 cell 的儲存節點會浮接（singular matrix），要接地；處理後仍有暫態不收斂的問題未解決。
  - 量測方法先驗證誤差（步長、修剪、初始條件、延遲表推算，都要偏保守；方向要對 .lib 實際用的那個量判斷，hold 弧和延遲的方向相反），再用植入錯誤證明腳本量得對；植入的字串要先確認找得到、改到預期的次數，否則植入什麼都沒做，測不到要測的東西。
  - 新加的 `rising_edge` 弧接進 SoC 後，要有 negative test 證明 STA 真的用到它。
  - .lib 延遲表的負載斜率會被 OpenROAD 當成 driver 強度。讀出穩定時間會隨負載跳動，照實寫進表裡等於 60–140 kΩ 的 driver，`repair_design` 會一直插 buffer。所以每列取負載中的最大延遲（hold 弧取最小），產生後先單步重跑 repair 確認時間正常。
  - 其他 PVT 的結果常在以 tt 為中心的搜尋範圍外：往外一次多測幾點（2 點、最多 3 次）再接著二分，不要整個重新二分（舊做法 ss 的最小週期預估近 20 小時）。
  - 產生 .lib 的程式本身也要有 checker：另寫一支不 import 它的程式，從量測 JSON 重算每個數字；在 .lib 採用的值上做確認模擬；檢查量測 JSON 的來源與數值、模擬快取是否完整。假的測試資料每格要不同，否則公式錯誤測不出來。
  - 每個 PVT 先證明讀寫正確再量時序。PDK 的 sky130 SRAM 在低溫（tt −40°C、ss −40°C 到 1.95 V）與 ss 1.60 V 室溫（25°C）連續讀到不同值時會讀成前一次的值：sense amp 沒有自己的預充電，column mux 只有 NMOS，內部節點拉不回去。測試序列要有連續讀取不同值的讀取；不能動的 PVT 只記下錯的讀取，給 STA 一份佔位 .lib。
- **不在這裡**：macro 的整合與擺放（hard-macro-integration）；餘量怎麼定（signoff-criteria）；corner 清單（multicorner-sta）。
- **本 repo 實例**：ADR-0010、`ip/sram/char/`（腳本與方法）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`（結果）；植入錯誤 N1–N16（`make neg-char`）與 P04、P17、P30、P32–P36。

#### drc-signoff：DRC、GDS 輸出、XOR

- **何時用**：Magic／KLayout DRC、GDS 輸出、XOR（兩個工具寫出的 GDS 逐點比對）；設計含 macro 時 DRC 不為 0、abstract DRC 報大量 `nwell.4`、GDS 有多個 top cell、金屬密度。
- **重點**：
  - abstract DRC 會在每條 standard cell row 報假的 `nwell.4`，所以改用完整 GDS 的 DRC。
  - SRAM 內部本來就有大量標準規則違規：外框外必須是 0；外框內每個違規都要落在 macro 單獨檢查時、同規則違規的位置上。只比規則種類會漏掉新的錯誤。
  - Magic 與 KLayout 的 sky130 deck 涵蓋範圍不同：KLayout 沒有 latch-up 與 implant 規則，浮接金屬檢查也開不起來。所以「KLayout DRC = 0」不代表全部合格。
  - 設了 `ERROR_ON_MAGIC_DRC=false` 之後 LibreLane 不再替 Magic DRC 判 FAIL，取代它的自寫 checker 必須有自己的植入錯誤。
  - Classic flow 不插 metal fill，也不查密度；soc_top 實測遠低於下限，chip-level 要補。
- **本 repo 實例**：`pnr/soc_top/check_soc.py`（magic_drc）、`pnr/soc_top/sram_drc_alone.py`、`signoff/waivers/`。negative test：P10、P11、P21。

#### formal-equivalence-eqy：formal equivalence

- **名詞**：formal equivalence 是用數學證明兩份電路在所有輸入與狀態下行為相同。
- **何時用**：用 EQY 證明兩份網表（或 RTL 與網表）等價；EQY 當機（SIGSEGV）或分區證不出來；設計 EQY 的 negative test。
- **重點**：
  - 目前可用的組合是合成網表 vs 最終網表。必要設定：加大 stack（`ulimit -s`）、`insbuf off`、刪掉 `$scopeinfo`。
  - EQY 會靜默略過三種情況，都要另外補：被換成常數的 bit（看 log 的 `found constant`）、flip-flop 本身的種類、clock 接線（`sat` 先把所有 flip-flop 改成同一個隱含 clock）。後兩項用 EQY 以外的結構比對。
  - negative test 要分清楚錯誤是被哪一種機制抓到的：分區證明失敗、常數規則、或名稱對應矛盾。而且要有一個非常數的錯誤，證明「證明步驟」本身有效。FAIL 的位置要在植入點附近（被接成常數的腳只往上游追，否則大扇出的 reset 樹會整棵算進來），並在案例之間做交叉檢查。
  - RTL 對合成網表：LibreLane 一定會重新編碼狀態機，目前沒有可用的做法，靠 gate-level 模擬與 directed 測試補。
- **本 repo 實例**：`signoff/eqy/`。negative test：`neg_eqy.py`（soc_top 9 種、Hazard3 版 soc_top 13 種、picorv32 11 種）。

#### antenna-signoff：antenna

- **名詞**：antenna 效應是製造時，只接到閘極的長金屬線收集電荷、擊穿閘極氧化層。
- **何時用**：antenna 違規、diode 插入與它造成的 fanout／slew 副作用、macro 的 LEF 沒有閘極面積資料（`ANTENNAGATEAREA`）。
- **重點**：
  - macro 沒有閘極面積資料時，checker 看不到接到 macro 的線。要從 macro 的 SPICE 算出閘極面積，補進 LEF。
  - 不要用 heuristic diode insertion：soc_top 被插了上萬顆 diode，之後繞線不收斂。
  - ODB 會快取 LEF，換 LEF 驗證時要直接用 openroad 讀。
  - OpenROAD 與 Magic 的 antenna 參數不同。Classic flow 沒有 antenna 的 checker，要自己判。
  - OpenROAD 不讀 `ANTENNAPARTIALMETAL*AREA`，macro 階層之間的 antenna 只能靠 port 上的 diode。
- **本 repo 實例**：ADR-0008、`ip/sram/.../gen_antenna_lef.py`。negative test：P06。

#### cts-clock-tree：clock tree

- **何時用**：clock buffer 的 fanout／cap 違規、skew、clock 輸入 pin 到第一級 buffer 的長線 slew、clock pin 擺放、CTS 把 macro 的 clock 延後而讓 macro 輸入的 hold 變差，以及 setup／hold 違規可能是 clock 造成的時候。
- **重點**：
  - clock pin 到 clock tree 根部的線不在 resizer 的修復範圍內。對策是把 pin 擺在 flip-flop 重心附近，或用 `CTS_CLK_MAX_WIRE_LENGTH` 讓 CTS 把這段線切開加 buffer（soc_top 這樣做之後通過，但同一次 run 也改了別的設定，這一項的效果沒有單獨實驗）。
  - clock buffer 的 fanout／cap 違規：`CTS_SINK_CLUSTERING_SIZE`、`CTS_DISTANCE_BETWEEN_BUFFERS`。PDK 的 `RT_CLOCK_MIN_LAYER` 在 LibreLane 3 沒有生效，clock 實際走 met1／met2。
  - skew 的 metric 含 clock uncertainty 與 derate，不是 skew 的真值。
  - CTS 會把 macro 的 clock 延到與 flip-flop 一樣晚（插 delay buffer），`CTS_DELAY_BUFFER_DERATE_PCT` 管不到這一步。這串 buffer 的上升緣、下降緣延遲不同，讓 SRAM 半週期路徑的 setup 與讀出的 hold 一起變差。關掉用 `clock_tree_synthesis -no_insertion_delay`；LibreLane 沒有對應設定，本 repo 用 LibreLane plugin 換掉 CTS step（ADR-0016）。
  - setup／hold 違規先拆 launch 與 capture 的 clock latency（各 corner、上升緣與下降緣），來自 clock 結構就在 clock 端修。在 data 端補 hold 很貴：delay cell 在慢 corner 的延遲是快 corner 的約 3 倍。
  - 有記錄試過但沒有作用的設定，例如 `CTS_MAX_CAP`。
- **本 repo 實例**：`pnr/soc_top/README.md` 的設定表、`pnr/soc_top/pin_order.cfg`、`pnr/librelane_plugin_arvinsa/`（negative test P52–P54）。

#### pdn-ir-drop：電源網路與 IR drop

- **名詞**：IR drop 是電流流過供電線造成的電壓降；EM（electromigration）是電流密度太大，金屬長期使用後斷線。
- **何時用**：PDN 產生失敗（例如 `PDN-0179` 窄 row）、macro 電源怎麼接、IR drop 分析與門檻、IR drop 結果小得不合理、EM、decap。
- **重點**：
  - 電源連接由四個範圍不同的檢查負責。macro 電源 pin 有沒有真的接上，證據是 IR 分析的連接檢查（PSM）與 LVS。設 `PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路與原本完全相同，不能拿來證明 macro 電源有接。
  - IR 要判 VDD 降壓加 GND 抬升的合計；LibreLane 的 `ir__drop__worst` 只有 VDD。
  - 沒給供電點（`VSRC_LOC_FILES`）時，所有 PDN pin 都被當成理想電源，結果樂觀到不能用。供電點模型要寫明假設，checker 也要擋住比假設樂觀的設定。
  - 最大電流（ff）與最大電阻（ss）不在同一個 corner。EM 要自己開 PSM 的選項，再和 tech LEF 的電流密度上限比對。
  - metric 陷阱：`design_powergrid__drop__average__*` 存的是平均電壓，不是壓降。
- **本 repo 實例**：`docs/notes/ir_worst_case_soc_top.md`、`pnr/soc_top/vsrc/`。negative test：P07、P26–P29。

#### lvs-signoff：LVS 與連接性

- **何時用**：LVS 失敗、macro 在 LVS 中是 black box、驗證電源或訊號 pin 的實體連接、斷線 pin。
- **重點**：
  - macro 用 LEF 萃取時，LVS 只驗 macro pin 的連接，不驗內部。
  - 斷線 pin 的表格只在有斷線時才產生。要讀 log 裡的那一行，有表格時還要確認表格完整。
  - macro 未用的輸出接 RTL 具名 wire，就不算斷線；並確認 `IGNORE_DISCONNECTED_MODULES` 仍是 PDK 預設。
  - 驗證方法：刪掉電源環上的 via，單步重跑萃取與 LVS，必須 FAIL。
- **negative test**：P05、P08、P15。

#### gate-level-simulation：gate-level 模擬

- **何時用**：在網表上跑 regression、RTL 與網表比對、X 的處理、帶電源的網表、cell 模型設定、模擬逾時。
- **重點**：
  - sky130 cell 模型用 `-DFUNCTIONAL -DUNIT_DELAY=#1`。
  - RTL 與網表放在同一個 testbench 做 lockstep，每個 cycle 比輸出，而且要證明比對真的有跑（`gl_compares` > 0，並植入錯誤確認會 FAIL）。X 的規則：RTL 是 0／1 才比，這時網表是 X 也算不一致；RTL 是 X 不比（合成可以合法替它選值）。
  - 帶電源的網表：電源腳沒接好的 cell 輸出 X，lockstep 就 FAIL；Icarus 對 tap cell 多出的 VPB／VNB 報的警告，只對那一個 cell 放行。
  - Icarus 要求先宣告再使用；用腳本改網表時也要注意。
  - 牆鐘時限要依 gate-level 的速度算：照 RTL 速度算只剩約 2 倍餘裕，機器一忙就會誤判逾時。
  - firmware 沒用到的功能，gate-level 模擬看不到（見 dv-directed-tests）。
- **本 repo 實例**：`dv/gl_soc/`、`dv/gl_core/`、`dv/monitors/gl_lockstep.v`。negative test：`neg_gl_soc.py`、`neg_gl_core.py`。

#### floorplan-congestion：floorplan 與繞線壅塞

- **何時用**：決定 die／core 尺寸與使用率（utilization，cell 面積佔可擺放面積的比例）、macro 位置與方向、IO pin、placement 目標密度；遇到繞線壅塞、某條線大幅繞路、窄 row、GCell 溢位。
- **重點**：
  - die 尺寸用前一階段實測的面積估，並寫清楚「使用率」的分母。IO pin 用 `IO_PIN_ORDER_CFG`，並設 `ERRORS_ON_UNMATCHED_IO = "both"`，pin 名稱對不上就報錯。
  - macro 座標要對齊 site 格點。halo 要嘛留出夠寬的 row，要嘛蓋過 core 邊界，否則會出現 PDN 接不到的窄 row。
  - 繞路用「繞線長度 ÷ 端點直線距離」判讀；全域的 congestion 報告看不到局部繞路。
  - logic 區是 L 形時要手動設 placement 目標密度（soc_top：自動的 68% 改 55%，轉角繞路消失）。
- **本 repo 實例**：ADR-0006、`pnr/soc_top/config.json`、`pnr/soc_top/pin_order.cfg`。

#### timing-constraints-sdc：時序約束

- **何時用**：寫或改 SDC（clock、IO delay、例外路徑、derate、max transition）；區分 PnR 與 signoff 的約束；STA 報未受約束的路徑。
- **重點**：
  - 新 SDC 先 `source` LibreLane 的 `base.sdc`，再改需要的一兩項。
  - 設了 `PNR_SDC_FILE` 就一定要同時設 `SIGNOFF_SDC_FILE`，否則 signoff STA 會改用 PnR 的約束。
  - LibreLane 每個 corner 都會檢查未受約束的路徑，但結果沒有變成 metric，也沒有 checker 判 FAIL，要自己寫。
  - 改完約束，用同一份版圖只重跑 STA，確認只改了想改的。
  - 用 `unset_*_delay` 拿掉約束時，STA 的完整性檢查看不出來；要模擬「漏寫」，就產生一份真的少一行的 SDC。
  - 半週期路徑（一個 clock edge 送出、相反 edge 接收）要算 duty cycle。PnR 與 signoff 共用的約束放在同一個檔。
- **本 repo 實例**：`pnr/soc_top/pnr.sdc`、`signoff.sdc`、`clock_uncertainty.sdc`。negative test：P01–P03、P13、P22–P25。

#### signoff-criteria：signoff 條件的推導與每次 harden 後的檢查

- **何時用**：每次 harden 跑完、回報結果之前（PASS 或 FAIL 都要）；決定或檢討任何 signoff 條件的數值，例如 clock uncertainty（jitter、duty cycle、margin）、OCV derate、PVT corner 與溫度反轉、IO delay、IR drop 預算、EM、SI、max transition／cap／fanout、antenna、density、latch-up、macro SPICE 特性化值的餘量；或要說明某個工具沒分析的效應用哪一筆 margin 涵蓋。
- **重點**：
  - 每個條件都要回答四件事：防什麼、數值怎麼算、預設值出自哪裡、工具有沒有分析。LibreLane 的預設值多半是沿用的常數，沒有成分說明。
  - 推導前要先有的輸入：clock 來源、供電範圍、溫度、外部介面時序。沒有就寫「假設」。
  - IO delay 的 `-min` 不能直接設 0，要和上層的 clock latency 一起建模，否則會出現大量假的 hold 違規。
  - macro 的 SPICE 特性化值要加上模型沒涵蓋的部分（寄生、量測誤差、mismatch）：延遲乘比例、setup/hold 加固定值、輸出最早變化的時間乘小於 1 的係數，再和既有保守值取較嚴者。
  - 推導出來的條件要寫進 flow 變成 checker，每個都要有植入錯誤的案例（附 soc_top 的實作範本）。
  - 一組已驗證的工具行為，例如：指定邊緣的 uncertainty 會取代一般值、instance derate 會取代 global、fmax 報告排除半週期路徑、OpenSTA 沒有 SI 分析。
  - 每次 signoff 都要列出「不分析的項目」，寫出各用哪一筆 margin 涵蓋。
  - **每次 harden 後的檢查**（使用者 2026-10-07 要求）：
    - 第一部分由 `signoff/scripts/review_criteria.py` 檢查 criteria 有沒有被執行：config 每個設定都進了 run、uncertainty 出現在每個時序步驟與 signoff corner、corner 齊全、repo 的 checker 都跑了。`pnr/soc_top/run.sh` 每次都跑它，LibreLane FAIL 也照跑；harden 要 PASS，它也必須 PASS。
    - 第二部分由 Claude 依 skill 判讀 criteria 合不合理，寫 `runs/<tag>_signoff/criteria_review.md`（有沒有被執行、合不合理、學習三節）。專案的 Stop hook（`.claude/hooks/require_criteria_review.py`）沒看到就不讓 Claude 回報。
    - golden 比對 FAIL 時，先找出和 golden run 第一個分歧的步驟，判斷是設計或設定改變，還是 flow 不可重現（同一份輸入單步重跑量頻率）；後者交給 signoff-checker-qualification，不直接放寬誤差。
    - 學到的數字寫進依製程分類的 knowledge 檔（`knowledge/sky130A_sky130_fd_sc_hd.md`）；依據不成立的 criterion 提給使用者決定，不自己改。
  - 製程專屬的事實（sky130 的預設值、.lib 範圍、DRC deck、latch-up、density、antenna）放在 knowledge 檔，編號 S2、S10 等沿用原規則編號。
- **本 repo 實例**：`docs/notes/signoff_criteria_soc_top.md`；negative test：`neg_pnr.py` P43–P49（`review_criteria.py` 的每個檢查項）、`make test-review-hook`（Stop hook）。

#### rtl-synthesis-lint：合成與 lint

- **何時用**：Yosys 合成設定、harden 的參數是否與 SoC 裡的 instance 一致、狀態機被重新編碼、暫存器被常數化、lint 警告、latch、為時序目標調整合成。
- **重點**：
  - 參數一致要用 Yosys 讀 RTL 取值比對，不比字串；Yosys 會忽略 `defparam`。
  - LibreLane 的合成一定會跑 `fsm` 重新編碼狀態機，沒有開關，所以 RTL 對網表的 formal 比對會失敗。
  - 上電時值未定、寫入後恆為常數的暫存器，可能被合法地換成常數。
  - LibreLane 的 lint 警告只計數、不判 FAIL，數量由 golden 鎖定。
  - 經驗較少：Phase 4 沒有調整過合成。
- **本 repo 實例**：`pnr/picorv32_core/cpu_params.py`、`rtl/lint/`。

#### flow-regression-reproducibility：一鍵 regression、可重現性與來源追溯

- **名詞**：乾淨 checkout 是從某個 commit 重新取出、沒有任何建置產物的目錄；來源追溯（provenance）是記錄並檢查一個 run 用了哪個 commit、哪版工具與 PDK。
- **何時用**：建立或執行 `make regress`；在乾淨 checkout 驗證；查一個 run 是怎麼產生的；讓下游步驟拒絕過期或沒 PASS 的 run；長時間 run 期間繼續開發或等待它結束；長 regression 開跑前的快速檢查與預跑；長 regression 中途因機器負載 FAIL。同樣設定重跑結果不同、golden 該給多少誤差，看 signoff-checker-qualification。
- **重點**：
  - regression 依相依順序一次跑一個 target，第一個 FAIL 就停。開始前工作目錄要乾淨，並拒絕 `make -i`／`-n`；結束時 HEAD 必須和開始時相同。
  - 只有在乾淨 checkout 從頭跑到底才算驗證。開發目錄裡忽略版控的建置產物，會藏住漏宣告的依賴。
  - 來源追溯要比內容，不只比版本字串：LibreLane clone 不能有改過的檔、PDK 要比內容 sha256、路徑要先解開 symlink。
  - 下游步驟要確認 run 是 PASS，而且來自目前的 commit。
  - golden 與 commit 的先後：更新 golden 的那次 run 永遠過不了下游檢查；要先 commit 新 golden，再用乾淨 checkout 跑完整 regression 證明它可重現。Makefile 要加 `.NOTPARALLEL:`，否則 `make -j` 時各 target 會互刪 `runs/`。
  - 長 run 期間另開 worktree 開發。用舊 run 測新 checker 時建 dev fixture，結果不能當證據。
  - 等長 run 結束用 PID：`pgrep -f` 會比到等待腳本自己；macOS 的 `pgrep` 裡 `\|` 不是「或」；從 log 判斷結果要比整行開頭（`regress: PASS` 也會比到 regress-rtl 那一行）。
  - 長 regression 之前，先用 `make py-check` 和 dev fixture 預跑，提早抓到會在中途才出錯的問題（未定義的名稱、寫檔前先清空了要讀的檔案；改過的 negative test 也要先單獨跑過）。Spotlight 之類的背景負載會拖慢有牆鐘時限的步驟。
- **本 repo 實例**：`scripts/regress.py`、`signoff/scripts/provenance.py`、`run_guard.py`。negative test：`neg_regress.py`、`neg_provenance.py`、`neg_run_guard.py`。

#### multicorner-sta：多 corner STA

- **名詞**：PVT corner 是製程、電壓、溫度的組合（例如 `ss_n40C_1v60`）；RC corner 是繞線寄生的 min／nom／max。
- **何時用**：增減 corner、設定每個 corner 都會執行的 hook、只重跑 STA 做 what-if（改週期、duty cycle、uncertainty、derate）、從 STA 結果推最小週期、繞線前量 resizer 看不到的 corner、corner 變多後 PnR 變慢。
- **重點**：
  - 在 config 設 `LIB` 會取代 LibreLane 的整組 corner 預設，相關的三個變數要一起設；新 corner 的名稱要符合寄生與萃取規則的萬用字元，先跑只做 lint 的 run 看 `resolved.json` 確認。
  - resizer、CTS、其他 step 與 signoff STA，各自讀不同的 corner 變數。`PNR_CORNERS` 沒設時只用 `DEFAULT_CORNER`（LibreLane 的變數說明寫成用 `STA_CORNERS`，和程式不符），所以 placement、global routing 與 PnR 中途的 STA 只看 nom_tt。設定了用哪組 corner，也不代表演算法每個決策都看了那些 corner（resizer 換尺寸只看第一個讀入的 .lib，見 drv-timing-closure 規則 11）。
  - 15 個 corner 會讓 post-GRT 修復停不下來，所以 resizer 維持原本的 9 個，新加的 corner 只在 signoff 判定。這個做法的 setup 部分 Phase 5 證實不夠（長路徑會漏），只給 signoff 看的 corner 要在繞線前量一次：把一個 resizer step 匯出（`eject`）、`RSZ_CORNERS` 加上那個 corner，換成自己的 Tcl 用 `worst_slack -corner` 量。
  - what-if 的正式證據要用 LibreLane 單步重跑全部 corner；單一 corner 的 `sta` 腳本只能當探索。
  - 最小週期要從關鍵路徑推，不能用 `report_clock_min_period`（它排除半週期路徑）。
  - PnR 中途的 STA（`STAMidPNR`）只看預設 corner；flow 中途 state 裡其他 corner 的 metrics 是 placement 前那一步留下的舊值，不能拿來判斷。決策看 signoff STA。
- **本 repo 實例**：`pnr/soc_top/config.json`、`sta_extra_corner.tcl`。negative test：P01–P04、P22–P25、P30。

#### dv-directed-tests：directed 測試補驗證缺口

- **名詞**：directed 測試是針對一個特定功能、明確檢查結果的測試。
- **何時用**：植入的錯誤在 gate-level 模擬或 formal 沒被抓到，或發現某個功能 regression 從沒用到。要證明的是 checker 本身會不會抓錯，看 signoff-checker-qualification。
- **重點**：
  - 缺口從「漏掉的植入錯誤」找。
  - 先讀 RTL 確認實際行為，再寫期望值。
  - 編譯器會改寫非對齊存取，要測特定指令時用 inline assembly，並看反組譯確認。
  - 寫明測不到的部分。新測試要登記在 Makefile、測試清單與 spec；UART 輸出要固定，不要印每次可能不同的數字。加完要重跑完整的 RTL regression 與植入錯誤。
  - 在網表植入對應的錯誤，證明新測試抓得到。
- **本 repo 實例**：`fw/tests/counters/`、`fw/tests/buserr/`、`dv/gl_soc/neg_gl_soc.py`。

#### phase-exit-review：Phase exit review 與獨立審查

- **何時用**：一個 Phase 收尾。
- **重點**：
  - exit criteria 照抄規劃，再加上前一階段帶過來的項目。
  - 證據只用乾淨 checkout 的最後一次 run；前幾次為什麼不算要寫明。每個數字都對回證據檔。
  - 請兩個沒參與實作的 agent 獨立審查：一個核對文件，一個找 checker 漏洞。審查找到的問題沒有重跑驗證，就不能寫「已修正」。
  - 要放寬門檻或改比對規則時先問使用者，並記錄決定。
  - 收尾時分析本階段的重大任務是否需要新 skill，並逐一對照每個 skill、README 與 `description` 有沒有寫回。
- **本 repo 實例**：`docs/phase_exit/phase0.md`–`phase4.md`。

#### core-migration-hazard3：把 CPU 換成 Hazard3

- **名詞**：AHB5 是 pipelined 匯流排，一筆傳輸分 address phase 與下一個 cycle 的 data phase；RVFI 是 core 每退休一條指令輸出的紀錄；ISS 是只模擬指令語意的軟體模型，當參考答案。
- **何時用**：SoC 的 CPU 從 PicoRV32（native bus）換成 Hazard3；選 1port 或 2port wrapper；AHB5 接 1RW 同步 SRAM；設定 Hazard3 的參數；搬移 trap、中斷、reset 相關的測試；建立 core 層級的驗證（上游 riscv-tests、rvcpp 逐指令比對）。
- **重點**：
  - 釘 stable 版、submodule 唯讀；參數要用 instance 參數或 `chparam`（不能用 define），而且要在展開階層前設定。
  - 預設值的陷阱：`CSR_COUNTER` 預設 0、計數器 reset 後是停住的、`EXTENSION_A` 預設開、暫存器堆沒有 reset。
  - debug、power 相關的 port 都要 tie-off，`dbg_sbus_vld` 一定要 0。
  - AHB5 的寫入資料晚一個 cycle，OpenRAM SRAM 要在同一個上升緣拿到位址與資料：要轉接器、write buffer 或 wait state。有副作用的周邊只在 `htrans[1] && hready` 那個 cycle 取樣。
  - 沒有 trap 腳、中斷是 level-sensitive 的標準模型、reset 是非同步的（要同步器）、CPI 小很多：依賴這些的測試與 checker 要重新定義或重量。
  - 上游測試要 newlib 工具鏈；rvcpp 印的是退休指令 trace，要自己用 RVFI 轉成同格式再逐條比對。
  - 舊 core 的建置要保持不變：新 core 專用的 RTL 都放在 define 下，再用前置處理後的 RTL 比對證明舊建置一字不差，舊的 golden 就能沿用。
  - 轉成 native bus 時，AHB 讀取的 `hwdata` 要擋掉（它會變動或是 X）；`mtval` 固定為 0；中斷進入次數與 cycle 數的期望值要依 CPU 分開訂。
  - PnR 與 signoff：PicoRV32 版調好的設定不能直接沿用。resizer 要看 signoff 的所有慢 corner、resizer 會換上的弱 cell 要重查、開繞線後的 setup 修復；上限檔裡依設計結構推導的數字（例如沒有寄生資料的 driver 數）要用新 core 的 run 重數，golden 另建一份，並重新量同設定 run 之間的差異（ADR-0015）。
  - core 層級驗證：測試台的設定檔從 SoC 的參數自動產生；上游測試台與 riscv-tests 都在 `runs/` 建置，submodule 不留檔案；rvcpp 要補 `fence`，而且它的 CSR 模型是全功能設定，所以逐指令比對只做 user-level 指令、從測試本體開始。
- **不在這裡**：SoC 驗證的一般寫法看 dv-directed-tests、gate-level-simulation；SRAM 整合看 hard-macro-integration。
- **本 repo 實例**：ADR-0011～0014、`rtl/cpu/`、`dv/core_hazard3/`（`make core-hazard3`）、`signoff/limits/soc_top_hazard3.toml`、`signoff/golden/soc_top_hazard3/`、`docs/phase_exit/phase5.md`（Phase 5）。

### skill 的由來

- 最初 11 個依使用者要求，對應重大流程任務（CTS、LVS、DRC、IR、timing、EQY……）。
- `floorplan-congestion`、`timing-constraints-sdc`、`rtl-synthesis-lint` 是 2026-10-03 請 Gemini 3.8 Flash（Antigravity CLI）審查「還漏了哪些任務」後補上的。同一次審查建議的 `openram-macro-characterization`（Phase 3.5／6）、`core-migration-hazard3`（Phase 5）、`tapeout-precheck-caravel`（Phase 7），會在進入那個 Phase 時建立；`openram-macro-characterization` 已在 Phase 3.5 開始時（2026-10-04）建立。
- `signoff-criteria` 是 2026-10-03 討論「clock 沒有 PLL，那 clock 從哪來」時，發現 signoff 條件多半沿用預設值、沒有推導，依使用者要求新增。
- 最後 4 個是 Phase 4（2026-10-04）依使用者要求，分析 Phase 4 的重大任務後新增的：一鍵 regression 與來源追溯、多 corner STA、directed 測試補缺口、Phase exit review。Phase 4 的其他任務（checker 漏洞、L5 模擬、IR、EQY、DRC 位置比對、signoff 條件、CTS 與 resizer 餘量）寫回既有的 skill。

### 在其他專案使用

使用者的做法（2026-10-04）：開新專案時，請 Claude Code 或 Codex「使用 arvinsa-rtl-gds 這個 repo 的流程」。skill 不搬到使用者層，也不複製到新專案；新專案的 agent 直接讀這個 repo（本機 clone 或 GitHub）。所以這個 repo 要讓沒參與過的 agent 自己讀得懂：

- **入口**：本節的「依情況找 skill」表，再讀對應的 `.claude/skills/<name>/SKILL.md`。SKILL.md 是一般的 Markdown，任何 agent 都能讀；只有在本 repo 裡開 Claude Code 時才會自動載入，在新專案裡要明確叫 agent 來讀。
- **Codex**：讀的是 repo 根目錄的 `AGENTS.md`；本 repo 的 `AGENTS.md` 指回 CLAUDE.md 與本節，不另寫一份。
- **可以直接沿用的流程骨架**：
  - `scripts/regress.py`：一鍵 regression。
  - `signoff/scripts/provenance.py`、`run_guard.py`：來源追溯，與下游拒絕過期的 run。
  - `signoff/scripts/check_signoff.py` 加 `signoff/limits/*.toml` 的格式：signoff 門檻與 golden 比對。
  - `pnr/librelane_flow.sh`：LibreLane 呼叫與有上限的重試。
  - `pnr/librelane_plugin_arvinsa/`：不改 LibreLane、只換掉一個 step 的寫法（`meta.substituting_steps` 加 `PYTHONPATH`；ADR-0016 的 CTS）。
  - `dv/scripts/dvlib.py`：模擬的 checker。
  - `dv/monitors/gl_lockstep.v`：RTL 與網表 lockstep。
  - `signoff/eqy/`：EQY 與它的植入錯誤。
  - `env/versions.mk`、`env/check_env.sh`、`toolchain.md`：釘版與環境檢查。
  - `scripts/check_py_names.py`、`scripts/check_skills.py`：開跑前的快速檢查。
- **要依新設計重做的**：
  - `pnr/<design>/config.json`、SDC、`signoff/limits/` 的數值，並用 `signoff-criteria` 重新推導。
  - golden。
  - 和設計綁在一起的植入錯誤案例，例如 `neg_pnr.py` 的 P01–P32。
  - ADR、exit review 的內容。
- **經驗寫回這裡**：新專案用到某個 skill 時發現的通用經驗，寫回本 repo 的 `SKILL.md`，並同步本節，維持單一來源；只屬於新設計的數字留在新專案的文件。

## 授權

本 repo 的內容以 [Apache License 2.0](LICENSE) 授權。
之後引入的第三方元件保留各自的授權，例如 PicoRV32 為 ISC，Hazard3 與 sky130 PDK 為 Apache-2.0。
