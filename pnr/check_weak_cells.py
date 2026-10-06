#!/usr/bin/env python3
"""Weak-cell check for a LibreLane flow: no cell the resizer may use is too weak to drive one buffer
within the slew limit of a design-repair step (drv-timing-closure rule 10, docs/notes/repair_design_loop.md).

usage: check_weak_cells.py <config.json or resolved.json> --pdk-dir <.../sky130A> [--design-dir D] [--scl sky130_fd_sc_hd]

Why (OpenROAD dcf36133, src/rsz/src/RepairDesign.cc): when a driver's own slew violates the limit,
repair_design first resizes it (repairDriverSlew) and judges the candidate sizes with the first
.lib read, not the corner of the violation (Phase 5 experiment D), so in a slow corner it can pick a
weaker size. If the driver still violates, the net's capacitance limit becomes the load at which the
driver's slew equals the limit (1107-1115); the wire repair cuts the wire at
max((limit - downstream cap) / wire cap, 0) (1527-1528), and after a buffer is inserted the downstream
cap is that buffer's input cap. When the limit is not above it, every cut is 0 and repairNetWire
inserts buffers at the same point forever (Phase 5: 92.9 GB). sky130's no_synth.cells keeps cells out
of synthesis only; the resizer still uses them (a2111oi_1).

Check, for the PVT of every resizer corner (RSZ_CORNERS, else STA_CORNERS; the LIB entry whose key
matches the corner name) and every design-repair step that runs (RepairDesignPostGPL with
DESIGN_REPAIR_MAX_SLEW_PCT; RepairDesignPostGRT with GRT_DESIGN_REPAIR_MAX_SLEW_PCT when
RUN_POST_GRT_DESIGN_REPAIR is true):
  max transition  min(set_max_transition of PNR_SDC_FILE, else MAX_TRANSITION_CONSTRAINT; the output
                  pin's max_transition, else the library's default_max_transition)
  limit           max transition x (1 - margin / 100)
  load            input capacitance of the weakest buffer the resizer may insert: the smallest pin A
                  capacitance among buf_N / clkbuf_N cells with the smallest N that are not excluded
                  (Phase 5 inserted clkbuf_1)
  input slew      the max transition (the slew repair_design annotates on violating inputs) and the
                  smallest table index; the larger output transition is used
Every cell with an output pin that is not excluded (PNR_EXCLUDED_CELL_FILE, default the PDK's
libs.tech/openlane/<scl>/drc_exclude.cells as in libs.tech/openlane/config.tcl line 103;
EXTRA_EXCLUDED_CELLS; both are wildcards) must have an output transition (largest over rise and fall
of every arc that is not a timing check or a tristate enable/disable, NLDM tables interpolated,
extrapolated linearly at the edges) at that load not above the limit. A cell that FAILs here is a
necessary condition for the endless loop, not a sufficient one (Phase 4's PicoRV32 run had an
a2111oi_1 from RepairDesignPostGRT and finished); the fix is to add it to EXTRA_EXCLUDED_CELLS or to
use a smaller margin.
Prints one row per step and PVT, then `weak-cells: PASS` / `weak-cells: FAIL`; exit code 0 only on
PASS. Python stdlib only.
"""
import argparse
import bisect
import fnmatch
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resolve(v, design_dir, pdk_dir):
    if not isinstance(v, str):
        return v
    if v.startswith("dir::"):
        return os.path.normpath(os.path.join(design_dir, v[len("dir::"):]))
    if v.startswith("pdk_dir::"):
        return os.path.normpath(os.path.join(pdk_dir, v[len("pdk_dir::"):]))
    return v


def braces(text):
    """{index of '{': index of the matching '}'} for the whole file, in one pass."""
    match, stack = {}, []
    for m in re.finditer(r"[{}]", text):
        if m.group(0) == "{":
            stack.append(m.start())
        else:
            match[stack.pop()] = m.start()
    return match


def floats(s):
    return [float(x) for x in re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", s)]


def groups(text, start, end, kind, match):
    """(name, body start, body end) of every `kind ("name") {` group directly inside text[start:end]."""
    out, pos = [], start
    rx = re.compile(r"\b" + kind + r'\s*\(\s*"?([^")]*)"?\s*\)\s*\{')
    while True:
        m = rx.search(text, pos, end)
        if not m:
            return out
        close = match[m.end() - 1]
        out.append((m.group(1), m.end(), close))
        pos = close + 1


def table(body):
    """(index_1, index_2, values) of an NLDM table body, or None (scalar or one-dimensional)."""
    i1 = re.search(r'index_1\s*\(\s*"([^"]*)"', body)
    i2 = re.search(r'index_2\s*\(\s*"([^"]*)"', body)
    vals = re.search(r"values\s*\((.*?)\)\s*;", body, re.S)
    if not (i1 and i2 and vals):
        return None
    rows = [floats(r) for r in re.findall(r'"([^"]*)"', vals.group(1))]
    return floats(i1.group(1)), floats(i2.group(1)), rows


def interp(tab, x1, x2):
    i1, i2, v = tab

    def seg(ix, x):
        j = max(1, min(len(ix) - 1, bisect.bisect_left(ix, x)))
        return j - 1, j, (x - ix[j - 1]) / (ix[j] - ix[j - 1])
    a0, a1, ta = seg(i1, x1)
    b0, b1, tb = seg(i2, x2)
    return (v[a0][b0] * (1 - ta) * (1 - tb) + v[a1][b0] * ta * (1 - tb)
            + v[a0][b1] * (1 - ta) * tb + v[a1][b1] * ta * tb)


def parse_lib(path):
    """{cell: {"pins_in_cap": {pin: cap}, "out": [(pin, max_transition or None, [tables])]}},
    default_max_transition, variable order of the transition templates."""
    text = open(path, encoding="utf8").read()
    match = braces(text)
    lib = groups(text, 0, len(text), "library", match)[0]
    dmt = re.search(r"default_max_transition\s*:\s*([0-9.eE+-]+)", text[lib[1]:lib[2]])
    templates = {}
    for name, s, e in groups(text, lib[1], lib[2], "lu_table_template", match):
        v1 = re.search(r'variable_1\s*:\s*"?(\w+)', text[s:e])
        templates[name] = v1.group(1) if v1 else None
    cells = {}
    for cname, cs, ce in groups(text, lib[1], lib[2], "cell", match):
        info = {"in_cap": {}, "out": []}
        for pname, ps, pe in groups(text, cs, ce, "pin", match):
            head = text[ps:pe]
            direction = re.search(r'\bdirection\s*:\s*"?(\w+)', head)
            if not direction:
                continue
            if direction.group(1) == "input":
                cap = re.search(r"\bcapacitance\s*:\s*([0-9.eE+-]+)", head)
                if cap:
                    info["in_cap"][pname] = float(cap.group(1))
                continue
            if direction.group(1) != "output":
                continue
            mt = re.search(r"\bmax_transition\s*:\s*([0-9.eE+-]+)", head)
            tabs = []
            for _, ts, te in groups(text, ps, pe, "timing", match):
                body = text[ts:te]
                tt = re.search(r'timing_type\s*:\s*"?(\w+)', body)
                if tt and re.match(r"(setup|hold|recovery|removal|min_pulse|skew|nochange|three_state)", tt.group(1)):
                    continue
                for kind in ("rise_transition", "fall_transition"):
                    for tname, ks, ke in groups(text, ts, te, kind, match):
                        t = table(text[ks:ke])
                        if t is None:
                            continue
                        if templates.get(tname) not in (None, "input_net_transition"):
                            t = (t[1], t[0], [list(r) for r in zip(*t[2])])  # index_1 = load: transpose
                        tabs.append(t)
            info["out"].append((pname, float(mt.group(1)) if mt else None, tabs))
        cells[cname] = info
    return cells, float(dmt.group(1)) if dmt else None


def sdc_max_transition(path):
    if not path or not os.path.isfile(path):
        return None
    vals = re.findall(r"^\s*set_max_transition\s+([0-9.eE+-]+)\s+\[current_design\]", open(path, encoding="utf8").read(), re.M)
    return float(vals[-1]) if vals else None


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config")
    ap.add_argument("--pdk-dir", required=True, help="the PDK variant directory, e.g. ~/.ciel/sky130A")
    ap.add_argument("--design-dir", default=ROOT)
    ap.add_argument("--scl", default="sky130_fd_sc_hd")
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config, encoding="utf8"))
    get = lambda k: resolve(cfg.get(k), a.design_dir, a.pdk_dir)  # noqa: E731
    rows = []

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    excl_file = get("PNR_EXCLUDED_CELL_FILE") or os.path.join(a.pdk_dir, "libs.tech", "openlane", a.scl, "drc_exclude.cells")
    if not os.path.isfile(excl_file):
        print(f"  [FAIL] inputs: PNR_EXCLUDED_CELL_FILE {excl_file} not found\nweak-cells: FAIL")
        return 1
    patterns = [ln.strip() for ln in open(excl_file, encoding="utf8") if ln.strip() and not ln.lstrip().startswith("#")]
    patterns += list(cfg.get("EXTRA_EXCLUDED_CELLS") or [])
    excluded = lambda c: any(fnmatch.fnmatchcase(c, p) for p in patterns)  # noqa: E731

    sdc_mt = sdc_max_transition(get("PNR_SDC_FILE"))
    if sdc_mt is None and cfg.get("MAX_TRANSITION_CONSTRAINT") is not None:
        sdc_mt = float(cfg["MAX_TRANSITION_CONSTRAINT"])
    steps = []
    for step, key, run_key in (("RepairDesignPostGPL", "DESIGN_REPAIR_MAX_SLEW_PCT", None),
                               ("RepairDesignPostGRT", "GRT_DESIGN_REPAIR_MAX_SLEW_PCT", "RUN_POST_GRT_DESIGN_REPAIR")):
        if run_key and not cfg.get(run_key):
            continue
        if cfg.get(key) is None:
            print(f"  [FAIL] inputs: {key} is not set in {os.path.basename(a.config)} (the check does not assume LibreLane's default)\nweak-cells: FAIL")
            return 1
        steps.append((step, key, float(cfg[key])))
    if sdc_mt is None:
        print("  [FAIL] inputs: no set_max_transition in PNR_SDC_FILE and no MAX_TRANSITION_CONSTRAINT\nweak-cells: FAIL")
        return 1

    corners = cfg.get("RSZ_CORNERS") or cfg.get("STA_CORNERS") or []
    libmap = cfg.get("LIB") or {}
    libs = {}
    for c in corners:
        keys = [k for k in libmap if fnmatch.fnmatchcase(c, k)]
        paths = [resolve(p, a.design_dir, a.pdk_dir) for k in keys for p in libmap[k]]
        paths = [p for p in paths if os.path.basename(p).startswith(a.scl + "__")]
        if len(paths) != 1:
            print(f"  [FAIL] inputs: corner {c} matches {len(paths)} {a.scl} .lib in LIB ({keys})\nweak-cells: FAIL")
            return 1
        libs[paths[0]] = libs.get(paths[0], []) + [c]
    if not libs:
        print("  [FAIL] inputs: no resizer corner (RSZ_CORNERS / STA_CORNERS)\nweak-cells: FAIL")
        return 1

    for path, cs in sorted(libs.items()):
        cells, dmt = parse_lib(path)
        bufs = {}
        for name, info in cells.items():
            m = re.fullmatch(re.escape(a.scl) + r"__(?:clk)?buf_(\d+)", name)
            if m and not excluded(name) and "A" in info["in_cap"]:
                bufs.setdefault(int(m.group(1)), []).append((info["in_cap"]["A"], name))
        if not bufs:
            row(os.path.basename(path), False, "no buf_N / clkbuf_N cell left after the exclusions")
            continue
        load, buf = min(bufs[min(bufs)])
        allowed = [n for n in cells if not excluded(n) and cells[n]["out"]]
        for step, key, margin in steps:
            worst = []
            for name in allowed:
                for pin, pin_mt, tabs in cells[name]["out"]:
                    if not tabs:
                        continue
                    mt = min(x for x in (sdc_mt, pin_mt if pin_mt is not None else dmt) if x is not None)
                    limit = mt * (1 - margin / 100)
                    s = max(interp(t, sin, load) for t in tabs for sin in (min(t[0]), mt))
                    if s > limit:
                        worst.append((s, f"{name.replace(a.scl + '__', '')}/{pin} {s:.3f}"))
            pvt = os.path.basename(path)[len(a.scl) + 2:-len(".lib")]
            row(f"{step} {pvt}", not worst,
                f"{len(allowed)} cells, {key} {margin:g}% -> limit {sdc_mt * (1 - margin / 100):.3f} ns, load = {buf.replace(a.scl + '__', '')} "
                f"input {load:.4f} pF; corners {', '.join(cs)}: "
                + ("no cell above the limit" if not worst else
                   "above the limit (add to EXTRA_EXCLUDED_CELLS or lower the margin): "
                   + ", ".join(w for _, w in sorted(worst, reverse=True))))
    ok = all(rows) and rows
    print(f"weak-cells: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
