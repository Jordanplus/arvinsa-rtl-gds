# make regress (CPU=caravel)

commit `2b04451e6f5be87202bf9ba4ace030c19a1c1320`; 18/18 targets PASS; 476 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.1 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 91 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `regress-rtl-caravel` | PASS | 1.7 | regress: PASS  32/32 PASS  (100.9 s)  -> runs/sim_caravel/summary.json, runs/sim_caravel/junit.xml |
| 5 | `neg-rtl-caravel` | PASS | 8.1 | neg: PASS  42/42 caught  (486.2 s)  -> runs/neg_caravel/summary.json |
| 6 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 7 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 26/26 |
| 8 | `neg-precheck` | PASS | 7.7 | neg-precheck: PASS 31/31 |
| 9 | `harden-caravel` | PASS | 286.6 | harden-soc: PASS |
| 10 | `eqy-caravel` | PASS | 14.0 | eqy: PASS |
| 11 | `neg-eqy-caravel` | PASS | 19.2 | neg-eqy: PASS 1/1 caught (1150 s) |
| 12 | `gl-caravel` | PASS | 15.0 | gl-soc: PASS 16/16 tests passed (897.9 s) |
| 13 | `neg-gl-caravel` | PASS | 0.4 | neg-gl-soc: PASS 1/1 caught (23 s) |
| 14 | `ir-caravel` | PASS | 16.9 | ir-caravel: PASS |
| 15 | `neg-ir-caravel` | PASS | 0.4 | neg-ir: PASS 10/10 (user_project_wrapper, worst 19.56 mV, limit 20.0 mV) |
| 16 | `neg-pnr-caravel` | PASS | 7.3 | neg-pnr: PASS 9/9 caught (439 s) |
| 17 | `precheck-caravel` | PASS | 98.6 | precheck: PASS (ADR-0019 decision 5) |
| 18 | `provenance-final` | PASS | 0.0 | provenance: PASS |
