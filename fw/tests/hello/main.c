/* fw/tests/hello - print "hello\n" and PASS (docs/spec/soc_spec.md §6.4). */
#include "fwlib.h"

int main(void)
{
    uart_init();
    uart_puts("hello\n");
    test_pass();
}
