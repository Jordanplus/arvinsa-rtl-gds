# SoC 介面規格（Phase 1 契約）

版本：1.0（2026-10-03）　適用：Phase 1（RTL + firmware + RTL 模擬 regression）
上位文件：`project-plan.md` §5（設計規格）、§7（驗證計畫）。本文件與 plan 衝突時，以本文件為準並回寫 ADR。

本文件是 RTL、firmware、DV（testbench 與 checker）三方的**契約**。任何一方都不得自行更改本文件定義的名稱、位址、時序或訊息格式；需要改時先改本文件。

---

## 1. 共通規則

- Repo 根目錄：clone 下來的 `arvinsa-rtl-gds/` 目錄。所有 script 從 repo 根目錄執行，路徑一律相對於 repo 根目錄。
- **唯讀**：`third_party/`（git submodule）、`ip/sram/*/upstream/`、`rtl/include/memmap.vh`、`env/versions.mk`、本文件。
- 不得 `git commit`、不得 `git push`、不得改 submodule commit。
- GNU make 版本是 **3.81**（macOS 內建）：不可用 `.SHELLFLAGS`、`.ONESHELL`、`$(file ...)`、`undefine`。Makefile recipe 不用 pipe；需要嚴格錯誤處理的邏輯寫在 bash（`set -euo pipefail`）或 Python script 裡。
- bash 是 macOS 內建 **3.2**：不可用 `declare -A`、`mapfile`／`readarray`、`${var,,}`、`|&`、`coproc`。
- Python ≥ 3.11，只用標準函式庫（設定檔用 TOML，以 `tomllib` 讀）。
- **不得安裝新工具或新套件**；只能用 `toolchain.md` 列出的工具。真的需要新工具時，停下來在回報中說明。
- 本機工具：Verilator 5.050（支援 `--timing`、`--binary`）、Icarus Verilog 13.0、Yosys 0.69、`riscv64-elf-gcc` 16.1（multilib：rv32i、rv32im、rv32iac、rv32imac、rv32imafc，ABI ilp32；**無 newlib**）。
- 模擬 timescale：`1ns/1ps`；clock 週期 40 ns（25 MHz，plan §5.4 的 silicon 目標）。
- 產出目錄：`runs/`（gitignore）。firmware 產出 `fw/build/`（gitignore）。
- Filelist（`.f`）格式：每行一個路徑或一個 `+incdir+<dir>`，**不寫註解**，路徑相對 repo 根目錄。Icarus（`-c`）與 Verilator（`-f`）共用。

### 1.1 檔案所有權

| 擁有者 | 檔案 |
|---|---|
| RTL | `rtl/soc/`、`rtl/bus/`、`rtl/periph/`、`rtl/lint/`、`rtl/scripts/`、`rtl/rtl.f` |
| Firmware | `fw/`（全部）、`rtl/bootrom/gen_bootrom.py`、`rtl/bootrom/bootrom.v`（產生物，需 commit） |
| DV | `dv/`（全部） |
| core-stock | `scripts/core_stock.sh`、`docs/notes/core_stock.md` |
| 主控（不給 agent 改） | `Makefile`、`env/`、`ip/`、`rtl/include/memmap.vh`、`docs/spec/`、`docs/decisions/`、`toolchain.md` |

Phase 1 的平行開發階段，每個 agent 只能寫自己擁有的檔案。整合階段才允許跨區修改，且要在回報中列出。

---

## 2. Memory map 與常數

唯一來源：`rtl/include/memmap.vh`。摘要：

| 區塊 | Base | 大小 | 暫存器（offset） |
|---|---|---|---|
| SRAM | `0x0000_0000` | 2 KB（512 words） | — |
| Boot ROM | `0x0001_0000` | 512 B（128 words） | — |
| UART | `0x0200_0000` | 8 B | `+0x0` DIV（RW）、`+0x4` DATA（W：送出低 8 bit；R：收到的 byte，無資料時 `0xFFFF_FFFF`） |
| GPIO | `0x0300_0000` | 8 B | `+0x0` GPIO_OUT（RW，低 8 bit 有效）、`+0x4` GPIO_IN（RO，`{30'b0, boot_mode[1:0]}`） |
| TEST_CTRL | `0x0400_0000` | 12 B | `+0x0` SIG（RW）、`+0x4` DONE（W：PASS=`0x600D_C0DE`，FAIL=`0xBAD0_0000 \| code[15:0]`；R：最後寫入值）、`+0x8` IRQ_TRIG（RW，bit0 驅動 `irq[4]`） |
| 其他位址 | — | — | 未映射（unmapped） |

- UART：`SOC_UART_DIV = 18`。simpleuart 的 bit 長度 = 除數 + 2 個 clock，所以 **bit 長度 = `SOC_UART_BIT_CYCLES` = 20 個 clock**（TX 與 RX 相同）。
- CPU：reset vector `0x0001_0000`（Boot ROM），IRQ vector `0x0000_0010`（SRAM），測試用 IRQ 線 `irq[4]`。
- Script 解析 `memmap.vh` 的規則見該檔開頭註解。

---

## 3. 頂層 `soc_top` 介面

```verilog
module soc_top (
`ifdef USE_POWER_PINS
    inout  wire        vccd1,
    inout  wire        vssd1,
`endif
    input  wire        clk,
    input  wire        resetn,      // 同步、低電位有效
    output wire        uart_tx,
    input  wire        uart_rx,
    output wire [7:0]  gpio_out,
    input  wire [1:0]  boot_mode,
    output wire        trap,        // PicoRV32 trap
    // Host write port：host_en=1 時 CPU 保持 reset，SRAM port 0 由 host 控制
    input  wire        host_en,
    input  wire        host_cs,     // 本 cycle 存取一次
    input  wire        host_we,
    input  wire [8:0]  host_addr,   // word address
    input  wire [31:0] host_wdata,
    input  wire [3:0]  host_wmask,
    output wire [31:0] host_rdata
);
```

### 3.1 必須存在、供 testbench 觀測的內部名稱（hierarchical probe 契約）

| 路徑（相對 `soc_top`） | 型別 | 意義 |
|---|---|---|
| `mem_valid`、`mem_instr`、`mem_ready`、`mem_addr[31:0]`、`mem_wdata[31:0]`、`mem_wstrb[3:0]`、`mem_rdata[31:0]` | wire | PicoRV32 native memory bus（`u_cpu` 的對應 port） |
| `u_cpu` | instance | `picorv32` |
| `u_bus.sel_sram`、`u_bus.sel_rom`、`u_bus.sel_uart`、`u_bus.sel_gpio`、`u_bus.sel_test`、`u_bus.sel_none` | wire | 位址解碼結果：`mem_valid` 且位址落在該視窗；`sel_none` = `mem_valid` 且不在任何視窗。正常時 `mem_valid=1` 必恰有一個為 1，`mem_valid=0` 時全為 0 |
| `sram0` | instance | `sky130_sram_2kbyte_1rw1r_32x512_8`，**直接放在 soc_top 這一層** |
| `u_test_ctrl.done_strobe` | wire | DONE 被寫入的那一個 cycle 為 1 |
| `u_test_ctrl.done_value[31:0]`、`u_test_ctrl.sig_value[31:0]` | wire/reg | 最後寫入的 DONE 與 SIG 值 |
| `u_uart.u_simpleuart.cfg_divider[31:0]` | reg | simpleuart 實際使用的除數（`uart_div` checker） |
| `u_cpu.irq[SOC_IRQ_TEST]` | wire | 送進 CPU 的測試用 IRQ 線（`irq_line` checker） |
| `sram0.csb0`、`sram0.web0`、`sram0.wmask0`、`sram0.addr0`、`sram0.din0`、`sram0.mem` | macro 腳位／模型陣列 | `sram_port` checker 觀察腳位；`mem` 給 backdoor 載入 |

---

## 4. 微架構

### 4.1 CPU：`picorv32 u_cpu`

參數（未列者用預設值）：`COMPRESSED_ISA=1`、`ENABLE_MUL=1`、`ENABLE_DIV=1`、`BARREL_SHIFTER=1`、`ENABLE_IRQ=1`、`ENABLE_IRQ_QREGS=1`、`ENABLE_IRQ_TIMER=1`、`CATCH_MISALIGN=1`、`CATCH_ILLINSN=1`、`ENABLE_TRACE=0`、`PROGADDR_RESET=SOC_PROGADDR_RESET`、`PROGADDR_IRQ=SOC_PROGADDR_IRQ`。
`resetn` 接 `resetn & ~host_en`。`irq[31:0]`：只有 `irq[SOC_IRQ_TEST]` 接 `TEST_CTRL.IRQ_TRIG[0]`，其餘為 0。
`pcpi_*` 外部介面不用（輸入接 0）。`trace_*`、`eoi` 不接。
Phase 2 單獨 harden 的 PicoRV32 用 `pnr/picorv32_core/config.json` 的 `SYNTH_PARAMETERS`，必須與這裡的 `u_cpu` 參數完全相同；`make harden-core`、`make gl-core` 執行前都會用 `pnr/picorv32_core/cpu_params.py` 比對，不同即 FAIL。

### 4.2 匯流排 `soc_bus u_bus`（模組名稱與檔案由 RTL 決定，instance 名稱固定 `u_bus`）

- 解碼：完整比對位址視窗（見 §2），不做 partial decode。
- 回應：所有存取都必須在有限 cycle 內回 `mem_ready`，包括 unmapped（回 `mem_rdata=0`、寫入忽略）。
- `mem_ready` 為 registered 輸出，每筆交易只拉高一個 cycle；`mem_valid` 在 handshake 後由 CPU 拉低。
- 周邊（UART、GPIO、TEST_CTRL）只支援 32-bit 存取；sub-word 寫入由 testbench 判定為違規（firmware 不得做）。
- 非 SRAM 讀取：選中後下一個 cycle 回 `mem_ready`，`mem_rdata` 為 registered。UART DATA 寫入在 `reg_dat_wait=1` 期間不得回 `mem_ready`。UART DATA 讀取時，`reg_dat_re` 每筆交易**只能拉高一個 cycle**，且與取用的資料同一筆。
- Datapath register（例如 `mem_rdata` 暫存、SRAM 讀出 register）**不做 reset**；控制用 FSM 與 valid/ready 要 reset。

### 4.3 SRAM port 0 時序（`sram0`）

SRAM 行為模型：上升緣取樣輸入；下降緣寫入或於 +3 ns 更新 `dout0`；下一個上升緣 +1 ns `dout0` 變 X（見 `ip/sram/.../README.md`）。規定的交易時序（Tn 為第 n 個上升緣）：

| 交易 | T0 | T1 | T2 |
|---|---|---|---|
| 讀 | SRAM 取樣 `csb0=0, web0=1`（輸入在 T0 前由組合邏輯驅動） | `rdata_q <= dout0`；之後 `mem_ready=1`、`mem_rdata=rdata_q` | CPU 取用資料；`mem_ready` 回 0 |
| 寫 | SRAM 取樣 `csb0=0, web0=0, wmask0=mem_wstrb`；之後 `mem_ready=1` | CPU 完成 handshake；`mem_ready` 回 0 | — |

- 每筆交易 `csb0` 只能在 T0 前的那一個 cycle 有效（不得重複存取）。
- `rdata_q`（SRAM 讀出 register）不 reset，只在 T1 更新。
- Port 1 tie-off：`clk1=0`、`csb1=1`、`addr1=0`，`dout1` 不接。
- `USE_POWER_PINS`：`sram0` 的 `vccd1/vssd1` 接 `soc_top` 的同名 port。

### 4.4 Host write port

- `host_en=1`：CPU 保持 reset；SRAM port 0 輸入改由 host 驅動。`host_en=0`：由 CPU 匯流排驅動。
- `host_cs=1` 的 cycle 結束時的上升緣（T0）SRAM 取樣：`web0=~host_we`、`wmask0=host_wmask`、`addr0=host_addr`、`din0=host_wdata`。
- Host 讀：T1 時 `rdata_q` 更新；`host_rdata = rdata_q`（在 T1 之後可讀）。
- 同步於 `clk`，不做 synchronizer（ADR-0005）。Testbench 在下降緣改變 host 訊號。

### 4.5 UART：包裝 `third_party/picorv32/picosoc/simpleuart.v`

- `simpleuart #(.DEFAULT_DIV(SOC_UART_DIV))`，第三方檔案不得修改，包裝邏輯放在 RTL 自己的檔案。
- DIV 暫存器只接受 32-bit 寫入（`reg_div_we = {4{write}}`）。

### 4.6 Boot ROM：`bootrom`（檔案 `rtl/bootrom/bootrom.v`，由 `rtl/bootrom/gen_bootrom.py` 產生）

```verilog
module bootrom (
    input  wire [6:0]  addr,    // word address = mem_addr[8:2]
    output reg  [31:0] rdata    // 組合邏輯 case-ROM；未使用的 word 回 32'h0000_006F（jal x0, 0）
);
```
匯流排負責把 `rdata` 暫存後回應。

### 4.7 GPIO

`GPIO_OUT` 8 bit 暫存器（reset 為 0），直接驅動 `gpio_out`。`GPIO_IN` 讀回 `{30'b0, boot_mode}`。

### 4.8 TEST_CTRL：`u_test_ctrl`

- SIG、DONE、IRQ_TRIG 三個 32-bit 暫存器，reset 為 0。
- `done_strobe`：DONE 被寫入的那個 cycle 為 1（與寫入同一個上升緣後的 cycle，一次寫入只產生一個 cycle）。
- IRQ_TRIG bit0 → `irq[SOC_IRQ_TEST]`（PicoRV32 預設 latched IRQ）。因為是 latched，handler 清掉 IRQ_TRIG 之前 IRQ 已再次被鎖存，所以每寫一次 IRQ_TRIG，handler 會進入 **恰好 2 次**（Phase 1 實測，兩次記錄的 pending mask 都是 `1<<4`）。
- `irq[SOC_IRQ_TEST]` 每個 cycle 都等於 IRQ_TRIG[0]（位準訊號，不是脈衝，清掉後不得延遲放掉）。

### 4.9 Reset

同步、低電位有效 `resetn`。`resetn=0` 至少 10 個 cycle。

- `resetn=0` 被取樣的那個上升緣上，CPU 送出的 SRAM 寫入**丟棄**，與同一個邊緣上的周邊暫存器寫入被 reset 蓋掉的行為一致（Phase 1 review RTL-RST-01）。

---

## 5. Bug injection（negative test 用的植入錯誤）

只在 RTL 自己的 glue 檔案中以 `` `ifdef `` 實作，**不得**修改 `third_party/`。預設（未定義任何 `BUG_*`）行為必須完全正確。

| ID | define | 植入內容（精確定義） | 用來執行的測試 | 預期 FAIL 的 checker（任一）與訊息 regex |
|---|---|---|---|---|
| R01 | `BUG_R01` | CPU 路徑送進 SRAM 的 `wmask0[0]` 與 `wmask0[1]` 對調 | `memtest` | `test_ctrl`，`(?i)0xbad00040` |
| R02 | `BUG_R02` | SRAM `addr0[8]` 固定為 0（套用在 host/CPU mux 之後） | `bootrom_march` | `test_ctrl`，`(?i)0xbad00e10` |
| R03 | `BUG_R03` | SRAM 讀取時 `mem_ready` 提早一個 cycle（T0 後就拉高，`mem_rdata` 仍取 `rdata_q`） | `hello` | `x_check`、`trap`、`timeout` |
| R04 | `BUG_R04` | 寫入 UART DIV 時，送給 simpleuart 的值 = 寫入值 + 1（bit 長度 21 clock，偏 5%） | `hello` | `uart_monitor`，`(?i)edge|timing|framing` |
| R05 | `BUG_R05` | `irq[SOC_IRQ_TEST]` 固定為 0 | `irq` | `timeout` |
| R06a | （無，firmware） | firmware 永不寫 DONE | `neg_fw_hang` | `timeout` |
| R06b | （無，firmware） | firmware 執行非法指令 | `neg_fw_illegal` | `trap` |
| R07 | `BUG_R07` | 位址在 UART 視窗時，`sel_gpio` 也拉高 | `hello` | `bus_assert`，`(?i)one-?hot|decode` |

以下由 Phase 1 testbench qualification review 補上：植入前，這些錯誤在所有 checker 都 PASS（checker 抓不到）。每一條都用來防止某支測試或 checker 被改弱而沒人發現。

| ID | define | 植入內容 | 用來執行的測試 | 預期 FAIL 的 checker 與訊息 regex |
|---|---|---|---|---|
| R02_memtest | `BUG_R02` | 同 R02 | `memtest` | `test_ctrl`／`trap`／`timeout`，`(?i)trap asserted|no DONE write|DONE=0xbad0`（證明 memtest 涵蓋 SRAM 上半部） |
| R08 | `BUG_R08` | 除法改用外接 `picorv32_pcpi_div`，結果 bit 0 反相 | `muldiv` | `test_ctrl`，`(?i)0xbad00104` |
| R09 | `BUG_R09` | unmapped 存取永遠不回 `mem_ready` | `unmapped` | `bus_assert`，`(?i)without mem_ready` |
| R10 | `BUG_R10` | UART 只比對 `addr[31:12]`（partial decode） | `unmapped` | `bus_assert`，`(?i)decode mismatch` |
| R11 | `BUG_R11` | `gpio_out[6]` 固定為 0（暫存器讀回正確） | `regs` | `gpio_seq`，`(?i)gpio_out sequence` |
| R12 | `BUG_R12` | GPIO_OUT、SIG、IRQ_TRIG、UART DIV 讀回 0 | `regs` | `test_ctrl`，`(?i)0xbad0021d` |
| R13 | `BUG_R13` | host port 忽略 `host_wmask` | `boot_host_hello` | `sim_error`，`(?i)host port partial-wmask write mismatch`（§7.2 沒有觀察 host port 的 checker，testbench 直接中止） |
| R14 | `BUG_R14` | IRQ_TRIG bit0 清掉後，`irq[4]` 仍多拉 200 cycle（handler 進入 4 次） | `irq` | `test_ctrl`，`(?i)0xbad00020` |
| R15 | `BUG_R15` | DONE 讀回 0 | `regs` | `test_ctrl`，`(?i)0xbad00240` |
| L01 | （無，激勵） | Boot ROM loader 收到 checksum 錯誤的封包 | `boot_uart_badck` | 只有 `test_ctrl` FAIL（`exclusive`），`(?i)0xbad00b00`，GPIO `B2→EE` |
| L02 | （無，激勵） | loader 收到 N = 0 | `boot_uart_n0` | 同 L01 |
| L03 | （無，激勵） | loader 收到 N = 449 | `boot_uart_n449` | 同 L01 |

L01–L03 的 RTL 是正確的，植入的是錯誤的輸入；正確的 Boot ROM 必須拒收。若 Boot ROM 不驗 checksum 或不檢查 N 範圍，這三條會變成「沒抓到」，`make neg-rtl` 隨之 FAIL。

第二輪 qualification review（自創 23 個錯誤，10 個原本抓不到）後再補：

| ID | 植入方式 | 植入內容 | 用來執行的測試 | 預期 FAIL 的 checker 與訊息 regex |
|---|---|---|---|---|
| R16 | `BUG_R16` | TEST_CTRL 的 SIG 寫入只解碼 `off[2]`（寫 IRQ_TRIG 時連 SIG 一起寫） | `regs` | `test_ctrl`，`(?i)0xbad00332` |
| R17 | `BUG_R17` | UART DATA 寫入的 stall 被忽略（忙碌時照樣收下，byte 遺失） | `uart_burst` | `coverage`，`(?i)held by the transmitter-busy stall` |
| R18 | `BUG_R18` | `csb0` 在回應 cycle 沒被擋住，一筆交易存取 SRAM 兩次 | `hello` | `sram_port`，`(?i)SRAM access #2 of one transaction` |
| R19 | `BUG_R19` | CPU 路徑的 `csb0` 不受 `resetn` 控制（§4.9 的規則失效） | `reset_store` | `sram_port`，`(?i)SRAM access at a rising edge that samples resetn=0` |
| R20 | `BUG_R20` | IRQ_TRIG[0] 清掉後 `irq[4]` 晚 40 cycle 才放掉（handler 次數仍是 2） | `irq` | `irq_line`，`(?i)irq\[4\]=1 but IRQ_TRIG\[0\]=0` |
| R21 | `BUG_R21` | simpleuart 除數的 reset 值為 `SOC_UART_DIV + 1` | `hello` | `uart_div`，`(?i)after reset release, expected the reset value` |
| R22 | `BUG_R22` | `irq[4]` 是寫 IRQ_TRIG 時的一拍脈衝，不是位準 | `irq` | `test_ctrl`，`(?i)0xbad00020` |
| M01 | firmware 變體 `memtest__no_march` | memtest 刪掉 march C− | `memtest` | `coverage`（每個 word 讀 83 次，應為 88） |
| B01 | Boot ROM 變體 `skip_last_word` | march 與 address-in-address 少測最後一個 word | `bootrom_march` | `coverage`（`0x7fc` 沒被存取） |
| B02 | Boot ROM 變體 `no_aia_readback` | address-in-address 不讀回 | `bootrom_march` | `coverage`（每個 word 讀 5 次，應為 6） |
| B03 | Boot ROM 變體 `no_div_write` | Boot ROM 第一步不寫 UART DIV | `hello` | `uart_div`（離開 Boot ROM 前沒寫 DIV） |
| S01 | firmware 變體 `hello__done_before_sig` | `test_pass()` 先寫 DONE 再寫 SIG | `hello` | `signature`（DONE 寫入時 SIG 還是 0） |
| C01 | firmware 變體 `reset_store__no_victim` | reset_store 的目標 store 不存在，testbench 沒機會做 mid-run reset | `reset_store` | `coverage`（mid-run reset 次數 0） |

**firmware／Boot ROM 錯誤變體**：有些錯誤在 firmware 或 Boot ROM 程式裡，RTL `define` 植入不了。`make -C fw all` 另外用 `-DFWBUG_*`／`-DBRBUG_*` 建出 `fw/build/<test>__<variant>.*` 與 `fw/build/bootrom__<variant>.v`（只給 negative test 用）；bugs.toml 以 `fw`／`bootrom` 欄位指定，用 Boot ROM 變體時 run_sim.py 只把 filelist 中的 `rtl/bootrom/bootrom.v` 換掉。已 commit 的 `rtl/bootrom/bootrom.v` 永遠是正確的 ROM（`check-bootrom` 檢查）。

---

## 6. Firmware 契約

### 6.1 Toolchain 與產出

- 前綴 `riscv64-elf-`。SoC 測試：`-march=rv32imc`（必要時加 `_zicsr` 等擴充名稱），`-mabi=ilp32 -Os -ffreestanding -nostdlib -nostartfiles`，連結 `-lgcc`。
- 每個測試產出：`fw/build/<name>.elf`、`.bin`（從 0x0 起的平面映像）、`.hex`（`$readmemh` 格式，每行一個 32-bit word，第一行對應 SRAM word 0，little-endian 組字）、`.lst`（反組譯）。
- `fw/build/size_report.txt`：每個測試的 text/data/bss 與剩餘空間。
- `make -C fw all`：建所有測試＋Boot ROM；`make -C fw <name>`：單一測試；`make -C fw bootrom`：重產 `rtl/bootrom/bootrom.v`；`make -C fw check-bootrom`：重產到暫存位置並與已 commit 的 `rtl/bootrom/bootrom.v` 比對，不同即 FAIL。
- `soc.h` 由 `memmap.vh` 產生到 `fw/build/`，不手寫位址。

### 6.2 記憶體配置與 size checker

- 映像從 `0x0000_0000` 起：`0x0` 放跳到 `_start` 的指令，`0x10` 放 IRQ handler 入口。
- Stack：頂端 `SOC_STACK_TOP`（`0x800`），保留 256 B（`0x700`–`0x7FF`）。
- Linker 提供 `_free_start`（bss 結束後 4-byte 對齊）。size checker：`_free_start ≤ 0x700`，否則 build FAIL。
- `memtest` 另需 `_free_start ≤ 0x400`（讓測試區涵蓋 SRAM 上半部，用來抓 `addr0[8]` 類錯誤）。

### 6.3 Firmware 函式庫（`fw/common/`）

- `uart_init()`：寫 DIV = `SOC_UART_DIV`（**每個測試開頭必呼叫**）。
- `uart_putc/uart_puts`：送出並累計 CRC32（IEEE 802.3，與 Python `zlib.crc32` 相同）。
- `uart_puts_burst(s)`：連續寫入 UART DATA（中間不做其他事，讓 transmitter 忙碌造成 stall），全部寫完才累計 CRC。
- `test_pass()`：**先**寫 SIG = 已送出 byte 的 CRC32，**再**寫 DONE = PASS magic，之後無窮迴圈（`signature` checker 比對 DONE 寫入那個 cycle 的 SIG）。
- `test_fail(code)`：寫 DONE = `0xBAD0_0000 | code`，之後無窮迴圈。
- IRQ handler：用 PicoRV32 custom 指令（可 `#include` `third_party/picorv32/firmware/custom_ops.S` 的巨集）；handler 只清 `IRQ_TRIG`、記錄 `q1`（pending mask）、累加計數，然後 `retirq`。`irq[1]`（非法指令／ebreak）與 `irq[2]`（bus error）預設保持遮蔽；只有 `buserr` 測試會暫時打開 `irq[2]`（Phase 4）。

### 6.4 測試清單（名稱、行為、UART 輸出必須完全一致）

| 名稱 | 載入方式 | boot_mode | 行為 | UART 輸出（精確） | signature 規則 |
|---|---|---|---|---|---|
| `hello` | backdoor | 0 | 印字後 PASS | `hello\n` | `uart_crc32` |
| `memtest` | backdoor | 0 | 測試區 `[_free_start, 0x700)`：固定 pattern（0/全 1/0xAAAA_AAAA/0x5555_5555）、address-in-address、march C−、byte-lane（sb/sh 後以 lb/lbu/lh/lhu/lw 驗證其他 lane 不變）。fail code：pattern `0x10`、addr-in-addr `0x20`、march `0x30`、byte-lane `0x40`、`_free_start>0x400` 為 `0x01` | `memtest PASS\n` | `uart_crc32` |
| `irq` | backdoor | 0 | 只開放 `irq[4]`；寫 IRQ_TRIG=1；等 handler 計數 ≠ 0，再讓 `irq[4]` 保持開放約 3000 cycle；要求計數**恰好 2 次**（§4.8；fail code `0x20` 表示次數 ≠ 2），且記錄的 pending mask 都等於 `1<<4` | `irq PASS\n` | `uart_crc32` |
| `muldiv` | backdoor | 0 | mul/mulh/mulhsu/mulhu/div/divu/rem/remu 各數組常數比對（含除以 0、溢位情況） | `muldiv PASS\n` | `uart_crc32` |
| `uart_echo` | backdoor | 0 | 從 UART 讀到 `\n` 為止，回送 `echo:` + 該行（含 `\n`） | `echo:ping\n`（testbench 送 `ping\n`） | `uart_crc32` |
| `bootrom_march` | 不載入 | 1 | Boot ROM 對整個 SRAM 跑 march C− 與 address-in-address | （無） | `const:0x4D415243` |
| `boot_uart_hello` | UART（Boot ROM loader） | 2 | Boot ROM 收 `hello` 映像後跳到 0 執行 | `hello\n` | `uart_crc32` |
| `boot_host_hello` | host port | 0 | testbench 經 host port 寫入 `hello` 映像並讀回比對；再用 10 種 `host_wmask` 寫入並讀回比對；之後放開 CPU | `hello\n` | `uart_crc32` |
| `boot_uart_max` | UART（Boot ROM loader） | 2 | 同 `boot_uart_hello`，但封包 N = 448（上限），映像補到 448 words | `hello\n` | `uart_crc32` |
| `regs` | backdoor | 3 | 讀回 Boot ROM 寫的 GPIO_OUT=`0xB3`；GPIO_OUT 逐一寫 walking-1、`0xFF`、`0x00` 再還原；SIG、IRQ_TRIG（IRQ 全程遮蔽）、UART DIV 寫入後讀回；GPIO_IN = boot_mode；UART DATA 無資料時讀到 `0xFFFF_FFFF`；DONE 讀回 PASS magic；再對 GPIO_OUT、GPIO_IN（唯讀）、SIG、IRQ_TRIG、UART DIV 各寫兩輪不同的值，每寫一次就把全部暫存器讀回，確認寫 A 不會改到 B（GPIO 序列尾端多 `0x3C,0xC3,0xB3`）。fail code `0x0200 | 壞掉的暫存器 bitmask`、DONE 讀回錯 `0x0240`、cross-talk `0x0300 | (w<<4) | r`（寫第 w 個改到第 r 個） | `regs PASS\n` | `uart_crc32` |
| `unmapped` | backdoor | 0 | 對 29 個空洞位址（每個視窗前後的 word、partial decode 會疊到暫存器的位址）各做讀、寫、再讀，共 87 次 unmapped 存取：讀到必須是 0，且 SRAM canary、SIG、IRQ_TRIG、GPIO_OUT、UART DIV 都不得被改到 | `unmapped PASS\n` | `uart_crc32` |
| `uart_burst` | backdoor | 0 | 用 `uart_puts_burst()` 連續送 81 個 byte；tests.toml `min_uart_stalls = 80`：至少 80 筆 DATA 寫入被 transmitter 忙碌擋住（§4.2 的 stall 路徑） | `uart_burst 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz PASS\n` | `uart_crc32` |
| `reset_store` | backdoor | 0 | testbench 在 CPU 第一次 store 到 `rst_victim` 時拉 reset 16 cycle（`+reset_on_store`）；第二次開機檢查該 word 沒被改（§4.9）。GPIO `B0→00→B0`；fail code `0x01`／`0x02`／`0x03` | `reset_store PASS\n` | `uart_crc32` |
| `counters` | backdoor | 0 | 讀 64-bit 計數器：`rdcycleh`、`rdinstreth` 在一段 100 次的迴圈前後都必須是 0（測試遠少於 2^32 cycle）；`rdcycle`、`rdinstret` 要遞增，instret 至少增加 100，且 instret ≤ cycle。fail code `0x10` cycleh、`0x20` instreth、`0x30` cycle 沒增加、`0x40` instret 增加不足、`0x50` instret > cycle（Phase 4，補 Phase 2 已知限制 7） | `counters PASS\n` | `uart_crc32` |
| `buserr` | backdoor | 0 | 打開 `irq[2]`，各做一次非對齊 `lw`、`sw`（inline assembly）。PicoRV32 只把 `irq[2]` 設成 pending，存取照樣以清掉 bit 1:0 的 word 位址送上 bus（`picorv32.v` 382、403–406、1922–1935）：每次必須恰好多一次 IRQ、pending mask 為 `1<<2`；`lw` 讀到對齊的 word，`sw` 寫入對齊的 word 且不動到下一個 word。fail code `0x10`–`0x12`（lw）、`0x20`–`0x22`（sw）（Phase 4，補 Phase 2 已知限制 7） | `buserr PASS\n` | `uart_crc32` |
| `neg_fw_hang` | backdoor | 0 | 只做 negative test：印字後無窮迴圈、永不寫 DONE | （任意） | — |
| `neg_fw_illegal` | backdoor | 0 | 只做 negative test：執行非法指令 | （任意） | — |
| `boot_uart_badck`／`boot_uart_n0`／`boot_uart_n449` | UART（Boot ROM loader） | 2 | 只做 negative test（L01–L03）：送出 checksum 錯誤／N=0／N=449 的封包，正確的 Boot ROM 必須拒收 | （無） | — |

`memtest`、`bootrom_march` 另設 SRAM 存取 coverage 規則（tests.toml `sram_cov`，由 `coverage` checker 判定）：memtest 測試區 `[_free_start, 0x700)` 每個 word 恰好 88 次讀、22 次寫、0 次取指令，且 byte strobe `1/2/4/8/3/C/F` 都出現；bootrom_march 全部 512 個 word 恰好 6 讀 6 寫、全 32-bit、0 次取指令。這些次數由程式推導並實測，改動測試的任何階段都要同步更新。

`memtest`、`muldiv`、`bootrom_march` 另在 `dv/tests.toml` 設 `min_cycles`（Phase 1 實測 DONE cycle 的約 90%）：DONE=PASS 寫得比這更早，代表測試主體被跳過或縮小，由 `test_ctrl` 判 FAIL。刻意改 RTL 時序讓測試變快時，要重新量測並更新。

### 6.5 Boot ROM 程式（`fw/bootrom/`，連結位址 `0x0001_0000`，≤ 128 words，建議 `-march=rv32i`）

1. 寫 UART DIV = `SOC_UART_DIV`；讀 GPIO_IN 得 `mode`；寫 GPIO_OUT = `0xB0 | mode`。DIV 必須在第一次存取 UART DATA、第一次離開 Boot ROM 取指令、第一次寫 DONE 之前寫好（`uart_div` checker）。
2. `mode=0` 或 `3`：跳到 `0x0000_0000`。
3. `mode=1`：全部 512 words 做 march C−（pattern 0 與全 1），再做 address-in-address（每個 word 寫入自身位址後全部讀回）。PASS：GPIO_OUT=`0xA5`、SIG=`0x4D41_5243`、DONE=PASS；FAIL：GPIO_OUT=`0xE1`、DONE=`0xBAD0_0E10`。之後無窮迴圈。不使用 SRAM 當 stack。每個 word 恰好寫 6 次（M0–M4、address-in-address）、讀 6 次（M1–M5、address-in-address），全部 32-bit 存取，不從 SRAM 取指令。
4. `mode=2`：UART loader。接收格式：`N`（2 bytes，little-endian，word 數，1 ≤ N ≤ 448）、`N×4` bytes 映像（little-endian word，寫到 SRAM word 0..N−1）、1 byte checksum（映像所有 byte 加總 mod 256）。正確：GPIO_OUT=`0xB8` 後跳到 0；錯誤：GPIO_OUT=`0xEE`、DONE=`0xBAD0_0B00`、無窮迴圈。

---

## 7. DV 契約

### 7.1 Testbench

- 頂層模組 `tb_soc`，DUT instance 名稱 `dut`。同一份 testbench 給 Icarus 與 Verilator（`--binary --timing`）用；Icarus 專屬的 X 檢查放在 `` `ifndef VERILATOR ``。
- Plusargs：`+fw=<hex>`（backdoor 預載到 `dut.sram0.mem`）、`+boot_mode=<n>`、`+load=backdoor|host|uart|none`、`+max_cycles=<n>`、`+uart_in=<hex 每行一 byte>`、`+uart_in_len=<n>`、`+uart_in_delay=<cycles>`、`+out_dir=<dir>`、`+trace`、`+vcd`、`+allow_unmapped`、`+reset_on_store=<hex addr>`（CPU 第一次 store 到該位址時拉 reset 16 cycle）。
- Testbench 只判斷它看得到的 checker；最終 PASS/FAIL 由 `run_sim.py` 綜合判定（§7.4）。

### 7.2 Checker 清單與訊息格式

每個 checker 失敗時印一行：`[CHK:<name>] FAIL <訊息>`。名稱固定如下（negative test 以此比對）：

| 名稱 | 位置 | 判定 |
|---|---|---|
| `test_ctrl` | TB＋run_sim.py | DONE 值不是 PASS magic、或 DONE 被寫兩次以上；或 DONE=PASS 寫入時 cycle 小於 tests.toml 的 `min_cycles` |
| `signature` | run_sim.py | SIG 不符合 tests.toml 的 signature 規則；有 DONE 時比對 DONE 寫入那個 cycle 的 SIG |
| `trap` | TB | `trap` 拉高 |
| `timeout` | TB | 到 `max_cycles` 仍未收到 DONE |
| `uart_monitor` | TB | UART TX 波形違規：每個轉態必須落在「起始位元下降緣 + k×20 cycle ± 1 cycle」；stop bit 必須為 1 |
| `uart_golden` | run_sim.py | 解碼出的 UART 文字與 tests.toml 不一致 |
| `gpio_seq` | run_sim.py | `gpio_out` 變化序列與 tests.toml 不一致 |
| `bus_assert` | TB | sel 不是 one-hot 或與 TB 自己的解碼不符；`mem_valid` 期間 addr/wdata/wstrb 變動；wstrb 非法；unmapped 存取（例外見下）；unmapped 讀取 handshake 時 `mem_rdata` ≠ 0；寫 ROM；周邊 sub-word 寫入；`mem_ready` 無 `mem_valid`；單筆交易超過 1000 cycle |
| `x_check` | TB（僅 Icarus） | reset 釋放 20 cycle 後，`trap`/`uart_tx`/`gpio_out`/`mem_valid` 出現 X；讀取 handshake 時 `mem_rdata` 含 X/Z |
| `sram_port` | TB | SRAM port 0 腳位協定：CPU 路徑每筆 SRAM 交易恰好一次存取且在 T0，addr0／web0／wmask0／din0 與交易一致，讀在 T2、寫在 T1 handshake；非 SRAM 交易或閒置時不得存取；取樣到 `resetn=0` 的上升緣不得存取；host 路徑 `csb0 = ~host_cs` 且其餘腳位等於 host 訊號 |
| `irq_line` | TB | `u_cpu.irq[4]` 每個 cycle 等於 IRQ_TRIG[0]（由 CPU 寫入推算；寫入交易進行中新舊值都接受） |
| `uart_div` | TB | reset 釋放時 simpleuart 除數 = `SOC_UART_DIV`，之後等於最後寫入 DIV 的值；每次 reset 後，第一次存取 UART DATA、第一次離開 Boot ROM、第一次寫 DONE 之前必須已寫 DIV = `SOC_UART_DIV` |
| `coverage` | run_sim.py | tests.toml 的 `sram_cov`（每個 word 的讀／寫／取指令次數與 byte strobe）、`min_uart_stalls`（被 stall 的 DATA 寫入數下限）、`reset_on_store` 時 mid-run reset 必須恰好 1 次 |
| `log_scan` | run_sim.py | log 出現 ERROR、FATAL、`Writing and reading`、模擬器 warning 等（白名單：`dv/log_whitelist.txt`） |
| `sim_error` | run_sim.py | 編譯失敗、模擬異常結束、找不到結果、`tb_result.txt` 缺任何欄位；testbench 自行中止（例如 host port 讀回或 byte mask 檢查不符） |

- **unmapped 例外**：§4.2 要求 unmapped 存取要回應、讀回 0、寫入忽略，但 `bus_assert` 對 unmapped 存取一律 FAIL，正向測試就驗證不了 §4.2。因此只有 tests.toml 設了 `expect_unmapped` 的測試（目前只有 `unmapped`，值 87），run_sim.py 才傳 `+allow_unmapped`：unmapped **資料**存取改成計數，次數必須完全相符；從 unmapped 位址取指令、decode mismatch、1000 cycle 上限照常 FAIL。
- host port 目前沒有獨立的 checker，錯誤由 testbench 中止並以 `sim_error` 回報（R13）。之後若新增 `host_port` checker，R13 改以它為預期。

- DONE 之後 testbench 繼續跑到 UART 閒置（至少 2 個 frame 時間）再結束，確保最後的 byte 被解碼。
- Testbench 輸出：`<out_dir>/uart.txt`（解碼 bytes）、`<out_dir>/gpio.txt`（每行一個 `gpio_out` 新值，十六進位）、`<out_dir>/tb_result.txt`（DONE 值、SIG 值、cycle 數）、`+trace` 時 `<out_dir>/trace.log`（每筆 handshake：cycle、addr、wdata、wstrb、rdata）、`<out_dir>/sram_cov.txt`（每個 SRAM word 的讀／取指令／寫次數與 strobe）。`tb_result.txt` 另含 `sig_at_done`、`uart_wr`、`uart_wr_stalled`、`uart_wr_stall_cycles`、`sram_port_accesses`、`mid_resets` 與各 TB checker 的 `fail.<name>`。

### 7.3 `dv/tests.toml` 與 `dv/bugs.toml`

```toml
[[test]]
name = "hello"            # 對應 fw/build/hello.hex
load = "backdoor"         # backdoor | host | uart | none
boot_mode = 0
max_cycles = 200000
expect_uart = "hello\n"
sig_rule = "uart_crc32"   # uart_crc32 | "const:0x4D415243" | none
expect_gpio = [0xB0]      # gpio_out 變化序列（不含 reset 值 0）；省略表示不檢查
uart_in = ""              # 送給 uart_rx 的文字（uart 載入時由 run_sim.py 產生 loader 封包）
smoke = true
negative_only = false     # true：只在 bugs.toml 引用，不列入正向 regression
# 以下為 Phase 1 review 後新增的選填欄位
min_cycles = 780000       # DONE=PASS 不得早於此 cycle（防止測試主體被跳過）
fw = "boot_uart_hello"    # 映像名稱與測試名稱不同時指定
loader_frame = "valid"    # valid | max_words | bad_checksum | n_zero | n_too_big（uart 載入的封包種類）
expect_unmapped = 87      # 允許並計數 unmapped 資料存取，次數必須完全相符
sram_cov = [{from = "_free_start", to = 0x700, rd = 88, wr = 22, fetch = 0, wstrb = [0x1, 0x2, 0x4, 0x8, 0x3, 0xC, 0xF]}]
                          # 每個 word 的存取次數（rd/wr/fetch 恰好；min_rd/min_wr 下限）；from/to 可寫 ELF symbol
min_uart_stalls = 80      # 被 transmitter 忙碌擋住的 UART DATA 寫入數下限
reset_on_store = "rst_victim"  # mid-run reset 的觸發位址（ELF symbol 或數值）
```

正向測試（`negative_only = false`）必須同時比對 `expect_uart`、`expect_gpio` 與 `sig_rule`（不可為 `none`），否則載入設定檔時即報錯。

```toml
[[bug]]
id = "R01"
define = "BUG_R01"        # 空字串表示不需 define（firmware 類）
test = "memtest"
sim = "icarus"
expect_checkers = ["test_ctrl"]
expect_regex = "(?i)0xbad00040"
exclusive = false         # 選填；true：expect_checkers 以外的 checker 也 FAIL 就算沒抓到
expect_gpio = [0xB1, 0xE1] # 選填；bug run 的 gpio_out 序列必須等於此值
fw = "memtest__no_march"  # 選填；改用 firmware 錯誤變體（此時 define = ""）
bootrom = "skip_last_word" # 選填；改用 Boot ROM 錯誤變體 fw/build/bootrom__<name>.v
```

### 7.4 Script 介面

| Script | 用法 | 結果 |
|---|---|---|
| `dv/scripts/run_sim.py` | `--test <name> --sim icarus\|verilator [--bug <id>] [--out runs/sim] [--trace] [--vcd]` | `runs/sim/<sim>/<test>[__<bug>]/result.json`；PASS 回傳 0，否則 1 |
| `dv/scripts/regress.py` | `--sims icarus,verilator --suite all\|smoke [-j N]` | 平行執行；`runs/sim/summary.json`、`runs/sim/junit.xml`；有任何 FAIL 回傳非 0 |
| `dv/scripts/neg.py` | `[--only R01,...]` | `runs/neg/summary.json`；每個 bug 都必須 FAIL 且至少一個 `expect_checkers` 失敗並符合 regex，否則回傳非 0 |

`result.json`：`{"test","sim","bug","status","failing_checkers":[],"messages":[],"cycles","uart_text","sig","done","log"}`。
**只有明確 PASS 才算 PASS**：收到 DONE=PASS、所有 checker 無 FAIL、log 掃描乾淨、模擬正常結束；任一條件缺漏即 FAIL。

---

## 8. Make targets（主控已寫好，各方提供被呼叫的 script）

| Target | 呼叫 |
|---|---|
| `make env-check` | `bash env/check_env.sh` |
| `make lint` | `bash rtl/scripts/lint.sh`（Verilator `--lint-only -Wall`；自有 RTL 必須 0 warning，第三方檔案以 `rtl/lint/waivers.vlt` 排除；`BUG_*` 清單從 `dv/bugs.toml` 讀取，與 RTL 雙向比對，每個 define 各 lint 一次） |
| `make synth-check` | `bash rtl/scripts/synth_check.sh`（本機 Yosys generic synth：無 latch、`sram0` blackbox 恰 1 個、`check -assert`） |
| `make fw` | `make -C fw all check-bootrom`（`all` 也建 negative test 用的 firmware／Boot ROM 錯誤變體） |
| `make sim TEST=hello SIM=icarus` | `python3 dv/scripts/run_sim.py ...` |
| `make regress-rtl` | `python3 dv/scripts/regress.py --sims icarus,verilator --suite all` |
| `make regress-rtl-smoke` | `python3 dv/scripts/regress.py --sims icarus --suite smoke` |
| `make neg-rtl` | `python3 dv/scripts/neg.py` |
| `make core-stock` | `bash scripts/core_stock.sh`（L1a：在 `runs/core_stock/` 的副本中跑上游 picorv32 測試，不得弄髒 submodule） |
| `make smoke` | `env-check lint fw regress-rtl-smoke`，目標 < 5 分鐘 |
| `make phase1` | `env-check lint synth-check fw core-stock regress-rtl neg-rtl` |

## 9. Phase 1 exit criteria

1. `make lint`、`make synth-check`、`make fw` PASS。
2. `make core-stock` PASS（若某個上游 target 因外部依賴無法執行，需在 `docs/notes/core_stock.md` 說明原因與替代方式）。
3. `make regress-rtl`：所有正向測試在 Icarus 與 Verilator 都 PASS。
4. `make neg-rtl`：`dv/bugs.toml` 的全部條目（§5，目前 33 項）都在預期的 checker FAIL。
5. `make smoke` < 5 分鐘。
