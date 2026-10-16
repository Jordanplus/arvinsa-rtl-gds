# arv_sram_2kbyte_1rw1r_32x512_8：OpenRAM 產生的 2 KB SRAM（Phase 6，ADR-0018）

和 PDK 附的 `sky130_sram_2kbyte_1rw1r_32x512_8` 同規格（1rw1r、32 bit × 512、write mask 8 bit），由本 repo 用 OpenRAM 產生，並套用 sense amp 輸入端預充電的 patch（ADR-0018 決定 8）。

## `openram/`：產生結果（`make openram-macro` 的輸出，複製進版控）

| 檔案 | 內容 |
|---|---|
| `arv_sram_2kbyte_1rw1r_32x512_8.sp` | 電晶體級 netlist，SPICE characterization 的輸入；sha256 等於 `summary.json` 記錄的值，或內容雜湊等於 `spice_content_sha256`（`check_char_lib.py` 的來源檢查、`check_inputs.py macro_source`）。目前這份是 patch 0001 那次產生的（做 characterization 用的），patch 0002–0004 只改 layout，那次 run 寫出的 netlist 子電路逐字相同、順序不同（ADR-0018 決定 17） |
| `summary.json` | 產生紀錄：OpenRAM commit、patch 檔名與 sha256、設定檔 sha256、OpenRAM 的 DRC／LVS 結果、各產出檔 sha256 |
| `arv_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib` | OpenRAM 的解析 .lib，原樣保存；internal_power 是錯的（1.036316e+11），不能直接用 |
| `arv_sram_2kbyte_1rw1r_32x512_8_TT_template.lib` | 做 characterization 用的 .lib 範本：上一個檔案把 internal_power 換成 PDK 附的 macro 的值（`make openram-lib-template`，skill `openram-macro-generation` 規則 8） |
| `arv_sram_2kbyte_1rw1r_32x512_8.gds`、`.lef`、`.v` | layout、OpenRAM 原始 LEF（`DATABASE MICRONS 2000`）、行為模型；sha256 等於 `summary.json`（`check_inputs.py macro_source`）。flow 直接讀這份 GDS（步驟 4a） |

## 交給 flow 的檔（步驟 4a，2026-10-10）

| 檔案 | 內容 | 怎麼產生／檢查 |
|---|---|---|
| `arv_sram_2kbyte_1rw1r_32x512_8.lef` | flow 用的 LEF：`openram/` 的 LEF 加上 59 支輸入腳位的 `ANTENNAGATEAREA`（資料／位址 0.6 µm²、`clk0`／`clk1` 0.222 µm²），`DATABASE MICRONS` 改成 1000（OpenROAD 會丟掉 2000 的 LEF，`ODB-0292`；座標都在 0.005 µm 格點，無損） | `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_antenna_lef.py openram/arv_sram_2kbyte_1rw1r_32x512_8.lef openram/arv_sram_2kbyte_1rw1r_32x512_8.sp arv_sram_2kbyte_1rw1r_32x512_8.lef`；`check_inputs.py antenna_lef` |
| `arv_sram_2kbyte_1rw1r_32x512_8.bb.v` | 合成與 lint 用的 blackbox | 手寫，腳位同 `upstream/` |
| `upstream/arv_sram_2kbyte_1rw1r_32x512_8.v` | OpenRAM 的行為模型（= `openram/arv_sram_2kbyte_1rw1r_32x512_8.v`） | `check_inputs.py macro_source` |
| `sim/arv_sram_2kbyte_1rw1r_32x512_8.v` | 模擬用：加 `timescale`、`VERBOSE = 0`（OpenRAM dev 已把 `mem` 宣告放在使用前，不用搬） | `ip/sram/gen_sim_model.py upstream/arv_sram_2kbyte_1rw1r_32x512_8.v sim/arv_sram_2kbyte_1rw1r_32x512_8.v`；`check_inputs.py sim_model` |

SoC 的接法：port 1 不用，`csb1 = 1`、`addr1 = 0`，`clk1` 接系統時脈（ADR-0018 決定 9，`check_soc.py port1_tieoff`）。放在 (290.72, 353.6)、N（ADR-0006 的 Phase 6 補充）。

## `char/`：SPICE characterization 結果（步驟 3c）

`char.json`、`confirm.json` 與 5 份 `arv_sram_2kbyte_1rw1r_32x512_8__<pvt>.lib`，做法同 `ip/sram/char/README.md`。

```bash
make openram-char        # characterization（數小時），接著產生 .lib 與確認模擬
make openram-check-lib   # 獨立重算、來源、確認模擬
```

- .lib 的數字公式與 PDK 附的 macro 相同（ADR-0010 的使用者決定：padded.lib 的下限、×1.6 的 layout 寄生 margin 等）。
- port 1 的時序是 OpenRAM 的解析值，不可信（ADR-0007 限制 3）；SoC 不用 port 1，但 `clk1` 接了時脈，STA 會用這些數字檢查它。internal power 與待機漏電是 SPICE 量測值（ADR-0018 決定 10–15，`char/power.json`）。
