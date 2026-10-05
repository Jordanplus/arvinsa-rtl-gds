/*
 * fw/tests/exc - the exception path of Hazard3 (Phase 5, ADR-0011; the Hazard3 counterpart of
 * buserr, which tests the PicoRV32 bus-error IRQ).
 *
 * Why: like buserr for PicoRV32, no other test takes an exception, so a netlist with the trap
 * logic broken (mcause, mtval or mepc wrong, or the entry never taken) would pass every other
 * gate-level simulation. Hazard3 does not put a misaligned access on the bus: it raises an
 * exception before the bus (skill core-migration-hazard3 rule 7). start_hazard3.S records the
 * exception and skips the instruction while exc_resume != 0.
 * Checks, for each of: a misaligned lw, a misaligned sw, ecall, ebreak (32-bit) and an illegal
 * instruction (compressed, all-zero halfword):
 *   exactly one more exception, with the RISC-V cause code; mtval reads 0 (Hazard3 hardwires
 *   it to 0, doc/sections/csr.adoc 257-261, so a bit stuck at 1 shows); the lw left its
 *   destination register unchanged; the sw changed no memory.
 *
 * Fail codes: 0x1n count, 0x2n cause, 0x3n mtval, 0x40 lw destination written, 0x41 sw wrote
 *             memory (n = 0 lw, 1 sw, 2 ecall, 3 ebreak, 4 illegal).
 */
#include "fwlib.h"

#ifndef SOC_CPU_HAZARD3
#error "fw/tests/exc is for the Hazard3 build (make -C fw CPU=hazard3)"
#endif

#define CAUSE_LOAD_MISALIGNED   4u
#define CAUSE_STORE_MISALIGNED  6u
#define CAUSE_ECALL_M          11u
#define CAUSE_BREAKPOINT        3u
#define CAUSE_ILLEGAL           2u

static volatile uint32_t target[2] = { 0x11223344u, 0x55667788u };

static void expect(unsigned n, uint32_t count, uint32_t cause)
{
    if (exc_count != count)
        test_fail(0x10 + n);
    if (exc_cause != cause)
        test_fail(0x20 + n);
}

int main(void)
{
    uint32_t v = 0xcafef00du;
    uintptr_t a;

    uart_init();
    exc_resume = 1;

    a = (uintptr_t)&target[0] + 2;
    __asm__ volatile ("lw %0, 0(%1)" : "+r"(v) : "r"(a) : "memory");
    expect(0, 1, CAUSE_LOAD_MISALIGNED);
    if (exc_tval != 0)
        test_fail(0x30);
    if (v != 0xcafef00du)
        test_fail(0x40);

    a = (uintptr_t)&target[0] + 1;
    __asm__ volatile ("sw %0, 0(%1)" : : "r"(0xdeadbeefu), "r"(a) : "memory");
    expect(1, 2, CAUSE_STORE_MISALIGNED);
    if (exc_tval != 0)
        test_fail(0x31);
    if (target[0] != 0x11223344u || target[1] != 0x55667788u)
        test_fail(0x41);

    __asm__ volatile ("ecall" ::: "memory");
    expect(2, 3, CAUSE_ECALL_M);
    __asm__ volatile (".option push\n.option norvc\nebreak\n.option pop" ::: "memory");
    expect(3, 4, CAUSE_BREAKPOINT);
    __asm__ volatile ("unimp" ::: "memory");
    expect(4, 5, CAUSE_ILLEGAL);

    exc_resume = 0;
    uart_puts("exc PASS\n");
    test_pass();
}
