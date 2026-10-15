# make regress (CPU=hazard3)

commit `4713c5fbacb46ae5086d952b119545fd6f844876`; 23/23 targets PASS; 153 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.1 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 75 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (49 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.5 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth_hazard3/stat.txt, log: runs/rtl/synth_hazard3/yosys.log) |
| 5 | `fw` | PASS | 0.1 | rm build_hazard3/obj/bootrom/bootrom__no_div_write.o build_hazard3/obj/bootrom/bootrom__skip_last_word.o build_hazard3/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-hazard3` | PASS | 0.4 | core-hazard3: PASS 65/65 riscv-tests, 2 unsupported, negative 1/1, trace 48/48 -> runs/core_hazard3/summary.txt |
| 7 | `regress-rtl` | PASS | 1.4 | regress: PASS  30/30 PASS  (82.9 s)  -> runs/sim_hazard3/summary.json, runs/sim_hazard3/junit.xml |
| 8 | `neg-rtl` | PASS | 6.9 | neg: PASS  36/36 caught  (414.5 s)  -> runs/neg_hazard3/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.2 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 0.3 | neg-openram: PASS 39/39 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 15/15 |
| 16 | `harden-soc` | PASS | 34.6 | harden-soc: PASS |
| 17 | `eqy-soc` | PASS | 4.8 | eqy: PASS |
| 18 | `neg-eqy-soc` | PASS | 33.7 | neg-eqy: PASS 14/14 caught (2024 s) |
| 19 | `gl-soc` | PASS | 14.5 | gl-soc: PASS 15/15 tests passed (871.9 s) |
| 20 | `gl-soc-powered` | PASS | 24.0 | gl-soc-powered: PASS 15/15 tests passed (1442.8 s) |
| 21 | `neg-gl-soc` | PASS | 11.7 | neg-gl-soc: PASS 8/8 caught (701 s) |
| 22 | `neg-pnr` | PASS | 19.0 | neg-pnr: PASS 71/71 caught (1137 s) |
| 23 | `provenance-final` | PASS | 0.0 | provenance: PASS |
