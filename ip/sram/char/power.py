#!/usr/bin/env python3
"""Internal power and leakage of the SRAM macro from ngspice (Phase 6, ADR-0018 decisions 10 and 11).

usage: power.py <out power.json> [--pvt NAME ...] [--jobs N] [--work DIR]

The .lib template's internal_power is analytical (ADR-0007 limitation 3; OpenRAM dev even wrote 1.04e+11).
This measures, for each PVT, on the untrimmed netlist (every bitcell; sramchar.trim_schematic with all 32 bits,
which only renames special_pfet_pass), the supply energy per clock edge from the VDD current of one sequence
(sequence() below, all on port 0, port 1 idle with csb1=1 and clk1 = clk0 as in the SoC, ADR-0018 decision 9):
  phase A  writes (alternating P/Q at address 0: every bit flips), reads (alternating addresses 0 and 3,
           which hold different values: dout flips), idle cycles (csb0=1); every read is checked
  phase B  clk0 stopped low after an idle cycle latched csb0=1, clk1 still running: clk1's own energy
  phase C  both clocks stopped low
Each cycle's energy is split at the clock edges (from 50 % of the rising ramp minus half the ramp):
rise = rising edge to falling edge, fall = falling edge to the next rising edge. Subtracted: the static current
of the window (local baseline: linear between the mean power of the QUIET ns before the window's start and
before its end, when the circuit has settled); in phase A, clk1's energy of the same edge; the energy into the
dout0 loads (C x V^2 per rising bit; STA tools add it from the load). So each number is the energy that one
clk0 (or clk1) edge of that kind adds inside the macro. Units: pJ per edge (pF x V^2, the .lib's
capacitive_load_unit) and mW.

Why a local baseline: with csb1=1 nothing ever precharges port 1 (p_en_bar1 = NAND(clk_buf AND cs1, ...)
stays 1); its bitlines and sense amp nodes float, the port 0 activity couples some of them to mid level and
those sense amps' output inverters conduct from VDD to ground. That current changes with the activity
(trimmed tt b4: 0.08 mW during reads and writes, 0.003 mW in phase C; ff 100C: 0.4 to 2.7 mW), so one value for
the whole run subtracts the wrong amount (it gave negative energies at ff 100C). It is not in the .lib
(ADR-0018 decision 11, known limitation): power.json records it as static_mw (phase C, both clocks stopped) and
static_max_mw (the largest settled level anywhere in the sequence).

The .lib leakage (leakage_mw) comes from a second deck (leak_sequence()): csb1=0 and the last cycle a port 0
read, both clocks parked high after its rising edge, so both ports precharge and no wordline is on (the
standby state of SRAM datasheets); the mean power of the last LEAK_WINDOW ns, which start PARK_SETTLE ns or
more after that edge. Every bitcell starts at Q = 0 (sramchar.bitcell_ic): the operating point otherwise
leaves the latches the sequence never writes balanced at mid level, and at ss -40C they fell to one side 75 ns
after the parked edge, inside the window (ADR-0018 decision 13). The window's two halves must agree within
LEAK_FLAT of their mean, or power.py FAILs (a step or slope means the standby state has not settled), except
when the second half is lower by LEAK_FLAT_ABS or less: nodes the activity coupled below ground recover through
junction leakage, which takes microseconds at ss -40C, so the current still falls slowly; the window then gives
an upper bound (ADR-0018 decision 14; a rise beyond LEAK_FLAT would give a low value and always FAILs). The
window sees no slow drift after it: tt 25C still rises 26 % by 342 ns (known limitation in the ADR).
The single-bitcell decks run with gmin = CELL_GMIN: with ngspice's default 1e-12 S across every junction, a
bitcell leaked about 13 pS x VDD^2 at every PVT but ff 100C (tt 42.7 pW; 0.53 pW at 1e-17), the dropped bitcells
x 15120 made the .lib 1.4-7x too high (ADR-0018 decision 15). Check: Q = 0 again at CELL_GMIN_CHECK must agree
within CELL_GMIN_TOL, or power.py FAILs (the leakage still depends on gmin). The trimmed deck keeps the default
gmin (a smaller one does not converge at ss -40C); at -40C it reads high (ff -40C 48 %, known limitation).

Writes power.json (settings, netlist sha256, per PVT the measured numbers and the static current).
Every measured number must be finite and >= 0, or power.py FAILs. gen_char_lib.py --power writes them into
the .lib; check_char_lib.py recomputes them. Prints `power: PASS ...` / `power: FAIL ...`; exit 0 only on PASS.
"""
import argparse
import datetime
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sramchar as sc  # noqa: E402
import characterize as ch  # noqa: E402

P, Q = ch.P, ch.Q
REPS = 6              # cycles per kind in phase A (the first one of each block is not averaged)
PHASE_B, PHASE_C = 6, 3
QUIET = 3.0           # ns of settled current before each window boundary (local baseline)
LEAK_WINDOW = 20.0    # ns at the end of phase C and of the leakage deck
PARK_CYCLES = 3       # cycles after the parked edge in the leakage deck (the clocks no longer toggle)
PARK_SETTLE = 60.0    # ns from the parked edge to the leakage window, at least
LEAK_FLAT = 0.05      # the two halves of the leakage window may differ by this fraction of their mean, at most
LEAK_FLAT_ABS = 1e-5  # mW: ... or the second half may be lower by this much (2x the ss -40C drift, 4.6 nW)
CELL_TRAN = 2.0       # ns of the single-bitcell standby deck (the mean of its last half is the cell's leakage)
CELL_GMIN = 1e-17     # S, gmin of the single-bitcell deck (1e-17 and 1e-18 agree within 0.2 % at all five PVTs)
CELL_GMIN_CHECK = 1e-18  # S, the same deck again (Q = 0) ...
CELL_GMIN_TOL = 0.01  # ... must agree within this fraction
SIM_TIMEOUT = 8 * 3600  # s per ngspice run (the untrimmed netlist; 2 h was not enough while the runs swapped)
PERIOD = ch.PERIOD
KINDS = ("write", "read", "idle0", "idle1")


def sequence(pvt):
    """(Seq, {kind: [cycle indices averaged]}, clk_stop, (leakage window t0, t1))."""
    s = sc.Seq(pvt, period=PERIOD, clk_slew=ch.CLK_SLEW_MID, in_slew=ch.IN_SLEW, load_ff=ch.LOADS[1] * 1000)
    mem = {0: P, 3: Q, 508: Q, 511: P}
    for a, v in mem.items():
        s.write(a, v)
    s.nop()
    cyc = {k: [] for k in KINDS}
    for i in range(REPS):                       # writes: every bit of word 0 flips
        mem[0] = Q if i % 2 == 0 else P
        k = s.write(0, mem[0])
        if i:
            cyc["write"].append(k)
    for i in range(REPS):                       # reads: words 0 and 3 differ, dout flips
        a = (0, 3)[i % 2]
        k = s.read(a, mem[a], f"r{a}")
        if i:
            cyc["read"].append(k)
    for i in range(REPS):
        k = s.nop()
        if i:
            cyc["idle0"].append(k)
    rise, fall = s.edges()
    last_a = len(s.cycles) - 1
    stop0 = fall[last_a] + s.cycles[last_a]["low"] / 2
    for i in range(PHASE_B):
        k = s.nop()
        if i > 1:
            cyc["idle1"].append(k)
    rise, fall = s.edges()
    last_b = len(s.cycles) - 1
    stop1 = fall[last_b] + s.cycles[last_b]["low"] / 2
    for _ in range(PHASE_C):
        s.nop()
    rise, _ = s.edges()
    return s, cyc, {"clk0": stop0, "clk1": stop1}, (rise[-1] - LEAK_WINDOW, rise[-1])


def leak_sequence(pvt):
    """(Seq, {"clk0": k, "clk1": k} park, (window t0, t1)): csb1 = 0, port 0 writes two words and idles, then
    cycle k reads on port 0 (not checked: its clock never falls) and both clocks stay high from its rising edge."""
    s = sc.Seq(pvt, period=PERIOD, clk_slew=ch.CLK_SLEW_MID, in_slew=ch.IN_SLEW, load_ff=ch.LOADS[1] * 1000)
    s.write(0, P)
    s.write(3, Q)
    s.nop()
    s.nop()
    k = s.cycle(0, 1, 0)
    for _ in range(PARK_CYCLES):
        s.nop()
    rise, _ = s.edges()
    t0, t1 = rise[-1] - LEAK_WINDOW, rise[-1]
    if t0 - rise[k] < PARK_SETTLE:
        raise ValueError(f"leakage window starts {t0 - rise[k]:.1f} ns after the parked edge (< {PARK_SETTLE})")
    return s, {"clk0": k, "clk1": k}, (t0, t1)


def integrate(w, vdd, t0, t1):
    """Supply energy in pJ between t0 and t1 ns (trapezoid; i(vvdd) is negative when the source supplies)."""
    ts, i_s = w["time"], w["i(vvdd)"]
    e = 0.0
    for k in range(1, len(ts)):
        a, b = max(ts[k - 1], t0), min(ts[k], t1)
        if b <= a:
            continue
        def p(t):    # supply power at t (W), linear between samples
            f = (t - ts[k - 1]) / (ts[k] - ts[k - 1]) if ts[k] > ts[k - 1] else 0.0
            return -vdd * (i_s[k - 1] + f * (i_s[k] - i_s[k - 1]))
        e += (p(a) + p(b)) / 2 * (b - a)
    return e * 1e3          # W x ns = nJ -> pJ


def dout_rises(w, vdd, t0, t1):
    """Number of 50 % rising crossings of the 32 dout0 bits between t0 and t1 ns."""
    n = 0
    for i in range(sc.WORD_BITS):
        ts, vs = w["time"], w[f"do{i}"]
        n += sum(1 for k in range(1, len(ts)) if t0 <= ts[k] < t1 and vs[k - 1] < vdd / 2 <= vs[k])
    return n


def mean_mw(w, vdd, win):
    t0, t1 = win
    return integrate(w, vdd, t0, t1) / (t1 - t0)                    # pJ / ns = mW


def leakage(w, vdd, win):
    """(mean mW over win, |second half - first half| / mean, second half - first half in mW): a settled
    standby current is flat; a step or a slope inside the window (a latch falling to one side, a node still
    moving) shows as a difference."""
    t0, t1 = win
    a, b = mean_mw(w, vdd, (t0, (t0 + t1) / 2)), mean_mw(w, vdd, ((t0 + t1) / 2, t1))
    mean = (a + b) / 2
    return mean, abs(b - a) / mean if mean > 0 else math.inf, b - a


def unsettled(drift, delta):
    """True when the window has not settled: the halves differ by more than LEAK_FLAT of their mean, unless
    the current falls by LEAK_FLAT_ABS mW or less (the mean is then a small overestimate, ADR-0018 decision 14)."""
    return drift > LEAK_FLAT and not (-LEAK_FLAT_ABS <= delta <= 0)


def energies(s, w, cyc, static_win):
    """{static_mw, static_max_mw, <kind>_rise, <kind>_fall (pJ)} from the sequence waveform. Each window
    [a, b] loses the energy of its local baseline and the energy the macro puts into its dout0 loads (C x V^2
    per rising dout bit; not internal power, STA tools add it from the load). The baseline is the line through
    the mean power of [a - QUIET, a] at a - QUIET/2 and of [b - QUIET, b] at b - QUIET/2 (exact for a static
    current that changes linearly; taking the means at a and b would lag it by QUIET/2)."""
    rise, fall = s.edges()
    half = s.clk_slew / 0.8 / 2
    load_pj = s.load_ff * 1e-3 * s.vdd ** 2                          # pF x V^2 = pJ per rising dout bit
    bounds = sorted([r - half for r in rise] + [f - half for f in fall])
    quiet = {b: mean_mw(w, s.vdd, (b - QUIET, b)) for b in bounds if b - QUIET >= 0}
    out = {"static_mw": mean_mw(w, s.vdd, static_win), "static_max_mw": max(quiet.values())}
    raw = {}
    for kind, ks in cyc.items():
        for edge in ("rise", "fall"):
            vals = []
            for k in ks:
                a, b = (rise[k] - half, fall[k] - half) if edge == "rise" else (fall[k] - half, rise[k + 1] - half)
                ta, tb = a - QUIET / 2, b - QUIET / 2
                base = (quiet[a] + (quiet[b] - quiet[a]) * ((a + b) / 2 - ta) / (tb - ta)) * (b - a)
                vals.append(integrate(w, s.vdd, a, b) - base - load_pj * dout_rises(w, s.vdd, a, b))
            raw[f"{kind}_{edge}"] = sum(vals) / len(vals)
    for kind in ("write", "read", "idle0"):            # phase A also carries clk1's edges
        for edge in ("rise", "fall"):
            out[f"{kind}_{edge}"] = raw[f"{kind}_{edge}"] - raw[f"idle1_{edge}"]
    for edge in ("rise", "fall"):
        out[f"idle1_{edge}"] = raw[f"idle1_{edge}"]
    return out


def cell_gmin_problem(cell_mw, check_mw):
    """None, or why the bitcell leakage at CELL_GMIN and at CELL_GMIN_CHECK disagree (gmin still adds to it)."""
    if cell_mw > 0 and abs(check_mw / cell_mw - 1) <= CELL_GMIN_TOL:
        return None
    return (f"bitcell leakage depends on gmin: {cell_mw * 1e9:.4g} pW at the deck's gmin, {check_mw * 1e9:.4g} pW "
            f"at {CELL_GMIN_CHECK:g} (> {CELL_GMIN_TOL:.0%} apart)")


def _submit(pool, deck, d):
    w = sc.cached_wave(d, deck)
    return pool.submit(lambda: w) if w is not None else pool.submit(sc.run, deck, d, SIM_TIMEOUT)


def cell_deck(pvt, netlist, q, gmin=CELL_GMIN):
    """One BITCELL in standby: its four bitlines at VDD (precharged), both wordlines at 0, Q = q (0 or 1) held
    during the operating point, ngspice gmin = gmin (S); wave.txt has i(vvdd), which carries the latch's and the
    bitlines' leakage."""
    model, vdd, temp = sc.PVTS[pvt]
    sub = sc.subckt_text(netlist, sc.BITCELL)
    ports = sub.split("\n", 1)[0].split()[2:]
    node = {"BL0": "vdd", "BR0": "vdd", "BL1": "vdd", "BR1": "vdd", "WL0": "0", "WL1": "0", "VDD": "vdd", "GND": "0"}
    if sorted(p.upper() for p in ports) != sorted(node):
        raise SystemExit(f"power: FAIL - {sc.BITCELL} ports {ports}, expected {sorted(node)}")
    return "\n".join([f"* one {sc.BITCELL} in standby, {pvt}, Q = {q} (ip/sram/char/power.py)",
                      f'.lib "{os.path.join(sc.NGSPICE_DIR, "sky130.lib.spice")}" {model}', f".temp {temp}", sub,
                      f"Vvdd vdd 0 {vdd}", "Xc " + " ".join(node[p.upper()] for p in ports) + f" {sc.BITCELL}",
                      f".ic v(xc.q)={vdd * q} v(xc.q_bar)={vdd * (1 - q)}", f".options gmin={gmin:g}",
                      f".tran 10p {CELL_TRAN:.1f}n",
                      ".control\nset wr_singlescale\nset wr_vecnames\noption numdgt=9\nrun\nwrdata wave.txt i(vvdd)\n.endc\n.end\n"])


def simulate(netlist, work, trim, kept, twork, pvt, pool):
    """The decks of one PVT: (sequence parts, sequence future, leakage parts, leakage future, [cell futures]).
    The sequence runs on the untrimmed netlist; the leakage deck on the trimmed one (its kept bitcells held at
    Q = 0 by .ic) and the dropped bitcells are added from the single-cell decks (Q = 0 and Q = 1, then Q = 0
    at CELL_GMIN_CHECK)."""
    s, cyc, stop, static = sequence(pvt)
    deck = s.deck(netlist, ch.TSTEP, ch.TMAX, probes=("i(vvdd)",), clk_stop=stop, save_only=True)
    ls, park, lwin = leak_sequence(pvt)
    ldeck = ls.deck(trim, ch.TSTEP, ch.TMAX, extra=sc.bitcell_ic(trim, ls.vdd, kept), probes=("i(vvdd)",),
                    clk_park=park, csb1=0, save_only=True)
    cells = [_submit(pool, cell_deck(pvt, trim, q), os.path.join(twork, pvt, f"cell_q{q}")) for q in (0, 1)]
    cells.append(_submit(pool, cell_deck(pvt, trim, 0, CELL_GMIN_CHECK), os.path.join(twork, pvt, "cell_gmin_check")))
    return ((s, cyc, static), _submit(pool, deck, os.path.join(work, pvt, "power")),
            (ls, lwin), _submit(pool, ldeck, os.path.join(twork, pvt, "leak")), cells)


def record_problems(rec):
    """Names of the measured numbers that are not finite or negative."""
    return [k for k, v in rec.items() if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("out")
    ap.add_argument("--pvt", nargs="*", default=list(sc.PVTS))
    ap.add_argument("--jobs", type=int, default=3,
                    help="parallel ngspice runs: the untrimmed 2 KB netlist takes about 4.2 GB each (5 at once on a 24 GB "
                         "machine swapped and ran 10-40x slower)")
    ap.add_argument("--work")
    a = ap.parse_args()
    sc.ensure_ngspice()
    base = a.work or os.path.join(sc.ROOT, "runs", "sram_char", *(() if sc.NETLIST == sc.PDK_NETLIST else (sc.MACRO,)), "power")
    d = os.path.abspath(os.path.join(base, "full"))
    os.makedirs(d, exist_ok=True)
    net = os.path.join(d, "trimmed.spice")
    kept = sc.trim_schematic(sc.NETLIST, net, tuple(range(sc.WORD_BITS)))
    if kept[1]:
        print(f"power: FAIL the untrimmed netlist dropped {kept[1]} bitcells")
        return 1
    td = os.path.abspath(os.path.join(base, "leak_trim"))
    os.makedirs(td, exist_ok=True)
    tnet = os.path.join(td, "trimmed.spice")
    tkept, dropped = sc.trim_schematic(sc.NETLIST, tnet)
    pool = ThreadPoolExecutor(max_workers=a.jobs)
    jobs = {p: simulate(net, d, tnet, tkept, td, p, pool) for p in a.pvt}
    pvts, errors = {}, []
    for p, ((s, cyc, swin), fut, (ls, lwin), lfut, cfuts) in jobs.items():
        try:
            w, lw = fut.result(), lfut.result()
            cell_mw = [mean_mw(cw, ls.vdd, (CELL_TRAN / 2, CELL_TRAN)) for cw in (c.result() for c in cfuts)]
            check_mw = cell_mw.pop()
            gp = cell_gmin_problem(cell_mw[0], check_mw)
            if gp:
                errors.append(f"{p}: {gp}")
                continue
            bad = sc.check_reads(s, w) + sc.check_reads(ls, lw)
            if bad:
                errors.append(f"{p}: reads wrong {bad[:2]}")
                continue
            e = energies(s, w, cyc, swin)
            static = {k: e.pop(k) for k in ("static_mw", "static_max_mw")}
            leak, drift, delta = leakage(lw, ls.vdd, lwin)
            if unsettled(drift, delta):
                errors.append(f"{p}: leakage window {lwin[0]:.1f}-{lwin[1]:.1f} ns not settled: its halves differ "
                              f"by {drift:.1%} of the mean (> {LEAK_FLAT:.0%}), {delta * 1e6:+.1f} nW (a fall of "
                              f"{LEAK_FLAT_ABS * 1e6:.0f} nW or less is allowed)")
                continue
            rec = {"leakage_mw": leak + dropped * sum(cell_mw) / 2, **e}
            neg = record_problems(rec)
            if neg:
                errors.append(f"{p}: not finite or negative: " + ", ".join(f"{k}={rec[k]}" for k in neg))
                continue
            pvts[p] = {"pvt": p, "model": sc.PVTS[p][0], "vdd": sc.PVTS[p][1], "temp": sc.PVTS[p][2],
                       "measured": rec, "leakage_parts": {"trimmed_mw": leak, "drift": drift, "drift_mw": delta,
                                                           "cell_nw": [m * 1e6 for m in cell_mw],
                                                           "cell_gmin_check_nw": check_mw * 1e6, "cells_added": dropped},
                       **static}
        except (RuntimeError, ValueError) as e:
            errors.append(f"{p}: {e}")
    if errors:
        print("power: FAIL " + "; ".join(errors))
        return 1
    doc = {"macro": sc.MACRO, "netlist_sha256": sc.sha256(sc.NETLIST), "ngspice": sc.ngspice_version(),
           "pdk": sc.pdk_version(), "tstep": ch.TSTEP, "period_ns": PERIOD, "clk_slew_ns": ch.CLK_SLEW_MID,
           "in_slew_ns": ch.IN_SLEW, "load_pf": ch.LOADS[1], "bitcells": kept[0], "reps": REPS, "quiet_ns": QUIET,
           "leak_window_ns": LEAK_WINDOW, "park_settle_ns": PARK_SETTLE, "leak_flat": LEAK_FLAT,
           "leak_flat_abs_mw": LEAK_FLAT_ABS, "cell_gmin": CELL_GMIN, "cell_gmin_check": CELL_GMIN_CHECK,
           "cell_gmin_tol": CELL_GMIN_TOL,
           "leak_trimmed_bitcells": tkept,
           "date": datetime.date.today().isoformat(), "units": {"energy": "pJ per edge", "leakage": "mW"},
           "pvts": pvts}
    json.dump(doc, open(a.out, "w"), indent=1)
    wr = {p: round(r["measured"]["write_rise"] + r["measured"]["write_fall"], 2) for p, r in pvts.items()}
    stat = max(r["static_max_mw"] for r in pvts.values())
    print(f"power: PASS {len(pvts)} PVT(s) -> {a.out}; write energy per cycle (pJ): {wr}; "
          f"largest static current with port 1 idle (not in the .lib): {stat:.3f} mW")
    return 0


if __name__ == "__main__":
    sys.exit(main())
