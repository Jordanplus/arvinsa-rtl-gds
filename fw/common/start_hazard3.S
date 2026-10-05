/*
 * fw/common/start_hazard3.S - reset and trap entry for SoC firmware tests on Hazard3
 * (Phase 5, ADR-0011; the PicoRV32 build uses start.S). Built by fw/Makefile CPU=hazard3.
 *
 *   0x00  jump to _start (the boot ROM jumps to SOC_SRAM_BASE)
 *   0x10  trap entry: Hazard3 is configured with MTVEC_INIT = SOC_PROGADDR_IRQ in direct mode,
 *         so interrupts and exceptions both come here (skill core-migration-hazard3 rule 7).
 *         Saves t0 in mscratch and t1/t2 in trap_save (no stack).
 *         interrupt (mcause[31] = 1; the only one enabled is the machine external interrupt
 *           from irq[0] = TEST_CTRL.IRQ_TRIG[0]): clear IRQ_TRIG, irq_pending_mask =
 *           1 << SOC_IRQ_TEST (the PicoRV32 numbering the tests use), irq_count++, mret.
 *         exception with exc_resume != 0 (the exc test): exc_cause = mcause, exc_tval = mtval,
 *           exc_count++, mepc += length of the faulting instruction, mret.
 *         any other exception: TEST_CTRL.FATAL = mcause, which raises the trap pin (Hazard3 has
 *           no trap output), then spin; the testbench trap checker ends the run.
 *   _start: zero x1-x31 (Hazard3 is built with RESET_REGFILE = 0, so a 4-state simulator
 *           starts them at X), let the cycle and instret counters run (mcountinhibit resets to
 *           1), keep interrupts off (mie = 0, mstatus.MIE = 0), sp = SOC_STACK_TOP, clear .bss,
 *           call main; if main returns, test_fail(0xFF).
 * irq_setmask(mask) keeps the PicoRV32 meaning for the tests (1 = masked, returns the old mask):
 *   bit SOC_IRQ_TEST clear enables the external interrupt (mie.MEIE and mstatus.MIE); other bits
 *   have no Hazard3 counterpart (illegal instruction and bus error are exceptions here).
 */
#include "soc.h"

#define MIE_MEIE     0x800
#define MSTATUS_MIE  0x8

    .section .text.start, "ax", @progbits

    .global _reset
_reset:
    j       _start

    .balign 16
    .global _irq_entry
_irq_entry:
    csrw    mscratch, t0
    la      t0, trap_save
    sw      t1, 0(t0)
    sw      t2, 4(t0)
    csrr    t1, mcause
    bltz    t1, 3f
    la      t2, exc_resume
    lw      t2, 0(t2)
    beqz    t2, 5f
    /* resumable exception (exc test) */
    la      t2, exc_cause
    sw      t1, 0(t2)
    csrr    t1, mtval
    la      t2, exc_tval
    sw      t1, 0(t2)
    la      t2, exc_count
    lw      t1, 0(t2)
    addi    t1, t1, 1
    sw      t1, 0(t2)
    csrr    t1, mepc
    lhu     t2, 0(t1)               /* low halfword of the faulting instruction */
    andi    t2, t2, 3
    addi    t1, t1, 2               /* compressed: bits 1:0 != 3 */
    xori    t2, t2, 3
    bnez    t2, 1f
    addi    t1, t1, 2               /* 32-bit instruction */
1:  csrw    mepc, t1
    j       4f
3:  /* interrupt */
    li      t1, SOC_TEST_BASE
    sw      zero, SOC_TEST_IRQ_OFF(t1)      /* drop irq[0] (level) */
    la      t1, irq_pending_mask
    li      t2, 1 << SOC_IRQ_TEST
    sw      t2, 0(t1)
    la      t1, irq_count
    lw      t2, 0(t1)
    addi    t2, t2, 1
    sw      t2, 0(t1)
4:  la      t0, trap_save
    lw      t1, 0(t0)
    lw      t2, 4(t0)
    csrr    t0, mscratch
    mret
5:  /* fatal exception: FATAL = mcause raises the trap pin */
    li      t0, SOC_TEST_BASE
    sw      t1, SOC_TEST_FATAL_OFF(t0)
6:  j       6b

    .global _start
_start:
    li      x1, 0
    li      x2, 0
    li      x3, 0
    li      x4, 0
    li      x5, 0
    li      x6, 0
    li      x7, 0
    li      x8, 0
    li      x9, 0
    li      x10, 0
    li      x11, 0
    li      x12, 0
    li      x13, 0
    li      x14, 0
    li      x15, 0
    li      x16, 0
    li      x17, 0
    li      x18, 0
    li      x19, 0
    li      x20, 0
    li      x21, 0
    li      x22, 0
    li      x23, 0
    li      x24, 0
    li      x25, 0
    li      x26, 0
    li      x27, 0
    li      x28, 0
    li      x29, 0
    li      x30, 0
    li      x31, 0
    csrw    mcountinhibit, zero
    csrw    mie, zero
    csrci   mstatus, MSTATUS_MIE
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

/* uint32_t irq_setmask(uint32_t mask): see the header. */
    .section .text.irq_setmask, "ax", @progbits
    .global irq_setmask
irq_setmask:
    csrr    t0, mie
    csrr    t1, mstatus
    srli    t0, t0, 11
    srli    t1, t1, 3
    and     t0, t0, t1
    andi    t0, t0, 1               /* 1 = the external interrupt was enabled */
    li      t1, -1
    beqz    t0, 1f
    li      t1, ~(1 << SOC_IRQ_TEST)
1:  srli    t0, a0, SOC_IRQ_TEST
    andi    t0, t0, 1
    li      t2, MIE_MEIE
    bnez    t0, 2f
    csrs    mie, t2
    csrsi   mstatus, MSTATUS_MIE
    j       3f
2:  csrci   mstatus, MSTATUS_MIE
    csrc    mie, t2
3:  mv      a0, t1
    ret

    .section .bss.irq_state, "aw", @nobits
    .balign 4
    .global irq_count
irq_count:
    .word   0
    .global irq_pending_mask
irq_pending_mask:
    .word   0
    .global exc_resume
exc_resume:
    .word   0
    .global exc_count
exc_count:
    .word   0
    .global exc_cause
exc_cause:
    .word   0
    .global exc_tval
exc_tval:
    .word   0
trap_save:
    .word   0, 0
