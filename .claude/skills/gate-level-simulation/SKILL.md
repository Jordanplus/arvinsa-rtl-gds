---
name: gate-level-simulation
description: 在網表上跑 regression、比對 RTL 與網表行為（bus trace 或 lockstep）、處理 GL 模擬中的 X、sky130 cell 模型設定與模擬速度時使用。Use for gate-level simulation of synthesized/PnR netlists, RTL-vs-GL comparison and X handling.
---

# Gate-level 模擬

RTL 層級的 DV 規則以 `dv/README.md` 為準；formal 看 `formal-equivalence-eqy`。本 repo 實例：`dv/gl_core/`、`dv/gl_soc/`、`dv/monitors/gl_lockstep.v`。

## 規則（已驗證）

1. **sky130 cell 模型**：`-DFUNCTIONAL -DUNIT_DELAY=#1`（只有 flip-flop 有 1 ns 延遲，組合邏輯無延遲）；檔案取自 LibreLane `resolved.json` 的 `CELL_VERILOG_MODELS`。X 敏感的模擬用 Icarus（`project-plan.md` §7.1）。
2. **兩種比對方式**：
   - 上游 testbench 加 bus trace 逐筆比對（`run_gl_core.py`）。
   - RTL 與網表放同一個 testbench lockstep（網表 module 改名），每個下降緣比輸出與 macro pin；X 規則：RTL 是 0／1 才比，網表必須完全相同（網表 X 也算不同）；RTL 是 X 不比（合成可合法替它選值）（`dv/gl_soc/README.md`）。
3. **lockstep 要證明比對真的有跑**：`gl_compares` > 0；並用植入錯誤確認會 FAIL（網表輸出 buffer 換成反相器 → 每個 cycle 都報不一致）。
4. **宣告順序**：Icarus 要求被引用的訊號先宣告（lockstep 區塊要放在 `cycle` 宣告之後）。
5. **coverage 缺口**：firmware 沒用到的功能 GL 模擬看不到（Phase 2：`rdcycleh`、bus-error IRQ），要靠 formal 補。
6. **時間**：soc_top 13 支測試約 9 分鐘（memtest 87 萬 cycle 占 552 秒）。

## 待補

- **帶電源的網表模擬**（`project-plan.md` §7.1 L5）：用 LibreLane 的 powered netlist（`final/pnl/`，`USE_POWER_PINS`），testbench 驅動 `vccd1`／`vssd1`，確認沒有電源斷線。SRAM 模擬模型與 soc_top 已有 `USE_POWER_PINS` 介面。
- **SDF 反標的時序模擬**：LibreLane 的 STA step 會輸出各 corner 的 `.sdf`（`*-openroad-stapostpnr/<corner>/*.sdf`）。Icarus 對 `$setuphold` 的支援有限，不能當 signoff 證據；要做 timing check 需另找模擬器（規劃提到 CVC，x86_64 Linux）。signoff 仍以 9 corner STA 為準。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | gl-soc bring-up | `Unable to bind wire/reg/memory 'cycle'` | 已驗證：使用早於宣告 | 區塊移到宣告之後 | `dv/tb/tb_soc.v` |
