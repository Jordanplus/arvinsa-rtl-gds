# picorv32_core golden：PicoRV32 單獨 harden 的 metrics

`make harden-core` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：325 個 metrics 的 key 必須完全一樣，多一個或少一個都算 FAIL。值必須相同，只有 `signoff/limits/picorv32_core.toml` 的 `[golden_tolerance]` 列出的族群可以有很小的誤差（原因見下一節）。另外還要通過同一個檔案裡的 signoff 門檻，這些門檻用的是這次 run 自己的值，不受誤差規則影響。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden-core`（tag `picorv32_core`）的 `runs/picorv32_core_signoff/metrics.json`，原檔複製，沒有修改 |
| 日期／平台 | 2026-10-03，Apple Silicon macOS（arm64） |
| LibreLane | 3.0.14（`f24e0ea5db2260719e9a0c7d51d07db74a87fa23`） |
| PDK | sky130A，ciel hash `8afc8346a57fe1ab7934ba5a6056ea8b43078e71`，`sky130_fd_sc_hd` |
| PicoRV32 | `third_party/picorv32` `ef203c2b0a3fb793280f5114941416c425c5b461` |
| flow 設定 | `pnr/picorv32_core/config.json`：產生本檔時的 sha256 `c60c3b4d2109876b4c37e1690e446fe72b21bbab5d8de427515a09b36c70829a`；之後只改了 `"//"` 說明文字，現行版 sha256 `d66099e1102e0209796bb457a0f602810c5993fe0c11f11c48f6f943cc64a610`，用它跑的第 4 次 run 與本檔 325 個 metrics 完全相同 |
| 本檔 sha256 | `29e89a6f7fc070a3a0452cf5b57840f41cd191a7180844b37a7e6b9dac75d464` |

以上版本都釘在 `env/versions.mk`。

## 可重現性（同一台機器重跑，結果是否每次一樣）

| run | 設定 | 與本檔比較 |
|---|---|---|
| 試跑 #9 | 比定案設定多一項 `CTS_MAX_CAP 0.15`（沒有作用：CTS 後的 DEF 逐 byte 相同） | 325 個 metrics 完全相同 |
| 正式 run 第 1 次 | 定案設定 | 本檔來源 |
| 正式 run 第 2 次（`make phase2`） | 定案設定 | 254 個相同，71 個有極小差異（見下）。當時規則是全部逐項相同，所以這次 `make phase2` 在 harden-core 的 golden 比對 FAIL，後面的步驟沒有執行；加入誤差規則後重新判定為 PASS |
| 正式 run 第 3 次（`make harden-core`） | 定案設定 | 325 個 metrics 完全相同 |
| 正式 run 第 4 次（最後一次 `make phase2`） | 定案設定（說明文字更新後） | 325 個 metrics 完全相同 |

**detailed routing 不是每次都一樣。** 上表 5 次 run（試跑 #9 多一項沒有作用的設定，其餘設定完全相同）中，只有第 2 次不同。第 2 次與第 3 次（`resolved.json` 完全相同）逐步比對中間產出的 DEF：從 floorplan 到 global routing、post-GRT repair（第 13–41 步）全部逐 byte 相同，第一個不同的是 `OpenROAD.DetailedRouting`（第 45 步，多執行緒）。第 2 次與試跑 #9 比對的結果也一樣。之後算出來的 metrics 因此有極小差異（第 1 次 vs 第 2 次）：

| 族群 | 第 1 次 vs 第 2 次 | 允許的誤差 |
|---|---|---|
| setup／hold slack（含 reg-to-reg） | ≤ 0.0003 ns | ±0.01 ns |
| clock skew | ≤ 0.0002 ns | ±0.01 ns |
| 線長（最終與各 iteration） | 708673 vs 708679 µm | ±0.1% |
| via 數 | 134168 vs 134172 | ±0.1% |
| 功耗、IR drop | 相對差 ≤ 0.004% | ±0.1% |

允許的誤差約是實測差異的 30–200 倍。設定、工具或 PDK 的變更，幾乎都會連帶改變 cell 數、面積這類必須完全相同的 metrics，所以仍然會被抓到。其他所有 metrics，包括 cell 數、面積、hold buffer 數、各種違規數、DRC、LVS，以及 detailed routing 各 iteration 的 DRC 數，都必須完全相同。這個比對規則做過 negative test：13 種超出誤差、不在允許族群內、key 缺少或誤差設定寫錯的情況全部 FAIL，誤差範圍內的正向對照 PASS（`docs/phase_exit/phase2.md`）。

改成單執行緒 detailed routing 或許能消除差異，但這一步用多執行緒就要 7–8.5 分鐘，單執行緒會慢好幾倍（推測，沒有實測），regression 會太慢，所以沒有採用。

## 重點數值

| 項目 | 值 |
|---|---|
| die／core | 533.575 × 544.295 µm／272662 µm² |
| standard cell | 21748 顆，196970 µm²（含 tap cell，不含 fill cell），使用率 72.2%；flip-flop 2382 顆 |
| setup worst slack | 6.175 ns（`max_ss_100C_1v60`）；nom_tt 14.910 ns |
| hold worst slack | 0.039 ns（`min_ff_n40C_1v95`） |
| DRC／LVS／antenna／XOR | 全部 0 |
| max slew／cap／fanout 違規 | 0／0／0（9 個 corner） |
| 總線長 | 708673 µm |

## 何時更新

升級 LibreLane、PDK、PicoRV32，或修改 `config.json` 之後，golden 比對一定會 FAIL。更新步驟：

1. 確認 limits 的每一列都 PASS（`runs/picorv32_core_signoff/signoff.txt` 裡除了 golden 以外沒有 FAIL）。
2. 逐項檢視與舊 golden 的差異，確認每一項差異都有合理原因。
3. 把 `runs/picorv32_core_signoff/metrics.json` 複製成本檔，在上表更新出處與 sha256，並在 commit message 寫明原因。
4. 再跑一次 `make harden-core`，確認新 golden PASS。
