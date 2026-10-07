#!/usr/bin/env python3
"""make core-hazard3: core-level ISA regression of the SoC's Hazard3 configuration (Phase 5,
ADR-0011 user decision 3; the Hazard3 counterpart of make core-stock for PicoRV32).

usage: run.py [--out DIR]          (default runs/core_hazard3)

  1. The configuration header (gen_config.py): the hazard3_config.vh defaults with the overrides
     of rtl/cpu/soc_cpu_hazard3.v, so the core under test is the SoC's.
  2. The upstream Verilator testbench (third_party/hazard3/test/sim/tb_verilator, tb.v with
     hazard3_cpu_2port: the same hazard3_core; the 1-port bus wrapper is covered by the SoC DV)
     built with that header. Every output goes under DIR: BUILD_DIR, TBEXEC and VINCDIR are set
     on the make command line, nothing is written into the submodule.
  3. riscv-tests (the Hazard3 author's fork, env_p_hazard3) rv32ui, rv32uc, rv32um, rv32mi built
     out of tree (make -f <src>/isa/Makefile src_dir=...) with the xPack toolchain (make
     xpack-fetch); rv32ua is not built (EXTENSION_A = 0).
  4. Each test runs on the testbench with --cpuret: exit code 0 = PASS. UNSUPPORTED tests test
     an optional feature this configuration leaves out and must FAIL (a PASS there means the
     configuration changed and this list must be looked at again).
  5. Negative test: the same flow with EXTENSION_M = 0; every rv32um test must FAIL, which shows
     that a core without a feature the SoC uses is caught.
  6. Instruction-by-instruction comparison with the rvcpp ISS (compare_trace.py) for rv32ui, rv32uc
     and rv32um: the testbench is built again with HAZARD3_RVFI_STANDALONE and rvfi_trace.sv bound
     into it; rvcpp is built from a copy of its sources with rvcpp_fence.patch (upstream rvcpp
     treats fence as illegal). Both traces start at the test's first test_N label: before it, the
     environment probes optional CSRs (PMP, satp) that rvcpp implements for the full Hazard3
     configuration. rv32mi is not compared for the same reason (rvcpp's CSR model, counters
     included, is the full configuration's; it fails rv32mi csr, illegal, instret_overflow and
     zicntr, which this core passes). NO_TRACE lists the tests without a test body to compare.
     The comparator's self-test (injected differences) must PASS first.
Nested submodules it needs (scripts, test/sim/riscv-tests/riscv-tests and its env) are
initialized when missing. Prints `core-hazard3: PASS ...` / `FAIL ...`; exit 0 only on PASS.
"""
import argparse
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
H3 = os.path.join(ROOT, "third_party", "hazard3")
TB_DIR = os.path.join(H3, "test", "sim", "tb_verilator")
RT = os.path.join(H3, "test", "sim", "riscv-tests", "riscv-tests")
SUITES = ("rv32ui", "rv32uc", "rv32um", "rv32mi")
UNSUPPORTED = {"rv32mi-p-pmpaddr": "PMP_REGIONS = 0 (no PMP)",
               "rv32ui-p-fence_i": "EXTENSION_ZIFENCEI = 0 (no fence.i)"}
CYCLES = 100000
TRACE_SUITES = ("rv32ui", "rv32uc", "rv32um")
NO_TRACE = {"rv32ui-p-simple": "no test body (passes at once)",
            "rv32ui-p-ma_data": "misaligned data: implementation-defined, the test accepts a trap or an access"}


def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk")):
        if line.split("=")[0].strip() == name:
            return line.split("=", 1)[1].strip()
    raise KeyError(name)


def sh(cmd, log, cwd=None, env=None):
    with open(log, "a") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        return subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env).returncode


def build_tb(out, name, extra, log, rvfi=False):
    """Generate config_<name>.vh (plus `extra` localparam overrides) and build <out>/tb_<name>
    (with rvfi: HAZARD3_RVFI_STANDALONE and the rvfi_trace.sv bind, as <out>/tb_<name>_rvfi)."""
    hdr = os.path.join(out, f"config_{name}.vh")
    if sh([sys.executable, os.path.join(ROOT, "dv", "core_hazard3", "gen_config.py"), hdr], log) != 0:
        return None
    if extra:
        text = open(hdr).read()
        for k, v in extra.items():
            old = next((l for l in text.splitlines() if l.startswith(f"localparam {k} ")), None)
            if old is None:
                return None
            text = text.replace(old, f"localparam {k:<19} = {v};  // negative test")
        open(hdr, "w").write(text)
    env = dict(os.environ, HDL=os.path.join(H3, "hdl"))
    vinc = subprocess.run([sys.executable, os.path.join(H3, "scripts", "listfiles"), "-f", "flati",
                           "../tb_common/hdl/tb.f"], cwd=TB_DIR, env=env, capture_output=True, text=True).stdout.split()
    tag = name + ("_rvfi" if rvfi else "")
    tb = os.path.join(out, f"tb_{tag}")
    cmd = ["make", "-C", TB_DIR, f"CONFIG={name}", f"BUILD_DIR={os.path.join(out, 'build_' + tag)}",
           f"TBEXEC={tb}", "VINCDIR=" + " ".join(vinc + [out])]
    if rvfi:
        files = subprocess.run([sys.executable, os.path.join(H3, "scripts", "listfiles"), "../tb_common/hdl/tb.f"],
                               cwd=TB_DIR, env=env, capture_output=True, text=True).stdout.split()
        # PINMISSING: tb.v leaves the RVFI outputs unconnected (rvfi_trace.sv reads them by bind);
        # WIDTHTRUNC: hazard3_rvfi_monitor.vh 324 (upstream, read-only).
        cmd += ["FILE_LIST=" + " ".join(files + [os.path.join(ROOT, "dv", "core_hazard3", "rvfi_trace.sv")]),
                "VERILATOR=verilator -DHAZARD3_RVFI_STANDALONE -Wno-PINMISSING -Wno-WIDTHTRUNC"]
    rc = sh(cmd, log)
    return tb if rc == 0 and os.path.isfile(tb) else None


def build_rvcpp(out, log):
    """rvcpp from a copy of its sources with rvcpp_fence.patch applied: <out>/rvcpp/rvcpp."""
    src = os.path.join(H3, "test", "sim", "rvcpp")
    dst = os.path.join(out, "rvcpp", "src")
    subprocess.run(["rm", "-rf", dst])
    os.makedirs(dst)
    for f in glob.glob(os.path.join(src, "*.cpp")):
        subprocess.run(["cp", f, dst])
    subprocess.run(["cp", "-R", os.path.join(src, "include"), dst])
    if sh(["patch", "-p1", "-s", "-i", os.path.join(ROOT, "dv", "core_hazard3", "rvcpp_fence.patch")], log, cwd=dst) != 0:
        return None
    exe = os.path.join(out, "rvcpp", "rvcpp")
    rc = sh(["g++", "-std=c++17", "-O3", "-I", os.path.join(dst, "include")] + sorted(glob.glob(os.path.join(dst, "*.cpp")))
            + ["-o", exe], log)
    return exe if rc == 0 else None


def first_test_label(elf, nm):
    """Address of the lowest test_N symbol of a riscv-tests ELF, or None."""
    out = subprocess.run([nm, elf], capture_output=True, text=True).stdout
    addrs = [int(m.group(1), 16) for m in re.finditer(r"^([0-9a-f]+) \w test_\d+$", out, re.M)]
    return min(addrs) if addrs else None


def trace_compare(out, tb, rvcpp, bins, nm, log):
    """{test: (ok, message)} for the instruction-by-instruction comparison."""
    res = {}
    for b in bins:
        name = os.path.basename(b)[:-4]
        d = os.path.join(out, "trace", name)
        os.makedirs(d, exist_ok=True)
        start = first_test_label(b[:-4], nm)
        if start is None:
            res[name] = (False, "no test_N label")
            continue
        subprocess.run([tb, "--bin", b, "--cycles", str(CYCLES), "--cpuret"], cwd=d, capture_output=True)
        with open(os.path.join(d, "iss.txt"), "w") as f:
            subprocess.run([rvcpp, "--bin", b, "--cycles", str(CYCLES), "--cpuret", "--trace"], stdout=f,
                           stderr=subprocess.STDOUT)
        cp = subprocess.run([sys.executable, os.path.join(ROOT, "dv", "core_hazard3", "compare_trace.py"),
                             os.path.join(d, "rvfi_trace.txt"), os.path.join(d, "iss.txt"), "--from", f"{start:08x}"],
                            capture_output=True, text=True)
        res[name] = (cp.returncode == 0, cp.stdout.strip())
    return res


def run_tests(tb, bins):
    """{test: exit code} with --cpuret (0 = the test passed)."""
    res = {}
    for b in bins:
        cp = subprocess.run([tb, "--bin", b, "--cycles", str(CYCLES), "--cpuret"], capture_output=True, text=True)
        res[os.path.basename(b)[:-4]] = cp.returncode
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "core_hazard3"))
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "run.log")
    open(log, "w").close()
    # XPACK_DIR, like LIBRELANE_DIR: a clean worktree has no .tools/ and points at the main checkout's
    # installed toolchain (make env-check-flow checks it before a Hazard3 regress).
    xpack = os.path.join(os.environ.get("XPACK_DIR") or os.path.join(
        ROOT, ".tools", f"xpack-riscv-none-elf-gcc-{pin('XPACK_RISCV_VERSION')}"), "bin")
    if not os.path.isfile(os.path.join(xpack, "riscv-none-elf-gcc")):
        print(f"core-hazard3: FAIL - xPack toolchain missing at {xpack} (run make xpack-fetch, or set XPACK_DIR)")
        return 1
    for repo, paths in ((H3, ["scripts", "test/sim/riscv-tests/riscv-tests"]), (RT, ["env"])):
        if sh(["git", "-C", repo, "submodule", "update", "--init"] + paths, log) != 0:
            print(f"core-hazard3: FAIL - could not initialize the submodules {paths} of {repo} (see {log})")
            return 1

    isa = os.path.join(out, "isa")
    os.makedirs(isa, exist_ok=True)
    if sh(["make", "-f", os.path.join(RT, "isa", "Makefile"), f"src_dir={os.path.join(RT, 'isa')}", "XLEN=32",
           "SKIP_V=1", f"RISCV_PREFIX={xpack}/riscv-none-elf-", "-j8", *SUITES], log, cwd=isa) != 0:
        print(f"core-hazard3: FAIL - riscv-tests build (see {log})")
        return 1
    bins = sorted(glob.glob(os.path.join(isa, "*-p-*.bin")))
    if len(bins) < 60:
        print(f"core-hazard3: FAIL - only {len(bins)} riscv-tests binaries built")
        return 1

    tb = build_tb(out, "soc", {}, log)
    if tb is None:
        print(f"core-hazard3: FAIL - testbench build with the SoC configuration (see {log})")
        return 1
    res = run_tests(tb, bins)
    passed = [t for t, rc in res.items() if rc == 0 and t not in UNSUPPORTED]
    failed = [f"{t}(rc={rc})" for t, rc in res.items() if rc != 0 and t not in UNSUPPORTED]
    unsup_pass = [t for t in UNSUPPORTED if res.get(t) == 0]
    unsup_missing = [t for t in UNSUPPORTED if t not in res]

    tbm = build_tb(out, "no_m", {"EXTENSION_M": "0"}, log)
    um = [b for b in bins if os.path.basename(b).startswith("rv32um-")]
    neg = run_tests(tbm, um) if tbm else {}
    neg_escaped = [t for t, rc in neg.items() if rc == 0]
    neg_ok = bool(tbm) and bool(um) and not neg_escaped

    selftest = subprocess.run([sys.executable, os.path.join(ROOT, "dv", "core_hazard3", "compare_trace.py"),
                               "--self-test"], capture_output=True, text=True)
    tbr = build_tb(out, "soc", {}, log, rvfi=True)
    rvcpp = build_rvcpp(out, log)
    nm = os.path.join(xpack, "riscv-none-elf-nm")
    tr_bins = [b for b in bins if os.path.basename(b).split("-p-")[0] in TRACE_SUITES
               and os.path.basename(b)[:-4] not in UNSUPPORTED and os.path.basename(b)[:-4] not in NO_TRACE]
    trace = trace_compare(out, tbr, rvcpp, tr_bins, nm, log) if tbr and rvcpp else {}
    tr_bad = [f"{t}: {m}" for t, (ok, m) in trace.items() if not ok]
    n_insn = sum(int(m.split()[2]) for ok, m in trace.values() if ok and m.startswith("compare_trace: PASS"))
    tr_ok = selftest.returncode == 0 and bool(tbr) and bool(rvcpp) and len(trace) == len(tr_bins) and not tr_bad

    with open(os.path.join(out, "summary.txt"), "w") as f:
        gcc = os.path.join(xpack, "riscv-none-elf-gcc")
        ver = subprocess.run([gcc, "--version"], capture_output=True, text=True).stdout.splitlines()
        f.write(f"toolchain {os.path.realpath(gcc)}: {ver[0] if ver else '?'}\n")
        for t, rc in sorted(res.items()):
            f.write(f"{t} rc={rc}{' UNSUPPORTED: ' + UNSUPPORTED[t] if t in UNSUPPORTED else ''}\n")
        for t, rc in sorted(neg.items()):
            f.write(f"negative EXTENSION_M=0 {t} rc={rc}\n")
        for t, (tok, m) in sorted(trace.items()):
            f.write(f"trace {t}: {m}\n")
        for t, why in NO_TRACE.items():
            f.write(f"trace {t}: not compared ({why})\n")
    ok = not failed and not unsup_pass and not unsup_missing and neg_ok and passed and tr_ok
    print(f"  [{'PASS' if not failed else 'FAIL'}] riscv-tests {', '.join(SUITES)}: {len(passed)} PASS"
          + (f", FAIL {failed[:6]}" if failed else ""))
    print(f"  [{'PASS' if not unsup_pass and not unsup_missing else 'FAIL'}] {len(UNSUPPORTED)} unsupported tests FAIL as they must"
          + (f"; PASSED {unsup_pass}" if unsup_pass else "") + (f"; missing {unsup_missing}" if unsup_missing else ""))
    print(f"  [{'PASS' if neg_ok else 'FAIL'}] negative test EXTENSION_M=0: {len(neg) - len(neg_escaped)}/{len(um)} rv32um tests FAIL"
          + (f"; escaped {neg_escaped}" if neg_escaped else "") + ("" if tbm else "; testbench build failed"))
    print(f"  [{'PASS' if tr_ok else 'FAIL'}] trace vs rvcpp: {len(trace) - len(tr_bad)}/{len(tr_bins)} tests identical "
          f"instruction by instruction ({n_insn} instructions; {len(NO_TRACE)} without a test body not compared); "
          f"comparator self-test {'PASS' if selftest.returncode == 0 else 'FAIL'}"
          + (f"; {tr_bad[:3]}" if tr_bad else "") + ("" if tbr and rvcpp else "; build failed"))
    print(f"core-hazard3: {'PASS' if ok else 'FAIL'} {len(passed)}/{len(bins) - len(UNSUPPORTED)} riscv-tests, "
          f"{len(UNSUPPORTED)} unsupported, negative 1/1, trace {len(trace) - len(tr_bad)}/{len(tr_bins)} -> "
          f"{os.path.relpath(os.path.join(out, 'summary.txt'), ROOT)}"
          if ok else f"core-hazard3: FAIL (see {os.path.relpath(os.path.join(out, 'summary.txt'), ROOT)}, {os.path.relpath(log, ROOT)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
