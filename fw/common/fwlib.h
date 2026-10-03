/*
 * fw/common/fwlib.h - SoC firmware library (docs/spec/soc_spec.md §6.3).
 */
#ifndef FWLIB_H
#define FWLIB_H

#include <stdint.h>
#include "fw_layout.h"

#define REG32(addr) (*(volatile uint32_t *)(uintptr_t)(addr))

#define UART_DIV_REG   REG32(SOC_UART_BASE + SOC_UART_DIV_OFF)
#define UART_DATA_REG  REG32(SOC_UART_BASE + SOC_UART_DATA_OFF)
#define TEST_SIG_REG   REG32(SOC_TEST_BASE + SOC_TEST_SIG_OFF)
#define TEST_DONE_REG  REG32(SOC_TEST_BASE + SOC_TEST_DONE_OFF)
#define TEST_IRQ_REG   REG32(SOC_TEST_BASE + SOC_TEST_IRQ_OFF)

/* Written by the IRQ entry in start.S. */
extern volatile uint32_t irq_count;
extern volatile uint32_t irq_pending_mask;

/* Linker symbols (fw/common/link.ld); use their addresses only. */
extern uint32_t _free_start[];
extern uint32_t _stack_limit[];
extern uint32_t _sram_half[];

void     uart_init(void);                 /* DIV = SOC_UART_DIV; call first in every test */
void     uart_putc(char c);               /* send one byte, accumulate CRC32 */
void     uart_puts(const char *s);        /* send a NUL-terminated string */
void     uart_puts_burst(const char *s);  /* same, DATA writes back to back (UART stall test) */
int      uart_getc(void);                 /* blocking receive, returns 0..255 */
void     uart_puthex(uint32_t v);         /* send 8 upper-case hex digits */
uint32_t uart_crc32(void);                /* zlib.crc32() of every byte sent so far */
uint32_t irq_setmask(uint32_t mask);      /* PicoRV32 maskirq (1 = masked); returns old mask */

void test_pass(void) __attribute__((noreturn));           /* SIG = CRC32, DONE = PASS */
void test_fail(uint32_t code) __attribute__((noreturn));  /* DONE = FAIL_BASE | code[15:0] */

#endif /* FWLIB_H */
