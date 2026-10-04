# Custom variant of librelane/scripts/openroad/irdrop.tcl (same setup lines),
# plus diagnostics and variant knobs read from env:
#   IR_SOURCE_TYPE  FULL|BUMPS|STRAPS (omit -> PSM default)
#   IR_VSRC_DIR     directory with <net>.vsrc files -> passed as -vsrc
#   IR_DEL_BTERMS   1 -> delete the supply BTerms in memory only (never written back)
#   IR_EM           1 -> -enable_em -em_outfile STEP_DIR/em-<net>.csv
#   IR_DEBUG        extra PSM debug groups (e.g. "timer nodes")
#   IR_SRC_SETTINGS extra args for set_pdnsim_source_settings
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl

read_current_odb

source $::env(SCRIPTS_DIR)/openroad/common/set_power_nets.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl

read_spef $::env(CURRENT_SPEF_DEFAULT_CORNER)

proc envget {k {d ""}} { if {[info exists ::env($k)]} { return $::env($k) } ; return $d }

# ---- diagnostics: corner, layer resistance used, power ----
set corner [sta::cmd_corner]
puts "DIAG corner=[$corner name] LIB_VOLTAGE=$::env(LIB_VOLTAGE)"
foreach layer [[ord::get_db_tech] getLayers] {
    set t [$layer getType]
    if {$t eq "ROUTING" || $t eq "CUT"} {
        set dbres [$layer getResistance]
        set estres "n/a"
        catch { set estres [est::layer_resistance $layer $corner] }
        puts "DIAG layer [$layer getName] type=$t tech_lef_res=$dbres est_layer_resistance=$estres width_dbu=[$layer getWidth]"
    }
}
puts "DIAG ---- report_power (corner [$corner name]) ----"
report_power
puts "DIAG ---- report_power -instances sram0 ----"
catch { report_power -instances [get_cells sram0] }

set_debug_level PSM resistance 1
set_debug_level PSM stats 1
foreach g [envget IR_DEBUG] { set_debug_level PSM $g 1 }

set src_settings [envget IR_SRC_SETTINGS]
if {$src_settings ne ""} { log_cmd set_pdnsim_source_settings {*}$src_settings }

if {[envget IR_DEL_BTERMS 0]} {
    foreach net [concat $::env(VDD_NETS) $::env(GND_NETS)] {
        set n [[ord::get_db_block] findNet $net]
        foreach bt [$n getBTerms] {
            puts "DIAG deleting (in memory only) BTerm [$bt getName] of $net"
            odb::dbBTerm_destroy $bt
        }
    }
}

puts "%OL_CREATE_REPORT irdrop.rpt"
foreach net [concat $::env(VDD_NETS) $::env(GND_NETS)] {
    set arg_list [list -net $net -voltage_file $::env(STEP_DIR)/net-$net.csv]
    if {[lsearch $::env(VDD_NETS) $net] >= 0} { set v $::env(LIB_VOLTAGE) } else { set v 0 }
    set_pdnsim_net_voltage -net $net -voltage $v
    set st [envget IR_SOURCE_TYPE]
    if {$st ne ""} { lappend arg_list -source_type $st }
    set vd [envget IR_VSRC_DIR]
    if {$vd ne ""} { lappend arg_list -vsrc $vd/$net.vsrc }
    if {[envget IR_EM 0]} { lappend arg_list -enable_em -em_outfile $::env(STEP_DIR)/em-$net.csv }
    log_cmd analyze_power_grid {*}$arg_list
}
puts "%OL_END_REPORT"
