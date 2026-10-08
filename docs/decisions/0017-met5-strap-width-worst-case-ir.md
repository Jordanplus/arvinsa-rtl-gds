# ADR-0017：met5 strap 加寬到 4.8 µm（`PDN_HWIDTH`），每次 harden 檢查最壞組合 IR

- 狀態：已採用（2026-10-08，使用者決定「IR 在 Phase 5 內修好」）；兩個 CPU 的 harden（`1dee974`）確認，golden 由這兩個 run 重建（`5aaf036`）
- 背景：flow 的 IR step（`OpenROAD.IRDropReport`）只跑 nom_tt。Phase 4 接受「nom_tt 判 20 mV」，依據是最壞組合（ff 電流 + ss 金屬電阻）在 PicoRV32 的 Phase 3 版圖只有 11.46 mV（`docs/notes/ir_worst_case_soc_top.md`）。Phase 5 換成 Hazard3 後，nom_tt 已到 18.28 mV，Phase 5 exit review 因此重測最壞組合。

## 原因（已驗證）

1. **Hazard3 的最壞組合超過 20 mV**：同一方法（模型 C，每條 met5 strap 左端一點，每個 net 5 點）在乾淨 regress 的版圖（`7348fab`）實測：

   | 版圖 | nom_tt | 最壞組合 | via4 EM（最壞組合，以單一 cut 計） |
   |---|---|---|---|
   | PicoRV32 | 7.40 mV | 10.36 mV | 30% |
   | Hazard3 | 18.28 mV | **25.75 mV** | 78% |

2. **電流大了一倍**：nom_tt 總功耗 PicoRV32 6.92 mW、Hazard3 15.3 mW；max_ff 8.06、18.0 mW（`docs/notes/ir_study/phase5/worst_case_results_raw.txt`）。最壞組合對 nom_tt 的比例兩者都約 1.4，與 Phase 4 相同，所以 nom_tt 的 20 mV 對 Hazard3 不夠。
3. **flow 的 checker 抓不到**：它只看 nom_tt（18.28 mV），判 PASS。

## PDN 的 what-if（Hazard3 版圖，`docs/notes/ir_study/phase5/`）

做法：取 IR step 的輸入 ODB，拆掉 vccd1／vssd1 的 PDN，用 LibreLane 的 `pdn_cfg.tcl` 與 `pdngen` 依候選設定重新產生，再跑同樣的 IR。用現行設定重新產生時，DEF 的 SPECIALNETS 逐行相同、IR 也相同（18.276／25.745 mV），所以方法可信。signal 繞線沿用原版圖。

| 候選 | 改了什麼 | 最壞組合 | via4 EM | 與原 signal 繞線間距不足 |
|---|---|---|---|---|
| 原設定 | met5 1.6 µm | 25.75 mV | 78.4%（1 cut） | — |
| `h32` | met5 寬 3.2 µm | 18.04 mV | 31.3%（2 cut） | 0 |
| `h40` | met5 寬 4.0 µm | 15.86 mV | 28.5% | 0 |
| **`h48`** | **met5 寬 4.8 µm** | **14.14 mV** | **17.9%（3 cut）** | **0** |
| `h64` | met5 寬 6.4 µm | 11.76 mV | 12.1%（4 cut） | 0 |
| `hp7659` | met5 數量加倍（pitch 減半），寬度不變 | 19.20 mV | 37.7% | 1 條 net |
| `hp5106` | met5 數量 3 倍 | 15.62 mV | 22.5% | 7 條 net |
| `v32`、`vp768`、`v32vp768` | 只改 met4（加寬、加密、兩者） | 24.40、24.02、22.65 mV | 38.1%、62.4%、30.8% | 48、19、81 條 net |

- 用掉同樣的 met5 金屬量時，加寬比加密好：2 倍 18.04 對 19.20 mV，3 倍 14.14 對 15.62 mV。加密還會碰到 met5 上的 signal 線。
- 只改 met4 最多降到 22.65 mV，仍超過 20 mV，而且碰到幾十條 met4 signal 線。
- 加寬時 met4–met5 交叉處的 via4 cut 數跟著變多，EM 同時改善。

## 決策

1. 兩份 config（`config.json`、`config_hazard3.json`）都設 `PDN_HWIDTH: 4.8`：met5 strap 1.6 → 4.8 µm，pitch、offset、met4 不變，每個 net 仍是 5 個供電點。`check_inputs.py cpu_config` 要求兩份只差 RTL 的 key，所以兩個 CPU 一起改。
2. `pnr/soc_top/vsrc/vssd1.vsrc` 跟著移到加寬後的 vssd1 strap：y = 646.75、493.57、340.39、187.21、34.03；vccd1 不變。`check_soc.py ir_sources` 檢查每個點在 strap 上。
3. 選 4.8 而不是 6.4（11.76 mV）：what-if 訂的目標是最壞組合 ≤ 約 17 mV，留約 3 mV 給 run 之間的差異與重跑後 placement 的改變。4.8 µm 是達到目標的最窄寬度，而且交叉點的 via4 有 3 個 cut（4.0 µm 只有 2 個 cut，EM 28.5%，離目標只差 1.1 mV）；6.4 µm 多用約三分之一的 met5，換來的餘量這次用不到。選定的是 Claude，依據是 what-if 的建議（2026-10-08）；使用者的決定是「Phase 5 內修好」。
4. **每次 harden 檢查最壞組合**：新增 `pnr/soc_top/ir_worst.py`，由 `pnr/soc_top/run.sh` 呼叫。
   - 用同一個 run 的 `OpenROAD.IRDropReport` step（同一份 ODB、SPEF、供電點）單步重跑一次。
   - 改三項：`DEFAULT_CORNER=max_ff_n40C_1v95`；`LAYERS_RC` 的 `*ff*` 換成 `*ss*` 的值；供電點電壓 1.95 V。
   - 判定：step log 確實讀了 ff_n40C_1v95 的 .lib、config 確實帶 ss 電阻，且 VDD 降壓 + GND 抬升 ≤ `[max_sum]` 的 20 mV。
   - harden-soc 要求 `ir-worst: PASS`。negative test P61（11 + 10 mV FAIL，9 + 9 mV PASS）、P62（`ir_worst.txt` 不在時 `review_criteria.py checkers_ran` FAIL）。
5. 不採用：只報告不判 FAIL、等 Phase 7；只列為已知限制（使用者 2026-10-08）。

## 確認 harden（commit `1dee974`）

| | Hazard3 | PicoRV32 |
|---|---|---|
| 最壞組合 IR（`ir_worst.py`） | 14.13 mV（原 25.75） | 5.72 mV（原 10.36） |
| nom_tt IR（flow 的 IR step） | 9.98 mV（原 18.28） | 4.06 mV（原 7.40） |
| 最差 setup | +1.114 ns | +0.789 ns |
| 最差 hold | +0.109 ns | +0.080 ns |

- Hazard3 的 14.13 mV 與 what-if 的 14.14 mV 相同。
- Magic DRC（完整 GDS）在 SRAM 框內 4,665,810 → 4,746,079 個框，每一個都在 SRAM 單獨檢查時同規則違規的位置（`check_soc.py magic_drc` PASS）；框外仍是 0。
- 兩個 golden 由這兩個 run 重建（`5aaf036`）。乾淨 checkout 的 Hazard3 regress（`5aaf036`）：`neg-pnr` 63/63。

## 影響與限制

- **供電位置仍是假設**：模型 C（每條 met5 strap 左端一點）要到 Phase 7 才知道 Caravel wrapper 實際怎麼接。只有一個接點（模型 D）時，20 mV 與 EM 都不會過。
- **最壞組合是人為的上限**：沒有一個真實 corner 同時有 ff 的電流與 ss 的金屬電阻。用它判 FAIL 是刻意保守。
- **EM 沒有 flow 檢查**：via4 的 78% → 18% 只在 what-if 與這份 ADR 記錄；flow 不讀 EM，也沒有 negative test。
- 其他限制同 Phase 4 研究：只做 static IR；switching activity 用 OpenSTA 預設值；SRAM 電流來自 .lib，SRAM 內部的 grid 沒有分析；macro 以外的壓降不在內。
- what-if 沿用原版圖的 signal 繞線；正式數字以重新 harden 的 run 為準（上表）。

## 出處

- `docs/phase_exit/phase5.md`「signoff 結果」「使用者決定」
- `docs/notes/ir_study/phase5/README.md`、`pdn_whatif_ir.txt`、`pdn_whatif_via4_em.txt`、`pdn_whatif_route_conflict.txt`、`worst_case_results_raw.txt`
- `docs/notes/ir_worst_case_soc_top.md`（Phase 4 研究與模型 C）
- `pnr/soc_top/config.json` 的 `//PDN_HWIDTH` 註解、`pnr/soc_top/ir_worst.py`
