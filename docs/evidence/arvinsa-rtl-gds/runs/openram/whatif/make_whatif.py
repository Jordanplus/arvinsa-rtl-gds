# Phase 6 step 3 what-if (ADR-0018 decision 7): two schematic-only fixes of the read failure, on the default
# 2 KB netlist (special_pfet_latch already renamed). Not layout; only to see which fix makes the failing PVTs read.
#  W1 transmission gate: a PMOS beside each column mux NMOS, gate = ideal vccd1 - sel (E source)
#  W2 precharge of the sense amp inputs: one precharge cell (2 pull-ups + equalizer) on bl_out/br_out per bit
import re, sys
src, macro = sys.argv[1], sys.argv[2]
text = open(src).read()
cm = f".SUBCKT {macro}_column_mux\n"
assert text.count(cm) == 1
w1 = ".global vccd1\n" + text
end = w1.index(f".ENDS {macro}_column_mux\n", w1.index(cm))
w1 = (w1[:end] + "Esel_b selb 0 vccd1 sel 1\n"
      "Xmux_tp1 bl selb bl_out vccd1 sky130_fd_pr__pfet_01v8 m=1 w=2.88 l=0.15\n"
      "Xmux_tp2 br selb br_out vccd1 sky130_fd_pr__pfet_01v8 m=1 w=2.88 l=0.15\n" + w1[end:])
open(sys.argv[3], "w").write(w1)
pd = f".SUBCKT {macro}_port_data\n"
assert text.count(pd) == 1
end = text.index(f".ENDS {macro}_port_data\n", text.index(pd))
add = "".join(f"Xprechg_out{b} bl_out_{b} br_out_{b} p_en_bar vdd {macro}_precharge_0\n" for b in range(32))
open(sys.argv[4], "w").write(text[:end] + add + text[end:])
print("W1: 2 PMOS per column mux; W2: 32 precharge cells on bl_out/br_out")
