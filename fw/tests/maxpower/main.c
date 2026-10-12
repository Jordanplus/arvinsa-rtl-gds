/*
 * fw/tests/maxpower - max-power pattern for the IR current (Phase 7 exploration, skill signoff-criteria
 * "IR 用多大的電流"). Two busy loops, each marked on GPIO_OUT so a simulation can record only that window:
 *   0x5A  A: loads and stores to SRAM every few cycles, every data bit inverted on each pass
 *         (0x55555555 <-> 0xAAAAAAAA), ALU ops on the loaded values; 32-bit instructions only
 *   0x5B  B: the same plus a MUL in each block (the sequential multiplier runs most of the time)
 *   0x5C  C: register-only ALU ops, one 32-bit instruction fetched every cycle, operands inverted each time
 *   0xA5  end of the windows
 * Then prints "maxpower PASS" and passes with the UART CRC as signature.
 */
#include "fwlib.h"

#define GPIO_OUT_REG REG32(SOC_GPIO_BASE + SOC_GPIO_OUT_OFF)
#define PASSES_A 14   /* about 5k cycles (RTL: 300 passes took 113k) */
#define PASSES_B 15   /* about 5k cycles (75 passes took 25k) */
#define PASSES_C 32    /* about 5k cycles (100 passes took 15.6k: about 3 cycles per instruction, fetch from SRAM) */

static volatile uint32_t buf[32];

#define BLOCK(off) \
    "lw   %[a], " #off "(%[p])\n\t" \
    "lw   %[b], " #off "+4(%[p])\n\t" \
    "xor  %[a], %[a], %[m]\n\t" \
    "xor  %[b], %[b], %[m]\n\t" \
    "sw   %[a], " #off "(%[p])\n\t" \
    "sw   %[b], " #off "+4(%[p])\n\t" \
    "add  %[c], %[a], %[b]\n\t" \
    "sub  %[d], %[a], %[b]\n\t" \
    "sll  %[c], %[c], %[s]\n\t" \
    "srl  %[d], %[d], %[s]\n\t" \
    "xor  %[acc], %[acc], %[c]\n\t" \
    "xor  %[acc], %[acc], %[d]\n\t"

static uint32_t loop_a(void)
{
    uint32_t a, b, c, d, acc = 0, n = PASSES_A;
    __asm__ volatile (
        ".option push\n\t.option norvc\n"
        "1:\n\t"
        BLOCK(0) BLOCK(8) BLOCK(16) BLOCK(24) BLOCK(32) BLOCK(40) BLOCK(48) BLOCK(56)
        "addi %[n], %[n], -1\n\t"
        "bnez %[n], 1b\n\t"
        ".option pop\n"
        : [a] "=&r"(a), [b] "=&r"(b), [c] "=&r"(c), [d] "=&r"(d), [acc] "+r"(acc), [n] "+r"(n)
        : [p] "r"(buf), [m] "r"(0xFFFFFFFFu), [s] "r"(1u)
        : "memory");
    return acc;
}

static uint32_t loop_b(void)
{
    uint32_t a, b, c, d, acc = 0, n = PASSES_B;
    __asm__ volatile (
        ".option push\n\t.option norvc\n"
        "1:\n\t"
        BLOCK(0)  "mul %[c], %[a], %[b]\n\t" "xor %[acc], %[acc], %[c]\n\t"
        BLOCK(8)  "mul %[c], %[a], %[b]\n\t" "xor %[acc], %[acc], %[c]\n\t"
        BLOCK(16) "mul %[c], %[a], %[b]\n\t" "xor %[acc], %[acc], %[c]\n\t"
        BLOCK(24) "mul %[c], %[a], %[b]\n\t" "xor %[acc], %[acc], %[c]\n\t"
        "addi %[n], %[n], -1\n\t"
        "bnez %[n], 1b\n\t"
        ".option pop\n"
        : [a] "=&r"(a), [b] "=&r"(b), [c] "=&r"(c), [d] "=&r"(d), [acc] "+r"(acc), [n] "+r"(n)
        : [p] "r"(buf), [m] "r"(0xFFFFFFFFu), [s] "r"(1u)
        : "memory");
    return acc;
}

#define ALU8 \
    "xor  %[a], %[a], %[m]\n\t" "xor  %[b], %[b], %[m]\n\t" \
    "add  %[c], %[a], %[b]\n\t" "sub  %[d], %[a], %[b]\n\t" \
    "sll  %[c], %[c], %[s]\n\t" "srl  %[d], %[d], %[s]\n\t" \
    "xor  %[acc], %[acc], %[c]\n\t" "or   %[acc], %[acc], %[d]\n\t"

static uint32_t loop_c(void)
{
    uint32_t a = 0x55555555u, b = 0xAAAAAAAAu, c, d, acc = 0, n = PASSES_C;
    __asm__ volatile (
        ".option push\n\t.option norvc\n"
        "1:\n\t"
        ALU8 ALU8 ALU8 ALU8 ALU8 ALU8
        "addi %[n], %[n], -1\n\t"
        "bnez %[n], 1b\n\t"
        ".option pop\n"
        : [a] "+r"(a), [b] "+r"(b), [c] "=&r"(c), [d] "=&r"(d), [acc] "+r"(acc), [n] "+r"(n)
        : [m] "r"(0xFFFFFFFFu), [s] "r"(1u));
    return acc;
}

int main(void)
{
    uart_init();
    for (unsigned i = 0; i < 32; i++)
        buf[i] = (i & 1) ? 0xAAAAAAAAu : 0x55555555u;
    GPIO_OUT_REG = 0x5A;
    uint32_t x = loop_a();
    GPIO_OUT_REG = 0x5B;
    x ^= loop_b();
    GPIO_OUT_REG = 0x5C;
    x ^= loop_c();
    GPIO_OUT_REG = 0xA5;
    (void)x;
    uart_puts("maxpower PASS\n");
    test_pass();
}
