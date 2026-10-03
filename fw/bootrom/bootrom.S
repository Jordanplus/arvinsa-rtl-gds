/*
 * fw/bootrom/bootrom.S - SoC boot ROM (docs/spec/soc_spec.md §6.5).
 *
 * Linked at SOC_ROM_BASE (= SOC_PROGADDR_RESET), at most SOC_ROM_WORDS words,
 * plain RV32I without compressed instructions. Never uses SRAM as a stack:
 * subroutines are leaf routines called with jal (return address in ra).
 *
 *   1. UART DIV = SOC_UART_DIV; mode = GPIO_IN[1:0]; GPIO_OUT = 0xB0 | mode.
 *   2. mode 0 (JUMP) or 3 (RESERVED): jump to SOC_SRAM_BASE.
 *   3. mode 1 (MARCH): march C- over all SOC_SRAM_WORDS words with data 0 and
 *      all-ones: up(w0) up(r0,w1) up(r1,w0) down(r0,w1) down(r1,w0) up(r0),
 *      then address-in-address (every word holds its own byte address, all
 *      written first, then all read back).
 *        PASS: GPIO_OUT = 0xA5, SIG = 0x4D415243, DONE = PASS magic.
 *        FAIL: GPIO_OUT = 0xE1, DONE = 0xBAD00E10. Then spin.
 *   4. mode 2 (UART): N (2 bytes, little-endian, 1 <= N <= 448), N*4 image bytes
 *      (little-endian words, stored to SRAM words 0..N-1), 1 checksum byte
 *      (sum of all image bytes mod 256).
 *        OK:   GPIO_OUT = 0xB8, jump to SOC_SRAM_BASE.
 *        FAIL: GPIO_OUT = 0xEE, DONE = 0xBAD00B00, spin. A bad N fails at once.
 *
 * Register use: s2 UART base, s3 GPIO base, s4 TEST_CTRL base, s0 mode,
 * s5/s6 SRAM start/end, s1 RX-empty value, s7..s11 loader state.
 *
 * SRAM accesses in mode 1 (dv/tests.toml bootrom_march sram_cov checks them):
 * every word is written 6 times (M0, M1, M2, M3, M4, address-in-address) and
 * read 6 times (M1, M2, M3, M4, M5, address-in-address), all 32-bit.
 *
 * BRBUG_* macros exist only for the negative-test boot ROM variants
 * fw/build/bootrom__<variant>.v (fw/README.md); the regular build and
 * rtl/bootrom/bootrom.v never define them.
 */
#include "fw_layout.h"

#define SRAM_END   (SOC_SRAM_BASE + SOC_SRAM_WORDS * 4)

    .option norvc
    .section .text.boot, "ax", @progbits
    .global _start
_start:
    li      s2, SOC_UART_BASE
#ifndef BRBUG_NO_DIV_WRITE
    li      t0, SOC_UART_DIV
    sw      t0, SOC_UART_DIV_OFF(s2)
#endif
    li      s3, SOC_GPIO_BASE
    lw      s0, SOC_GPIO_IN_OFF(s3)
    andi    s0, s0, 3                       /* mode = boot_mode[1:0] */
    ori     t0, s0, SOC_GPIO_BOOT_BASE
    sw      t0, SOC_GPIO_OUT_OFF(s3)
    li      s4, SOC_TEST_BASE
    li      t0, SOC_BOOT_MARCH
    beq     s0, t0, boot_march
    li      t0, SOC_BOOT_UART
    beq     s0, t0, boot_uart
    /* SOC_BOOT_JUMP and SOC_BOOT_RESERVED fall through */
jump_sram:
    li      t0, SOC_SRAM_BASE
    jr      t0

/* ---------------------------------------------------------------- mode 1 */
boot_march:
    li      s5, SOC_SRAM_BASE
#ifndef BRBUG_SKIP_LAST_WORD
    li      s6, SRAM_END
#else
    li      s6, SRAM_END - 4                /* variant: last word never tested */
#endif
    li      a2, 0
    jal     fill_up                         /* M0 up(w0) */
    li      a0, 0
    li      a1, -1
    jal     rw_up                           /* M1 up(r0,w1) */
    li      a0, -1
    li      a1, 0
    jal     rw_up                           /* M2 up(r1,w0) */
    li      a0, 0
    li      a1, -1
    jal     rw_down                         /* M3 down(r0,w1) */
    li      a0, -1
    li      a1, 0
    jal     rw_down                         /* M4 down(r1,w0) */
    jal     check_up                        /* M5 up(r0): a2 = 0 */
    li      a2, -1
    jal     fill_up                         /* address-in-address: write */
#ifndef BRBUG_NO_AIA_READBACK
    jal     check_up                        /* address-in-address: read back */
#endif
    li      t0, SOC_GPIO_MARCH_PASS
    sw      t0, SOC_GPIO_OUT_OFF(s3)
    li      t0, SOC_MARCH_SIG
    sw      t0, SOC_TEST_SIG_OFF(s4)
    li      t0, SOC_TEST_PASS_MAGIC
    sw      t0, SOC_TEST_DONE_OFF(s4)
    j       hang

march_fail:
    li      t0, SOC_GPIO_MARCH_FAIL
    sw      t0, SOC_GPIO_OUT_OFF(s3)
    li      t0, SOC_TEST_FAIL_BASE | SOC_FAIL_MARCH
    sw      t0, SOC_TEST_DONE_OFF(s4)
hang:
    j       hang

/* fill_up: word[p] = p & a2 for p = s5 .. s6-4 (a2 = 0: zeros, a2 = -1: own address) */
fill_up:
    mv      t0, s5
1:  and     t2, t0, a2
    sw      t2, 0(t0)
    addi    t0, t0, 4
    bne     t0, s6, 1b
    ret

/* check_up: expect word[p] == p & a2, ascending */
check_up:
    mv      t0, s5
1:  lw      t1, 0(t0)
    and     t2, t0, a2
    bne     t1, t2, march_fail
    addi    t0, t0, 4
    bne     t0, s6, 1b
    ret

/* rw_up / rw_down: expect a0 then write a1, ascending / descending */
rw_up:
    mv      t0, s5
1:  lw      t1, 0(t0)
    bne     t1, a0, march_fail
    sw      a1, 0(t0)
    addi    t0, t0, 4
    bne     t0, s6, 1b
    ret

rw_down:
    mv      t0, s6
1:  addi    t0, t0, -4
    lw      t1, 0(t0)
    bne     t1, a0, march_fail
    sw      a1, 0(t0)
    bne     t0, s5, 1b
    ret

/* ---------------------------------------------------------------- mode 2 */
boot_uart:
    li      s1, SOC_UART_RX_EMPTY
    jal     getb
    mv      s7, a0
    jal     getb
    slli    a0, a0, 8
    or      s7, s7, a0                      /* N = word count */
    beqz    s7, load_fail
    li      t0, FW_LOAD_MAX_WORDS
    bgtu    s7, t0, load_fail
    li      s8, 0                           /* byte sum */
    li      s11, 0                          /* word being assembled (never read uninitialized) */
    li      s9, SOC_SRAM_BASE               /* store pointer */
    slli    s10, s7, 2
    add     s10, s10, s9                    /* end pointer */
load_word:
    li      t2, 4
1:  jal     getb
    add     s8, s8, a0
    srli    s11, s11, 8
    slli    a0, a0, 24
    or      s11, s11, a0                    /* little-endian word assembly */
    addi    t2, t2, -1
    bnez    t2, 1b
    sw      s11, 0(s9)
    addi    s9, s9, 4
    bne     s9, s10, load_word
    jal     getb                            /* checksum byte */
    andi    s8, s8, 0xFF
    bne     a0, s8, load_fail
    li      t0, SOC_GPIO_LOAD_OK
    sw      t0, SOC_GPIO_OUT_OFF(s3)
    j       jump_sram

load_fail:
    li      t0, SOC_GPIO_LOAD_FAIL
    sw      t0, SOC_GPIO_OUT_OFF(s3)
    li      t0, SOC_TEST_FAIL_BASE | SOC_FAIL_LOAD
    sw      t0, SOC_TEST_DONE_OFF(s4)
    j       hang

/* getb: a0 = next received byte (blocking) */
getb:
    lw      a0, SOC_UART_DATA_OFF(s2)
    beq     a0, s1, getb
    ret
