# Signoff SDC for soc_top (SIGNOFF_SDC_FILE; read by OpenROAD.STAPostPNR only).
# LibreLane's base SDC unchanged: max transition 0.75 ns, max fanout 10 (MAX_TRANSITION_CONSTRAINT and
# MAX_FANOUT_CONSTRAINT from the PDK's libs.tech/openlane/sky130_fd_sc_hd/config.tcl lines 63-64).
# This file exists because without SIGNOFF_SDC_FILE the signoff STA falls back to PNR_SDC_FILE
# (pnr.sdc, max fanout 8; verified: sta.log reads pnr.sdc), and signoff must check the real limits.
source $::env(SCRIPTS_DIR)/base.sdc
# Clock uncertainty by component (setup, hold, half-cycle paths); same file as pnr.sdc.
source [file join [file dirname [info script]] clock_uncertainty.sdc]
