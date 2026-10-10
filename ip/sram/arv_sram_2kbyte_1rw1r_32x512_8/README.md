# arv_sram_2kbyte_1rw1r_32x512_8：OpenRAM 自產的 2 KB SRAM（Phase 6，ADR-0018）

和預建的 `sky130_sram_2kbyte_1rw1r_32x512_8` 同規格（1rw1r、32 bit × 512、write mask 8 bit），由本 repo 用 OpenRAM 產生，並套用 sense amp 輸入端預充電的 patch（ADR-0018 決定 8）。

## `openram/`：產生結果（`make openram-macro` 的輸出，複製進版控）

| 檔案 | 內容 |
|---|---|
| `arv_sram_2kbyte_1rw1r_32x512_8.sp` | 電晶體級網表，SPICE 特性化的輸入；sha256 必須等於 `summary.json` 記錄的值（`check_char_lib.py` 的來源檢查） |
| `summary.json` | 產生紀錄：OpenRAM commit、patch 檔名與 sha256、設定檔 sha256、OpenRAM 的 DRC／LVS 結果、各產出檔 sha256 |
| `arv_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib` | OpenRAM 的解析 .lib，原樣保存；internal_power 是錯的（1.036316e+11），不能直接用 |
| `arv_sram_2kbyte_1rw1r_32x512_8_TT_template.lib` | 特性化用的 .lib 範本：上一個檔案把 internal_power 換成預建 macro 的值（`make openram-lib-template`，skill `openram-macro-characterization` 規則 24） |

GDS、LEF 與 Verilog 模型在步驟 4a 換進 SoC 時一起加入。

## `char/`：SPICE 特性化結果（步驟 3c）

`char.json`、`confirm.json` 與 5 份 `arv_sram_2kbyte_1rw1r_32x512_8__<pvt>.lib`，做法同 `ip/sram/char/README.md`。

```bash
make openram-char        # 特性化（數小時），接著產生 .lib 與確認模擬
make openram-check-lib   # 獨立重算、來源、確認模擬
```

- .lib 的數字公式與預建 macro 相同（ADR-0010 的使用者決定：padded.lib 的下限、×1.6 走線餘量等）。
- port 1 的時序是 OpenRAM 的解析值；power 是預建 macro 的解析值，兩者都不可信（ADR-0007 限制 3）。
