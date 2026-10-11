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
  a Python script of the tree run     "running", labelled with the script name (for example characterize.py
  directly (not under make)           or power.py started without make; 2026-10-09 the status line showed
                                      nothing during a 6-hour characterization started that way)
  a Python script in this repo's      the same, under "scratchpad", labelled <folder>/<script> (a trial that
  Claude Code scratchpad              an agent runs outside the tree; 2026-10-11 the status line showed
  (/tmp/claude-<uid>/<project>/       nothing during the 3-hour extracted-netlist trial of Phase 6)
  <session>/scratchpad/)
To-do list (todo()): runs/todo.md of the main checkout (git-ignored: ticking an item must not dirty the working
tree that harden and regress require clean); `- [ ]` open, `- [~]` in progress, `- [x]` done.
The percentages are estimates for people; nothing in signoff reads them.
--oneline prints one line for the status line (.claude/statusline-progress), cached 10 s; it prints
nothing on any error so the status line never breaks. --json: the same data for the progress-pane mod
(todo items, and per job: done/total, current step or target, elapsed, an estimate of the time left from
the newest complete run of the same tag or regression summary in any worktree, alerts such as a GRT-0229
retry). Without either: one line per item.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REGRESS_OUT = {"hazard3": "regress", "picorv32": "regress_picorv32"}
CACHE_S = 10
# Claude Code names a project's temp directory after its path with every other character turned into "-"
SCRATCH = re.compile(rf"/claude-{os.getuid()}/{re.escape(re.sub(r'[^A-Za-z0-9-]', '-', ROOT))}/[^/]+/scratchpad/")


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
    """{pid: (ppid, elapsed seconds, command)}"""
    procs = {}
    for line in run("ps", "-axo", "pid=,ppid=,etime=,command=").splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit() and parts[1].isdigit():
            procs[int(parts[0])] = (int(parts[1]), etime(parts[2]), parts[3])
    return procs


def etime(text):
    """ps etime [[dd-]hh:]mm:ss -> seconds."""
    days, _, rest = text.rpartition("-")
    nums = [int(x) for x in rest.split(":")]
    while len(nums) < 3:
        nums.insert(0, 0)
    return (int(days) if days else 0) * 86400 + nums[0] * 3600 + nums[1] * 60 + nums[2]


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
        if pid in procs and pred(procs[pid][2]):
            return True
    return False


def arg(cmd, flag):
    m = re.search(rf"{flag}[ =]'?([^ ']+)", cmd)
    return m.group(1) if m else None


def step_times(run_dir):
    """(start, [finish time of each finished step, in step order]) of a LibreLane run directory; a step
    finished when its directory has state_out.json (a stopped retry attempt does not count)."""
    try:
        names = sorted((n for n in os.listdir(run_dir) if re.match(r"\d+-", n)), key=lambda n: int(n.split("-")[0]))
    except OSError:
        return None, []
    if not names:
        return None, []
    first = os.path.join(run_dir, names[0])
    start = min(os.path.getmtime(os.path.join(first, f)) for f in os.listdir(first)) if os.listdir(first) else os.path.getmtime(first)
    done = [os.path.getmtime(os.path.join(run_dir, n, "state_out.json")) for n in names
            if os.path.isfile(os.path.join(run_dir, n, "state_out.json"))]
    return start, sorted(done)


def harden_info(run_dir, tag, trees, now):
    """Progress of a running LibreLane run: done/total steps, elapsed, an estimate of the time left from
    the newest complete run of the same tag in any worktree (its step finish times), alerts."""
    start, done_t = step_times(run_dir)
    names = [n for n in os.listdir(run_dir) if re.match(r"\d+-", n)] if os.path.isdir(run_dir) else []
    current = max(names, key=lambda n: int(n.split("-")[0]), default="")
    info = {"kind": "harden", "label": tag, "done": len(done_t), "total": None, "current": re.sub(r"^\d+-", "", current),
            "elapsed_s": int(now - start) if start else None, "eta_s": None, "alerts": []}
    refs = [os.path.join(t, "runs", tag) for t in trees]
    refs = [r for r in refs if os.path.realpath(r) != os.path.realpath(run_dir) and os.path.isdir(os.path.join(r, "final"))]
    if refs:
        r_start, r_done = step_times(max(refs, key=os.path.getmtime))
        if r_done:
            info["total"] = len(r_done)
            k = min(len(done_t), len(r_done))
            info["eta_s"] = max(0, int(r_done[-1] - (r_done[k - 1] if k else r_start)))
    retries = run_dir.rstrip("/") + "_signoff"
    rt = os.path.join(retries, "retries.txt")
    if start and os.path.isfile(rt) and os.path.getmtime(rt) >= start:
        n = len([ln for ln in open(rt, errors="replace") if ln.strip()])
        info["alerts"].append(f"GRT-0229 重試 {n} 次")
    return info


def regress_reference(trees, out_name, here):
    """{target: minutes} from the newest complete regression summary of the same CPU in another worktree."""
    best = None
    for t in trees:
        p = os.path.join(t, "runs", out_name, "summary.md")
        if t != here and os.path.isfile(p) and "targets PASS" in open(p, errors="replace").read():
            if best is None or os.path.getmtime(p) > os.path.getmtime(best):
                best = p
    rows = re.findall(r"^\| \d+ \| `([^`]+)` \| PASS \| ([\d.]+) \|", open(best).read(), re.M) if best else []
    return {t: float(m) for t, m in rows}


def jobs():
    trees = worktrees()
    procs = processes()
    now = time.time()
    is_regress = lambda c: "regress.py" in c
    is_make = lambda c: re.match(r"(\S*/)?make(\s|$)", c) is not None
    regress = [p for p, (_, _, c) in procs.items() if is_regress(c) and "python" in c.lower()]
    librelane = [p for p, (_, _, c) in procs.items() if "-m librelane" in c and "--run-tag" in c]
    # top-level make only: EQY and others run their own make (-f strategies.mk, -C work) underneath
    makes = [p for p, (_, _, c) in procs.items() if is_make(c) and not has_ancestor(p, procs, is_make)]
    # python <tree>/.../x.py (or a relative x.py run from inside a tree), not started by make or regress
    is_py = lambda c: re.match(r"(\S*/)?[Pp]ython[\d.]*\s", c) is not None or "/Python.app/" in c
    scripts = [p for p, (_, _, c) in procs.items() if is_py(c) and re.search(r"\S+\.py\b", c)
               and not is_regress(c) and not has_ancestor(p, procs, is_make) and not has_ancestor(p, procs, is_regress)
               and not has_ancestor(p, procs, is_py) and os.path.basename(__file__) not in c]
    where = cwds(regress + makes + scripts)
    by_tree = {}
    for p in librelane:
        cmd = procs[p][2]
        tree = tree_of(arg(cmd, "--design-dir") or "", trees)
        if tree:
            tag = arg(cmd, "--run-tag")
            by_tree.setdefault(tree, {}).setdefault("ll", []).append(
                harden_info(os.path.join(arg(cmd, "--design-dir"), "runs", tag), tag, trees, now))
    for p in regress:
        tree = tree_of(where.get(p, ""), trees)
        if not tree:
            continue
        cpu = arg(procs[p][2], "--cpu") or "hazard3"
        targets = run(sys.executable, os.path.join(tree, "scripts", "regress.py"), "--list", "--cpu", cpu).split()
        out_name = REGRESS_OUT.get(cpu, "regress")
        out = os.path.join(tree, "runs", out_name)
        started = [i for i, t in enumerate(targets) if os.path.isfile(os.path.join(out, f"{t}.log"))]
        i = started[-1] if started else 0
        ref = regress_reference(trees, out_name, tree)
        current = targets[i] if started else None
        cur_t = os.path.getmtime(os.path.join(out, f"{current}.log")) if current else now
        eta = rest = None
        if ref and all(t in ref for t in targets):
            rest = int(sum(ref[t] for t in targets[i + 1:]) * 60)
            eta = rest + int(max(0.0, ref[current] * 60 - (now - cur_t)) if current else 0)
        by_tree.setdefault(tree, {})["regress"] = {
            "kind": "regress", "label": "regress" + ("" if cpu == "hazard3" else "-" + cpu), "done": i,
            "total": len(targets), "current": current, "elapsed_s": procs[p][1], "eta_s": eta, "rest_s": rest, "alerts": []}
    for p in makes:
        tree = tree_of(where.get(p, ""), trees)
        words = procs[p][2].split()[1:]
        target = next((w for w in words if not w.startswith("-") and "=" not in w), None)
        if not tree or not target or target.startswith("regress") or has_ancestor(p, procs, is_regress):
            continue
        made = by_tree.setdefault(tree, {}).setdefault("make", [])
        if target not in [m["label"] for m in made]:
            made.append({"kind": "make", "label": target, "done": None, "total": None, "current": None,
                         "elapsed_s": procs[p][1], "eta_s": None, "alerts": []})
    for p in scripts:
        cmd = procs[p][2]
        script = re.search(r"(\S+\.py)\b", cmd).group(1)
        path = script if os.path.isabs(script) else os.path.join(where.get(p, ""), script)
        real = os.path.realpath(path)
        tree, label = tree_of(real, trees), os.path.basename(script)
        m = SCRATCH.search(real)
        if not tree and m:
            tree, label = "scratchpad", real[m.end():]
        if not tree:
            continue
        made = by_tree.setdefault(tree, {}).setdefault("make", [])
        if label not in [m["label"] for m in made]:
            made.append({"kind": "make", "label": label, "done": None, "total": None, "current": None,
                         "elapsed_s": procs[p][1], "eta_s": None, "alerts": []})
    items = []
    for tree in trees + ["scratchpad"]:
        if tree not in by_tree:
            continue
        info, name = by_tree[tree], os.path.basename(tree)
        name = "main" if tree == os.path.realpath(ROOT) else name.replace("arvinsa-rtl-gds-", "")
        ll = list(info.get("ll", []))
        if "regress" in info:
            job = dict(info["regress"], tree=name)
            if ll and (job["current"] or "").startswith("harden"):
                job["sub"] = ll.pop(0)
                if job["eta_s"] is not None and job["sub"]["eta_s"] is not None:
                    # the harden's own estimate replaces the reference minutes of the current target
                    job["eta_s"] = job.pop("rest_s") + job["sub"]["eta_s"]
                job["alerts"] += job["sub"]["alerts"]
            job.pop("rest_s", None)
            items.append(job)
        for job in info.get("make", []):
            job = dict(job, tree=name)
            if ll and job["label"].startswith("harden"):
                sub = ll.pop(0)
                job.update(done=sub["done"], total=sub["total"], current=sub["current"], eta_s=sub["eta_s"],
                           alerts=sub["alerts"])
            items.append(job)
        items += [dict(j, tree=name) for j in ll]
    return items


def minutes(sec):
    if sec is None:
        return None
    return f"{sec // 3600} 小時 {sec % 3600 // 60} 分" if sec >= 3600 else f"{max(1, sec // 60)} 分"


def pct(done, total):
    return min(99, 100 * done // total) if total else None


def job_text(j, short=False):
    def part(x, unit):
        if x.get("total"):
            return f"{unit} {x['done']}/{x['total']} {pct(x['done'], x['total'])}%"
        return f"{unit} {x['done']}" if x.get("done") is not None else "執行中"
    unit = "step" if j["kind"] == "harden" or (j["kind"] == "make" and j.get("total")) else ""
    text = f"{j['tree']} {j['label']} " + (part(j, unit).strip() if j["kind"] != "make" or j.get("total") else "執行中")
    if j.get("sub"):
        text += f" › {j['current']} {part(j['sub'], 'step')}"
    elif j["kind"] == "regress" and j.get("current"):
        text += f" › {j['current']}"
    eta = minutes(j.get("eta_s"))
    if eta:
        text += f" 剩約 {eta}"
    if not short and j.get("elapsed_s") is not None:
        text += f"（已跑 {minutes(j['elapsed_s'])}）"
    if j.get("alerts"):
        text += " ⚠ " + "、".join(j["alerts"])
    return text


def todo():
    """{left, doing, done, total, doing_items, doing_detail, open_items} from runs/todo.md, or None. The fields
    are those of the shared provider ~/.claude/skills/progress-pane/bin/todo_progress.py, which the progress
    pane reads. doing_detail: one {item, section, done, total} per in-progress item, counting its indented
    sub-items; an item without sub-items counts the sub-items of its parent item (5d counts the items under
    5), and a top-level one the boxes under its `##`/`###` heading. Boxes inside ``` blocks do not count."""
    path = os.path.join(ROOT, "runs", "todo.md")
    if not os.path.isfile(path):
        return None
    boxes, section, in_code = [], "", False   # boxes: (section, indent, mark, text)
    for line in open(path, encoding="utf-8"):
        if re.match(r"\s*```", line):
            in_code = not in_code
            continue
        h = None if in_code else re.match(r"#{2,3}\s+(.*\S)\s*$", line)
        m = None if in_code else re.match(r"(\s*)[-*]\s+\[([ ~xX])\]\s+(.*\S)\s*$", line)
        if h:
            section = h.group(1)
        elif m:
            boxes.append((section, len(m.group(1).expandtabs(4)), m.group(2), m.group(3)))
    if not boxes:
        return None

    def under(i):   # the boxes nested under box i
        out = []
        for b in boxes[i + 1:]:
            if b[0] != boxes[i][0] or b[1] <= boxes[i][1]:
                break
            out.append(b)
        return out

    detail = []
    for i, (sec, ind, mark, text) in enumerate(boxes):
        if mark != "~":
            continue
        group, name = under(i), "子項目"
        if not group:
            parent = next((j for j in range(i - 1, -1, -1) if boxes[j][0] == sec and boxes[j][1] < ind), None)
            group, name = (under(parent), boxes[parent][3]) if parent is not None else ([b for b in boxes if b[0] == sec], sec)
        detail.append({"item": text, "section": name, "done": sum(1 for b in group if b[2] in "xX"), "total": len(group)})
    return {"left": sum(1 for b in boxes if b[2] in " ~"), "doing": sum(1 for b in boxes if b[2] == "~"),
            "done": sum(1 for b in boxes if b[2] in "xX"), "total": len(boxes),
            "doing_items": [b[3] for b in boxes if b[2] == "~"], "doing_detail": detail,
            "open_items": [b[3] for b in boxes if b[2] == " "]}


def todo_text(t):
    return f"待辦 {t['done']}/{t['total']}（{100 * t['done'] // t['total']}%）·剩 {t['left']}，進行中 {t['doing']}" if t else None


def oneline():
    cache = os.path.join(tempfile.gettempdir(), f"arvinsa-progress-{hashlib.sha1(ROOT.encode()).hexdigest()[:12]}.txt")
    try:
        if time.time() - os.path.getmtime(cache) < CACHE_S:
            return open(cache, encoding="utf-8").read()
    except OSError:
        pass
    line = " │ ".join(x for x in [todo_text(todo())] + [job_text(j, short=True) for j in jobs()] if x)
    tmp = f"{cache}.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(line)
    os.replace(tmp, cache)
    return line


def main():
    args = sys.argv[1:]
    if "--oneline" in args:
        try:
            print(oneline())
        except Exception:
            pass
        return 0
    if "--json" in args:   # for the progress-pane mod (~/.claude/skills/progress-pane)
        try:
            print(json.dumps({"project": os.path.basename(ROOT), "todo": todo(), "jobs": jobs()}, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 - the pane shows the error instead of breaking
            print(json.dumps({"project": os.path.basename(ROOT), "error": repr(e)}))
        return 0
    t = todo()
    print(todo_text(t) or "待辦: runs/todo.md 不存在或沒有勾選項")
    for d in (t or {}).get("doing_detail", []):
        print(f"  進行中：{d['item']}  〔{d['section'] or '（無標題）'} {d['done']}/{d['total']}〕")
    for j in jobs() or []:
        print(job_text(j))
    return 0


if __name__ == "__main__":
    sys.exit(main())
