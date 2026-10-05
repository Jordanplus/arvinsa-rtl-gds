# arvinsa-rtl-gds top-level entry. Compatible with GNU make 3.81 (macOS default):
# recipes do not use pipes; strict error handling lives in the called scripts.
# Contract for every target: docs/spec/soc_spec.md §8.
SHELL := /bin/bash
.DELETE_ON_ERROR:
# The targets share run directories (runs/soc_top, runs/picorv32_core, ...) and remove them at the
# start; `make -j` would let one target delete what another is using. Always run in order.
.NOTPARALLEL:

TEST ?= hello
SIM  ?= icarus
SIMS ?= icarus,verilator
PY   ?= python3
DRY_RUN ?= 0

.PHONY: help nix-install flow-setup pdk-fetch ci-sram-ref env-check env-check-flow lint synth-check fw sim regress-rtl regress-rtl-smoke \
        neg-rtl core-stock smoke phase1 harden-core gl-core neg-gl-core soc-area phase2 \
        eqy-core neg-eqy-core harden-soc eqy-soc neg-eqy-soc gl-soc neg-gl-soc neg-pnr neg-provenance test-flow-retry phase3 \
        neg-run-guard gl-soc-powered provenance-final harden regress py-check skill-check neg-regress clean \
        sram-lib sram-char sram-extract neg-char

help:
	@echo "Phase 0 environment (run in your own terminal):"
	@echo "  make nix-install          install Nix + FOSSi cache (asks for admin password; DRY_RUN=1 to preview)"
	@echo "  make flow-setup           fetch LibreLane (pinned tag), nix-shell smoke test, download sky130A"
	@echo "  make pdk-fetch            download sky130A tarballs (parallel, resumable, sha256) and install with ciel"
	@echo "  make ci-sram-ref          re-run LibreLane CI test_sram_macro, check signoff items + local golden"
	@echo ""
	@echo "Phase 1 targets (see docs/spec/soc_spec.md §8):"
	@echo "  make env-check            check local tools and pinned IP"
	@echo "  make env-check-flow       also require Nix/LibreLane/PDK (Phase 0 flow env)"
	@echo "  make lint                 Verilator lint (L0)"
	@echo "  make synth-check          local Yosys sanity synthesis"
	@echo "  make fw                   build firmware + check generated boot ROM"
	@echo "  make sim TEST=hello SIM=icarus|verilator"
	@echo "  make regress-rtl          all positive tests on Icarus and Verilator (L1b)"
	@echo "  make regress-rtl-smoke    smoke subset on Icarus"
	@echo "  make neg-rtl              bug injection (all dv/bugs.toml entries), each must FAIL at its checker"
	@echo "  make core-stock           upstream PicoRV32 tests (L1a)"
	@echo "  make smoke                env-check py-check skill-check lint fw regress-rtl-smoke"
	@echo "  make phase1               full Phase 1 exit check"
	@echo ""
	@echo "Phase 2 targets (PicoRV32 hardened alone, see pnr/picorv32_core/README.md):"
	@echo "  make harden-core          LibreLane on picorv32 with the SoC CPU parameters, check signoff limits + golden"
	@echo "  make gl-core              upstream PicoRV32 tests on the hardened netlist vs RTL (GL ISA regression)"
	@echo "  make neg-gl-core          bug injection into the hardened netlist, gl-core must FAIL on each"
	@echo "  make soc-area             estimate soc_top stdcell area from the hardened core (DIE_AREA input)"
	@echo "  make phase2               full Phase 2 exit check (env-check-flow harden-core gl-core neg-gl-core soc-area)"
	@echo ""
	@echo "Phase 3 targets (soc_top with the SRAM macro, see pnr/soc_top/README.md, signoff/eqy/README.md):"
	@echo "  make eqy-core             formal equivalence: synthesized vs final netlist of make harden-core (EQY)"
	@echo "  make neg-eqy-core         bug injection into the hardened core netlist, eqy-core must FAIL on each"
	@echo "  make harden-soc           LibreLane on soc_top with the SRAM macro, check signoff limits + golden + soc checks"
	@echo "                            (harden-core and harden-soc PASS only from a committed working tree: source tracking)"
	@echo "  make eqy-soc              formal equivalence: synthesized vs final netlist of make harden-soc (EQY)"
	@echo "  make neg-eqy-soc          bug injection into the hardened soc_top netlist, eqy-soc must FAIL on each"
	@echo "  make gl-soc               SoC tests with the RTL and the final netlist in lockstep (gate-level simulation)"
	@echo "  make neg-gl-soc           bug injection into the hardened soc_top netlist, gl-soc must FAIL on each (lockstep)"
	@echo "  make neg-pnr              bug injection P00-P32 (STA, PDN, IR, DRC, XOR, placement, inputs, ...), each must FAIL at its checker"
	@echo "  make neg-provenance       bug injection into the source tracking (uncommitted files, edited LibreLane/PDK, ...)"
	@echo "  make neg-run-guard        the steps that use a harden run must refuse a FAILed run or one from another commit"
	@echo "  make test-flow-retry      the GRT-0229 retry in pnr/librelane_flow.sh, with a mocked LibreLane"
	@echo "  make phase3               full Phase 3 exit check (env-check-flow neg-provenance test-flow-retry harden-soc eqy-soc neg-eqy-soc"
	@echo "                            gl-soc neg-gl-soc neg-pnr harden-core eqy-core neg-eqy-core); needs a committed working tree"
	@echo ""
	@echo "Phase 4 targets (signoff closure, see docs/phase_exit/phase4.md):"
	@echo "  make regress              EVERYTHING in one command, in order, stops at the first FAIL (about 2.5 hours):"
	@echo "                            Phase 1 RTL checks, flow checkers, soc_top (harden, EQY, GL, L5, negative tests),"
	@echo "                            PicoRV32 alone, provenance-final; logs, summary.md and junit.xml in runs/regress/"
	@echo "  make gl-soc-powered       L5: the powered netlist (final/pnl) in lockstep with the RTL, cells powered by VPWR/VGND"
	@echo "  make provenance-final     HEAD and working tree unchanged since harden-soc and harden-core started"
	@echo "  make py-check             every name a tracked Python file reads is defined in that file (seconds, not at runtime)"
	@echo "  make skill-check          every .claude/skills/*/SKILL.md has a valid header and is listed in README.md"
	@echo "  make neg-regress          make regress must refuse a dirty tree, make -i, a HEAD that changes, and stop at a FAIL"
	@echo "  make harden D=soc_top|picorv32_core   same as harden-soc / harden-core"
	@echo ""
	@echo "Phase 3.5 targets (SRAM timing from SPICE, ADR-0010, ip/sram/char/README.md; need ngspice):"
	@echo "  make sram-lib             regenerate the five SRAM .lib from $(SRAM_CHAR)/char.json (seconds)"
	@echo "  make neg-char             bug injection into the characterization N1-N8, each must be caught (about 40 minutes)"
	@echo "  make sram-char            ngspice characterization of the SRAM: tt, then the other four PVTs seeded from tt,"
	@echo "                            into $(SRAM_CHAR)/char.json, then sram-lib (hours; not part of make regress)"
	@echo "  make sram-extract         Magic extraction of the SRAM GDS with wire capacitances (about 30 minutes)"
	@echo ""
	@echo "  make clean                remove Phase 1 sim/firmware outputs (keeps LibreLane runs)"

nix-install:
	DRY_RUN=$(DRY_RUN) bash env/install_nix.sh

flow-setup:
	bash env/setup_flow.sh

pdk-fetch:
	bash env/fetch_pdk.sh

ci-sram-ref:
	bash pnr/ci_sram_ref/run.sh

env-check:
	bash env/check_env.sh

env-check-flow:
	bash env/check_env.sh --flow

lint:
	bash rtl/scripts/lint.sh

synth-check:
	bash rtl/scripts/synth_check.sh

fw:
	$(MAKE) -C fw all check-bootrom

sim: fw
	$(PY) dv/scripts/run_sim.py --test $(TEST) --sim $(SIM)

regress-rtl: fw
	$(PY) dv/scripts/regress.py --sims $(SIMS) --suite all

regress-rtl-smoke: fw
	$(PY) dv/scripts/regress.py --sims icarus --suite smoke

neg-rtl: fw
	$(PY) dv/scripts/neg.py

core-stock:
	bash scripts/core_stock.sh

smoke: env-check py-check skill-check lint fw regress-rtl-smoke

phase1: env-check lint synth-check fw core-stock regress-rtl neg-rtl

harden-core:
	bash pnr/picorv32_core/run.sh

gl-core:
	$(PY) dv/gl_core/run_gl_core.py

neg-gl-core:
	$(PY) dv/gl_core/neg_gl_core.py

soc-area:
	$(PY) scripts/soc_area_estimate.py

phase2: env-check-flow harden-core gl-core neg-gl-core soc-area

eqy-core:
	$(PY) signoff/eqy/run_eqy.py --design picorv32_core

neg-eqy-core:
	$(PY) signoff/eqy/neg_eqy.py --design picorv32_core

harden-soc:
	bash pnr/soc_top/run.sh

eqy-soc:
	$(PY) signoff/eqy/run_eqy.py --design soc_top

neg-eqy-soc:
	$(PY) signoff/eqy/neg_eqy.py --design soc_top

gl-soc: fw
	$(PY) dv/gl_soc/run_gl_soc.py

neg-gl-soc: fw
	$(PY) dv/gl_soc/neg_gl_soc.py

neg-pnr:
	$(PY) pnr/soc_top/neg_pnr.py

neg-provenance:
	$(PY) signoff/scripts/neg_provenance.py

neg-run-guard:
	$(PY) signoff/scripts/neg_run_guard.py

gl-soc-powered: fw
	$(PY) dv/gl_soc/run_gl_soc.py --powered

provenance-final:
	$(PY) signoff/scripts/provenance.py --final runs/soc_top_signoff/provenance.json runs/picorv32_core_signoff/provenance.json

# project-plan.md §7.5 `make harden D=<design>`; the run tag stays the design name (runs/<design>), and
# the commit of a run is in runs/<design>_signoff/provenance.json, which every later step compares
# with HEAD (signoff/scripts/run_guard.py), instead of a tag per git sha.
harden:
	@case "$(D)" in soc_top) $(MAKE) harden-soc ;; picorv32_core) $(MAKE) harden-core ;; \
	  *) echo "harden: FAIL - D must be soc_top or picorv32_core (got '$(D)')"; exit 1 ;; esac

# SRAM SPICE characterization (Phase 3.5, ADR-0010). char.json and the five .lib are committed;
# make harden-soc checks the .lib against char.json (pnr/soc_top/check_inputs.py char_lib).
SRAM_CHAR = ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char
SRAM_PDK_LIB = $${PDK_ROOT:-$$HOME/.ciel}/sky130A/libs.ref/sky130_sram_macros/lib/sky130_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib

sram-lib:
	$(PY) ip/sram/char/gen_char_lib.py $(SRAM_CHAR)/char.json "$(SRAM_PDK_LIB)" $(SRAM_CHAR)

neg-char:
	$(PY) ip/sram/char/neg_char.py

sram-extract:
	$(PY) ip/sram/char/extract_sram.py

sram-char:
	$(PY) ip/sram/char/characterize.py $(SRAM_CHAR)/char.json --pvt tt_025C_1v80
	$(PY) ip/sram/char/characterize.py $(SRAM_CHAR)/char.json --seed $(SRAM_CHAR)/char.json \
	  --pvt ss_100C_1v60 ff_n40C_1v95 ss_n40C_1v60 ff_100C_1v95
	$(MAKE) sram-lib

# The whole regression (scripts/regress.py lists the targets and their order).
regress:
	$(PY) scripts/regress.py

py-check:
	$(PY) scripts/check_py_names.py

skill-check:
	$(PY) scripts/check_skills.py

neg-regress:
	$(PY) scripts/neg_regress.py

test-flow-retry:
	bash pnr/test_librelane_flow.sh

# harden-core is re-run so that eqy-core checks a run with source tracking (result.txt).
phase3: env-check-flow neg-provenance test-flow-retry harden-soc eqy-soc neg-eqy-soc gl-soc neg-gl-soc neg-pnr harden-core eqy-core neg-eqy-core

# Removes Phase 1 sim/firmware outputs only. LibreLane outputs (runs/flow_setup, runs/ci_sram_ref, runs/picorv32_core, runs/soc_top)
# take tens of minutes to regenerate and are kept; delete them by hand when needed.
clean:
	rm -rf runs/sim runs/neg runs/sim_build runs/core_stock runs/rtl sim_build fw/build obj_dir
