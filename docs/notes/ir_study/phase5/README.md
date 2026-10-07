# Phase 5 的 IR 量測（2026-10-08）

由兩個 agent 在 session 的暫存目錄執行。這裡只保存結果與可以重現量測的腳本；呼叫用的 shell 腳本含本機路徑，沒有放進來。結論寫在 `docs/phase_exit/phase5.md`「signoff 結果」一節。

## 一、最壞組合的實測

方法同 Phase 4 研究（`../README.md`）：
- 對兩次乾淨 regress 的版圖（commit `7348fab`），單步重跑 LibreLane 的 `OpenROAD.IRDropReport`。
- 供電模型是模型 C：每條 met5 strap 左端一點，每個 net 5 點。
- 最壞組合 = ff 電流 + ss 金屬電阻：`DEFAULT_CORNER=max_ff_n40C_1v95`，`LAYERS_RC["*ff*"]` 換成 `*ss*` 的值，供電點 1.95 V。

nom_tt 的結果和 flow 的 IR 步驟完全相同（Hazard3 9.18／9.09 mV），所以這個量測可以採信。

| 檔案 | 內容 |
|---|---|
| `worst_case_results_raw.txt` | 每次 run 一行：corner、功耗、最差與平均壓降、供電點數、每平方電阻 |
| `worst_case_per_instance.txt` | 每顆 cell 的 VDD 降壓 + GND 抬升，最差的那一顆 |
| `worst_case_em.txt` | 各層 EM（via 以單一 cut 計） |

Hazard3：nom_tt 18.28 mV，最壞組合 25.75 mV（超過 20 mV），via4 EM 78%。
PicoRV32：nom_tt 7.40 mV，最壞組合 10.36 mV。

現在 flow 每次 harden 都會跑這個檢查：`pnr/soc_top/ir_worst.py`。

## 二、PDN 的 what-if

**做法**：
- 取 Hazard3 版圖在 IR 步驟的輸入 ODB。
- 刪掉 vccd1／vssd1 的 special wiring 與電源 pin 的形狀，再用 LibreLane 的 `pdn_cfg.tcl` 和 `pdngen` 依候選設定重新產生（`regen_pdn.tcl`、`run_pdn.py`）。
- 依新的 strap 位置重產供電點檔，再跑同樣的 IR。

**方法驗證**：用現行設定重新產生，DEF 的 SPECIALNETS 與原版圖逐行相同，IR 也完全一樣（18.276／25.745 mV）。

| 檔案 | 內容 |
|---|---|
| `pdn_whatif_ir.txt` | 每個候選的 nom_tt 與最壞組合 IR |
| `pdn_whatif_via4_em.txt` | via4 EM（依 DEF 的 via 名稱數 cut 數） |
| `pdn_whatif_route_conflict.txt` | 原版圖的 signal 線段離新 strap 不到最小間距的數量 |

**結果與採用**：
- 採用 `PDN_HWIDTH 4.8`（met5 strap 1.6 → 4.8 µm，pitch 不變）：最壞組合 14.14 mV，via4 EM 17.9%，新增衝突 0。
- 加密 met5 在用掉同樣金屬量時，效果比加寬差；只改 met4 最多降到 22.65 mV。

**限制**：
- signal 繞線與 placement 沿用原版圖，沒有包含重跑後的差異；正式數字以重新 harden 的 run 為準。
- 最壞組合是人為組合的上限，不是真實存在的 corner。
