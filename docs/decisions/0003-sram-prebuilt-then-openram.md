# ADR-0003：SRAM 先用 PDK 預建 macro、後用 OpenRAM 自產

- 狀態：已採用（2026-10-02，使用者確認）
- 決策：第一階段用 `sky130_sram_2kbyte_1rw1r_32x512_8`（fossi-foundation/sky130_sram_macros `5ad1c960`，與 open_pdks 同源），只用 port 0；Phase 6 用 OpenRAM 自產並產生多 corner .lib。
- 行為模型 vendor 在 `ip/sram/`，原檔不改，模擬副本只改 `timescale` 與 `VERBOSE`。
- 出處：project-plan.md §5.1、§6。
