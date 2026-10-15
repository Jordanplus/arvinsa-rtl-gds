#!/usr/bin/env python3
"""Architecture / flow diagrams for the technical report, drawn with the
arvinsa-draw-diagram engine (hand-written nodes/links JSON, no spec extraction).

usage: python3 diagrams.py [en|zh ...]   (default: both)
Writes docs/report/figures/diagrams/<name>_<lang>.json and renders
docs/report/figures/<name>_<lang>.png / .svg with engine.py.
Every fact on a diagram has its source in the graph's "_note".
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.dirname(HERE)
JSON_DIR = os.path.join(FIG, "diagrams")
TEMPLATE = os.path.expanduser("~/claude_prjs/Arvinsa-skill-develop-template")
ENGINE = os.path.join(TEMPLATE, ".claude/skills/arvinsa-draw-diagram/scripts/render/engine.py")
PY = os.path.join(TEMPLATE, ".venv/bin/python")

BLUE = ("#2980B9", "#DEEBF7")
GREEN = ("#27AE60", "#E2F0D9")
ORANGE = ("#E67E22", "#FBE5D6")
PURPLE = ("#8E44AD", "#EADCF0")
GREY = ("#7F8C8D", "#EDEDED")
RED = ("#C0392B", "#F8D7D3")
TEAL = ("#16A085", "#D5F0EA")


def node(i, label, parent="root", layer=1, color=GREY):
    return {"id": i, "label": label, "layer": layer, "parent": parent,
            "border": color[0], "fill": color[1]}


def L(en, zh):
    return {"en": en, "zh": zh}


# ---------------------------------------------------------------------------
# 1. Phase roadmap
ROADMAP = {
    "name": "roadmap",
    "title": L("arvinsa-rtl-gds: Phase 0-7 roadmap", "arvinsa-rtl-gds：Phase 0–7 路線圖"),
    "_note": "README.md 專案狀態與階段路線圖；docs/phase_exit/phase*.md",
    "rows": "p0,p1,p2|p3,p4,p35|p5,p6,p7",
    "ranksep": "0.35",
    "nodes": [
        ("p0", BLUE, L("Phase 0 (10-03)\nEnvironment\nNix, LibreLane 3.0.14, sky130A\nreference SRAM design re-run: signoff PASS",
                       "Phase 0（10-03）\n環境建置\nNix、LibreLane 3.0.14、sky130A\n重跑官方 SRAM 範例：signoff PASS")),
        ("p1", BLUE, L("Phase 1 (10-03)\nPicoRV32 SoC RTL + firmware\nRTL regression 26/26\n33 injected bugs caught",
                       "Phase 1（10-03）\nPicoRV32 SoC RTL 與 firmware\nRTL regression 26/26\n33 個植入錯誤全抓到")),
        ("p2", BLUE, L("Phase 2 (10-03)\nPicoRV32 core hardened alone\n40 ns, 9 corners\nDRC / LVS 0",
                       "Phase 2（10-03）\nPicoRV32 單獨 harden\n40 ns、9 個 corner\nDRC／LVS 0")),
        ("p3", GREEN, L("Phase 3 (10-04)\nSoC + prebuilt 2 KB SRAM macro\n1000 x 800 um, 40 ns\nEQY + gate-level sim",
                        "Phase 3（10-04）\nSoC 整合預建 2 KB SRAM\n1000 × 800 µm、40 ns\nEQY 與 gate-level 模擬")),
        ("p4", GREEN, L("Phase 4 (10-04)\nSignoff closure, one-command regression\n42 ns, 15 corners\nmake regress 25/25",
                        "Phase 4（10-04）\nsignoff 收斂、一鍵 regression\n42 ns、15 個 corner\nmake regress 25/25")),
        ("p35", ORANGE, L("Phase 3.5 (10-05)\nSRAM timing by SPICE (ngspice)\n43 ns\nfound: read failure at ss, low temp",
                          "Phase 3.5（10-05）\nSRAM 時序改用 SPICE 實測\n43 ns\n發現 ss 低溫讀取失敗")),
        ("p5", PURPLE, L("Phase 5 (10-08)\nCPU swapped to Hazard3\n44 ns, riscv-tests 65/65\nflow reused; 4 settings changed",
                         "Phase 5（10-08）\nCPU 換成 Hazard3\n44 ns、riscv-tests 65/65\n沿用 flow，改了 4 項設定")),
        ("p6", PURPLE, L("Phase 6 (10-11)\nSelf-generated OpenRAM SRAM\nread failure fixed\n7 PVT read OK",
                         "Phase 6（10-11）\nOpenRAM 自產 SRAM\n修好讀取失敗\n7 個 PVT 讀寫正確")),
        ("p7", RED, L("Phase 7 (10-15)\nHazard3 SoC in Caravel wrapper\nChipFoundry precheck PASS\n(not taped out)",
                      "Phase 7（10-15）\nHazard3 SoC 放進 Caravel\nChipFoundry precheck PASS\n（不下線）")),
    ],
    "links": [("p0", "p1"), ("p1", "p2"), ("p3", "p4"), ("p4", "p35"), ("p5", "p6"), ("p6", "p7")],
}

# ---------------------------------------------------------------------------
# 2. Flow architecture (one box per stage, tools + checkers in the label)
FLOW = {
    "name": "flow",
    "title": L("RTL-to-GDS flow and checkers", "RTL-to-GDS 流程與 checker"),
    "_note": "arvinsa-rtl-gds-flow.md §3、§4；Makefile；scripts/regress.py",
    "rows": "spec,rtl,macro|cons,harden,signoff|netlist,regress,precheck",
    "ranksep": "0.4",
    "nodes": [
        ("spec", GREY, L("1  Spec & plan\noperating range, corners\nplatform worksheet\npad / block / pin plan (approved)",
                         "1  規格與計畫\n操作範圍、corner\n平台試算表\npad／block／pin 規劃（核准）")),
        ("rtl", BLUE, L("2  RTL & DV\nVerilator lint, Yosys synth check\nIcarus + Verilator regression\ninjected-bug negative tests",
                        "2  RTL 與驗證\nVerilator lint、Yosys 合成檢查\nIcarus＋Verilator regression\n植入錯誤的 negative test")),
        ("macro", ORANGE, L("3  SRAM macro\nOpenRAM generate + patches\nngspice characterization -> .lib\nview QA, macro DRC",
                            "3  SRAM macro\nOpenRAM 產生＋patch\nngspice 特性化 → .lib\nview QA、macro DRC")),
        ("cons", GREY, L("4  Constraints & criteria\nSDC, 15 signoff corners\nlimits derived per design\n(signoff/limits/*.toml)",
                         "4  約束與 signoff 條件\nSDC、15 個 signoff corner\n每個設計自己推導的上限\n（signoff/limits/*.toml）")),
        ("harden", GREEN, L("5  Harden (LibreLane)\nfloorplan, PDN, placement\nCTS, routing, fill\nOpenROAD / Magic / KLayout",
                            "5  harden（LibreLane）\nfloorplan、PDN、placement\nCTS、routing、fill\nOpenROAD／Magic／KLayout")),
        ("signoff", GREEN, L("6  Signoff checkers\nSTA 15 corners, DRC, LVS, XOR\nantenna, IR (max-power pattern)\ngolden compare, criteria review",
                             "6  signoff checker\n15 corner STA、DRC、LVS、XOR\nantenna、IR（max power pattern）\ngolden 比對、criteria review")),
        ("netlist", BLUE, L("7  Netlist verification\nEQY equivalence\ngate-level lockstep sim\n(powered netlist too)",
                            "7  網表驗證\nEQY 等價證明\ngate-level lockstep 模擬\n（含電源接腳網表）")),
        ("regress", PURPLE, L("8  One-command regression\nmake regress / -picorv32 / -caravel\nrun guard + provenance\nclean worktree only",
                              "8  一鍵 regression\nmake regress／-picorv32／-caravel\nrun guard＋來源追溯\n只認乾淨 worktree")),
        ("precheck", RED, L("9  Tapeout precheck\nChipFoundry cf-precheck 1.3.7\nofficial image in lima VM\nmake precheck-caravel",
                            "9  下線預檢\nChipFoundry cf-precheck 1.3.7\n官方 image 跑在 lima VM\nmake precheck-caravel")),
    ],
    "links": [("spec", "rtl"), ("rtl", "macro"), ("cons", "harden"), ("harden", "signoff"),
              ("netlist", "regress"), ("regress", "precheck")],
}

# ---------------------------------------------------------------------------
# 3. SoC inside the Caravel user_project_wrapper
SOC = {
    "name": "soc_caravel",
    "title": L("Hazard3 SoC inside the Caravel user_project_wrapper",
               "Hazard3 SoC 放在 Caravel 的 user_project_wrapper 裡"),
    "_note": "docs/spec/soc_spec.md §2、§4；ADR-0011 決定 1；ADR-0019 決定 8–10、12；rtl/caravel/",
    "rows": "wb,la|bridge|cpu,adapter,bus|sram,rom,uart,gpio,test",
    "ranksep": "0.45",
    "extra": ["--no-concentrate"],  # with concentrate, ortho routing dropped the wb -> bridge edge
    "clusters": [
        ("mgmt", GREY, L("Caravel management SoC (fixed)", "Caravel 管理用 SoC（固定）")),
        ("wrap", BLUE, L("user_project_wrapper (2920 x 3520 um)", "user_project_wrapper（2920 × 3520 µm）")),
        ("soc", GREEN, L("soc_top (u_soc), flat in the wrapper, lower-left corner",
                         "soc_top（u_soc），扁平放在 wrapper 左下角")),
    ],
    "nodes": [
        ("wb", GREY, L("Wishbone master\nwb_clk_i / wb_rst_i", "Wishbone master\nwb_clk_i／wb_rst_i"), "mgmt"),
        ("la", GREY, L("Logic analyzer\nla_data_out[13:0]", "Logic analyzer\nla_data_out[13:0]"), "mgmt"),
        ("bridge", BLUE, L("wb_host_bridge\n0x3000_0000 host_en (reset 1)\n0x3000_1000 SRAM window",
                           "wb_host_bridge\n0x3000_0000 host_en（reset 1）\n0x3000_1000 SRAM 視窗"), "wrap"),
        ("cpu", GREEN, L("Hazard3\nhazard3_cpu_1port (AHB5)", "Hazard3\nhazard3_cpu_1port（AHB5）"), "soc"),
        ("adapter", GREEN, L("AHB -> native bus\nadapter", "AHB 轉 native bus\n轉接器"), "soc"),
        ("bus", GREEN, L("soc_bus\naddress decode", "soc_bus\n位址解碼"), "soc"),
        ("sram", ORANGE, L("SRAM 2 KB\narv_sram_2kbyte_1rw1r_32x512_8\n0x0000_0000",
                           "SRAM 2 KB\narv_sram_2kbyte_1rw1r_32x512_8\n0x0000_0000"), "soc"),
        ("rom", GREEN, L("Boot ROM\n0x0001_0000", "Boot ROM\n0x0001_0000"), "soc"),
        ("uart", GREEN, L("UART\n0x0200_0000\nGPIO 37 tx / 36 rx", "UART\n0x0200_0000\nGPIO 37 tx／36 rx"), "soc"),
        ("gpio", GREEN, L("GPIO\n0x0300_0000\nout via LA only", "GPIO\n0x0300_0000\n輸出只走 LA"), "soc"),
        ("test", GREEN, L("TEST_CTRL\n0x0400_0000\ntrap -> GPIO 35", "TEST_CTRL\n0x0400_0000\ntrap → GPIO 35"), "soc"),
    ],
    "links": [("wb", "bridge"), ("bridge", "sram"), ("cpu", "adapter"), ("adapter", "bus"),
              ("bus", "sram"), ("bus", "rom"), ("bus", "uart"), ("bus", "gpio"), ("bus", "test"),
              ("gpio", "la")],
}

# ---------------------------------------------------------------------------
# 4. How a harden is judged and how the checkers are qualified
CHECK = {
    "name": "checkers",
    "title": L("Signoff judgement and checker qualification",
               "signoff 判定與 checker qualification"),
    "_note": "signoff/scripts/check_signoff.py；pnr/soc_top/check_soc.py；signoff/scripts/review_criteria.py；"
             "signoff/scripts/provenance.py、run_guard.py；neg_*.py；signoff-checker-qualification skill",
    "rows": "run,limits,golden|cs,csoc,crit,prov|verdict,neg",
    "ranksep": "0.4",
    "nodes": [
        ("run", GREEN, L("harden run\nfinal/metrics.json, reports\nGDS, netlists", "harden 的 run\nfinal/metrics.json、報表\nGDS、網表")),
        ("limits", GREY, L("limits file\nsignoff/limits/<design>.toml\nlimits derived per design", "上限檔\nsignoff/limits/<design>.toml\n每個設計自己推導的上限")),
        ("golden", GREY, L("golden metrics\nsignoff/golden/<design>/\n+ tolerance table", "golden metrics\nsignoff/golden/<design>/\n＋誤差表")),
        ("cs", BLUE, L("check_signoff.py\nlimits + golden compare", "check_signoff.py\n上限＋golden 比對")),
        ("csoc", BLUE, L("check_soc.py\nslew, Magic DRC vs SRAM alone\nIR sources, disconnected", "check_soc.py\nslew、Magic DRC 對 SRAM 單獨檢查\n供電點、disconnected")),
        ("crit", BLUE, L("review_criteria.py\nsettings really applied?\n+ human review (.md)", "review_criteria.py\n設定真的生效？\n＋人工 review（.md）")),
        ("prov", BLUE, L("provenance / run guard\ncommit = HEAD, clean tree", "來源追溯／run guard\ncommit = HEAD、工作樹乾淨")),
        ("verdict", GREEN, L("harden-soc: PASS / FAIL", "harden-soc：PASS／FAIL")),
        ("neg", RED, L("negative tests (bug injection)\nneg-pnr 82, neg-precheck 31, neg-ir 12 ...\neach injected bug must FAIL",
                       "negative test（植入錯誤）\nneg-pnr 82、neg-precheck 31、neg-ir 12 …\n每個植入錯誤都必須 FAIL")),
    ],
    "links": [("run", "cs"), ("limits", "cs"), ("golden", "cs"), ("run", "csoc"), ("run", "crit"), ("run", "prov"),
              ("cs", "verdict"), ("csoc", "verdict"), ("crit", "verdict"), ("prov", "verdict"),
              ("neg", "cs"), ("neg", "csoc")],
}

# ---------------------------------------------------------------------------
# 5. How problems become skills, flow steps and checkers
LOOP = {
    "name": "knowledge_loop",
    "title": L("From a problem to a rule, a checker and a flow step",
               "從問題到規則、checker 與流程步驟"),
    "_note": "CLAUDE.md 規則 2、3、5、8、10、13；phase-exit-review skill；ADR-0020",
    "rows": "prob,cause,exp|rule,guard,flow|adr,review",
    "ranksep": "0.4",
    "nodes": [
        ("prob", RED, L("1  Problem seen\n(log message, FAIL, review)", "1  遇到問題\n（log 訊息、FAIL、審查）")),
        ("cause", ORANGE, L("2  Root cause\nverified (experiment) or\nmarked as speculation", "2  找根因\n已驗證（實驗）或\n標明推測")),
        ("exp", GREY, L("3  Skill experience record\ndate, run, message,\ncause, fix, evidence", "3  skill 經驗紀錄\n日期、run、原文訊息、\n根因、處理、證據")),
        ("rule", BLUE, L("4  Skill rule\n(seen twice or verified)\nsymptom also in description", "4  skill 規則\n（出現兩次或已驗證）\n症狀也寫進 description")),
        ("guard", PURPLE, L("5  Guard\nchecker + negative test\nor 'no automatic guard' + why", "5  防護\nchecker＋negative test\n或寫明「沒有自動防護」與原因")),
        ("flow", GREEN, L("6  Flow document step\narvinsa-rtl-gds-flow.md\n(reused by new projects)", "6  流程文件步驟\narvinsa-rtl-gds-flow.md\n（新專案沿用）")),
        ("adr", GREY, L("Any choice: decision (ADR)\noptions + user's own words", "每個選擇：決定（ADR）\n選項＋使用者原話")),
        ("review", TEAL, L("End of phase: exit review\nclean-worktree regression\nindependent agent review", "每個 Phase 收尾：exit review\n乾淨 worktree regression\n獨立 agent 審查")),
    ],
    "links": [("prob", "cause"), ("cause", "exp"), ("exp", "rule"), ("rule", "guard"), ("guard", "flow"), ("adr", "review")],
    # rows are read left to right; numbering in the labels gives the order across rows
}


# ---------------------------------------------------------------------------
# 6. Skill map: three stages, each with an entry skill (ADR-0021 decision 6)
M_SUBS = ["rtl-synthesis-lint", "dv-directed-tests", "core-migration-hazard3", "timing-constraints-sdc",
          "formal-equivalence-eqy", "macro-qualification", "openram-macro-generation",
          "openram-macro-characterization", "sram-layout-extraction"]
B_SUBS = ["floorplan-congestion", "hard-macro-integration", "pdn-ir-drop", "cts-clock-tree", "drv-timing-closure",
          "multicorner-sta", "antenna-signoff", "drc-signoff", "lvs-signoff", "gate-level-simulation",
          "signoff-criteria", "librelane-run-debug"]
P_SUBS = ["chip-floorplan-pin-planning", "caravel-user-project-integration", "tapeout-precheck-caravel"]
C_SUBS = ["signoff-checker-qualification", "flow-regression-reproducibility", "phase-exit-review"]


def _skill_nodes():
    out = []
    for i, n in enumerate(M_SUBS):
        out.append((f"m{i}", BLUE, L(n, n), "mid"))
    for i, n in enumerate(B_SUBS):
        out.append((f"b{i}", GREEN, L(n, n), "back"))
    for i, n in enumerate(P_SUBS):
        out.append((f"p{i}", RED, L(n, n), "pkg"))
    for i, n in enumerate(C_SUBS):
        out.append((f"c{i}", PURPLE, L(n, n), "common"))
    return out


SKILLMAP = {
    "name": "skill_map",
    "title": L("Skills in three stages (entry skill -> sub-skills; listed by name only)",
               "skill 分成三段（入口 skill → 子 skill；子 skill 在清單只列名稱）"),
    "_note": "ADR-0021 決定 6；.claude/skills/{middle-end-flow,backend-flow,package-flow}/SKILL.md；"
             ".claude/settings.json skillOverrides",
    "rows": "mid,back,pkg,common",
    "ranksep": "0.4",
    "extra": ["--no-concentrate"],
    "clusters": [
        ("mid", BLUE, L("middle-end-flow (entry): RTL to netlist, SDC, macro prep, EQY",
                        "middle-end-flow（入口）：RTL 到網表、SDC、macro 準備、EQY")),
        ("back", GREEN, L("backend-flow (entry): LibreLane harden, PnR, physical signoff",
                          "backend-flow（入口）：LibreLane harden、PnR、實體 signoff")),
        ("pkg", RED, L("package-flow (entry): chip level, Caravel, precheck",
                       "package-flow（入口）：晶片層級、Caravel、precheck")),
        ("common", PURPLE, L("cross-stage (always listed with description)",
                             "跨段共用（清單上保留描述）")),
    ],
    "nodes": _skill_nodes(),
    "links": [],
}

GRAPHS = [ROADMAP, FLOW, SOC, CHECK, LOOP, SKILLMAP]


def build(g, lang):
    nodes = [{"id": "root", "label": g["title"][lang], "layer": 0, "parent": None}]
    for c in g.get("clusters", []):
        cid, color, lab = c
        nodes.append(node(cid, lab[lang], "root", 1, color))
    for n in g["nodes"]:
        nid, color, lab = n[0], n[1], n[2]
        parent = n[3] if len(n) > 3 else "root"
        layer = 2 if parent != "root" else 1
        nodes.append(node(nid, lab[lang], parent, layer, color))
    links = [{"source": a, "target": b} for a, b in g["links"]]
    only = os.environ.get("DIAG_ONLY")
    if only and g["name"] not in only.split(","):
        return None  # DIAG_ONLY=a,b renders only those graphs
    return {"_note": g["_note"], "nodes": nodes, "links": links}


def main(langs):
    os.makedirs(JSON_DIR, exist_ok=True)
    for g in GRAPHS:
        for lang in langs:
            name = f"{g['name']}_{lang}"
            path = os.path.join(JSON_DIR, name + ".json")
            data = build(g, lang)
            if data is None:
                continue
            with open(path, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            cmd = [PY, ENGINE, path, "-o", FIG, "-n", name, "--ranksep", g.get("ranksep", "0.4")]
            if g.get("rows"):
                cmd += ["--rows", g["rows"]]
            cmd += g.get("extra", [])
            if g.get("splines"):
                cmd += ["--splines", g["splines"], "--show-edge-labels", "no"]
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=TEMPLATE)
            print(name, "rc", r.returncode, (r.stderr or r.stdout).strip().splitlines()[-1:] )


if __name__ == "__main__":
    main(sys.argv[1:] or ["en", "zh"])
