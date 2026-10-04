# soc_top 的 static IR drop：供電模型與最壞情況（2026-10-04，Phase 4）

## 問題

- 使用者決定 IR drop 上限 20 mV（`docs/notes/signoff_criteria_soc_top.md`）：ss corner 的 .lib 在 1.60 V 特性化，Caravel 的 VCCD 最低 1.62 V，cell 的 VPWR 與 VGND 之間只能少掉 20 mV。
- Phase 3 的 IR drop 是 0.306 mV，用的是 LibreLane 的預設供電模型：所有電源 pin 的形狀都當成理想電壓源。soc_top 的電源 pin 是 5 條橫跨整顆 macro 的 met5 strap 加 7 條 met4 strap（`final/def/soc_top.def` 的 PINS），等於整條 strap 處處都是理想電源，所以數字非常小，不能當 signoff 依據。
- 真正的供電位置要到 Phase 7（Caravel wrapper 怎麼接這顆 macro）才知道。

## 做法

一個 agent 在 Phase 3 的版圖上（PDN 與 Phase 4 相同）用 OpenROAD PSM 重跑 LibreLane 的 `OpenROAD.IRDropReport` step，比較 4 種供電模型與 4 種 corner。腳本與原始結果在 `docs/notes/ir_study/`（`ir_custom.tcl` 是 LibreLane `irdrop.tcl` 加診斷輸出與開關；`results_raw.txt` 是每次 run 的摘要）。

## 結果（單位 mV；「合計」= VDD 降壓 + GND 抬升）

| 供電模型 | corner | vccd1 降壓 | vssd1 抬升 | 合計 |
|---|---|---|---|---|
| A. 所有 pin 形狀當理想電源（LibreLane 預設，Phase 3 的數字） | nom_tt | 0.306 | 0.249 | 0.555 |
| | ff 電流 + ss 金屬電阻（上限用的組合） | 0.414 | 0.339 | 0.753 |
| B. met5 每 34 µm 一個供電點（PSM 的 STRAPS，每個 net 145 點） | nom_tt | 0.583 | 0.525 | 1.108 |
| | ff 電流 + ss 金屬電阻 | 0.782 | 0.705 | 1.487 |
| **C. 只從一側供電：每條 met5 strap 左端 1 點（每個 net 5 點）** | **nom_tt** | **4.11** | **4.09** | **8.19** |
| | max_ss | 4.89 | 4.87 | 9.75 |
| | max_ff | 3.19 | 3.18 | 6.36 |
| | **ff 電流 + ss 金屬電阻** | **5.75** | **5.73** | **11.46** |
| D. 整顆 macro 只有一個供電點（最上面那條 strap 的左端） | nom_tt | 24.0 | 24.1 | 48.1 |
| | ff 電流 + ss 金屬電阻 | 33.6 | 33.6 | 67.1 |

- 電流與電阻：nom_tt 7.76 mW、max_ss 6.50 mW、max_ff 9.03 mW（SRAM 每個 corner 都是 0.708 mW，來自 padded.lib）；met5 每平方電阻 tt 0.0285、ss 0.0370、ff 0.0199 Ω。沒有一個真實的 corner 同時有最大電流（ff）與最大電阻（ss），所以「ff 電流 + ss 金屬電阻」是人為組合的上限，不是物理上存在的 corner。
- 最壞位置：模型 C、D 在右下角（離左側供電點最遠）。
- EM（電流密度）：模型 C 每一層最高約上限的 32%（via4：vccd1 31.9%、vssd1 32.4%，以 ff 電流 + ss 電阻計）；模型 D 的單一個 via4 cut 流 3.3 mA，超過上限 2.49 mA。

## 結論與做法

1. **signoff 改用模型 C**（`pnr/soc_top/config.json` 的 `VSRC_LOC_FILES`，點位在 `pnr/soc_top/vsrc/`）：比 LibreLane 預設悲觀，但仍是每條 strap 都接得到電源的合理假設。`check_soc.py ir_sources` 檢查每個點都在對應 net 的 met5 strap 上。
2. **判定改成「VDD 降壓 + GND 抬升 ≤ 20 mV」**（`signoff/limits/soc_top.toml` 的 `[max_sum]`）：LibreLane 的 `ir__drop__worst` 只有 vccd1 的降壓（它只取 `irdrop.rpt` 的第一筆），GND 抬升在 `design_powergrid__drop__worst__net:vssd1`；20 mV 的預算是兩者合計。
3. flow 的 IR step 用 nom_tt：本研究在 Phase 3 版圖上是 8.19 mV；Phase 4 改 42 ns 後的 golden run 實測 4.04 + 4.03 = 8.07 mV。最壞的組合（本研究，Phase 3 版圖）是 11.46 mV，仍比 20 mV 低 8.5 mV。
4. **Phase 7 要確認**：Caravel 實際怎麼接這顆 macro 的電源。如果只有一個接點（模型 D），20 mV 與 EM 都不過。
5. picorv32_core（只當流程測試用的 block）保留 LibreLane 預設模型，判定同樣改成兩個 net 合計 ≤ 20 mV。

## 工具行為（這版 OpenROAD，2026-02-17）

- 只要 net 有 pin，PSM 一律拿所有 pin 形狀當電源，`-source_type` 被忽略（log：`Generate source nodes from bterms`）；給 `-vsrc` 檔時才只用檔案裡的點。
- `-vsrc` 檔格式（實驗確認）：每行 `x_um,y_um,size_um,voltage`，逗號分隔；以 (x, y) 為中心、邊長 size 的正方形內，最上層金屬的節點都變成理想電源。用空白分隔會報 `PSM-0075 Expected four values on line`。
- LibreLane 的 `VSRC_LOC_FILES = {net: file}` 走的就是這個選項；給了它，`irdrop.tcl` 不再呼叫 `set_pdnsim_net_voltage`，電壓取檔案第 4 欄。

## 限制

只做 static；switching activity 用 OpenSTA 的預設值；SRAM 的電流來自 padded.lib（解析模型），只從一個端點注入，SRAM 內部的 grid 沒有分析；via 電阻不隨 corner 變；macro 以外（Caravel wrapper、pad、封裝）的壓降不在內，20 mV 的預算假設 1.62 V 在 macro 的 pin 上成立。
