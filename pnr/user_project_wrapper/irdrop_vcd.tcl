# LibreLane f24e0ea librelane/scripts/openroad/irdrop.tcl with one addition (after read_spef): read_vcd of
# $IR_VCD when set (ADR-0019 decision 20, IR with the max-power pattern). Run by irdrop_vcd_step.py, which
# replaces the Tcl script of OpenROAD.IRDropReport; when LibreLane is updated, re-copy and re-add the block.
# Copyright 2022 Efabless Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl

read_current_odb

source $::env(SCRIPTS_DIR)/openroad/common/set_power_nets.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl

read_spef $::env(CURRENT_SPEF_DEFAULT_CORNER)
# arvinsa: switching activity of a simulation window (VCD of the gate-level copy tb_soc.dut_gl) instead of
# OpenSTA's vectorless default; report_activity_annotation shows how many pins the VCD annotated.
if { [info exists ::env(IR_VCD)] && $::env(IR_VCD) ne "" } {
    log_cmd read_vcd -scope tb_soc/dut_gl $::env(IR_VCD)
    report_activity_annotation
}

if { [info exists ::env(VSRC_LOC_FILES)] } {
    puts "%OL_CREATE_REPORT irdrop.rpt"
    foreach {net vsrc_file} "$::env(VSRC_LOC_FILES)" {
        set arg_list [list]
        lappend arg_list -net $net
        lappend arg_list -voltage_file $::env(STEP_DIR)/net-$net.csv
        lappend arg_list -vsrc $vsrc_file
        log_cmd analyze_power_grid {*}$arg_list
    }
    puts "%OL_END_REPORT"
} else {
    puts "\[INFO\] Using voltage extracted from lib ($::env(LIB_VOLTAGE)V) for power nets and 0V for ground nets…"
    puts "%OL_CREATE_REPORT irdrop.rpt"
    foreach net "$::env(VDD_NETS)" {
        set arg_list [list]
        lappend arg_list -net $net
        lappend arg_list -voltage_file $::env(STEP_DIR)/net-$net.csv
        set_pdnsim_net_voltage -net $net -voltage $::env(LIB_VOLTAGE)
        log_cmd analyze_power_grid {*}$arg_list
    }
    foreach net "$::env(GND_NETS)" {
        set arg_list [list]
        lappend arg_list -net $net
        lappend arg_list -voltage_file $::env(STEP_DIR)/net-$net.csv
        set_pdnsim_net_voltage -net $net -voltage 0
        log_cmd analyze_power_grid {*}$arg_list
    }
    puts "%OL_END_REPORT"
}
