# make regress (CPU=hazard3)

commit `f02a1a0733e6bba7cce7c113eee98ddf29d4278e`; 30/30 targets PASS; 174 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 100 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.6 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth_hazard3/stat.txt, log: runs/rtl/synth_hazard3/yosys.log) |
| 5 | `fw` | PASS | 0.0 | rm build_hazard3/obj/bootrom/bootrom__no_div_write.o build_hazard3/obj/bootrom/bootrom__skip_last_word.o build_hazard3/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-hazard3` | PASS | 0.4 | core-hazard3: PASS 65/65 riscv-tests, 2 unsupported, negative 1/1, trace 48/48 -> runs/core_hazard3/summary.txt |
| 7 | `regress-rtl` | PASS | 2.0 | regress: PASS  32/32 PASS  (120.5 s)  -> runs/sim_hazard3/summary.json, runs/sim_hazard3/junit.xml |
| 8 | `neg-rtl` | PASS | 7.0 | neg: PASS  36/36 caught  (421.1 s)  -> runs/neg_hazard3/summary.json |
| 9 | `regress-rtl-caravel` | PASS | 1.4 | regress: PASS  32/32 PASS  (81.8 s)  -> runs/sim_caravel/summary.json, runs/sim_caravel/junit.xml |
| 10 | `neg-rtl-caravel` | PASS | 6.8 | neg: PASS  42/42 caught  (405.4 s)  -> runs/neg_caravel/summary.json |
| 11 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 12 | `neg-run-guard` | PASS | 0.1 | neg-run-guard: PASS 65/65 |
| 13 | `neg-regress` | PASS | 0.4 | neg-regress: PASS 10/10 |
| 14 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 15 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 16 | `neg-openram` | PASS | 0.6 | neg-openram: PASS 50/50 |
| 17 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 18 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 19 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 26/26 |
| 20 | `neg-precheck` | PASS | 5.8 | neg-precheck: PASS 31/31 |
| 21 | `harden-soc` | PASS | 33.4 | harden-soc: PASS |
| 22 | `eqy-soc` | PASS | 4.1 | eqy: PASS |
| 23 | `neg-eqy-soc` | PASS | 42.7 | neg-eqy: PASS 16/16 caught (2561 s) |
| 24 | `gl-soc` | PASS | 13.3 | gl-soc: PASS 16/16 tests passed (795.8 s) |
| 25 | `gl-soc-powered` | PASS | 22.4 | gl-soc-powered: PASS 16/16 tests passed (1345.7 s) |
| 26 | `neg-gl-soc` | PASS | 10.6 | neg-gl-soc: PASS 8/8 caught (633 s) |
| 27 | `neg-pnr` | PASS | 18.8 | neg-pnr: PASS 82/82 caught (1129 s) |
| 28 | `ir-soc` | PASS | 1.7 | ir-soc: PASS |
| 29 | `neg-ir-soc` | PASS | 1.6 | neg-ir: PASS 12/12 (soc_top_hazard3, worst 4.67 mV, limit 20.0 mV) |
| 30 | `provenance-final` | PASS | 0.0 | provenance: PASS |
