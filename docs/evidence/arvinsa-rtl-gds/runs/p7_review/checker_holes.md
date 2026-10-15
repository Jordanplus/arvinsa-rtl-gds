# Phase 7 exit review：找 checker 漏洞（獨立審查）

審查者：沒有參與 Phase 7 實作的獨立 agent，2026-10-14，HEAD `84fe505`（working tree 乾淨，只寫了 `runs/p7_review/`）。
方法：讀每支 Phase 7 新增或改過的 checker，列出「設計或結果真的壞了，checker 卻 PASS」的可能；每個懷疑點都把輸入複製到
`runs/p7_review/holes/<案例>/`、植入錯誤、實際執行 checker，並跑一個沒植入的對照組（control）。沒有跑 LibreLane 完整 flow、
完整 EQY、gate-level 模擬或 VM；IR 只跑單一 `OpenROAD.IRDropReport` 步驟（每次約 1.3 分鐘，一次一個）。

## 結論

確認 **7 個漏洞**（checker 應該 FAIL 卻 PASS），另有 1 個覆蓋缺口（只靠其他 checker 間接抓到）。**這次交付的版圖沒有受影響**：
每個漏洞都查了正式結果（550869c 的 harden、`runs/ir_caravel`、`formal_550869c` precheck），沒有一個實際走到漏洞的路徑。

| # | 嚴重度 | checker／列 | 漏洞（白話） | 對這次交付的影響 |
|---|---|---|---|---|
| H1 | 中 | `scripts/check_pin_plan.py` approval | 規劃改了以後，自己用 `--digest` 重算 `plan_sha256` 填回去，**不需要使用者**就重新變成「已核准」。ADR 裡只要找得到引文就算數，而引文是「可以」（2 個字，ADR-0019 裡出現 4 次），ADR 也沒記錄核准的是哪一版（digest） | 無：現行 `plan_sha256` 與 ADR-0019 第 67 行的核准紀錄一致，規劃在核准後沒改過 |
| H2 | 中低 | `ir_caravel.py`（與 `ir_pattern.py`） | 不檢查 VCD 是不是用 signoff 週期錄的：錄波週期寫死在 Makefile（`--clk-half-ns 22`），沒有和 run 的 `CLOCK_PERIOD` 比。把 VCD 時間拉長 10%（等於用 48.4 ns 錄），所有列照樣 PASS，最差 IR 從 19.56 降到 19.18 mV。正式結果離上限只有 0.44 mV | 無：正式錄波的 log 是 `-DTB_CLK_HALF_NS=22`，與 `CLOCK_PERIOD` 44 ns 相符 |
| H3 | 中低 | `ir_caravel.py`、`ir_pattern.py` | 本身不呼叫 run guard（harden 沒 PASS、或不是目前 commit 做的 run 也照判），也不要求三個 window 都在（只給一個 `--vcd` 也 PASS） | 無：`make ir-caravel` 的第一步 `run_gl_soc.py` 有做 run guard；正式 run 三個 window 都有 |
| H4 | 中低 | `ir_pattern.judge()`、`ir_worst.py` | IR 數值是 NaN 時，`drop()` 不擋；找最差 corner 用 `max()`，NaN 在第二個 corner 時被略過，判 PASS（NaN 在第一個時才 FAIL，看順序） | 無：正式結果全部是有限數值 |
| H5 | 中低 | `signoff/scripts/check_signoff.py` judged_by | 任何 `[max_sum]` 上限加上 `judged_by = "<任意字串>"` 就變成 INFO，不檢查那個 target 存在、有沒有在 regression 裡跑、結果是不是 PASS | 無：只有 `ir_caravel_vdd_drop_plus_gnd_rise` 用了它，`make ir-caravel` 在 `regress-caravel` 裡 |
| H6 | 低 | `check_precheck.py` 時間列 | `project.json` 的時間戳把時區直接丟掉再比（`replace(tzinfo=None)`），+08:00 的時間戳在結果目錄開始前寫入也 PASS | 無：正式 `project.json` 是 `+00:00` |
| H7 | 低 | `check_precheck.py` 來源 | `arvinsa_source.json` 說 `verification: true`（沒過 run guard）或根本沒有這個檔，仍判 `precheck: PASS`（只印 INFO）；也不比對 GDS 是不是目前 harden run 的 GDS | 無：正式專案 `verification: false`、`run_guard: PASS`，GDS sha1 `29f7b599…` 與 `runs/user_project_wrapper/final/gds` 相同 |
| H8 | 低 | `check_inputs.py` inout_dont_touch | 向量只檢查 bit 0：`RSZ_DONT_TOUCH_RX = ^analog_io\[0\]$` 也 PASS，但 bit 1–28 仍會讓 `RepairDesignPostGRT` 中止於 RSZ-0074（錯誤是大聲的，代價是浪費一次數小時的 harden） | 無：現行設定 `^analog_io\[` 涵蓋全部 |
| G1 | 註記 | `check_pin_plan.py` localparams | 只比 localparam 的值，不檢查 RTL 有沒有用它（`uart_rx = io_in[30]`、localparam 仍是 36 也 PASS）。tb 把 GPIO 寫死（`dv/tb/tb_soc.v:104,139,141`），所以 RTL 改錯會在 DV FAIL；不算 checker 漏洞，但 pin-plan 本身抓不到 | 無 |

建議的優先順序：H1（規則 14 的核准是使用者明確要求的流程）→ H2/H3（離上限只有 0.44 mV 的判定，輸入卻沒有綁定）→ H4、H5（各兩三行就能修）→ H6–H8。

## 確認的漏洞：每個實驗

所有指令都在 repo 根目錄執行；log 在各案例目錄。

### H1 規劃核准可以不經使用者自行更新（`check_pin_plan.py` approval）

- **宣稱擋什麼**：「plan_sha256 = sha256 of the plan text before its [approval] line (a plan changed after the approval is no longer approved)」（`scripts/check_pin_plan.py` 說明）；CLAUDE.md 規則 14「規劃改了要重新核准（`plan_sha256`）」。
- **植入**：`runs/p7_review/holes/pp1_self_approval/`，三份 `--root` 複本（plan、config、範本 DEF、LEF、wrapper RTL、user_defines、ADR-0019）：
  - `control`：原樣。
  - `no_digest`：`uart_tx` 從 GPIO 37 改到 32（plan、`user_defines.v` 的 GPIO 32/37 模式、wrapper 的 `GPIO_UART_TX`），`plan_sha256` 不動。
  - `renewed`：同樣的改動，再用 `scripts/check_pin_plan.py --digest` 自己算新的 digest 填回 `[approval]`（日期、引文、ADR 都沒動）。
- **指令**：`python3 scripts/check_pin_plan.py --root runs/p7_review/holes/pp1_self_approval/<case> --design user_project_wrapper`
- **結果**：

  | 案例 | approval 列 | 結論 |
  |---|---|---|
  | control | PASS approved 2026-10-12 | `pin-plan: PASS` |
  | no_digest | FAIL plan_sha256 differs | `pin-plan: FAIL` |
  | renewed | **PASS approved 2026-10-12** | **`pin-plan: PASS`**（應該 FAIL：使用者沒看過 GPIO 32 的規劃） |

- **原因**：digest 由 checker 自己就能算；ADR 只檢查「包含引文」，引文「可以」很短且 ADR 裡有 4 處；ADR 沒記錄被核准的 digest。hook `.claude/hooks/require_pin_plan.py` 只擋 `[governs]` 的檔案，`pin_plan.toml` 本身（含 `[approval]`）不受管轄，所以「改規劃 → 重算 digest → 改 RTL」三步都不會被擋。
- **影響**：這次交付沒有；`plan_sha256 8c3c9693…` 是 ADR-0019 第 67 行記錄核准時的規劃。
- **建議修正**：
  1. 核准時把 `plan_sha256` 寫進 ADR 的核准那一段，checker 要求「同一段（或同一行）同時有引文、日期與 digest」；這樣更新核准一定要改 ADR，會出現在 commit diff 裡。
  2. hook 把 `pnr/*/pin_plan.toml` 的 `[approval]` 也列為受管轄（改 `plan_sha256`／`quote`／`date` 的 Edit 一律擋下並提示「請使用者自己填」），與規則 13 的「由使用者決定」一致。
  3. 引文太短時（例如少於 4 個字），要求 ADR 的同一行另有日期與 digest，避免任意子字串都對得上。
- **negative test**：`neg_pin_plan.py` 加一個案例：改規劃後只重算 digest（ADR 不動）→ approval 列 FAIL。

### H2 IR 的錄波週期沒有和 signoff 週期比（`ir_caravel.py`）

- **宣稱擋什麼**：`ir_caravel.py` 說明「with the switching activity of each --vcd window: the max-power pattern recorded on the final netlist (... 44 ns clock; ADR-0019 decision 20)」。實際只檢查「VCD 註記到的 pin 數 > 0、未註記 = 0」。
- **植入**：`runs/p7_review/holes/ir2_vcd_period/win_5c_x1p1.vcd`：正式的 `runs/ir_caravel_vcd/win_5c.vcd`，每個時間戳 ×1.1（同樣的翻轉，時脈變成 48.4 ns；等同 run 的 `CLOCK_PERIOD` 若改成 40 ns 而 Makefile 仍用 `--clk-half-ns 22` 錄）。
- **指令**：`runs/p7_review/holes/ir2_vcd_period/run_corner.py <vcd> <tag> <work>`：用正式 run 的 `runs/ir_caravel/ir_caravel/pads` 步驟呼叫 `ir_worst.run_corner()`（`ir_caravel.py` 判定時呼叫的同一個函式），corner `max_ss_100C_1v60`（正式結果最差的 corner）。
- **結果**（`control.log`、`x1p1.log`）：

  | 案例 | currents／supply points／activity 三列 | Total power | VDD + GND |
  |---|---|---|---|
  | control（原 VCD） | 全 PASS，73872 pins annotated, 0 unannotated | 5.08 mW | 11.92 + 7.65 = **19.56 mV**（與正式 log 相同） |
  | 時間 ×1.1 | **全 PASS**，73872 annotated, 0 unannotated | 4.98 mW | 11.68 + 7.50 = **19.18 mV** |

  checker 看不出錄波週期錯了。這個案例的 IR 只少 0.38 mV（功耗大部分不隨資料翻轉變化：同 corner 的 vectorless 是 11.6 mW），但正式結果離 20 mV 上限只有 0.44 mV，這個量級已經足以把 FAIL 變 PASS。
- **影響**：無。正式錄波的 compile log 有 `-DTB_CLK_HALF_NS=22`（`runs/ir_caravel_vcd/run_5a/icarus/maxpower/sim.log`），`CLOCK_PERIOD` 是 44（`pnr/user_project_wrapper/config.json:55`）。風險在下一顆設計或改週期時：Makefile 的 22 不會跟著變。
- **建議修正**：`ir_caravel.py`／`ir_pattern.py` 從 VCD 量出時脈週期（`tb_soc.clk` 相鄰兩個上升緣，或 `run_gl_soc.py --record-window` 把實際週期寫進一個 sidecar JSON），要求等於 run 的 `CLOCK_PERIOD`；Makefile 的 `--clk-half-ns` 改成從 config 的 `CLOCK_PERIOD` 算。
- **negative test**：`neg_ir.py` 加 `period`：把一個 window 的時間戳 ×1.1（或用 `--clk-half-ns 24` 錄）→ 新的週期列 FAIL。

### H3 IR 判定本身沒有 run guard，也不要求三個 window 都在

- **宣稱擋什麼**：`run_guard.py` 說明「Shared check for every step that uses the output of a harden run」；`ir_caravel.py` 判「The largest VDD drop + GND rise over windows」，Makefile 給 5a、5b、5c 三個 window。
- **植入**：`runs/p7_review/holes/rg1_ir_no_guard/`：對目前已經被 run guard 拒絕的 `runs/user_project_wrapper`（550869c 做的、HEAD 是 84fe505）直接跑 `ir_caravel.py`，而且只給一個 window（`win_5b`，三個裡 IR 最小的）。
- **對照**：`python3 signoff/scripts/run_guard.py runs/user_project_wrapper "harden-soc: PASS"` → `run-guard: FAIL`（`guard.log`）。
- **指令**：`python3 pnr/user_project_wrapper/ir_caravel.py runs/user_project_wrapper runs/p7_review/holes/rg1_ir_no_guard signoff/limits/user_project_wrapper.toml --vcd runs/ir_caravel_vcd/win_5b.vcd`
- **結果**（`ir_caravel.log`，約 9 分鐘）：所有列 PASS，`[PASS] drop: worst max_ss_100C_1v60_win_5b 19.13 mV ... vs max 20.0 mV`、**`ir-caravel: PASS`、rc=0**。輸入的 run 已被 run guard 拒絕，而且三個 window 只給了一個（IR 最小的 5b，比最差的 5c 少 0.43 mV），checker 都沒有反應。
- **影響**：無。`make ir-caravel` 第一步 `run_gl_soc.py --record-window` 有呼叫 `guard()`（`dv/gl_soc/run_gl_soc.py:138`），guard 不過就不會走到 `ir_caravel.py`；正式判定三個 window 都在（`runs/p7_formal2_ir.log`）。漏洞只在單獨執行 `ir_caravel.py`／`ir_pattern.py`（例如重判或 README 示範）時出現，而 `neg_run_guard.py` 的 STEPS 沒有涵蓋這兩支。
- **建議修正**：`ir_caravel.py`、`ir_pattern.py` 開頭呼叫 `guard(run, "harden-soc: PASS")`；window 清單（5a、5b、5c）放進 limits 或 config，判定要求每個都有結果；`neg_run_guard.py` 的 STEPS 加這兩支。

### H4 IR 數值是 NaN 時被略過（`ir_pattern.judge()`、`ir_worst.py`）

- **宣稱擋什麼**：`ir_worst.drop()`「VDD drop + GND rise in V, or None when a key is missing or negative」；judge 取所有 window × corner 的最大值比上限。
- **植入**：`runs/p7_review/holes/ir1_nan/`：手寫的 `results.json`（格式同 `ir_pattern.write_results`），兩個 corner：
  - `control`：17.0、18.6 mV → 應 PASS
  - `over`：17.0、25.0 mV → 應 FAIL
  - `nan_second`：17.0 mV、第二個 corner 的 VDD 是 NaN → 應 FAIL
  - `nan_first`：第一個 corner 是 NaN、第二個 18.6 mV → 應 FAIL
- **指令**：`python3 pnr/soc_top/ir_pattern.py --judge <case>.json signoff/limits/soc_top_hazard3.toml`；另外直接呼叫 `ir_worst.drop({'a': nan, 'b': 0.007}, ['a','b'])`。
- **結果**（`run.log`）：control PASS、over FAIL（對照組正常）；**`nan_second`：`[PASS] drop: worst max_ss_n40C_1v60_win_5a 17.00 mV`，`ir-soc: PASS`**；`nan_first`：FAIL（`nan mV`）。`drop()` 對 NaN 回傳 `[nan, 0.007]`，不是 None。原因：`nan < 0` 是 False，`max()` 比較 NaN 一律 False，所以 NaN 只有排第一時才會被選為最差。`ir_worst.py` main 的最差值也是同一段寫法。
- **NaN 會不會真的出現**（推測）：LibreLane 用 Python `float()` 讀 OpenROAD 的 metric，`float("nan")` 合法，`json.dump` 也會寫出 `NaN`；PSM 解不出來時是否會印 nan 沒查證。
- **影響**：無，正式結果都是有限數值。
- **建議修正**：`drop()` 改成 `not math.isfinite(v) or v < 0` 就回傳 None（`check_signoff.py` 的 `finite()` 已經這樣做）。
- **negative test**：`neg_ir.py` 加 `nan_drop`：把 positive `results.json` 第二個 drop 改成 NaN → FAIL。

### H5 `judged_by` 可以讓任何 `[max_sum]` 上限變成 INFO（`check_signoff.py`）

- **宣稱擋什麼**：`check_signoff.py` 說明「a limit another checker judges on its own data (e.g. make ir-caravel ...): printed as INFO」。negative test P81 只測了空字串的 judged_by。
- **植入**：`runs/p7_review/holes/so1_judged_by/`，wrapper 正式 run 的 `metrics.json` 與 golden，limits 複本：
  - `over.toml`：`ir_vdd_drop_plus_gnd_rise` 的 max 改成 0.001（run 是 4.09 mV）
  - `over_judged_by.toml`：同上，再加 `judged_by = "make no-such-target"`
- **指令**：`python3 signoff/scripts/check_signoff.py runs/user_project_wrapper_signoff/metrics.json <limits> signoff/golden/user_project_wrapper/metrics.json`
- **結果**：control（原 limits）`signoff: PASS`；`over` → `[FAIL] max ir_vdd_drop_plus_gnd_rise ... run=0.00409432 expected=<= 0.001`、`signoff: FAIL`；**`over_judged_by` → `[INFO] ... judged by make no-such-target`、`signoff: PASS`**（不存在的 target）。
- **影響**：無；現行只有 `ir_caravel_vdd_drop_plus_gnd_rise` 用了 judged_by，`make ir-caravel` 在 `scripts/regress.py` 的 caravel 清單裡。
- **建議修正**：judged_by 必須是 `make <target>`，target 存在於 Makefile，且在 `scripts/regress.py` 的 `TARGET_LISTS` 裡（至少一個 CPU）；更好的是 check_signoff 或 review_criteria 讀那個 target 的結果檔（例如 `runs/ir_caravel/ir_caravel/results.json` 重新 `--judge`）。
- **negative test**：P81 加一個子案例：judged_by 指向不存在的 target → FAIL。

### H6 precheck 的時間戳比對丟掉時區（`check_precheck.py`）

- **宣稱擋什麼**：「project.json was written after that directory's start」（避免讀到前一次 run 的 project.json）。
- **植入**：`runs/p7_review/holes/pc1_timezone/`：neg_precheck 的 fixture（`runs/neg_precheck/base`，結果目錄 `14_OCT_2026___00_00_00`，UTC），`project.json` 的 `timestamp` 改成 `2026-10-14T07:00:00+08:00`（= 10-13 23:00 UTC，在結果目錄開始前 1 小時）。
- **指令**：`python3 signoff/precheck/check_precheck.py --project <case>/project --ref-dir <case>/ref --out <case>/out`（`mk_pc.sh` 建複本）
- **結果**：control（`pc0_control`）PASS；**植入的也是 `[PASS] project.json written 2026-10-14 07:00:00, after the results directory's start 2026-10-14 00:00:00`、`precheck: PASS`**。
- **影響**：無；正式 `project.json` 是 `2026-10-14T07:33:42.057711+00:00`。這一列是次要防護（`logs/gds.info` 的 sha1 已綁定 GDS）。
- **建議修正**：`datetime.fromisoformat(...).astimezone(timezone.utc).replace(tzinfo=None)`；沒有時區的時間戳直接 FAIL。
- **negative test**：`neg_precheck.py` 加 `results_after_tz`：`+08:00` 且換算後早於開始 → FAIL。

### H7 precheck 判定不管專案來源（`check_precheck.py`）

- **宣稱擋什麼**：`make_project.py`「The run must pass the run guard ... --verification skips that for a check of an older run」；`check_precheck.py` 只把來源印成 INFO。
- **植入**：`runs/p7_review/holes/pc2_verification/`：fixture 加一個 `arvinsa_source.json`，`{"run": "runs/some_old_run", "run_commit": "deadbee", "verification": true}`。另外 `pc0_control` 本身就沒有 `arvinsa_source.json`。
- **結果**：兩者都 `precheck: PASS`；`pc2` 只多一行 `[INFO] ... verification, run guard skipped`。
- **影響**：無。正式 `formal_550869c/arvinsa_source.json` 是 `run_guard: PASS`、`verification: false`；GDS sha1 `29f7b5994c7192365affa97bcd95dcdd3c94e33f` 與 `runs/user_project_wrapper/final/gds/user_project_wrapper.gds` 相同。風險是 Phase exit 引用 `make precheck-check PRECHECK_PROJECT=<查證用目錄>` 的 PASS 當正式證據。
- **建議修正**：預設模式要求 `arvinsa_source.json` 存在、`run_guard == "PASS"`、`verification == false`，而且 `files["gds/..."].sha1` 等於專案 GDS；查證用另給 `--verification` 旗標，verdict 改印 `precheck: PASS (verification only)`，讓 regression 與 exit review 不會誤用。
- **negative test**：`neg_precheck.py` 加 `verification_source`（verification true → FAIL）與 `no_source`（沒有 `arvinsa_source.json` → FAIL）；fixture 要補一份正常的 `arvinsa_source.json`。

### H8 inout_dont_touch 只看向量的 bit 0（`check_inputs.py`）

- **宣稱擋什麼**：「every inout port of the top module ... is matched by RSZ_DONT_TOUCH_RX (bit 0 of a vector, e.g. analog_io[0])」，防 `RepairDesignPostGRT` 中止於 RSZ-0074。
- **植入**：`runs/p7_review/holes/ci1_inout_bit0/config_bit0.json`：wrapper config 複本，`RSZ_DONT_TOUCH_RX = "^analog_io\\[0\\]$"`。
- **指令**：`python3 pnr/soc_top/check_inputs.py --cpu caravel [--config <copy>]`
- **結果**：control `[PASS] inout_dont_touch ... '^analog_io\\['`；植入的也是 **`[PASS] inout_dont_touch: ... all matched by RSZ_DONT_TOUCH_RX '^analog_io\\[0\\]$'`**、`soc-inputs: PASS`。`analog_io[1..28]` 不是 dont_touch，`p7_harden2` 的 RSZ-0074 停在 `analog_io[9]`（`.claude/skills/librelane-run-debug/SKILL.md` 經驗紀錄），所以這個設定會讓 harden 中止。
- **影響**：無；後果是大聲的 flow 錯誤，不是假 PASS，代價是浪費一次 harden（wrapper 數小時）。
- **建議修正**：從 port 宣告的範圍展開每一個 bit（`check_soc.top_ports` 已有展開的寫法），每個 bit 都要被 regex 涵蓋。
- **negative test**：P79 加一個子案例：regex 只涵蓋 bit 0 → FAIL 並列出 `analog_io[1]`。

### G1（覆蓋缺口）pin-plan 不檢查 localparam 有沒有被用到

- **植入**：`runs/p7_review/holes/pp2_localparam_unused/`：wrapper 的 `uart_rx = io_in[GPIO_UART_RX]` 改成 `io_in[30]`，localparam 仍是 36。
- **結果**：`[PASS] localparams: ... 4 localparams as planned`、`pin-plan: PASS`。
- **為什麼不列為漏洞**：tb 把 GPIO 寫死（`dv/tb/tb_soc.v:104` `io_in = {1'b0, uart_rx, ...}` 在 GPIO 36、`:139` `uart_tx = io_out[37]`），用 UART 載入的測試會在 `regress-rtl-caravel` FAIL。但 tb 的 GPIO 不受 `pin_plan.toml` 管轄：規劃與 RTL 一起改、tb 也跟著改時，三邊一致但都沒經核准，要靠 H1 修好。
- **建議**：tb 的 GPIO 編號從 wrapper 的 localparam 取（`dut.GPIO_UART_RX`），或 pin-plan 檢查 tb 的對應。

## 沒有確認為漏洞的懷疑點（實驗或現有證據顯示 checker 抓得到）

| 懷疑 | 怎麼查 | 結果 |
|---|---|---|
| `read_vcd` 用「VCD 結束時間」而不是「window 長度」算翻轉率（window 從 67／301／523 µs 才開始錄，會把活動量稀釋成 0.78／?／0.29 倍） | 比正式三個 window 的 Total power（`runs/ir_caravel/ir_caravel/corners/max_ss_100C_1v60_win_*/step/openroad-irdropreport.log`）：5a（234 µs window，結束於 301 µs）5.06 mW、5c（216 µs，結束於 739 µs）5.08 mW | 兩者幾乎相同；若用結束時間正規化，5c 會明顯小於 5a。OpenSTA 用的是 window 長度，沒有漏洞 |
| 部分 net 沒被 VCD 註記時改用 vectorless 預設，unannotated 仍是 0 | 讀 `report_activity_annotation` 輸出：只有 `vcd` 與 `unannotated` 兩類，沒有其他來源類別 | 沒註記到的 pin 會計入 unannotated；`neg_ir.py unannotated`（scope 改名）也確認 0 annotated 會 FAIL |
| `check_soc.py disconnected` 只比數量 | 讀程式：比對的是集合（`got_sig - exp_sig`、`exp_sig - got_sig`），數量另外比；`neg_pnr.py --cpu caravel` C15 用「同數量、換一支」驗過 | 抓得到 |
| `check_soc.py max_slew` 欄位順序讀錯（把 Limit 當 Slew） | 對照正式 `runs/user_project_wrapper/57-openroad-stapostpnr/max_ss_n40C_1v60/checks.rpt` 第 363 行欄位 `Pin Limit Slew Slack`；regex 取第二個數字 = Slew；表格數量另與 `max slew violation count` 比 | 正確；C80a/b/c 涵蓋內部 pin、超過外部 transition、數量不符 |
| max_slew 例外把同名的內部 net 也放過 | 讀程式：先查 pin 所在的 net，再去掉 `[...]` 後比 SDC 的 port 名稱；扁平 wrapper 內部 net 是 `\u_soc.…` 或 `_NNNN_` 形式，不會等於 port 名稱；查不到 net 時判 FAIL | 沒有漏洞 |
| EQY amend 把 flip-flop 併進分區造成空洞證明 | 讀程式：`amend_rules` 排除 gold 網表的 sequential instance，另有 `amended_sequential()` 檢查第二輪分區 RTLIL 有沒有 `$*dff*`／`$*latch*`／`$sr`（雙重防護）；`neg_eqy.py nand2_to_nor2` 是它的 negative test；正式 `runs/eqy_user_project_wrapper/summary.json`：`amended_sequential: {}`、16149/16149 | 有防護（完整 EQY 不能跑，沒做植入實驗） |
| precheck 讀到別次 run 的報表 | `neg_precheck.py` 的 `stale_results`、`other_gds`、`total_mismatch` | 抓得到（H6 只是其中時間戳那一列的時區問題） |
| precheck 的 SRAM 外有 MR 違規、或 SRAM 內多一個位置 | `neg_precheck.py` 的 `outside`、`moved`、`two_macros` | 抓得到 |
| `ir_caravel.py` 的 Caravel 電源網路沒接上（IR 變樂觀） | 讀 log：`PSM-0040 All shapes on net vccd1 are connected`；橋或 pad strap 少接只會讓供電點變少、IR 變大（偏悲觀）；`neg_ir.py bridge_missing`／`pad_missing` 檢查數量 | 方向是悲觀的，不是假 PASS |
| 錄波時 testbench 另外整段 dump（plusarg 前綴撞到 `vcd`） | `neg_ir.py stray_dump` | 抓得到 |

## 附帶觀察（不是 checker 漏洞，給 exit review 參考）

- IR 的組成：同一個 corner，max-power pattern 5.08 mW、vectorless 11.6 mW；把翻轉率降 9% 只少 2% 功耗，代表大部分功耗不隨資料翻轉變化（漏電、clock 網路、SRAM）。正式最差 19.56 mV 對 20 mV 上限只剩 0.44 mV，任何讓輸入偏樂觀的小差錯（H2、H3）都可能改變結論，這是把 H2、H3 排在前面的原因。
- `make ir-caravel` 的 run guard 只在錄波那一步；如果之後有人用現成的 VCD 只重跑 `ir_caravel.py`（例如調整 Caravel 電源資料後），就沒有 guard（H3）。
- precheck VM 的 image 是 `chipfoundry/mpw_precheck:latest`（`env/check_env.sh`）；check_precheck 只釘 cf-precheck 版本，image 裡的 KLayout／Magic／Netgen 版本沒有比對（`run_precheck.sh` 有記 digest）。這是刻意跟著官方最新版，不列為漏洞。

## 審查期間主 checkout 的變動

審查中途（約在 H3 實驗執行時），主 checkout 出現不是本審查造成的未提交修改（`git status`：14 個檔，包括 skill、README、ADR-0019，以及 `ir_caravel.py`、`neg_precheck.py`、`neg_run_guard.py` 的說明文字）。我看過三支 checker 的 diff，都只改 docstring，不影響上面的結論。所有實驗都用 HEAD `84fe505` 的程式碼；H1 的 ADR 複本與 HEAD 的版本相同（已用 diff 確認）。

## 實驗檔案

`runs/p7_review/holes/`：`pc0_control`、`pc1_timezone`、`pc2_verification`（H6、H7；`mk_pc.sh` 建複本）、`ir1_nan`（H4）、`ir2_vcd_period`（H2）、`rg1_ir_no_guard`（H3）、`so1_judged_by`（H5）、`pp1_self_approval`（H1）、`pp2_localparam_unused`（G1）、`ci1_inout_bit0`（H8）。每個目錄有植入後的輸入、執行 log 與對照組。
