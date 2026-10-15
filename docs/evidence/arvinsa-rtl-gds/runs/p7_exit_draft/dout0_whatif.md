# dout0 transition what-if on the wrapper（2026-10-14，Phase 6 限制 1、ADR-0018 決定 20 的方法）
- 版圖：runs/user_project_wrapper（commit 550869c 的確認 harden，與 golden 逐值相同）。
- 做法：runs/p7_dout0_whatif/whatif.py；neg_pnr.rerun 重跑 OpenROAD.STAPostPNR（15 corners），只把 ss_n40C／ss_100C 的 SRAM char .lib 複本中 bus(dout0) 的 rise/fall transition（各 4 張表）改成量到的值 1.40／2.22 ns，延遲照 .lib；sta.log 確認讀到複本。
- 結果（setup ws，ns）：min_ss_n40C 0.548 → 0.151（最差）、nom_ss_n40C 0.639 → 0.242、max_ss_n40C 0.741 → 0.344、min_ss_100C 1.118 → 0.498、nom_ss_100C 1.154 → 0.534、max_ss_100C 1.195 → 0.574；hold 最差 0.187 不變。Checker.SetupViolations rc 0（MET）。
- 對照：Phase 6 soc_top_hazard3 同法 +0.763 → +0.37（ss −40°C）。wrapper 少約 0.22 ns：原本就少 0.11 ns（wb_clk_i→root 長線，runs/p7_skew_analysis/README.md），其餘是 transition 敏感度（推測）。
