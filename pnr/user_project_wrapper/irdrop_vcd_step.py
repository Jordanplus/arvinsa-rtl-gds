# Runs LibreLane's OpenROAD.IRDropReport (python3 -m librelane.steps arguments) with its Tcl script replaced by
# irdrop_vcd.tcl next to this file: the same step plus read_vcd of $IR_VCD (ADR-0019 decision 20).
import os
from librelane.steps.openroad import IRDropReport
IRDropReport.get_script_path = lambda self: os.path.join(os.path.dirname(os.path.abspath(__file__)), "irdrop_vcd.tcl")
from librelane.steps.__main__ import cli
cli()
