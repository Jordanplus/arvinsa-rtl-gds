#!/usr/bin/env python3
"""phase_metrics.png: key numbers per phase, only from repo documents (README.md "專案狀態" and
docs/phase_exit/phase*.md). Every number below carries its file:line; SOURCES.md repeats them.
Phases are in the order they were closed (Phase 4 on 2026-10-04 before Phase 3.5 on 2026-10-05,
docs/phase_exit/phase4.md:3, phase3_5.md:3).
"""
from common import C1, C2, C3, INK, INK2, out, plt, style

ORDER = ["P2", "P3", "P4", "P3.5", "P5", "P6", "P7"]
X = {p: i for i, p in enumerate(ORDER)}

# (a) SoC clock period (ns); P2 is picorv32_core alone
PERIOD = [("P2", 40, "README.md:15"), ("P3", 40, "README.md:16"), ("P4", 42, "README.md:24"),
          ("P3.5", 43, "README.md:32"), ("P5", 44, "README.md:39"), ("P6", 44, "docs/phase_exit/phase6.md:61"),
          ("P7", 44, "docs/phase_exit/phase7.md:60")]
# (b) worst setup / hold slack at phase exit (ns), the design named in the label
SLACK = [("P2", 6.175, 0.039, "picorv32\ncore", "docs/phase_exit/phase2.md:13"),
         ("P4", 0.313, 0.082, "soc_top\nPicoRV32", "docs/phase_exit/phase4.md:42"),
         ("P5", 1.114, 0.109, "soc_top\nHazard3", "README.md:40"),
         ("P6", 0.656, 0.126, "soc_top\nHazard3", "README.md:49"),
         ("P7", 0.548, 0.187, "Caravel\nwrapper", "README.md:56")]
# (c) IR: VDD drop + VSS rise (mV), limit 20 mV; the model changed between phases
IR = [("P4", 8.07, "one-side supply\nnom_tt", "README.md:25; docs/phase_exit/phase4.md:113"),
      ("P5", 14.13, "ff current\n+ ss metal R", "README.md:41"),
      ("P6", 15.91, "ff current\n+ ss metal R", "README.md:49"),
      ("P7", 19.56, "Caravel pads,\nmax-power pattern", "README.md:56")]
# (d) closing regressions on a clean checkout: (phase, target, items, minutes, source)
REGRESS = [("P4", "make regress", 25, 123, "README.md:27"),
           ("P3.5", "make regress", 25, 136, "README.md:34"),
           ("P5", "make regress", 21, 109, "README.md:43"),
           ("P5", "regress-picorv32", 26, 124, "README.md:43"),
           ("P6", "make regress", 23, 126, "README.md:52"),
           ("P6", "regress-picorv32", 28, 196, "README.md:52"),
           ("P7", "make regress", 30, 211, "README.md:60"),
           ("P7", "regress-picorv32", 31, 248, "README.md:60"),
           ("P7", "regress-caravel", 18, 476, "README.md:60")]
# (e) bug-injection cases, all caught by the expected checker (totals stated in the docs)
NEG = [("P1", 33, "README.md:14"),
       ("P3", 44, "README.md:19 (PnR 20 + EQY 11 + GL sim 4 + provenance 9)"),
       ("P4", 163, "README.md:27; docs/phase_exit/phase4.md:149"),
       ("P3.5", 164, "README.md:34; docs/phase_exit/phase3_5.md:122")]


def main():
    style()
    fig, axes = plt.subplots(2, 3, figsize=(17, 10))
    a, b, c = axes[0]
    d, e, f = axes[1]

    xs = [X[p] for p, _, _ in PERIOD]; ys = [v for _, v, _ in PERIOD]
    a.step(xs, ys, where="post", color=C1, lw=2)
    a.scatter(xs, ys, color=C1, s=60, zorder=3)
    for x, y in zip(xs, ys):
        a.text(x, y + 0.25, f"{y} ns", ha="center", va="bottom", fontsize=10, color=INK)
    a.set_xticks(range(len(ORDER)), ORDER)
    a.set_ylim(38, 46); a.set_ylabel("clock period (ns)")
    a.set_title("(a) SoC clock period at phase exit\nP2 = picorv32_core alone; 42→43→44 ns were user decisions",
                loc="left", fontsize=11)

    w = 0.38
    for i, (p, s, h, lab, _) in enumerate(SLACK):
        b.bar(i - w / 2, s, w, color=C1, label="setup" if i == 0 else None)
        b.bar(i + w / 2, h, w, color=C2, label="hold" if i == 0 else None)
        b.text(i - w / 2, min(s, 1.62) + 0.03, f"+{s:.3f}" + (" ↑" if s > 1.8 else ""), ha="center", va="bottom", fontsize=8.5, color=INK)
        b.text(i + w / 2, h + 0.03, f"+{h:.3f}", ha="center", va="bottom", fontsize=8.5, color=INK)
    b.set_xticks(range(len(SLACK)), [f"{p}\n{lab}" for p, _, _, lab, _ in SLACK], fontsize=8.5)
    b.set_ylim(0, 1.8); b.set_ylabel("worst slack over all corners (ns)")
    b.legend(loc="upper right", fontsize=9, frameon=False)
    b.axhline(0, color=INK, lw=1)
    b.set_title("(b) worst setup / hold slack at phase exit (all ≥ 0)\nP2: 9 corners, others 15; axis clipped at 1.8 ns",
                loc="left", fontsize=11)
    b.grid(axis="x", visible=False)

    for i, (p, v, lab, _) in enumerate(IR):
        c.bar(i, v, 0.6, color=C3)
        c.text(i, v + 0.3, f"{v:.2f}", ha="center", va="bottom", fontsize=10, color=INK)
    c.axhline(20, color="#e34948", lw=1.6, ls="--")
    c.text(-0.4, 20.3, "limit 20 mV", ha="left", va="bottom", fontsize=9.5, color=INK)
    c.set_xticks(range(len(IR)), [f"{p}\n{lab}" for p, _, lab, _ in IR], fontsize=8.5)
    c.set_ylim(0, 23); c.set_ylabel("VDD drop + VSS rise (mV)")
    c.set_title("(c) static IR at phase exit (P7: the Caravel wrapper from its pads)\nthe judging model changed between phases: not directly comparable",
                loc="left", fontsize=11)
    c.grid(axis="x", visible=False)

    cols = {"make regress": C1, "regress-picorv32": C2, "regress-caravel": C3}
    labels = []
    for i, (p, t, n, m, _) in enumerate(REGRESS):
        d.bar(i, m, 0.7, color=cols[t], label=t if t not in labels else None)
        labels.append(t)
        d.text(i, m + 6, f"{m} min\n{n}/{n}", ha="center", va="bottom", fontsize=8.5, color=INK)
    d.set_xticks(range(len(REGRESS)), [p for p, *_ in REGRESS])
    d.set_ylim(0, 560); d.set_ylabel("wall-clock time (min)")
    d.legend(loc="upper left", fontsize=9, frameon=False)
    d.set_title("(d) closing regression on a clean checkout\nlabel: minutes and items PASS",
                loc="left", fontsize=11)
    d.grid(axis="x", visible=False)

    for i, (p, n, _) in enumerate(NEG):
        e.bar(i, n, 0.6, color=C1)
        e.text(i, n + 3, str(n), ha="center", va="bottom", fontsize=10, color=INK)
    e.set_xticks(range(len(NEG)), [p for p, *_ in NEG])
    e.set_ylim(0, 190); e.set_ylabel("negative-test cases (all as expected)")
    e.set_title("(e) negative-test cases in the regression, incl. positive controls\n(Phases 5–7 report per-suite counts only, no total)",
                loc="left", fontsize=11)
    e.grid(axis="x", visible=False)

    f.axis("off")
    f.text(0, 1, "Sources (file:line)", fontsize=10.5, fontweight="bold", va="top", color=INK)
    lines = [f"(a) {p} {v} ns  {s}" for p, v, s in PERIOD] + \
            [f"(b) {p}  {s}" for p, *_, s in SLACK] + [f"(c) {p}  {s}" for p, *_, s in IR] + \
            [f"(d) {p} {t}  {s}" for p, t, _, _, s in REGRESS] + [f"(e) {p}  {s}" for p, _, s in NEG]
    f.text(0, 0.95, "\n".join(lines), fontsize=7.4, va="top", family="DejaVu Sans Mono", color=INK2)

    fig.suptitle("arvinsa-rtl-gds: key numbers per phase (from README.md and docs/phase_exit/, phases in closing order)",
                 x=0.01, ha="left", fontsize=13.5)
    fig.tight_layout()
    fig.savefig(out("phase_metrics.png"), dpi=140)


if __name__ == "__main__":
    main()
