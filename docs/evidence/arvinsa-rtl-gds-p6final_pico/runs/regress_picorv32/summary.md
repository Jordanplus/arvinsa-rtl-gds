# make regress (CPU=picorv32)

commit `4713c5fbacb46ae5086d952b119545fd6f844876`; 28/28 targets PASS; 135 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 75 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (49 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.1 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.1 | rm build/obj/bootrom/bootrom__skip_last_word.o build/obj/bootrom/bootrom__no_div_write.o build/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-stock` | PASS | 3.3 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.5 | regress: PASS  30/30 PASS  (30.0 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.5 | neg: PASS  33/33 caught  (29.0 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.2 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 0.2 | neg-openram: PASS 39/39 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 15/15 |
| 16 | `harden-soc` | PASS | 29.2 | harden-soc: PASS |
| 17 | `eqy-soc` | PASS | 4.2 | eqy: PASS |
| 18 | `neg-eqy-soc` | PASS | 17.2 | neg-eqy: PASS 10/10 caught (1032 s) |
| 19 | `gl-soc` | PASS | 7.1 | gl-soc: PASS 15/15 tests passed (428.7 s) |
| 20 | `gl-soc-powered` | PASS | 9.8 | gl-soc-powered: PASS 15/15 tests passed (585.0 s) |
| 21 | `neg-gl-soc` | PASS | 4.0 | neg-gl-soc: PASS 8/8 caught (239 s) |
| 22 | `neg-pnr` | PASS | 12.2 | neg-pnr: PASS 71/71 caught (729 s) |
| 23 | `harden-core` | PASS | 12.8 | harden-core: PASS |
| 24 | `gl-core` | PASS | 2.3 | gl-core: PASS in 140 s |
| 25 | `neg-gl-core` | PASS | 5.5 | neg-gl-core: PASS 2/2 caught |
| 26 | `eqy-core` | PASS | 3.2 | eqy: PASS |
| 27 | `neg-eqy-core` | PASS | 22.5 | neg-eqy: PASS 12/12 caught (1350 s) |
| 28 | `provenance-final` | PASS | 0.0 | provenance: PASS |
