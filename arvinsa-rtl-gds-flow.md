# arvinsa-rtl-gds 流程（完整版）

這份文件是本 repo RTL-to-GDS 流程的完整說明，也是其他 IC 專案沿用這套流程時的入口（`CLAUDE.md` 規則 8）。README 只放簡易流程並指到這裡。

**各文件的分工**（同一件事只寫在一個地方）：

| 文件 | 放什麼 |
|---|---|
| 本文件 | 流程：做哪些步驟、順序、每一步的 checker 與 negative test、交給哪個 skill |
| [`CLAUDE.md`](CLAUDE.md) | agent 必須遵守的規則（本文件第 2 節只列摘要與編號） |
| `.claude/skills/<name>/SKILL.md` | 每類任務的規則、已知工具缺陷與防護、經驗紀錄；索引在 README「Claude Code skills」一章 |
| [`project-plan.md`](project-plan.md) | 本 repo 這顆 SoC 的計畫：各 Phase 的內容、exit criteria、negative test 總表 |
| `docs/decisions/`（ADR，architecture decision record：每個重大決定的選項、代價與使用者的選擇）、`pnr/*/README.md`、`docs/phase_exit/` | 本設計的決定、設定理由、數字、階段收尾 |
| [`toolchain.md`](toolchain.md)、`env/versions.mk`、[`env/setup.md`](env/setup.md) | 工具與 PDK 的版本、在新機器上建環境的逐步說明 |

本文件用到的名詞：
- **checker**：判 PASS／FAIL 的程式。
- **negative test（bug injection）**：故意植入一個錯誤，確認 checker 真的 FAIL；**positive test**：不植入錯誤時 checker 必須 PASS，證明它不是一直 FAIL。
- **golden**：確認過正確的一次 run 的完整 metrics，之後每次 harden 都逐項和它比對。
- **PVT**：製程 corner、電壓、溫度的組合，例如 `ss_n40C_1v60`；STA 的每個 corner 都對應一個 PVT。
- **lockstep**：RTL 與網表同時模擬，每個 cycle 比對兩邊的訊號。

---

## 1. 在新專案使用

使用者的做法（2026-10-04）：開新專案時，請 Claude Code 或 Codex「使用 arvinsa-rtl-gds 這個 repo 的流程」。skill 不搬到使用者層，也不複製到新專案；新專案的 agent 直接讀這個 repo。

### 1.1 起手清單

1. **讀對的那一份**：GitHub `github.com/Jordanplus/arvinsa-rtl-gds` 的 main，或本機的 main checkout。不要讀 `arvinsa-rtl-gds-p5*` 這類舊的 git worktree，它們停在舊 commit，skill 是舊版。
2. **在新專案寫一份自己的 `CLAUDE.md`（Codex 是 `AGENTS.md`）**：寫一行「流程照 arvinsa-rtl-gds 的 `arvinsa-rtl-gds-flow.md`」，並把第 2 節的規則抄進去（或寫明照做）。只靠對話交代的話，下一次對話就忘了。
3. **照 4.0 建環境**，照 4.1 寫新設計的計畫（Phase、exit criteria、negative test 總表）。
4. **需要沿用的程式複製進新 repo**（來源追溯要求所有用到的檔案都已 commit，不能從這裡引用），在新專案記下複製時本 repo 的 commit；複製後修掉的錯誤，通用的部分寫回本 repo。
5. 開始每一步之前，用 README 的「依情況找 skill」表找到 skill，讀對應的 `.claude/skills/<name>/SKILL.md`。

SKILL.md 是一般的 Markdown，任何 agent 都能讀。它們放在專案層：在本 repo（或它的上層目錄）開 Claude Code 才會自動列出，在新專案要明確叫 agent 來讀。在上層目錄開時，舊 worktree 裡的舊版 skill 也會一起列出，注意不要用到它們。

**Codex**：讀的是 repo 根目錄的 `AGENTS.md`；本 repo 的 `AGENTS.md` 指回 `CLAUDE.md` 與本文件，不另寫一份。

### 1.2 可以直接沿用的

寫法與程式都能直接用，只要換參數或路徑：
- `scripts/regress.py`：一鍵 regression（target 清單要換成新設計的）。
- `signoff/scripts/provenance.py`、`run_guard.py`：來源追溯（harden 只能在已 commit 的工作樹上開，記錄工具與 PDK 版本），以及下游步驟拒絕用 FAIL 或別的 commit 的 run。
- `signoff/scripts/check_signoff.py` 加 `signoff/limits/*.toml` 的格式：signoff 門檻與 golden 比對。
- `pnr/librelane_flow.sh`：LibreLane 呼叫與有上限的重試。
- `pnr/librelane_plugin_arvinsa/`：不改 LibreLane、只換掉一個 step 的寫法（`meta.substituting_steps` 加 `PYTHONPATH`；ADR-0016 的 CTS）。
- `dv/scripts/dvlib.py`：模擬的 checker；`dv/monitors/gl_lockstep.v`：RTL 與網表 lockstep。
- `signoff/eqy/`：EQY（formal equivalence check）與它的植入錯誤。
- `scripts/check_macro_views.py`（`gds_bbox.py`、`neg_macro_views.py`）：任何 macro 的 view QA，檔案路徑由參數指定，不綁特定產生工具。
- `env/versions.mk`、`env/check_env.sh`、`toolchain.md`：釘版與環境檢查。
- `scripts/check_py_names.py`、`scripts/check_skills.py`：開跑前的快速檢查。

### 1.3 寫法可沿用，但要依新設計修改的

- `ip/sram/char/`：SRAM macro 的 ngspice 特性化、.lib 產生、獨立重算與確認模擬。方法通用；程式只支援 OpenRAM 架構的 1rw1r、32 bit × 512 word（`sramchar.py` 的字寬、位址寬、網表修剪依 OpenRAM 的命名），macro 名稱與網表可用環境變數 `SRAM_CHAR_MACRO`、`SRAM_CHAR_NETLIST` 換；其他容量或架構要改 `sramchar.py`。
- `signoff/scripts/review_criteria.py` 與 `.claude/hooks/require_criteria_review.py`：每次 harden 後的 criteria review 與強制它的 Claude Code Stop hook。設計名稱、run tag、要讀哪些 checker 的結果都寫在程式裡，要改。
- `scripts/progress.py` 加 `.claude/statusline-progress`：Claude Code 狀態列第二行的進度顯示（待辦清單 `runs/todo.md`，格式 `- [ ]` 待辦、`- [~]` 進行中、`- [x]` 完成）。它判斷「執行中工作」的方式綁本 repo 的 target 與 run 目錄（regress、LibreLane 有百分比；其他 make target 與直接執行的本 repo Python 腳本只顯示「執行中」）。

### 1.4 只在使用者這台機器有的

換機器或用 Codex 時不存在，不要當成流程的一部分：
- 全域狀態列（claude-usage skill v1.6.0）與進度面板 mod（`/progress`，`~/.claude/skills/progress-pane/`），呼叫 `.claude/statusline-progress`／`--json`。
- 全域 PreToolUse hook `~/.claude/hooks/guard-bash.py` 與它讀的 `.claude/guard.json`：公開 repo 的推送內容不能有本機絕對路徑或機密、harden 要在已 commit 的工作樹上開、force push 一律擋（使用者自己做）；「同時最多 2 個 LibreLane／EQY、可用記憶體至少 4 GB」是依這台 24 GB 機器訂的。

### 1.5 要依新設計重做的

- `pnr/<design>/config.json`、SDC、`signoff/limits/` 的數值，用 `signoff-criteria` 重新推導。
- `pnr/<design>/run.sh` 與設計專屬的 checker：本 repo 的 `check_inputs.py`（harden 前的輸入檢查）、`check_soc.py`（SRAM 擺放、未用 port 的接法、斷線 pin、STA 設定、macro clock 前有沒有 delay buffer、Magic DRC 對 SRAM 單獨的結果）、`sram_drc_alone.py`、`ir_worst.py`（最壞情況的靜態 IR）。
- golden。
- 和設計綁在一起的植入錯誤案例，例如 `pnr/soc_top/neg_pnr.py` 的 P00–P62（PnR 與 signoff checker 的植入錯誤）。
- ADR、exit review 的內容。

### 1.6 經驗寫回這裡

新專案用到某個 skill 時發現的通用經驗，寫回本 repo 的 `SKILL.md`；流程本身有改，寫回本文件。只屬於新設計的數字留在新專案的文件（`CLAUDE.md` 規則 8）。

## 2. 必須遵守的流程規則（全文在 `CLAUDE.md`）

`CLAUDE.md` 只在本 repo 自動載入；下列各條在新專案也適用，新專案的 agent 要先讀原文：

| 規則 | 摘要 |
|---|---|
| 1–3 | 做到 skill 涵蓋的任務先讀 `SKILL.md`；新現象寫進經驗紀錄；同一現象出現兩次以上或已用實驗確認，才搬進規則本文，推測不進規則 |
| 4 | 這顆設計的數字放 repo 文件；skill 只放能帶到下一顆設計的規則 |
| 5 | skill 有改，同一個 commit 同步 README 的 skill 一節與 `description`，跑 `make skill-check` |
| 7（通用部分） | 進入沒有 skill 涵蓋的新類任務前（例如下線預檢、換 PDK），先建立對應的 skill 再開始 |
| 8 | 通用經驗寫回本 repo，不把 skill 複製到新專案；流程有改，更新本文件 |
| 9 | 每次 harden 跑完（PASS 或 FAIL），先做 criteria review 再回報。本 repo 由 Stop hook 強制；新專案與 Codex 沒有這個 hook，要自行遵守，或在新專案裝同樣的 hook |
| 10 | 每個確認過的工具缺陷都要寫成防護：症狀、怎麼發現、怎麼繞過、防復發的 checker 或 negative test |
| 11 | 目前 Phase 的待辦清單在 `runs/todo.md`，Phase exit review 寫完後清空 |
| 12 | 自建或收到的 macro 都要先做 view QA，才能交給 flow |
| 13 | 要做選擇時（新 Phase 開始、改變已定的決定、工作中出現影響規格／量測方法／signoff 標準／時程的分岔）：先查證，列出選項、代價與建議，由使用者決定，再實作並記成 ADR（`docs/decisions/` 的每一份都是這樣產生的） |

另外一個貫穿全程的做法：每個 checker 都要有 negative test 與 positive test（`signoff-checker-qualification` 規則 7）。

## 3. 全流程總覽

```
環境與釘版 ............................ （不做成 skill）toolchain.md、env/setup.md
規格與計畫 ............................ project-plan.md、ADR
RTL：合成、lint ........................ rtl-synthesis-lint
 └ RTL 模擬與 directed 測試 ............ dv-directed-tests
 └ 換 CPU core ......................... core-migration-hazard3
macro 產生或取得（memory compiler、廠商 IP）
 └ view QA（每個交付檔的內容）........ hard-macro-integration（清單第 0 項）
 └ 整顆 macro 的 DRC ................... drc-signoff
 └ 各 corner 功能確認、SPICE 特性化、.lib ... openram-macro-characterization
約束與 signoff 條件（第一次 harden 前）
 ├ SDC、corner ......................... timing-constraints-sdc、multicorner-sta
 └ signoff 門檻的推導 .................. signoff-criteria
harden（LibreLane）
 └ floorplan、macro、IO pin ............ floorplan-congestion、hard-macro-integration
    └ PDN .............................. pdn-ir-drop
       └ placement、resizer ............ drv-timing-closure、floorplan-congestion（密度）
          └ CTS ........................ cts-clock-tree
             └ routing、antenna ........ drv-timing-closure、antenna-signoff、floorplan-congestion（繞路）
signoff（harden 結尾自動執行）
 ├ STA ................................. multicorner-sta、timing-constraints-sdc、drv-timing-closure
 ├ DRC、XOR、密度 ...................... drc-signoff
 ├ LVS、連接性 ......................... lvs-signoff
 ├ IR、EM .............................. pdn-ir-drop
 ├ golden 比對 ......................... signoff-checker-qualification
 └ 每次 harden 後的 criteria review ..... signoff-criteria
網表驗證
 ├ 等價證明 ............................ formal-equivalence-eqy
 └ 網表模擬 ............................ gate-level-simulation、dv-directed-tests
一鍵 regression 與來源追溯 ............. flow-regression-reproducibility
階段收尾 ............................... phase-exit-review
貫穿全程 ............................... librelane-run-debug（執行與除錯）
                                         signoff-checker-qualification（checker、golden、植入錯誤）
尚未涵蓋 ............................... chip-level 整合與下線預檢（本 repo Phase 7；沒有 skill，進入前先建，規則 7）
```

## 4. 逐步流程

每一步的格式：**做什麼**、**怎麼跑**、**PASS 條件**（checker 與 negative test）、**skill**。括號裡是本 repo 的 target；新專案照同樣的結構建自己的 target。

**本 repo 的設計選擇**：目前主要設計是 Hazard3 版 SoC。`CPU` 預設是 `picorv32`（`Makefile` 的 `CPU ?= picorv32`），所以 `fw`、`sim`、`regress-rtl`、`neg-rtl`、`synth-check`、`harden-soc`、`eqy-soc`、`neg-eqy-soc`、`gl-soc`、`gl-soc-powered`、`neg-gl-soc`、`neg-pnr`、`provenance-final` 要加 `CPU=hazard3`，否則跑的是 PicoRV32 版（run 在 `runs/soc_top`，Hazard3 版在 `runs/soc_top_hazard3`）。`make regress` 固定跑 Hazard3 版。

### 4.0 環境與釘版

- 做什麼：所有工具、PDK、IP 釘到確切的版本或 commit，安裝方式可重現。
- 怎麼跑：逐步說明在 `env/setup.md`。`make nix-install`、`make flow-setup`、`make pdk-fetch`、`make xpack-fetch`（RISC-V toolchain，`core-hazard3` 要用）；macro 用 OpenRAM 產生時加 `make openram-setup`。版本在 `env/versions.mk`，說明在 `toolchain.md`（兩者由 `env/check_toolchain_doc.py` 檢查一致）。
- PASS 條件：`make env-check`（本機工具與 IP）、`make env-check-flow`（加上 Nix、LibreLane、PDK）；用 LibreLane 官方範例重跑一次當參考（`make ci-sram-ref`）。
- skill：不做成 skill（`CLAUDE.md` 規則 6）。

### 4.1 規格與計畫

- 做什麼：規格（本 repo `docs/spec/`）、分 Phase 的計畫與每個 Phase 的 exit criteria（`project-plan.md` 第 8 章）、negative test 總表（第 7.3 節）。
- 重大選擇（PDK、core、SRAM、週期、corner、餘量）由使用者決定，記成 ADR。

### 4.2 RTL 與 RTL 驗證

- 怎麼跑：`make lint`、`make synth-check`、`make fw`、`make regress-rtl`（Icarus 與 Verilator）、上游 core 的測試（`make core-stock`、`make core-hazard3`）。
- PASS 條件：每個 test 都是 self-checking；`make neg-rtl` 對每個植入錯誤都要 FAIL。
- skill：`rtl-synthesis-lint`、`dv-directed-tests`；換 core 時 `core-migration-hazard3`。

### 4.3 macro：取得或產生、QA、特性化

1. **取得或產生**：PDK 預建 macro、memory compiler（本 repo：OpenRAM，`make openram-macro`）、廠商 IP。產生工具自己的 DRC／LVS 要讀報告判斷，不能只看 exit code（OpenRAM 在 LVS 不一致時仍 exit 0）。本 repo 對 OpenRAM 執行結果、安裝、patch、macro DRC 比對、.lib 範本與自產 macro 特性化來源的 negative test：`make neg-openram`。
2. **view QA**（`CLAUDE.md` 規則 12，`hard-macro-integration` 清單第 0 項）：`scripts/check_macro_views.py` 檢查 LEF、.lib、Verilog、SPICE、GDS 的名稱、腳位與方向一致，.lib 數值範圍與面積，LEF 尺寸等於 GDS 外框。產生 macro 的 target 要接這一步；整合中的 macro 用 `make macro-views`。FAIL 的 view 修正或替換後重跑到 PASS，做法記進該 macro 的 README 或 ADR。negative test：`make neg-macro-views`。
3. **整顆 macro 的 DRC**：用 full 規則，逐種類和已知 baseline 比較，不只比總數（`ip/sram/openram/macro_drc.py`；negative test 在 `neg-openram` 的 D1–D3）。
4. **每個 corner 的功能確認**：先證明 macro 在每個 STA corner 與 corner 之間的溫度都讀寫正確，再談時序。不能動的 corner 用標明 PLACEHOLDER 的佔位 .lib，列為下線風險。未用的 port 照實際 SoC 的接法模擬（OpenRAM SRAM 未用 port 的時脈要打時脈，ADR-0018 決定 9）。
5. **SPICE 特性化**：延遲、setup／hold、最小週期與 pulse width、internal power，每個 PVT 一份 .lib。量測方法先驗證誤差，再用植入錯誤證明量得對（`make neg-char`），最後在 .lib 採用的數值上跑確認模擬（`make sram-confirm`／`openram-confirm`），並由不 import 產生器的程式獨立重算（`check_char_lib.py`：預建 macro 由 `harden-soc` 開頭的 `check_inputs.py` 執行，自產 macro 用 `make openram-check-lib`）。特性化本身用 `make sram-char`／`openram-char`。internal power 與漏電也用 SPICE 量（自產 macro：`make openram-power`，再 `make openram-lib` 寫進 .lib），不用 memory compiler 的解析值；漏電要在所有 port 都 precharge、時脈停住的待機狀態量；單顆 bitcell 的漏電 deck 要把 ngspice 的 gmin 調小並用再小 10 倍的值核對（`bitcell leakage depends on gmin`，`make neg-char` N21），量測窗的平穩度只放行小幅下降（`openram-macro-characterization` 規則 25、28）。沒用到的 port 在 SoC 接法下可能浮接、漏出額外的靜態電流，它不進 .lib，要另外記錄並列為已知限制（`openram-macro-characterization` 規則 25）。
- skill：`hard-macro-integration`、`openram-macro-characterization`、`drc-signoff`。

### 4.4 子區塊單獨 harden（可選）

- 做什麼：先單獨 harden 一個主要區塊（本 repo：PicoRV32），打通流程並取得面積與時序實測值，估計 SoC 的 die 尺寸（`make soc-area`）。
- 怎麼跑：`make harden-core`；之後 `make gl-core`、`make eqy-core`。
- PASS 條件：同 4.6、4.7；negative test `make neg-gl-core`、`make neg-eqy-core`。

### 4.5 約束與 signoff 條件（第一次 harden 前）

- 做什麼：定週期與 STA corner、寫 SDC（`timing-constraints-sdc`、`multicorner-sta`）；推導每個 signoff 門檻（防什麼、數值怎麼算、預設值出自哪裡、工具有沒有分析），寫進 `signoff/limits/<tag>.toml`（`signoff-criteria`「先要有的輸入」）。製程的事實與量到的校準資料在 `signoff-criteria/knowledge/<製程>.md`。

### 4.6 harden 與 signoff（floorplan → PDN → placement → CTS → routing → signoff）

- 開跑前：`pnr/<design>/check_inputs.py` 檢查輸入。本 repo 檢查 RTL 檔案清單與 config 一致、兩顆 CPU 的 config 只差 RTL（本 repo 專屬）、macro 的 .lib 與 antenna LEF 是產生器的最新輸出、.lib 的數字由 `check_char_lib.py` 獨立重算、STA 每個 corner 只讀到一份 macro .lib、`LIB`／`EXTRA_LIBS` 沒有帶進別的 macro .lib、弱 cell。harden 只能在已 commit 的工作樹上開（來源追溯）。
- 怎麼跑：`make harden-soc`（本 repo 要加 `CPU=hazard3`）。它呼叫 `pnr/soc_top/run.sh`：LibreLane（`pnr/librelane_flow.sh` 對已知的偶發錯誤做有上限的重試），接著自動執行 signoff 的全部 checker：
  - `check_signoff.py`：`signoff/limits/<tag>.toml` 的門檻（多 corner 的 setup、hold、slew、cap，DRC、LVS、antenna、IR）與 golden 比對；
  - `check_soc.py`（加 `sram_drc_alone.py`）、`check_inputs.py --resolved`（這次 run 真的用了這些輸入）、`ir_worst.py`、`provenance.py --verify`、`review_criteria.py`。
- 結果：`runs/<tag>_signoff/`（`signoff.txt`、`soc_checks.txt`、`ir_worst.txt`、整體結果 `result.txt`）。
- 每一步的設定與已知問題：`floorplan-congestion`、`pdn-ir-drop`、`drv-timing-closure`、`cts-clock-tree`、`antenna-signoff`、`multicorner-sta`、`drc-signoff`、`lvs-signoff`；執行與除錯看 `librelane-run-debug`。
- 跑完（PASS 或 FAIL）：`CLAUDE.md` 規則 9 的 criteria review（`signoff-criteria`「每次 harden 後的檢查」，寫 `runs/<tag>_signoff/criteria_review.md`），學到的數字寫進該製程的 knowledge 檔。
- **golden**：第一次 signoff 全部 PASS、criteria review 也確認後，把那次 run 的 metrics 存成 golden（`signoff/golden/<tag>/`）。之後改了工具、PDK、RTL、config、SDC、macro 的產生檔，golden 比對一定 FAIL，要照 `signoff-checker-qualification` 規則 6 更新：先確認所有門檻與 checker PASS，逐項說明差異，複製並記 sha256，再跑一次確認 PASS。同樣設定重跑的差異怎麼給誤差也在該 skill。
- negative test：`make neg-pnr`（本 repo P00–P62）。

### 4.7 網表驗證

- 等價證明：合成網表對最終網表（`make eqy-soc`，`formal-equivalence-eqy`），negative test `make neg-eqy-soc`。**限制**：RTL 到合成網表這一段沒有 formal 證明（合成會重新編碼狀態機），由 gate-level 模擬加 directed 測試補（README「專案狀態」、`formal-equivalence-eqy`）。
- gate-level 模擬：RTL 與網表 lockstep（`make gl-soc`），含電源腳位的網表（`make gl-soc-powered`），negative test `make neg-gl-soc`（`gate-level-simulation`）。

### 4.8 一鍵 regression 與來源追溯

- `make regress`（Hazard3 版，`scripts/regress.py --cpu hazard3`）依序跑下列項目，第一個 FAIL 就停（實際清單：`scripts/regress.py` 的 `TARGET_LISTS`）：
  1. `env-check-flow py-check lint synth-check fw core-hazard3 regress-rtl neg-rtl`
  2. flow 的 checker：`neg-provenance`（來源追溯的植入錯誤）、`neg-run-guard`（下游拒絕 FAIL 或別的 commit 的 run）、`neg-regress`（regression 自己的植入錯誤）、`test-flow-retry`（偶發錯誤的重試）、`test-review-hook`（criteria review 的 Stop hook）、`neg-openram`、`neg-macro-views`
  3. `harden-soc eqy-soc neg-eqy-soc gl-soc gl-soc-powered neg-gl-soc neg-pnr`
  4. `provenance-final`：HEAD 與工作樹從 harden 開始後都沒變。
- `make regress-picorv32`：PicoRV32 版，把 `core-hazard3` 換成 `core-stock`，另加 4.4 的 `harden-core gl-core neg-gl-core eqy-core neg-eqy-core`。
- **不在 regression 裡、要另外跑的**：`ci-sram-ref`；macro 的產生、view QA、特性化與它們的確認（`openram-macro`、`macro-views`、`sram-char`／`openram-char`、`sram-confirm`／`openram-confirm`、`openram-check-lib`、`neg-char`）。這些在 macro 或量測方法有改時跑，結果進版控；regression 只檢查進版控的結果沒過期（`harden-soc` 開頭的 `check_inputs.py`）。
- 要在乾淨的 checkout 執行；乾淨的 worktree 沒有 `.tools/`，要設 `LIBRELANE_DIR`、`XPACK_DIR` 指到已安裝的副本。
- skill：`flow-regression-reproducibility`。

### 4.9 Phase 收尾

- 獨立審查、exit review（`docs/phase_exit/`）、經驗寫回 skill（`phase-exit-review`）。exit review 的證據只能來自乾淨 checkout 的端到端 run（該 skill 規則 2）。
- 清空 `runs/todo.md`（`CLAUDE.md` 規則 11）。

## 5. 遇到工具缺陷時

照 `CLAUDE.md` 規則 10：確認（出現兩次或實驗確認）之後，在對應的 skill 寫出症狀（確切訊息，也寫進 `description`）、怎麼發現、怎麼繞過（設定、repo 的 plugin 或 patch、有上限的重試，不改釘版工具本身），以及能抓到它再次出現的 checker 或 negative test。防護不能綁在 step 名稱、log 措辭這類 flow 會變的東西上。

## 6. 維護這份文件

- 流程的步驟、順序、checker 或 negative test 有改，同一個 commit 更新本文件；README 的「流程（簡易版）」只在大方向改變時才跟著改。
- 新專案發現的通用流程經驗寫回這裡（1.6）。
- 本文件 2026-10-09 建立後，由獨立 agent 逐條對照 repo 審查過一次（14 項中重度問題已修正）。
