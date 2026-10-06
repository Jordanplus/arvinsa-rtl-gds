# soc_top_hazard3 golden：Hazard3 版 soc_top 的 metrics

`make harden-soc CPU=hazard3` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/soc_top_hazard3.toml` 的 `[golden_tolerance]` 列出的族群可以有誤差（與 `signoff/golden/soc_top/README.md` 相同的規則：detailed routing 不是每次都一樣）。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden-soc CPU=hazard3`（tag `soc_top_hazard3`）的 `runs/soc_top_hazard3_signoff/metrics.json`，原檔複製，沒有修改 |
| 日期／平台 | 2026-10-07（Phase 5），Apple Silicon macOS（arm64） |
| 來源 run | Phase 5 Hazard3 第 5 次 harden-soc，commit `3a28d54`（worktree `../arvinsa-rtl-gds-p5h3`）。`check_signoff.py` 當時有 2 列 FAIL：沒有 golden（預期），以及 `timing__unannotated_net__count` 125 ≠ 133（上限是從 PicoRV32 複製的，已改成依 Hazard3 推導的 125，見上限檔註解）。改完上限後只剩沒有 golden。`check_soc.py`、`sram_drc_alone`、`check_inputs.py --resolved`、`provenance.py`、`review_criteria.py` 全部 PASS |
| signoff criteria 檢查 | `runs/soc_top_hazard3_signoff/criteria_review.md`（p5h3 worktree） |
| LibreLane／PDK／Hazard3／SRAM macro | 同 `env/versions.mk` |
| flow 設定 | `pnr/soc_top/config_hazard3.json` sha256 `b51e75b55cea6433f5834bc0aeac37c10bdd55cb9e90c149683515004e0a5b3c` |
| 本檔 sha256 | `7ed3f5114ab0a11e4b1470fb41d7501cb3123a7c1b282fabe02594363175c40e` |

## 與 PicoRV32 版 golden（`signoff/golden/soc_top/`）的差異

兩者是不同的設計，不做逐項比對；以下是檢視過的主要差異（2026-10-07）。PicoRV32 版的 golden 是 43 ns、沒有 `RUN_POST_GRT_RESIZER_TIMING` 的舊設定，之後會重跑。

- metrics 440 個（PicoRV32 版 439 個）：多了 `flow__warnings__count:RSZ-0062`（繞線後的 setup 修復剩 1 個違規，signoff 已 PASS）與 `RSZ-0064`（CTS 後的 hold 修復沒有全部修到餘量內，signoff 最差 hold +0.107 ns）；少了 `GRT-0243`。
- 設定：週期 44 ns（PicoRV32 golden 43 ns），開 `RUN_POST_GRT_RESIZER_TIMING`（ADR-0014），resizer 看得到 ss_n40C（ADR-0013）。
- timing：最差 setup +0.530 ns（min_ss_n40C，SRAM 下降緣送出的半週期路徑；PicoRV32 golden 同一類路徑 +0.384）；最差 hold +0.107 ns（min_ff_n40C）。
- cell：standard cell 30,474（29,373），面積 239,577 µm²（237,877）；timing repair buffer 11,088（9,545）、clock buffer 458（531）。
- **`design__instance__count__hold_buffer` 是 0，不是 hold buffer 數**：這個 metric 是最後一個 resizer 步驟自己報的數字，這次最後一步是 `ResizerTimingPostGRT`，沒有插 hold buffer。網表裡的 hold buffer（`hold*`）是 2,739 顆。另外，`ResizerTimingPostCTS` 的 log 寫「Inserted 1 hold buffers」，但那一步面積 +5.7%，hold buffer 約 2,700 顆都是那一步插的；PicoRV32 版同一行寫 3479，與網表一致。為什麼這次的計數不對，沒有查證。要看 hold buffer 數，用 `review_criteria.py` 的 INFO 列（數網表）。
- 繞線：線長 798,897 µm（895,243），via 157,447（162,780），net 23,753（22,679）。
- 功耗 19.43 mW（9.24 mW），IR `ir__drop__worst` 9.22 mV（3.95 mV）：都在上限內。功耗約為兩倍的原因沒有查證。
- `timing__unannotated_net__count` 125（133）：組成見上限檔。
- 相同的：Magic DRC 4,665,810（全部在 SRAM 框內、位置與 SRAM 單獨檢查相同）、KLayout DRC 0、LVS 0、XOR 0、繞線 DRC 0、slew／cap／fanout 違規 0。

## 可重現性

| run | 與本檔比較 |
|---|---|
| Phase 5 Hazard3 第 5 次 harden-soc（commit `3a28d54`） | 本檔來源 |

實驗 A（從第 4 次 run 的第 43 步之後接續，只跑到 signoff STA）與本次的 signoff STA 數字完全相同；完整 harden 的重跑比較待補（規則：至少重跑一次）。

## 何時更新

與 `signoff/golden/soc_top/README.md` 相同：升級工具或 PDK、修改 Hazard3 RTL、`config_hazard3.json`、SDC、SRAM 產生檔之後，golden 比對一定會 FAIL。更新步驟：確認 limits 與 `check_soc.py`、`review_criteria.py` 全部 PASS，逐項檢視差異，複製 metrics 並更新本表與 sha256，再跑一次確認 PASS。
