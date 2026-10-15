# make regress (CPU=caravel)

commit `84fe5051f055ec2a1100464672f5b32cd146bacb`; 18/18 targets PASS; 404 min; PASS

| # | target | result | min | last line |
|---|---|---|---|---|
| 1 | `env-check-flow` | PASS | 0.0 | env-check: PASS |
| 2 | `py-check` | PASS | 0.0 | py-check: PASS 91 files, no undefined names, no file emptied before it is read |
| 3 | `lint` | PASS | 0.2 | LINT: PASS (57 variants, 0 warnings, 0 errors) |
| 4 | `regress-rtl-caravel` | PASS | 1.5 | regress: PASS  32/32 PASS  (85.5 s)  -> runs/sim_caravel/summary.json, runs/sim_caravel/junit.xml |
| 5 | `neg-rtl-caravel` | PASS | 7.5 | neg: PASS  42/42 caught  (449.9 s)  -> runs/neg_caravel/summary.json |
| 6 | `pin-plan` | PASS | 0.0 | pin-plan: PASS |
| 7 | `neg-pin-plan` | PASS | 0.0 | neg-pin-plan: PASS 25/25 |
| 8 | `neg-precheck` | PASS | 5.5 | neg-precheck: PASS 25/25 |
| 9 | `harden-caravel` | PASS | 236.2 | harden-soc: PASS |
| 10 | `eqy-caravel` | PASS | 13.7 | eqy: PASS |
| 11 | `neg-eqy-caravel` | PASS | 25.1 | neg-eqy: PASS 1/1 caught (1505 s) |
| 12 | `gl-caravel` | PASS | 17.4 | gl-soc: PASS 16/16 tests passed (1043.9 s) |
| 13 | `neg-gl-caravel` | PASS | 0.4 | neg-gl-soc: PASS 1/1 caught (25 s) |
| 14 | `ir-caravel` | PASS | 28.5 | ir-caravel: PASS |
| 15 | `neg-ir-caravel` | PASS | 0.0 | neg-ir: PASS 7/7 (user_project_wrapper, worst 19.56 mV, limit 20.0 mV) |
| 16 | `neg-pnr-caravel` | PASS | 6.8 | neg-pnr: PASS 8/8 caught (406 s) |
| 17 | `precheck-caravel` | PASS | 61.4 | precheck: PASS (ADR-0019 decision 5) |
| 18 | `provenance-final` | PASS | 0.0 | provenance: PASS |
