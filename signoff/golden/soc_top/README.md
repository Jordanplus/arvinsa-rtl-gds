# soc_top golden：整合 SRAM 的 soc_top 的 metrics

`make harden-soc` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/soc_top.toml` 的 `[golden_tolerance]` 列出的族群（detailed routing 不是每次都一樣，見 `signoff/golden/picorv32_core/README.md`）可以有誤差：slack、skew、線長、via、功耗、IR drop 很小的誤差，繞線器中間各輪的 DRC 數 ±100（見下方可重現性）。ADR-0015 另外加了 `[golden_layout_tolerance]`（會隨繞線變的數量與面積）與 `[golden_optional]`（只出現在一邊的每輪與 warning key），目前暫用 Hazard3 的實測值；本 golden 已是新設定（ADR-0013／0014／0016），誤差要等之後的 PicoRV32 run 量出 run 之間的差異再更新。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden-soc`（tag `soc_top`）的 `runs/soc_top_signoff/metrics.json`，原檔複製，沒有修改 |
| 日期／平台 | 2026-10-07（Phase 5），Apple Silicon macOS（arm64） |
| 來源 run | Phase 5 PicoRV32 的 ADR-0016 正式 harden，commit `2caad0e`（p5h3 worktree；log `runs/p5_pico_harden3.log`）。`check_signoff.py` 當時有兩類 FAIL：與舊 golden 比對（預期），以及 `timing__unannotated_net__count` 118 ≠ 133（上限依新的 clock tree 改成 118，組成見上限檔）。改完上限後只剩 golden；`check_soc.py`（含 `cts_macro_latency`）、`sram_drc_alone`、`check_inputs.py --resolved`、`provenance.py`、`review_criteria.py` 全部 PASS |
| signoff criteria 檢查 | p5h3 worktree `runs/p5_pico_h3_signoff/criteria_review.md`（跑的時候 tag 是 `soc_top`，之後改名為 `p5_pico_h3`） |
| LibreLane／PDK／PicoRV32／SRAM macro | 同 `env/versions.mk` |
| flow 設定 | `pnr/soc_top/config.json` sha256 `df16dc8d1f4fc5d3c414b613c4ca97b86ee6e0cfa96f7a35a44d85a50d9a48b8`（含 `meta.substituting_steps`；CTS step 在 `pnr/librelane_plugin_arvinsa/`） |
| 本檔 sha256 | `c4cad54c295e2c9e47fdcc9a5645846d68cd77f4aa89e1346c46d81249446e8e` |

## 與 Phase 3.5 golden 的差異（逐項檢視過，2026-10-07）

- metrics 從 439 個變成 436 個：少了 `route__drc_errors__iter:7`、`route__wirelength__iter:7`（detailed routing 少跑一輪，最終 DRC 仍是 0）與 `flow__warnings__count:GRT-0243`；沒有新 key。共有的 436 個中 261 個相同、175 個改變。
- 原因是 Phase 5 的四項變更，沒有逐項分開實驗：週期 43 → 44 ns（ADR-0004 Phase 5 補充）、resizer 看 ss_n40C 且 setup 餘量 0.6 → 0.1 ns（ADR-0013）、繞線後再修一次 timing（ADR-0014）、CTS 不做 SRAM 的 latency 對齊（ADR-0016）。
- timing：最差 setup +0.384 → +0.765 ns（仍是 min_ss_n40C 的 SRAM 半週期路徑）；最差 hold +0.074 → +0.079 ns。只有 ADR-0013／0014、還沒有 ADR-0016 的 run（commit `c976976`）是 −0.113 ns（`docs/decisions/0016-cts-no-macro-latency-balancing.md`）。
- clock：`sram0/clk0` 前的 10 顆 `delaybuf_*` 沒有了；clock buffer 531 → 508、clock inverter 62 → 49；skew metric（setup）0.680 → 0.450 ns。
- cell：standard cell 29,373 → 31,960（+2,587），面積 237,877 → 254,319 µm²，utilization 0.679 → 0.701；timing repair buffer 9,545 → 12,129（推測是 resizer 看到 ss_n40C 後多修的，沒有分開實驗）；網表的 hold buffer（`hold*`）3,563 顆，32 條 `sram_dout0` 上沒有 hold delay cell。`design__instance__count__hold_buffer` 3,479 → 8：這個 metric 是最後一個 resizer 步驟自己的數字，現在最後一步是 `ResizerTimingPostGRT`（只插了 8 顆），不是 hold buffer 總數（`drv-timing-closure` 規則 7）。antenna diode 48 → 83。
- 功耗 9.24 → 8.73 mW；IR `ir__drop__worst` 3.95 → 3.72 mV。
- 繞線：線長 895,243 → 863,010 µm，net 22,679 → 25,254，via 162,780 → 170,172。
- `timing__unannotated_net__count` 133 → 118：CTS dummy load 90 → 75，其他組成不變。
- 沒變的：Magic DRC 4,665,810（全部在 SRAM 框內）、KLayout DRC 0、LVS 0、XOR 0、SRAM 位置。

## 與 Phase 4 golden 的差異（逐項檢視過，2026-10-05）

- metrics 從 434 個變成 439 個：多了 `route__drc_errors__iter:6`、`:7`、`route__wirelength__iter:6`、`:7`（detailed routing 多跑兩輪，最終 DRC 仍是 0）與 `flow__warnings__count:GRT-0243`（見下）；沒有 metric 消失。
- 共有的 434 個中 148 個值改變：96 個超出誤差、52 個在誤差內（`check_signoff.py` 報的 101 個不同 = 這 96 個 + 5 個新 key）。原因都是 Phase 3.5 的兩項變更：
  - SRAM .lib 改用 SPICE 特性化、每個 PVT 一份（ADR-0010），多了 dout0 的 `rising_edge` hold 弧，SRAM 的 instance derate 拿掉。
  - 週期 42 → 43 ns（使用者決定，ADR-0004 Phase 3.5 補充）。
- timing：最差 setup 0.313 → 0.384 ns（仍在 min_ss_n40C、SRAM 半週期路徑）；ss 100°C 0.788 → 0.921 ns；tt／ff 約 +0.3 ns（週期）。最差 hold 0.082 → 0.074 ns；ss −40°C 的 hold 0.93 → 0.07–0.29 ns：那個 corner 的 SRAM .lib 是佔位，hold 弧取所有 PVT 最早的值（ff 的 0.64 ns）。
- cell：standard cell 29,352 → 29,373（+21），面積 237,644 → 237,877 µm²；hold buffer 3452 → 3479（淨 +27。32 個 `rdata_q` 的 D 前各有一顆 `dlygate4sd3`，是為了新的 hold 弧插的；淨增比 32 少，表示別處少了幾顆或 Phase 4 已有一部分，Phase 4 的網表已不在，無法確認）；antenna cell 85 → 86、diode 51 → 48；clock buffer／inverter 不變（531／62）。
- 功耗 9.451 → 9.241 mW（−2.2%，約 42/43）；IR `ir__drop__worst` 4.04 → 3.95 mV。
- 繞線：線長 894,480 → 895,243 µm，最長線 619.53 → 616.77 µm，net 22,659 → 22,679。
- `GRT-0243`（antenna 修補時有一條 net 用 diode 修不掉）是新的警告：修補前 146 個 antenna 違規，jumper 後剩 19 個，插 diode 後的 `CheckAntennas` 與繞線後的檢查都是 0 個違規；signoff 的 3 個 antenna 指標都是 0。
- `STA-1140`（同一份 .lib 讀兩次）14 → 12：推測是因為 SRAM 不再是 9 個 corner 共用一份 padded.lib（數字已核對，原因沒有驗證）。
- 沒變的：Magic DRC 4,665,810（全部在 SRAM 框內、位置與 SRAM 單獨檢查相同）、KLayout DRC 0、LVS 0、XOR 0、unannotated driver 133、SRAM 位置。

## 與 Phase 3 golden 的差異（Phase 4 時檢視）

- metrics 從 320 個變成 434 個：多的 114 個是新加的 6 個溫度反轉 corner（`*_ss_n40C_1v60`、`*_ff_100C_1v95`）各 19 個；沒有 metric 消失。
- 127 個值改變，原因都是 Phase 4 的設定變更：
  - 週期 40 → 42 ns（使用者決定，ADR-0004 補充），uncertainty 分成 setup／hold 並加 duty cycle 預算（`clock_uncertainty.sdc`），SRAM derate 1.575／0.665：最差 setup slack 3.553 → 0.313 ns（min_ss_n40C，SRAM 半週期路徑）。
  - resizer hold 餘裕 0.1 → 0.3 ns：hold buffer 2468 → 3452，最差 hold 0.032 → 0.082 ns。
  - PnR 的 max transition 0.70 ns（signoff 仍 0.75）、clock pin 的線切段（`CTS_CLK_MAX_WIRE_LENGTH` 150）、resizer setup 餘裕 0.6 ns。
  - standard cell 27,932 → 29,352 顆（+1420），面積 227,740 → 237,644 µm²：timing repair buffer 8117 → 9525（其中 hold buffer +984，來自 hold 餘裕 0.3 ns；其他 +424）、antenna diode 78 → 85、clock buffer 551 → 531、clock inverter 37 → 62。這些是上面幾項設定一起造成的，沒有逐項分開實驗。
  - IR 改一側供電模型：`ir__drop__worst` 0.306 → 4.04 mV（GND 抬升 4.03 mV）。
  - unannotated driver 134 → 133（CTS dummy load 91 → 90，組成見 `signoff/limits/soc_top.toml`）。
- 沒變的：Magic DRC 4,665,810（全部在 SRAM 框內、位置與 SRAM 單獨檢查相同）、KLayout DRC 0、LVS 0、XOR 0、最長線 619.53 µm、SRAM 位置。

## 可重現性

| run | 與本檔比較 |
|---|---|
| Phase 5 PicoRV32 ADR-0016 正式 harden（commit `2caad0e`） | 本檔來源 |
| Phase 5 PicoRV32 確認 harden（commit `1d13775`） | 436 個完全相同；第 44 步遇到 GRT-0229，從該步接續一次（接續的 run 與一次跑完的 run 結果相同）→ harden-soc PASS |
| Phase 5 乾淨 checkout 的 `make regress-picorv32`（commit `7348fab`，2026-10-08） | 436 個完全相同，沒有重試 → harden-soc PASS，regress 26/26 |
| 下列為舊 golden 的紀錄 | |
| Phase 3.5 第 3 次 harden-soc（commit `edb7d63`） | Phase 3.5 golden 的來源（見 git 歷史，commit `2caad0e` 以前的本檔） |
| Phase 4 的 run（下列） | 與 Phase 4 的 golden 比較；該 golden 見 git 歷史（commit `edb7d63` 以前的本檔） |
| Phase 4 第 5 次 harden-soc（commit `e5b7a4b`） | Phase 4 golden 的來源 |
| Phase 4 `make regress` 第 1 次（乾淨 checkout，commit `72e5433`） | 434 個完全相同（沒有用到誤差） |
| Phase 4 `make regress` 第 2 次（乾淨 checkout，commit `c635ffb`） | 349 個相同、84 個在誤差內、1 個不同：`route__drc_errors__iter:2` 14（golden 11）→ harden-soc FAIL |
| Phase 4 `make regress` 第 3 次（乾淨 checkout，commit `59c6748`） | 434 個完全相同（LibreLane 遇到一次已知的 GRT-0229，從第 41 步重試後完成）；這次 regress 後來在 gl-soc-powered FAIL（gate-level 牆鐘時限，`dv/gl_soc/README.md` 判定第 4 點） |
| Phase 4 `make regress` 第 4 次（乾淨 checkout，commit `b7860b7`） | 434 個完全相同（GRT-0229 重試 1 次）；整個 regress 25/25 PASS，Phase 4 以這次結案 |

第 2 次與第 1 次的設定（`resolved.json`，路徑以外）相同，送進 `OpenROAD.DetailedRouting`（第 45 步）的 ODB 逐 byte 相同；之前抽查的各步（floorplan、placement、CTS、global routing、antenna 修補）DEF 也相同。第 45 步的主繞線各輪 DRC 數兩次一樣（15174 → 8308 → 7550 → 747 → 21 → 0），差異從 antenna 修補後的第一次重繞開始（第 1 輪 309 vs 308），最後一次重繞的第 2 輪剩 11 vs 14 個；最終 DRC 兩次都是 0。第 1 次 434 個完全相同只是剛好，不代表繞線每次都一樣。`route__drc_errors__iter:N` 是「最後一次走到第 N 輪的繞線呼叫」在第 N 輪後剩下的 DRC 數，屬於繞線器中間過程，因此使用者決定（2026-10-04）兩個設計都給 ±100 的誤差（高於看過的所有值：本設計最大 87），最終 `route__drc_errors` 仍要完全相同且 = 0；`neg_pnr.py` P31 證明最終 DRC 數 +1、中間輪 +101 都 FAIL，+3 PASS。剩下的風險：如果某次繞線多跑或少跑幾輪，`route__drc_errors__iter:*` 的 key 會多或少，比對仍判 FAIL（到目前每次都是同一組 key）。

Phase 3 的 golden（320 個 metrics，2026-10-03）與它的可重現性紀錄見 git 歷史（commit `3b08251` 以前的本檔）。

## 何時更新

升級 LibreLane、PDK、PicoRV32、SRAM 的產生檔（特性化 .lib、antenna LEF），或修改 `config.json`、`pin_order.cfg`、`*.sdc`、`sta_extra_corner.tcl`、RTL 之後，golden 比對一定會 FAIL。更新步驟與 `signoff/golden/picorv32_core/README.md` 相同：確認 limits 與 `check_soc.py` 全部 PASS、逐項檢視差異、複製 metrics 並更新本表與 sha256、再跑一次確認 PASS。
