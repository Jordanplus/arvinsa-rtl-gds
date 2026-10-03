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
| `irq` | `irq PASS\n` | `0x10` 記錄的 pending mask ≠ `1<<4`；`0x20` handler 進入次數不在 1–2 次；IRQ 沒來則一直等（由 timeout checker FAIL） |
| `muldiv` | `muldiv PASS\n` | `0x100 \| (case << 3) \| op`，op 依序為 mul、mulh、mulhsu、mulhu、div、divu、rem、remu |
| `uart_echo` | `echo:` ＋ 收到的那一行 | `0x01` 一行超過 64 byte |
| `neg_fw_hang` | `hang\n` | 永不寫 DONE（negative test，預期 timeout checker FAIL） |
| `neg_fw_illegal` | `illegal\n` | 執行非法指令（negative test，預期 trap checker FAIL）；若沒有 trap 則寫 `0x01` |
| `regs` | `regs PASS\n` | `0x0200 \| mask`：bit 0 GPIO_OUT、1 GPIO_IN、2 SIG、3 IRQ_TRIG、4 UART DIV、5 UART DATA（全部檢查完才回報，一次列出所有壞掉的暫存器）；`0x0240` DONE 讀回不是 PASS magic（第二次寫 DONE） |
| `unmapped` | `unmapped PASS\n` | `0x0100 \| i` 第 i 個空洞位址讀到非 0；`0x0180 \| i` 寫入後再讀非 0；`0x01` canary（SRAM）被改、`0x02` SIG、`0x03` IRQ_TRIG、`0x04` GPIO_OUT、`0x05` UART DIV 被改 |

任何測試的 `main()` 若返回，`start.S` 寫 fail code `0xFF`。Boot ROM 的 fail code：march `0x0E10`、loader `0x0B00`。

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
  （兩次記錄的 pending mask 都是 `1<<4`）。測試先等「計數 ≠ 0」，再讓 `irq[4]` 保持開放約 3000 cycle，關閉後要求計數在 1–2 次之間：
  Phase 1 RTL 是 2 次；spec §6.4 寫「計數變 1」，所以 1 次也接受，等主控在 spec 定下確切次數。3 次以上代表 IRQ 線在 IRQ_TRIG 清掉後沒有放掉。

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
- X 檢查（x_check）相關：PicoRV32 register file 沒有 reset，`start.S` 先把 s0–s11 歸零，避免函式 prologue 存入、
  epilogue 讀回一個從沒寫過的暫存器而讓 `mem_rdata` 出現 X；`uart_echo` 的接收緩衝只用整個 word 寫入，
  避免讀到同一個 word 裡從沒寫過的 byte。
