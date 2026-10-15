# Session-only: per-corner worst slack (like sta_corners.tcl), slew/cap violation counts, repair
# buffer counts by name prefix, the longest nets on sram0 input pins, and the worst max_ss_n40C path.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
set ::env(CURRENT_ODB) $::env(STA_ODB)
read_current_odb
set_propagated_clock [all_clocks]
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
estimate_parasitics -placement
set i 0
while { [info exists ::env(_LIB_CORNER_$i)] } {
    set c [lindex $::env(_LIB_CORNER_$i) 0]
    puts [format "CORNER %-18s setup_ws %8.3f setup_tns %9.3f hold_ws %7.3f hold_tns %8.3f" $c \
        [worst_slack -corner $c -max] [total_negative_slack -corner $c -max] \
        [worst_slack -corner $c -min] [total_negative_slack -corner $c -min]]
    incr i
}
puts "VIOL slew [sta::max_slew_violation_count] cap [sta::max_capacitance_violation_count] fanout [sta::max_fanout_violation_count]"
set block [ord::get_db_block]
array set cnt {}
set area 0
foreach inst [$block getInsts] {
    set m [$inst getMaster]
    if {[$m getType] eq "CORE" || [string match "sky130_fd_sc_hd__*" [$m getName]]} {
        if {![string match "*fill*" [$m getName]] && ![string match "*tap*" [$m getName]] && ![string match "*decap*" [$m getName]]} {
            set area [expr {$area + [$m getWidth] * [$m getHeight] / 1e6}]
        }
    }
    if {[regexp {^(wire|fanout|load_slew|max_length|split|rebuffer|hold)\d+$} [$inst getName] -> p]} {
        if {![info exists cnt($p)]} { set cnt($p) 0 }
        incr cnt($p)
    }
}
puts "BUFFERS [array get cnt] stdcell_area_um2 [format %.0f $area]"
set sram [$block findInst sram0]
set lens {}
foreach it [$sram getITerms] {
    if {![$it isInputSignal]} continue
    set n [$it getNet]
    if {$n eq "NULL"} continue
    set xs {}; set ys {}
    foreach j [$n getITerms] { lassign [[$j getInst] getLocation] x y; lappend xs $x; lappend ys $y }
    set hp [expr {([tcl::mathfunc::max {*}$xs] - [tcl::mathfunc::min {*}$xs] + [tcl::mathfunc::max {*}$ys] - [tcl::mathfunc::min {*}$ys]) / 1000.0}]
    lappend lens [list $hp [$n getName] [[$it getMTerm] getName]]
}
set lens [lsort -real -decreasing -index 0 $lens]
puts "SRAM_INPUT_NETS [llength $lens], longest HPWL (um, instance origins): [lrange $lens 0 4]"
set n200 0
foreach l $lens { if {[lindex $l 0] > 200} { incr n200 } }
puts "SRAM_INPUT_NETS over 200 um: $n200"
foreach c {max_ss_n40C_1v60 min_ff_n40C_1v95} {
    puts "SKEW $c"
    report_clock_skew -setup -corner $c
    report_clock_skew -hold -corner $c
}
report_checks -path_delay max -corner max_ss_n40C_1v60 -fields {slew cap fanout} -digits 6 > $::env(PATH_RPT)
