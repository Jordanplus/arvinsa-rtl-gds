# Max current per layer / layer pair from PSM -em_outfile (current in A per resistor).
# Wire density uses the PDN shape widths from the DEF (met5/met4 straps 1.6 um, met1 rails 0.48 um) -> calculation.
# Limits: sky130_fd_sc_hd__nom.tlef DCCURRENTDENSITY AVERAGE (mA/um for wires, mA per via for cuts), Tj=90C.
import csv, sys, collections
LIM_W = {"met1": 2.8, "met2": 2.8, "met3": 6.8, "met4": 6.8, "met5": 10.17}
WID = {"met1": 0.48, "met4": 1.6, "met5": 1.6}
CUT = {("met1","met2"): ("via", 0.29), ("met2","met3"): ("via2", 0.48), ("met3","met4"): ("via3", 0.48), ("met4","met5"): ("via4", 2.49)}
for f in sys.argv[1:]:
    mx = collections.defaultdict(lambda: (0.0, None))
    for r in csv.DictReader(open(f)):
        a, b = r["Node0 Layer"], r["Node1 Layer"]; i = abs(float(r["Current"]))
        key = a if a == b else tuple(sorted((a, b), key=lambda s: int(s[3:]) if s.startswith("met") else 0))
        if i > mx[key][0]: mx[key] = (i, (r["Node0 X location"], r["Node0 Y location"], r["Node1 X location"], r["Node1 Y location"]))
    print("==", f.split("/runs/")[1])
    for k, (i, loc) in sorted(mx.items(), key=lambda kv: str(kv[0])):
        if isinstance(k, str):
            w = WID.get(k)
            dens = f"{i*1e3/w:.3f} mA/um (width {w} um) vs limit {LIM_W[k]} mA/um -> {i*1e3/w/LIM_W[k]*100:.1f}%" if w else f"limit {LIM_W.get(k)} mA/um (width not assumed)"
            print(f"  {k:5s} max I = {i*1e3:.4f} mA  {dens}  at {loc}")
        else:
            cn, lim = CUT.get(k, ("?", None))
            extra = f"vs {lim} mA per cut -> {i*1e3/lim*100:.1f}% if this connection were ONE cut" if lim else ""
            print(f"  {cn:5s} {k} max I = {i*1e3:.4f} mA {extra} at {loc}")
