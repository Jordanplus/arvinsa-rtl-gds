# arvinsa-rtl-gds top-level entry. Compatible with GNU make 3.81 (macOS default):
# recipes do not use pipes; strict error handling lives in the called scripts.
# Contract for every target: docs/spec/soc_spec.md §8.
SHELL := /bin/bash
.DELETE_ON_ERROR:

TEST ?= hello
SIM  ?= icarus
SIMS ?= icarus,verilator
PY   ?= python3
DRY_RUN ?= 0

.PHONY: help nix-install flow-setup pdk-fetch ci-sram-ref env-check env-check-flow lint synth-check fw sim regress-rtl regress-rtl-smoke \
        neg-rtl core-stock smoke phase1 harden-core gl-core neg-gl-core soc-area phase2 \
        eqy-core neg-eqy-core harden-soc eqy-soc neg-eqy-soc gl-soc neg-gl-soc neg-pnr neg-provenance test-flow-retry phase3 clean

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
	@echo "  make smoke                env-check lint fw regress-rtl-smoke"
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
	@echo "  make neg-pnr              bug injection P01-P20 (STA, PDN, DRC, XOR, placement, inputs, ...), each must FAIL at its checker"
	@echo "  make neg-provenance       bug injection into the source tracking (uncommitted files, wrong LibreLane/PDK, ...)"
	@echo "  make test-flow-retry      the GRT-0229 retry in pnr/librelane_flow.sh, with a mocked LibreLane"
	@echo "  make phase3               full Phase 3 exit check (env-check-flow neg-provenance test-flow-retry harden-soc eqy-soc neg-eqy-soc"
	@echo "                            gl-soc neg-gl-soc neg-pnr harden-core eqy-core neg-eqy-core); needs a committed working tree"
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

smoke: env-check lint fw regress-rtl-smoke

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

gl-soc:
	$(PY) dv/gl_soc/run_gl_soc.py

neg-gl-soc:
	$(PY) dv/gl_soc/neg_gl_soc.py

neg-pnr:
	$(PY) pnr/soc_top/neg_pnr.py

neg-provenance:
	$(PY) signoff/scripts/neg_provenance.py

test-flow-retry:
	bash pnr/test_librelane_flow.sh

# harden-core is re-run so that eqy-core checks a run with source tracking (result.txt).
phase3: env-check-flow neg-provenance test-flow-retry harden-soc eqy-soc neg-eqy-soc gl-soc neg-gl-soc neg-pnr harden-core eqy-core neg-eqy-core

# Removes Phase 1 sim/firmware outputs only. LibreLane outputs (runs/flow_setup, runs/ci_sram_ref, runs/picorv32_core, runs/soc_top)
# take tens of minutes to regenerate and are kept; delete them by hand when needed.
clean:
	rm -rf runs/sim runs/neg runs/sim_build runs/core_stock runs/rtl sim_build fw/build obj_dir
