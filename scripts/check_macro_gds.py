#!/usr/bin/env python3
"""The macro in the final GDS is the macro's own GDS: same cells, same contents (Phase 6, ADR-0018; skill
macro-qualification).

usage: check_macro_gds.py --cell <macro> --macro-gds <macro.gds> --final-gds <design.gds>

Why (2026-10-10): with an OpenRAM LEF that had no FOREIGN, LibreLane's KLayout stream-out kept an empty macro cell
in the final GDS and printed "All LEF cells have matching GDS cells"; only the Magic/KLayout XOR (5.69 million
differences) showed it. If both stream-outs went wrong the same way, XOR would pass. Also, a GDS cell name is
global: OpenRAM prefixes its own cells with the macro name, but its library cells (sky130_fd_bd_sram__openram_*,
the bitcells) keep theirs, so another GDS defining one of them would replace it silently (one definition per name).
Checks:
  - the final GDS has <macro>, and the cells below it are exactly the cells below <macro> in the macro GDS;
  - each of those cells has the same fingerprint (scripts/gds_cells.py: every shape in full per layer, instances);
  - no cell of the final GDS is a renamed copy of one of them (`<name>$<n>`, KLayout's conflict resolution).
Cells without the macro-name prefix are listed in the PASS line. KLayout from LibreLane's nix-shell.
Prints `macro-gds: PASS ...` / `macro-gds: FAIL ...`; exit 0 only on PASS. Negative tests: neg_pnr.py P67, P68.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def cells(gds, cell):
    """{"all": [...], "tree": {name: sha1} or None} of gds, or None if KLayout failed."""
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    cmd = f"klayout -b -rd src='{os.path.abspath(gds)}' -rd cell={cell} -r '{os.path.join(HERE, 'gds_cells.py')}'"
    env = dict(os.environ)
    env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    r = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, capture_output=True, text=True, env=env)
    m = re.search(r"^GDS_CELLS (.*)$", r.stdout, re.M)
    return json.loads(m.group(1)) if m else None


def compare(cell, macro, final):
    """Problems (list of str) of the final GDS's copy of `cell` against the macro GDS's."""
    if macro is None or macro["tree"] is None:
        return [f"{cell} not found in the macro GDS"]
    if final is None or final["tree"] is None:
        return [f"{cell} not found in the final GDS"]
    want, have = macro["tree"], final["tree"]
    out = []
    missing, extra = sorted(set(want) - set(have)), sorted(set(have) - set(want))
    if missing:
        out.append(f"{len(missing)} cell(s) of the macro missing below {cell} in the final GDS, e.g. {missing[:3]}")
    if extra:
        out.append(f"{len(extra)} cell(s) below {cell} that the macro GDS does not have, e.g. {extra[:3]}")
    differ = sorted(n for n in set(want) & set(have) if want[n] != have[n])
    if differ:
        out.append(f"{len(differ)} cell(s) with other contents than in the macro GDS, e.g. {differ[:3]}")
    renamed = sorted(n for n in final["all"] if re.fullmatch(r"(.+)\$\d+", n) and n.rsplit("$", 1)[0] in want)
    if renamed:
        out.append(f"renamed copies of macro cells (a cell name defined twice): {renamed[:3]}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--cell", required=True)
    ap.add_argument("--macro-gds", required=True)
    ap.add_argument("--final-gds", required=True)
    a = ap.parse_args(argv)
    macro, final = cells(a.macro_gds, a.cell), cells(a.final_gds, a.cell)
    problems = compare(a.cell, macro, final)
    if problems:
        print(f"macro-gds: FAIL - {a.cell}: " + "; ".join(problems))
        return 1
    plain = sorted(n for n in macro["tree"] if not n.startswith(a.cell))
    print(f"macro-gds: PASS - {a.cell}: {len(macro['tree'])} cells identical to the macro GDS, none renamed; "
          f"{len(plain)} without the macro-name prefix, each defined once: {', '.join(plain[:4])}"
          + (" ..." if len(plain) > 4 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
