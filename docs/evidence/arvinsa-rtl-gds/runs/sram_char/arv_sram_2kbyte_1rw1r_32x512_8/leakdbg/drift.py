"""Debug: which node drifts while both clocks are parked high (leakage deck, trimmed b4 netlist, longer park).
usage: drift.py <pvt>   -> leakdbg/drift/<pvt>/all.raw (binary, every node)"""
import os, re, subprocess, sys
M = "arv_sram_2kbyte_1rw1r_32x512_8"
ROOT = "~/claude_prjs/arvinsa-rtl-gds"
sys.path.insert(0, ROOT + "/ip/sram/char")
import sramchar as sc, characterize as ch, power  # noqa
pvt = sys.argv[1]
power.PARK_CYCLES = 12
here = os.path.join(ROOT, f"runs/sram_char/{M}/leakdbg/drift/{pvt}")
os.makedirs(here, exist_ok=True)
net = f"{ROOT}/runs/sram_char/{M}/power/b4/trimmed.spice"
s, park, win = power.leak_sequence(pvt)
deck = s.deck(net, ch.TSTEP, ch.TMAX, probes=("i(vvdd)",), clk_park=park, csb1=0)
deck = re.sub(r"^wrdata .*$", "set filetype=binary\nwrite all.raw", deck, flags=re.M)
open(os.path.join(here, "deck.sp"), "w").write(deck)
sc.spiceinit(here)
r = subprocess.run(["ngspice", "-b", "deck.sp"], cwd=here, stdout=open(os.path.join(here, "ngspice.log"), "w"), stderr=subprocess.STDOUT)
print(pvt, "rc", r.returncode, "park edge", s.edges()[0][park["clk0"]], "end", s.edges()[0][-1])
