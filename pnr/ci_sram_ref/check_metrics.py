#!/usr/bin/env python3
"""Checker for the Phase 0 golden run of LibreLane CI design test_sram_macro.

usage: check_metrics.py <local metrics.json> <upstream metrics.json> [<local golden metrics.json>]

Rows:
  must   : the value must equal the expected value (signoff items that are clean upstream)
  corner : every per-corner setup/hold worst slack must be >= 0, and all 9 corners must be present
  golden : every metric must equal the local golden exactly (same key set, same values).
           The flow is deterministic on one machine (two runs on 2026-10-03: 307 metrics, 0 differ),
           so any difference means a tool, PDK or config change that needs review.
  info   : printed for comparison with upstream only. Upstream runs on x86_64 Linux and placement /
           routing differ slightly across platforms (2026-10-03: max slew violations 74 here vs 70
           upstream, max cap 2 vs 3, wirelength -1.3 %), so items that are not clean upstream either
           are compared exactly against the local golden instead of against upstream.

Prints one line per row and `ci-sram-ref: PASS` / `ci-sram-ref: FAIL`; exit code 0 only on PASS.
A metric missing from the local run is a FAIL (a checker that silently skips is not a checker).
"""
import json
import sys

MUST = {
    "flow__errors__count": 0,
    "design__lvs_error__count": 0,
    "route__drc_errors": 0,
    "klayout__drc_error__count": 0,
    "magic__illegal_overlap__count": 0,
    "design__power_grid_violation__count": 0,
    "design__disconnected_pin__count": 0,
    "design__critical_disconnected_pin__count": 0,
    "antenna__violating__nets": 0,
    "antenna__violating__pins": 0,
    "route__antenna_violation__count": 0,
    "design__instance_unmapped__count": 0,
    "synthesis__check_error__count": 0,
    "timing__setup_vio__count": 0,
    "timing__hold_vio__count": 0,
    "design__instance__count__macros": 2,
}
INFO = [
    "magic__drc_error__count",
    "design__max_slew_violation__count",
    "design__max_cap_violation__count",
    "design__max_fanout_violation__count",
    "timing__unannotated_net__count",
    "design__die__bbox",
    "design__instance__count__stdcell",
    "design__instance__count__class:sequential_cell",
    "design__instance__utilization",
    "route__wirelength",
    "timing__setup__ws",
    "timing__hold__ws",
    "ir__drop__worst",
    "power__total",
]
CORNERS = [f"{lvl}_{c}" for lvl in ("nom", "min", "max")
           for c in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95")]


def main(local_path, upstream_path, golden_path=None):
    local = json.load(open(local_path, encoding="utf8"))
    upstream = json.load(open(upstream_path, encoding="utf8"))
    fail = 0

    def row(kind, key, have, want, ok):
        nonlocal fail
        tag = "PASS" if ok else "FAIL"
        if kind == "info":
            tag = "INFO"
        elif not ok:
            fail += 1
        print(f"  [{tag}] {kind:6} {key}: local={have} expected={want}")

    for key, want in MUST.items():
        have = local.get(key)
        row("must", key, have, f"== {want}", have == want)

    for kind in ("setup", "hold"):
        for corner in CORNERS:
            key = f"timing__{kind}__ws__corner:{corner}"
            have = local.get(key)
            row("corner", key, have, f">= 0 (upstream {upstream.get(key)})",
                isinstance(have, (int, float)) and have >= 0)

    if golden_path is not None:
        golden = json.load(open(golden_path, encoding="utf8"))
        keys = sorted(set(golden) | set(local))
        diff = [k for k in keys if golden.get(k, "<missing>") != local.get(k, "<missing>")]
        for key in diff:
            row("golden", key, local.get(key, "<missing>"), golden.get(key, "<missing>"), False)
        if not diff:
            row("golden", f"all {len(keys)} metrics", "identical", "local golden", True)

    for key in INFO:
        row("info", key, local.get(key), f"{upstream.get(key)} (upstream)", True)

    print(f"ci-sram-ref: {'PASS' if fail == 0 else f'FAIL ({fail} rows)'}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print("usage: check_metrics.py <local metrics.json> <upstream metrics.json> [<local golden metrics.json>]")
        sys.exit(2)
    sys.exit(main(*sys.argv[1:]))
