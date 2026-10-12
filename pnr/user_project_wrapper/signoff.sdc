# Signoff SDC for user_project_wrapper (Phase 7, ADR-0019): as pnr/soc_top/signoff.sdc, LibreLane's base
# SDC unchanged (max transition 0.75 ns, max fanout 10) and the same clock uncertainty file as soc_top.
source $::env(SCRIPTS_DIR)/base.sdc
source [file join [file dirname [info script]] .. soc_top clock_uncertainty.sdc]
