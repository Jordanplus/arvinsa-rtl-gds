#!/usr/bin/env python3
"""make pin-plan: every top-level design follows its approved pad, block and pin plan
(pnr/<design>/pin_plan.toml; skill chip-floorplan-pin-planning, CLAUDE.md rule 14).

usage: check_pin_plan.py [--root DIR] [--design D | --digest PLAN | PLAN ...]
Without PLAN, checks every pnr/*/pin_plan.toml under ROOT, and that every design directory
pnr/<design>/ with a LibreLane config has a plan, except LEGACY (designs whose pins were placed
before rule 14, user 2026-10-12; their pins cannot change without a plan: the Claude Code hook
.claude/hooks/require_pin_plan.py). --design D checks only D (make harden: a legacy design PASSes,
another one needs pnr/D/pin_plan.toml). --digest PLAN prints the plan_sha256 to put in [approval]
when the user approved it. For each plan:
  approval      date (YYYY-MM-DD), the user's quote, an ADR file under ROOT that contains it, and
                plan_sha256 = sha256 of the plan text before its [approval] line (a plan changed after
                the approval is no longer approved); one line of the ADR has the quote, the date and the full
                plan_sha256 together (the approved version is recorded in the ADR: re-approving a changed plan
                changes the ADR too and shows in its diff, not only the digest in [approval]; a short quote
                such as 「可以」 alone matches anywhere; Phase 7 review H1)
  governs       every governed file exists
  pads=fixed:
    template    the template DEF exists and has every planned pin (io_in[<gpio>]) placed
    pins        no reserved GPIO, no GPIO twice, every pin within max_pin_distance_um of the macro
                outline (Manhattan distance to the box, the macro size from its LEF), or with a reason
    gpio_modes  rtl user_defines.v: every GPIO 5-37 has the planned mode (default_mode if not planned)
    localparams the wrapper's localparam named by each pin equals its GPIO
    config      the LibreLane config places the macro instance at the planned location and uses the
                template DEF (FP_DEF_TEMPLATE = dir::<template_def>)
Prints `pin-plan: PASS` / `pin-plan: FAIL`; exit code 0 only on PASS. Python stdlib only.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEGACY = {"soc_top", "picorv32_core"}
CONFIG_NAMES = ("config.json", "config_hazard3.json")


def plan_digest(text):
    """sha256 of the plan text before its [approval] table: what the user approved."""
    return hashlib.sha256(re.split(r"^\[approval\]", text, maxsplit=1, flags=re.M)[0].encode()).hexdigest()


def approval(root, plan_path):
    """(ok, message): the plan carries the user's approval and has not changed since."""
    try:
        text = open(plan_path, encoding="utf8").read()
        plan = tomllib.loads(text)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return False, f"cannot read {plan_path}: {e}"
    name = plan.get("design", "?")
    ap = plan.get("approval", {})
    date, quote, adr, digest = (ap.get(k, "") for k in ("date", "quote", "adr", "plan_sha256"))
    adr_path = os.path.join(root, adr) if adr else ""
    if not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or "") and quote and adr and digest):
        return False, f"{name}: no approval (date, the user's quote, the ADR and plan_sha256 must all be filled after the user reviewed the plan)"
    if not os.path.isfile(adr_path):
        return False, f"{name}: ADR {adr} does not exist"
    if quote not in open(adr_path, encoding="utf8").read():
        return False, f"{name}: ADR {adr} does not contain the quote {quote!r}"
    if digest != plan_digest(text):
        return False, f"{name}: the plan changed after the approval of {date} (plan_sha256 differs); the user has to approve it again"
    if not any(quote in ln and date in ln and digest in ln for ln in open(adr_path, encoding="utf8").read().splitlines()):
        return False, (f"{name}: ADR {adr} has no line with the quote, the date {date} and plan_sha256 {digest} together "
                       "(the approval of this version of the plan is not recorded); the user has to approve it")
    return True, f"{name}: approved {date} ({adr})"


def def_pins(path):
    pins = {}
    t = open(path, encoding="utf8", errors="replace").read()
    for name, x, y in re.findall(r"- (\S+) \+ NET \S+[^;]*?\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \)", t, re.S):
        pins[name] = (int(x) / 1000.0, int(y) / 1000.0)
    return pins


def lef_size(path, macro):
    t = open(path, encoding="utf8", errors="replace").read()
    m = re.search(r"MACRO\s+" + re.escape(macro) + r"\b.*?SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", t, re.S)
    return (float(m.group(1)), float(m.group(2))) if m else None


def box_distance(p, box):
    (x, y), (x0, y0, x1, y1) = p, box
    return max(x0 - x, 0.0, x - x1) + max(y0 - y, 0.0, y - y1)


def check_plan(root, plan_path, row):
    try:
        plan = tomllib.load(open(plan_path, "rb"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        row("plan", False, f"cannot read {plan_path}: {e}")
        return
    rp = lambda p: os.path.join(root, p)
    name = plan.get("design", "?")

    row("approval", *approval(root, plan_path))

    gov = plan.get("governs", {}).get("files", [])
    missing = [f for f in gov if not os.path.exists(rp(f))]
    row("governs", bool(gov) and not missing, f"{len(gov)} governed files" + (f"; missing {missing}" if missing else ""))

    pads = plan.get("pads", {})
    if pads.get("source") != "fixed":
        row("pads", False, f"pads.source = {pads.get('source')!r}: only 'fixed' (a given pad ring, e.g. Caravel) is implemented")
        return
    tdef = pads.get("template_def", "")
    pins = def_pins(rp(tdef)) if os.path.isfile(rp(tdef)) else {}
    planned = plan.get("pin", [])
    gpios = [p.get("gpio") for p in planned]
    absent = [g for g in gpios if f"io_in[{g}]" not in pins]
    row("template", bool(pins) and not absent, f"{tdef}: {len(pins)} placed pins" + (f"; planned GPIO not placed: {absent}" if absent else ""))

    blk = plan.get("block", {})
    size = lef_size(rp(blk.get("macro_lef", "")), blk.get("macro", "")) if os.path.isfile(rp(blk.get("macro_lef", ""))) else None
    loc = blk.get("location")
    bad = []
    reserved = set(pads.get("reserved_gpio", []))
    for p in planned:
        g = p.get("gpio")
        if g in reserved or not isinstance(g, int) or not 0 <= g <= 37:
            bad.append(f"GPIO {g} ({p.get('signal')}) is reserved or out of range")
        if gpios.count(g) > 1:
            bad.append(f"GPIO {g} planned twice")
    dists = []
    if size and loc and not absent:
        box = (loc[0], loc[1], loc[0] + size[0], loc[1] + size[1])
        lim = blk.get("max_pin_distance_um")
        for p in planned:
            d = box_distance(pins[f"io_in[{p['gpio']}]"], box)
            dists.append(f"{p['gpio']}:{d:.0f}")
            if lim is None or (d > lim and not p.get("reason")):
                bad.append(f"GPIO {p['gpio']} ({p.get('signal')}) is {d:.0f} um from the macro, over max_pin_distance_um {lim} with no reason")
    else:
        bad.append("cannot compute pin distances (macro LEF size, location or template pins missing)")
    row("pins", not bad, (f"{len(planned)} pins, distance to the macro (um) " + " ".join(dists)) if not bad else "; ".join(dict.fromkeys(bad)))

    rtl = plan.get("rtl", {})
    ud = rp(rtl.get("user_defines", ""))
    if os.path.isfile(ud):
        have = dict(re.findall(r"`define\s+USER_CONFIG_GPIO_(\d+)_INIT\s+`GPIO_MODE_(\w+)", open(ud, encoding="utf8").read()))
        want = {str(g): plan.get("gpio", {}).get("default_mode", "") for g in range(5, 38)}
        want.update({str(p["gpio"]): p.get("mode", "") for p in planned})
        diff = [f"GPIO {g}: {have.get(g)} (plan {m})" for g, m in sorted(want.items(), key=lambda kv: int(kv[0])) if have.get(g) != m]
        row("gpio_modes", not diff, f"{rtl['user_defines']}: GPIO 5-37 as planned" if not diff else "; ".join(diff))
    else:
        row("gpio_modes", False, f"user_defines {rtl.get('user_defines')!r} not found")
    wr = rp(rtl.get("wrapper", ""))
    if os.path.isfile(wr):
        lps = {k: int(v) for k, v in re.findall(r"localparam\s+(\w+)\s*=\s*(\d+)\s*;", open(wr, encoding="utf8").read())}
        diff = [f"{p['localparam']} = {lps.get(p['localparam'])} (plan {p['gpio']})" for p in planned
                if p.get("localparam") and lps.get(p["localparam"]) != p["gpio"]]
        n = sum(1 for p in planned if p.get("localparam"))
        row("localparams", n > 0 and not diff, f"{rtl['wrapper']}: {n} localparams as planned" if n and not diff
            else ("; ".join(diff) or "no pin names a localparam"))
    else:
        row("localparams", False, f"wrapper {rtl.get('wrapper')!r} not found")

    cfg_path = rp(blk.get("config", ""))
    try:
        cfg = json.load(open(cfg_path, encoding="utf8"))
        inst = cfg.get("MACROS", {}).get(blk.get("macro"), {}).get("instances", {}).get(blk.get("instance"), {})
        ok_loc = inst.get("location") == loc
        ok_def = cfg.get("FP_DEF_TEMPLATE") == "dir::" + tdef
        row("config", ok_loc and ok_def,
            f"{blk['config']}: {blk.get('instance')} at {inst.get('location')} (plan {loc}), FP_DEF_TEMPLATE {cfg.get('FP_DEF_TEMPLATE')}")
    except (OSError, ValueError) as e:
        row("config", False, f"cannot read {blk.get('config')}: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--design")
    ap.add_argument("--digest")
    ap.add_argument("plans", nargs="*")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    rows = []
    if args.digest:
        print(plan_digest(open(args.digest, encoding="utf8").read()))
        return 0

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    plans = [os.path.abspath(p) for p in args.plans]
    if args.design:
        own = os.path.join(root, "pnr", args.design, "pin_plan.toml")
        if os.path.isfile(own):
            plans = [own]
        else:
            row("coverage", args.design in LEGACY,
                f"{args.design}: legacy design, pins placed before rule 14" if args.design in LEGACY
                else f"{args.design}: no pnr/{args.design}/pin_plan.toml (write the plan and get it approved first)")
    elif not plans:
        plans = sorted(glob.glob(os.path.join(root, "pnr", "*", "pin_plan.toml")))
        tops = sorted(os.path.basename(os.path.dirname(c)) for n in CONFIG_NAMES for c in glob.glob(os.path.join(root, "pnr", "*", n)))
        without = sorted({d for d in tops if d not in LEGACY and not os.path.isfile(os.path.join(root, "pnr", d, "pin_plan.toml"))})
        row("coverage", not without and bool(plans),
            f"plans for {[os.path.basename(os.path.dirname(p)) for p in plans]}; legacy without a plan {sorted(LEGACY & set(tops))}"
            + (f"; designs without a plan: {without}" if without else ""))
    for p in plans:
        print(f"pin-plan: {os.path.relpath(p, root)}")
        check_plan(root, p, row)
    ok = bool(rows) and all(rows)
    print(f"pin-plan: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
