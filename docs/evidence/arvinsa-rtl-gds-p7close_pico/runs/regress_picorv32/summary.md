# make regress (CPU=picorv32)

commit `84fe5051f055ec2a1100464672f5b32cd146bacb`; 31/31 targets PASS; 216 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 91 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.0 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.1 | rm build/obj/bootrom/bootrom__skip_last_word.o build/obj/bootrom/bootrom__no_div_write.o build/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-stock` | PASS | 3.2 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.5 | regress: PASS  30/30 PASS  (27.4 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.5 | neg: PASS  33/33 caught  (28.0 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.1 | neg-run-guard: PASS 57/57 |
| 11 | `neg-regress` | PASS | 0.1 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 0.5 | neg-openram: PASS 50/50 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 16 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 17 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 25/25 |
| 18 | `neg-precheck` | PASS | 4.7 | neg-precheck: PASS 25/25 |
| 19 | `harden-soc` | PASS | 31.0 | harden-soc: PASS |
| 20 | `eqy-soc` | PASS | 4.2 | eqy: PASS |
| 21 | `neg-eqy-soc` | PASS | 39.4 | neg-eqy: PASS 12/12 caught (2363 s) |
| 22 | `gl-soc` | PASS | 7.4 | gl-soc: PASS 15/15 tests passed (443.8 s) |
| 23 | `gl-soc-powered` | PASS | 15.3 | gl-soc-powered: PASS 15/15 tests passed (915.2 s) |
| 24 | `neg-gl-soc` | PASS | 4.5 | neg-gl-soc: PASS 8/8 caught (272 s) |
| 25 | `neg-pnr` | PASS | 20.3 | neg-pnr: PASS 82/82 caught (1218 s) |
| 26 | `harden-core` | PASS | 16.8 | harden-core: PASS |
| 27 | `gl-core` | PASS | 2.7 | gl-core: PASS in 160 s |
| 28 | `neg-gl-core` | PASS | 11.7 | neg-gl-core: PASS 2/2 caught |
| 29 | `eqy-core` | PASS | 5.0 | eqy: PASS |
| 30 | `neg-eqy-core` | PASS | 47.6 | neg-eqy: PASS 14/14 caught (2854 s) |
| 31 | `provenance-final` | PASS | 0.0 | provenance: PASS |
