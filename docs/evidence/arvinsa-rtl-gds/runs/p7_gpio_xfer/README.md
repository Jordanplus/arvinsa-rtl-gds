# GPIO 33–37 與 GPIO 設定傳送的 scratch 模擬（2026-10-16）

這個目錄是 2026-10-16 查證「management 韌體做 GPIO 設定傳送後，GPIO 33–37 會不會變回 management mode」時的模擬與 netlist 讀取，查證過程與結論在 `docs/notes/caravel_gpio_xfer.md`，決定在 ADR-0022 決定 3，Phase 7 已知限制 22（`docs/phase_exit/phase7.md`）指向這裡。

這是一次性的實驗，不在 `make regress` 裡，也沒有接任何 make target，所以之後有人改了 `rtl/caravel/user_defines.v` 或 wrapper，不會有 checker 自動重跑。2026-10-15 清理 `runs/` 之後才做，不是 `make collect-evidence` 收的；檔案直接寫在這裡，log 裡的家目錄路徑寫成 `~`（和 `docs/evidence/README.md` 的慣例相同）。

## 模擬了什麼

- **DUT**：Caravel 的 `caravel_core`，RTL 來自 caravel-lite 2024.09.12-1（commit `5593d992`，取自 precheck 官方 Docker image 的 `/opt/caravel`，`docs/report/figures/SOURCES.md` 第 219–223 行）；用到的檔案和 ChipFoundry 現用的 Caravel（CC2509）逐檔相同（`cc2509_blobs.txt`）。GPIO 的開機模式用本專案的 `rtl/caravel/user_defines.v`（第 92–96 行：33、34 是 user mode 下拉輸入，35、37 是 user mode 輸出，36 是 user mode 輸入）。
- **假的 management core**（`stubs.v` 的 `mgmt_core_wrapper`）：只有 Wishbone master 的 `wb_write`／`wb_read` 兩個 task，直接寫 housekeeping 的暫存器，等同韌體寫 `reg_mprj_io_N`、`reg_mprj_xfer`。`qspi_enabled`、`spi_enabled`、`uart_enabled` 都接 0，所以 management SoC 的 QSPI、SPI master、UART 搶 pad 的情況沒有模擬到。
- **假的 user_project_wrapper**（`stubs.v`）：`io_out`／`io_oeb` 照 `rtl/caravel/user_project_wrapper.v` 第 149–163 行的接法（37 `uart_tx`、35 `trap` 是輸出，33、34 輸出 0 且 `oeb` 0，其他 `oeb` 1）。
- pad cell 本身沒有模擬：log 裡的 `dm`、`oeb(pad)`、`out(pad)`、`inp_dis` 是 GPIO 控制區塊送給 pad 的控制訊號，pad 實際怎麼動要由這些訊號推。
- POR 用 Caravel 的行為模型（`simple_por.v` 第 47–53 行：沒有電源腳位時只在時間 0 之後 500 ns 放開一次），所以「重新上電」沒有模擬；每個情境開頭的 `after POR` 就是上電後的狀態。

## 情境與結果

| 情境 | 做法 | 33–37 的結果 | log |
|---|---|---|---|
| 0 | 只寫 GPIO 5、6（management UART）就傳送 | 全部變回 management mode：`uart_tx`、`trap` 到不了腳位（`NO`），33、34 的 `dm` 從 `011`（下拉）變 `001`（不加上拉或下拉），輸入仍送得到 wrapper 的 `io_in` | `case0.log` |
| 1 | 先把 33–37 寫回 `0c00 0c00 1808 0402 1808`，再傳送 | 維持 user mode（`YES`） | `case1.log` |
| 2 | 不傳送 | 一直是 user mode（`YES`） | `case2.log` |
| 3 | 情境 0 之後，用 bit-bang 模式把 `serial_resetn` 拉低一次（寫 `0x2600_0000` = `0x2`、`0x6`、`0x0`） | 回到 user mode（`YES`）；housekeeping 存的那份（`hk_cfg`）仍是 `0403 0403 0403 1803 1803`，再傳一次又會變回去 | `case3.log` |
| 4 | 情境 0 之後拉低 resetb 5 µs 再放開 | 救不回來（`NO`）：resetb 為低時 `caravel_rstn` = 0，但 `porb_l` 與 `serial_resetn` 都維持 1 | `case4.log` |
| 5 | 情境 0 之後，把 33–37 寫回上面的值再傳送一次 | 回到 user mode（`YES`），`hk_cfg` 變成寫回的值 | `case5.log` |
| 對照 | 改用 caravel-lite 範本的 `user_defines.v`（5–37 全是 management mode），不傳送 | 上電後就是 `NO`，證明輸出那一項檢查在 pad 不是 user mode 時會報 `NO` | `control_template_defines.log` |

每個情境最後都再拉一次 resetb（log 的 `after resetb`），結果和拉之前相同。

「pad inputs 33/34/36 reach the wrapper io_in」在所有情境都是 `YES`，連對照也是：GPIO 控制區塊不論模式都把 pad 輸入送給 user area（Caravel `verilog/rtl/gpio_control_block.v` 第 251 行），所以這一項不能用來判斷模式，只說明輸入還收得到。

gate-level netlist（只讀，沒有模擬）：
- `gl_reset_values.log`：`verilog/gl/housekeeping.v` 裡 `gpio_configure[33..37]` 每個位元的 flip-flop 種類（`dfrtp` reset 成 0、`dfstp` reset 成 1）與 reset 腳位追到哪裡。結果 33–35 = `0x0403`、36–37 = `0x1803`，全部只接 housekeeping 的 `porb` 輸入，和 RTL（`verilog/rtl/housekeeping.v` 第 1061–1072 行）一致。
- `gl_reset_nets.log`：`verilog/gl/caravel_core.v` 裡 housekeeping 的 `porb` 經兩顆 buffer 接到 `por.porb_l`（`simple_por`）；`wb_rstn_i` 接到 `clock_ctrl.resetb_sync`；`clock_ctrl.resetb` 接到 `rstb_level.X`（`xres_buf`，也就是 resetb 腳位）。resetb 經 `xres_buf` 只接到 `caravel_clocking` 與 PLL（RTL `verilog/rtl/caravel_core.v` 第 528、544 行），不會到 `porb`。

## 檔案

| 檔案 | 內容 |
|---|---|
| `tb_gpio_xfer.v` | testbench，`+case=0..5` 選情境 |
| `stubs.v` | 假的 management core 與 wrapper |
| `run.sh` | 編譯、執行全部情境與對照、讀 gate-level netlist，並和這裡的 log 比對 |
| `gl_reset_values.py`、`gl_trace_net.py` | 讀 gate-level netlist 的腳本 |
| `versions.txt` | 工具版本、caravel-lite 與 PDK 版本、所用原始檔的 sha256 |
| `cc2509_blobs.txt` | 所用 Caravel 檔案的 git blob 和 ChipFoundry 現用 Caravel（CC2509，`chipfoundry/caravel` `a0b50ad1`）的比對，全部相同；要網路，`run.sh` 不重跑 |
| `compile.log`、`compile_template.log` | 編譯輸出（空的表示沒有警告） |
| `case0.log`–`case5.log`、`control_template_defines.log`、`gl_reset_values.log`、`gl_reset_nets.log` | 各情境的輸出 |

## 怎麼重現

需要：
- caravel-lite 2024.09.12-1 放在 `.tools/caravel-lite/`（git 不追蹤）。取得指令在 `docs/report/figures/scripts/caravel_chip.py` 開頭的說明（從 `chipfoundry/mpw_precheck` image 複製 `/opt/caravel` 的 `def/` 與 `verilog/`）；`run.sh` 先檢查 `def/chip_io.def` 的 git blob 是 `9af4f403…`，不是就停。也可以用環境變數 `CARAVEL` 指到別的目錄。
- sky130A PDK `8afc8346`（`env/versions.mk` 第 13 行的 `SKY130_PDK_HASH`，`make pdk-fetch`），路徑是 `${PDK_ROOT:-~/.ciel}/sky130A`；只用到 `sky130_fd_sc_hd`、`sky130_fd_sc_hvl` 的 Verilog 模型。
- Icarus Verilog 13.0（`iverilog`、`vvp`）、python3（這次是 3.14.6）。

在 repo 根目錄：

```sh
sh docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/run.sh            # 新 log 寫到暫存目錄，逐檔和這裡的比對
sh docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/run.sh <目錄>     # 指定輸出目錄；給這個目錄本身就是覆寫這裡的 log
```

比對全部相同時每個檔印 `same as the kept log`，有不同時印 `DIFFERS` 並 exit 1。整個流程約 4 秒。編譯指令（`run.sh` 的 `build`）：

```sh
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY=#1 -I $R -o core.vvp $R/defines.v <user_defines.v> \
  $P/sky130_fd_sc_hd/verilog/primitives.v $P/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v \
  $P/sky130_fd_sc_hvl/verilog/primitives.v $P/sky130_fd_sc_hvl/verilog/sky130_fd_sc_hvl.v \
  $R/caravel_core.v $R/caravel_clocking.v $R/clock_div.v $R/digital_pll.v $R/housekeeping.v \
  $R/housekeeping_spi.v $R/gpio_control_block.v $R/gpio_defaults_block.v $R/gpio_logic_high.v \
  $R/mgmt_protect.v $R/mgmt_protect_hv.v $R/mprj_logic_high.v $R/mprj2_logic_high.v $R/mprj_io_buffer.v \
  $R/manual_power_connections.v $R/empty_macro.v $R/spare_logic_block.v $R/simple_por.v $R/xres_buf.v \
  $R/user_id_programming.v stubs.v tb_gpio_xfer.v
vvp -n core.vvp +case=0      # 0..5
```

`$R` 是 `.tools/caravel-lite/verilog/rtl`，`$P` 是 `${PDK_ROOT:-~/.ciel}/sky130A/libs.ref`；`-I $R` 讓 `digital_pll.v` 找得到它 include 的 `digital_pll_controller.v`、`ring_osc2x13.v`。

## 和查核時的 scratch 版本的關係

獨立查核在 Claude session 的暫存區重建了 `tb3.v` 與編譯結果，但沒有留下編譯指令與 log。這裡的 `tb_gpio_xfer.v` 是從 `tb3.v` 改的：
- 多印 housekeeping 存的那份設定（`hk_cfg`）；
- 多一項輸入檢查；
- 多兩個情境（4、5）。

`stubs.v` 只改了開頭的註解。2026-10-16 核對過：用上面的指令重新編譯 `tb3.v`，四個情境的輸出和查核者的編譯結果每一行都相同，連最後一行 `$finish` 也相同。`tb_gpio_xfer.v` 的情境 0–3 拿掉新增的那幾行（開頭的 `case N`、`hk_cfg`、輸入檢查）後，只有最後一行 `$finish` 不同：檔名與行號不同，而且輸入檢查多花了時間，結束時間較晚；其他每一行都相同。
