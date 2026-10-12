# PnR SDC for user_project_wrapper (Phase 7, ADR-0019): the constraints of pnr/soc_top/pnr.sdc (see the
# reasons there): LibreLane's base SDC (caravel_base.sdc: without its driving cells), max fanout 8, max
# transition 0.70 ns, the same clock uncertainty file as soc_top, then the Caravel boundary constraints
# (caravel_io.sdc, ADR-0019 decision 14).
source [file join [file dirname [info script]] caravel_base.sdc]   ;# base.sdc without driving cells
set_max_fanout 8 [current_design]
set_max_transition 0.70 [current_design]
source [file join [file dirname [info script]] .. soc_top clock_uncertainty.sdc]
source [file join [file dirname [info script]] caravel_io.sdc]
