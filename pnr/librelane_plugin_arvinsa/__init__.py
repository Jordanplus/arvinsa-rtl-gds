"""LibreLane plugin of this repo (docs/decisions/0016-cts-no-macro-latency-balancing.md).

LibreLane imports every module named librelane_plugin_* on the Python path (librelane/plugins.py);
pnr/librelane_flow.sh puts pnr/ on PYTHONPATH. The soc_top configs replace OpenROAD.CTS with the
step below through "meta": {"substituting_steps": ...}.

Arvinsa.CTSNoInsertionDelay is OpenROAD.CTS (same config variables, same outputs and metrics) with
one change: OpenROAD's clock_tree_synthesis is called with -no_insertion_delay. Without it, CTS
builds a separate clock tree for the macro clock pins and adds delay buffers until their latency
matches the flip-flops (TritonCTS::balanceMacroRegisterLatencies, OpenROAD dcf36133): ten
clkbuf_16 before sram0/clk0 in soc_top. LibreLane 3.0.14 has no variable for that flag
(librelane/scripts/openroad/cts.tcl), and the pinned LibreLane is not edited.
"""
import os

from librelane.steps import Step
from librelane.steps.openroad import CTS


@Step.factory.register()
class CTSNoInsertionDelay(CTS):
    """OpenROAD.CTS with clock_tree_synthesis -no_insertion_delay (no macro latency balancing)."""

    id = "Arvinsa.CTSNoInsertionDelay"
    name = "Clock Tree Synthesis (no macro latency balancing)"

    def get_script_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "cts_no_insertion_delay.tcl")
