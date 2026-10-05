# Sourced by LibreLane's STA steps once per corner (librelane/scripts/openroad/sta/corner.tcl
# lines 59-61, LibreLane 3.0.14), after the corner is selected; $corner_name holds its name,
# e.g. max_ss_100C_1v60. Only STA sees this: placement, CTS and the resizer do not.
#
# The SRAM has one characterized .lib per PVT (docs/decisions/0010-sram-spice-characterization.md),
# so it no longer gets an instance derate here (ADR-0007's 1.575 / 0.665 are gone): an instance
# derate would replace, not multiply, the global +-5 % OCV derate of base.sdc (sdc/Sdc.cc 626-662),
# and without one sram0 is derated like every other cell.

# Minimum pulse width and minimum period (not in LibreLane's STA reports). The SRAM clk0 limits are
# in its .lib (min_pulse_width, minimum_period; ADR-0010). STA measures the pulse with
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
