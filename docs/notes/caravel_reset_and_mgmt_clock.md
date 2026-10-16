# Caravel 的 `wb_rst_i` 與管理端時脈上限：查證紀錄（2026-10-16）

2026-10-16 審技術報告時，發現 ADR-0019 有三處說法和原始碼或出處不符：
- 決定 8（第 31 行）寫「`wb_rst_i` 由管理用 SoC 在 `wb_clk_i` 下產生」；
- 第 60 行（決定 14）把 `wb_rst_i` 的半週期 input delay 說成「從 Caravel 的 STA 抽出」；
- Caravel 核心時脈上限寫成「TBD，約 50 MHz」，沒附出處（決定 15，第 66 行）。

`rtl/caravel/wb_host_bridge.v` 第 25 行的註解（「synchronous to clk」）與 `pnr/user_project_wrapper/caravel_io.sdc` 的註解也沿用同樣的說法。

查證分兩輪：第一輪讀原始碼與出處，第二輪由另一個 agent 獨立查核。本筆記以查核後的版本為準，寫進來的出處都在 2026-10-16 重新打開核對過。使用者的決定與原話在 ADR-0022 決定 1、2。

用到的版本：
- Caravel：efabless/caravel `27cbe49c`。本筆記引用的 `verilog/rtl/caravel_clocking.v`、`caravel_core.v`、`mgmt_protect.v`、`housekeeping.v`、`mprj_logic_high.v` 與 `verilog/gl/caravel_clocking.v`，和 repo 的 `.tools/caravel-lite`（git 忽略）同名檔用 `cmp` 比對過，內容相同。
- 官方 wrapper SDC：caravel_user_project `b510613` 的 `openlane/user_project_wrapper/signoff.sdc`。
- 管理用 SoC：efabless/caravel_mgmt_soc_litex `main`（`503eda07`）。

## 結論

- **reset**：三處文件寫錯，設計與時序都不受影響，不用重新 harden。`wb_rst_i` 的放開和 `wb_clk_i` 同步，由 STA 檢查；拉起是非同步的，STA 不檢查，`soc_top` 規格裡「同步 reset」的部分保證在晶片上不完全成立（第 3 節）。
- **管理端時脈**：「約 50 MHz」是 Efabless 在 2021 年就撤掉的舊文字。可以引用的是 40 MHz（Caravel 自己 signoff 的時脈）與 33 MHz（datasheet 保證的操作條件）。本設計 signoff 在 44 ns（22.7 MHz），比這些數字都慢，所以 signoff 結論與「管理端時脈 ≤ 22.7 MHz」這條使用限制都不變（第 5 節）。

## 1. `wb_rst_i` 怎麼產生（原始碼逐行）

管理用 SoC 只接收這個 reset，不產生它。產生它的是 `caravel_core` 裡的 `caravel_clocking`：

1. **三個來源合成一個非同步 reset**：`resetb_async = porb & resetb & (!ext_reset)`（`caravel_clocking.v` 第 51 行）。
   - `porb`：POR（`caravel_core.v` 第 523 行）。行為模型的註解寫，實際電路約 15 ms 才放開（`simple_por.v` 第 43–45 行）。
   - `resetb`：`resetb` pad 經 `xres_buf` 轉成 1.8 V（`caravel_core.v` 第 528、1390–1399 行）。
   - `ext_reset`：housekeeping 的 `reset` 輸出（`caravel_core.v` 第 531、615 行），等於 `pass_thru_mgmt_reset ? 1'b1 : reset_reg`（`housekeeping.v` 第 254 行）。也就是 SPI pass-through 模式，或 housekeeping 的 reset 暫存器（位址 0x0b，第 1107–1108 行）。這個暫存器外部 SPI 與管理用 CPU 經 Wishbone 都寫得到（第 1020–1023 行的位址、資料、時脈選擇），只有 POR 會把它清成 0（第 1031、1043 行）。
2. **3 級的 reset synchronizer**：`resetb_async` 為 0 時，`reset_delay` 立刻被設成 `3'b111`；放開後，每個核心時脈的下降緣往右移一位（`caravel_clocking.v` 第 101–110 行）。`resetb_sync = ~reset_delay[0]`（第 112 行）。所以拉起是立刻的（非同步）；三個來源都放開後，要到核心時脈的第 3 個下降緣才放開。gate-level netlist 也是三顆 flop（`verilog/gl/caravel_clocking.v` 第 290–292、1957–1980 行），輸出經 `buf_12` 送出（第 3266–3271 行）。
3. **送到管理用 SoC 與 wrapper**：`resetb_sync` 接到 `caravel_rstn`（`caravel_core.v` 第 534 行），送給管理用 SoC（第 282 行）、housekeeping（第 575 行）與 `mgmt_protect`（第 386 行）。
4. **`mgmt_protect` 反相**：`user_reset = (~caravel_rstn) & mprj_logic1[0]`，`user_clock = caravel_clk & mprj_logic1[1]`（`mgmt_protect.v` 第 232–233 行）。`caravel_clk` 就是 `caravel_clocking` 的 `core_clk`（`caravel_core.v` 第 532 行）。
5. **接進 wrapper**：`.wb_clk_i(mprj_clock)`、`.wb_rst_i(mprj_reset)`（`caravel_core.v` 第 443–444 行），`mprj_reset` 來自 `mgmt_protect` 的 `user_reset`（第 410 行）。

所以 `wb_clk_i` 就是管理用 CPU 的核心時脈；`wb_rst_i` 是 synchronizer 最後一級 flop 的輸出，中間只有反相器、buffer 與「AND 常數 1」。glitch 的風險很低（推測，沒有看 Caravel 的 layout 與時序報表）。

本設計怎麼用它：
- `wb_host_bridge` 的 `rst`（`rtl/caravel/user_project_wrapper.v` 第 105 行），在 `always @(posedge clk)` 裡當 synchronous reset（`wb_host_bridge.v` 第 57–58 行）。
- `soc_top` 的 `resetn = ~wb_rst_i`（`user_project_wrapper.v` 第 129 行）。`soc_top` 的規格是同步、低電位有效的 reset，`resetn=0` 至少 10 個 cycle（`docs/spec/soc_spec.md` §4.9 第 166 行）。
- Hazard3 的 reset 腳是非同步的，但它接的是 flop `rst_n_q`（`rtl/cpu/soc_cpu_hazard3.v` 第 41–43 行），不是直接接 `wb_rst_i`。所以 `wb_rst_i` 沒有直接接到任何非同步 reset 腳，不需要另外檢查 recovery／removal；`rst_n_q` 到 Hazard3 reset 腳的 recovery／removal 在同一個時脈域內，由 STA 檢查（同檔第 12–16 行的註解）。

## 2. 放開：STA 怎麼看 `wb_rst_i`

- `caravel_io.sdc` 給 `wb_rst_i` 的 input delay 是半週期（第 27 行），參考 `wb_clk_i` 的上升緣。這個值在官方 SDC 前半手寫的「Pre-defined Constraints」段（官方 `signoff.sdc` 第 11、52–53 行），不是後半從 Caravel STA 抽出的「Retrieved Constraints」段（第 64 行起）。ADR-0019 第 60 行與 `caravel_io.sdc` 開頭原本的說法不精確，已加更正。
- STA 會把 input delay 加在 clock 的 source latency（4.65–5.57 ns，`caravel_io.sdc` 第 16–17 行）上面。ADR-0019 決定 17 的 hold 分析（第 74 行）就是這樣算的：資料在 Caravel 時脈的 min latency 4.65 ns 之後再加 0.79 ns 才送出。所以這個模型的意思是「reset 在時脈到達 wrapper 腳位之後半個週期才到」，等於假設 Caravel 內部的 reset 路徑與時脈路徑一樣長。第一輪查證說「官方的半週期沒算 Caravel 內部延遲」，是錯的。
- 真正沒算進去的有兩項：
  - reset 路徑與時脈路徑在 Caravel 內部的延遲差（wrapper 的 STA 看不到，沒有數字）；
  - duty cycle 偏差：`clock_uncertainty.sdc` 只在下降緣到上升緣、上升緣到下降緣這兩種邊緣組合加上 DCD（`pnr/soc_top/clock_uncertainty.sdc` 第 20–21、27–28 行）。`wb_rst_i` 的 input delay 參考上升緣，STA 當成上升緣到上升緣的路徑，只扣一般的 setup uncertainty。實際上 reset 在下降緣放開，高電位佔 55% 時，下降緣比模型的半週期晚 (55% − 50%) × 44 = 2.2 ns。
- 粗估的 setup slack（推測）：capture 在 44 ns 加上 capture 端 latency（min 4.65 ns，加上 wrapper 內部 clock tree 約 2 ns，ADR-0019 第 74 行），arrival 是 max latency 5.57 ns 加 22 ns 加 wrapper 內部的 reset 繞線與 buffer 延遲。內部延遲沒有讀出來（`runs/` 已刪），若是 2–4 ns，slack 約 19–21 ns；扣掉上面沒算的 2.2 ns 與幾 ns 的路徑差，仍有十幾 ns。第一輪把內部 clock tree 當成扣掉，第二輪更正為加上。
- 有實際數字的下限：wrapper signoff 的 setup 與 hold 違規數都是 0，最差 setup slack +0.548 ns，而這個最差值等於暫存器到暫存器路徑的最差值（`signoff/golden/user_project_wrapper/metrics.json` 的 `timing__setup__ws`、`timing__setup_r2r__ws`、`timing__setup_vio__count`、`timing__hold_vio__count`）。所以 `wb_rst_i` 這條路徑的 slack 至少 +0.548 ns；實際值沒有讀出來。之後再 harden 時，可以順便用 `report_checks -from wb_rst_i` 讀各 corner 的值（推論：不必為這件事專門 harden 一次）。
- `wb_rst_i` 與 SoC 用同一個時脈，沒有跨時脈域的問題。

## 3. 拉起：非同步，STA 不檢查

拉起和 `wb_clk_i` 沒有固定關係（第 1 節第 2 點），STA 不檢查這一段。影響如下：

- **synchronous reset 的 flop**：拉起剛好落在某個上升緣附近時，那一拍可能有 flop 進入 metastable。之後至少還有一個 reset 有效的上升緣（下面「reset 最短多長」），會把它們全部歸位（推論）。
- **SRAM 的 `csb0`**（第一輪漏掉）：`resetn` 經組合邏輯接到 SRAM 的 `csb0`。CPU 路徑是 `cpu_csb0 = ~(resetn & idle & sel_sram)`，`sram_csb0 = host_en ? ~host_cs : cpu_csb0`（`rtl/bus/soc_bus.v` 第 229、241 行）。reset 剛好在 CPU 寫 SRAM 的那一拍拉起時，`csb0` 會在 SRAM 時脈邊緣附近改變，違反 SRAM 的 setup／hold，這筆寫入可能寫壞。規格 §4.9 的 RTL-RST-01（`resetn=0` 被取樣的那個上升緣上，CPU 送出的 SRAM 寫入要丟棄；`docs/spec/soc_spec.md` 第 168 行）在 RTL 模擬成立（`reset_store` 測試），在晶片上不保證。本設計 reset 之後 `host_en` 是 1，CPU 停住，由管理用韌體重新載入 SRAM，所以沒有長期影響（推論）。
- **reset 最短多長**：只看 synchronizer，`resetb_async` 的脈衝就算比一個時脈短，`wb_rst_i` 也會從拉起一直維持到放開後的第 3 個下降緣，中間至少有 2 個上升緣，比規格 §4.9 的 10 個 cycle 少（推論）。不過這要 reset 來源本身短於一個時脈才會發生：POR 約 15 ms（`simple_por.v` 第 43–45 行的註解），reset 暫存器寫 1 之後要再寫 0 才放開（`housekeeping.v` 第 1107–1108 行），`resetb` pad 由板子決定。本設計的 synchronous reset 有 1 個上升緣就夠，Hazard3 經 `rst_n_q` 也只多一拍（推論，依 RTL）。
- **PLL 啟用後的時脈切換**：`pll_bypass`（接到 `ext_clk_sel`，`caravel_core.v` 第 524、594 行）只有 POR 會重置（`housekeeping.v` 第 1031、1041 行）。韌體切到 PLL 之後，如果 reset 來自 POR 以外的來源（`resetb` pad、reset 暫存器或 SPI pass-through），拉起時 `use_pll_first`／`use_pll_second` 被非同步清掉，核心時脈切回外部時脈；放開後這兩顆 flop 在 PLL 時脈下依序變回 1，核心時脈再切回 PLL（`caravel_clocking.v` 第 55–66、93–94 行）。兩次切換都經一般的 `mux2_1`（`verilog/gl/caravel_clocking.v` 第 378–393 行的 `_207_`、`_208_`），不是 glitch-free 的時脈切換電路，可能產生很短的時脈脈衝（推論，沒有模擬）。切回 PLL 只要兩個 PLL 時脈，`reset_delay` 要等三個外部時脈的下降緣，所以切換大概發生在 `wb_rst_i` 仍拉起的期間（推論）。
- **`vccd1` 的上電順序**：送進 wrapper 的 reset 與時脈都要經過 `mprj_logic1` 這組 tie-high（`mgmt_protect.v` 第 232–233 行），它由 `vccd1` 供電（`mprj_logic_high.v` 第 23–29 行；`mgmt_protect.v` 第 122–128 行）。`vccd1` 在 Caravel 的 reset 放開之後才上電時，wrapper 收不到 reset，flop 停在上電時的任意狀態，`host_en` 也可能是 0（推論）。補救方式是由管理用韌體或外部再觸發一次 reset（reset 暫存器或 `resetb` pad），會連管理用 SoC 一起重置；`mprj_logic1[461]` 也接成 `user1_vcc_powergood` 給管理端讀（`mgmt_protect.v` 第 257 行），韌體可以先確認 `vccd1` 有電再觸發（推論）。

## 4. 給下一個要放進 Caravel 的專案

以下都是推論，沒有模擬：
- 在 wrapper 內對 `wb_rst_i` 加一個 2 顆 flop 的同步器（時脈用 `wb_clk_i`），讓拉起也變成同步的，`soc_top` 規格的「同步 reset」與 RTL-RST-01 就完全成立。這是業界常見的整合做法：外部送進來的非同步 reset，先在使用它的時脈域同步。本專案不下線，不改（ADR-0022 決定 1 的選項 E）。
- 不要把 SoC 規格的「reset 至少 N 個 cycle」當成 Caravel 保證的；Caravel 只保證放開在下降緣，長度由 reset 來源決定。
- 晶片上電程序要確認 `vccd1` 先有電，或在韌體裡等 `user1_vcc_powergood` 之後再觸發一次 reset。
- harden 後用 `report_checks -from wb_rst_i` 讀 reset 放開路徑的 slack，不要只看整體最差值。
- 韌體啟用 PLL 之後，避免用 POR 以外的來源（`resetb` pad、reset 暫存器、SPI pass-through）觸發 reset；要用的話，先切回外部時脈。

## 5. 管理端時脈上限：50／40／33 MHz 各是什麼

現行 Caravel 的管理核心是 VexRiscv，不是 PicoRV32（`.tools/caravel-lite` 的 `verilog/gl/caravel_core.v` 第 20207 行起的 `soc.core.VexRiscv.*` net 名稱）。

| 數字 | 出處 | 代表什麼 | 能不能引用 |
|---|---|---|---|
| 約 50 MHz | efabless/caravel `e5cf492`（2021-12-17 01:51 UTC）`docs/source/description.rst`：「Core clock rate: (TBD) MHz maximum over all PVT conditions (likely around 50MHz guaranteed).」同一節寫核心是 PicoRV32。這句在 efabless/caravel 最早出現在同日 10 分鐘前的 `3ccce01`（當時路徑是 `doc/source/description.rst`），`e5cf492` 只把目錄改名 | PicoRV32 時期的估計，自己標 TBD | 不能。`ee7eded`（同日 19:55 UTC）把整節改成「TO BE UPDATED」，`27cbe49c` 仍是（`description.rst` 第 29 行） |
| 40 MHz | `27cbe49c` `signoff/caravel_core/caravel_core.sdc` 第 7–8 行（`clk_period 25`）；`docs/source/maximum-ratings.rst` 第 40 行（「Absolute maximum ratings」表格的「Management clock」列，`a61fc8b` 在 2022-03-08 加入）；caravel_mgmt_soc_litex `openlane/mgmt_core_wrapper/config.tcl` 第 22 行（`CLOCK_PERIOD 25`） | 設計目標：Caravel 自己對管理核心 signoff 用的時脈 | 可以，寫明是設計目標 |
| 33 MHz | `27cbe49c` `docs/caravel_datasheet_2.pdf`（CARAVEL-001）§3.2 Operating conditions，第 11 頁：「Clock and IO frequency」0–33 MHz，操作溫度 0–70 °C；第 1 頁的特色清單也寫 33 MHz | datasheet 保證的操作條件 | 可以，最保守 |

另外，Efabless 文件裡還有 80 MHz（`counter-timers.rst` 第 25 行、`gpio.rst` 第 193 行）與 100 MHz（`uart.rst` 第 56 行）這類數字，都是舉例，不是額定值。所以判斷時以 signoff 用的 SDC 與 datasheet 為準，不要以文件內文為準。

ADR-0019 原本引的是第一列，而且沒附出處。技術報告 §3.4 已經引用 40 MHz，§9.1 卻寫「TBD，約 50 MHz」，前後矛盾；報告的「Efabless 文件」指的是 `27cbe49c` 的 `docs/`，而那一版同一節寫的是「TO BE UPDATED」，所以和報告自己宣告的出處也對不上。

### 對本設計的影響

- signoff 在 44 ns（22.7 MHz），比上面三個數字都慢。signoff 的結論與「管理端時脈 ≤ 22.7 MHz」這條使用限制（`docs/phase_exit/phase7.md` 已知限制 6，第 218 行）都不變，不用重跑 harden 或 STA。
- wrapper 的 IO constraint（`caravel_io.sdc`）是 Caravel 那一端的固定延遲，只有 `wb_rst_i` 會跟週期縮放，不受 Caravel 上限寫 40 或 50 MHz 影響（推論，依 SDC 的寫法）。
- 如果真的跑在 40／50 MHz（推估，沒有實際跑 STA）：
  - 最差的應該是 Hazard3 的整週期路徑。soc_top Hazard3 在 43 ns 是 −0.381 ns（`docs/relaxation_register.md` T03，第 27 行），推回 44 ns 約 +0.6 ns；週期每縮 1 ns 就少約 1 ns，25 ns 約 −18 ns，20 ns 約 −23 ns。
  - SRAM 的半週期路徑：dout0 transition 改用量到的值後，44 ns 時最差 setup +0.151 ns（`phase7.md` 已知限制 2，第 214 行）。可用時間約 0.45 個週期（半週期扣掉 5% 的 DCD），25 ns 約 −8.4 ns，20 ns 約 −10.6 ns。
  - PicoRV32 時期在 25 ns 實際跑過 STA what-if，SRAM 路徑就差約 7 ns（ADR-0004 第 13 行）。
  - 兩個頻率都遠遠不過。第一輪查證寫的「−8／−10 ns」低估了差距，第二輪更正。
- 44 ns 本身幾乎沒有空間：半週期路徑最短大約只能到 43.7 ns（0.151 ÷ 0.45 ≈ 0.34 ns），整週期路徑沒有在 wrapper 上反推過（放寬清單 T03）。第一輪查證說「最短可跑週期約 42.8 ns」，沒考慮已知限制 2，不成立。

### 另案（沒有決定）

查核時讀到 Caravel 未發布的 DLL 文件寫，DLL 模式每個週期可能瞬間變動約 250 ps，比 `clock_uncertainty.sdc` 假設的 period jitter 0.15 ns 多約 0.1 ns；而最差 setup 用量到的 transition 只剩 +0.151 ns。這份文件本筆記沒有再核對原文，數字怎麼解讀還不確定，要另開一題（放寬清單 T07）。

## 6. 這次改了什麼，之後要做什麼

- 這次（ADR-0022 決定 1、2）：
  - ADR-0019 第 31、60、66 行加 2026-10-16 的更正註記，不改原文；
  - `rtl/caravel/wb_host_bridge.v` 第 25–27 行、`pnr/user_project_wrapper/caravel_io.sdc` 第 4–6、24–26 行只改註解，不改邏輯與 SDC 指令；
  - 本筆記與 ADR-0022。
- 同一個 commit 一起完成（由其他工作進行）：
  - `caravel-user-project-integration` 的經驗紀錄加一列，分清楚由原始碼確認的與推論的；推論不寫進正式規則（CLAUDE.md 規則 3）；
  - `docs/spec/soc_spec.md` §4.9 第 166、168 行加註記：Caravel 版的 `resetn` 拉起是非同步的，10 個 cycle 與 RTL-RST-01 只在 reset 同步時成立；
  - 技術報告的對應段落（§3.4 reset 的路徑第 4 點補上 SPI pass-through；§9.1 的管理端時脈；§3.4 的 40 MHz 補上 25 ns 與 33 MHz），然後重建兩份 PDF。
- 驗證：`make lint`（含 Caravel 版）與 `make pin-plan`（`scripts/check_pin_plan.py` 會讀 ADR-0019 的核准原話）。不用 harden 或 regress。
