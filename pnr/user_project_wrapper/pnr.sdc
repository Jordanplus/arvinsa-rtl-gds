# PnR SDC for user_project_wrapper (Phase 7, ADR-0019): the constraints of pnr/soc_top/pnr.sdc (see the
# reasons there): LibreLane's base SDC, max fanout 8, max transition 0.70 ns, and the same clock
# uncertainty file as soc_top.
source $::env(SCRIPTS_DIR)/base.sdc
set_max_fanout 8 [current_design]
set_max_transition 0.70 [current_design]
source [file join [file dirname [info script]] .. soc_top clock_uncertainty.sdc]
