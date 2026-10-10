#!/usr/bin/env python3
"""Write one .lib per PVT for the SRAM macro from the SPICE characterization (ADR-0010).

usage: gen_char_lib.py <char.json> <pdk TT .lib> <out_dir> [--check] [--power <power.json>]
  --check   exit 1 if any <out_dir>/<macro>__<pvt>.lib differs from what would be generated
  --power   internal power and leakage measured by power.py (ADR-0018 decision 10) instead of the template's:
            clk0 "!csb0 & !web0" = write, "!csb0 & web0" = read, "csb0 & ..." = idle (csb0=1); clk1 "csb1" =
            clk1 idle; clk1 "!csb1" (a port 1 read: never in the SoC, not measured) = the port 0 read;
            leakage_power value and cell_leakage_power = leakage. The PVT's measured record (untrimmed netlist,
            ADR-0018 decision 11).
<char.json> must hold exactly the five PVTs of sramchar.PVTS.

The PDK .lib (OpenRAM analytical model, port 0 and port 1) is the template: pins, capacitances,
power and memory groups are copied. The numbers follow the user decision of 2026-10-05 (ADR-0010):
the schematic netlist has no layout parasitics (they made the read about 42-65 % slower in the
bitcell-annotated test), so every limit is the more conservative of the ADR-0007 padded.lib
value (FLOOR) and the characterized value with a parasitic allowance. For each PVT:
  library name, operating conditions, nominal voltage/temperature, VCCD1 voltage map
  CELL_TABLE / CONSTRAINT_TABLE indices  -> the characterized clk0 slews and dout0 loads
  dout0 falling_edge cell_rise/cell_fall -> settle_max x PARASITIC, each row (clk0 slew) set to its
                                            largest value over the loads, then the whole table shifted
                                            up so its smallest entry is at least FLOOR dout (x PVT_FLOOR_SCALE)
        rise/fall_transition             -> DOUT_TRANSITION (user decision: the schematic, 1.1-1.3 ns,
                                            and the annotated test, 0.23-0.28 ns, disagree 5x)
  dout0 rising_edge arc (new)            -> depart_min x HOLD_ARC_SCALE, each row set to its smallest
                                            value over the loads: the data of the previous read starts
                                            to change this long after the rising edge (the annotated
                                            test changes later, so this is the early side)
  Why no load slope: settle_max is when dout enters the valid band, not an RC delay; at ss it jumps
  1.3 ns from 5 to 20 fF. As a load slope it reads as a 60-140 kOhm driver and OpenROAD's
  repair_design kept buffering the dout0 nets (Phase 3.5 harden-soc 1: 75 minutes, then the step
  ended with an error; the same step finished in 98 s with a flat table). Within the characterized
  loads (max_capacitance) the row maximum bounds the delay from above and the row minimum bounds
  the earliest change from below.
  setup_rising / hold_rising of din0 addr0 wmask0 csb0 web0
                                         -> max(FLOOR, first passing offset + CONSTRAINT_ADD) (rise/fall)
  clk0 minimum_period / min_pulse_width  -> max(FLOOR, first passing value x PARASITIC)
  dout0 max_capacitance                  -> the largest characterized load
  addr0 / wmask0 max_transition          -> INPUT_MAX_TRANSITION
Port 1 (addr1 csb1 clk1 dout1) keeps the template's analytical numbers: the SoC ties it off and STA
has no clock on clk1. The template's internal_power values must be in (0, POWER_MAX]. Each kind of change must hit the expected number of places, counted per pin
and per rise/fall (a total over the five pins let one pin lose its setup arc while another got two),
else FAIL. Before that, char.json must be sound: each record is the PVT it is filed under (model,
VDD, temperature of sramchar.PVTS), and every number used is finite, delays and pulses > 0, and each
search result has pass > fail by at most resolution_ns (a NaN went through max() as the floor).
gen_char_lib.py --check compares with its own output only; check_char_lib.py recomputes the numbers
independently.
A PVT recorded as read_fail (the macro does not read correctly there in simulation) gets a
PLACEHOLDER .lib (user decision 2026-10-05): the numbers of PLACEHOLDER_FROM[pvt] with the
operating conditions of the PVT, and as hold arc the earliest change over all characterized PVTs.
It only lets STA keep timing the logic around the SRAM at that PVT; the header says so.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sramchar as sc  # noqa: E402

# docs/decisions/0010-sram-spice-characterization.md (user decisions 2026-10-05).
PARASITIC = 1.6              # x on measured delays and pulse widths (layout parasitics are not simulated)
CONSTRAINT_ADD = 0.10        # ns added to measured setup and hold
HOLD_ARC_SCALE = 0.9         # x on the earliest change of dout0 after the rising edge
DOUT_TRANSITION = 0.5        # ns, dout0 rise/fall transition (= padded.lib)
FLOOR = {"dout": 10.0, "setup": 1.0, "hold": 0.5, "minimum_period": 30.0, "min_pulse_width": 12.0}   # padded.lib
PVT_FLOOR_SCALE = {"ss": 1.5, "tt": 1.0, "ff": 1.0}   # ADR-0007: ss late delay x1.5 (OCV now comes from base.sdc)
INPUT_MAX_TRANSITION = 0.5   # ns, addr0/wmask0 pin limit (= the .lib's default_max_transition)
PORT0_INPUTS = ("din0", "addr0", "wmask0", "csb0", "web0")
PLACEHOLDER_FROM = {"ss_n40C_1v60": "ss_100C_1v60"}   # read_fail PVT -> characterized PVT (same model)
NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
# The template's internal_power values (analytical, ADR-0007 limitation 3) go unchanged into every .lib and the
# IR-drop analysis. OpenRAM dev 3608704c writes 1.04e+11 (the PDK macro 13.8): refuse anything above this
# (ADR-0018, ip/sram/openram/lib_template.py; negative test neg_openram.py L1).
POWER_MAX = 1000.0


def power_problems(src):
    """Template internal_power values that are not finite numbers in (0, POWER_MAX]."""
    import math
    vals = re.findall(r"(?:rise|fall)_power\s*\(\s*scalar\s*\)\s*\{\s*values\(\"(" + NUM + r")", src)
    if not vals:
        return ["no internal_power values in the template"]
    bad = sorted({v for v in vals if not (math.isfinite(float(v)) and 0 < float(v) <= POWER_MAX)})
    return [f"internal_power {', '.join(bad[:3])} outside (0, {POWER_MAX:g}]"] if bad else []


def fmt(x):
    return f"{x:.4f}"


def table(rows):
    return ("values(" + ",\\\n                   ".join('"' + ", ".join(fmt(x) for x in r) + '"' for r in rows) + ");")


def block_end(text, open_idx):
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit("gen_char_lib: FAIL - unbalanced braces")


def set_values(block, group, rows):
    """Replace the values(...) of `group(...) { ... }` inside block (exactly one such group)."""
    ms = list(re.finditer(r"\b" + group + r"\s*\([^)]*\)\s*\{", block))
    if len(ms) != 1:
        raise SystemExit(f"gen_char_lib: FAIL - {len(ms)} {group} groups in a timing block")
    end = block_end(block, ms[0].end() - 1)
    sub = block[ms[0].start():end]
    sub2, n = re.subn(r"values\((?:[^()]|\n)*?\)\s*;", lambda _: table(rows), sub)
    if n != 1:
        raise SystemExit(f"gen_char_lib: FAIL - {group}: {n} values()")
    return block[:ms[0].start()] + sub2 + block[end:]


def const(v, n1, n2):
    return [[v] * n2 for _ in range(n1)]


REQUIRED = {"delay": ("settle_max", "depart_min"), "constraints": None, "pulse": None}


def missing(doc, pvt):
    """What transform() needs from the characterization of pvt and does not find."""
    import characterize as ch
    r, out = doc["pvts"][pvt], []
    if "read_fail" in r:
        src = PLACEHOLDER_FROM.get(pvt)
        if not r["read_fail"]:
            return ["read_fail (empty)"]
        if src is None:
            return ["a PLACEHOLDER_FROM entry (it does not read correctly)"]
        if src not in doc["pvts"] or "read_fail" in doc["pvts"][src]:
            return [f"a characterized PLACEHOLDER_FROM PVT ({src})"]
        if doc["pvts"][src]["model"] != r["model"]:
            return [f"PLACEHOLDER_FROM {src} of the same model as {r['model']}"]
        return missing(doc, src)
    for key, sub in REQUIRED.items():
        if key not in r:
            out.append(key)
            continue
        names = sub or (ch.LANES if key == "constraints" else ch.PULSE)
        out += [f"{key}.{n}" for n in names if n not in r[key]]
    return out


def problems(doc, pvt):
    """Everything wrong with the record of pvt: another PVT's record, missing results (missing()),
    or unsound numbers (see the module docstring)."""
    import math
    r, out = doc["pvts"][pvt], []
    if (r.get("pvt"), r.get("model"), r.get("vdd"), r.get("temp")) != (pvt, *sc.PVTS[pvt]):
        out.append(f"is the record of {r.get('pvt')} ({r.get('model')}, {r.get('vdd')} V, {r.get('temp')} C), "
                   f"not of {pvt} {sc.PVTS[pvt]}")
    gaps = missing(doc, pvt)
    if gaps:
        return out + [f"lacks {', '.join(gaps[:6])}"]
    if "read_fail" in r:
        return out
    shape = (len(doc["clk_slews_ns"]), len(doc["loads_pf"]))
    for k in ("settle_max", "depart_min"):
        t = r["delay"][k]
        if (len(t), *{len(row) for row in t}) != shape or not all(math.isfinite(x) and x > 0 for row in t for x in row):
            out.append(f"delay.{k} is not a {shape[0]}x{shape[1]} table of finite numbers > 0")
    res = doc.get("resolution_ns")
    for key in ("constraints", "pulse"):
        for n, v in r[key].items():
            lo, hi = v.get("fail"), v.get("pass")
            if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (lo, hi)) or not hi > lo \
                    or not isinstance(res, (int, float)) or hi - lo > res + 1e-9 or key == "pulse" and hi <= 0:
                out.append(f"{key}.{n} fail {lo} / pass {hi} (need finite, pass > fail, pass - fail <= resolution_ns {res}"
                           + (", pass > 0)" if key == "pulse" else ")"))
    return out


def placeholder(doc, pvt):
    """The record a read_fail PVT's .lib is made from (see the module docstring)."""
    r = json.loads(json.dumps(doc["pvts"][PLACEHOLDER_FROM[pvt]]))
    r.update({k: doc["pvts"][pvt][k] for k in ("pvt", "vdd", "temp")})
    ok = [p for p, x in doc["pvts"].items() if "read_fail" not in x]
    tables = [doc["pvts"][p]["delay"]["depart_min"] for p in ok]
    r["delay"]["depart_min"] = [[min(t[i][j] for t in tables) for j in range(len(tables[0][0]))]
                                for i in range(len(tables[0]))]
    note = (f"   PLACEHOLDER: in simulation the macro does not read correctly at this PVT (char.json read_fail),\n"
            f"   so nothing here is measured: the numbers are those of {PLACEHOLDER_FROM[pvt]} and the hold arc is\n"
            f"   the earliest change over {', '.join(ok)}. It only keeps the logic around the SRAM timed.\n")
    return r, note


def transform(src, doc, pvt, power=None):
    r = doc["pvts"][pvt]
    note = ""
    if "read_fail" in r:
        r, note = placeholder(doc, pvt)
    slews, loads = doc["clk_slews_ns"], doc["loads_pf"]
    d = r["delay"]
    counts = {}

    def hit(k):
        counts[k] = counts.get(k, 0) + 1

    def sub1(pat, repl, text, key):
        text, n = re.subn(pat, repl, text)
        counts[key] = counts.get(key, 0) + n
        return text

    src = sub1(r"library\s*\(\s*[A-Za-z0-9_]+\s*\)", f"library ({sc.MACRO}__{pvt})", src, "library")
    src = sub1(r"(operating_conditions\s*\(\s*OC\s*\)\s*\{\s*process\s*:\s*[^;]+;\s*voltage\s*:\s*)" + NUM +
               r"(\s*;\s*temperature\s*:\s*)" + NUM,
               lambda m: f"{m.group(1)}{r['vdd']}{m.group(2)}{r['temp']:g}", src, "operating_conditions")
    src = sub1(r"(nom_voltage\s*:\s*)" + NUM, lambda m: f"{m.group(1)}{r['vdd']}", src, "nom_voltage")
    src = sub1(r"(nom_temperature\s*:\s*)" + NUM, lambda m: f"{m.group(1)}{r['temp']:g}", src, "nom_temperature")
    src = sub1(r"(voltage_map\s*\(\s*VCCD1\s*,\s*)" + NUM, lambda m: f"{m.group(1)}{r['vdd']}", src, "voltage_map")
    idx = lambda xs: '"' + ", ".join(fmt(x) for x in xs) + '"'
    src = sub1(r"(lu_table_template\(CELL_TABLE\)\{[^}]*?index_1\()[^)]*(\);[^}]*?index_2\()[^)]*(\);)",
               lambda m: m.group(1) + idx(slews) + m.group(2) + idx(loads) + m.group(3), src, "cell_template")
    src = sub1(r"(lu_table_template\(CONSTRAINT_TABLE\)\{[^}]*?index_1\()[^)]*(\);[^}]*?index_2\()[^)]*(\);)",
               lambda m: m.group(1) + idx(slews) + m.group(2) + idx(slews) + m.group(3), src, "constraint_template")

    settle = [[max(row) * PARASITIC] * len(row) for row in d["settle_max"]]
    floor = FLOOR["dout"] * PVT_FLOOR_SCALE[r["model"]]
    lift = max(0.0, floor - min(min(row) for row in settle))
    settle = [[x + lift for x in row] for row in settle]
    tran = const(DOUT_TRANSITION, len(slews), len(loads))
    depart = [[min(row) * HOLD_ARC_SCALE] * len(row) for row in d["depart_min"]]
    cons = r["constraints"]
    pulse = r["pulse"]

    out, pos = [], 0
    for bm in re.finditer(r"\b(bus|pin)\s*\(\s*([A-Za-z0-9_]+)\s*\)\s*\{", src):
        if bm.start() < pos or bm.group(1) != "bus" and bm.group(2) not in ("csb0", "web0", "clk0", "csb1", "clk1"):
            continue
        name = bm.group(2)
        end = block_end(src, bm.end() - 1)
        block = src[bm.start():end]
        if name in PORT0_INPUTS:
            def fix(tm):
                t = tm.group(0)
                kind = re.search(r"timing_type\s*:\s*(\w+)", t).group(1)
                sh = {"setup_rising": "setup", "hold_rising": "hold"}[kind]
                for rf in ("rise", "fall"):
                    v = max(FLOOR[sh], cons[f"{name.rstrip('0')}_{sh}_{rf}"]["pass"] + CONSTRAINT_ADD)
                    t = set_values(t, f"{rf}_constraint", const(v, len(slews), len(slews)))
                hit(f"{kind}:{name}")
                return t
            block = re.sub(r"\btiming\s*\(\s*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", fix, block)
            if name in ("addr0", "wmask0"):
                block, n = re.subn(r"(max_transition\s*:\s*)" + NUM, lambda m: m.group(1) + fmt(INPUT_MAX_TRANSITION), block)
                counts[f"max_transition:{name}"] = counts.get(f"max_transition:{name}", 0) + n
        elif name == "dout0":
            tms = list(re.finditer(r"\btiming\s*\(\s*\)\s*\{", block))
            if len(tms) != 1:
                raise SystemExit(f"gen_char_lib: FAIL - dout0 has {len(tms)} timing groups")
            te = block_end(block, tms[0].end() - 1)
            t = block[tms[0].start():te]
            for g in ("cell_rise", "cell_fall"):
                t = set_values(t, g, settle)
            for g in ("rise_transition", "fall_transition"):
                t = set_values(t, g, tran)
            hold_arc = t.replace("timing_type : falling_edge;", "timing_type : rising_edge;")
            if hold_arc == t:
                raise SystemExit("gen_char_lib: FAIL - dout0 timing is not falling_edge")
            for g in ("cell_rise", "cell_fall"):
                hold_arc = set_values(hold_arc, g, depart)
            block = block[:tms[0].start()] + t + "\n        " + hold_arc + block[te:]
            block, n = re.subn(r"(max_capacitance\s*:\s*)" + NUM, lambda m: m.group(1) + fmt(max(loads)), block)
            counts["max_capacitance"] = counts.get("max_capacitance", 0) + n
            hit("dout0")
        elif name == "clk0":
            def fixc(tm):
                t = tm.group(0)
                kind = re.search(r'timing_type\s*:\s*"?(\w+)"?', t).group(1)
                if kind == "minimum_period":
                    v = max(FLOOR["minimum_period"], pulse["pulse_period"]["pass"] * PARASITIC)
                    vals = {"rise": v, "fall": v}
                elif kind == "min_pulse_width":
                    vals = {"rise": max(FLOOR["min_pulse_width"], pulse["pulse_high"]["pass"] * PARASITIC),
                            "fall": max(FLOOR["min_pulse_width"], pulse["pulse_low"]["pass"] * PARASITIC)}
                else:
                    return t
                for rf, v in vals.items():
                    t = sub1(r"(" + rf + r"_constraint\(scalar\)\s*\{\s*values\(\")" + NUM, lambda m: m.group(1) + fmt(v),
                             t, f"{kind}:{rf}")
                return t
            block = re.sub(r"\btiming\s*\(\s*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", fixc, block)
        out.append(src[pos:bm.start()])
        out.append(block)
        pos = end
    out.append(src[pos:])
    src = "".join(out)

    expect = {"library": 1, "operating_conditions": 1, "nom_voltage": 1, "nom_temperature": 1, "voltage_map": 1,
              "cell_template": 1, "constraint_template": 1, "dout0": 1, "max_capacitance": 1,
              "max_transition:addr0": 1, "max_transition:wmask0": 1}
    expect.update({f"{k}:{p}": 1 for k in ("setup_rising", "hold_rising") for p in PORT0_INPUTS})
    expect.update({f"{k}:{rf}": 1 for k in ("minimum_period", "min_pulse_width") for rf in ("rise", "fall")})
    if power is not None:
        src, pc = set_power(src, power)
        counts.update(pc)
        expect.update(POWER_EXPECT)
    if counts != expect:
        raise SystemExit(f"gen_char_lib: FAIL - {pvt}: change counts {counts} != expected {expect}")
    pdk = sc.NETLIST == sc.PDK_NETLIST
    tmpl = "the PDK TT .lib (template)" if pdk else "OpenRAM's TT .lib (template)"
    keep = ("   Port 1 and power keep the PDK's analytical numbers. ADR-0010. Do not edit by hand.\n" if pdk else
            "   Port 1 keeps OpenRAM's analytical numbers, power the PDK macro's (ip/sram/openram/lib_template.py).\n"
            "   ADR-0010, ADR-0018. Do not edit by hand.\n")
    if power is not None:
        keep = ("   Port 1 timing keeps the template's analytical numbers; internal power and leakage measured\n"
                "   (power.py, untrimmed netlist; a port 1 read is not measured: the port 0 read; the static current\n"
                "   of the floating idle port 1 is not in the leakage, ADR-0018 decision 11).\n"
                "   ADR-0010, ADR-0018. Do not edit by hand.\n")
    header = (f"/* GENERATED by ip/sram/char/gen_char_lib.py from {tmpl} and the ngspice\n"
              f"   characterization {os.path.basename(doc.get('_path', 'char.json'))} (netlist {doc['netlist']},"
              f" sha256 {doc['netlist_sha256'][:12]}, ngspice {doc['ngspice']}).\n"
              f"   PVT {pvt}: model {r['model']}, {r['vdd']} V, {r['temp']:g} C. Port 0: each limit is the larger of the\n"
              f"   padded.lib value (ADR-0007) and the schematic measurement x{PARASITIC} (setup/hold +{CONSTRAINT_ADD} ns);\n"
              f"   dout0 delays do not depend on the load: each slew row holds its largest delay over the loads\n"
              f"   (the earliest change for the rising_edge arc);\n"
              f"   dout0 transition {DOUT_TRANSITION} ns; dout0 rising_edge (hold) arc = earliest change x{HOLD_ARC_SCALE}.\n"
              + keep + note + "*/\n")
    return header + src


POWER_MAP = {("clk0", "!csb0 & !web0"): "write", ("clk0", "!csb0 & web0"): "read",
             ("clk0", "csb0 & !web0"): "idle0", ("clk0", "csb0 & web0"): "idle0",
             ("clk1", "csb1"): "idle1", ("clk1", "!csb1"): "read"}


def set_power(src, pw):
    """Write the measured energies pw (power.json "measured" of one PVT) into the clk0/clk1 internal_power groups and
    the leakage into leakage_power/cell_leakage_power. Returns (text, {what: count})."""
    counts = {}
    out, pos = [], 0
    for pm in re.finditer(r"\bpin\s*\(\s*(clk0|clk1)\s*\)\s*\{", src):
        end = block_end(src, pm.end() - 1)
        block = src[pm.start():end]

        def fix(im, pin=pm.group(1)):
            g = im.group(0)
            when = re.search(r'when\s*:\s*"([^"]*)"', g)
            kind = POWER_MAP.get((pin, when.group(1) if when else None))
            if kind is None:
                raise SystemExit(f"gen_char_lib: FAIL - no measured power for {pin} when {when.group(1) if when else None!r}")
            for rf in ("rise", "fall"):
                g, n = re.subn(r"(" + rf + r"_power\s*\(\s*scalar\s*\)\s*\{\s*values\(\")" + NUM,
                               lambda m: m.group(1) + f"{pw[kind + '_' + rf]:.6f}", g)
                counts[f"power:{pin}:{rf}"] = counts.get(f"power:{pin}:{rf}", 0) + n
            return g
        block = re.sub(r"\binternal_power\s*\(\s*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", fix, block)
        out += [src[pos:pm.start()], block]
        pos = end
    out.append(src[pos:])
    src = "".join(out)
    src, n1 = re.subn(r"(leakage_power\s*\(\s*\)\s*\{\s*value\s*:\s*)" + NUM, lambda m: m.group(1) + f"{pw['leakage_mw']:.6f}", src)
    src, n2 = re.subn(r"(?<!\w)(cell_leakage_power\s*:\s*)" + NUM, lambda m: m.group(1) + f"{pw['leakage_mw']:.6f}", src)
    counts.update({"leakage_power": n1, "cell_leakage_power": n2})
    return src, counts


POWER_EXPECT = {"power:clk0:rise": 4, "power:clk0:fall": 4, "power:clk1:rise": 2, "power:clk1:fall": 2,
                "leakage_power": 1, "cell_leakage_power": 1}


def power_record_problems(pdoc, doc, pvt):
    """Problems of power.json for pvt: another netlist than char.json, the PVT missing or another PVT's
    record, a missing or non-finite number, a negative energy or leakage."""
    import math
    out = []
    if pdoc.get("netlist_sha256") != doc.get("netlist_sha256"):
        out.append("power.json is from another netlist than char.json")
    r = pdoc.get("pvts", {}).get(pvt)
    if r is None:
        return out + [f"power.json has no {pvt}"]
    if (r.get("pvt"), r.get("model"), r.get("vdd"), r.get("temp")) != (pvt, *sc.PVTS[pvt]):
        out.append(f"power.json record under {pvt} is {r.get('pvt')}")
    x = r.get("measured", {})
    need = ["leakage_mw"] + [f"{k}_{rf}" for k in ("write", "read", "idle0", "idle1") for rf in ("rise", "fall")]
    bad = [k for k in need if not (isinstance(x.get(k), (int, float)) and math.isfinite(x[k]) and x[k] >= 0)]
    if bad:
        out.append(f"power.json {pvt} measured value missing, not finite or negative: {', '.join(bad)}")
    return out


def lib_name(pvt):
    return f"{sc.MACRO}__{pvt}.lib"


def main(argv):
    pdoc = None
    if "--power" in argv:
        i = argv.index("--power")
        if i + 1 >= len(argv):
            print(__doc__)
            return 2
        pdoc = json.load(open(argv[i + 1]))
        argv = argv[:i] + argv[i + 2:]
    if len(argv) not in (4, 5) or (len(argv) == 5 and argv[4] != "--check"):
        print(__doc__)
        return 2
    doc = json.load(open(argv[1]))
    doc["_path"] = argv[1]
    src = open(argv[2], encoding="utf-8").read()
    pw = power_problems(src)
    if pw:
        print(f"gen_char_lib: FAIL - template {argv[2]}: {'; '.join(pw)}")
        return 1
    os.makedirs(argv[3], exist_ok=True)
    if set(doc["pvts"]) != set(sc.PVTS):
        print(f"gen_char_lib: FAIL - {argv[1]} has PVTs {sorted(doc['pvts'])}, expected exactly {sorted(sc.PVTS)}")
        return 1
    bad = {pvt: problems(doc, pvt) + (power_record_problems(pdoc, doc, pvt) if pdoc else []) for pvt in doc["pvts"]}
    if any(bad.values()):
        for pvt, g in bad.items():
            if g:
                print(f"gen_char_lib: FAIL - {argv[1]} {pvt} {'; '.join(g)}")
        return 1
    stale = []
    for pvt in doc["pvts"]:
        want = transform(src, doc, pvt, pdoc["pvts"][pvt]["measured"] if pdoc else None)
        dst = os.path.join(argv[3], lib_name(pvt))
        if len(argv) == 5:
            have = open(dst, encoding="utf-8").read() if os.path.isfile(dst) else ""
            if have != want:
                stale.append(dst)
        else:
            open(dst, "w", encoding="utf-8").write(want)
    if stale:
        print(f"gen_char_lib: STALE {' '.join(stale)} (regenerate: python3 {argv[0]} {argv[1]} {argv[2]} {argv[3]})")
        return 1
    ph = [p for p, r in doc["pvts"].items() if "read_fail" in r]
    print(f"gen_char_lib: {'up to date' if len(argv) == 5 else 'wrote'} {len(doc['pvts'])} .lib in {argv[3]}"
          + (f" (placeholder, the macro does not read correctly: {', '.join(ph)})" if ph else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
