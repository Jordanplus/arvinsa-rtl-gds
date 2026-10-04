---
name: signoff-criteria
description: 決定或檢討 signoff 條件的數值與依據時使用：clock uncertainty 要算哪些成分（jitter、duty cycle、skew、margin）、OCV derate、PVT corner 與溫度反轉、IO delay、IR drop 預算、EM、SI（crosstalk）、max transition／cap／fanout、antenna、density、latch-up，以及開源工具沒分析的項目要怎麼用 margin 補。Use when deriving or reviewing signoff limits and margins (uncertainty, derate, corners, IR/EM/SI budgets, PDK rules) for sky130 + LibreLane/OpenROAD.
---

# Signoff 條件怎麼推導

每一個 signoff 條件都要能回答四件事：
1. 它防的是什麼實際問題。
2. 數值由哪些成分組成、怎麼算。
3. 預設值出自哪個檔案的哪一行。
4. 開源工具到底有沒有分析它；沒有的話，用哪一筆 margin 或哪一個額外檢查補上。

LibreLane 對 sky130 的預設值多半是沿用 OpenLane 1 的常數，沒有成分說明。所以「用預設值」不等於「條件合理」。

本 repo 實例：`docs/notes/signoff_criteria_soc_top.md`（soc_top 逐項的數字、缺口與建議動作）。

相關 skill：
- SDC 寫法：`timing-constraints-sdc`
- 修違規：`drv-timing-closure`
- IR 的執行：`pdn-ir-drop`
- DRC、antenna：`drc-signoff`、`antenna-signoff`
- checker 本身的 negative test：`signoff-checker-qualification`

名詞：
- **jitter**：clock 邊緣相對理想時間的抖動。有三種：
  - period jitter：單一週期比理想值長或短多少。
  - cycle-to-cycle jitter：相鄰兩個週期的長度差。
  - long-term jitter：多個週期累積的偏移。
- **DCD**（duty cycle distortion）：clock 高電位時間不等於半個週期。例如 55%／45%。
- **OCV**（on-chip variation）：同一顆晶片上不同位置的快慢差異。
- **derate**：把延遲乘上一個係數，例如慢的一邊 ×1.05。
- **CRPR**：launch 與 capture 共用的那段 clock path 不可能同時快又慢，工具把重複算的悲觀量扣回來。
- **SI**：相鄰繞線之間的耦合造成的延遲變化與雜訊。
- **EM**（electromigration）：電流密度太大時金屬原子被推移，長期使用後斷線。

## 先要有的輸入（沒有就寫「假設」並標明）

| 輸入 | 用在哪裡 | 沒有時 |
|---|---|---|
| clock 來源：晶振、PLL 或 DCO；period jitter 的峰值或 RMS；duty cycle 範圍 | setup uncertainty、DCD、min pulse width | 假設值，報告標「假設」。RMS 換峰值的倍數取決於觀察的 cycle 數或允許的錯誤率，不能寫死：SiTime AN10007 中 10,000 cycles 對應 ±3.719σ |
| 供電範圍（最低、典型、最高）與接面溫度範圍 | corner 是否涵蓋、IR drop 預算 | 用載具晶片的規格。Caravel：VCCD 1.62／1.8／1.98 V，Tj −40～100 °C（caravel-harness maximum-ratings） |
| 外部介面的時序（外部 clk→Q、外部 setup／hold、板上走線）與上層 clock source latency | IO delay 的 -min／-max | block 層級標「假設」，不要直接把 -min 設成 0（規則 6） |
| 電源 pad／bump 的位置 | IR drop 的電壓源 | 預設是 PDN 的所有 pin 形狀，偏樂觀 |
| 封裝與平台會做的檢查 | 哪些交給 chip-level | 寫出範圍聲明 |

## 已驗證的工具行為（LibreLane 3.0.14、OpenSTA 857316ff、OpenROAD dcf36133）

1. **signoff STA 的引擎**是獨立的 `sta` binary，不是 openroad 內建的 OpenSTA（`librelane/steps/openroad.py` 第 579 行；`.tools/librelane/nix/opensta.nix` 第 20–21 行，`sta -version` 為 2.7.0 加上 LibreLane patch）。驗證約束行為的實驗要在這支 binary 上做。
2. **LibreLane 對 sky130 的預設**（`librelane/config/pdk_compat.py`、`librelane/scripts/base.sdc`、PDK `libs.tech/openlane/sky130_fd_sc_hd/config.tcl`）：

   | 項目 | 值 | 說明 |
   |---|---|---|
   | clock uncertainty | 0.25 ns，setup 與 hold 同值 | pdk_compat 327–328；base.sdc 65–66；沿用 OpenLane 1 的常數，沒有成分說明 |
   | clock transition | 0.15 ns | 只在 ideal clock 時使用；signoff（propagated clock）不使用，改用實際算出的 slew |
   | timing derate | early 0.95、late 1.05，套用到 cell、net、clock 與 data path 全部 | base.sdc 71–73；這是唯一的 OCV 建模 |
   | IO delay | 週期 × 20%，input 與 output 都是，min = max | base.sdc 19–20、44–45 |
   | 輸入驅動／輸出負載 | `inv_2/Y`／33.442 fF（= inv_16 的 A pin） | PDK config 27–31 |
   | max transition／cap／fanout | 0.75 ns／0.2 pF／10 | PDK config 62–64 |
   | 哪些 corner 判 FAIL | setup 只判 `*tt*`；hold 判全部 corner（`checker.py` 第 683 行）；max slew、max cap 預設都不判 | 要全部判 FAIL 就把四個 `*_VIOLATION_CORNERS` 都設 `["*"]` |

3. **uncertainty 在 propagated clock 下照樣套用**。指定邊緣的 inter-clock uncertainty（`-fall_from clk -rise_to clk`）會**取代**一般的值，不是相加（OpenSTA `search/PathEnd.cc` 364–381）。實測：設 1.0 ns 後 slack 少了 0.75 ns，也就是 1.0 − 0.25。
4. **clock skew 的 metric 不是 skew 的真值**：`clock__skew__worst_*` 與 `report_clock_skew` 都含 uncertainty，也含 ±5% derate。要看名目的 skew，得扣掉 uncertainty，再把 launch 端除以 1.05、capture 端除以 0.95。
5. **instance derate 取代 global derate**，不是相乘。優先順序是 instance → lib cell → global（OpenSTA `sdc/Sdc.cc` 626–662）。對 macro 設 ss 1.5，結果就是 1.5 倍，原本的 OCV 1.05 不再套用；要保留 OCV，就自己乘進去（1.5 × 1.05）。
6. **IO delay 的 min／max 要和 clock latency 一起建模**：
   - block 內的 flop 在 clock tree 後面，有幾 ns 的插入延遲；外部 launch 端卻被當成 0 latency。
   - 只把 input／output 的 `-min` 改成 0，會出現大量假的 hold 違規。soc_top 實測：269 個端點，最差 −3.3 ns。
   - 正確做法：搭配 `set_clock_latency -source -min/-max`，或帶 latency 的 virtual clock。Caravel 的 `user_project_wrapper/signoff.sdc` 第 67–98 行就是範本。
   - 不加 `-source` 的 `set_clock_latency` 會把 clock 變回 ideal，不要用。
7. **`set_max_transition -clock_path` 在 propagated clock 下不會作用**：OpenSTA `search/CheckSlews.cc` 第 272 行用 `isIdealClock` 判斷 clock pin。實測：`-clock_path 0.05` 時 0 筆違規；`-data_path 0.05` 時連 clock buffer 的 pin 都被列進來。所以要另外限制 clock slew，得寫 checker 逐一看 clock net 的 pin。
8. **`report_clock_min_period`（fmax）不能當 signoff 依據**：它只看 rise→rise 與 fall→fall 的路徑（OpenSTA `search/Sta.cc` 第 3604 行），會排除半週期路徑，也不看 .lib 的 `minimum_period`。實測：週期 32 ns 時 setup 已經 −0.42 ns，報告仍說 `period_min = 25.41`。最小週期要從半週期路徑反推。
9. **`set_max_transition` 的有效上限**：取 SDC、pin 的 `max_transition`、輸出 pin 的 `default_max_transition` 三者中最嚴的（`CheckSlews.cc`）。`max_capacitance` 也一樣取 SDC 與 pin 中較小的（`CheckCapacitances.cc`），而 pin 的上限每個 corner 不同：sky130 的 ss 比 tt 小約 37%。
10. **sky130_fd_sc_hd .lib 的量測與特性化範圍**：slew 的量測門檻是 20%–80%（tt.lib 157–160）。多數延遲表的輸入 slew 只到 1.5 ns，整份 tt.lib 只有 18 張表到 5 ns（buf_8／12／16）。`default_max_transition` 為 1.5 ns。PDK 的 0.75 ns 是 1.5 的一半，這個關係是推論，沒有出處。
11. **OpenSTA 沒有 SI 分析**：
    - read_spef 把 coupling cap 乘上 factor（預設 1.0）後接地，也就是當作鄰線不動（`parasitics/Parasitics.tcl` 50、72–73）。
    - 維護者在 issue #99 表示 SI「has not been started」；PDK 附的 ccsnoise .lib 不會被使用。
    - **用全域 coupling factor 做邊界分析不保證悲觀**：factor 2.0 也會拖慢 capture clock，實測 setup 反而變好 0.11 ns。clock 與 data 要分開處理。
12. **sky130 只能用 flat derate**：三份 .lib 都沒有 ocv／sigma／LVF 表。本版 OpenSTA 也沒有 LVF（3.0.1 之後才有）。AOCV、POCV 都不適用。
13. **IR drop**（LibreLane `irdrop.tcl`、OpenROAD PSM）：
    - 只做 static。
    - 電流用 nom_tt 的 SPEF 加上 OpenSTA 的預設 activity，電壓取 lib 的 1.8 V。
    - 金屬電阻取 `set_layer_rc`（也就是 nom_tt 的 `LAYERS_RC`），不是最大電阻的 corner（`ir_solver.cpp` 415–463）。
    - 沒給 `-vsrc` 檔時，PDN 的所有 pin 形狀都當成理想電壓源（`ir_solver.cpp` 507–527）。
    - `set_pdnsim_inst_power` 是**疊加**在 STA 功耗之上（844–878 行兩段都是 `+=`）：要模擬功耗變成 k 倍，給 (k−1)×P。
14. **EM**：tech LEF 有每層的 DC／AC 電流密度上限（例如 met1 2.8／6.1 mA/µm）。PSM 用 `analyze_power_grid -enable_em -em_outfile` 可以輸出每段電源線的電流，但 LibreLane 沒有開，也沒有任何工具比對。signal net 的 EM 沒有任何開源工具分析。
15. **KLayout 的 sky130 DRC deck**（`sky130A_mr.drc`）：
    - 沒有 latch-up（LU）、`nwell.4`、density、antenna 規則。
    - nsdm／psdm 的寬度、間距、包覆規則只有 `sram_exclude=true` 時才跑（557–633、639–729 行），LibreLane 沒有開，所以這些只由 Magic 檢查。
    - LibreLane 傳的 `floating_metal`、`topcell`、`threads` 和 deck 讀的變數名對不上（`$floating_met`、`$top_cell`、`$thr`），所以浮接金屬檢查開不起來。
    - 結論：「KLayout DRC = 0」不代表 latch-up、density、antenna 合格。
16. **latch-up**：
    - SkyWater 的預設規則是 tap 到 diffusion 6 µm。只有 `areaid.lowTapDensity`（81/14）覆蓋、且距 padframe ≥ 50 µm 的區域，才能用 15 µm（skywater-pdk `rules/layers.html`）。
    - Magic 寫 GDS 時會自動產生 81/14，KLayout 的 GDS 沒有。
    - `FP_TAPCELL_DIST 13` 的意思是每列 tap 間距 2 × 13 µm，相鄰列錯開半格，最壞約 13 µm。
17. **metal density**：
    - Classic flow 不插 metal fill，也不檢查 density。`FillInsertion` 只放 standard cell filler 與 decap。
    - 下限 35%（met5 45%）只寫在 PDK 的 Magic `check_density.py` 裡。
    - ChipFoundry 的 cf-precheck 只檢查上限（`met_min_ca_density.lydrc`）。
    - slotting（m1–m4 .11／.12）與 m*.13 是銅製程專用規則，sky130 是鋁後段，不適用。
18. **antenna**：
    - OpenROAD 的比值與 tech LEF 一致。
    - Magic 的 via1 參數比較嚴（3＋18×A，tech LEF 與 SkyWater 是 6＋36×A；`sky130A.tech` 第 5087 行）。
    - `diode_2` 本身帶 `ANTENNAGATEAREA` 0.4347，OpenROAD 會把它加進閘極面積。
    - OpenROAD 不讀 `ANTENNAPARTIALMETAL*AREA`，所以 macro 階層之間的 antenna 只能靠 port diode。
19. **PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒有生效**（`resolved.json` 為 None），clock 實際走 met1／met2。要讓 clock 走粗金屬，必須在專案 config 明確設定。

## 各條件的推導方法

### 時序

| 條件 | 推導 | 工具支援／沒分析時怎麼補 |
|---|---|---|
| setup uncertainty | pre-CTS（ideal clock）：J_period + S_est + M_setup；post-CTS 與 signoff（propagated）：J_period + M_setup，skew 已由 STA 算出，不能再加。J_period 用 period jitter 的峰值 | M_setup 要逐條寫出它取代了哪些沒分析的效應：SI delta delay、dynamic IR、aging、macro 模型誤差。分開寫 `-setup`、`-hold` |
| hold uncertainty | 同一個 edge 送出又接收，period jitter 在兩端抵銷：pre-CTS 為 S_est + M_hold，post-CTS 為 M_hold | M_hold 涵蓋：SI 造成的加速、capture clock 的 dynamic IR、ff corner 電壓與實際最高供電的差、extraction 誤差 |
| 半週期路徑（一個 edge 送出、相反 edge 接收） | 可用時間 = T × (1 − D) 或 T × D；DCD 預算 = max(0, D_max − 0.5) × T + J_half，只對讓可用時間變短的方向敏感 | 用 `set_clock_uncertainty -fall_from [get_clocks clk] -rise_to [get_clocks clk] -setup <J + DCD + M>` 建模，這個值會取代一般值，所以要包含完整的 jitter 與 margin。或用 `create_clock -waveform {0 T×D_max}` 另跑一次 what-if。來源造成的 DCD 和 clock tree／driving cell 造成的 rise／fall 不對稱要分開列，後者 STA 已經算到 |
| min pulse width、minimum period | 高電位時間 T × D_min − J_half 必須 ≥ .lib 的 `min_pulse_width`；低電位同理 | LibreLane 不跑；要加 `report_check_types -min_pulse_width -min_period -violators`，並把違規數變成 checker |
| OCV | flat derate d；sky130 沒有 local variation 資料，5% 是沿用值 | 要改 d，要用 SPICE mismatch model 做 Monte Carlo（方法為推論）。macro 的 instance derate 要乘上 OCV（規則 5） |
| PVT corner | IR 預算 = V_supply_min − V_slow_corner（例如 1.62 − 1.60 = 20 mV）；hold 用 V_supply_max，而且不扣 IR | 先掃描 PDK 所有 .lib，比較同電壓下不同溫度的延遲，看有沒有溫度反轉（低電壓時低溫反而比較慢），再決定 corner 清單 |
| IO delay | input -max = 外部 clk→Q(max) + 走線(max)；-min 用 min 值；output -max = 外部 setup + 走線；output -min = −外部 hold + 走線(min)。都要和 source latency 一起給（規則 6） | 非同步的 port 不該給 IO delay：加 synchronizer，再設 false path |
| max transition／cap | 有效上限是 SDC 與 .lib 取較小者，而且每個 corner 不同（規則 9）；目的是讓延遲查表落在特性化範圍內 | 0.75 ns 是設計上的保守值，放寬要寫 ADR |
| max fanout | sky130 .lib 沒有 max_fanout，所以這不是物理限制，是實作輔助 | signoff 以 slew 與 cap 為主 |
| resizer 的 slack margin | margin =（post-CTS 估計 − signoff 結果）的實測差距 × 安全係數 | 這是實作手段，不能拿來代替 signoff 的餘量 |
| 「典型 corner 的 slack ≥ 週期 X%」這類規則 | 只有在 slow corner 對 typical 的延遲比 r < T_avail / (T_avail − X) 時，才會比「slow corner ≥ 0」更嚴；std cell 的 r 約 1.9，所以通常沒有作用 | 餘量放在最慢的 corner，並逐項列出它涵蓋什麼 |

### 電源與可靠度

| 條件 | 推導 | 工具支援／沒分析時怎麼補 |
|---|---|---|
| static IR drop 上限 | 不能超過 corner 電壓隱含的預算（上表的 PVT 一列）。上限大於預算時，STA 的 slow corner 就不再保守 | 用最大電阻的 RC corner 與最大功耗的 corner 再算一次（`analyze_power_grid -corner`）；電壓源要放在真實 pad 的位置 |
| dynamic IR、L·di/dt | 開源工具沒有 | 用 decap 與 margin 補；用最壞情境的 VCD（reset 解除、SRAM 連續讀寫）估 peak current |
| 功耗 | 沒有 VCD／SAIF 時用預設 activity（vectorless）；`power__total` 是最後寫入的 corner | 用模擬的 activity（`read_vcd`、`read_saif`）；報告附上 activity 標註率 |
| power grid EM | 每段電流 / 線寬 ≤ tech LEF 的電流密度（Tj 90 °C 基準）；via 個別比對 | `-enable_em` 輸出電流後自己比對 |
| signal EM | 估算 I_rms ≈ C·V·√(2/(t_r·T))，t_r 是 transition 時間，與最小線寬的 AC 上限比 | 沒有工具，只能估算，標明「估算」 |
| aging（NBTI／HCI） | sky130 沒有 aging 模型 | 放進 M_setup，並寫明「不分析」 |

### 實體與 PDK 規則

| 條件 | 推導 | 工具支援／沒分析時怎麼補 |
|---|---|---|
| antenna | 每層 gate 比值上限（tech LEF 的 PWL）；diode 會用擴散面積放寬上限 | macro 的 LEF 沒有 `ANTENNAGATEAREA` 時，checker 看不到接到 macro 的線（`antenna-signoff`） |
| latch-up | tap 間距（規則 16） | Magic 的完整 GDS DRC 才檢查 LU.2／LU.3／nwell.4；chip-level 要確認 81/14 的覆蓋範圍 |
| density | 700 µm 視窗，35%–70%（met5 45%–76%） | 屬於 chip-level：macro 只記錄實測密度，不判 FAIL。但 macro 若畫了禁止 fill 的區域，該區的密度要自己達標（SkyWater waffleDrop 規則，IP 等級必須遵守） |
| LVS 範圍 | LibreLane 只做到 macro 為 black box 的 LVS | device-level LVS、soft connection、ERC（CVC-RV）都在 LibreLane 之外 |

## 實作範本（soc_top，Phase 4）

推導出來的條件要變成 flow 的一部分，而且每一項都有植入錯誤的案例：

| 條件 | 寫在哪裡 | 怎麼判 | negative test |
|---|---|---|---|
| setup／hold uncertainty 分開、逐項列成分 | `pnr/soc_top/clock_uncertainty.sdc`（PnR 與 signoff 的 SDC 都 source） | STA 本身 | P01、P02 |
| 半週期路徑的 DCD 預算 | 同上：`-fall_from`／`-rise_from` 的 inter-edge uncertainty = 半週期 jitter + DCD + margin | STA 本身 | P24（D = 60%）、P25（預算改 60%），最差路徑必須從 sram0 下降緣送出 |
| min pulse width、min period | `sta_extra_corner.tcl` 每個 corner 輸出報告，必要的 slack 從 SDC 的變數算 | `check_soc.py pulse_width` | P22、P23 |
| macro derate 乘進 OCV | `sta_extra_corner.tcl` | STA 本身 | P04 |
| 溫度反轉 corner | `config.json` 的 `STA_CORNERS`、`LIB`（resizer 用 `RSZ_CORNERS` 另外控制，`multicorner-sta`） | `[corners]` | — |
| IR 預算（VDD 降壓 + GND 抬升） | `[max_sum]`；供電模型 `VSRC_LOC_FILES` | `check_signoff.py`、`check_soc.py ir_sources` | P07、P26–P29 |
| 「typical corner slack ≥ 週期 X%」 | 降為只報告（`[info]`） | — | — |

假設值（jitter、duty cycle 範圍、供電位置）集中寫在檔案開頭並標「假設」，確定來源後只改那幾個值。

## 不分析的項目清單（每次 signoff 都要逐條寫在報告裡）

SI（delta delay 與 glitch）、dynamic IR、signal EM、aging、ESD、density 下限、chip-level latch-up marker、device-level LVS、電路層級 ERC。

每一條都要寫出用哪一筆 margin 或哪一個額外檢查涵蓋；兩者都沒有的，就寫「沒有涵蓋」。

## negative test（植入錯誤，確認 checker 抓得到）

每個推導出來的條件寫成 checker 之後，都要有一個植入錯誤的案例，作法照 `signoff-checker-qualification`：
- DCD：`create_clock -waveform {0 T×0.6}`，半週期路徑必須 FAIL。
- min pulse width：把 clock 改成很窄的脈衝，必須 FAIL。
- IR 上限：把 metric 改大，或放大 PDN pitch，必須 FAIL。
- IO：拿掉某個 port 的 delay，必須出現 unconstrained 警告。

## 用完後

1. 本次的推導結果寫進該設計的 repo 文件（本 repo：`docs/notes/signoff_criteria_<design>.md`），不寫進本 skill。
2. 新發現的工具行為寫進「經驗紀錄」；用實驗確認過的，搬進「已驗證的工具行為」。
3. LibreLane、OpenROAD、OpenSTA 或 PDK 升版時，逐條重新確認規則 1–19 的行號與行為。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | arvinsa-rtl-gds soc_top | 最差 setup 路徑是 SRAM 下降緣送出的半週期路徑；0.25 ns uncertainty 沒有 DCD 預算 | 已驗證：nom_ss 改 waveform，D = 59% 時 slack −0.022 ns，D = 60% 時 −0.422 ns | 列入 Phase 4 待辦，等 clock 來源規格確定再定數值 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-03 | 同上 | IR 上限 90 mV，但 ss corner 1.60 V 對 Caravel 最低供電 1.62 V 只隱含 20 mV 預算 | 已驗證（規格與 .lib 數值）；實測 0.3 mV，所以是規則不一致，不是違規 | 同上 | 同上 |
| 2026-10-03 | 同上 | 調查 agent 的 22 項論述中有部分錯誤：把 skew metric 當真值、`-clock_path` 的建議無效、全域 coupling factor 當上界、hold 預設的判 FAIL corner 寫錯 | 已驗證：獨立核對 agent 實測推翻 | 本 skill 只收錄核對過的結論 | workflow `signoff-criteria-research` |
| 2026-10-04 | soc_top Phase 4 | uncertainty 成分、DCD、pulse width、溫度反轉 corner、derate×OCV、IR 預算全部實作 | 已驗證（單 corner `sta` 實驗：半週期路徑 slack 0.83 ns；pulse width slack 7.95 ns） | 「實作範本」一節 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-04 | soc_top IR 研究 | LibreLane 的 IR 是「所有 pin 理想」且只看 VDD；換成一側供電 + VDD/GND 合計後 8.2 mV（最壞組合 11.5 mV） | 已驗證（agent 單步重跑 16 種組合） | IR 預算改判合計；`pdn-ir-drop` 規則 4、10、11 | `docs/notes/ir_worst_case_soc_top.md` |
