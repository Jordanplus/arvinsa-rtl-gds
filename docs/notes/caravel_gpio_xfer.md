# Caravel 的 GPIO 設定傳送會讓 GPIO 33–37 變回 management mode（2026-10-16）

起因：技術報告 §3.4「GPIO」一節寫了一段推論（依原始碼，沒有模擬確認）：management 韌體只要做一次 GPIO 設定傳送，33–37 就會變回 management mode。2026-10-16 先查證並做 scratch 模擬，再由獨立 agent 查核；查核沒有推翻結論，補了一條恢復方法、gate-level netlist 的 reset 值，以及 `boot_mode` 浮接與 QSPI 可能搶 pad 兩項影響。使用者 2026-10-16 選「A：寫進文件與 skill (建議)」（ADR-0022 決定 3）。

模擬的 testbench、執行指令與 log 收在 `docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/`（以下簡稱「證據目錄」，怎麼重現見該目錄的 `README.md`）。

下面寫「Caravel `路徑`」的，都是 caravel-lite 2024.09.12-1（commit `5593d992`，`docs/report/figures/SOURCES.md` 第 219–223 行）裡的檔案，放在 `.tools/caravel-lite/`（git 不追蹤）。

## 結論

**影響**：本專案不下線（ADR-0019 決定 1，第 10 行；ADR-0021 決定 8，第 102 行），這顆晶片沒有實際風險。影響的是報告與 skill 寫得對不對，以及沿用這套流程的下一個 Caravel 設計。

假設真的下線，management 韌體做了一次傳送、事先沒把 33–37 寫回 user mode（模擬確認，證據目錄 `case0.log`）：

| GPIO | 訊號 | 傳送後 |
|---|---|---|
| 37 | `uart_tx`（輸出） | 到不了腳位：pad 改由 management 控制，輸出致能關閉 |
| 35 | `trap`（輸出） | 同上 |
| 36 | `uart_rx`（輸入） | 仍送得到 user area；如果 management 再打開 QSPI，pad 可能被 management 推，和板上接到這支的 UART TX 搶（只依原始碼，沒有模擬） |
| 33、34 | `boot_mode[0]`、`boot_mode[1]`（下拉輸入） | 仍送得到 user area，但內部下拉沒了；板子上沒接線時浮接，boot ROM 讀到的開機方式無法確定 |

`uart_tx` 與 `trap` 也鏡射在 `la_data_out`（`rtl/caravel/user_project_wrapper.v` 第 170 行），management 打開 LA 的輸入致能後仍讀得到（Caravel `verilog/rtl/mgmt_protect.v` 第 161–175 行）。

**怎麼恢復**：
- 拉 resetb 沒用（模擬 `case4.log`；RTL 與 gate-level netlist 都顯示 resetb 不會重置這份設定）。
- 可以用的方法：
  - 重新上電（依原始碼；模擬只有開機那一次 POR）；
  - 把 33–37 寫回正確的值，再傳一次（模擬 `case5.log`）；
  - 用 bit-bang 模式把 `serial_resetn` 拉低一次，38 支全部回到開機預設（依原始碼；模擬 `case3.log` 確認 33–37 回到 user mode）；
  - 外部經 housekeeping SPI 寫同一個暫存器（依原始碼，沒有模擬）。
- 韌體放在外部 SPI flash（上游範例的 testbench 也是把韌體載入 SPI flash 模型，Caravel `verilog/dv/caravel/mgmt_soc/uart/uart_tb.v` 第 133–135 行），重燒就能修，晶片不用重做。

**使用規則**：
- 本設計的 management 韌體不需要做 GPIO 設定傳送（推論，見「本設計的 management 韌體要不要傳送」）。
- 要傳送時，先把 `reg_mprj_io_33..37` 寫成下表的值，再寫 `reg_mprj_xfer`（模擬 `case1.log`）。
- 通用的說法：`user_defines.v` 裡設成 user mode 的每一支腳，傳送前都要用同樣的值寫回。

| 暫存器（Caravel `verilog/dv/caravel/defs.h` 第 112–116 行） | 位址 | 值 | 模式（本專案 `rtl/caravel/user_defines.v` 第 41–44、92–96 行） |
|---|---|---|---|
| `reg_mprj_io_33` | `0x2600_00a8` | `0x0c00` | `GPIO_MODE_USER_STD_INPUT_PULLDOWN` |
| `reg_mprj_io_34` | `0x2600_00ac` | `0x0c00` | `GPIO_MODE_USER_STD_INPUT_PULLDOWN` |
| `reg_mprj_io_35` | `0x2600_00b0` | `0x1808` | `GPIO_MODE_USER_STD_OUTPUT` |
| `reg_mprj_io_36` | `0x2600_00b4` | `0x0402` | `GPIO_MODE_USER_STD_INPUT_NOPULL` |
| `reg_mprj_io_37` | `0x2600_00b8` | `0x1808` | `GPIO_MODE_USER_STD_OUTPUT` |

**沒有自動檢查**：repo 的 Caravel 模擬直接驅動 wrapper 的腳位，沒有 management SoC（`dv/tb/tb_soc.v` 第 36–41 行）。證據目錄的模擬是一次性的實驗，不在 `make regress` 裡。precheck 的 `gpio_defines` 只查 5–37 有沒有填值，`oeb` 只查 `io_out`／`io_oeb` 的接線（`docs/notes/caravel_precheck_phase7.md` 第 28 行；技術報告 §3.4；ADR-0019 決定 10）。正式的 regression test 與全晶片模擬留給下一個要下線的專案（ADR-0022 決定 3）。

## 原因：同一份設定存了兩份，開機預設值不同

### 開機時 pad 用的那份

- 每支 GPIO 的控制區塊在 `resetn` 為低時，載入 `gpio_defaults`（Caravel `verilog/rtl/gpio_control_block.v` 第 174–187 行）。
- `gpio_defaults` 由 `gpio_defaults_block` 依參數 `GPIO_CONFIG_INIT` 產生（`gpio_defaults_block.v` 第 24–30、56–59 行）。33–37 的參數是 `USER_CONFIG_GPIO_33..37_INIT`（`caravel_core.v` 第 1036–1078 行），也就是專案 `user_defines.v` 的值。
- `resetn` 是 housekeeping 輸出的 `serial_resetn`，沿兩條鏈傳給每個控制區塊（`caravel_core.v` 第 506–507、619 行）。
- `serial_resetn` 平常等於 `serial_resetn_pre`（`housekeeping.v` 第 908–911 行）。`serial_resetn_pre` 只在 `porb` 為低時是 0，`porb` 放開後的第一個 `wb_clk_i` 就變成 1（第 920–939 行）。
- 所以上電後，33–37 就是本專案設的 user mode。模擬每個情境開頭的 `after POR` 都是這個狀態。

### housekeeping 存的那份

- housekeeping 為每支 GPIO 存一份 13 位元設定 `gpio_configure`。reset 值寫死在 RTL：
  - GPIO 0、1、36、37 是 `0x1803`；
  - GPIO 3 是 `0x0801`；
  - 其他都是 `0x0403`。
- 出處：`housekeeping.v` 第 1061–1072 行。註解寫「These are not startup values, but they should match the startup values applied to the GPIO, or else the GPIO should be always triggered to load at startup」，「To-do」寫要改成從外部讀專案的預設值，這一版沒有做（第 1052–1059 行）。
- 這份設定只由 `porb` 重置（第 1031 行 `always @(posedge csclk or negedge porb)`）。

### 傳送做了什麼

- 韌體寫 `reg_mprj_xfer`（`0x2600_0000`，`defs.h` 第 66 行）。這個位址對到 housekeeping 的暫存器 `0x13`（`housekeeping.v` 第 528 行），bit 0 是 `serial_xfer`（第 1132–1139 行）。
- 狀態機同時送兩條鏈，每次各取一支 GPIO 的 `gpio_configure` 移位送出（鏈 1 從 GPIO 18 往 0，鏈 2 從 GPIO 19 往 37），直到 38 支都送完（第 942–943、953–961、969 行）。最後送一個 `serial_load` 脈衝（第 984–996 行）。
- 每個控制區塊收到 `serial_load`，就把移位暫存器的值載入成現在的設定（`gpio_control_block.v` 第 188–201 行）。
- 所以一次傳送會把 38 支全部換成 housekeeping 存的那份，不只韌體剛寫的那幾支。

### 本設計裡哪幾支兩份不同

| GPIO | 開機預設值 | housekeeping 的 reset 值 | 相同？ |
|---|---|---|---|
| 0–4 | `0x1803`、`0x1803`、`0x0403`、`0x0801`、`0x0403`（Caravel 寫死，`caravel_core.v` 第 704、714、724、735、745 行） | 同左 | 相同 |
| 5–32 | `0x0403`（本專案 `user_defines.v` 第 61–91 行，和範本相同） | `0x0403` | 相同 |
| 33–35 | user mode（`0x0c00`、`0x0c00`、`0x1808`） | `0x0403`（management 輸入） | **不同** |
| 36–37 | user mode（`0x0402`、`0x1808`） | `0x1803`（management mode，輸出致能關閉） | **不同** |

只有 33–37 兩份不同，所以傳送只影響這 5 支（GPIO 5、6 是韌體刻意改的）。

## gate-level netlist 的 reset 值

讀 Caravel `verilog/gl/housekeeping.v`（腳本 `gl_reset_values.py`，輸出 `gl_reset_values.log`）。每個 `gpio_configure[33..37]` 位元的 flip-flop：
- `dfrtp`（`RESET_B`）reset 成 0，`dfstp`（`SET_B`）reset 成 1；
- 組起來是 33–35 = `0x0403`、36–37 = `0x1803`，和 RTL 相同；
- 每個 `RESET_B`／`SET_B` 經 buffer 追回去，都只接 housekeeping 的 `porb` 輸入。

讀 Caravel `verilog/gl/caravel_core.v`（腳本 `gl_trace_net.py`，輸出 `gl_reset_nets.log`）：
- housekeeping 的 `porb` 經兩顆 buffer 接到 `por.porb_l`（`simple_por`）；
- housekeeping 的 `wb_rstn_i` 接到 `clock_ctrl.resetb_sync`；
- `clock_ctrl.resetb` 接到 `rstb_level.X`（`xres_buf`，也就是 resetb 腳位）。

所以「resetb 救不回來」在 gate-level netlist 上也成立，不只是 RTL 的結論。gate-level netlist 只讀了接線，沒有做模擬。

## 為什麼 resetb 沒用

- resetb 腳位經 `xres_buf` 變成 `rstb_l`（`caravel_core.v` 第 1390–1398 行），只接 `caravel_clocking` 與 PLL（`digital_pll`）的 `resetb`（第 528、544 行）。`caravel_clocking` 同步後的 `caravel_rstn` 給 management core 與 housekeeping 的 `wb_rstn_i`（第 534、282、575 行）。
- `wb_rstn_i` 在 housekeeping 裡只重置 Wishbone back-door 的狀態機（`housekeeping.v` 第 638–646 行）。
- `gpio_configure` 與 `serial_resetn_pre` 都只由 `porb` 重置（第 1031、920 行）。`porb` 來自 `simple_por`（`caravel_core.v` 第 586、1384–1385 行），和 resetb 無關。
- 模擬 `case4.log`：resetb 為低時 `caravel_rstn` = 0，`porb_l` 與 `serial_resetn` 都維持 1；放開後 33–37 仍是 management mode。

## 恢復方法

1. **重新上電**：`porb` 先低後高，`serial_resetn` 跟著先低後高，控制區塊重新載入開機預設值，housekeeping 的那份回到 reset 值（上面兩節的原始碼）。模擬的 POR 是行為模型，只在開機時放開一次（`simple_por.v` 第 39–52 行），所以重新上電沒有模擬；每個情境開頭的 `after POR` 就是上電後的狀態。
2. **寫回正確的值再傳一次**：`case5.log`，壞掉的傳送之後寫回上表的值再傳送，33–37 回到 user mode。
3. **bit-bang 把 `serial_resetn` 拉低一次**：
   - 做法：寫 `0x2600_0000` = `0x2`（`serial_bb_enable` = 1、`serial_bb_resetn` = 0，這時 `serial_resetn` = 0），再寫 `0x6`（`serial_bb_resetn` = 1），最後寫 `0x0` 離開 bit-bang 模式（`housekeeping.v` 第 908–911、1132–1139 行）。
   - 效果：每個控制區塊重新載入開機預設值，38 支全部回到上電時的狀態（`gpio_control_block.v` 第 174–187 行）。模擬 `case3.log`：33–37 回到 user mode。
   - 注意：housekeeping 存的那份沒變（`hk_cfg` 仍是 `0403 0403 0403 1803 1803`），之後再傳送一次又會變回 management mode，除非先寫回 33–37。
4. **外部經 housekeeping SPI**（依原始碼，沒有模擬）：housekeeping SPI 寫的也是同一組暫存器，暫存器 `0x13` 的位元相同（`housekeeping.v` 第 1020–1023、1132–1139 行），所以外部也能觸發傳送或 bit-bang。傳送後 GPIO 1–4 的設定和開機預設值相同（上表），SPI 仍可用；SPI 只在 `gpio_configure[3]` 的 `INP_DIS` 是 0、而且沒有被 `hkspi_disable` 關掉時有效（第 632 行）。

## 每支腳的影響

傳送後 33–37 的狀態（`case0.log`）：

| GPIO | `dm` | `oeb(pad)` | user 輸出到得了腳位？ | pad 輸入送得到 `io_in`？ |
|---|---|---|---|---|
| 33、34 | `011` → `001` | 0 → 1 | （輸入腳） | 是 |
| 35 | `110` → `001` | 0 → 1 | 否 | 是 |
| 36 | `001` → `110` | 1 → 1 | （輸入腳） | 是 |
| 37 | `110` → `110` | 0 → 1 | 否 | 是 |

- **輸出腳（35、37）**：控制區塊在 management mode 時，輸出致能取 `mgmt_gpio_oeb` 與 `OEB` 位元（`gpio_control_block.v` 第 228–229 行）。`0x0403`、`0x1803` 的 `OEB` 都是 1，`mgmt_gpio_oeb` 平常也是 1（`housekeeping.v` 第 783–788 行，取 `~INP_DIS`），所以 pad 不輸出，wrapper 的 `io_out` 不再接到 pad（`gpio_control_block.v` 第 235–237 行）。
- **輸入腳（33、34、36）**：控制區塊不論模式都把 pad 輸入送給 user area（`gpio_control_block.v` 第 251 行），傳送後 `INP_DIS` 也是 0，所以輸入仍收得到。這也表示證據目錄的輸入檢查在所有情境都是 `YES`，連範本 `user_defines.v` 的對照也是，它不能用來判斷模式。
- **33、34 的下拉沒了**：`dm` 從 `011`（`0x0c00`，`GPIO_MODE_USER_STD_INPUT_PULLDOWN`）變成 `001`（`0x0403`，不加上拉或下拉），編碼見 Caravel `verilog/rtl/user_defines.v` 第 23–36 行。
  - 板子上沒接線時，`boot_mode` 浮接。
  - boot ROM 在 CPU 開始執行時讀一次 `GPIO_IN[1:0]` 決定開機方式（`fw/bootrom/bootrom.S` 第 8、47–48 行）：0 跳到 SRAM、1 March test、2 從 UART 載入、3 保留（`rtl/include/memmap.vh` 第 59–63 行；3 照 0 處理，`fw/bootrom/bootrom.S` 第 9、56 行）。
  - 推論：傳送發生在 management 寫 `host_en` = 0 之前，或之後 CPU 又重新開機，開機方式就無法確定。
- **management 的 pad 功能可能搶 pad**（只依原始碼；證據目錄的假 management core 把 `qspi_enabled`、`spi_enabled` 接 0，沒有模擬）：
  - GPIO 35–37 的控制區塊，`mgmt_gpio_oeb` 由 housekeeping 驅動，中間只經過 `mprj_io_buffer`（`caravel_core.v` 第 625、676–696、1261、1283 行）。management 打開 QSPI 時，36、37 的輸出致能改由 flash 控制器決定（`housekeeping.v` 第 783–786 行）；打開 SPI master 時，35 改由 `spi_sdoenb` 決定（第 787–788 行）。
  - 所以 36 可能被推，和接在 `uart_rx` 上的外部 UART TX 搶；35 會輸出 SPI 的 SDO。
  - 33、34 的控制區塊，`mgmt_gpio_oeb` 接固定值 1（`caravel_core.v` 第 1314、1336 行），輸出致能只看 `OEB` 位元，`0x0403` 是 1，所以打開 SPI master 也不會推 33（`spi_csb` 只接到 `mgmt_gpio_out[33]`，`housekeeping.v` 第 797 行）。

## 本設計的 management 韌體要不要傳送（推論）

本設計需要 management 韌體做的事（ADR-0019 決定 9；技術報告 §3.4「management SoC 與 wrapper 的介面」）：
- 經 Wishbone 把程式寫進 SRAM（`0x3000_1000`–`0x3000_17FF`）；
- 把 `host_en` 寫 0 放開 CPU（`0x3000_0000`）；
- 要讀回 wrapper 的資料時，打開 Wishbone 與 LA 的輸入致能。

這幾件事都不改 pad 設定。33–37 開機就是 user mode，所以不需要傳送。

會需要傳送的情況：management 想用自己的 UART（GPIO 5、6，開機是 management 輸入，6 要改成輸出才能送資料）或其他 management mode 的輸出。上游的範例 `verilog/dv/caravel/mgmt_soc/uart/uart.c` 第 34–63 行，就是設好 GPIO 6 與 16–31 後傳送，沒有寫 33–37；照抄到本設計會踩到這個問題（推論）。

查不到的一點：實際的 management SoC（LiteX 版）開機程式會不會自己做一次傳送。它的 RTL 與韌體不在 caravel-lite 裡，本機無法確認，要用實際的 management SoC 韌體確認。

## 模擬結果

證據目錄的 testbench：
- DUT 是 Caravel 的 `caravel_core`，加上本專案的 `user_defines.v`、假的 management core（只會寫 housekeeping 的 Wishbone master）、照本專案 wrapper 接法的假 wrapper；
- 只模擬到控制區塊送給 pad 的控制訊號，pad cell 沒有模擬。

| 情境 | 做法 | 結果 |
|---|---|---|
| 0 | 只寫 GPIO 5、6 就傳送 | 33–37 變 management mode；`uart_tx`、`trap` 到不了腳位；輸入仍收得到；33、34 下拉沒了 |
| 1 | 先寫回 33–37 再傳送 | 維持 user mode |
| 2 | 不傳送 | 一直是 user mode |
| 3 | 情境 0 之後 bit-bang 拉低 `serial_resetn` | 回到 user mode |
| 4 | 情境 0 之後拉低 resetb 5 µs | 仍是 management mode |
| 5 | 情境 0 之後寫回 33–37 再傳送 | 回到 user mode |
| 對照 | 改用範本 `user_defines.v`（5–37 全是 management mode），不傳送 | 上電後 `uart_tx`、`trap` 就到不了腳位，表示輸出檢查在 pad 不是 user mode 時會報 `NO` |

每個情境最後都再拉一次 resetb，結果和拉之前相同。

這次模擬的範圍與限制：
- 假的 management core 不跑韌體，QSPI、SPI master、management UART 都沒有打開；
- pad cell 沒有模擬，pad 的行為是從控制訊號推的；
- POR 是行為模型，重新上電沒有模擬；
- 只用 RTL 模擬，gate-level netlist 只讀接線；
- 和 ChipFoundry 現用的 Caravel 是同一份原始碼：
  - CC2509 = `chipfoundry/caravel` `a0b50ad1`（`pnr/user_project_wrapper/caravel_pwr/README.md` 第 7 行）；
  - 這次編譯用到的 24 個 RTL 檔、兩份 gate-level netlist、`defs.h`、`uart.c`、`def/chip_io.def`，git blob 都和 CC2509 相同（2026-10-16 用 GitHub API 比對，證據目錄 `cc2509_blobs.txt`）；
  - management SoC（LiteX 版）不在其中。

## 查證過程

1. **第一輪（技術報告 §3.4）**：讀原始碼推論「傳送會讓 33–37 變回 management mode」，報告標明「推論，依原始碼，沒有模擬確認」。
2. **2026-10-16 查證**：在 Claude session 的暫存區建 scratch 模擬（Caravel RTL＋本專案 `user_defines.v`＋假的 management core），跑三個情境（只設 5、6 就傳送、先寫回再傳送、不傳送），確認推論。
3. **獨立查核**（同日，另一個 agent）。結論不變，修正了這幾處：
   - 補了 bit-bang 恢復的方法；
   - 讀 gate-level netlist 確認 reset 值與 reset 來源；
   - 補了 `boot_mode` 浮接、QSPI 與 SPI master 可能搶 pad 兩項影響；
   - 指出暫存區沒有 log、也沒記編譯指令。暫存區的舊編譯結果還會卡住，印 `TIMEOUT`。
   - 查核者重建了 `tb3.v` 與可用的編譯結果。
4. **證據收進 repo**（同日）：
   - 依查核者編譯結果裡記錄的檔案清單，重建完整的編譯指令。用它重新編譯 `tb3.v`，四個情境的輸出和查核者的編譯結果逐行相同。
   - 加了 housekeeping 那份設定的列印、輸入檢查，以及情境 4（resetb）、情境 5（寫回再傳一次）、範本 `user_defines.v` 的對照；
   - gate-level netlist 的讀取寫成腳本；
   - 全部收進證據目錄，`run.sh` 一個指令重跑並和保存的 log 比對。
