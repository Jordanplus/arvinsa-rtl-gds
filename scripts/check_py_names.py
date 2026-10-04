#!/usr/bin/env python3
"""make py-check: every name a tracked Python file reads must be defined somewhere in that file.

usage: check_py_names.py [file ...]      (default: `git ls-files '*.py'`, submodules not included)

Why: a function renamed in a refactor left one caller with the old name (neg_pnr.py P11,
Phase 4). Python only fails when that line runs, so the error showed up 20 minutes into
neg-pnr instead of at the start of `make regress`.

The check is deliberately loose: a name counts as defined if it is bound anywhere in the file
(def, class, import, assignment, argument, loop or `with` target, except name, global), or is a
builtin. It finds names that exist nowhere in the file; it does not check scopes. A file with
`from x import *` is skipped.
Before scanning, it checks itself on a snippet that calls an undefined function and FAILs if
that is not reported (a check that cannot report anything must not PASS).
Prints `py-check: PASS <n> files` / `py-check: FAIL ...`; exit code 0 only on PASS.
"""
import ast
import builtins
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILTIN = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}


def undefined(src, path):
    """[(line, name)] of names read in src that are bound nowhere in it; None if it uses `import *`."""
    tree = ast.parse(src, path)
    bound = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        if isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.name == "*":
                    return None
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            bound.update(n.names)
        elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            bound.add(n.name)
    return sorted({(n.lineno, n.id) for n in ast.walk(tree)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                   and n.id not in bound and n.id not in BUILTIN})


def main():
    bad_snippet = "def new_name():\n    return 1\n\ndef caller():\n    return old_name()\n"
    if undefined(bad_snippet, "<self-test>") != [(5, "old_name")]:
        print("py-check: FAIL self-test: the call to an undefined function in the test snippet was not reported")
        return 1
    files = sys.argv[1:] or subprocess.run(["git", "-C", ROOT, "ls-files", "*.py"], capture_output=True,
                                           text=True, check=True).stdout.split()
    errors, skipped = [], []
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        try:
            found = undefined(open(p).read(), f)
        except SyntaxError as e:
            errors.append(f"{f}:{e.lineno}: syntax error: {e.msg}")
            continue
        if found is None:
            skipped.append(f)
            continue
        errors += [f"{f}:{line}: '{name}' is read but never defined in this file" for line, name in found]
    for e in errors:
        print("  " + e)
    note = f" ({len(skipped)} skipped for `import *`: {', '.join(skipped)})" if skipped else ""
    if errors:
        print(f"py-check: FAIL {len(errors)} problem(s) in {len(files)} files{note}")
        return 1
    print(f"py-check: PASS {len(files)} files, no undefined names{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
