# 決策紀錄（ADR）

| 編號 | 決策 | 日期 |
|---|---|---|
| [0001](0001-pdk-sky130a.md) | PDK 用 sky130A，不用 SKY90-FD | 2026-10-02 |
| [0002](0002-core-picorv32-then-hazard3.md) | RISC-V core 先 PicoRV32、後 Hazard3 | 2026-10-02 |
| [0003](0003-sram-prebuilt-then-openram.md) | SRAM 先用 PDK 預建 macro、後用 OpenRAM 自產 | 2026-10-02 |
| [0004](0004-timing-target-40ns.md) | silicon 時序目標 40 ns，25 ns 為 stretch goal | 2026-10-03 |
| [0005](0005-phase1-tooling-conventions.md) | Phase 1 工具慣例：make 3.81 相容、TOML、同步 host port、UART bit 長度 | 2026-10-03 |
| [0006](0006-soc-die-area.md) | soc_top 的 DIE_AREA = 1000 × 800 µm（依 Phase 2 實測面積） | 2026-10-03 |
| [0007](0007-sram-padded-lib.md) | SRAM macro 用保守的 padded.lib 做 STA（9 corner 共用，ss／ff 加 derate） | 2026-10-03 |
| [0008](0008-sram-antenna-lef.md) | SRAM 的 LEF 補上 antenna 資料（ANTENNAGATEAREA，由 macro 自己的 SPICE 算出） | 2026-10-03 |
| [0009](0009-signoff-max-transition.md) | PnR 的 max fanout 用 8；signoff max transition 放寬到 1.0 ns 的決定已撤回（改用 placement 密度 55% 解決） | 2026-10-03 |
