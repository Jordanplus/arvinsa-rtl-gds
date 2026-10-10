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
# CPU of soc_top for fw, sim, regress-rtl(-smoke), neg-rtl, harden-soc, eqy-soc, gl-soc and their
# negative tests: picorv32 (default) or hazard3 (Phase 5, ADR-0011). The soc_top LibreLane run of
# each CPU has its own tag: runs/soc_top (picorv32) and runs/soc_top_hazard3 (pnr/soc_top/run.sh).
CPU  ?= picorv32
SOC_TAG = $(if $(filter hazard3,$(CPU)),soc_top_hazard3,soc_top)
PY   ?= python3
DRY_RUN ?= 0

.PHONY: help nix-install flow-setup pdk-fetch xpack-fetch core-hazard3 ci-sram-ref env-check env-check-flow lint synth-check fw sim regress-rtl regress-rtl-smoke \
        neg-rtl core-stock smoke phase1 harden-core gl-core neg-gl-core soc-area phase2 \
        eqy-core neg-eqy-core harden-soc eqy-soc neg-eqy-soc gl-soc neg-gl-soc neg-pnr neg-provenance test-flow-retry phase3 \
        neg-run-guard gl-soc-powered provenance-final harden regress regress-picorv32 py-check skill-check neg-regress test-review-hook clean \
        sram-lib sram-confirm sram-char sram-extract neg-char openram-setup openram-macro neg-openram \
        openram-lib-template openram-char openram-power openram-lib openram-confirm openram-check-lib macro-views neg-macro-views

help:
	@echo "Phase 0 environment (run in your own terminal):"
	@echo "  make nix-install          install Nix + FOSSi cache (asks for admin password; DRY_RUN=1 to preview)"
	@echo "  make flow-setup           fetch LibreLane (pinned tag), nix-shell smoke test, download sky130A"
	@echo "  make pdk-fetch            download sky130A tarballs (parallel, resumable, sha256) and install with ciel"
	@echo "  make xpack-fetch          download the xPack riscv-none-elf-gcc (newlib) into .tools/ (byte ranges in parallel, resumable, sha256)"
	@echo "  make ci-sram-ref          re-run LibreLane CI test_sram_macro, check signoff items + local golden"
	@echo ""
	@echo "Phase 1 targets (see docs/spec/soc_spec.md §8):"
	@echo "  make env-check            check local tools and pinned IP"
	@echo "  make env-check-flow       also require Nix/LibreLane/PDK (Phase 0 flow env)"
	@echo "  make lint                 Verilator lint (L0)"
	@echo "  make synth-check          local Yosys sanity synthesis"
	@echo "  make fw                   build firmware + check generated boot ROM"
	@echo "  make sim TEST=hello SIM=icarus|verilator [CPU=picorv32|hazard3]  (CPU also for fw, regress-rtl, neg-rtl)"
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
	@echo "  make neg-pnr              bug injection P00-P62, 63 cases (STA, PDN, IR, worst-case IR, DRC, XOR, placement, inputs, SRAM .lib, weak cells, criteria review, CTS, ...), each must FAIL at its checker"
	@echo "  make neg-provenance       bug injection into the source tracking (uncommitted files, edited LibreLane/PDK, ...)"
	@echo "  make neg-run-guard        the steps that use a harden run must refuse a FAILed run or one from another commit"
	@echo "  make test-flow-retry      the GRT-0229 retry in pnr/librelane_flow.sh, with a mocked LibreLane"
	@echo "  make test-review-hook     the Claude Code Stop hook asking for the signoff criteria review after a harden"
	@echo "  make phase3               full Phase 3 exit check (env-check-flow neg-provenance test-flow-retry harden-soc eqy-soc neg-eqy-soc"
	@echo "                            gl-soc neg-gl-soc neg-pnr harden-core eqy-core neg-eqy-core); needs a committed working tree"
	@echo ""
	@echo "Phase 4 targets (signoff closure, see docs/phase_exit/phase4.md):"
	@echo "  make regress-picorv32     EVERYTHING for the PicoRV32 SoC in one command, in order, stops at the first FAIL (about"
	@echo "                            2.5 hours): Phase 1 RTL checks, flow checkers, soc_top (harden, EQY, GL, L5, negative"
	@echo "                            tests), PicoRV32 alone, provenance-final; logs, summary.md, junit.xml in runs/regress_picorv32/"
	@echo "                            (it was make regress until Phase 5)"
	@echo "  make gl-soc-powered       L5: the powered netlist (final/pnl) in lockstep with the RTL, cells powered by VPWR/VGND"
	@echo "  make provenance-final     HEAD and working tree unchanged since the harden runs of CPU started"
	@echo "                            (hazard3: harden-soc; picorv32: harden-soc and harden-core)"
	@echo "  make py-check             every name a tracked Python file reads is defined in that file, no file emptied before it is read (seconds)"
	@echo "  make skill-check          every .claude/skills/*/SKILL.md has a valid header and is listed in README.md"
	@echo "  make neg-regress          make regress must refuse a dirty tree, make -i, a HEAD that changes, and stop at a FAIL"
	@echo "  make harden D=soc_top|soc_top_hazard3|picorv32_core   same as harden-soc CPU=picorv32 / CPU=hazard3 / harden-core"
	@echo ""
	@echo "Phase 5 targets (Hazard3 replaces PicoRV32 as the main CPU, docs/decisions/0011-hazard3-integration.md):"
	@echo "  make regress              EVERYTHING for the Hazard3 SoC in one command, in order, stops at the first FAIL:"
	@echo "                            RTL checks, core-hazard3, flow checkers, soc_top with Hazard3 (harden, EQY, GL, L5,"
	@echo "                            negative tests), provenance-final; logs, summary.md and junit.xml in runs/regress/"
	@echo "                            (a clean worktree has no .tools/: set LIBRELANE_DIR and XPACK_DIR to installed copies)"
	@echo "  make core-hazard3         Hazard3 core: riscv-tests rv32ui/uc/um/mi on the SoC's configuration, and an"
	@echo "                            instruction-by-instruction comparison with the rvcpp ISS (needs make xpack-fetch)"
	@echo "  CPU=hazard3               for fw, sim, regress-rtl, neg-rtl, synth-check, harden-soc, eqy-soc, neg-eqy-soc,"
	@echo "                            gl-soc, gl-soc-powered, neg-gl-soc, neg-pnr, provenance-final (run tag soc_top_hazard3)"
	@echo ""
	@echo "Phase 3.5 targets (SRAM timing from SPICE, ADR-0010, ip/sram/char/README.md; need ngspice):"
	@echo "  make sram-lib             regenerate the five SRAM .lib from $(SRAM_CHAR)/char.json (seconds)"
	@echo "  make sram-confirm         simulate every setup/hold and clock pulse lane at the .lib values -> confirm.json (about 1 hour)"
	@echo "  make neg-char             bug injection into the characterization N1-N21, each must be caught (about 40 minutes)"
	@echo "  make sram-char            ngspice characterization of the SRAM: tt, then the other four PVTs seeded from tt,"
	@echo "                            into $(SRAM_CHAR)/char.json, then sram-lib and sram-confirm (hours; not part of make regress)"
	@echo "  make sram-extract         Magic extraction of the SRAM GDS with wire capacitances (about 30 minutes)"
	@echo ""
	@echo "Phase 6 targets (OpenRAM self-generated SRAM, ADR-0018, ip/sram/openram/README.md):"
	@echo "  make openram-setup         install the pinned OpenRAM, sky130_fd_bd_sram, OpenRAM's own PDK and a venv into .tools/"
	@echo "  make openram-macro OPENRAM_CONFIG=<cfg>  generate a macro, check OpenRAM's DRC/LVS (summary.json), the contents of every view (views.json), then the full-deck Magic DRC rule by rule against the prebuilt macro (macro_drc.json); about 45 min for 2 KB"
	@echo "  make macro-views          QA of the SRAM views the SoC uses: names, pins and directions agree in LEF/.lib/Verilog/SPICE, .lib numbers in range, area and GDS box = LEF SIZE (seconds)"
	@echo "  make neg-macro-views      bug injection into that QA, Q1-Q11 (seconds; part of make regress)"
	@echo "  make neg-openram          bug injection into the OpenRAM run, install, patch, macro DRC, .lib template and characterization provenance checkers O1-O8, I1-I4, T1-T3, D1-D3, L1-L2, C1-C2 (seconds; part of make regress)"
	@echo "  make openram-lib-template  the .lib template of $(OR_SRAM): OpenRAM's TT .lib with the PDK macro's internal_power values"
	@echo "  make openram-char          ngspice characterization of $(OR_SRAM) (tt, then four PVTs), then openram-lib and openram-confirm (hours)"
	@echo "  make openram-power         ngspice internal power and standby leakage of $(OR_SRAM), five PVTs on the untrimmed netlist, 3 runs at a time (about 4.2 GB each; several hours)"
	@echo "  make openram-lib           regenerate its five .lib from $(OR_SRAM_DIR)/char/char.json, with the measured power when char/power.json exists (seconds)"
	@echo "  make openram-confirm       simulate it at the .lib setup/hold and clock pulse values"
	@echo "  make openram-check-lib     independent recomputation of its .lib from char.json, provenance and confirm.json"
	@echo ""
	@echo "  make clean                remove Phase 1 sim/firmware outputs (keeps LibreLane runs)"

nix-install:
	DRY_RUN=$(DRY_RUN) bash env/install_nix.sh

flow-setup:
	bash env/setup_flow.sh

pdk-fetch:
	bash env/fetch_pdk.sh

xpack-fetch:
	bash env/fetch_xpack.sh

ci-sram-ref:
	bash pnr/ci_sram_ref/run.sh

env-check:
	bash env/check_env.sh

env-check-flow:
	bash env/check_env.sh --flow

lint:
	bash rtl/scripts/lint.sh

synth-check:
	CPU=$(CPU) bash rtl/scripts/synth_check.sh

fw:
	$(MAKE) -C fw CPU=$(CPU) all check-bootrom

sim: fw
	$(PY) dv/scripts/run_sim.py --test $(TEST) --sim $(SIM) --cpu $(CPU)

regress-rtl: fw
	$(PY) dv/scripts/regress.py --sims $(SIMS) --suite all --cpu $(CPU)

regress-rtl-smoke: fw
	$(PY) dv/scripts/regress.py --sims icarus --suite smoke --cpu $(CPU)

neg-rtl: fw
	$(PY) dv/scripts/neg.py --cpu $(CPU)

# Hazard3 core-level ISA regression (Phase 5, ADR-0011): riscv-tests on the SoC's configuration.
core-hazard3:
	$(PY) dv/core_hazard3/run.py

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
	CPU=$(CPU) bash pnr/soc_top/run.sh

eqy-soc:
	$(PY) signoff/eqy/run_eqy.py --design $(SOC_TAG)

neg-eqy-soc:
	$(PY) signoff/eqy/neg_eqy.py --design $(SOC_TAG)

gl-soc: fw
	$(PY) dv/gl_soc/run_gl_soc.py --cpu $(CPU)

neg-gl-soc: fw
	$(PY) dv/gl_soc/neg_gl_soc.py --cpu $(CPU)

neg-pnr:
	$(PY) pnr/soc_top/neg_pnr.py --cpu $(CPU)

neg-provenance:
	$(PY) signoff/scripts/neg_provenance.py

neg-run-guard:
	$(PY) signoff/scripts/neg_run_guard.py

gl-soc-powered: fw
	$(PY) dv/gl_soc/run_gl_soc.py --cpu $(CPU) --powered

# The harden runs of this CPU's regression: soc_top_hazard3 (hazard3), soc_top and picorv32_core (picorv32).
PROV_RECORDS = $(if $(filter hazard3,$(CPU)),runs/soc_top_hazard3_signoff/provenance.json,runs/soc_top_signoff/provenance.json runs/picorv32_core_signoff/provenance.json)

provenance-final:
	$(PY) signoff/scripts/provenance.py --final $(PROV_RECORDS)

# project-plan.md §7.5 `make harden D=<design>`; the run tag stays the design name (runs/<design>), and
# the commit of a run is in runs/<design>_signoff/provenance.json, which every later step compares
# with HEAD (signoff/scripts/run_guard.py), instead of a tag per git sha.
harden:
	@case "$(D)" in soc_top) $(MAKE) harden-soc CPU=picorv32 ;; soc_top_hazard3) $(MAKE) harden-soc CPU=hazard3 ;; \
	  picorv32_core) $(MAKE) harden-core ;; \
	  *) echo "harden: FAIL - D must be soc_top, soc_top_hazard3 or picorv32_core (got '$(D)')"; exit 1 ;; esac

# SRAM SPICE characterization (Phase 3.5, ADR-0010). char.json and the five .lib are committed;
# make harden-soc checks the .lib against char.json (pnr/soc_top/check_inputs.py char_lib).
SRAM_CHAR = ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char
SRAM_PDK_LIB = $${PDK_ROOT:-$$HOME/.ciel}/sky130A/libs.ref/sky130_sram_macros/lib/sky130_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib

sram-confirm:
	$(PY) ip/sram/char/confirm_char_lib.py $(SRAM_CHAR)/char.json $(SRAM_CHAR)

sram-lib:
	$(PY) ip/sram/char/gen_char_lib.py $(SRAM_CHAR)/char.json "$(SRAM_PDK_LIB)" $(SRAM_CHAR)

neg-char:
	$(PY) ip/sram/char/neg_char.py

sram-extract:
	$(PY) ip/sram/char/extract_sram.py

# OpenRAM self-generated SRAM (Phase 6, ADR-0018); not part of make regress.
OPENRAM_CONFIG ?= ip/sram/openram/configs/arv_sram_2kbyte_1rw1r_32x512_8.py
OPENRAM_DRC_MAX ?= 0
openram-setup:
	bash ip/sram/openram/setup.sh

neg-openram:
	$(PY) ip/sram/openram/neg_openram.py

OPENRAM_NAME = $(basename $(notdir $(OPENRAM_CONFIG)))
# Three checks after OpenRAM: its own DRC/LVS (gen_macro), the contents of every delivered view (check_macro_views,
# skill hard-macro-integration) and the full-deck DRC against the prebuilt macro; all run, any FAIL fails.
OPENRAM_OUT = runs/openram/$(OPENRAM_NAME)/macro/$(OPENRAM_NAME)
openram-macro:
	$(PY) ip/sram/openram/gen_macro.py $(OPENRAM_CONFIG) runs/openram/$(OPENRAM_NAME) --drc-max $(OPENRAM_DRC_MAX)
	rc=0; \
	$(PY) scripts/check_macro_views.py --name $(OPENRAM_NAME) --lef $(OPENRAM_OUT).lef --lib $(OPENRAM_OUT)_TT_1p8V_25C.lib \
	  --verilog $(OPENRAM_OUT).v --spice $(OPENRAM_OUT).sp --gds $(OPENRAM_OUT).gds --json runs/openram/$(OPENRAM_NAME)/views.json || rc=1; \
	$(PY) ip/sram/openram/macro_drc.py $(OPENRAM_OUT).gds $(OPENRAM_NAME) runs/openram/$(OPENRAM_NAME)/macro_drc.json || rc=1; \
	exit $$rc

# View QA of the SRAM the SoC uses now: the repo LEF (antenna added) and the five characterized .lib, with the
# PDK's Verilog, SPICE and GDS (skill hard-macro-integration). Seconds.
SRAM_REF = $${PDK_ROOT:-$$HOME/.ciel}/sky130A/libs.ref/sky130_sram_macros
SRAM_NAME = sky130_sram_2kbyte_1rw1r_32x512_8
macro-views:
	$(PY) scripts/check_macro_views.py --name $(SRAM_NAME) --lef ip/sram/$(SRAM_NAME)/$(SRAM_NAME).lef \
	  $(foreach f,$(wildcard ip/sram/$(SRAM_NAME)/char/*.lib),--lib $(f)) \
	  --verilog $(SRAM_REF)/verilog/$(SRAM_NAME).v --spice $(SRAM_REF)/spice/$(SRAM_NAME).spice --gds $(SRAM_REF)/gds/$(SRAM_NAME).gds

neg-macro-views:
	$(PY) scripts/neg_macro_views.py

# SPICE characterization of the self-generated macro (Phase 6 step 3c, ADR-0018) with the Phase 3.5 programs;
# the netlist and OpenRAM's .lib are committed under ip/sram/$(OR_SRAM)/openram/. Not part of make regress.
OR_SRAM = arv_sram_2kbyte_1rw1r_32x512_8
OR_SRAM_DIR = ip/sram/$(OR_SRAM)
OR_SRAM_ENV = SRAM_CHAR_MACRO=$(OR_SRAM) SRAM_CHAR_NETLIST=$(CURDIR)/$(OR_SRAM_DIR)/openram/$(OR_SRAM).sp
OR_SRAM_TEMPLATE = $(OR_SRAM_DIR)/openram/$(OR_SRAM)_TT_template.lib

openram-lib-template:
	$(PY) ip/sram/openram/lib_template.py $(OR_SRAM_DIR)/openram/$(OR_SRAM)_TT_1p8V_25C.lib "$(SRAM_PDK_LIB)" $(OR_SRAM_TEMPLATE)

openram-char:
	$(OR_SRAM_ENV) $(PY) ip/sram/char/characterize.py $(OR_SRAM_DIR)/char/char.json --pvt tt_025C_1v80
	$(OR_SRAM_ENV) $(PY) ip/sram/char/characterize.py $(OR_SRAM_DIR)/char/char.json --seed $(OR_SRAM_DIR)/char/char.json \
	  --pvt ss_100C_1v60 ff_n40C_1v95 ss_n40C_1v60 ff_100C_1v95
	$(MAKE) openram-lib
	$(MAKE) openram-confirm

openram-power:
	$(OR_SRAM_ENV) $(PY) ip/sram/char/power.py $(OR_SRAM_DIR)/char/power.json $(OR_POWER_ARGS)

openram-lib:
	$(OR_SRAM_ENV) $(PY) ip/sram/char/gen_char_lib.py $(OR_SRAM_DIR)/char/char.json $(OR_SRAM_TEMPLATE) $(OR_SRAM_DIR)/char \
	  $(if $(wildcard $(OR_SRAM_DIR)/char/power.json),--power $(OR_SRAM_DIR)/char/power.json)

openram-confirm:
	$(OR_SRAM_ENV) $(PY) ip/sram/char/confirm_char_lib.py $(OR_SRAM_DIR)/char/char.json $(OR_SRAM_DIR)/char

openram-check-lib:
	$(OR_SRAM_ENV) $(PY) ip/sram/char/check_char_lib.py $(OR_SRAM_DIR)/char/char.json $(OR_SRAM_DIR)/char

sram-char:
	$(PY) ip/sram/char/characterize.py $(SRAM_CHAR)/char.json --pvt tt_025C_1v80
	$(PY) ip/sram/char/characterize.py $(SRAM_CHAR)/char.json --seed $(SRAM_CHAR)/char.json \
	  --pvt ss_100C_1v60 ff_n40C_1v95 ss_n40C_1v60 ff_100C_1v95
	$(MAKE) sram-lib
	$(MAKE) sram-confirm

# The whole regression (scripts/regress.py lists the targets and their order).
regress:
	$(PY) scripts/regress.py --cpu hazard3

regress-picorv32:
	$(PY) scripts/regress.py --cpu picorv32

py-check:
	$(PY) scripts/check_py_names.py

skill-check:
	$(PY) scripts/check_skills.py

neg-regress:
	$(PY) scripts/neg_regress.py

test-flow-retry:
	bash pnr/test_librelane_flow.sh

# The Claude Code Stop hook that asks for the signoff criteria review after a harden (skill signoff-criteria).
test-review-hook:
	$(PY) signoff/scripts/test_review_hook.py

# harden-core is re-run so that eqy-core checks a run with source tracking (result.txt).
phase3: env-check-flow neg-provenance test-flow-retry harden-soc eqy-soc neg-eqy-soc gl-soc neg-gl-soc neg-pnr harden-core eqy-core neg-eqy-core

# Removes Phase 1 sim/firmware outputs only. LibreLane outputs (runs/flow_setup, runs/ci_sram_ref, runs/picorv32_core, runs/soc_top)
# take tens of minutes to regenerate and are kept; delete them by hand when needed.
clean:
	rm -rf runs/sim runs/neg runs/sim_build runs/core_stock runs/rtl sim_build fw/build obj_dir
