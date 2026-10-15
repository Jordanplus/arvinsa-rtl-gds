foreach lib [list ~/claude_prjs/arvinsa-rtl-gds/ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/sky130_sram_2kbyte_1rw1r_32x512_8__ss_n40C_1v60.lib <claude-session-tmp>/scratchpad/slew13.lib] {
  sta::clear_sta
  read_liberty ~/.ciel/ciel/sky130/versions/8afc8346a57fe1ab7934ba5a6056ea8b43078e71/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ss_n40C_1v60.lib
  read_liberty $lib
  read_verilog ~/claude_prjs/arvinsa-rtl-gds/runs/soc_top/final/nl/soc_top.nl.v
  link_design soc_top
  read_spef ~/claude_prjs/arvinsa-rtl-gds/runs/soc_top/final/spef/min/soc_top.min.spef
  read_sdc ~/claude_prjs/arvinsa-rtl-gds/runs/soc_top/final/sdc/soc_top.sdc
  set_propagated_clock [all_clocks]
  puts "== $lib"
  report_checks -path_delay max -from [get_cells sram0] -group_path_count 1 -format end
}
