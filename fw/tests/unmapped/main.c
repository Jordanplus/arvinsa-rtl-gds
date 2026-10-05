/*
 * fw/tests/unmapped - unmapped accesses and full address decode
 * (docs/spec/soc_spec.md §2, §4.2): every address outside the five windows
 * must answer (mem_ready) with read data 0, and a write there must change
 * nothing.
 *
 * For each hole address: read (must be 0), write 0xFFFFFFFF; after all holes
 * are written, read every hole again (must still be 0). The holes sit just
 * above and just below every window and at the addresses a partial decode
 * would alias onto a register (e.g. UART + 0x10 = DIV, TEST_CTRL + 0x14 =
 * DONE). Four more holes alias the SRAM word `canary` if the SRAM decode were
 * partial. Afterwards the registers a stray write could reach must be
 * unchanged: canary, SIG (0), IRQ_TRIG (0), GPIO_OUT (0xB0), UART DIV (18);
 * a write that reached UART DATA, GPIO_OUT or DONE also shows up in the
 * uart_golden, gpio_seq or test_ctrl checker.
 *
 * dv/tests.toml declares this test with expect_unmapped (the exact number of
 * unmapped bus accesses below), which turns the bus_assert "unmapped access"
 * rule into a count check for this test only; bus_assert still checks the
 * decode, the read data (0) and the 1000-cycle response limit.
 * Accesses: 3 per hole (read, write, read again).
 *
 * Fail codes: 0x0100 | i  hole i read non-zero before the writes
 *             0x0180 | i  hole i read non-zero after the writes
 *             0x01 canary changed, 0x02 SIG, 0x03 IRQ_TRIG, 0x04 GPIO_OUT,
 *             0x05 UART DIV changed.
 */
#include "fwlib.h"

#define GPIO_OUT_REG  REG32(SOC_GPIO_BASE + SOC_GPIO_OUT_OFF)
#define CANARY        0x12345678u

#define N_FIXED   (sizeof fixed_holes / sizeof fixed_holes[0])
#define N_SRAM    4
#define N_HOLES   (N_FIXED + N_SRAM)

static const uint32_t fixed_holes[] = {
    /* Boot ROM 0x0001_0000, 512 B */
    0x0000FFFCu, 0x00010200u, 0x00010400u, 0x00030000u,
    /* UART 0x0200_0000, 8 B */
    0x01FFFFFCu, 0x02000008u, 0x0200000Cu, 0x02000010u, 0x02000014u, 0x02001000u,
    /* GPIO 0x0300_0000, 8 B */
    0x02FFFFFCu, 0x03000008u, 0x0300000Cu, 0x03000010u, 0x03000014u, 0x03001000u,
#ifdef SOC_CPU_HAZARD3
    /* TEST_CTRL 0x0400_0000, 16 B (FATAL at 0x0C, ADR-0011); 0x1C aliases FATAL */
    0x03FFFFFCu, 0x0400001Cu, 0x04000010u, 0x04000014u, 0x04000018u, 0x04001000u,
#else
    /* TEST_CTRL 0x0400_0000, 12 B */
    0x03FFFFFCu, 0x0400000Cu, 0x04000010u, 0x04000014u, 0x04000018u, 0x04001000u,
#endif
    /* nothing mapped */
    0x05000000u, 0x80000000u, 0xFFFFFFFCu,
};

/* SRAM aliases of the canary word: + window size, + 4 KB, + 128 KB, bit 31. */
static const uint32_t sram_alias_off[N_SRAM] = {
    SOC_SRAM_SIZE, 0x00001000u, 0x00020000u, 0x80000000u,
};

static volatile uint32_t canary;

static uint32_t hole(unsigned i)
{
    if (i < N_FIXED)
        return fixed_holes[i];
    return sram_alias_off[i - N_FIXED] + (uint32_t)(uintptr_t)&canary;
}

int main(void)
{
    uart_init();
    canary = CANARY;

    for (unsigned i = 0; i < N_HOLES; i++) {
        volatile uint32_t *p = (volatile uint32_t *)(uintptr_t)hole(i);
        if (*p != 0)
            test_fail(0x0100u | i);
        *p = 0xFFFFFFFFu;
    }
    for (unsigned i = 0; i < N_HOLES; i++) {
        volatile uint32_t *p = (volatile uint32_t *)(uintptr_t)hole(i);
        if (*p != 0)
            test_fail(0x0180u | i);
    }

    if (canary != CANARY)
        test_fail(0x01);
    if (TEST_SIG_REG != 0)
        test_fail(0x02);
    if (TEST_IRQ_REG != 0)
        test_fail(0x03);
    if (GPIO_OUT_REG != (SOC_GPIO_BOOT_BASE | SOC_BOOT_JUMP))
        test_fail(0x04);
    if (UART_DIV_REG != SOC_UART_DIV)
        test_fail(0x05);

    uart_puts("unmapped PASS\n");
    test_pass();
}
