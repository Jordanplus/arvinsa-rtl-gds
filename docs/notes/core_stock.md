# core-stock（L1a）：上游 PicoRV32 regression test

最後更新：2026-10-03　對應 script：`scripts/core_stock.sh`（`make core-stock` 呼叫它）
依據：`docs/spec/soc_spec.md` §8、§9 第 2 條；`project-plan.md` §5.3、§7.1（L1a）。

## 1. 這在做什麼

L1a 是「CPU core 本身」的 regression test：不經過我們自己的 SoC，直接跑 PicoRV32 上游自帶的測試，確認我們釘住的那一版 core（`third_party/picorv32` @ `ef203c2b0a3f`，見 `env/versions.mk` 的 `PICORV32_COMMIT`）在本機工具下行為正確。用途是把「core 本身有問題」與「我們的 SoC glue 有問題」分開：L1a PASS 但 L1b（SoC RTL 模擬）FAIL，就先懷疑 glue。

執行方式：

```
make core-stock                 # 或 bash scripts/core_stock.sh
```

產出：`runs/core_stock/summary.txt`（結果彙整）、`runs/core_stock/logs/<target>.log`（每個上游 make target 的完整輸出）。`runs/` 已被 gitignore。任何必要 target FAIL 時，script 以非 0 結束。

## 2. 執行流程

1. **Preflight**：確認 `iverilog`、`vvp`、`yosys`、`riscv64-elf-gcc`、`riscv64-elf-objcopy`、`python3`、`make`、`git` 都在 PATH；確認 submodule 的 HEAD 等於 `env/versions.mk` 釘的 commit。任一不符就 FAIL 並結束（exit 2，寫 `summary.txt`）。
2. **匯出**：`git -C third_party/picorv32 archive HEAD | tar -x -C runs/core_stock/src`。所有編譯與模擬都在這份複本裡做，submodule 工作目錄完全不會被改到。
3. **跑上游 Makefile**（不改任何上游檔案）：`make TOOLCHAIN_PREFIX=riscv64-elf- <target>`，依序 `test`、`test_ez`、`test_wb`、`test_synth`，最後處理 `test_rvf`。
4. **依 §4 的準則判斷 PASS／FAIL**。
5. **事後檢查**：再跑一次 `git -C third_party/picorv32 status --porcelain`，必須是空的、HEAD 沒變；否則整體 FAIL。
6. 寫 `summary.txt`（含實際使用的工具版本與是否與 `toolchain.md` 一致），依結果決定 exit code。

每次執行都會先清掉並重建 `runs/core_stock/src`、`logs/`、`summary.txt`，所以結果不依賴上一次的殘留檔案。

## 3. 各 target 在測什麼

| target | 上游做的事 | 測試對象 |
|---|---|---|
| `test` | Icarus 模擬 `testbench.v`（AXI4 介面的 PicoRV32 + 記憶體模型）。載入 `firmware/firmware.hex`：45 個單一指令測試（`tests/*.S`，每個印 `<名稱>..OK`）、sieve（質數篩，自帶 checksum 比對）、乘除法 hard/soft 比對（`multest`）、IRQ（`irq.c`）、`stats`，最後印 `DONE`，寫 `123456789` 到 `0x20000000` 後 `ebreak` | core ISA 行為、IRQ、乘除法 |
| `test_ez` | Icarus 模擬 `testbench_ez.v`：只有 6 個 word 的小程式（計數器反覆 `lw`／`addi`／`sw` 到 `0x3fc`），印出每筆 native memory bus 交易，跑 1000 個 clock 後 `$finish` | native memory 介面的最小 smoke test |
| `test_wb` | 同 `test` 的 firmware，但用 `testbench_wb.v`（PicoRV32 的 Wishbone 包裝 `picorv32_wb`） | Wishbone 介面 |
| `test_synth` | 先用本機 Yosys 以 `scripts/yosys/synth_sim.ys`（`read_verilog`、`chparam`、`hierarchy`、`synth`、`write_verilog`）把 `picorv32_axi` 合成成 `synth.v`，再用 `testbench.v`（`-DSYNTH_TEST`）跑同一份 firmware | Yosys generic 合成後的 netlist 與 RTL 行為一致（不是 sky130 標準元件庫的 gate-level 模擬，也沒有 SDF） |
| `test_rvf` | 以 `-D RISCV_FORMAL` 編 `testbench.v`＋`rvfimon.v`，由 rvfi monitor 即時檢查每筆退休指令的 ISA 語意 | 逐指令 ISA 語意 checker。**本機 N/A，見 §6** |

## 4. PASS／FAIL 判斷準則

`make` 的 exit code 為 0 **而且**下列條件全部成立才算 PASS，缺任何一項都是 FAIL（包括「exit code 0 但沒印成功字串」）：

**`test`、`test_wb`、`test_synth`**。成功字串的出處：`testbench.v` 第 263–268 行與 `testbench_wb.v` 第 156–161 行（`TRAP after N clock cycles`，接著依 `tests_passed` 印 `ALL TESTS PASSED.` 或 `ERROR!`）；`tests_passed` 只在 firmware 寫入 `123456789` 到 `0x20000000` 時被設起（`testbench.v` 第 420 行、`testbench_wb.v` 第 262 行；firmware 端是 `firmware/start.S` 第 494 行）；單一指令測試的 `<名稱>..OK`／`<名稱>..ERROR` 來自 `tests/riscv_test.h` 的 `RVTEST_CODE_BEGIN`、`RVTEST_PASS`、`RVTEST_FAIL`；`DONE` 來自 `firmware/start.S` 第 480 行起。

- 有一行完全等於 `ALL TESTS PASSED.`。
- 有一行 `TRAP after <N> clock cycles`，且有 firmware 的 `DONE` 行。
- `tests/*.S` 的每一個檔案都有對應的 `<名稱>..OK` 行（目前 45 個；逐一比對，不是只數總數）。
- log 裡沒有 `ERROR!`（testbench 判定失敗，以及 `multest` 的 hard/soft 不一致）、`..ERROR`（單一指令測試失敗）、`TIMEOUT`（testbench 跑滿 1,000,000 個 clock 的 timeout，它印完仍以 exit 0 結束，所以一定要靠字串）、`OUT-OF-BOUNDS`（存取模型外的位址）。
- `test_synth` 另外要求 `synth.v` 存在且非空。

這些條件裡，缺 `ALL TESTS PASSED.` 本身就涵蓋 sieve／`multest` 的自我比對失敗：它們失敗時會執行 `ebreak`（`firmware/sieve.c`、`firmware/multest.c`），CPU 在寫 `123456789` 之前就 trap，testbench 印 `ERROR!`。

**`test_ez`**：上游 `testbench_ez.v` **不印任何成功字串**（它只印 bus 交易，跑 1000 個 clock 後在第 24–25 行 `$finish`），所以沒有「上游明確的成功字串」可以比對。依規格「找不到成功字串就是 FAIL」的精神，改用一個由程式內容推導出來的 checker（這是我們加的，不是上游的）：

- 第一筆 `ifetch` 必須是 `0x00000000: 0x3fc00093`（`li x1,1020`）。
- 每一行 bus 交易格式都必須完整（出現 X／Z 就判 FAIL）。
- 寫入 `0x3fc` 的值必須是 0、1、2、……連續遞增、不跳號，且至少 32 筆（實測 45 筆，0..44）。
- 每次讀 `0x3fc` 回來的值必須等於最近一次寫入的值。
- log 裡沒有 `ERROR`、`TIMEOUT`、`OUT-OF-BOUNDS`。

**`submodule_clean`**（事後檢查）：`git -C third_party/picorv32 status --porcelain` 為空，且 HEAD 仍是釘住的 commit。

## 5. 結果（2026-10-03）

環境：macOS（Darwin 25.6.0，arm64）；工具版本見 §7。以下是從空的 `runs/core_stock/` 開始，執行 `make core-stock`（exit code 0）的實際結果，取自 `runs/core_stock/summary.txt`（2026-10-03 09:26 +0800）。

| target | 結果 | 成功證據（來自 log） | 時間 |
|---|---|---|---|
| `test` | PASS | `ALL TESTS PASSED.`、`DONE`、45/45 個指令測試 OK、`TRAP after 474601 clock cycles` | 12 s |
| `test_ez` | PASS（推導的 checker） | `0x3fc` 計數 0..44，共 45 筆寫入、讀回一致、無 X／Z | < 1 s |
| `test_wb` | PASS | `ALL TESTS PASSED.`、`DONE`、45/45 OK、`TRAP after 871658 clock cycles` | 14 s |
| `test_synth` | PASS | `ALL TESTS PASSED.`、`DONE`、45/45 OK、`TRAP after 474601 clock cycles`（與 RTL 的 `test` 週期數相同）；`synth.v` 約 1.0 MB（1,002,766 bytes） | 165 s |
| `test_rvf` | N/A | 見 §6 | 0 s |
| `submodule_clean` | PASS | `git status --porcelain` 為空，HEAD 仍為 `ef203c2b0a3f` | 0 s |

整體：`core-stock: PASS`，exit code 0。**總執行時間約 191 s**（其中 `test_synth` 佔 165 s：它是在 Icarus 上跑 Yosys 合成出來的 `synth.v`，慢是預期的）。同一個 script 在這次修訂內另外從空目錄跑過兩次（其中一次在我修改 script 的註解與訊息文字之前），結果相同（總時間 188–192 s）。

build 過程只有一則 linker 訊息：`riscv64-elf-ld: warning: firmware/firmware.elf has a LOAD segment with RWX permissions`（`logs/test.log` 內）。這是新版 binutils 對上游 `sections.lds`（code 與 data 放同一個 segment）的提醒，不影響結果，未處理。

## 6. N/A 項目：`test_rvf`

- 原因：`test_rvf` 依賴 `rvfimon.v`（`third_party/picorv32/Makefile` 第 61 行：`testbench_rvf.vvp: testbench.v picorv32.v rvfimon.v`）。`testbench.v` 在 `RISCV_FORMAL` 下會 instantiate `picorv32_rvfimon`，但 PicoRV32 repo 內沒有這個檔案，也沒有這個 module 的定義（`git -C third_party/picorv32 ls-files` 找不到 rvfi 相關檔案；本 repo 內 `grep -rn "module picorv32_rvfimon" third_party ip rtl dv` 無結果；本機 `mdfind -name rvfimon` 也找不到）。上游 `README.md` 開頭只說 core 的 formal verification 要用 riscv-formal（`github.com/YosysHQ/riscv-formal`）。「`rvfimon.v` 是由 riscv-formal 的 monitor generator 產生」是我的背景知識，repo 內無法驗證，屬推測。無論如何，riscv-formal 不在本 repo 內、需要網路下載、也不在 `toolchain.md` 的工具清單上；依規格 §1「不得安裝新工具、只能用 `toolchain.md` 列出的工具」，標 N/A。
- 實際證據：script 在 repo 內搜尋 `rvfimon.v`（排除 `runs/`）找不到後，仍真的執行一次 `make test_rvf`，得到 `make: *** No rule to make target `rvfimon.v', needed by `testbench_rvf.vvp'.  Stop.`（`runs/core_stock/logs/test_rvf.log`；經 `make core-stock` 呼叫時前綴是 `make[1]:`）。script 只接受這一種失敗訊息當作 N/A；失敗原因不同則判 FAIL。
- 「`rvfimon.v` 存在」這條路徑的驗證：repo 內沒有真的 `rvfimon.v`，所以用一個**空殼** `picorv32_rvfimon`（port 與 `testbench.v` 對齊、不做任何檢查）放在 `runs/` 下的暫存目錄，指給 script 的複本。結果 `test_rvf` 依 `test` 的規則判成 PASS（`ALL TESTS PASSED.`、45/45、474601 cycles）。這只證明 script 的流程會走通，**不代表** rvfi monitor 的檢查有跑；空殼已刪除，正式 script 不含它。
- 該路徑的副作用：上游 `test_rvf` 規則以 `+vcd` 執行，用空殼實測 `testbench.vcd` 就有約 370 MB（寫在 `runs/core_stock/src` 內）。日後真的補上 `rvfimon.v` 時要預留這個磁碟空間。
- **覆蓋缺口**：N/A 代表「逐指令的 ISA 語意即時 checker」這一項目前沒有被執行。`test`／`test_wb`／`test_synth` 的 45 個指令測試加上乘除法比對仍涵蓋 ISA 結果，但不能取代 rvfi monitor 的逐筆比對，這是 L1a 目前最弱的一環。
- 替代方式（規格 §9 第 2 條要求說明）：目前沒有等效的離線替代。要補上需要主控決定把 riscv-formal 以固定 commit 納入專案（例如 submodule 加 ADR、更新 `toolchain.md`）。

## 7. 工具版本與 override

實際使用的版本（取自 `summary.txt`；`env/check_toolchain_doc.py` 對 `toolchain.md` 判定一致）：

| 工具 | 版本 |
|---|---|
| Icarus Verilog（`iverilog`／`vvp`） | 13.0 |
| Yosys | 0.69+post（git `143eb14f`） |
| `riscv64-elf-gcc` | 16.1.0 |
| `riscv64-elf-binutils`（`ld`、`objcopy`） | 2.46.1 |
| Python | 3.14.6（只用標準函式庫） |
| GNU make／bash | 3.81／3.2.57 |

make 命令列 override（寫在 `scripts/core_stock.sh` 的 `MAKE_ARGS`，上游檔案一律不改）：

| override | 原因 |
|---|---|
| `TOOLCHAIN_PREFIX=riscv64-elf-` | 上游預設是 `/opt/riscv32i/bin/riscv32-unknown-elf-`（`Makefile` 第 18 行），本機沒有；規格 §6.1 規定的前綴就是 `riscv64-elf-` |
| 沒有其他 override | 先用上游預設值試跑：GCC 16.1 沒有讓上游 `GCC_WARNS`（含 `-Werror`）觸發任何 warning（`logs/test.log` 內 C 檔編譯行都乾淨通過），`-march=rv32imc`、`rv32ic`、`rv32im` 在 binutils 2.46.1 下都能組譯，不需要 `_zicsr`，所以不加 `GCC_WARNS=` 或 `-march=` 的覆寫 |

## 8. 這支 script 本身的驗證（negative test）

regression 的 checker 如果抓不到錯誤，PASS 就沒有意義，所以用 bug injection 確認 checker 真的會 FAIL。以下全部在 `runs/core_stock/neg/` 的 script 複本（改寫輸出目錄）上做，已清掉，不影響正式 script。為了能在不重新跑模擬的情況下改 log，用一支假的 `vvp` 重播先前錄下的真實模擬輸出（可選擇性改動），其餘 make／編譯流程是真的。先跑**對照組**：重播未改動的輸出，`test`、`test_ez` 都 PASS（證明這套重播方法本身沒有讓 checker 誤判）。

| 植入的錯誤 | 預期 | 實際 |
|---|---|---|
| 真實 RTL bug injection：把匯出複本 `picorv32.v` 第 1240 行 `alu_add_sub = instr_sub ? reg_op1 - reg_op2 : reg_op1 + reg_op2;` 改成永遠做加法，跑 `test`、`test_wb` | 兩者 FAIL，script 非 0 結束 | 兩者 FAIL（`make` 非 0；log 出現 `auipc..ERROR`、`TRAP after 36323 clock cycles`、`ERROR!`；只有 1/45 個指令測試 OK）；整體 `core-stock: FAIL`，exit 1 |
| 用 `VVP=true` 讓模擬器根本沒跑（exit code 0、沒有輸出）| `test`、`test_ez` 都 FAIL | 兩者 `rc=0` 仍判 FAIL（缺 `ALL TESTS PASSED.`；`test_ez` 讀不到任何 ifetch）；exit 1 |
| `TOOLCHAIN_PREFIX=nonexist-` | `test` FAIL | `make exited with 2`（`make: *** [firmware/start.o] Error 127`），FAIL；exit 1 |
| Preflight：在必要工具清單加一個不存在的工具；或把釘住的 commit 改成錯的值 | 立即 FAIL，exit 2，不跑任何 target | 分別印 `tool not found: no_such_tool_xyz`、`submodule ... is at ef203c2b0a3f, env/versions.mk pins 0123456789ab`，exit 2；前者另寫 `summary.txt` |
| 把 `submodule_clean` 讀到的 `git status --porcelain` 換成假的 ` M picorv32.v`（不實際弄髒 submodule）| `submodule_clean` FAIL | FAIL，整體 `core-stock: FAIL`，exit 1 |
| 改動重播的 `test` log（9 種各單獨一次）：刪 `ALL TESTS PASSED.`；`sub..OK` 改 `sub..ERROR`；刪一個 `add..OK`；加 `TIMEOUT`；加 `ERROR!`；刪 `DONE`；刪 `TRAP after`；整個清空；加 `OUT-OF-BOUNDS MEMORY WRITE TO 00000000` | 全部 FAIL | 9 種全部 FAIL（`make` 的 rc 都是 0），原因訊息各自正確，例如 `per-test OK 44/45, missing: add`、`failure text in log: 'TIMEOUT'` |
| 改動重播的 `test_ez` log（7 種各單獨一次）：寫入值跳號（`0x2b` 改 `0x2d`）；ifetch 資料含 `xx`；只剩前 40 行；加 `TIMEOUT`；刪第一筆 ifetch；整個清空；某次讀回值改錯 | 全部 FAIL | 7 種全部 FAIL，原因訊息各自正確，例如 `only 7 writes to 0x3fc, expected >= 32`、`read of 0x3fc returned 17, last written 16` |

經驗：bug injection 要放在**實際被使用的程式路徑**上。我第一次把錯誤植在 `picorv32.v` 第 1231 行（`TWO_CYCLE_ALU=1` 才會用到的分支，上游預設是 0），`test`、`test_wb` 仍 PASS 且 cycle 數完全相同，那是錯誤沒有生效，不是 checker 漏抓；改植在第 1240 行（預設啟用的組合邏輯路徑）後才如預期 FAIL。

未驗證／限制：
- `test_synth` 沒有另做 bug injection（約 165 s 一次）。它與 `test` 共用同一個 checker 函式；`picorv32.v` 的錯誤同時會進入 `synth.v`，但這點沒有實測。
- `test_rvf` 在真正的 `rvfimon.v` 存在時的行為沒有驗證，只驗證了空殼路徑（§6）。

## 9. 對規格的解讀與限制

- **`test_ez` 沒有上游成功字串**：規格要求「以上游 testbench 印出的明確成功字串判定」，但 `testbench_ez.v` 沒有，字面上它永遠是 FAIL。我採保守解讀：不放寬成「exit 0 就算 PASS」，而是用 §4 推導的 checker，並在本文與 `summary.txt` 明確標示它是推導的。
- **`submodule_clean` 列為必要項目**：規格要求事後確認 submodule 乾淨，我把它當成一列必要的 PASS／FAIL，不是只印一行訊息。
- **`toolchain.md` 一致性只當資訊**：`summary.txt` 會記錄 `env/check_toolchain_doc.py` 的結果，但不影響 exit code（正式的強制檢查在 `make env-check`）。
- **`toolchain.md` 不由本區域維護**：該檔屬主控專屬（規格 §1.1）。先前被中斷的那次嘗試在檔尾加了 §7（各 regression 實際用到的子元件與 override）。這次沒有再改它，也沒有移除它；是否保留由主控決定。我逐項重跑後，§7.1 的版本、override、4 項 PASS 都與實測一致；只有 `test_rvf` 的 N/A 原因一句需要改成保守說法，見回報的 open_issues。
- **不屬於 L1a 的上游 target**（`test_verilator`、`test_sp`、`test_axi`、各 `*_vcd`、`check`）：任務範圍沒有要求，未執行。
