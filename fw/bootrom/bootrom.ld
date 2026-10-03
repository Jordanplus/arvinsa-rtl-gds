/*
 * fw/bootrom/bootrom.ld - boot ROM linker script (docs/spec/soc_spec.md §4.6, §6.5).
 * Run through the C preprocessor (fw/Makefile); addresses come from soc.h.
 * The ROM region is SOC_ROM_SIZE bytes, so an oversized boot ROM fails to link.
 */
#include "soc.h"

ENTRY(_start)

MEMORY
{
    rom (rx) : ORIGIN = SOC_ROM_BASE, LENGTH = SOC_ROM_SIZE
}

SECTIONS
{
    .text :
    {
        KEEP(*(.text.boot))
        *(.text .text.*)
    } > rom

    /* The boot ROM must not own any SRAM data; collect such input sections here
     * so the ASSERT below rejects them instead of letting them become orphans. */
    .no_sram_data (NOLOAD) :
    {
        *(.data .data.* .sdata .sdata.* .bss .bss.* .sbss .sbss.* COMMON)
    } > rom
}

ASSERT(_start == SOC_PROGADDR_RESET, "bootrom.S: _start must be at SOC_PROGADDR_RESET")
ASSERT(SIZEOF(.text) <= SOC_ROM_WORDS * 4, "bootrom.S: boot ROM exceeds SOC_ROM_WORDS")
ASSERT(SIZEOF(.no_sram_data) == 0, "bootrom.S: boot ROM must not use .data/.bss (no SRAM)")
