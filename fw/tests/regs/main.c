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
 *   Cross-talk (Phase 1 qualification review M4: a write to one register must
 *              not change another, e.g. a partial offset decode inside
 *              TEST_CTRL). Runs after the checks above passed. Every register
 *              X of { GPIO_OUT, GPIO_IN (read-only: the write is ignored),
 *              SIG, IRQ_TRIG, UART DIV } is written twice with a value no other
 *              register holds, and after every write all seven registers
 *              (those five, UART DATA, DONE) are read and compared with their
 *              expected values. After "regs PASS\n" is sent, all seven are read
 *              once more (UART DATA writes must not change any of them).
 *              The first difference ends the test.
 *   DONE       after DONE = PASS magic, DONE must read back the PASS magic.
 *
 * Fail codes: 0x0200 | mask with mask bit 0 GPIO_OUT, 1 GPIO_IN, 2 SIG,
 * 3 IRQ_TRIG, 4 UART DIV, 5 UART DATA. 0x0300 | (w << 4) | r: cross-talk,
 * writing register w changed register r, with the index order GPIO_OUT 0,
 * GPIO_IN 1, SIG 2, IRQ_TRIG 3, UART DIV 4, UART DATA 5, DONE 6 (w = 5: the
 * check after the UART text; w = 15: the check before the first write).
 * 0x0240: DONE did not read back the PASS magic; this is a second DONE write,
 * which the test_ctrl checker also reports as "DONE written 2 times".
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
#define FAIL_XTALK_BASE 0x0300u

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

/* ---- cross-talk check ---- */
enum { X_GPIO_OUT, X_GPIO_IN, X_SIG, X_IRQ, X_DIV, X_DATA, X_DONE, X_N };

static const uint32_t xaddr[X_N] = {
    SOC_GPIO_BASE + SOC_GPIO_OUT_OFF, SOC_GPIO_BASE + SOC_GPIO_IN_OFF,
    SOC_TEST_BASE + SOC_TEST_SIG_OFF, SOC_TEST_BASE + SOC_TEST_IRQ_OFF,
    SOC_UART_BASE + SOC_UART_DIV_OFF, SOC_UART_BASE + SOC_UART_DATA_OFF,
    SOC_TEST_BASE + SOC_TEST_DONE_OFF,
};

/* Values written in the cross-talk check, two rounds; no value appears in two
 * registers. IRQ_TRIG bit 0 toggles, the IRQ stays masked (start.S). */
#define X_WRITTEN 5
static const uint32_t xval[2][X_WRITTEN] = {
    {0xFFFFFF3Cu, 0xFFFFFFFFu, 0x5160A001u, 0x12900003u, 0x0D100005u},
    {0x000000C3u, 0x00000000u, 0xAE9F5FFEu, 0xED6FFFFCu, 0xF2EFFFFAu},
};

/* Expected read value of every register. */
static uint32_t xexp[X_N];

static void xcheck(uint32_t w)
{
    for (uint32_t r = 0; r < X_N; r++)
        if (REG32(xaddr[r]) != xexp[r])
            test_fail(FAIL_XTALK_BASE | (w << 4) | r);
}

static void xwrite(uint32_t w, uint32_t v)
{
    REG32(xaddr[w]) = v;
    if (w == X_GPIO_OUT)
        xexp[w] = v & 0xFFu;            /* 8 valid bits */
    else if (w != X_GPIO_IN)            /* read-only: the write is ignored */
        xexp[w] = v;
    xcheck(w);
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

    /* Cross-talk. State here: GPIO_OUT 0xB3, SIG 0, IRQ_TRIG 0, DIV 18
     * (uart_init), DONE never written (0), no UART input. */
    xexp[X_GPIO_OUT] = SOC_GPIO_BOOT_BASE | REGS_BOOT_MODE;
    xexp[X_GPIO_IN]  = REGS_BOOT_MODE;
    xexp[X_SIG]      = 0;
    xexp[X_IRQ]      = 0;
    xexp[X_DIV]      = SOC_UART_DIV;
    xexp[X_DATA]     = SOC_UART_RX_EMPTY;
    xexp[X_DONE]     = 0;
    xcheck(0xF);
    for (unsigned k = 0; k < 2; k++)
        for (uint32_t w = 0; w < X_WRITTEN; w++)
            xwrite(w, xval[k][w]);
    /* Restore before any UART output: GPIO_OUT 0xB3, SIG/IRQ_TRIG 0, DIV 18. */
    xwrite(X_GPIO_OUT, SOC_GPIO_BOOT_BASE | REGS_BOOT_MODE);
    xwrite(X_SIG, 0);
    xwrite(X_IRQ, 0);
    uart_init();
    xexp[X_DIV] = SOC_UART_DIV;

    uart_puts("regs PASS\n");
    xcheck(X_DATA);
    /* test_pass() plus a DONE read-back (DONE: "R = last value written"). */
    TEST_SIG_REG = uart_crc32();
    TEST_DONE_REG = SOC_TEST_PASS_MAGIC;
    if (TEST_DONE_REG != SOC_TEST_PASS_MAGIC)
        test_fail(FAIL_DONE_RB);
    for (;;)
        ;
}
