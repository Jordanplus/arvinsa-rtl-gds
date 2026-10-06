#!/usr/bin/env python3
"""make test-review-hook: the Claude Code Stop hook .claude/hooks/require_criteria_review.py blocks a
stop while a harden run has no valid signoff criteria review, and lets it through otherwise.

Each case builds a project in a temporary directory (runs/<tag>_signoff/criteria_review.txt and
.md as the case needs), runs the hook with CLAUDE_PROJECT_DIR set to it and the Stop payload on
stdin, and checks the exit code (2 = blocked) and the message. Prints one line per case and
`test-review-hook: PASS` / `FAIL`; exit code 0 only on PASS. Python stdlib only.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOK = os.path.join(ROOT, ".claude", "hooks", "require_criteria_review.py")
TXT = "  [PASS] config_applied: ...\ncriteria-review: FAIL\n"
GOOD_MD = "# review\n\ncriteria-review: FAIL\n\n## 有沒有被執行\n\n## 合不合理\n\n## 學習\n"


def case(name, files, expect_block, expect_text="", payload=None, touch_txt_later=False):
    with tempfile.TemporaryDirectory() as d:
        sig = os.path.join(d, "runs", "soc_top_signoff")
        os.makedirs(sig)
        for rel, text in files.items():
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(text)
        if touch_txt_later:   # the run was redone after the review
            t = time.time() + 10
            os.utime(os.path.join(sig, "criteria_review.txt"), (t, t))
        cp = subprocess.run([sys.executable, HOOK], input=json.dumps(payload or {"stop_hook_active": False}),
                            capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=d))
        blocked = cp.returncode == 2
        ok = blocked == expect_block and (expect_text in cp.stderr) and cp.returncode in (0, 2)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {'blocked' if blocked else 'allowed'} (rc {cp.returncode})"
              + ("" if ok else f"; stderr: {cp.stderr.strip()[:300]}"))
        return ok


def main():
    s = "runs/soc_top_signoff/"
    results = [
        case("no harden run", {}, False),
        case("run without review part 1 (made before the hook)", {s + "metrics.json": "{}"}, False),
        case("part 1 only", {s + "criteria_review.txt": TXT}, True, "還沒寫"),
        case("complete review", {s + "criteria_review.txt": TXT, s + "criteria_review.md": GOOD_MD}, False),
        case("review older than the run", {s + "criteria_review.txt": TXT, s + "criteria_review.md": GOOD_MD},
             True, "比 criteria_review.txt 舊", touch_txt_later=True),
        case("review without 合不合理", {s + "criteria_review.txt": TXT,
                                       s + "criteria_review.md": GOOD_MD.replace("## 合不合理\n", "")}, True, "## 合不合理"),
        case("review without the verdict line", {s + "criteria_review.txt": TXT,
                                                 s + "criteria_review.md": GOOD_MD.replace("criteria-review: FAIL\n", "")},
             True, "criteria-review: FAIL"),
        case("stop_hook_active lets it through", {s + "criteria_review.txt": TXT}, False,
             payload={"stop_hook_active": True}),
        case("signoff .prev directory ignored", {"runs/soc_top_signoff.prev/criteria_review.txt": TXT}, False),
    ]
    ok = all(results)
    print(f"test-review-hook: {'PASS' if ok else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
