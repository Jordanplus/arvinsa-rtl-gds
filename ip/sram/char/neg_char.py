#!/usr/bin/env python3
"""Negative tests (bug injection) for the SRAM characterization (ADR-0010).

usage: neg_char.py [--only N1,N2,...] [--work DIR]     (default runs/sram_char/neg/)

Each case injects one fault and passes only when the named check reports it:
  N1  sense amp output loaded with 100 fF (all sense amps)  delay settle time >= nominal + 0.2 ns
  N2  bitcells r127 c124 and c127 with Q tied to ground    read check FAILs (bit 31 of 508 or 511)
  N3  setup lane with the input move ignored               bisection reports "passed everywhere" (no range extension)
  N4  PDK netlist with one bitcell instance removed        trim count check FAILs
  N5  characterization without the pulse results          gen_char_lib.py FAIL ... lacks pulse
  N6  one generated .lib edited by hand (hold arc dropped) gen_char_lib.py --check STALE
  N7  read_fail PVT whose placeholder source does not read gen_char_lib.py FAIL <pvt> lacks a characterized ... (<source>)
      (positive control first: with the source, the placeholder .lib is written and says PLACEHOLDER)
  N8  characterization without one of the five PVTs        gen_char_lib.py FAIL ... expected exactly, and the
      PVT it reports missing is exactly the one removed
  N9  records of two PVTs swapped in char.json              gen_char_lib.py FAIL ... is the record of
  N10 char.json provenance fields changed, one at a time    check_char_lib.py provenance FAIL naming the field
      (netlist sha256, PDK, ngspice version, trim count, time step, resolution)
  N11 unsound numbers: NaN setup, hold pass < fail, NaN     gen_char_lib.py FAIL for each
      period, NaN hold-arc entry
  N12 gen_char_lib.py formula errors M1-M5 (rows flattened  check_char_lib.py values FAIL for each (positive
      to the minimum, hold rows to the maximum, placeholder  control first: the unchanged program PASSes)
      hold arc not the minimum, x1.6 and x0.9 left out)
  N13 PDK template variants: clk0 pulse width written as    gen_char_lib.py FAIL change counts
      `rise_constraint (scalar)`; csb0 without a setup arc
      and din0 with two
  N14 confirm.json at another value than the .lib, a lane   check_char_lib.py confirm FAIL for each (positive
      not passed, or made from another char.json            control first)
  N15 a cached simulation that failed part way (error in    the cache is not reused and the read checks raise
      ngspice.log, waveform cut short)                      instead of judging past the waveform's end
  N16 characterization with one PVT failing                 characterize.py FAIL and <out.json> unchanged
  N17 power.json from another netlist, or with a negative  gen_char_lib.py --power FAIL for each (positive
      energy (ADR-0018 decision 10)                         control first: the .lib says its power is measured)
  N18 measured power in the .lib: one value edited by hand, check_char_lib.py power FAIL for each (positive
      gen_char_lib.py with read and write swapped,           control first)
      power.json removed while the .lib says measured
  N19 power.py arithmetic on a made-up waveform with known  every energy, the clk1 share, the dout load share,
      energies per edge, a static current that ramps 100x   the static current and the standby leakage
      over the run, dout load, and a leakage deck with a    recovered within 1 %
      burst at the parked edge
  N20 leakage window with a latch falling to one side      power.unsettled for the step, the slope, the rise
      inside it, or a 20 % slope; a 6 % rise below           and the large fall (positive controls: flat, 1 %
      LEAK_FLAT_ABS; a 6 % fall above it; a netlist with     settling, a step before the window, a 6 % fall of
      one bitcell removed (ADR-0018 decisions 13, 14)        4.6 nW as at ss -40C PASS); sramchar.bitcell_ic
                                                            FAILs on the missing bitcell (positive control: one
                                                            .ic line per PDK bitcell)
  N21 single-bitcell leakage deck without its gmin option   power.cell_gmin_problem reports it against the
      (ngspice's default 1e-12 S; ADR-0018 decision 15)      CELL_GMIN_CHECK deck (positive control: CELL_GMIN
                                                            PASS)
N1 and N2 simulate tt_025C_1v80 (about 10 minutes each, run in parallel), N3 about 20 minutes; the
others take seconds (N14 needs the committed confirm.json).
Prints one line per case and `neg-char: PASS n/n` or `neg-char: FAIL ...`; exit 0 only on PASS.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import characterize as ch  # noqa: E402
import check_char_lib as cc  # noqa: E402
import sramchar as sc  # noqa: E402

PVT = "tt_025C_1v80"
PDK_LIB = os.path.join(sc.PDK_ROOT, "sky130A", "libs.ref", "sky130_sram_macros", "lib", sc.MACRO + "_TT_1p8V_25C.lib")


def trimmed(work):
    p = os.path.join(work, "trimmed.spice")
    if not os.path.isfile(p):
        sc.trim_schematic(sc.PDK_NETLIST, p)
    return p


def edit_subckt(text, name, fn):
    """Apply fn to the lines of `.SUBCKT name` (exactly one)."""
    m = list(re.finditer(rf"^\.SUBCKT {re.escape(name)} .*?^\.ENDS[^\n]*$", text, re.M | re.S))
    if len(m) != 1:
        raise SystemExit(f"neg_char: FAIL - {len(m)} .SUBCKT {name}")
    return text[:m[0].start()] + fn(m[0].group(0)) + text[m[0].end():]


def delay_of(netlist, work, name):
    s = ch.delay_seq(PVT, ch.CLK_SLEW_MID, ch.LOADS[1])
    w = sc.run(s.deck(netlist, ch.TSTEP, ch.TMAX), os.path.join(work, name))
    return ch.delay_metrics(s, w, name)


def n1(work):
    base = trimmed(work)
    bad = os.path.join(work, "n1_slow_sense.spice")
    text = edit_subckt(open(base).read(), "sky130_fd_bd_sram__openram_sense_amp",
                       lambda b: b.replace("\n.ENDS", "\nCinj_n1 dout gnd 100f\n.ENDS", 1))
    open(bad, "w").write(text)
    with ThreadPoolExecutor(2) as ex:
        nom, slow = ex.map(lambda a: delay_of(*a), ((base, work, "n1_nominal"), (bad, work, "n1_bug")))
    d = slow["settle_max"] - nom["settle_max"]
    return d >= 0.2, f"settle_max {nom['settle_max']:.3f} -> {slow['settle_max']:.3f} ns (+{d:.3f}, needs >= 0.2)"


def n2(work):
    bad = os.path.join(work, "n2_stuck.spice")
    text = open(trimmed(work)).read()
    for c in (124, 127):
        text, n = re.subn(rf"^(Xbit_r127_c{c} .*) sky130_fd_bd_sram__openram_dp_cell$",
                          r"\1 sky130_fd_bd_sram__openram_dp_cell_n2", text, flags=re.M)
        if n != 1:
            return False, f"could not find bitcell r127 c{c}"
    cell = re.search(r"^\.SUBCKT sky130_fd_bd_sram__openram_dp_cell .*?^\.ENDS[^\n]*$", text, re.M | re.S).group(0)
    ports = cell.split("\n")[0].split()[2:]
    q = "Q" if "Q" in cell else "q"
    variant = cell.replace(".SUBCKT sky130_fd_bd_sram__openram_dp_cell ", ".SUBCKT sky130_fd_bd_sram__openram_dp_cell_n2 ", 1)
    variant = variant.replace("\n.ENDS", f"\nRstuck_n2 {q} {ports[-1]} 10\n.ENDS", 1)
    text = text.replace(cell, cell + "\n" + variant, 1)
    open(bad, "w").write(text)
    s = ch.delay_seq(PVT, ch.CLK_SLEW_MID, ch.LOADS[1])
    w = sc.run(s.deck(bad, ch.TSTEP, ch.TMAX), os.path.join(work, "n2_bug"))
    badreads = sc.check_reads(s, w)
    hit = [b for b in badreads if b[1] in ("r508", "r511") and "31:" in b[2]]
    return bool(hit), f"read check: {badreads[:2]}"


def n3(work):
    runner = ch.Runner(trimmed(work), os.path.join(work, "n3"), 4)
    orig = sc.Seq.move
    sc.Seq.move = lambda self, k, group, t: None
    saved = ch.RESOLUTION, ch.MAX_EXTEND
    ch.RESOLUTION, ch.MAX_EXTEND = 0.5, 0
    try:
        ch.bisect(runner, PVT, {"din_setup_rise": (ch.LANES["din_setup_rise"], ch.BRACKET["setup"])}, "n3",
                  period=ch.CONS_PERIOD["tt"])
        return False, "bisection returned a number"
    except RuntimeError as e:
        return "passed everywhere" in str(e), str(e)
    finally:
        sc.Seq.move = orig
        ch.RESOLUTION, ch.MAX_EXTEND = saved


def n4(work):
    bad = os.path.join(work, "n4_missing_cell.spice")
    text = open(sc.PDK_NETLIST).read()
    text, n = re.subn(r"^Xbit_r5_c5 .*\n", "", text, count=1, flags=re.M)
    open(bad, "w").write(text)
    try:
        sc.trim_schematic(bad, os.path.join(work, "n4_trimmed.spice"))
        return False, "trim accepted the netlist"
    except SystemExit as e:
        return n == 1 and "trim: FAIL" in str(e), str(e)


def fake_doc(drop=None):
    """A char.json made up for the tests. The numbers differ per PVT, per slew row and per load, and
    some are above the floors, so a formula that takes the wrong extreme or drops a factor gives
    another .lib (Phase 3.5 review: with one value everywhere, all below the floors, it did not)."""
    pv = {}
    for i, (p, (m, v, t)) in enumerate(sc.PVTS.items()):
        g = lambda base: [[round(base * (1 + 0.1 * i) + 0.3 * r + 0.05 * c, 4) for c in range(len(ch.LOADS))]
                          for r in range(len(ch.CLK_SLEWS))]
        pv[p] = {"pvt": p, "model": m, "vdd": v, "temp": t,
                 "delay": {"settle_max": g(7.0), "d50_max": g(6.0), "tran_max": g(1.2), "depart_min": g(1.0 + 0.2 * i),
                           "depart_max": g(3.0)},
                 "constraints": {n: {"fail": round(0.1 + 0.3 * i + 0.01 * j, 4), "pass": round(0.12 + 0.3 * i + 0.01 * j, 4)}
                                 for j, n in enumerate(ch.LANES)},
                 "pulse": {n: {"fail": round(3.0 + 3 * i + j, 4), "pass": round(3.02 + 3 * i + j, 4)} for j, n in enumerate(ch.PULSE)}}
        if drop:
            del pv[p][drop]
    return {"macro": sc.MACRO, "netlist": "schematic", "netlist_sha256": "0" * 64, "ngspice": "test", "resolution_ns": ch.RESOLUTION,
            "clk_slews_ns": list(ch.CLK_SLEWS), "loads_pf": list(ch.LOADS), "pvts": pv}


def gen(args):
    return subprocess.run([sys.executable, os.path.join(HERE, "gen_char_lib.py")] + args, capture_output=True, text=True)


def n5(work):
    j = os.path.join(work, "n5.json")
    json.dump(fake_doc(drop="pulse"), open(j, "w"))
    cp = gen([j, PDK_LIB, os.path.join(work, "n5_lib")])
    return cp.returncode == 1 and "lacks pulse" in cp.stdout, cp.stdout.strip()


def n6(work):
    j, d = os.path.join(work, "n6.json"), os.path.join(work, "n6_lib")
    json.dump(fake_doc(), open(j, "w"))
    if gen([j, PDK_LIB, d]).returncode != 0:
        return False, "could not generate the reference .lib"
    f = os.path.join(d, f"{sc.MACRO}__{PVT}.lib")
    t = open(f).read()
    if t.count("timing_type : rising_edge;") != 1:
        return False, "injection point not found: the dout0 rising_edge arc"
    open(f, "w").write(t.replace("timing_type : rising_edge;", "timing_type : falling_edge;"))
    cp = gen([j, PDK_LIB, d, "--check"])
    return cp.returncode == 1 and "STALE" in cp.stdout and os.path.basename(f) in cp.stdout, cp.stdout.strip()


def n7(work):
    cold = "ss_n40C_1v60"
    src = gen_char_lib_placeholder_from()[cold]
    doc = fake_doc()
    doc["pvts"][cold] = {k: doc["pvts"][cold][k] for k in ("pvt", "model", "vdd", "temp")}
    doc["pvts"][cold]["read_fail"] = ["cycle 4 r511: injected"]
    j, d = os.path.join(work, "n7_ok.json"), os.path.join(work, "n7_lib")
    json.dump(doc, open(j, "w"))
    cp = gen([j, PDK_LIB, d])
    f = os.path.join(d, f"{sc.MACRO}__{cold}.lib")
    if cp.returncode != 0 or not os.path.isfile(f) or "PLACEHOLDER" not in open(f).read():
        return False, f"positive control: no placeholder .lib for {cold}: {cp.stdout.strip()}"
    have = cc.lib_values(f)
    wrong = have.pop("problems") + cc.diff(cc.expected(doc, cold), have)
    if wrong:      # e.g. the hold arc not the earliest over the characterized PVTs (Phase 3.5 review)
        return False, f"positive control: placeholder .lib numbers: {wrong[:2]}"
    doc["pvts"][src] = dict({k: doc["pvts"][src][k] for k in ("pvt", "model", "vdd", "temp")}, read_fail=["cycle 4 r511: injected"])
    j = os.path.join(work, "n7.json")
    json.dump(doc, open(j, "w"))
    cp = gen([j, PDK_LIB, os.path.join(work, "n7_bad_lib")])
    want = f"{cold} lacks a characterized PLACEHOLDER_FROM PVT ({src})"
    return cp.returncode == 1 and want in cp.stdout, cp.stdout.strip()


def n8(work):
    doc = fake_doc()
    del doc["pvts"]["ff_100C_1v95"]
    j = os.path.join(work, "n8.json")
    json.dump(doc, open(j, "w"))
    cp = gen([j, PDK_LIB, os.path.join(work, "n8_lib")])
    m = re.search(r"has PVTs (\[[^]]*\]), expected exactly (\[[^]]*\])", cp.stdout)
    gone = set(json.loads(m.group(2).replace("'", '"'))) - set(json.loads(m.group(1).replace("'", '"'))) if m else None
    return cp.returncode == 1 and gone == {"ff_100C_1v95"}, cp.stdout.strip()


REAL_DIR = os.path.join(sc.ROOT, "ip", "sram", sc.MACRO, "char")
REAL_JSON = os.path.join(REAL_DIR, "char.json")


def check(args):
    return subprocess.run([sys.executable, os.path.join(HERE, "check_char_lib.py")] + args, capture_output=True, text=True)


def failed_rows(out):
    return {m.split(":")[0] for m in re.findall(r"^  \[FAIL\] ([^\n]*)", out, re.M)}


def n9(work):
    doc = fake_doc()
    a, b = "ss_100C_1v60", "ff_100C_1v95"
    doc["pvts"][a], doc["pvts"][b] = doc["pvts"][b], doc["pvts"][a]
    j = os.path.join(work, "n9.json")
    json.dump(doc, open(j, "w"))
    cp = gen([j, PDK_LIB, os.path.join(work, "n9_lib")])
    return cp.returncode == 1 and f"{a} is the record of {b}" in cp.stdout and f"{b} is the record of {a}" in cp.stdout, \
        cp.stdout.strip()[:300]


def n10(work):
    real = json.load(open(REAL_JSON))
    edits = {"netlist_sha256": "f" * 64, "pdk": "0" * 40, "ngspice": "46", "tstep": "1n", "resolution_ns": 0.5,
             "trim": dict(real["trim"], kept=5)}
    missed = []
    for k, v in edits.items():
        doc = json.loads(json.dumps(real))
        doc[k] = v
        j = os.path.join(work, f"n10_{k}.json")
        json.dump(doc, open(j, "w"))
        cp = check([j, REAL_DIR, "--no-confirm"])
        named = "ngspice 46 < NGSPICE_MIN" if k == "ngspice" else f"{k} " if k == "netlist_sha256" else f"{k} = "
        line = re.search(r"^  \[FAIL\] provenance:[^\n]*", cp.stdout, re.M)
        if not (cp.returncode == 1 and failed_rows(cp.stdout) == {"provenance"} and line and named in line.group(0)):
            missed.append(k)
    return not missed, f"{len(edits) - len(missed)}/{len(edits)} fields reported" + (f"; missed {missed}" if missed else "")


def n11(work):
    nan = float("nan")
    cases = {"NaN setup": lambda d: d["constraints"]["din_setup_rise"].update({"pass": nan}),
             "hold pass < fail": lambda d: d["constraints"]["csb_hold_rise"].update({"fail": 5.0, "pass": -3.0}),
             "NaN period": lambda d: d["pulse"]["pulse_period"].update({"pass": nan}),
             "NaN hold arc": lambda d: d["delay"]["depart_min"][0].__setitem__(0, nan)}
    missed = []
    for name, fn in cases.items():
        doc = fake_doc()
        fn(doc["pvts"][PVT])
        j = os.path.join(work, f"n11_{name.replace(' ', '_').replace('<', 'lt')}.json")
        json.dump(doc, open(j, "w"))
        cp = gen([j, PDK_LIB, os.path.join(work, "n11_lib")])
        if not (cp.returncode == 1 and f"FAIL - {j} {PVT}" in cp.stdout):
            missed.append(name)
    return not missed, f"{len(cases) - len(missed)}/{len(cases)} reported" + (f"; missed {missed}" if missed else "")


MUTANTS = {"M1 rows to the minimum": ("settle = [[max(row) * PARASITIC]", "settle = [[min(row) * PARASITIC]"),
           "M2 hold rows to the maximum": ("depart = [[min(row) * HOLD_ARC_SCALE]", "depart = [[max(row) * HOLD_ARC_SCALE]"),
           "M3 placeholder hold not the minimum": ('r["delay"]["depart_min"] = [[min(t[i][j]', 'r["delay"]["depart_min"] = [[max(t[i][j]'),
           "M4 no x1.6": ("PARASITIC = 1.6 ", "PARASITIC = 1.0 "),
           "M5 no x0.9": ("HOLD_ARC_SCALE = 0.9 ", "HOLD_ARC_SCALE = 1.0 ")}


def n12(work):
    src = open(os.path.join(HERE, "gen_char_lib.py")).read()
    missed = []
    for i, (name, (a, b)) in enumerate([("positive control", ("", ""))] + list(MUTANTS.items())):
        if a and src.count(a) != 1:
            return False, f"injection point not found: {name}"
        d = os.path.join(work, f"n12_{i}")
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        for f in ("sramchar.py", "characterize.py"):
            shutil.copy(os.path.join(HERE, f), d)
        open(os.path.join(d, "gen_char_lib.py"), "w").write(src.replace(a, b) if a else src)
        cp = subprocess.run([sys.executable, os.path.join(d, "gen_char_lib.py"), REAL_JSON, PDK_LIB, os.path.join(d, "out")],
                            capture_output=True, text=True)
        if cp.returncode != 0:
            return False, f"{name}: generation failed: {cp.stdout.strip()}"
        r = check([REAL_JSON, os.path.join(d, "out"), "--no-confirm"])
        caught = r.returncode == 1 and failed_rows(r.stdout) and all(x.startswith("values ") for x in failed_rows(r.stdout))
        if (not a and r.returncode != 0) or (a and not caught):
            missed.append(name)
    return not missed, f"positive control PASS and {len(MUTANTS)}/{len(MUTANTS)} formula errors reported" if not missed \
        else f"missed {missed}"


def n13(work):
    t = open(PDK_LIB).read()
    variants = {}
    i = t.index('timing_type :"min_pulse_width"')
    variants["clk0 pulse width with a space"] = t[:i] + t[i:].replace("rise_constraint(scalar)", "rise_constraint (scalar)", 1)
    pins = list(re.finditer(r"\bpin\(csb0\)\{", t))
    if len(pins) != 1:
        return False, "injection point not found: pin(csb0)"
    cs = pins[0].start()
    setup = re.compile(r"\n\s*timing\(\)\{\s*timing_type : setup_rising;(?:[^{}]|\{[^{}]*\})*\}")
    m = setup.search(t, cs)
    dn = setup.search(t, t.index("bus(din0)"))
    if not m or not dn:
        return False, "injection point not found: setup_rising arcs"
    no_csb = t[:m.start()] + t[m.end():]
    k = no_csb.index(dn.group(0))
    variants["csb0 without setup, din0 with two"] = no_csb[:k] + dn.group(0) + no_csb[k:]
    doc = fake_doc()
    j = os.path.join(work, "n13.json")
    json.dump(doc, open(j, "w"))
    missed = []
    for name, text in variants.items():
        lib = os.path.join(work, f"n13_{len(missed)}_{abs(hash(name)) % 1000}.lib")
        open(lib, "w").write(text)
        cp = gen([j, lib, os.path.join(work, "n13_lib")])
        if not (cp.returncode != 0 and "change counts" in (cp.stdout + cp.stderr)):
            missed.append(name)
    return not missed, f"{len(variants) - len(missed)}/{len(variants)} template variants reported" + (f"; missed {missed}" if missed else "")


def n14(work):
    if not os.path.isfile(os.path.join(REAL_DIR, "confirm.json")):
        return False, "no committed confirm.json"
    base = check([REAL_JSON, REAL_DIR])
    if base.returncode != 0:
        return False, f"positive control: {base.stdout.strip()[-200:]}"
    real = json.load(open(os.path.join(REAL_DIR, "confirm.json")))
    def moved(c):
        c["pvts"][PVT]["lanes"]["din_setup_rise"] += 0.5
    def failed(c):
        c["pvts"][PVT]["pass"]["pulse_low"] = False
    def other(c):
        c["char_json_sha256"] = "0" * 64
    missed = []
    for name, fn in (("value", moved), ("pass", failed), ("char.json", other)):
        d = os.path.join(work, f"n14_{name.replace('.', '_')}")
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(REAL_DIR, d)
        c = json.loads(json.dumps(real))
        fn(c)
        json.dump(c, open(os.path.join(d, "confirm.json"), "w"))
        cp = check([os.path.join(d, "char.json"), d])
        if not (cp.returncode == 1 and failed_rows(cp.stdout) == {"confirm"}):
            missed.append(name)
    return not missed, "positive control PASS and 3/3 confirm.json faults reported" if not missed else f"missed {missed}"


def n15(work):
    s = ch.delay_seq(PVT, ch.CLK_SLEW_MID, ch.LOADS[1])
    deck = s.deck(trimmed(work), ch.TSTEP, ch.TMAX)
    end = sc.tran_end(deck)
    d = os.path.join(work, "n15")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    open(os.path.join(d, "deck.sp"), "w").write(deck)
    cols = ["time", "v(clk0)"] + [f"v(do{i})" for i in range(32)]
    def wave(t_end):
        with open(os.path.join(d, "wave.txt"), "w") as f:
            f.write(" ".join(cols) + "\n")
            for k in range(int(t_end) + 1):
                f.write(" ".join([f"{k * 1e-9:.6e}"] + ["0"] * (len(cols) - 1)) + "\n")
            f.write("1.2e-08 0 0")          # a line cut short, as a killed run leaves it
    out = []
    wave(5)
    open(os.path.join(d, "ngspice.log"), "w").write("doAnalyses: TRAN:  Timestep too small\nsimulation interrupted\n")
    out.append(sc.cached_wave(d, deck) is None)
    open(os.path.join(d, "ngspice.log"), "w").write("clean\n")
    out.append(sc.cached_wave(d, deck) is None)            # clean log, but the wave stops at 5 of {end} ns
    try:
        sc.check_reads(s, sc.read_wave(os.path.join(d, "wave.txt")))
        out.append(False)
    except RuntimeError as e:
        out.append("before the read check" in str(e))
    return all(out), f"error log not reused {out[0]}, short wave not reused {out[1]}, read check on it raises {out[2]}"


def n16(work):
    out = os.path.join(work, "n16_char.json")
    shutil.copy(REAL_JSON, out)
    before = open(out, "rb").read()
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import characterize as ch, sramchar as sc\n"
        "real = ch.characterize_pvt\n"
        "def fake(runner, p, only, seed=None):\n"
        "    if p == 'ff_100C_1v95': raise RuntimeError('injected failure')\n"
        "    return dict(pvt=p, model=sc.PVTS[p][0], vdd=sc.PVTS[p][1], temp=sc.PVTS[p][2], injected=True)\n"
        "ch.characterize_pvt = fake\n"
        "sys.argv = ['characterize.py', %r, '--pvt', 'ss_100C_1v60', 'ff_100C_1v95', '--seed', %r, '--work', %r]\n"
        "sys.exit(ch.main())\n") % (HERE, out, REAL_JSON, os.path.join(work, "n16_work"))
    cp = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    same = open(out, "rb").read() == before
    return cp.returncode == 1 and "characterize: FAIL" in cp.stdout and same, \
        f"rc {cp.returncode}, {cp.stdout.strip()[:160]}; out.json unchanged: {same}"


def fake_power(real, sha=None, negative=False):
    """power.json for the real char.json: different energies per PVT and kind, so a swapped mapping shows."""
    pv = {}
    for i, (p, (m, v, tmp)) in enumerate(sc.PVTS.items()):
        x = {"leakage_mw": 0.01 + 0.001 * i}
        for j, kind in enumerate(("write", "read", "idle0", "idle1")):
            for rf in ("rise", "fall"):
                x[f"{kind}_{rf}"] = round(5.0 + 3 * j + 0.5 * i + (0.25 if rf == "fall" else 0), 6)
        if negative and i == 1:
            x["read_fall"] = -0.5
        pv[p] = {"pvt": p, "model": m, "vdd": v, "temp": tmp, "measured": x}
    return {"macro": sc.MACRO, "netlist_sha256": sha or real["netlist_sha256"], "pvts": pv}


def n17(work):
    real = json.load(open(REAL_JSON))
    out = []
    for name, kw, want in (("positive control", {}, None), ("another netlist", {"sha": "1" * 64}, "another netlist"),
                           ("negative energy", {"negative": True}, "negative")):
        pj, d = os.path.join(work, f"n17_{name[:3]}.json"), os.path.join(work, f"n17_{name[:3]}_lib")
        json.dump(fake_power(real, **kw), open(pj, "w"))
        cp = gen([REAL_JSON, PDK_LIB, d, "--power", pj])
        if want is None:
            ok = cp.returncode == 0 and cc.MEASURED_MARK in open(os.path.join(d, f"{sc.MACRO}__tt_025C_1v80.lib")).read()
        else:
            ok = cp.returncode == 1 and want in cp.stdout
        out.append((name, ok))
    missed = [n for n, ok in out if not ok]
    return not missed, "positive control PASS and 2/2 power.json faults reported" if not missed else f"missed {missed}"


def n18(work):
    real = json.load(open(REAL_JSON))
    src = open(os.path.join(HERE, "gen_char_lib.py")).read()
    swap = ('("clk0", "!csb0 & !web0"): "write", ("clk0", "!csb0 & web0"): "read"',
            '("clk0", "!csb0 & !web0"): "read", ("clk0", "!csb0 & web0"): "write"')
    if src.count(swap[0]) != 1:
        return False, "injection point not found: POWER_MAP"
    res = []
    for name in ("positive control", "value edited", "read/write swapped", "power.json removed"):
        d = os.path.join(work, "n18_" + name.split()[0].replace("/", "_"))
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        for f in ("sramchar.py", "characterize.py"):
            shutil.copy(os.path.join(HERE, f), d)
        open(os.path.join(d, "gen_char_lib.py"), "w").write(src.replace(*swap) if name == "read/write swapped" else src)
        pj = os.path.join(d, "out", "power.json")
        os.makedirs(os.path.dirname(pj))
        json.dump(fake_power(real), open(pj, "w"))
        cp = subprocess.run([sys.executable, os.path.join(d, "gen_char_lib.py"), REAL_JSON, PDK_LIB, os.path.join(d, "out"),
                             "--power", pj], capture_output=True, text=True)
        if cp.returncode != 0:
            return False, f"{name}: generation failed: {cp.stdout.strip()}"
        lib = os.path.join(d, "out", f"{sc.MACRO}__ss_100C_1v60.lib")
        if name == "value edited":
            text = open(lib).read()
            m = re.search(r'(when : "!csb0 & !web0";\s*rise_power\(scalar\)\{\s*values\(")([\d.]+)', text)
            if not m:
                return False, "injection point not found: write rise_power"
            open(lib, "w").write(text[:m.start(2)] + f"{float(m.group(2)) + 0.5:.6f}" + text[m.end(2):])
        if name == "power.json removed":
            os.remove(pj)
        r = check([REAL_JSON, os.path.join(d, "out"), "--no-confirm"])
        rows = failed_rows(r.stdout)
        res.append((name, r.returncode == 0 if name == "positive control" else (r.returncode == 1 and rows == {"power"})))
    missed = [n for n, ok in res if not ok]
    return not missed, "positive control PASS and 3/3 power faults reported" if not missed else f"missed {missed}"


def n19(work):
    import power
    s, cyc, stop, leak = power.sequence("tt_025C_1v80")
    rise, fall = s.edges()
    half = s.clk_slew / 0.8 / 2
    vdd, i0, i1 = s.vdd, 5e-6, 500e-6               # A: the static current ramps from i0 to i1 over the run
                                                     # (like the floating port 1, ADR-0018 decision 11)
    e1 = {"rise": 0.7, "fall": 0.3}                  # pJ per clk1 edge (phases A and B)
    ek = {"write": (9.0, 4.0), "read": (6.0, 2.5), "idle0": (1.2, 0.4)}
    kind_of = {k: kind for kind, ks in cyc.items() if kind != "idle1" for k in ks}    # phase B: clk1 only
    for kind in ("write", "read", "idle0"):         # every phase A cycle of that block, not only the averaged ones
        for k in range(min(cyc[kind]) - 1, max(cyc[kind]) + 1):
            kind_of.setdefault(k, kind)
    step = 0.005
    n = int(rise[-1] / step) + 2
    ts = [i * step for i in range(n)]
    tend = ts[-1]

    def i_static(t):
        return i0 + (i1 - i0) * t / tend
    cur = [-i_static(x) for x in ts]
    dout = [0.0] * n

    def pulse(t0, energy_pj):                      # 1 ns rectangle starting at t0 (inside the window)
        a = energy_pj * 1e-3 / vdd                   # pJ = A x V x ns x 1e3
        for i in range(int(round(t0 / step)), int(round((t0 + 1.0) / step))):
            cur[i] -= a
    for k in range(len(s.cycles)):
        a0, b0 = rise[k] - half + 0.5, fall[k] - half + 0.5
        kind = kind_of.get(k)
        if kind:
            pulse(a0, ek[kind][0]); pulse(b0, ek[kind][1])
        if rise[k] < stop["clk1"]:
            pulse(a0 + 2.0, e1["rise"]); pulse(b0 + 2.0, e1["fall"])
    rk = cyc["read"][0]                              # one dout bit rises in the first averaged read: its load energy
    load_pj = s.load_ff * 1e-3 * vdd ** 2
    t_up = fall[rk] + 1.0
    for i in range(int(round(t_up / step)), n):
        dout[i] = vdd
    pulse(fall[rk] - half + 4.0, load_pj)
    w = {"time": ts, "i(vvdd)": cur, **{f"do{b}": (dout if b == 0 else [0.0] * n) for b in range(sc.WORD_BITS)}}
    got = power.energies(s, w, cyc, leak)
    b_last = rise[-1] - half                         # the last window boundary: the highest settled level
    want = {"static_mw": vdd * i_static(sum(leak) / 2) * 1e3, "static_max_mw": vdd * i_static(b_last - power.QUIET / 2) * 1e3,
            "idle1_rise": e1["rise"], "idle1_fall": e1["fall"]}
    for kind, (er, ef) in ek.items():
        want[f"{kind}_rise"], want[f"{kind}_fall"] = er, ef
    ls, park, lwin = power.leak_sequence("tt_025C_1v80")     # leakage deck: a 50 pJ burst at the parked edge
    lrise, _ = ls.edges()                                    # must stay out of the window
    i_stby = 2e-7
    ln = int(lrise[-1] / step) + 2
    lcur = [-i_stby] * ln
    for i in range(int(round(lrise[park["clk0"]] / step)), int(round((lrise[park["clk0"]] + 1.0) / step))):
        lcur[i] -= 50.0 * 1e-3 / vdd
    got["leakage_mw"] = power.mean_mw({"time": [i * step for i in range(ln)], "i(vvdd)": lcur}, vdd, lwin)
    want["leakage_mw"] = vdd * i_stby * 1e3
    bad = {k: (round(got[k], 6), v) for k, v in want.items() if abs(got[k] - v) > 0.01 * max(abs(v), 1e-6)}
    return not bad, ("every energy, the clk1 share, the dout load share, a ramping static current and the "
                     "standby leakage recovered within 1 %") if not bad else f"wrong (got, want): {bad}"


def n20(work):
    import power
    ls, park, (t0, t1) = power.leak_sequence("tt_025C_1v80")
    vdd, step, i_stby = ls.vdd, 0.005, 2e-7
    ts = [i * step for i in range(int(ls.edges()[0][-1] / step) + 2)]

    def drift(c):
        return power.unsettled(*power.leakage({"time": ts, "i(vvdd)": [-c(x) for x in ts]}, vdd, (t0, t1))[1:])
    mid = (t0 + t1) / 2
    i_low = 4.6e-9 / 0.06 / vdd                                  # A: mean whose 6 % is 4.6 nW
    i_big = 2.5 * power.LEAK_FLAT_ABS * 1e-3 / 0.06 / vdd       # A: mean whose 6 % is 2.5 x LEAK_FLAT_ABS
    cases = {   # name: (current in A at time t, must the window check FAIL)
        "flat": (lambda x: i_stby, False),
        "settling 1 % over the window": (lambda x: i_stby * (1 - 0.01 * (x - t0) / (t1 - t0)), False),
        "latch step before the window": (lambda x: i_stby * (10 if x > t0 - 5 else 1), False),
        "latch step inside the window": (lambda x: i_stby * (10 if x > mid + 2 else 1), True),
        "slope 20 % over the window": (lambda x: i_stby * (1 + 0.2 * (x - t0) / (t1 - t0)), True),
        # LEAK_FLAT_ABS: a slow fall is allowed (an upper bound), a rise never (ADR-0018 decision 14)
        "fall 6 %, 4.6 nW (ss -40C)": (lambda x: i_low * (1.06 - 0.12 * (x - t0) / (t1 - t0)), False),
        "rise 6 %, 4.6 nW": (lambda x: i_low * (0.94 + 0.12 * (x - t0) / (t1 - t0)), True),
        "fall 6 %, 2.5 x LEAK_FLAT_ABS": (lambda x: i_big * (1.06 - 0.12 * (x - t0) / (t1 - t0)), True),
    }
    got = {n: drift(c) for n, (c, _) in cases.items()}
    wrong = [n for n, (_, want) in cases.items() if got[n] != want]
    paths = sc.bitcell_paths(sc.PDK_NETLIST)                     # positive control: every bitcell gets its .ic
    ic = sc.bitcell_ic(sc.PDK_NETLIST, vdd).splitlines()
    if len(paths) != sc.ROWS * sc.COLS or len(ic) != len(paths) or not ic[0].endswith(f".q_bar)={vdd}"):
        wrong.append(f"bitcell_ic gave {len(ic)} lines for {len(paths)} bitcells")
    bad = os.path.join(work, "n20_missing_cell.spice")
    text, n = re.subn(r"^Xbit_r5_c5 .*\n(\+.*\n)*", "", open(sc.PDK_NETLIST).read(), count=1, flags=re.M)
    open(bad, "w").write(text)
    try:
        sc.bitcell_ic(bad, vdd)
        wrong.append("bitcell_ic accepted a netlist with a bitcell removed")
    except SystemExit as e:
        if n != 1 or "expected" not in str(e):
            wrong.append(f"bitcell_ic: {e}")
    return not wrong, (f"positive controls PASS and {sum(w for _, w in cases.values())}/"
                       f"{sum(w for _, w in cases.values())} unsettled leakage windows and the missing bitcell "
                       f"reported") if not wrong else f"wrong: {wrong}"

def n21(work):
    import power
    net = trimmed(work)
    vdd = sc.PVTS[PVT][1]

    def leak(name, deck):
        w = sc.run(deck, os.path.join(work, "n21", name), 600)
        return power.mean_mw(w, vdd, (power.CELL_TRAN / 2, power.CELL_TRAN))
    good = power.cell_deck(PVT, net, 0)
    bad, n = re.subn(r"^\.options gmin=\S+\n", "", good, flags=re.M)
    if n != 1:
        return False, f"cell_deck has {n} gmin option lines, expected 1"
    check = leak("check", power.cell_deck(PVT, net, 0, power.CELL_GMIN_CHECK))
    ok, nogmin = leak("cell_gmin", good), leak("no_gmin", bad)
    wrong = []
    if power.cell_gmin_problem(ok, check):
        wrong.append(f"positive control: {power.cell_gmin_problem(ok, check)}")
    if not power.cell_gmin_problem(nogmin, check):
        wrong.append(f"the deck without gmin passed ({nogmin * 1e9:.4g} vs {check * 1e9:.4g} pW)")
    return not wrong, (f"default gmin {nogmin * 1e9:.3g} pW vs {check * 1e9:.3g} pW at {power.CELL_GMIN_CHECK:g} reported; "
                       f"CELL_GMIN {ok * 1e9:.3g} pW PASS") if not wrong else f"wrong: {wrong}"


def gen_char_lib_placeholder_from():
    import gen_char_lib
    return gen_char_lib.PLACEHOLDER_FROM


CASES = {"N1": n1, "N2": n2, "N3": n3, "N4": n4, "N5": n5, "N6": n6, "N7": n7, "N8": n8, "N9": n9, "N10": n10,
         "N11": n11, "N12": n12, "N13": n13, "N14": n14, "N15": n15, "N16": n16, "N17": n17, "N18": n18, "N19": n19,
         "N20": n20, "N21": n21}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=",".join(CASES))
    ap.add_argument("--work", default=os.path.join(sc.ROOT, "runs", "sram_char", "neg"))
    a = ap.parse_args()
    sc.ensure_ngspice()
    work = os.path.abspath(a.work)
    os.makedirs(work, exist_ok=True)
    # Made once before the cases start: they run in parallel threads, and a case that found the file
    # while another was still writing it read half a netlist (Phase 5, a fresh --work stopped with
    # "no .subckt ..."; earlier runs reused a work directory that already had it).
    trimmed(work)
    names = a.only.split(",")
    with ThreadPoolExecutor(len(names)) as ex:
        res = dict(zip(names, ex.map(lambda n: CASES[n](work), names)))
    bad = []
    for n in names:
        ok, msg = res[n]
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}: {msg}")
        if not ok:
            bad.append(n)
    if bad:
        print(f"neg-char: FAIL {', '.join(bad)} not caught")
        return 1
    print(f"neg-char: PASS {len(names)}/{len(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
