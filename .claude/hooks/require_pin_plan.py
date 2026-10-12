#!/usr/bin/env python3
"""Claude Code PreToolUse hook (Edit, Write, MultiEdit): no edit of the files that place a block or
map its pins before the user approved the pad, block and pin plan (user decision 2026-10-12;
CLAUDE.md rule 14, skill chip-floorplan-pin-planning).

Blocked (exit code 2, reason on stderr, the edit does not happen):
  - a file listed under [governs] of pnr/<design>/pin_plan.toml while that plan is not approved
    (scripts/check_pin_plan.py approval(): date, the user's quote in the ADR, plan_sha256 equal to
    the plan as it is now). A governed pnr/<design>/config*.json only when the edit touches a
    placement or pin setting (PLACEMENT_KEYS); a clock period or a resizer setting stays editable.
  - an edit of pnr/<design>/config*.json that touches a placement or pin setting, for a design that
    has no pin_plan.toml and is not legacy (check_pin_plan.LEGACY).
Everything else passes (exit code 0). Edits through Bash (sed -i, a script) are not seen here;
make pin-plan catches the result at harden and in make regress. An error inside the hook lets the
edit through with a warning (exit code 1), so a broken hook cannot stop the session.
make neg-pin-plan (scripts/neg_pin_plan.py) tests this hook. Python stdlib only.
"""
import glob
import json
import os
import re
import sys
import tomllib

PLACEMENT_KEYS = re.compile(
    r"^(MACROS|FP_DEF_TEMPLATE|DIE_AREA|CORE_AREA|FP_SIZING|FP_CORE_UTIL|FP_ASPECT_RATIO|MACRO_PLACEMENT_CFG"
    r"|IO_PIN\w*|FP_PIN\w*|FP_IO\w*|location|orientation|instances)$")
CONFIG = re.compile(r"^pnr/([^/]+)/config[^/]*\.json$")


def keys_in_text(text):
    return {k for k in re.findall(r'"(\w+)"\s*:', text) if PLACEMENT_KEYS.match(k)}


def placement_view(obj):
    """The placement and pin settings of a LibreLane config (top level, MACROS whole)."""
    return {k: v for k, v in obj.items() if PLACEMENT_KEYS.match(k)} if isinstance(obj, dict) else {}


def touches_placement(tool, inp, path):
    if tool == "Write":
        new = inp.get("content", "")
        try:
            old = json.load(open(path, encoding="utf8")) if os.path.isfile(path) else {}
            return placement_view(json.loads(new)) != placement_view(old)
        except (OSError, ValueError):
            return bool(keys_in_text(new))
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    return any(keys_in_text(e.get("old_string", "") + "\n" + e.get("new_string", "")) for e in edits or [])


def problem(project, tool, inp):
    path = inp.get("file_path") or ""
    if not path:
        return None
    path = os.path.realpath(os.path.join(project, path))
    rel = os.path.relpath(path, os.path.realpath(project))
    if rel.startswith(".."):
        return None
    sys.path.insert(0, os.path.join(project, "scripts"))
    import check_pin_plan as cpp  # noqa: E402

    plans = sorted(glob.glob(os.path.join(project, "pnr", "*", "pin_plan.toml")))
    cfg = CONFIG.match(rel)
    for p in plans:
        try:
            gov = tomllib.load(open(p, "rb")).get("governs", {}).get("files", [])
        except (OSError, tomllib.TOMLDecodeError):
            gov = []
        if rel not in gov:
            continue
        if cfg and not touches_placement(tool, inp, path):
            return None
        ok, msg = cpp.approval(project, p)
        if not ok:
            return (f"{rel} 由 {os.path.relpath(p, project)} 管轄，這份 pad／block／pin 規劃還沒經使用者核准"
                    f"（{msg}）。先畫 floorplan 圖（scripts/plot_floorplan.py）連同規劃請使用者確認，"
                    "把日期、原話、ADR 與 plan_sha256 填進 [approval]，`make pin-plan` PASS 後再改。")
        return None
    if cfg and cfg.group(1) not in cpp.LEGACY and touches_placement(tool, inp, path) \
            and not os.path.isfile(os.path.join(project, "pnr", cfg.group(1), "pin_plan.toml")):
        return (f"{rel} 要改 block 擺放或腳位的設定，但 pnr/{cfg.group(1)}/pin_plan.toml 不存在。"
                "先照 skill chip-floorplan-pin-planning 寫 pad／block／pin 規劃，經使用者核准後再改。")
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
        tool = payload.get("tool_name", "")
        if tool not in ("Edit", "Write", "MultiEdit"):
            return 0
        msg = problem(project, tool, payload.get("tool_input") or {})
    except Exception as e:  # noqa: BLE001 - a hook never breaks the session
        sys.stderr.write(f"require_pin_plan.py: hook error, edit allowed: {e!r}\n")
        return 1
    if not msg:
        return 0
    sys.stderr.write(msg + "（使用者 2026-10-12 的要求，CLAUDE.md 規則 14）\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
