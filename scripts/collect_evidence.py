#!/usr/bin/env python3
"""make collect-evidence: copy the evidence reports that the repo's documents cite out of runs/ into docs/evidence/.

usage: collect_evidence.py [--out docs/evidence] [--extra DIR [--skip NAME ...]] [--copy]

Why: runs/ is not under version control (.gitignore), and the closing regressions run in worktrees
that are removed after the phase (skill flow-regression-reproducibility rule 16). ADRs, exit reviews,
golden READMEs and skills cite files there (console logs, criteria reviews, signoff verdicts), so the
citations break when runs/ and the worktrees are cleaned. Before the clean-up the reports are copied
into the repo; large artifacts (GDS, DEF, netlists, whole LibreLane run directories, SPICE output)
are not, since a commit and its regression regenerate them. User 2026-10-15: "我們跑這些主要是出技術
報告跟建立流程，相關重要資料與數據報告給技術流程都收錄後，就都不需要了", "主要是重要的佐證報告才收".

What is copied (each text file <= TEXT_CAP, checked for NUL bytes):
  1. every runs/ file a tracked document names (not layout or netlist files); images <= IMAGE_CAP
  2. every runs/ directory a document names: all its text files if it has <= SMALL_DIR_FILES files
     and <= SMALL_DIR bytes (an experiment: its scripts and logs), else only its top-level reports (.md .txt .console .csv .toml, summary.*)
  3. in the repo and every worktree of it (`git worktree list`): top-level reports in runs/, the verdict
     files of each runs/*_signoff/ (SIGNOFF), the summary of each regression, negative test and simulation
  4. --extra DIR: top-level reports of each sub-directory of DIR except --skip names (the precheck
     work directory, whose pdks/ and example project are the environment, not results)
A file lands at <out>/<checkout directory name>/<path in that checkout>, so `runs/x` cited in a
document is `<out>/<repo name>/runs/x`. <out>/references.md lists every cited path with what was kept.
Text files are copied with the home directory written as ~ and temp paths as <claude-session-tmp>, <claude-tmp>,
<tmp> (the repo is public; no tracked file has the user's home or temp path, the push guard rejects them). Without --copy it only prints what it would copy. It refuses to run when runs/ is gone (after the
clean-up every citation would be listed as missing).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

TEXT_CAP = 512 * 1024
IMAGE_CAP = 2 * 1024 * 1024
SMALL_DIR = 2 * 1024 * 1024
SMALL_DIR_FILES = 20
REPORT_EXT = {".md", ".txt", ".console", ".csv", ".toml"}
IMAGE_EXT = {".png", ".svg", ".jpg"}
LAYOUT_EXT = {".gds", ".def", ".odb", ".v", ".vcd", ".fst", ".spice", ".sp", ".raw", ".tsv", ".lib", ".lef"}
SIGNOFF = {"result.txt", "signoff.txt", "criteria_review.md", "criteria_review.txt", "soc_checks.txt", "ir_worst.txt",
           "provenance.txt", "provenance_end.txt", "inputs_resolved.txt", "disconnected.txt",
           "cpu_params_resolved.txt", "retries.txt", "sram_drc_alone.txt"}
REF_RE = r"(\.\./[A-Za-z0-9_.-]+/)?runs/[A-Za-z0-9_./*<>{}-]+"
# session and system temp paths carry the user name (macOS: claude-<uid>/-Users-<name>-.../<session>/scratchpad under
# the private temp directory); [t] and [v] keep the literal path out of this public file (the push guard looks for it)
LOCAL_TMP = [(rb"/private/[t]mp/claude-\d+/[^/\s]+/[0-9a-f-]{36}", b"<claude-session-tmp>"),
             (rb"/private/[t]mp/claude-\d+", b"<claude-tmp>"),
             (rb"/private/[v]ar/folders/[^\s\"']+", b"<tmp>"),
             (rb"/private/[t]mp", b"<tmp>")]


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True).stdout


def is_text(path):
    with open(path, "rb") as f:
        return b"\0" not in f.read(4096)


def dir_size(d):
    files = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs]
    return sum(os.path.getsize(f) for f in files if not os.path.islink(f)), len(files)


class Picker:
    def __init__(self, checkouts):
        self.checkouts = checkouts  # absolute path -> name under <out>
        self.files = {}

    def dest(self, path):
        for root, name in self.checkouts.items():
            if path.startswith(root + os.sep):
                return os.path.join(name, os.path.relpath(path, root))
        return None

    def add(self, path, cap=TEXT_CAP):
        path = os.path.normpath(path)
        if "sim_build" in path.split(os.sep):  # simulator build files, not evidence (.gitignore)
            return
        if not os.path.isfile(path) or os.path.islink(path) or os.path.getsize(path) > cap:
            return
        image = os.path.splitext(path)[1].lower() in IMAGE_EXT
        if (image or is_text(path)) and self.dest(path):
            self.files[path] = self.dest(path)

    def top_reports(self, d):
        for e in os.listdir(d):
            if os.path.splitext(e)[1] in REPORT_EXT or e.startswith("summary."):
                self.add(os.path.join(d, e))

    def all_text(self, d):
        for r, _, fs in os.walk(d):
            for f in fs:
                if os.path.splitext(f)[1].lower() not in LAYOUT_EXT:
                    self.add(os.path.join(r, f))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="docs/evidence")
    ap.add_argument("--extra", action="append", default=[])
    ap.add_argument("--skip", action="append", default=[])
    ap.add_argument("--copy", action="store_true")
    a = ap.parse_args()
    repo = git(".", "rev-parse", "--show-toplevel").strip()
    if not os.path.isdir(os.path.join(repo, "runs")):
        sys.exit("collect-evidence: FAIL no runs/ in the repo; run it before the clean-up")
    out = os.path.join(repo, a.out)
    checkouts = {}
    for line in git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            p = os.path.realpath(line.split(" ", 1)[1])
            checkouts[p] = os.path.basename(p)
    extras = [os.path.realpath(e) for e in a.extra if os.path.isdir(e)]
    for e in extras:
        checkouts[e] = os.path.basename(e)
    pk = Picker(checkouts)

    # 1, 2: what the tracked documents cite (this directory's own copies excluded)
    grep = subprocess.run(["git", "-C", repo, "grep", "-ohE", REF_RE, "--", "*.md", "*.toml", "*.txt", "*.py",
                           "*.sh", "Makefile", ":!" + a.out], capture_output=True, text=True).stdout
    refs = sorted({r.rstrip(".,)`") for r in grep.split()})
    status = {}
    for r in refs:
        if re.search(r"[<{*]|\.\.\.", r):
            continue
        p = os.path.normpath(os.path.join(repo, r))
        if os.path.isfile(p):
            ext = os.path.splitext(p)[1].lower()
            if ext in IMAGE_EXT:
                pk.add(p, IMAGE_CAP)
            elif ext not in LAYOUT_EXT:
                pk.add(p)
            status[r] = ("file", p, os.path.getsize(p))
        elif os.path.isdir(p) and p != os.path.join(repo, "runs"):
            size, count = dir_size(p)
            pk.all_text(p) if size <= SMALL_DIR and count <= SMALL_DIR_FILES else pk.top_reports(p)
            status[r] = ("dir", p, size)
        elif not os.path.exists(p):
            status[r] = ("missing", p, 0)
    # 3: every checkout's verdicts and summaries
    for root in checkouts:
        runs = os.path.join(root, "runs")
        if root in extras or not os.path.isdir(runs):
            continue
        for e in os.listdir(runs):
            q = os.path.join(runs, e)
            if os.path.isfile(q) and os.path.splitext(e)[1] in REPORT_EXT:
                pk.add(q)
            elif os.path.isdir(q) and e.endswith("_signoff"):
                for f in SIGNOFF:
                    pk.add(os.path.join(q, f))
            elif os.path.isdir(q) and e.startswith(("regress", "neg", "sim_", "core_")):
                for f in ("summary.md", "summary.txt"):
                    pk.add(os.path.join(q, f))
    # 4: extra work directories
    for e in extras:
        for s in sorted(os.listdir(e)):
            q = os.path.join(e, s)
            if s in a.skip:
                continue
            if os.path.isdir(q):
                pk.top_reports(q)
            else:
                pk.add(q)

    total = sum(os.path.getsize(p) for p in pk.files)
    print(f"collect-evidence: {len(pk.files)} files, {total / 1e6:.1f} MB from {len(checkouts)} checkouts "
          f"-> {a.out}{'' if a.copy else ' (dry run; --copy to write)'}")
    if not a.copy:
        return
    home = os.path.expanduser("~").encode()
    for src, rel in pk.files.items():
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.splitext(src)[1].lower() in IMAGE_EXT:
            shutil.copy2(src, dst)
            continue
        with open(src, "rb") as f:
            data = f.read()
        data = data.replace(home + b"/", b"~/").replace(home, b"~")
        for rx, to in LOCAL_TMP:
            data = re.sub(rx, to, data)
        with open(dst, "wb") as f:  # the repo is public: no home directory or temp path (user name) in tracked files
            f.write(data)
        shutil.copystat(src, dst)
    kept = set(pk.files)
    rows = []
    for r, (kind, p, size) in status.items():
        if kind == "missing":
            st = "清理前就已不存在"
        elif kind == "file":
            st = "已收錄" if p in kept else f"未收錄（{size / 1e6:.0f} MB）" if size > 1e6 else "未收錄"
        else:
            n = sum(1 for k in kept if k.startswith(p + os.sep))
            st = f"目錄：收錄其中 {n} 個檔" if n else f"目錄：未收錄（{size / 1e6:.0f} MB 的 run 中間產物）"
        cite = subprocess.run(["git", "-C", repo, "grep", "-nF", r, "--", ".", ":!" + a.out],
                              capture_output=True, text=True).stdout.splitlines()
        where = sorted({":".join(c.split(":")[:2]) for c in cite})
        rows.append(f"| `{r}` | {st} | {', '.join(where[:2])}{f' 等 {len(where)} 處' if len(where) > 2 else ''} |")
    with open(os.path.join(out, "references.md"), "w") as f:
        f.write("# 文件引用的 runs/ 路徑與收錄狀態\n\n"
                "由 `scripts/collect_evidence.py` 在清理前產生：列出 repo 文件（不含本目錄）引用到的每個 `runs/` 或 "
                "worktree 路徑。`runs/x` 收錄後在本目錄的 `<repo 目錄名>/runs/x`，`../<worktree>/runs/x` 在 "
                "`<worktree>/runs/x`。通用寫法（例如 `runs/<tag>_signoff`）不列。\n\n"
                "| 引用的路徑 | 狀態 | 引用處（前兩處） |\n|---|---|---|\n" + "\n".join(rows) + "\n")
    print(f"collect-evidence: PASS {len(rows)} cited paths listed in {a.out}/references.md")


if __name__ == "__main__":
    main()
