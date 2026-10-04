# Clock uncertainty of soc_top, by component. Sourced by pnr.sdc and signoff.sdc after LibreLane's
# base.sdc, so placement, CTS, the resizer and signoff STA all use the same values.
# Why and how: docs/notes/signoff_criteria_soc_top.md ("clock uncertainty 的成分"), skill
# signoff-criteria. Values in ns. "A" = assumption until the clock source is known (Phase 7:
# Caravel clock); the clock tree skew is not in here, STA computes it (propagated clock).
#
# Setup, full-cycle paths (launch and capture on rising edges):
set unc_j_period 0.15   ;# A: peak period jitter of the clock source
set unc_m_setup  0.10   ;# effects the tools do not analyse: SI delta delay, dynamic IR drop, aging
# Hold (launch and capture on the same edge, so the period jitter cancels):
set unc_m_hold   0.25   ;# SI speed-up, dynamic IR drop on the capture clock, extraction error
# Half-cycle paths (one edge launches, the opposite edge captures, e.g. sram0 dout0 launched on
# the falling edge and captured by the rdata register on the rising edge): duty cycle distortion.
set unc_duty_max 0.55   ;# A: each clock phase is at most 55 % of the period (45/55 % symmetry)
set unc_j_half   $unc_j_period   ;# A: jitter of one half period, taken as the full period jitter
#
# base.sdc already set 0.25 for setup and hold (CLOCK_UNCERTAINTY_CONSTRAINT); these replace it.
set unc_clk [get_clocks $::clock_port]
set unc_setup [expr {$unc_j_period + $unc_m_setup}]
set unc_dcd   [expr {($unc_duty_max - 0.5) * $::env(CLOCK_PERIOD)}]
set unc_half  [expr {$unc_j_half + $unc_dcd + $unc_m_setup}]
set_clock_uncertainty -setup $unc_setup $unc_clk
set_clock_uncertainty -hold $unc_m_hold $unc_clk
# An edge-specific (inter-clock) uncertainty replaces the one above for that edge pair, it is not
# added to it (OpenSTA search/PathEnd.cc 364-381; skill signoff-criteria rule 3), so it holds the
# full setup terms plus the duty cycle distortion.
set_clock_uncertainty -fall_from $unc_clk -rise_to $unc_clk -setup $unc_half
set_clock_uncertainty -rise_from $unc_clk -fall_to $unc_clk -setup $unc_half
puts "clock_uncertainty.sdc: setup $unc_setup, hold $unc_m_hold, half-cycle setup $unc_half (duty cycle distortion $unc_dcd)"
