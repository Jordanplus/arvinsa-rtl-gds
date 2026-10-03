/*
 * fw/tests/reset_store - SRAM store at the reset edge (docs/spec/soc_spec.md
 * §4.9, RTL-RST-01): the store the CPU presents at the rising edge that
 * samples resetn = 0 must be dropped. Directed test from the Phase 1 testbench
 * qualification review (m6); needs dv/tests.toml reset_on_store = "rst_victim".
 *
 * The testbench (+reset_on_store=<address of rst_victim>) drives resetn = 0 at
 * the falling edge where the CPU first presents a store to rst_victim, holds
 * it for 16 cycles and releases it; the CPU then boots again from the boot ROM.
 * Both variables are in .data, which the backdoor load initializes once and
 * which start.S does not clear, so the second boot sees what the first left.
 *
 *   first boot  (rst_stage = STAGE_FIRST):  rst_stage = STAGE_SECOND, then the
 *               store rst_victim = VICTIM_NEW, at which the reset hits.
 *   second boot (rst_stage = STAGE_SECOND): rst_victim must still hold
 *               VICTIM_OLD, then print and PASS.
 *
 * Fail codes: 0x01 no reset came after the victim store (the testbench did not
 *             apply it), 0x02 rst_stage holds neither value, 0x03 the store at
 *             the reset edge was written (rst_victim = VICTIM_NEW).
 * Nothing is sent on the UART before the reset, so no frame is cut by it.
 * FWBUG_RESET_STORE_NO_VICTIM exists only for the negative-test variant
 * reset_store__no_victim (fw/README.md): the first boot stores to another
 * variable, so the testbench never applies the reset.
 */
#include "fwlib.h"

#define STAGE_FIRST   0x51A6E001u
#define STAGE_SECOND  0x51A6E002u
#define VICTIM_OLD    0x0DDC0FFEu
#define VICTIM_NEW    0xDEADBEEFu

#define FAIL_NO_RESET 0x01
#define FAIL_STAGE    0x02
#define FAIL_WRITTEN  0x03

volatile uint32_t rst_stage  = STAGE_FIRST;
volatile uint32_t rst_victim = VICTIM_OLD;
#ifdef FWBUG_RESET_STORE_NO_VICTIM
volatile uint32_t rst_other = VICTIM_OLD;
#define rst_victim_store rst_other
#else
#define rst_victim_store rst_victim
#endif

int main(void)
{
    uart_init();
    if (rst_stage == STAGE_FIRST) {
        rst_stage = STAGE_SECOND;
        rst_victim_store = VICTIM_NEW;  /* resetn = 0 is sampled with this store */
        test_fail(FAIL_NO_RESET);
    }
    if (rst_stage != STAGE_SECOND)
        test_fail(FAIL_STAGE);
    if (rst_victim != VICTIM_OLD)
        test_fail(FAIL_WRITTEN);
    uart_puts("reset_store PASS\n");
    test_pass();
}
