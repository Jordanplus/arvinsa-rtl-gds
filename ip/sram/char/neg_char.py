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
  N8  characterization without one of the five PVTs        gen_char_lib.py FAIL ... expected exactly
N1 and N2 simulate tt_025C_1v80 (about 10 minutes each, run in parallel), N3 about 20 minutes.
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
    g = lambda v: [[v] * len(ch.LOADS) for _ in ch.CLK_SLEWS]
    pv = {}
    for p, (m, v, t) in sc.PVTS.items():
        pv[p] = {"pvt": p, "model": m, "vdd": v, "temp": t,
                 "delay": {"settle_max": g(2.5), "d50_max": g(2.2), "tran_max": g(1.2), "depart_min": g(1.0), "depart_max": g(3.0)},
                 "constraints": {n: {"fail": 0.1, "pass": 0.12} for n in ch.LANES},
                 "pulse": {n: {"fail": 3.0, "pass": 3.02} for n in ch.PULSE}}
        if drop:
            del pv[p][drop]
    return {"macro": sc.MACRO, "netlist": "schematic", "netlist_sha256": "0" * 64, "ngspice": "test",
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
    return cp.returncode == 1 and "expected exactly" in cp.stdout and "ff_100C_1v95" in cp.stdout, cp.stdout.strip()


def gen_char_lib_placeholder_from():
    import gen_char_lib
    return gen_char_lib.PLACEHOLDER_FROM


CASES = {"N1": n1, "N2": n2, "N3": n3, "N4": n4, "N5": n5, "N6": n6, "N7": n7, "N8": n8}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=",".join(CASES))
    ap.add_argument("--work", default=os.path.join(sc.ROOT, "runs", "sram_char", "neg"))
    a = ap.parse_args()
    sc.ensure_ngspice()
    work = os.path.abspath(a.work)
    os.makedirs(work, exist_ok=True)
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
