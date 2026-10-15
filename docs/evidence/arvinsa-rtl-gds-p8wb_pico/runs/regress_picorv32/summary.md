# make regress (CPU=picorv32)

commit `f02a1a0733e6bba7cce7c113eee98ddf29d4278e`; 31/31 targets PASS; 223 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 100 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.1 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.1 | rm build/obj/bootrom/bootrom__skip_last_word.o build/obj/bootrom/bootrom__no_div_write.o build/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-stock` | PASS | 3.2 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.5 | regress: PASS  30/30 PASS  (28.2 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.5 | neg: PASS  33/33 caught  (28.8 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.1 | neg-run-guard: PASS 65/65 |
| 11 | `neg-regress` | PASS | 0.4 | neg-regress: PASS 10/10 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 0.5 | neg-openram: PASS 50/50 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 16 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 17 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 26/26 |
| 18 | `neg-precheck` | PASS | 7.0 | neg-precheck: PASS 31/31 |
| 19 | `harden-soc` | PASS | 33.6 | harden-soc: PASS |
| 20 | `eqy-soc` | PASS | 4.7 | eqy: PASS |
| 21 | `neg-eqy-soc` | PASS | 44.4 | neg-eqy: PASS 12/12 caught (2666 s) |
| 22 | `gl-soc` | PASS | 7.8 | gl-soc: PASS 15/15 tests passed (469.2 s) |
| 23 | `gl-soc-powered` | PASS | 14.8 | gl-soc-powered: PASS 15/15 tests passed (885.7 s) |
| 24 | `neg-gl-soc` | PASS | 4.9 | neg-gl-soc: PASS 8/8 caught (296 s) |
| 25 | `neg-pnr` | PASS | 21.8 | neg-pnr: PASS 82/82 caught (1310 s) |
| 26 | `harden-core` | PASS | 15.6 | harden-core: PASS |
| 27 | `gl-core` | PASS | 2.5 | gl-core: PASS in 151 s |
| 28 | `neg-gl-core` | PASS | 5.9 | neg-gl-core: PASS 2/2 caught |
| 29 | `eqy-core` | PASS | 3.8 | eqy: PASS |
| 30 | `neg-eqy-core` | PASS | 50.0 | neg-eqy: PASS 14/14 caught (2997 s) |
| 31 | `provenance-final` | PASS | 0.0 | provenance: PASS |
