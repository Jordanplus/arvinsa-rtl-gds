# make regress (CPU=picorv32)

commit `71b1454213eed2dadb4457c18f26d5ef11306cf1`; 26/26 targets PASS; 124 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 58 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.1 | LINT: PASS (49 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.0 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.0 | rm build/obj/bootrom/bootrom__skip_last_word.o build/obj/bootrom/bootrom__no_div_write.o build/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-stock` | PASS | 3.1 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.4 | regress: PASS  30/30 PASS  (26.1 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.4 | neg: PASS  33/33 caught  (26.4 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.1 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `harden-soc` | PASS | 25.3 | harden-soc: PASS |
| 15 | `eqy-soc` | PASS | 3.7 | eqy: PASS |
| 16 | `neg-eqy-soc` | PASS | 14.3 | neg-eqy: PASS 9/9 caught (858 s) |
| 17 | `gl-soc` | PASS | 6.9 | gl-soc: PASS 15/15 tests passed (413.5 s) |
| 18 | `gl-soc-powered` | PASS | 9.3 | gl-soc-powered: PASS 15/15 tests passed (558.7 s) |
| 19 | `neg-gl-soc` | PASS | 3.9 | neg-gl-soc: PASS 8/8 caught (231 s) |
| 20 | `neg-pnr` | PASS | 11.0 | neg-pnr: PASS 63/63 caught (658 s) |
| 21 | `harden-core` | PASS | 12.7 | harden-core: PASS |
| 22 | `gl-core` | PASS | 2.3 | gl-core: PASS in 141 s |
| 23 | `neg-gl-core` | PASS | 5.5 | neg-gl-core: PASS 2/2 caught |
| 24 | `eqy-core` | PASS | 3.2 | eqy: PASS |
| 25 | `neg-eqy-core` | PASS | 20.8 | neg-eqy: PASS 11/11 caught (1251 s) |
| 26 | `provenance-final` | PASS | 0.0 | provenance: PASS |
