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

Second check: a file opened for writing (mode with w or x, or a mode that is not a constant) while
the same path is opened again. `open(f, "w").write(... open(f).read() ...)` evaluates `open(f, "w")`,
which empties the file, before the argument, so the read gets "" (neg_pnr.py P17, Phase 3.5: the
injection found nothing to edit, at the 19th target, about 80 minutes into `make regress`). Reported:
  - one simple statement that opens a path for writing and opens the same path again, in any order
    (`print(open(f).read(), file=open(f, "w"))` happens to read first; write it as two statements);
  - `with` whose items open a path for writing and the same path again, or whose body opens it;
  - `h = open(p, "w")` followed, in the same block, by a statement that opens p before one that
    calls `h.close()`.
open is `open(...)` or `io.open`, `codecs.open`, `builtins.open`, with the path as first argument or
`file=`. "The same path" means the same expression text: an alias (`g = f`), a path built another
way, or a read inside a helper function is not seen (Phase 3.5 review listed these forms).

Before scanning, it checks itself on snippets with an undefined function, with each reported form of
the emptied file and with forms that must not be reported (another path; read after close), and
FAILs if any is judged wrong (a check that cannot report anything must not PASS).
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
    """(path expression dump, writes?) when n opens a file (see the module docstring), else None."""
    if not isinstance(n, ast.Call):
        return None
    f = n.func
    if not (isinstance(f, ast.Name) and f.id == "open" or isinstance(f, ast.Attribute) and f.attr == "open"
            and isinstance(f.value, ast.Name) and f.value.id in ("io", "codecs", "builtins")):
        return None
    kw = {k.arg: k.value for k in n.keywords}
    path = n.args[0] if n.args else kw.get("file")
    if path is None:
        return None
    mode = n.args[1] if len(n.args) > 1 else kw.get("mode")
    if mode is None:
        writes = False
    elif isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        writes = bool(set(mode.value) & set("wx"))
    else:
        writes = True
    return ast.dump(path), writes


def opens(node):
    return [o for o in map(open_call, ast.walk(node)) if o]


def emptied_before_read(src, path):
    """[line] of statements that open a path for writing while it is opened again (module docstring)."""
    tree = ast.parse(src, path)
    lines = set()
    compound = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef,
                ast.AsyncFunctionDef, ast.ClassDef) + ((ast.Match,) if hasattr(ast, "Match") else ())
    for st in ast.walk(tree):
        if isinstance(st, ast.stmt) and not isinstance(st, compound):
            os_ = opens(st)
            if any(w and sum(p2 == p for p2, _ in os_) > 1 for p, w in os_):
                lines.add(st.lineno)
        if isinstance(st, (ast.With, ast.AsyncWith)):
            items = [o for it in st.items for o in opens(it.context_expr)]
            body = [o for b in st.body for o in opens(b)]
            for p, w in items:
                if w and (sum(p2 == p for p2, _ in items) > 1 or any(p2 == p for p2, _ in body)):
                    lines.add(st.lineno)
        for field in ("body", "orelse", "finalbody"):
            block = getattr(st, field, None)
            if not isinstance(block, list):
                continue
            pending = {}                       # handle name -> path opened for writing
            for b in block:
                for name in [n for n in pending if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                                                      and c.func.attr == "close" and isinstance(c.func.value, ast.Name)
                                                      and c.func.value.id == n for c in ast.walk(b))]:
                    del pending[name]
                if any(p in pending.values() for p, _ in opens(b)):
                    lines.add(b.lineno)
                if isinstance(b, ast.Assign) and len(b.targets) == 1 and isinstance(b.targets[0], ast.Name):
                    o = open_call(b.value)
                    if o and o[1]:
                        pending[b.targets[0].id] = o[0]
    return sorted(lines)


def main():
    bad_snippet = "def new_name():\n    return 1\n\ndef caller():\n    return old_name()\n"
    if undefined(bad_snippet, "<self-test>") != [(5, "old_name")]:
        print("py-check: FAIL self-test: the call to an undefined function in the test snippet was not reported")
        return 1
    reported = {
        "basic": 'open(f, "w").write(open(f).read().upper())',
        "file= keyword": 'open(file=f, mode="w").write(open(f).read())',
        "io.open": 'io.open(f, "w").write(open(f).read())',
        "mode in a variable": 'open(f, m).write(open(f).read())',
        "copyfileobj": 'shutil.copyfileobj(open(f), open(f, "w"))',
        "with body": 'with open(f, "w") as o:\n    o.write(open(f).read())',
        "with items": 'with open(f) as i, open(f, "w") as o:\n    o.write(i.read())',
        "two lines": 'o = open(f, "w")\no.write(open(f).read())',
    }
    clean = {
        "another path": 'open(f + "2", "w").write(open(f).read())',
        "read after close": 'o = open(f, "w")\no.write("x")\no.close()\ny = open(f).read()',
        "read only": 'x = open(f).read() + open(f).read()',
    }
    wrong = [k for k, v in reported.items() if not emptied_before_read(v + "\n", "<self-test>")] + \
        [k for k, v in clean.items() if emptied_before_read(v + "\n", "<self-test>")]
    if wrong:
        print(f"py-check: FAIL self-test: the emptied-file check judged these snippets wrong: {', '.join(wrong)}")
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
        errors += [f"{f}:{line}: a path opened for writing (which empties it) is opened again here; read it first, in its own statement"
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
