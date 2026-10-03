# Phase 1 exit review：SoC RTL、firmware、RTL 模擬 regression

日期：2026-10-03　結論：**PASS**（spec §9 五項 exit criteria 全部達成）

Exit criteria 出處：`project-plan.md` §8 Phase 1（L0、L1a、L1b PASS；bug injection 全部在預期 checker FAIL）與 `docs/spec/soc_spec.md` §9。
以下數字來自主控獨立重跑（`make clean` 後 `make phase1`，2026-10-03），不是取自 agent 的回報。

| # | Exit criterion | 結果 | 證據 |
|---|---|---|---|
| 1 | `make lint`、`make synth-check`、`make fw` PASS | PASS | `LINT: PASS (23 variants, 0 warnings, 0 errors)`；`SYNTH-CHECK: PASS`（無 latch、`sram0` 恰 1 顆、`check -assert`、0 個 Yosys warning）；`check-bootrom: PASS` |
| 2 | `make core-stock` PASS | PASS | 上游 PicoRV32 `test`、`test_ez`、`test_wb`、`test_synth` PASS；`test_rvf` N/A（需要 riscv-formal，不在 repo 與工具清單內，見 `docs/notes/core_stock.md` §6） |
| 3 | `make regress-rtl`：所有正向測試在 Icarus 與 Verilator 都 PASS | PASS | `regress: PASS 26/26`（13 支測試 × 2 個模擬器，兩邊 cycle 數、UART 文字、SIG、GPIO 序列一致） |
| 4 | `make neg-rtl`：`dv/bugs.toml` 全部條目在預期 checker FAIL | PASS | `neg: PASS 33/33 caught` |
| 5 | `make smoke` < 5 分鐘 | PASS | 26 秒（`make phase1` 全部 244 秒） |

## Testbench qualification（植入錯誤後，checker 會不會 FAIL）

Phase 1 做了兩輪獨立的 qualification review，每輪由沒有參與撰寫的 agent 在 repo 副本中植入 `bugs.toml` 以外的錯誤：

| 輪次 | 植入 | 原本抓不到 | 處理後 |
|---|---|---|---|
| 第 1 輪 | 20 個 | 10 個（例如 firmware 測試主體被跳過、Boot ROM loader 不驗 checksum、unmapped 位址的回應規則沒有測試） | 新增 `min_cycles`、unmapped 定向測試、`regs` 測試、loader 錯誤封包的 negative test 等；neg-rtl 8 → 20 項 |
| 第 2 輪 | 23 個（F01–F24，F16 作廢改 F16b） | 10 個 regress 抓不到（UART stall 路徑沒走到、memtest 刪掉 march C−、Boot ROM march 少一個 word、TEST_CTRL 寫入互相干擾、IRQ 線時序、UART 除數 reset 值、Boot ROM 沒寫除數、SRAM 一筆交易存取兩次、先寫 DONE 再寫 SIG） | 新增 4 個 checker：`sram_port`、`irq_line`、`uart_div`、`coverage`（SRAM 每個 word 的存取次數、UART stall 數）；新測試 `uart_burst`、`reset_store`；`regs` 加交叉讀回；neg-rtl 20 → 33 項 |

第 2 輪的 24 個錯誤在修正後重跑：**22 個由 `make regress-rtl` 抓到，兩個模擬器都 FAIL**；其餘 F23（loader 不驗 checksum）、F24（loader 不檢查 N 上限）要送格式錯誤的封包才看得到，由 neg-rtl 的 L01、L03 抓到。主控另外獨立重跑原本抓不到的 10 個，結果相同（每個都在兩個模擬器 FAIL，見下表）。

| 錯誤 | 抓到的 checker | FAIL 的 run 數 |
|---|---|---|
| F02 UART 除數 reset 值 +1 | `uart_div` | 26／26 |
| F08 Boot ROM march 少測最後一個 word | `coverage` | 2（bootrom_march × 2 模擬器） |
| F11 一筆交易存取 SRAM 兩次 | `sram_port` | 26／26 |
| F14 UART DATA 寫入的 stall 被忽略 | `coverage`、`uart_golden`、`signature` | 4 |
| F15 寫 IRQ_TRIG 時連 SIG 一起寫 | `test_ctrl`、`uart_golden`、`signature`、`gpio_seq` | 2 |
| F16b memtest 刪掉 march C− | `coverage` | 2 |
| F17 先寫 DONE 再寫 SIG | `signature` | 22 |
| F19 IRQ 線清掉後晚 40 cycle 才放 | `irq_line` | 4 |
| F20 IRQ 是一拍脈衝不是位準 | `irq_line`、`test_ctrl` | 4 |
| F21 Boot ROM 沒寫 UART 除數 | `uart_div` | 26／26 |

## 與計畫不同的地方

- 測試設定檔用 TOML（`dv/tests.toml`、`dv/bugs.toml`），不是計畫寫的 YAML：Python 3.14 內建 `tomllib`，不需要另裝 PyYAML（ADR 0005）。
- 計畫 §7.3 的 R02 原本跑 memtest；spec 把 R02 改跑 `bootrom_march`，第 1 輪 review 發現 memtest 的上半部 coverage 因此沒人保護，已補 `R02_memtest`。
- `test_rvf`（上游 rvfi monitor）N/A；ISA 語意改由上游 `test`／`test_ez`／`test_wb`／`test_synth` 與自寫的 `muldiv` 等測試涵蓋。

## 已知限制（帶到後續階段）

1. **F23／F24 只有 negative test 抓得到**：loader 拒收錯誤封包的正確結果是 DONE = fail code，依 spec §7.4 不能當正向測試。要讓 regression 也抓到，需要 spec 允許「預期 DONE = 指定 fail code」的測試類型。
2. **R13（host port 忽略 byte mask）以 `sim_error` 判定**：沒有專門的 host port checker，由 testbench 中止。`sram_port` 現在也檢查 host 路徑的腳位，之後可改以它為預期。
3. **`sram_cov` 用精確次數**：memtest 每個 word 88 讀 22 寫、bootrom_march 6 讀 6 寫，跟程式綁在一起；改動測試的任何階段都要同步更新 `dv/tests.toml`。`min_cycles` 也一樣（約為實測值的 90%）。
4. **stall 判定與 SRAM 時序**：「交易超過 2 cycle 算被 stall」與 `sram_port` 的 T1／T2 handshake 規則都取自目前的匯流排時序（spec §4.2、§4.3）；改匯流排時序要重新校準。
5. **negative test 都在 Icarus 上跑**；Verilator 的偵測力由植入錯誤重跑表佐證。Verilator 是 2-state，沒有 `x_check`。
6. **Python 3.11** 只確認語法相容，沒有實際執行（本機是 3.14）。
7. spec §6.5 step 1「DIV 要在第一次 UART DATA 存取、第一次離開 Boot ROM、第一次寫 DONE 之前寫好」是 Phase 1 對原文「第一步寫 DIV」的具體化，已寫入 spec。

## 交付物

`rtl/`（soc_top、bus、UART／GPIO／TEST_CTRL、boot ROM、lint 與 synth-check script）、`fw/`（11 支測試程式，其中 2 支只給 negative test 用；Boot ROM；negative test 用的錯誤變體）、`dv/`（testbench、15 個 checker、`run_sim`／`regress`／`neg`）、`scripts/core_stock.sh`、`docs/spec/soc_spec.md`（Phase 1 契約）。
