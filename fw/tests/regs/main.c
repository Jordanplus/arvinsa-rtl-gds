/*
 * fw/tests/regs - peripheral register read-back and GPIO pin check
 * (docs/spec/soc_spec.md §2, §4.5, §4.7, §4.8, §6.5 step 2). Runs with
 * boot_mode = 3 (SOC_BOOT_RESERVED): the boot ROM writes GPIO_OUT = 0xB3 and
 * jumps to SRAM, so this test also covers the reserved boot mode and both
 * boot_mode pins.
 *
 * Checks (every register is checked before any fail code is reported, so one
 * run names every failing register):
 *   GPIO_OUT   reads back 0xB0 | boot_mode (written by the boot ROM), then
 *              0x01, 0x02, ..., 0x80 (walking ones), 0xFF, 0x00 and 0xB3, each
 *              written with ones in bits 31:8 and read back (low 8 bits valid,
 *              spec §2). dv/tests.toml expect_gpio lists the same sequence, so
 *              the gpio_seq checker sees every pin go to 1 and to 0.
 *   GPIO_IN    reads {30'b0, boot_mode} = 3.
 *   SIG, IRQ_TRIG, UART DIV (32-bit RW): walking ones over bits 0..31, then
 *              0xFFFFFFFF, 0xA5A5A5A5, 0x5A5A5A5A and 0, each read back.
 *              IRQ_TRIG bit 0 drives irq[SOC_IRQ_TEST], which stays masked
 *              (start.S). Nothing is sent on the UART before uart_init()
 *              restores DIV = SOC_UART_DIV, so no frame uses a test divider.
 *   UART DATA  reads SOC_UART_RX_EMPTY (the testbench sends nothing).
 *   DONE       after DONE = PASS magic, DONE must read back the PASS magic.
 *
 * Fail codes: 0x0200 | mask with mask bit 0 GPIO_OUT, 1 GPIO_IN, 2 SIG,
 * 3 IRQ_TRIG, 4 UART DIV, 5 UART DATA. 0x0240: DONE did not read back the
 * PASS magic; this is a second DONE write, which the test_ctrl checker also
 * reports as "DONE written 2 times".
 */
#include "fwlib.h"

#define REGS_BOOT_MODE  SOC_BOOT_RESERVED

#define GPIO_OUT_REG    REG32(SOC_GPIO_BASE + SOC_GPIO_OUT_OFF)
#define GPIO_IN_REG     REG32(SOC_GPIO_BASE + SOC_GPIO_IN_OFF)

#define BAD_GPIO_OUT    (1u << 0)
#define BAD_GPIO_IN     (1u << 1)
#define BAD_SIG         (1u << 2)
#define BAD_IRQ_TRIG    (1u << 3)
#define BAD_UART_DIV    (1u << 4)
#define BAD_UART_DATA   (1u << 5)
#define FAIL_REG_BASE   0x0200u
#define FAIL_DONE_RB    0x0240u

/* GPIO_OUT values in write order; the boot ROM value comes first. */
static const uint8_t gpio_seq[] = {
    0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0xFF, 0x00,
    SOC_GPIO_BOOT_BASE | REGS_BOOT_MODE,
};

static const uint32_t rw_pats[] = {0xFFFFFFFFu, 0xA5A5A5A5u, 0x5A5A5A5Au, 0x00000000u};

/* 32-bit read/write check; returns 1 on any mismatch. Ends with the register at 0. */
static uint32_t rw32_bad(volatile uint32_t *r)
{
    uint32_t bad = 0;
    for (int b = 0; b < 32; b++) {
        *r = 1u << b;
        if (*r != (1u << b))
            bad = 1;
    }
    for (unsigned i = 0; i < sizeof rw_pats / sizeof rw_pats[0]; i++) {
        *r = rw_pats[i];
        if (*r != rw_pats[i])
            bad = 1;
    }
    return bad;
}

int main(void)
{
    uint32_t mask = 0;

    uart_init();

    if ((GPIO_OUT_REG & 0xFFu) != (SOC_GPIO_BOOT_BASE | REGS_BOOT_MODE))
        mask |= BAD_GPIO_OUT;
    for (unsigned i = 0; i < sizeof gpio_seq; i++) {
        GPIO_OUT_REG = 0xFFFFFF00u | gpio_seq[i];
        if ((GPIO_OUT_REG & 0xFFu) != gpio_seq[i])
            mask |= BAD_GPIO_OUT;
    }
    if (GPIO_IN_REG != REGS_BOOT_MODE)
        mask |= BAD_GPIO_IN;

    if (rw32_bad(&TEST_SIG_REG))
        mask |= BAD_SIG;
    if (rw32_bad(&TEST_IRQ_REG))
        mask |= BAD_IRQ_TRIG;
    if (rw32_bad(&UART_DIV_REG))
        mask |= BAD_UART_DIV;
    uart_init();
    if (UART_DIV_REG != SOC_UART_DIV)
        mask |= BAD_UART_DIV;
    if (UART_DATA_REG != SOC_UART_RX_EMPTY)
        mask |= BAD_UART_DATA;

    if (mask)
        test_fail(FAIL_REG_BASE | mask);

    uart_puts("regs PASS\n");
    /* test_pass() plus a DONE read-back (DONE: "R = last value written"). */
    TEST_SIG_REG = uart_crc32();
    TEST_DONE_REG = SOC_TEST_PASS_MAGIC;
    if (TEST_DONE_REG != SOC_TEST_PASS_MAGIC)
        test_fail(FAIL_DONE_RB);
    for (;;)
        ;
}
