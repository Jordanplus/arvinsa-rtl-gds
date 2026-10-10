# OpenRAM 自產 SRAM macro（Phase 6，ADR-0018）

用釘版的 OpenRAM 產生 SRAM macro，並檢查 OpenRAM 自己跑的 DRC 與 LVS。時序的 .lib 不用 OpenRAM 產生，
沿用 `ip/sram/char/` 的 ngspice 特性化流程（skill `openram-macro-characterization` 規則 3）。

## 使用

```sh
make openram-setup                       # 一次：裝 OpenRAM、sky130_fd_bd_sram、OpenRAM 釘的 PDK、Python venv 到 .tools/
make openram-macro                       # 預設 configs/arv_sram_2kbyte_1rw1r_32x512_8.py → runs/openram/<name>/
make openram-macro OPENRAM_CONFIG=<cfg> OPENRAM_DRC_MAX=<n>
```

`runs/openram/<name>/` 裡：`macro/`（GDS、LEF、SPICE、LVS 網表、Verilog 模型、OpenRAM 的解析 .lib）、
`tmp/`（OpenRAM 的 DRC／LVS 報告）、`openram.log`、`summary.json`（PASS／FAIL、DRC 數、LVS 結果、各產出檔的 sha256、版本）。
同名目錄已存在時，舊的會改名成 `.old-<時間>` 保留。

## 版本與環境

- 版本釘在 `env/versions.mk`（`OPENRAM_*`、`SKY130_FD_BD_SRAM_*`），說明在 `toolchain.md` §3.1、§5。
- **macro 用 OpenRAM 自己釘的 2022 PDK（`e8294524`）產生與驗證**；SoC flow 與 SPICE 特性化仍用 `8afc834`（ADR-0018 決定 5）。
- Magic、Netgen、KLayout 由 LibreLane 的 nix-shell 提供；OpenRAM 設 `use_nix = False`（由 `gen_macro.py` 附加到設定檔）。
- `PYTHONHASHSEED=0`：不固定的話，同一份設定兩次產生的繞線不同。

## 對 OpenRAM 的修改（patch）

OpenRAM 不在 repo 裡改，改動一律放在 `patches/*.patch`（相對 OpenRAM repo 根目錄，依檔名順序套用）：

| patch | 內容 | 依據 |
|---|---|---|
| `0001-sense-amp-input-precharge.patch` | 有 column mux 的讀取 port，在 column mux 與 sense amp 之間多放一排 precharge cell（每個資料 bit 一個，接 `bl_out`／`br_out` 與 `p_en_bar`）；`precharge_array` 加 `mirror_stride`；bank 連接 port_data 的每一支 `p_en_bar` | ADR-0018 決定 8 |

- `make openram-setup`：OpenRAM 的追蹤檔案不等於「`OPENRAM_COMMIT`＋全部 patch」時，回到釘選 commit（只丟掉 `.tools/openram` 追蹤檔案的修改，已安裝的 cell 庫不受影響）再依序 `git apply`。
- `check_install.py` 的 `tree_problems()`：用暫時的 git index 算「釘選 commit＋patch」的 tree 與工作樹追蹤檔案的 tree，兩者必須相同，HEAD 必須是釘選 commit。`gen_macro.py` 產生前也會檢查，並把 patch 檔名與 sha256 寫進 `summary.json`。negative test：`neg-openram` T1–T3。
- 改 patch 的做法：在 `.tools/openram` 從釘選 commit 開本機分支修改並 commit，`git format-patch --zero-commit --no-signature -1` 匯出到 `patches/`，再跑 `make openram-setup`。

## 腳本

| 檔案 | 用途 |
|---|---|
| `setup.sh` | `make openram-setup`。套用 patch；安裝後檢查每個 bd_sram cell 的 GDS 都裝進 OpenRAM 的 `technology/sky130/gds_lib`（OpenRAM 的 `make sky130-install` 會因為時間戳記少複製、仍回傳 0） |
| `../../../scripts/check_macro_views.py` | `make openram-macro` 的第二步：每個交付檔的內容（名稱、腳位與方向、.lib 數值與面積、LEF 尺寸對 GDS 外框），結果 `views.json`；任何 macro 都要做（CLAUDE.md 規則 12） |
| `macro_drc.py` | 整顆 macro 的 Magic full 規則 DRC，逐種類和預建 macro 的 baseline（`drc_baseline_*.json`）比較（`make openram-macro` 的第三步；三步都會跑，任一 FAIL 就 FAIL） |
| `read_check.py` | 步驟 3a：用 `ip/sram/char/` 的方法在各 PVT 檢查讀取正確性 |
| `lib_template.py` | `make openram-lib-template`：OpenRAM 的 TT .lib 當特性化範本前，internal_power 換成預建 macro 的值（OpenRAM dev 寫成 1e9–1e11；skill `openram-macro-characterization` 規則 24） |
| `patches/` | 對 OpenRAM 的修改（上一節） |
| `gen_macro.py` | `make openram-macro`。PASS 要同時滿足：log 沒有 `ERROR`（OpenRAM 在 LVS 不一致時仍回傳 0）、DRC ≤ 上限、LVS `Circuits match uniquely.`、產出檔齊全 |
| `check_install.py` | cell 庫安裝完整、OpenRAM 工作樹＝釘選 commit＋patch |
| `neg_openram.py` | `make neg-openram`：O1–O8、I1–I4、T1–T3、D1–D3、L1–L2、C1–C2 |
| `extract_cell.py` | KLayout 從 GDS 切出一個 cell（`setup.sh` 用來取 `dlxtn_1`） |
| `requirements.txt` | Python 套件版本 |
| `configs/` | macro 設定（只放設計參數） |

環境建立過程遇到的工具問題與實驗：`docs/notes/openram_phase6_bringup.md`。
