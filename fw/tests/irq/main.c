/*
 * fw/tests/irq - IRQ path through TEST_CTRL.IRQ_TRIG -> irq[SOC_IRQ_TEST]
 * (docs/spec/soc_spec.md §4.8, §6.3, §6.4).
 *
 * Only irq[SOC_IRQ_TEST] is unmasked; irq[1] (illegal insn/ebreak) and irq[2]
 * (bus error) stay masked. Write IRQ_TRIG = 1 and wait for the handler count
 * to become non-zero. Then keep irq[SOC_IRQ_TEST] unmasked for a settle
 * window of about IRQ_SETTLE_LOOPS * 15 cycles, mask it again, and check
 *   - the number of handler entries is IRQ_MIN_ENTRIES..IRQ_MAX_ENTRIES, and
 *   - the recorded pending mask is 1 << SOC_IRQ_TEST.
 * If the IRQ never arrives the test spins until the timeout checker fires.
 *
 * Entry count: PicoRV32 latches IRQs (LATCHED_IRQ default, spec §4.8) and ORs
 * the irq lines into the pending set every cycle. IRQ_TRIG is a level that the
 * handler clears with its first store (spec §6.3), so irq[SOC_IRQ_TEST] is
 * latched again while the handler starts, and the handler runs a second time
 * right after retirq; both entries record 1 << SOC_IRQ_TEST. Spec §4.8 fixes
 * this at exactly 2 entries per IRQ_TRIG write. 1 entry means the line was not
 * a level (e.g. a one-cycle pulse); more entries mean the IRQ line did not drop
 * when IRQ_TRIG was cleared (or the handler did not clear it); none within the
 * window means no IRQ at all. A line released a few tens of cycles late can
 * still give 2 entries; the testbench irq_line checker compares the line with
 * IRQ_TRIG[0] in every cycle and catches that.
 *
 * Fail codes: 0x10 recorded pending mask is not 1 << SOC_IRQ_TEST,
 *             0x20 handler entry count outside IRQ_MIN_ENTRIES..IRQ_MAX_ENTRIES.
 */
#include "fwlib.h"

#define FAIL_MASK        0x10
#define FAIL_COUNT       0x20
#define IRQ_MIN_ENTRIES  2u   /* spec §4.8: exactly 2 entries per IRQ_TRIG write */
#define IRQ_MAX_ENTRIES  2u
/* Each loop iteration is a few instructions (about 15 cycles on PicoRV32),
 * so the window is about 3000 cycles: much longer than the IRQ entry latency
 * (about 100 cycles per entry). */
#define IRQ_SETTLE_LOOPS 200u

int main(void)
{
    uint32_t n;

    uart_init();
    irq_setmask(~(1u << SOC_IRQ_TEST));
    TEST_IRQ_REG = 1;
    while (irq_count == 0)
        ;
    for (unsigned i = 0; i < IRQ_SETTLE_LOOPS; i++)
        __asm__ volatile ("" ::: "memory");
    irq_setmask(~0u);
    n = irq_count;
    if (n < IRQ_MIN_ENTRIES || n > IRQ_MAX_ENTRIES)
        test_fail(FAIL_COUNT);
    if (irq_pending_mask != (1u << SOC_IRQ_TEST))
        test_fail(FAIL_MASK);
    uart_puts("irq PASS\n");
    test_pass();
}
