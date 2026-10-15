# make regress

commit `38e85cb635e521b8fd1ec9024663843531407ca7`; 18/25 targets PASS; 79 min; FAIL

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 45 files, no undefined names |
| 3 | `lint` | PASS | 0.0 | LINT: PASS (23 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.0 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.0 | rm build/obj/bootrom/bootrom__skip_last_word.o build/obj/bootrom/bootrom__no_div_write.o build/obj/bootrom/bootrom__no_aia_readback.o |
| 6 | `core-stock` | PASS | 3.1 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.4 | regress: PASS  30/30 PASS  (26.3 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.4 | neg: PASS  33/33 caught  (26.5 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.1 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.0 | neg-run-guard: PASS 37/37 |
| 11 | `neg-regress` | PASS | 0.0 | neg-regress: PASS 5/5 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 7/7 |
| 13 | `harden-soc` | PASS | 22.4 | harden-soc: PASS |
| 14 | `eqy-soc` | PASS | 4.2 | eqy: PASS |
| 15 | `neg-eqy-soc` | PASS | 16.0 | neg-eqy: PASS 9/9 caught (958 s) |
| 16 | `gl-soc` | PASS | 7.3 | gl-soc: PASS 15/15 tests passed (440.7 s) |
| 17 | `gl-soc-powered` | PASS | 10.0 | gl-soc-powered: PASS 15/15 tests passed (598.6 s) |
| 18 | `neg-gl-soc` | PASS | 3.6 | neg-gl-soc: PASS 8/8 caught (217 s) |
| 19 | `neg-pnr` | FAIL | 11.1 | make[1]: *** [neg-pnr] Error 1 |
| - | `harden-core` | not run | - | - |
| - | `gl-core` | not run | - | - |
| - | `neg-gl-core` | not run | - | - |
| - | `eqy-core` | not run | - | - |
| - | `neg-eqy-core` | not run | - | - |
| - | `provenance-final` | not run | - | - |
