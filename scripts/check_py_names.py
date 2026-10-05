#!/usr/bin/env python3
"""make py-check: every name a tracked Python file reads must be defined somewhere in that file,
and no file is opened for writing in the same expression that reads it.

usage: check_py_names.py [file ...]      (default: `git ls-files '*.py'`, submodules not included)

Why: a function renamed in a refactor left one caller with the old name (neg_pnr.py P11,
Phase 4). Python only fails when that line runs, so the error showed up 20 minutes into
neg-pnr instead of at the start of `make regress`.

The check is deliberately loose: a name counts as defined if it is bound anywhere in the file
(def, class, import, assignment, argument, loop or `with` target, except name, global), or is a
builtin. It finds names that exist nowhere in the file; it does not check scopes, nor names
taken from another module (`from run_guard import guard_renamed`, `neg_eqy.renamed(...)` pass;
Phase 4 review). A file with `from x import *` is skipped.

Second check: `open(f, "w").write(... open(f).read() ...)`. Python evaluates `open(f, "w")`, which
empties the file, before the argument, so the read gets "" (neg_pnr.py P17, Phase 3.5: the
injection found nothing to edit, at the 19th target, about 80 minutes into `make regress`). Only this
one-expression form is checked, with the same path expression on both sides.

Before scanning, it checks itself on snippets that call an undefined function and that empty a
file before reading it, and FAILs if either is not reported (a check that cannot report anything
must not PASS).
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


def open_call(n):
    """(path expression dump, mode) when n is a call open(path[, mode]), else None."""
    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open" and n.args):
        return None
    mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
    mode = mode.value if isinstance(mode, ast.Constant) and isinstance(mode.value, str) else "r"
    return ast.dump(n.args[0]), mode


def emptied_before_read(src, path):
    """[line] of `open(p, "w").write(...)` calls whose argument opens the same p again."""
    lines = []
    for n in ast.walk(ast.parse(src, path)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("write", "writelines")):
            continue
        target = open_call(n.func.value)
        if target is None or not set(target[1]) & set("wx"):
            continue
        if any(open_call(m) and open_call(m)[0] == target[0] for a in n.args for m in ast.walk(a)):
            lines.append(n.lineno)
    return lines


def main():
    bad_snippet = "def new_name():\n    return 1\n\ndef caller():\n    return old_name()\n"
    if undefined(bad_snippet, "<self-test>") != [(5, "old_name")]:
        print("py-check: FAIL self-test: the call to an undefined function in the test snippet was not reported")
        return 1
    emptied = 'f = "a.txt"\nopen(f, "w").write(open(f).read().upper())\nopen(f + "2", "w").write(open(f).read())\n'
    if emptied_before_read(emptied, "<self-test>") != [2]:
        print("py-check: FAIL self-test: the file emptied before it is read in the test snippet was not reported "
              "(or the write to another file was)")
        return 1
    files = sys.argv[1:] or subprocess.run(["git", "-C", ROOT, "ls-files", "*.py"], capture_output=True,
                                           text=True, check=True).stdout.split()
    errors, skipped = [], []
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        try:
            src = open(p).read()
            found = undefined(src, f)
        except SyntaxError as e:
            errors.append(f"{f}:{e.lineno}: syntax error: {e.msg}")
            continue
        errors += [f"{f}:{line}: the file is opened for writing (emptied) before the same expression reads it"
                   for line in emptied_before_read(src, f)]
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
    print(f"py-check: PASS {len(files)} files, no undefined names, no file emptied before it is read{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
