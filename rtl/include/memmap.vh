// =============================================================================
// memmap.vh — single source of truth for the SoC memory map and SW/HW contract.
// Consumers: RTL (`include), testbench (`include), firmware (fw/ generates soc.h
// from this file), Python checkers (parse `define lines).
// Parsing rule for scripts: lines of the form
//     `define NAME <width>'h<hex>   or   `define NAME <decimal>
// Underscores inside numbers are separators. Keep one define per line.
// =============================================================================
`ifndef SOC_MEMMAP_VH
`define SOC_MEMMAP_VH

// ---- SRAM: sky130_sram_2kbyte_1rw1r_32x512_8 (port 0 only) ----
`define SOC_SRAM_BASE        32'h0000_0000
`define SOC_SRAM_SIZE        32'h0000_0800
`define SOC_SRAM_WORDS       512

// ---- Boot ROM (synthesized case-ROM, 128 words max) ----
`define SOC_ROM_BASE         32'h0001_0000
`define SOC_ROM_SIZE         32'h0000_0200
`define SOC_ROM_WORDS        128

// ---- UART (third_party/picorv32/picosoc/simpleuart.v) ----
`define SOC_UART_BASE        32'h0200_0000
`define SOC_UART_SIZE        32'h0000_0008
`define SOC_UART_DIV_OFF     32'h0000_0000
`define SOC_UART_DATA_OFF    32'h0000_0004
// simpleuart bit period = divider register + 2 clock cycles (both TX and RX).
`define SOC_UART_DIV         18
`define SOC_UART_BIT_CYCLES  20
// simpleuart DATA read value when RX buffer empty
`define SOC_UART_RX_EMPTY    32'hFFFF_FFFF

// ---- GPIO ----
`define SOC_GPIO_BASE        32'h0300_0000
`define SOC_GPIO_SIZE        32'h0000_0008
`define SOC_GPIO_OUT_OFF     32'h0000_0000
`define SOC_GPIO_IN_OFF      32'h0000_0004

// ---- TEST_CTRL (simulation/bring-up status registers; exists in silicon too) ----
`define SOC_TEST_BASE        32'h0400_0000
`define SOC_TEST_SIZE        32'h0000_000C
`define SOC_TEST_SIG_OFF     32'h0000_0000
`define SOC_TEST_DONE_OFF    32'h0000_0004
`define SOC_TEST_IRQ_OFF     32'h0000_0008
// Hazard3 build only (SOC_CPU_HAZARD3, ADR-0011): FATAL drives the trap pin (Hazard3 has none);
// the window is SOC_TEST_SIZE_H3 there. The PicoRV32 build keeps SOC_TEST_SIZE.
`define SOC_TEST_FATAL_OFF   32'h0000_000C
`define SOC_TEST_SIZE_H3     32'h0000_0010
`define SOC_TEST_PASS_MAGIC  32'h600D_C0DE
// FAIL value = SOC_TEST_FAIL_BASE | code[15:0]
`define SOC_TEST_FAIL_BASE   32'hBAD0_0000

// ---- CPU (PicoRV32) ----
`define SOC_PROGADDR_RESET   32'h0001_0000
`define SOC_PROGADDR_IRQ     32'h0000_0010
`define SOC_STACK_TOP        32'h0000_0800
`define SOC_IRQ_TEST         4

// ---- Boot ROM modes (GPIO_IN[1:0] = boot_mode pins) ----
`define SOC_BOOT_JUMP        0
`define SOC_BOOT_MARCH       1
`define SOC_BOOT_UART        2
`define SOC_BOOT_RESERVED    3

// ---- Boot ROM GPIO_OUT status codes ----
`define SOC_GPIO_BOOT_BASE   8'hB0
`define SOC_GPIO_MARCH_PASS  8'hA5
`define SOC_GPIO_MARCH_FAIL  8'hE1
`define SOC_GPIO_LOAD_OK     8'hB8
`define SOC_GPIO_LOAD_FAIL   8'hEE

// ---- Boot ROM signatures / fail codes ----
`define SOC_MARCH_SIG        32'h4D41_5243
`define SOC_FAIL_MARCH       32'h0000_0E10
`define SOC_FAIL_LOAD        32'h0000_0B00

`endif // SOC_MEMMAP_VH
