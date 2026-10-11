#!/usr/bin/env python3
"""QA of the views of a hard macro, whatever made it (a memory compiler such as OpenRAM, a vendor, a previous
harden): check the contents of every delivered file, not only that it exists. Skill hard-macro-integration.

    python3 scripts/check_macro_views.py --name <top> --lef <lef> --lib <lib> [--lib <lib> ...] --verilog <v>
                                         --spice <netlist> [--gds <gds>] [--power-max PJ] [--cap-max PF] [--dbu N] [--no-foreign] [--json out.json]

Why (2026-10-08, ADR-0018): OpenRAM's own checks (DRC, LVS, files present) let a .lib with every internal_power
ten orders of magnitude off (1.036316e+11) through, and the SoC IR-drop analysis reads those numbers. LVS ties
the GDS to the SPICE netlist only; nothing tied the LEF, the .lib and the Verilog model to them.
  names   LEF MACRO, every .lib cell, the Verilog module and the SPICE top .SUBCKT are all <top>
  pins    the same signal bits in LEF, each .lib, Verilog and SPICE (buses expanded), with the same direction
          where the file states one (SPICE only through OpenRAM-style `* INPUT : x` comments); power and ground
          pins (LEF USE POWER/GROUND) compared as a set
  lib     every number finite; internal_power in (0, --power-max]; pin capacitance in (0, --cap-max] pF;
          leakage >= 0; delays and transitions >= 0; area = LEF width x height (AREA_TOL)
  size    with --gds: LEF SIZE = the bounding box of the GDS top cell, at the origin (KLayout from LibreLane's
          nix-shell, scripts/gds_view.py; SIZE_TOL um)
  pinpos  with --gds: every LEF pin has a text of its name in the GDS top cell, and every such text sits inside
          one of that pin's LEF RECTs on the same layer (LEF_LAYERS). LVS sees the macro through its LEF only
          (a black box), so a LEF with two pin RECTs swapped passed every check and would have connected the
          SoC to the wrong bits (Phase 6 independent review H1, ADR-0018 decision 19)
  obs     with --gds: on each routing layer (ROUTING), the GDS top cell's metal, flattened, lies inside the LEF OBS
          and pin RECTs, apart from metal that touches a pin RECT (the pin running on into the macro). A LEF
          without OBS passed and would have let the router cross the macro's own wires (review H2)
  units   LEF DATABASE MICRONS <= the tech LEF's (--dbu, sky130 1000): OpenROAD discards a finer macro LEF
          ("[ODB-0292] LEF data from ... is discarded due to errors"; OpenRAM dev writes 2000, Phase 6)
  foreign the LEF has `FOREIGN <top>`: without it LibreLane's KLayout stream-out leaves the macro empty in the
          final GDS, with no error (Phase 6: XOR 5.69 million; --no-foreign for a raw generator LEF)
Units: a .lib with capacitive_load_unit(1, pF) and voltage 1V gives internal power in pJ per transition.
Prints PASS/FAIL with the reasons; exit 0 only on PASS. Negative tests: scripts/neg_macro_views.py (make neg-macro-views).
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

POWER_MAX = 1000.0   # pJ per clock edge: the sky130 2 KB SRAM's analytical value is 13.8; OpenRAM dev wrote 1.04e+11
CAP_MAX = 1.0        # pF: a macro input pin is a few fF; 1 pF would be a unit or model error
AREA_TOL = 1e-3      # relative
SIZE_TOL = 0.005     # um, the sky130 manufacturing grid
TECH_DBU = 1000      # DATABASE MICRONS of the sky130 tech LEF
LEF_LAYERS = {"li1": 67, "met1": 68, "met2": 69, "met3": 70, "met4": 71, "met5": 72}   # sky130 GDS layer numbers
ROUTING = ("met1", "met2", "met3", "met4", "met5")   # the router's layers; drawing datatype 20 in sky130
NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
DIRS = {"INPUT": "input", "OUTPUT": "output", "INOUT": "inout", "input": "input", "output": "output", "inout": "inout"}


def expand(name, hi, lo):
    return [f"{name}[{i}]" for i in range(min(hi, lo), max(hi, lo) + 1)]


# ---------------------------------------------------------------- readers: (top, {pin: direction or None}, {power pins})

def read_lef(text):
    m = re.search(r"^\s*MACRO\s+(\S+)", text, re.M)
    size = re.search(r"^\s*SIZE\s+(" + NUM + r")\s+BY\s+(" + NUM + r")\s*;", text, re.M)
    sig, pwr = {}, set()
    for pm in re.finditer(r"^\s*PIN\s+(\S+)(.*?)^\s*END\s+(\S+)", text, re.M | re.S):
        body = pm.group(2)
        use = re.search(r"\bUSE\s+(\w+)", body)
        if use and use.group(1) in ("POWER", "GROUND"):
            pwr.add(pm.group(1))
        else:
            d = re.search(r"\bDIRECTION\s+(\w+)", body)
            sig[pm.group(1)] = DIRS.get(d.group(1)) if d else None
    return (m.group(1) if m else None), sig, pwr, ((float(size.group(1)), float(size.group(2))) if size else None)


def lef_geometry(text):
    """({pin: [(layer, (x1, y1, x2, y2)), ...]}, [(layer, box), ...] of OBS) from a LEF macro."""
    pins, obs, cur, layer, in_obs = {}, [], None, None, False
    for line in text.splitlines():
        t = line.replace(";", " ").split()
        if not t:
            continue
        if t[0] == "PIN":
            cur, in_obs = t[1], False
            pins[cur] = []
        elif t[0] == "OBS":
            cur, in_obs = None, True
        elif t[0] == "END":
            if cur is not None and len(t) > 1 and t[1] == cur:
                cur = None
            elif in_obs and len(t) == 1:
                in_obs = False
        elif t[0] == "LAYER":
            layer = t[1]
        elif t[0] == "RECT" and len(t) >= 5 and (cur is not None or in_obs):
            box = tuple(float(v) for v in t[1:5])
            (pins[cur] if cur is not None else obs).append((layer, box))
    return pins, obs


def read_lib(text):
    m = re.search(r"\bcell\s*\(\s*\"?(\w+)\"?\s*\)", text)
    sig, pwr = {}, set(re.findall(r"\bpg_pin\s*\(\s*\"?(\w+)\"?\s*\)", text))
    for bm in re.finditer(r"\bbus\s*\(\s*\"?(\w+)\"?\s*\)\s*\{", text):
        d = re.search(r"direction\s*:\s*\"?(\w+)", text[bm.end():bm.end() + 400])
        r = re.search(r"pin\s*\(\s*\"?" + re.escape(bm.group(1)) + r"\[(\d+):(\d+)\]\"?\s*\)", text[bm.end():])
        if d and r:
            for b in expand(bm.group(1), int(r.group(1)), int(r.group(2))):
                sig[b] = DIRS.get(d.group(1))
    for pm in re.finditer(r"\bpin\s*\(\s*\"?(\w+)\"?\s*\)\s*\{", text):
        d = re.search(r"direction\s*:\s*\"?(\w+)", text[pm.end():pm.end() + 300])
        sig[pm.group(1)] = DIRS.get(d.group(1)) if d else None
    area = re.search(r"\barea\s*:\s*(" + NUM + r")", text)
    return (m.group(1) if m else None), sig, pwr, (float(area.group(1)) if area else None)


def _int_expr(expr, params):
    expr = re.sub(r"\b([A-Za-z_]\w*)\b", lambda x: str(params.get(x.group(1), x.group(1))), expr)
    if not re.fullmatch(r"[\d\s+\-*/()<>]+", expr):
        raise ValueError(expr)
    return int(eval(expr, {"__builtins__": {}}))     # digits and operators only (checked above)


def read_verilog(text, power_names):
    """Ports of the first module; inout ports named like LEF power pins (in or out of `ifdef USE_POWER_PINS`) are power."""
    m = re.search(r"^\s*module\s+(\w+)", text, re.M)
    params = {}
    for pm in re.finditer(r"\b(?:parameter|localparam)\s+(?:integer\s+)?(\w+)\s*=\s*([^;,]+)[;,]", text):
        try:
            params[pm.group(1)] = _int_expr(pm.group(2), params)
        except (ValueError, SyntaxError):
            pass
    sig, pwr = {}, set()
    for dm in re.finditer(r"^\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:\[([^\]:]+):([^\]]+)\])?\s*([\w\s,]+?)\s*;", text, re.M):
        for name in [n.strip() for n in dm.group(4).split(",") if n.strip()]:
            if dm.group(1) == "inout" and name in power_names:
                pwr.add(name)
            elif dm.group(2) is not None:
                for b in expand(name, _int_expr(dm.group(2), params), _int_expr(dm.group(3), params)):
                    sig[b] = dm.group(1)
            else:
                sig[name] = dm.group(1)
    return (m.group(1) if m else None), sig, pwr


def read_spice(text, name, power_names):
    m = re.search(rf"^\.SUBCKT\s+{re.escape(name)}\b(.*?)(?=^[^+])", text, re.M | re.S | re.I)
    if not m:
        return None, {}, set()
    ports = " ".join(l.lstrip("+") for l in m.group(1).splitlines()).split()
    rest = text[m.end():m.end() + 40 * len(ports) + 2000]
    kinds = dict((p, k) for k, p in re.findall(r"^\*\s*(INPUT|OUTPUT|INOUT|POWER|GROUND)\s*:\s*(\S+)", rest, re.M))
    sig, pwr = {}, set()
    for p in ports:
        if kinds.get(p) in ("POWER", "GROUND") or p in power_names:
            pwr.add(p)
        else:
            sig[p] = DIRS.get(kinds.get(p))
    return name, sig, pwr


# ---------------------------------------------------------------- checks

def lib_numbers(text, power_max=POWER_MAX, cap_max=CAP_MAX):
    """Problems with the numbers of one .lib."""
    out = []
    vals = [v for grp in re.findall(r"values\(((?:[^()]|\n)*?)\)", text) for v in re.findall(NUM + r"|nan|inf", grp, re.I)]
    bad = [v for v in vals if not math.isfinite(float(v))]
    if bad:
        out.append(f"{len(bad)} values() entries not finite (e.g. {bad[0]})")
    # every number of every rise_power/fall_power table, also after index_1 (review H7: only the first number
    # of tables that start with values() was read, so 1e11 in a second entry or in an indexed table passed)
    power = [v for body in re.findall(r"(?:rise|fall)_power\s*\([^)]*\)\s*\{([^{}]*)\}", text)
             for grp in re.findall(r"\bvalues\(((?:[^()]|\n)*?)\)", body) for v in re.findall(NUM, grp)]
    badp = sorted({p for p in power if not 0 < float(p) <= power_max})
    if not power:
        out.append("no internal_power values")
    elif badp:
        out.append(f"internal_power {', '.join(badp[:3])} outside (0, {power_max:g}]")
    caps = re.findall(r"^\s*capacitance\s*:\s*(" + NUM + r"|nan|inf)", text, re.M | re.I)
    badc = sorted({c for c in caps if not (math.isfinite(float(c)) and 0 < float(c) <= cap_max)})
    if not caps:
        out.append("no pin capacitance")
    elif badc:
        out.append(f"pin capacitance {', '.join(badc[:3])} pF outside (0, {cap_max:g}]")
    for v in re.findall(r"\bcell_leakage_power\s*:\s*(" + NUM + r"|nan|inf)", text, re.I):
        if not (math.isfinite(float(v)) and float(v) >= 0):
            out.append(f"cell_leakage_power {v}")
    timing = [v for g in re.findall(r"(?:cell_rise|cell_fall|rise_transition|fall_transition)\s*\([^)]*\)\s*\{\s*values\(((?:[^()]|\n)*?)\)",
                                    text) for v in re.findall(NUM, g)]
    neg = [v for v in timing if float(v) < 0]
    if neg:
        out.append(f"{len(neg)} negative delay/transition values (e.g. {neg[0]})")
    return out


def compare_pins(views):
    """views: {label: (top, {bit: dir}, {power})}, first entry the LEF; problems where the others differ from it."""
    out = []
    (ref_label, (_, ref_sig, ref_pwr, *_)), *others = views.items()
    for label, (_, sig, pwr, *_) in others:
        miss, extra = sorted(set(ref_sig) - set(sig)), sorted(set(sig) - set(ref_sig))
        if miss or extra:
            out.append(f"{label} signal pins differ from the LEF: missing {miss[:4]}, extra {extra[:4]}")
        wrong = sorted(b for b in set(ref_sig) & set(sig) if sig[b] and ref_sig[b] and ref_sig[b] != sig[b])
        if wrong:
            out.append(f"{label} direction differs from the LEF: " + ", ".join(f"{b} {sig[b]} vs {ref_sig[b]}" for b in wrong[:4]))
        if pwr != ref_pwr:
            out.append(f"{label} power pins {sorted(pwr)} != LEF {sorted(ref_pwr)}")
    return out


def gds_view(gds, name, lef_text, work):
    """The GDS facts check() needs (scripts/gds_view.py in KLayout): {"bbox", "labels", "uncovered"}, or None."""
    pins, obs = lef_geometry(lef_text)
    cover = {f"{LEF_LAYERS[l]}/20": {"obs": [b for la, b in obs if la == l],
                                     "pins": [b for rects in pins.values() for la, b in rects if la == l]} for l in ROUTING}
    src, dst = os.path.join(work, "gds_view_in.json"), os.path.join(work, "gds_view_out.json")
    json.dump(cover, open(src, "w"))
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    cmd = (f"klayout -b -rd src='{os.path.abspath(gds)}' -rd cell={name} -rd cover='{src}' -rd dst='{dst}' "
           f"-r '{os.path.join(HERE, 'gds_view.py')}'")
    subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, capture_output=True, text=True)
    return json.load(open(dst)) if os.path.isfile(dst) else None


def gds_problems(lef_text, gds):
    """Pin positions and OBS coverage of the LEF against the GDS facts of gds_view()."""
    out = []
    pins, _ = lef_geometry(lef_text)
    labels = {}
    for text, layer, _dt, x, y in gds["labels"]:
        labels.setdefault(text, []).append((layer, x, y))
    unlabelled = sorted(p for p in pins if p not in labels)
    if unlabelled:
        out.append(f"{len(unlabelled)} LEF pin(s) without a text of their name in the GDS top cell: {unlabelled[:4]}")
    off = []
    for pin, rects in pins.items():
        for layer, x, y in labels.get(pin, []):
            if not any(LEF_LAYERS.get(la) == layer and b[0] <= x <= b[2] and b[1] <= y <= b[3] for la, b in rects):
                off.append(f"{pin} at ({x}, {y}) layer {layer}")
    if off:
        out.append(f"{len(off)} GDS pin text(s) outside the pin's LEF RECTs on that layer: {', '.join(off[:3])}")
    for key, u in sorted(gds["uncovered"].items()):
        if u["loose"] > 0:
            out.append(f"GDS {key} has {u['loose']:.3f} um2 of metal outside the LEF OBS and pins, not part of a pin "
                       f"(e.g. {u['examples'][:1]}): the router may cross it")
    return out


def check(name, texts, gds=None, power_max=POWER_MAX, cap_max=CAP_MAX, dbu=TECH_DBU, foreign=True):
    """texts: {"lef": str, "lib": {label: str}, "verilog": str, "spice": str}; gds: gds_view() facts or None (not
    checked). Returns (problems, details)."""
    bbox = gds["bbox"] if gds else None
    lef_top, lef_sig, lef_pwr, size = read_lef(texts["lef"])
    views = {"LEF": (lef_top, lef_sig, lef_pwr)}
    areas, out = {}, []
    for label, t in texts["lib"].items():
        top, sig, pwr, areas[label] = read_lib(t)
        views[label] = (top, sig, pwr)
        out += [f"{label}: {x}" for x in lib_numbers(t, power_max, cap_max)]
    views["Verilog"] = read_verilog(texts["verilog"], lef_pwr)
    views["SPICE"] = read_spice(texts["spice"], name, lef_pwr)
    wrong_top = {k: v[0] for k, v in views.items() if v[0] != name}
    if wrong_top:
        out.insert(0, "top names " + ", ".join(f"{k}={t}" for k, t in wrong_top.items()) + f" (expected {name})")
    if not lef_sig:
        out.append("no signal pins in the LEF")
    else:
        out += compare_pins(views)
    units = re.search(r"^\s*DATABASE\s+MICRONS\s+(\d+)", texts["lef"], re.M)
    if units and int(units.group(1)) > dbu:
        out.append(f"LEF DATABASE MICRONS {units.group(1)} > the tech LEF's {dbu} (OpenROAD ODB-0292 discards it)")
    if foreign and not re.search(r"^\s*FOREIGN\s+" + re.escape(name) + r"\b", texts["lef"], re.M):
        out.append(f"LEF has no FOREIGN {name} (KLayout stream-out would leave the macro empty in the final GDS)")
    if size is None:
        out.append("no SIZE in the LEF")
    else:
        for label, area in areas.items():
            if area is None:
                out.append(f"{label}: no area")
            elif abs(area - size[0] * size[1]) > AREA_TOL * size[0] * size[1]:
                out.append(f"{label}: area {area} != LEF {size[0]} x {size[1]} = {size[0] * size[1]:.3f}")
        if bbox is not None:
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if max(abs(w - size[0]), abs(h - size[1]), abs(bbox[0]), abs(bbox[1])) > SIZE_TOL:
                out.append(f"LEF SIZE {size[0]} x {size[1]} != GDS box ({bbox[0]}, {bbox[1]})-({bbox[2]}, {bbox[3]})")
    if gds is not None:
        out += gds_problems(texts["lef"], gds)
    details = {"signal_pins": len(lef_sig), "power_pins": sorted(lef_pwr), "lef_size": size, "lib_area": areas,
               "gds_bbox": bbox, "gds_uncovered": gds["uncovered"] if gds else None}
    return out, details


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--lef", required=True)
    ap.add_argument("--lib", action="append", required=True)
    ap.add_argument("--verilog", required=True)
    ap.add_argument("--spice", required=True)
    ap.add_argument("--gds")
    ap.add_argument("--power-max", type=float, default=POWER_MAX)
    ap.add_argument("--cap-max", type=float, default=CAP_MAX)
    ap.add_argument("--dbu", type=int, default=TECH_DBU, help="DATABASE MICRONS of the tech LEF")
    ap.add_argument("--no-foreign", action="store_true", help="a raw generator LEF without FOREIGN (not the flow's LEF)")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    paths = [a.lef, *a.lib, a.verilog, a.spice] + ([a.gds] if a.gds else [])
    missing = [p for p in paths if not (os.path.isfile(p) and os.path.getsize(p) > 0)]
    probs, details = [], {}
    if missing:
        probs = [f"missing or empty: {', '.join(missing)}"]
    else:
        rd = lambda p: open(p, encoding="utf-8", errors="replace").read()
        texts = {"lef": rd(a.lef), "lib": {os.path.basename(p): rd(p) for p in a.lib}, "verilog": rd(a.verilog),
                 "spice": rd(a.spice)}
        gds = None
        if a.gds:
            with tempfile.TemporaryDirectory() as work:
                gds = gds_view(a.gds, a.name, texts["lef"], work)
            if gds is None or gds["bbox"] is None:
                probs.append("could not read the GDS top cell (KLayout)")
                gds = None
        p, details = check(a.name, texts, gds, a.power_max, a.cap_max, a.dbu, not a.no_foreign)
        probs += p
    res = {"name": a.name, "result": "FAIL" if probs else "PASS", "problems": probs,
           "files": [os.path.relpath(os.path.abspath(p), ROOT) if os.path.abspath(p).startswith(ROOT) else os.path.basename(p)
                     for p in paths], **details}
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    print(f"check_macro_views: {res['result']} - {a.name}: " + ("; ".join(probs) if probs else
          f"names, {details['signal_pins']} signal pins and {len(details['power_pins'])} power pins agree in LEF, "
          f"{len(a.lib)} .lib, Verilog and SPICE; .lib numbers in range; .lib area"
          + (" and GDS box match" if a.gds else " matches") + " the LEF SIZE"
          + ("; LEF pin RECTs hold the GDS pin texts; GDS routing metal inside the LEF OBS and pins" if a.gds else "")))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
