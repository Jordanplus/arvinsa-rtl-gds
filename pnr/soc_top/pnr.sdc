# PnR SDC for soc_top (PNR_SDC_FILE; read by the OpenROAD placement, CTS, resizer and routing steps).
# LibreLane's base SDC unchanged, then max fanout tightened from 10 (MAX_FANOUT_CONSTRAINT, PDK
# libs.tech/openlane/sky130_fd_sc_hd/config.tcl line 64) to 8: antenna repair adds diodes to nets
# after the resizer has fixed fanout, and a diode pin counts as one more load (run soc_explore7: a
# buffer with 10 loads + 1 diode = 11). Signoff STA still checks 10 (signoff.sdc).
# docs/decisions/0009-signoff-max-transition.md.
source $::env(SCRIPTS_DIR)/base.sdc
set_max_fanout 8 [current_design]
# Max transition 0.70 ns for PnR only (signoff keeps 0.75 ns, signoff.sdc). The resizer repairs with
# the 9 corners of RSZ_CORNERS; the temperature-inversion corner ss_n40C, checked only at signoff,
# has about 25 % slower transitions than ss_100C, and one data net ended at 0.766 ns there (Phase 4
# harden-soc 4). The resizer cannot see ss_n40C itself: RepairDesignPostGRT then does not finish
# (pnr/soc_top/config.json RSZ_CORNERS).
set_max_transition 0.70 [current_design]
# Clock uncertainty by component (setup, hold, half-cycle paths); same file as signoff.sdc.
source [file join [file dirname [info script]] clock_uncertainty.sdc]
