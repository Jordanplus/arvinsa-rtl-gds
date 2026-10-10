#!/usr/bin/env python3
"""Phase 6 step 3a (ADR-0018): does a 2 KB 1rw1r OpenRAM macro read correctly at each PVT?

    python3 ip/sram/openram/read_check.py <netlist.sp> <macro name> <out.json> [--pvt ...] [--jobs N] [--words-per-row 1]

Uses the Phase 3.5 machinery (ip/sram/char: trimming, stimulus, ngspice decks, read checks) with
SRAM_CHAR_MACRO=<macro name>, and the flow PDK's ngspice models (PDK_ROOT, default ~/.ciel), as for the SoC.
The read check is characterize.py's read_fails(): the delay sequence at the middle clock slew and load,
whose reads of different consecutive values expose the Phase 3.5 failure (the sense amp keeps the previous
read at low temperature or ss low voltage, ADR-0010).
Before trimming, sky130_fd_pr__special_pfet_pass is renamed to sky130_fd_pr__special_pfet_latch: the flow PDK
renamed the device and its legacy alias subckt fails in ngspice with "unknown subckt" (ADR-0018 decision 5).
The run FAILs if any special_pfet_pass is left. PVTs: the five STA PVTs plus ss_025C_1v60 and tt_n40C_1v60, the
two other conditions where the PDK macro failed in Phase 3.5. Writes {pvt: [failing reads]} and the setup.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

EXTRA_PVTS = {"ss_025C_1v60": ("ss", 1.60, 25.0), "tt_n40C_1v60": ("tt", 1.60, -40.0)}


def rename_pfet(src, dst):
    """Copy src to dst with the legacy PMOS name replaced; returns the number of replacements."""
    text = open(src, encoding="utf-8").read()
    n = text.count("sky130_fd_pr__special_pfet_pass")
    out = text.replace("sky130_fd_pr__special_pfet_pass", "sky130_fd_pr__special_pfet_latch")
    if "special_pfet_pass" in out:
        raise SystemExit(f"read_check: FAIL - special_pfet_pass left in {dst}")
    open(dst, "w", encoding="utf-8").write(out)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("macro")
    ap.add_argument("out")
    ap.add_argument("--pvt", nargs="*")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 3))
    ap.add_argument("--words-per-row", type=int, default=4, help="4 (OpenRAM default for 2 KB) or 1 (no column mux)")
    a = ap.parse_args()
    os.environ["SRAM_CHAR_MACRO"] = a.macro            # before sramchar is imported
    os.environ["SRAM_CHAR_WORDS_PER_ROW"] = str(a.words_per_row)
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "char"))
    import sramchar as sc  # noqa: E402
    import characterize as ch  # noqa: E402
    sc.PVTS.update(EXTRA_PVTS)
    pvts = a.pvt or list(sc.PVTS)
    sc.ensure_ngspice()
    work = os.path.join(os.path.dirname(os.path.abspath(a.out)), "read_check_work")
    os.makedirs(work, exist_ok=True)
    renamed_net = os.path.join(work, "netlist.spice")
    renamed = rename_pfet(a.netlist, renamed_net)
    trimmed = os.path.join(work, "trimmed.spice")
    kept, dropped = sc.trim_schematic(renamed_net, trimmed)
    runner = ch.Runner(trimmed, work, a.jobs)
    with ThreadPoolExecutor(max_workers=len(pvts)) as pool:
        futs = {p: pool.submit(ch.read_fails, runner, p) for p in pvts}
        fails = {p: f.result() for p, f in futs.items()}
    res = {"macro": a.macro, "netlist": os.path.relpath(os.path.abspath(a.netlist)), "netlist_sha256": sc.sha256(a.netlist),
           "pfet_pass_renamed": renamed, "words_per_row": sc.WORDS_PER_ROW,
           "trim": {"kept": kept, "dropped": dropped, "rows": sc.KEEP_ROWS, "columns": sc.KEEP_COLS}, "pdk": sc.pdk_version(),
           "ngspice": sc.ngspice_version(), "simulations": runner.n,
           "pvts": {p: {"corner": sc.PVTS[p][0], "vdd": sc.PVTS[p][1], "temp": sc.PVTS[p][2],
                        "reads_ok": not fails[p], "failing_reads": fails[p][:20], "n_failing": len(fails[p])} for p in pvts}}
    json.dump(res, open(a.out, "w"), indent=1)
    bad = [p for p in pvts if fails[p]]
    print(f"read_check: {a.macro}: reads correct at {len(pvts) - len(bad)}/{len(pvts)} PVTs"
          + (f"; wrong reads at {', '.join(f'{p} ({len(fails[p])})' for p in bad)}" if bad else "") + f" -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
