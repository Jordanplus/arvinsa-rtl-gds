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
                        "Phase 3（10-04）\nSoC 整合 PDK 附的 2 KB SRAM\n1000 × 800 µm、40 ns\nEQY 與 gate-level 模擬")),
        ("p4", GREEN, L("Phase 4 (10-04)\nSignoff closure, one-command regression\n42 ns, 15 corners\nmake regress 25/25",
                        "Phase 4（10-04）\nsignoff 收斂、一鍵 regression\n42 ns、15 個 corner\nmake regress 25/25")),
        ("p35", ORANGE, L("Phase 3.5 (10-05)\nSRAM timing by SPICE (ngspice)\n43 ns\nfound: read failure at ss, low temp",
                          "Phase 3.5（10-05）\nSRAM 時序改用 SPICE 模擬\n43 ns\n發現 ss 低溫讀取失敗")),
        ("p5", PURPLE, L("Phase 5 (10-08)\nCPU swapped to Hazard3\n44 ns, riscv-tests 65/65\nflow reused; 4 settings changed",
                         "Phase 5（10-08）\nCPU 換成 Hazard3\n44 ns、riscv-tests 65/65\n沿用 flow，改了 4 項設定")),
        ("p6", PURPLE, L("Phase 6 (10-11)\nSelf-generated OpenRAM SRAM\nread failure fixed\n7 PVT read OK",
                         "Phase 6（10-11）\n用 OpenRAM 產生 SRAM\n修好讀取失敗\n7 個 PVT 讀寫正確")),
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
                         "1  規格與計畫\n操作條件、corner\n下線規定對照表\npad／block／pin 規劃（核准）")),
        ("rtl", BLUE, L("2  RTL & DV\nVerilator lint, Yosys synth check\nIcarus + Verilator regression\ninjected-bug negative tests",
                        "2  RTL 與驗證\nVerilator lint、Yosys 合成檢查\nIcarus＋Verilator regression\n植入錯誤的 negative test")),
        ("macro", ORANGE, L("3  SRAM macro\nOpenRAM generate + patches\nngspice characterization -> .lib\nview QA, macro DRC",
                            "3  SRAM macro\nOpenRAM 產生＋patch\nngspice characterization → .lib\nview QA、macro DRC")),
        ("cons", GREY, L("4  Constraints & criteria\nSDC, 15 signoff corners\nlimits derived per design\n(signoff/limits/*.toml)",
                         "4  constraint 與 signoff 條件\nSDC、15 個 signoff corner\n每個設計自己推導的門檻\n（signoff/limits/*.toml）")),
        ("harden", GREEN, L("5  Harden (LibreLane)\nfloorplan, PDN, placement\nCTS, routing, fill\nOpenROAD / Magic / KLayout",
                            "5  harden（LibreLane）\nfloorplan、PDN、placement\nCTS、routing、fill\nOpenROAD／Magic／KLayout")),
        ("signoff", GREEN, L("6  Signoff checkers\nSTA 15 corners, DRC, LVS, XOR\nantenna, IR (max-power pattern)\ngolden compare, criteria review",
                             "6  signoff checker\n15 corner STA、DRC、LVS、XOR\nantenna、IR（max power pattern）\ngolden 比對、criteria review")),
        ("netlist", BLUE, L("7  Netlist verification\nEQY equivalence\ngate-level lockstep sim\n(powered netlist too)",
                            "7  netlist 驗證\nEQY 等價證明\ngate-level lockstep 模擬\n（也跑 PG netlist）")),
        ("regress", PURPLE, L("8  One-command regression\nmake regress / -picorv32 / -caravel\nrun guard + provenance\nclean worktree only",
                              "8  一鍵 regression\nmake regress／-picorv32／-caravel\nrun guard＋版本追溯\n只認乾淨 worktree")),
        ("precheck", RED, L("9  Tapeout precheck\nChipFoundry cf-precheck 1.3.7\nofficial image in lima VM\nmake precheck-caravel",
                            "9  下線前檢查\nChipFoundry cf-precheck 1.3.7\n官方 image 跑在 lima VM\nmake precheck-caravel")),
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
        ("mgmt", GREY, L("Caravel management SoC (fixed)", "Caravel management SoC（固定）")),
        ("wrap", BLUE, L("user_project_wrapper (2920 x 3520 um)", "user_project_wrapper（2920 × 3520 µm）")),
        ("soc", GREEN, L("soc_top (u_soc), flat in the wrapper, lower-left corner",
                         "soc_top（u_soc），以 flat 方式放在 wrapper 左下角")),
    ],
    "nodes": [
        ("wb", GREY, L("Wishbone master\nwb_clk_i / wb_rst_i", "Wishbone master\nwb_clk_i／wb_rst_i"), "mgmt"),
        ("la", GREY, L("Logic analyzer\nla_data_out[13:0]", "Logic analyzer\nla_data_out[13:0]"), "mgmt"),
        ("bridge", BLUE, L("wb_host_bridge\n0x3000_0000 host_en (reset 1)\n0x3000_1000 SRAM window",
                           "wb_host_bridge\n0x3000_0000 host_en（reset 1）\n0x3000_1000 SRAM 位址區"), "wrap"),
        ("cpu", GREEN, L("Hazard3\nhazard3_cpu_1port (AHB5)", "Hazard3\nhazard3_cpu_1port（AHB5）"), "soc"),
        ("adapter", GREEN, L("AHB -> native bus\nadapter", "AHB 轉 native bus\nbridge"), "soc"),
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
               "signoff 檢查與 checker qualification"),
    "_note": "signoff/scripts/check_signoff.py；pnr/soc_top/check_soc.py；signoff/scripts/review_criteria.py；"
             "signoff/scripts/provenance.py、run_guard.py；neg_*.py；signoff-checker-qualification skill",
    "rows": "run,limits,golden|cs,csoc,crit,prov|verdict,neg",
    "ranksep": "0.4",
    "nodes": [
        ("run", GREEN, L("harden run\nfinal/metrics.json, reports\nGDS, netlists", "harden 的 run\nfinal/metrics.json、報表\nGDS、netlist")),
        ("limits", GREY, L("limits file\nsignoff/limits/<design>.toml\nlimits derived per design", "limits 檔\nsignoff/limits/<design>.toml\n每個設計自己推導的門檻")),
        ("golden", GREY, L("golden metrics\nsignoff/golden/<design>/\n+ tolerance table", "golden metrics\nsignoff/golden/<design>/\n＋誤差表")),
        ("cs", BLUE, L("check_signoff.py\nlimits + golden compare", "check_signoff.py\nlimits 檔＋golden 比對")),
        ("csoc", BLUE, L("check_soc.py\nslew, Magic DRC vs SRAM alone\nIR sources, disconnected", "check_soc.py\nslew、Magic DRC 對 SRAM 單獨檢查\nIR 電壓源、disconnected")),
        ("crit", BLUE, L("review_criteria.py\nsettings really applied?\n+ human review (.md)", "review_criteria.py\n設定真的生效？\n＋人工 review（.md）")),
        ("prov", BLUE, L("provenance / run guard\ncommit = HEAD, clean tree", "版本追溯／run guard\ncommit = HEAD、working tree 乾淨")),
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
        ("cause", ORANGE, L("2  Root cause\nverified (experiment) or\nmarked as speculation", "2  找出原因\n已驗證（實驗）或\n標明推測")),
        ("exp", GREY, L("3  Skill experience record\ndate, run, message,\ncause, fix, evidence", "3  skill 經驗紀錄\n日期、run、原文訊息、\n原因、處理、證據")),
        ("rule", BLUE, L("4  Skill rule\n(seen twice or verified)\nsymptom also in description", "4  skill 規則\n（出現兩次或已驗證）\n症狀也寫進 description")),
        ("guard", PURPLE, L("5  Guard\nchecker + negative test\nor 'no automatic guard' + why", "5  自動檢查\nchecker＋negative test\n或寫明「沒有自動檢查」與原因")),
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
                        "middle-end-flow（入口）：RTL 到 netlist、SDC、macro 準備、EQY")),
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

# ---------------------------------------------------------------------------
# 7. Overview flow (report §1)
# Overview RTL-to-GDS data-flow diagram for report §1 (name: overview_flow).
#
# Same format as docs/report/figures/scripts/diagrams.py (ROADMAP / FLOW / SOC): a dict with name, title,
# _note, rows, ranksep, clusters, nodes, links; drawn by diagrams.build()/main() with the
# arvinsa-draw-diagram engine. Unlike FLOW (figure in §4.1: nine boxes, steps and checkers), this one
# shows each step's tool and the files that pass between steps.
#
# Layout notes (found by trial, engine.py has no ordering option):
# - the order inside a row comes from graphviz, not from the order written in "rows"; the engine links the
#   middle entry (index len//2) of each row to the next row's middle entry with a heavy invisible edge, so
#   the middle entries chosen here (rtl, rtlv, synth, rt, chk, caravel) end up as the left column;
# - edges between stages that sit in different clusters are drawn cluster-to-cluster (inp -> ll, ll -> so,
#   so -> chip); per-node edges there pulled the last node of a row to the left;
# - landscape on purpose: docs/report PDF builds give a figure 100 % page width only when height/width <= 0.8.
OVERVIEW = {
    "name": "overview_flow",
    "title": L("arvinsa-rtl-gds: complete RTL-to-GDS flow (tools and files)",
               "arvinsa-rtl-gds：完整 RTL-to-GDS 流程（工具與檔案）"),
    "_note": (
        "Steps and order: arvinsa-rtl-gds-flow.md §3 (tree) and §4.0-4.8. LibreLane steps: "
        ".tools/librelane/librelane/flows/classic.py Steps (lines 40-121); Yosys.EQY is in the list but "
        "RUN_EQY defaults to False (line 255), so EQY runs as the repo's make eqy-soc / eqy-caravel. "
        "pnr/user_project_wrapper/config.json and pnr/soc_top/config*.json: meta.flow = Classic, "
        "substituting_steps OpenROAD.CTS -> Arvinsa.CTSNoInsertionDelay (pnr/librelane_plugin_arvinsa/__init__.py, "
        "ADR-0016); STA_CORNERS = 5 PVT x nom/min/max RC = 15; PRIMARY_GDSII_STREAMOUT_TOOL klayout. "
        "OpenROAD.RCX writes one SPEF per RCX_RULESETS corner (librelane/steps/openroad.py class RCX); "
        "OpenROAD.STAPostPNR writes SDF, no SDF timing simulation was done (report Phase 4, plan L5). "
        "Fill = fill/decap cells (OpenROAD.FillInsertion); no metal fill (README Phase 7). "
        "Repo checkers after LibreLane: pnr/soc_top/run.sh -> check_signoff.py, check_soc.py, check_inputs.py "
        "--resolved, ir_worst.py, provenance.py --verify, review_criteria.py (flow doc §4.6); check_inputs.py "
        "before LibreLane (flow doc §4.6). EQY / gate-level / IR from the pads: Makefile eqy-caravel, gl-caravel, "
        "ir-caravel (lines 192-212), flow doc §4.7; IR limit 20 mV (README Phase 7). Regressions: "
        "scripts/regress.py TARGET_LISTS, flow doc §4.8. Precheck: Makefile precheck-caravel (line 259), "
        "report §2 (cf-precheck 1.3.7, lima VM), README Phase 7 (PASS). Not taped out: ADR-0019 decision 1. "
        "SRAM: flow doc §4.3, ADR-0018, CLAUDE.md rule 12 (view QA). pad / block / pin plan: CLAUDE.md rule 14, "
        "make pin-plan (Makefile line 473)."
    ),
    "rows": "pdk,spec,rtl,pin|sram,rtlv|fp,pl,synth,cts|rcx,sta,rt,gds|eqy,gl,chk,ir|precheck,tape,caravel,regress",
    "ranksep": "0.25",
    "extra": ["--no-concentrate", "--row-minlen", "1"],
    "clusters": [
        ("inp", GREY, L("Inputs", "輸入")),
        ("ll", GREEN, L("LibreLane 3.0.14 Classic flow (make harden)",
                        "LibreLane 3.0.14 Classic flow（make harden）")),
        ("so", TEAL, L("Repo signoff and netlist verification", "repo 自己的 signoff 與 netlist 驗證")),
        ("chip", RED, L("Chip level and tapeout", "晶片層級與下線")),
    ],
    "nodes": [
        # ---- inputs (rtl first: the inputs -> LibreLane edge leaves the inputs box next to it, on the left)
        ("rtl", BLUE, L("RTL and firmware\nHazard3 / PicoRV32 SoC\nfw: gcc → boot ROM, tests",
                        "RTL 與 firmware\nHazard3／PicoRV32 SoC\nfw：gcc → boot ROM、測試"), "inp"),
        ("pin", GREY, L("pad / block / pin plan\npin_plan.toml\nuser-approved",
                        "pad／block／pin 規劃\npin_plan.toml\n使用者核准"), "inp"),
        ("pdk", GREY, L("PDK sky130A\nsky130_fd_sc_hd std cells\n.lib, LEF, GDS, rule decks",
                        "PDK sky130A\nsky130_fd_sc_hd 標準元件\n.lib、LEF、GDS、規則 deck"), "inp"),
        ("spec", GREY, L("Spec and constraints\nproject-plan.md, ADRs\nSDC, signoff limits",
                         "規格與 constraint\nproject-plan.md、ADR\nSDC、signoff 門檻"), "inp"),
        # ---- before the first harden
        ("sram", ORANGE, L("SRAM macro: OpenRAM → GDS, LEF\nngspice → .lib for 5 PVTs\nview QA (check_macro_views.py)",
                           "SRAM macro：OpenRAM → GDS、LEF\nngspice characterization → 5 個 PVT 的 .lib\nview QA（check_macro_views.py）")),
        ("rtlv", BLUE, L("RTL verification\nVerilator lint, Yosys synth check\nIcarus + Verilator self-checking tests\nevery injected bug must FAIL",
                         "RTL 驗證：Verilator lint、Yosys 合成檢查\nIcarus＋Verilator self-checking 測試\n植入的錯誤都必須 FAIL")),
        # ---- LibreLane
        ("synth", GREEN, L("1 Synthesis (Yosys)\n→ synthesized netlist .v",
                           "1 合成（Yosys）\n→ 合成 netlist .v"), "ll"),
        ("fp", GREEN, L("2 Floorplan, macros, PDN\nOpenROAD → ODB / DEF",
                        "2 floorplan、macro placement、PDN\nOpenROAD → ODB／DEF"), "ll"),
        ("pl", GREEN, L("3 Placement + resizer\nOpenROAD, slew/cap repair",
                        "3 placement＋resizer\nOpenROAD，修 slew／cap"), "ll"),
        ("cts", GREEN, L("4 CTS (repo plugin), repair\nArvinsa.CTSNoInsertionDelay",
                         "4 CTS（repo 的 plugin）＋時序修復\nArvinsa.CTSNoInsertionDelay"), "ll"),
        ("rt", GREEN, L("5 Global / detailed routing\nantenna repair, fill cells\n→ ODB / DEF, final netlist",
                        "5 global／detailed routing\nantenna 修補、fill cell\n→ ODB／DEF、最終 netlist"), "ll"),
        ("rcx", GREEN, L("6 RC extraction (OpenRCX)\n→ SPEF (3 RC corners)",
                         "6 RC 萃取（OpenRCX）\n→ SPEF（3 種 RC）"), "ll"),
        ("sta", GREEN, L("7 STA: 15 corners\nOpenSTA; IR: PSM\n→ timing reports, SDF",
                         "7 STA：15 個 corner\nOpenSTA；IR：PSM\n→ 時序報表、SDF"), "ll"),
        ("gds", GREEN, L("8 GDS out\nMagic, KLayout → GDS, LEF\nDRC, XOR, LVS (Netgen)",
                         "8 GDS 輸出\nMagic、KLayout → GDS、LEF\nDRC、XOR、LVS（Netgen）"), "ll"),
        # ---- repo signoff
        ("chk", TEAL, L("check_signoff.py: limits, golden\ncheck_soc.py, run guard\nreview_criteria.py",
                        "check_signoff.py：limits 檔、golden\ncheck_soc.py、run guard\nreview_criteria.py"), "so"),
        ("eqy", TEAL, L("EQY equivalence\nsynthesized == final netlist\n(make eqy-soc)",
                        "EQY 等價證明\n合成 netlist ≡ 最終 netlist\n（make eqy-soc）"), "so"),
        ("gl", TEAL, L("Gate-level simulation: RTL\nvs final netlist, every cycle\nalso the powered netlist",
                       "gate-level 模擬：RTL 與\n最終 netlist 每個 cycle 比對\n也跑 PG netlist"), "so"),
        ("ir", TEAL, L("IR: max-power pattern\nwrapper: from the Caravel pads\nlimit 20 mV",
                       "IR：max power pattern\nwrapper 從 Caravel pad 起算\n上限 20 mV"), "so"),
        # ---- regression, chip level
        ("caravel", RED, L("Caravel integration: wrapper\nsame flow run again",
                           "Caravel 整合：wrapper\n同一條流程再跑一次"), "chip"),
        ("precheck", RED, L("ChipFoundry precheck\ncf-precheck 1.3.7: PASS",
                            "ChipFoundry precheck\ncf-precheck 1.3.7：PASS"), "chip"),
        ("tape", GREY, L("Tapeout\nnot done in this project",
                         "下線（tapeout）\n本專案沒有做"), "chip"),
        ("regress", PURPLE, L("One-command regression (3)\nRTL verification → IR / precheck\nclean worktree only",
                              "一鍵 regression（3 條）\n依序跑 RTL 驗證 → IR／precheck\n只認乾淨 worktree")),
    ],
    "links": [
        ("rtl", "rtlv"), ("rtlv", "ll"), ("sram", "fp"), ("inp", "ll"),
        ("synth", "fp"), ("fp", "pl"), ("pl", "cts"), ("cts", "rt"), ("rt", "rcx"), ("rcx", "sta"), ("sta", "gds"),
        ("ll", "so"), ("chk", "eqy"), ("eqy", "gl"), ("gl", "ir"),
        ("so", "chip"), ("caravel", "precheck"), ("precheck", "tape"),
    ],
}


# ---------------------------------------------------------------------------
# 8. Caravel clock, reset and user-area supply (report §3.4)
# Caravel clock, reset and user-area supply paths, from the pads to this design (name: caravel_clock_power).
#
# Same format as docs/report/figures/scripts/diagrams.py (ROADMAP / FLOW / SOC): a dict with name, title,
# _note, rows, ranksep, clusters, nodes, links; drawn by diagrams.build()/main() with the
# arvinsa-draw-diagram engine. Rows go from the outside in: pads, the management area (plus Caravel's
# supply network around the wrapper), the wrapper. Node colours follow the path, as the title says:
# blue = clock, orange = reset, purple = blocks both pass through, red = vccd1 / vssd1 supply,
# grey = Caravel blocks that only set things up or share the signals, green = this design.
# The title ends each line with a literal \l (graphviz: left-justified line) so both lines start at the left.
# user_clock2 is listed in the mgmt_protect box (not used by this design) instead of a node of its own.
#
# Caravel = caravel-lite tag 2024.09.12-1 (commit 5593d992), from /opt/caravel of the precheck image
# chipfoundry/mpw_precheck; paths below are relative to it (how to get it: figures/SOURCES.md).
#
# Cluster labels are left-justified by the engine. Leading no-break spaces move three of them clear of
# the edges that cross the cluster top (checked on the rendered PNGs; re-check after any layout change).
NB = "\u00a0"
WRAP_PAD = NB * 40

CARAVEL_IO = {
    "name": "caravel_clock_power",
    "title": L("Caravel clock, reset and user-area supply, from the pads to this design\\l"
               "blue: clock; orange: reset; purple: both pass through; red: vccd1 / vssd1 supply;\\l"
               "grey: other Caravel blocks; green: this design\\l",
               "Caravel 的 clock、reset 與 user area 供電：從 pad 到本設計\\l"
               "藍：clock；橘：reset；紫：兩者都經過；紅：vccd1／vssd1 電源；灰：其他 Caravel 電路；綠：本設計\\l"),
    "_note": (
        "Caravel = caravel-lite 2024.09.12-1 (5593d992). "
        "clock pad: verilog/rtl/caravel.v line 57 (CMOS core clock input, not a crystal), chip_io.v line 288; "
        "pad positions: def/chip_io.def COMPONENTS (clock_pad, resetb_pad on the bottom edge; "
        "user1_vccd_lvclamp_pad lines 17057-17058, user1_vssd_lvclamp_pad lines 16653-16654, right edge). "
        "clock_core -> caravel_clocking ext_clk and digital_pll osc: caravel_core.v lines 525, 546. "
        "Power-up: housekeeping.v lines 1040-1041 pll_ena <= 0, pll_bypass <= 1; pll_bypass = ext_clk_sel "
        "(caravel_core.v lines 524, 594); caravel_clocking.v lines 93-95 core_clk = ext_clk until use_pll_second, "
        "then pll_clk_divided (clock_div, lines 70-79; divider sel reset 3'b010 'divide-by-2', housekeeping.v line 1036). "
        "PLL registers 0x08/0x09/0x11/0x12: housekeeping.v lines 1097-1131. "
        "core_clk -> caravel_clk -> management SoC (caravel_core.v lines 281, 532) and mgmt_protect; "
        "user_clock = caravel_clk & mprj_logic1[1], user_clock2 = caravel_clk2 & mprj_logic1[2], "
        "user_reset = ~caravel_rstn & mprj_logic1[0] (mgmt_protect.v lines 232-234); mprj_logic1 = vccd1 logic high "
        "(mgmt_protect.v lines 122-128); wb_clk_i / wb_rst_i / user_clock2 of mprj: caravel_core.v lines 408-410, 443-444, 468. "
        "resetb: XRES pad with glitch filter, pull-up enabled (chip_io.v lines 301-304, 318); xres_buf 3.3 V -> 1.8 V "
        "(caravel_core.v lines 1390-1399, xres_buf.v lines 16-19); simple_por about 15 ms (simple_por.v lines 35-45); "
        "resetb_async = porb & resetb & !ext_reset (caravel_clocking.v line 51); 3-bit delay on negedge core_clk, "
        "resetb_sync high on the 3rd falling edge (lines 101-112); ext_reset = housekeeping reset register 0x0b "
        "(housekeeping.v lines 1043, 1107-1108). "
        "This design: CLOCK_PORT wb_clk_i, CLOCK_PERIOD 44 (pnr/user_project_wrapper/config.json lines 53-55); "
        "soc_top clk = wb_clk_i, resetn = ~wb_rst_i, vccd1 / vssd1 (rtl/caravel/user_project_wrapper.v lines 125-129); "
        "user_clock2 unused (line 175). "
        "Supply: vccd1 / vssd1 one pad each, right edge, about 2.2 mm apart; Caravel's 5 um met4 ring; met3 bridges of "
        "manual_power_connections.lef on the left and right sides of the wrapper ring only, 54 left / 53 right per net "
        "(.claude/skills/caravel-user-project-integration/SKILL.md rule 3 line 27; "
        "pnr/user_project_wrapper/caravel_pwr/README.md lines 13, 20; ADR-0019 line 82). "
        "IR from the pads 19.56 mV, limit 20 mV (README.md line 56)."
    ),
    "rows": "clk_pad,rst_pad,pwr_pad|hk,pll,xres,ring|por,clocking,bridge|cpu,prot|wring,soc",
    "ranksep": "0.3",
    "extra": ["--no-concentrate", "--row-minlen", "1"],
    "clusters": [
        ("pads", GREY, L("padframe (pads on the chip edge)", "padframe（晶片邊緣的 pad）")),
        ("mgmt", GREY, L(NB * 105 + "Caravel management area (fixed)", NB * 30 + "Caravel management area（固定）")),
        ("pnet", RED, L(NB * 8 + "Caravel supply network", "Caravel 在 wrapper 外圍的供電網路")),
        ("wrap", BLUE, L(WRAP_PAD + "user_project_wrapper", WRAP_PAD + "user_project_wrapper")),
    ],
    "nodes": [
        # ---- pads
        ("clk_pad", BLUE, L("clock pad (bottom edge)\nexternal CMOS clock input",
                            "clock pad（下側）\n外部 CMOS 時脈輸入"), "pads"),
        ("rst_pad", ORANGE, L("resetb pad (bottom edge)\nactive low, 3.3 V XRES pad\nglitch filter, pull-up",
                              "resetb pad（下側）\n低電位有效、3.3 V XRES pad\n內建 glitch filter 與上拉"), "pads"),
        ("pwr_pad", RED, L("vccd1 / vssd1 pads\nonly one each, right edge\n(about 2.2 mm apart)",
                           "vccd1／vssd1 pad\n右側各只有一顆\n（相距約 2.2 mm）"), "pads"),
        # ---- management area
        ("pll", BLUE, L("PLL (digital_pll)\nreference = clock pad", "PLL（digital_pll）\n參考時脈 = clock pad"), "mgmt"),
        ("hk", GREY, L("housekeeping registers\npower-up: PLL off, bypass\nfirmware turns the PLL on\nreset register: ext_reset",
                       "housekeeping 暫存器\n開機：PLL 關、bypass\n韌體寫暫存器啟用 PLL\nreset 暫存器：ext_reset"), "mgmt"),
        ("xres", ORANGE, L("xres_buf\n3.3 V -> 1.8 V", "xres_buf\n3.3 V → 1.8 V"), "mgmt"),
        ("por", ORANGE, L("simple_por\npower-on reset (about 15 ms) -> porb", "simple_por\n上電重置 POR（約 15 ms）→ porb"), "mgmt"),
        ("clocking", PURPLE, L("caravel_clocking\ncaravel_clk: ext_clk at power-up;\nPLL output / clock_div once enabled\n"
                               "resetb_async = porb & resetb & !ext_reset\ncaravel_rstn: released on the 3rd falling edge",
                               "caravel_clocking\ncaravel_clk：開機時 = ext_clk；\nPLL 啟用後 = PLL 經 clock_div 除頻\n"
                               "resetb_async = porb & resetb & !ext_reset\ncaravel_rstn：放開時對齊第 3 個下降緣"), "mgmt"),
        ("cpu", GREY, L("management SoC (VexRiscv CPU)\nsame caravel_clk and caravel_rstn",
                        "management SoC（VexRiscv CPU）\n用同一組 caravel_clk 與 caravel_rstn"), "mgmt"),
        ("prot", PURPLE, L("mgmt_protect: AND with vccd1-side 1\nwb_clk_i = caravel_clk\nwb_rst_i = ~caravel_rstn (active high)\n"
                           "user_clock2 = caravel_clk2 (not used here)",
                           "mgmt_protect：AND 上 vccd1 區的 1\nwb_clk_i = caravel_clk\nwb_rst_i = ~caravel_rstn（高電位有效）\n"
                           "user_clock2 = caravel_clk2（本設計未用）"), "mgmt"),
        # ---- supply network
        ("ring", RED, L("Caravel met4 ring\n5 um wide, around the wrapper", "Caravel 的 met4 ring\n5 µm 寬，繞在 wrapper 外圍"), "pnet"),
        ("bridge", RED, L("met3 bridges\nleft and right sides only\n54 left, 53 right per net",
                          "met3 電源連接線\n只在 wrapper 左右兩側\n每個 net 左 54、右 53 條"), "pnet"),
        # ---- wrapper
        ("soc", GREEN, L("soc_top (this design)\nclk = wb_clk_i, period 44 ns\nresetn = ~wb_rst_i\nIR from the pads 19.56 mV (limit 20 mV)",
                         "soc_top（本設計）\nclk = wb_clk_i，週期 44 ns\nresetn = ~wb_rst_i\nIR 從 pad 起算 19.56 mV（上限 20 mV）"), "wrap"),
        ("wring", RED, L("wrapper core ring\nvccd1 / vssd1", "wrapper core ring\nvccd1／vssd1"), "wrap"),
    ],
    "links": [
        ("clk_pad", "pll"), ("clk_pad", "clocking"), ("pll", "clocking"), ("hk", "pll"), ("hk", "clocking"),
        ("rst_pad", "xres"), ("xres", "clocking"), ("por", "clocking"),
        ("clocking", "cpu"), ("clocking", "prot"), ("prot", "soc"),
        ("pwr_pad", "ring"), ("ring", "bridge"), ("bridge", "wring"), ("wring", "soc"),
    ],
}


GRAPHS = [ROADMAP, FLOW, SOC, CHECK, LOOP, SKILLMAP, OVERVIEW, CARAVEL_IO]


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
