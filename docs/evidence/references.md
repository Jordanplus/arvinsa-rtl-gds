# 文件引用的 runs/ 路徑與收錄狀態

由 `scripts/collect_evidence.py` 在清理前產生：列出 repo 文件（不含本目錄）引用到的每個 `runs/` 或 worktree 路徑。`runs/x` 收錄後在本目錄的 `<repo 目錄名>/runs/x`，`../<worktree>/runs/x` 在 `<worktree>/runs/x`。通用寫法（例如 `runs/<tag>_signoff`）不列。

| 引用的路徑 | 狀態 | 引用處（前兩處） |
|---|---|---|
| `../arvinsa-rtl-gds-p5h3/runs/p5_h3_h4_signoff/criteria_review.md` | 已收錄 | docs/decisions/0014-post-grt-resizer-timing.md:58 |
| `../arvinsa-rtl-gds-p5h3/runs/p5_h3_h5_signoff/criteria_review.md` | 已收錄 | docs/decisions/0014-post-grt-resizer-timing.md:58 |
| `../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3/56-openroad-stapostpnr/max_ss_n40C_1v60/` | 清理前就已不存在 | docs/decisions/0013-resizer-sees-ss-n40c.md:58 |
| `runs/ci_sram_ref` | 目錄：收錄其中 2 個檔 | Makefile:486, env/setup.md:71 等 4 處 |
| `runs/ci_sram_ref/metrics.json` | 已收錄 | signoff/golden/ci_sram_ref/README.md:40 |
| `runs/cleanup_2026-10-15.txt` | 已收錄 | docs/phase_exit/phase7.md:33 |
| `runs/core_hazard3` | 目錄：收錄其中 1 個檔 | dv/core_hazard3/run.py:5 |
| `runs/core_stock` | 目錄：收錄其中 3 個檔 | Makefile:489, docs/notes/core_stock.md:111 等 14 處 |
| `runs/core_stock/` | 目錄：收錄其中 3 個檔 | docs/notes/core_stock.md:111, docs/notes/core_stock.md:16 等 11 處 |
| `runs/core_stock/logs/test_rvf.log` | 已收錄 | docs/notes/core_stock.md:83 |
| `runs/core_stock/neg/` | 清理前就已不存在 | docs/notes/core_stock.md:111 |
| `runs/core_stock/src` | 目錄：收錄其中 1 個檔 | docs/notes/core_stock.md:21, docs/notes/core_stock.md:27 等 5 處 |
| `runs/core_stock/summary.txt` | 已收錄 | docs/notes/core_stock.md:16, docs/notes/core_stock.md:65 等 3 處 |
| `runs/dev5_gl.log` | 已收錄 | .claude/skills/gate-level-simulation/SKILL.md:55, .claude/skills/gate-level-simulation/SKILL.md:57 |
| `runs/dev5_neg_pnr.log` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:125 |
| `runs/devfix_core` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:139 |
| `runs/devfix_h3` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:139 |
| `runs/drc_gds_exp` | 清理前就已不存在 | .claude/skills/drc-signoff/SKILL.md:95 |
| `runs/exp_h_d` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:68, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:89 等 3 處 |
| `runs/exp_h_d/` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:68 |
| `runs/exp_p_c1` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:146 |
| `runs/exp_p_c1/01-openroad-resizertimingpostcts/openroad-resizertimingpostcts.log` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:146 |
| `runs/exp_p_c2` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:146 |
| `runs/exp_p_d` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:68, .claude/skills/drv-timing-closure/SKILL.md:145 等 4 處 |
| `runs/exp_p_d/01-openroad-cts/openroad-cts.log` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:68 |
| `runs/exp_p_dtdout` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:145 |
| `runs/exp_p_hm01` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:145, docs/decisions/0016-cts-no-macro-latency-balancing.md:77 |
| `runs/exp_t41_r17` | 清理前就已不存在 | docs/decisions/0015-golden-layout-tolerance.md:15, signoff/limits/soc_top_hazard3.toml:90 等 3 處 |
| `runs/exp_t41_r4` | 清理前就已不存在 | docs/decisions/0015-golden-layout-tolerance.md:15, signoff/limits/soc_top_hazard3.toml:90 等 3 處 |
| `runs/flow_setup` | 目錄：收錄其中 1 個檔 | Makefile:486, docs/notes/problem_review/review_p0_35.md:208 等 11 處 |
| `runs/flow_setup/` | 目錄：收錄其中 1 個檔 | docs/notes/problem_review/review_p0_35.md:208, docs/notes/problem_review/review_p0_35.md:40 等 8 處 |
| `runs/flow_setup/smoke_test.log` | 未收錄 | docs/phase_exit/phase0.md:9, env/setup.md:56 |
| `runs/flow_setup/versions.txt` | 已收錄 | env/setup.md:57, env/setup_flow.sh:4 等 3 處 |
| `runs/gl_core` | 清理前就已不存在 | dv/gl_core/run_gl_core.py:34 |
| `runs/gl_dev5_rerun/` | 清理前就已不存在 | .claude/skills/gate-level-simulation/SKILL.md:55 |
| `runs/gl_soc` | 目錄：收錄其中 1 個檔 | dv/gl_soc/run_gl_soc.py:40, dv/gl_soc/run_gl_soc.py:41 |
| `runs/gl_soc_hazard3` | 目錄：收錄其中 1 個檔 | dv/gl_soc/run_gl_soc.py:41 |
| `runs/gl_soc_powered` | 目錄：收錄其中 1 個檔 | dv/gl_soc/run_gl_soc.py:40, dv/gl_soc/run_gl_soc.py:41 |
| `runs/gl_soc_powered_hazard3` | 目錄：收錄其中 1 個檔 | dv/gl_soc/run_gl_soc.py:41 |
| `runs/ir_caravel` | 目錄：未收錄（1619 MB 的 run 中間產物） | Makefile:207, Makefile:209 等 7 處 |
| `runs/ir_caravel/ir_caravel` | 目錄：未收錄（1619 MB 的 run 中間產物） | docs/report/figures/SOURCES.md:121, docs/report/figures/scripts/ir_drop_map.py:23 等 4 處 |
| `runs/ir_caravel/ir_caravel/` | 目錄：未收錄（1619 MB 的 run 中間產物） | docs/report/figures/SOURCES.md:121, docs/report/figures/scripts/ir_drop_map.py:5 |
| `runs/ir_caravel_vcd` | 目錄：未收錄（983 MB 的 run 中間產物） | Makefile:207, Makefile:210 等 3 處 |
| `runs/ir_caravel_vcd/win_` | 清理前就已不存在 | Makefile:210 |
| `runs/ir_soc` | 清理前就已不存在 | Makefile:216, Makefile:218 等 4 處 |
| `runs/ir_soc/ir_pattern` | 清理前就已不存在 | pnr/soc_top/neg_ir.py:53 |
| `runs/ir_soc_vcd` | 清理前就已不存在 | Makefile:216, Makefile:219 等 3 處 |
| `runs/ir_soc_vcd/win_` | 清理前就已不存在 | Makefile:219 |
| `runs/layout_png/p7_floorplan4_modules.png` | 已收錄 | .claude/skills/chip-floorplan-pin-planning/SKILL.md:67, docs/decisions/0019-phase7-caravel-precheck.md:67 等 3 處 |
| `runs/m_` | 清理前就已不存在 | docs/notes/ir_study/combined.py:5 |
| `runs/neg` | 目錄：收錄其中 1 個檔 | .claude/skills/core-migration-hazard3/SKILL.md:109, .claude/skills/drc-signoff/SKILL.md:101 等 36 處 |
| `runs/neg/summary.json` | 已收錄 | docs/spec/soc_spec.md:373, dv/README.md:48 等 3 處 |
| `runs/neg_` | 清理前就已不存在 | .claude/skills/core-migration-hazard3/SKILL.md:109, .claude/skills/drc-signoff/SKILL.md:101 等 32 處 |
| `runs/neg_eqy_dev6/clk0_inverted/` | 清理前就已不存在 | .claude/skills/formal-equivalence-eqy/SKILL.md:98 |
| `runs/neg_eqy_picorv32_core` | 清理前就已不存在 | .claude/skills/formal-equivalence-eqy/SKILL.md:93, .claude/skills/signoff-checker-qualification/SKILL.md:157 |
| `runs/neg_eqy_picorv32_core/wdata3_stuck0/eqy/summary.json` | 清理前就已不存在 | .claude/skills/signoff-checker-qualification/SKILL.md:157 |
| `runs/neg_gl_core` | 清理前就已不存在 | dv/gl_core/neg_gl_core.py:4, dv/gl_core/neg_gl_core.py:8 |
| `runs/neg_gl_soc` | 目錄：未收錄（108 MB 的 run 中間產物） | dv/gl_soc/neg_gl_soc.py:12, dv/gl_soc/neg_gl_soc.py:6 等 3 處 |
| `runs/neg_gl_soc_hazard3` | 目錄：未收錄（110 MB 的 run 中間產物） | dv/gl_soc/neg_gl_soc.py:7 |
| `runs/neg_hazard3/summary.json` | 已收錄 | .claude/skills/core-migration-hazard3/SKILL.md:109 |
| `runs/neg_pnr/P10/run.log` | 清理前就已不存在 | .claude/skills/drc-signoff/SKILL.md:97 |
| `runs/neg_pnr/P13/neg.sdc` | 清理前就已不存在 | .claude/skills/timing-constraints-sdc/SKILL.md:64 |
| `runs/neg_pnr/P13/run.log` | 清理前就已不存在 | .claude/skills/signoff-checker-qualification/SKILL.md:160 |
| `runs/neg_pnr_dev/P21/run.log` | 清理前就已不存在 | .claude/skills/drc-signoff/SKILL.md:101 |
| `runs/neg_precheck` | 目錄：未收錄（205 MB 的 run 中間產物） | signoff/precheck/neg_precheck.py:296, signoff/precheck/neg_precheck.py:7 |
| `runs/neg_precheck/` | 目錄：未收錄（205 MB 的 run 中間產物） | signoff/precheck/neg_precheck.py:7 |
| `runs/neg_provenance` | 目錄：收錄其中 5 個檔 | .claude/skills/flow-regression-reproducibility/SKILL.md:122, signoff/scripts/neg_provenance.py:107 等 4 處 |
| `runs/neg_provenance/clean.log` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:122, signoff/scripts/neg_provenance.py:107 |
| `runs/neg_provenance/repo` | 目錄：收錄其中 4 個檔 | signoff/scripts/neg_provenance.py:7 |
| `runs/neg_regress` | 目錄：收錄其中 1 個檔 | scripts/neg_regress.py:102, scripts/neg_regress.py:63 等 3 處 |
| `runs/neg_regress/pass/regress.log` | 已收錄 | scripts/neg_regress.py:102 |
| `runs/neg_run_guard` | 目錄：未收錄（0 MB 的 run 中間產物） | signoff/scripts/neg_run_guard.py:8, signoff/scripts/neg_run_guard.py:84 |
| `runs/openram` | 目錄：收錄其中 4 個檔 | .claude/skills/macro-qualification/SKILL.md:17, .claude/skills/openram-macro-characterization/SKILL.md:170 等 21 處 |
| `runs/openram/` | 目錄：收錄其中 4 個檔 | .claude/skills/macro-qualification/SKILL.md:17, .claude/skills/openram-macro-characterization/SKILL.md:170 等 19 處 |
| `runs/openram/arv_sram_2kbyte_1rw1r_32x512_8/` | 目錄：收錄其中 1 個檔 | docs/phase_exit/phase6.md:52 |
| `runs/openram/arv_sram_2kbyte_1rw_32x512_8/` | 目錄：收錄其中 1 個檔 | .claude/skills/openram-macro-generation/SKILL.md:104 |
| `runs/openram/drc_baseline.magic.log.boxes.tsv` | 未收錄（426 MB） | docs/decisions/0018-openram-self-generated-macro.md:120 |
| `runs/openram/p3p1_small/` | 目錄：未收錄（110 MB 的 run 中間產物） | docs/notes/openram_phase6_bringup.md:173 |
| `runs/openram/read_check_clk1_self/` | 目錄：未收錄（17 MB 的 run 中間產物） | docs/notes/openram_phase6_bringup.md:237, docs/notes/openram_phase6_bringup.md:464 等 3 處 |
| `runs/openram/read_check_wpr1/period_exp.py` | 已收錄 | docs/notes/openram_phase6_bringup.md:149 |
| `runs/openram/whatif/make_whatif.py` | 已收錄 | docs/notes/openram_phase6_bringup.md:151 |
| `runs/openram_try/arv_sram_2kbyte_1rw_32x512_8.py` | 已收錄 | docs/notes/openram_phase6_bringup.md:286 |
| `runs/p35_regress1/` | 目錄：收錄其中 4 個檔 | docs/phase_exit/phase3_5.md:11 |
| `runs/p35_regress_clean1.log` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:128 |
| `runs/p35_regress_clean2.log` | 已收錄 | docs/phase_exit/phase3_5.md:9 |
| `runs/p35_whatif/` | 目錄：收錄其中 4 個檔 | docs/decisions/0010-sram-spice-characterization.md:180, docs/phase_exit/phase3_5.md:198 等 3 處 |
| `runs/p3_neg_eqy_soc.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:96 |
| `runs/p3_phase3_clean.log` | 已收錄 | .claude/skills/librelane-run-debug/SKILL.md:116, docs/notes/grt0229_repro.md:12 |
| `runs/p3_phase3_clean2.log` | 已收錄 | .claude/skills/gate-level-simulation/SKILL.md:52, .claude/skills/signoff-checker-qualification/SKILL.md:164 |
| `runs/p3_phase3_clean3.log` | 已收錄 | .claude/skills/gate-level-simulation/SKILL.md:54, .claude/skills/signoff-checker-qualification/SKILL.md:165 |
| `runs/p4_harden_soc_1_stopped/` | 目錄：收錄其中 1 個檔 | .claude/skills/multicorner-sta/SKILL.md:56 |
| `runs/p4_regress_clean3.log` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:127, .claude/skills/gate-level-simulation/SKILL.md:56 等 3 處 |
| `runs/p4_regress_clean4.log` | 已收錄 | docs/phase_exit/phase4.md:12 |
| `runs/p5_h3_exp_postgrt_slew/` | 目錄：收錄其中 9 個檔 | .claude/skills/drv-timing-closure/SKILL.md:141, .claude/skills/flow-regression-reproducibility/SKILL.md:130 等 4 處 |
| `runs/p5_h3_exp_wirelength/` | 目錄：收錄其中 8 個檔 | .claude/skills/drv-timing-closure/SKILL.md:140, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:73 等 3 處 |
| `runs/p5_h3_exp_wirelength/lat.log` | 已收錄 | .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:73 |
| `runs/p5_h3_h10` | 清理前就已不存在 | .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:91, docs/decisions/0016-cts-no-macro-latency-balancing.md:50 |
| `runs/p5_h3_h4_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:142, .claude/skills/signoff-criteria/SKILL.md:277 等 4 處 |
| `runs/p5_h3_h4_signoff/criteria_review.txt` | 清理前就已不存在 | .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:69 |
| `runs/p5_h3_h5/` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:67, .claude/skills/drv-timing-closure/SKILL.md:143 等 4 處 |
| `runs/p5_h3_h5/37-openroad-resizertimingpostcts/` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:143 |
| `runs/p5_h3_h5/57-openroad-stapostpnr/min_ss_n40C_1v60/max.rpt` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:67, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:78 |
| `runs/p5_h3_h5_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/cts-clock-tree/SKILL.md:67, .claude/skills/signoff-criteria/SKILL.md:278 等 4 處 |
| `runs/p5_h3_h6_signoff/` | 清理前就已不存在 | .claude/skills/antenna-signoff/SKILL.md:50, .claude/skills/drv-timing-closure/SKILL.md:144 等 5 處 |
| `runs/p5_h3_h6_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:131, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:81 |
| `runs/p5_h3_h7_signoff/` | 清理前就已不存在 | .claude/skills/antenna-signoff/SKILL.md:50, .claude/skills/drv-timing-closure/SKILL.md:144 等 5 處 |
| `runs/p5_h3_h7_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:132, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:82 |
| `runs/p5_h3_harden2.log` | 已收錄 | .claude/skills/drv-timing-closure/SKILL.md:138, .claude/skills/multicorner-sta/SKILL.md:57 等 3 處 |
| `runs/p5_h3_harden3.log` | 已收錄 | .claude/skills/drv-timing-closure/SKILL.md:139, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:68 等 3 處 |
| `runs/p5_h3_harden4.log` | 已收錄 | .claude/skills/drv-timing-closure/SKILL.md:140, docs/decisions/0014-post-grt-resizer-timing.md:58 |
| `runs/p5_h3_harden5.log` | 已收錄 | .claude/skills/drv-timing-closure/SKILL.md:142, docs/decisions/0014-post-grt-resizer-timing.md:58 |
| `runs/p5_h3_harden7_mem.log` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:133 |
| `runs/p5_h3_harden9.log` | 已收錄 | .claude/skills/librelane-run-debug/SKILL.md:124 |
| `runs/p5_h3_neg-eqy-soc.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:100, .claude/skills/formal-equivalence-eqy/SKILL.md:99 |
| `runs/p5_h3_neg-eqy-soc_fix.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:99, signoff/eqy/README.md:67 |
| `runs/p5_pico_h1_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/core-migration-hazard3/SKILL.md:113, .claude/skills/drv-timing-closure/SKILL.md:145 等 4 處 |
| `runs/p5_pico_h3` | 清理前就已不存在 | .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:91, docs/decisions/0016-cts-no-macro-latency-balancing.md:50 |
| `runs/p5_pico_harden2.log` | 已收錄 | .claude/skills/librelane-run-debug/SKILL.md:124 |
| `runs/p5_pico_neg-eqy-soc.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:100, signoff/eqy/README.md:67 |
| `runs/p5_pico_neg-pnr.log` | 已收錄 | .claude/skills/signoff-checker-qualification/SKILL.md:177 |
| `runs/p5_pre_neg-eqy-core.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:100, signoff/eqy/README.md:67 |
| `runs/p5_regress_hazard3.console` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:135 |
| `runs/p5fin_pico_regress_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/signoff-checker-qualification/SKILL.md:179 |
| `runs/p5fin_pico_s4_grt0116` | 清理前就已不存在 | .claude/skills/librelane-run-debug/SKILL.md:62, docs/notes/grt0229_repro.md:63 |
| `runs/p5final_regress_hazard3.console` | 已收錄 | docs/phase_exit/phase5.md:24 |
| `runs/p5final_regress_picorv32.console` | 已收錄 | docs/phase_exit/phase5.md:25 |
| `runs/p6_3m_h3_signoff/` | 目錄：收錄其中 11 個檔 | signoff/golden/soc_top_hazard3/README.md:12, signoff/golden/soc_top_hazard3/README.md:9 |
| `runs/p6_3m_h3_signoff/criteria_review.md` | 已收錄 | signoff/golden/soc_top_hazard3/README.md:12 |
| `runs/p6_3m_harden_h3.log` | 已收錄 | signoff/golden/soc_top_hazard3/README.md:11 |
| `runs/p6_3m_harden_pico.log` | 已收錄 | signoff/golden/soc_top/README.md:11 |
| `runs/p6_3m_pico_signoff/` | 目錄：收錄其中 11 個檔 | .claude/skills/hard-macro-integration/SKILL.md:52, signoff/golden/soc_top/README.md:12 等 3 處 |
| `runs/p6_3m_pico_signoff/criteria_review.md` | 已收錄 | .claude/skills/hard-macro-integration/SKILL.md:52, signoff/golden/soc_top/README.md:12 |
| `runs/p6_4c2_eqy-soc_h3.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:103 |
| `runs/p6_4c2_neg-eqy-soc_h3.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:104 |
| `runs/p6_4c3_neg-eqy-2cases_h3.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:105 |
| `runs/p6_4c3_neg-eqy-soc_pico.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:108 |
| `runs/p6_4c3_summary.txt` | 已收錄 | docs/notes/openram_phase6_bringup.md:423 |
| `runs/p6_4c4_summary.txt` | 已收錄 | docs/notes/openram_phase6_bringup.md:423 |
| `runs/p6_4c_eqy-soc_h3.log` | 已收錄 | .claude/skills/formal-equivalence-eqy/SKILL.md:103 |
| `runs/p6_4c_summary.txt` | 已收錄 | docs/notes/openram_phase6_bringup.md:412 |
| `runs/p6_devfix_summary.txt` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:139 |
| `runs/p6_drcfix/arv_small_1rw1r_16x64_8.py` | 已收錄 | docs/notes/openram_phase6_bringup.md:391 |
| `runs/p6_extract_trial/` | 目錄：收錄其中 4 個檔 | .claude/skills/sram-layout-extraction/SKILL.md:56, docs/decisions/0018-openram-self-generated-macro.md:122 等 7 處 |
| `runs/p6_extract_trial/sta_whatif/dout_load.log` | 已收錄 | docs/phase_exit/phase6.md:122 |
| `runs/p6_extract_trial/sta_whatif/sram_hold.log` | 已收錄 | docs/phase_exit/phase6.md:135 |
| `runs/p6_fp_pico` | 目錄：未收錄（260 MB 的 run 中間產物） | .claude/skills/macro-qualification/SKILL.md:67, docs/decisions/0006-soc-die-area.md:46 等 4 處 |
| `runs/p6_fp_pico.console` | 已收錄 | .claude/skills/macro-qualification/SKILL.md:67 |
| `runs/p6_openram_macro_fix2.log` | 已收錄 | docs/decisions/0018-openram-self-generated-macro.md:99 |
| `runs/p6_review/doc_check.md` | 已收錄 | docs/phase_exit/phase6.md:223 |
| `runs/p6_review/holes/` | 目錄：未收錄（1408 MB 的 run 中間產物） | docs/phase_exit/phase6.md:223 |
| `runs/p6close_attempt1/` | 目錄：收錄其中 7 個檔 | .claude/skills/phase-exit-review/SKILL.md:61, docs/phase_exit/phase6.md:179 等 3 處 |
| `runs/p6close_negchar.console` | 已收錄 | docs/phase_exit/phase6.md:117 |
| `runs/p6close_regress_hazard3.console` | 已收錄 | docs/phase_exit/phase6.md:31 |
| `runs/p6close_regress_picorv32.console` | 已收錄 | docs/phase_exit/phase6.md:32 |
| `runs/p6final_summary.txt` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:140, docs/notes/openram_phase6_bringup.md:428 |
| `runs/p7_confirm_signoff` | 目錄：收錄其中 11 個檔 | docs/decisions/0019-phase7-caravel-precheck.md:150, signoff/golden/user_project_wrapper/README.md:43 |
| `runs/p7_confirm_signoff/criteria_review.md` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:150 |
| `runs/p7_decap_confirm_signoff` | 目錄：收錄其中 11 個檔 | docs/decisions/0019-phase7-caravel-precheck.md:188, signoff/golden/user_project_wrapper/README.md:44 |
| `runs/p7_decap_confirm_signoff/criteria_review.md` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:188 |
| `runs/p7_decap_signoff` | 目錄：收錄其中 12 個檔 | .claude/skills/signoff-criteria/SKILL.md:249, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:99 等 5 處 |
| `runs/p7_decap_signoff/` | 目錄：收錄其中 12 個檔 | .claude/skills/signoff-criteria/SKILL.md:249, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:99 等 5 處 |
| `runs/p7_decap_signoff/criteria_review.md` | 已收錄 | .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:99, docs/decisions/0019-phase7-caravel-precheck.md:184 等 3 處 |
| `runs/p7_decap_signoff/metrics.json` | 已收錄 | signoff/golden/user_project_wrapper/README.md:14 |
| `runs/p7_exit_draft/` | 目錄：收錄其中 5 個檔 | docs/notes/flow_retro/retro_p6_7.md:105, docs/notes/flow_retro/retro_p6_7.md:34 等 9 處 |
| `runs/p7_exit_draft/carryover.md` | 已收錄 | docs/relaxation_register.md:19 |
| `runs/p7_exit_draft/dout0_whatif.md` | 已收錄 | docs/notes/flow_retro/retro_p6_7.md:34, docs/phase_exit/phase7.md:113 等 3 處 |
| `runs/p7_exit_draft/sram_sta.md` | 已收錄 | docs/phase_exit/phase7.md:132, docs/phase_exit/phase7.md:137 等 4 處 |
| `runs/p7_exp_loop` | 目錄：未收錄（239 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:152 |
| `runs/p7_exp_loop22` | 目錄：未收錄（239 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:152 |
| `runs/p7_exp_pl_dens` | 目錄：未收錄（8868 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:154, .claude/skills/floorplan-congestion/SKILL.md:49 等 3 處 |
| `runs/p7_exp_pl_pad` | 目錄：未收錄（8911 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:154, .claude/skills/floorplan-congestion/SKILL.md:49 |
| `runs/p7_exp_rd2` | 目錄：未收錄（8139 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:150 |
| `runs/p7_exp_rd3` | 目錄：未收錄（8141 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:150 |
| `runs/p7_floorplan1` | 目錄：未收錄（563 MB 的 run 中間產物） | .claude/skills/chip-floorplan-pin-planning/SKILL.md:66 |
| `runs/p7_floorplan2` | 目錄：未收錄（637 MB 的 run 中間產物） | .claude/skills/chip-floorplan-pin-planning/SKILL.md:66 |
| `runs/p7_floorplan4` | 目錄：收錄其中 1 個檔 | .claude/skills/caravel-user-project-integration/SKILL.md:98, docs/report/figures/SOURCES.md:83 等 3 處 |
| `runs/p7_floorplan4/21-openroad-generatepdn/` | 目錄：收錄其中 1 個檔 | .claude/skills/caravel-user-project-integration/SKILL.md:98 |
| `runs/p7_floorplan4/28-openroad-globalplacement/user_project_wrapper.def` | 未收錄（29 MB） | docs/report/figures/SOURCES.md:83 |
| `runs/p7_formal2_eqy.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:190 |
| `runs/p7_formal2_gl.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:191 |
| `runs/p7_formal2_ir.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:192, docs/notes/flow_retro/retro_p6_7.md:22 等 3 處 |
| `runs/p7_formal_eqy.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:152 |
| `runs/p7_formal_gl.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:153 |
| `runs/p7_formal_ir.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:154, signoff/golden/user_project_wrapper/README.md:19 |
| `runs/p7_formal_precheck.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:193, docs/notes/caravel_precheck_phase7.md:153 等 3 處 |
| `runs/p7_formal_signoff/` | 目錄：收錄其中 11 個檔 | .claude/skills/phase-exit-review/SKILL.md:21, .claude/skills/signoff-criteria/SKILL.md:249 等 8 處 |
| `runs/p7_formal_signoff/criteria_review.md` | 已收錄 | .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:93, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:97 等 4 處 |
| `runs/p7_harden1_out/` | 目錄：收錄其中 6 個檔 | .claude/skills/drv-timing-closure/SKILL.md:147 |
| `runs/p7_harden2/79-openroad-repairdesignpostgrt/state_in.json` | 已收錄 | .claude/skills/librelane-run-debug/SKILL.md:130 |
| `runs/p7_harden2_out/attempt2_margin005/` | 目錄：收錄其中 3 個檔 | .claude/skills/caravel-user-project-integration/SKILL.md:103, docs/decisions/0019-phase7-caravel-precheck.md:74 |
| `runs/p7_harden2_out/console.log` | 已收錄 | .claude/skills/librelane-run-debug/SKILL.md:130 |
| `runs/p7_harden3/01-openroad-repairdesignpostgrt/` | 目錄：未收錄（6 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:148 |
| `runs/p7_harden5/final/def/` | 目錄：未收錄（288 MB 的 run 中間產物） | .claude/skills/drv-timing-closure/SKILL.md:153 |
| `runs/p7_harden_confirm.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:150, signoff/golden/user_project_wrapper/README.md:43 |
| `runs/p7_harden_decap.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:180, signoff/golden/user_project_wrapper/README.md:15 |
| `runs/p7_harden_decap_confirm.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:188, signoff/golden/user_project_wrapper/README.md:44 |
| `runs/p7_harden_formal.log` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:143, signoff/golden/user_project_wrapper/README.md:17 |
| `runs/p7_hold_probe/` | 目錄：收錄其中 5 個檔 | .claude/skills/drv-timing-closure/SKILL.md:147 |
| `runs/p7_precheck_preview/check.log` | 已收錄 | docs/notes/caravel_precheck_phase7.md:114 |
| `runs/p7_precheck_verify/` | 目錄：收錄其中 1 個檔 | .claude/skills/tapeout-precheck-caravel/SKILL.md:88, docs/notes/caravel_precheck_phase7.md:140 |
| `runs/p7_precheck_verify/check.log` | 已收錄 | docs/notes/caravel_precheck_phase7.md:140 |
| `runs/p7_review/` | 目錄：收錄其中 11 個檔 | .claude/skills/caravel-user-project-integration/SKILL.md:105, .claude/skills/caravel-user-project-integration/SKILL.md:77 等 37 處 |
| `runs/p7_review/checker_holes.md` | 已收錄 | .claude/skills/signoff-checker-qualification/SKILL.md:184, docs/notes/flow_retro/retro_p6_7.md:36 等 3 處 |
| `runs/p7_review/chipfoundry_fill.md` | 已收錄 | docs/decisions/0019-phase7-caravel-precheck.md:213, docs/notes/flow_retro/retro_p6_7.md:28 等 6 處 |
| `runs/p7_review/doc_check.md` | 已收錄 | .claude/skills/phase-exit-review/SKILL.md:21, .claude/skills/phase-exit-review/SKILL.md:43 等 7 處 |
| `runs/p7_review/doc_fixes.md` | 已收錄 | docs/phase_exit/phase7.md:252 |
| `runs/p7_review/fill_trial` | 目錄：收錄其中 3 個檔 | .claude/skills/caravel-user-project-integration/SKILL.md:105, .claude/skills/caravel-user-project-integration/SKILL.md:77 等 18 處 |
| `runs/p7_review/fill_trial/` | 目錄：收錄其中 3 個檔 | .claude/skills/caravel-user-project-integration/SKILL.md:105, .claude/skills/caravel-user-project-integration/SKILL.md:77 等 15 處 |
| `runs/p7_review/fill_trial/README.md` | 已收錄 | .claude/skills/caravel-user-project-integration/SKILL.md:105, .claude/skills/caravel-user-project-integration/SKILL.md:77 等 9 處 |
| `runs/p7_review/fill_trial/aggregate.py` | 已收錄 | docs/report/figures/SOURCES.md:108, docs/report/figures/scripts/density_fill_trial.py:7 |
| `runs/p7_review/fill_trial/nofill/density.log` | 已收錄 | docs/report/figures/SOURCES.md:107 |
| `runs/p7_review/holes/` | 目錄：未收錄（1719 MB 的 run 中間產物） | docs/decisions/0019-phase7-caravel-precheck.md:214, docs/phase_exit/phase7.md:241 |
| `runs/p7_skew_analysis/README.md` | 已收錄 | .claude/skills/cts-clock-tree/SKILL.md:71, .claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md:151 等 5 處 |
| `runs/p7close2_h3_neg_precheck_ref_klayout_sig11.log` | 已收錄 | .claude/skills/signoff-checker-qualification/SKILL.md:145, .claude/skills/tapeout-precheck-caravel/SKILL.md:90 等 5 處 |
| `runs/p7close2_regress_caravel.console` | 已收錄 | docs/phase_exit/phase7.md:28 |
| `runs/p7close2_regress_hazard3.console` | 已收錄 | docs/phase_exit/phase7.md:30 |
| `runs/p7close2_regress_hazard3.enospc.console` | 已收錄 | docs/phase_exit/phase7.md:33 |
| `runs/p7close2_regress_hazard3.sig11.console` | 已收錄 | .claude/skills/tapeout-precheck-caravel/SKILL.md:90 |
| `runs/p7close2_regress_picorv32.console` | 已收錄 | .claude/skills/flow-regression-reproducibility/SKILL.md:142, docs/phase_exit/phase7.md:29 |
| `runs/p7close2_regress_picorv32.enospc.console` | 已收錄 | docs/phase_exit/phase7.md:33 |
| `runs/picorv32_core` | 目錄：未收錄（1768 MB 的 run 中間產物） | .claude/skills/flow-regression-reproducibility/SKILL.md:141, Makefile:333 等 22 處 |
| `runs/picorv32_core/` | 目錄：未收錄（1768 MB 的 run 中間產物） | docs/phase_exit/phase2.md:10, docs/report/figures/SOURCES.md:38 等 5 處 |
| `runs/picorv32_core/final/gds/picorv32.gds` | 未收錄（30 MB） | docs/phase_exit/phase2.md:10, docs/report/figures/SOURCES.md:38 等 3 處 |
| `runs/picorv32_core_signoff/` | 目錄：收錄其中 7 個檔 | .claude/skills/flow-regression-reproducibility/SKILL.md:141, Makefile:333 等 11 處 |
| `runs/picorv32_core_signoff/criteria_review.md` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:141, docs/phase_exit/phase5.md:32 等 4 處 |
| `runs/picorv32_core_signoff/metrics.json` | 已收錄 | signoff/golden/picorv32_core/README.md:64, signoff/golden/picorv32_core/README.md:9 |
| `runs/picorv32_core_signoff/provenance.json` | 清理前就已不存在 | Makefile:333 |
| `runs/picorv32_core_signoff/signoff.txt` | 已收錄 | signoff/golden/picorv32_core/README.md:62 |
| `runs/precheck_sram_ref` | 目錄：收錄其中 7 個檔 | Makefile:244, signoff/precheck/README.md:56 |
| `runs/precheck_sram_ref/` | 目錄：收錄其中 7 個檔 | signoff/precheck/README.md:56 |
| `runs/regress` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:142, Makefile:109 等 26 處 |
| `runs/regress/` | 清理前就已不存在 | Makefile:109, README.md:77 等 11 處 |
| `runs/regress/summary.md` | 清理前就已不存在 | docs/phase_exit/phase3_5.md:16, docs/phase_exit/phase3_5.md:9 等 8 處 |
| `runs/regress_caravel` | 清理前就已不存在 | Makefile:96, README.md:77 等 4 處 |
| `runs/regress_caravel/` | 清理前就已不存在 | Makefile:96, README.md:77 等 3 處 |
| `runs/regress_caravel/summary.md` | 清理前就已不存在 | docs/phase_exit/phase7.md:28 |
| `runs/regress_picorv32` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:142, Makefile:92 等 10 處 |
| `runs/regress_picorv32/` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:142, Makefile:92 等 8 處 |
| `runs/regress_picorv32/neg-eqy-core.log` | 清理前就已不存在 | .claude/skills/flow-regression-reproducibility/SKILL.md:142 |
| `runs/regress_picorv32/summary.md` | 清理前就已不存在 | docs/phase_exit/phase5.md:25, docs/phase_exit/phase5.md:53 等 4 處 |
| `runs/rtl` | 目錄：收錄其中 6 個檔 | Makefile:489, rtl/scripts/lint.sh:19 等 7 處 |
| `runs/rtl/lint` | 目錄：未收錄（0 MB 的 run 中間產物） | rtl/scripts/lint.sh:19, rtl/scripts/lint.sh:27 |
| `runs/rtl/synth` | 目錄：收錄其中 3 個檔 | rtl/scripts/synth_check.sh:20, rtl/scripts/synth_check.sh:22 等 4 處 |
| `runs/rtl/synth_hazard3` | 目錄：收錄其中 3 個檔 | rtl/scripts/synth_check.sh:22, rtl/scripts/synth_check.sh:33 |
| `runs/rtl/synth_hazard3/` | 目錄：收錄其中 3 個檔 | rtl/scripts/synth_check.sh:22 |
| `runs/sdc075_10` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:133, .claude/skills/timing-constraints-sdc/SKILL.md:63 |
| `runs/sdc075_10/out/max_ss_100C_1v60/sta.log` | 清理前就已不存在 | .claude/skills/timing-constraints-sdc/SKILL.md:63 |
| `runs/sim` | 目錄：收錄其中 2 個檔 | Makefile:489, docs/spec/soc_spec.md:371 等 18 處 |
| `runs/sim/junit.xml` | 已收錄 | docs/spec/soc_spec.md:372, dv/README.md:47 等 3 處 |
| `runs/sim/summary.json` | 已收錄 | docs/spec/soc_spec.md:372, dv/README.md:47 等 3 處 |
| `runs/sim_` | 清理前就已不存在 | Makefile:489, dv/README.md:118 等 10 處 |
| `runs/sim_build` | 目錄：未收錄（1209 MB 的 run 中間產物） | Makefile:489, dv/README.md:118 等 7 處 |
| `runs/sim_build/` | 目錄：未收錄（1209 MB 的 run 中間產物） | dv/README.md:118, dv/README.md:50 等 5 處 |
| `runs/sim_build/filelists/` | 目錄：未收錄（0 MB 的 run 中間產物） | dv/README.md:118, dv/scripts/dvlib.py:574 |
| `runs/sim_hazard3/` | 目錄：收錄其中 1 個檔 | dv/scripts/regress.py:9 |
| `runs/soc_area_estimate/estimate.json` | 已收錄 | scripts/soc_area_estimate.py:14 |
| `runs/soc_top` | 目錄：收錄其中 1 個檔 | .claude/skills/drv-timing-closure/SKILL.md:132, .claude/skills/drv-timing-closure/SKILL.md:138 等 61 處 |
| `runs/soc_top.prev` | 目錄：未收錄（4304 MB 的 run 中間產物） | .claude/skills/macro-qualification/SKILL.md:68, .claude/skills/signoff-checker-qualification/SKILL.md:181 |
| `runs/soc_top/` | 目錄：收錄其中 1 個檔 | .claude/skills/drv-timing-closure/SKILL.md:132, .claude/skills/hard-macro-integration/SKILL.md:52 等 12 處 |
| `runs/soc_top/46-openroad-detailedrouting/openroad-detailedrouting.log` | 已收錄 | .claude/skills/hard-macro-integration/SKILL.md:52 |
| `runs/soc_top/56-openroad-stapostpnr/min_ss_100C_1v60/max.rpt` | 清理前就已不存在 | .claude/skills/timing-constraints-sdc/SKILL.md:65 |
| `runs/soc_top/65-magic-drc/reports/drc.magic.rpt` | 清理前就已不存在 | docs/notes/phase3_review/drc_position_compare.py:4 |
| `runs/soc_top/final/def/soc_top.def` | 未收錄（25 MB） | .claude/skills/drv-timing-closure/SKILL.md:132 |
| `runs/soc_top/final/nl/soc_top.nl.v` | 未收錄（6 MB） | docs/notes/repair_design_loop.md:108, dv/gl_soc/README.md:12 |
| `runs/soc_top_hazard3` | 目錄：收錄其中 2 個檔 | .claude/skills/drv-timing-closure/SKILL.md:138, .claude/skills/drv-timing-closure/SKILL.md:139 等 28 處 |
| `runs/soc_top_hazard3/` | 目錄：收錄其中 2 個檔 | .claude/skills/drv-timing-closure/SKILL.md:138, .claude/skills/drv-timing-closure/SKILL.md:139 等 13 處 |
| `runs/soc_top_hazard3/37-openroad-resizertimingpostcts/` | 目錄：收錄其中 1 個檔 | .claude/skills/drv-timing-closure/SKILL.md:139 |
| `runs/soc_top_hazard3/38-openroad-stamidpnr-2/` | 目錄：收錄其中 1 個檔 | .claude/skills/librelane-run-debug/SKILL.md:121 |
| `runs/soc_top_hazard3/56-openroad-stapostpnr/max_ss_n40C_1v60/` | 清理前就已不存在 | .claude/skills/drv-timing-closure/SKILL.md:138, docs/decisions/0013-resizer-sees-ss-n40c.md:58 |
| `runs/soc_top_hazard3/final/gds/soc_top.gds` | 未收錄（41 MB） | docs/notes/problem_review/verify_and_merge.md:225, docs/report/figures/SOURCES.md:36 等 3 處 |
| `runs/soc_top_hazard3_signoff/` | 目錄：收錄其中 14 個檔 | Makefile:333, docs/notes/repair_design_loop.md:7 等 8 處 |
| `runs/soc_top_hazard3_signoff/console.log` | 已收錄 | docs/notes/repair_design_loop.md:7 |
| `runs/soc_top_hazard3_signoff/criteria_review.md` | 已收錄 | docs/phase_exit/phase5.md:30, docs/phase_exit/phase6.md:37 等 3 處 |
| `runs/soc_top_hazard3_signoff/metrics.json` | 已收錄 | signoff/golden/soc_top_hazard3/README.md:9 |
| `runs/soc_top_hazard3_signoff/provenance.json` | 已收錄 | Makefile:333 |
| `runs/soc_top_hazard3_signoff/signoff.txt` | 已收錄 | docs/phase_exit/phase5.md:50 |
| `runs/soc_top_signoff.prev/criteria_review.txt` | 已收錄 | signoff/scripts/test_review_hook.py:69 |
| `runs/soc_top_signoff/` | 目錄：收錄其中 13 個檔 | .claude/skills/librelane-run-debug/SKILL.md:128, Makefile:333 等 12 處 |
| `runs/soc_top_signoff/criteria_review.md` | 已收錄 | .claude/skills/librelane-run-debug/SKILL.md:128, docs/phase_exit/phase5.md:31 等 4 處 |
| `runs/soc_top_signoff/metrics.json` | 已收錄 | signoff/golden/soc_top/README.md:9 |
| `runs/soc_top_signoff/provenance.json` | 已收錄 | Makefile:333 |
| `runs/soc_top_signoff/result.txt` | 已收錄 | dv/gl_soc/README.md:33, pnr/soc_top/README.md:17 |
| `runs/soc_top_signoff/retries.txt` | 清理前就已不存在 | docs/phase_exit/phase4.md:12, docs/phase_exit/phase5.md:27 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/char.log` | 已收錄 | docs/notes/openram_phase6_bringup.md:254 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/` | 目錄：收錄其中 1 個檔 | .claude/skills/openram-macro-characterization/SKILL.md:171, .claude/skills/openram-macro-characterization/SKILL.md:175 等 3 處 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/dcop/` | 目錄：未收錄（232 MB 的 run 中間產物） | .claude/skills/openram-macro-characterization/SKILL.md:175 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/drift.py` | 已收錄 | docs/notes/openram_phase6_bringup.md:315 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/openram-power.log` | 已收錄 | .claude/skills/openram-macro-characterization/SKILL.md:173 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/power/full/` | 目錄：未收錄（38 MB 的 run 中間產物） | .claude/skills/openram-macro-characterization/SKILL.md:174 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/power_try.json` | 已收錄 | docs/notes/openram_phase6_bringup.md:275 |
| `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/schematic/` | 目錄：未收錄（554 MB 的 run 中間產物） | docs/notes/openram_phase6_bringup.md:254 |
| `runs/sram_char/neg/` | 目錄：未收錄（23 MB 的 run 中間產物） | ip/sram/char/neg_char.py:4 |
| `runs/sram_char/neg_char2.log` | 已收錄 | docs/decisions/0010-sram-spice-characterization.md:171, docs/phase_exit/phase3_5.md:103 |
| `runs/sram_char/neg_char_20261010.log` | 已收錄 | docs/notes/openram_phase6_bringup.md:270 |
| `runs/sram_char/neg_char_full2.log` | 已收錄 | docs/phase_exit/phase5.md:177 |
| `runs/sram_char/neg_char_n5n8_6316ea9.log` | 已收錄 | docs/decisions/0010-sram-spice-characterization.md:171, docs/phase_exit/phase3_5.md:103 |
| `runs/sram_char/schematic/` | 目錄：未收錄（531 MB 的 run 中間產物） | ip/sram/char/confirm_char_lib.py:17 |
| `runs/sram_drc_baseline` | 清理前就已不存在 | docs/notes/phase3_review/README.md:7, docs/notes/phase3_review/drc_position_compare.py:4 |
| `runs/sram_drc_baseline/out/reports/drc.magic.rpt` | 清理前就已不存在 | docs/notes/phase3_review/drc_position_compare.py:4 |
| `runs/sram_extract/` | 清理前就已不存在 | ip/sram/char/extract_sram.py:4 |
| `runs/test_flow_retry` | 清理前就已不存在 | pnr/test_librelane_flow.sh:22 |
| `runs/todo.md` | 已收錄 | .claude/skills/phase-exit-review/SKILL.md:13, .claude/skills/phase-exit-review/SKILL.md:3 等 21 處 |
| `runs/user_project_wrapper` | 目錄：收錄其中 2 個檔 | .claude/skills/pdn-ir-drop/SKILL.md:40, .claude/skills/phase-exit-review/SKILL.md:21 等 32 處 |
| `runs/user_project_wrapper.prev/flow.log` | 已收錄 | .claude/skills/signoff-criteria/SKILL.md:109, .claude/skills/signoff-criteria/SKILL.md:280 等 4 處 |
| `runs/user_project_wrapper/` | 目錄：收錄其中 2 個檔 | .claude/skills/pdn-ir-drop/SKILL.md:40, README.md:79 等 7 處 |
| `runs/user_project_wrapper/final/gds/user_project_wrapper.gds` | 未收錄（103 MB） | docs/notes/problem_review/verify_and_merge.md:226, docs/report/figures/SOURCES.md:35 等 3 處 |
| `runs/user_project_wrapper/final/metrics.json` | 已收錄 | docs/report/figures/SOURCES.md:99, docs/report/figures/scripts/timing_wrapper_corners.py:11 |
| `runs/user_project_wrapper/resolved.json` | 已收錄 | .claude/skills/pdn-ir-drop/SKILL.md:40 |
| `runs/user_project_wrapper_signoff` | 目錄：收錄其中 12 個檔 | .claude/skills/phase-exit-review/SKILL.md:21, .claude/skills/signoff-criteria/SKILL.md:251 等 8 處 |
| `runs/user_project_wrapper_signoff/` | 目錄：收錄其中 12 個檔 | .claude/skills/phase-exit-review/SKILL.md:21, .claude/skills/signoff-criteria/SKILL.md:251 等 7 處 |
| `runs/user_project_wrapper_signoff/criteria_review.md` | 已收錄 | docs/phase_exit/phase7.md:43 |
| `runs/user_project_wrapper_signoff/provenance.json` | 已收錄 | Makefile:333 |
| `runs/wall_times.txt` | 清理前就已不存在 | docs/notes/ir_study/parse.py:4 |
| `runs/x` | 清理前就已不存在 | scripts/collect_evidence.py:198, scripts/collect_evidence.py:199 等 4 處 |
