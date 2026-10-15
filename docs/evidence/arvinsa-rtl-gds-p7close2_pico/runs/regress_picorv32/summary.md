# make regress (CPU=picorv32)

commit `2b04451e6f5be87202bf9ba4ace030c19a1c1320`; 31/31 targets PASS; 248 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.1 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 91 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 0.1 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth/stat.txt, log: runs/rtl/synth/yosys.log) |
| 5 | `fw` | PASS | 0.0 | check-bootrom: PASS: ../rtl/bootrom/bootrom.v matches the boot ROM image |
| 6 | `core-stock` | PASS | 7.0 | core-stock: PASS |
| 7 | `regress-rtl` | PASS | 0.5 | regress: PASS  30/30 PASS  (30.7 s)  -> runs/sim/summary.json, runs/sim/junit.xml |
| 8 | `neg-rtl` | PASS | 0.5 | neg: PASS  33/33 caught  (32.6 s)  -> runs/neg/summary.json |
| 9 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 10 | `neg-run-guard` | PASS | 0.1 | neg-run-guard: PASS 65/65 |
| 11 | `neg-regress` | PASS | 0.2 | neg-regress: PASS 8/8 |
| 12 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 13 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 14 | `neg-openram` | PASS | 2.4 | neg-openram: PASS 50/50 |
| 15 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 16 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 17 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 26/26 |
| 18 | `neg-precheck` | PASS | 9.5 | neg-precheck: PASS 31/31 |
| 19 | `harden-soc` | PASS | 30.6 | harden-soc: PASS |
| 20 | `eqy-soc` | PASS | 5.1 | eqy: PASS |
| 21 | `neg-eqy-soc` | PASS | 47.0 | neg-eqy: PASS 12/12 caught (2820 s) |
| 22 | `gl-soc` | PASS | 11.7 | gl-soc: PASS 15/15 tests passed (699.6 s) |
| 23 | `gl-soc-powered` | PASS | 18.2 | gl-soc-powered: PASS 15/15 tests passed (1094.4 s) |
| 24 | `neg-gl-soc` | PASS | 8.5 | neg-gl-soc: PASS 8/8 caught (509 s) |
| 25 | `neg-pnr` | PASS | 23.2 | neg-pnr: PASS 82/82 caught (1391 s) |
| 26 | `harden-core` | PASS | 20.8 | harden-core: PASS |
| 27 | `gl-core` | PASS | 3.8 | gl-core: PASS in 229 s |
| 28 | `neg-gl-core` | PASS | 6.5 | neg-gl-core: PASS 2/2 caught |
| 29 | `eqy-core` | PASS | 4.2 | eqy: PASS |
| 30 | `neg-eqy-core` | PASS | 48.0 | neg-eqy: PASS 14/14 caught (2878 s) |
| 31 | `provenance-final` | PASS | 0.0 | provenance: PASS |
