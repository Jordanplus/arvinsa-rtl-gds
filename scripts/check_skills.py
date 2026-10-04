#!/usr/bin/env python3
"""make skill-check: every Claude Code skill has a valid header and is listed in README.md.

usage: check_skills.py

Why: Claude picks a skill by the `description` in the YAML header of its SKILL.md. A plain YAML
value must not contain ': ' or ' #'; the phase-exit-review header had ': ' from Phase 4 on and
was not valid YAML. README.md's skill section is the human index and has to follow every skill
change (user, 2026-10-04; CLAUDE.md rule 5).

For each .claude/skills/<dir>/SKILL.md:
  - a `---` header with `name: <dir>` and a one-line `description:` that is a valid plain YAML
    value (no ': ', no ' #', no leading YAML indicator; also parsed with PyYAML if installed)
  - README.md has its index row `[<dir>](.claude/skills/<dir>/SKILL.md)`, its section
    `#### <dir>：` and names it in the "依情況找 skill" table
and README.md says "<n> 個 Claude Code skill", CLAUDE.md "有 <n> 個流程 skill" (n = number of
skills), and README.md links no skill that does not exist.
It cannot tell whether a README section still says what its SKILL.md says; that stays a review
item (phase-exit-review rule 9).
Before checking, it injects 3 faults into a temporary copy (a ': ' in a description, a removed
README section, a new skill not in README.md) and FAILs unless each one is reported.
Prints `skill-check: PASS <n> skills` / `skill-check: FAIL ...`; exit code 0 only on PASS.
"""
import os
import re
import shutil
import sys
import tempfile

try:
    import yaml
except ImportError:  # the plain-value rules below still apply
    yaml = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INDICATORS = set("-?:,[]{}#&*!|>'\"%@`")


def problems(root):
    """(skill names, [problem]) for the tree at root."""
    out = []
    sk = os.path.join(root, ".claude", "skills")
    names = sorted(d for d in os.listdir(sk) if os.path.isfile(os.path.join(sk, d, "SKILL.md")))
    readme = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    claude = open(os.path.join(root, "CLAUDE.md"), encoding="utf-8").read()
    parts = readme.split("### 依情況找 skill", 1)
    table = parts[1].split("\n### ", 1)[0] if len(parts) == 2 else ""
    if not table:
        out.append("README.md: no '### 依情況找 skill' section")
    for n in names:
        text = open(os.path.join(sk, n, "SKILL.md"), encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not m:
            out.append(f"{n}: SKILL.md does not start with a --- header")
            continue
        fields = {}
        for line in m.group(1).split("\n"):
            key, sep, value = line.partition(": ")
            if sep:
                fields[key] = value
            else:
                out.append(f"{n}: header line is not 'key: value': {line[:40]!r}")
        if fields.get("name") != n:
            out.append(f"{n}: header name is {fields.get('name')!r}, not the directory name")
        desc = fields.get("description", "")
        if not desc:
            out.append(f"{n}: no description")
        elif ": " in desc or " #" in desc or desc[0] in INDICATORS:
            out.append(f"{n}: description is not a valid plain YAML value (': ', ' #' or a leading indicator)")
        if yaml is not None:
            try:
                yaml.safe_load(m.group(1))
            except yaml.YAMLError as e:
                out.append(f"{n}: header is not valid YAML: {str(e).splitlines()[0]}")
        if f"[{n}](.claude/skills/{n}/SKILL.md)" not in readme:
            out.append(f"{n}: no index row in README.md")
        if f"#### {n}：" not in readme:
            out.append(f"{n}: no '#### {n}：' section in README.md")
        if not re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", table):
            out.append(f"{n}: not in README.md '依情況找 skill'")
    for n in sorted(set(re.findall(r"\]\(\.claude/skills/([\w-]+)/SKILL\.md\)", readme)) - set(names)):
        out.append(f"README.md links {n}, which has no SKILL.md")
    if f"{len(names)} 個 Claude Code skill" not in readme:
        out.append(f"README.md does not say '{len(names)} 個 Claude Code skill'")
    if f"有 {len(names)} 個流程 skill" not in claude:
        out.append(f"CLAUDE.md does not say '有 {len(names)} 個流程 skill'")
    return names, out


def self_test(names):
    """[error] unless each injected fault is reported on a copy of the tree."""
    first = names[0]

    def colon(t):
        p = os.path.join(t, ".claude", "skills", first, "SKILL.md")
        s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(s.replace("description: ", "description: Use for x: y ", 1))

    def no_section(t):
        p = os.path.join(t, "README.md")
        s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(s.replace(f"#### {first}：", f"#### {first}-gone：", 1))

    def new_skill(t):
        d = os.path.join(t, ".claude", "skills", "zz-new-skill")
        os.makedirs(d)
        open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8").write(
            "---\nname: zz-new-skill\ndescription: 新的 skill\n---\n")

    cases = [("colon", colon, f"{first}: description is not a valid plain YAML value"),
             ("no_section", no_section, f"{first}: no '#### {first}：' section"),
             ("new_skill", new_skill, "zz-new-skill: no index row in README.md")]
    errors = []
    for name, inject, want in cases:
        with tempfile.TemporaryDirectory() as t:
            shutil.copytree(os.path.join(ROOT, ".claude", "skills"), os.path.join(t, ".claude", "skills"))
            for f in ("README.md", "CLAUDE.md"):
                shutil.copy(os.path.join(ROOT, f), t)
            inject(t)
            _, found = problems(t)
            if not any(p.startswith(want) for p in found):
                errors.append(f"self-test {name}: expected '{want}', got {found[:3]}")
    return errors


def main():
    names, found = problems(ROOT)
    if not names:
        print("skill-check: FAIL no .claude/skills/*/SKILL.md found")
        return 1
    errors = self_test(names)
    if errors:
        print("skill-check: FAIL " + "; ".join(errors))
        return 1
    for p in found:
        print(f"  [FAIL] {p}")
    if found:
        print(f"skill-check: FAIL {len(found)} problem(s) in {len(names)} skills")
        return 1
    print(f"skill-check: PASS {len(names)} skills, headers valid, all in README.md"
          + ("" if yaml is not None else " (PyYAML not installed: plain-value rules only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
