# criteria review：user_project_wrapper（Phase 7 步驟 7，decap 改 `ef_decap_12`，2026-10-14）

run：`runs/user_project_wrapper`，commit `7eff65a`（ADR-0019 決定 24：`DECAP_CELLS` 改 `sky130_ef_sc_hd__decap_12`、`FILL_CELLS` 加 `fill_8`／`fill_4`；RTL、SDC、其他設定與確認 harden `f4ea9de` 相同），log `runs/p7_harden_decap.log`，約 182 分鐘（08:3x–11:35；上次 240 分鐘）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：config_applied 57 個設定（上次 55，多了 `DECAP_CELLS`、`FILL_CELLS`）、step_config 78 個步驟、uncertainty、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran。`criteria-review: PASS`。

`harden-soc: FAIL`，FAIL 只有 golden 比對 6 列（`signoff: FAIL (6 rows)`）；signoff 上限列全部 PASS。

- `check_signoff.py` golden：455 個 metrics 中 440 個逐值相同、10 個在誤差內、5 個不同。全部差異（與 golden 逐 key 比）：
  - `design__instance__count` 2,774,042 → 1,140,379、`design__instance__count__class:fill_cell` 2,608,464 → 974,801：Fill Insertion 放了 543,617 個 `ef_decap_12`、fill_1／2／4／8 共 428,280 個（原本 2,458,784 個 `decap_3` 與 fill_1／2）；row 兩端的 endcap 2,904 個 `decap_3` 不變。fill 類的面積 `design__instance__area__class:fill_cell` 9,431,600 相同（同一塊空白）。
  - `power__leakage__total` 0.7506 → 0.7396 mW（`power__total` 隨之 −0.011 mW）：`ef_decap_12` 沒有 .lib，STA 把它的漏電算 0；少掉的 `decap_3` 在 ff_100C 的 .lib 漏電 4.379 pW × 2,458,784 = 0.01077 mW，佔差額 0.01101 mW 的 98%（功耗寫入的 corner 是 max_ff_100C，golden README）。剩下 0.24 µW 沒有拆。
  - `ir__drop__avg` 0.180 → 0.187 mV、`design_powergrid__drop__average__net:vssd1` 0.1869 → 0.1946 mV：平均值隨 instance 節點組成改變；最差壓降 2.05633 → 2.05617 mV（在誤差內），`ir_worst.py` 的 max_ss_100C 4.94 mV 與上次相同。
- `check_soc.py` 13 項全部 PASS；Magic DRC 5,572,955 個，與上次相同，全部在 SRAM 框內。KLayout DRC 0、LVS 0、XOR 0、antenna 0（metrics 與 golden 相同）。
- `ir_worst.py` PASS（max_ss_100C 4.94 mV）；`provenance.py --verify` PASS（開始與結束都是 `7eff65a`，工作樹乾淨）。

「不分析的項目清單」：新增一項——`ef_decap_12` 的漏電（沒有 .lib，見「合不合理」）。

## 合不合理

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold、slew、DRC、LVS、antenna、disconnected、unannotated | 與 `f4ea9de` 逐值相同（setup +0.548 ns、hold +0.187 ns；Fill Insertion 在 detailed routing 之後，不改繞線） | 依據仍成立 |
| 靜態 IR（wrapper 內） | 最差 4.94 mV，與上次相同 | 依據仍成立；靜態 IR 看不到 decap 的種類（ADR-0019 決定 24 不選 B 的理由） |
| power signoff（功耗數字） | 報告的 leakage 少了 0.011 mW（總功耗的 0.06%），是 `ef_decap_12` 沒有 .lib 造成的低估，不是真的變少 | 依據需補充：功耗報告不含沒有 .lib 的 cell；量級在 pW／個，對 18.2 mW 的總功耗與 IR 沒有實質影響，但要記在不分析的項目清單 |
| precheck 的 li1 密度（`li1.pd.1d`，上限 60%） | 本機 KLayout flat 計算 39.9%（舊版圖 75.1%，與 precheck 報的一致） | 預期 PASS；正式判定是 `make precheck-caravel` |
| golden 容許誤差 | 差異全部來自 decap 設定的改變，各自有對應的原因 | 照 golden README「何時更新」：config.json 改了，更新 golden |

## 學習

- decap 種類換掉只影響 fill 類 instance 數、leakage 報告與 IR 平均值；timing、DRC、LVS、最差 IR 逐值相同，因為 Fill Insertion 在 detailed routing 之後，靜態 IR 的電流來自有 .lib 的 cell。
- instance 少了 163 萬個，harden 從 240 分鐘降到約 182 分鐘。
- knowledge 檔追加：S29（decap／fill 的 li1 比例、`ef_decap_12` 沒有 .lib 的影響），以及校準表 2026-10-14 一列。
