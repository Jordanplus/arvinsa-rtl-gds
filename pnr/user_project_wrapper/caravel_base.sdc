# LibreLane's base.sdc without its set_driving_cell (ADR-0019 decision 14), sourced by pnr.sdc and
# signoff.sdc in place of base.sdc. OpenSTA ignores set_input_transition on a port that has a driving
# cell, whatever the order (2026-10-12, run p7_floorplan4 netlist: with base.sdc's inv_2 the slew at
# wbs_dat_i[3] stayed 0.019 ns after set_input_transition -max 0.84; without the driving cell it is
# 0.84; set_drive 0 does not clear it; skill timing-constraints-sdc). caravel_io.sdc gives every input
# its Caravel transition instead, and wb_rst_i (no Caravel number) keeps the inv_2 driving cell.
rename set_driving_cell cio_set_driving_cell
proc set_driving_cell {args} {}
source $::env(SCRIPTS_DIR)/base.sdc
rename set_driving_cell ""
rename cio_set_driving_cell set_driving_cell
