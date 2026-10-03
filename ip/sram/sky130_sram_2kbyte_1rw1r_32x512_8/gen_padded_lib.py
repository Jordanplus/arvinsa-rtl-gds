#!/usr/bin/env python3
"""Generate padded.lib: a conservative timing model of the prebuilt SRAM macro.

The PDK ships one TT liberty file for this macro, produced by OpenRAM's
analytical model (no SPICE characterization; project-plan.md §5.4, §6.2). Its
numbers are far too optimistic for signoff (clk0 fall -> dout0 0.38-0.53 ns,
minimum_period 1.956 ns). This script copies that file and replaces the timing
numbers with the engineering assumptions recorded in
docs/decisions/0007-sram-padded-lib.md. Everything else (pins, capacitances,
power, memory groups) is copied unchanged.

Changes (each kind must be found the expected number of times, otherwise FAIL):
  library name          <orig> -> <orig>_padded
  falling_edge arcs     cell_rise/cell_fall shifted so the smallest entry is DOUT_DELAY
                        (the load dependence of the original table is kept);
                        rise/fall_transition raised to at least DOUT_TRANSITION
  setup_rising arcs     every entry raised to at least SETUP
  hold_rising arcs      every entry raised to at least HOLD
  minimum_period        raised to at least MIN_PERIOD
  min_pulse_width       raised to at least MIN_PULSE_WIDTH
  max_transition        pin-level limit on addr0/wmask0/addr1 (0.04 ns, the top of the
                        table index) set to INPUT_MAX_TRANSITION

Usage: gen_padded_lib.py <pdk TT .lib> <padded.lib> [--check]
  --check   exit 1 if <padded.lib> differs from what would be generated (stale copy)
"""
import pathlib
import re
import sys

# Engineering assumptions (ns). Rationale and sources: docs/decisions/0007-sram-padded-lib.md.
DOUT_DELAY = 10.0
DOUT_TRANSITION = 0.5
SETUP = 1.0
HOLD = 0.5
MIN_PERIOD = 30.0
MIN_PULSE_WIDTH = 12.0
INPUT_MAX_TRANSITION = 0.5   # = this .lib's own default_max_transition (other input pins)

# Expected counts in the 2 KB 1rw1r macro (2 ports): each kind of change must hit exactly this many.
EXPECT = {
    "falling_edge": 2,     # dout0, dout1
    "setup_rising": 7,     # port 0: din0 addr0 wmask0 csb0 web0; port 1: addr1 csb1
    "hold_rising": 7,
    "minimum_period": 2,   # clk0, clk1
    "min_pulse_width": 2,
    "max_transition": 3,   # pin-level on addr0, wmask0, addr1 (library default_max_transition is kept)
}

NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def fmt(x):
    return f"{x:.3f}"


def find_block_end(text, open_idx):
    """Index just past the '}' that closes the '{' at open_idx."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit("gen_padded_lib: FAIL - unbalanced braces")


def map_values(block, group, fn):
    """Apply fn(list_of_floats) -> list_of_floats to every values(...) inside each `group(...) { }`."""
    out, pos, hits = [], 0, 0
    for m in re.finditer(r"\b" + group + r"\s*\([^)]*\)\s*\{", block):
        if m.start() < pos:
            continue
        end = find_block_end(block, m.end() - 1)
        sub = block[m.start():end]

        def repl(vm):
            nums = [float(x) for x in re.findall(NUM, vm.group(1))]
            new = fn(nums)
            rows = [r for r in re.findall(r'"([^"]*)"', vm.group(1))]
            # Keep the original row shape.
            it = iter(new)
            new_rows = []
            for r in rows:
                n = len(re.findall(NUM, r))
                new_rows.append('"' + ", ".join(fmt(next(it)) for _ in range(n)) + '"')
            return "values(" + ",\\\n                   ".join(new_rows) + ")"

        sub2, n = re.subn(r"values\(((?:[^()]|\n)*?)\)", repl, sub)
        if n == 0:
            raise SystemExit(f"gen_padded_lib: FAIL - no values() in {group}")
        hits += 1
        out.append(block[pos:m.start()])
        out.append(sub2)
        pos = end
    out.append(block[pos:])
    return "".join(out), hits


def transform(src):
    counts = {k: 0 for k in EXPECT}

    m = re.search(r"library\s*\(\s*([A-Za-z0-9_]+)\s*\)", src)
    if not m:
        raise SystemExit("gen_padded_lib: FAIL - no library() header")
    src = src[:m.start(1)] + m.group(1) + "_padded" + src[m.end(1):]

    out, pos = [], 0
    for tm in re.finditer(r"\btiming\s*\(\s*\)\s*\{", src):
        if tm.start() < pos:
            continue
        end = find_block_end(src, tm.end() - 1)
        block = src[tm.start():end]
        tt = re.search(r'timing_type\s*:\s*"?([a-z_]+)"?\s*;', block)
        if not tt:
            raise SystemExit("gen_padded_lib: FAIL - timing() without timing_type")
        kind = tt.group(1)
        if kind == "falling_edge":
            delays = [float(x) for g in ("cell_rise", "cell_fall")
                      for vm in re.finditer(g + r"\s*\([^)]*\)\s*\{[^}]*values\(((?:[^()]|\n)*?)\)", block)
                      for x in re.findall(NUM, vm.group(1))]
            shift = DOUT_DELAY - min(delays)
            for g in ("cell_rise", "cell_fall"):
                block, h = map_values(block, g, lambda v: [x + shift for x in v])
                assert h == 1, (g, h)
            for g in ("rise_transition", "fall_transition"):
                block, h = map_values(block, g, lambda v: [max(x, DOUT_TRANSITION) for x in v])
                assert h == 1, (g, h)
        elif kind in ("setup_rising", "hold_rising"):
            floor = SETUP if kind == "setup_rising" else HOLD
            for g in ("rise_constraint", "fall_constraint"):
                block, h = map_values(block, g, lambda v, f=floor: [max(x, f) for x in v])
                assert h == 1, (kind, g, h)
        elif kind in ("minimum_period", "min_pulse_width"):
            floor = MIN_PERIOD if kind == "minimum_period" else MIN_PULSE_WIDTH
            for g in ("rise_constraint", "fall_constraint"):
                block, h = map_values(block, g, lambda v, f=floor: [max(x, f) for x in v])
                assert h == 1, (kind, g, h)
        else:
            raise SystemExit(f"gen_padded_lib: FAIL - unexpected timing_type {kind}")
        counts[kind] += 1
        out.append(src[pos:tm.start()])
        out.append(block)
        pos = end
    out.append(src[pos:])
    src = "".join(out)

    src, n = re.subn(r"(?<![A-Za-z_])(max_transition\s*:\s*)" + NUM + r"(\s*;)",
                     lambda mm: mm.group(1) + fmt(INPUT_MAX_TRANSITION) + mm.group(2), src)
    counts["max_transition"] = n

    if counts != EXPECT:
        raise SystemExit(f"gen_padded_lib: FAIL - change counts {counts} != expected {EXPECT}")

    header = ("/* GENERATED by ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_padded_lib.py from the PDK TT .lib.\n"
              "   Conservative engineering assumptions, NOT characterized data: see\n"
              "   docs/decisions/0007-sram-padded-lib.md. Do not edit by hand. */\n")
    return header + src


def main(argv):
    if len(argv) not in (3, 4) or (len(argv) == 4 and argv[3] != "--check"):
        print(__doc__)
        return 2
    src_lib, dst = pathlib.Path(argv[1]), pathlib.Path(argv[2])
    want = transform(src_lib.read_text(encoding="utf-8"))
    if len(argv) == 4:
        have = dst.read_text(encoding="utf-8") if dst.exists() else ""
        if have != want:
            print(f"gen_padded_lib: STALE {dst} (regenerate with: python3 {argv[0]} {src_lib} {dst})")
            return 1
        print(f"gen_padded_lib: {dst} is up to date")
        return 0
    dst.write_text(want, encoding="utf-8")
    print(f"gen_padded_lib: wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
