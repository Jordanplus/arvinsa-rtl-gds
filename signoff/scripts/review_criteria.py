#!/usr/bin/env python3
"""Signoff criteria review of one soc_top run, part 1: were the criteria applied (skill signoff-criteria,
"每次 harden 後的檢查"; user decision 2026-10-07).

usage: review_criteria.py [--cpu picorv32|hazard3] [--run <dir>] [--out <dir>] [--config <file>]

Defaults: --run runs/<tag>, --out runs/<tag>_signoff, --config pnr/soc_top/config.json or
config_hazard3.json (the same tags as pnr/soc_top/run.sh). Rows, each PASS or FAIL:
  config_applied   every setting of the config (except meta) has the same value in the run's
                   resolved.json: numbers as numbers, dir::<p> = <the run's DESIGN_DIR>/<p>,
                   pdk_dir::<p> = a path ending in /<p>, a dict only for the keys the config has,
                   EXTRA_EXCLUDED_CELLS the config's cells all present (LibreLane adds the PDK's)
  step_config      every step's config.json has the resolved value of each of those settings it
                   carries (each step really received them)
  uncertainty      the line clock_uncertainty.sdc prints (tclsh runs the run's
                   pnr/soc_top/clock_uncertainty.sdc with the resolved CLOCK_PERIOD) is in the log
                   of every timing step (STAPrePNR, GlobalPlacement, RepairDesignPostGPL, CTS,
                   ResizerTimingPostCTS, GlobalRouting, RepairDesignPostGRT, and ResizerTimingPostGRT
                   when RUN_POST_GRT_RESIZER_TIMING is on) and in the sta.log of every signoff corner;
                   a step the config replaces (meta substituting_steps) is looked up under its
                   replacement (CTS: Arvinsa.CTSNoInsertionDelay, ADR-0016)
  signoff_corners  the signoff STA (STAPostPNR) has one directory per STA_CORNERS entry, no more
  checkers_ran     <out> has the verdict line of check_signoff.py (signoff.txt), check_soc.py
                   (soc_checks.txt), check_inputs.py --resolved (inputs_resolved.txt) and
                   provenance.py --verify (provenance_end.txt): PASS or FAIL, but present (a
                   LibreLane FAIL must not skip them)
Then [INFO] rows with the numbers the second part needs (are the criteria reasonable; Claude
reads them with the skill and writes <out>/criteria_review.md): where each resizer timing repair
(ResizerTimingPostCTS, ResizerTimingPostGRT) ended and the gap from the last one to signoff
against its margin, hold and repair buffers, the worst setup path by category with its launch and
capture clock edges and the uncertainty it got, the worst half-cycle setup path (a falling edge
to a rising edge or back; it carries the duty cycle distortion budget), the clock skew metric
without the hold uncertainty (skill rule 4), the SDC slew limits.
Prints `criteria-review: PASS` / `criteria-review: FAIL` last; exit code 0 only on PASS.
Python stdlib and tclsh.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TAGS = {"picorv32": ("soc_top", "config.json"), "hazard3": ("soc_top_hazard3", "config_hazard3.json")}
TIMING_STEPS = ["OpenROAD.STAPrePNR", "OpenROAD.GlobalPlacement", "OpenROAD.RepairDesignPostGPL", "OpenROAD.CTS",
                "OpenROAD.ResizerTimingPostCTS", "OpenROAD.GlobalRouting", "OpenROAD.RepairDesignPostGRT",
                "OpenROAD.ResizerTimingPostGRT"]
# Steps that only run when a flag is on: (flag, LibreLane default).
OPTIONAL_STEPS = {"OpenROAD.RepairDesignPostGRT": ("RUN_POST_GRT_DESIGN_REPAIR", True),
                  "OpenROAD.ResizerTimingPostGRT": ("RUN_POST_GRT_RESIZER_TIMING", False)}
# Resizer timing repairs in flow order: (step, parasitics, setup margin, hold margin).
REPAIRS = [("OpenROAD.ResizerTimingPostCTS", "placement parasitics", "PL_RESIZER_SETUP_SLACK_MARGIN",
            "PL_RESIZER_HOLD_SLACK_MARGIN"),
           ("OpenROAD.ResizerTimingPostGRT", "global routing parasitics", "GRT_RESIZER_SETUP_SLACK_MARGIN",
            "GRT_RESIZER_HOLD_SLACK_MARGIN")]
VERDICTS = {"signoff.txt": "signoff", "soc_checks.txt": "soc-checks", "inputs_resolved.txt": "soc-inputs",
            "provenance_end.txt": "provenance"}
REPAIR_RE = re.compile(r"^(wire|fanout|load_slew|max_length|split|rebuffer)\d+$")
HOLD_RE = re.compile(r"^hold\d+$")


# The config's "meta": {"substituting_steps": {old id: new id}} (set in main): a step the flow replaced
# is looked up under its replacement (OpenROAD.CTS -> Arvinsa.CTSNoInsertionDelay, ADR-0016).
SUBSTITUTED = {}


def step_dirs(run, step_id):
    """All step directories of a LibreLane step id, in run order (a repeated step gets -1, -2, ...)."""
    step_id = SUBSTITUTED.get(step_id, step_id)
    pat = re.compile(r"\d+-" + re.escape(step_id.lower().replace(".", "-")) + r"(-\d+)?$")
    return sorted((d for d in glob.glob(os.path.join(run, "[0-9]*")) if pat.fullmatch(os.path.basename(d))),
                  key=lambda d: int(os.path.basename(d).split("-")[0]))


def same(cfg, res, design_dir, key):
    """Differences between a config value and its resolved value (empty list if they agree)."""
    if isinstance(cfg, str) and cfg.startswith("dir::"):
        want = os.path.normpath(os.path.join(design_dir, cfg[5:]))
        return [] if isinstance(res, str) and os.path.normpath(res) == want else [f"{cfg} -> {res}"]
    if isinstance(cfg, str) and cfg.startswith("pdk_dir::"):
        return [] if isinstance(res, str) and res.endswith("/" + cfg[9:]) else [f"{cfg} -> {res}"]
    if isinstance(cfg, bool) or isinstance(res, bool):
        return [] if cfg is res else [f"{cfg} -> {res}"]
    if isinstance(cfg, (int, float)):
        return [] if isinstance(res, (int, float)) and float(cfg) == float(res) else [f"{cfg} -> {res}"]
    if isinstance(cfg, dict):
        if not isinstance(res, dict):
            return [f"dict -> {res}"]
        return [f"{k}: {d}" for k in cfg for d in (same(cfg[k], res[k], design_dir, key) if k in res else ["missing"])]
    if isinstance(cfg, list):
        if key == "EXTRA_EXCLUDED_CELLS":
            miss = [c for c in cfg if c not in (res or [])]
            return [f"not excluded: {' '.join(miss)}"] if miss else []
        if not isinstance(res, list) or len(res) != len(cfg):
            return [f"{cfg} -> {res}"]
        return [d for a, b in zip(cfg, res) for d in same(a, b, design_dir, key)]
    return [] if cfg == res else [f"{cfg!r} -> {res!r}"]


def expected_uncertainty_line(design_dir, period):
    """The line clock_uncertainty.sdc prints, from the SDC itself (tclsh with stubs for the STA commands)."""
    sdc = os.path.join(design_dir, "pnr", "soc_top", "clock_uncertainty.sdc")
    tclsh = shutil.which("tclsh")
    if tclsh is None or not os.path.isfile(sdc):
        return None, f"cannot evaluate {sdc} (tclsh {'missing' if tclsh is None else 'ok'})"
    script = ("proc get_clocks {args} {return clk}\nproc set_clock_uncertainty {args} {}\n"
              f"set ::clock_port clk\nset ::env(CLOCK_PERIOD) {period}\nsource {{{sdc}}}\n")
    cp = subprocess.run([tclsh], input=script, capture_output=True, text=True)
    lines = [ln for ln in cp.stdout.splitlines() if ln.startswith("clock_uncertainty.sdc:")]
    if cp.returncode != 0 or len(lines) != 1:
        return None, f"tclsh on {sdc} failed: {cp.stderr.strip()[:200]}"
    return lines[0], ""


def has_line(path, line):
    try:
        with open(path, errors="replace") as f:
            return any(ln.rstrip("\r\n").endswith(line) for ln in f)
    except OSError:
        return False


def resizer_final(log):
    """(setup WNS, hold WNS) of the `final` rows of the repair tables in a resizer step log."""
    setup = hold = None
    text = open(log, errors="replace").read() if log and os.path.isfile(log) else ""
    for block, kind in ((text.split("Iter   |"), "setup"), (text.split("Iteration |"), "hold")):
        for part in block[1:]:
            m = re.search(r"^\s*final\s*\|(.*)$", part, re.M)
            if m:
                cols = [c.strip() for c in m.group(1).split("|")]
                idx = 6 if kind == "setup" else 4   # setup: Removed Resized Inserted Cloned Pin Area WNS; hold: Resized Buffers Cloned Area WNS
                try:
                    val = float(cols[idx])
                except (IndexError, ValueError):
                    continue
                if kind == "setup":
                    setup = val
                else:
                    hold = val
    return setup, hold


def path_edges(p):
    """Launch and capture clock edges of one path of an OpenSTA report, [(time, clock, rise|fall)],
    and the uncertainty it got (positive ns; None if the path has none)."""
    edges = [(float(t), c, e) for t, c, e in
             re.findall(r"^\s*(-?\d+\.\d+)\s+-?\d+\.\d+\s+clock (\S+) \((rise|fall) edge\)", p, re.M)]
    unc = re.search(r"^\s*(-?\d+\.\d+)\s+-?\d+\.\d+\s+(?:inter-clock |clock )?uncertainty", p, re.M)
    return edges[:2], abs(float(unc.group(1))) if unc else None


def half_cycle(edges):
    return len(edges) == 2 and edges[0][2] != edges[1][2]


def worst_half_cycle(rpt):
    """First (worst, the report is sorted by slack) half-cycle path of an OpenSTA max.rpt:
    (start, end, slack, uncertainty) or None, and the number of paths looked at."""
    paths = open(rpt, errors="replace").read().split("Startpoint:")[1:]
    for i, p in enumerate(paths):
        edges, unc = path_edges(p)
        if half_cycle(edges):
            slack = re.search(r"(-?\d+\.\d+)\s+slack", p)
            return (p.split()[0], re.search(r"Endpoint: (\S+)", p).group(1),
                    float(slack.group(1)) if slack else None, unc), i + 1
    return None, len(paths)


def path_by_category(rpt):
    """Worst path of an OpenSTA max.rpt: delay per category (launch clock, clk->Q, logic, repair
    buffers, hold buffers, interconnect), the start and end points, the slack, the launch and
    capture clock edges and the uncertainty."""
    text = open(rpt, errors="replace").read()
    if "Startpoint:" not in text:
        return None
    p = text.split("Startpoint:", 2)[1]
    start = p.split()[0]
    end = re.search(r"Endpoint: (\S+)", p).group(1)
    slack = re.search(r"(-?\d+\.\d+)\s+slack", p)
    edges, unc = path_edges(p)
    data = p.split("data arrival time", 1)[0]
    cats, in_clock = {}, True
    for ln in data.splitlines():
        m = re.match(r"\s*(?:\d+\s+\S+\s+)?\S+\s+(-?\d+\.\d+)\s+-?\d+\.\d+\s+[v^]\s+(\S+)/(\S+)\s+\((\S+)\)", ln)
        if not m:
            continue
        delay, inst, pin = float(m.group(1)), m.group(2), m.group(3)
        out_pin = re.match(r"\s*\d+\s+\S+\s+\S+\s+-?\d+\.\d+\s+-?\d+\.\d+\s+[v^]", ln) is not None
        if in_clock:
            k = "launch clock"
            if inst == start and not out_pin:
                in_clock = False
        elif not out_pin:
            k = "interconnect"
        elif inst == start:
            k = "clk->Q"
        elif HOLD_RE.match(inst):
            k = "hold buffers"
        elif REPAIR_RE.match(inst):
            k = "repair buffers"
        else:
            k = "logic"
        n, d = cats.get(k, (0, 0.0))
        cats[k] = (n + (1 if out_pin else 0), d + delay)
    return start, end, float(slack.group(1)) if slack else None, cats, edges, unc


def netlist_buffers(nl):
    counts = {}
    if nl and os.path.isfile(nl):
        for m in re.finditer(r"^\s*sky130_fd_sc_hd__\w+\s+(\w+)\s*\(", open(nl, errors="replace").read(), re.M):
            name = m.group(1)
            k = "hold" if HOLD_RE.match(name) else (REPAIR_RE.match(name).group(1) if REPAIR_RE.match(name) else None)
            if k:
                counts[k] = counts.get(k, 0) + 1
    return counts


def metric(step, key):
    p = os.path.join(step, "or_metrics_out.json") if step else ""
    return json.load(open(p)).get(key) if p and os.path.isfile(p) else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpu", default="picorv32", choices=sorted(TAGS))
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--config")
    args = ap.parse_args()
    tag, cfg_name = TAGS[args.cpu]
    run = os.path.abspath(args.run or os.path.join(ROOT, "runs", tag))
    out = os.path.abspath(args.out or os.path.join(ROOT, "runs", tag + "_signoff"))
    config_path = os.path.abspath(args.config or os.path.join(ROOT, "pnr", "soc_top", cfg_name))
    rows = []

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    print(f"criteria-review: run {run}, config {config_path}")
    raw = json.load(open(config_path))
    SUBSTITUTED.update(((raw.get("meta") or {}).get("substituting_steps")) or {})
    cfg = {k: v for k, v in raw.items() if not k.startswith("//") and k != "meta"}
    res_p = os.path.join(run, "resolved.json")
    if not os.path.isfile(res_p):
        row("config_applied", False, f"no {res_p}")
        print("criteria-review: FAIL")
        return 1
    res = json.load(open(res_p))
    design_dir = res.get("DESIGN_DIR") or ROOT

    bad = [f"{k}: {d}" for k in cfg for d in (same(cfg[k], res[k], design_dir, k) if k in res else ["not in resolved.json"])]
    row("config_applied", not bad, f"{len(cfg)} settings of {os.path.basename(config_path)} = resolved.json" if not bad
        else "; ".join(bad[:6]) + (f" (and {len(bad) - 6} more)" if len(bad) > 6 else ""))

    bad, n_steps = [], 0
    for sc in sorted(glob.glob(os.path.join(run, "[0-9]*", "config.json"))):
        n_steps += 1
        sc_cfg = json.load(open(sc))
        for k in cfg:
            if k in sc_cfg and k in res and sc_cfg[k] != res[k]:
                bad.append(f"{os.path.basename(os.path.dirname(sc))} {k}")
    row("step_config", n_steps > 0 and not bad, f"{n_steps} step configs agree with resolved.json" if n_steps and not bad
        else ("no step config.json" if not n_steps else "; ".join(bad[:6])))

    line, err = expected_uncertainty_line(design_dir, res.get("CLOCK_PERIOD"))
    sta_steps = step_dirs(run, "OpenROAD.STAPostPNR")
    sta = sta_steps[-1] if sta_steps else None
    if line is None:
        row("uncertainty", False, err)
    else:
        missing, n_timing = [], 0
        for sid in TIMING_STEPS:
            dirs = step_dirs(run, sid)
            if sid in OPTIONAL_STEPS and not res.get(*OPTIONAL_STEPS[sid]):
                continue
            n_timing += 1
            if not dirs:
                missing.append(f"{sid} (no step)")
            elif not any(has_line(lg, line) for d in dirs for lg in glob.glob(os.path.join(d, "**", "*.log"), recursive=True)):
                missing.append(sid)
        corner_logs = sorted(glob.glob(os.path.join(sta, "*", "sta.log"))) if sta else []
        missing += [f"signoff {os.path.basename(os.path.dirname(lg))}" for lg in corner_logs if not has_line(lg, line)]
        if not corner_logs:
            missing.append("signoff STA (no corner sta.log)")
        row("uncertainty", not missing, f"'{line}' in {n_timing} timing steps and {len(corner_logs)} signoff corners"
            if not missing else f"'{line}' missing in: {', '.join(missing)}")

    want = set(res.get("STA_CORNERS") or [])
    have = {os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(sta, "*", "sta.log"))} if sta else set()
    row("signoff_corners", bool(want) and have == want, f"{len(have)} corners = STA_CORNERS" if have == want and want
        else f"missing {sorted(want - have)}, extra {sorted(have - want)}")

    missing = []
    for f, word in VERDICTS.items():
        p = os.path.join(out, f)
        txt = open(p, errors="replace").read() if os.path.isfile(p) else ""
        if not re.search(rf"^{re.escape(word)}: (PASS|FAIL)\b", txt, re.M):
            missing.append(f)
    row("checkers_ran", not missing, f"verdict lines in {', '.join(VERDICTS)}" if not missing
        else f"no verdict line in {', '.join(missing)} (in {out})")

    # Numbers for part 2 (are the criteria reasonable); printed only.
    def info(msg):
        print(f"  [INFO] {msg}")

    m = json.load(open(os.path.join(out, "metrics.json"))) if os.path.isfile(os.path.join(out, "metrics.json")) else {}
    corners = sorted(want)
    ws = {c: (m.get(f"timing__setup__ws__corner:{c}"), m.get(f"timing__hold__ws__corner:{c}")) for c in corners}
    setups = [(v[0], c) for c, v in ws.items() if isinstance(v[0], (int, float))]
    holds = [(v[1], c) for c, v in ws.items() if isinstance(v[1], (int, float))]
    rtc = (step_dirs(run, "OpenROAD.ResizerTimingPostCTS") or [None])[-1]
    repairs = []   # (step, parasitics, setup margin key, hold margin key, setup final, hold final)
    for sid, para, s_key, h_key in REPAIRS:
        d = (step_dirs(run, sid) or [None])[-1]
        if d:
            fin = resizer_final(next(iter(glob.glob(os.path.join(d, "*.log"))), None))
            repairs.append((sid.split(".")[1], para, s_key, h_key) + fin)
    for kind, worst, idx, key_idx in (("setup", setups, 4, 2), ("hold", holds, 5, 3)):
        if not repairs:
            info(f"{kind}: no resizer timing repair step in the run")
            continue
        ends = "; ".join(f"{r[0]} ended its {kind} repair at WNS {r[idx]:+.3f} ns ({r[1]})" if r[idx] is not None
                         else f"{r[0]} has no {kind} repair table (no {kind} violation in RSZ_CORNERS)" for r in repairs)
        last = [r for r in repairs if r[idx] is not None]
        if worst and last:
            w, c = min(worst)
            r = last[-1]
            ends += (f"; signoff worst {w:+.3f} ns ({c}); gap from the last {kind} repair ({r[0]}) {r[idx] - w:.3f} ns vs "
                     f"{r[key_idx]} {res.get(r[key_idx])} ns")
        info(f"{kind}: {ends}")
    viol = [c for c in corners if isinstance(m.get(f"timing__setup_vio__count__corner:{c}"), int)
            and m.get(f"timing__setup_vio__count__corner:{c}") > 0]
    if setups:
        info("signoff setup ws per corner: " + ", ".join(f"{c} {v:+.3f}" for v, c in sorted(setups)[:5])
             + (f"; setup violations in {', '.join(viol)}" if viol else ""))
    cts = (step_dirs(run, "OpenROAD.CTS") or [None])[-1]
    a0, a1 = metric(cts, "design__instance__area__stdcell"), metric(rtc, "design__instance__area__stdcell")
    nl = os.path.join(run, "final", "nl", "soc_top.nl.v")
    bufs = netlist_buffers(nl)
    if a0 and a1:
        info(f"ResizerTimingPostCTS stdcell area {a0:.0f} -> {a1:.0f} um^2 ({100 * (a1 - a0) / a0:+.1f} %); final netlist "
             f"hold buffers {bufs.get('hold', 0)}, repair buffers "
             + ", ".join(f"{k} {v}" for k, v in sorted(bufs.items()) if k != "hold"))
    if viol or setups:
        worst_c = min(setups)[1] if setups else None
        rpt = os.path.join(sta, worst_c, "max.rpt") if sta and worst_c else ""
        r = path_by_category(rpt) if os.path.isfile(rpt) else None
        if r:
            start, end, slack, cats, edges, unc = r
            total = sum(d for _, d in cats.values())
            how = (f"launched at the {edges[0][2]} edge ({edges[0][0]:.2f} ns), captured at the {edges[1][2]} edge "
                   f"({edges[1][0]:.2f} ns){', a half-cycle path' if half_cycle(edges) else ''}, uncertainty "
                   + (f"{unc:.3f} ns" if unc is not None else "none") if len(edges) == 2 else "clock edges not found")
            info(f"worst setup path ({worst_c}) {start} -> {end}, slack {slack}, {how}: " + ", ".join(
                f"{k} {d:.2f} ns ({n} cells)" if k not in ("interconnect", "launch clock") else f"{k} {d:.2f} ns"
                for k, (n, d) in sorted(cats.items(), key=lambda x: -x[1][1])) + f"; arrival {total:.2f} ns after the launch edge")
    hc, looked = [], 0
    for c in corners:
        rpt = os.path.join(sta, c, "max.rpt") if sta else ""
        if os.path.isfile(rpt):
            h, n = worst_half_cycle(rpt)
            looked += n
            if h and h[2] is not None:
                hc.append((h[2], c) + h)
    dcd = re.search(r"duty cycle distortion (\d+(?:\.\d+)?)", line or "")
    if hc:
        slack, c, start, end, _, unc = min(hc)
        info(f"worst half-cycle setup path ({c}) {start} -> {end}, slack {slack:+.3f} ns, uncertainty "
             + (f"{unc:.3f} ns" if unc is not None else "none") + (f" of which duty cycle distortion {float(dcd.group(1)):.3f} ns"
                                                                 if dcd else ""))
    elif sta:
        info(f"no half-cycle setup path in the {looked} paths of the signoff max.rpt files")
    unc = re.search(r"hold (\d+(?:\.\d+)?)", line or "")
    for c in ("nom_ff_n40C_1v95", "nom_ss_n40C_1v60"):
        sk = m.get(f"clock__skew__worst_hold__corner:{c}")
        if isinstance(sk, (int, float)) and unc:
            info(f"clock skew metric (hold) {c} {sk:+.3f} ns, without the hold uncertainty {sk + float(unc.group(1)):+.3f} ns "
                 "(still includes the 5 % derate; skill signoff-criteria rule 4)")
    for key in ("PNR_SDC_FILE", "SIGNOFF_SDC_FILE"):
        p = res.get(key)
        txt = open(p, errors="replace").read() if p and os.path.isfile(p) else ""
        mt = re.findall(r"^\s*set_max_transition\s+(\S+)", txt, re.M)
        info(f"{key} set_max_transition {', '.join(mt) or 'not set (PDK default)'}; DESIGN_REPAIR_MAX_SLEW_PCT "
             f"{res.get('DESIGN_REPAIR_MAX_SLEW_PCT')}, GRT_DESIGN_REPAIR_MAX_SLEW_PCT {res.get('GRT_DESIGN_REPAIR_MAX_SLEW_PCT')}"
             if key == "PNR_SDC_FILE" else f"{key} set_max_transition {', '.join(mt) or 'not set (PDK default)'}")
    info(f"part 2: review these numbers with skill signoff-criteria and write {os.path.join(out, 'criteria_review.md')}")
    ok = all(rows)
    print("criteria-review: PASS" if ok else "criteria-review: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
