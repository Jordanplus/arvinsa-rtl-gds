#!/usr/bin/env python3
"""Static IR of the wrapper including Caravel's own supply network, from the pads (ADR-0019 decisions 18, 19).

usage: ir_caravel.py <run dir> <out dir> <limits.toml> --vcd <window.vcd> [--vcd ...] [--ll-dir <LibreLane checkout>]
                    [--power <power.json>]

The run's IR step (and ir_worst.py) puts ideal sources on the wrapper's core rings. Caravel feeds those rings
through one vccd1 and one vssd1 pad on the right side, its own 5 um met4 ring and met3 bridges on the left and
right ring sides only (caravel_pwr/README.md), so most of the drop is outside the wrapper. This check:
  1. adds Caravel's vccd1/vssd1 shapes (caravel_pwr/shapes.txt, bridges.txt, vias.def, pads.txt; moved by
     -(121.74, 1037.0) um into wrapper coordinates) to a copy of the IR step's input DEF and makes an ODB of it;
  2. control: the IR step re-run on that ODB with the run's own supply points must give the run's IR result
     within CONTROL_TOL (relative; the added shapes do not change the wrapper; the DEF -> ODB round trip alone
     moved it by 0.01-0.02 % on p7_harden2);
  3. the IR step re-run with one ideal source at the pad end of each pad strap, in the slow corners of
     ir_worst.py (JUDGED: their libraries, 1.60 V and ss resistance, with the SRAM's port 1 floating current),
     with the switching activity of each --vcd window: the max-power pattern recorded on the final netlist
     (fw/tests/maxpower, run_gl_soc.py --record-window, 44 ns clock; ADR-0019 decision 20). The largest VDD
     drop + GND rise over windows and corners <= [max_sum] ir_caravel_vdd_drop_plus_gnd_rise of the limits
     file (20 mV: lowest pad supply 1.62 V - 1.60 V). Every window must annotate all pins (0 unannotated).
     The same corners with OpenSTA's vectorless activity are printed as [INFO] (decision 19's value, about
     2.2 times the max-power pattern on p7_harden2).
Also required: 54 + 53 bridges per net (left + right), two pad straps per net, the via definitions found; and,
before any tool runs, ir_pattern.check_inputs(): the run guard, exactly the windows win_5a/5b/5c, each recorded
with the run's CLOCK_PERIOD (Phase 7 review H2, H3).
Writes <out>/ir_caravel/ (with results.json, which ir_pattern.py --judge re-judges) and prints `ir-caravel: PASS` /
`ir-caravel: FAIL` last; exit code 0 only on PASS. Negative test: make neg-ir-caravel (neg_ir.py).
Python stdlib only (LibreLane and OpenROAD run inside LibreLane's nix-shell).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pnr", "soc_top"))
import ir_pattern  # noqa: E402
import ir_worst  # noqa: E402

DATA = os.environ.get("IR_CARAVEL_DATA", os.path.join(HERE, "caravel_pwr"))   # neg_ir.py points it at an edited copy
DX, DY = 121740, 1037000              # wrapper origin in caravel_core (DEF units, 1000/um)
NETS = ("vccd1", "vssd1")
BRIDGES = {"left": 54, "right": 53}   # per net (caravel_pwr/README.md)
KEY = "ir_caravel_vdd_drop_plus_gnd_rise"
CONTROL_TOL = 0.001
BRIDGE_VIA = ("- via4_5_bridge + VIARULE M3M4_PR + CUTSIZE 200 200  + LAYERS met3 via3 met4  + CUTSPACING 200 200 "
              " + ENCLOSURE 100 150 100 65  + ROWCOL 2 11  ;")
PAD_VIA = ("- via5_6_pad + VIARULE M4M5_PR + CUTSIZE 800 800  + LAYERS met4 via4 met5  + CUTSPACING 800 800 "
           " + ENCLOSURE 500 190 310 500  + ROWCOL 14 3  ;")


def special_net(def_text, net):
    sn = def_text[def_text.index("\nSPECIALNETS"):def_text.index("\nEND SPECIALNETS")]
    return re.search(rf"^    - {re.escape(net)} .*?;\s*$", sn, re.M | re.S)


def ring_x(def_text, net):
    """x (DEF units) of the left and right vertical core-ring shapes of a net in the wrapper DEF."""
    m = special_net(def_text, net)
    xs = sorted({int(x0) for w, x0, y0, x1, y1 in re.findall(
        r"(?:ROUTED|NEW) met4 (\d+) \+ SHAPE RING \( (-?\d+) (-?\d+) \) \( (-?\d+|\*) (-?\d+|\*) \)", m.group(0) if m else "")
        if int(w) > 0 and (x1 == "*" or x1 == x0)})
    return (xs[0], xs[-1]) if len(xs) == 2 else None


def build(def_in, def_out, vsrc_dir):
    """Write the DEF with Caravel's network and the pad sources; returns (rows, {net: vsrc path})."""
    d = open(def_in).read()
    rows, add, vias, srcs = [], {n: [] for n in NETS}, set(), {}
    core_ring = {}
    for line in open(os.path.join(DATA, "shapes.txt")):
        f = line.split()
        if not f or f[0].startswith("#"):
            continue
        net, kind = f[0], f[1]
        if kind == "via":
            name, x, y = f[2], int(f[3]) - DX, int(f[4]) - DY
            vias.add(name)
            add[net].append(f"NEW met4 0 + SHAPE STRIPE ( {x} {y} ) {name}")
        else:
            lay, w, x1, y1, x2, y2 = f[2], int(f[3]), *(int(v) for v in f[4:8])
            if lay == "met4" and x1 == x2 and w == 5000 and abs(y2 - y1) > 4000000:
                core_ring.setdefault(net, set()).add(x1)
            add[net].append(f"NEW {lay} {w} + SHAPE STRIPE ( {x1 - DX} {y1 - DY} ) ( {x2 - DX} {y2 - DY} )")
    # drop the four corner vias of the wrapper ring that caravel_core also lists (they are in the wrapper DEF)
    for net in NETS:
        wx = ring_x(d, net)
        if wx is None or len(core_ring.get(net, ())) != 2:
            rows.append((False, f"{net}: wrapper ring sides {wx}, caravel_core ring x {sorted(core_ring.get(net, ()))}"))
            return rows, None
        add[net] = [l for l in add[net] if not (l.startswith("NEW met4 0") and
                    any(f"( {x} " in l for x in wx))]
        cl, cr = sorted(core_ring[net])
        wl, wr = (x + DX for x in wx)
        count = {"left": 0, "right": 0}
        for line in open(os.path.join(DATA, "bridges.txt")):
            f = line.split()
            if not f or f[0].startswith("#"):
                continue
            x1, y1, x2, y2 = map(int, f)
            ends = (x1, x2)
            near = lambda a: any(abs(e - a) < 3000 for e in ends)
            side = "left" if near(cl) and near(wl) else "right" if near(wr) and near(cr) else None
            if not side:
                continue
            count[side] += 1
            yc, w = (y1 + y2) // 2, y2 - y1
            add[net].append(f"NEW met3 {w} + SHAPE STRIPE ( {x1 - DX} {yc - DY} ) ( {x2 - DX} {yc - DY} )")
            for xe in ((cl, wl) if side == "left" else (wr, cr)):
                add[net].append(f"NEW met3 0 + SHAPE STRIPE ( {xe - DX} {yc - DY} ) via4_5_bridge")
        rows.append((count == BRIDGES, f"{net}: {count['left']} + {count['right']} met3 bridges (left + right), expected "
                                       f"{BRIDGES['left']} + {BRIDGES['right']}"))
    pads = [l.split() for l in open(os.path.join(DATA, "pads.txt")) if l.strip() and not l.startswith("#")]
    for net in NETS:
        straps = [p for p in pads if p[0] == net]
        rows.append((len(straps) == 2, f"{net}: {len(straps)} pad straps (expected 2)"))
        for _, rx, ya, yb, xe in straps:
            rx, ya, yb, xe = map(int, (rx, ya, yb, xe))
            yc = (ya + yb) // 2
            add[net].append(f"NEW met5 {yb - ya} + SHAPE STRIPE ( {rx - 2500 - DX} {yc - DY} ) ( {xe - DX} {yc - DY} )")
            add[net].append(f"NEW met4 0 + SHAPE STRIPE ( {rx - DX} {yc - DY} ) via5_6_pad")
            srcs.setdefault(net, []).append(((xe - 3000 - DX) / 1000, (yc - DY) / 1000))
    # VIAS: the caravel_core definitions used, plus the bridge and pad vias
    have = set(re.findall(r"^\s*- (\S+) ", d[d.index("\nVIAS"):d.index("\nEND VIAS")], re.M))
    defs = [l for l in open(os.path.join(DATA, "vias.def")).read().splitlines() if l.split()[1] in vias]
    found = {l.split()[1] for l in defs}
    rows.append((found == vias, f"via definitions: {len(found)} of the {len(vias)} met4-met5 vias used"))
    defs = [l for l in defs + [BRIDGE_VIA, PAD_VIA] if l.split()[1] not in have]
    m = re.search(r"^VIAS (\d+) ;", d, re.M)
    d = d[:m.start()] + f"VIAS {int(m.group(1)) + len(defs)} ;" + d[m.end():]
    i = d.index("\nEND VIAS")
    d = d[:i] + "\n" + "\n".join("    " + l for l in defs) + d[i:]
    # die area large enough for Caravel's ring (PSM and the DEF reader)
    d = re.sub(r"^DIEAREA .*$", "DIEAREA ( -150000 -1050000 ) ( 3120000 3720000 ) ;", d, count=1, flags=re.M)
    sp0, sp1 = d.index("\nSPECIALNETS"), d.index("\nEND SPECIALNETS")
    sp = d[sp0:sp1]
    for net in NETS:
        m = re.search(rf"^    - {net} .*?(?=\n    - |\Z)", sp, re.M | re.S)
        body = m.group(0).rstrip()
        body = body[:-1].rstrip() + "\n      " + "\n      ".join(add[net]) + " ;"
        sp = sp[:m.start()] + body + sp[m.end():]
    open(def_out, "w").write(d[:sp0] + sp + d[sp1:])
    os.makedirs(vsrc_dir, exist_ok=True)
    vsrc = {}
    for net in NETS:
        vsrc[net] = os.path.join(vsrc_dir, f"{net}.vsrc")
        volt = "1.80" if net == "vccd1" else "0"
        open(vsrc[net], "w").write("".join(f"{x:.3f},{y:.3f},4.0,{volt}\n" for x, y in srcs.get(net, [])))
    return rows, vsrc


def main(argv):
    pos, opts = [], {}
    it = iter(argv)
    for a in it:
        if a in ("--ll-dir", "--power"):
            opts[a] = os.path.abspath(next(it, ""))
        elif a == "--vcd":
            opts.setdefault("--vcd", []).append(os.path.abspath(next(it, "")))
        else:
            pos.append(a)
    if len(pos) != 3:
        print(__doc__.split("\n\n")[1])
        return 2
    run, out, limits_path = (os.path.abspath(a) for a in pos)
    ll_dir = opts.get("--ll-dir") or os.environ.get("LIBRELANE_DIR") or os.path.join(ROOT, ".tools", "librelane")
    spec = __import__("tomllib").load(open(limits_path, "rb")).get("max_sum", {}).get(KEY)
    if not spec or len(spec.get("keys", [])) != 2:
        return finish([(False, f"limit: no [max_sum] {KEY} with two keys in {limits_path}")])
    lim, keys = spec["max"], spec["keys"]
    work = os.path.join(out, "ir_caravel")
    shutil.rmtree(work, ignore_errors=True)   # only this check's own output, before the run guard
    rows = ir_pattern.check_inputs(run, opts.get("--vcd") or [])
    if not all(ok for ok, _ in rows):
        return finish(rows)
    vcds = opts["--vcd"]
    steps = sorted((s for s in glob.glob(os.path.join(run, "[0-9]*-openroad-irdropreport*"))
                    if os.path.isfile(os.path.join(s, "state_out.json"))), key=lambda s: int(os.path.basename(s).split("-")[0]))
    if not steps:
        return finish(rows + [(False, f"no finished OpenROAD.IRDropReport step in {run}")])
    step = steps[-1]
    os.makedirs(work)
    cfg = json.load(open(os.path.join(step, "config.json")))
    state = json.load(open(os.path.join(step, "state_in.json")))
    r, vsrc = build(state["def"], os.path.join(work, "caravel.def"), os.path.join(work, "vsrc"))
    rows += r
    if vsrc is None or not all(ok for ok, _ in rows):
        return finish(rows)
    lefs = [cfg["TECH_LEFS"]["nom_*"]] + list(cfg.get("CELL_LEFS") or []) + list(cfg.get("EXTRA_LEFS") or []) \
        + [l for spec_ in (cfg.get("MACROS") or {}).values() for l in (spec_.get("lef") or [])]
    tcl = os.path.join(work, "mkodb.tcl")
    open(tcl, "w").write("".join(f"read_lef {l}\n" for l in lefs) + f"read_def {work}/caravel.def\nwrite_db {work}/caravel.odb\n")
    with open(os.path.join(work, "mkodb.log"), "w") as log:
        rc = subprocess.run(["nix-shell", "--run", f"openroad -exit -no_splash {tcl}"], cwd=ll_dir, stdout=log,
                            stderr=subprocess.STDOUT).returncode
    if rc != 0 or not os.path.isfile(os.path.join(work, "caravel.odb")):
        return finish(rows + [(False, f"ODB of the DEF with Caravel's network: rc {rc}, see {work}/mkodb.log")])
    state["odb"] = os.path.join(work, "caravel.odb")
    # 2. control: the run's own supply points on the new ODB reproduce the run's IR step exactly
    cstep = os.path.join(work, "control")
    os.makedirs(cstep)
    json.dump(cfg, open(os.path.join(cstep, "config.json"), "w"), indent=1)
    json.dump(state, open(os.path.join(cstep, "state_in.json"), "w"), indent=1)
    cmd = (f"python3 -m librelane.steps run --id OpenROAD.IRDropReport -c '{cstep}/config.json' "
           f"-i '{cstep}/state_in.json' -o '{cstep}/step'")
    with open(os.path.join(cstep, "console.log"), "w") as log:
        subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, stdout=log, stderr=subprocess.STDOUT)
    so = os.path.join(cstep, "step", "state_out.json")
    got = json.load(open(so)).get("metrics", {}) if os.path.isfile(so) else {}
    ref = json.load(open(os.path.join(step, "state_out.json"))).get("metrics", {})
    same = all(isinstance(got.get(k), (int, float)) and isinstance(ref.get(k), (int, float)) and ref.get(k) > 0
               and abs(got.get(k) - ref.get(k)) <= CONTROL_TOL * ref.get(k) for k in keys)
    rows.append((same, f"control: the run's supply points on the ODB with Caravel's network give "
                       f"{[got.get(k) for k in keys]} V, the run's IR step {[ref.get(k) for k in keys]} V "
                       f"(within {CONTROL_TOL:.1%})"))
    # 3. pad sources in the judged slow corners
    pstep = os.path.join(work, "pads")
    os.makedirs(pstep)
    pcfg = dict(cfg, VSRC_LOC_FILES=vsrc)
    json.dump(pcfg, open(os.path.join(pstep, "config.json"), "w"), indent=1)
    json.dump(state, open(os.path.join(pstep, "state_in.json"), "w"), indent=1)
    drops, info = {}, []
    for vcd in vcds + [None]:
        tag = "_" + os.path.splitext(os.path.basename(vcd))[0] if vcd else "_vectorless"
        for corner, voltage, ss_r in ir_worst.JUDGED:
            r, metrics = ir_worst.run_corner(pstep, corner, voltage, ss_r, os.path.join(work, "corners"), ll_dir,
                                             opts.get("--power"), vcd=vcd, tag=tag)
            vals = ir_worst.drop(metrics, keys) if metrics is not None else None
            if vals:
                r.append((True, f"{corner}{tag} drop from the pads: VDD {vals[0] * 1e3:.2f} + GND {vals[1] * 1e3:.2f} = "
                                f"{sum(vals) * 1e3:.2f} mV"))
            elif metrics is not None:
                r.append((False, f"{corner}{tag} drop: {[metrics.get(k) for k in keys]} (missing or negative)"))
            if vcd:
                rows += r
                if vals:
                    drops[corner + tag] = vals
            else:   # vectorless: recorded, not judged (ADR-0019 decision 20)
                info += [("" if ok else "not applied: ") + msg for ok, msg in r]
    results = os.path.join(work, "results.json")   # ir_pattern.py --judge re-applies a limit to it (neg_ir.py)
    ir_pattern.write_results(results, rows, drops, len(ir_pattern.WINDOWS) * len(ir_worst.JUDGED),
                             "from Caravel's pads (max-power pattern, slow corner)")
    return finish(ir_pattern.judge(json.load(open(results)), lim), info)


def finish(rows, info=()):
    for ok, msg in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    for msg in info:
        print(f"  [INFO] {msg}")
    ok = bool(rows) and all(r[0] for r in rows)
    print(f"ir-caravel: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
