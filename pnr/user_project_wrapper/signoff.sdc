# Signoff SDC for user_project_wrapper (Phase 7, ADR-0019): as pnr/soc_top/signoff.sdc, LibreLane's base
# SDC unchanged (max transition 0.75 ns, max fanout 10), the same clock uncertainty file as soc_top and the
# Caravel boundary constraints (caravel_io.sdc, ADR-0019 decision 14).
source [file join [file dirname [info script]] caravel_base.sdc]   ;# base.sdc without driving cells
source [file join [file dirname [info script]] .. soc_top clock_uncertainty.sdc]
source [file join [file dirname [info script]] caravel_io.sdc]
