---
name: rtl-synthesis-lint
description: 處理 Yosys 合成（策略、參數、狀態機重新編碼、常數化的暫存器）、LibreLane／Verilator lint 警告、latch、邏輯深度，或為了縮短週期調整合成時使用；對 formal 比對的影響看 formal-equivalence-eqy。Use for Yosys synthesis settings, lint, latches, FSM recoding and logic depth in the LibreLane flow.
---

# RTL 合成與 lint

PnR 階段的時序修復看 `drv-timing-closure`；合成對 formal equivalence 的影響看 `formal-equivalence-eqy`。目前經驗較少。Phase 4 判定 25 ns 做不到（SRAM 半週期路徑差約 7 ns，其他路徑在 ss 也差 1.8–4.7 ns），改 42 ns（Phase 3.5 因 SRAM 的 hold 弧再改 43 ns），沒有調整合成；下方待補在要壓週期時再做。本 repo 實例：`rtl/scripts/`、`pnr/picorv32_core/cpu_params.py`、LibreLane `librelane/scripts/pyosys/synthesize.py`。

## 規則（已驗證）

1. **參數一致**：harden 用的 `SYNTH_PARAMETERS` 必須等於 SoC 裡該 instance 的參數；用 Yosys 讀 RTL 取值比對，不比字串；`defparam` 與 `SYNTHESIS` define 會造成差異，要直接判 FAIL（`cpu_params.py`）。Yosys 會忽略 `defparam`。
2. **LibreLane synthesis 一律跑 `fsm`**（`synthesize.py` 186 行），會把狀態機改成 one-hot（PicoRV32：`cpu_state` 8 → 6 bit、`mem_wordsize` 2 → 3 bit），沒有關閉選項。合成 log 的 `FSM_RECODE` 段落有對照表。這會讓 RTL 對網表的 formal 比對失敗。
3. **上電值未定、寫入後恆為常數的暫存器**會被合成換成常數（例：`mem_addr[1:0]` 接 tie-low），屬於 X 語意下的合法最佳化，但 RTL 模擬時這些 bit 在第一次寫入前是 X。
4. **lint**：LibreLane 的 `Verilator.Lint` 警告只計數、不判 FAIL；soc_top 的 499 個警告來自 PicoRV32、simpleuart 與 LibreLane 產生的 cell blackbox（`TIMESCALEMOD`），自己寫的 RTL 為 0。數量由 golden 鎖定。專案自己的 lint 規則（Phase 1 `make lint` 與 waiver）以 `rtl/lint/` 為準。

## 待補

`SYNTH_STRATEGY`（AREA／DELAY）對縮短週期的影響；邏輯深度與關鍵路徑分析；latch 偵測（`Checker.YosysSynthChecks`）的 negative test；Hazard3（SystemVerilog）的讀入方式。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | picorv32_core 合成 log | `Recoding FSM ... mapping auto encoding to one-hot` | 已驗證：synthesize.py 固定跑 fsm | EQY 改證合成網表 vs 最終網表 | `signoff/eqy/README.md` |
