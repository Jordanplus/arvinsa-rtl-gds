# dv/：SoC 層級 testbench、checker 與 regression script

契約：`docs/spec/soc_spec.md` §7（DV）、§5（bug injection）、§6.4（測試清單）、§6.5（UART loader 封包）。
所有 script 只用 Python 標準函式庫，從任何目錄執行都以 repo 根目錄為準。

## 檔案

| 檔案 | 內容 |
|---|---|
| `tb/tb_soc.v` | 頂層 `tb_soc`，DUT instance `dut`；40 ns clock、reset 16 cycle；backdoor／host port／UART／none 四種載入；UART RX driver；host port 載入後做 byte mask 檢查；輸出 `uart.txt`、`gpio.txt`、`tb_result.txt`、`trace.log`（`+trace`）、`wave.vcd`（`+vcd`） |
| `monitors/uart_monitor.v` | checker `uart_monitor`：依 `SOC_UART_BIT_CYCLES` 解碼 TX；frame 內每個轉態必須在「起始位元下降緣 + k×20 ± 1 cycle」，stop bit 必須為 1 |
| `monitors/bus_assert.v` | checker `bus_assert`：§7.2 全部規則；位址解碼由 `memmap.vh` 視窗獨立計算，再與 `dut.u_bus.sel_*` 比對；另檢查 unmapped 讀取在 handshake 時回 0（§4.2） |
| `monitors/test_ctrl_monitor.v` | checker `test_ctrl`：DONE 不是 PASS magic、或 DONE 寫兩次以上 |
| `monitors/x_check.v` | checker `x_check`（只在 Icarus 編譯）：reset 釋放 20 cycle 後 `trap`/`uart_tx`/`gpio_out`/`mem_valid` 出現 X/Z、讀取 handshake 時 `mem_rdata` 含 X/Z |
| `tb/dv.f`、`tb/timescale.v` | DV filelist；`timescale.v` 排在最前面，讓沒寫 `` `timescale `` 的檔案繼承 1ns/1ps |
| `tb/sim_waivers.vlt` | Verilator 模擬 build 的 waiver：只豁免 `simpleuart.v`（第三方、不可修改）的兩種寬度 warning |
| `tests.toml`、`bugs.toml` | 測試清單（§6.4 加上定向測試 `regs`、`unmapped`、`boot_uart_max`）與 negative test 清單（§5 加上 testbench qualification 補的項目） |
| `log_whitelist.txt` | `log_scan` 白名單（目前沒有條目） |
| `scripts/run_sim.py`、`regress.py`、`neg.py`、`dvlib.py` | §7.4 的三支 script 與共用函式庫 |

`trap`、`timeout` 兩個 checker 寫在 `tb_soc.v` 裡；`signature`、`uart_golden`、`gpio_seq`、`log_scan`、`sim_error` 由 `run_sim.py` 判定。
每個 checker 失敗時印一行 `[CHK:<name>] FAIL <訊息>`。

## 怎麼跑

```
make sim TEST=hello SIM=icarus      # python3 dv/scripts/run_sim.py --test hello --sim icarus
make regress-rtl                    # 全部正向測試，Icarus + Verilator
make regress-rtl-smoke              # smoke 子集（hello、memtest、bootrom_march），Icarus
make neg-rtl                        # R01–R07 bug injection，判定反轉
```

`run_sim.py` 另有 `--bug <id>`、`--out <dir>`、`--trace`、`--vcd`、`--timeout <秒>`；`regress.py` 另有 `-j N`（預設 CPU 數 − 2）、`--tests a,b`；`neg.py` 另有 `--only R01,R04`、`-j N`。

結果位置：

| Script | 輸出 |
|---|---|
| `run_sim.py` | `runs/sim/<sim>/<test>[__<bug>]/`：`result.json`、`sim.log`、`compile.log`、`uart.txt`、`gpio.txt`、`tb_result.txt` |
| `regress.py` | 上述每個 run，加上 `runs/sim/summary.json`、`runs/sim/junit.xml` |
| `neg.py` | `runs/neg/<sim>/<test>__<bug>/`，加上 `runs/neg/summary.json` |

編譯結果依（模擬器, define）快取在 `runs/sim_build/<sim>/<define 組合>/`。快取的判斷依據包含：編譯指令、每個原始檔與 include 檔的內容，
以及工具本身的身分（`dvlib.tool_identity`：Icarus 為 `iverilog -V`、`vvp -V`；Verilator 為 `verilator --version` 與 `c++ --version` 的第一行，
加上各自解析後的實際路徑）。任何一項改變就重新編譯；所以升級 Verilator、Icarus 或 Xcode Command Line Tools 的 clang 後，
不會沿用舊版工具編出的模擬執行檔。工具身分也寫在 `compile.log` 開頭（`# tool:` 行）與每個 `result.json` 的 `tools` 欄位。

## 判定規則

**只有明確 PASS 才算 PASS**（§7.4）：模擬器正常結束、`tb_result.txt` 完整、DONE 恰好寫一次且等於 PASS magic、沒有任何 checker FAIL、log 掃描乾淨。缺任何一項都判 FAIL，並在 `failing_checkers` 列出原因；找不到原因時一律記為 `sim_error`。

`tb_result.txt` 完整的意思：`dvlib.TB_RESULT_KEYS` 的每個 key（`end_reason`、`done_count`、`done`、`done_cycle`、`sig`、`cycles`、
`cpu_start_cycle`、`uart_bytes`、`unmapped`、`simulator`、`finished`）都在，每個 testbench checker 都有 `fail.<name>` 計數
（`fail.x_check` 只在 Icarus 有，Verilator 不得出現），加上 `fail.sim_error`；而且 `simulator=` 必須等於這次執行的模擬器。
缺少的 key 不會當成 0，一律記為 `sim_error`。

- `uart_golden`：`expect_uart` 省略表示不檢查；`""` 表示不允許任何 UART 輸出（`bootrom_march`）。
- `signature`：`uart_crc32` 用解碼出的 UART bytes 算 CRC32（與 `zlib.crc32` 相同）和 SIG 比對；`const:0x...` 直接比對；`none` 不檢查。
- `gpio_seq`：`gpio_out` 變化序列（不含 reset 值 0）必須與 `expect_gpio` 完全相同。
- `test_ctrl` 的 `min_cycles` 下限（`tests.toml` 擴充欄位）：DONE = PASS magic 必須在 `min_cycles` 之後才寫入（DONE 是 FAIL code 時本來就 FAIL，不另外檢查）。這是為了抓「測試主體被跳過或縮小」：
  例如 `muldiv` 的比對迴圈被拿掉，UART 仍印 `muldiv PASS\n`、SIG 仍是同一個 CRC，只有測試時間變短。目前設在
  `memtest`、`muldiv`、`bootrom_march`，數值約為 Phase 1 RTL 實測 DONE cycle 的 90%；若刻意改了 RTL 時序讓測試變快，要重新量測後更新。
- `bus_assert` 的 unmapped 規則：預設任何 unmapped 存取都 FAIL（§7.2）。只有在 `tests.toml` 寫了 `expect_unmapped = N` 的測試，
  `run_sim.py` 才會加 `+allow_unmapped`：此時 unmapped 的**資料**存取改成計數並印 `[TB] bus_assert: unmapped ...` 資訊行，
  `run_sim.py` 要求計數恰好等於 N（不符記為 `bus_assert` FAIL）。從 unmapped 位址取指令一律 FAIL；解碼比對、1000 cycle 回應上限、
  unmapped 讀取必須回 0 這幾條規則在任何測試都照常檢查。目前只有 `unmapped` 測試使用（spec §4.2 要求 unmapped 必須回應，
  但 §7.2 不允許正向測試做 unmapped 存取，這是兩者之間的折衷，見下方「與 spec 的差異」）。
- host port byte mask 檢查（`load = "host"`）：image 寫入並讀回之後，testbench 對最後一個 SRAM word（511，image 最多 448 word，用不到它）
  先寫全 1，再用 10 種 `host_wmask`（含 `0000` 與 `1111`）寫 0 並讀回，每個 byte 必須照 mask 改變或保持 `0xFF`。
  不符時印 `[CHK:sim_error] FAIL host port partial-wmask write mismatch ...` 並中止，與既有的 host 讀回比對相同處理方式
  （§7.2 沒有觀察 host port 的 checker，見下方「與 spec 的差異」）。
- `log_scan`：compile log 與 simulation log 中含 ERROR、FATAL、warning、`Writing and reading`、`Unable to find`（不分大小寫）的行，白名單外一律 FAIL。
- trap 或 timeout 結束的 run 仍會比對 UART、SIG、GPIO（多給資訊）；testbench 因設定錯誤中止（`sim_error`）時不比對。

## `tests.toml` 擴充欄位

| 欄位 | 意義 |
|---|---|
| `min_cycles` | DONE 寫入的 cycle 下限（`test_ctrl`），必須 `0 < min_cycles < max_cycles` |
| `loader_frame` | 只用於 `load = "uart"`：`valid`（預設）、`max_words`（image 補 0 到 448 word，N 的上限）、`bad_checksum`（checksum + 1）、`n_zero`（N = 0）、`n_too_big`（只送 N = 449 的 2 byte 表頭） |
| `expect_unmapped` | 測試刻意做的 unmapped 資料存取次數（正整數），見上方 `bus_assert` |
| `fw` | image 名稱（預設 = 測試名稱） |

正向測試（`negative_only = false`）一定要寫 `expect_uart` 與 `expect_gpio`，且 `sig_rule` 不得為 `none`；否則 `load_tests()` 直接報錯，
regression 判 FAIL。避免有人把測試條目改到「只要寫了 DONE 就 PASS」。

## Negative test 判定（`neg.py`）

每個 bug 必須同時滿足：run 結果是 FAIL；不是編譯失敗或模擬異常結束（`sim_error`）；`expect_checkers` 中至少一個 checker FAIL，且它的訊息符合 `expect_regex`。
其他情況（PASS、編譯失敗、只在其他 checker FAIL、訊息不符）都算 escape（checker 沒抓到植入的錯誤），`neg.py` 回傳非 0。
`expect_regex` 為空字串時，該 checker 的任何 FAIL 訊息都算數（§5 對 R03、R05、R06a、R06b 沒有指定 regex）。

`bugs.toml` 的選用欄位：
- `exclusive = true`：除了 `expect_checkers` 之外不得有其他 checker FAIL。用在整個可觀察行為都有規定的情況，例如 Boot ROM loader
  的錯誤處理：DONE = `0xBAD0_0B00`、GPIO_OUT `0xB2 → 0xEE`、沒有 UART 輸出，所以只能有 `test_ctrl` FAIL。
- `expect_gpio = [...]`：這個 bug run 的 `gpio_out` 序列必須等於它（例如 R02 的 march FAIL 狀態 `[0xB1, 0xE1]`）。

### negative test 清單

| ID | 植入的錯誤 | 測試 | 預期 FAIL 的 checker | 用途 |
|---|---|---|---|---|
| R01–R07 | spec §5 | — | — | — |
| R02_memtest | `BUG_R02`（SRAM `addr0[8]` 固定為 0） | `memtest` | `test_ctrl`／`trap`／`timeout`（regex 排除 `min_cycles` 訊息） | 確認 `memtest` 真的涵蓋 SRAM 上半部（§6.2）；`memtest` 被縮成只測下半部時這項會 escape |
| R08 | `BUG_R08`：除法結果 bit 0 反相（以外接 `picorv32_pcpi_div` 取代內建除法器） | `muldiv` | `test_ctrl` `0xbad00104` | 確認 `muldiv` 真的比對結果；比對迴圈被跳過時 escape |
| R09 | `BUG_R09`：unmapped 存取永遠不回 `mem_ready` | `unmapped` | `bus_assert`（超過 1000 cycle） | §4.2 unmapped 必須回應 |
| R10 | `BUG_R10`：UART 只比對 `addr[31:12]`（partial decode） | `unmapped` | `bus_assert`（decode mismatch） | §4.2 完整位址解碼 |
| R11 | `BUG_R11`：`gpio_out` pin 6 固定為 0（暫存器讀回正確） | `regs` | `gpio_seq` | 每個 GPIO pin 都要被驅動成 1 與 0 |
| R12 | `BUG_R12`：GPIO_OUT、SIG、IRQ_TRIG、UART DIV 讀回 0 | `regs` | `test_ctrl` `0xbad0021d`（四個暫存器都要被點名） | RW 暫存器讀回 |
| R13 | `BUG_R13`：host port 忽略 `host_wmask` | `boot_host_hello` | `sim_error`（regex 限定 byte mask 訊息） | §4.4 `wmask0 = host_wmask` |
| R14 | `BUG_R14`：IRQ_TRIG 清掉後 IRQ 線多維持 200 cycle | `irq` | `test_ctrl` `0xbad00020` | handler 進入次數必須在 1–2 次 |
| R15 | `BUG_R15`：DONE 讀回 0 | `regs` | `test_ctrl` `0xbad00240` | DONE 的「R：最後寫入值」 |
| L01 | 不植入 RTL 錯誤；loader 封包 checksum 錯 | `boot_uart_badck` | 只有 `test_ctrl` `0xbad00b00` | §6.5 loader 必須拒絕 checksum 錯誤 |
| L02 | 同上；N = 0 | `boot_uart_n0` | 同上 | §6.5 `1 ≤ N` |
| L03 | 同上；N = 449（只送表頭） | `boot_uart_n449` | 同上 | §6.5 `N ≤ 448`，且收到表頭就要拒絕 |

這些項目的 checker 是否真的有效，已用反向植入確認（植入後 `neg.py` 必須回報 escape）：`muldiv` 比對迴圈跳過 → R08 escape；
`memtest` 只測下半部 → R02_memtest escape；Boot ROM 不比對 checksum → L01 escape；不檢查 N 上限 → L03 escape；接受 N = 0 → L02 escape。
另外 `muldiv` 跳過與 `memtest` 縮小在正向 regression 也會被 `min_cycles` 抓到。

## 與 spec 的差異（交主控決定）

- `bus_assert` 的 unmapped 規則：§7.2 寫「unmapped 存取」一律 FAIL，但 §4.2 要求 unmapped 必須回應、讀回 0、寫入忽略，正向測試因此無法驗證 §4.2。
  目前做法：只有宣告 `expect_unmapped` 的測試可以做 unmapped 資料存取，且次數必須完全相符。
- host port 的錯誤沒有專屬 checker：§7.2 的 checker 都看不到 host port，所以 host 讀回不符與 byte mask 不符都以 `sim_error` 中止（R13 的
  `expect_checkers` 因此是 `sim_error`，並用 regex 限定訊息）。建議在 §7.2 加一個 `host_port` checker。
- `test_ctrl` 多了 `min_cycles` 這一條判定；`tests.toml`／`bugs.toml` 多了上述擴充欄位；測試清單多了 §6.4 以外的定向測試。

## 已知限制

- Verilator 是 2-state 模擬器，看不到 X/Z，所以 `x_check` 只在 Icarus 存在；R03（`mem_ready` 提早一拍）在 `bugs.toml` 指定 Icarus。
- `min_cycles` 是「測試時間異常變短」的下限，不是功能檢查；真正保護測試主體的是上表的 negative test（R02_memtest、R08）。
- `max_cycles` 從模擬時間 0 起算，包含 reset 與 host port 載入。
- UART RX driver 在 CPU 放開後 400 cycle（2 個 frame）才開始送 byte。
