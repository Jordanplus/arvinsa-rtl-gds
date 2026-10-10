#!/usr/bin/env python3
"""SPICE characterization of sky130_sram_2kbyte_1rw1r_32x512_8 port 0 with ngspice (ADR-0010).

usage: characterize.py <out.json> [--pvt NAME ...] [--seed tt.json] [--netlist schematic|extracted]
                       [--jobs N] [--work DIR] [--only delay,constraints,pulse]

Run tt_025C_1v80 first (the default --pvt); the other PVTs need --seed with that result: their
searches start around the tt values and their delay grid simulates only the middle row and column.

Measures, for each PVT of sramchar.PVTS (all five by default):
  delay        clk0 fall -> dout0 rise for a read of 1 (max over the 32 bits and over rows 0/127),
               its 10-90 % transition, and clk0 rise -> dout0 fall (the pull-down to 0 that every
               active cycle starts with; min and max over bits), on a CLK_SLEWS x LOADS grid
  constraints  setup and hold of csb0, web0, addr0, din0, wmask0 for a rising and a falling input,
               each by bisection on when the input changes, judged only by the data read back
               (lanes below); input and clock slew IN_SLEW / CLK_SLEW_MID
  pulse        minimum clk0 high time, low time and period (50 % duty) at which a block of reads
               and writes still returns the right data, by bisection
Every simulation also checks every read; a read check failing outside the bisection is an error.
Each PVT starts with the middle delay simulation; if any read in it is wrong, the macro does not
work at that PVT: only those reads are recorded (read_fail) and gen_char_lib.py writes a
placeholder .lib for it (ADR-0010).
The netlist is the PDK's (schematic) or the Magic extraction of the PDK GDS (extracted, see
extract_sram.sh), trimmed to rows/columns 0 and 127 (sramchar.trim_*). With SRAM_CHAR_MACRO and
SRAM_CHAR_NETLIST set, the schematic netlist of a self-generated macro is used instead (Phase 6,
ADR-0018; simulations under runs/sram_char/<macro>/).
Adds the PVTs to <out.json> (with the settings, tool versions and netlist hash; a file made with
other settings is refused unless --fresh) only when every requested PVT finished, and keeps every
simulation under --work (default runs/sram_char/<netlist>/), where an unchanged deck whose earlier
run left a clean log and a complete waveform is not simulated again.
Prints `characterize: PASS ...` or `characterize: FAIL ...`; exit 0 only on PASS.
"""
import argparse
import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sramchar as sc  # noqa: E402

CLK_SLEWS = (0.05, 0.2, 0.5)      # ns, 10-90 %: .lib index_1 of the dout0 tables
LOADS = (0.005, 0.02, 0.05)       # pF: index_2
CLK_SLEW_MID, IN_SLEW = 0.2, 0.2  # ns, for the constraint and pulse searches
TSTEP, TMAX = "100p", None        # validated against 10p (validate.py)
RESOLUTION = 0.04                 # ns, bisection stops when the bracket is this narrow
MAX_EXTEND = 3                    # times a search may step outside its range
EXTEND_POINTS = 2                 # probes per step outside the range, spread over the initial width
SEED_HALF_WIDTH = {"constraints": 0.5, "pulse": 1.0}   # ns, range around the tt result for other PVTs
P = 0x5A5AA5A5                    # mixed patterns: a trimmed (empty) row cannot read back as them
Q = (~P) & sc.ONES
PERIOD = 20.0                     # ns: 10 ns phases, several times the SS read delay


# ---------------------------------------------------------------- lanes: one setup/hold experiment each
# lane(seq, x) appends the lane's cycles; x is the setup offset s (input changes at rise - s) or the
# hold offset h (input changes at rise + h). Every lane passes when x is large enough.

def lane_addr(kind, d):
    old, new = (0, 511) if d == "rise" else (511, 0)
    data = {511: P, 0: Q}

    def f(s, x):
        s.write(new, data[new])
        s.write(old, data[old])
        if kind == "setup":
            k = s.read(new, data[new], "test")
            s.move(k, "addr", s.rise_of(k) - x)
        else:
            k = s.read(old, data[old], "test")
            k2 = s.read(new, data[new], "next")
            s.move(k2, "addr", s.rise_of(k) + x)
    return f


def lane_din(kind, d):
    old, new = (0, sc.ONES) if d == "rise" else (sc.ONES, 0)

    def f(s, x):
        s.write(511, P)
        s.write(3, old)
        if kind == "setup":
            k = s.write(511, new)
            s.move(k, "din", s.rise_of(k) - x)
            s.read(511, new, "test")
        else:
            k = s.write(511, old)
            k2 = s.write(3, new)
            s.move(k2, "din", s.rise_of(k) + x)
            s.read(511, old, "test")
    return f


def lane_wmask(kind, d):
    old, new = (0, 0xF) if d == "rise" else (0xF, 0)

    def f(s, x):
        s.write(511, 0)
        s.write(508, sc.ONES, wmask=old)
        if kind == "setup":
            k = s.write(511, sc.ONES, wmask=new)
            s.move(k, "wmask", s.rise_of(k) - x)
            s.read(511, sc.ONES if new else 0, "test")
        else:
            k = s.write(511, sc.ONES, wmask=old)
            k2 = s.write(508, sc.ONES, wmask=new)
            s.move(k2, "wmask", s.rise_of(k) + x)
            s.read(511, sc.ONES if old else 0, "test")
    return f


def lane_web(kind, d):
    # rise: write -> read, fall: read -> write. din is Q around the test so that a write by mistake shows.
    def f(s, x):
        s.write(511, P)
        if kind == "setup" and d == "rise":
            s.write(508, Q)
            k = s.read(511, P, "test")
            s.move(k, "web", s.rise_of(k) - x)
            s.read(511, P, "after")
        elif kind == "setup":
            s.write(508, Q)
            s.read(511, P, "prev")
            k = s.write(511, Q)
            s.move(k, "web", s.rise_of(k) - x)
            s.read(511, Q, "test")
        elif d == "rise":
            s.write(508, Q)
            k = s.write(511, Q)
            k2 = s.read(511, Q, "test")
            s.move(k2, "web", s.rise_of(k) + x)
        else:
            s.write(508, Q)
            k = s.read(511, P, "test")
            k2 = s.write(508, Q)
            s.move(k2, "web", s.rise_of(k) + x)
            s.read(511, P, "after")
    return f


def lane_csb(kind, d):
    # rise: selected -> deselected, fall: deselected -> selected. A deselected cycle carries a write of Q to 511.
    def f(s, x):
        s.write(511, P)
        if kind == "setup" and d == "rise":
            s.write(508, Q)
            k = s.nop(web=0, addr=511, din=Q)
            s.move(k, "csb", s.rise_of(k) - x)
            s.read(511, P, "test")
        elif kind == "setup":
            s.nop(web=0, addr=511, din=Q)
            k = s.write(511, Q)
            s.move(k, "csb", s.rise_of(k) - x)
            s.read(511, Q, "test")
        elif d == "rise":
            s.write(508, Q)
            k = s.write(511, Q)
            k2 = s.nop(web=0, addr=511, din=Q)
            s.move(k2, "csb", s.rise_of(k) + x)
            s.read(511, Q, "test")
        else:
            s.nop(web=0, addr=511, din=Q)
            k = s.nop(web=0, addr=511, din=Q)
            k2 = s.write(508, Q)
            s.move(k2, "csb", s.rise_of(k) + x)
            s.read(511, P, "test")
    return f


LANES = {f"{g}_{k}_{d}": fn(k, d)
         for g, fn in (("csb", lane_csb), ("web", lane_web), ("addr", lane_addr), ("din", lane_din), ("wmask", lane_wmask))
         for k in ("setup", "hold") for d in ("rise", "fall")}


def pulse_block(which):
    """Reads and writes whose clk0 high (or low, or both at 50 % duty) phase is x ns."""
    def f(s, x):
        kw = {"high": dict(high=x), "low": dict(low=x), "period": dict(high=x / 2, low=x / 2)}[which]
        s.write(511, P)
        s.write(0, Q)
        s.read(511, P, "test", **kw)
        s.write(508, sc.ONES, **kw)
        s.read(0, Q, "test", **kw)
        s.write(3, 0, **kw)
        s.read(508, sc.ONES, "test", **kw)
        s.read(3, 0, "test")
    return f


PULSE = {"pulse_high": pulse_block("high"), "pulse_low": pulse_block("low"), "pulse_period": pulse_block("period")}
# Search ranges (ns) for tt_025C_1v80; the other PVTs search around the tt result (SEED_HALF_WIDTH).
BRACKET = {"setup": (-1.0, 1.56), "hold": (-1.0, 1.56), "pulse_high": (0.2, 10.44), "pulse_low": (0.2, 10.44),
           "pulse_period": (1.0, 21.48)}
CONS_PERIOD = {"tt": 10.0, "ff": 10.0, "ss": 16.0}   # ns, clock period of the constraint searches per model
# ns, the smallest x probed outside a pulse range: a clock phase of 0.4 ns still has a flat part
# between the two ramps (CLK_SLEW_MID / 0.8 = 0.25 ns each); the period has two phases.
PULSE_FLOOR = {"pulse_high": 0.4, "pulse_low": 0.4, "pulse_period": 0.8}

# ---------------------------------------------------------------- running

class Runner:
    def __init__(self, netlist, work, jobs):
        self.netlist, self.work, self.pool = netlist, work, ThreadPoolExecutor(max_workers=jobs)
        self.n = 0

    def submit(self, seq, name):
        d = os.path.join(self.work, seq.pvt, name)
        deck = seq.deck(self.netlist, TSTEP, TMAX)
        w = sc.cached_wave(d, deck)                                 # same deck already simulated, cleanly
        if w is not None:
            return self.pool.submit(lambda: w)
        self.n += 1
        return self.pool.submit(sc.run, deck, d)


def lane_results(seq, w, blocks):
    """{block index: passed?} from the read checks; a check of a block's setup cycles must pass."""
    bad = sc.check_reads(seq, w)
    out = {}
    for i, (c0, c1) in enumerate(blocks):
        fails = [b for b in bad if c0 <= b[0] < c1]
        out[i] = not fails
    return out, bad


def bisect(runner, pvt, lanes, label, period=PERIOD, per_sim=6, resolution=None, floor=None):
    """Bisection for each lane in lanes {name: (builder, (lo, hi))}; a lane fails for small x and
    passes for large x. The ends of the range are not simulated. When the bracket has shrunk to the
    resolution and one side has never been seen (never failed, or never passed), the lane steps
    outside its range: one iteration probes EXTEND_POINTS points spread over the initial width on
    that side (not below floor[name]), and repeats from the outermost probe until that side is seen, at
    most MAX_EXTEND times, then it is an error; bisection then continues between the nearest
    failing and passing probes. Several lanes share one simulation (per_sim blocks; the probes of
    one lane go to different simulations).
    Returns {name: (last failing x, first passing x)}."""
    res = resolution or RESOLUTION
    br = {n: [lo, hi, False, False, hi - lo, 0] for n, (f, (lo, hi)) in lanes.items()}   # lo hi seen_fail seen_pass width extends
    it = 0
    while True:
        rounds = [[]]                       # rounds[k]: the k-th probe of each lane, one block per lane
        for n, (f, _) in lanes.items():
            lo, hi, sf, sp, w0, ext = br[n]
            if hi - lo > res:
                rounds[0].append((n, f, (lo + hi) / 2))
                continue
            if sf and sp:
                continue
            if ext >= MAX_EXTEND:
                side = "passed everywhere down to" if not sf else "failed everywhere up to"
                raise RuntimeError(f"{pvt} {n}: {side} {lo if not sf else hi:.3f} ns; check the lane or BRACKET")
            br[n][5] = ext + 1
            if not sf:
                xs = sorted({max((floor or {}).get(n, -1e9), hi - w0 * k / EXTEND_POINTS)
                             for k in range(1, EXTEND_POINTS + 1)}, reverse=True)
            else:
                xs = [lo + w0 * k / EXTEND_POINTS for k in range(1, EXTEND_POINTS + 1)]
            for k, x in enumerate(xs):
                if len(rounds) <= k:
                    rounds.append([])
                rounds[k].append((n, f, x))
        if not any(rounds):
            return {n: (b[0], b[1]) for n, b in br.items()}
        futs = []
        for todo in rounds:
            for j in range(0, len(todo), per_sim):
                group = todo[j:j + per_sim]
                s = sc.Seq(pvt, period=period, clk_slew=CLK_SLEW_MID, in_slew=IN_SLEW)
                blocks = []
                for n, f, x in group:
                    c0 = len(s.cycles)
                    f(s, x)
                    blocks.append((c0, len(s.cycles)))
                futs.append((group, s, blocks, runner.submit(s, f"{label}_it{it}_{len(futs)}")))
        seen = {}
        for group, s, blocks, fut in futs:
            w = fut.result()
            ok, _ = lane_results(s, w, blocks)
            for i, (n, f, x) in enumerate(group):
                seen.setdefault(n, []).append((x, ok[i]))
        for n, probes in seen.items():
            b = br[n]
            passing = [x for x, ok in probes if ok] + ([b[1]] if b[3] else [])
            hi = min(passing) if passing else None
            bad = [x for x, ok in probes if not ok and hi is not None and x > hi]
            if bad:
                raise RuntimeError(f"{pvt} {n}: fails at {bad[0]:.3f} ns but passes at {hi:.3f} ns (not monotonic)")
            failing = [x for x, ok in probes if not ok] + ([b[0]] if b[2] else [])
            if hi is not None:
                b[1], b[3] = hi, True
            if failing:
                b[0], b[2] = max(failing), True
            if b[5] and not (b[2] and b[3]):    # outside the range and the other side still unseen:
                if b[2]:                         # step out again from the outermost probe
                    b[1] = b[0]
                else:
                    b[0] = b[1]
        it += 1


def delay_seq(pvt, clk_slew, load_pf, period=PERIOD):
    """Reads that put both values on the measured bits 0 and 31 (P: bit 0 = 1, bit 31 = 0; Q the
    inverse), in rows 0 and 127 and words 0 and 3, with every change of value and a word change
    with the same value between consecutive reads."""
    s = sc.Seq(pvt, period=period, clk_slew=clk_slew, in_slew=IN_SLEW, load_ff=load_pf * 1000)
    s.write(511, P)
    s.write(508, Q)
    s.write(3, Q)
    s.write(0, P)
    for a, e in ((511, P), (508, Q), (3, Q), (0, P), (511, P), (0, P), (508, Q)):
        s.read(a, e, f"r{a}")
    return s


DELAY_KEYS = ("settle_max", "d50_max", "tran_max", "depart_min", "depart_max")


def delay_metrics(s, w, what):
    bad = sc.check_reads(s, w)
    if bad:
        raise RuntimeError(f"{what}: read check failed {bad}")
    rt = sc.read_timing(s, w)
    get = lambda key: [x for r in rt for x in r[key]]
    settle, d50, tran, dep = get("settle"), get("d50"), get("tran"), get("depart")
    if not (settle and d50 and dep):
        raise RuntimeError(f"{what}: missing measurements (settle {len(settle)}, d50 {len(d50)}, depart {len(dep)})")
    return dict(settle_max=max(settle), d50_max=max(d50), tran_max=max(tran), depart_min=min(dep), depart_max=max(dep))


def run_delay(runner, pvt, full):
    """The CLK_SLEWS x LOADS grid; with full=False only the middle row and column are simulated and
    the four corners are filled assuming the slew and load effects add:
    d(s, l) = d(s, mid) + d(mid, l) - d(mid, mid) (checked against the full tt grid, see README)."""
    ms, ml = CLK_SLEWS[len(CLK_SLEWS) // 2], LOADS[len(LOADS) // 2]
    points = [(cs, ld) for cs in CLK_SLEWS for ld in LOADS if full or cs == ms or ld == ml]
    futs = {}
    for cs, ld in points:
        s = delay_seq(pvt, cs, ld)
        futs[(cs, ld)] = (s, runner.submit(s, f"delay_s{cs}_l{ld}"))
    grid = {key: delay_metrics(s, fut.result(), f"{pvt} delay slew {key[0]} load {key[1]}")
            for key, (s, fut) in futs.items()}
    for cs in CLK_SLEWS:
        for ld in LOADS:
            if (cs, ld) not in grid:
                grid[(cs, ld)] = {k: grid[(cs, ml)][k] + grid[(ms, ld)][k] - grid[(ms, ml)][k] for k in DELAY_KEYS}
    out = {k: [[round(grid[(cs, ld)][k], 5) for ld in LOADS] for cs in CLK_SLEWS] for k in DELAY_KEYS}
    out["simulated"] = [[(cs, ld) in futs for ld in LOADS] for cs in CLK_SLEWS]
    return out


def read_fails(runner, pvt):
    """The delay sequence at the middle clock slew and load (the delay grid's middle point, so the
    simulation is shared): the read checks that fail, as text. The macro is characterized at a PVT
    only when every read of this sequence is right (ADR-0010: at ss_n40C_1v60 the sense amps keep
    the previous read's value)."""
    ms, ml = CLK_SLEWS[len(CLK_SLEWS) // 2], LOADS[len(LOADS) // 2]
    s = delay_seq(pvt, ms, ml)
    w = runner.submit(s, f"delay_s{ms}_l{ml}").result()
    return [f"cycle {b[0]} {b[1]}: {b[2]}" for b in sc.check_reads(s, w)]


def characterize_pvt(runner, pvt, only, seed=None):
    """seed: the tt_025C_1v80 result; the searches of this PVT then start around it. When the
    macro does not read correctly at this PVT, only the failing reads are returned (read_fail)."""
    model = sc.PVTS[pvt][0]
    res = {"pvt": pvt, "model": model, "vdd": sc.PVTS[pvt][1], "temp": sc.PVTS[pvt][2]}
    bad = read_fails(runner, pvt)
    if bad:
        res["read_fail"] = bad
        return res
    if seed is not None:     # how a search may step outside its range around the tt result
        res["search"] = {"max_extend": MAX_EXTEND, "extend_points": EXTEND_POINTS, "pulse_floor_ns": PULSE_FLOOR}

    def rng(kind, name):
        if seed is None:
            return BRACKET[name.split("_")[1] if kind == "constraints" else name]
        c, h = seed[kind][name]["pass"], SEED_HALF_WIDTH[kind]
        return (c - h, c + h) if kind == "constraints" else (max(0.1, c - h), c + h)

    def constraints():
        lanes = {n: (f, rng("constraints", n)) for n, f in LANES.items()}
        br = bisect(runner, pvt, lanes, "cons", period=CONS_PERIOD[model])
        return {n: {"fail": round(lo, 4), "pass": round(hi, 4)} for n, (lo, hi) in br.items()}

    def pulse():
        lanes = {n: (f, rng("pulse", n)) for n, f in PULSE.items()}
        br = bisect(runner, pvt, lanes, "pulse", per_sim=3, floor=PULSE_FLOOR)
        return {n: {"fail": round(lo, 4), "pass": round(hi, 4)} for n, (lo, hi) in br.items()}

    parts = {"delay": lambda: run_delay(runner, pvt, full=seed is None), "constraints": constraints, "pulse": pulse}
    with ThreadPoolExecutor(max_workers=3) as ex:     # the three run side by side; ngspice jobs share runner's pool
        futs = {k: ex.submit(fn) for k, fn in parts.items() if k in only}
        for k, f in futs.items():
            res[k] = f.result()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--pvt", nargs="*", default=["tt_025C_1v80"])
    ap.add_argument("--netlist", choices=("schematic", "extracted"), default="schematic")
    ap.add_argument("--extracted", default=os.path.join(sc.ROOT, "runs", "sram_extract", sc.MACRO + ".spice"))
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 3))
    ap.add_argument("--work")
    ap.add_argument("--only", default="delay,constraints,pulse")
    ap.add_argument("--seed", help="a previous characterize.py output whose tt_025C_1v80 result centres the searches")
    ap.add_argument("--fresh", action="store_true", help="overwrite <out.json> instead of adding these PVTs to it")
    a = ap.parse_args()
    sc.ensure_ngspice()
    default_work = os.path.join(sc.ROOT, "runs", "sram_char", a.netlist)
    if sc.NETLIST != sc.PDK_NETLIST:     # a self-generated macro (Phase 6) keeps its own simulations
        default_work = os.path.join(sc.ROOT, "runs", "sram_char", sc.MACRO, a.netlist)
    work = os.path.abspath(a.work or default_work)
    os.makedirs(work, exist_ok=True)
    src = sc.NETLIST if a.netlist == "schematic" else a.extracted
    if not os.path.isfile(src):
        print(f"characterize: FAIL - netlist {src} missing")
        return 1
    trimmed = os.path.join(work, "trimmed.spice")
    kept, dropped = (sc.trim_schematic if a.netlist == "schematic" else sc.trim_extracted)(src, trimmed)
    runner = Runner(trimmed, work, a.jobs)
    only = set(a.only.split(","))
    results, errors = {}, []
    seed = json.load(open(a.seed))["pvts"]["tt_025C_1v80"] if a.seed else None
    if seed is None and any(p != "tt_025C_1v80" for p in a.pvt):
        print("characterize: FAIL - PVTs other than tt_025C_1v80 need --seed (the tt result)")
        return 1
    with ThreadPoolExecutor(max_workers=len(a.pvt)) as outer:
        futs = {p: outer.submit(characterize_pvt, runner, p, only, None if p == "tt_025C_1v80" else seed)
                for p in a.pvt}
        for p, f in futs.items():
            try:
                results[p] = f.result()
            except (RuntimeError, ValueError) as e:
                errors.append(f"{p}: {e}")
    meta = {"macro": sc.MACRO, "netlist": a.netlist, "netlist_sha256": sc.sha256(src),
            "trim": {"kept": kept, "dropped": dropped, "rows": sc.KEEP_ROWS, "columns": sc.KEEP_COLS},
            "ngspice": sc.ngspice_version(), "pdk": sc.pdk_version(), "tstep": TSTEP, "tmax": TMAX,
            "resolution_ns": RESOLUTION, "clk_slews_ns": CLK_SLEWS, "loads_pf": LOADS, "clk_slew_mid_ns": CLK_SLEW_MID,
            "in_slew_ns": IN_SLEW, "period_ns": PERIOD, "constraint_period_ns": CONS_PERIOD, "brackets_ns": BRACKET,
            "seed_half_width_ns": SEED_HALF_WIDTH}
    meta = json.loads(json.dumps(meta))          # tuples -> lists, as they come back from the file
    for p, r in results.items():
        r["seed"] = a.seed and os.path.relpath(os.path.abspath(a.seed), sc.ROOT)
        r["date"] = datetime.date.today().isoformat()
    if errors:      # write nothing: a partly updated file would mix new and old PVTs (Phase 3.5 review);
        print("characterize: FAIL " + "; ".join(errors) + f" ({a.out} not changed; finished simulations stay cached)")
        return 1
    pvts = {}
    if os.path.isfile(a.out) and not a.fresh:
        old = json.load(open(a.out))
        diff = [k for k in meta if old.get(k) != meta[k]]
        if diff:
            print(f"characterize: FAIL - {a.out} was made with other settings ({', '.join(diff)}); use --fresh")
            return 1
        pvts = old["pvts"]
    pvts.update(results)
    with open(a.out, "w") as f:
        json.dump(dict(meta, pvts={p: pvts[p] for p in sc.PVTS if p in pvts}), f, indent=1)
        f.write("\n")
    nf = [p for p, r in results.items() if "read_fail" in r]
    print(f"characterize: PASS {len(results)} PVT(s), {runner.n} simulations -> {a.out}"
          + (f"; the macro does not read correctly at {', '.join(nf)} (recorded as read_fail)" if nf else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
