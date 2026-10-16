# arvinsa-rtl-gds 流程（完整版）

這份文件是本 repo RTL-to-GDS 流程的完整說明，也是其他 IC 專案沿用這套流程時的入口（`CLAUDE.md` 規則 8）。README 只放簡易流程並指到這裡。

**各文件的分工**（同一件事只寫在一個地方）：

| 文件 | 放什麼 |
|---|---|
| 本文件 | 流程：做哪些步驟、順序、每一步的 checker 與 negative test、交給哪個 skill |
| [`CLAUDE.md`](CLAUDE.md) | agent 必須遵守的規則（本文件第 2 節只列摘要與編號） |
| `.claude/skills/<name>/SKILL.md` | 每類任務的規則、已知工具缺陷與對策、經驗紀錄；索引在 README「Claude Code skills」一章 |
| [`project-plan.md`](project-plan.md) | 本 repo 這顆 SoC 的計畫：各 Phase 的內容、exit criteria、negative test 總表 |
| `docs/decisions/`（ADR，architecture decision record：每個重大決定的選項、代價與使用者的選擇）、`pnr/*/README.md`、`docs/phase_exit/` | 本設計的決定、設定理由、數字、階段收尾 |
| [`toolchain.md`](toolchain.md)、`env/versions.mk`、[`env/setup.md`](env/setup.md) | 工具與 PDK 的版本、在新機器上建環境的逐步說明 |

本文件用到的名詞：
- **checker**：判 PASS／FAIL 的程式。
- **negative test（bug injection）**：故意植入一個錯誤，確認 checker 真的 FAIL；**positive test**：不植入錯誤時 checker 必須 PASS，證明它不是一直 FAIL。
- **golden**：確認過正確的一次 run 的完整 metrics，之後每次 harden 都逐項和它比對。
- **PVT**：製程 corner、電壓、溫度的組合，例如 `ss_n40C_1v60`；STA 的每個 corner 都對應一個 PVT。
- **lockstep**：RTL 與 netlist 同時模擬，每個 cycle 比對兩邊的訊號。

---

## 1. 在新專案使用

使用者的做法（2026-10-04）：開新專案時，請 Claude Code 或 Codex「使用 arvinsa-rtl-gds 這個 repo 的流程」。skill 不搬到使用者層，也不複製到新專案；新專案的 agent 直接讀這個 repo。

### 1.1 起手清單

1. **讀對的那一份**：GitHub `github.com/Jordanplus/arvinsa-rtl-gds` 的 main，或本機的 main checkout。不要讀 `arvinsa-rtl-gds-p5*` 這類舊的 git worktree，它們停在舊 commit，skill 是舊版。
2. **在新專案寫一份自己的 `CLAUDE.md`（Codex 是 `AGENTS.md`）**：寫一行「流程照 arvinsa-rtl-gds 的 `arvinsa-rtl-gds-flow.md`」，並把第 2 節的規則抄進去（或寫明照做）。只靠對話交代的話，下一次對話就忘了。
3. **照 4.0 建環境**，照 4.1 寫新設計的計畫（Phase、exit criteria、negative test 總表）。第 4 節標「目前沒有自動檢查，下一個專案開始時做成 checker」的提早檢查（ADR-0020 決定 2），在新專案第一次 harden 之前做成 checker 並加 negative test，排進計畫。
4. **需要沿用的程式複製進新 repo**（來源追溯要求所有用到的檔案都已 commit，不能從這裡引用），在新專案記下複製時本 repo 的 commit；複製後修掉的錯誤，通用的部分寫回本 repo。
5. 開始每一步之前，用 README 的「依情況找 skill」表找到 skill，讀對應的 `.claude/skills/<name>/SKILL.md`。

SKILL.md 是一般的 Markdown，任何 agent 都能讀。它們放在專案層：在本 repo（或它的上層目錄）開 Claude Code 才會自動列出，在新專案要明確叫 agent 來讀。在上層目錄開時，舊 worktree 裡的舊版 skill 也會一起列出，注意不要用到它們。

**Codex**：讀的是 repo 根目錄的 `AGENTS.md`；本 repo 的 `AGENTS.md` 指回 `CLAUDE.md` 與本文件，不另寫一份。

### 1.2 可以直接沿用的

寫法與程式都能直接用，只要換參數或路徑：
- `scripts/regress.py`：一鍵 regression（target 清單要換成新設計的）。
- `signoff/scripts/provenance.py`、`run_guard.py`：來源追溯（harden 只能在已 commit 的 working tree 上開，記錄工具與 PDK 版本），以及下游步驟拒絕用 FAIL 或別的 commit 的 run。
- `signoff/scripts/check_signoff.py` 加 `signoff/limits/*.toml` 的格式：signoff 門檻與 golden 比對。
- `pnr/librelane_flow.sh`：LibreLane 呼叫與有上限的重試。
- `pnr/librelane_plugin_arvinsa/`：不改 LibreLane、只換掉一個 step 的寫法（`meta.substituting_steps` 加 `PYTHONPATH`；ADR-0016 的 CTS）。
- `dv/scripts/dvlib.py`：模擬的 checker；`dv/monitors/gl_lockstep.v`：RTL 與 netlist lockstep。
- `signoff/eqy/`：EQY（formal equivalence check）與它的植入錯誤。
- `scripts/check_macro_views.py`（`gds_bbox.py`、`neg_macro_views.py`）：任何 macro 的 view QA，檔案路徑由參數指定，不綁特定產生工具。
- `env/versions.mk`、`env/check_env.sh`、`toolchain.md`：固定版本與環境檢查。
- `scripts/check_py_names.py`、`scripts/check_skills.py`：開跑前的快速檢查。

### 1.3 寫法可沿用，但要依新設計修改的

- `ip/sram/char/`：SRAM macro 的 ngspice characterization、.lib 產生、獨立重算與確認模擬。方法通用；程式只支援 OpenRAM 架構的 1rw1r、32 bit × 512 word（`sramchar.py` 的字寬、位址寬、netlist 縮減依 OpenRAM 的命名），macro 名稱與 netlist 可用環境變數 `SRAM_CHAR_MACRO`、`SRAM_CHAR_NETLIST` 換；其他容量或架構要改 `sramchar.py`。
- `signoff/scripts/review_criteria.py` 與 `.claude/hooks/require_criteria_review.py`：每次 harden 後的 criteria review 與強制它的 Claude Code Stop hook。設計名稱、run tag、要讀哪些 checker 的結果都寫在程式裡，要改。
- `scripts/progress.py` 加 `.claude/statusline-progress`：Claude Code 狀態列第二行的進度顯示（待辦清單 `runs/todo.md`，格式 `- [ ]` 待辦、`- [~]` 進行中、`- [x]` 完成；進行中的項目顯示它的子項目完成幾項，沒有子項目時算上層項目的子項目）。它判斷「執行中工作」的方式綁本 repo 的 target 與 run 目錄（regress、LibreLane 有百分比；其他 make target、直接執行的本 repo Python 腳本，以及本專案 Claude Code scratchpad 裡直接執行的 Python 腳本（例如 agent 的試跑）只顯示「執行中」與已跑時間；沒有固定總數的工作算不出百分比）。

### 1.4 只在使用者這台機器有的

換機器或用 Codex 時不存在，不要當成流程的一部分：
- 全域狀態列（claude-usage skill v1.6.0）與進度面板 mod（`/progress`，`~/.claude/skills/progress-pane/`），呼叫 `.claude/statusline-progress`／`--json`。
- 全域 PreToolUse hook `~/.claude/hooks/guard-bash.py` 與它讀的 `.claude/guard.json`：公開 repo 的推送內容不能有本機絕對路徑或機密、harden 要在已 commit 的 working tree 上開、force push 一律擋（使用者自己做）；「同時最多 2 個 LibreLane／EQY、可用記憶體至少 4 GB」是依這台 24 GB 機器訂的。

### 1.5 要依新設計重做的

- `pnr/<design>/config.json`、SDC、`signoff/limits/` 的數值，用 `signoff-criteria` 重新推導。
- `pnr/<design>/run.sh` 與設計專屬的 checker：本 repo 的 `check_inputs.py`（harden 前的輸入檢查）、`check_soc.py`（SRAM 的 placement、沒用到的 port 的接法、disconnected pin（沒接到任何線的 pin；Caravel wrapper：表上只能是設計沒用到的固定腳位，與 pin 規劃逐支相符）、STA 設定、max slew（外部 transition 驅動的 IO net 另外檢查）、macro clock 前有沒有 delay buffer、Magic DRC 對 SRAM 單獨的結果）、`sram_drc_alone.py`、`ir_worst.py`（最壞情況的靜態 IR）。重寫 `run.sh` 時，flow FAIL 也要照跑 repo 的 checker 與 criteria review（本 repo `pnr/soc_top/run.sh` 第 93–97 行；Phase 5 三次 Hazard3 run 在 LibreLane FAIL 後一支 checker 都沒跑；4.6）。
- golden。
- 和設計綁在一起的植入錯誤案例，例如 `pnr/soc_top/neg_pnr.py` 的 P00–P81（PnR 與 signoff checker 的植入錯誤）。
- ADR、exit review 的內容。

### 1.6 經驗寫回這裡

新專案用到某個 skill 時發現的通用經驗，寫回本 repo 的 `SKILL.md`；流程本身有改，寫回本文件。只屬於新設計的數字留在新專案的文件（`CLAUDE.md` 規則 8）。

## 2. 必須遵守的流程規則（全文在 `CLAUDE.md`）

`CLAUDE.md` 只在本 repo 自動載入；下列各條在新專案也適用，新專案的 agent 要先讀原文：

| 規則 | 摘要 |
|---|---|
| 1–3 | 做到 skill 涵蓋的任務，先讀該段的入口 skill（`middle-end-flow`、`backend-flow`、`package-flow`），依對照表找到細部 skill 的 `SKILL.md` 再讀；新現象寫進經驗紀錄；同一現象出現兩次以上或已用實驗確認，才搬進正式規則，推測不進正式規則 |
| 4 | 這顆設計的數字放 repo 文件；skill 只放能帶到下一顆設計的規則 |
| 5 | skill 有改，同一個 commit 同步 README 的 skill 一節與 `description`；新增或改名細部 skill 時，同時更新所屬入口的對照表與 `.claude/settings.json` 的 `skillOverrides`；跑 `make skill-check`（格式、索引、分段一致、長度） |
| 7（通用部分） | 進入沒有 skill 涵蓋的新類任務前（例如下線前的 precheck、換 PDK），先建立對應的 skill 再開始 |
| 8 | 通用經驗寫回本 repo，不把 skill 複製到新專案；流程有改，更新本文件 |
| 9 | 每次 harden 跑完（PASS 或 FAIL），先做 criteria review 再回報。本 repo 由 Stop hook 強制；新專案與 Codex 沒有這個 hook，要自行遵守，或在新專案裝同樣的 hook |
| 10 | 每個確認過的工具缺陷都要寫成對策：症狀（也寫進 description 與入口表）、怎麼發現、怎麼繞過、怎麼防止再發生（checker 或 negative test） |
| 11 | 目前 Phase 的待辦清單在 `runs/todo.md`，Phase exit review 寫完後清空 |
| 12 | 自己產生或收到的 macro 都要先做 view QA，才能交給 flow |
| 14 | pad（含電源 pad 與電源進入點）、block 位置、pin 指定先規劃並經使用者核准，才寫頂層 RTL 的腳位對應與 config（`package-flow` → `chip-floorplan-pin-planning`；本 repo 由 `make pin-plan` 與 hook 強制） |
| 13 | 要做選擇時（新 Phase 開始、改變已定的決定、工作中出現影響規格／量測方法／signoff 標準／時程的分岔）：先查證，列出選項、代價與建議，由使用者決定，再實作並記成 ADR（`docs/decisions/` 的每一份都是這樣產生的） |

另外一個貫穿全程的做法：每個 checker 都要有 negative test 與 positive test（`signoff-checker-qualification` 規則 7）。

## 3. 全流程總覽

**三段與入口 skill**：使用者 2026-10-15 決定：「整個流程可以分成Middle-end，backend，package 三大部分，每一部分各自搜尋相關的skill」（ADR-0021 決定 6）。每段有一個入口 skill，內容是「情況／錯誤訊息 → 細部 skill」對照表；細部 skill 在 Claude 的 skill 清單只列名稱（`.claude/settings.json` 的 `skillOverrides`），所以先讀入口。

| 段 | 入口 skill | 本文件的步驟 |
|---|---|---|
| Middle-end：RTL 到 netlist、constraint、macro 與 IP 準備、netlist 等價 | `middle-end-flow` | 4.2、4.3、4.5 的 SDC、4.7 的等價證明 |
| Backend：LibreLane harden、PnR 與實體 signoff | `backend-flow` | 4.4、4.5 的 signoff 條件、4.6、4.7 的 netlist 模擬 |
| Package：晶片層級、wrapper 與下線 | `package-flow` | 4.1 的下線規定對照表與 pad／block／pin 規劃、precheck |
| 跨段共用：checker 與 golden、一鍵 regression、Phase 收尾 | （直接讀，清單上保留描述） | 4.8、4.9，貫穿全程 |

新專案沿用時：
- 三個入口與 `skillOverrides` 一起帶過去，細部 skill 的歸屬照上表；
- 新增細部 skill 時，同時改所屬入口的表與 `skillOverrides`（`make skill-check` 檢查）。

下面的樹是各 skill 在流程中的位置。

```
環境與固定版本 ........................ （不做成 skill）toolchain.md、env/setup.md
規格與計畫 ............................ project-plan.md、ADR
 └ 操作條件對照表、corner 代價（提早檢查 A1、A3）... signoff-criteria
 └ 下線規定對照表（A2）.................. caravel-user-project-integration（用 Caravel 時）
 └ pad（含電源進入點）、block 位置、pin 指定（寫 RTL 前）... chip-floorplan-pin-planning
RTL：合成、lint ........................ rtl-synthesis-lint
 └ RTL 模擬與 directed 測試 ............ dv-directed-tests
 └ 換 CPU core ......................... core-migration-hazard3
macro 產生或取得（memory compiler、廠商 IP）
 └ 選定前的 go／no-go（B1：操作條件範圍內的 SPICE 讀寫、precheck 的 deck）... macro-qualification
 └ 用 OpenRAM 產生、判讀 DRC／LVS 結果 .. openram-macro-generation
 └ view QA（每個交付檔的內容）........ macro-qualification（規則 1）
 └ 整顆 macro 的 DRC ................... drc-signoff、openram-macro-generation（規則 6）
 └ layout 萃取（characterization 之前先試）.. sram-layout-extraction
 └ 各 corner 功能確認、SPICE characterization、.lib ... openram-macro-characterization
constraint 與 signoff 條件（第一次 harden 前）
 ├ SDC、corner ......................... timing-constraints-sdc、multicorner-sta
 └ signoff 門檻的推導 .................. signoff-criteria
harden（LibreLane）
 └ floorplan、macro、IO pin ............ floorplan-congestion（pad／block／pin 核准之後）、hard-macro-integration
    └ PDN .............................. pdn-ir-drop
       └ placement、resizer ............ drv-timing-closure、floorplan-congestion（密度）
          └ CTS ........................ cts-clock-tree
             └ routing、antenna ........ drv-timing-closure、antenna-signoff、floorplan-congestion（繞路）
signoff（harden 結尾自動執行）
 ├ STA ................................. multicorner-sta、timing-constraints-sdc、drv-timing-closure
 ├ DRC、XOR、密度 ...................... drc-signoff
 ├ LVS、連接性 ......................... lvs-signoff
 ├ IR（EM 目前沒有檢查）.............. pdn-ir-drop
 ├ golden 比對 ......................... signoff-checker-qualification
 └ 每次 harden 後的 criteria review ..... signoff-criteria
netlist 驗證
 ├ 等價證明 ............................ formal-equivalence-eqy
 └ netlist 模擬 ............................ gate-level-simulation、dv-directed-tests
一鍵 regression 與來源追溯 ............. flow-regression-reproducibility
階段收尾 ............................... phase-exit-review
貫穿全程 ............................... librelane-run-debug（執行與除錯）
                                         signoff-checker-qualification（checker、golden、植入錯誤）
放進 wrapper（Caravel user_project_wrapper）... caravel-user-project-integration
precheck（下線服務商收件前的自動檢查）... tapeout-precheck-caravel（本 repo Phase 7：Caravel、ChipFoundry precheck）
```

## 4. 逐步流程

每一步的格式：**做什麼**、**怎麼跑**、**PASS 條件**（checker 與 negative test）、**skill**。括號裡是本 repo 的 target；新專案照同樣的結構建自己的 target。

**提早檢查（A1–E3）**：2026-10-14 回顧 Phase 0–7（三個沒參與實作的 agent 讀 ADR、exit review、筆記與 git，報告在 [`docs/notes/flow_retro/`](docs/notes/flow_retro/README.md)），找出處理很久或必須放寬要求、其實應該早一點看的事，合併成 19 條提早檢查；使用者決定全部寫進流程（[ADR-0020](docs/decisions/0020-flow-shift-left.md)）。下面各步驟用「提早檢查 A1」這樣的標記，編號對應回顧 README 的表，每條寫做什麼、通過條件與本 repo 的例子。共同的教訓有五個：signoff 條件太晚定；下線服務商、library、macro 的 QA 太晚；下線服務商的規定只讀了項目名稱、沒有算到自己的數字；放寬的依據只在一個設計上量過；換東西時舊檢查沒有重套。能做成自動 checker 的幾條，使用者決定這次只寫進流程（ADR-0020 決定 2：Phase 7 在收尾，加 checker 要擴大範圍、延後 regress），各條寫明「目前沒有自動檢查，下一個專案開始時做成 checker」。時間與「省下多少」是從 commit 時間推算，只是粗估。

**貫穿全程：放寬清單**（提早檢查 E1，ADR-0020 決定 3；清單在 [`docs/relaxation_register.md`](docs/relaxation_register.md)）：
- 做什麼：每一項放寬或補償（加長週期、resizer 的 margin、golden 誤差、placeholder .lib、只檢查某個 corner、延後處理）在決定的同時記進放寬清單：原因、依據的量測、在哪個設計上量的、什麼情況要重新驗證、什麼條件下可以拿掉這項放寬。換設計、換 macro、或原因被修掉時，逐項做 what-if（多半只要重跑 STA 或 IR），能拿掉的放寬提給使用者決定。每次 criteria review（4.6）對照放寬清單。
- 通過條件：沒有「原因已經不在、卻沒評估」或「依據不是現在這個設計量的」項目。
- 本 repo 的例子：IR 只檢查 nom_tt、resizer 用 0.6 ns margin 代替 ss −40°C、golden 誤差，三項的依據都是在 PicoRV32 上量的，Phase 5 換成 Hazard3 時三項都失效（`docs/phase_exit/phase5.md`、ADR-0013、ADR-0015、ADR-0017）；週期 44 ns、hold margin 0.3 ns、PnR max transition 0.70 ns 的原因後來由 ADR-0014、0016 處理，設定沒有回頭評估（回顧 `retro_p35_5.md` #12，拿掉這些放寬的效果是推算的）。
- 自動檢查：沒有（放寬清單是文件；「依據的設計等於現在的設計」可以做成 checker，下一個專案開始時做）。

**本 repo 的設計選擇**：目前主要設計是 Hazard3 版 SoC。`CPU` 預設是 `picorv32`（`Makefile` 的 `CPU ?= picorv32`），所以 `fw`、`sim`、`regress-rtl`、`neg-rtl`、`synth-check`、`harden-soc`、`eqy-soc`、`neg-eqy-soc`、`gl-soc`、`gl-soc-powered`、`neg-gl-soc`、`neg-pnr`、`provenance-final` 要加 `CPU=hazard3`，否則跑的是 PicoRV32 版（run 在 `runs/soc_top`，Hazard3 版在 `runs/soc_top_hazard3`）。`make regress` 固定跑 Hazard3 版。

### 4.0 環境與固定版本

- 做什麼：所有工具、PDK、IP 固定在確切的版本或 commit，安裝方式可重現。
- 怎麼跑：逐步說明在 `env/setup.md`。`make nix-install`、`make flow-setup`、`make pdk-fetch`、`make xpack-fetch`（RISC-V toolchain，`core-hazard3` 要用）；macro 用 OpenRAM 產生時加 `make openram-setup`。版本在 `env/versions.mk`，說明在 `toolchain.md`（兩者由 `env/check_toolchain_doc.py` 檢查一致）。
- PASS 條件：`make env-check`（本機工具與 IP）、`make env-check-flow`（加上 Nix、LibreLane、PDK）；用 LibreLane 官方範例重跑一次當參考（`make ci-sram-ref`）。
- **參考設計當成工具預設值的 QA**（提早檢查 C2 的前半）：重跑官方範例時，它的每一個 DRV 違規（max slew、max cap、max fanout）都要查出原因，不能只比「和官方結果一樣」。
  - 通過條件：違規 0，或每個違規都有寫下的原因（例如某個設定沒開、某類 cell 太弱）。
  - 本 repo 的例子：Phase 0 的參考設計有 74 個 max slew、2 個 max cap 違規，因為和官方相符，只列出、不算 FAIL（`signoff/golden/ci_sram_ref/README.md`）；Phase 2 單獨 harden CPU 時試跑 9 次才找到原因：繞線前的寄生估計表 `LAYERS_RC` 沒啟用、被 resizer 當成一般 buffer 用的 clock 延遲 cell `clkdlybuf4s25_1` 沒排除（`docs/phase_exit/phase2.md` 第 37 行、`pnr/picorv32_core/README.md`）。
  - 後半（找出 drive 太弱的 cell，要涵蓋所有 signoff corner）在 4.5。
- skill：不做成 skill（`CLAUDE.md` 規則 6）；查 DRV 違規的原因看 `drv-timing-closure`。

### 4.1 規格與計畫

- 做什麼：規格（本 repo `docs/spec/`）、分 Phase 的計畫與每個 Phase 的 exit criteria（`project-plan.md` 第 8 章）、negative test 總表（第 7.3 節）。
- 重大選擇（PDK、core、SRAM、週期、corner、margin）由使用者決定，記成 ADR。
- **操作條件對照表**（提早檢查 A1，寫計畫時）：
  - 做什麼：晶片要操作的 VDD 範圍（最低、典型、最高）與接面溫度 Tj 範圍，從下線服務商的規格取得，由使用者決定並記 ADR。STA 的 corner 清單由它推出：先掃描 PDK 所有 .lib，比較同一電壓、不同溫度的延遲，有 temperature inversion（低電壓時低溫反而比較慢）就把那個 corner 放進清單（`signoff-criteria` 的「PVT corner」一列）。再逐一對照每個 macro／IP 與 standard cell library **已驗證**的範圍：晶片實測的條件、廠商或 memory compiler 做 characterization 的 corner、.lib 是 SPICE 模擬量出來的還是解析模型（公式估算）。
  - 通過條件：每個 corner 都對應到規格的某個角落；規格裡沒被驗證涵蓋的範圍，列成「選定前要確認」，交給 4.3 的 go／no-go（B1）。macro 在某個 corner 不能動時，不要因此拿掉 corner：corner 由操作規格決定，要縮小操作規格（例如只在室溫、最低 1.8 V 操作）由使用者在這一步決定並寫進 ADR 與使用限制。
  - 本 repo 的例子：計畫第一版就寫了 OpenRAM 1 KB macro 的晶片實測只在 ≥1.7 V 不出錯（`project-plan.md` §5.4），比 ss corner 的 1.60 V 高，這個落差在 Phase 0 就看得到；SRAM 的低溫讀取失敗到 Phase 3.5 做 characterization 才發現（ADR-0010），同一顆 SRAM 在 ss 25°C 1.60 V（不是 STA corner）也讀錯，所以拿掉 ss −40°C corner 救不了它（回顧 README「使用者的例子」）。ss −40°C 是為了標準元件的 temperature inversion 與 Caravel Tj −40°C 在 Phase 4 加的（ADR-0004、`docs/notes/signoff_criteria_soc_top.md`），和 SRAM 無關。
- **下線規定對照表**（提早檢查 A2，選定下線服務商時）：
  - 做什麼：precheck 的每一項檢查、wrapper 的 IO constraint（input transition、IO delay、clock source latency）、供電結構（電源 pad 數量與位置，見本節最後一點的 pad 規劃）、fill 由誰做與密度的上下限、下線服務商用的 PDK 與工具版本，逐條算出「對本設計是多少」，和本設計的 signoff 上限並排。下線服務商的工具或 PDK 版本和 flow 不同的，寫明以誰的結果為準，並用下線服務商的版本另取一份它會用到的 macro（例如 PDK 附的 SRAM）。需要下線服務商回覆的問題（已知 deck 問題、自己產生的 macro 的 DRC 怎麼看、fill 誰做）當天送出，記下送出日期與回覆。
  - 通過條件：每一條都有數字，或寫「待查，在哪一步查」；有衝突的（例如官方 input transition 超過自己的 slew 上限）在第一次 harden 前已列選項、由使用者決定；每個問題是「已送出（日期）」或「使用者決定不送（原話）」。
  - 本 repo 的例子：Phase 7 的 Caravel 單顆 vccd1 pad、官方 SDC 的 input transition 0.84–0.97 ns 超過 0.70／0.75 ns 的上限、IO 路徑的 hold、預設 `decap_3` 讓 li1 密度 75%、precheck 用的 PDK 附的 SRAM 另有違規、metal fill 誰補，全部在 harden 之後才發現，粗估重做約 2 天、3 項放寬（ADR-0019 決定 16–20、24；回顧 `retro_p6_7.md` #2–#10）；這些每項試算只要 10 分鐘到半天。給 ChipFoundry 的 issue 到 Phase 7 結案仍是草稿（ADR-0019 決定 26）。
  - 自動檢查：沒有（對照表與問題清單是文件）。用 Caravel 時，做法在 `caravel-user-project-integration` 規則 5。
- **corner 代價 what-if**（提早檢查 A3，第一份 netlist 出來之後；本 repo 是 Phase 2 單獨 harden CPU 時）：
  - 做什麼：用同一份 layout 只重跑 STA（`multicorner-sta` 規則 5），列出每個「決定週期」的 corner 的代價：有它和沒有它時的最小週期差多少，交給使用者確認操作規格。
  - 通過條件：每個會決定週期的 corner 都有代價數字，使用者確認過規格（記 ADR）。
  - 本 repo 的例子：週期三次加長（40 → 42 → 43 → 44 ns）都由 ss −40°C 決定，當時 ss 100°C 分別還有 +0.07、+0.47、+0.955 ns（ADR-0004 的三段補充；回顧 `retro_p35_5.md` #3）；原因是標準元件與 clock tree 的 temperature inversion，不是 SRAM。
- 晶片層級的規劃要在寫 wrapper RTL 之前做，順序是：pad／wrapper 腳位（含電源 pad 與電源進入點）→ block 位置 → pin 指定（使用者 2026-10-12：「block擺放位置應該在後段開始前就應該先確認之後出pin決定好」）。電源從 wrapper 的哪幾邊、哪些點進來，在 pad 階段就查清楚，查不到的列成幾種可能的電壓源位置，定 block 位置時一起考慮，採用哪一種（signoff IR 用它）在核准規劃時一起決定（使用者 2026-10-12：「Caravel pad都是固定，應該早就要決定可以有哪些供電選擇」；Phase 7 到 harden 後才量，用 ff 電流加 ss 電阻悲觀估算，整圈供電 6.87 mV、只從上側 143 mV；signoff 已改用 slow corner 與 max power pattern）。wrapper 的腳位位置固定時（本 repo Phase 7 的 Caravel：pad 與 wrapper 腳位都固定，XOR 檢查），pin 指定就是選用哪幾支 GPIO：先依有時序要求的介面（Caravel 是 Wishbone）定 block 位置，再挑離 block 最近的 GPIO（`caravel-user-project-integration` 規則 1）。
  - 規劃寫在 `pnr/<design>/pin_plan.toml`，LibreLane 只跑到套用 DEF 範本或 global placement 就出 floorplan 圖，連同規劃請使用者核准；核准前 Claude Code 的 hook 擋下這份規劃 `[governs]` 列出的檔案（頂層 RTL、腳位定義、DEF 範本等）的編輯，LibreLane config 只在改到擺放或腳位的設定（`MACROS`、`FP_DEF_TEMPLATE`、`DIE_AREA`、`FP_PIN*` 等）時才擋，`make pin-plan` 在 harden 與 regress 擋下沒核准或與規劃不符的設計（植入錯誤 `make neg-pin-plan`）。核准的版本要記在 ADR：同一行寫使用者原話、日期與規劃的 `plan_sha256`，只改規劃檔裡的 digest 不算核准（Phase 7 審查）。做法在 skill `chip-floorplan-pin-planning`（使用者 2026-10-12，ADR-0019 決定 13）。採用的電壓源位置也要寫進規劃（`pin_plan.toml` 的 `[power]`；本 repo 沒寫，目前沒有自動檢查，`chip-floorplan-pin-planning` 規則 2）。

### 4.2 RTL 與 RTL 驗證

- 怎麼跑：`make lint`、`make synth-check`、`make fw`、`make regress-rtl`（Icarus 與 Verilator）、上游 core 的測試（`make core-stock`、`make core-hazard3`）。
- PASS 條件：每個 test 都是 self-checking；`make neg-rtl` 對每個植入錯誤都要 FAIL。
- 晶片層級的 wrapper（本 repo Phase 7：Caravel `user_project_wrapper`）：同一組測試透過 wrapper 再跑一次（`make regress-rtl-caravel`，host port 走 Wishbone），wrapper 自己的接線另有 checker（`caravel_pins`）與植入錯誤（`make neg-rtl-caravel`，W01–W06）。regression 不涵蓋全晶片的 GPIO 設定（testbench 直接拿 wrapper 當 DUT，沒有 management SoC 與 housekeeping；2026-10-16 只做過一次性的模擬，`docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/`，不在 `make regress` 裡）；management SoC 的韌體做 GPIO 設定傳送的規則見 `caravel-user-project-integration` 規則 8，目前沒有自動檢查（ADR-0022）。
- RTL testbench 也要請沒寫它的 agent 做植入錯誤審查，對照 `signoff-checker-qualification` 漏洞類型表的「測試被縮水或跳過，仍判 PASS」「只比最終結果，中間的介面錯誤互相掩蓋」（本 repo Phase 1 兩輪審查各漏 10 個植入錯誤，`docs/phase_exit/phase1.md`）。
- 參數一致：harden 用的 `SYNTH_PARAMETERS` 要等於 SoC 裡該 instance 的參數；checker 遇到 config 的 `pdk::`／`scl::` 條件區塊就 FAIL，不猜（`rtl-synthesis-lint` 規則 1）。
- skill：`rtl-synthesis-lint`、`dv-directed-tests`；換 core 時 `core-migration-hazard3`。

### 4.3 macro：取得或產生、QA、characterization

**SRAM 的來源：建議一開始就用 OpenRAM 自己產生，不要先用 PDK 附的再換**（使用者 2026-10-10：「直接使用已經有的OpenRAM macro，其實還是用自己產生的也沒慢多少」；依據是本 repo 一顆設計的經驗，下一顆設計要再確認）：
- 花時間的工作兩種都要做：每個 PVT 的 SPICE characterization、view QA、換進 SoC 後的 signoff。PDK 附的 macro，.lib 是解析模型，一樣要自己量（Phase 3.5，2026-10-04 到 10-05）。
- 自己產生多出來的是一次性成本：OpenRAM 環境、DRC／LVS 對照、工具的小毛病（LVS 元件改名、LEF 單位 `ODB-0292`、netlist 沒有 `PININFO`）。本 repo 在 2026-10-08 一天內完成環境、產生、DRC／LVS 與讀取修正；這些現在都是 `openram-macro-generation`、`macro-qualification` 的規則與 checker。
- 自己產生才修得了電路：sky130 PDK 附的 2 KB SRAM 在 ss −40°C 讀出前一次的值，Phase 3.5 只能給 placeholder .lib、列為下線風險；用 OpenRAM 產生時加了 sense amp 輸入端預充電（ADR-0018 決定 8），5 個 PVT 都讀對。沒用到的 port 的時脈接法、量測的功耗、外框尺寸也因為有產生流程才查得清楚。
- 本 repo 的歷程（ADR-0007、0010、0018）：Phase 3 PDK 附的 SRAM＋保守 .lib → Phase 3.5 用 SPICE 量的 .lib → Phase 6 換成 OpenRAM 產生的，同樣的 characterization 與整合做了兩次。

0. **選定 macro 之前的 go／no-go**（提早檢查 B1；原本放在第 4 項「取得 macro 之後」，ADR-0020 移到這裡）：寫進計畫之前，先證明這顆 macro 在晶片要操作的整個範圍能動，而且過得了下線服務商的 DRC。
   - 做什麼：用廠商或 PDK 附的電晶體級 netlist（和 GDS 同一顆電路），在 4.1 操作條件對照表（A1）的每個 PVT 條件做 SPICE 讀寫：每個 STA PVT、corner 之間的溫度（例如 ss 25°C）、最低供電（下線服務商規格的下限，例如 Caravel 1.62 V，以及 ss corner 的 1.60 V）。測試序列要有「連續兩次讀到相反的值」與「寫入後馬上讀」，沒用到的 port 照實際 SoC 的接法；同時記下輸出在 clock 兩個邊緣之後的波形（.lib 需要的 timing arc，例如 OpenRAM SRAM 的 `rising_edge` hold arc）。縮減版 netlist 要先在一個點和完整 netlist 對照。另外用**下線服務商的 DRC deck**（不只 flow 的 deck）單獨檢查 macro（`tapeout-precheck-caravel` 規則 2）。整條做法在 `macro-qualification` 規則 2。
   - 通過條件：每個 PVT 條件都讀寫正確；下線服務商的 deck 報的每個違規都有原因與比對基準（例如下線服務商所用 PDK 附的 macro 在同一個位置也有）。有任何一點失敗，先列選項（換 macro、自己產生並修電路、縮小操作規格）由使用者決定並記 ADR，再整合。
   - 本 repo 的例子：PDK 附的 2 KB SRAM 在 ss −40°C、tt −40°C 與 ss 25°C 1.60 V 都讀成前一次的值（ADR-0010），netlist 從 Phase 0 就在 PDK 裡，卻到 Phase 3.5 做 characterization 才發現；結果 Phase 3.5–5 帶著 placeholder .lib、Phase 6 改用 OpenRAM 產生並修讀取電路（ADR-0018 決定 8），characterization 與整合做了兩次。回顧推算第一次做約半天到一天（縮減版 netlist 每個 PVT 幾分鐘到幾十分鐘）。precheck 的 deck 對任何 OpenRAM bitcell 報 `MR_licon.SP.6`、`MR_mcon.CON.10`，deck 在 2026-05 改的，比本專案開工早，到 Phase 7 才看到（ADR-0019 決定 5）。
1. **取得或產生**：PDK 附的 macro、memory compiler（本 repo：OpenRAM，`make openram-macro`）、廠商 IP。產生工具自己的 DRC／LVS 要讀報告判斷，不能只看 exit code（OpenRAM 在 LVS 不一致時仍 exit 0，`openram-macro-generation` 規則 2）。本 repo 的 negative test `make neg-openram` 涵蓋 OpenRAM 執行結果、安裝、patch、macro DRC 比對、.lib 範本，以及 OpenRAM 產生的 macro 做 characterization 用的來源。
2. **view QA**（`CLAUDE.md` 規則 12，`macro-qualification` 規則 1）：`scripts/check_macro_views.py` 檢查 LEF、.lib、Verilog、SPICE、GDS 的名稱、腳位與方向一致，.lib 數值範圍與面積，LEF 尺寸等於 GDS 外框，LEF 的資料庫單位與 `FOREIGN`（缺 `FOREIGN` 時 KLayout 輸出的最終 GDS 裡 macro 是空的，也沒有錯誤訊息），以及 LEF 與 GDS 的幾何：每支腳位的 GDS 文字落在該腳位同層的 LEF RECT 裡、繞線金屬在 LEF 的 OBS 與腳位內（LVS 只透過 LEF 看 macro，腳位位置錯了 flow 的每個檢查都看不到）。產生鏈上的中間檔（例如 .lib 範本）也要能對回它的來源。harden 後再用 `scripts/check_macro_gds.py` 比對最終 GDS 的 macro 與 macro 自己的 GDS（本 repo `check_soc.py macro_gds`）。產生 macro 的 target 要接這一步；整合中的 macro 用 `make macro-views`。FAIL 的 view 修正或替換後重跑到 PASS，做法記進該 macro 的 README 或 ADR。negative test：`make neg-macro-views`。
   - **.lib 輸出的驅動能力**（提早檢查 B3，`macro-qualification` 規則 3）：從 macro .lib 輸出 timing arc 的延遲表算等效驅動電阻（延遲變化 ÷ 負載變化），和標準元件的範圍比；延遲表要隨負載單調不減。通過條件：落在標準元件的範圍內；植入一份斜率過大的 .lib 必須 FAIL。本 repo 的例子：Phase 3.5 的 SRAM .lib 延遲表斜率等於 60–140 kΩ 的 driver，`repair_design` 跑 75 分鐘後異常結束，用 4 種 .lib 各單獨重跑這一步才找到原因（ADR-0010；`openram-macro-characterization` 規則 14）。目前沒有自動檢查（`check_macro_views.py` 沒有這項），下一個專案開始時做成 checker。
3. **整顆 macro 的 DRC**：用 full 規則，和已知 baseline 按規則種類分別比較，不只比總數：不能出現 baseline 沒有的規則種類，每一種的違規區域（相接的 DRC marker 合併後的塊數）不能超過 baseline，面積只容許 Magic 把違規切成幾個 marker 造成的微小差異（本 repo 0.05%）。不比 marker 數：Magic 會把同一個違規切成幾個 marker，怎麼切隨 cell 的座標變（本 repo OpenRAM 產生的 SRAM 有 3 種規則多了幾百個 marker，合併後與 PDK 附的那顆完全相同，ADR-0018 決定 19）（`ip/sram/openram/macro_drc.py`；negative test 在 `neg-openram` 的 D 系列，案例表在 `ip/sram/openram/neg_openram.py`）。再用 flow 簽核用的 KLayout deck 跑整顆 macro，要 0（`macro_klayout_drc.py`，`neg-openram` 的 K 系列）：memory compiler 的 DRC 與 Magic deck 都沒報的錯誤，macro 進了晶片才被 flow 的 KLayout DRC 抓到（本 repo：nwell.6、psdm.1、m2.2，ADR-0018 決定 17）。deck 若依名稱排除某些 cell（sky130：`*sky130_sram_*kbyte_*`），macro 不能取這種名字（`openram-macro-generation` 規則 6）。
4. **每個 corner 的功能確認**：主要的檢查已移到第 0 項（選定之前）。這裡在實際交付的 netlist 上重跑同一套序列：產生或取得的電路和第 0 項模擬的不是同一份時（自己產生、加了 patch、換了設定），一定要重跑（本 repo Phase 6：OpenRAM 產生的 macro 照預設設定也讀錯，修讀取電路後 7 個條件重跑才讀對，ADR-0018 決定 8）。先證明 macro 在每個 STA corner、corner 之間的溫度與最低供電都讀寫正確，再談時序。不能動的 corner 用 placeholder .lib（檔案裡標明 PLACEHOLDER），列為下線風險（這是第 0 項由使用者決定接受風險之後的做法）。沒用到的 port 照實際 SoC 的接法模擬（OpenRAM SRAM 沒用到的 port，時脈腳也要給時脈，ADR-0018 決定 9）。
5. **SPICE characterization**：**開始之前先試 layout 萃取**（提早檢查 B2）：從 GDS 萃取含走線寄生的 netlist（Magic 用 flat 輸出 `ext2spice hierarchy off`，並檢查沒有總電容為負的節點，`sram-layout-extraction` 規則 2；整條做法在該 skill 規則 3），能模擬就直接用萃取 netlist 做 characterization；只能用 schematic netlist 時，寄生的倍數用萃取量到的值，不用假設。通過條件：萃取 netlist 在 tt、最慢的 ss、最低溫的 ss 讀寫正確；.lib 的延遲與 transition 不低於萃取值。本 repo 的例子：Phase 3.5 假設寄生 × 1.6，Phase 6 最後才萃取，實際是 2.0 倍；dout0 transition .lib 寫 0.5 ns、實際 1.4–2.2 ns，Phase 7 wrapper 換成實際值後最差 setup 從 +0.548 剩 +0.151 ns，使用者選擇不重新產生 .lib、寫進已知限制（ADR-0018 決定 20；回顧 `retro_p6_7.md` #15）。萃取試跑約 3 小時。
   之後：延遲、setup／hold、最小週期與 pulse width、internal power，每個 PVT 一份 .lib。量測方法先驗證誤差，再用植入錯誤證明量得對（`make neg-char`），最後在 .lib 採用的數值上跑確認模擬（`make sram-confirm`／`openram-confirm`），並由不 import 產生器的程式獨立重算（`check_char_lib.py`：每次 `harden-soc` 開頭由 `check_inputs.py` 執行，PDK 附的與 OpenRAM 產生的 macro 都是；產生 .lib 之後也可以單獨跑，OpenRAM 產生的 macro 用 `make openram-check-lib`）。characterization 本身用 `make sram-char`／`openram-char`。internal power 與漏電也用 SPICE 量（OpenRAM 產生的 macro：`make openram-power`，再 `make openram-lib` 寫進 .lib），不用 memory compiler 的解析值；漏電要在所有 port 都 precharge、時脈停住的待機狀態量；單顆 bitcell 的漏電 deck 要把 ngspice 的 gmin 調小並用再小 10 倍的值核對（`bitcell leakage depends on gmin`，`make neg-char` N21），量測區間內的平穩度只放行小幅下降（`openram-macro-characterization` 規則 25、28）。沒用到的 port 在 SoC 接法下可能浮接、漏出額外的靜態電流，它不進 .lib，要另外記錄並列為已知限制（`openram-macro-characterization` 規則 25）。量測的週期、輸出負載與 input slew 要涵蓋 SoC 實際的工作點，.lib 的 `min_capacitance`／`max_capacitance` 設成做過 characterization 的範圍，否則 STA 外插、也不警告（`openram-macro-characterization` 規則 30）。
6. **換 macro 時的檢查清單**（提早檢查 B4，`macro-qualification` 規則 4）：
   - 做什麼：之前對舊 macro 做過的每一項檢查（不論在哪個 Phase、是不是 checker），對新 macro 逐條重跑一次，列成清單附結果。每支會碰到 macro 的 checker（EQY、DRC 位置比對、最終 GDS 比對、STA 讀的 .lib），在第一次 positive run 印出它讀到的 macro instance 與內容摘要，確認比對的對象不是空的。macro 換名稱時，搜尋 repo 中用舊名稱或名稱 prefix 辨認 cell 的腳本（`macro-qualification` 經驗紀錄 2026-10-10）。
   - 通過條件：清單逐條 PASS；每支 checker 的 positive run 都印出 macro instance。
   - 本 repo 的例子：Phase 0 就確認過 PDK 附的 SRAM 的 LEF 有 `FOREIGN`（`docs/phase_exit/phase0.md`），Phase 6 換成 OpenRAM 產生的 macro 時沒重查，最終 GDS 裡的 SRAM 是空的，flow 的 log 還印 `All LEF cells have matching GDS cells`，第一輪 harden（兩個 CPU）白跑（`macro-qualification` 規則 1 與經驗紀錄）；第二輪又因為 flow 的 KLayout deck 到這時才對 SRAM 檢查而白跑（ADR-0018 決定 17，第 3 項的「再用 flow 簽核用的 KLayout deck 跑整顆 macro」就是為此加的）；EQY 的 netlist 解析只認 `sky130_` 開頭的 cell，SRAM 的 clock 檢查在 Phase 6 步驟 4a–4c 一直被略過照樣 PASS（`docs/phase_exit/phase6.md`）。
   - 自動檢查：部分 checker 已會擋空的比對對象（`formal-equivalence-eqy` 規則 5、`check_soc.py macro_gds` 與 `magic_drc` 的下限）；「舊檢查逐條重跑」本身目前沒有自動檢查，下一個專案開始時做成 checker。
- skill：`macro-qualification`（go／no-go、view QA、換 macro）、`openram-macro-generation`（用 OpenRAM 產生）、`sram-layout-extraction`（萃取）、`openram-macro-characterization`（characterization 與 .lib）、`drc-signoff`、`hard-macro-integration`（接進 flow）；下線服務商的 deck 看 `tapeout-precheck-caravel`。

### 4.4 子區塊單獨 harden（選用）、換 core、定 die 時的 floorplan 試跑

- 做什麼：先單獨 harden 一個主要區塊（本 repo：PicoRV32），確認 RTL 到 GDS 的流程能完整跑完，並取得面積與時序實際跑出來的數字，估計 SoC 的 die 尺寸（`make soc-area`）。
- 開跑前：4.5 的 signoff 條件要先定好（提早檢查 C1：「第一次 harden」包括這裡的子區塊 harden），resizer 看的 corner 也照 4.5 的 C3。
- 怎麼跑：`make harden-core`；之後 `make gl-core`、`make eqy-core`。
- PASS 條件：同 4.6、4.7；negative test `make neg-gl-core`、`make neg-eqy-core`。
- **換 core 時新 core 先單獨 harden**（提早檢查 D3；換 core 時這一步不是選用）：
  - 做什麼：新 core 單獨合成並 harden（至少在合成 netlist 上跑全部 signoff corner 的 STA），列出低溫 ss 對高溫 ss 延遲比例最大的長路徑，再放進 SoC。
  - 通過條件：目標週期在所有 signoff corner 都 PASS，或已知差多少、進 SoC 之前由使用者決定。
  - 本 repo 的例子：Phase 5 直接在 SoC 裡換上 Hazard3，harden 1–5 依序是 resizer 停不下來、−4.158 ns、−0.381 ns（週期 44 ns）、−1.131 ns、PASS；exit criteria「flow 設定只需改 design 層」沒達成，使用者接受為與計畫不同（ADR-0012、0013、0014；`docs/phase_exit/phase5.md`）。單獨 harden 一次約 30–40 分鐘（回顧推算）。做法看 `core-migration-hazard3` 規則 22、23。為新 core 改了共用的 flow 設定時，每個版本的設計都要各 harden 一次，不要等結案 regress（`core-migration-hazard3` 規則 22；`flow-regression-reproducibility` 規則 11）。
- **定 die 尺寸時的 floorplan 試跑**（提早檢查 D1、D2）：
  - 做什麼：整顆設計加 macro，只跑到 PDN、global placement 與 global routing（幾分鐘到二十分鐘），看三件事：PDN 有沒有窄 row 錯誤（`PDN-0179`）；global placement log 的目標密度（`GPL-0052`）和 logic 區實際使用率差多少；global routing 的 overflow。出 floorplan 圖（`scripts/plot_floorplan.py`）給使用者看。同一個試跑也跑 IR（D2）：從下線服務商實際的 pad 起算（4.1 採用的電壓源位置）、在預算所保護的 slow corner 檢查；gate-level 模擬能跑之後，電流改用 CPU max power pattern（4.7）。
  - 通過條件：沒有窄 row 錯誤、overflow 0、目標密度不高於「logic 區使用率＋約定的 margin」（margin 由使用者決定）；IR ≤ 預算。IR 結果比預算小 100 倍以上時，先檢查電壓源位置的設定（多半是把電源 pin 都當成理想電源），不要當成 PASS。
  - 本 repo 的例子：Phase 3 為了 ss corner 的 max slew 試跑了約 8 次，signoff 的 max transition 一度放寬到 1.0 ns 又撤回，原因是 LibreLane 自動算的 68% 目標密度把 cell 擠在 L 形 logic 區的轉角（ADR-0009；`floorplan-congestion` 規則 6）；Phase 3 的 IR 0.3 mV 是把 PDN 的 pin 全當理想電源算的，電壓源位置與電流模型到 Phase 7 才修完（`docs/phase_exit/phase3.md`、ADR-0017、ADR-0019 決定 18–20）。限制：只在繞完線才出現的局部熱點，試跑看不到（Phase 7 wrapper 的 55% → 50%，ADR-0019 決定 21，`floorplan-congestion` 規則 5）。
  - 自動檢查：PDN 錯誤會讓試跑直接失敗；密度與 overflow 目前沒有自動檢查，下一個專案開始時做成 checker。

### 4.5 constraint 與 signoff 條件（第一次 harden 前）

- 做什麼：定週期與 STA corner、寫 SDC（`timing-constraints-sdc`、`multicorner-sta`）；推導每個 signoff 門檻（防什麼、數值怎麼算、預設值出自哪裡、工具有沒有分析），寫進 `signoff/limits/<tag>.toml`（`signoff-criteria`「先要有的輸入」）。製程的事實與量到的校準資料在 `signoff-criteria/knowledge/<製程>.md`。
- 寫 SDC：設了 `PNR_SDC_FILE` 就同時設 `SIGNOFF_SDC_FILE`（沒設時 signoff 改讀 PnR 的 SDC），改 constraint 後看 STA 報表的路徑分解確認生效，不看 SDC 有沒有被讀（`timing-constraints-sdc` 規則 2、16）。
- 檢查哪些 corner：LibreLane 預設只有 tt 的 setup 違規會讓 flow FAIL，slew／cap 違規都不會；`SETUP_VIOLATION_CORNERS` 等 `*_VIOLATION_CORNERS` 要設成全部 signoff corner（`drv-timing-closure` 規則 1；`check_signoff.py` 的 `[corners]` 檢查）。
- config 第一版就明確設 `RT_CLOCK_MIN_LAYER`（sky130 用 `met3`）：PDK 的值在 LibreLane 3 讀不進來，沒設時 clock 走 met1／met2 且沒有警告；第一次 harden 後看 `resolved.json` 確認不是 null（`cts-clock-tree` 規則 8，ADR-0021 決定 8；目前沒有自動檢查）。
- limits 裡「不是 0」的計數要逐項分類，會隨 layout 變的類別不寫死總數（`signoff-checker-qualification` 規則 4；目前沒有自動檢查）。
- **任何 harden 之前定好並強制 signoff 條件**（提早檢查 C1；「任何」包括 4.4 的子區塊與試跑）：
  - 做什麼：`signoff/limits/<tag>.toml` 每一列寫出處（推導筆記或 ADR 的哪一節）；STA 的 corner 清單等於 4.1 操作條件對照表（A1）推出的清單。IR 的檢查方式一次定清楚：預算防的是什麼（slow corner 的 setup）、電流、電壓、金屬電阻取同一個 corner、電流來自 CPU max power pattern（firmware 在 RTL 階段就寫好）、從真實 pad 起算（`signoff-criteria`「IR 用多大的電流」）。
  - 通過條件：上面每一項都有出處；`make harden` 開頭檢查 limits 檔存在、每列有出處、corner 清單等於規格推出的清單。目前沒有自動檢查，下一個專案開始時做成 checker（加 negative test）。
  - 本 repo 的例子：Phase 2、3 用 LibreLane 與 PDK 的預設值當 PASS 條件，Phase 3 收尾才推導（`docs/notes/signoff_criteria_soc_top.md`）；加嚴後 40 ns 不過，週期改 42 ns（ADR-0004）。IR 的檢查方式在 Phase 7 一天內改了三次（worst-case 組合 → slow corner → max power pattern），最後只剩不到 0.5 mV 的 margin（ADR-0019 決定 18–20）。
- **library 與工具預設值的 QA：找 drive 太弱的 cell 要涵蓋所有 signoff corner**（提早檢查 C2 的後半；前半在 4.0）：
  - 做什麼：用規劃的 slew 上限與每個修復步驟的 margin，對 resizer 可用的每個 cell 在**每個 signoff corner**（不只 resizer 看的 corner）查表，確認推得動 resizer 最小的 buffer（`drv-timing-closure` 規則 10）。改 slew 上限、margin、corner 或 cell library 時重跑。
  - 通過條件：排除之後沒有 drive 太弱的 cell。
  - 本 repo 的例子：resizer 停不下來發生 4 次（Phase 3、3.5、4、5），Phase 5 一個修復步驟跑 108 分鐘、記憶體 92.9 GB（機器 24 GB）才查到是 drive 太弱的 cell（ADR-0012）；查表腳本跑幾秒。`pnr/check_weak_cells.py` 目前只查 resizer 的 corner（`RSZ_CORNERS`）；涵蓋所有 signoff corner 目前沒有自動檢查，下一個專案開始時做成 checker。
- **resizer 看的 corner 預設等於 signoff corner**（提早檢查 C3）：
  - 做什麼：resizer 的 corner（LibreLane `RSZ_CORNERS`）預設就是全部 signoff corner。要拿掉某個 corner，要有根本原因（不能只因為「跑不完」，先照 `drv-timing-closure` 規則 10 找）、what-if 與 ADR；每次 criteria review 檢查「最差 setup／hold 的 corner 在不在 resizer 的清單裡」。
  - 通過條件：沒有拿掉；或拿掉的每個 corner 都有 ADR，criteria review 有那一列。
  - 本 repo 的例子：Phase 4 因為 15 個 corner 時修復步驟停不下來，resizer 只看 9 個，ss −40°C 用 0.6 ns margin 代替（`drv-timing-closure` 規則 9；經過見 `multicorner-sta` 規則 3）；Phase 5 換成 Hazard3 後 ss −40°C 差 −4.158 ns（ADR-0013）。Phase 7 wrapper 的 resizer 不看 ff 100°C，用 hold margin 0.2 ns 代替，有 ADR（ADR-0019 決定 17）。criteria review 的這一列目前沒有自動檢查（`review_criteria.py` 沒有），下一個專案開始時做成 checker。
- **wrapper 設計：IO constraint 先試算**（提早檢查 C4）：
  - 做什麼：採用 wrapper 官方的 IO constraint（SDC）時，第一次 harden 前先算兩件事：官方的 input transition 和自己的 slew 上限並排比；用官方的 clock source latency（min／max）、min input delay 加上預估的 clock tree，算 IO 路徑的 hold 需要多少延遲，決定 hold margin 與 resizer 要看的 corner。
  - 通過條件：有衝突的項目在 harden 前已列選項、由使用者決定。
  - 本 repo 的例子：Caravel 官方 SDC 的 input transition 0.84–0.97 ns 超過本 repo 的 0.70／0.75 ns，floorplan 試跑的 netlist 上就量到 0.84 ns 卻沒拿去比，到試跑 harden 時才處理（ADR-0019 決定 16）；IO 路徑在 ff 100°C hold −0.071 ns，ff 下資料要多延遲約 2.4 ns，多跑了 `p7_harden3`、`p7_harden4` 一輪（決定 17）。做法看 `caravel-user-project-integration` 規則 6。

### 4.6 harden 與 signoff（floorplan → PDN → placement → CTS → routing → signoff）

- 開跑前：`pnr/<design>/check_inputs.py` 檢查輸入。本 repo 檢查 RTL 檔案清單與 config 一致、兩顆 CPU 的 config 只差 RTL（本 repo 專屬）、macro 產生器的輸出沒被改過（sha256 對產生紀錄）、flow 讀的 macro view 通過 view QA、macro 的 .lib、antenna LEF 與模擬模型是產生器的最新輸出、.lib 的數字由 `check_char_lib.py` 獨立重算、STA 每個 corner 只讀到一份 macro .lib、`LIB`／`EXTRA_LIBS` 沒有帶進別的 macro .lib、drive 太弱的 cell。harden 只能在已 commit 的 working tree 上開（來源追溯）。
- 怎麼跑：`make harden-soc`（本 repo 要加 `CPU=hazard3`）。它呼叫 `pnr/soc_top/run.sh`：LibreLane（`pnr/librelane_flow.sh` 對已知的偶發錯誤做有上限的重試），接著自動執行 signoff 的全部 checker：
  - `check_signoff.py`：`signoff/limits/<tag>.toml` 的門檻（多 corner 的 setup、hold、slew、cap，DRC、LVS、antenna、IR）與 golden 比對；
  - `check_soc.py`（加 `sram_drc_alone.py`）、`check_inputs.py --resolved`（這次 run 真的用了這些輸入）、`ir_worst.py`（IR 在預算所保護的兩個 slow corner 檢查：該 corner 的電流、1.60 V、ss 金屬電阻，加上 macro 不在 .lib 裡的電流，取較大的那個和上限比；ff 電流＋ss 電阻只列為參考，ADR-0019 決定 19；IR 用多大的電流怎麼決定見 `signoff-criteria`）、wrapper 的 `ir_caravel.py`（Caravel wrapper：把 Caravel 從 pad 到 wrapper ring 的供電網路加進模型，電流用 CPU max power pattern 的 switching activity、在兩個 slow corner 以 20 mV 為上限檢查，接在 gl 模擬之後的 `make ir-caravel`，ADR-0019 決定 18–20；決定 18 原本的「對板子的供電要求」已由決定 20 取消）、`provenance.py --verify`、`review_criteria.py`。
  - flow FAIL 時，repo 的 checker 與 criteria review 也照跑，結果記為 FAIL（`pnr/soc_top/run.sh`；新專案重寫 `run.sh` 時要做到，1.5；criteria review 的植入錯誤 `neg-pnr` P43–P49、Stop hook 的 `make test-review-hook`）。
  - 某一步遠超過同設計上次同一步的時間，或記憶體一直漲：照 `librelane-run-debug` 規則 7 停掉並保留 run，再只重跑那一步；目前沒有自動停止（ADR-0021，下一個專案做）。
- 結果：`runs/<tag>_signoff/`（`signoff.txt`、`soc_checks.txt`、`ir_worst.txt`、整體結果 `result.txt`）。
- 每一步的設定與已知問題：`floorplan-congestion`、`pdn-ir-drop`、`drv-timing-closure`、`cts-clock-tree`、`antenna-signoff`、`multicorner-sta`、`drc-signoff`、`lvs-signoff`；執行與除錯看 `librelane-run-debug`。
- 已知不會被 checker 抓到、要自己看的地方：antenna 的 `GRT-0243` 只看最終指標（`antenna-signoff` 規則 11），`DRT_ANTENNA_REPAIR_MARGIN` 設了沒有作用（規則 10）；wrapper 頂層的 disconnected pin 要剛好是沒用到的固定腳位（`lvs-signoff` 規則 2）；KLayout 的浮接金屬檢查開不起來（`drc-signoff` 規則 5）；6 µm 的 latch-up 規則沒有任何檢查，交付的 GDS 沒有 81/14 標記（`drc-signoff` 規則 7，ADR-0021 決定 2；量測腳本 `docs/notes/latchup/tap_distance.drc`，下一個專案在 floorplan 試跑就量）；EM 目前完全沒有檢查，下一個專案開始時做成 checker（`pdn-ir-drop` 規則 8）。
- 跑完（PASS 或 FAIL）：`CLAUDE.md` 規則 9 的 criteria review（`signoff-criteria`「每次 harden 後的檢查」，寫 `runs/<tag>_signoff/criteria_review.md`），學到的數字寫進該製程的 knowledge 檔，出處用不會被覆蓋的路徑。也 grep flow log 的 `The checker will be skipped`、`metric was not found`，逐條補門檻或寫明由什麼取代（`signoff-criteria` 規則 30；沒有自動檢查）。criteria review 也對照放寬清單（E1），並檢查最差 corner 在不在 resizer 的清單裡（4.5 的 C3）。
- **第一次帶 macro 的 harden：檢查 macro 的 clock 結構**（提早檢查 D4）：
  - 做什麼：CTS 之後看每個 macro clock pin 前有沒有被插入對齊 latency 用的 buffer 鏈，報出 macro clock pin 的上升緣與下降緣 latency、和 capture 端 flip-flop 比，列出半週期路徑（一個 clock edge launch、相反的 edge capture）。flow 的變數關不掉某個工具行為時，查到底層工具的指令選項，再判斷是不是真的沒辦法。
  - 通過條件：沒有預期外、用來對齊 latency 的 delay buffer，或已記錄決定；半週期路徑兩個邊緣的 latency 差已列出。結構 checker（本 repo `check_soc.py cts_macro_latency`，數 macro clock pin 上方只驅動下一級的 clock buffer 有幾級）從第一次帶 macro 的 harden 就啟用。
  - 本 repo 的例子：Phase 4 就看到 CTS 在 `sram0/clk0` 前插了 10 顆 delay buffer，當時認定「LibreLane 沒有設定可以關」，改用 hold margin 0.3 ns 補；Phase 5 才查到 OpenROAD 的 `clock_tree_synthesis -no_insertion_delay`，用 LibreLane plugin 關掉，PicoRV32 的 setup −0.113 → +0.765 ns（ADR-0016；`cts-clock-tree` 規則 10）。Phase 3.5 的 42 → 43 ns 有一部分可能也來自它（回顧推測，沒有在 42 ns 重跑驗證）。
- **wrapper 設計第一次試跑 harden 之後：跑一次完整的 precheck**（提早檢查 D5）：
  - 做什麼：wrapper 設計（本 repo 的 Caravel wrapper）第一次試跑的 harden 完成後，用試跑產生的 GDS 跑一次完整的 precheck（非正式的，不列入 signoff 證據，結論標明不是正式結果），順便量 precheck 工具跑在 VM 時的記憶體峰值；fill 與 decap cell 的選擇依結果決定。下線服務商的密度上下限（4.1 下線規定對照表的結果）做成 harden 內的 checker，不要等 precheck（本 repo 約 1 小時）才知道。
  - 通過條件：除了已由使用者決定的項目，其他全 PASS；VM 記憶體峰值低於配置。
  - 本 repo 的例子：wrapper 的空白被 PDK 預設的 `decap_3` 填滿，li1 密度 75%（precheck 上限 60%），246 萬個 decap 也讓 10 GiB 的 VM 被 OOM 砍掉，到 Phase 7 步驟 7 官方 precheck 才發現，整段約 14 小時、多兩次 harden（ADR-0019 決定 24；`tapeout-precheck-caravel` 規則 1、`caravel-user-project-integration` 規則 4）。li1 密度本機算只要 84 秒（回顧 `retro_p6_7.md` #8）。
  - 自動檢查：harden 內的密度 checker 目前沒有（`caravel-user-project-integration` 規則 4：要等 precheck 才抓得到），下一個專案開始時做成 checker。
  - 補 fill 之後的密度下限由下線服務商在 tapeout 時檢查（Caravel 的 `check_density.py`，precheck 不查）；fill 誰補要在選下線服務商時問清楚（`caravel-user-project-integration`「待確認」，ADR-0019 決定 26）。
- **golden**：第一次 signoff 全部 PASS、criteria review 也確認後，把那次 run 的 metrics 存成 golden（`signoff/golden/<tag>/`）。之後改了工具、PDK、RTL、config、SDC、macro 產生器輸出的檔案（例如 .lib、antenna LEF），golden 比對一定 FAIL，要照 `signoff-checker-qualification` 規則 6 更新：先確認所有門檻與 checker PASS，逐項說明差異，複製並記 sha256，再跑一次確認 PASS。同樣設定重跑的差異怎麼給誤差也在該 skill。
  - **誤差至少用 4 個樣本定**（提早檢查 E2，`signoff-checker-qualification` 規則 11）：每個設計第一次建 golden 時，同一個設定至少 4 個樣本（含一次乾淨 checkout；可以是完整 harden，或把不可重現的那一步單獨重跑，再接著跑完），依每一類 metric 的實際差異定誤差，golden 的 README 寫明每一類用了幾個樣本；不能暫用別的設計的誤差。通過條件：樣本彼此都在誤差內。本 repo 的例子：Phase 2 用 3 次 run 定的誤差，Phase 4 regress 第 2 次就 FAIL（繞線器中間各輪的 DRC 數），Phase 5 Hazard3 的 golden 比對又 FAIL（ADR-0015），PicoRV32 暫用 Hazard3 的誤差被審查抓到，多跑兩輪 regress（`docs/phase_exit/phase4.md`、`phase5.md`）。每個設計多 2–3 次 harden。wrapper 的三組比較每個值都完全相同、量不出誤差大小，仍暫用 Hazard3 的值並寫明理由（ADR-0019 決定 26）。
- negative test：`make neg-pnr`（本 repo P00–P81）。

### 4.7 netlist 驗證

- 等價證明：合成 netlist 對最終 netlist（`make eqy-soc`，wrapper 用 `make eqy-caravel`，`formal-equivalence-eqy`），negative test `make neg-eqy-soc`。OpenROAD 時序修復對調的等價輸入（pin swap）只排除那幾個腳位名稱的對應，cell 輸出照樣證明（negative test `o21ai_swap`）；config 列出的 macro instance 必須在 netlist 中被解析到，macro 的 clock 檢查才不會被略過（Phase 6）。只有一兩個 partition 沒證明、沒有別的問題時，用 EQY 的 `amend` 把驅動它們輸入的組合邏輯併進來重跑一次，PASS／FAIL 看第二輪（partition 切在輸入上（cut point）時，輸入之間的邏輯關係被切掉，好 netlist 也會證不出來）；flip-flop 不能併進來（會變成 vacuous pass：實際上什麼都沒檢查就 PASS），被 amend 的 partition 有 sequential cell 就 FAIL。negative test `nand2_comb_to_nor2` 要求重試後仍 FAIL、`nand2_flop_to_nor2` 防止併入 flip-flop（Phase 7）。**限制**：RTL 到合成 netlist 這一段沒有 formal 證明（合成會重新編碼狀態機），由 gate-level 模擬加 directed 測試補（README「專案狀態」、`formal-equivalence-eqy`）。EQY 的 PASS 不涵蓋被換成常數的 bit、flip-flop 本身的種類、clock 接線三種情況，要在 EQY 之外補（`formal-equivalence-eqy` 規則 8）。
- gate-level 模擬：RTL 與 netlist lockstep（`make gl-soc`），PG netlist（含電源／地腳位的 netlist，`make gl-soc-powered`），negative test `make neg-gl-soc`（`gate-level-simulation`）。Caravel wrapper 用 `make gl-caravel`：比對 wrapper 全部的輸出腳位（`gl_lockstep` 的 `OUT_W`）。
- IR 與功耗一律用 CPU max power pattern 的 switching activity，不用 OpenSTA 的預設 toggle rate（使用者 2026-10-13；`signoff-criteria`）；EM 目前沒有檢查（`pdn-ir-drop` 規則 8）；下一個專案開始時做電源網路 EM 的 checker（strap 與 via，ff 與 ss corner，ADR-0021 決定 8）。新設計要有一支 max power firmware，並在 harden、gate-level 模擬之後 dump VCD。
- IR 的檢查（Caravel wrapper，`make ir-caravel`，接在 gate-level 模擬之後）：CPU 的 max power pattern（`fw/tests/maxpower`，滿負載迴圈標在 GPIO）在最終 netlist 的 gate-level 模擬 dump 成 VCD（`run_gl_soc.py --record-window`，時脈用 signoff 週期），含 wrapper 供電網路的 IR 讀這些 VCD，在 slow corner 檢查（`ir_caravel.py`，ADR-0019 決定 20）。檢查前先核對輸入：harden run 通過 run guard、window 齊全、VCD 的時脈週期等於 run 的 `CLOCK_PERIOD`（dump 波形的週期也從 `CLOCK_PERIOD` 取）。harden 內的 `ir_worst.py`（預設 toggle rate）只當早期檢查。switching activity 要用 max power pattern 的依據見 `signoff-criteria`「IR 用多大的電流」。
- precheck（下線前檢查；本 repo Phase 7：ChipFoundry precheck）：只認官方 image 的結果，每次記下版本與 image digest。官方結果裡的已知工具問題不能直接放過，要寫成有比對基準的 checker：precheck 的 deck 在任何 OpenRAM SRAM（包括 PDK 附的）裡都報 `MR_licon.SP.6`、`MR_mcon.CON.10`，`make precheck-check` 要求其他項目全 PASS，這兩條的每個違規展開後都在 SRAM 裡、而且 PDK 附的 macro 單獨檢查時同一個位置也有（ADR-0019 決定 5；比對基準 `make precheck-sram-ref`，植入錯誤 `make neg-precheck`）。要當正式結果的 precheck，專案目錄要來自通過 run guard 的 harden run（`arvinsa_source.json`）；非正式的結果（不列入 signoff 證據）要加 `--verification`，結論標明不是 signoff 結果。報表要綁到這一次的 GDS，讀到前一次 run 的報表也會判 PASS（`tapeout-precheck-caravel` 規則 12，`neg-precheck` 的 `stale_results`）。SRAM 在 precheck 的 LVS 用 `EXTRACT_ABSTRACT` 當 black box，LVS log 結尾的 `possible errors ... CVC` 是 SRAM 輸出沒人驅動，不是比對失敗（規則 4）。做法在 `tapeout-precheck-caravel` 規則 3。比對基準要用 precheck 實際用的那顆 PDK 附的 macro、在同一個 image 跑（`make precheck-caravel` 一次做完：組專案目錄、跑官方 image、產生比對基準、判斷 PASS／FAIL）；它若另有別的規則，只比允許的那幾條（ADR-0019 決定 24）。官方 image 跑在 VM 裡時，記憶體不足會讓 BEOL、LVS、OEB 沒跑完，先看 VM 的 OOM kill。wrapper 的 user area 很大、頂層又有標準 cell 時，空白區的 fill 會決定整體 li1 密度：sky130 預設的 `decap_3` 填滿會超過 precheck 的 60%，要改用 li1 較少的 decap 與 fill，harden 後先在本機算 li1 密度再送 precheck（`caravel-user-project-integration` 規則 4）。

### 4.8 一鍵 regression 與來源追溯

- `make regress`（Hazard3 版，`scripts/regress.py --cpu hazard3`）依序跑下列項目，第一個 FAIL 就停（實際清單：`scripts/regress.py` 的 `TARGET_LISTS`）：
  1. `env-check-flow py-check lint synth-check fw core-hazard3 regress-rtl neg-rtl regress-rtl-caravel neg-rtl-caravel`
  2. flow 的 checker：`neg-provenance`（來源追溯的植入錯誤）、`neg-run-guard`（下游拒絕 FAIL 或別的 commit 的 run）、`neg-regress`（regression 自己的植入錯誤）、`test-flow-retry`（偶發錯誤的重試）、`test-review-hook`（criteria review 的 Stop hook）、`neg-openram`、`neg-macro-views`、`pin-plan`、`neg-pin-plan`、`neg-precheck`（precheck 結果檢查的植入錯誤，Phase 7）
  3. `harden-soc eqy-soc neg-eqy-soc gl-soc gl-soc-powered neg-gl-soc neg-pnr ir-soc neg-ir-soc`（`ir-soc`：用 CPU 的 max-power pattern 檢查 IR，ADR-0019 決定 20、25）
  4. `provenance-final`：HEAD 與 working tree 從 harden 開始後都沒變。
- `make regress-picorv32`：PicoRV32 版，把 `core-hazard3` 換成 `core-stock`，另加 4.4 的 `harden-core gl-core neg-gl-core eqy-core neg-eqy-core`。
- `make regress-caravel`（本 repo Phase 7：晶片層級的 wrapper，`scripts/regress.py --cpu caravel`，約 6 小時）：wrapper 裡的 RTL 測試、wrapper 的 harden、EQY、gate-level、從 pad 起算的 IR、官方 image 的 precheck（`env-check-flow` 先檢查 VM），以及**只屬於 wrapper 的** negative test（`neg-eqy-caravel`、`neg-gl-caravel`、`neg-ir-caravel`、`neg-pnr-caravel`）。和內部設計共用的 checker 由 `make regress` 的完整 negative test 驗證，wrapper 不重複植入（ADR-0019 決定 25：完整移植每輪多 4–6 小時）。結案時三條 regress 各在一個乾淨 worktree 跑，外部共用的目錄（precheck 的 VM 工作目錄）依 checkout 分開。
- **不在 regression 裡、要另外跑的**：`ci-sram-ref`；macro 的產生、view QA、characterization 與它們的確認（`openram-macro`、`macro-views`、`sram-char`／`openram-char`、`sram-confirm`／`openram-confirm`、`openram-check-lib`、`neg-char`）。這些在 macro 或量測方法有改時跑，結果進版控；regression 只檢查進版控的結果沒過期（`harden-soc` 開頭的 `check_inputs.py`）。
- 要在乾淨的 checkout 執行；乾淨的 worktree 沒有 `.tools/`，要設 `LIBRELANE_DIR`、`XPACK_DIR`、`PRECHECK_DECK` 指到已安裝的副本。
- 開結案 regress 前，先讓最後改過的 checker 在現有 run 上跑 positive control（`phase-exit-review` 規則 2、12）。改 checker 時新變數（含迴圈變數、模組層）不能蓋掉同一個 scope 既有的名稱，改完先在實際的 run（harden 實際跑出來、沒有植入錯誤的 run）跑 positive control（`signoff-checker-qualification` 規則 13；沒有自動檢查）。
- **資源與長時間工作**（`flow-regression-reproducibility` 規則 13–17）：依記憶體決定同時跑幾條（目前沒有自動檢查）；開跑前看磁碟；每個 regress 項目有逾時；結案後清理舊 worktree 與中間檔案；`runs/` 與 worktree 不要被 Spotlight 索引。自動檢查（ADR-0021 決定 3）：`scripts/regress.py` 開跑前檢查磁碟剩餘 ≥ `REGRESS_MIN_FREE_GB`（預設 100 GiB），每個 target 有逾時（參考時間 × 3、至少 30 分鐘，用 `REGRESS_TIMEOUT_SCALE` 調），逾時砍整個程序群組並記為 FAIL（log 有 `regress: TIMEOUT`）；negative test 是 `make neg-regress` 的 `low_disk`、`timeout`。
- GDS 的 sha256 每次不同不代表 flow 不可重現：netlist、DEF 比 sha256，GDS 用 XOR（`flow-regression-reproducibility` 規則 12）。共用 flow 設定改了，每個版本的設計都要重 harden（規則 11）。
- **新 checker 寫完就做獨立漏洞審查**（提早檢查 E3）：
  - 做什麼：每支新的或大改的 checker，寫完、第一次正式 harden 或放進 regression 之前，就請一個沒寫它的 agent 找「該 FAIL 卻 PASS」的漏洞：做植入錯誤的實驗加對照組，不能只讀程式（`signoff-checker-qualification` 規則 12）。Phase 收尾時只審最後改過的 checker。
  - 通過條件：每支新 checker 有獨立審查的紀錄與 negative test；收尾審查沒有新的高、中嚴重度漏洞。
  - 本 repo 的例子：每個 Phase 收尾的審查都找到一批漏洞，修完要整套 regression 重跑：Phase 4 有 10 個、Phase 3.5 有 12 個、Phase 5 有 8 個、Phase 6 有 7 個、Phase 7 有 8 個加 1 個缺口（各 Phase 的 exit review「獨立審查」；ADR-0019 決定 26）。Phase 7 那次三條 regression 要重跑，wrapper 一條約 6 小時。
  - 自動檢查：沒有（審查要 agent 做實驗）；審查紀錄齊不齊可以做成 checker，下一個專案開始時做。
- skill：`flow-regression-reproducibility`；審查的做法看 `signoff-checker-qualification`。

### 4.9 Phase 收尾

- 獨立審查、exit review（`docs/phase_exit/`）、經驗寫回 skill（`phase-exit-review`）。exit review 的證據只能來自乾淨 checkout 從頭到尾跑完的 run（該 skill 規則 2）。收尾時找 checker 漏洞的那份審查只審本 Phase 最後改過的 checker，其餘在寫完時已審過（文件核對照舊全部做）（E3，`phase-exit-review` 規則 10）。已知限制裡的放寬引用放寬清單（E1）。
- 收尾的順序與清單（`phase-exit-review` 規則 9、12）：開結案 regress 前先在現有 run 跑 positive control；審查與 regress 同時進行，預留至少兩輪乾淨 regress 加一輪修正；延後的項目逐條對照前一階段與再前一階段的已知限制（規則 1）；證據當下存到不會被覆蓋或消失的地方（規則 3）；偏離計畫時寫明原本防範什麼、現在由誰防範（規則 4）；不在 regression 裡的 negative test 列出最後一次跑的 commit 與環境（規則 2）；決定改了要標出被取代的舊段落，skill 不寫會變的數字（規則 11）；流程文件與 `AGENTS.md` 同步、規則 10 稽核、清理舊 worktree（規則 9）。
- 清空 `runs/todo.md`（`CLAUDE.md` 規則 11）。
- 專案結束、要清掉 `runs/` 與所有 worktree 時：先確認 worktree 沒有只存在那裡的修改，再 `make collect-evidence`，把文件引用的報告、每次 harden 的 PASS／FAIL 結果與 criteria review、regression 摘要收進 `docs/evidence/`（保留路徑；`docs/evidence/references.md` 列出每個引用是否收錄），提交之後才刪。GDS、DEF、netlist、整個 run 目錄不收，靠 commit 重跑產生（`flow-regression-reproducibility` 規則 16，ADR-0021 決定 7；使用者 2026-10-15：「主要是重要的佐證報告才收」）。

## 5. 遇到工具缺陷時

照 `CLAUDE.md` 規則 10：確認（出現兩次或實驗確認）之後，在對應的 skill 寫出症狀（確切訊息，也寫進 `description`）、怎麼發現、怎麼繞過（設定、repo 的 plugin 或 patch、有上限的重試，不改固定版本的工具本身），以及怎麼防止再發生（能抓到它再次出現的 checker 或 negative test）。對策不能綁在 step 名稱、log 措辭這類 flow 會變的東西上。

- 包外部工具的 checker 要分得出工具當掉與結果不對（`signoff-checker-qualification` 漏洞類型表）。
- 工具升版時，逐條重看 `librelane-run-debug`「升版時要重看的綁定」。

## 6. 維護這份文件

- 流程的步驟、順序、checker 或 negative test 有改，同一個 commit 更新本文件；README 的「流程（簡易版）」只在大方向改變時才跟著改。
- 新專案發現的通用流程經驗寫回這裡（1.6）。
- skill 的 `description` 有長度上限：`make skill-check` 檢查單份 ≤ 1,024 字元與合計上限（`scripts/check_skills.py`），超過時 Claude Code 會截斷或拿掉 description，選不到 skill。寫法是使用時機與確切錯誤訊息放前面，做法細節與設計數字放在 SKILL.md 本身（ADR-0021）。
- 本文件 2026-10-09 建立後，由獨立 agent 逐條對照 repo 審查過一次（14 項中重度問題已修正）。
- 2026-10-14 依 ADR-0020 加入 19 條提早檢查（第 4 節標「提早檢查」的各點）；它們的 checker 在下一個專案開始時做，做好後把各點的「目前沒有自動檢查」改成 checker 與 negative test 的名稱。
- 2026-10-15 依 ADR-0021 寫回 Phase 0–7 問題總檢討的結果；三個 description 超過上限的 skill 依功能拆分，skill 從 23 個變成 27 個（決定 5）；再依使用者決定分成 Middle-end、Backend、Package 三段，加三個入口 skill，共 30 個（決定 6）。
