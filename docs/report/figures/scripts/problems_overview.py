#!/usr/bin/env python3
"""problems_overview.png: the 247 problems of Phase 0-7 by category and by how they are captured now.

Data: docs/notes/problem_review/review_p0_35.md, review_p4_5.md, review_p6_7.md (2026-10-15).
- Categories: the "類別" column of each problem row (rows whose id starts with P<phase>-), grouped by the
  first matching keyword (see GROUPS); the grouping is this script's, not the reviewers'.
- Capture status: the counts each report gives in its summary (strongest layer per problem).
"""
import collections
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../../.."))
REVIEW = os.path.join(REPO, "docs/notes/problem_review")
FILES = ["review_p0_35.md", "review_p4_5.md", "review_p6_7.md"]
GROUPS = [("checker", "checker / test hole"), ("驗證覆蓋", "checker / test hole"),
          ("工具", "tool defect or\nunexpected behaviour"), ("macro", "macro / IP"), ("IP", "macro / IP"),
          ("平台", "platform rule"), ("規格", "spec / assumption"), ("假設", "spec / assumption"),
          ("量測", "spec / assumption"), ("已知限制", "spec / assumption"),
          ("環境", "host environment\n/ resources"), ("資源", "host environment\n/ resources"),
          ("文件", "documentation drift"), ("流程", "flow order / process"), ("計畫", "flow order / process"),
          ("人為", "flow order / process"), ("退回", "flow order / process")]
# summary counts from each report: rule + automatic guard, rule / flow doc only, experience record only, nowhere
CAPTURE = {"Phase 0-3.5": (36, 42, 3, 9), "Phase 4-5": (36, 19, 6, 1), "Phase 6-7": (43, 32, 14, 6)}


def categories():
    c = collections.Counter()
    for f in FILES:
        for line in open(os.path.join(REVIEW, f)):
            if not re.match(r"^\| *P[0-9.]+[-‑]", line):
                continue
            cells = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            group = "other"
            for key, name in GROUPS:
                if key in cells[3]:
                    group = name
                    break
            c[group] += 1
    return c


def main():
    cat = categories()
    total = sum(cat.values())
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.15, 1]})
    items = cat.most_common()
    a.barh([k for k, _ in items][::-1], [v for _, v in items][::-1], color="#2980B9")
    for i, (_, v) in enumerate(items[::-1]):
        a.text(v + 1, i, str(v), va="center", fontsize=10)
    a.set_title(f"(a) {total} problems in Phase 0-7 by category", loc="left")
    a.set_xlabel("problems")
    a.spines[["top", "right"]].set_visible(False)

    labels = ["skill rule / flow doc\n+ automatic guard", "skill rule / flow doc\nonly",
              "experience record\nonly", "nowhere\n(ADR, notes, commit)"]
    colors = ["#27AE60", "#F1C40F", "#E67E22", "#C0392B"]
    phases = list(CAPTURE)
    left = [0] * len(phases)
    for k in range(4):
        vals = [CAPTURE[p][k] for p in phases]
        b.barh(phases[::-1], vals[::-1], left=left[::-1], color=colors[k], label=labels[k])
        for i, (l0, v) in enumerate(zip(left[::-1], vals[::-1])):
            if v >= 4:
                b.text(l0 + v / 2, i, str(v), ha="center", va="center", fontsize=10)
        left = [l0 + v for l0, v in zip(left, vals)]
    b.set_title("(b) how each problem is captured now (strongest layer)", loc="left")
    b.set_xlabel("problems")
    b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=9, frameon=False)
    b.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, "Source: docs/notes/problem_review/review_p0_35.md, review_p4_5.md, review_p6_7.md "
             "(2026-10-15); categories grouped by keyword in this script", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = os.path.join(HERE, "..", "problems_overview.png")
    fig.savefig(out, dpi=150)
    print("saved", os.path.abspath(out), total)


if __name__ == "__main__":
    main()
