foreach rc {min max} {
  sta::clear_sta
  read_liberty ~/.ciel/ciel/sky130/versions/8afc8346a57fe1ab7934ba5a6056ea8b43078e71/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
  read_liberty ~/claude_prjs/arvinsa-rtl-gds/ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/char/arv_sram_2kbyte_1rw1r_32x512_8__tt_025C_1v80.lib
  read_verilog ~/claude_prjs/arvinsa-rtl-gds/runs/user_project_wrapper/final/nl/user_project_wrapper.nl.v
  link_design user_project_wrapper
  read_spef ~/claude_prjs/arvinsa-rtl-gds/runs/user_project_wrapper/final/spef/$rc/user_project_wrapper.$rc.spef
  set caps {}
  foreach p [get_pins u_soc.sram0/dout0*] { set n [get_nets -of_objects $p]; lappend caps [sta::format_capacitance [$n capacitance [sta::cmd_corner] max] 4] }
  set s [lsort -real $caps]
  puts "== wrapper $rc dout0 load pF: min [lindex $s 0] max [lindex $s end] n [llength $s]"
}
foreach rc {min nom max} {
  sta::clear_sta
  read_liberty ~/.ciel/ciel/sky130/versions/8afc8346a57fe1ab7934ba5a6056ea8b43078e71/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ff_n40C_1v95.lib
  read_liberty ~/claude_prjs/arvinsa-rtl-gds/ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/char/arv_sram_2kbyte_1rw1r_32x512_8__ff_n40C_1v95.lib
  read_verilog ~/claude_prjs/arvinsa-rtl-gds/runs/user_project_wrapper/final/nl/user_project_wrapper.nl.v
  link_design user_project_wrapper
  read_spef ~/claude_prjs/arvinsa-rtl-gds/runs/user_project_wrapper/final/spef/$rc/user_project_wrapper.$rc.spef
  read_sdc ~/claude_prjs/arvinsa-rtl-gds/runs/user_project_wrapper/final/sdc/user_project_wrapper.sdc
  set_propagated_clock [all_clocks]
  puts "== wrapper ${rc}_ff_n40C hold to sram0 inputs"
  report_checks -path_delay min -to [get_pins u_soc.sram0/*] -group_path_count 3 -format end
  puts "== wrapper ${rc}_ff_n40C hold worst overall [sta::format_time [sta::worst_slack -min] 3]"
}
exit
