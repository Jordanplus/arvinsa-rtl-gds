# ADR-0008：SRAM 的 LEF 補上 antenna 資料（ANTENNAGATEAREA）

- 狀態：已採用（2026-10-03）
- 背景：PDK 的 `sky130_sram_2kbyte_1rw1r_32x512_8.lef` 沒有任何 `ANTENNA` 屬性（`project-plan.md` §5.1、§6.4、風險 R6）。OpenROAD 的 antenna 檢查與修復靠 LEF 的 `ANTENNAGATEAREA` 知道一個 pin 後面接了多少電晶體閘極；沒有這個值，接到 SRAM 輸入的 net 一律不被檢查，「antenna = 0」只是看不到。LibreLane 的 `Odb.CheckMacroAntennaProperties` 也因此警告「59 個 input pin 沒有 antenna gate 資訊」。

- **Antenna 效應**：製造時，金屬線在接上上層金屬之前像天線一樣收集電漿電荷；如果它只接到電晶體閘極、又夠長，電荷會擊穿閘極氧化層。規則是「金屬面積 ÷ 閘極面積」不能超過上限，所以必須知道閘極面積。

## 試過但不採用的做法

| 做法 | 結果 |
|---|---|
| `RUN_HEURISTIC_DIODE_INSERTION`（規劃 §6.4 的第一個選項） | 它對整個設計所有超過 90 µm 的 net 加 diode，不只 SRAM 輸入；soc_top 被插了 10231 顆，之後 global routing 反覆跑壅塞迭代超過 10 分鐘不收斂，停掉（試跑 soc_explore1） |
| 自寫 checker：接到 SRAM 輸入的 net 總長 ≤ 90 µm（規劃 §6.4 的第二個選項） | 90 µm 是猜的。實際長度最長 355 µm（未修）／252 µm（加 200 µm 長線修復後），但用下面的閘極面積換算，met1／met2 單層可到約 340 µm，總長不是正確的判斷方式 |

## 決策

`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_antenna_lef.py` 從 PDK 的 LEF 與 SPICE 產生 flow 用的 LEF：每個輸入 pin 在 `DIRECTION INPUT ;` 後加一行 `ANTENNAGATEAREA`，其他內容（尺寸、pin 形狀、OBS）完全不變；GDS 仍用 PDK 原檔。`pnr/soc_top/config.json` 的 `MACROS.lef` 改用這份 LEF。

閘極面積由 `gate_area.py` 從 macro 自己的 SPICE netlist 算：把階層攤平，對每個輸入 pin 加總閘極接在該 net 上的 sky130 電晶體 W × L。

| pin | 個數 | 閘極面積 | 內部接到 |
|---|---|---|---|
| `din0`、`addr0`、`addr1`、`wmask0`、`csb0`、`csb1`、`web0` | 57 | 0.6 µm² | OpenRAM DFF（`sky130_fd_bd_sram__openram_dff`）的 D：nfet W=1 + pfet W=3，L=0.15 |
| `clk0`、`clk1` | 2 | 0.168 µm² | macro 內的一級小反相器 |

這樣 OpenROAD 的 antenna 檢查（`OpenROAD.CheckAntennas`）與修復（global routing 後、detailed routing 中插 diode 或換層）就把 SRAM 輸入當成一般閘極處理，signoff 的 `antenna__violating__nets = 0` 也涵蓋了這些 net。

驗證：negative test P06（`pnr/soc_top/neg_pnr.py`）把這份 LEF 的閘極面積除以 1000 後重跑 `OpenROAD.CheckAntennas`，必須出現違規；用原本的面積同一步是 0。

## 限制

- 只算輸入 pin 進去第一級的閘極；macro 內部從 pin 到閘極那一段金屬（也會收集電荷）不在 LEF 裡，OpenROAD 看不到。這段屬於 macro 自身的設計，OpenRAM 產生時已做過 DRC／LVS（PDK 附的 log）。
- 沒有加 `ANTENNADIFFAREA`（輸出 pin 的擴散區面積可以放寬接收端的限制）；不加比較保守。

## 出處

`project-plan.md` §5.1、§6.4、§9 R6；`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gate_area.py`、`gen_antenna_lef.py`；PDK `libs.ref/sky130_sram_macros/{lef,spice}/sky130_sram_2kbyte_1rw1r_32x512_8.*`；sky130 tech LEF `sky130_fd_sc_hd__nom.tlef`（met1 `ANTENNADIFFSIDEAREARATIO` 無 diode 時 400、`THICKNESS 0.35`）。
