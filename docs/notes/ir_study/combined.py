# Per-instance supply loss = (Vnom - V(VPWR)) + V(VGND), from PSM's measured per-instance voltage files
# (net-vccd1.csv / net-vssd1.csv). Instance-level only (PSM's node-level worst may be slightly higher).
import csv, glob, os, re, sys
W = sys.argv[1]
for d in sorted(glob.glob(f"{W}/runs/m_[BOSX]*/")):
    name = os.path.basename(d.rstrip("/"))
    log = open(f"{d}/openroad-irdropreport.log").read()
    vnom = float(re.search(r"Supply voltage\s*:\s*([\d.e+-]+)", log)[1])
    vdd = {}
    for r in csv.DictReader(open(f"{d}/net-vccd1.csv")):
        k = r["Instance"]; vdd[k] = min(vdd.get(k, 9), float(r["Voltage"]))
    gnd = {}
    for r in csv.DictReader(open(f"{d}/net-vssd1.csv")):
        k = r["Instance"]; gnd[k] = max(gnd.get(k, -9), float(r["Voltage"]))
    best = max(((vnom - vdd[k]) + gnd[k], k) for k in vdd if k in gnd)
    print(f"{name:22s} worst per-instance (VDD drop + GND rise) = {best[0]*1e3:.3f} mV at {best[1]}  (Vnom {vnom})")
