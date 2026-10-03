/*
 * fw/common/fwlib.c - SoC firmware library (docs/spec/soc_spec.md §6.3).
 * Built with -ffunction-sections and linked with --gc-sections, so each test
 * only carries the functions it uses.
 */
#include "fwlib.h"

/* zlib.crc32() (IEEE 802.3, reflected, poly 0xEDB88320) of every byte sent. */
static uint32_t crc_sent;

void uart_init(void)
{
    UART_DIV_REG = SOC_UART_DIV;
}

void uart_putc(char c)
{
    uint32_t crc = ~crc_sent ^ (uint8_t)c;
    for (int i = 0; i < 8; i++)
        crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    crc_sent = ~crc;
    UART_DATA_REG = (uint8_t)c;   /* the bus stalls while the transmitter is busy */
}

void uart_puts(const char *s)
{
    while (*s)
        uart_putc(*s++);
}

int uart_getc(void)
{
    uint32_t v;
    do {
        v = UART_DATA_REG;
    } while (v == SOC_UART_RX_EMPTY);
    return (int)(v & 0xFFu);
}

void uart_puthex(uint32_t v)
{
    for (int sh = 28; sh >= 0; sh -= 4) {
        uint32_t d = (v >> sh) & 0xFu;
        uart_putc((char)(d < 10 ? '0' + d : 'A' + d - 10));
    }
}

uint32_t uart_crc32(void)
{
    return crc_sent;
}

void test_pass(void)
{
    TEST_SIG_REG = crc_sent;
    TEST_DONE_REG = SOC_TEST_PASS_MAGIC;
    for (;;)
        ;
}

void test_fail(uint32_t code)
{
    TEST_DONE_REG = SOC_TEST_FAIL_BASE | (code & 0xFFFFu);
    for (;;)
        ;
}
