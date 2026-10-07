# Runs LibreLane's OpenROAD.GeneratePDN step with its Tcl script replaced by $PDN_SCRIPT (regen_pdn.tcl).
import os
from librelane.steps.openroad import GeneratePDN
GeneratePDN.get_script_path = lambda self: os.environ["PDN_SCRIPT"]
from librelane.steps.__main__ import cli
cli()
