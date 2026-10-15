#!/usr/bin/env python3
"""Extract the SRAM macro's GDS with Magic into a SPICE netlist with wire capacitances.

usage: extract_sram.py [<out_dir>]      (default runs/sram_extract/)

Runs Magic from LibreLane's nix-shell (LIBRELANE_DIR, default .tools/librelane) with PDK_ROOT set:
without PDK_ROOT the magicrc cannot find the tech file and Magic still exits 0 with no output
(skill sram-layout-extraction rule 1), so the result is checked, not the exit code.
Capacitance and coupling capacitance are extracted, resistance is not (ADR-0010). Takes about
26 minutes and 1.4 GB for the 2 KB macro.
Writes <out_dir>/<macro>.spice and <out_dir>/extract.log; prints `extract_sram: PASS ...` when the
netlist defines the macro subckt with the 16384 bitcells and the capacitors, and no node has a negative
total capacitance, else FAIL.
Negative total capacitance (negative_nodes): `ext2spice lvs` writes the netlist hierarchically, and
Magic then puts negative capacitors in a parent cell to correct the capacitance counted twice where
cells overlap. On the 2 KB macro 263 nodes come out negative in total (bank_0/port_data_0/bl_127
-108 fF), and a corrector on a node that is not a port of the child cell becomes a separate floating
node. ngspice then stops with `Timestep too small` (Phase 3.5 limitation 3) or a singular operating
point; the same netlist without the negative capacitors, or Magic's flat output (`ext2spice hierarchy
off`), simulates (Phase 6 trial, docs/notes/openram_phase6_bringup.md). Negative test: neg_char.py N22.
"""
import collections
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sramchar as sc  # noqa: E402

GDS = os.path.join(sc.PDK_ROOT, "sky130A", "libs.ref", "sky130_sram_macros", "gds", sc.MACRO + ".gds")
MAGICRC = os.path.join(sc.PDK_ROOT, "sky130A", "libs.tech", "magic", "sky130A.magicrc")


UNITS = {"a": 1e-18, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1.0}


def capacitance(word):
    m = re.fullmatch(r"([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)([afpnum]?)", word.lower())
    if not m:
        raise ValueError(f"capacitor value {word!r}")
    return float(m.group(1)) * UNITS[m.group(2)]


def node_capacitance(path, top):
    """{flat node: total capacitance in F with sign} over every capacitor of the netlist (a coupling
    capacitor counts on both of its nodes), with the hierarchy of `top` flattened. A flat node is a
    tuple: the instance path, then the name inside that instance; a port takes the node of the net it is
    connected to. A net named like an inner node ("X0/n1") stays a node of its own, as in ngspice."""
    subs, cur = {}, None
    for line in re.sub(r"\n\+", " ", open(path, errors="replace").read()).split("\n"):
        t = line.split()
        if not t or t[0].startswith("*"):
            continue
        k = t[0].lower()
        if k == ".subckt":
            cur = subs[t[1]] = {"ports": [x for x in t[2:] if "=" not in x], "inst": [], "caps": []}
        elif k == ".ends":
            cur = None
        elif cur is not None and k[0] == "x":
            words = [x for x in t[1:] if "=" not in x]
            cur["inst"].append((t[0], words[:-1], words[-1]))
        elif cur is not None and k[0] == "c":
            cur["caps"].append((t[1], t[2], capacitance(t[3])))
    if top not in subs:
        raise ValueError(f"no .subckt {top}")
    total = collections.defaultdict(float)
    stack = [(top, (), {p: ((), p) for p in subs[top]["ports"]})]
    while stack:
        name, where, nets = stack.pop()
        node = lambda n: nets.get(n, (where, n))   # noqa: E731
        for a, b, v in subs[name]["caps"]:
            total[node(a)] += v
            total[node(b)] += v
        for inst, conn, model in subs[name]["inst"]:
            if model in subs:
                stack.append((model, where + (inst,), {p: node(n) for p, n in zip(subs[model]["ports"], conn)}))
    return total


def negative_nodes(path, top):
    """[(total F, "inst/.../node")] of the nodes whose total capacitance is negative, most negative first
    (ground, "0", is left out)."""
    return sorted((v, "/".join(w + (n,))) for (w, n), v in node_capacitance(path, top).items()
                  if v < 0 and not (w == () and n == "0"))


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(sc.ROOT, "runs", "sram_extract"))
    ext = os.path.join(out, "ext")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(ext)
    spice = os.path.join(out, sc.MACRO + ".spice")
    tcl = os.path.join(out, "extract.tcl")
    open(tcl, "w").write("\n".join([
        "gds readonly true", "gds rescale false", f"gds read {GDS}", f"load {sc.MACRO}", f"cd {ext}",
        "select top cell", "extract do capacitance", "extract do coupling", "extract no resistance",
        "extract all", "ext2spice lvs", "ext2spice cthresh 0.01", f"ext2spice -o {spice}",
        'puts "EXTRACT_DONE"', "quit -noprompt", ""]))
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(sc.ROOT, ".tools", "librelane"))
    env = dict(os.environ, PDK_ROOT=sc.PDK_ROOT)
    if shutil.which("nix-shell") is None:
        env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    cmd = f"magic -dnull -noconsole -rcfile '{MAGICRC}' '{tcl}'"
    log = os.path.join(out, "extract.log")
    with open(log, "w") as f:
        f.write(f"$ (cd {ll_dir} && PDK_ROOT={sc.PDK_ROOT} nix-shell --run {cmd!r})\n")
        f.flush()
        rc = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env, stdout=f,
                            stderr=subprocess.STDOUT).returncode
    problems = []
    text = open(log, errors="replace").read()
    if "EXTRACT_DONE" not in text:
        problems.append("Magic did not reach the end of the script")
    if not os.path.isfile(spice):
        problems.append("no netlist written")
    else:
        net = open(spice, errors="replace").read()
        if not re.search(rf"^\.subckt {sc.MACRO}\s", net, re.M):
            problems.append(f"no .subckt {sc.MACRO}")
        joined = re.sub(r"\n\+", " ", net)       # continuation lines
        cells = len(re.findall(rf"^X\S* .* {sc.BITCELL}\s*$", joined, re.M))
        caps = len(re.findall(r"^C", net, re.M))
        if cells != sc.ROWS * sc.COLS:
            problems.append(f"{cells} bitcell instances, expected {sc.ROWS * sc.COLS}")
        if caps < 10000:
            problems.append(f"only {caps} capacitors")
        if not problems:
            neg = negative_nodes(spice, sc.MACRO)
            if neg:
                problems.append(f"{len(neg)} nodes with negative total capacitance, the most negative "
                                f"{neg[0][0] * 1e15:.1f} fF on {neg[0][1]} (hierarchical ext2spice corrections; "
                                f"ngspice stops with 'Timestep too small'; flat output: ext2spice hierarchy off)")
    if rc != 0 or problems:
        print(f"extract_sram: FAIL (Magic exit {rc}; {'; '.join(problems) or 'see log'}; {log})")
        return 1
    print(f"extract_sram: PASS {spice} ({cells} bitcells, {caps} capacitors, sha256 {sc.sha256(spice)[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
