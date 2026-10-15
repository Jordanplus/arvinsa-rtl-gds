# signoff criteria 檢查：Hazard3，PDN_HWIDTH 4.8（commit `1dee974`）

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3`，2026-10-08
  - log：主 repo 的 `runs/p5_pdn_harden_hazard3.log`
  - 費時 1686 s，沒有重試
- 目的：Phase 5 獨立審查後的修正，見 `docs/phase_exit/phase5.md` 使用者決定 1。
  - met5 strap 1.6 → 4.8 µm；
  - 新增最壞組合 IR 檢查與 `uncertainty_applied`。
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: FAIL`。只有 golden 比對 FAIL，因為 PDN 改了，舊 golden 不再適用；其他 limits 全部 PASS。新 golden 要從這次 run 重建。

## 有沒有被執行

腳本 6 項都 PASS：
- config 42 個設定都生效，比上次多 `PDN_HWIDTH`；
- 78 個 step config 一致；
- SDC 印出的那一行出現在 8 個時序 step 與 15 個 corner；
- `uncertainty_applied`：**新項目**，15 個 corner 共 50,670 條 signoff 路徑實際套用的 uncertainty 都對：同緣 setup 0.25、半週期 2.45、hold 0.25 ns；
- corner 齊全；
- 5 個 checker 都有結果行，含新的 `ir_worst.txt`。

| checker | 結果 | 說明 |
|---|---|---|
| `check_signoff.py` | FAIL（15 列，全是 golden） | 見下 |
| `ir_worst.py`（新） | PASS | ff 電流＋ss 金屬電阻：VDD 7.11＋GND 7.02＝**14.13 mV**，上限 20 mV。舊 PDN 是 25.75 mV<br>PDN what-if 預估 14.14 mV，實測幾乎相同 |
| `check_soc.py` | PASS | 見下 |
| `check_inputs.py --resolved`、`provenance.py` | PASS | — |

`check_soc.py` 的重點列：
- `ir_sources`：新的 vssd1 供電點落在加寬後 strap 的左端；
- `cts_macro_latency`：新的結構判斷，SRAM 上方單一扇出的 clock buffer 為 0 級；
- `magic_drc`：見 golden 差異的說明。

golden 比對有 14 個 metric 不同，另有 2 個 optional key 只出現在一邊：
- **IR**：nom_tt 從 18.28 降到 **9.98 mV**（5.02＋4.96）。這是 PDN 改動的目的。
- **Magic DRC 總數**：4,665,810 → 4,746,079。
  - `magic_drc` 列 PASS：SRAM 框外是 0；框內每一個違規都對得上 SRAM 單獨檢查時的位置（4,735,395 個框完全相同）。
  - 數字變多，推測是加寬的 met5 跨過 SRAM 的方式改變，Magic 對 SRAM 內部違規的分割或計數跟著變。這是推測，沒有逐規則比對。
- **其他版圖 metric**：standard cell 30,428 → 30,423、繞線長度 +0.05%、diode 92 → 88，都在誤差內，或只是 key 有差。

## 合不合理

| criterion | 依據 | 這次的實測 | 判斷 |
|---|---|---|---|
| IR 上限 20 mV 用 nom_tt 判 | Phase 4：最壞組合在 PicoRV32 版圖是 11.46 mV | Phase 5：舊 PDN 的最壞組合 25.75 mV，所以**改成每次都判最壞組合**（`ir_worst.py`）。這次 14.13 mV | 依據已修正：現在兩者都判 |
| via4 EM | Phase 4 研究，沒有 flow 檢查 | what-if 估 17.9%，用 3 個 cut；這次沒有重量 | 資料不足：EM 仍沒有 flow 檢查 |
| setup margin | 同上一輪 | signoff 最差 +1.114 ns（舊 PDN +1.116），半週期路徑 | 依據仍成立；met5 加寬對時序沒有可見影響 |
| hold margin | 同上一輪 | +0.109 ns（舊 +0.106），hold buffer 2721 顆，和之前相同 | 依據仍成立 |
| DCD 2.2 ns | 假設值 | 同上 | 資料不足（Phase 5 已知限制 1） |
| unannotated 上限 126 | Phase 5 推導 | 126 | 依據仍成立 |

## 學習

- PDN 的 what-if 方法（`docs/notes/ir_study/phase5/`）預測得很準：14.14 vs 14.13 mV。之後調 PDN 可以先用這個方法篩選，不必每個候選都完整 harden。
- met5 加寬到 4.8 µm，時序、cell 數、繞線幾乎不變（signal 繞線只有 102 段用到 met5）。
- 新的 knowledge 數字：sky130、這顆 0.77 mm² 的 core、一側供電，最壞組合對 nom_tt 的比值約 1.41（14.13／9.98），和 Phase 4 的 1.40 一致。寫入 knowledge 檔。
