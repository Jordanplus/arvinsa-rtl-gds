/*
 * fw/tests/uart_echo - read one line from the UART (up to and including '\n'),
 * then send "echo:" + that line (docs/spec/soc_spec.md §6.4).
 *
 * The whole line is received before anything is sent: the UART receiver holds a
 * single byte, so transmitting (which stalls the bus) while bytes arrive could
 * overrun it.
 *
 * Received bytes are packed into 32-bit words and the buffer is written with
 * whole-word stores only. Stack words start uninitialized (X in the SRAM model);
 * a byte store followed by a load of a word that still holds never-written bytes
 * would put X on mem_rdata at the read handshake (x_check).
 *
 * Fail codes: 0x01 line longer than LINE_MAX bytes.
 */
#include "fwlib.h"

#define LINE_MAX      64
#define FAIL_OVERFLOW 0x01

int main(void)
{
    uint32_t line[LINE_MAX / 4];
    uint32_t acc = 0;
    unsigned n = 0;
    int c;

    uart_init();
    do {
        c = uart_getc();
        if (n >= LINE_MAX)
            test_fail(FAIL_OVERFLOW);
        acc |= (uint32_t)c << (8 * (n % 4));
        n++;
        if (n % 4 == 0 || c == '\n') {
            line[(n - 1) / 4] = acc;
            acc = 0;
        }
    } while (c != '\n');

    uart_puts("echo:");
    for (unsigned i = 0; i < n; i++)
        uart_putc((char)(line[i / 4] >> (8 * (i % 4))));
    test_pass();
}
