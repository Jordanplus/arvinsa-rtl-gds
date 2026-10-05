#!/usr/bin/env python3
"""Run one SoC test on one simulator and judge it (docs/spec/soc_spec.md 7.4).

Usage:
    python3 dv/scripts/run_sim.py --test <name> --sim icarus|verilator
                                  [--bug <id>] [--out runs/sim] [--trace] [--vcd]

Writes <out>/<sim>/<test>[__<bug>]/result.json. Exit code 0 only for an explicit
PASS (DONE = PASS magic exactly once, no checker FAIL, clean log scan, normal
end of simulation); 1 otherwise.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dvlib  # noqa: E402


def main(argv=None):
    ap = dvlib.Parser.make(description="Run one SoC test (spec 7.4).")
    ap.add_argument("--test", required=True, help="test name from dv/tests.toml")
    ap.add_argument("--sim", required=True, choices=dvlib.SIMS)
    ap.add_argument("--bug", default=None, help="bug id from dv/bugs.toml (adds its define)")
    ap.add_argument("--cpu", default="picorv32", choices=sorted(dvlib.CPUS),
                    help="CPU build (default picorv32; hazard3: rtl/rtl_hazard3.f, fw/build_hazard3)")
    ap.add_argument("--out", default="runs/sim", help="output root (default runs/sim)")
    ap.add_argument("--trace", action="store_true", help="write trace.log (bus handshakes)")
    ap.add_argument("--vcd", action="store_true", help="write wave.vcd")
    ap.add_argument("--timeout", type=int, default=None,
                    help="wall-clock limit in seconds (default derived from max_cycles)")
    # Hidden options for the DV self-test only (stub RTL, private test lists).
    ap.add_argument("--rtl-f", default=dvlib.RTL_F, help=argparse.SUPPRESS)
    ap.add_argument("--tests-toml", default=dvlib.TESTS_TOML, help=argparse.SUPPRESS)
    ap.add_argument("--bugs-toml", default=dvlib.BUGS_TOML, help=argparse.SUPPRESS)
    ap.add_argument("--fw-dir", default=dvlib.FW_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--plusarg", action="append", default=[], help=argparse.SUPPRESS)
    ap.add_argument("--max-cycles", type=int, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    result = dvlib.run_test(
        args.test, args.sim, bug_id=args.bug, out_root=args.out, trace=args.trace,
        vcd=args.vcd, rtl_f=args.rtl_f, tests_toml=args.tests_toml,
        bugs_toml=args.bugs_toml, fw_dir=args.fw_dir, extra_plusargs=args.plusarg,
        max_cycles=args.max_cycles, timeout=args.timeout, cpu=args.cpu)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
