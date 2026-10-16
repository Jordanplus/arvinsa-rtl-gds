# arvinsa-rtl-gds

以全開源 EDA 工具鏈建立一條可重複執行、有 regression test 的 RTL-to-GDS 流程，
並以開源 RISC-V SoC（含 SRAM macro）當 test vehicle，一路跑到 signoff（DRC／LVS／STA PASS）。

An open-source RTL-to-GDS flow on SkyWater sky130A using LibreLane and OpenRAM SRAM macros,
with RISC-V cores (PicoRV32, then Hazard3) as test vehicles. Documentation is written in Traditional Chinese.

## 專案狀態

**2026-10-15：Phase 0–7 與 Phase 3.5 完成（Phase 7 只做到 ChipFoundry precheck PASS，不下線）。** 完整規劃見 [project-plan.md](project-plan.md)。

- Phase 0：Nix、LibreLane 3.0.14、sky130A PDK 已安裝；LibreLane 官方的 SRAM 參考設計在本機重跑，signoff 全 PASS。紀錄見 [docs/phase_exit/phase0.md](docs/phase_exit/phase0.md)。
- Phase 1：PicoRV32 SoC 的 RTL、firmware、RTL 模擬 regression 完成。正向測試 26/26 PASS（Icarus、Verilator），33 項植入錯誤都在預期的 checker FAIL；經兩輪獨立 testbench qualification review。紀錄見 [docs/phase_exit/phase1.md](docs/phase_exit/phase1.md)。
- Phase 2：PicoRV32 單獨 harden 到 GDS（40 ns）。DRC、LVS 為 0，9 個 corner 的 setup／hold 與 slew／cap／fanout 全部 PASS；上游 ISA 測試在最終 netlist 上 PASS，RTL 與 GL 的 bus transaction 每一筆都相同；soc_top 的 `DIE_AREA` 定為 1000 × 800 µm（ADR-0006）。紀錄見 [docs/phase_exit/phase2.md](docs/phase_exit/phase2.md)。
- Phase 3：SoC 整合 PDK 附的 2 KB SRAM macro，harden 到 GDS（1000 × 800 µm，40 ns）。
  - 9 個 corner 的 setup／hold 與 slew／cap 全部 PASS；LVS、KLayout DRC、XOR 為 0；SRAM 範圍以外的 Magic DRC 為 0。
  - EQY 證明合成 netlist 與最終 netlist 等價（RTL 到合成 netlist 這一段還沒有 formal 證明）。13 支 gate-level 模擬測試裡，RTL 與 netlist 每個 cycle 都相同。
  - 植入錯誤全部在預期的 checker FAIL：PnR 20 個、EQY 11 個、gate-level 模擬 4 個、來源追溯 9 個。
  - `make phase3` 在乾淨 checkout 從頭到尾跑完 PASS。這是第四次：第一次遇到 OpenROAD 的隨機錯誤，用有上限的重試繞過；第二、三次分別是少宣告對 firmware 的相依、一個植入錯誤的案例編譯不過，都已修正。
  - signoff 條件本身的缺口（clock duty cycle、IR drop 預算等）列為 Phase 4 待辦。
  - 紀錄見 [docs/phase_exit/phase3.md](docs/phase_exit/phase3.md)。
- Phase 4：signoff 收斂與一鍵 regression。
  - soc_top 收斂在 42 ns：25 ns、40 ns 在加嚴的條件下做不到，使用者決定改 42 ns；SRAM 的時序仍是假設值（ADR-0007）。
  - 15 個 corner（加上 temperature inversion 的 corner：低電壓時 cell 在低溫反而比高溫慢）的 setup／hold 與 slew／cap 全部 PASS；VDD 與 VSS 兩端 IR drop 的合計 8.07 mV（上限 20 mV）。
  - EQY 另外比對 flip-flop 種類與 clock 接線；PG netlist（有電源與地接腳的 netlist）的 gate-level 模擬 15/15 PASS；補 2 支 directed 測試。
  - `make regress` 一個指令跑完 Phase 1–4 的全部檢查。第 4 次在乾淨 checkout 25/25 PASS（123 分鐘），163 個植入錯誤全部在預期的 checker FAIL。前 3 次重跑的原因：依獨立審查修改 checker、多執行緒繞線的中間數字不同、gate-level 模擬的時限太緊。
  - 重現性只在同一台機器驗證過。
  - 紀錄見 [docs/phase_exit/phase4.md](docs/phase_exit/phase4.md)。
- Phase 3.5：SRAM 的時序改用 SPICE 模擬量測（本機 ngspice 量 PDK 附的電晶體級 netlist，ADR-0010）。
  - 5 個 PVT 各一份 .lib，由量測結果的 JSON 產生並檢查沒過期；加上 dout0 在 clock 上升緣後就開始變化的 hold arc。
  - 延遲、setup、週期都仍由原本保守的下限決定；新的 hold arc 讓 soc_top 週期 42 → 43 ns（使用者決定）。
  - **頭號下線風險**：這顆 SRAM 在 ss 1.60 V 的 −40°C 與 25°C 讀取失敗（讀成前一次的值，sense amp 的設計問題），ss −40°C corner 用 placeholder .lib（不是量測值）。Phase 6 用 OpenRAM 產生的 macro 已修正。
  - `make regress` 第 2 次在乾淨 checkout 25/25 PASS（136 分鐘），soc_top 439 個 metric 與 golden 完全相同，164 個植入錯誤全部在預期的 checker FAIL。第 1 次因一個植入程式的 bug FAIL，已修正。
  - 獨立審查更正了文件，並找到 12 個 checker 漏洞（沒有一個造成 false pass，也就是實際有錯、checker 卻判 PASS），Phase 5 開頭修。
  - 紀錄見 [docs/phase_exit/phase3_5.md](docs/phase_exit/phase3_5.md)。
- Phase 5：CPU 換成 Hazard3（`hazard3_cpu_1port` 加 AHB-to-native bus bridge，ADR-0011），PicoRV32 版保留在 `make regress-picorv32`。
  - riscv-tests 65/65，與 rvcpp 逐條指令比對 48/48；兩個 CPU 共用同一份 flow 設定，只差 RTL。
  - 週期 44 ns。為了 Hazard3 改了 4 項 flow 設定（ADR-0012–0014、0016），以及 met5 strap 加寬到 4.8 µm（ADR-0017）。
  - 15 個 corner 的 setup／hold 全部 PASS：Hazard3 +1.114／+0.109 ns、PicoRV32 +0.789／+0.080 ns。
  - IR 的 worst-case 組合（ff 電流＋ss 金屬電阻，人為湊出的上限）Hazard3 14.13 mV、PicoRV32 5.72 mV，上限 20 mV；Phase 5 起 flow 每次 harden 都檢查 worst-case 組合（Phase 7 改成在兩個 slow corner 檢查，這個組合只列為參考，ADR-0019 決定 19）。
  - 獨立審查找到 8 個 checker 漏洞，並發現 Hazard3 的 worst-case IR 原本 25.75 mV 超標，全部修正後重跑。
  - 結案證據：commit `71b1454` 的乾淨 checkout，`make regress` 21/21（109 分鐘）、`make regress-picorv32` 26/26（124 分鐘），三次 harden 都與 golden 逐項相同。
  - 紀錄見 [docs/phase_exit/phase5.md](docs/phase_exit/phase5.md)。
- Phase 6：SRAM 換成 OpenRAM 產生的 `arv_sram_2kbyte_1rw1r_32x512_8`（OpenRAM 釘選 commit 加 repo 內 4 個 patch，ADR-0018）。
  - Phase 3.5 的頭號下線風險已解決：sense amp 輸入端預充電，加上 `clk1` 接系統時脈，7 個 PVT 條件都讀對；layout 萃取 netlist（含寄生）在 tt、ss −40°C、ss 100°C 也讀寫正確。
  - 5 個 PVT 的時序與功耗都用 SPICE 量，寫成 .lib；macro 的每個 view 先過 view QA 才交給 flow。
  - macro 的 DRC 合併錯誤區域後每種規則都 ≤ PDK 附的那顆 macro，flow 的 KLayout deck 0；OpenRAM 的 LVS match。
  - 15 個 corner 的 setup／hold 全部 PASS：Hazard3 +0.656／+0.126 ns、PicoRV32 +0.769／+0.082 ns；IR 的 worst-case 組合 15.91／13.49 mV（上限 20 mV）。
  - 已知限制：.lib 的時序沒有繞線寄生（萃取 netlist 的延遲是 schematic netlist 的 2.0 倍），靠下限蓋住；dout0 transition 偏低，改成量到的值後 setup 仍 +0.37 ns。
  - 獨立審查找到 7 個 checker 漏洞，全部修正後重跑；第一次結案 regress 抓到修正時弄壞的一支 checker，修正後重跑。
  - 結案證據：commit `85bfa75` 的乾淨 worktree，`make regress` 23/23（126 分鐘）、`make regress-picorv32` 28/28（196 分鐘），三次 harden 都與 golden 逐項相同。
  - 紀錄見 [docs/phase_exit/phase6.md](docs/phase_exit/phase6.md)。
- Phase 7：Hazard3 SoC 與 OpenRAM 產生的 SRAM 以 flat 方式（standard cell 與 SRAM macro 直接在 wrapper 層做 placement 與 routing）放進 ChipFoundry Caravel 的 `user_project_wrapper`，只做到 precheck PASS，不下線（ADR-0019）。
  - 官方 precheck image 13 項中 11 項 PASS；`klayout_feol`／`klayout_beol` 只剩 OpenRAM bitcell 的兩條規則，每個違規位置都和 PDK 附的 SRAM 單獨檢查時相同（決定 5 的判斷方式，ChipFoundry 收不收不知道）。
  - wrapper 完成和 soc_top 同一套 signoff：15 個 corner 的 setup／hold +0.548／+0.187 ns，EQY 16149/16149，gate-level 模擬 16/16。IR 從 Caravel 的 pad 起算、用 CPU max power pattern 的 switching activity 檢查，19.56 mV（上限 20 mV）。
  - 流程新增「先規劃 pad、block 位置與 pin，經使用者核准才寫 RTL 與 harden」，用 checker、hook、skill、流程文件強制（CLAUDE.md 規則 14）。
  - 獨立審查找到 8 個 checker 漏洞與 1 個漏掉的檢查，全部修正後重跑；流程回顧整理出 19 條該提早做的檢查（ADR-0020），放寬項目記進放寬清單（`docs/relaxation_register.md`）。
  - 下線前要處理：precheck 的判斷方式要 ChipFoundry 確認、SRAM .lib 沒有繞線寄生（dout0 改成量到的值後 setup 剩 +0.151 ns）、金屬密度低於 tapeout 的下限、EM 沒檢查、IR margin 只有 0.44 mV。
  - 結案證據：commit `2b04451` 的三個乾淨 worktree，`make regress-caravel` 18/18（476 分鐘）、`make regress-picorv32` 31/31（248 分鐘）、`make regress` 30/30（211 分鐘）；四次 harden 都與 golden 逐項相同。
  - 紀錄見 [docs/phase_exit/phase7.md](docs/phase_exit/phase7.md)。

## 快速開始

```bash
make help          # 所有 target
make env-check     # 檢查本機工具、固定版本的 IP、toolchain.md 是否最新
make smoke         # 環境檢查、Python 名稱檢查、lint、firmware、RTL 模擬 smoke（約 30 秒）
make phase1        # Phase 1 完整檢查（約 4 分鐘）
make phase2        # Phase 2 完整檢查：LibreLane harden + GL regression（約 24 分鐘，需要 flow 環境）
make phase3        # Phase 3 完整檢查：SoC 與 core 的 harden、EQY、GL 模擬與全部植入錯誤（約 91 分鐘，需要 flow 環境）
make regress       # Hazard3 版 SoC 的全部檢查一次跑完（Phase 5 起的主要設計；依序執行、第一個 FAIL 就停；需要 flow 環境）
make regress-picorv32  # PicoRV32 版 SoC 的全部檢查（Phase 1–4 的 make regress，約 2–2.5 小時）
make regress-caravel   # Caravel wrapper 的全部檢查，含官方 precheck（約 6–8 小時，需要 lima VM）
```

`make regress` 的結果在 `runs/regress/`（`make regress-picorv32` 在 `runs/regress_picorv32/`，`make regress-caravel` 在 `runs/regress_caravel/`）：`summary.md`（每個 target 的 PASS／FAIL 與時間）、`junit.xml`、每個 target 的 log。
個別 target 用 `CPU=picorv32`（預設）或 `CPU=hazard3` 選 SoC 的 CPU，例如 `make harden-soc CPU=hazard3`（run 在 `runs/soc_top_hazard3/`）。
Phase 7 的 Caravel wrapper 用 `make harden D=user_project_wrapper`（等於 `make harden-soc CPU=caravel`，run 在 `runs/user_project_wrapper/`）。
它會先刪掉自己的結果目錄，並由每個 harden 步驟重新產生自己的 run；下游步驟只接受同一個 commit 產生、且 PASS 的 run。
工作目錄有未提交的修改時，來源追溯（provenance）會判 FAIL，所以請在乾淨的 checkout 上執行。

第一次在新機器上建 flow 環境的步驟見 [env/setup.md](env/setup.md)。

## 技術組合

| 項目 | 選擇 |
|---|---|
| PDK | SkyWater sky130A，標準元件庫 `sky130_fd_sc_hd` |
| RTL-to-GDS flow | [LibreLane](https://github.com/librelane/librelane) 3.x（Classic flow），內含 Yosys、OpenROAD、Magic、KLayout、Netgen |
| SRAM | 先用 PDK 附的 OpenRAM macro（2 KB，`sky130_sram_2kbyte_1rw1r_32x512_8`），後期改用 [OpenRAM](https://github.com/VLSIDA/OpenRAM) 自己產生 |
| RISC-V core | 先用 [PicoRV32](https://github.com/YosysHQ/picorv32)，再換 [Hazard3](https://github.com/Wren6991/Hazard3)，證明流程可以換 core |
| 模擬 | Verilator、Icarus Verilog |
| Firmware | riscv64-elf-gcc（rv32） |
| 執行環境 | Apple Silicon macOS + Nix；OpenRAM 也在本機原生執行（官方環境是 x86_64 Linux，只用 Colab 對照，ADR-0018） |

完整的工具與版本清單見 [toolchain.md](toolchain.md)，固定版本的值以 `env/versions.mk` 為準。

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
| 2 | 單獨 harden PicoRV32，確認 RTL 到 GDS 的流程能完整跑完，並取得面積與時序的實際數字 | 完成（2026-10-03） |
| 3 | 整合 PDK 附的 SRAM macro | 完成（2026-10-04） |
| 3.5 | （選用）用 SPICE 模擬量測 SRAM macro 的時序，取代假設值。2026-10-04 改為本機 ngspice 直接量 PDK 附的 netlist（ADR-0010） | 完成（2026-10-05） |
| 4 | Signoff 收斂、單一指令跑完整 regression、補齊文件 | 完成（2026-10-04） |
| 5 | 換成 Hazard3 | 完成（2026-10-08） |
| 6 | 用 OpenRAM 產生的 SRAM 取代 PDK 附的 macro | 完成（2026-10-11，ADR-0018） |
| 7 | （選用）chip-level 整合：Hazard3 SoC 放進 ChipFoundry Caravel，做到 precheck PASS、不下線 | 完成（2026-10-15，ADR-0019） |

各階段的 exit criteria 與工時估計見 project-plan.md 第 8 章。

## 驗證方式

- **分層 regression test**：lint、RTL 模擬、gate-level 模擬、PnR signoff、equivalence check、post-layout 模擬。
- **Signoff 門檻**：多個 STA corner 的 setup 與 hold 全部 PASS：PicoRV32 單獨 harden 是 9 個（tt／ss／ff 三種 library corner × 三種繞線寄生 RC），soc_top 另加兩個 temperature inversion 的 PVT，共 15 個，
  另有 DRC、LVS、antenna、IR drop 等 metrics 門檻。
- **Bug injection**：刻意植入錯誤，確認對應的 checker 確實會 FAIL，避免 checker 永遠 PASS 卻抓不到問題。
- **每次 harden 後檢查 signoff criteria**：`review_criteria.py` 確認自己訂的條件這次真的有生效（LibreLane FAIL 時 checker 也照跑），再由 Claude 依 skill `signoff-criteria` 判讀條件合不合理，寫 `runs/<tag>_signoff/criteria_review.md`。專案的 Claude Code Stop hook 沒看到這份檢查，就不讓 Claude 回報 harden 結果。

細節見 project-plan.md 第 6、7 章。

## 流程（簡易版）

完整、詳細的流程（每一步怎麼跑、PASS 條件是什麼、交給哪個 skill，以及在新專案怎麼沿用）在 **[arvinsa-rtl-gds-flow.md](arvinsa-rtl-gds-flow.md)**。

1. 環境與固定版本：工具、PDK、IP 的固定版本（`toolchain.md`、`env/versions.mk`），`make env-check-flow`。
2. 規格與計畫：`project-plan.md` 分 Phase，重大選擇由使用者決定並記成 ADR。
3. RTL 與 RTL 驗證：lint、合成檢查、self-checking 模擬與植入錯誤。
4. macro：取得或產生 → 每個交付檔的 view QA → 整顆 macro 的 DRC → 各 corner 功能確認 → 用 SPICE 做 characterization、產生每個 PVT 的 .lib。
5. constraint 與 signoff 條件：週期、corner、SDC，推導每個 signoff 門檻。
6. harden：輸入檢查 → LibreLane（floorplan、PDN、placement、CTS、routing）→ 每次跑完做 criteria review；第一次全部 PASS 後建立 golden。
7. signoff：多 corner STA、DRC、LVS、antenna、IR drop，門檻有推導、有 golden。
8. netlist 驗證：等價證明、gate-level 模擬。
9. 一鍵 regression 與來源追溯，乾淨 checkout 執行。
10. Phase 收尾：獨立審查、exit review、經驗寫回 skill。

每個 checker 都有 negative test（植入錯誤後必須 FAIL）。

## Claude Code skills（流程知識庫）

`.claude/skills/` 放了 30 個 Claude Code skill，每個對應 RTL-to-GDS 流程中的一類任務。skill 是一份工作說明（`SKILL.md`），內容是已驗證的規則、已知陷阱、植入錯誤的案例（negative test），以及每次使用後追加的經驗紀錄。

**分成三段，各一個入口**（ADR-0021 決定 6，使用者 2026-10-15：「整個流程可以分成Middle-end，backend，package 三大部分，每一部分各自搜尋相關的skill」）：

| 段 | 入口 skill | 細部 skill |
|---|---|---|
| Middle-end：RTL 到 netlist、constraint、macro 與 IP 準備、netlist 等價 | `middle-end-flow` | rtl-synthesis-lint、dv-directed-tests、core-migration-hazard3、timing-constraints-sdc、formal-equivalence-eqy、macro-qualification、openram-macro-generation、openram-macro-characterization、sram-layout-extraction |
| Backend：LibreLane harden、PnR 與實體 signoff | `backend-flow` | floorplan-congestion、hard-macro-integration、pdn-ir-drop、cts-clock-tree、drv-timing-closure、multicorner-sta、antenna-signoff、drc-signoff、lvs-signoff、gate-level-simulation、signoff-criteria、librelane-run-debug |
| Package：晶片層級、wrapper 與下線 | `package-flow` | chip-floorplan-pin-planning、caravel-user-project-integration、tapeout-precheck-caravel |
| 跨段共用 | — | signoff-checker-qualification、flow-regression-reproducibility、phase-exit-review |

**Claude 怎麼挑 skill**：
- 每次對話開始時，Claude 只看得到 skill 清單：名稱加上開頭的 `description`（什麼情況用）。判斷和手上的任務相關，才讀整份 `SKILL.md`。
- 清單有長度預算：單份 description 超過 1,536 字元會被截斷；全部超過 context window 的 1% 時，最少被使用的 skill 先失去 description。2026-10 時有 5 個 skill 因此只剩名稱。
- 所以清單上只保留 3 個入口與 3 個跨段共用 skill 的 description。其餘 24 個細部 skill，在專案 `.claude/settings.json` 的 `skillOverrides` 設成 `name-only`，只列名稱。
- Claude 先讀該段的入口，入口裡的「情況／錯誤訊息 → 細部 skill 檔案」表，再指到要讀的 `SKILL.md`。
- `make skill-check` 檢查三件事：每個細部 skill 剛好在一個入口的表裡；設定與分段一致；長度上限（單份 ≤ 1,024 字元，清單上的 description 合計 ≤ 8,000）。

這一節是給人看的索引：先用「依情況找 skill」查，再看每個 skill 的說明。

**只在本 repo 生效**：這些 skill 放在專案層，只有在這個 repo 裡用 Claude Code 才看得到。在其他專案使用的方法見 [arvinsa-rtl-gds-flow.md](arvinsa-rtl-gds-flow.md) 第 1 節。

**經驗怎麼累積**：
- 每個 `SKILL.md` 結尾有「經驗紀錄」表。每次做完該任務，就把新遇到的現象寫一列：日期、run、原文訊息、原因（標明已驗證或推測）、處理方式、證據路徑。
- 同一個現象出現兩次以上，或原因已經用實驗確認，才從紀錄搬進正式規則。
- skill 的重要任務是防工具的缺陷（使用者 2026-10-07，`CLAUDE.md` 規則 10）：確認過的工具缺陷，要寫出症狀（確切的訊息）、怎麼發現、怎麼繞過，以及怎麼防止再發生（能抓到它再次出現的 checker 或 negative test）；這些對策不能綁在 step 名稱、log 措辭這類 flow 會變的東西上。
- 這顆設計的具體數字（設定理由、試跑紀錄）留在 repo 文件；skill 只放可以帶到下一顆設計的規則，和指向 repo 文件的連結。
- 製程相關的知識依製程分類：`signoff-criteria/knowledge/<製程>.md` 累積 PDK 事實與每次 harden 量到的校準資料，下一顆同製程設計用它來定 criteria。
- skill 的規則、陷阱或適用範圍有改，同一個 commit 就要更新本節該 skill 的說明，以及該 `SKILL.md` 的 `description`。`make skill-check` 會檢查格式與索引是否齊全，但內容是否一致仍要人檢查。

規則見 [CLAUDE.md](CLAUDE.md)。Phase 0 的環境建置不做成 skill。

### 依情況找 skill

| 遇到的情況 | 先看 | 再看 |
|---|---|---|
| 不確定該讀哪個 skill：依工作屬於哪一段 | middle-end-flow（RTL、合成、SDC、EQY、macro 準備）、backend-flow（harden、PnR、signoff、LibreLane 除錯）、package-flow（pad／pin 規劃、wrapper、precheck） | 各入口表列的細部 skill |
| 開新設計寫計畫：定 VDD 與 Tj 的操作條件、推 corner 清單；第一份 netlist 後想知道哪個 corner 決定週期、代價多少；任何 harden（含子區塊單獨 harden、試跑）之前先定 signoff 條件 | signoff-criteria（「提早檢查」A1、A3、C1） | multicorner-sta（只重跑 STA 的 what-if）、macro-qualification（規則 2：macro 已驗證的範圍） |
| 選下線服務商：precheck 的每一項檢查、wrapper 的 IO constraint、供電 pad、fill 與密度上下限、下線服務商用的 PDK 與工具版本要算到本設計的數字；需要下線服務商回覆的問題；wrapper 設計第一次試跑的 harden 完成後 | caravel-user-project-integration（規則 5、6）、tapeout-precheck-caravel（規則 11） | chip-floorplan-pin-planning（電源進入點）、timing-constraints-sdc（IO constraint） |
| 選 macro 之前：macro 的晶片實測或 characterization 範圍比 signoff corner 窄（例如只到 1.7 V、沒有 −40°C）、要不要用這顆 macro；換 macro 時舊檢查要不要重跑 | macro-qualification（規則 2、4） | openram-macro-characterization（SPICE 讀寫的做法）、sram-layout-extraction（layout 萃取）、tapeout-precheck-caravel（規則 2：下線服務商的 DRC deck） |
| 要放寬或補償某項條件（加長週期、加 margin、placeholder .lib、只在某個 corner 檢查、延後處理）；換設計或換 macro 後，舊的放寬還成不成立 | signoff-criteria（「提早檢查」E1，`docs/relaxation_register.md`） | phase-exit-review（已知限制引用放寬清單）、drv-timing-closure（規則 15：resizer 少看 corner） |
| 要跑 LibreLane、從中間 step 接續（包括已跑完的 run 改設定從中間重來）、只重跑一個 step、重跑時保留上一次的 run；LibreLane／OpenROAD 升版時要重看哪些對策 | librelane-run-debug（「升版時要重看的綁定」一節） | — |
| run 失敗、錯誤時有時無（例如 `GRT-0229`、總 overflow 只有個位數的 `GRT-0116`）、`RSZ-0074 failed to build tree from gloubal routes`（三種原因的對照表）、某一步很久不結束或記憶體一直漲（規則 7） | librelane-run-debug | drv-timing-closure（繞線後 ECO 在這版 OpenROAD 做不到，會報 `RSZ-0074`；resizer 停不下來：推最小負載就超標的 cell、slew margin、post-GRT 修復的設定）、multicorner-sta（corner 太多）、openram-macro-characterization（macro .lib 的延遲隨負載電容上升太快） |
| STA 有 setup／hold 違規（`Setup violations found in the following corners`）；hold 修復的 log 報 `RSZ-0064 Unable to repair all hold checks`、進度表看似卡住、`RSZ-0032` 的數字太小 | drv-timing-closure（規則 16：hold 修復的 log 怎麼讀） | multicorner-sta（哪個 corner、只重跑 STA 試）、timing-constraints-sdc（constraint 有沒有寫錯）、cts-clock-tree（macro 的 clock 被延後） |
| hold delay cell 卡在 setup 吃緊的路徑上、半週期路徑、launch 與 capture 的 clock 差隨 corner 變號 | cts-clock-tree | drv-timing-closure（hold 修復本身） |
| max slew／cap／fanout 違規；signoff 只有少數內部 net 略超、post-GRT 修復時卻已是 0 | drv-timing-closure（規則 13：最後一次修復後的重新 global routing 造成繞路，降 placement 密度） | floorplan-congestion（繞路、局部熱點）、antenna-signoff（diode 增加 fanout）、cts-clock-tree（clock net）、signoff-criteria（Caravel 給的 input transition 就超過上限：Caravel 直接驅動的 IO net 另外檢查） |
| 修某個 corner 的違規；換 PnR／sizing 工具或升版；改 corner、library 或修復 margin | drv-timing-closure（規則 11：用違規 corner 的資料判斷該怎麼修，工具有沒有做到要用對照實驗確認；規則 10：檢查 drive 太弱的 cell） | multicorner-sta（哪個 step 用哪組 corner） |
| signoff 才在 resizer 看不到的 corner 出現 setup 違規；繞線前想看某個 corner 的 slack | drv-timing-closure（規則 9：不能只靠 PnR 的 margin 補，長路徑會漏；規則 15：拿掉 corner 要有原因、what-if、ADR） | multicorner-sta（規則 8：繞線前怎麼量；規則 7：flow 中途 state 的 metrics 可能是舊值） |
| CTS 後修完 setup，signoff 卻在長路徑 setup 違規；想調大 setup margin 或加週期 | drv-timing-closure（規則 12：先量差距落在哪一段，繞線後才出現的就開 `RUN_POST_GRT_RESIZER_TIMING`） | signoff-criteria（`review_criteria.py` 印出每次修復到 signoff 的差距） |
| harden 跑完（PASS 或 FAIL）、要回報結果前；自己訂的 signoff criteria 有沒有生效、還合不合理；Stop hook 說要寫 `criteria_review.md`；flow log 有 `The checker will be skipped`、`metric was not found` | signoff-criteria（每次 harden 後的檢查；規則 30：內建 checker 沒設門檻就略過；knowledge 檔依製程分類，出處不能是會被覆蓋的路徑） | drv-timing-closure（怎麼修）、multicorner-sta（corner） |
| 要決定週期，或從 slack 推最小週期 | multicorner-sta | signoff-criteria |
| 要定 clock uncertainty、derate、corner、IR 上限、max transition 這類數值 | signoff-criteria | timing-constraints-sdc（寫進 SDC）、pdn-ir-drop（IR） |
| 寫或改 SDC；signoff 的 sta.log 讀的是 `pnr.sdc`（`SIGNOFF_SDC_FILE` 沒設）；改了 constraint 要確認生效；STA 報 unconstrained endpoint；`set_input_transition` 寫了但報表的腳位 slew 沒變；放進 Caravel wrapper 的 IO constraint | timing-constraints-sdc（規則 2；規則 16：看報表的路徑分解） | caravel-user-project-integration（Caravel 的 clock 來源、IO constraint 試算） |
| 增減 PVT corner、每個 corner 要多做事（hook）、corner 變多後 PnR 變慢 | multicorner-sta | drv-timing-closure |
| pad／block／pin 規劃核准之後，決定 die 尺寸與使用率、macro 的格點與 halo、placement 密度（`GPL-0052`）；繞線壅塞或繞遠路；`PDN-0179` 窄 row | floorplan-congestion | chip-floorplan-pin-planning（規劃與核准）、hard-macro-integration |
| 開新的頂層設計、決定用哪幾支 pad／GPIO、搬動 block 或 macro，要先規劃並經使用者核准；電源從 wrapper 的哪幾邊進來、IR 的電壓源位置怎麼選（要在定 block 位置前查清楚）；hook 擋下編輯（「這份 pad／block／pin 規劃還沒經使用者核准」）、`make pin-plan` FAIL（`no approval`、`plan_sha256 differs`、`no pnr/<design>/pin_plan.toml`、ADR `has no line with the quote`）；harden 前出 floorplan 圖確認 | chip-floorplan-pin-planning | caravel-user-project-integration（Caravel 的固定腳位）、floorplan-congestion（die 內的密度與壅塞） |
| 把 SRAM／IP macro 接進設計：`MACROS`、各種 view 的來源、每個 PVT 一份 .lib（`LIB`／`EXTRA_LIBS` 不能重複帶進）、沒用到的 port 怎麼 tie-off、macro 的 clock、`DRT-0418 ... has no pins on routing grid`；macro 的 .lib 只有 TT 或只是解析模型 | hard-macro-integration（整合清單） | 清單上連到的各 signoff skill、multicorner-sta、openram-macro-characterization（用 SPICE 模擬量測的 .lib 取代） |
| 選定、自己產生、收到或更換 macro：選定前的 go／no-go；view QA（`check_macro_views` 報 `internal_power ... outside`、`LEF SIZE ... != GDS box`、`signal pins differ from the LEF`、`LEF DATABASE MICRONS 2000 > the tech LEF's 1000`、`LEF has no FOREIGN`、`GDS pin text(s) outside the pin's LEF RECTs`）；OpenROAD 報 `ODB-0292 LEF data from ... is discarded due to errors`；最終 GDS 的 macro 是空的、XOR 差異幾百萬；.lib 輸出的驅動能力；換 macro 後 checker 的比對對象是空的（KeyError `'sram0'`） | macro-qualification（`CLAUDE.md` 規則 12） | hard-macro-integration、openram-macro-generation、lvs-signoff（`check_macro_gds.py`） |
| SRAM macro 的時序與功耗要用 SPICE 量、產生每個 corner 的 .lib；macro 在某些 corner 讀出前一次的值；換上新 .lib 後 repair_design 跑很久；ngspice 讀大 netlist 很慢（`INP2M`）、平行跑時每步慢 10–40 倍、報 `bad v() syntax`、長時間模擬到結尾才報 `no such vector`；量測條件沒涵蓋 SoC 的週期與負載；`gen_char_lib` 報 `internal_power ... outside (0, 1000]`；用 SPICE 量 internal power 時漏電隨 netlist 改變或外插成負值；漏電量測區間 `leakage window ... not settled`、`bitcell leakage depends on gmin`、用 `.nodeset` 算 DC 工作點報 `doAnalyses: out of memory` | openram-macro-characterization | signoff-criteria（量到的數字加多少 margin）、hard-macro-integration（換上新 .lib）、sram-layout-extraction（寄生） |
| 用 OpenRAM 產生 SRAM macro：官方環境只有 x86_64-linux、`use_nix` 時 `could not find a flake.nix file`；OpenRAM 的 LVS 用新 PDK 報 `Netlists do not match`（`special_nfet_01v8`、`special_pfet_latch`）、log 有 `ERROR` 但 exit 0、`Custom cell pin names do not match spice file`、同一設定產生的 GDS 每次不同（`PYTHONHASHSEED`）；OpenRAM 產的 macro 在 KLayout DRC 報 nwell.6、psdm.1、m2.2，或改了 OpenRAM 裡 cell 的 placement 後 LVS 不一致、報 nwell.2a；`Should use a pin iterator`；sky130 1RW 報 `must have an even number of cols including replica cols`；words_per_row 與讀取電路 | openram-macro-generation | macro-qualification（產生後的 view QA）、openram-macro-characterization、drc-signoff |
| 從 GDS 萃取 SRAM 的寄生、萃取 netlist 報 singular matrix 或 `Timestep too small`（階層式輸出的負值修正電容）、Magic exit 0 卻沒有輸出、寄生延遲倍數（萃取 netlist 比 schematic netlist 慢幾倍）怎麼定 | sram-layout-extraction | openram-macro-characterization |
| PDN 產生失敗、IR 步驟 `PSM-0069` 中止或 `PSM-0075 Expected four values on line`、macro 電源怎麼接、IR drop（包括小得不合理）、EM（目前沒有檢查，規則 8）；flow 的 nom_tt IR PASS 但換了設計；想改 PDN（strap 寬度、間距） | pdn-ir-drop（規則 12：在兩個 slow corner 用 CPU max power pattern 檢查，電壓源從真實 pad 起算；規則 13：改 PDN 前先 what-if） | floorplan-congestion（macro 旁的窄 row）、lvs-signoff（實體連接）、signoff-criteria（IR drop 預算） |
| DRC 不為 0、macro 內部的 DRC 怎麼檢查、換了自己產生或改名的 macro 後 KLayout 在 macro 裡報違規、`The layout has multiple top cells in Layout.top_cell`、XOR、金屬密度；latch-up 標記 81/14 與 6 µm 規則（目前沒有任何檢查，規則 7）；浮接金屬檢查開不起來（規則 5） | drc-signoff | openram-macro-generation（規則 6：OpenRAM macro 單獨的 DRC）、macro-qualification（換 macro） |
| antenna 違規、`GRT-0243 Unable to repair antennas on net with diodes`（規則 11：看最終指標）、設了 `DRT_ANTENNA_REPAIR_MARGIN` 卻沒作用（規則 10）、macro 的 LEF 沒有 antenna 資料 | antenna-signoff | drv-timing-closure（長線修復） |
| LVS 失敗、disconnected pin（layout 上沒接到任何線的 pin；wrapper 頂層報幾百個但 0 個 critical：比對剛好是哪幾支，規則 2）、電源 pin 有沒有真的接上；LVS PASS 但不確定 macro 的 layout 有沒有進 GDS | lvs-signoff | pdn-ir-drop、macro-qualification（`check_macro_gds.py`） |
| 合成設定、lint 警告、狀態機被重新編碼（`Recoding FSM`，formal 因此對不上）；`cpu-params` FAIL（包括 config 的 `pdk::` 條件區塊） | rtl-synthesis-lint | formal-equivalence-eqy |
| 證明兩份 netlist 等價、EQY 當機（`returncode=-11`）或證不出來（好 netlist 也有一兩個 partition（EQY 把電路切成的小塊）`Failed to prove`：partition 切在輸入上，把輸入之間的邏輯關係切掉了）、EQY 在切 partition 時停下（`conflicting matches`，例如 OpenROAD 對調了輸入腳位）；EQY 的 PASS 不涵蓋哪些情況（規則 8） | formal-equivalence-eqy | — |
| netlist 模擬、RTL 與 netlist 比對、X、模擬逾時（`wall-clock timeout`）、Icarus `Unable to bind`、PG netlist 的 `dangling input port`、dump 給 IR 用的 VCD 是 0 bytes | gate-level-simulation | flow-regression-reproducibility（機器負載） |
| gate-level 模擬或 formal 的植入錯誤沒被抓到、某個功能從沒被測到 | dv-directed-tests | gate-level-simulation |
| signoff checker（PnR、STA、DRC、來源追溯……）的植入錯誤沒被抓到 | signoff-checker-qualification | 該 checker 所屬主題的 skill |
| 寫或改任何 PASS／FAIL checker（寫完就做獨立漏洞審查）；建立或更新 golden（誤差至少 4 個樣本）；同樣設定重跑結果不同（連 cell 數、diode 數都變）；checker 只證明設定被讀到、靠名稱辨識結構、抓到的機制和宣稱的不同；改完 checker 某一列對每個 run 都 FAIL（變數名稱重複，規則 13）；limits 檔寫死的計數每次改 CTS 就 FAIL（規則 4）；checker 的訊息像結果不對、其實是工具當掉 | signoff-checker-qualification（漏洞類型表；規則 7：檢查是哪個機制抓到的、守門條件本身要有測試） | flow-regression-reproducibility、librelane-run-debug（哪一步不可重現） |
| 一鍵 regression、乾淨 checkout 驗證、查 run 是哪個 commit 與哪版工具產生的、run 要跑很久時繼續開發或等它結束；`No space left on device`、regress 某一項卡住、同時跑幾條被系統中止、清理舊 worktree（規則 13–17）；GDS 的 sha256 每次不同（規則 12）；改了共用 flow 設定（規則 11） | flow-regression-reproducibility | signoff-checker-qualification |
| 把 SoC 的 CPU 換成另一顆 core（例如 Hazard3，AHB5）：wrapper、匯流排 bridge、設定參數、中斷與 reset、上游測試與 ISS 比對、PnR 設定與 limits 檔要不要重做、共用 flow 設定改了每個 CPU 版本都重 harden、IR 重新量測 | core-migration-hazard3 | dv-directed-tests、gate-level-simulation（驗證改法）、hard-macro-integration（SRAM 介面）、drv-timing-closure（時序收斂） |
| 跑 ChipFoundry precheck（`make precheck-caravel`）並判斷 PASS／FAIL（`make precheck-check`）；precheck 的 `klayout_beol` 在 SRAM 裡報 `MR_mcon.CON.10`、`klayout_feol` 報 `MR_licon.SP.6`；`klayout_beol failed (stat=-9)`、LVS extraction 沒完成（VM 記憶體）；LVS log 的 `possible errors ... CVC`；checker 報 `the results directory checked this GDS`（讀到前一次 run 的報表）；Apple Silicon 上沒有 amd64 的 Docker | tapeout-precheck-caravel | drc-signoff（DRC 判讀）、lvs-signoff（SRAM black box）、caravel-user-project-integration |
| 把設計放進 Caravel 的 `user_project_wrapper`、決定用哪幾支 GPIO（先定 block 位置）；`PDN-0239`／`GRT-0036` 警告；`li1.pd.1d` 密度違規；Caravel 的 metal fill 由誰補、`check_density.py` 的密度下限；`wb_clk_i`、vccd1／vssd1 的供電；Caravel 輸入腳位的 max slew 與 IO 路徑的 hold；management SoC 的韌體做 GPIO 設定傳送（`reg_mprj_xfer`）後 user 輸出腳沒訊號、下拉消失，拉 `resetb` 恢復不了；Caravel 的 `wb_rst_i` 怎麼產生（拉起是非同步的） | caravel-user-project-integration（規則 8：GPIO 設定傳送） | chip-floorplan-pin-planning（規劃與核准）、timing-constraints-sdc（IO constraint）、pdn-ir-drop（IR）、tapeout-precheck-caravel |
| 一個 Phase 收尾：證據、延後項目的追蹤、與計畫不同的地方、開結案 regress 前的 positive control、獨立審查、收尾清單與時程 | phase-exit-review | flow-regression-reproducibility（同時跑幾條、磁碟、清理 worktree） |

### 在流程中的位置

每個 skill 在 RTL-to-GDS 流程中的位置（總覽圖）與逐步流程，見 [arvinsa-rtl-gds-flow.md](arvinsa-rtl-gds-flow.md) 第 3、4 節。

### 索引

「適用範圍」說明換到別的設計時哪些內容可以直接用：「通用」是不限工具的方法；「LibreLane／OpenROAD」是同一套開源流程都適用；「sky130」是這個 PDK 的數值、規則名稱或 cell 名稱。經驗多寡看各 `SKILL.md` 的經驗紀錄表。

| skill | 一句話 | 適用範圍 |
|---|---|---|
| [middle-end-flow](.claude/skills/middle-end-flow/SKILL.md) | Middle-end 的入口：情況與錯誤訊息對照到細部 skill | 本 repo 的分段 |
| [backend-flow](.claude/skills/backend-flow/SKILL.md) | Backend 的入口：情況與錯誤訊息對照到細部 skill | 本 repo 的分段 |
| [package-flow](.claude/skills/package-flow/SKILL.md) | Package 的入口：情況與錯誤訊息對照到細部 skill | 本 repo 的分段 |
| [librelane-run-debug](.claude/skills/librelane-run-debug/SKILL.md) | 跑 LibreLane、接續、只重跑某個 step，查失敗、卡住或停不下來的 step；升版時要重看的綁定 | LibreLane 3 |
| [signoff-checker-qualification](.claude/skills/signoff-checker-qualification/SKILL.md) | checker 與 golden 的設計，用植入錯誤證明 checker 抓得到 | 通用 |
| [drv-timing-closure](.claude/skills/drv-timing-closure/SKILL.md) | 多 corner 的 setup／hold 與 slew／cap／fanout 收斂 | LibreLane／OpenROAD；cell 名稱是 sky130 |
| [hard-macro-integration](.claude/skills/hard-macro-integration/SKILL.md) | SRAM 等 hard macro 接進 flow 的整合清單 | LibreLane；SRAM 細節是 sky130 |
| [macro-qualification](.claude/skills/macro-qualification/SKILL.md) | macro 交給 flow 之前的檢查：選定前的 go／no-go、view QA、.lib 驅動能力、換 macro 的檢查清單 | 方法通用；checker 是 LibreLane／sky130 |
| [openram-macro-characterization](.claude/skills/openram-macro-characterization/SKILL.md) | 用 SPICE 模擬量測 SRAM macro 的時序與功耗、產生每個 corner 的 .lib | 方法通用；ngspice 的細節是 sky130 |
| [openram-macro-generation](.claude/skills/openram-macro-generation/SKILL.md) | 用 OpenRAM 產生 SRAM macro：固定版本的 PDK、patch、DRC／LVS 結果怎麼判斷、可重現 | OpenRAM＋sky130 |
| [sram-layout-extraction](.claude/skills/sram-layout-extraction/SKILL.md) | 從 GDS 萃取 SRAM 寄生、模擬萃取 netlist、寄生延遲倍數 | Magic＋ngspice；細節是 sky130 |
| [drc-signoff](.claude/skills/drc-signoff/SKILL.md) | DRC、GDS 輸出、XOR、macro 內部 DRC、金屬密度、latch-up 標記 | 多為 sky130；位置比對方法通用 |
| [formal-equivalence-eqy](.claude/skills/formal-equivalence-eqy/SKILL.md) | EQY 等價證明、它會默默略過的情況與解法 | Yosys／EQY |
| [antenna-signoff](.claude/skills/antenna-signoff/SKILL.md) | antenna 檢查與修復，macro 沒有 antenna 資料時的處理 | OpenROAD；數值是 sky130 |
| [cts-clock-tree](.claude/skills/cts-clock-tree/SKILL.md) | clock tree、clock pin、macro 的 clock latency、clock 造成的 setup／hold | OpenROAD／LibreLane |
| [pdn-ir-drop](.claude/skills/pdn-ir-drop/SKILL.md) | 電源網路、IR drop（slow corner＋max power pattern）、電壓源位置；EM 目前沒有檢查 | OpenROAD／LibreLane |
| [lvs-signoff](.claude/skills/lvs-signoff/SKILL.md) | LVS、macro black box、實體連接、disconnected pin | LibreLane（Magic、Netgen） |
| [gate-level-simulation](.claude/skills/gate-level-simulation/SKILL.md) | netlist 模擬、RTL 與 netlist lockstep、X、PG netlist、時限 | Icarus＋sky130 模型；lockstep 方法通用 |
| [floorplan-congestion](.claude/skills/floorplan-congestion/SKILL.md) | die 尺寸、macro 位置、IO pin、placement 密度、壅塞與繞路 | OpenROAD；格點是 sky130 |
| [timing-constraints-sdc](.claude/skills/timing-constraints-sdc/SKILL.md) | SDC timing constraint、PnR 與 signoff constraint 分開、未受 constraint 路徑 | OpenSTA／LibreLane |
| [signoff-criteria](.claude/skills/signoff-criteria/SKILL.md) | signoff 條件的數值怎麼推導，工具沒分析的項目怎麼補；每次 harden 後檢查 criteria 有沒有被執行、合不合理 | 推導與檢查方法通用；製程知識依製程分類（目前 sky130＋LibreLane） |
| [rtl-synthesis-lint](.claude/skills/rtl-synthesis-lint/SKILL.md) | Yosys 合成設定、狀態機重新編碼、lint、latch | Yosys／LibreLane |
| [flow-regression-reproducibility](.claude/skills/flow-regression-reproducibility/SKILL.md) | 一鍵 regression、乾淨 checkout、來源追溯、長時間的 run 還在跑時怎麼開發、機器資源（記憶體、磁碟、逾時、清理） | 方法通用；實作是 LibreLane／Nix |
| [multicorner-sta](.claude/skills/multicorner-sta/SKILL.md) | 增減 corner、每個 corner 的 hook、只重跑 STA 的 what-if、最小週期 | LibreLane／OpenSTA |
| [dv-directed-tests](.claude/skills/dv-directed-tests/SKILL.md) | 從漏掉的植入錯誤找缺口，寫 directed 測試補上並證明有效 | 通用；例子是 RISC-V firmware |
| [phase-exit-review](.claude/skills/phase-exit-review/SKILL.md) | Phase 收尾：證據、延後項目、限制、獨立審查、使用者決定、skill 回寫、收尾時程 | 通用 |
| [core-migration-hazard3](.claude/skills/core-migration-hazard3/SKILL.md) | 換 CPU core（例子是 PicoRV32 換成 Hazard3，AHB5）：介面、參數、中斷與 reset、驗證資產、PnR 重新驗證 | Hazard3 細節；換 core 的檢查方法通用 |
| [tapeout-precheck-caravel](.claude/skills/tapeout-precheck-caravel/SKILL.md) | 跑 ChipFoundry precheck 並判斷 PASS／FAIL，precheck 與 flow 的工具和 deck 差異 | ChipFoundry Caravel、sky130 |
| [caravel-user-project-integration](.claude/skills/caravel-user-project-integration/SKILL.md) | 放進 Caravel `user_project_wrapper`：GPIO（含韌體的 GPIO 設定傳送）、`wb_clk_i`、供電、li1 密度、fill 與密度下限、IO constraint、下線規定對照表 | ChipFoundry Caravel、sky130 |
| [chip-floorplan-pin-planning](.claude/skills/chip-floorplan-pin-planning/SKILL.md) | 晶片層級的 pad、block 位置、pin 指定先規劃並經使用者核准，再寫 RTL 與 harden；規劃文件、出圖檢查點、checker 與 hook | 方法通用；checker 目前只實作 pad 固定的 wrapper（Caravel） |

### 各 skill 說明

#### middle-end-flow：Middle-end 的入口

- **何時用**：工作在 RTL 寫好之後、交給 PnR 之前：合成與 lint、RTL 驗證與 directed 測試、換 core、寫 SDC、EQY、hard macro 的 view QA 與 go／no-go、用 OpenRAM 產生 SRAM、SRAM 的 SPICE characterization 與 layout 萃取。
- **重點**：只是索引。依「情況／錯誤訊息」表找到細部 skill 的 `SKILL.md` 再讀。細部 skill 在清單只列名稱，要從這裡進去。
- **本 repo 實例**：流程文件 4.2、4.3、4.5 的 SDC、4.7 的等價證明。

#### backend-flow：Backend 的入口

- **何時用**：用 LibreLane harden 與每次 harden 之後：floorplan 與壅塞、macro 接進設計、PDN／IR、CTS、時序與 DRV 收斂、多 corner STA、antenna、DRC／XOR、LVS、gate-level 模擬、criteria review 與 signoff 上限、跑 LibreLane 與除錯。
- **重點**：只是索引。每次 harden 跑完先讀 `signoff-criteria`（`CLAUDE.md` 規則 9）。
- **本 repo 實例**：流程文件 4.4、4.5 的 signoff 條件、4.6、4.7 的 netlist 模擬。

#### package-flow：Package 的入口

- **何時用**：晶片層級與下線：pad（含電源進入點）、block 位置、pin 的規劃與核准（`CLAUDE.md` 規則 14）、放進 Caravel wrapper、跑 ChipFoundry precheck 並判斷 PASS／FAIL。
- **重點**：只是索引。順序是 pad → block 位置 → pin → RTL → harden。
- **本 repo 實例**：流程文件 4.1 的下線規定對照表與規劃、4.6 的 wrapper 相關檢查、4.7 的 precheck。

#### librelane-run-debug：LibreLane 執行與除錯

- **何時用**：跑 LibreLane、從中間 step 接續、只重跑一個 step（驗證設定或做 negative test）、run 失敗找原因、某一步很久不結束、記憶體一直漲、錯誤時有時無、`RSZ-0074 failed to build tree from gloubal routes`、重跑時保留上一次的 run、要改某一步的工具指令而不改 LibreLane 本身、LibreLane／OpenROAD 升版。
- **重點**：
  - 只重跑某個 step 用 `python3 -m librelane.steps run`，改的是 config 與 state 的複本，原 run 不動。
  - 要改某一步的行為：寫一個繼承原 step 的 plugin step、只換 Tcl，config 用 `meta.substituting_steps` 換掉；手動跑完整 flow 時 `PYTHONPATH` 要含 plugin 的目錄，否則一開始就報 `no replacement step with ID`（ADR-0016）。
  - 錯誤要先證明是隨機的（同一份輸入重跑 3–4 次，有過有不過），才能加重試；重試只針對已證明隨機的訊息，而且有次數上限（規則 5）。本 repo 認兩種：`GRT-0229`，以及總 overflow ≤ 10 的 `GRT-0116`；都只在 `RepairDesignPostGRT`、`ResizerTimingPostGRT` 中止時從那一步接續，最多重試 2 次。只跑一次就把錯誤歸因到某個設定不可靠：`GRT-0229` 原本被誤認為是某個設定造成的。重試規則綁 step 名稱，flow 多開一個做同樣工具指令的 step（例如繞線後的 timing 修復也做 global routing）時要一起檢查。接續後的 run 用 golden 的誤差比對，不保證逐項相同。
  - 判斷是不是卡住：log 有緩衝，要看 CPU 時間、記憶體與 call stack（`sample`）。記憶體要看 physical footprint，`ps` 的 RSS 不算被換到 swap 的部分，會嚴重低估；CPU 使用率低、swap 一直增加，就是記憶體用量一直漲、停不下來，要馬上停（Phase 5 一個 step 用到 92.9 GB，機器只有 24 GB）。
  - 規則 7，某一步停不下來（出現 4 次）：和同設計上次的同一步比時間（`runtime.txt`），看 physical footprint，超過好幾倍就用 process group 停掉、保留 run、只重跑那一步，一次只換一個輸入。正式 harden 沒有時間或記憶體上限，目前沒有自動停止（ADR-0021 決定 3，留到下一個專案）。判斷太久以同設計上一次為準，本設計實際跑出來的時間在 `pnr/*/README.md`。
  - 要在某一步的工具指令裡加除錯輸出時，用 `python3 -m librelane.steps eject` 把那一步匯出成獨立 script 再改；可能停不下來的實驗要加記憶體上限，超過就自動停。
  - 重跑會覆蓋同名的 run：Phase 3.5 第 1 次 harden 的 log 就因此不見。Phase 5 起 `run.sh` 把上一次的 run 搬成 `<dir>.prev`（只留一層），要保存更多次就自己改名；改名後各步的 `state_in.json` 仍指向舊路徑，只重跑某個 step 之前要在複本裡換掉。
  - 從中間接續（`--from`）時，LibreLane 讀的是 run 目錄裡修改時間最新的 `state_out.json`，不是前一步的。失敗後立刻接續沒問題；run 已跑過那一步、想改設定從中間重來時，要用新的 run tag 加 `--with-initial-state <前一步>/state_out.json`，否則那一步拿到的是最後一步的成品（Phase 7：`RepairDesignPostGRT` 拿到已填 fill 的 layout，報 `EST-0026` 後中止於 `RSZ-0074`）。
  - 常見陷阱：重跑的 step 目錄多 `-1` 字尾、從中間接續後之後每一步的編號都多 1（checker 不要寫死 step 編號），而且中止那次的目錄還在（checker 只採計有 `state_out.json` 的目錄）、ODB 會快取 LEF、STA hook 只在 STA 生效、console 輸出會自動換行。
  - metrics 的彙總值：DRV 計數是各 corner 的最大值；`power__total` 是最後寫入的 corner，不是 nom_tt。state 的 metrics 會沿用前面步驟的值，flow 中途 `state_out.json` 的數字不一定是那一步量的，要看該步的 `or_metrics_out.json`。log 的 `RSZ-0032 Inserted N hold buffers` 不是總數，要數 netlist。
  - what-if：改 config 複本後只重跑那一個 step（例如 `IRDropReport` 換 corner 與電阻、`GeneratePDN` 換 Tcl 重新產生 PDN），先用現行設定確認結果與原 run 相同（Phase 5）。GRT-0229 接續後的結果不一定逐項相同。同一步還有另一種隨機中止 `GRT-0116`（overflow 只有個位數），重試只在總 overflow ≤ 10 時接手。
  - `RSZ-0074 failed to build tree from gloubal routes` 有三種原因，看訊息尾巴與情境分辨（「三種原因」表）：`expected 0` 是頂層 inout 訊號腳位（Caravel 的 `analog_io`）被同時算成 driver 和 load，用 `RSZ_DONT_TOUCH_RX` 設成 dont_touch，`check_inputs.py inout_dont_touch` 在 harden 前檢查（P79）；前面有 `EST-0026` 的是同一個 tag 加 `--from` 讀到最後一步的成品；自己寫的繞線後 ECO 在這版 OpenROAD 做不到。
  - 「升版時要重看的綁定」一節：列出目前綁在 step 名稱、step 編號、log 措辭上的對策（重試的比對式、`review_criteria.py` 的 `TIMING_STEPS`、`check_soc.py` 的 step 目錄、P55、EQY 與 OpenRAM 的 log 措辭……），LibreLane、OpenROAD、EQY、OpenRAM 升版時逐列確認。`TIMING_STEPS` 清單外新增的時序 step 會被默默略過，目前沒有自動檢查。
- **不在這裡**：設定值該設多少、PASS 條件怎麼定，看各主題的 skill。
- **本 repo 實例**：`pnr/*/run.sh`、`pnr/librelane_flow.sh`（`GRT-0229`、`GRT-0116` 的重試，negative test `make test-flow-retry`，情境清單在 `pnr/test_librelane_flow.sh`）、`pnr/soc_top/neg_pnr.py` 的 `rerun()`。

#### signoff-checker-qualification：checker、golden 與植入錯誤

- **名詞**：checker 是判 PASS／FAIL 的程式或規則；golden 是確認過正確的一次 run 的完整 metrics，之後每次逐項比對；negative test（bug injection）是故意植入錯誤，確認 checker 真的 FAIL。
- **何時用**：新寫或修改任何 checker（signoff metrics、DV、EQY、自己寫的腳本）；建立或更新 golden；決定 golden 比對哪些 metric 可以有誤差；同樣設定重跑結果不同；設計植入錯誤的案例。
- **重點**：
  - 只認明確 PASS：缺一個 metric、表格被截斷、工具沒跑完都是 FAIL。型別要嚴格：`false` 不是 0；slack 是 1e30 代表沒有 constraint 的路徑。
  - golden 的誤差依「這個數字是哪一步產生的」分類，不要等出過差異才給。不可重現那一步（多執行緒 detailed routing）之後算出來的數字分三類：隨繞線微小變動的連續量（slack、skew、線長、via、功耗、IR）給很小的誤差；繞線器中間各輪的 DRC 數這類中間過程數字給大誤差（等於不比數值）；計數、面積、最終 DRC、LVS 一律完全相同。
  - 不可重現的步驟也會改變數量時（Phase 5 Hazard3：global routing 偶發不同、detailed routing 多插 diode）：先找到分歧的那一步、量出發生頻率，收集足夠樣本，再把會跟著繞線變的數量與面積放進另一個誤差表（約實際量到的最大差異的 5 倍），每輪與個別 warning 的 key 列為可選。違規、錯誤類的計數仍一律完全相同，由 checker 拒絕任何碰到它們的誤差設定（ADR-0015）。
  - 規則 4，「不是 0」的計數（unannotated、disconnected pin）逐項分類，會隨 layout 變的類別（CTS dummy load）不寫死總數：寫死總數已讓 harden 在設計沒問題時 FAIL 4 次。目前 `check_signoff.py` 仍比總數，沒有自動檢查，下一個專案改成逐項分類的 checker。
  - 每個 checker 至少要有一個植入錯誤，加一個沒植入時必須 PASS 的對照。檢查要寫成「FAIL 的列剛好是這幾列」，而且要看全部問題，不能只看第一個。
  - 每個植入錯誤必須在**預期的** checker、以預期的原因 FAIL，FAIL 的位置要和植入點有關。修 checker 漏洞時，要證明舊 checker 會漏、新的會抓。
  - 附一張已知 checker 漏洞類型表，例如工具靜默略過、檢查範圍比名稱小、植入沒生效、只看有沒有不看大小或位置、產生器的公式沒有獨立驗證、檢查分不出 FAIL 的原因、checker 綁死 step 名稱（flow 換掉或多開 step 就失效，也沒有警告）、重試留下的中止目錄頂替完成的那次。新 checker 要逐條對照。
  - Phase 5 獨立審查的 9 種新漏洞類型：只證明設定被讀到、沒證明生效；靠名稱辨識工具產生的結構；誤差表的保護字與萬用字元；強制機制的觸發條件比規則小；抓到的機制和宣稱的不同；守門條件本身沒測試；只看版本字串；暫用另一個設計的誤差；比對到資料而不是指令。規則 7 補兩條：檢查是哪個機制抓到的、每道守門條件都要有「拿掉就 FAIL」的情境。
  - Phase 6 獨立審查的 5 種新漏洞類型：black box 看不到的一致性沒有別處在比（LEF 腳位 RECT 對調，LVS 照樣 PASS）；指紋不精確卻自稱內容相同；只讀表格的第一個數字；把工具的特例清單抄一份寫死；產生鏈的中間檔沒有來源追溯。另外 `abs(x - y) > tol` 對 NaN 永遠不成立，要寫成 `not abs(x - y) <= tol`。
  - Phase 7 獨立審查的 7 種新漏洞類型：核准紀錄只存在被檢查的檔案裡、自己算得出來；checker 只看結果、不核對輸入的產生條件與來源；例外欄位接受任何字串；時間比較丟掉時區；非正式的結果（不列入 signoff 證據）被當成正式結果；向量只檢查一個 bit；例外只放寬、不要求被例外的東西存在。`max()` 遇到 NaN 也會略過它。規則 13：改 checker 時新變數（包括迴圈變數）不能和同一個 scope（函式內或模組層）既有的名稱重複，已出現三次（Phase 6 `files`、Phase 7 `defines` 讓 `resolved` 列對每個 run FAIL；Phase 7 `cbf2c5e` 的迴圈變數蓋掉 SRAM 原點）；`make py-check` 看不出變數撞名，目前靠 P00 這類「在實際的 run 上必須 PASS」的 positive control，沒有自動檢查。
  - Phase 6 結案 regress 抓到的一類：checker 的某個模式（`check_inputs.py --resolved`）只有植入錯誤的案例在跑，checker 改壞成永遠 FAIL 時這些案例照樣「抓到」。每個模式都要有沒植入時必須 PASS 的對照（neg-pnr P00）。
  - 2026-10-15 問題總檢討加進漏洞類型表的三類：RTL testbench 的測試被縮水或跳過仍 PASS（要計數比對每支測試宣告的動作）；只比最終結果，中間的介面錯誤互相掩蓋（要腳位層的協定 monitor）；checker 的訊息分不出工具當掉與結果不對（先掃 log 的 `Signal number`、`Segmentation fault`、`Killed`）。三類都還沒有自動檢查。
  - 提早檢查（流程回顧，ADR-0020，使用者決定，效益為推算）：規則 11，golden 的誤差每個設計至少用 4 個同設定的樣本（含一次乾淨 checkout）定，記下樣本數，不暫用別的設計的誤差；規則 12，新 checker 寫完就請沒寫它的 agent 做漏洞審查，不等 Phase 收尾（Phase 4–7 每次收尾都找到 7–12 個漏洞，修完整套 regression 重跑）。
- **本 repo 實例**：`signoff/scripts/check_signoff.py`、`signoff/limits/`、`signoff/golden/*/README.md`、`pnr/soc_top/check_soc.py`、各 `neg_*.py`。

#### drv-timing-closure：時序與 DRV 收斂

- **名詞**：DRV（design rule violation，電性限制的違規）指 max slew（訊號轉換太慢）、max cap（負載電容太大）、max fanout（一條線接太多負載）。
- **何時用**：多 corner STA 有 setup／hold 違規或 DRV 違規；要調 resizer、長線修復、cell 排除、繞線前的寄生估計；resizer 跑很久停不下來。
- **重點**：
  - LibreLane 對 sky130 預設只在 tt 判 setup FAIL，slew／cap 不檢查；先把四個 `*_VIOLATION_CORNERS` 都設 `["*"]`。repo 的 `check_signoff.py [corners]` 不靠這個預設，逐 corner 檢查。
  - DRV 收斂清單，依實際有效的順序：排除延遲 cell（`clkdlybuf4s*`）、設 `LAYERS_RC`（LibreLane 3.0.14 把 sky130 的表註解掉了，沒設時繞線前電容估一半）、開 post-GRT 修復、設最大線長（超過就切開插 buffer）；剩下少數違規先查是不是繞路。前兩項漏設時沒有 checker 直接檢查（drive 太弱的 cell 檢查抓不到延遲 cell；`LAYERS_RC` 只有 `ir_worst.py` 間接擋），下一個專案做成 `check_inputs.py` 的列。
  - resizer 只看 `RSZ_CORNERS`，新設計預設等於全部 signoff corner（規則 8、15）。它看不到的 corner 不能只靠 PnR 的 margin 補（規則 9）：corner 之間的延遲差和路徑長度成比例，Hazard3 一條長路徑在 ss_100C 有 +1.48 ns，signoff 在 ss_n40C 卻是 −4.16 ns；調大 setup margin 還會擋住 hold 修復。soc_top 與 wrapper 現在讓 resizer 也看 ss_n40C（ADR-0013），Phase 4 的補償記在放寬清單 T12、T15。換 CPU 或改週期後，繞線前就要量一次只給 signoff 看的 corner。
  - resizer 停不下來、記憶體一直漲：OpenROAD 的 `repair_design` 修 driver 的 slew 時，可能把它換成更弱的尺寸（Phase 5：`a2111oi_2` 被換成 `a2111oi_1`）；換完若弱到連一顆最小 buffer 的輸入電容都推不動，長線修復會在同一位置無限插 buffer（Phase 5 只重跑那一步確認）。PDK 的 `no_synth.cells` 只擋合成，resizer 照樣會用裡面的弱 `_1`。slew margin 越大、resizer 的 corner 越慢，會出事的 cell 越多。用除錯輸出找出那條 net；本 repo 把 `a2111oi_1` 加進 `EXTRA_EXCLUDED_CELLS`（ADR-0012），並在 harden 前用 .lib 查表檢查 resizer 可用的每個 cell（`pnr/check_weak_cells.py`）。macro 的 .lib 也曾讓這一步停不下來，換上新的先只重跑那一步確認時間。
  - 修哪個 corner 的違規，就用那個 corner 的資料判斷修正方式的影響。工具不一定做到：OpenROAD resizer 在 ss 100°C 抓到違規，卻用第一個讀進來的 tt .lib 挑尺寸（只改讀取順序，挑的尺寸就不同）。所以修完要在違規的 corner 確認被改的 cell 真的變好；換工具、升版或改 corner 設定時，用「只改 library 讀取順序或預設 corner」的對照實驗確認工具有沒有看對 corner。這條寫成規則而不只寫在腳本，是為了換工具或流程時也會重新驗證。流程設定也會讓工具看不到違規的 corner：用另一個 corner 加 margin 代替，就是沒有用違規那個 corner 的資料。
  - signoff 只有少數內部 net 的 slew 略超上限、post-GRT 修復結束時卻已是 0：slew 修復與 setup 修復修完都會重新 global routing，修的當下是直線的 net 可能被擠去繞路，之後沒有步驟再檢查 slew（Phase 7 已驗證）。在 global routing 後多插修復步驟或加迴圈都試過、無效；降 placement 目標密度解掉局部熱點（Phase 7 wrapper 55% → 50%，ADR-0019 決定 21）。繞線後 ECO 在固定版本的 OpenROAD 做不到（`detailed_routing` 寄生來源還沒實作）。
  - macro 的 .lib 要每個 PVT 一份，resizer 才看得到 macro 在 slow corner 的延遲；只靠 STA hook 加 derate 時，PnR 看不到。OpenRAM SRAM 的 .lib 要有 dout 在上升緣後開始變化的 timing arc，STA 才會檢查 capture flop 的 hold。
  - CTS 後修完 setup，signoff 卻在長路徑違規：先量「修完 → 繞線前 → signoff」差距落在哪一段。繞線後才出現的，開 `RUN_POST_GRT_RESIZER_TIMING`，讓 resizer 用 global routing 估計的寄生再修一次（Phase 5 Hazard3：−1.131 → +0.530 ns，只換尺寸與拿掉 buffer）。不要調大 CTS 後的 setup margin（會擋住 hold 修復），也不要靠加週期（run 之間差約 1 ns）。
  - 放寬 signoff 上限之前先找出原因；真的要放寬，由使用者決定並寫 ADR。
  - detailed routing 之後才出現的違規，Classic flow 沒有修復步驟。
  - 附「試過但沒採用的做法」表，避免再試沒用的設定。
  - hold 修復：OpenROAD 整顆晶片只用一種 hold buffer（sky130 是 `dlygate4sd3_1`，slow corner 約是 fast corner 的 3 倍），換小 cell 會插好幾倍、碰上限 `RSZ-0060`。hold delay cell 卡在 setup 吃緊的路徑時，先從 clock 端找原因（cts-clock-tree）。繞線後的估計不一定比 signoff 悲觀（Hazard3 保守、PicoRV32 半週期路徑樂觀），開了 post-GRT 修復仍要用 criteria review 確認差距沒有變號。
  - 規則 16，hold 修復的 log 怎麼讀：`RSZ-0064 Unable to repair all hold checks` 只表示沒修到 hold margin，不等於有違規；進度表 WNS 幾千列不動不等於卡住（一輪內最差的先處理）；`RSZ-0032` 與 metric 的 hold buffer 數不是總數（journal 復原時歸零），要數 netlist 的 `hold<N>`。PASS／FAIL 一律看 signoff STA，不要因此調大 margin 或加 `-max_iterations`。
  - 提早檢查（流程回顧，ADR-0020）：規則 14，第一次 harden 前做 library 與工具預設值的 QA：重跑參考設計時每個 DRV 違規都要查出原因（Phase 0 的 74 個 slew 違規只列出、沒有逐一查，Phase 2 試跑 9 次才找到原因），drive 太弱的 cell 查表涵蓋所有 signoff corner（`check_weak_cells.py` 目前只查 resizer 的 corner）；規則 15，resizer 看的 corner 預設等於 signoff corner，跑不完時先找原因，要拿掉要有 what-if 與 ADR（Phase 4 減少 corner，Phase 5 在 ss −40°C 差 −4.158 ns）。兩條的自動檢查留到下一個專案。
- **不在這裡**：SDC 寫法看 timing-constraints-sdc；corner 設定看 multicorner-sta；clock tree 看 cts-clock-tree；數值怎麼定看 signoff-criteria。
- **本 repo 實例**：`pnr/picorv32_core/README.md`、`pnr/soc_top/README.md` 的設定表、ADR-0009、ADR-0010、ADR-0012、ADR-0013、ADR-0014、`pnr/check_weak_cells.py`、`docs/notes/repair_design_loop.md`。negative test：P01–P04、P32、P40–P42。

#### hard-macro-integration：hard macro 接進 flow

- **何時用**：把 SRAM、IP 這類已完成 layout 的區塊接進設計，或換一顆 macro 後接回 flow；macro 的 .lib 只有 TT、或只是解析模型（沒做 SPICE characterization）。選定前的檢查與 view QA 看 macro-qualification（2026-10-15 拆出，ADR-0021 決定 5）。
- **重點**：
  - 每種 view 的來源：GDS、補上 antenna 資料與 `FOREIGN` 的 LEF、每個 PVT 一份的 .lib（SPICE 模擬量測，Phase 3.5 起）、合成用的 blackbox、修正過的模擬模型。每個產生出來的檔都要能檢查是否過期。
  - .lib 少給一個 corner 時，那個 corner 會把 macro 當 black box，而且沒有任何錯誤訊息。所以 .lib 要每個 PVT 一份（用 SPICE 模擬量測產生，看 openram-macro-characterization）；只有廠商的單一 TT 解析 .lib 時，暫時用一份保守的 padded .lib 給全部 corner，再用 STA hook 對 macro 加 derate（multicorner-sta）。STA 的每個 corner 只能讀到一份 macro .lib：`LIB`、`EXTRA_LIBS` 也會被讀進每個 corner。
  - macro 的行為模型不能放進合成的檔案清單，合成用 blackbox；`VDD_NETS`／`GND_NETS` 要和 macro 的電源 pin 同名。
  - 沒用到的 port 要 tie-off，checker 要檢查實際接的值。例外：OpenRAM SRAM 沒用到的 port，時脈不能接固定值（chip-select 由時脈取樣、沒有 reset），要接系統時脈、`csb` 接 1；checker 沿 buffer 往回追到時脈 port（`check_soc.py port1_tieoff`，P65）。
  - macro 在每個 STA corner 都要先證明功能正確（選定前就要做，macro-qualification 規則 2；這裡是在交付的 netlist 上重跑）。不能動的 corner 仍要給一份標明 PLACEHOLDER 的 .lib（否則被當 black box），並列為下線風險。
  - macro 的 clock：CTS 預設會在 macro clock pin 前插 delay buffer 對齊 flip-flop 的 latency，對 SRAM 半週期讀出反而有害；soc_top 關掉了（ADR-0016，看 cts-clock-tree）。
  - 整合清單逐項連到各 signoff skill（時序、antenna、DRC、LVS、模擬、EQY）。
- **本 repo 實例**：`pnr/soc_top/config.json`、`ip/sram/`、`pnr/soc_top/check_inputs.py`、ADR-0006／0007／0008／0010／0016／0018。negative test：P08、P09、P14、P16–P20、P30、P32、P64（案例表在 `pnr/soc_top/neg_pnr.py`）。

#### macro-qualification：macro 交給 flow 之前的檢查

- **何時用**：選定、自己產生、收到或更換 macro（OpenRAM 產生的、廠商 IP、先前 harden 的區塊都一樣，`CLAUDE.md` 規則 12）；`check_macro_views` FAIL、OpenROAD 報 `ODB-0292`、最終 GDS 的 macro 是空的。2026-10-15 從 hard-macro-integration 拆出。
- **重點**：
  - 規則 1，view QA：LEF、.lib、Verilog、SPICE 的名稱、腳位與方向一致，.lib 的數字在合理範圍、面積等於 LEF 尺寸，LEF 尺寸等於 GDS 外框，LEF 的資料庫單位不比 tech LEF 細，每支腳位的 GDS 文字落在同層的 LEF RECT 裡、繞線金屬在 LEF 的 OBS 與腳位內。產生工具自己的 DRC、LVS 不看這些：OpenRAM dev 的 .lib power 錯了 10 個數量級仍然 DRC／LVS 全過；它的 LEF 寫 `DATABASE MICRONS 2000`，OpenROAD 會整份丟掉（`ODB-0292`）；它的 LEF 沒有 `FOREIGN`，LibreLane 的 KLayout 輸出會留下空的 macro，也沒有任何錯誤訊息（只有 XOR 抓到），harden 後要比對最終 GDS 的 macro 和 macro 自己的 GDS（`check_soc.py macro_gds`）。
  - 提早檢查（流程回顧，ADR-0020）：規則 2，選定 macro 之前做 go／no-go，在晶片所有的操作條件（STA corner、corner 之間的溫度、最低供電）下做 SPICE 讀寫，並用下線服務商的 DRC deck 單獨檢查；規則 3，.lib 輸出的等效驅動電阻要落在標準元件的範圍內；規則 4，換 macro 時舊檢查逐條重跑、每支 checker 證明比對對象不是空的（`FOREIGN`、EQY 只認 `sky130_` 的教訓）。規則 3、4 的自動檢查留到下一個專案。
- **本 repo 實例**：`scripts/check_macro_views.py`（`make macro-views`；植入錯誤 `make neg-macro-views`，案例表在 `scripts/neg_macro_views.py`）、`scripts/check_macro_gds.py`、`pnr/soc_top/check_inputs.py`（`macro_views`、`macro_source`、`lib_template`）、ADR-0010、ADR-0018。negative test：P63、P66–P69、P71–P76。

#### openram-macro-characterization：SRAM macro 的 SPICE characterization

- **名詞**：characterization 是用電路模擬量出 macro 的延遲、setup/hold、最小週期，寫成 STA 讀的 .lib；解析模型是 OpenRAM 不跑模擬、用公式估出來的 .lib。
- **何時用**：macro 的 .lib 只是解析模型或只有一個 corner，要用 SPICE 模擬量測取代；要產生每個 PVT 的 .lib 或量功耗與漏電；macro 在某些 corner 讀出前一次的值；ngspice 讀大 netlist 很慢、輸出 bus 節點時報 `bad v() syntax`、長時間模擬到結尾才報 `no such vector`。用 OpenRAM 產生 macro 看 openram-macro-generation，layout 萃取看 sram-layout-extraction（2026-10-15 拆出，ADR-0021 決定 5）。
- **重點**：
  - 先判斷廠商 .lib 是不是解析模型：延遲表每一列相同、最小週期是延遲乘固定倍數。sky130 PDK 附的 SRAM .lib 全部是這種。
  - 量 macro 隨附的 netlist（和 GDS 同一顆電路），不要用重新產生的電路代替。
  - OpenRAM 自己的 SPICE characterization 有缺陷：setup/hold 只量輸入端那顆 DFF、只量第一個 corner、rise 抄 fall、pulse width 取週期一半、預設不含萃取的寄生 RC。
  - 2 KB 完整 netlist 在 ngspice 光讀檔就超過 35 分鐘，要縮減成只留第一／最後一列與行，並和完整 netlist 比對一次；模擬步長也要用小步長驗證。完整 netlist 每個 ngspice 約 4.2 GB，平行跑超過實體記憶體時每個時間點慢 10–40 倍、看起來像卡住；deck 用 `save` 只存要寫出的向量。
  - ngspice 的陷阱：bus 節點名稱、`meas ... FALL=1` 從 t=0 起算、要量測的節點名稱錯時到模擬結束才報 `no such vector`（長時間模擬前先用同一份 deck 跑 1 ns）。
  - OpenRAM SRAM 的 dout 在上升緣後約 1 ns 就開始變化，廠商 .lib 沒有這條 timing arc，STA 不會檢查 capture 端的 hold；新 .lib 要加上，接進 SoC 後要有 negative test 證明 STA 真的用到它。
  - setup/hold 要在整顆 macro 上量：內部 clock buffer 讓 setup 變負、hold 變大，只量 DFF 的 hold 少算約 0.3 ns。
  - 每個 PVT 先證明讀寫正確再量時序：PDK 的 sky130 SRAM 在低溫與 ss 1.60 V 室溫會讀成前一次的值（sense amp 沒有預充電、column mux 只有 NMOS）；不能動的 PVT 給 STA 一份 placeholder .lib。
  - 量測的週期、輸出負載與 input slew 要涵蓋 SoC 實際的工作點，.lib 的 `min_capacitance`／`max_capacitance` 設成 characterization 量過的範圍，否則 STA 外插、不警告（規則 30，出現兩次）。
  - 量測方法先驗證誤差（方向要對 .lib 實際用的那個量判斷），再用植入錯誤證明腳本量得對；植入的字串要先確認找得到、改到預期的次數。
  - .lib 延遲表裡延遲對負載電容的斜率（等效驅動電阻）會被 OpenROAD 當成 driver 強度，照實寫進表裡等於 60–140 kΩ 的 driver，`repair_design` 會一直插 buffer；每列取負載中的最大延遲（hold arc 取最小），產生後先只重跑 repair 那一步確認時間正常。
  - 其他 PVT 的結果常在以 tt 為中心的搜尋範圍外：往外一次多測幾點再接著二分，不要整個重新二分。
  - 產生 .lib 的程式本身也要有 checker：另寫一支不 import 它的程式從量測 JSON 重算每個數字；在 .lib 採用的值上做確認模擬；檢查量測 JSON 的來源與數值、模擬快取是否完整。
  - 量功耗與漏電：沒用到的 port 從不 precharge，sense amp 浮接、上下同時導通，漏電隨 netlist 與動作改變，不能外插；.lib 漏電要在所有 port precharge、時脈停在高電位的待機狀態量，讀寫能量扣局部基準。ngspice 的 gmin 會蓋過 bitcell 漏電，單顆 bitcell deck 用 1e-17 並以 1e-18 核對；不要用 DC 工作點量；新的量測方法先在縮減版 netlist 跑完所有 corner，完整 netlist 只驗證一次。
- **不在這裡**：OpenRAM 產生 macro（openram-macro-generation）；layout 萃取（sram-layout-extraction）；view QA 與選定前的 go／no-go（macro-qualification）；macro 的整合與 placement（hard-macro-integration）；margin 怎麼定（signoff-criteria）；corner 清單（multicorner-sta）。
- **本 repo 實例**：ADR-0010、ADR-0018、`ip/sram/char/`（腳本與方法）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`、`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/`（結果）；植入錯誤 `make neg-char`（案例表在 `ip/sram/char/neg_char.py`），以及 P04、P17、P30、P32–P36。

#### openram-macro-generation：用 OpenRAM 產生 SRAM macro

- **何時用**：用 OpenRAM 產生或重新產生 macro、改 OpenRAM、換 OpenRAM 或 PDK 的釘選版本；OpenRAM 的 LVS 報 `Netlists do not match`、log 有 `ERROR` 但 exit 0、`Custom cell pin names do not match spice file`、GDS 每次不同、macro 進了 SoC 後 KLayout 報 nwell.6／psdm.1／m2.2。2026-10-15 從 openram-macro-characterization 拆出。
- **重點**：
  - DRC／LVS 用 OpenRAM 自己釘的 PDK：新版 PDK 改了元件名稱，LVS 會不過；SPICE 用新 PDK 的模型時 netlist 要先改名。
  - OpenRAM 在 DRC／LVS 失敗時 exit 0，DRC 錯誤只記成 WARNING，要讀 log 與報告判斷；`make sky130-install` 可能少複製 cell 卻 exit 0，安裝後要逐一檢查；固定 `PYTHONHASHSEED=0` 才能每次產生相同的 GDS（比 GDS 用 XOR，不比 sha256）；在官方 devShell 裡 `use_nix` 要關掉。
  - OpenRAM 自己的 DRC 不用 full 規則、不跑 flow 的 KLayout deck：整顆 GDS 要另跑 full 規則 DRC 並按規則種類分別和 PDK 附的那顆 macro 比對合併後的違規區域，再跑 flow 的 KLayout deck 要 0（sky130 產生器固定會出保護環 nwell.5a／nwell.6、DFF abut 造成的 met2.2、tap 位置的 psdm.1，repo 的 patch 0002–0004 修；把原本 abut 在一起的 cell 拉開時要補回 M3 clk 線與井；deck 依名稱排除 `*sky130_sram_*kbyte_*` 的 cell）。
  - 改 OpenRAM 只用 repo 內的 patch，並檢查 OpenRAM 的 worktree 恰好是釘選 commit 加 patch。
  - OpenRAM dev 的解析 .lib，internal_power 全是 1e9–1e11 的同一個值，當 characterization 範本前要換掉。
  - sky130 的 1RW（單 port）macro 在釘住的 OpenRAM dev 產不出 DRC／LVS 乾淨的 layout，只用一個 port 時仍用 1rw1r。
  - 開工前查證：預設的讀取電路和 PDK 附的 macro 相同，讀取失敗不會自己消失（本 repo 用 sense amp 輸入端預充電的 patch 0001 修）；cell 名稱的 prefix；OpenRAM 沒有人維護，釘 commit。
- **本 repo 實例**：ADR-0018、`ip/sram/openram/`（`make openram-setup`、`make openram-macro`；植入錯誤 `make neg-openram`，案例表在 `ip/sram/openram/neg_openram.py`）、`docs/notes/openram_phase6_bringup.md`。

#### sram-layout-extraction：SRAM 的 layout 萃取與萃取 netlist 的模擬

- **何時用**：從 GDS 萃取 SRAM 的寄生、模擬萃取 netlist、決定做 characterization 用的寄生延遲倍數；萃取 netlist 報 singular matrix 或 `Timestep too small`。2026-10-15 從 openram-macro-characterization 拆出。
- **重點**：
  - Magic 沒設 `PDK_ROOT` 時會 exit 0 但沒有輸出，要檢查輸出檔。
  - 萃取 netlist 的基板 net VSUBS 與電晶體被拿掉的 cell 的儲存節點會浮接（singular matrix），要接地並加 `rshunt`；暫態報 `Timestep too small` 的原因是 `ext2spice lvs` 階層式輸出的負值修正電容讓部分節點總電容為負（`extract_sram.py` 會 FAIL，`neg-char` N22），改用 flat 輸出（`ext2spice hierarchy off`）。
  - 寄生的影響要用整顆 layout 萃取估：只換 bitcell 估 +48%，整顆萃取是 2.0 倍。萃取 netlist 的讀取檢查，低電位不能小於 .lib 的 `min_pulse_width`，否則在 ss 會誤判成讀取失敗。
  - 提早檢查（流程回顧，ADR-0020）：規則 3，做 characterization 之前先試整顆 layout 萃取，寄生延遲倍數用萃取量到的值（Phase 3.5 假設 × 1.6，Phase 6 萃取是 2.0 倍；dout0 transition 寫 0.5 ns、實際 1.4–2.2 ns，wrapper 的 setup 只剩 +0.151 ns）；.lib 裡沒把握的假設先用只重跑 STA 的 what-if 量影響。
- **本 repo 實例**：`ip/sram/char/extract_sram.py`、`ip/sram/char/sramchar.py`（`trim_extracted`）、ADR-0018 決定 20、`docs/notes/openram_phase6_bringup.md` 步驟 5d。

#### drc-signoff：DRC、GDS 輸出、XOR

- **何時用**：Magic／KLayout DRC、GDS 輸出、XOR（把兩個工具寫出的 GDS 疊起來，找出只出現在其中一份的部分）；設計含 macro 時 DRC 不為 0、abstract DRC 報大量 `nwell.4`（`416 Magic DRC errors found - deferred`）、`The layout has multiple top cells in Layout.top_cell`、金屬密度、latch-up 標記；換了自己產生或改名的 macro 後 KLayout 在 macro 裡報違規。
- **重點**：
  - abstract DRC 會在每條 standard cell row 報假的 `nwell.4`，所以改用完整 GDS 的 DRC。
  - SRAM 內部本來就有大量標準 DRC 規則的違規：SRAM 範圍外必須是 0；範圍內每個違規都要落在 macro 單獨檢查時、同一條規則的違規位置上。只比規則種類會漏掉新的錯誤。Magic 會把同一個違規切成幾個 marker，切的方式隨 cell 的座標變，所以兩顆 macro 之間比 DRC 要比合併後的違規區域，不比 marker 數。
  - Magic 與 KLayout 的 sky130 deck 涵蓋範圍不同：KLayout 沒有 latch-up 規則，而且依 cell 名稱（`*sky130_sram_*kbyte_*`）排除 SRAM 的 `nwell.6`。所以「KLayout DRC = 0」不代表全部合格；自己產生或改名的 macro 要在 macro 單獨時用同一份 deck 檢查到 0。
  - 規則 5，LibreLane 傳給 KLayout deck 的參數名稱對不上：`floating_metal`、`threads` 傳不進 deck（deck 讀 `floating_met`、`thr`），浮接金屬檢查一直是關的、threads 固定 4；看 `klayout-drc.log` 結尾的 `Args:` 段對照。本 repo 不看浮接金屬，沒有自動檢查。
  - 規則 7，**latch-up 的 6 µm 規則目前沒有任何檢查**：交付的 GDS（KLayout 寫出）沒有 `areaid.lowTapDensity`（81/14），Magic 寫 GDS 時產生的 81/14 也只蓋外框內縮 250 µm；Magic DRC 只實作 15 µm 的 LU.2／LU.3，KLayout 與 precheck 的 deck 只宣告 81/14 沒有使用。量測（`docs/notes/latchup/tap_distance.drc`）：15 µm 為 0；6 µm 時 SRAM 外約 7% 的 diffusion 離同型 tap 太遠（標準元件照 15 µm 規則放 tap）。使用者決定記錄下來並詢問下線服務商，不改設計（ADR-0021 決定 2；Phase 7 已知限制 21）。
  - SRAM 範圍內的違規至少要是 macro 單獨檢查的一半：macro 在最終 GDS 裡是空的時，位置比對沒有東西可比也會 PASS。
  - 設了 `ERROR_ON_MAGIC_DRC=false` 之後 LibreLane 不再替 Magic DRC 判 FAIL，自己寫來取代它的 checker 必須有自己的植入錯誤。
  - Classic flow 不插 metal fill，也不查密度；soc_top 實際量到的遠低於下限。放進共乘下線用的 wrapper 時，fill 可能由下線服務商補，先查它的規定（Caravel 看 caravel-user-project-integration）。量密度之前先定義 window 可不可以超出 die 邊界。
- **本 repo 實例**：`pnr/soc_top/check_soc.py`（magic_drc）、`pnr/soc_top/sram_drc_alone.py`、`signoff/waivers/`。negative test：P10、P11、P21。

#### formal-equivalence-eqy：formal equivalence

- **名詞**：formal equivalence 是用數學證明兩份電路在所有輸入與狀態下行為相同。
- **何時用**：用 EQY 證明兩份 netlist（或 RTL 與 netlist）等價；EQY 當機（SIGSEGV）、partition 證不出來，或在切 partition 時停下（`conflicting matches`）；設計 EQY 的 negative test。
- **重點**：
  - 目前可用的組合是合成 netlist vs 最終 netlist。必要設定：加大 stack（`ulimit -s`）、`insbuf off`、刪掉 `$scopeinfo`。
  - 規則 8，EQY 的 PASS 不涵蓋三種情況，都要另外補：被換成常數的 bit（看 log 的 `found constant`，一律 FAIL）、flip-flop 本身的種類（`sequential_cells` 結構比對）、clock 接線（`sat` 先把所有 flip-flop 改成同一個隱含 clock；`clock_sources` 往回追來源）。換 Yosys／EQY 版本或換設計時重跑 `make neg-eqy-*` 確認三道都還抓得到。
  - negative test 要分清楚錯誤是被哪一種機制抓到的：partition 證明失敗、常數規則、或名稱對應衝突。而且要有一個非常數的錯誤，證明「證明步驟」本身有效。FAIL 的位置要在植入點附近（被接成常數的腳只往上游追，否則大扇出的 reset 樹會整棵算進來），並在案例之間做交叉檢查。
  - RTL 對合成 netlist：LibreLane 一定會重新編碼狀態機，目前沒有可用的做法，靠 gate-level 模擬與 directed 測試補。
  - 改到 reset 連接的錯誤（接固定值、接 tie cell、繞過同步器）都在 partition 步驟被拒絕，不會走到證明；negative test 用 `REQUIRE` 檢查是哪個機制抓到的（Phase 5）。
  - OpenROAD 時序修復會對調可互換的輸入（pin swap，`RSZ-0043`），EQY 依「instance.腳位」名稱對應時互相衝突而停下；`run_eqy.py` 只把這些腳位名稱排除在名稱對應外，cell 輸出照樣證明，negative test `o21ai_swap` 確認對調錯誤仍被證明抓到（Phase 6）。
  - netlist 解析要涵蓋任何名稱的 macro：Phase 6 換成 `arv_sram_*` 後，SRAM 的 clock 檢查曾被悄悄略過；現在 config 列出的 macro instance 沒被解析到就 FAIL。
  - 好 netlist 也可能有 partition 證不出來：EQY 在對應名稱切開、partition 的輸入當獨立的值，gate 端經由另有名稱的 net 計算時會失去邏輯關係，得到不可能的反例（Phase 7 wrapper，pin swap 後共用 OR）。`run_eqy.py` 只在「partition 沒證明」是唯一問題時，用 EQY 的 `amend` 把驅動輸入的組合邏輯併進來重試一次；併入 flip-flop 會變成 vacuous pass（實際上什麼都沒檢查就 PASS，真的錯誤也被判 PASS），所以不併、而且第二輪檢查。negative test `nand2_comb_to_nor2`、`nand2_flop_to_nor2`。
- **本 repo 實例**：`signoff/eqy/`（各設計的 partition 數與時間在 `signoff/eqy/README.md`）。negative test：`neg_eqy.py`（每個設計的案例清單以 `CASES` 為準；Caravel wrapper 有靠 amend 重試才證明的 partition，只植入會走重試的 `nand2_comb_to_nor2`，其他類別在 soc_top 上驗證）。

#### antenna-signoff：antenna

- **名詞**：antenna 效應是製造時，只接到閘極的長金屬線收集電荷、擊穿閘極氧化層。
- **何時用**：antenna 違規、diode 插入與它造成的 fanout／slew 副作用、`[WARNING GRT-0243] Unable to repair antennas on net with diodes.`、設了 `DRT_ANTENNA_REPAIR_MARGIN` 卻沒作用、macro 的 LEF 沒有閘極面積資料（`ANTENNAGATEAREA`）。
- **重點**：
  - macro 沒有閘極面積資料時，checker 看不到接到 macro 的線。要從 macro 的 SPICE 算出閘極面積，補進 LEF。
  - 不要用 heuristic diode insertion：soc_top 被插了上萬顆 diode，之後繞線不收斂。
  - ODB 會快取 LEF，換 LEF 驗證時要直接用 openroad 讀。
  - OpenROAD 與 Magic 的 antenna 參數不同。Classic flow 沒有 antenna 的 checker，要自己檢查：`antenna__violating__nets`、`antenna__violating__pins`、`route__antenna_violation__count` 必須是 0（規則 10）。
  - 規則 10，`DRT_ANTENNA_REPAIR_MARGIN` 設了也沒有作用：LibreLane 的 `drt.tcl` 傳的是 `GRT_ANTENNA_REPAIR_MARGIN`（兩處修補共用，沒辦法分開設）；看 DetailedRouting log 的 `repair_antennas ... -ratio_margin <N>` 對照。本 repo 沒用到，沒有自動檢查，下一個專案在 `check_inputs.py` 加一列。
  - 規則 11，`GRT-0243` 不代表有違規：只是某一輪修補有一條 net 修不掉，PASS／FAIL 看最終的 antenna 指標（Phase 3.5–7 四次最終都是 0）；它跟著繞線時有時無，golden 比對列在 `[golden_optional]`。
  - OpenROAD 不讀 `ANTENNAPARTIALMETAL*AREA`，macro 階層之間的 antenna 只能靠 port 上的 diode。
- **本 repo 實例**：ADR-0008、`ip/sram/.../gen_antenna_lef.py`。negative test：P06。

#### cts-clock-tree：clock tree

- **何時用**：clock buffer 的 fanout／cap 違規、skew、clock 輸入 pin 到第一級 buffer 的長線 slew、clock pin 的位置、CTS 把 macro 的 clock 延後而讓 macro 輸入的 hold 變差，以及 setup／hold 違規可能是 clock 造成的時候。
- **重點**：
  - clock pin 到 clock tree 根部的線不在 resizer 的修復範圍內。對策是把 pin 擺在 flip-flop 重心附近，或用 `CTS_CLK_MAX_WIRE_LENGTH` 讓 CTS 把這段線切開加 buffer（soc_top 這樣做之後通過，但同一次 run 也改了別的設定，這一項的效果沒有單獨實驗）。
  - clock buffer 的 fanout／cap 違規：`CTS_SINK_CLUSTERING_SIZE`、`CTS_DISTANCE_BETWEEN_BUFFERS`。
  - 規則 8，PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒有生效（`resolved.json` 是 null，沒有警告），clock 實際走 met1／met2；要走粗金屬只能在專案 config 明確設定。本 repo 沒設，clock 的 EM 只有估算；使用者 2026-10-15 決定本 repo 不設、新專案的 config 第一版就設（sky130 用 `met3`），第一次 harden 後確認 `resolved.json` 不是 null（ADR-0021 決定 8）。沒有自動檢查，checker 下一個專案做。
  - skew 的 metric 含 clock uncertainty 與 derate，不是 skew 的真值；彙總的 `clock__skew__worst_hold` 是各 corner 的最大值（最不負），要看最差 corner 讀 `__corner:` 的值。
  - CTS 會把 macro 的 clock 延到與 flip-flop 一樣晚（插 delay buffer），`CTS_DELAY_BUFFER_DERATE_PCT` 管不到這一步。這串 buffer 的上升緣、下降緣延遲不同，讓 SRAM 半週期路徑的 setup 與讀出的 hold 一起變差。關掉用 `clock_tree_synthesis -no_insertion_delay`；LibreLane 沒有對應設定，本 repo 用 LibreLane plugin 換掉 CTS step（ADR-0016）。
  - setup／hold 違規先拆 launch 與 capture 的 clock latency（各 corner、上升緣與下降緣），來自 clock 結構就在 clock 端修。在 data 端補 hold 很貴：delay cell 在 slow corner 的延遲是 fast corner 的約 3 倍。
  - 有記錄試過但沒有作用的設定，例如 `CTS_MAX_CAP`（CTS 後的 DEF 完全相同，byte-identical；沒有自動檢查，升版時再比一次）。
  - macro latency 對齊的檢查改成依 clock tree 的連接結構判斷：`sram0/clk0` 上方「只驅動下一級」的 clock buffer 連續幾級（對齊 11–12、沒對齊 0），不靠 `delaybuf_*` 名稱；比 tree 總級數分不出來（Phase 5 獨立審查）。
  - 提早檢查（流程回顧，ADR-0020）：規則 13，第一次帶 macro 的 harden 就檢查 macro clock 的結構與兩個邊緣的 latency；flow 的變數關不掉時查到底層工具的指令選項（Phase 4 認定「關不掉」，Phase 5 才找到 `-no_insertion_delay`）。
- **本 repo 實例**：`pnr/soc_top/README.md` 的設定表、`pnr/soc_top/pin_order.cfg`、`pnr/librelane_plugin_arvinsa/`（negative test P52–P54、P58–P60（結構判斷））。

#### pdn-ir-drop：電源網路與 IR drop

- **名詞**：IR drop 是電流流過供電線造成的電壓降；EM（electromigration）是電流密度太大，金屬長期使用後斷線。
- **何時用**：PDN 產生失敗（例如 `PDN-0179` 窄 row）、IR 步驟 `PSM-0069` 中止或 `PSM-0075 Expected four values on line`、macro 電源怎麼接、IR drop 分析與門檻、IR drop 結果小得不合理、EM、decap。
- **重點**：
  - 電源連接由四個範圍不同的檢查負責。macro 電源 pin 有沒有真的接上，證據是 IR 分析的連接檢查（PSM）與 LVS。設 `PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路與原本完全相同，不能拿來證明 macro 電源有接。
  - IR 要檢查 VDD 與 VSS 兩端 IR drop 的合計；LibreLane 的 `ir__drop__worst` 只有 VDD 端。
  - 沒給電壓源位置（`VSRC_LOC_FILES`）時，所有 PDN pin 都被當成理想電源，結果樂觀到不能用。電壓源位置要寫明是假設，checker 也要擋住比假設樂觀的設定。
  - 最大電流（ff）與最大電阻（ss）不在同一個 corner；「ff 電流＋ss 電阻」的人為組合只當上限參考，不是拿來和上限比的值（規則 11）。
  - **EM 目前沒有檢查**（規則 8）：`ir_worst.py`、`ir_pattern.py`、`ir_caravel.py` 都沒開 PSM 的 `-enable_em`，只有 Phase 4、5 量過一次 via4。記在放寬清單 I12（下線前要做）；沒有自動檢查，新 checker 留到下一個專案；範圍已由使用者決定為電源網路 EM（strap 與 via，`-enable_em` 的電流對 tech LEF 上限，max power pattern、ff 與 ss corner，植入「strap 改窄」「via 單一 cut」；ADR-0021 決定 8），訊號線 EM 不在範圍。
  - metric 陷阱：`design_powergrid__drop__average__*` 存的是平均電壓，不是壓降。
  - 規則 12：拿來和上限比的是 CPU max power pattern 的 IR（`fw/tests/maxpower` 在最終 netlist 跑 gate-level 模擬 dump 出的 switching activity，`make ir-caravel`、soc_top 的 `make ir-soc`，ADR-0019 決定 20、25；negative test `make neg-ir-soc`／`neg-ir-caravel`；檢查前先核對 run guard、window 齊全、VCD 的時脈週期等於 `CLOCK_PERIOD`；OpenSTA 預設的 toggle rate 在 Phase 7 高估約 2.2 倍）。harden 內每次也在預算所保護的兩個 slow corner 用預設 toggle rate 檢查（該 corner 的電流、1.60 V、ss 金屬電阻，`ir_worst.py`），不能只檢查 nom_tt；「ff 電流＋ss 電阻」的 worst-case 組合只列為參考（Phase 5 起檢查它，Phase 7 發現它拿 ff 的電流和 slow corner 的預算比，改掉，ADR-0019 決定 19）。macro 不在 .lib 裡的電流（OpenRAM SRAM 沒用到的 port 浮接時的電流）依 PVT 加在 macro 上。電壓源要從晶片的真實 pad 起算（Caravel 只有一顆 vccd1 pad，只用 wrapper ring 會低估約 9 倍）。規則 13：改 PDN 前先在完成的 layout 上 what-if（重新產生 PDN、只跑 IR，約 25 秒），同樣金屬量下加寬 strap 比增加 strap 密度有效（Phase 5，ADR-0017）。經驗紀錄：電壓源放在 met3 電源連接線接到 wrapper ring 的位置時 PSM 會 Signal 11（Phase 7，原因沒查），改放在 ring 與 strap 的交點。
  - 提早檢查（流程回顧，ADR-0020）：規則 14，定 die 的 floorplan 試跑時 IR 就要成立（真實 pad、slow corner，gate-level 模擬能跑之後用 max power pattern）；結果比預算小 100 倍以上先查電壓源位置的設定（本 repo 的 IR 模型分四個 Phase 才修完）。
- **已知限制**：EM 沒有檢查；「PDN 變細就會 FAIL」沒有 end-to-end 的 negative test（現有的都在 checker 層）；只做 static IR，沒有 dynamic IR。
- **本 repo 實例**：`docs/notes/ir_worst_case_soc_top.md`、`pnr/soc_top/vsrc/`、`pnr/soc_top/ir_worst.py`、`pnr/soc_top/ir_pattern.py`、`pnr/user_project_wrapper/ir_caravel.py`。negative test：P07、P26–P29、P61、P62、P77、P78，以及 `make neg-ir-soc`／`neg-ir-caravel`（案例清單在 `pnr/soc_top/neg_ir.py`）。

#### lvs-signoff：LVS 與連接性

- **何時用**：LVS 失敗、macro 在 LVS 中是 black box、驗證電源或訊號 pin 的實體連接、disconnected pin（`Found N disconnected pin(s), of which 0 are critical.`，包括 wrapper 頂層報幾百個）。
- **重點**：
  - macro 用 LEF 萃取時，LVS 只驗 macro pin 的連接，不驗內部。macro 在最終 GDS 裡是空的，LVS 照樣 PASS（Phase 6 只有 XOR 抓到），macro 的 layout 內容要靠 XOR 與 `check_macro_gds.py`。
  - disconnected pin 的表格只在有 disconnected pin 時才產生。要讀 log 裡的那一行，有表格時還要確認表格完整。
  - macro 沒用到的輸出接到 RTL 裡宣告的 wire，就不會被列為 disconnected pin；並確認 `IGNORE_DISCONNECTED_MODULES` 仍是 PDK 預設。
  - 規則 2，預期會有 disconnected pin 時要比對「剛好是哪幾支」，不能只比數量：單獨 harden 的 PicoRV32 必須剛好是 35 支沒用到的 PCPI 輸入（`pnr/picorv32_core/check_disconnected.py`）；Caravel wrapper 的頂層必須剛好是沒用到的固定輸入／inout 腳位加沒有 cell 用的電源腳位、0 個 critical（`check_soc.py disconnected` 的 `unused_ports`，C15）；soc_top 必須是 0。
  - 驗證方法：刪掉電源環上的 via，只重跑萃取與 LVS 那幾步，必須 FAIL。
- **negative test**：P05、P08、P15、C15（`make neg-pnr-caravel`）；案例說明在 `pnr/soc_top/neg_pnr.py` 開頭。

#### gate-level-simulation：gate-level 模擬

- **何時用**：在 netlist 上跑 regression、RTL 與 netlist 比對、X 的處理、PG netlist、cell 模型設定、模擬逾時。
- **重點**：
  - sky130 cell 模型用 `-DFUNCTIONAL -DUNIT_DELAY=#1`。
  - RTL 與 netlist 放在同一個 testbench 做 lockstep，每個 cycle 比輸出，而且要證明比對真的有跑（`gl_compares` > 0，並植入錯誤確認會 FAIL）。X 的規則：RTL 是 0／1 才比，這時 netlist 是 X 也算不一致；RTL 是 X 不比（合成可以合法替它選值）。
  - PG netlist：電源腳沒接好的 cell 輸出 X，lockstep 就 FAIL；Icarus 對 tap cell 多出的 VPB／VNB 報的警告，只對那一個 cell 放行。
  - Icarus 要求先宣告再使用；用腳本改 netlist 時也要注意，escaped identifier（`\sram_din0[31] `）結尾的空白不能去掉，否則讀檔報 `syntax error, unexpected TOK_ID`。
  - wall-clock 時限要依 gate-level 的速度算：照 RTL 速度算，時限只有實際所需時間的約 2 倍，機器一忙（包括 Spotlight 索引 `runs/`）就會誤判逾時。各支實際跑出來的時間與時限在 `dv/gl_soc/README.md`。
  - firmware 沒用到的功能，gate-level 模擬看不到（見 dv-directed-tests）。
  - dump IR 用的 switching activity（規則 9）：firmware 把滿負載的段落標在 GPIO，`run_gl_soc.py --record-window` 只 dump netlist 那一份、只 dump 那一段、用 run 的 `CLOCK_PERIOD`（testbench 不帶參數時的預設 40 ns 不是 signoff 週期）；plusarg 名稱不能是 testbench 現有 plusarg 的延伸（`$test$plusargs` 比對 prefix，`+vcd_win` 會打開整個 testbench 的波形 dump）。
- **本 repo 實例**：`dv/gl_soc/`（含 `vcd_window.v`）、`dv/gl_core/`、`dv/monitors/gl_lockstep.v`。negative test：`neg_gl_soc.py`、`neg_gl_core.py`。

#### floorplan-congestion：floorplan 與繞線壅塞

- **何時用**：pad、block、pin 的規劃經使用者核准之後（chip-floorplan-pin-planning，`CLAUDE.md` 規則 14），決定 die／core 尺寸與使用率（utilization，cell 面積佔可放置 cell 面積的比例）、macro 的格點與 halo、placement 目標密度（`GPL-0052`）；遇到繞線壅塞、某條線大幅繞路、窄 row（`PDN-0179`）、GCell overflow。
- **重點**：
  - 新的頂層設計或搬動 macro／block 之前，先經 chip-floorplan-pin-planning 的規劃與核准；核准前改 `MACROS` 位置會被 hook 擋下、`make pin-plan` FAIL（legacy 的 soc_top、picorv32_core 除外）。
  - die 尺寸用前一階段實際量到的面積估，並寫清楚「使用率」的分母。自己排腳位的設計用 `IO_PIN_ORDER_CFG`，並設 `ERRORS_ON_UNMATCHED_IO = "both"`，pin 名稱對不上就會出現錯誤；wrapper 腳位固定的設計（Caravel）用 `FP_DEF_TEMPLATE`。
  - macro 座標要對齊 site 格點。halo 要嘛留出夠寬的 row，要嘛蓋過 core 邊界，否則會出現 PDN 接不到的窄 row。
  - 繞路用「繞線長度 ÷ 端點直線距離」判讀；全域的 congestion 報告看不到局部繞路。
  - logic 區是 L 形時要手動設 placement 目標密度（soc_top：自動的 68% 改 55%，轉角繞路消失；wrapper 因繞完線才出現的局部熱點改 50%）。
  - 提早檢查（流程回顧，ADR-0020，使用者決定，效益為推算）：規則 7，定 die 尺寸時整顆設計加 macro 只跑到 PDN、global placement、global routing，看窄 row、目標密度對 logic 區使用率、overflow，出 floorplan 圖（Phase 3 約 8 次試跑與一度放寬的 max transition 可以提早看到）；繞完線才出現的局部熱點仍看不到。自動檢查留到下一個專案。
- **本 repo 實例**：ADR-0006、`pnr/soc_top/config.json`、`pnr/soc_top/pin_order.cfg`。

#### timing-constraints-sdc：timing constraint

- **何時用**：寫或改 SDC（clock、IO delay、例外路徑、derate、max transition）；區分 PnR 與 signoff 的 constraint（sta.log 寫 `Reading design constraints file at .../pnr.sdc`）；確認 constraint 真的生效；STA 報沒有 constraint 的路徑（`unconstrained endpoints`、`unclocked register/latch pin`）。
- **重點**：
  - 新 SDC 先 `source` LibreLane 的 `base.sdc`，再改需要的一兩項。
  - 規則 2，設了 `PNR_SDC_FILE` 就一定要同時設 `SIGNOFF_SDC_FILE`，否則 signoff STA 會改用 PnR 的 constraint，而且沒有任何警告；看 `resolved.json` 與 signoff `sta.log` 的 `Reading design constraints file at` 那一行。`review_criteria.py` 只印 INFO，沒有自動檢查，下一個專案做成 checker。
  - LibreLane 每個 corner 都會檢查沒有 constraint 的路徑，但結果沒有變成 metric，也沒有 checker 判 FAIL，要自己寫：本 repo `check_soc.py sta_setup` 在 soc_top 不允許任何警告（Phase 6 `clk1` 接系統時脈後拿掉 `sram0/clk1` 的例外），wrapper 只允許 Caravel 範本的 29 支 `analog_io`。
  - 規則 16，constraint 有沒有生效看 STA 報表的路徑分解，不看 SDC 有沒有被讀（出現兩次：uncertainty、input transition）：uncertainty 看每條路徑的 `clock uncertainty`／`inter-clock uncertainty`，input transition 看 `(in)` 那一行的 slew。uncertainty 由 `review_criteria.py uncertainty_applied` 逐條核對（P56），其他種類靠手動查。
  - 改完 constraint，用同一份 layout 只重跑 STA，確認只改了想改的。
  - 用 `unset_*_delay` 拿掉 constraint 時，STA 的完整性檢查看不出來；要模擬「漏寫」，就產生一份真的少一行的 SDC。
  - 半週期路徑（launch 與 capture 在相反 clock edge 的路徑）要算 duty cycle。PnR 與 signoff 共用的 constraint 放在同一個檔。
  - OpenSTA 對設了 driving cell 的腳位會忽略 `set_input_transition`，而 `base.sdc` 對所有輸入都設了 driving cell；要用 input transition，source `base.sdc` 時先暫時停用 `set_driving_cell`，改完看報表腳位的 slew 確認。
  - 放進 Caravel wrapper 時，IO constraint 用從 Caravel extract 出的數值（source latency、IO delay、transition、負載）；例外路徑要確認自己的電路適用才用。Caravel 給的 transition 超過自己的 max transition 時照用，Caravel 直接驅動的 IO net 另外檢查（`check_soc.py max_slew`，ADR-0019 決定 16）。
- **本 repo 實例**：`pnr/soc_top/pnr.sdc`、`signoff.sdc`、`clock_uncertainty.sdc`；wrapper 的 `pnr/user_project_wrapper/caravel_base.sdc`、`caravel_io.sdc`（ADR-0019 決定 14）。negative test：P01–P03、P13、P22–P25。

#### signoff-criteria：signoff 條件的推導與每次 harden 後的檢查

- **何時用**：開新設計寫計畫時（操作條件、corner 清單、corner 的代價）與任何 harden 之前；要放寬或補償某項條件時（放寬清單）；每次 harden 跑完、回報結果之前（PASS 或 FAIL 都要）；決定或檢討任何 signoff 條件的數值，例如 clock uncertainty（jitter、duty cycle、margin）、OCV derate、PVT corner 與 temperature inversion、IO delay、IR drop 預算、EM、SI、max transition／cap／fanout、antenna、density、latch-up、macro SPICE characterization 值的 margin；或要說明某個工具沒分析的效應用哪一筆 margin 涵蓋。
- **重點**：
  - 每個條件都要回答四件事：防什麼、數值怎麼算、預設值出自哪裡、工具有沒有分析。LibreLane 的預設值多半是沿用的常數，沒有成分說明。
  - 推導前要先有的輸入：clock 來源、供電範圍、溫度、外部介面時序。沒有就寫「假設」。
  - IO delay 的 `-min` 不能直接設 0，要和上層的 clock latency 一起建模，否則會出現大量假的 hold 違規。
  - macro 的 SPICE characterization 值要加上模型沒涵蓋的部分（寄生、量測誤差、mismatch）：延遲乘比例、setup/hold 加固定值、輸出最早變化的時間乘小於 1 的係數，再和既有保守值取較嚴者。
  - 推導出來的條件要寫進 flow 變成 checker，每個都要有植入錯誤的案例（附 soc_top 的實作範本）。
  - 規則 30，LibreLane 的內建 checker 沒設門檻就略過、flow 照樣 PASS：flow log 只有 `Threshold for Threshold-surpassing long wires is not set. The checker will be skipped.`（`Checker.WireLength`），metric 不存在時印 `metric was not found` 也放行。harden 後 grep 這兩句，逐條補門檻或寫明由什麼取代（本 repo 最長線由 golden 鎖住）；沒有自動檢查。
  - power signoff（IR、EM、功耗）一律用 CPU max power pattern 在最終 netlist dump 出的 switching activity 檢查，OpenSTA 預設的 toggle rate 只當參考或 harden 內的早期檢查（使用者 2026-10-13）；沒有 pattern 的 legacy 設計要在報告寫明。
  - IR 用多大的電流要先量測再決定（Phase 7，使用者 2026-10-13）：電流、電壓、電阻取預算所保護的那個 slow corner（不是「ff 電流＋ss 電阻」），先重現 flow 的功耗並按類別拆解，.lib 沒有的電流按 PVT 加，switching activity 用 CPU max power pattern 在最終 netlist 跑 gate-level 模擬 dump 出的 VCD（工具預設的 toggle rate 只當參考），用 R = 壓降 ÷ 電流和幾何估算交叉檢查，電壓源從晶片的真實 pad 起算。
  - 一組已驗證的工具行為，例如：指定邊緣的 uncertainty 會取代一般值、instance derate 會取代 global、fmax 報告排除半週期路徑、OpenSTA 沒有 SI 分析。
  - 每次 signoff 都要列出「不分析的項目」，寫出各用哪一筆 margin 涵蓋。
  - **每次 harden 後的檢查**（使用者 2026-10-07 要求）：
    - 第一部分由 `signoff/scripts/review_criteria.py` 檢查 criteria 有沒有被執行：config 每個設定都進了 run、uncertainty 出現在每個時序步驟與 signoff corner、corner 齊全、repo 的 checker 都跑了。`pnr/soc_top/run.sh` 每次都跑它，LibreLane FAIL 也照跑；harden 要 PASS，它也必須 PASS。
    - 第二部分由 Claude 依 skill 判讀 criteria 合不合理，寫 `runs/<tag>_signoff/criteria_review.md`（有沒有被執行、合不合理、學習三節）。專案的 Stop hook（`.claude/hooks/require_criteria_review.py`）沒看到就不讓 Claude 回報。
    - golden 比對 FAIL 時，先找出和 golden run 第一個分歧的步驟，判斷是設計或設定改變，還是 flow 不可重現（同一份輸入只重跑那一步，量發生頻率）；後者交給 signoff-checker-qualification，不直接放寬誤差。
    - 學到的數字寫進依製程分類的 knowledge 檔（`knowledge/sky130A_sky130_fd_sc_hd.md`）；出處要在下一次 harden 之後還找得到：不能引用 `runs/<tag>/`、`runs/<tag>_signoff/`、`.prev`、scratchpad，先複製到 `runs/<實驗名>_signoff/` 或 `docs/notes/` 再引用（`runs/` 裡的在清理前由 `make collect-evidence` 收進 `docs/evidence/`；沒有自動檢查）。依據不成立的 criterion 提給使用者決定，不自己改。
  - 製程專屬的事實（sky130 的預設值、.lib 範圍、DRC deck、latch-up、density、antenna、EM 電流密度與片電阻）放在 knowledge 檔，編號 S2、S10 等沿用原規則編號；SKILL.md 本身只放和製程無關的方法，本設計的 mW／mV 數字在 knowledge 檔「實測校準資料」與 ADR。「已驗證的工具行為」編號 20–29 已由 knowledge 的 S20–S29 使用，新的工具行為從 30 起。
  - 第一部分新增 `uncertainty_applied`（逐條路徑核對 STA 實際套用的 uncertainty），`checkers_ran` 加 `ir_worst.py`（兩個 slow corner 的 IR，預設 toggle rate），`harden-core` 也跑（`--design picorv32_core`）。判斷原則補：criterion 的依據是在哪個設計量的，換設計就要重新量（Phase 5 的 IR）。sky130 的 knowledge 檔補了 Phase 5 確認的製程事實 S20–S24：連最小負載都推不動的 cell、`dlygate` 被當成 buffer、`clkbuf_16` 下降緣較慢、預設 PDN（via4 只有 1 個 cut）與 worst-case IR 約是 nom_tt 的 1.4 倍、SRAM 內的 Magic DRC 計數隨上方金屬改變。
  - 提早檢查（流程回顧，ADR-0020，「提早檢查」一節）：A1 寫計畫時的操作條件對照表（VDD、Tj 由使用者決定，corner 清單由它推出，對照 macro 與 library 已驗證的範圍；macro 在某個 corner 不能動時不拿掉 corner）；A3 第一份 netlist 後的 corner 代價 what-if；C1 任何 harden 之前（含子區塊與試跑）limits 每列有出處、IR 的檢查方式一次定清楚；E1 放寬清單（`docs/relaxation_register.md`）。每次 harden 後的「合不合理」多兩列：最差 corner 在不在 resizer 的清單、放寬清單。C1 與 E1 的自動檢查留到下一個專案。
- **本 repo 實例**：`docs/notes/signoff_criteria_soc_top.md`；negative test：`neg_pnr.py` P43–P49（`review_criteria.py` 的每個檢查項）、`make test-review-hook`（Stop hook）。

#### rtl-synthesis-lint：合成與 lint

- **何時用**：Yosys 合成設定、harden 的參數是否與 SoC 裡的 instance 一致（`cpu-params` FAIL，包括 `config.json has conditional blocks ... not supported by this check`）、狀態機被重新編碼（`Recoding FSM`）、暫存器被常數化、lint 警告、latch、為時序目標調整合成。
- **重點**：
  - 參數一致要用 Yosys 讀 RTL 取值比對，不比字串；Yosys 會忽略 `defparam`。config 的 `pdk::`／`scl::` 條件區塊會依 PDK 換掉參數，checker 看到就直接 FAIL；也要比 harden run 實際用的參數（`cpu_params.py --resolved`）。
  - LibreLane 的合成一定會跑 `fsm` 重新編碼狀態機，沒有開關，所以 RTL 對 netlist 的 formal 比對會失敗。
  - 上電時值未定、寫入後恆為常數的暫存器，可能被合法地換成常數。
  - LibreLane 的 lint 警告只計數、不判 FAIL，數量與 latch 數由 golden 鎖定（名稱含 lint、latch 的 metric 不給誤差）。
  - 經驗較少：本 repo 沒有為縮短週期調整過合成。已知限制：`SYNTH_STRATEGY` 與邏輯深度沒試過；latch 偵測沒有 negative test，只靠 golden 的 `design__inferred_latch__count` 鎖在 0。
- **本 repo 實例**：`pnr/picorv32_core/cpu_params.py`、`rtl/lint/`。

#### flow-regression-reproducibility：一鍵 regression、可重現性與來源追溯

- **名詞**：乾淨 checkout 是從某個 commit 重新取出、沒有任何 build 產出的目錄；來源追溯（provenance）是記錄並檢查一個 run 用了哪個 commit、哪版工具與 PDK。
- **何時用**：建立或執行 `make regress`（`regress-picorv32`、`regress-caravel`）；機器資源問題：`No space left on device`（`Errno 28`）、某一項卡住卻沒有錯誤訊息、同時跑幾條被系統中止、開跑前決定同時跑幾條、清理舊 worktree、Spotlight 拖慢；在乾淨 checkout 驗證；查一個 run 是怎麼產生的；讓下游步驟拒絕過期或沒 PASS 的 run；長時間 run 期間繼續開發或等待它結束；長時間的 regression 開跑前的快速檢查與試跑；GDS 的 sha256 每次不同；改了共用 flow 設定後另一個版本的設計 FAIL。同樣設定重跑結果不同、golden 該給多少誤差，看 signoff-checker-qualification。
- **重點**：
  - regression 依相依順序一次跑一個 target，第一個 FAIL 就停。開始前工作目錄要乾淨，並拒絕 `make -i`／`-n`；結束時 HEAD 必須和開始時相同。拒絕條件由 `make neg-regress` 用假的 make 測（10 個案例，清單在 `scripts/neg_regress.py`）。
  - 只有在乾淨 checkout 從頭跑到底才算驗證。main worktree 裡忽略版控的 build 產出，會藏住漏宣告的相依。版控外的工具（`.tools/`）要有環境變數覆寫（`LIBRELANE_DIR`、`XPACK_DIR`），並在第一個 target `env-check-flow` 就檢查。
  - 來源追溯要比內容，不只比版本字串：LibreLane clone 不能有改過的檔、PDK 要比內容 sha256、路徑要先解開 symlink。
  - 下游步驟要確認 run 是 PASS，而且來自目前的 commit。
  - golden 與 commit 的先後：更新 golden 的那次 run 永遠過不了下游檢查；要先 commit 新 golden，再用乾淨 checkout 跑完整 regression 證明它可重現。Makefile 要加 `.NOTPARALLEL:`，否則 `make -j` 時各 target 會互刪 `runs/`。
  - 長時間的 run 還在跑時另開 worktree 開發。用舊 run 測新 checker 時建 dev fixture，結果不能當證據。
  - 等跑很久的 run 結束用 PID：`pgrep -f` 會比到等待腳本自己；macOS 的 `pgrep` 裡 `\|` 不是「或」；從 log 判斷結果要比整行開頭（`regress: PASS` 也會比到 regress-rtl 那一行）。
  - 長時間的 regression 之前，先用 `make py-check` 和 dev fixture 試跑，提早抓到會在中途才出錯的問題（未定義的名稱、寫檔前先清空了要讀的檔案；改過的 negative test 也要先單獨跑過）。
  - 規則 11，同一個設計的幾個版本共用 flow 設定、plugin 或 SDC 時，為其中一個改的設定，改完就在每個版本上各 harden 一次，不要等結案 regression（Phase 5 為 Hazard3 改的設定讓 PicoRV32 setup FAIL）。
  - 規則 12，GDS 的 sha256 每次不同不代表不可重現：差在 BGNLIB／BGNSTR 的日期記錄；netlist、DEF 比 sha256，GDS 用 KLayout XOR 或清掉日期再比。
  - 資源與長時間工作（規則 13–17）：同時跑幾條依記憶體決定（目前沒有自動檢查）；開跑前看磁碟，`scripts/regress.py` 在剩餘空間少於 `REGRESS_MIN_FREE_GB`（預設 100 GiB）時第一個 target 前就 FAIL；每個 target 有逾時（參考時間 × 3、至少 30 分鐘，`REGRESS_TIMEOUT_SCALE`），逾時砍整個程序群組、判 FAIL，log 有 `regress: TIMEOUT`（negative test `make neg-regress` 的 `low_disk`、`timeout`）；卡住要三項一起看（耗時、工具程序的 CPU、log 修改時間）；結案後清理舊 worktree 與 negative test 的中間檔案（先複製要引用的證據，刪前請使用者確認）；專案結束清掉 `runs/` 與所有 worktree 前，`make collect-evidence` 把文件引用的報告、每次 harden 的 PASS／FAIL 結果與 criteria review、regression 摘要收進 `docs/evidence/`（保留路徑，`references.md` 列出每個引用是否收錄），GDS、netlist、整個 run 目錄不收（規則 16，ADR-0021 決定 7）；`runs/` 與 worktree 排除在 Spotlight 索引外（使用者操作）。
- **本 repo 實例**：`scripts/regress.py`、`signoff/scripts/provenance.py`、`run_guard.py`。negative test：`neg_regress.py`（10 個案例）、`neg_provenance.py`、`neg_run_guard.py`（下游步驟清單是 `STEPS`，目前 65 個案例，以 `neg-run-guard: PASS <n>/<n>` 為準）。

#### multicorner-sta：多 corner STA

- **名詞**：PVT corner 是製程、電壓、溫度的組合（例如 `ss_n40C_1v60`）；RC corner 是繞線寄生的 min／nom／max。
- **何時用**：增減 corner、設定每個 corner 都會執行的 hook、只重跑 STA 做 what-if（改週期、duty cycle、uncertainty、derate）、從 STA 結果推最小週期、繞線前量 resizer 看不到的 corner、corner 變多後 PnR 變慢。
- **重點**：
  - 在 config 設 `LIB` 會取代 LibreLane 的整組 corner 預設，相關的三個變數要一起設；新 corner 的名稱要符合寄生與萃取規則的萬用字元，先跑只做 lint 的 run 看 `resolved.json` 確認。`check_signoff.py [corners]` 要求 limits 檔的 corner 清單等於 metrics 裡出現的 corner。
  - resizer、CTS、其他 step 與 signoff STA，各自讀不同的 corner 變數。`PNR_CORNERS` 沒設時只用 `DEFAULT_CORNER`（LibreLane 的變數說明寫成用 `STA_CORNERS`，和程式不符），所以 placement、global routing 與 PnR 中途的 STA 只看 nom_tt。設定了用哪組 corner，也不代表演算法每個決策都看了那些 corner（resizer 換尺寸只看第一個讀入的 .lib，見 drv-timing-closure 規則 11）。
  - 規則 3，resizer 看的 corner 預設等於全部 signoff corner；corner 變多讓 PnR 變慢或修復停不下來時，先拿同一份輸入把那一步單獨重跑，一次只改 `RSZ_CORNERS`，找出原因（Phase 4 的 15 個 corner 停不下來，根本原因其實是 drive 太弱的 cell），不要直接減少 corner。真的要讓某個 corner 只在 signoff 檢查，要有原因、what-if、ADR 與放寬清單；本 repo 現有的例外是 wrapper 的 resizer 不看 ff_100C（ADR-0019 決定 17）。只給 signoff 看的 corner 要在繞線前量一次：把一個 resizer step 匯出（`eject`）、`RSZ_CORNERS` 加上那個 corner，換成自己的 Tcl 用 `worst_slack -corner` 量。
  - what-if 的正式證據要用 LibreLane 只重跑 STA 那一步、涵蓋全部 corner；單一 corner 的 `sta` 腳本只能當非正式的參考。
  - 最小週期要從關鍵路徑推，不能用 `report_clock_min_period`（它排除半週期路徑）。
  - PnR 中途的 STA（`STAMidPNR`）只看預設 corner；flow 中途 state 裡其他 corner 的 metrics 是 placement 前那一步留下的舊值，不能拿來判斷。決策看 signoff STA。
- **本 repo 實例**：`pnr/soc_top/config.json`、`sta_extra_corner.tcl`。negative test：P01–P04、P22–P25、P30。

#### dv-directed-tests：directed 測試補驗證缺口

- **名詞**：directed 測試是針對一個特定功能、明確檢查結果的測試。
- **何時用**：植入的錯誤在 gate-level 模擬或 formal 沒被抓到，或發現某個功能 regression 從沒用到。要證明的是 checker 本身會不會抓錯，看 signoff-checker-qualification。
- **重點**：
  - 缺口從「漏掉的植入錯誤」找。
  - 先讀 RTL 確認實際行為，再寫期望值。
  - 編譯器會改寫未對齊（misaligned）存取，要測特定指令時用 inline assembly，並看反組譯確認。
  - 寫明測不到的部分。新測試要加進 Makefile、測試清單與 spec；UART 輸出要固定，不要印每次可能不同的數字。加完要重跑完整的 RTL regression 與植入錯誤。
  - 在 netlist 植入對應的錯誤，證明新測試抓得到。
- **本 repo 實例**：`fw/tests/counters/`、`fw/tests/buserr/`、`dv/gl_soc/neg_gl_soc.py`。

#### phase-exit-review：Phase exit review 與獨立審查

- **何時用**：一個 Phase 收尾。
- **重點**：
  - exit criteria 照抄規劃，再加上前一階段帶過來的項目。
  - 證據只用乾淨 checkout 的最後一次 run；前幾次為什麼不算要寫明。每個數字都對回證據檔。
  - 開結案 regress 之前，最後改過的每支 checker 先在現有的 run 上跑一次沒植入時必須 PASS 的對照（Phase 3.5 與 Phase 6 都因為改了沒跑，各浪費一輪 regress）。
  - 請兩個沒參與實作的 agent 獨立審查：一個核對文件，一個找 checker 漏洞。審查找到的問題沒有重跑驗證，就不能寫「已修正」。
  - 要放寬門檻或改比對規則時先問使用者，並記錄決定。
  - 收尾時分析本階段的重大任務是否需要新 skill，並逐一對照每個 skill、README 與 `description` 有沒有寫回。
  - 規則 1 補：再前一個階段沒結的限制也要延續；「沒變」要在新設計上重新量過才算（Phase 5 的 IR 原本寫沒變，實際超過上限）。延後的項目要追到結：收尾時 grep 本階段改過的筆記、ADR、skill 裡「Phase N 才能處理」「之後會加」這類句子逐條對照（latch-up 標記 81/14 就是這樣漏掉的），決定當下寫進 `runs/todo.md`。
  - 規則 2 補：不在 regression 裡的 negative test（例如 `neg-char`）列出最後一次跑的 commit 與環境，被測程式改過就在乾淨 checkout 補跑（目前沒有自動檢查）。
  - 規則 3 補：證據在做的當下存到不會被覆蓋或消失的地方（`docs/notes/<主題>/` 或 main worktree 的 `runs/<實驗名>/`；`runs/` 不進版控，清理前用 `make collect-evidence` 收進 `docs/evidence/`），不能引用 scratchpad、會被下一次 harden 覆蓋的 `runs/<tag>_signoff/`、之後會刪的 worktree、只在終端機看到的輸出。
  - 規則 4：章節以 `phase7.md` 為準；與計畫不同的地方，每一項寫原本防範什麼、現在由誰防範，沒有替代的列入已知限制與放寬清單。
  - 規則 9 收尾清單：README、skill 與 `description`（`make skill-check`）、流程文件與 `AGENTS.md` 同步、規則 10 稽核、清空 `runs/todo.md`、清理舊 worktree（專案結束先 `make collect-evidence`）、推送只在使用者要求時做。
  - 規則 11：新決定取代舊決定時，同一個 commit 把舊段落標成已被取代、其他文件一起改；比較數字要寫明兩邊的條件；skill 與流程文件不寫會隨程式變的案例數，改指向腳本或總結行。
  - 規則 12，收尾的順序與時程：最後改過的 checker 先在現有 run 上跑 positive control → 開結案 regress → regress 期間做獨立審查 → 修正 → 下一輪；至少預留兩輪乾淨 regress 再加一輪修正。
  - 提早檢查（流程回顧，ADR-0020）：規則 10，收尾時找 checker 漏洞的審查只審本 Phase 最後改過的 checker（其他在寫完時就審過）；已知限制裡的放寬引用放寬清單，並核對依據的設計是不是本 Phase 的設計。
- **本 repo 實例**：`docs/phase_exit/phase0.md`–`phase7.md`（章節以 `phase7.md` 為準）。

#### core-migration-hazard3：把 CPU 換成 Hazard3

- **名詞**：AHB5 是 pipelined 匯流排，一筆傳輸分 address phase 與下一個 cycle 的 data phase；RVFI 是 core 每退休一條指令輸出的紀錄；ISS 是只模擬指令語意的軟體模型，當參考答案。
- **何時用**：SoC 的 CPU 換成另一顆 core（例子是 PicoRV32 換成 Hazard3）；Yosys `check -assert` 報 `core_haddr_d` 沒有 driver、`bus_assert` 報 `addr/wdata/wstrb changed while mem_valid=1`、`exc`／`irq` 測試或 cycle 下限 FAIL、rvcpp 在 riscv-tests 結尾逾時；選 1port 或 2port wrapper；AHB5 接 1RW 同步 SRAM；設定 Hazard3 的參數；搬移 trap、中斷、reset 相關的測試；建立 core 層級的驗證（上游 riscv-tests、rvcpp 逐條指令比對）。
- **重點**：
  - 固定用 stable 版、submodule 唯讀；參數要用 instance 參數或 `chparam`（不能用 define），而且要在展開階層前設定。
  - 預設值的陷阱：`CSR_COUNTER` 預設 0、計數器 reset 後是停住的、`EXTENSION_A` 預設開、暫存器堆沒有 reset。
  - debug、power 相關的 port 都要 tie-off，`dbg_sbus_vld` 一定要 0。
  - AHB5 的寫入資料晚一個 cycle，OpenRAM SRAM 要在同一個上升緣拿到位址與資料：要 bridge、write buffer 或 wait state。有副作用的周邊只在 `htrans[1] && hready` 那個 cycle 取樣。
  - 沒有 trap 腳、中斷是 level-sensitive 的標準模型、reset 是非同步的（要同步器）、CPI 小很多：以這些為前提的測試與 checker 要重新定義或重新量。
  - 上游測試要 newlib 工具鏈；rvcpp 印的是退休指令 trace，要自己用 RVFI 轉成同格式再逐條比對。
  - 舊 core 的建置要保持不變：新 core 專用的 RTL 都放在 define 下，再用前置處理後的 RTL 比對證明舊建置一字不差，舊的 golden 就能沿用。
  - 轉成 native bus 時，AHB 讀取的 `hwdata` 要擋掉（它會變動或是 X）；`mtval` 固定為 0；中斷進入次數與 cycle 數的期望值要依 CPU 分開訂。
  - PnR 與 signoff：PicoRV32 版調好的設定不能直接沿用。resizer 要看 signoff 的所有 slow corner、resizer 會換上的 cell 裡 drive 太弱的要重查、開繞線後的 setup 修復；limits 檔裡依設計結構推導的數字（例如沒有寄生資料的 driver 數）要用新 core 的 run 重新計數，golden 另建一份，並重新量同設定 run 之間的差異（ADR-0015）。規則 22 另兩點：為新 core 改了舊 core 也共用的 flow 設定，改完就在每個 CPU 版本各 harden 一次（Phase 5 因此讓 PicoRV32 setup FAIL，開發中沒有自動提醒，最後一道是 `make regress-picorv32`）；換 core 後 IR 的依據要重新量，max power pattern 的 VCD 用新 core 的最終 netlist 重錄。
  - core 層級驗證：測試台的設定檔從 SoC 的參數自動產生；上游測試台與 riscv-tests 都在 `runs/` 建置，submodule 不留檔案；rvcpp 要補 `fence`，而且它的 CSR 模型是全功能設定，所以逐條指令比對只做 user-level 指令、從測試本體開始。
  - 提早檢查（流程回顧，ADR-0020）：規則 23，新 core 放進 SoC 之前先單獨 harden，看全部 signoff corner 的 STA（Phase 5 直接在 SoC 裡換，harden 5 次才 PASS）；換任何 core 都適用。
  - 已知限制：2port 沒有用（ADR-0011 選 1port 加 bridge）；riscv-arch-test 與 Hazard3 上游的 formal 在本機沒跑過。
- **不在這裡**：SoC 驗證的一般寫法看 dv-directed-tests、gate-level-simulation；SRAM 整合看 hard-macro-integration，換 macro 的檢查清單看 macro-qualification。
- **本 repo 實例**：ADR-0011～0014、`rtl/cpu/`、`dv/core_hazard3/`（`make core-hazard3`）、`signoff/limits/soc_top_hazard3.toml`、`signoff/golden/soc_top_hazard3/`、`docs/phase_exit/phase5.md`（Phase 5）。

#### tapeout-precheck-caravel：ChipFoundry precheck 的執行與結果判讀

- **名詞**：Caravel 是 ChipFoundry 的 harness 晶片，pad、電源、管理用 RISC-V 都做好了，使用者的設計放在 `user_project_wrapper`（2920 × 3520 µm）；precheck 是 ChipFoundry 收件前的自動檢查（`cf precheck`）。
- **何時用**：跑或判讀 precheck；precheck 和 flow 的結果不一致；wrapper 設計第一次試跑的 harden 完成後。設計放進 wrapper 的做法看 caravel-user-project-integration（2026-10-15 拆出，ADR-0021 決定 5）。
- **重點**：
  - precheck 一定用 Docker 跑官方 image，只有 linux/amd64，Apple Silicon 要用 VM＋Rosetta 模擬（本 repo 用 lima，docker context `lima-cf-precheck`）；容器每次會升級 `cf-precheck`，每次要記下版本（`make precheck-check` 比對 `CF_PRECHECK_VERSION`）。只有官方 image 的結果算正式結果。
  - VM 記憶體不夠時，`klayout_beol` 報 `stat=-9`、LVS 報 `extraction did not complete successfully`、OEB 報 `stat=5`；先看 VM 的 `dmesg` 有沒有 OOM kill（本 repo 的 wrapper 要 16 GiB，`env/check_env.sh` 在 `make regress-caravel` 時要求 ≥ 15 GB）。
  - precheck 內建的 KLayout deck 比 flow 用的新：flow 的 KLayout DRC 是 0，precheck 不一定過。每顆 macro 先用 precheck 的 deck 單獨跑一次。
  - OpenRAM bitcell（包括 PDK 附的 `sky130_sram_*`）在新 deck 報 `MR_mcon.CON.10` 與 `MR_licon.SP.6`：2026-05 的 deck 拿掉了 SRAM 核心區（`areaid.ce`）的例外，沒有參數能關。本 repo 的 PASS 條件是只允許這兩條、而且要和 PDK 附的 macro 一致（ADR-0019 決定 5）：`make precheck-check` 把違規展開到相對 bitcell array 的位置再比，植入錯誤 `make neg-precheck`（案例表在 `signoff/precheck/neg_precheck.py`）；precheck 所用 PDK 附的 SRAM 本身另有 nsdm／psdm 的 FEOL 違規，比對基準只比允許的這兩條（決定 24）。向 ChipFoundry 反映的草稿到 Phase 7 結案仍沒送出。
  - LVS 是電晶體層級，SRAM 用 `EXTRACT_ABSTRACT` 當 black box；LVS log 結尾的 `possible errors ... CVC` 是 SRAM 輸出被當成沒人驅動，LVS 本身仍是 PASS。
  - precheck 的報表要綁到這一次的 GDS：讀到前一次 run 的報表也會 PASS；`make precheck-check` 比對 GDS sha1、`input_file_hash` 與 `logs/gds.info`（規則 12，`neg-precheck` 的 `stale_results`）。
  - 2026-10-14 官方 image 的正式結果是 PASS（13 項中 11 項 PASS，FEOL／BEOL 只有 SRAM 的兩條規則）。
  - 提早檢查（流程回顧，ADR-0020）：規則 11，第一次試跑的 harden 完成後，就用試跑產生的 GDS 跑一次完整 precheck、量 VM 記憶體，密度上下限做成 harden 內的 checker（留到下一個專案）。
- **不在這裡**：wrapper 範本、GPIO、供電、li1 與 fill（caravel-user-project-integration）；macro 本身的 view QA（macro-qualification）；DRC、LVS 的一般做法（drc-signoff、lvs-signoff）。
- **本 repo 實例**：ADR-0019、`docs/notes/caravel_precheck_phase7.md`、`signoff/precheck/`（Phase 7）。

#### caravel-user-project-integration：放進 Caravel user_project_wrapper

- **何時用**：把設計放進 `user_project_wrapper`、選 GPIO、算供電與 IO constraint；選定下線服務商時做下線規定對照表；看到 `PDN-0239`／`GRT-0036` 警告或 `li1.pd.1d`；寫 management SoC 的韌體要做 GPIO 設定傳送（`reg_mprj_xfer`），或傳送後 user 輸出腳沒訊號。2026-10-15 從 tapeout-precheck-caravel 拆出。
- **重點**：
  - pad 與 wrapper 腳位位置都是固定的，能選的只有用哪幾支 GPIO：先依 Wishbone（下側偏左那一段）定 block 位置，再挑最近的 GPIO，最後才寫 wrapper RTL（Phase 7 順序做反了，重做一次）。規劃與核准的做法看 chip-floorplan-pin-planning。
  - `wb_clk_i` 是管理用 CPU 的核心時脈（外部時脈或 PLL 除頻）：設計的週期就是管理端時脈的下限；wrapper 的 IO constraint 用官方 wrapper SDC 的數值（見 timing-constraints-sdc）。
  - user area 的供電：vccd1、vssd1 各只有一顆 pad（右側），經 Caravel 5 µm 的 met4 ring 與只在 wrapper ring 左右兩側的 met3 電源連接線進來；wrapper 的電源 pin 不能當理想電源，IR 要從 pad 起算，電流用 max power pattern 量（ADR-0019 決定 18–20）。
  - wrapper 頂層放標準 cell 時，PDK 預設的 `decap_3` 把空白填滿，li1 密度超過 60%（`li1.pd.1d`）；改用 `sky130_ef_sc_hd__decap_12` 與 fill（ADR-0019 決定 24）。
  - `PDN-0239`、`GRT-0036` 是範本的 ring 與腳位畫到 die 外造成的預期警告，不要為了消警告改範本（precheck 的 `xor` 會 FAIL）。
  - metal fill 由下線服務商在 tapeout 時補，補完另有 `check_density.py` 的下限（li1、met1–4 ≥ 35%、met5 ≥ 45%、FOM ≥ 33%），precheck 不查；本 repo 的試跑在左下角 SoC 與 SRAM 一帶有 window 低於下限，要向下線服務商書面確認（「待確認」，ADR-0019 決定 26）。
  - XOR、GPIO 設定、`io_oeb` 的實體接線都實際跑過、PASS；違反時會不會 FAIL 還沒有實際試過。
  - management SoC 的韌體做 GPIO 設定傳送（`reg_mprj_xfer`）時，housekeeping 用自己存的值覆蓋全部 38 支 pad，那份值的 reset 值全是 management mode：`user_defines.v` 設成 user mode 的腳，傳送前要先寫回同樣的值，不需要就不要傳送。傳錯時 user 輸出腳沒訊號、輸入腳的下拉消失；拉 `resetb` 救不回來，要重新上電、用正確的設定再傳一次，或用 bit-bang 把 `serial_resetn` 拉低一次（規則 8，2026-10-16 用模擬前後比較確認，ADR-0022）。沒有自動檢查：management SoC 的韌體不在 repo，regression 也只模擬到 wrapper（2026-10-16 的 Caravel 模擬是一次性的實驗）。
  - 經驗紀錄（2026-10-16）：Caravel 的 `wb_rst_i` 由 `caravel_clocking` 的 reset synchronizer 產生，拉起是非同步的，在核心時脈的下降緣放開；STA 的半週期 input delay 只檢查放開，SRAM 的 `csb0` 也受非同步拉起影響（推論）。下一個專案建議在 wrapper 內對 `wb_rst_i` 加 2 顆 flop 的同步器（ADR-0022）。
  - 提早檢查（流程回顧，ADR-0020）：規則 5，選定下線服務商時做下線規定對照表（precheck 的每一項檢查、wrapper 的 IO constraint、供電、fill 與密度上下限、下線服務商用的 PDK 與工具版本都算到本設計的數字），需要下線服務商回覆的問題當天送出；規則 6，採用官方的 wrapper SDC 前先試算 input transition 與 IO 路徑的 hold。
- **不在這裡**：precheck 的執行與結果判讀（tapeout-precheck-caravel）；pad、block、pin 的規劃與核准（chip-floorplan-pin-planning）。
- **本 repo 實例**：ADR-0019、ADR-0022、`pnr/user_project_wrapper/`（`ir_caravel.py`、`caravel_pwr/`、`pin_plan.toml`）、`docs/notes/caravel_precheck_phase7.md`、`docs/notes/caravel_gpio_xfer.md`、`docs/notes/caravel_reset_and_mgmt_clock.md`、main worktree 的 `runs/p7_review/fill_trial/README.md`（不進版控）。

#### chip-floorplan-pin-planning：晶片層級的 pad、block 與 pin 規劃

- **何時用**：開新的頂層設計，或要決定、改變用哪幾支 pad／GPIO、block 與 macro 放哪裡；被 hook 或 `make pin-plan` 擋下時（「這份 pad／block／pin 規劃還沒經使用者核准」、`no approval`、`plan_sha256 differs`、`no pnr/<design>/pin_plan.toml`、ADR `has no line with the quote`）。
- **重點**：
  - 順序是 pad（含電源 pad 與電源進入點）→ block 位置 → pin 指定 → 頂層 RTL 的腳位對應 → harden。block 位置依有時序要求的介面定，pin 挑離 block 最近的。
  - 電源進入點和訊號 pad 一樣在 pad 階段查清楚：上層晶片（本 repo 是 Caravel）從哪幾邊、哪些點把電源接進來，查不到的列成幾種可能的電壓源位置，定 block 位置時一起考慮，採用的電壓源位置（signoff IR 用它）在核准規劃時一起決定，寫進 `pin_plan.toml` 的 `[power]`。Phase 7 到 harden 後才量，同一份 layout 只換電壓源位置 IR 差到 20 倍以上（數字在 ADR-0019 決定 18；signoff 已改用 slow corner 與 max power pattern，決定 19、20）。本 repo 的 `pin_plan.toml` 沒有 `[power]` 節，`check_pin_plan.py` 也還不看這一節，沒有自動檢查，下一個專案先擴充 checker。
  - 規劃寫在 `pnr/<design>/pin_plan.toml`。LibreLane 只跑到套用 DEF 範本（看腳位）或 global placement（看邏輯分布，幾分鐘）就出圖（`scripts/plot_floorplan.py`），連同規劃請使用者確認。
  - 使用者核准後，在 `[approval]` 填日期、原話、ADR 與規劃的 sha256；規劃之後再改，核准就失效。
  - 四層機制：規則（`CLAUDE.md` 規則 14）、規劃文件、checker（`make pin-plan`，harden 與 regress 都跑；植入錯誤 `make neg-pin-plan`，checker 與 hook 都測，目前 26 個案例，清單在 `scripts/neg_pin_plan.py`）、Claude Code 的 PreToolUse hook（核准前，編輯受 pin plan 控管的檔案會被擋下）。用 Bash 改檔 hook 看不到，要到 checker 才擋。
  - 看圖的陷阱：停在 PDN 的 DEF 還沒有範本腳位；範本套用後腳位是 `FIXED`；停在套用範本時 cell 還沒有位置；大的 wrapper 會鋪滿 tap cell。
- **不在這裡**：die 內的密度與壅塞看 floorplan-congestion；Caravel 的固定腳位座標與 GPIO 模式看 caravel-user-project-integration。
- **本 repo 實例**：ADR-0019 決定 10、12、13，`pnr/user_project_wrapper/pin_plan.toml`，`scripts/check_pin_plan.py`、`scripts/neg_pin_plan.py`、`.claude/hooks/require_pin_plan.py`。

### skill 的由來

- 最初 11 個依使用者要求，對應重大流程任務（CTS、LVS、DRC、IR、timing、EQY……）。
- `floorplan-congestion`、`timing-constraints-sdc`、`rtl-synthesis-lint` 是 2026-10-03 請 Gemini 3.8 Flash（Antigravity CLI）審查「還漏了哪些任務」後補上的。同一次審查建議的 `openram-macro-characterization`（Phase 3.5／6）、`core-migration-hazard3`（Phase 5）、`tapeout-precheck-caravel`（Phase 7），會在進入那個 Phase 時建立（`tapeout-precheck-caravel` 在 2026-10-12 Phase 7 開始時建立）；`openram-macro-characterization` 已在 Phase 3.5 開始時（2026-10-04）建立。
- 2026-10-15 問題總檢討（ADR-0021 決定 5）時，description 超過單份上限的三個 skill 依功能拆分：`openram-macro-characterization` 拆出 `openram-macro-generation`、`sram-layout-extraction`，`tapeout-precheck-caravel` 拆出 `caravel-user-project-integration`，`hard-macro-integration` 拆出 `macro-qualification`，共 27 個。
- 同一天（ADR-0021 決定 6）依使用者「整個流程可以分成Middle-end，backend，package 三大部分，每一部分各自搜尋相關的skill」，新增三個入口 `middle-end-flow`、`backend-flow`、`package-flow`，共 30 個；細部 skill 在清單只列名稱。
- `signoff-criteria` 是 2026-10-03 討論「clock 沒有 PLL，那 clock 從哪來」時，發現 signoff 條件多半沿用預設值、沒有推導，依使用者要求新增。
- 最後 4 個是 Phase 4（2026-10-04）依使用者要求，分析 Phase 4 的重大任務後新增的：一鍵 regression 與來源追溯、多 corner STA、directed 測試補缺口、Phase exit review。Phase 4 的其他任務（checker 漏洞、L5 模擬、IR、EQY、DRC 位置比對、signoff 條件、CTS 與 resizer margin）寫回既有的 skill。

### 在其他專案使用

開新專案時沿用這套流程的方法（入口、可直接沿用的骨架、要依新設計重做的、經驗寫回、新專案也要照做的 `CLAUDE.md` 規則）見 [arvinsa-rtl-gds-flow.md](arvinsa-rtl-gds-flow.md) 第 1、2 節。

## 授權

本 repo 的內容以 [Apache License 2.0](LICENSE) 授權。
之後引入的第三方元件保留各自的授權，例如 PicoRV32 為 ISC，Hazard3 與 sky130 PDK 為 Apache-2.0。
