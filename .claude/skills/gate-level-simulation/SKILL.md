---
name: gate-level-simulation
description: 在 netlist 上跑 regression 時使用。常見症狀：Icarus `Unable to bind wire/reg/memory`（宣告順序，含用腳本改 netlist 時）、PG netlist 的 `dangling input port ... floating`（tap cell 的 VPB／VNB）、`wall-clock timeout`（模擬被停掉，時限沒照 gate-level 的速度算或機器負載）、`firmware image ... not found`（沒宣告對 `fw` 的相依）、IR 分析用的 VCD 是 0 bytes 而 run 目錄多出 `wave.vcd`（plusarg 的 prefix 撞到 `$test$plusargs("vcd")`）。涵蓋 sky130 cell 模型的 define、RTL 與 netlist lockstep 或 bus trace 比對、X 的處理、PG netlist（`USE_POWER_PINS`）、dump max power pattern 的 switching activity（`run_gl_soc.py --record-window`、`vcd_window.v`，時脈用 run 的 `CLOCK_PERIOD`）、firmware 沒用到的功能看不到。Use for gate-level simulation of synthesized/PnR netlists (incl. powered netlists), RTL-vs-GL lockstep comparison, X handling, switching-activity recording and simulation time limits.
---

# Gate-level 模擬

RTL 層級的 DV 規則以 `dv/README.md` 為準；formal 看 `formal-equivalence-eqy`。本 repo 實例：`dv/gl_core/`、`dv/gl_soc/`、`dv/monitors/gl_lockstep.v`。

## 規則（已驗證）

1. **sky130 cell 模型**：`-DFUNCTIONAL -DUNIT_DELAY=#1`（只有 flip-flop 有 1 ns 延遲，組合邏輯無延遲）；檔案取自 LibreLane `resolved.json` 的 `CELL_VERILOG_MODELS`。X 敏感的模擬用 Icarus（`project-plan.md` §7.1）。
2. **兩種比對方式**：
   - 上游 testbench 加 bus trace 逐筆比對（`run_gl_core.py`）。
   - RTL 與 netlist 放同一個 testbench lockstep（netlist module 改名），每個下降緣比對輸出與 macro pin；X 規則：RTL 是 0／1 才比對，netlist 必須完全相同（netlist X 也算不同）；RTL 是 X 不比對（合成可合法替它選值）（`dv/gl_soc/README.md`）。
3. **lockstep 要證明比對真的有跑**：`gl_compares` > 0；並用植入錯誤確認會 FAIL（netlist 輸出 buffer 換成反相器 → 每個 cycle 都報不一致）。
4. **宣告順序**：Icarus 要求被引用的訊號先宣告（lockstep 區塊要放在 `cycle` 宣告之後）。用腳本修改 netlist 時也一樣：新加的 `wire` 要放在第一次使用之前，Yosys 不檢查這點（`neg_eqy.edit()`）。同類的 netlist 編輯陷阱：escaped identifier（`\sram_din0[31] ` 這種以 `\` 開頭、以空白結束的名稱）結尾的空白不能去掉，否則後面的逗號會併進名稱，讀檔報 `syntax error, unexpected TOK_ID`（Phase 6，已驗證，`formal-equivalence-eqy` 經驗紀錄 2026-10-10）。
5. **coverage hole**：firmware 沒用到的功能 GL 模擬看不到（Phase 2：`rdcycleh`、bus-error IRQ）。formal 只證明合成 netlist → 最終 netlist，合成這一步仍靠模擬，所以要補 directed 測試（`dv-directed-tests`；Phase 4 的 `counters`、`buserr` 在 netlist 植入對應錯誤後都被 lockstep 抓到）。
6. **時間與機器負載**：各支測試實際跑出來的時間與時限在 `dv/gl_soc/README.md`（PASS 條件第 4 點）；最長的是 cycle 數最多的那幾支（本 repo 是 memtest、boot_uart_max）。
   - 每支模擬有 wall-clock 時限，用途是擋住不再前進的模擬器，不是速度規格；firmware 卡住時，由 cycle 上限與 `timeout` checker 判 FAIL。
   - **gate-level 的時限要用 gate-level 的速度算**：RTL 的 `dvlib.default_timeout`（120 秒＋cycle 上限／4000）套到 gate-level（每秒約 1200–1600 cycle）時，時限只有實際所需時間的約 2 倍。`run_gl_soc.py` 改用 `gl_timeout`（120 秒＋cycle 上限／400），比實際執行時間多 10–50 倍。
   - 機器忙時每支會一致變慢好幾倍：和 neg-pnr、EQY 同時跑會，**依序執行的 `make regress` 也會**（Spotlight 在索引 `runs/` 時）。兩次實際量到的時間在經驗紀錄 2026-10-04 的三列。
   - 手動試跑時 GL 要單獨跑；同時跑了而逾時，先單獨重跑逾時的那幾支，再判斷是不是設計問題（看全部測試是否一致變慢）。
7. **firmware 是 build 產生的檔案**：`make gl-soc`、`make neg-gl-soc` 讀 `fw/build/`（不在版控），Makefile 要宣告對 `fw` 的相依。gl-core 不需要，因為它在 export 出來的上游樹裡自己編 firmware（`run_gl_core.py`）。

8. **PG netlist（含電源／地接腳的 netlist）的模擬（L5，`run_gl_soc.py --powered`）**：
   - 用 `final/pnl/`，加 `-DUSE_POWER_PINS`；testbench 給 `vccd1` = 1、`vssd1` = 0，RTL 與 netlist 兩份都接。
   - `-DFUNCTIONAL` 的 cell model 在 `USE_POWER_PINS` 下每個輸出都經過 `udp_pwrgood_pp$PG`：電源腳沒接 vccd1／vssd1 的 cell 輸出 X，lockstep 就 FAIL（植入：一顆 buffer 的 VPWR 改接 vssd1，`hello` 就抓到）。
   - tap cell（`tapvpwrvgnd_1`）的 LEF 只有 VPWR／VGND 兩個 pin，所以 powered netlist 只接這兩個；它的 Verilog model 卻多宣告 VPB／VNB，Icarus 對每顆 tap 報兩行 `dangling input port ... floating`（soc_top 6635 顆）。只對這個 cell 的這兩個 port 加白名單（`dv/log_whitelist.txt`），其他 cell 不放行。
   - 速度與沒有電源接腳的 netlist 差不多（Phase 4 實際量到的時間見經驗紀錄 2026-10-04「執行時間」那列）。

9. **dump IR 分析用的 switching activity（max power pattern，`run_gl_soc.py --record-window`，ADR-0019 決定 20）**：
   - 做法：firmware 把每段滿負載迴圈標在 GPIO_OUT（`fw/tests/maxpower`：0x5A／0x5B／0x5C），`dv/gl_soc/vcd_window.v` 只在 GPIO 等於 `+irwin_gpio` 時 dump `tb_soc.dut_gl`，那段一結束就 `$finish`；每段各跑一次模擬，輸出 `win_<hex>.vcd`。GPIO 讀 `tb_soc.gpio_out`（RTL 那份的 soc_top 埠），soc_top 與 Caravel 兩種 build 都有；原本讀 Caravel 才有的 `la_data_out[9:2]`，Phase 7 步驟 8 為了 soc_top 的 `make ir-soc` 改掉（Caravel build 裡 `caravel_pins` 每週期比對兩者相同）。
   - 時脈用 signoff 的週期（run 的 `CLOCK_PERIOD`，本 repo 44 ns；testbench 不帶參數時的預設是 40 ns，不是 signoff 週期），讓模擬與 signoff 的條件一致：`--record-window` 從 harden run 的 `resolved.json` 取 `CLOCK_PERIOD`（奇數 ns 或與 `--clk-half-ns` 不同就 FAIL），IR 檢查前再從 VCD 量 clock 週期核對（`ir_pattern.check_inputs()`；Phase 7 審查 H2：原本 Makefile 寫死 22，VCD 用別的週期 dump 也 PASS）。實際量到的影響很小：同一段 pattern 用 40 ns dump 是 5.99 mW、44 ns 是 5.87 mW（nom_tt，約 2%，不是原本以為的 10%；為什麼只差這麼少沒有讀原始碼確認，推測見經驗紀錄 2026-10-13 第二列）。clock net 的功耗 OpenSTA 照 SDC 算，不受 VCD 影響。
   - 只 dump `dut_gl`、只 dump 那一段：從時間 0 dump 整個 testbench，開機與印 UART 的時間會把平均 toggle rate 拉低。三段各約 5000 個週期，每段約 300–350 MB。
   - 每段的檢查：dump 到至少 1000 個週期、VCD 非空、dump 完之前沒有 lockstep 不一致、run 目錄沒有 testbench 自己的 `wave.vcd`（下一條）。完整跑一次 maxpower 的 `gl-caravel` 要 PASS（netlist 在這個 pattern 下與 RTL 每個 cycle 都一致，dump 出的 switching activity 才可信）。
   - **plusarg 名稱不能是現有 plusarg 的延伸**（工具行為的對策，CLAUDE.md 規則 10）：
     - 症狀：dump 的週期數正確，但指定的 VCD 是 0 bytes，run 目錄多了一個幾百 MB 的 `wave.vcd`。
     - 原因（已驗證）：`tb_soc.v` 用 `$test$plusargs("vcd")` 開整個 testbench 的波形 dump；`$test$plusargs` 比對的是 prefix，`+vcd_win=5a` 也算，於是從時間 0 dump 進 `wave.vcd`，之後模組自己的 `$dumpfile` 被忽略（一個模擬只能有一個 dump 檔）。
     - 怎麼發現：`gl-record` 的那一列印出 VCD 大小與 `testbench dump ... present`。
     - 怎麼繞過：用不撞名的 prefix（`irwin_gpio`、`irwin_vcd`）。
     - 怎麼防止再發生：`record_windows()` 要求 VCD 非空、run 目錄沒有 `wave.vcd`，否則 FAIL；negative test `make neg-ir-soc`（`pnr/soc_top/neg_ir.py`）的 `stray_dump`（多傳一個 `vcd` 開頭的 plusarg，`run_gl_soc.py --plusarg`）與 `no_window`（firmware 沒標的 GPIO 值，0 個週期）。

## 待補
- **SDF 反標的時序模擬**：LibreLane 的 STA step 會輸出各 corner 的 `.sdf`（`*-openroad-stapostpnr/<corner>/*.sdf`）。Icarus 對 `$setuphold` 的支援有限，不能當 signoff 證據；要做 timing check 需另找模擬器（規劃提到 CVC，x86_64 Linux）。signoff 仍以全部 corner（soc_top 15 個）的 STA 為準。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | gl-soc bring-up | `Unable to bind wire/reg/memory 'cycle'` | 已驗證：使用早於宣告 | 區塊移到宣告之後 | `dv/tb/tb_soc.v` |
| 2026-10-04 | 第二次 `make phase3`（乾淨 worktree） | 12/13 支測試 `firmware image ... not found` | 已驗證：`gl-soc` 沒宣告對 `fw` 的相依，main worktree 有舊的 `fw/build/` 所以沒發現 | Makefile 加上相依；規則 7 | `runs/p3_phase3_clean2.log` |
| 2026-10-04 | Phase 4 L5 第一次 | `log_scan` FAIL：13270 行 `Instantiating module sky130_fd_sc_hd__tapvpwrvgnd_1 with dangling input port 3 (VPB) floating` | 已驗證：tap cell 的 LEF 只有 VPWR／VGND | 只對這個 cell 的 VPB／VNB 加白名單（規則 8） | `dv/log_whitelist.txt` |
| 2026-10-04 | 第三次 `make phase3`，neg-gl-soc | `csb0_inverted` 編譯失敗：`Unable to bind wire ... neg_eqy_inv ... Check for declaration after use` | 已驗證：植入腳本把 `wire` 宣告加在 module 最後 | 宣告移到 `sram0` 前；修正後 11/11 支測試報 `sram0.csb0` 不一致。另外 `mux_swap` 只在 1/11 支測試被抓到，lockstep 能抓到的範圍受 firmware 用到的功能限制（規則 5） | `runs/p3_phase3_clean3.log` |
| 2026-10-04 | Phase 4 試跑（dev fixture，與 neg-pnr、EQY 同時跑） | `gl-soc: FAIL 12/15`：memtest、boot_uart_max、uart_burst `wall-clock timeout: simulation killed after 1370/620/170 s` | 已驗證：機器負載；全部 15 支一致慢 3–6 倍，單獨重跑 3 支 PASS（429、209、23 秒） | 規則 6；不改時限 | `runs/dev5_gl.log`、`runs/gl_dev5_rerun/` |
| 2026-10-04 | Phase 4 `make regress` 第 3 次（乾淨 checkout，`59c6748`） | `gl-soc-powered: FAIL 14/15`：boot_uart_max `wall-clock timeout: simulation killed after 620 s`（regress 1 同一支 304 秒） | 已驗證：Spotlight 索引造成負載（load 17–21，約 10 個 `mdworker`）；時限是照 RTL 速度算的，gate-level 時只有實際所需時間的約 2 倍 | `gl_timeout`（規則 6）；第二次發生，從「不改時限」改成規則 | `runs/p4_regress_clean3.log` |
| 2026-10-04 | Phase 4 試跑與 regress 的執行時間（原本寫在規則 6、8，2026-10-15 移到這裡） | soc_top 15 支約 7 分鐘、PG netlist 約 9.5 分鐘（regress 4；memtest 87 萬 cycle 最長，約 430–550 秒）。PG netlist：3 支短測試約 11 秒，15 支約 17 分鐘（memtest 1004 秒，當時另有 EQY 在跑）。與 neg-pnr、EQY 同時跑：hello 4 → 12 秒、unmapped 12 → 82 秒。regress 第 3 次 Spotlight 索引時：memtest 548 → 952 秒 | 已驗證（實際量到） | 規則 6 的時限與「機器忙時先單獨重跑」 | `runs/dev5_gl.log`、`runs/p4_regress_clean3.log` |
| 2026-10-13 | Phase 7 IR max power pattern（`p7_harden2` netlist，`--record-window 5a,5b,5c`） | 三段都 dump 到正確的週期數（5328／5048／4904），指定的 VCD 卻是 0 bytes，run 目錄各多一個 400–780 MB 的 `wave.vcd` | 已驗證：`$test$plusargs("vcd")` 比對 prefix，`+vcd_win=` 觸發整個 testbench 從時間 0 dump 波形；改名後三段 VCD 各 300–350 MB、沒有 `wave.vcd` | plusarg 改名 `irwin_*`；`record_windows()` 檢查 VCD 非空、沒有 `wave.vcd`；規則 9 | `dv/gl_soc/run_gl_soc.py`、`dv/gl_soc/vcd_window.v` |
| 2026-10-13 | Phase 7 IR，maxpower 以 40 ns 與 44 ns 各 dump 一次（`9100d07`） | nom_tt 功耗 5.99 → 5.87 mW，只差約 2%；原本預期 VCD 是每秒切換次數、會差約 10% | 推測（沒讀 OpenSTA 原始碼）：OpenSTA 讀 VCD 後依 SDC 的時脈週期換算 toggle rate。原本寫在規則 9 裡，2026-10-15 移到這裡（`review_skills.md` 1.3） | dump 波形仍用 run 的 `CLOCK_PERIOD`，IR 檢查前核對 VCD 的週期（規則 9） | ADR-0019 決定 20 |
| 2026-10-15 | Phase 0–7 問題總檢討（ADR-0021，`verify_and_merge.md` B10、C1、C2） | 規則 6、8 有每次 run 的秒數與 `mdworker` 個數；規則 9 有一句推測，「testbench 預設 40 ns」容易讀成 signoff 週期是 40 ns；escaped identifier 結尾空白的陷阱只在 EQY 的經驗紀錄 | 已驗證（`review_skills.md` 1.2 R21、1.3、3.1 Q22、3.2） | 數字改指向 `dv/gl_soc/README.md` 與經驗紀錄；推測移到經驗紀錄；規則 9 寫明 signoff 週期取 run 的 `CLOCK_PERIOD`；規則 4 補 escaped identifier | 本檔 |
