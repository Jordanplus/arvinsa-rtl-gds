/*
 * fw/common/fw_layout.h - firmware memory layout constants (docs/spec/soc_spec.md §6.2, §6.5).
 * Shared by C, assembly and the (C-preprocessed) linker scripts. Addresses come from
 * the generated soc.h (rtl/include/memmap.vh); only the stack reserve is defined here.
 */
#ifndef FW_LAYOUT_H
#define FW_LAYOUT_H

#include "soc.h"

/* 256-byte stack reserve at the top of SRAM: 0x700-0x7FF (spec §6.2). */
#define FW_STACK_RESERVE   0x100
/* Lowest address the stack may use; _free_start must not exceed it (size checker). */
#define FW_STACK_LIMIT     (SOC_STACK_TOP - FW_STACK_RESERVE)
/* memtest image must end in the lower SRAM half so its test area covers the upper half. */
#define FW_SRAM_HALF       (SOC_SRAM_BASE + SOC_SRAM_SIZE / 2)
/* UART loader word-count limit (spec §6.5: 1 <= N <= 448), i.e. the image may not reach the stack. */
#define FW_LOAD_MAX_WORDS  ((FW_STACK_LIMIT - SOC_SRAM_BASE) / 4)

#endif /* FW_LAYOUT_H */
