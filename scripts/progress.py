#!/usr/bin/env python3
"""Progress of the running work and of the to-do list, for the Claude Code status line (CLAUDE.md rule 11).

usage: progress.py [--oneline]

Running work is found with ps in this repo and in every worktree of it (git worktree list):
  make regress / regress-picorv32   targets done / targets in that worktree's `regress.py --list`
                                    (runs/regress or runs/regress_picorv32 gets <target>.log when a
                                    target starts; the current one is the last listed target with a log)
  LibreLane (harden-*)              finished steps / finished steps of the newest complete run with the
                                    same run tag in any worktree (a step finished when its directory has
                                    state_out.json: a stopped retry attempt does not count, the same rule
                                    as signoff/scripts/review_criteria.py); no reference run: step count only
  any other make <target>           "running" (no denominator, so no percentage)
To-do list: runs/todo.md of the main checkout (git-ignored: ticking an item must not dirty the working
tree that harden and regress require clean); `- [ ]` open, `- [~]` in progress, `- [x]` done.
The percentages are estimates for people; nothing in signoff reads them.
--oneline prints one line for the status line (.claude/statusline-progress), cached 10 s; it prints
nothing on any error so the status line never breaks. Without it: one line per item.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGRESS_OUT = {"hazard3": "regress", "picorv32": "regress_picorv32"}
CACHE_S = 10


def run(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout


def worktrees():
    trees = [line[9:] for line in run("git", "-C", ROOT, "worktree", "list", "--porcelain").splitlines()
             if line.startswith("worktree ")]
    return [os.path.realpath(t) for t in trees] or [ROOT]


def tree_of(path, trees):
    path = os.path.realpath(path)
    hits = [t for t in trees if path == t or path.startswith(t + os.sep)]
    return max(hits, key=len) if hits else None


def processes():
    procs = {}
    for line in run("ps", "-axo", "pid=,ppid=,command=").splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            procs[int(parts[0])] = (int(parts[1]), parts[2])
    return procs


def cwds(pids):
    if not pids:
        return {}
    out, pid = {}, None
    for line in run("lsof", "-a", "-d", "cwd", "-Fpn", "-p", ",".join(map(str, pids))).splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            out[pid] = line[1:]
    return out


def has_ancestor(pid, procs, pred):
    seen = set()
    while pid in procs and pid not in seen:
        seen.add(pid)
        pid = procs[pid][0]
        if pid in procs and pred(procs[pid][1]):
            return True
    return False


def arg(cmd, flag):
    m = re.search(rf"{flag}[ =]'?([^ ']+)", cmd)
    return m.group(1) if m else None


def finished_steps(run_dir):
    try:
        names = os.listdir(run_dir)
    except OSError:
        return None
    return sum(1 for n in names if re.match(r"\d+-", n) and os.path.isfile(os.path.join(run_dir, n, "state_out.json")))


def step_text(run_dir, tag, trees):
    done = finished_steps(run_dir) or 0
    refs = [os.path.join(t, "runs", tag) for t in trees]
    refs = [r for r in refs if os.path.realpath(r) != os.path.realpath(run_dir) and os.path.isdir(os.path.join(r, "final"))]
    total = finished_steps(max(refs, key=os.path.getmtime)) if refs else None
    if total:
        return f"step {done}/{total} {min(99, 100 * done // total)}%"
    return f"step {done}"


def pct(done, total):
    return f"{done}/{total} {100 * done // total}%" if total else f"{done}"


def jobs():
    trees = worktrees()
    procs = processes()
    is_regress = lambda c: "regress.py" in c
    is_make = lambda c: re.match(r"(\S*/)?make(\s|$)", c) is not None
    regress = [p for p, (_, c) in procs.items() if is_regress(c) and "python" in c.lower()]
    librelane = [p for p, (_, c) in procs.items() if "-m librelane" in c and "--run-tag" in c]
    # top-level make only: EQY and others run their own make (-f strategies.mk, -C work) underneath
    makes = [p for p, (_, c) in procs.items() if is_make(c) and not has_ancestor(p, procs, is_make)]
    where = cwds(regress + makes)
    by_tree = {}
    for p in librelane:
        cmd = procs[p][1]
        tree = tree_of(arg(cmd, "--design-dir") or "", trees)
        if tree:
            tag = arg(cmd, "--run-tag")
            by_tree.setdefault(tree, {}).setdefault("ll", []).append(
                (tag, step_text(os.path.join(arg(cmd, "--design-dir"), "runs", tag), tag, trees)))
    for p in regress:
        tree = tree_of(where.get(p, ""), trees)
        if not tree:
            continue
        cpu = arg(procs[p][1], "--cpu") or "hazard3"
        targets = run(sys.executable, os.path.join(tree, "scripts", "regress.py"), "--list", "--cpu", cpu).split()
        out = os.path.join(tree, "runs", REGRESS_OUT.get(cpu, "regress"))
        started = [i for i, t in enumerate(targets) if os.path.isfile(os.path.join(out, f"{t}.log"))]
        current = targets[started[-1]] if started else None
        by_tree.setdefault(tree, {})["regress"] = (cpu, started[-1] if started else 0, len(targets), current)
    for p in makes:
        tree = tree_of(where.get(p, ""), trees)
        words = procs[p][1].split()[1:]
        target = next((w for w in words if not w.startswith("-") and "=" not in w), None)
        if not tree or not target or target.startswith("regress") or has_ancestor(p, procs, is_regress):
            continue
        targets = by_tree.setdefault(tree, {}).setdefault("make", [])
        if target not in targets:
            targets.append(target)
    items = []
    for tree in trees:
        if tree not in by_tree:
            continue
        info, name = by_tree[tree], os.path.basename(tree)
        name = "main" if tree == os.path.realpath(ROOT) else name.replace("arvinsa-rtl-gds-", "")
        ll = list(info.get("ll", []))
        if "regress" in info:
            cpu, done, total, current = info["regress"]
            text = f"{name} regress{'' if cpu == 'hazard3' else '-' + cpu} {pct(done, total)}"
            if current:
                text += f" › {current}" + (f" {ll.pop(0)[1]}" if ll and current.startswith("harden") else "")
            items.append(text)
        for target in info.get("make", []):
            text = f"{name} {target} "
            text += ll.pop(0)[1] if ll and target.startswith("harden") else "執行中"
            items.append(text)
        items += [f"{name} {tag} {steps}" for tag, steps in ll]
    return items


def todo():
    path = os.path.join(ROOT, "runs", "todo.md")
    if not os.path.isfile(path):
        return None
    marks = re.findall(r"^\s*[-*] \[([ ~xX])\]", open(path, encoding="utf-8").read(), re.M)
    if not marks:
        return None
    left = sum(1 for m in marks if m in " ~")
    doing = sum(1 for m in marks if m == "~")
    return f"待辦 剩 {left}（進行中 {doing}）／共 {len(marks)}"


def oneline():
    cache = os.path.join(tempfile.gettempdir(), f"arvinsa-progress-{hashlib.sha1(ROOT.encode()).hexdigest()[:12]}.txt")
    try:
        if time.time() - os.path.getmtime(cache) < CACHE_S:
            return open(cache, encoding="utf-8").read()
    except OSError:
        pass
    line = " │ ".join(x for x in [todo()] + jobs() if x)
    tmp = f"{cache}.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(line)
    os.replace(tmp, cache)
    return line


def main():
    if "--oneline" in sys.argv[1:]:
        try:
            print(oneline())
        except Exception:
            pass
        return 0
    print(todo() or "待辦: runs/todo.md 不存在或沒有勾選項")
    for item in jobs() or ["沒有執行中的工作"]:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
