# soc_top golden：整合 SRAM 的 soc_top 的 metrics

`make harden-soc` 最後一步用 `signoff/scripts/check_signoff.py` 把這次 run 的 metrics 與 `metrics.json` 逐項比對：key 必須完全一樣，值必須相同，只有 `signoff/limits/soc_top.toml` 的 `[golden_tolerance]` 列出的族群（detailed routing 不是每次都一樣，見 `signoff/golden/picorv32_core/README.md`）可以有很小的誤差。signoff 門檻用的是這次 run 自己的值，不受誤差規則影響。

## 出處

| 項目 | 值 |
|---|---|
| 產生方式 | `make harden-soc`（tag `soc_top`）的 `runs/soc_top_signoff/metrics.json`，原檔複製，沒有修改 |
| 日期／平台 | 2026-10-03，Apple Silicon macOS（arm64） |
| LibreLane／PDK／PicoRV32／SRAM macro | 同 `env/versions.mk` |
| flow 設定 | `pnr/soc_top/config.json` sha256 `abb94013cff62201db83745ec422a6896b7e78587f021c457da253a23e88008f`（golden 建立時）。之後只改過 `//` 註解（2026-10-03，更正 GRT-0229 的說明），現在是 `827b3add2a897461791ae85f354c970818e732d44b720c722d0aac3b1f94992d`；LibreLane 不讀 `//` 開頭的 key（`librelane/config/config.py` 第 1056 行；`resolved.json` 裡沒有這些 key） |
| 本檔 sha256 | `1c017aa38985fbc1759a5795bc23e627cfc9b9f57d21cd04b0c91bafbbbe765d` |

## 可重現性

| run | 與本檔比較 |
|---|---|
| 試跑 soc_explore10（與定案設定相同：密度 55% 由命令列 `-c` 給，signoff SDC 為 1.0 ns 版本，PnR 部分與定案相同） | 320 個 metrics 完全相同（兩種 signoff 門檻下 slew／fanout 違規都是 0，所以違規數也相同） |
| 定案設定的第 1 次正式 run（`make harden-soc`，2026-10-03；`pnr/soc_top/README.md` 試跑紀錄的 harden-soc 2） | 本檔來源 |

## 何時更新

升級 LibreLane、PDK、PicoRV32、SRAM 的產生檔（padded.lib、antenna LEF），或修改 `config.json`、`pin_order.cfg`、`*.sdc`、`sta_extra_corner.tcl`、RTL 之後，golden 比對一定會 FAIL。更新步驟與 `signoff/golden/picorv32_core/README.md` 相同：確認 limits 與 `check_soc.py` 全部 PASS、逐項檢視差異、複製 metrics 並更新本表與 sha256、再跑一次確認 PASS。
