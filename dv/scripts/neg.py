#!/usr/bin/env python3
"""Negative tests by bug injection (docs/spec/soc_spec.md 5, 7.4).

Usage:
    python3 dv/scripts/neg.py [--only R01,R04,...] [-j N]

For every entry of dv/bugs.toml: run its test with its define on its simulator
and invert the judgment. The bug is caught only when
  - the run is FAIL, and
  - it is not a compile error / abnormal end (sim_error), unless sim_error is
    itself an expected checker, and
  - at least one checker in expect_checkers failed with a message that matches
    expect_regex, and
  - with exclusive = true: no checker outside expect_checkers failed (used where
    the whole observable behavior is specified, e.g. the boot ROM loader error
    path: DONE fail code, GPIO_OUT 0xEE and no UART output), and
  - with expect_gpio: the gpio_out change sequence of the run equals it (e.g.
    the boot ROM march FAIL status 0xE1).
Anything else (PASS, compile error, FAIL only at other checkers, no matching
message) is an escape. Writes runs/neg/summary.json; exit code 0 only when every
selected bug was caught.
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dvlib  # noqa: E402


def judge(bug, result):
    """Return (caught, matched, reason) for one bug run."""
    failing = result["failing_checkers"]
    if result["status"] == "PASS":
        return False, None, "escape: the run PASSED, the bug was not detected"
    if "sim_error" in failing and "sim_error" not in bug["expect_checkers"]:
        return False, None, "escape: sim_error (compile error or abnormal end), not a checker detection"
    rx = re.compile(bug["expect_regex"])
    expected_failed = [c for c in bug["expect_checkers"] if c in failing]
    if not expected_failed:
        return False, None, ("escape: FAIL only at unexpected checker(s) %s, expected one of %s"
                             % (failing, bug["expect_checkers"]))
    if bug.get("exclusive"):
        other = [c for c in failing if c not in bug["expect_checkers"]]
        if other:
            return False, None, ("escape: exclusive bug, but checker(s) %s outside %s also failed"
                                 % (other, bug["expect_checkers"]))
    if "expect_gpio" in bug:
        want = ["0x%02x" % g for g in bug["expect_gpio"]]
        got = result.get("gpio")
        if got != want:
            return False, None, ("escape: gpio_out sequence %s, expected %s for this bug" % (got, want))
    for msg in result["messages"]:
        m = dvlib.CHK_LINE_RE.match(msg)
        if m and m.group(1) in bug["expect_checkers"] and rx.search(m.group(2)):
            return True, msg, "caught by %s" % m.group(1)
    return False, None, ("escape: %s failed but no message matches %r"
                         % (expected_failed, bug["expect_regex"]))


def main(argv=None):
    ap = dvlib.Parser.make(description="Bug-injection negative tests (spec 5, 7.4).")
    ap.add_argument("--only", default="", help="comma list of bug ids (default: all)")
    ap.add_argument("-j", "--jobs", type=int, default=dvlib.default_jobs(),
                    help="parallel runs (default %d)" % dvlib.default_jobs())
    ap.add_argument("--cpu", default="picorv32", choices=sorted(dvlib.CPUS), help="CPU build (default picorv32)")
    ap.add_argument("--out", default=None, help="output root (default runs/neg, runs/neg_<cpu> for another CPU)")
    ap.add_argument("--timeout", type=int, default=None, help="wall-clock limit per run in seconds")
    ap.add_argument("--rtl-f", default=dvlib.RTL_F, help=argparse.SUPPRESS)
    ap.add_argument("--tests-toml", default=dvlib.TESTS_TOML, help=argparse.SUPPRESS)
    ap.add_argument("--bugs-toml", default=dvlib.BUGS_TOML, help=argparse.SUPPRESS)
    ap.add_argument("--fw-dir", default=dvlib.FW_DIR, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.out is None:
        args.out = "runs/neg" if args.cpu == "picorv32" else "runs/neg_%s" % args.cpu
    if args.jobs < 1:
        print("neg: error: -j must be >= 1", file=sys.stderr)
        return 1

    try:
        tests = dvlib.load_tests(args.tests_toml)
        bugs = dvlib.load_bugs(args.bugs_toml, tests)
    except Exception as e:  # OSError, DvError, tomllib.TOMLDecodeError
        print("neg: error: %s" % e, file=sys.stderr)
        return 1
    only = [b for b in args.only.split(",") if b]
    unknown = [b for b in only if b not in bugs]
    if unknown:
        print("neg: error: unknown bug id(s): %s (known: %s)" % (", ".join(unknown), ", ".join(bugs)),
              file=sys.stderr)
        return 1
    skipped = [b for b in only if not dvlib.applies(bugs[b], args.cpu)]
    if skipped:
        print("neg: error: bug(s) %s do not apply to %s" % (", ".join(skipped), args.cpu), file=sys.stderr)
        return 1
    ids = [b for b in bugs if (not only or b in only) and dvlib.applies(bugs[b], args.cpu)]
    out = dvlib.repo_path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print("neg: cpu=%s %d bug(s), jobs=%d" % (args.cpu, len(ids), args.jobs))

    def one(bid):
        b = bugs[bid]
        r = dvlib.safe_run_test(b["test"], b["sim"], bug_id=bid, out_root=args.out, rtl_f=args.rtl_f,
                           tests_toml=args.tests_toml, bugs_toml=args.bugs_toml,
                           fw_dir=args.fw_dir, timeout=args.timeout, quiet=True, cpu=args.cpu)
        caught, matched, reason = judge(b, r)
        print("neg: %-5s %-8s %-15s %-9s %s" % (bid, "CAUGHT" if caught else "ESCAPE", b["test"], b["sim"], reason))
        return {
            "id": bid, "define": b["define"], "test": b["test"], "sim": b["sim"],
            "expect_checkers": b["expect_checkers"], "expect_regex": b["expect_regex"],
            "exclusive": b["exclusive"], "expect_gpio": b.get("expect_gpio"),
            "run_status": r["status"], "failing_checkers": r["failing_checkers"],
            "caught": caught, "matched_message": matched, "reason": reason,
            "result_json": r.get("result_json"),
        }

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        rows = list(ex.map(one, ids))

    caught = sum(1 for r in rows if r["caught"])
    status = "PASS" if rows and caught == len(rows) else "FAIL"
    summary = {"cpu": args.cpu, "status": status, "total": len(rows), "caught": caught, "escaped": len(rows) - caught,
               "wall_time_s": round(time.time() - t0, 2), "bugs": rows}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("neg: %s  %d/%d caught  (%.1f s)  -> %s"
          % (status, caught, len(rows), summary["wall_time_s"], dvlib.rel(out / "summary.json")))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
