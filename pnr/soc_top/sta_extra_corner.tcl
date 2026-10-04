# Sourced by LibreLane's STA steps once per corner (librelane/scripts/openroad/sta/corner.tcl
# lines 59-61, LibreLane 3.0.14), after the corner is selected; $corner_name holds its name,
# e.g. max_ss_100C_1v60. Only STA sees this: placement, CTS and the resizer do not.
#
# The SRAM timing model (padded.lib) is a single TT-based table used for all corners.
# Derate the SRAM instance per corner: docs/decisions/0007-sram-padded-lib.md.
# OpenSTA uses an instance derate instead of the global one, it does not multiply them
# (sdc/Sdc.cc 626-662; skill signoff-criteria rule 5). The global derate of base.sdc is the
# +-5 % OCV (TIME_DERATING_CONSTRAINT), so it is multiplied in here (user decision 2026-10-04):
#   ss late  1.5 (process/voltage/temperature of the SRAM, ADR-0007) x 1.05 = 1.575
#   ff early 0.7 x 0.95 = 0.665
set sram_late_ss 1.575
set sram_early_ff 0.665

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

# Minimum pulse width and minimum period (not in LibreLane's STA reports). The SRAM clk0 needs
# >= 12 ns high and low and a period >= 30 ns (padded.lib, ADR-0007). STA measures the pulse with
# the ideal 50 % waveform, so the slack must also cover what it does not see (skill
# signoff-criteria): for the pulse width the duty cycle distortion plus half-period jitter, for the
# period the period jitter (unc_* of pnr/soc_top/clock_uncertainty.sdc, read with the SDC).
# Written to <corner>/pulse_width.rpt; checked by pnr/soc_top/check_soc.py pulse_width.
puts "%OL_CREATE_REPORT pulse_width.rpt"
if { [info exists ::unc_dcd] && [info exists ::unc_j_half] && [info exists ::unc_j_period] } {
    puts "required_slack min_pulse_width [expr {$::unc_dcd + $::unc_j_half}] min_period $::unc_j_period"
} else {
    puts "required_slack missing: the SDC did not define unc_dcd, unc_j_half and unc_j_period"
}
report_check_types -min_pulse_width -min_period -corner $corner_name
puts "%OL_END_REPORT"
