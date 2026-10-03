/*
 * fw/tests/neg_fw_hang - negative test only (spec §5 R06a, §6.4): print, then spin
 * forever without ever writing DONE. The timeout checker must FAIL this test.
 */
#include "fwlib.h"

int main(void)
{
    uart_init();
    uart_puts("hang\n");
    for (;;)
        ;
}
