#!/usr/bin/env python3
"""Independent check of the characterized SRAM .lib files (ADR-0010; Phase 3.5 review).

usage: check_char_lib.py <char.json> <char_dir> [--no-confirm]

gen_char_lib.py --check only compares the .lib with what the same program makes again, so an error
in its formulas passes (Phase 3.5 review: rows flattened to the minimum instead of the maximum, the
placeholder hold arc not taken as the minimum, x1.6 or x0.9 left out: N5-N8 and --check all PASS).
This script does not import gen_char_lib.py. From char.json it recomputes every number that
gen_char_lib.py writes, with the user decisions of ADR-0010 written out again below, and compares
them with the numbers it parses from each <char_dir>/<macro>__<pvt>.lib:
  values      operating conditions and library name; CELL_TABLE / CONSTRAINT_TABLE indices; dout0
              falling_edge delays (each slew row: largest settle time over the loads x PARASITIC,
              the table lifted so its smallest entry is the floor) and transitions; the dout0
              rising_edge (hold) arc (each row: earliest change over the loads x HOLD_ARC_SCALE;
              for a placeholder PVT, the earliest over all characterized PVTs); setup and hold of
              the five port 0 inputs, rise and fall (measured + CONSTRAINT_ADD, at least the floor);
              clk0 min_pulse_width and minimum_period; dout0 max_capacitance; addr0/wmask0
              max_transition. Each of these timing groups must appear exactly once per pin.
  provenance  char.json was made from the pinned PDK's schematic netlist (sha256 of the file under
              the SKY130_PDK_HASH version of env/versions.mk), with ngspice >= NGSPICE_MIN, the trim
              of rows 0/127 and the columns of bits 0 and 31 (1264 bitcells kept), and the settings
              of characterize.py (step, resolution, slews, loads, periods, ranges); each record is
              the PVT it is filed under; only the PVTs of PLACEHOLDER may be read_fail.
  confirm     <char_dir>/confirm.json (confirm_char_lib.py) simulated every setup/hold lane and the
              three clock pulse lanes of each characterized PVT at exactly the values of its .lib,
              all passed, and was made from this char.json (sha256): a bisection checks
              monotonicity only at the points it probed (Phase 3.5 review).
Prints one row per check and `check_char_lib: PASS` / `check_char_lib: FAIL`; exit 0 only on PASS.
"""
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MACRO = "sky130_sram_2kbyte_1rw1r_32x512_8"

# ADR-0010 user decisions (2026-10-05), written out here on purpose, not imported from gen_char_lib.py.
PARASITIC, CONSTRAINT_ADD, HOLD_ARC_SCALE, DOUT_TRANSITION, INPUT_MAX_TRANSITION = 1.6, 0.10, 0.9, 0.5, 0.5
FLOOR = {"dout": 10.0, "setup": 1.0, "hold": 0.5, "minimum_period": 30.0, "min_pulse_width": 12.0}
DOUT_FLOOR_SCALE = {"ss": 1.5, "tt": 1.0, "ff": 1.0}
PLACEHOLDER = {"ss_n40C_1v60": "ss_100C_1v60"}
PVT_COND = {"tt_025C_1v80": ("tt", 1.80, 25.0), "ss_100C_1v60": ("ss", 1.60, 100.0),
            "ff_n40C_1v95": ("ff", 1.95, -40.0), "ss_n40C_1v60": ("ss", 1.60, -40.0),
            "ff_100C_1v95": ("ff", 1.95, 100.0)}
INPUTS = ("din0", "addr0", "wmask0", "csb0", "web0")
TRIM = {"kept": 1264, "dropped": 128 * 128 - 1264, "rows": [0, 127], "columns": [0, 1, 2, 3, 124, 125, 126, 127]}
TOL = 6e-5          # the .lib prints 4 decimals


# ---------------------------------------------------------------- a small Liberty reader

GROUP = re.compile(r'\s*(?:(\w+)\s*\(([^)]*)\)\s*\{|(\w+)\s*\(([^)]*)\)\s*;|(\w+)\s*:\s*([^;{}]*?)\s*;|(\}))', re.S)


def parse(text):
    """Liberty text -> nested {"type", "name", "attrs", "children"}; complex attributes such as
    values(...) are kept as their raw argument text."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S).replace("\\\n", " ")
    root = {"type": "", "name": "", "attrs": {}, "children": []}
    stack, pos = [root], 0
    while True:
        m = GROUP.match(text, pos)
        if not m:
            if text[pos:].strip():
                raise ValueError(f"cannot parse the .lib near {text[pos:pos + 60]!r}")
            break
        if m.group(1):
            node = {"type": m.group(1), "name": m.group(2).strip().strip('"'), "attrs": {}, "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)
        elif m.group(3):
            stack[-1]["attrs"][m.group(3)] = m.group(4)
        elif m.group(5):
            stack[-1]["attrs"][m.group(5)] = m.group(6).strip().strip('"')
        else:
            stack.pop()
            if not stack:
                raise ValueError("unbalanced braces in the .lib")
        pos = m.end()
    if len(stack) != 1:
        raise ValueError("unbalanced braces in the .lib")
    return root


def numbers(raw):
    return [[float(x) for x in row.split(",")] for row in re.findall(r'"([^"]*)"', raw)]


def walk(node):
    yield node
    for c in node["children"]:
        yield from walk(c)


def find(node, typ, name=None):
    return [n for n in walk(node) if n["type"] == typ and (name is None or n["name"] == name)]


def timings(node):
    """{timing_type: [timing groups]} below node."""
    out = {}
    for t in find(node, "timing"):
        out.setdefault(t["attrs"].get("timing_type", "").strip('"'), []).append(t)
    return out


def table(group, sub):
    gs = [c for c in group["children"] if c["type"] == sub]
    if len(gs) != 1 or "values" not in gs[0]["attrs"]:
        raise ValueError(f"{len(gs)} {sub} groups with values")
    return numbers(gs[0]["attrs"]["values"])


def lib_values(path):
    """The numbers of one characterized .lib that check_char_lib.py and confirm_char_lib.py use."""
    root = parse(open(path, encoding="utf-8").read())
    libs = find(root, "library")
    if len(libs) != 1:
        raise ValueError(f"{len(libs)} library groups")
    lib = libs[0]
    oc = find(lib, "operating_conditions")
    tmpl = {t["name"]: t for t in find(lib, "lu_table_template")}
    v = {"library": lib["name"], "voltage": float(oc[0]["attrs"]["voltage"]) if len(oc) == 1 else None,
         "temperature": float(oc[0]["attrs"]["temperature"]) if len(oc) == 1 else None,
         "cell_index": [numbers(tmpl["CELL_TABLE"]["attrs"][k])[0] for k in ("index_1", "index_2")],
         "constraint_index": [numbers(tmpl["CONSTRAINT_TABLE"]["attrs"][k])[0] for k in ("index_1", "index_2")],
         "setup": {}, "hold": {}, "problems": []}
    cell = find(lib, "cell")
    if len(cell) != 1:
        raise ValueError(f"{len(cell)} cell groups")
    pins = {c["name"]: c for c in cell[0]["children"] if c["type"] in ("bus", "pin")}
    for p in INPUTS:
        ts = timings(pins[p])
        for kind, key in (("setup_rising", "setup"), ("hold_rising", "hold")):
            if len(ts.get(kind, [])) != 1:
                v["problems"].append(f"{p}: {len(ts.get(kind, []))} {kind} groups")
                continue
            v[key][p] = {rf: table(ts[kind][0], f"{rf}_constraint") for rf in ("rise", "fall")}
    dts = timings(pins["dout0"])
    for kind, key in (("falling_edge", "dout_fall"), ("rising_edge", "dout_rise")):
        if len(dts.get(kind, [])) != 1:
            v["problems"].append(f"dout0: {len(dts.get(kind, []))} {kind} groups")
            continue
        v[key] = {g: table(dts[kind][0], g) for g in ("cell_rise", "cell_fall", "rise_transition", "fall_transition")}
    v["dout_max_capacitance"] = float(pins["dout0"]["attrs"].get("max_capacitance", "nan"))
    v["max_transition"] = {p: float(pins[p]["attrs"].get("max_transition", "nan")) for p in ("addr0", "wmask0")}
    cts = timings(pins["clk0"])
    for kind in ("min_pulse_width", "minimum_period"):
        if len(cts.get(kind, [])) != 1:
            v["problems"].append(f"clk0: {len(cts.get(kind, []))} {kind} groups")
            continue
        v[kind] = {rf: table(cts[kind][0], f"{rf}_constraint")[0][0] for rf in ("rise", "fall")}
    return v


# ---------------------------------------------------------------- expected numbers from char.json

def expected(doc, pvt):
    model, vdd, temp = PVT_COND[pvt]
    rec = doc["pvts"][pvt]
    if "read_fail" in rec:
        src = doc["pvts"][PLACEHOLDER[pvt]]
        hold_from = [r for r in doc["pvts"].values() if "read_fail" not in r]
    else:
        src, hold_from = rec, [rec]
    rows = [max(r) * PARASITIC for r in src["delay"]["settle_max"]]
    lift = max(0.0, FLOOR["dout"] * DOUT_FLOOR_SCALE[model] - min(rows))
    nl = len(doc["loads_pf"])
    hold_rows = [min(min(r["delay"]["depart_min"][i]) for r in hold_from) * HOLD_ARC_SCALE
                 for i in range(len(doc["clk_slews_ns"]))]
    cons, pulse = src["constraints"], src["pulse"]
    e = {"library": f"{MACRO}__{pvt}", "voltage": vdd, "temperature": temp,
         "cell_index": [doc["clk_slews_ns"], doc["loads_pf"]],
         "constraint_index": [doc["clk_slews_ns"], doc["clk_slews_ns"]],
         "dout_fall": {"cell_rise": [[x + lift] * nl for x in rows], "cell_fall": [[x + lift] * nl for x in rows],
                       "rise_transition": [[DOUT_TRANSITION] * nl for _ in rows],
                       "fall_transition": [[DOUT_TRANSITION] * nl for _ in rows]},
         "dout_rise": {"cell_rise": [[x] * nl for x in hold_rows], "cell_fall": [[x] * nl for x in hold_rows],
                       "rise_transition": [[DOUT_TRANSITION] * nl for _ in rows],
                       "fall_transition": [[DOUT_TRANSITION] * nl for _ in rows]},
         "dout_max_capacitance": max(doc["loads_pf"]),
         "max_transition": {p: INPUT_MAX_TRANSITION for p in ("addr0", "wmask0")},
         "min_pulse_width": {"rise": max(FLOOR["min_pulse_width"], pulse["pulse_high"]["pass"] * PARASITIC),
                             "fall": max(FLOOR["min_pulse_width"], pulse["pulse_low"]["pass"] * PARASITIC)},
         "minimum_period": {rf: max(FLOOR["minimum_period"], pulse["pulse_period"]["pass"] * PARASITIC)
                            for rf in ("rise", "fall")}}
    ns = len(doc["clk_slews_ns"])
    for key in ("setup", "hold"):
        e[key] = {p: {rf: [[max(FLOOR[key], cons[f"{p[:-1]}_{key}_{rf}"]["pass"] + CONSTRAINT_ADD)] * ns] * ns
                      for rf in ("rise", "fall")} for p in INPUTS}
    return e


def diff(want, have, path=""):
    """Paths where two nested structures of numbers differ (beyond TOL)."""
    if isinstance(want, dict):
        if not isinstance(have, dict):
            return [f"{path}: missing"]
        out = []
        for k in want:
            out += diff(want[k], have.get(k), f"{path}.{k}" if path else k) if k in have else [f"{path}.{k}: missing"]
        return out
    if isinstance(want, list):
        if not isinstance(have, list) or len(want) != len(have):
            return [f"{path}: shape {have!r:.40} != {len(want)} entries"]
        return [x for i, (a, b) in enumerate(zip(want, have)) for x in diff(a, b, f"{path}[{i}]")]
    if isinstance(want, str):
        return [] if want == have else [f"{path}: {have!r} != {want!r}"]
    if have is None or not math.isfinite(have) or abs(have - want) > TOL:
        return [f"{path}: {have} != {want:.4f}"]
    return []


# ---------------------------------------------------------------- provenance

def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise KeyError(name)


def provenance(doc):
    sys.path.insert(0, HERE)
    import characterize as ch
    out = []
    pdk_root = os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel"))
    net = os.path.realpath(os.path.join(pdk_root, pin("PDK"), "libs.ref", "sky130_sram_macros", "spice", MACRO + ".spice"))
    if f"/versions/{pin('SKY130_PDK_HASH')}/" not in net or not os.path.isfile(net):
        out.append(f"PDK netlist {net} missing or not PDK version {pin('SKY130_PDK_HASH')[:12]}")
    elif doc.get("netlist_sha256") != hashlib.sha256(open(net, "rb").read()).hexdigest():
        out.append(f"netlist_sha256 {str(doc.get('netlist_sha256'))[:12]} is not the PDK netlist's")
    want = {"macro": MACRO, "netlist": "schematic", "pdk": pin("SKY130_PDK_HASH"), "trim": TRIM}
    settings = {"tstep": ch.TSTEP, "tmax": ch.TMAX, "resolution_ns": ch.RESOLUTION, "clk_slews_ns": ch.CLK_SLEWS,
                "loads_pf": ch.LOADS, "clk_slew_mid_ns": ch.CLK_SLEW_MID, "in_slew_ns": ch.IN_SLEW,
                "period_ns": ch.PERIOD, "constraint_period_ns": ch.CONS_PERIOD, "brackets_ns": ch.BRACKET,
                "seed_half_width_ns": ch.SEED_HALF_WIDTH}
    want.update(json.loads(json.dumps(settings)))
    out += [f"{k} = {doc.get(k)!r:.60} (expected {v!r:.60})" for k, v in want.items() if doc.get(k) != v]
    try:
        if int(doc.get("ngspice")) < int(pin("NGSPICE_MIN")):
            out.append(f"ngspice {doc.get('ngspice')} < NGSPICE_MIN {pin('NGSPICE_MIN')}")
    except (TypeError, ValueError):
        out.append(f"ngspice version {doc.get('ngspice')!r} is not a number")
    if set(doc.get("pvts", {})) != set(PVT_COND):
        out.append(f"PVTs {sorted(doc.get('pvts', {}))} != {sorted(PVT_COND)}")
    for p, r in doc.get("pvts", {}).items():
        if p in PVT_COND and (r.get("pvt"), r.get("model"), r.get("vdd"), r.get("temp")) != (p, *PVT_COND[p]):
            out.append(f"record filed under {p} is {r.get('pvt')} ({r.get('model')}, {r.get('vdd')} V, {r.get('temp')} C)")
        if "read_fail" in r and p not in PLACEHOLDER:
            out.append(f"{p} is read_fail but has no placeholder source")
    return out


# ---------------------------------------------------------------- confirmation simulations

def confirm_problems(doc_path, doc, char_dir, have):
    sys.path.insert(0, HERE)
    import characterize as ch
    path = os.path.join(char_dir, "confirm.json")
    if not os.path.isfile(path):
        return [f"{path} missing (run confirm_char_lib.py)"]
    c = json.load(open(path))
    out = []
    if c.get("char_json_sha256") != hashlib.sha256(open(doc_path, "rb").read()).hexdigest():
        out.append("confirm.json was made from another char.json")
    want_pvts = sorted(p for p, r in doc["pvts"].items() if "read_fail" not in r)
    if sorted(c.get("pvts", {})) != want_pvts:
        out.append(f"confirm.json PVTs {sorted(c.get('pvts', {}))} != characterized {want_pvts}")
    for p in want_pvts:
        r, v = c.get("pvts", {}).get(p, {}), have.get(p)
        if v is None:
            continue
        lanes = {}
        for n in ch.LANES:
            g, kind, rf = n.split("_")
            lanes[n] = v[kind][g + "0"][rf][0][0]
        lanes.update({"pulse_high": v["min_pulse_width"]["rise"], "pulse_low": v["min_pulse_width"]["fall"],
                      "pulse_period": v["minimum_period"]["rise"]})
        got = r.get("lanes", {})
        out += [f"{p} {n}: confirmed at {got.get(n)}, .lib {x}" for n, x in lanes.items()
                if not isinstance(got.get(n), (int, float)) or abs(got[n] - x) > TOL]
        failed = [n for n in lanes if r.get("pass", {}).get(n) is not True]
        if failed:
            out.append(f"{p}: not passed at the .lib values: {', '.join(failed[:4])}")
    return out


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2 or set(argv) - set(args) - {"--no-confirm"}:
        print(__doc__)
        return 2
    doc_path, char_dir = args
    doc = json.load(open(doc_path))
    rows = []

    def row(name, problems, ok_msg):
        rows.append(not problems)
        print(f"  [{'FAIL' if problems else 'PASS'}] {name}: "
              + (f"{len(problems)} problem(s): {'; '.join(problems[:4])}" if problems else ok_msg))

    prov = provenance(doc)
    row("provenance", prov, "pinned PDK netlist, ngspice, trim and characterize.py settings; records match their PVTs")
    have = {}
    for p in PVT_COND:
        f = os.path.join(char_dir, f"{MACRO}__{p}.lib")
        try:
            have[p] = lib_values(f)
            problems = have[p].pop("problems") + diff(expected(doc, p), have[p])
        except (OSError, ValueError, KeyError, TypeError) as e:
            problems = [f"{os.path.basename(f)}: {e}"]
        row(f"values {p}", problems, "every number matches the ADR-0010 formulas recomputed from char.json"
            + (" (placeholder)" if "read_fail" in doc["pvts"].get(p, {}) else ""))
    if "--no-confirm" not in argv:
        row("confirm", confirm_problems(doc_path, doc, char_dir, have),
            "every setup/hold and pulse lane passed in simulation at the .lib values")
    ok = all(rows)
    print(f"check_char_lib: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
