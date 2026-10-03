# fw/：SoC firmware 與 Boot ROM

契約：`docs/spec/soc_spec.md` §6（firmware）、§4.6（Boot ROM 介面）、§5（negative test）。
位址一律來自 `rtl/include/memmap.vh`，經 `fw/scripts/gen_soc_h.py` 產生 `fw/build/soc.h`，不手寫位址。

## Make targets（GNU make 3.81）

| 指令 | 產出 |
|---|---|
| `make -C fw all` | 全部測試 image ＋ Boot ROM image ＋ `build/size_report.txt` |
| `make -C fw <test>` | `build/<test>.elf .bin .hex .lst`（另有 `.map`、`.size`） |
| `make -C fw bootrom_march` | 只建 Boot ROM image（這個測試不載入 SRAM） |
| `make -C fw bootrom` | 重產 `rtl/bootrom/bootrom.v`（產生物，需 commit） |
| `make -C fw check-bootrom` | 重產到 `build/bootrom_check.v` 並與 `rtl/bootrom/bootrom.v` 比對，不同即 FAIL |
| `make -C fw variants` | negative test 用的 bug 變體（見下方「negative test 用的 bug 變體」）；`all` 會一起建 |
| `make -C fw clean` | 刪除 `build/` |

- `.hex`：`$readmemh` 格式，每行一個 32-bit word，第一行是 SRAM word 0，little-endian 組字；行數 = image word 數（不補滿 512）。
- `build/build_flags.txt`：記錄編譯旗標、toolchain 版本與每個測試的 size 上限。每次 `make` 都會重新產生，但內容不變時不覆寫；
  所有 object、linker script、ELF 與 size checker 都依賴它和 `Makefile` 本身，所以改了旗標（包括命令列覆寫）或 Makefile，
  增量 build 會整批重建，結果與 clean build 一致。注意 make 3.81 的檔案時間只到秒：同一秒內改旗標又 build 可能不會觸發，實際操作不會遇到。
- `boot_uart_hello`、`boot_host_hello` 與 `hello` 同一份原始碼，image 內容相同，只是檔名不同。
- size checker（`scripts/size_check.py`）：`_free_start > 0x700` 時 build FAIL；`memtest` 另外要求 `_free_start ≤ 0x400`。

## 記憶體配置（`common/link.ld`，經 C 前處理器展開到 `build/link.ld`）

| 位址 | 內容 |
|---|---|
| `0x000` | `j _start` |
| `0x010` | IRQ 入口（`SOC_PROGADDR_IRQ`） |
| 之後 | `.text`、`.rodata`、`.data`、`.bss`；`_free_start` = bss 結束（4-byte 對齊） |
| `0x700`–`0x7FF` | stack 保留區（256 B），`sp` 初值 `SOC_STACK_TOP` = `0x800` |

`start.S` 流程：s0–s11 歸零 → 遮蔽全部 IRQ → `sp` → 清 `.bss` → `main()`；`main` 返回則 `test_fail(0xFF)`。

## 函式庫（`common/fwlib.h`）

`uart_init`（每個測試開頭必呼叫）、`uart_putc`／`uart_puts`（送出並累計 CRC32，與 Python `zlib.crc32` 相同）、
`uart_getc`（blocking）、`uart_puthex`、`uart_crc32`、`irq_setmask`、`test_pass`（SIG = CRC32，DONE = PASS）、`test_fail(code)`。

## 測試與 fail code（DONE = `0xBAD0_0000 | code`）

| 測試 | UART 輸出 | fail code |
|---|---|---|
| `hello` | `hello\n` | — |
| `memtest` | `memtest PASS\n` | `0x01` image 超過 `0x400`、`0x10` 固定 pattern、`0x20` address-in-address、`0x30` march C−、`0x40` byte-lane |
| `irq` | `irq PASS\n` | `0x10` 記錄的 pending mask ≠ `1<<4`；`0x20` handler 進入次數不是恰好 2 次（spec §4.8）；IRQ 沒來則一直等（由 timeout checker FAIL） |
| `muldiv` | `muldiv PASS\n` | `0x100 \| (case << 3) \| op`，op 依序為 mul、mulh、mulhsu、mulhu、div、divu、rem、remu |
| `uart_echo` | `echo:` ＋ 收到的那一行 | `0x01` 一行超過 64 byte |
| `neg_fw_hang` | `hang\n` | 永不寫 DONE（negative test，預期 timeout checker FAIL） |
| `neg_fw_illegal` | `illegal\n` | 執行非法指令（negative test，預期 trap checker FAIL）；若沒有 trap 則寫 `0x01` |
| `regs` | `regs PASS\n` | `0x0200 \| mask`：bit 0 GPIO_OUT、1 GPIO_IN、2 SIG、3 IRQ_TRIG、4 UART DIV、5 UART DATA（全部檢查完才回報，一次列出所有壞掉的暫存器）；`0x0240` DONE 讀回不是 PASS magic（第二次寫 DONE）；`0x03wr` cross-talk（見表下說明） |
| `unmapped` | `unmapped PASS\n` | `0x0100 \| i` 第 i 個空洞位址讀到非 0；`0x0180 \| i` 寫入後再讀非 0；`0x01` canary（SRAM）被改、`0x02` SIG、`0x03` IRQ_TRIG、`0x04` GPIO_OUT、`0x05` UART DIV 被改 |
| `uart_burst` | `uart_burst 0123456789 ABC…XYZ abc…xyz PASS\n`（81 byte） | 無（firmware 看不到 TX 線；由 testbench 的 `uart_golden`、`signature`、`coverage` 判定） |
| `reset_store` | `reset_store PASS\n` | `0x01` 寫 `rst_victim` 之後沒有被 reset、`0x02` `rst_stage` 值不對、`0x03` reset 邊緣上的 store 被寫進去了 |

任何測試的 `main()` 若返回，`start.S` 寫 fail code `0xFF`。Boot ROM 的 fail code：march `0x0E10`、loader `0x0B00`。
`regs` 另有 cross-talk fail code `0x0300 | (w << 4) | r`：寫第 w 號暫存器改到了第 r 號（編號：GPIO_OUT 0、GPIO_IN 1、SIG 2、
IRQ_TRIG 3、UART DIV 4、UART DATA 5、DONE 6；w = 5 是送完 UART 文字後的檢查，w = 15 是第一次寫入前的檢查）。

## Boot ROM（`bootrom/bootrom.S`，RV32I，連結到 `0x0001_0000`，118／128 words，不使用 SRAM 當 stack）

1. UART DIV = 18；讀 GPIO_IN 得 mode；GPIO_OUT = `0xB0 | mode`。
2. mode 0／3：跳到 `0x0`。
3. mode 1：整個 SRAM 做 march C−（資料 0 與全 1），再做 address-in-address（每個 word 寫入自己的 byte 位址）。
   PASS：GPIO_OUT `0xA5`、SIG `0x4D41_5243`、DONE PASS。FAIL：GPIO_OUT `0xE1`、DONE `0xBAD0_0E10`。
4. mode 2：UART loader，封包為 N（2 byte LE，1–448）＋ N×4 byte image ＋ 1 byte checksum（image byte 總和 mod 256）。
   正確：GPIO_OUT `0xB8` 後跳到 `0x0`；N 不合法或 checksum 錯：GPIO_OUT `0xEE`、DONE `0xBAD0_0B00`。

## 給 testbench 的時序資訊（RTL 模擬實測，Icarus，CPU 放開後起算）

| 項目 | 數值 | 對 testbench 的意義 |
|---|---|---|
| `uart_echo` 第一次讀 UART DATA | 約 360 cycle | UART RX 只有 1 byte 緩衝；第 2 個 byte 必須在這之後才收完，`+uart_in_delay` 建議 ≥ 400 |
| Boot ROM loader 第一次讀 UART DATA | 約 80 cycle | `uart_in_delay` = 0 也可以 |
| `memtest` 完成 | 約 871k cycle | `max_cycles` 需大於此值（建議 ≥ 1.2M） |
| `bootrom_march` 完成 | 約 112k cycle | 建議 `max_cycles` ≥ 200k |
| `boot_uart_hello` 完成（`uart_in_delay`=400） | 約 63k cycle | 建議 `max_cycles` ≥ 150k |

- `irq`：PicoRV32 的 IRQ 是 latched，IRQ_TRIG 在 handler 清掉之前已再次被鎖存，所以每寫一次 IRQ_TRIG，handler 會進入兩次
  （兩次記錄的 pending mask 都是 `1<<4`）。測試先等「計數 ≠ 0」，再讓 `irq[4]` 保持開放約 3000 cycle，關閉後要求計數**恰好 2 次**（spec §4.8）。
  1 次代表 IRQ 線不是位準（例如只有 1 cycle 的脈衝）；3 次以上代表 IRQ 線在 IRQ_TRIG 清掉後沒有放掉。
  IRQ 線晚 40 cycle 才放掉仍然是 2 次，firmware 看不到，由 testbench 的 `irq_line` checker 逐 cycle 比對抓。

## 定向測試（spec §6.4 以外，testbench qualification 補的）

- `regs`（boot_mode 3）：Boot ROM 對保留模式寫 GPIO_OUT = `0xB3` 後跳到 SRAM。測試讀回 `0xB3`，再對 GPIO_OUT 依序寫
  `0x01 … 0x80`（walking ones）、`0xFF`、`0x00`、`0xB3`（寫入值的 bit 31:8 全為 1，必須被忽略），每次讀回比對低 8 bit；
  `dv/tests.toml` 的 `expect_gpio` 列出相同序列，所以每個 pin 都在 SoC 輸出端被確認過 1 與 0。GPIO_IN 必須是 3。
  SIG、IRQ_TRIG、UART DIV 做 32 bit walking ones 加 `0xFFFFFFFF`、`0xA5A5A5A5`、`0x5A5A5A5A`、`0` 的讀寫比對
  （IRQ_TRIG bit 0 會拉 `irq[4]`，但 IRQ 全程遮蔽）；DIV 測完由 `uart_init()` 還原，之後才送 UART。UART DATA 必須讀到 `0xFFFF_FFFF`。
  最後寫 DONE = PASS 後讀回，必須仍是 PASS magic。
- `unmapped`：29 個空洞位址（每個視窗的上一個與下一個 word、partial decode 會疊到暫存器的位址，例如 UART + 0x10 = DIV、
  TEST_CTRL + 0x14 = DONE、會疊到 SRAM 某個 word 的 `0x800 + x`、`0x1000 + x`、`0x20000 + x`、`0x8000_0000 + x`，以及 `0x0500_0000`、
  `0x8000_0000`、`0xFFFF_FFFC`）。每個先讀（必須 0）再寫 `0xFFFFFFFF`，全部寫完再讀一次（仍須 0），最後確認 canary、SIG、IRQ_TRIG、
  GPIO_OUT、UART DIV 都沒變。共 87 次 unmapped 存取，與 `dv/tests.toml` 的 `expect_unmapped` 一致；改了這支測試要同步更新該值。
- `regs` 的 cross-talk 檢查（review M4）：前面的逐一讀寫都通過之後，對 GPIO_OUT、GPIO_IN（唯讀，寫入必須被忽略）、SIG、IRQ_TRIG、
  UART DIV 各寫兩輪互不相同的值，每寫一次就把這五個加上 UART DATA、DONE 全部讀回比對；送完 `regs PASS\n` 再全部讀一次。
  GPIO_OUT 因此多了 `0x3C`、`0xC3`、`0xB3` 三個值（`dv/tests.toml` 的 `expect_gpio` 已同步）。
- `uart_burst`（review M1）：`uart_putc()` 每送一個 byte 前要先算 CRC，花的時間比一個 UART frame（200 cycle）長，
  所以其他測試從來不會在傳送中寫 UART DATA，§4.2 的 stall 從沒被用到。這個測試用 `uart_puts_burst()` 連續寫入整行（CRC 事後再算），
  81 次寫入全部被 stall 擋住（Phase 1 RTL 實測共 13558 個 stall cycle）。
- `reset_store`（review m6，§4.9 RTL-RST-01）：`rst_stage`、`rst_victim` 放在 `.data`（backdoor 載入時初始化一次，`start.S` 不清），
  所以第二次開機看得到第一次留下的值。第一次開機寫 `rst_stage`，再寫 `rst_victim = 0xDEADBEEF`；testbench（`dv/tests.toml`
  `reset_on_store = "rst_victim"`）在這個 store 出現的下降緣把 `resetn` 拉低，CPU 從 Boot ROM 重新開機；第二次開機檢查 `rst_victim`
  仍是原值 `0x0DDC0FFE`。GPIO_OUT 因此是 `0xB0 → 0x00 → 0xB0`。
- `memtest` 與 Boot ROM march 的 SRAM 存取次數：`dv/tests.toml` 的 `sram_cov` 逐 word 比對（`memtest` 測試區每個 word 88 讀、22 寫，
  strobe 1/2/4/8/3/C/F 各至少一次；Boot ROM 512 個 word 每個 6 讀 6 寫），推導寫在 `tests/memtest/main.c` 與 `bootrom/bootrom.S` 開頭。
  改動這兩支程式的任何階段都要同步更新 `sram_cov`。

## negative test 用的 bug 變體

有些錯誤只能放在 firmware 或 Boot ROM 裡（RTL 的 `` `define `` 植入不了），例如 Boot ROM 少寫一步、`test_pass()` 寫入順序顛倒。
為了讓 `dv/bugs.toml` 也能用它們當 negative test，`make -C fw all` 另外建「bug 變體」，只放在 `build/`，不影響正常的 image 與 `rtl/bootrom/bootrom.v`：

| 種類 | 定義（`Makefile`） | 產出 | `dv/bugs.toml` 用法 |
|---|---|---|---|
| firmware 變體 `<test>__<名稱>` | `FW_VARIANTS`；`VSRC_<變體>` = 原始碼目錄、`VDEF_<變體>` = 額外的 `-D` | `build/<變體>.elf .bin .hex .lst .size`（`fw/common` 也用同一個 `-D` 重編） | `fw = "<變體>"`，`define = ""` |
| Boot ROM 變體 `<名稱>` | `BOOTROM_VARIANTS`；`BRDEF_<名稱>` = 額外的 `-D` | `build/bootrom__<名稱>.elf .hex .lst .v`（module 名稱同樣是 `bootrom`） | `bootrom = "<名稱>"`，`define = ""`；`run_sim.py` 用它取代 `rtl/bootrom/bootrom.v` |

原始碼裡的植入點一律用 `#ifdef FWBUG_*`（firmware）或 `#ifdef BRBUG_*`（Boot ROM）包起來，正常 build 從不定義它們；
`check-bootrom` 只比對正常 build，所以 `rtl/bootrom/bootrom.v` 永遠是正確的 ROM。目前的變體：

| 變體 | 植入的錯誤 | bugs.toml |
|---|---|---|
| `memtest__no_march` | `FWBUG_MEMTEST_NO_MARCH`：刪掉 march C− 階段 | M01 |
| `hello__done_before_sig` | `FWBUG_DONE_BEFORE_SIG`：`test_pass()` 先寫 DONE 再寫 SIG | S01 |
| `reset_store__no_victim` | `FWBUG_RESET_STORE_NO_VICTIM`：第一次開機寫到別的變數 | C01 |
| `bootrom__skip_last_word` | `BRBUG_SKIP_LAST_WORD`：march 與 address-in-address 跳過最後一個 word | B01 |
| `bootrom__no_aia_readback` | `BRBUG_NO_AIA_READBACK`：拿掉 address-in-address 讀回 | B02 |
| `bootrom__no_div_write` | `BRBUG_NO_DIV_WRITE`：step 1 不寫 UART DIV | B03 |

- X 檢查（x_check）相關：PicoRV32 register file 沒有 reset，`start.S` 先把 s0–s11 歸零，避免函式 prologue 存入、
  epilogue 讀回一個從沒寫過的暫存器而讓 `mem_rdata` 出現 X；`uart_echo` 的接收緩衝只用整個 word 寫入，
  避免讀到同一個 word 裡從沒寫過的 byte。
