#!/usr/bin/env python3
"""Claude Code Stop hook: no report on a harden run before its signoff criteria review is written
(user decision 2026-10-07; skill signoff-criteria, "每次 harden 後的檢查").

pnr/soc_top/run.sh writes part 1, runs/<tag>_signoff/criteria_review.txt (signoff/scripts/
review_criteria.py: were the criteria applied, plus the numbers). Part 2 is Claude's review with
the skill: runs/<tag>_signoff/criteria_review.md. This hook looks at runs/*_signoff/ of the project
and of every git worktree of it; for each criteria_review.txt, criteria_review.md must exist, be
newer than it, carry its verdict line (`criteria-review: PASS` or `FAIL`) and the three sections
"## 有沒有被執行", "## 合不合理", "## 學習". Otherwise the stop is blocked (exit code 2, reason on
stderr). stop_hook_active (Claude is already answering a block) lets the stop through, so it cannot
loop. Python stdlib only.
"""
import glob
import json
import os
import re
import subprocess
import sys

SECTIONS = ("## 有沒有被執行", "## 合不合理", "## 學習")


def roots(project):
    out = [project]
    try:
        cp = subprocess.run(["git", "-C", project, "worktree", "list", "--porcelain"],
                            capture_output=True, text=True, timeout=10)
        out += [ln[9:] for ln in cp.stdout.splitlines() if ln.startswith("worktree ")]
    except (OSError, subprocess.SubprocessError):
        pass
    seen, res = set(), []
    for r in out:
        r = os.path.realpath(r)
        if r not in seen:
            seen.add(r)
            res.append(r)
    return res


def problems(project):
    found = []
    for root in roots(project):
        for txt in sorted(glob.glob(os.path.join(root, "runs", "*_signoff", "criteria_review.txt"))):
            md = os.path.join(os.path.dirname(txt), "criteria_review.md")
            verdict = re.findall(r"^criteria-review: (?:PASS|FAIL)$", open(txt, errors="replace").read(), re.M)
            if not os.path.isfile(md):
                found.append(f"{md}：還沒寫")
                continue
            if os.path.getmtime(md) < os.path.getmtime(txt):
                found.append(f"{md}：比 criteria_review.txt 舊（run 重跑過）")
                continue
            text = open(md, errors="replace").read()
            miss = [s for s in SECTIONS if s not in text]
            if miss:
                found.append(f"{md}：缺少章節 {'、'.join(miss)}")
            if verdict and verdict[-1] not in text:
                found.append(f"{md}：沒有引用腳本的結果行「{verdict[-1]}」")
    return found


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 - a hook never breaks the session on bad input
        payload = {}
    if payload.get("stop_hook_active"):
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    found = problems(project)
    if not found:
        return 0
    sys.stderr.write(
        "harden 跑完後要先做 signoff criteria 檢查，才能回報結果（使用者 2026-10-07 的要求）：\n"
        + "\n".join(f"  · {f}" for f in found[:8])
        + "\n請讀 .claude/skills/signoff-criteria/SKILL.md 的「每次 harden 後的檢查」與該製程的 knowledge 檔，"
          "依同目錄的 criteria_review.txt 寫 criteria_review.md（三個章節：## 有沒有被執行、## 合不合理、## 學習，"
          "並引用它最後的 criteria-review 結果行），再回報。\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
