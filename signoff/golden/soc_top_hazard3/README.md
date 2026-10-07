# soc_top_hazard3 golden：Hazard3 版 soc_top 的 metrics

`make harden-soc CPU=hazard3` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/soc_top_hazard3.toml` 的 `[golden_tolerance]`（連續量）與 `[golden_layout_tolerance]`（會隨繞線變的數量與面積）列出的族群可以有誤差，`[golden_optional]` 列出的 key 可以只出現在一邊；違規數一律相同。誤差約為實測最大差異的 5 倍，依據見下方「可重現性」與 ADR-0015。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden-soc CPU=hazard3`（tag `soc_top_hazard3`）的 `runs/soc_top_hazard3_signoff/metrics.json`（之後改名為 `runs/p5_h3_h10_signoff/`），原檔複製，沒有修改 |
| 日期／平台 | 2026-10-07（Phase 5），Apple Silicon macOS（arm64） |
| 來源 run | Phase 5 Hazard3 第 10 次 harden-soc（ADR-0016 正式 harden），commit `2caad0e`（worktree `../arvinsa-rtl-gds-p5h3`；log `runs/p5_h3_harden10.log`）。`check_signoff.py` 當時有兩類 FAIL：與舊 golden 比對（預期），以及 `timing__unannotated_net__count` 126 ≠ 125（上限依新的 clock tree 改成 126，見上限檔註解）。改完上限後只剩 golden；`check_soc.py`（含 `cts_macro_latency`）、`sram_drc_alone`、`check_inputs.py --resolved`、`provenance.py`、`review_criteria.py` 全部 PASS |
| signoff criteria 檢查 | `runs/p5_h3_h10_signoff/criteria_review.md`（p5h3 worktree） |
| LibreLane／PDK／Hazard3／SRAM macro | 同 `env/versions.mk` |
| flow 設定 | `pnr/soc_top/config_hazard3.json` sha256 `ee7fa839d6cf8aec6083d411d080338db006eedb70bd918b50ede36ce861e747`（含 `meta.substituting_steps`；CTS step 在 `pnr/librelane_plugin_arvinsa/`） |
| 本檔 sha256 | `e7fbdb2b720c937394fc8e80f2ee481277039bf969fd95a20111d0312dd2b62c` |

## 與第 5 次 harden 的 golden 的差異（逐項檢視過，2026-10-07）

- 唯一的設定變更是 ADR-0016（CTS 不做 SRAM 的 latency 對齊）。
- metrics 從 440 個變成 434 個：少了 `route__drc_errors__iter:5`–`:7`、`route__wirelength__iter:5`–`:7`（detailed routing 這次 4 輪就收斂，最終 DRC 0）與 `flow__warnings__count:RSZ-0062`（`ResizerTimingPostGRT` 這次全部修完）；多了 `flow__warnings__count:GRT-0243`。共有的 434 個中 264 個相同、169 個改變。
- timing：最差 setup +0.530 → +1.116 ns（仍是 min_ss_n40C 的 SRAM 半週期路徑，`sram0` → `_21031_`）；nom_ss_100C +1.136 → +1.443；最差 hold +0.107 → +0.106 ns。
- clock：`sram0/clk0` 前的 9 顆 `delaybuf_*` 沒有了；clock buffer 458 → 445；skew metric（setup）0.527 → 0.459 ns。
- cell：standard cell 30,474 → 30,428，面積 239,577 → 239,062 µm²；網表的 hold buffer 2,739 → 2,721，32 條 `sram_dout0` 上沒有 hold delay cell；antenna diode 100 → 92。
- 功耗 19.43 → 19.34 mW；IR 9.22 → 9.18 mV；線長 798,897 → 795,843 µm。
- `timing__unannotated_net__count` 125 → 126：CTS dummy load 81 → 82。
- 沒變的：Magic DRC 4,665,810、KLayout DRC 0、LVS 0、XOR 0、SRAM 位置。

## 與 PicoRV32 版 golden（`signoff/golden/soc_top/`）的差異（第 5 次 harden 的 golden 建立時檢視，數字是當時的）

兩者是不同的設計，不做逐項比對；以下是檢視過的主要差異（2026-10-07）。PicoRV32 版的 golden 是 43 ns、沒有 `RUN_POST_GRT_RESIZER_TIMING` 的舊設定，之後會重跑。

- metrics 440 個（PicoRV32 版 439 個）：多了 `flow__warnings__count:RSZ-0062`（繞線後的 setup 修復剩 1 個違規，signoff 已 PASS）與 `RSZ-0064`（CTS 後的 hold 修復沒有全部修到餘量內，signoff 最差 hold +0.107 ns）；少了 `GRT-0243`。
- 設定：週期 44 ns（PicoRV32 golden 43 ns），開 `RUN_POST_GRT_RESIZER_TIMING`（ADR-0014），resizer 看得到 ss_n40C（ADR-0013）。
- timing：最差 setup +0.530 ns（min_ss_n40C，SRAM 下降緣送出的半週期路徑；PicoRV32 golden 同一類路徑 +0.384）；最差 hold +0.107 ns（min_ff_n40C）。
- cell：standard cell 30,474（29,373），面積 239,577 µm²（237,877）；timing repair buffer 11,088（9,545）、clock buffer 458（531）。
- **`design__instance__count__hold_buffer` 是 0，不是 hold buffer 數**：這個 metric 是最後一個 resizer 步驟自己報的數字，這次最後一步是 `ResizerTimingPostGRT`，沒有插 hold buffer。網表裡的 hold buffer（`hold*`）是 2,739 顆。另外，`ResizerTimingPostCTS` 的 log 寫「Inserted 1 hold buffers」，但那一步面積 +5.7%，hold buffer 約 2,700 顆都是那一步插的：`RSZ-0032` 的數字不是總數，hold 修復進度表的 Buffers 欄中途會掉回來（`drv-timing-closure` 規則 7、`librelane-run-debug` 已知陷阱；PicoRV32 版同一行剛好與網表一致）。要看 hold buffer 數，用 `review_criteria.py` 的 INFO 列（數網表）。
- 繞線：線長 798,897 µm（895,243），via 157,447（162,780），net 23,753（22,679）。
- 功耗 19.43 mW（9.24 mW），IR `ir__drop__worst` 9.22 mV（3.95 mV）：都在上限內。功耗約為兩倍的原因沒有查證。
- `timing__unannotated_net__count` 125（133）：組成見上限檔。
- 相同的：Magic DRC 4,665,810（全部在 SRAM 框內、位置與 SRAM 單獨檢查相同）、KLayout DRC 0、LVS 0、XOR 0、繞線 DRC 0、slew／cap／fanout 違規 0。

## 可重現性

| run | 與本檔比較 |
|---|---|
| Phase 5 Hazard3 第 10 次 harden-soc（commit `2caad0e`，ADR-0016） | 本檔來源 |
| Phase 5 Hazard3 第 11 次 harden-soc（commit `1d13775`） | 434 個完全相同 → harden-soc PASS |
| 下列為第 5 次 harden 的 golden（見 git 歷史，commit `2caad0e` 以前的本檔）的紀錄；ADR-0015 的誤差就是從它們量的 | |
| Phase 5 Hazard3 第 5 次 harden-soc（commit `3a28d54`） | 舊 golden 的來源 |
| Phase 5 Hazard3 第 6 次 harden-soc（commit `d6f3074`，flow 設定相同） | 293 個相同、86 個在誤差內、61 個不同（含數量、面積與 `iter:7` 的 key）→ harden-soc FAIL；signoff 全部 PASS。ADR-0015 的誤差下：PASS |
| Phase 5 Hazard3 第 7 次 harden-soc（commit `4d309de`） | 335 個相同、94 個在誤差內、11 個不同（diode、cell 數、面積）→ harden-soc FAIL；signoff 全部 PASS。ADR-0015 的誤差下：PASS |
| Phase 5 Hazard3 第 8 次 harden-soc（commit `9ef0be7`，ADR-0015 的誤差） | 440 個完全相同（第 41 步與 detailed routing 都與本檔來源相同）→ harden-soc PASS |

實驗 A（從第 4 次 run 的第 43 步之後接續，只跑到 signoff STA）與本次的 signoff STA 數字完全相同。

第 6 次的差異從第 41 步（`RepairDesignPostGRT`）最後一次 global routing 開始：修完的 DEF 相同，global routing 的線長與 routing guide 不同（1,146,538 對本檔來源的 1,146,421 µm），之後的 antenna 修補、`ResizerTimingPostGRT`、detailed routing 跟著改變。用第 6 次自己的輸入單步重跑這一步 4 次，4 次都和本檔來源相同；第 4、5 次 harden 也相同。之後再用同一份輸入單步重跑 20 次：16 次與 golden 相同，其餘 4 次分成 3 種結果（其中 2 次與第 6 次相同）。合計 27 次裡 22 次相同（約 81%），沒有一次出現 GRT-0229。PicoRV32 版 golden 的前提「不可重現的只有 detailed routing」對 Hazard3 版不成立。

第 7 次 harden（commit `4d309de`）的第 41 步與本檔來源相同，但 detailed routing 內的 antenna 修補多跑一輪、多插 1 顆 diode：11 個 metric 不同（diode、cell 數、面積）。

使用者決定改 golden 規則（ADR-0015）：用本檔來源對第 6、7 次 harden 與兩組「第 41 步不同、接著跑完」的 run 量出每個族群的最大差異，誤差訂為約 5 倍。改完後這 4 組 run 都 PASS（依據就是它們，所以不算驗證）；驗證要看之後的 harden。

## 何時更新

與 `signoff/golden/soc_top/README.md` 相同：升級工具或 PDK、修改 Hazard3 RTL、`config_hazard3.json`、SDC、SRAM 產生檔之後，golden 比對一定會 FAIL。更新步驟：確認 limits 與 `check_soc.py`、`review_criteria.py` 全部 PASS，逐項檢視差異，複製 metrics 並更新本表與 sha256，再跑一次確認 PASS。
