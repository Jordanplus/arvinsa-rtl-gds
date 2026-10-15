# make regress (CPU=hazard3)

commit `2b04451e6f5be87202bf9ba4ace030c19a1c1320`; 30/30 targets PASS; 211 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.3 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 91 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.3 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `synth-check` | PASS | 1.1 | SYNTH-CHECK: PASS (full statistics: runs/rtl/synth_hazard3/stat.txt, log: runs/rtl/synth_hazard3/yosys.log) |
| 5 | `fw` | PASS | 0.0 | check-bootrom: PASS: ../rtl/bootrom/bootrom.v matches the boot ROM image |
| 6 | `core-hazard3` | PASS | 0.2 | core-hazard3: PASS 65/65 riscv-tests, 2 unsupported, negative 1/1, trace 48/48 -> runs/core_hazard3/summary.txt |
| 7 | `regress-rtl` | PASS | 3.1 | regress: PASS  32/32 PASS  (188.3 s)  -> runs/sim_hazard3/summary.json, runs/sim_hazard3/junit.xml |
| 8 | `neg-rtl` | PASS | 10.6 | neg: PASS  36/36 caught  (638.1 s)  -> runs/neg_hazard3/summary.json |
| 9 | `regress-rtl-caravel` | PASS | 1.5 | regress: PASS  32/32 PASS  (91.6 s)  -> runs/sim_caravel/summary.json, runs/sim_caravel/junit.xml |
| 10 | `neg-rtl-caravel` | PASS | 7.6 | neg: PASS  42/42 caught  (453.7 s)  -> runs/neg_caravel/summary.json |
| 11 | `neg-provenance` | PASS | 0.2 | neg-provenance: PASS 19/19 |
| 12 | `neg-run-guard` | PASS | 0.1 | neg-run-guard: PASS 65/65 |
| 13 | `neg-regress` | PASS | 0.1 | neg-regress: PASS 8/8 |
| 14 | `test-flow-retry` | PASS | 0.0 | test-flow-retry: PASS 15/15 |
| 15 | `test-review-hook` | PASS | 0.0 | test-review-hook: PASS 12/12 |
| 16 | `neg-openram` | PASS | 0.5 | neg-openram: PASS 50/50 |
| 17 | `neg-macro-views` | PASS | 0.0 | neg-macro-views: PASS 22/22 |
| 18 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 19 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 26/26 |
| 20 | `neg-precheck` | PASS | 13.9 | neg-precheck: PASS 31/31 |
| 21 | `harden-soc` | PASS | 52.5 | harden-soc: PASS |
| 22 | `eqy-soc` | PASS | 4.5 | eqy: PASS |
| 23 | `neg-eqy-soc` | PASS | 45.6 | neg-eqy: PASS 16/16 caught (2476 s) |
| 24 | `gl-soc` | PASS | 12.9 | gl-soc: PASS 16/16 tests passed (775.4 s) |
| 25 | `gl-soc-powered` | PASS | 23.6 | gl-soc-powered: PASS 16/16 tests passed (1417.1 s) |
| 26 | `neg-gl-soc` | PASS | 10.3 | neg-gl-soc: PASS 8/8 caught (616 s) |
| 27 | `neg-pnr` | PASS | 18.4 | neg-pnr: PASS 82/82 caught (1073 s) |
| 28 | `ir-soc` | PASS | 1.7 | ir-soc: PASS |
| 29 | `neg-ir-soc` | PASS | 1.6 | neg-ir: PASS 12/12 (soc_top_hazard3, worst 4.67 mV, limit 20.0 mV) |
| 30 | `provenance-final` | PASS | 0.0 | provenance: PASS |
