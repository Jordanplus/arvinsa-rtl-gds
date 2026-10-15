# signoff criteria 檢查：PicoRV32 SoC，PDN_HWIDTH 4.8（commit `1dee974`）

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top`，2026-10-08
  - log：主 repo 的 `runs/p5_pdn_harden_picorv32.log`
  - 費時 1479 s，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: FAIL`，只有 golden 比對 FAIL。PDN 改了，而且 PicoRV32 的版圖誤差依使用者決定已清空，所以任何版圖差異都會列出來；其他 limits 全部 PASS。新 golden 從這次 run 重建。

## 有沒有被執行

腳本 6 項都 PASS：
- config 41 個設定都生效；
- 78 個 step config 一致；
- SDC 那一行出現在 8 個時序 step 與 15 個 corner；
- `uncertainty_applied`：15 個 corner 共 30,000 條路徑都對；
- corner 齊全；
- 5 個 checker 都有結果行。

| checker | 結果 | 說明 |
|---|---|---|
| `check_signoff.py` | FAIL（90 列，全是 golden） | 見下 |
| `ir_worst.py` | PASS | 2.86＋2.85＝5.72 mV（舊 PDN 10.36 mV） |
| `check_soc.py` | PASS | `ir_sources`、`cts_macro_latency`（0 級）都 PASS<br>`magic_drc`：框外 0，框內 4,746,079 個全部對得上 SRAM 單獨檢查時的位置；和 Hazard3 版同樣多出約 8 萬個 |
| `check_inputs.py --resolved`、`provenance.py` | PASS | — |

golden 比對有 89 個 metric 不同，另有 3 個 optional key 只出現在一邊：
- **IR**：nom_tt 7.40 → 4.06 mV。
- **時序**：setup 最差 +0.765 → +0.789 ns；ss_n40C 的 hold 少了 0.02–0.03 ns；clock skew 差 0.01–0.04 ns。
- **版圖**：standard cell +6、diode 83 → 100、via +0.2%。

這些都是 PDN 改變後 placement 與繞線跟著改變造成的：strap 變寬，standard cell 能放的位置和繞線資源都變了。新 golden 從這次 run 建立。

## 合不合理

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| 最壞組合 IR（新） | 5.72 mV，上限 20 mV | 依據成立 |
| setup margin | +0.789 ns（min_ss_n40C，半週期路徑）；兩次 resizer 修復都沒有 setup 違例可修 | 依據仍成立 |
| hold margin | 最後一次修復（`ResizerTimingPostGRT`）結束在 +0.082 ns，signoff +0.080 ns；hold buffer 3562 顆 | 依據仍成立 |
| DCD 2.2 ns | 半週期路徑仍是最差路徑 | 資料不足（已知限制 1） |
| 版圖誤差（PicoRV32 不給） | 這次是設計改變，不是重現差異，量不出 run 之間的差異 | 等乾淨 regress 的重現結果再看 |

## 學習

- PDN 加寬對 PicoRV32 的 placement 影響比 Hazard3 大：PicoRV32 有 89 項不同，Hazard3 只有 14 項。原因沒有查證。
- 沒有新的製程數字；IR 比值已在 Hazard3 那份寫進 knowledge 檔。
