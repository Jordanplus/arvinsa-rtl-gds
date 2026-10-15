# make regress (CPU=hazard3)

commit `71b1454213eed2dadb4457c18f26d5ef11306cf1`; 21/21 targets PASS; 109 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 58 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.1 | LINT: PASS (49 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.4 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth_hazard3/stat.txt, log: runs/rtl/synth_hazard3/yosys.log) |
| 5 | `fw` | PASS | 0.0 | rm build_hazard3/obj/bootrom/bootrom__no_div_write.o build_hazard3/obj/bootrom/bootrom__skip_last_word.o build_hazard3/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-hazard3` | PASS | 0.4 | core-hazard3: PASS 65/65 riscv-tests, 2 unsupported, negative 1/1, trace 48/48 -> runs/core_hazard3/summary.txt |
| 7 | `regress-rtl` | PASS | 1.3 | regress: PASS  30/30 PASS  (75.2 s)  -> runs/sim_hazard3/summary.json, runs/sim_hazard3/junit.xml |
| 8 | `neg-rtl` | PASS | 6.1 | neg: PASS  36/36 caught  (363.5 s)  -> runs/neg_hazard3/summary.json |
| 9 | `neg-provenance` | PASS | 0.1 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.1 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `harden-soc` | PASS | 28.0 | harden-soc: PASS |
| 15 | `eqy-soc` | PASS | 3.3 | eqy: PASS |
| 16 | `neg-eqy-soc` | PASS | 21.3 | neg-eqy: PASS 13/13 caught (1275 s) |
| 17 | `gl-soc` | PASS | 9.7 | gl-soc: PASS 15/15 tests passed (582.3 s) |
| 18 | `gl-soc-powered` | PASS | 18.2 | gl-soc-powered: PASS 15/15 tests passed (1092.1 s) |
| 19 | `neg-gl-soc` | PASS | 8.6 | neg-gl-soc: PASS 8/8 caught (514 s) |
| 20 | `neg-pnr` | PASS | 11.5 | neg-pnr: PASS 63/63 caught (687 s) |
| 21 | `provenance-final` | PASS | 0.0 | provenance: PASS |
