# ADR-0011：Phase 5 把 CPU 換成 Hazard3

- 狀態：已採用（2026-10-05）。四個選項由使用者在 2026-10-05 一次決定（全部採建議）；其他項目是我宣告的預設，使用者沒有反對。
- 範圍：soc_top 的 CPU 從 PicoRV32 換成 Hazard3；SRAM、周邊、PnR 設定盡量不動。`project-plan.md` §8 Phase 5 的 exit criteria：「L0–L5 全 PASS；flow 設定只需改 design 層」，§10 第 4 項：「Hazard3 以同一套 flow 設定完成 signoff」。
- skill：`core-migration-hazard3`（Phase 5 開始時建立，CLAUDE.md 規則 7）。

## 查證結果（2026-10-05，Hazard3 clone，唯讀調查與本機實驗）

1. **版本**：stable 分支 = tag `v1.1.1`，commit `8af992930f71a69b0e06c38734c1094f41a05ca0`（2026-03-12）。作者建議 ASIC 用 stable（`Readme.md:45`）。develop 在 2026-08-29 仍有 commit。
2. **wrapper**：`hazard3_cpu_1port`（指令與資料共用一條 AHB5）與 `hazard3_cpu_2port`（指令、資料各一條），都只是 `hazard3_core` 的薄包裝。
3. **AHB5 對 1RW 同步 SRAM**：寫入資料在 data phase 才出現，比位址晚一個 cycle，core 內沒有 write buffer（`bus_behaviour.adoc:49`）；OpenRAM macro 要在同一個上升緣拿到位址與資料。
4. **SRAM port 1 的位置**：port 1 的 `dout1`、`clk1` 在 macro 上邊，`csb1` 與 5 條 `addr1` 在右邊（LEF），現在的 floorplan 這兩邊離 die 邊緣只有 15–19 µm。port 1 也還沒有 SPICE 特性化（ADR-0010 已知限制 8）。
5. **面積**（本機 Yosys 估算，與 ADR-0006 同一個配方；同配方跑 PicoRV32 得 114,023 µm²，與 ADR-0006 相同）：Hazard3 RV32IMC＋計數器約 96,878 µm²，比 PicoRV32 小約 15%；die 不需要放大（推測）。
6. **相容性**：純 Verilog-2005；Icarus、Verilator lint、Yosys 都直接吃得下，沒有 latch。
7. **驗證資產**：上游 `sw_testcases` 與 riscv-tests 要 newlib 工具鏈，本機 Homebrew 工具鏈沒有；`rvcpp`（ISS）可以 build；上游沒有 RTL 對 rvcpp 的逐指令比對工具，要用 RVFI 自己做。
8. **會被換 core 影響的地方**：沒有 `trap` 腳、中斷模型不同、非同步 reset、CPI 變小（`dv/tests.toml` 的 `min_cycles`）、PCPI 不存在（植入錯誤 R08 不能移植）、DV 的 bus checker 都以 native bus 為前提。逐項清單在 skill `core-migration-hazard3` 與 Phase 5 的工作紀錄。
9. **授權**：進 RTL 的 `hdl/` 全部 Apache-2.0。

## 使用者決定（2026-10-05）

1. **`hazard3_cpu_1port`＋AHB 轉 native bus 的轉接器**。SoC 匯流排（`soc_bus`）、SRAM 介面（含 `rdata_q` 的半週期路徑）、周邊與多數 DV checker 不動，PnR 設定幾乎不變，最能證明「flow 只改 design 層」。代價是每筆存取多幾個 cycle，效能接近 PicoRV32；轉接器本身要有 AHB 協定 checker。
2. **RV32IMC＋`CSR_COUNTER`**：和現在 PicoRV32 SoC 的功能相同，firmware 的 `-march=rv32imc` 不改。不開 A、debug、timer。
3. **core 層級驗證**：裝 xPack 的 newlib 工具鏈，跑上游 riscv-tests（rv32ui／um／uc／mi）；再寫 RVFI 轉 rvcpp trace 的工具，逐指令比對。
4. **Hazard3 SoC 成為 `make regress` 的主設計**；PicoRV32 版保留，移到 `make regress-picorv32`，Phase 5 結案時兩個都跑。

## 預設（我宣告，使用者沒有反對）

- **trap 腳保留**：由 TEST_CTRL 新增的「致命錯誤」暫存器驅動，firmware 的 exception handler 寫入後拉高。pin、PnR、GL lockstep 都不動。
- Hazard3 釘 stable `v1.1.1`；週期先沿用 43 ns；中斷只接 1 條（`NUM_IRQS=1`，不開 Xh3irq）。
- reset 前加同步器（skill 規則 9）。
- 未映射位址維持「讀回 0、寫入忽略、不報錯」（轉接器後面的 `soc_bus` 不改）。
- 不單獨 harden Hazard3 core；PicoRV32 的 core 級 harden 跟著 PicoRV32 版移到 `make regress-picorv32`。

## 計畫

0. 先修 Phase 3.5 獨立審查找到的 12 個 checker 漏洞與 `run.sh`（使用者決定，`docs/phase_exit/phase3_5.md`）。
1. skill `core-migration-hazard3`、本 ADR。
2. `third_party/hazard3` submodule 釘 `v1.1.1`；轉出專案格式的檔案清單；lint waiver。
3. RTL：把 CPU 包成一個介面相同的模組（native bus、`trap`、`irq`），PicoRV32 版與 Hazard3 版各一份；Hazard3 版含 AHB 轉接器、reset 同步器、tie-off、`trap` 的產生方式。轉接器的 AHB 協定 checker 與植入錯誤。
4. firmware：Hazard3 版的 `start.S`（`mtvec`、`mcountinhibit`、清暫存器堆）、中斷 handler 用 `mret`；受 CPI、中斷模型、trap 影響的測試重新定義期望值。
5. DV：`tests.toml` 的 cycle 上下限重量；植入錯誤 R01–R08 逐一檢查能否移植（R08 不能）。
6. core 層級：riscv-tests 與 RVFI 對 rvcpp 的逐指令比對。
7. PnR：Hazard3 SoC 的 config（只改 design 層），新的 golden；neg-pnr、EQY、gate-level 模擬（含帶電源網表）。
8. regress 拆成 `make regress`（Hazard3）與 `make regress-picorv32`；乾淨 checkout 兩個都 PASS 後結案。

## 風險

- 時序：Hazard3 的關鍵路徑在 sky130 的表現沒有數據；43 ns 是 SRAM 半週期路徑決定的，CPU 邏輯若更慢要重新收斂。
- 轉接器與 AHB 協定：自己寫的轉接器要用協定 checker 與植入錯誤證明。
- 中斷與 reset 的語意改變：`irq` 測試的進入次數、`reset_store` 測試的 reset 取樣邊緣都要重新定義。
- 暫存器堆沒有 reset：gate-level 與 4-state 模擬會看到 X，firmware 要先清。

## 出處

- Hazard3：github.com/Wren6991/Hazard3，tag `v1.1.1`（`hdl/`、`doc/sections/*.adoc`、`test/sim/rvcpp/`）。
- skill `core-migration-hazard3`（逐條附檔名與行號）。
