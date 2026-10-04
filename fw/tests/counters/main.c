/*
 * fw/tests/counters - the 64-bit cycle and retired-instruction counters of PicoRV32
 * (rdcycle/rdcycleh, rdinstret/rdinstreth; ENABLE_COUNTERS64 is on by default).
 *
 * Why (docs/phase_exit/phase2.md known limitation 7, phase3.md known limitation 11): no other
 * test reads the upper halves, so a netlist with count_cycle[45] or count_instr[40] stuck at 1
 * passed every gate-level simulation. Synthesis is not covered by formal equivalence (EQY proves
 * the synthesized netlist against the final one only), so gate-level simulation is the check.
 *
 * Checks (the test runs far fewer than 2^32 cycles, so both upper halves must be 0: a bit of
 * 63:32 stuck at 1 is caught, a bit stuck at 0 is not, that would need 2^32 cycles):
 *   cycleh and instreth read 0, before and after a loop of COUNT_LOOPS iterations;
 *   cycle and instret increase over the loop, instret by at least COUNT_LOOPS (each iteration
 *   retires at least one instruction), and instret never exceeds cycle (PicoRV32 needs at least
 *   3 cycles per instruction).
 *
 * Fail codes: 0x10 cycleh != 0, 0x20 instreth != 0, 0x30 cycle did not increase,
 *             0x40 instret increased by less than COUNT_LOOPS, 0x50 instret > cycle.
 */
#include "fwlib.h"

#define COUNT_LOOPS 100u

#define CSR_READ(name) ({ uint32_t v_; __asm__ volatile ("rd" #name " %0" : "=r"(v_)); v_; })

static void check_high(void)
{
    if (CSR_READ(cycleh) != 0)
        test_fail(0x10);
    if (CSR_READ(instreth) != 0)
        test_fail(0x20);
}

int main(void)
{
    uint32_t c0, i0, c1, i1;

    uart_init();
    check_high();
    i0 = CSR_READ(instret);
    c0 = CSR_READ(cycle);
    for (unsigned i = 0; i < COUNT_LOOPS; i++)
        __asm__ volatile ("" ::: "memory");
    c1 = CSR_READ(cycle);
    i1 = CSR_READ(instret);
    check_high();
    if (c1 <= c0)
        test_fail(0x30);
    if (i1 - i0 < COUNT_LOOPS)
        test_fail(0x40);
    if (i1 > c1)
        test_fail(0x50);
    uart_puts("counters PASS\n");
    test_pass();
}
