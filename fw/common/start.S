/*
 * fw/common/start.S - reset and IRQ entry for SoC firmware tests
 * (docs/spec/soc_spec.md §6.2, §6.3).
 *
 *   0x00  jump to _start (the boot ROM jumps to SOC_SRAM_BASE)
 *   0x10  IRQ entry (SOC_PROGADDR_IRQ): clear IRQ_TRIG, record q1 (pending mask),
 *         increment irq_count, retirq. Uses q2/q3 to preserve t0/t1, no stack.
 *   _start: zero s0-s11, mask all IRQs, sp = SOC_STACK_TOP, clear .bss,
 *           call main; if main returns, test_fail(0xFF).
 *
 * PicoRV32 custom instructions come from third_party/picorv32/firmware/custom_ops.S
 * (q0 = return PC, q1 = pending IRQ bitmask at entry).
 */
#include "soc.h"
#include "custom_ops.S"

    .section .text.start, "ax", @progbits

    .global _reset
_reset:
    j       _start

    .balign 16
    .global _irq_entry
_irq_entry:
    picorv32_setq_insn(q2, t0)
    picorv32_setq_insn(q3, t1)
    li      t0, SOC_TEST_BASE
    sw      zero, SOC_TEST_IRQ_OFF(t0)      /* drop irq[SOC_IRQ_TEST] */
    picorv32_getq_insn(t1, q1)
    lui     t0, %hi(irq_pending_mask)
    sw      t1, %lo(irq_pending_mask)(t0)
    lui     t0, %hi(irq_count)
    lw      t1, %lo(irq_count)(t0)
    addi    t1, t1, 1
    sw      t1, %lo(irq_count)(t0)
    picorv32_getq_insn(t0, q2)
    picorv32_getq_insn(t1, q3)
    picorv32_retirq_insn()

    .global _start
_start:
    /* PicoRV32 does not reset its register file (REGS_INIT_ZERO=0), so in a
     * 4-state simulator every register the boot ROM did not write is X. C
     * prologues save callee-saved registers whether or not they were ever
     * written (e.g. s0 in uart_puts) and the epilogue loads them back, which
     * would put X on mem_rdata at that read handshake (x_check). Zero s0-s11.
     * Other registers are only stored to memory while they hold a live, written
     * value, so they are left alone to keep the reset-to-main latency short. */
    li      s0, 0
    li      s1, 0
    li      s2, 0
    li      s3, 0
    li      s4, 0
    li      s5, 0
    li      s6, 0
    li      s7, 0
    li      s8, 0
    li      s9, 0
    li      s10, 0
    li      s11, 0
    /* Keep every IRQ masked (incl. irq[1] illegal insn/ebreak and irq[2] bus error,
     * which must trap); tests unmask only what they need via irq_setmask(). */
    li      t0, -1
    picorv32_maskirq_insn(zero, t0)
    li      sp, SOC_STACK_TOP
    la      t0, _bss_start
    la      t1, _bss_end
1:  bgeu    t0, t1, 2f
    sw      zero, 0(t0)
    addi    t0, t0, 4
    j       1b
2:  call    main
    li      a0, 0xFF
    tail    test_fail

/* uint32_t irq_setmask(uint32_t mask): set the PicoRV32 IRQ mask (1 = masked),
 * return the previous mask. */
    .section .text.irq_setmask, "ax", @progbits
    .global irq_setmask
irq_setmask:
    picorv32_maskirq_insn(a0, a0)
    ret

    .section .bss.irq_state, "aw", @nobits
    .balign 4
    .global irq_count
irq_count:
    .word   0
    .global irq_pending_mask
irq_pending_mask:
    .word   0
