# 決策紀錄（ADR）

| 編號 | 決策 | 日期 |
|---|---|---|
| [0001](0001-pdk-sky130a.md) | PDK 用 sky130A，不用 SKY90-FD | 2026-10-02 |
| [0002](0002-core-picorv32-then-hazard3.md) | RISC-V core 先 PicoRV32、後 Hazard3 | 2026-10-02 |
| [0003](0003-sram-prebuilt-then-openram.md) | SRAM 先用 PDK 預建 macro、後用 OpenRAM 自產 | 2026-10-02 |
| [0004](0004-timing-target-40ns.md) | silicon 時序目標 40 ns，25 ns 為 stretch goal | 2026-10-03 |
| [0005](0005-phase1-tooling-conventions.md) | Phase 1 工具慣例：make 3.81 相容、TOML、同步 host port、UART bit 長度 | 2026-10-03 |
| [0006](0006-soc-die-area.md) | soc_top 的 DIE_AREA = 1000 × 800 µm（依 Phase 2 實測面積） | 2026-10-03 |
| [0007](0007-sram-padded-lib.md) | SRAM macro 用保守的 padded.lib 做 STA（9 corner 共用，ss／ff 加 derate）；已由 0010 取代，數值保留為下限 | 2026-10-03 |
| [0008](0008-sram-antenna-lef.md) | SRAM 的 LEF 補上 antenna 資料（ANTENNAGATEAREA，由 macro 自己的 SPICE 算出） | 2026-10-03 |
| [0009](0009-signoff-max-transition.md) | PnR 的 max fanout 用 8；signoff max transition 放寬到 1.0 ns 的決定已撤回（改用 placement 密度 55% 解決） | 2026-10-03 |
| [0010](0010-sram-spice-characterization.md) | SRAM macro 的時序改用本機 ngspice 實測 PDK 附的網表；每個 PVT 一份 .lib，以 0007 的數值為下限，新增 dout0 的 hold 時序弧（Phase 3.5） | 2026-10-04 |
| [0011](0011-hazard3-integration.md) | Phase 5 把 CPU 換成 Hazard3：hazard3_cpu_1port＋AHB 轉 native bus 轉接器、RV32IMC＋計數器、riscv-tests＋RVFI 對 rvcpp 逐指令比對、PicoRV32 版移到 regress-picorv32 | 2026-10-05 |
| [0012](0012-resizer-weak-cell-exclusion.md) | resizer 不准用推不動一顆 buffer 的弱 cell：soc_top 排除 `a2111oi_1`，harden 前用 .lib 查表檢查（`check_weak_cells.py`） | 2026-10-06 |
