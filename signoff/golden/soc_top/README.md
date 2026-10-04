# soc_top golden：整合 SRAM 的 soc_top 的 metrics

`make harden-soc` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/soc_top.toml` 的 `[golden_tolerance]` 列出的族群（detailed routing 不是每次都一樣，見 `signoff/golden/picorv32_core/README.md`）可以有誤差：slack、skew、線長、via、功耗、IR drop 很小的誤差，繞線器中間各輪的 DRC 數 ±100（見下方可重現性）。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden-soc`（tag `soc_top`）的 `runs/soc_top_signoff/metrics.json`，原檔複製，沒有修改 |
| 日期／平台 | 2026-10-04（Phase 4），Apple Silicon macOS（arm64） |
| 來源 run | Phase 4 第 5 次 harden-soc，commit `e5b7a4b`。limits 有兩類 FAIL：與舊 golden 比對（預期）；沒有寄生值的 driver 133 個，當時上限寫「剛好 134」（見下方最後一點，檢視後上限改 133）。`check_soc.py`、輸入一致、來源追溯 PASS |
| LibreLane／PDK／PicoRV32／SRAM macro | 同 `env/versions.mk` |
| flow 設定 | `pnr/soc_top/config.json` sha256 `3623be19eb2cfeb089690bb3abd3459652905f39516744684d4083b1b8d8b6d2` |
| 本檔 sha256 | `5c7b95eb6ad7abf3e6d1d7b92c542629bf8d6d8680e9c931d8e7b8510f5fa351` |

## 與 Phase 3 golden 的差異（逐項檢視過）

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
| Phase 4 第 5 次 harden-soc（commit `e5b7a4b`） | 本檔來源 |
| Phase 4 `make regress` 第 1 次（乾淨 checkout，commit `72e5433`） | 434 個完全相同（沒有用到誤差） |
| Phase 4 `make regress` 第 2 次（乾淨 checkout，commit `c635ffb`） | 349 個相同、84 個在誤差內、1 個不同：`route__drc_errors__iter:2` 14（golden 11）→ harden-soc FAIL |
| ＜Phase 4 `make regress` 第 3 次（乾淨 checkout）＞ | ＜待填＞ |

第 2 次與第 1 次的設定（`resolved.json`，路徑以外）相同，送進 `OpenROAD.DetailedRouting`（第 45 步）的 ODB 逐 byte 相同；之前抽查的各步（floorplan、placement、CTS、global routing、antenna 修補）DEF 也相同。第 45 步的主繞線各輪 DRC 數兩次一樣（15174 → 8308 → 7550 → 747 → 21 → 0），差異從 antenna 修補後的第一次重繞開始（第 1 輪 309 vs 308），最後一次重繞的第 2 輪剩 11 vs 14 個；最終 DRC 兩次都是 0。第 1 次 434 個完全相同只是剛好，不代表繞線每次都一樣。`route__drc_errors__iter:N` 是「最後一次走到第 N 輪的繞線呼叫」在第 N 輪後剩下的 DRC 數，屬於繞線器中間過程，因此使用者決定（2026-10-04）兩個設計都給 ±100 的誤差（高於看過的所有值：本設計最大 87），最終 `route__drc_errors` 仍要完全相同且 = 0；`neg_pnr.py` P31 證明最終 DRC 數 +1、中間輪 +101 都 FAIL，+3 PASS。剩下的風險：如果某次繞線多跑或少跑幾輪，`route__drc_errors__iter:*` 的 key 會多或少，比對仍判 FAIL（到目前每次都是同一組 key）。

Phase 3 的 golden（320 個 metrics，2026-10-03）與它的可重現性紀錄見 git 歷史（commit `3b08251` 以前的本檔）。

## 何時更新

升級 LibreLane、PDK、PicoRV32、SRAM 的產生檔（padded.lib、antenna LEF），或修改 `config.json`、`pin_order.cfg`、`*.sdc`、`sta_extra_corner.tcl`、RTL 之後，golden 比對一定會 FAIL。更新步驟與 `signoff/golden/picorv32_core/README.md` 相同：確認 limits 與 `check_soc.py` 全部 PASS、逐項檢視差異、複製 metrics 並更新本表與 sha256、再跑一次確認 PASS。
