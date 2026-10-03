# Sourced by LibreLane's STA steps once per corner (librelane/scripts/openroad/sta/corner.tcl
# lines 59-61, LibreLane 3.0.14), after the corner is selected; $corner_name holds its name,
# e.g. max_ss_100C_1v60. Only STA sees this: placement, CTS and the resizer do not.
#
# The SRAM timing model (padded.lib) is a single TT-based table used for all 9 corners.
# Derate the SRAM instance per corner: docs/decisions/0007-sram-padded-lib.md.
set sram_late_ss 1.5
set sram_early_ff 0.7

set sram_cells [get_cells sram0]
if { [llength $sram_cells] != 1 } {
    puts stderr "sta_extra_corner: ERROR - expected exactly one instance sram0"
    exit 1
}
if { [string match "*ss*" $corner_name] } {
    set_timing_derate -late -cell_delay $sram_late_ss $sram_cells
    puts "sta_extra_corner: $corner_name: sram0 -late -cell_delay $sram_late_ss"
} elseif { [string match "*ff*" $corner_name] } {
    set_timing_derate -early -cell_delay $sram_early_ff $sram_cells
    puts "sta_extra_corner: $corner_name: sram0 -early -cell_delay $sram_early_ff"
} else {
    puts "sta_extra_corner: $corner_name: sram0 no derate"
}
