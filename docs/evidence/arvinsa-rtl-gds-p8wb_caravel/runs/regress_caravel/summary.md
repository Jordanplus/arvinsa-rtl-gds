# make regress (CPU=caravel)

commit `f02a1a0733e6bba7cce7c113eee98ddf29d4278e`; 18/18 targets PASS; 429 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 100 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `regress-rtl-caravel` | PASS | 1.6 | regress: PASS  32/32 PASS  (93.1 s)  -> runs/sim_caravel/summary.json, runs/sim_caravel/junit.xml |
| 5 | `neg-rtl-caravel` | PASS | 7.7 | neg: PASS  42/42 caught  (461.5 s)  -> runs/neg_caravel/summary.json |
| 6 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 7 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 26/26 |
| 8 | `neg-precheck` | PASS | 7.2 | neg-precheck: PASS 31/31 |
| 9 | `harden-caravel` | PASS | 259.6 | harden-soc: PASS |
| 10 | `eqy-caravel` | PASS | 14.3 | eqy: PASS |
| 11 | `neg-eqy-caravel` | PASS | 24.8 | neg-eqy: PASS 1/1 caught (1487 s) |
| 12 | `gl-caravel` | PASS | 17.3 | gl-soc: PASS 16/16 tests passed (1040.6 s) |
| 13 | `neg-gl-caravel` | PASS | 0.4 | neg-gl-soc: PASS 1/1 caught (23 s) |
| 14 | `ir-caravel` | PASS | 13.8 | ir-caravel: PASS |
| 15 | `neg-ir-caravel` | PASS | 0.2 | neg-ir: PASS 10/10 (user_project_wrapper, worst 19.56 mV, limit 20.0 mV) |
| 16 | `neg-pnr-caravel` | PASS | 9.4 | neg-pnr: PASS 9/9 caught (561 s) |
| 17 | `precheck-caravel` | PASS | 71.9 | precheck: PASS (ADR-0019 decision 5) |
| 18 | `provenance-final` | PASS | 0.0 | provenance: PASS |
