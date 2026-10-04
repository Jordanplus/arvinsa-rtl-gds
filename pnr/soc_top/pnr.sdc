# PnR SDC for soc_top (PNR_SDC_FILE; read by the OpenROAD placement, CTS, resizer and routing steps).
# LibreLane's base SDC unchanged, then max fanout tightened from 10 (MAX_FANOUT_CONSTRAINT, PDK
# libs.tech/openlane/sky130_fd_sc_hd/config.tcl line 64) to 8: antenna repair adds diodes to nets
# after the resizer has fixed fanout, and a diode pin counts as one more load (run soc_explore7: a
# buffer with 10 loads + 1 diode = 11). Signoff STA still checks 10 (signoff.sdc).
# docs/decisions/0009-signoff-max-transition.md.
source $::env(SCRIPTS_DIR)/base.sdc
set_max_fanout 8 [current_design]
# Clock uncertainty by component (setup, hold, half-cycle paths); same file as signoff.sdc.
source [file join [file dirname [info script]] clock_uncertainty.sdc]
