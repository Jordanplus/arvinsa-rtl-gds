#!/usr/bin/env python3
"""Write one .lib per PVT for the SRAM macro from the SPICE characterization (ADR-0010).

usage: gen_char_lib.py <char.json> <pdk TT .lib> <out_dir> [--check]
  --check   exit 1 if any <out_dir>/<macro>__<pvt>.lib differs from what would be generated
<char.json> must hold exactly the five PVTs of sramchar.PVTS.

The PDK .lib (OpenRAM analytical model, port 0 and port 1) is the template: pins, capacitances,
power and memory groups are copied. The numbers follow the user decision of 2026-10-05 (ADR-0010):
the schematic netlist has no layout parasitics (they made the read about 42-65 % slower in the
bitcell-annotated test), so every limit is the more conservative of the ADR-0007 padded.lib
value (FLOOR) and the characterized value with a parasitic allowance. For each PVT:
  library name, operating conditions, nominal voltage/temperature, VCCD1 voltage map
  CELL_TABLE / CONSTRAINT_TABLE indices  -> the characterized clk0 slews and dout0 loads
  dout0 falling_edge cell_rise/cell_fall -> settle_max x PARASITIC, the whole table shifted up so its
                                            smallest entry is at least FLOOR dout (x PVT_FLOOR_SCALE)
        rise/fall_transition             -> DOUT_TRANSITION (user decision: the schematic, 1.1-1.3 ns,
                                            and the annotated test, 0.23-0.28 ns, disagree 5x)
  dout0 rising_edge arc (new)            -> depart_min x HOLD_ARC_SCALE: the data of the previous read
                                            starts to change this long after the rising edge (the
                                            annotated test changes later, so this is the early side)
  setup_rising / hold_rising of din0 addr0 wmask0 csb0 web0
                                         -> max(FLOOR, first passing offset + CONSTRAINT_ADD) (rise/fall)
  clk0 minimum_period / min_pulse_width  -> max(FLOOR, first passing value x PARASITIC)
  dout0 max_capacitance                  -> the largest characterized load
  addr0 / wmask0 max_transition          -> INPUT_MAX_TRANSITION
Port 1 (addr1 csb1 clk1 dout1) keeps the PDK's analytical numbers: the SoC ties it off and STA
has no clock on clk1. Each kind of change must hit the expected number of places, else FAIL.
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


def transform(src, doc, pvt):
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

    settle = [[x * PARASITIC for x in row] for row in d["settle_max"]]
    floor = FLOOR["dout"] * PVT_FLOOR_SCALE[r["model"]]
    lift = max(0.0, floor - min(min(row) for row in settle))
    settle = [[x + lift for x in row] for row in settle]
    tran = const(DOUT_TRANSITION, len(slews), len(loads))
    depart = [[x * HOLD_ARC_SCALE for x in row] for row in d["depart_min"]]
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
                hit(f"{kind}")
                return t
            block = re.sub(r"\btiming\s*\(\s*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", fix, block)
            if name in ("addr0", "wmask0"):
                block, n = re.subn(r"(max_transition\s*:\s*)" + NUM, lambda m: m.group(1) + fmt(INPUT_MAX_TRANSITION), block)
                counts["max_transition"] = counts.get("max_transition", 0) + n
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
                    t = re.sub(r"(rise_constraint\(scalar\)\s*\{\s*values\(\")" + NUM, lambda m: m.group(1) + fmt(v), t)
                    t = re.sub(r"(fall_constraint\(scalar\)\s*\{\s*values\(\")" + NUM, lambda m: m.group(1) + fmt(v), t)
                elif kind == "min_pulse_width":
                    hi = max(FLOOR["min_pulse_width"], pulse["pulse_high"]["pass"] * PARASITIC)
                    lo = max(FLOOR["min_pulse_width"], pulse["pulse_low"]["pass"] * PARASITIC)
                    t = re.sub(r"(rise_constraint\(scalar\)\s*\{\s*values\(\")" + NUM, lambda m: m.group(1) + fmt(hi), t)
                    t = re.sub(r"(fall_constraint\(scalar\)\s*\{\s*values\(\")" + NUM, lambda m: m.group(1) + fmt(lo), t)
                hit(kind)
                return t
            block = re.sub(r"\btiming\s*\(\s*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", fixc, block)
        out.append(src[pos:bm.start()])
        out.append(block)
        pos = end
    out.append(src[pos:])
    src = "".join(out)

    expect = {"library": 1, "operating_conditions": 1, "nom_voltage": 1, "nom_temperature": 1, "voltage_map": 1,
              "cell_template": 1, "constraint_template": 1, "setup_rising": 5, "hold_rising": 5,
              "max_transition": 2, "dout0": 1, "max_capacitance": 1, "minimum_period": 1, "min_pulse_width": 1}
    if counts != expect:
        raise SystemExit(f"gen_char_lib: FAIL - {pvt}: change counts {counts} != expected {expect}")
    header = (f"/* GENERATED by ip/sram/char/gen_char_lib.py from the PDK TT .lib (template) and the ngspice\n"
              f"   characterization {os.path.basename(doc.get('_path', 'char.json'))} (netlist {doc['netlist']},"
              f" sha256 {doc['netlist_sha256'][:12]}, ngspice {doc['ngspice']}).\n"
              f"   PVT {pvt}: model {r['model']}, {r['vdd']} V, {r['temp']:g} C. Port 0: each limit is the larger of the\n"
              f"   padded.lib value (ADR-0007) and the schematic measurement x{PARASITIC} (setup/hold +{CONSTRAINT_ADD} ns);\n"
              f"   dout0 transition {DOUT_TRANSITION} ns; dout0 rising_edge (hold) arc = earliest change x{HOLD_ARC_SCALE}.\n"
              f"   Port 1 and power keep the PDK's analytical numbers. ADR-0010. Do not edit by hand.\n"
              + note + "*/\n")
    return header + src


def lib_name(pvt):
    return f"{sc.MACRO}__{pvt}.lib"


def main(argv):
    if len(argv) not in (4, 5) or (len(argv) == 5 and argv[4] != "--check"):
        print(__doc__)
        return 2
    doc = json.load(open(argv[1]))
    doc["_path"] = argv[1]
    src = open(argv[2], encoding="utf-8").read()
    os.makedirs(argv[3], exist_ok=True)
    if set(doc["pvts"]) != set(sc.PVTS):
        print(f"gen_char_lib: FAIL - {argv[1]} has PVTs {sorted(doc['pvts'])}, expected exactly {sorted(sc.PVTS)}")
        return 1
    gaps = {pvt: missing(doc, pvt) for pvt in doc["pvts"]}
    if any(gaps.values()):
        for pvt, g in gaps.items():
            if g:
                print(f"gen_char_lib: FAIL - {argv[1]} {pvt} lacks {', '.join(g[:6])}")
        return 1
    stale = []
    for pvt in doc["pvts"]:
        want = transform(src, doc, pvt)
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
