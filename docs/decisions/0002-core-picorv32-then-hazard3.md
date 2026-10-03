# ADR-0002：RISC-V core 先 PicoRV32、後 Hazard3

- 狀態：已採用（2026-10-02，使用者確認）
- 決策：Phase 1–4 用 PicoRV32（Verilog-2005、記憶體介面最單純），Phase 5 換 Hazard3 證明流程可換 core。
- PicoRV32 釘在 `ef203c2b`（上游已於 2026-09 封存，只當 test vehicle）。
- 出處：project-plan.md §2。
