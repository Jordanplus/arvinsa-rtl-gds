#!/usr/bin/env python3
"""Signoff checker: LibreLane metrics vs a limits file and a golden run (project-plan.md §7.2).

usage: check_signoff.py <metrics.json> <limits.toml> <golden metrics.json>

<metrics.json> comes from `python3 -m librelane.state latest <run> --extract-metrics-to`.
<limits.toml> (signoff/limits/<design>.toml) has these tables; every row is checked:
  [equal]   "<metric>" = value       metric must equal value (a number must be a number, not a bool)
  [min]     "<metric>" = value       metric must be a finite number >= value
  [max]     "<metric>" = value       metric must be a finite number <= value
  [max_sum] "<name>" = {keys = [...], max = value}   every key a finite number, their sum <= value
                                     (e.g. VDD drop + GND rise against one supply budget)
  [corners] names = [...]            for every corner: setup_ws_min <= timing__setup__ws__corner:<c> < slack_max
            setup_ws_min, hold_ws_min,                  hold_ws_min  <= timing__hold__ws__corner:<c>  < slack_max
            slack_max                names must be unique and equal the corners present in the metrics.
                                     slack_max (one clock period) rejects the huge or infinite slack
                                     OpenSTA reports when no constrained path exists (e.g. a lost clock)
  [info]    keys = [...]             printed only
  [golden_tolerance] "<pattern>" = {abs = x} or {rel = y}   (optional, see below)
Golden: the run must have exactly the golden key set, and every value must equal the golden value.
The only exception are metrics whose key matches a [golden_tolerance] pattern (fnmatch, first match
wins): there a numeric difference up to abs (|run - golden| <= x) or rel (<= y * |golden|) passes.
Use it only for metric families measured to vary between identical runs (the detailed router is
not deterministic, see signoff/golden/<design>/README.md); every other difference means a tool,
PDK, RTL or config change that needs review before the golden file is replaced. A tolerance must
be finite and > 0, and its pattern must not match an [equal] key or any key containing "count"
or "area" (those must always be identical).

Prints one line per row and `signoff: PASS` / `signoff: FAIL`; exit code 0 only on PASS.
A metric missing from the run is a FAIL (a checker that silently skips is not a checker).
Python stdlib only.
"""
import fnmatch
import json
import math
import os
import sys
import tomllib


def main(metrics_path, limits_path, golden_path):
    run = json.load(open(metrics_path, encoding="utf8"))
    with open(limits_path, "rb") as f:
        limits = tomllib.load(f)
    golden = json.load(open(golden_path, encoding="utf8")) if os.path.isfile(golden_path) else None
    fail = 0

    def row(kind, key, have, want, ok):
        nonlocal fail
        tag = "INFO" if kind == "info" else ("PASS" if ok else "FAIL")
        fail += tag == "FAIL"
        if isinstance(have, str) and have != "<missing>" and kind in ("equal", "min", "max", "corner"):
            have = json.dumps(have)
        print(f"  [{tag}] {kind:6} {key}: run={have} expected={want}")

    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def finite(v):
        return number(v) and math.isfinite(v)

    for key, want in limits.get("equal", {}).items():
        have = run.get(key, "<missing>")
        same_kind = number(have) == number(want) and isinstance(have, bool) == isinstance(want, bool)
        row("equal", key, have, f"== {want}", same_kind and have == want)
    for key, want in limits.get("min", {}).items():
        have = run.get(key, "<missing>")
        row("min", key, have, f">= {want}", finite(have) and have >= want)
    for key, want in limits.get("max", {}).items():
        have = run.get(key, "<missing>")
        row("max", key, have, f"<= {want}", finite(have) and have <= want)
    for name, spec in limits.get("max_sum", {}).items():
        keys, top = (spec.get("keys") or [], spec.get("max")) if isinstance(spec, dict) else ([], None)
        vals = [run.get(k, "<missing>") for k in keys]
        ok = bool(keys) and finite(top) and all(finite(v) for v in vals)
        total = sum(vals) if ok else "<missing>"
        # every term is a drop or rise and must be >= 0: a negative one would hide the other in the sum
        neg = [k for k, v in zip(keys, vals) if finite(v) and v < 0]
        row("max", f"{name} (sum of {', '.join(keys) or 'no keys'}{'; negative: ' + ', '.join(neg) if neg else ''})",
            total, f"<= {top}, each >= 0", ok and not neg and total <= top)
    corners = limits.get("corners", {})
    names, top = corners.get("names", []), corners.get("slack_max")
    for kind in ("setup", "hold"):
        floor = corners.get(f"{kind}_ws_min")
        for corner in names:
            key = f"timing__{kind}__ws__corner:{corner}"
            have = run.get(key, "<missing>")
            ok = finite(floor) and finite(top) and finite(have) and floor <= have < top
            row("corner", key, have, f">= {floor} and < {top}", ok)
    present = sorted({k.split(":", 1)[1] for k in run if k.startswith("timing__setup__ws__corner:")})
    if not names or len(set(names)) != len(names) or sorted(names) != present:
        row("corner", "names", names, f"unique and equal to the corners in the metrics {present}", False)

    if golden is None:
        row("golden", "file", "<missing>", golden_path, False)
    else:
        tolerance = limits.get("golden_tolerance", {})
        protected = set(limits.get("equal", {})) | {k for k in set(golden) | set(run) if "count" in k or "area" in k}
        for pattern, spec in tolerance.items():
            if not (isinstance(spec, dict) and len(spec) == 1 and set(spec) <= {"abs", "rel"}
                    and finite(next(iter(spec.values()))) and next(iter(spec.values())) > 0):
                row("golden", f"tolerance {pattern}", spec, "{abs = x} or {rel = y}, x/y finite and > 0", False)
            hit = sorted(k for k in protected if fnmatch.fnmatchcase(k, pattern))
            if hit:
                row("golden", f"tolerance {pattern}", f"matches {hit[:3]}", "no [equal], count or area metric", False)
        keys = sorted(set(golden) | set(run))
        tolerated, differ = 0, 0
        for key in keys:
            have, want = run.get(key, "<missing>"), golden.get(key, "<missing>")
            if have == want:
                continue
            pattern = next((p for p in tolerance if fnmatch.fnmatchcase(key, p)), None)
            spec = tolerance.get(pattern) if pattern else None
            if isinstance(spec, dict) and number(have) and number(want):
                limit = spec.get("abs") or (spec.get("rel") or 0) * abs(want)
                if abs(have - want) <= limit:
                    tolerated += 1
                    continue
                row("golden", key, have, f"{want} ({pattern}: {spec})", False)
            else:
                row("golden", key, have, want, False)
            differ += 1
        row("golden", f"{len(keys)} metrics", f"{len(keys) - tolerated - differ} identical, {tolerated} within tolerance, "
            f"{differ} different", golden_path.split("signoff/")[-1], differ == 0)

    for key in limits.get("info", {}).get("keys", []):
        row("info", key, run.get(key, "<missing>"), "-", True)

    print(f"signoff: {'PASS' if fail == 0 else f'FAIL ({fail} rows)'}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: check_signoff.py <metrics.json> <limits.toml> <golden metrics.json>")
        sys.exit(2)
    sys.exit(main(*sys.argv[1:]))
