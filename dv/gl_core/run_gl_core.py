#!/usr/bin/env python3
"""make gl-core: Phase 2 GL ISA regression of the hardened PicoRV32 (project-plan.md §8 Phase 2).

Runs the upstream PicoRV32 test firmware (third_party/picorv32/firmware: 45 instruction tests,
IRQ, multiply/divide, sieve, stats) with the upstream testbench.v -DSYNTH_TEST twice:
  rtl : upstream RTL picorv32 with the SoC parameters (reference)
  gl  : the final netlist of `make harden-core` with the sky130_fd_sc_hd Verilog cell models
        (-DFUNCTIONAL -DUNIT_DELAY=#1, files from CELL_VERILOG_MODELS in LibreLane's resolved.json)
The testbench, firmware and picorv32_axi_adapter are upstream and unmodified; the files added
around them are dv/gl_core/picorv32_axi_shim.v and dv/gl_core/gl_core_boot.v (see their headers).

PASS needs all of:
  - the harden run passed all its own checks (<harden-run>_signoff/result.txt says
    `harden-core: PASS`: signoff limits and golden, disconnected pins, CPU parameters, source
    tracking), so a netlist that failed signoff or came from uncommitted files is not used
  - cpu_params.py PASS (config.json SYNTH_PARAMETERS == soc_top u_cpu parameters == the
    SYNTH_PARAMETERS the harden run used, from its resolved.json)
  - the firmware IRQ handler address (symbol irq_vec) == PROGADDR_IRQ of the core
  - each run: upstream success protocol as in scripts/core_stock.sh (`ALL TESTS PASSED.`, `DONE`,
    `TRAP after N clock cycles`, every tests/*.S prints `<name>..OK`, no ERROR!/..ERROR/TIMEOUT/
    OUT-OF-BOUNDS), the reset-address jump was installed, no gl-core-boot ERROR
  - each bus trace: non-empty, address/strobe/I-D without X/Z (data may be X, see TRACE_LINE);
    first transfer is the jump fetched at PROGADDR_RESET,
    the second a fetch from 0; PROGADDR_RESET is not accessed again
  - the RTL and GL bus traces are identical line by line (cycle, addr, data, strobe, I/D),
    and both runs report the same TRAP cycle

usage: run_gl_core.py [--harden-run <dir>] [--netlist <path>] [--out <dir>]
  --harden-run  LibreLane run of `make harden-core` (default runs/picorv32_core); gives the
                cell model list (resolved.json) and the default netlist (final/nl/picorv32.nl.v)
  --netlist     netlist to simulate instead; used by negative tests that simulate an edited copy
  --out      output directory (default runs/gl_core)
Prints `gl-core: PASS` / `gl-core: FAIL`; exit code 0 only on PASS. Python stdlib only.
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
sys.path.insert(0, os.path.join(ROOT, "pnr", "picorv32_core"))
from cpu_params import parse_verilog_int  # noqa: E402  (same literal parser as the parameter check)
HERE = os.path.join(ROOT, "dv", "gl_core")
SUBMODULE = os.path.join(ROOT, "third_party", "picorv32")
TOOLCHAIN_PREFIX = "riscv64-elf-"
SHIM = os.path.join(HERE, "picorv32_axi_shim.v")
BOOT = os.path.join(HERE, "gl_core_boot.v")
FAIL_TEXT = re.compile(r"ERROR!|\.\.ERROR$|^TIMEOUT$|OUT-OF-BOUNDS|gl-core-boot: ERROR", re.M)
# Address, strobe and I/D must be known. The data field may hold X: the upstream IRQ code saves
# registers that were never written (PicoRV32 does not reset its register file, REGS_INIT_ZERO=0)
# to irq_regs (0x200-0x27c) and to the IRQ stack below irq_stack (0x480), and reads them back
# (84 such transfers). Such X must be identical in RTL and GL (trace comparison).
TRACE_LINE = re.compile(r"^(\d+) (R [0-9a-f]{8} [0-9a-fxXzZ]{8} [ID]|W [0-9a-f]{8} [0-9a-fxXzZ]{8} [01]{4})$")


def pin(name):
    with open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf8") as f:
        for line in f:
            m = re.match(rf"^{name}\s*=\s*(\S+)", line)
            if m:
                return m.group(1)
    raise KeyError(name)


def sh(cmd, log, cwd=None):
    """Run cmd, append its output to log, return exit code."""
    with open(log, "a", encoding="utf8") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        return subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT).returncode


def strip_modules(text, names):
    """Return text without the `module <name> ... endmodule` blocks; each name must occur once."""
    out, found, skipping = [], {n: 0 for n in names}, False
    for line in text.splitlines(keepends=True):
        m = re.match(r"module\s+(\w+)\b", line)
        if not skipping and m and m.group(1) in names:
            found[m.group(1)] += 1
            skipping = True
            continue
        if skipping:
            if re.match(r"endmodule\b", line):
                skipping = False
            continue
        out.append(line)
    bad = {n: c for n, c in found.items() if c != 1}
    if bad or skipping:
        raise ValueError(f"module blocks not found exactly once: {bad}")
    return "".join(out)


def check_run(name, log_path, trace_path, tests, reset_addr):
    """Return (errors, trap_cycle, trace_lines) for one simulation run."""
    errors = []
    log = open(log_path, encoding="utf8", errors="replace").read()
    lines = log.splitlines()
    if "ALL TESTS PASSED." not in lines:
        errors.append("missing 'ALL TESTS PASSED.'")
    if "DONE" not in lines:
        errors.append("missing firmware 'DONE'")
    cycles = re.findall(r"^TRAP after (\d+) clock cycles$", log, re.M)
    if len(cycles) != 1:
        errors.append(f"expected one 'TRAP after N clock cycles', found {len(cycles)}")
    missing = [t for t in tests if f"{t}..OK" not in lines]
    if missing:
        errors.append(f"instruction tests OK {len(tests) - len(missing)}/{len(tests)}, missing: {' '.join(missing)}")
    bad = FAIL_TEXT.search(log)
    if bad:
        errors.append(f"failure text in log: {bad.group(0)!r}")
    if reset_addr != 0 and not re.search(rf"^gl-core-boot: reset address {reset_addr:08x} holds jal x0", log, re.M):
        errors.append("reset-address jump was not installed")

    trace = []
    if os.path.exists(trace_path):
        trace = open(trace_path, encoding="utf8").read().splitlines()
    if not trace:
        errors.append("bus trace is empty")
    for i, t in enumerate(trace):
        if not TRACE_LINE.match(t):
            errors.append(f"bus trace line {i + 1} malformed or has X/Z outside the data field: {t!r}")
            break
    if reset_addr != 0 and len(trace) >= 2:
        first, second = trace[0].split(" ", 1)[1], trace[1].split(" ", 1)[1]
        if not re.fullmatch(rf"R {reset_addr:08x} [0-9a-f]{{8}} I", first):
            errors.append(f"first transfer is {first!r}, expected the fetch at the reset address {reset_addr:08x}")
        if not re.fullmatch(r"R 00000000 [0-9a-f]{8} I", second):
            errors.append(f"second transfer is {second!r}, expected a fetch from 00000000")
        again = [t for t in trace[1:] if t.split(" ")[2] == f"{reset_addr:08x}"]
        if again:
            errors.append(f"reset address accessed again: {again[0]!r}")
    print(f"  [{'PASS' if not errors else 'FAIL'}] {name}: " +
          ("; ".join(errors) if errors else
           f"ALL TESTS PASSED, DONE, {len(tests)}/{len(tests)} instruction tests OK, "
           f"TRAP after {cycles[0]} cycles, {len(trace)} bus transfers "
           f"({sum(1 for t in trace if re.search(r'[xXzZ]', t))} with X data)"))
    return errors, (cycles[0] if len(cycles) == 1 else None), trace


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harden-run", default=os.path.join(ROOT, "runs", "picorv32_core"))
    ap.add_argument("--netlist")
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "gl_core"))
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    harden_run = os.path.abspath(args.harden_run)
    netlist = os.path.abspath(args.netlist or os.path.join(harden_run, "final", "nl", "picorv32.nl.v"))
    t0 = time.time()

    def fail(msg):
        print(f"gl-core: FAIL ({msg})")
        return 1

    for tool in ("git", "make", "yosys", "iverilog", "vvp", f"{TOOLCHAIN_PREFIX}gcc", f"{TOOLCHAIN_PREFIX}nm"):
        if shutil.which(tool) is None:
            return fail(f"tool not found: {tool}")
    if not os.path.isfile(netlist):
        return fail(f"netlist not found: {netlist}; run `make harden-core` first")
    resolved = os.path.join(harden_run, "resolved.json")
    if not os.path.isfile(resolved):
        return fail(f"{resolved} not found; run `make harden-core` first")
    with open(resolved, encoding="utf8") as f:
        cell_models = json.load(f)["CELL_VERILOG_MODELS"]
    signoff_dir = harden_run.rstrip(os.sep) + "_signoff"
    path = os.path.join(signoff_dir, "result.txt")
    lines = open(path, encoding="utf8").read().splitlines() if os.path.isfile(path) else []
    if lines != ["harden-core: PASS"]:
        return fail(f"{path} does not say 'harden-core: PASS': the harden run did not pass; run `make harden-core`")
    have = subprocess.run(["git", "-C", SUBMODULE, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if have != pin("PICORV32_COMMIT"):
        return fail(f"third_party/picorv32 is at {have[:12]}, env/versions.mk pins {pin('PICORV32_COMMIT')[:12]}")

    # Only paths below the output directory are removed.
    shutil.rmtree(out, ignore_errors=True)
    inc, src = os.path.join(out, "inc"), os.path.join(out, "src")
    os.makedirs(inc)
    os.makedirs(src)
    build_log = os.path.join(out, "build.log")

    print("[gl-core] CPU parameters: config.json vs soc_top u_cpu")
    rc = subprocess.run([sys.executable, os.path.join(ROOT, "pnr", "picorv32_core", "cpu_params.py"),
                         "--emit-dir", inc, "--resolved", resolved]).returncode
    if rc != 0:
        return fail("cpu_params.py")
    defines = dict(re.findall(r"^`define CPU_(\w+) (\S+)$", open(os.path.join(inc, "cpu_defines.vh")).read(), re.M))
    num = parse_verilog_int
    reset_addr, irq_addr = num(defines.get("PROGADDR_RESET", "0")), num(defines.get("PROGADDR_IRQ", "16"))

    print("[gl-core] export upstream PicoRV32 and build its test firmware")
    archive = subprocess.run(["git", "-C", SUBMODULE, "archive", "HEAD"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", src], input=archive, check=True)
    if sh(["make", f"TOOLCHAIN_PREFIX={TOOLCHAIN_PREFIX}", "firmware/firmware.hex"], build_log, cwd=src) != 0:
        return fail(f"firmware build failed, see {build_log}")
    nm = subprocess.run([f"{TOOLCHAIN_PREFIX}nm", os.path.join(src, "firmware", "firmware.elf")],
                        capture_output=True, text=True, check=True).stdout
    m = re.search(r"^([0-9a-f]+) \w irq_vec$", nm, re.M)
    if not m or int(m.group(1), 16) != irq_addr:
        return fail(f"firmware irq_vec is at {m.group(1) if m else 'nowhere'}, core PROGADDR_IRQ is {irq_addr:08x}")
    tests = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(src, "tests", "*.S")))

    upstream = open(os.path.join(src, "picorv32.v"), encoding="utf8").read()
    rtl_lib, gl_lib = os.path.join(out, "picorv32_rtl_lib.v"), os.path.join(out, "picorv32_gl_lib.v")
    open(rtl_lib, "w").write(strip_modules(upstream, ["picorv32_axi"]))
    open(gl_lib, "w").write(strip_modules(upstream, ["picorv32_axi", "picorv32"]))

    common = ["iverilog", "-DSYNTH_TEST", f"-I{inc}", "-s", "testbench", "-s", "gl_core_boot"]
    tb = [os.path.join(src, "testbench.v"), SHIM, BOOT]
    builds = {
        "rtl": common + ["-DGL_CORE_RTL_REF", "-o", os.path.join(out, "rtl.vvp")] + tb + [rtl_lib],
        "gl": common + ["-DFUNCTIONAL", "-DUNIT_DELAY=#1", "-o", os.path.join(out, "gl.vvp")]
              + tb + [gl_lib, netlist] + cell_models,
    }
    results = {}
    for name, cmd in builds.items():
        print(f"[gl-core] {name}: compile and run (log: {out}/{name}.log)")
        t1 = time.time()
        if sh(cmd, build_log) != 0:
            return fail(f"{name} compile failed, see {build_log}")
        log = os.path.join(out, f"{name}.log")
        # vvp runs in the exported tree: testbench.v reads firmware/firmware.hex relative to it.
        sh(["vvp", "-N", os.path.join(out, f"{name}.vvp"), f"+bus_trace=../{name}.trace"], log, cwd=src)
        print(f"[gl-core] {name}: finished in {time.time() - t1:.0f} s")
        results[name] = check_run(name, log, os.path.join(out, f"{name}.trace"), tests, reset_addr)

    errors = [f"{n}: {e}" for n, (errs, _, _) in results.items() for e in errs]
    (_, rtl_cyc, rtl_tr), (_, gl_cyc, gl_tr) = results["rtl"], results["gl"]
    diff = next((i for i, (a, b) in enumerate(zip(rtl_tr, gl_tr)) if a != b), None)
    if diff is None and len(rtl_tr) != len(gl_tr):
        diff = min(len(rtl_tr), len(gl_tr))
    if diff is not None:
        a = rtl_tr[diff] if diff < len(rtl_tr) else "<end>"
        b = gl_tr[diff] if diff < len(gl_tr) else "<end>"
        errors.append(f"bus traces differ at transfer {diff + 1}: rtl {a!r} gl {b!r}")
    print(f"  [{'PASS' if diff is None else 'FAIL'}] rtl vs gl bus trace: " +
          (f"{len(gl_tr)} transfers identical" if diff is None else errors[-1]))
    if rtl_cyc != gl_cyc:
        errors.append(f"TRAP cycle differs: rtl {rtl_cyc} gl {gl_cyc}")
        print(f"  [FAIL] {errors[-1]}")
    status = "PASS" if not errors else "FAIL"
    with open(os.path.join(out, "summary.txt"), "w", encoding="utf8") as f:
        f.write(f"gl-core: {status}\nnetlist: {netlist}\n" + "".join(f"error: {e}\n" for e in errors))
    print(f"gl-core: {status}" + (f" ({len(errors)} errors)" if errors else "") + f" in {time.time() - t0:.0f} s")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
