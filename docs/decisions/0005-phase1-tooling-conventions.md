# ADR-0005：Phase 1 工具慣例

- 狀態：已採用（2026-10-03）
- 決策與理由：
  1. **GNU make 3.81 相容**：macOS 內建版本不支援 `.SHELLFLAGS`（plan §4 原寫法），改為 Makefile 只轉呼叫 script，嚴格錯誤處理（`set -euo pipefail`）放在 script。
  2. **regression 設定用 TOML**（`dv/tests.toml`、`dv/bugs.toml`），取代 plan 寫的 YAML：Python 3.11+ 內建 `tomllib`，不需額外套件。
  3. **Host write port 為同步介面**、不加 synchronizer：Phase 7 接 Caravel Wishbone 時與 CPU 同一個 clock domain。
  4. **UART bit 長度 = 除數 + 2 clock**（simpleuart 的實作特性）：除數 18、bit 長度 20 clock；testbench 監測器以 20 clock 判定。
  5. **`+skip_boot` 改為 `boot_mode=0`**（plan §5.2）：Boot ROM 讀 boot_mode 腳位直接跳到 SRAM，regression 不需另外的 plusarg。
- 出處：docs/spec/soc_spec.md。
