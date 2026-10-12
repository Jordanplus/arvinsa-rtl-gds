#!/usr/bin/env python3
"""Bug injection for the pad, block and pin plan (CLAUDE.md rule 14): make neg-pin-plan.

Each case copies the user_project_wrapper plan and the files it checks into a temporary project,
fills [approval] (an ADR with the quote, plan_sha256 of the plan after the case's change, unless the
case is about the approval), applies one change and runs scripts/check_pin_plan.py and the Claude
Code hook .claude/hooks/require_pin_plan.py on it.
Checker (must FAIL at the named row, every other row PASS; P0 is the positive control):
  P0 approved plan, files as planned: PASS          A1 no approval
  A2 the ADR does not contain the quote             A3 the plan changed after the approval
  G1 a reserved GPIO (3)                            G2 one GPIO planned twice
     (G1, G2 also FAIL gpio_modes and localparams: the RTL still has the GPIO the plan had)
  G3 a pin farther than max_pin_distance_um without a reason (limit lowered to 100 um)
  T1 a planned GPIO missing in the template DEF (pins also FAILs: no distance)  M1 user_defines.v mode differs from the plan
  L1 a wrapper localparam differs from the plan     C1 config places the SRAM elsewhere
  C2 config without the template DEF                V1 a new design with a config and no plan
  D1 --design of that new design FAILs; D0 --design soc_top (legacy) PASSes
Hook (exit 2 = blocked, 0 = allowed):
  H1 edit of governed RTL, plan not approved: blocked       H2 the same, approved: allowed
  H3 governed config, clock period only, not approved: allowed
  H4 governed config, a macro location, not approved: blocked
  H5 Write of the governed config with another MACROS: blocked; H6 Write changing the period only: allowed
  H7 the plan changed after the approval: governed edit blocked
  H8 placement edit of a new design's config without a plan: blocked
  H9 placement edit of a legacy design's config: allowed   H10 a Read: allowed
Prints one line per case and `neg-pin-plan: PASS n/n`; exit code 0 only on PASS. Python stdlib only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLAN = "pnr/user_project_wrapper/pin_plan.toml"
COPY = [PLAN, "scripts/check_pin_plan.py", ".claude/hooks/require_pin_plan.py",
        "pnr/user_project_wrapper/config.json", "pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def",
        "rtl/caravel/user_project_wrapper.v", "rtl/caravel/user_defines.v",
        "ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/arv_sram_2kbyte_1rw1r_32x512_8.lef",
        "pnr/soc_top/config.json", "pnr/soc_top/config_hazard3.json", "pnr/picorv32_core/config.json"]
ADR = "docs/decisions/neg_pin_plan_adr.md"
QUOTE = "plan approved for the negative test"
results = []


def sub(d, rel, pat, rep, count=1):
    p = os.path.join(d, rel)
    t = open(p, encoding="utf8").read()
    n = len(re.findall(pat, t, re.M))
    if n < 1:
        raise SystemExit(f"neg-pin-plan: injection pattern {pat!r} not found in {rel} (the case went stale)")
    open(p, "w", encoding="utf8").write(re.sub(pat, rep, t, count=count, flags=re.M))


def approve(d, quote_in_adr=True):
    sys.path.insert(0, os.path.join(d, "scripts"))
    p = os.path.join(d, PLAN)
    text = open(p, encoding="utf8").read()
    head, _ = re.split(r"^\[approval\]", text, maxsplit=1, flags=re.M)
    import hashlib
    digest = hashlib.sha256(head.encode()).hexdigest()
    open(p, "w", encoding="utf8").write(
        head + f'[approval]\ndate = "2026-10-12"\nquote = "{QUOTE}"\nadr = "{ADR}"\nplan_sha256 = "{digest}"\n')
    os.makedirs(os.path.join(d, os.path.dirname(ADR)), exist_ok=True)
    open(os.path.join(d, ADR), "w", encoding="utf8").write(f"# ADR\n\n{QUOTE if quote_in_adr else 'other words'}\n")


def project(change=None, approved=True, quote_in_adr=True, after=None):
    """A temporary project: copy, `change` (before the approval), approve, `after` (after it)."""
    d = tempfile.mkdtemp(prefix="neg_pin_plan_")
    for rel in COPY:
        os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), os.path.join(d, rel))
    if change:
        change(d)
    if approved:
        approve(d, quote_in_adr)
    if after:
        after(d)
    return d


def checker(d, *args):
    cp = subprocess.run([sys.executable, os.path.join(d, "scripts", "check_pin_plan.py"), "--root", d, *args],
                        capture_output=True, text=True)
    fails = re.findall(r"^\s*\[FAIL\] (\w+):", cp.stdout, re.M)
    return cp.returncode, fails, cp.stdout


def case_checker(cid, what, expect_row, args=(), also=(), text="", **kw):
    """expect_row None: PASS; else FAIL at expect_row plus the rows in `also` that the same change
    breaks by design (a plan GPIO moved: the RTL no longer follows the plan), with `text` printed."""
    d = project(**kw)
    try:
        rc, fails, out = checker(d, *args)
        ok = (rc == 0 and not fails) if expect_row is None else \
            (rc == 1 and sorted(fails) == sorted([expect_row, *also]) and text in out)
        got = "PASS" if rc == 0 else f"FAIL at {fails}"
        results.append(ok)
        print(f"  [{'ok' if ok else 'WRONG'}] {cid} {what}: {got}" + ("" if ok else f" (expected {expect_row or 'PASS'})\n{out}"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def case_hook(cid, what, tool, inp, expect_block, **kw):
    d = project(**kw)
    try:
        cp = subprocess.run([sys.executable, os.path.join(d, ".claude", "hooks", "require_pin_plan.py")],
                            input=json.dumps({"tool_name": tool, "tool_input": inp, "cwd": d}),
                            capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=d))
        ok = cp.returncode == (2 if expect_block else 0)
        results.append(ok)
        got = {0: "allowed", 2: "blocked"}.get(cp.returncode, f"exit {cp.returncode}")
        print(f"  [{'ok' if ok else 'WRONG'}] {cid} {what}: {got}" + ("" if ok else f"\n{cp.stderr}"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def new_design(d):
    os.makedirs(os.path.join(d, "pnr", "newtop"))
    open(os.path.join(d, "pnr", "newtop", "config.json"), "w").write('{"DESIGN_NAME": "newtop"}\n')


def main():
    print("neg-pin-plan: checker")
    case_checker("P0", "approved plan, files as planned", None)
    case_checker("A1", "no approval", "approval", approved=False)
    case_checker("A2", "ADR without the quote", "approval", quote_in_adr=False)
    case_checker("A3", "plan changed after the approval", "approval",
                 after=lambda d: sub(d, PLAN, r"^max_pin_distance_um = 1000", "max_pin_distance_um = 1100"))
    case_checker("G1", "reserved GPIO 3", "pins", also=("gpio_modes", "localparams"), text="GPIO 3 (uart_tx) is reserved",
                 change=lambda d: sub(d, PLAN, r"^gpio = 37$", "gpio = 3"))
    case_checker("G2", "GPIO 36 planned twice", "pins", also=("gpio_modes", "localparams"), text="GPIO 36 planned twice",
                 change=lambda d: sub(d, PLAN, r"^gpio = 37$", "gpio = 36"))
    case_checker("G3", "pin over max_pin_distance_um", "pins", text="over max_pin_distance_um 100",
                 change=lambda d: sub(d, PLAN, r"^max_pin_distance_um = 1000", "max_pin_distance_um = 100"))
    case_checker("T1", "io_in[37] missing in the template", "template", also=("pins",), text="planned GPIO not placed: [37]",
                 change=lambda d: sub(d, "pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def",
                                      r"^    - io_in\[37\] .*\n(?:      .*\n)*?.*PLACED.*;\n", ""))
    case_checker("M1", "user_defines mode of GPIO 36", "gpio_modes",
                 change=lambda d: sub(d, "rtl/caravel/user_defines.v", r"(GPIO_36_INIT `GPIO_MODE_)\w+", r"\1USER_STD_OUTPUT"))
    case_checker("L1", "localparam GPIO_UART_TX = 30", "localparams",
                 change=lambda d: sub(d, "rtl/caravel/user_project_wrapper.v", r"GPIO_UART_TX = 37;", "GPIO_UART_TX = 30;"))
    case_checker("C1", "SRAM at another location", "config",
                 change=lambda d: sub(d, "pnr/user_project_wrapper/config.json", r"350\.98", "400.98"))
    case_checker("C2", "config without the template DEF", "config",
                 change=lambda d: sub(d, "pnr/user_project_wrapper/config.json", r'"FP_DEF_TEMPLATE"', '"FP_DEF_TEMPLATE_OFF"'))
    case_checker("V1", "new design without a plan", "coverage", change=new_design)
    case_checker("D1", "--design newtop without a plan", "coverage", args=("--design", "newtop"), change=new_design)
    case_checker("D0", "--design soc_top (legacy)", None, args=("--design", "soc_top"), approved=False)

    print("neg-pin-plan: hook")
    rtl = {"file_path": "rtl/caravel/user_defines.v", "old_string": "a", "new_string": "b"}
    cfg = "pnr/user_project_wrapper/config.json"
    case_hook("H1", "governed RTL, not approved", "Edit", rtl, True, approved=False)
    case_hook("H2", "governed RTL, approved", "Edit", rtl, False)
    case_hook("H3", "governed config, period only, not approved", "Edit",
              {"file_path": cfg, "old_string": '"CLOCK_PERIOD": 40', "new_string": '"CLOCK_PERIOD": 45'}, False, approved=False)
    case_hook("H4", "governed config, macro location, not approved", "Edit",
              {"file_path": cfg, "old_string": '"location": [350.98, 413.44]', "new_string": '"location": [400.98, 413.44]'},
              True, approved=False)
    real = json.load(open(os.path.join(ROOT, cfg), encoding="utf8"))
    moved = dict(real, MACROS={})
    case_hook("H5", "Write of the governed config with another MACROS", "Write",
              {"file_path": cfg, "content": json.dumps(moved)}, True, approved=False)
    case_hook("H6", "Write of the governed config, period only", "Write",
              {"file_path": cfg, "content": json.dumps(dict(real, CLOCK_PERIOD=99))}, False, approved=False)
    case_hook("H7", "plan changed after the approval", "Edit", rtl, True,
              after=lambda d: sub(d, PLAN, r"^max_pin_distance_um = 1000", "max_pin_distance_um = 1100"))
    case_hook("H8", "new design's config placement, no plan", "Edit",
              {"file_path": "pnr/newtop/config.json", "old_string": '"DESIGN_NAME"', "new_string": '"DIE_AREA": [0, 0, 1, 1], "DESIGN_NAME"'},
              True, change=new_design)
    case_hook("H9", "legacy design's config placement", "Edit",
              {"file_path": "pnr/soc_top/config.json", "old_string": '"DIE_AREA"', "new_string": '"DIE_AREA"'}, False)
    case_hook("H10", "a Read", "Read", {"file_path": rtl["file_path"]}, False, approved=False)

    n, ok = len(results), sum(results)
    print(f"neg-pin-plan: {'PASS' if ok == n else 'FAIL'} {ok}/{n}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
