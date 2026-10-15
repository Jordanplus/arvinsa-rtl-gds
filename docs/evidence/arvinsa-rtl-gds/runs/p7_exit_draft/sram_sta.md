# wrapper 上的 SRAM 邊界量測（2026-10-14，Phase 3.5 限制 14、Phase 5 限制 7 的方法）
- 版圖：runs/user_project_wrapper（550869c 確認 harden，golden 455 個逐值相同）；腳本與 log：sta_wrapper/wrap.tcl、wrap.log（OpenSTA，LibreLane nix-shell；Phase 6 runs/p6_extract_trial/sta_whatif/ 同法）。
- dout0 負載（32 支）：min RC 4.3–25.1 fF；max RC 4.8–27.9 fF。特性化範圍下限 5 fF、.lib 上限 50 fF。Phase 6：Hazard3 3.5 fF、PicoRV32 3.4 fF。→ 仍低於 5 fF（STA 會外插、不警告），沒變。
- SRAM 輸入腳 hold（ff_n40C，final SDC＋propagated clock）：min RC +0.21 ns（u_soc.sram0/addr0[6]）、nom +0.23、max +0.25。Phase 6 Hazard3 soc_top +0.28 ns、PicoRV32 +0.09 ns。
- 腳本最後一行的 `worst overall` 是 format_time 對無窮大的輸出，不使用（Phase 6 log 也一樣）。
