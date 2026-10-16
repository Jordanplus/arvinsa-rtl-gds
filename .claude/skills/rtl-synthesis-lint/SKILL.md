---
name: rtl-synthesis-lint
description: Yosys 合成與 lint 的問題時使用。常見症狀：合成 log 的 `Recoding FSM ... mapping auto encoding to one-hot`（RTL 對 netlist 的 formal 比對因此對不上）、暫存器被換成常數（tie-low）、`cpu-params` FAIL（harden 的 `SYNTH_PARAMETERS` 與 SoC 裡 instance 的參數不同，RTL 有 `defparam`、`SYNTHESIS` define 讓參數不同，或 `config.json has conditional blocks ... not supported by this check`，即 config 的 `pdk::`／`scl::` 條件區塊）、LibreLane／Verilator lint 警告數變了、latch。也用在為了縮短週期調整合成（策略、邏輯深度）。對 formal 比對的影響看 formal-equivalence-eqy。Use for Yosys synthesis settings, parameter consistency between harden and SoC, lint, latches, FSM recoding and logic depth in the LibreLane flow.
---

# RTL 合成與 lint

PnR 階段的時序修復看 `drv-timing-closure`；合成對 formal equivalence 的影響看 `formal-equivalence-eqy`。目前經驗較少：本 repo 沒有為縮短週期調整過合成，週期都是由 PnR 與 signoff 的結果決定（40 → 42 → 43 → 44 ns，經過見 ADR-0004 與它的 Phase 4、Phase 3.5、Phase 5 補充）。本 repo 實例：`rtl/scripts/`、`pnr/picorv32_core/cpu_params.py`、LibreLane `librelane/scripts/pyosys/synthesize.py`。

## 規則（已驗證）

1. **參數一致**：harden 用的 `SYNTH_PARAMETERS` 必須等於 SoC 裡該 instance 的參數；用 Yosys 讀 RTL 取值比對，不比字串；`defparam` 與 `SYNTHESIS` define 會造成差異，要直接判 FAIL（`cpu_params.py`）。Yosys 會忽略 `defparam`。
   - LibreLane config 的 `pdk::`／`scl::` 條件區塊會依 PDK 換掉參數，蓋過 checker 讀到的 `SYNTH_PARAMETERS`，所以參數一致的 checker 看到條件區塊就直接 FAIL（`cpu_params.py` 的 `config_params()`，訊息 `config.json has conditional blocks [...]; not supported by this check`）。Phase 2 獨立審查植入這個錯誤，修正後抓到（`docs/phase_exit/phase2.md` 第 70、79 行）。
   - checker 也要比 harden run 實際用的參數（`cpu_params.py --resolved` 讀 run 的 `resolved.json`，`signoff-checker-qualification` 規則 3）。
2. **LibreLane synthesis 一律跑 `fsm`**（`synthesize.py` 186 行），會把狀態機改成 one-hot（PicoRV32：`cpu_state` 8 → 6 bit、`mem_wordsize` 2 → 3 bit），沒有關閉選項。合成 log 的 `FSM_RECODE` 段落有對照表。這會讓 RTL 對 netlist 的 formal 比對失敗。
3. **上電值未定、寫入後恆為常數的暫存器**會被合成換成常數（例：`mem_addr[1:0]` 接 tie-low），屬於 X 語意下的合法最佳化，但 RTL 模擬時這些 bit 在第一次寫入前是 X。
4. **lint**：LibreLane 的 `Verilator.Lint` 警告只計數、不判 FAIL；警告來自第三方 RTL（CPU core、simpleuart）與 LibreLane 產生的 cell blackbox（`TIMESCALEMOD`），自己寫的 RTL 為 0。數量（`design__lint_warning__count`）與 latch 數（`design__inferred_latch__count`）由 golden 鎖定（`signoff/golden/<design>/metrics.json`；名稱含 lint、latch 的 metric 一律不給誤差，`check_signoff.py` 的 `VIOLATION_WORDS`）。專案自己的 lint 規則（Phase 1 `make lint` 與 waiver）以 `rtl/lint/` 為準。

## 已知限制（原「待補」）

- 沒有試過的：`SYNTH_STRATEGY`（AREA／DELAY）對縮短週期的影響、邏輯深度與關鍵路徑分析。要壓週期時再做。
- latch 偵測（`Checker.YosysSynthChecks`）沒有 negative test；目前只靠 golden 的 `design__inferred_latch__count` 鎖在 0。沒有自動檢查能證明 latch 出現時一定會被抓到，原因是還沒有植入 latch 的案例。
- Hazard3 的讀入方式不用另外處理：原始碼是 `.v`，Icarus `-g2005`、Verilator、Yosys 都直接吃得下（`core-migration-hazard3` 規則 13）；原本「SystemVerilog 讀入方式」這一項的前提不對。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | picorv32_core 合成 log | `Recoding FSM ... mapping auto encoding to one-hot` | 已驗證：synthesize.py 固定跑 fsm | EQY 改成證明合成 netlist 與最終 netlist 等價 | `signoff/eqy/README.md` |
| 2026-10-03 | Phase 2 獨立審查（`cpu_params.py`） | checker 看不到 `defparam`、`` `ifdef SYNTHESIS `` 分支、config 的 `pdk::` 條件區塊，也不比 harden run 實際用的參數 | 已驗證：審查者植入，修正前 PASS、修正後 14/14 FAIL | 規則 1 | `docs/phase_exit/phase2.md` 第 70、79 行；`pnr/picorv32_core/cpu_params.py` |
| 2026-10-15 | Phase 0–7 問題總檢討（ADR-0021，`verify_and_merge.md` B10、C2、C3） | 規則 1 沒寫 `pdk::` 條件區塊；開頭的週期寫到 43 ns（現在 44 ns）；規則 4 的 499 個警告是 PicoRV32 版 soc_top 的數字；待補「Hazard3（SystemVerilog）的讀入方式」前提不對 | 已驗證（`review_p0_35.md` 建議 13；`review_skills.md` 3.1 Q17、3.2） | 規則 1 補條件區塊；週期改指向 ADR-0004（42 ns 是 Phase 4 補充）；警告數改指向 golden；待補改成已知限制 | 本檔 |
