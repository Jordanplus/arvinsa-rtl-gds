/*
 * fw/tests/buserr - the bus-error IRQ (irq[2]) of PicoRV32 (CATCH_MISALIGN = 1, spec §4.8).
 *
 * Why (docs/phase_exit/phase2.md known limitation 7, phase3.md known limitation 11): every
 * other test keeps irq[2] masked (start.S), where a misaligned access traps, so a netlist with the
 * bus-error IRQ broken (irq_pending[2] stuck at 0) passed every gate-level simulation.
 *
 * With irq[2] unmasked, PicoRV32 only flags a misaligned access: irq[2] becomes pending
 * (third_party/picorv32/picorv32.v 1922-1935) and the access still goes to the bus at the word
 * address with bits 1:0 dropped (line 382), a word store with all four byte strobes (403-406).
 * The IRQ entry in start.S runs after the instruction and retirq continues with the next one.
 * Checks, for a misaligned lw and then a misaligned sw:
 *   exactly one more IRQ entry, with pending mask 1 << 2;
 *   the lw returned the aligned word; the sw wrote the aligned word and nothing else.
 * Then irq[2] is masked again.
 *
 * Fail codes: 0x10 lw: entry count, 0x11 lw: pending mask, 0x12 lw: value,
 *             0x20 sw: entry count, 0x21 sw: pending mask, 0x22 sw: memory.
 */
#include "fwlib.h"

#define IRQ_BUSERR 2u

static volatile uint32_t target[2] = { 0x11223344u, 0x55667788u };

/* Inline assembly: GCC splits a C access through a pointer it knows to be misaligned into byte
 * and halfword accesses, which would not test anything. */
static inline uint32_t lw_at(uintptr_t addr)
{
    uint32_t v;
    __asm__ volatile ("lw %0, 0(%1)" : "=r"(v) : "r"(addr) : "memory");
    return v;
}

static inline void sw_at(uintptr_t addr, uint32_t v)
{
    __asm__ volatile ("sw %0, 0(%1)" : : "r"(v), "r"(addr) : "memory");
}

int main(void)
{
    uart_init();
    irq_setmask(~(1u << IRQ_BUSERR));

    uint32_t v = lw_at((uintptr_t)&target[0] + 2);
    if (irq_count != 1)
        test_fail(0x10);
    if (irq_pending_mask != (1u << IRQ_BUSERR))
        test_fail(0x11);
    if (v != 0x11223344u)
        test_fail(0x12);

    sw_at((uintptr_t)&target[0] + 1, 0xdeadbeefu);
    if (irq_count != 2)
        test_fail(0x20);
    if (irq_pending_mask != (1u << IRQ_BUSERR))
        test_fail(0x21);
    if (target[0] != 0xdeadbeefu || target[1] != 0x55667788u)
        test_fail(0x22);

    irq_setmask(~0u);
    uart_puts("buserr PASS\n");
    test_pass();
}
