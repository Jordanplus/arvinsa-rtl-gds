#!/usr/bin/env python3
"""Positive SoC regression (docs/spec/soc_spec.md 7.4).

Usage:
    python3 dv/scripts/regress.py --sims icarus,verilator --suite all|smoke [-j N]

Runs every selected test (negative_only tests excluded) on every simulator in
parallel, then writes runs/sim/summary.json and runs/sim/junit.xml. Exit code 0
only when at least one test ran and every run is an explicit PASS.
"""

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dvlib  # noqa: E402


def select_tests(tests, suite, only=None):
    names = []
    for name, t in tests.items():
        if t["negative_only"]:
            continue
        if suite == "smoke" and not t["smoke"]:
            continue
        names.append(name)
    if only:
        unknown = [n for n in only if n not in tests]
        if unknown:
            raise dvlib.DvError("unknown test(s): %s" % ", ".join(unknown))
        names = [n for n in names if n in only]
    return names


def write_junit(path, results, suite):
    root = ET.Element("testsuites", name="soc-regress-" + suite)
    by_sim = {}
    for r in results:
        by_sim.setdefault(r["sim"], []).append(r)
    total_f = 0
    for sim, rs in by_sim.items():
        fails = sum(1 for r in rs if r["status"] != "PASS")
        total_f += fails
        ts = ET.SubElement(root, "testsuite", name=sim, tests=str(len(rs)), failures=str(fails),
                           errors="0", time="%.2f" % sum(r.get("wall_time_s", 0) for r in rs))
        for r in rs:
            tc = ET.SubElement(ts, "testcase", classname="soc." + sim, name=r["test"],
                               time="%.2f" % r.get("wall_time_s", 0))
            if r["status"] != "PASS":
                f = ET.SubElement(tc, "failure",
                                  message="failing checkers: " + ", ".join(r["failing_checkers"]))
                f.text = "\n".join(r["messages"]) + "\nresult: %s\n" % r.get("result_json")
    root.set("tests", str(len(results)))
    root.set("failures", str(total_f))
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    ap = dvlib.Parser.make(description="Positive SoC regression (spec 7.4).")
    ap.add_argument("--sims", default="icarus,verilator", help="comma list of icarus,verilator")
    ap.add_argument("--suite", default="all", choices=("all", "smoke"))
    ap.add_argument("-j", "--jobs", type=int, default=dvlib.default_jobs(),
                    help="parallel runs (default max(1, cpu_count-2) = %d)" % dvlib.default_jobs())
    ap.add_argument("--out", default="runs/sim", help="output root (default runs/sim)")
    ap.add_argument("--tests", default="", help="comma list: run only these tests of the suite")
    ap.add_argument("--timeout", type=int, default=None, help="wall-clock limit per run in seconds")
    ap.add_argument("--rtl-f", default=dvlib.RTL_F, help=argparse.SUPPRESS)
    ap.add_argument("--tests-toml", default=dvlib.TESTS_TOML, help=argparse.SUPPRESS)
    ap.add_argument("--fw-dir", default=dvlib.FW_DIR, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    sims = [s for s in args.sims.split(",") if s]
    bad = [s for s in sims if s not in dvlib.SIMS]
    if bad or not sims:
        print("regress: error: --sims must be a comma list of %s" % ",".join(dvlib.SIMS), file=sys.stderr)
        return 1
    if args.jobs < 1:
        print("regress: error: -j must be >= 1", file=sys.stderr)
        return 1
    try:
        tests = dvlib.load_tests(args.tests_toml)
        only = [n for n in args.tests.split(",") if n]
        names = select_tests(tests, args.suite, only)
    except Exception as e:  # OSError, DvError, tomllib.TOMLDecodeError
        print("regress: error: %s" % e, file=sys.stderr)
        return 1

    out = dvlib.repo_path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print("regress: suite=%s sims=%s tests=%d jobs=%d" % (args.suite, ",".join(sims), len(names), args.jobs))

    # Compile once per simulator before the parallel runs (cached under runs/sim_build/).
    builds = {}
    with ThreadPoolExecutor(max_workers=len(sims)) as ex:
        futs = {s: ex.submit(dvlib.build, s, (), args.rtl_f, False) for s in sims}
        for s, f in futs.items():
            try:
                builds[s] = f.result()
            except (OSError, dvlib.DvError) as e:
                builds[s] = dvlib.BuildResult(s, False, dvlib.REPO / dvlib.SIM_BUILD / s, None, None, [],
                                              False, "compile setup failed: %s" % e)
            b = builds[s]
            print("regress: build %s: %s%s" % (s, "ok" if b.ok else "FAIL",
                                               " (cached)" if b.cached else "") +
                  ("" if b.ok else " - " + b.message))

    jobs = [(n, s) for s in sims for n in names]

    def one(job):
        n, s = job
        return dvlib.safe_run_test(n, s, out_root=args.out, rtl_f=args.rtl_f, tests_toml=args.tests_toml,
                              fw_dir=args.fw_dir, timeout=args.timeout, build_result=builds[s],
                              quiet=False)

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        results = list(ex.map(one, jobs))

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = len(results) - passed
    status = "PASS" if results and failed == 0 else "FAIL"
    summary = {
        "suite": args.suite, "sims": sims, "jobs": args.jobs, "status": status,
        "total": len(results), "passed": passed, "failed": failed,
        "wall_time_s": round(time.time() - t0, 2),
        "tools": {s: ["%s %s (%s)" % (n, ver, path) for n, path, ver in dvlib.tool_identity(s)] for s in sims},
        "results": [{k: r.get(k) for k in ("test", "sim", "status", "failing_checkers", "cycles",
                                           "wall_time_s", "result_json")} for r in results],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_junit(out / "junit.xml", results, args.suite)
    print("regress: %s  %d/%d PASS  (%.1f s)  -> %s, %s"
          % (status, passed, len(results), summary["wall_time_s"],
             dvlib.rel(out / "summary.json"), dvlib.rel(out / "junit.xml")))
    for r in results:
        if r["status"] != "PASS":
            print("  FAIL %-16s %-9s %s" % (r["test"], r["sim"], ", ".join(r["failing_checkers"])))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
