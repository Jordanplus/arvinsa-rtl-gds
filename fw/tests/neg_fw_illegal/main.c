/*
 * fw/tests/neg_fw_illegal - negative test only (spec §5 R06b, §6.4): print, then
 * execute an illegal instruction. irq[1] stays masked (start.S), so PicoRV32 with
 * CATCH_ILLINSN=1 must assert trap. Should execution continue anyway, DONE gets
 * FAIL code 0x01 so the run can never be mistaken for a PASS.
 */
#include "fwlib.h"

#define FAIL_NO_TRAP 0x01

int main(void)
{
    uart_init();
    uart_puts("illegal\n");
    __asm__ volatile ("unimp" ::: "memory");   /* all-zero halfword: defined illegal */
    test_fail(FAIL_NO_TRAP);
}
