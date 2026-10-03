#!/usr/bin/env python3
"""Check that the Phase 2 hardening uses the same PicoRV32 parameters as the SoC.

usage: cpu_params.py [--emit-dir <dir>] [--resolved <LibreLane run>/resolved.json]

The parameters of instance u_cpu in rtl/soc/soc_top.v are the single source of truth
(soc_spec.md §4.1, project-plan.md §5.1). This script reads them with Yosys (`read_verilog`
+ `write_json`, no BUG_* defines, so the shipped configuration) and compares them with
SYNTH_PARAMETERS in pnr/picorv32_core/config.json: same parameter names, same values.
Things this reading cannot see are rejected instead of trusted:
  - soc_top is read twice, with the SYNTHESIS define Yosys adds by default and without it
    (what the simulators see); the u_cpu parameters must be the same both times
  - `defparam` anywhere in the RTL of rtl/rtl.f (Yosys ignores it, simulators apply it)
  - conditional blocks in config.json (top-level keys starting with pdk:: or scl::), which
    LibreLane would apply on top of the SYNTH_PARAMETERS read here
--resolved also requires SYNTH_PARAMETERS in a LibreLane run's resolved.json (the values the
flow actually used) to equal config.json, so a run made with other parameters is rejected.

--emit-dir writes two Verilog include files for `make gl-core` (only on PASS):
  cpu_params.vh  : the config values as a parameter-override list, one `.NAME(value)` per line
                   (RTL reference run, dv/gl_core/picorv32_axi_shim.v)
  cpu_defines.vh : one `define CPU_<NAME> <value> per parameter (dv/gl_core/gl_core_boot.v)

Prints one row per parameter and `cpu-params: PASS` / `cpu-params: FAIL`; exit code 0 only on PASS.
Python stdlib only; needs the local `yosys` (toolchain.md §1).
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOC_TOP = os.path.join(ROOT, "rtl", "soc", "soc_top.v")
INCLUDE = os.path.join(ROOT, "rtl", "include")
CONFIG = os.path.join(ROOT, "pnr", "picorv32_core", "config.json")
CPU_INSTANCE = "u_cpu"

VERILOG_INT = re.compile(r"^(?:(\d+)?'([bBoOdDhH]))?([0-9a-fA-F_]+)$")
BASES = {"b": 2, "o": 8, "d": 10, "h": 16}


def parse_verilog_int(text):
    """Value of a plain Verilog integer constant such as 1, 32'h0001_0000 or 4'b1010."""
    m = VERILOG_INT.match(text.strip())
    if not m:
        raise ValueError(f"not a Verilog integer constant: {text!r}")
    width, base, digits = m.groups()
    value = int(digits.replace("_", ""), BASES[base.lower()] if base else 10)
    if width is not None and value >= (1 << int(width)):
        raise ValueError(f"value does not fit its width: {text!r}")
    return value


def soc_params(synthesis):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "soc_top.json")
        flag = "" if synthesis else "-nosynthesis "
        script = f"read_verilog {flag}-I {INCLUDE} {SOC_TOP}; write_json {out}"
        subprocess.run(["yosys", "-q", "-p", script], check=True)
        with open(out, encoding="utf8") as f:
            design = json.load(f)
    cell = design["modules"]["soc_top"]["cells"][CPU_INSTANCE]
    if cell["type"] != "picorv32":
        raise ValueError(f"{CPU_INSTANCE} is a {cell['type']}, expected picorv32")
    params = {}
    for name, bits in cell["parameters"].items():
        if not re.fullmatch(r"[01]+", bits):
            raise ValueError(f"{CPU_INSTANCE}.{name} is not a constant 0/1 bit string: {bits!r}")
        params[name] = int(bits, 2)
    return params


def rtl_defparams():
    """Files of rtl/rtl.f that use defparam (comments removed first)."""
    found = []
    with open(os.path.join(ROOT, "rtl", "rtl.f"), encoding="utf8") as f:
        files = [line.strip() for line in f if line.strip() and not line.startswith("+")]
    for rel in files:
        with open(os.path.join(ROOT, rel), encoding="utf8") as f:
            text = re.sub(r"//[^\n]*|/\*.*?\*/", "", f.read(), flags=re.S)
        if re.search(r"\bdefparam\b", text):
            found.append(rel)
    return found


def config_params():
    with open(CONFIG, encoding="utf8") as f:
        config = json.load(f)
    conditional = [k for k in config if k.startswith(("pdk::", "scl::"))]
    if conditional:
        raise ValueError(f"config.json has conditional blocks {conditional}; not supported by this check")
    texts, values = {}, {}
    for item in config.get("SYNTH_PARAMETERS") or []:
        name, text = item.split("=", 1)
        if name in texts:
            raise ValueError(f"SYNTH_PARAMETERS lists {name} twice")
        texts[name] = text
        values[name] = parse_verilog_int(text)
    return texts, values


def main(argv):
    opts = dict(zip(argv[::2], argv[1::2]))
    if len(argv) % 2 or not set(opts) <= {"--emit-dir", "--resolved"}:
        print(__doc__.strip().splitlines()[2])
        return 2
    emit, resolved = opts.get("--emit-dir"), opts.get("--resolved")

    soc = soc_params(synthesis=True)
    texts, cfg = config_params()
    fail = 0
    if soc_params(synthesis=False) != soc:
        fail += 1
        print(f"  [FAIL] soc_top.{CPU_INSTANCE} parameters differ with and without the SYNTHESIS define")
    for rel in rtl_defparams():
        fail += 1
        print(f"  [FAIL] {rel} uses defparam (not visible to this check)")
    if resolved:
        with open(resolved, encoding="utf8") as f:
            used = json.load(f).get("SYNTH_PARAMETERS")
        with open(CONFIG, encoding="utf8") as f:
            listed = json.load(f).get("SYNTH_PARAMETERS")
        ok = used == listed
        fail += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] SYNTH_PARAMETERS used by the run ({resolved}) == config.json")
    for name in sorted(set(soc) | set(cfg)):
        have = cfg.get(name, "<missing>")
        want = soc.get(name, "<missing>")
        ok = have == want
        fail += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: config.json={have} soc_top.{CPU_INSTANCE}={want}")
    if not soc:
        fail += 1
        print(f"  [FAIL] soc_top.{CPU_INSTANCE} has no parameter overrides (unexpected)")
    print(f"cpu-params: {'PASS' if fail == 0 else f'FAIL ({fail} rows)'}")
    if fail:
        return 1
    if emit:
        header = "// Generated by pnr/picorv32_core/cpu_params.py from pnr/picorv32_core/config.json; do not edit.\n"
        with open(os.path.join(emit, "cpu_params.vh"), "w", encoding="utf8") as f:
            f.write(header + ",\n".join(f".{n}({texts[n]})" for n in sorted(texts)) + "\n")
        with open(os.path.join(emit, "cpu_defines.vh"), "w", encoding="utf8") as f:
            f.write(header + "".join(f"`define CPU_{n} {texts[n]}\n" for n in sorted(texts)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        print("cpu-params: FAIL (could not read the parameters)")
        sys.exit(1)
