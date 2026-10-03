/*
 * fw/tests/memtest - SRAM test over the test area [_free_start, _stack_limit)
 * (docs/spec/soc_spec.md §6.2, §6.4). The image itself must end at or below the
 * SRAM half (_sram_half) so the test area covers the whole upper half.
 *
 * Phases (in order) and fail codes:
 *   0x01  _free_start > _sram_half (image too large)
 *   0x10  fixed patterns 0x00000000, 0xFFFFFFFF, 0xAAAAAAAA, 0x55555555
 *   0x20  address-in-address (each word holds its own byte address)
 *   0x30  march C-: up(w0) up(r0,w1) up(r1,w0) down(r0,w1) down(r1,w0) up(r0)
 *   0x40  byte lane: sb / sh into a known background, then every lane is checked
 *         with lw, lbu, lb, lhu and lh
 * Phases 0x10-0x30 use word accesses only, so a byte-lane fault (e.g. swapped
 * write-mask bits) first shows up as 0x40.
 *
 * Accesses per test-area word (dv/tests.toml sram_cov counts them, so a phase
 * that is skipped or shortened fails the coverage checker; keep both in sync):
 *   patterns 4 W + 4 R, address-in-address 1 W + 1 R, march C- 5 W + 5 R,
 *   byte lane 6 x (1 full W + 1 sb/sh W + 13 R: lw, 4 x lbu/lb, 2 x lhu/lh)
 *   = 22 writes (16 full, one each with strobe 1/2/4/8/3/C) and 88 reads.
 * FWBUG_MEMTEST_NO_MARCH exists only for the negative-test variant
 * memtest__no_march (fw/README.md); the regular build never defines it.
 */
#include "fwlib.h"

#define FAIL_LAYOUT  0x01
#define FAIL_PATTERN 0x10
#define FAIL_ADDR    0x20
#define FAIL_MARCH   0x30
#define FAIL_LANE    0x40

#define LANE_BG   0xC3A55A3Cu   /* distinct bytes, both signs */
#define LANE_B    0x96u         /* byte written by sb */
#define LANE_H    0x8E71u       /* halfword written by sh */

typedef volatile uint32_t vu32;

static vu32 *const area_lo = (vu32 *)_free_start;
static vu32 *const area_hi = (vu32 *)_stack_limit;

static void fill(uint32_t v)
{
    for (vu32 *p = area_lo; p < area_hi; p++)
        *p = v;
}

static void expect_all(uint32_t v, uint32_t code)
{
    for (vu32 *p = area_lo; p < area_hi; p++)
        if (*p != v)
            test_fail(code);
}

/* One march element: read-compare then write, ascending or descending. */
static void march_rw(int down, uint32_t rd, uint32_t wr)
{
    for (unsigned i = 0, n = (unsigned)(area_hi - area_lo); i < n; i++) {
        vu32 *p = down ? area_hi - 1 - i : area_lo + i;
        if (*p != rd)
            test_fail(FAIL_MARCH);
        *p = wr;
    }
}

/* Check one word through every load width and signedness. */
static void lane_check(vu32 *p, uint32_t exp)
{
    volatile uint8_t *bu = (volatile uint8_t *)p;
    volatile int8_t *bs = (volatile int8_t *)p;
    volatile uint16_t *hu = (volatile uint16_t *)p;
    volatile int16_t *hs = (volatile int16_t *)p;

    if (*p != exp)
        test_fail(FAIL_LANE);
    for (int k = 0; k < 4; k++) {
        uint32_t b = (exp >> (8 * k)) & 0xFFu;
        if (bu[k] != b || bs[k] != (int8_t)b)
            test_fail(FAIL_LANE);
    }
    for (int k = 0; k < 2; k++) {
        uint32_t h = (exp >> (16 * k)) & 0xFFFFu;
        if (hu[k] != h || hs[k] != (int16_t)h)
            test_fail(FAIL_LANE);
    }
}

static void byte_lane(void)
{
    for (vu32 *p = area_lo; p < area_hi; p++) {
        for (int k = 0; k < 4; k++) {
            *p = LANE_BG;
            ((volatile uint8_t *)p)[k] = (uint8_t)LANE_B;
            lane_check(p, (LANE_BG & ~(0xFFu << (8 * k))) | (LANE_B << (8 * k)));
        }
        for (int k = 0; k < 2; k++) {
            *p = LANE_BG;
            ((volatile uint16_t *)p)[k] = (uint16_t)LANE_H;
            lane_check(p, (LANE_BG & ~(0xFFFFu << (16 * k))) | (LANE_H << (16 * k)));
        }
    }
}

int main(void)
{
    static const uint32_t patterns[] = {0x00000000u, 0xFFFFFFFFu, 0xAAAAAAAAu, 0x55555555u};

    uart_init();
    if ((uintptr_t)_free_start > (uintptr_t)_sram_half)
        test_fail(FAIL_LAYOUT);

    for (unsigned i = 0; i < sizeof patterns / sizeof patterns[0]; i++) {
        fill(patterns[i]);
        expect_all(patterns[i], FAIL_PATTERN);
    }

    for (vu32 *p = area_lo; p < area_hi; p++)
        *p = (uint32_t)(uintptr_t)p;
    for (vu32 *p = area_lo; p < area_hi; p++)
        if (*p != (uint32_t)(uintptr_t)p)
            test_fail(FAIL_ADDR);

#ifndef FWBUG_MEMTEST_NO_MARCH
    fill(0);
    march_rw(0, 0, ~0u);
    march_rw(0, ~0u, 0);
    march_rw(1, 0, ~0u);
    march_rw(1, ~0u, 0);
    expect_all(0, FAIL_MARCH);
#else
    (void)march_rw;     /* bug variant (dv/bugs.toml M01): march C- phase removed */
#endif

    byte_lane();

    uart_puts("memtest PASS\n");
    test_pass();
}
