# make regress (CPU=hazard3)

commit `85bfa75b8f3fa45178f681386f69fe37fb2fbaf7`; 23/23 targets PASS; 127 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 76 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (49 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.5 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth_hazard3/stat.txt, log: runs/rtl/synth_hazard3/yosys.log) |
| 5 | `fw` | PASS | 0.0 | rm build_hazard3/obj/bootrom/bootrom__no_div_write.o build_hazard3/obj/bootrom/bootrom__skip_last_word.o build_hazard3/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-hazard3` | PASS | 0.4 | core-hazard3: PASS 65/65 riscv-tests, 2 unsupported, negative 1/1, trace 48/48 -> runs/core_hazard3/summary.txt |
| 7 | `regress-rtl` | PASS | 1.4 | regress: PASS  30/30 PASS  (83.3 s)  -> runs/sim_hazard3/summary.json, runs/sim_hazard3/junit.xml |
| 8 | `neg-rtl` | PASS | 6.2 | neg: PASS  36/36 caught  (374.8 s)  -> runs/neg_hazard3/summary.json |
| 9 | `neg-provenance` | PASS | 0.1 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.1 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 0.5 | neg-openram: PASS 50/50 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 16 | `harden-soc` | PASS | 29.0 | harden-soc: PASS |
| 17 | `eqy-soc` | PASS | 3.3 | eqy: PASS |
| 18 | `neg-eqy-soc` | PASS | 23.6 | neg-eqy: PASS 14/14 caught (1414 s) |
| 19 | `gl-soc` | PASS | 11.3 | gl-soc: PASS 15/15 tests passed (680.7 s) |
| 20 | `gl-soc-powered` | PASS | 19.2 | gl-soc-powered: PASS 15/15 tests passed (1154.5 s) |
| 21 | `neg-gl-soc` | PASS | 9.9 | neg-gl-soc: PASS 8/8 caught (592 s) |
| 22 | `neg-pnr` | PASS | 20.9 | neg-pnr: PASS 79/79 caught (1253 s) |
| 23 | `provenance-final` | PASS | 0.0 | provenance: PASS |
