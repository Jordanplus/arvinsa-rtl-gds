# make regress (CPU=picorv32)

commit `85bfa75b8f3fa45178f681386f69fe37fb2fbaf7`; 28/28 targets PASS; 196 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.1 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 76 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (49 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.0 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.1 | rm build/obj/bootrom/bootrom__skip_last_word.o build/obj/bootrom/bootrom__no_div_write.o build/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-stock` | PASS | 3.6 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.5 | regress: PASS  30/30 PASS  (32.2 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.5 | neg: PASS  33/33 caught  (31.5 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.3 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 0.6 | neg-openram: PASS 50/50 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 16 | `harden-soc` | PASS | 33.2 | harden-soc: PASS |
| 17 | `eqy-soc` | PASS | 6.4 | eqy: PASS |
| 18 | `neg-eqy-soc` | PASS | 28.5 | neg-eqy: PASS 10/10 caught (1712 s) |
| 19 | `gl-soc` | PASS | 10.2 | gl-soc: PASS 15/15 tests passed (609.1 s) |
| 20 | `gl-soc-powered` | PASS | 15.5 | gl-soc-powered: PASS 15/15 tests passed (927.5 s) |
| 21 | `neg-gl-soc` | PASS | 6.1 | neg-gl-soc: PASS 8/8 caught (364 s) |
| 22 | `neg-pnr` | PASS | 22.6 | neg-pnr: PASS 79/79 caught (1358 s) |
| 23 | `harden-core` | PASS | 17.7 | harden-core: PASS |
| 24 | `gl-core` | PASS | 2.6 | gl-core: PASS in 159 s |
| 25 | `neg-gl-core` | PASS | 6.7 | neg-gl-core: PASS 2/2 caught |
| 26 | `eqy-core` | PASS | 5.3 | eqy: PASS |
| 27 | `neg-eqy-core` | PASS | 35.4 | neg-eqy: PASS 12/12 caught (2123 s) |
| 28 | `provenance-final` | PASS | 0.0 | provenance: PASS |
