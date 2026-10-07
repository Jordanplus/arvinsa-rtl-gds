# Rip up the vccd1/vssd1 special wiring (core grid, followpin rails, macro hookup) and the
# supply BPins of the finished layout, then regenerate the whole grid with LibreLane's own
# pdn_cfg.tcl + pdngen using the PDN_* values of the step config. Signal routing is left as is.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
read_current_odb
source $::env(SCRIPTS_DIR)/openroad/common/set_power_nets.tcl
set block [ord::get_db_block]
foreach netname [concat $::env(VDD_NETS) $::env(GND_NETS)] {
    set net [$block findNet $netname]
    set nsw 0; set nbp 0
    foreach sw [$net getSWires] { odb::dbSWire_destroy $sw; incr nsw }
    foreach bt [$net getBTerms] { foreach bp [$bt getBPins] { odb::dbBPin_destroy $bp; incr nbp } }
    puts "RIPUP $netname swires=$nsw bpins=$nbp"
}
read_pdn_cfg
if {[catch {log_cmd pdngen} errmsg]} { puts stderr $errmsg; exit 1 }
# dump met5/met4 stripes per net (um) for the vsrc generator
set f [open $::env(STEP_DIR)/stripes.txt w]
foreach netname [concat $::env(VDD_NETS) $::env(GND_NETS)] {
    set net [$block findNet $netname]
    foreach sw [$net getSWires] {
        foreach w [$sw getWires] {
            if {[$w isVia]} continue
            set l [[$w getTechLayer] getName]
            if {$l ne "met5" && $l ne "met4"} continue
            puts $f "$netname $l [$w getWireShapeType] [expr {[$w xMin]/1000.0}] [expr {[$w yMin]/1000.0}] [expr {[$w xMax]/1000.0}] [expr {[$w yMax]/1000.0}]"
        }
    }
}
close $f
write_views
foreach {net} "$::env(VDD_NETS) $::env(GND_NETS)" {
    set report_file $::env(STEP_DIR)/$net-grid-errors.rpt
    set f [open $report_file "w"]; puts $f ""; close $f
    if { [catch {check_power_grid -net $net -error_file $report_file} err] } { puts stderr "\[WARNING\] Grid check for $net failed: $err" }
}
