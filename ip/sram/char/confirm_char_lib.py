#!/usr/bin/env python3
"""Simulate the SRAM at the setup, hold and clock pulse values of its characterized .lib (ADR-0010).

usage: confirm_char_lib.py <char.json> <char_dir> [--jobs N] [--work DIR]

The bisection of characterize.py checks that a lane passes for large x and fails for small x only
at the points it probed; a lane that also failed in a window above its result would go unnoticed
(Phase 3.5 review). The .lib does not use the bisection results directly either: most limits are
the padded.lib floors. So, for every characterized PVT of <char.json> (read_fail PVTs have nothing
to confirm), this script reads the numbers of <char_dir>/<macro>__<pvt>.lib and simulates:
  every setup/hold lane of characterize.LANES with x = that pin's rise/fall constraint, at the
  constraint search period of the PVT's model (characterize.CONS_PERIOD);
  pulse_high, pulse_low and pulse_period with x = clk0 min_pulse_width rise, fall and
  minimum_period, at characterize.PERIOD.
Every lane must read back right. Writes <char_dir>/confirm.json (the values, the result per lane,
and the sha256 of <char.json>); check_char_lib.py checks it against the .lib.
Simulations are kept under --work (default runs/sram_char/schematic/), like characterize.py.
Prints `confirm_char_lib: PASS ...` / `FAIL ...`; exit 0 only on PASS.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import characterize as ch  # noqa: E402
import check_char_lib as cc  # noqa: E402
import sramchar as sc  # noqa: E402


def lib_lanes(v):
    """{lane: x} at the values of one parsed .lib (check_char_lib.lib_values)."""
    out = {}
    for n in ch.LANES:
        g, kind, rf = n.split("_")
        rows = v[kind][g + "0"][rf]
        if len({x for r in rows for x in r}) != 1:
            raise ValueError(f"{n}: the .lib constraint table is not a single value ({rows})")
        out[n] = rows[0][0]
    out["pulse_high"] = v["min_pulse_width"]["rise"]
    out["pulse_low"] = v["min_pulse_width"]["fall"]
    out["pulse_period"] = v["minimum_period"]["rise"]
    if v["minimum_period"]["fall"] != out["pulse_period"]:
        raise ValueError("minimum_period rise and fall differ")
    return out


def confirm_pvt(runner, pvt, lanes):
    """{lane: passed?} and the number of simulations, all lanes of one PVT."""
    model = sc.PVTS[pvt][0]
    groups = [([n for n in ch.LANES], ch.CONS_PERIOD[model], 6, ch.LANES), ([n for n in ch.PULSE], ch.PERIOD, 3, ch.PULSE)]
    futs = []
    for names, period, per_sim, fns in groups:
        for j in range(0, len(names), per_sim):
            s = sc.Seq(pvt, period=period, clk_slew=ch.CLK_SLEW_MID, in_slew=ch.IN_SLEW)
            blocks = []
            for n in names[j:j + per_sim]:
                c0 = len(s.cycles)
                fns[n](s, lanes[n])
                blocks.append((n, c0, len(s.cycles)))
            futs.append((s, blocks, runner.submit(s, f"confirm_{'cons' if fns is ch.LANES else 'pulse'}_{j // per_sim}")))
    out = {}
    for s, blocks, fut in futs:
        bad = sc.check_reads(s, fut.result())
        for n, c0, c1 in blocks:
            out[n] = not [b for b in bad if c0 <= b[0] < c1]
    return out, len(futs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("char_json")
    ap.add_argument("char_dir")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 3))
    ap.add_argument("--work", default=os.path.join(sc.ROOT, "runs", "sram_char", "schematic"))
    a = ap.parse_args()
    sc.ensure_ngspice()
    doc = json.load(open(a.char_json))
    work = os.path.abspath(a.work)
    trimmed = os.path.join(work, "trimmed.spice")
    os.makedirs(work, exist_ok=True)
    kept, _ = sc.trim_schematic(sc.PDK_NETLIST, trimmed)
    if kept != doc["trim"]["kept"]:
        print(f"confirm_char_lib: FAIL - trim kept {kept}, char.json {doc['trim']['kept']}")
        return 1
    runner = ch.Runner(trimmed, work, a.jobs)
    pvts = [p for p in sc.PVTS if "read_fail" not in doc["pvts"][p]]
    out, failed = {}, []
    for p in pvts:
        lanes = lib_lanes(cc.lib_values(os.path.join(a.char_dir, f"{sc.MACRO}__{p}.lib")))
        out[p] = {"lanes": lanes}
    results = {}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(pvts)) as ex:
        futs = {p: ex.submit(confirm_pvt, runner, p, out[p]["lanes"]) for p in pvts}
        for p, f in futs.items():
            try:
                results[p] = f.result()
            except (RuntimeError, ValueError) as e:
                failed.append(f"{p}: {e}")
    if failed:
        print("confirm_char_lib: FAIL " + "; ".join(failed) + " (confirm.json not written)")
        return 1
    for p, (passed, nsim) in results.items():
        out[p].update({"pass": passed, "simulations": nsim})
        failed += [f"{p} {n}" for n, ok in passed.items() if not ok]
    doc_sha = hashlib.sha256(open(a.char_json, "rb").read()).hexdigest()
    with open(os.path.join(a.char_dir, "confirm.json"), "w") as f:
        json.dump({"char_json_sha256": doc_sha, "tstep": ch.TSTEP, "pvts": out}, f, indent=1)
        f.write("\n")
    if failed:
        print(f"confirm_char_lib: FAIL {len(failed)} lane(s) do not read back right at the .lib values: {', '.join(failed[:6])}")
        return 1
    print(f"confirm_char_lib: PASS {len(pvts)} PVT(s), {sum(len(r[0]) for r in results.values())} lanes, "
          f"{runner.n} simulations -> {os.path.join(a.char_dir, 'confirm.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
