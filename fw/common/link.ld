/*
 * fw/common/link.ld - linker script for SoC firmware tests (docs/spec/soc_spec.md §6.2).
 * This file is run through the C preprocessor (see fw/Makefile) so that every address
 * comes from the generated soc.h; do not hand-write addresses here.
 *
 * Layout: 0x0 reset jump, 0x10 IRQ entry, then text/rodata/data/bss.
 * _free_start = end of bss, 4-byte aligned. Stack: SOC_STACK_TOP downwards,
 * FW_STACK_RESERVE bytes reserved. The size checker (fw/scripts/size_check.py)
 * fails the build when _free_start > _stack_limit (and > _sram_half for memtest).
 */
#include "fw_layout.h"

ENTRY(_reset)

MEMORY
{
    sram (rwx) : ORIGIN = SOC_SRAM_BASE, LENGTH = SOC_SRAM_SIZE
}

SECTIONS
{
    .text :
    {
        KEEP(*(.text.start))
        *(.text .text.*)
    } > sram

    .rodata :
    {
        *(.rodata .rodata.* .srodata .srodata.*)
    } > sram

    .data :
    {
        *(.data .data.* .sdata .sdata.*)
        . = ALIGN(4);
    } > sram

    .bss (NOLOAD) : ALIGN(4)
    {
        _bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(4);
        _bss_end = .;
    } > sram

    _free_start  = ALIGN(_bss_end, 4);
    _stack_top   = SOC_STACK_TOP;
    _stack_limit = FW_STACK_LIMIT;
    _sram_half   = FW_SRAM_HALF;
}

ASSERT(_reset == SOC_SRAM_BASE, "start.S: reset jump must be at SOC_SRAM_BASE")
ASSERT(_irq_entry == SOC_PROGADDR_IRQ, "start.S: IRQ entry must be at SOC_PROGADDR_IRQ")
