/*
 * fw/tests/uart_burst - UART DATA write stall (docs/spec/soc_spec.md §4.2:
 * no mem_ready while simpleuart reg_dat_wait = 1). Directed test from the
 * Phase 1 testbench qualification review (M1).
 *
 * uart_putc() computes the CRC before each byte, which takes longer than one
 * UART frame (10 bits x 20 cycles), so no other test ever writes DATA while
 * the transmitter is busy. Here the whole line is written back to back
 * (uart_puts_burst): the first write lands in the idle period simpleuart
 * inserts after the DIV write, every later one while the previous byte is
 * still being sent, so the bus must hold every write until the transmitter
 * takes it. A bus that ignores the stall drops bytes; the testbench sees it
 * as a wrong UART text (uart_golden, signature) and as too few stalled writes
 * (coverage, tests.toml min_uart_stalls). No fail code: the firmware cannot
 * see the TX line itself.
 */
#include "fwlib.h"

static const char burst_line[] =
    "uart_burst 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz PASS\n";

int main(void)
{
    uart_init();
    uart_puts_burst(burst_line);
    test_pass();
}
