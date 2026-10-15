source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
read_current_odb
set_propagated_clock [all_clocks]
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
estimate_parasitics -placement
proc fo {pin} {
  set net [get_nets -of_objects [get_pins $pin]]
  puts "net [get_full_name $net] loads: [lmap p [get_pins -of_objects $net -filter direction==input] {get_full_name $p}]"
}
puts "=== fanout along wbs_adr_i\[9\] path"
fo input36/A
fo input36/X
fo _19440_/X
fo _19441_/X
puts "=== worst setup through each pin (all corners)"
foreach p {input36/X _19440_/X _19441_/X} {
  puts "--- $p"
  report_checks -path_delay max -through [get_pins $p] -format end -digits 3
}
puts "=== setup path through input36/X"
report_checks -path_delay max -through [get_pins input36/X] -digits 3
puts "=== hold slack of every wbs_* endpoint by corner"
foreach c [sta::corners] {
  set n [sta::corner_name $c]
  puts "--- $n"
  report_checks -path_delay min -corner $n -from [get_ports {wbs_*}] -format end -group_path_count 1 -digits 3
  report_checks -path_delay min -corner $n -from [all_registers] -format end -group_path_count 1 -digits 3
}
