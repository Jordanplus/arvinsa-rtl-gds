#!/usr/bin/env python3
"""Formal equivalence (EQY): synthesized netlist vs final netlist of one LibreLane run.

usage: run_eqy.py --design <tag> [--run <dir>] [--netlist <path>] [--out <dir>] [-j N]
  --design   picorv32_core | soc_top | soc_top_hazard3 | user_project_wrapper (the run tag: default run
             directory runs/<design>; soc_top_hazard3 is soc_top with Hazard3, make harden-soc CPU=hazard3;
             user_project_wrapper is the Caravel wrapper with that SoC flattened into it, Phase 7)
  --run      LibreLane run directory
  --netlist  gate netlist to check instead of <run>/final/nl/<DESIGN_NAME>.nl.v (negative tests)
  --out      output directory (default runs/eqy_<design>)
  -j         parallel EQY jobs (default: CPU count)

What is proved (README.md next to this file):
  gold  <run>/*-yosys-synthesis/<DESIGN_NAME>.nl.v  (Yosys output, before placement and routing)
  gate  <run>/final/nl/<DESIGN_NAME>.nl.v           (after OpenROAD: resizing, buffering, CTS,
                                                     hold buffers, diodes, tie cells, ...)
  Both use the sky130_fd_sc_hd Verilog models (CELL_VERILOG_MODELS in resolved.json) converted by
  eqy.formal_pdk_proc. Macros (MACROS[*].vh in resolved.json) are blackboxes on both sides.
  EQY cuts both netlists at signals with the same name and proves every cut equivalent; a
  wrong netlist edit anywhere in the final netlist makes a partition FAIL.

Settings found necessary (see README.md for the evidence):
  - stack 64 MB (`ulimit -s 65520`): EQY's partition step recurses deeply and crashes with
    SIGSEGV under the 8 MB default
  - `delete t:$scopeinfo` after flattening: Yosys 0.62 keeps $scopeinfo cells
  - [options] insbuf off: OpenROAD puts output buffers between a flip-flop and the port it drives
    and renames the flip-flop output net; without insbuf the buffered nets are aliases of the
    matched port bit instead of separate unmatched state

PASS needs: the harden run passed all its checks and was made from the commit checked out now
(signoff/scripts/run_guard.py: <run>_signoff/result.txt says `harden-core: PASS` or `harden-soc: PASS`,
which includes signoff limits, golden and source tracking; provenance.json records HEAD),
EQY ends with `DONE (PASS, rc=0)`, the partition list is not empty, every partition is in a
`Proved equivalence of partition` line, and the partition log has no `found constant ... bit`
line (EQY maps such a bit to the constant without proving it; see README.md), and the sequential
cells (flip-flops, latches, clock gates) of the two netlists are the same instances with the same
cell function, only the drive strength may differ (sequential_cells below), and the clock pin of
every sequential cell and macro reaches the same port (or constant) through buffers and inverters,
with the same inversion, in both netlists (clock_sources below), and every MACROS instance of the
config is parsed in both netlists. Input pins of a combinational cell that the final netlist only
permutes (an OpenROAD pin swap, pin_swaps below) are left out of EQY's name matching; the cell
output is still proved. When EQY ran to the end and its only problem is at most MAX_AMEND partitions
not proved, EQY runs once more with each of them amended with the partitions that drive its inputs
(amend_rules below, ADR-0019 decision 23); the verdict is that second round's, every partition must
be proved in it, and the partitions that needed it are printed as INFO. Prints `eqy: PASS` /
`eqy: FAIL`; exit code 0 only on PASS.

Why the sequential cells are compared outside EQY (Phase 4): EQY's sat strategy does not prove the
behaviour of a flip-flop itself. A final netlist with one dfxtp_2 replaced by a dfrtp_2 whose
RESET_B is the resetn port (the flip-flop clears while reset is low) still gave 18100/18100
partitions proved (neg_eqy.py flop_async_reset); probably the initial-state constraints of such
a partition are unsatisfiable, so its base case proves nothing (agent experiment, 2026-10-04, not
saved). The logic around each flip-flop (its D input and everything its Q drives) is still proved
by EQY; the flip-flop cell and its clock connection are checked here. EQY does not check the clock
either: its sat strategy runs formalff -clk2ff, which puts every flip-flop on one implicit clock.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Verdict line of <run>_signoff/result.txt for each run tag (signoff/scripts/run_guard.py).
VERDICT = {"picorv32_core": "harden-core: PASS", "soc_top": "harden-soc: PASS", "soc_top_hazard3": "harden-soc: PASS",
           "user_project_wrapper": "harden-soc: PASS"}
# sky130_fd_sc_hd sequential cells: flip-flops (df*, edf*, sdf*, sedf*), latches (dlx*, dlr*) and
# clock gates (dlclkp, sdlclkp). Not the delay buffers dlygate*/dlymetal*/dlybuf*, which are
# combinational.
SEQ_CELL = re.compile(r"^\s*sky130_fd_sc_hd__((?:df|edf|sdf|sedf)\w*?|dl[xr]\w*?|s?dlclkp)_\d+\s+(\S+)\s*\(", re.M)
sys.path.insert(0, os.path.join(ROOT, "signoff", "scripts"))
from run_guard import guard  # noqa: E402
STACK_KB = 65520  # macOS hard limit for the main thread stack
# At most this many partitions not proved in the first round get the amend retry (amend_rules); more
# FAIL directly (a real error; the retry would only cost time).
MAX_AMEND = 20
# Any cell, standard cell or macro. Up to Phase 6 step 4a this matched sky130_\w+ only, and the
# self-generated arv_sram_* macro was not parsed: clock_sources skipped sram0/clk0 and clk1 and
# eqy-soc still PASSed (found by neg_eqy.py clk0_inverted, 2026-10-10). main() now also requires
# every MACROS instance of the config to be parsed.
INST = re.compile(r"^\s*(?!(?:module|macromodule|input|output|inout|wire|reg|assign|supply0|supply1)\b)"
                  r"([A-Za-z_]\w*)\s+(\S+)\s*\((.*?)\);", re.M | re.S)
PIN = re.compile(r"\.(\w+)\(((?:\{[^}]*\})|[^()]*)\)")
# Cells a clock passes through between a port and a clock pin (CTS buffers, delay buffers,
# inverters); group 2 is set for the inverting ones. Output pins of sky130_fd_sc_hd cells.
CLOCK_PATH = re.compile(r"sky130_fd_sc_hd__(?:(buf|clkbuf|bufbuf|dlygate4sd\d|dlymetal6s\ds|clkdlybuf4s\d+)|"
                        r"(inv|clkinv|clkinvlp|bufinv))_\d+$")
OUT_PINS = ("X", "Y", "Q", "Q_N", "GCLK", "HI", "LO", "COUT", "SUM")
CLOCK_PINS = ("CLK", "CLK_N", "GATE", "GATE_N")


def nix_shell(cmd, log):
    """Run cmd (a shell string) inside the pinned LibreLane nix-shell; return exit code."""
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    env = dict(os.environ)
    nix_bin = "/nix/var/nix/profiles/default/bin"
    if shutil.which("nix-shell") is None and os.path.isdir(nix_bin):
        env["PATH"] = nix_bin + os.pathsep + env.get("PATH", "")
    with open(log, "a", encoding="utf8") as f:
        f.write(f"$ (cd {ll_dir} && nix-shell --run {cmd!r})\n")
        f.flush()
        return subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env,
                              stdout=f, stderr=subprocess.STDOUT).returncode


def eqy_script(top, cells, gold, gate, blackboxes, nomatch=(), amend=()):
    bb = "".join(f"read_verilog -sv {b}\n" for b in blackboxes)
    match = "".join(f"{side}-nomatch {n}\n" for side in ("gold", "gate") for n in nomatch)
    rules = "".join(f"amend {driver} {part}\n" for driver, part in amend)
    return f"""# Generated by signoff/eqy/run_eqy.py
[options]
splitnets on
insbuf off

[gold]
{bb}read_verilog -sv {cells} {gold}

[gate]
{bb}read_verilog -sv {cells} {gate}

[script]
hierarchy -top {top}
proc
prep -top {top} -flatten
delete t:$scopeinfo
opt_clean
async2sync

[strategy sat]
use sat
depth 5

[strategy pdr]
use sby
engine abc pdr
""" + (f"\n[match {top}]\n{match}" if match else "") + (f"\n[partition {top}]\n{rules}" if rules else "")


def amend_rules(work, top, unproved, seq):
    """EQY `amend <input> <partition>` rules for each partition in `unproved` (names "<top>.<po>"):
    one rule per input of the partition, so that the partitions driving its inputs are added to it.
    EQY cuts at every matched name and proves each partition with its inputs free; when the final
    netlist computes a function through a net that also has a matched name, the partition loses how
    that net depends on its other inputs, and the free input gives a counterexample no circuit
    reaches. Seen on the Caravel wrapper (Phase 7, ADR-0019 decision 23): OpenROAD swapped the inputs
    of or4 _10121_, the gate-side model then shared the OR of _10119_ (net _06100_, matched as
    _10119_.X / _10120_.B), and partition _10122_.B was not proved; amending it with the partition
    of _10119_.X proved all 16149. Only inputs driven by combinational logic get a rule: an input
    that is the output of a sequential cell (its instance in `seq`, e.g. _20986_.dff0.Q) would add a
    flip-flop to the partition, and EQY's sat strategy proves such a partition vacuously
    (formal-equivalence-eqy rule 5). Found by neg_eqy.py nand2_to_nor2 (Phase 7): amending with its
    two flip-flop inputs put two $sdff into the partition and the wrong nor2 was "proved";
    amended_sequential() checks the second round for this. Amending with combinational logic adds
    the real driving logic and assumes nothing; every matched name is still proved in its own
    partition. Inputs whose names are not plain EQY patterns (globs) get no rule either, so such a
    partition stays unproved (FAIL)."""
    rules = []
    for part in unproved:
        po = part[len(top) + 1:] if part.startswith(top + ".") else None
        il = os.path.join(work, "partitions", f"{part}.il")
        if not po or not os.path.isfile(il) or not re.fullmatch(r"[A-Za-z0-9_.]+", po):
            continue
        for pi in sorted(set(re.findall(r"^\s*wire input \d+ \\__pi_(\S+)$", open(il, encoding="utf8").read(), re.M))):
            if re.fullmatch(r"[A-Za-z0-9_.]+", pi) and pi.split(".")[0] not in seq:
                rules.append((pi, po))
    return rules


SEQ_RTLIL = re.compile(r"^\s*cell \$(\w*(?:dff|ff|latch|sr)\w*) ", re.M | re.I)


def amended_sequential(work, parts):
    """{partition: [RTLIL sequential cell types]} of the partitions in `parts` whose RTLIL
    (<work>/partitions/<partition>.il) has a flip-flop, latch or SR cell. A partition amended with
    sequential logic is proved vacuously by the sat strategy (amend_rules), so any is a FAIL."""
    out = {}
    for part in parts:
        il = os.path.join(work, "partitions", f"{part}.il")
        cells = sorted(set(SEQ_RTLIL.findall(open(il, encoding="utf8").read()))) if os.path.isfile(il) else ["missing"]
        if cells:
            out[part] = cells
    return out


def sequential_cells(text):
    """{instance name (no backslash): cell function, i.e. the cell name without the drive strength}."""
    return {name.lstrip("\\"): base for base, name in SEQ_CELL.findall(text)}


def instances(text):
    """{instance: (cell, {pin: [nets]})} of a flat gate netlist (escaped names without the backslash)."""
    out = {}
    for cell, name, body in INST.findall(text):
        pins = {}
        for pin, val in PIN.findall(body):
            val = val.strip()
            nets = [v.strip() for v in val[1:-1].split(",")] if val.startswith("{") else [val]
            pins[pin] = [n.lstrip("\\").strip() for n in nets if n]
        out[name.lstrip("\\")] = (cell, pins)
    return out


def clock_sources(text):
    """{"<instance>/<pin>": source} for the clock pin of every sequential cell and every macro pin
    named clk*. The source is what the pin reaches walking back through buffers and inverters: an
    input port ("clk"), a constant ("1'b0"), or the output of another cell ("and2.X"); "~" in front
    when the walk passed an odd number of inverters. The sequential cell check above only compares
    cell types, and EQY's sat strategy turns every flip-flop into one on a common implicit clock
    (formalff -clk2ff), so a flip-flop clocked by the inverted clock would pass both (Phase 4
    review)."""
    insts = instances(text)
    ports = {p.lstrip("\\") for p in re.findall(r"^\s*input\s+(?:\[[^\]]*\]\s*)?(\S+?)\s*;", text, re.M)}
    driver = {}
    for name, (cell, pins) in insts.items():
        for pin in OUT_PINS:
            for net in pins.get(pin, []):
                driver[net] = (name, cell, pin)

    def source(net):
        inv = False
        for _ in range(200):
            if net in ports:
                return ("~" if inv else "") + net
            if re.fullmatch(r"1'b[01]", net):
                return f"1'b{int(net[-1]) ^ inv}"
            if net not in driver:
                return ("~" if inv else "") + "undriven"
            name, cell, pin = driver[net]
            path = CLOCK_PATH.match(cell)
            if path and insts[name][1].get("A"):
                inv ^= bool(path.group(2))
                net = insts[name][1]["A"][0]
                continue
            if cell.startswith("sky130_fd_sc_hd__conb_"):
                return f"1'b{int(pin == 'HI') ^ inv}"
            return ("~" if inv else "") + re.sub(r"^sky130_fd_sc_hd__|_\d+$", "", cell) + "." + pin
        return "loop"

    seq = sequential_cells(text)
    out = {}
    for name, (cell, pins) in insts.items():
        if name in seq:
            keys = [p for p in CLOCK_PINS if p in pins]
        elif not cell.startswith("sky130_fd_sc_hd__"):
            keys = [p for p in pins if re.fullmatch(r"clk\d*", p, re.I)]
        else:
            continue
        for pin in keys:
            out[f"{name}/{pin}"] = source(pins[pin][0]) if pins[pin] else "unconnected"
        if name in seq and not keys:
            out[f"{name}/<clock pin>"] = "missing"
    return out


def data_sources(text):
    """{instance: (cell function, {input pin: source})} of every combinational sky130_fd_sc_hd cell.
    The source is what the pin reaches walking back through non-inverting buffers: an input port,
    a constant, or "<instance>.<output pin>" of the driving cell."""
    insts = instances(text)
    seq = sequential_cells(text)
    driver = {net: (name, pin) for name, (cell, pins) in insts.items() for pin in OUT_PINS for net in pins.get(pin, [])}

    def source(net):
        for _ in range(200):
            if net not in driver:
                return net
            name, pin = driver[net]
            path = CLOCK_PATH.match(insts[name][0])
            if path and path.group(1) and insts[name][1].get("A"):
                net = insts[name][1]["A"][0]
                continue
            return f"{name}.{pin}"
        return "loop"

    return {name: (re.sub(r"_\d+$", "", cell), {p: source(v[0]) if v else "unconnected"
                                                for p, v in pins.items() if p not in OUT_PINS})
            for name, (cell, pins) in insts.items() if cell.startswith("sky130_fd_sc_hd__") and name not in seq}


def pin_swaps(gold_text, gate_text):
    """{instance: [input pins]} of the combinational cells whose input connections the final
    netlist permutes: same instance, same cell function, and the moved pins reach the same sources
    in another order. OpenROAD repair_timing does this to equivalent inputs (SwapPinsMove,
    `RSZ-0043 Swapped pins on N instances`), e.g. Hazard3 Phase 6: _10787_ or2 A<->B and
    _10793_ o21ai A1<->A2. EQY matches the flattened cell's pin wires by name (_10787_.A), so a
    swap maps one gold signal to two gate signals and EQY refuses to partition
    (`conflicting matches for gold bit`). main() leaves these pin names out of the name matching on
    both sides; the cell output is still a matched name and is proved, so a permutation that changes
    the function (neg_eqy.py mux_swap: mux2 A0<->A1) still FAILs, in the proof."""
    a, b = data_sources(gold_text), data_sources(gate_text)
    out = {}
    for name, (cell, src) in a.items():
        if name not in b or b[name][0] != cell or set(b[name][1]) != set(src):
            continue
        moved = sorted(p for p in src if src[p] != b[name][1][p])
        if moved and sorted(src[p] for p in moved) == sorted(b[name][1][p] for p in moved):
            out[name] = moved
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--design", required=True, choices=sorted(VERDICT))
    ap.add_argument("--run")
    ap.add_argument("--netlist")
    ap.add_argument("--out")
    ap.add_argument("-j", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()
    run = os.path.abspath(args.run or os.path.join(ROOT, "runs", args.design))
    out = os.path.abspath(args.out or os.path.join(ROOT, "runs", f"eqy_{args.design}"))
    t0 = time.time()

    def fail(msg):
        print(f"eqy: FAIL ({msg})")
        return 1

    # Only the output directory is removed, first, so that a refused run leaves no old result behind.
    shutil.rmtree(out, ignore_errors=True)
    verdict = VERDICT[args.design]
    errs = guard(run, verdict)
    if errs:
        return fail("; ".join(errs))
    resolved = os.path.join(run, "resolved.json")
    if not os.path.isfile(resolved):
        return fail(f"{resolved} not found; run the harden step first")
    cfg = json.load(open(resolved, encoding="utf8"))
    top = cfg["DESIGN_NAME"]
    golds = glob.glob(os.path.join(run, "*-yosys-synthesis", f"{top}.nl.v"))
    if len(golds) != 1:
        return fail(f"expected one synthesized netlist {run}/*-yosys-synthesis/{top}.nl.v, found {len(golds)}")
    gold = golds[0]
    gate = os.path.abspath(args.netlist or os.path.join(run, "final", "nl", f"{top}.nl.v"))
    if not os.path.isfile(gate):
        return fail(f"gate netlist not found: {gate}")
    blackboxes = [vh for m in (cfg.get("MACROS") or {}).values() for vh in m.get("vh", [])]
    for p in [gold, gate] + blackboxes + cfg["CELL_VERILOG_MODELS"]:
        if " " in p:
            return fail(f"path contains a space, not supported by the EQY script: {p}")

    os.makedirs(out)
    log = os.path.join(out, "eqy_run.log")
    cells = os.path.join(out, "formal_pdk.v")
    print(f"[eqy] {top}: gold {os.path.relpath(gold, ROOT)}")
    print(f"[eqy] {top}: gate {os.path.relpath(gate, ROOT) if gate.startswith(ROOT) else gate}")
    rc = nix_shell(f"eqy.formal_pdk_proc --output '{cells}' " + " ".join(f"'{m}'" for m in cfg["CELL_VERILOG_MODELS"]), log)
    if rc != 0 or not os.path.isfile(cells):
        return fail(f"eqy.formal_pdk_proc failed, see {log}")
    gold_text, gate_text = open(gold, encoding="utf8").read(), open(gate, encoding="utf8").read()
    swaps = pin_swaps(gold_text, gate_text)
    nomatch = [f"{i}.{p}" for i, pins in sorted(swaps.items()) for p in pins]
    odd = [n for n in nomatch if not re.fullmatch(r"[A-Za-z0-9_.]+", n)]
    if odd:  # EQY match patterns are globs; only plain names are left out, never a pattern
        return fail(f"pin swap on a cell whose name is not a plain EQY match pattern: {', '.join(odd[:3])}")
    if swaps:
        print(f"[eqy] {top}: {len(swaps)} cell(s) with swapped equivalent inputs, pin names left out of the "
              f"name matching: {', '.join(nomatch[:6])}")
    script = os.path.join(out, f"{top}.eqy")

    def eqy_round(amend=()):
        """Run EQY into <out>/work with log <out>/eqy_run.log; return the parsed result."""
        open(script, "w", encoding="utf8").write(eqy_script(top, cells, gold, gate, blackboxes, nomatch, amend))
        print(f"[eqy] {top}: running EQY ({args.j} jobs; log {os.path.relpath(log, ROOT)})")
        rc = nix_shell(f"ulimit -s {STACK_KB} && cd '{out}' && eqy -f '{script}' -d work -j {args.j}", log)
        text = open(log, encoding="utf8", errors="replace").read()
        plist = os.path.join(out, "work", "partition.list")
        # partition.list: one partition per line, "<module> <partition name> : <bits ...>"
        parts = [line.split()[1] for line in open(plist) if line.strip()] if os.path.isfile(plist) else []
        proved = set(re.findall(r"Proved equivalence of partition '([^']+)'", text))
        plog_path = os.path.join(out, "work", "partition.log")
        plog = open(plog_path, encoding="utf8", errors="replace").read() if os.path.isfile(plog_path) else ""
        return {"rc": rc, "parts": parts, "proved": proved,
                "unproved": sorted(set(re.findall(r"Failed to prove equivalence of partition (\S+)", text))),
                # EQY maps a gold bit whose gate counterpart is a constant to that constant and then
                # never proves it (found with neg_eqy.py wdata3_stuck0: an output tied to 0 passed).
                # The positive runs have no such line, so any is a FAIL.
                "constants": re.findall(r"found constant \w+ bit for \w+ bit (\S+): (\S+)", plog),
                "conflicts": re.findall(r"ERROR: (conflicting \w+ for .*)", plog),
                "done": re.findall(r"DONE \((\w+), rc=(\d+)\)", text)}

    r = eqy_round()
    first_missing = [p for p in r["parts"] if p not in r["proved"]]
    amend = []
    # One retry, only when the partitions that were not proved are the only problem (EQY ran to the
    # end, no constant mapping, no refused name match): amend each of them with the partitions that
    # drive its inputs (amend_rules). The first round stays in work_round1/ and eqy_run_round1.log;
    # the verdict and neg_eqy.py read the second round only.
    if (first_missing and r["parts"] and r["done"] and not r["constants"] and not r["conflicts"]
            and len(first_missing) <= MAX_AMEND):
        amend = amend_rules(os.path.join(out, "work"), top, first_missing, sequential_cells(gold_text))
        if amend:
            print(f"[eqy] {top}: {len(first_missing)} partition(s) not proved ({', '.join(first_missing[:3])}); "
                  f"retrying once with {len(amend)} amend rule(s) (the partitions driving their inputs added)")
            os.rename(os.path.join(out, "work"), os.path.join(out, "work_round1"))
            os.rename(log, os.path.join(out, "eqy_run_round1.log"))
            r = eqy_round(amend)
    rc, parts, proved, unproved = r["rc"], r["parts"], r["proved"], r["unproved"]
    constants, conflicts, done = r["constants"], r["conflicts"], r["done"]
    errors = []
    if rc != 0:
        errors.append(f"eqy exit code {rc}")
    if not done or done[-1] != ("PASS", "0"):
        errors.append(f"EQY result {done[-1] if done else 'missing'}")
    if not parts:
        errors.append("no partitions (nothing was compared)")
    missing = [p for p in parts if p not in proved]
    if missing:
        errors.append(f"{len(missing)}/{len(parts)} partitions not proved{' after the amend retry' if amend else ''}, "
                      f"e.g. {', '.join(missing[:5])}")
    if unproved:
        errors.append(f"failed partitions: {', '.join(unproved[:5])}")
    if constants:
        errors.append(f"{len(constants)} matched bit(s) mapped to a constant without proof, e.g. "
                      + ", ".join(f"{b} = {c}" for b, c in constants[:3]))
    if conflicts:
        errors.append(f"EQY partition step refused: {conflicts[0]}")
    vacuous = amended_sequential(os.path.join(out, "work"), first_missing) if amend else {}
    if vacuous:
        errors.append(f"{len(vacuous)} amended partition(s) contain sequential cells, their proof is vacuous: "
                      + ", ".join(f"{p} ({' '.join(c)})" for p, c in list(vacuous.items())[:3]))
    macro_insts = sorted(i for m in (cfg.get("MACROS") or {}).values() for i in (m.get("instances") or {}))
    for side, text in (("synthesized", gold_text), ("final", gate_text)):
        parsed = instances(text)
        lost = [i for i in macro_insts if i not in parsed]
        if lost:
            errors.append(f"macro instance(s) of the config not found in the {side} netlist: {', '.join(lost)}")
    seq_gold, seq_gate = sequential_cells(gold_text), sequential_cells(gate_text)
    seq_bad = sorted(n for n in set(seq_gold) | set(seq_gate) if seq_gold.get(n) != seq_gate.get(n))
    if not seq_gold:
        errors.append("no sequential cell found in the synthesized netlist")
    if seq_bad:
        errors.append(f"{len(seq_bad)} sequential cell(s) differ from the synthesized netlist, e.g. "
                      + ", ".join(f"{n} ({seq_gold.get(n, 'missing')} -> {seq_gate.get(n, 'missing')})" for n in seq_bad[:3]))
    clk_gold, clk_gate = clock_sources(gold_text), clock_sources(gate_text)
    clk_bad = sorted(k for k in set(clk_gold) | set(clk_gate) if clk_gold.get(k) != clk_gate.get(k))
    if not clk_gold:
        errors.append("no clock pin found in the synthesized netlist")
    if clk_bad:
        errors.append(f"{len(clk_bad)} clock pin(s) reach another source than in the synthesized netlist, e.g. "
                      + ", ".join(f"{k} ({clk_gold.get(k, 'missing')} -> {clk_gate.get(k, 'missing')})" for k in clk_bad[:3]))
    matched = sum(1 for line in open(os.path.join(out, "work", "matched.ids")) if not line.startswith("#")) \
        if os.path.isfile(os.path.join(out, "work", "matched.ids")) else 0
    summary = {"design": top, "gold": gold, "gate": gate, "partitions": len(parts), "proved": len(proved),
               "constant_matches": len(constants), "conflicting_matches": len(conflicts), "pin_swaps": swaps,
               "amend_retry": bool(amend), "round1_not_proved": first_missing, "amend_rules": [" ".join(a) for a in amend],
               "amended_sequential": vacuous,
               "sequential_cells": len(seq_gate), "sequential_mismatch": seq_bad,
               "clock_pins": len(clk_gate), "clock_sources": sorted(set(clk_gate.values())),
               "clock_mismatch": sorted({k.split("/")[0] for k in clk_bad}),
               "matched_names": matched, "result": "PASS" if not errors else "FAIL", "errors": errors,
               "wall_time_s": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=2)
    for e in errors:
        print(f"  [FAIL] {e}")
    if errors:
        print(f"eqy: FAIL ({top}; details in {os.path.relpath(log, ROOT)})")
        return 1
    if amend:
        print(f"  [INFO] {top}: {len(first_missing)} partition(s) proved only with the amend retry: "
              f"{', '.join(first_missing[:5])} (rules in summary.json, first round in eqy_run_round1.log)")
    print(f"  [PASS] {top}: {len(proved)}/{len(parts)} partitions proved equivalent, "
          f"{matched} matched names, {len(seq_gate)} sequential cells identical in function, "
          f"{len(clk_gate)} clock pins on the same source ({', '.join(summary['clock_sources'])}), {summary['wall_time_s']} s")
    print("eqy: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
