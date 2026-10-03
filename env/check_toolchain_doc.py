#!/usr/bin/env python3
"""Check that toolchain.md is up to date (called by `make env-check`).

Rule 1: for each local tool row in toolchain.md §1, the "目前版本" cell equals the
        version detected on this machine, and the "最低版本" cell equals the
        matching *_MIN value in env/versions.mk (or "—" when there is none).
Rule 2: every other value in env/versions.mk (commits, hashes, names) appears
        verbatim in toolchain.md.
Exit 0 when all rules hold; otherwise list every stale item and exit 1.
"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "toolchain.md"
PINS = ROOT / "env" / "versions.mk"

# row label in toolchain.md §1 -> (probe command, regex, versions.mk *_MIN key or None)
TOOLS = {
    "Verilator": (["verilator", "--version"], r"Verilator\s+([0-9.]+)", "VERILATOR_MIN"),
    "Icarus Verilog": (["iverilog", "-V"], r"version\s+([0-9.]+)", "ICARUS_MIN"),
    "Yosys": (["yosys", "-V"], r"Yosys\s+([0-9.]+)", "YOSYS_MIN"),
    "riscv64-elf-gcc": (["riscv64-elf-gcc", "-dumpfullversion"], r"([0-9.]+)", "RISCV_GCC_MIN"),
    "riscv64-elf-binutils": (["riscv64-elf-as", "--version"], r"Binutils\)\s+([0-9.]+)", None),
    "Python": (["python3", "--version"], r"Python\s+([0-9.]+)", "PYTHON_MIN"),
    "GNU make": (["make", "--version"], r"GNU Make\s+([0-9.]+)", None),
    "bash": (["bash", "--version"], r"version\s+([0-9.]+)", None),
    "git": (["git", "--version"], r"git version\s+([0-9.]+)", None),
}


def pinned_values():
    vals = {}
    for line in PINS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z0-9_]+)\s*=\s*(\S+)\s*$", line)
        if m:
            vals[m.group(1)] = m.group(2)
    return vals


def detect(cmd, pat):
    if shutil.which(cmd[0]) is None:
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(pat, out.stdout + out.stderr)
    return m.group(1) if m else None


def tool_rows(doc):
    """Parse the §1 table: {label: (current, minimum)}."""
    rows = {}
    sec = re.search(r"^## 1\..*?(?=^## 2\.)", doc, re.S | re.M)
    if not sec:
        return rows
    for line in sec.group(0).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0] in TOOLS:
            rows[cells[0]] = (cells[2], cells[3])
    return rows


def main():
    doc = DOC.read_text(encoding="utf-8")
    pins = pinned_values()
    rows = tool_rows(doc)
    stale = []
    used_min_keys = set()
    for label, (cmd, pat, min_key) in TOOLS.items():
        if label not in rows:
            stale.append(f"toolchain.md §1 缺少「{label}」這一列")
            continue
        cur_doc, min_doc = rows[label]
        actual = detect(cmd, pat)
        if actual is None:
            stale.append(f"本機找不到 {cmd[0]}，但 toolchain.md 列為已安裝")
        elif cur_doc != actual:
            stale.append(f"{label}：本機實際 {actual}，toolchain.md 寫 {cur_doc}")
        want_min = pins.get(min_key, "—") if min_key else "—"
        if min_key:
            used_min_keys.add(min_key)
        if min_doc != want_min:
            stale.append(f"{label}：versions.mk 最低版本 {want_min}，toolchain.md 寫 {min_doc}")
    for name, value in pins.items():
        if name in used_min_keys:
            continue
        if value not in doc:
            stale.append(f"env/versions.mk {name} = {value} 未出現在 toolchain.md")
    if stale:
        print("toolchain.md 過期：")
        for s in stale:
            print("  - " + s)
        return 1
    print(f"toolchain.md 一致：{len(TOOLS)} 個本機工具、{len(pins)} 個釘版值")
    return 0


if __name__ == "__main__":
    sys.exit(main())
