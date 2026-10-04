---
name: gate-level-simulation
description: 在網表上跑 regression 時使用：sky130 cell 模型的 define、RTL 與網表 lockstep 或 bus trace 比對、X 的處理、帶電源的網表（`USE_POWER_PINS`）、Icarus 的宣告順序、模擬的牆鐘時限與機器負載（逾時誤判）、firmware 沒用到的功能看不到。Use for gate-level simulation of synthesized/PnR netlists (incl. powered netlists), RTL-vs-GL lockstep comparison, X handling and simulation time limits.
---

# Gate-level 模擬

RTL 層級的 DV 規則以 `dv/README.md` 為準；formal 看 `formal-equivalence-eqy`。本 repo 實例：`dv/gl_core/`、`dv/gl_soc/`、`dv/monitors/gl_lockstep.v`。

## 規則（已驗證）

1. **sky130 cell 模型**：`-DFUNCTIONAL -DUNIT_DELAY=#1`（只有 flip-flop 有 1 ns 延遲，組合邏輯無延遲）；檔案取自 LibreLane `resolved.json` 的 `CELL_VERILOG_MODELS`。X 敏感的模擬用 Icarus（`project-plan.md` §7.1）。
2. **兩種比對方式**：
   - 上游 testbench 加 bus trace 逐筆比對（`run_gl_core.py`）。
   - RTL 與網表放同一個 testbench lockstep（網表 module 改名），每個下降緣比輸出與 macro pin；X 規則：RTL 是 0／1 才比，網表必須完全相同（網表 X 也算不同）；RTL 是 X 不比（合成可合法替它選值）（`dv/gl_soc/README.md`）。
3. **lockstep 要證明比對真的有跑**：`gl_compares` > 0；並用植入錯誤確認會 FAIL（網表輸出 buffer 換成反相器 → 每個 cycle 都報不一致）。
4. **宣告順序**：Icarus 要求被引用的訊號先宣告（lockstep 區塊要放在 `cycle` 宣告之後）。用腳本修改網表時也一樣：新加的 `wire` 要放在第一次使用之前，Yosys 不檢查這點（`neg_eqy.edit()`）。
5. **coverage 缺口**：firmware 沒用到的功能 GL 模擬看不到（Phase 2：`rdcycleh`、bus-error IRQ）。formal 只證明合成網表 → 最終網表，合成這一步仍靠模擬，所以要補 directed 測試（`dv-directed-tests`；Phase 4 的 `counters`、`buserr` 在網表植入對應錯誤後都被 lockstep 抓到）。
6. **時間與機器負載**：soc_top 15 支測試約 7 分鐘、帶電源約 9.5 分鐘（Phase 4 regress 4；memtest 87 萬 cycle 是最長的一支，約 430–550 秒）。
   - 每支模擬有牆鐘時限，用途是擋住不再前進的模擬器，不是速度規格；firmware 卡住由 cycle 上限與 `timeout` checker 判定。
   - **gate-level 的時限要用 gate-level 的速度算**：RTL 的 `dvlib.default_timeout`（120 秒＋cycle 上限／4000）套到 gate-level（每秒約 1200–1600 cycle）只剩約 2 倍餘裕。`run_gl_soc.py` 改用 `gl_timeout`（120 秒＋cycle 上限／400），比實測時間多 10–50 倍。
   - 機器忙時每支慢 2–6 倍：Phase 4 預跑與 neg-pnr、EQY 同時跑（hello 4→12 秒、unmapped 12→82 秒，3 支逾時）；**依序執行的 `make regress` 也會遇到**——第 3 次 regress 時 Spotlight 在索引 `runs/`（約 10 個 `mdworker`），memtest 548→952 秒，boot_uart_max 在舊時限 620 秒被停掉，整個 regress FAIL。
   - 手動預跑時 GL 要單獨跑；同時跑了而逾時，先單獨重跑逾時的那幾支，再判斷是不是設計問題（看全部測試是否一致變慢）。
7. **firmware 是建置產物**：`make gl-soc`、`make neg-gl-soc` 讀 `fw/build/`（不在版控），Makefile 要宣告依賴 `fw`。gl-core 不需要，因為它在 export 出來的上游樹裡自己編 firmware（`run_gl_core.py`）。

8. **帶電源的網表模擬（L5，`run_gl_soc.py --powered`）**：
   - 用 `final/pnl/`，加 `-DUSE_POWER_PINS`；testbench 給 `vccd1` = 1、`vssd1` = 0，RTL 與網表兩份都接。
   - `-DFUNCTIONAL` 的 cell model 在 `USE_POWER_PINS` 下每個輸出都經過 `udp_pwrgood_pp$PG`：電源腳沒接 vccd1／vssd1 的 cell 輸出 X，lockstep 就 FAIL（植入：一顆 buffer 的 VPWR 改接 vssd1，`hello` 就抓到）。
   - tap cell（`tapvpwrvgnd_1`）的 LEF 只有 VPWR／VGND 兩個 pin，所以 powered netlist 只接這兩個；它的 Verilog model 卻多宣告 VPB／VNB，Icarus 對每顆 tap 報兩行 `dangling input port ... floating`（soc_top 6635 顆）。只對這個 cell 的這兩個 port 加白名單（`dv/log_whitelist.txt`），其他 cell 不放行。
   - 速度：3 支短測試約 11 秒，與不帶電源差不多；15 支約 17 分鐘（memtest 1004 秒，當時另有 EQY 在跑）。

## 待補
- **SDF 反標的時序模擬**：LibreLane 的 STA step 會輸出各 corner 的 `.sdf`（`*-openroad-stapostpnr/<corner>/*.sdf`）。Icarus 對 `$setuphold` 的支援有限，不能當 signoff 證據；要做 timing check 需另找模擬器（規劃提到 CVC，x86_64 Linux）。signoff 仍以全部 corner（soc_top 15 個）的 STA 為準。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | gl-soc bring-up | `Unable to bind wire/reg/memory 'cycle'` | 已驗證：使用早於宣告 | 區塊移到宣告之後 | `dv/tb/tb_soc.v` |
| 2026-10-04 | 第二次 `make phase3`（乾淨 worktree） | 12/13 支測試 `firmware image ... not found` | 已驗證：`gl-soc` 沒依賴 `fw`，開發目錄有舊的 `fw/build/` 所以沒發現 | Makefile 加依賴；規則 7 | `runs/p3_phase3_clean2.log` |
| 2026-10-04 | Phase 4 L5 第一次 | `log_scan` FAIL：13270 行 `Instantiating module sky130_fd_sc_hd__tapvpwrvgnd_1 with dangling input port 3 (VPB) floating` | 已驗證：tap cell 的 LEF 只有 VPWR／VGND | 只對這個 cell 的 VPB／VNB 加白名單（規則 8） | `dv/log_whitelist.txt` |
| 2026-10-04 | 第三次 `make phase3`，neg-gl-soc | `csb0_inverted` 編譯失敗：`Unable to bind wire ... neg_eqy_inv ... Check for declaration after use` | 已驗證：植入腳本把 `wire` 宣告加在 module 最後 | 宣告移到 `sram0` 前；修正後 11/11 支測試報 `sram0.csb0` 不一致。另外 `mux_swap` 只在 1/11 支測試被抓到，lockstep 能抓到的範圍受 firmware 用到的功能限制（規則 5） | `runs/p3_phase3_clean3.log` |
| 2026-10-04 | Phase 4 預跑（dev fixture，與 neg-pnr、EQY 同時跑） | `gl-soc: FAIL 12/15`：memtest、boot_uart_max、uart_burst `wall-clock timeout: simulation killed after 1370/620/170 s` | 已驗證：機器負載；全部 15 支一致慢 3–6 倍，單獨重跑 3 支 PASS（429、209、23 秒） | 規則 6；不改時限 | `runs/dev5_gl.log`、`runs/gl_dev5_rerun/` |
| 2026-10-04 | Phase 4 `make regress` 第 3 次（乾淨 checkout，`59c6748`） | `gl-soc-powered: FAIL 14/15`：boot_uart_max `wall-clock timeout: simulation killed after 620 s`（regress 1 同一支 304 秒） | 已驗證：Spotlight 索引造成負載（load 17–21，約 10 個 `mdworker`）；時限是照 RTL 速度算的，gate-level 只剩約 2 倍餘裕 | `gl_timeout`（規則 6）；第二次發生，從「不改時限」改成規則 | `runs/p4_regress_clean3.log` |
