#!/usr/bin/env python3
"""make neg-regress: scripts/regress.py must refuse what would make its PASS meaningless.

usage: neg_regress.py

Each case runs this working tree's scripts/regress.py in a local clone of HEAD
(runs/neg_regress/<case>/repo; the script is copied in and committed there, so the clone is
clean) with MAKE set to a fake make that only records the target, prints `<target>: PASS` and
exits 0, so no real target runs:
  pass           clean clone (positive control)        regress: PASS, every target in order
  dirty          clone + one untracked file             FAIL before the first target (uncommitted)
  ignore_errors  MAKEFLAGS=i (as under `make -i regress`) FAIL before the first target (make flags)
  head_changed   the fake make commits during the second target
                                                        FAIL, HEAD changed during the regression
  target_fail    the fake make exits 1 on the third target
                                                        FAIL at that target, the later ones not run
Prints `neg-regress: PASS n/n` / `neg-regress: FAIL ...`; exit code 0 only on PASS.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "runs", "neg_regress")
REGRESS = os.path.join(ROOT, "scripts", "regress.py")
FAKE_MAKE = """#!/bin/sh
# fake make for neg_regress.py: $1 is --no-print-directory, $2 the target
echo "$2" >> "$NEG_REGRESS_LOG"
NEG_REGRESS_N=$(wc -l < "$NEG_REGRESS_LOG" | tr -d ' ')
case "$NEG_REGRESS_MODE:$NEG_REGRESS_N:$2" in
  head_changed:2:*) git -c user.name=neg -c user.email=neg@example.invalid commit -q --allow-empty -m neg ;;
  target_fail:3:*) echo "$2: FAIL"; exit 1 ;;
esac
echo "$2: PASS"
"""


def git(d, *args):
    subprocess.run(["git", "-C", d, "-c", "user.name=neg", "-c", "user.email=neg@example.invalid", *args],
                   check=True, capture_output=True, text=True)


def main():
    shutil.rmtree(OUT, ignore_errors=True)  # only runs/neg_regress is removed
    os.makedirs(OUT)
    targets = subprocess.run([sys.executable, REGRESS, "--list"], capture_output=True, text=True).stdout.split()
    fake = os.path.join(OUT, "fake_make.sh")
    open(fake, "w").write(FAKE_MAKE)
    os.chmod(fake, 0o755)
    results = []

    def case(name, want_rc, want_last, want_targets, extra_env=None, prepare=None):
        d = os.path.join(OUT, name)
        repo = os.path.join(d, "repo")
        subprocess.run(["git", "clone", "-q", ROOT, repo], check=True)
        shutil.copy(REGRESS, os.path.join(repo, "scripts", "regress.py"))
        git(repo, "commit", "-q", "-a", "--allow-empty", "-m", "neg_regress: this working tree's regress.py")
        if prepare:
            prepare(repo)
        log = os.path.join(d, "targets.txt")
        open(log, "w").close()
        env = dict(os.environ, MAKE=fake, NEG_REGRESS_LOG=log, NEG_REGRESS_MODE=name, MAKEFLAGS="")
        env.update(extra_env or {})
        cp = subprocess.run([sys.executable, os.path.join(repo, "scripts", "regress.py")], cwd=repo, env=env,
                            capture_output=True, text=True)
        open(os.path.join(d, "regress.log"), "w").write(cp.stdout + cp.stderr)
        ran = open(log).read().split()
        last = (cp.stdout.strip().splitlines() or [""])[-1]
        ok = cp.returncode == want_rc and last.startswith(want_last) and ran == want_targets
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: expected '{want_last}...' after {len(want_targets)} target(s); "
              f"got rc {cp.returncode}, {len(ran)} target(s), '{last[:100]}'")

    case("pass", 0, f"regress: PASS {len(targets)}/{len(targets)}", targets)
    if not results[-1]:
        print("neg-regress: FAIL (the positive control did not PASS; see runs/neg_regress/pass/regress.log)")
        return 1
    case("dirty", 1, "regress: FAIL before the first target", [],
         prepare=lambda r: open(os.path.join(r, "neg_untracked.txt"), "w").write("x\n"))
    case("ignore_errors", 1, "regress: FAIL before the first target (make flags 'i'", [], extra_env={"MAKEFLAGS": "i"})
    case("head_changed", 1, "regress: FAIL (HEAD changed during the regression", targets)
    case("target_fail", 1, f"regress: FAIL at {targets[2]}", targets[:3])
    ok = all(results)
    print(f"neg-regress: {'PASS' if ok else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
