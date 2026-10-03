/*
 * fw/tests/muldiv - RV32M instruction check against constant results
 * (docs/spec/soc_spec.md §6.4), including divide-by-zero and signed overflow.
 *
 * Expected values follow the RISC-V ISA manual (M extension): x/0 = all ones
 * (div, divu), x%0 = x (rem, remu); -2^31 / -1 = -2^31 and -2^31 % -1 = 0.
 * Every instruction is issued through inline asm so the compiler cannot fold it.
 *
 * Fail code: 0x100 | (case_index << 3) | op_index, op_index in the order
 * mul, mulh, mulhsu, mulhu, div, divu, rem, remu.
 */
#include "fwlib.h"

#define FAIL_BASE 0x100u

enum { OP_MUL, OP_MULH, OP_MULHSU, OP_MULHU, OP_DIV, OP_DIVU, OP_REM, OP_REMU, OP_COUNT };

typedef struct {
    uint32_t a, b;
    uint32_t r[OP_COUNT];
} md_case_t;

static const md_case_t cases[] = {
    {0x00000007u, 0x00000003u, {0x00000015u, 0x00000000u, 0x00000000u, 0x00000000u, 0x00000002u, 0x00000002u, 0x00000001u, 0x00000001u}},  /* small positive */
    {0xFFFFFFF9u, 0x00000003u, {0xFFFFFFEBu, 0xFFFFFFFFu, 0xFFFFFFFFu, 0x00000002u, 0xFFFFFFFEu, 0x55555553u, 0xFFFFFFFFu, 0x00000000u}},  /* negative / positive (truncate toward zero) */
    {0x00000007u, 0xFFFFFFFDu, {0xFFFFFFEBu, 0xFFFFFFFFu, 0x00000006u, 0x00000006u, 0xFFFFFFFEu, 0x00000000u, 0x00000001u, 0x00000007u}},  /* positive / negative */
    {0xFFFFFFF9u, 0xFFFFFFFDu, {0x00000015u, 0x00000000u, 0xFFFFFFF9u, 0xFFFFFFF6u, 0x00000002u, 0x00000000u, 0xFFFFFFFFu, 0xFFFFFFF9u}},  /* negative / negative */
    {0x80000000u, 0xFFFFFFFFu, {0x80000000u, 0x00000000u, 0x80000000u, 0x7FFFFFFFu, 0x80000000u, 0x00000000u, 0x00000000u, 0x80000000u}},  /* signed overflow: -2^31 / -1 */
    {0x12345678u, 0x00000000u, {0x00000000u, 0x00000000u, 0x00000000u, 0x00000000u, 0xFFFFFFFFu, 0xFFFFFFFFu, 0x12345678u, 0x12345678u}},  /* divide by zero */
    {0x87654321u, 0x00000000u, {0x00000000u, 0x00000000u, 0x00000000u, 0x00000000u, 0xFFFFFFFFu, 0xFFFFFFFFu, 0x87654321u, 0x87654321u}},  /* divide by zero, negative dividend */
    {0x00000000u, 0x00000000u, {0x00000000u, 0x00000000u, 0x00000000u, 0x00000000u, 0xFFFFFFFFu, 0xFFFFFFFFu, 0x00000000u, 0x00000000u}},  /* zero / zero */
    {0xFFFFFFFFu, 0xFFFFFFFFu, {0x00000001u, 0x00000000u, 0xFFFFFFFFu, 0xFFFFFFFEu, 0x00000001u, 0x00000001u, 0x00000000u, 0x00000000u}},  /* all ones */
    {0x12345678u, 0x9ABCDEF0u, {0x242D2080u, 0xF8CC93D6u, 0x0B00EA4Eu, 0x0B00EA4Eu, 0x00000000u, 0x00000000u, 0x12345678u, 0x12345678u}},  /* large mixed */
    {0x7FFFFFFFu, 0x80000000u, {0x80000000u, 0xC0000000u, 0x3FFFFFFFu, 0x3FFFFFFFu, 0x00000000u, 0x00000000u, 0x7FFFFFFFu, 0x7FFFFFFFu}},  /* max positive x min negative */
};

#define RR(insn, a, b) ({ uint32_t r_; __asm__ volatile (insn " %0, %1, %2" : "=r"(r_) : "r"(a), "r"(b)); r_; })

static uint32_t run_op(int op, uint32_t a, uint32_t b)
{
    switch (op) {
    case OP_MUL:    return RR("mul", a, b);
    case OP_MULH:   return RR("mulh", a, b);
    case OP_MULHSU: return RR("mulhsu", a, b);
    case OP_MULHU:  return RR("mulhu", a, b);
    case OP_DIV:    return RR("div", a, b);
    case OP_DIVU:   return RR("divu", a, b);
    case OP_REM:    return RR("rem", a, b);
    default:        return RR("remu", a, b);
    }
}

int main(void)
{
    uart_init();
    for (unsigned c = 0; c < sizeof cases / sizeof cases[0]; c++)
        for (int op = 0; op < OP_COUNT; op++)
            if (run_op(op, cases[c].a, cases[c].b) != cases[c].r[op])
                test_fail(FAIL_BASE | (c << 3) | (unsigned)op);
    uart_puts("muldiv PASS\n");
    test_pass();
}
