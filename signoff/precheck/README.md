# ChipFoundry precheck 的判定（ADR-0019 決定 5）

`make precheck-check PRECHECK_PROJECT=<precheck 跑過的目錄>` 依 ADR-0019 決定 5 判定 ChipFoundry precheck 的結果。

- **precheck**：ChipFoundry 收件前的自動檢查（pip 套件 `cf-precheck`，在官方 Docker image 裡跑），共 13 項，每項的結果寫在專案目錄的 `.cf/project.json`。
- **為什麼要另外判定**：precheck 的 KLayout deck 在 2026-05 拿掉了 SRAM 核心區的豁免（cf-precheck commit `08f559e30a`），任何用 OpenRAM bitcell 的 SRAM，**包括 PDK 預建的 `sky130_sram_*`**，`klayout_feol` 都會報 `MR_licon.SP.6`、`klayout_beol` 都會報 `MR_mcon.CON.10`，沒有參數能關掉（`docs/notes/caravel_precheck_phase7.md` 第 7 節）。官方結果在這兩項一定是 FAIL。
- **使用者的決定**（2026-10-12）：其他 11 項全部 PASS；這兩項只允許這兩條規則，每一個違規都在 SRAM 裡，而且 PDK 預建 macro 單獨檢查時，同一個位置也有。

## 判定內容

| 檢查 | 內容 | FAIL 的例子 |
|---|---|---|
| 檢查項目齊全 | `project.json` 剛好是 cf-precheck 1.3.7 的 13 項；`magic_drc`（選用，預設不跑）只能是 skip 或 pass | precheck 升版加了新檢查、少了一項 |
| 其他 11 項 | 全部 pass | `lvs: fail` |
| 版本 | cf-precheck 是 `env/versions.mk` 的 `CF_PRECHECK_VERSION` | image 升級了 cf-precheck，檢查內容可能變了 |
| 檢查的是這份 GDS | `gds/<top>.gds` 的 sha1 = `project.json` 的 `input_file_hash` = 結果目錄 `logs/gds.info` 記的 sha1；`project.json` 在結果目錄開始之後寫入 | precheck 跑完後 GDS 被換掉、讀到前一次 run 的報表 |
| 報表本身一致 | 報表的 top cell、`<item>` 數 = `logs/<check>_check.total`、status 是 pass 恰好在沒有違規時 | 讀到別次的報表 |
| 同一版 deck、對的比對基準 | 報表與比對基準的規則清單（名稱與描述）相同；比對基準的 `input.sha1` 是 `--ref-gds` 的 sha1 | 比對基準是舊 deck 或別版 PDK 的 macro 產生的 |
| 規則 | 設計的 FEOL 只有 `MR_licon.SP.6`，BEOL 只有 `MR_mcon.CON.10`；比對基準的其他規則印出、不列入比對（ADR-0019 決定 24：precheck 的 PDK `3e0e31dc` 裡的預建 SRAM，FEOL 控制邏輯另有 10 個 nsdm／psdm 違規） | 多了 `m1.1`；比對基準與設計都有同一條其他規則 |
| 位置 | KLayout 讀到的項目數等於 XML 的；沒有無法定位的違規（cell 不在 GDS 裡、沒有座標值）；展開後每一個違規都在唯一的 SRAM instance 裡，換回 SRAM 的座標後，相對 bitcell array 的位置在比對基準裡也有（數量不超過） | SRAM 外有一個 `MR_mcon.CON.10`、SRAM 裡多了一個預建 macro 沒有的位置 |

### 為什麼比「展開後相對 bitcell array 的位置」，不是「同一個 cell」

決定 5 原文是「同一個 cell、同一個相對位置」。實作時發現兩件事（2026-10-14，比對兩顆 macro 單獨檢查的報表）：

1. deck 用 deep 模式，一個違規只在找到它的那一層 cell 回報一次。同樣的違規，自產 macro 有 2 個掛在 `dummy_array`，預建 macro 掛在 `replica_bitcell_array`；cell 名稱也有各自的前綴（`arv_sram_…`、`sky130_sram_…`）。直接比 cell，兩顆好的 macro 也對不上。
2. 自產 macro 是新版 OpenRAM 產生的，比預建的大（694.27 × 428.415 對 683.1 × 416.54 µm），bitcell array 在 macro 裡的位置差 (5.61, 9.32) µm。

限制：設計裡只能有一顆用 OpenRAM bitcell 的 SRAM。bitcell 這層 cell（`sky130_fd_bd_sram__openram_dp_cell*`）沒有 macro 名稱的前綴，第二顆 SRAM 的違規會被算成在受檢 SRAM 外而 FAIL（不會誤判 PASS）；設計有第二顆時要改成逐顆比對。

所以 `rdb_flatten.py` 把每個違規展開到它所在 cell 的每一個 instance（array 逐個元素），換回 SRAM 的座標，再以 bitcell array（所有 `sky130_fd_bd_sram__openram_dp_cell` instance 的外框）左下角為原點。位移由 GDS 的 instance 位置決定，不從違規位置去擬合。結果：兩顆 macro 單獨檢查時，FEOL 16,900 個、BEOL 50,184 個位置**完全相同**；比 cell 名稱更嚴，因為每個 instance 的每個違規都要對得上。

## 檔案

| 檔案 | 用途 |
|---|---|
| `make_project.py` | 從 harden run 組出 precheck 的專案目錄：GDS、帶電源的網表、`user_defines.v`、`lvs_config.json`（SRAM 在 `EXTRACT_ABSTRACT`，網表沒有它的 module，當 black box 比，照 ChipFoundry `caravel_user_sram` 範例）。要通過 run guard；`--verification` 略過 guard 做查證，來源記在 `arvinsa_source.json`，checker 會印出來 |
| `run_precheck.sh` | 在 lima VM 用官方 image 跑 precheck（照 `cf precheck` 的 `docker run`），記下開始時間、image digest、PDK、cf-precheck 版本、結束碼；同一個容器接著用 image 自己的 deck 與 KLayout 跑 precheck PDK 的 SRAM，當比對基準（`<project>/sram_ref/`） |
| `check_precheck.py` | 判定（上表） |
| `rdb_flatten.py` | KLayout 腳本：報表的違規展開到頂層、換回 SRAM 座標、以 bitcell array 為原點 |
| `run_deck.py` | 用固定版本的 deck 在本機跑 FEOL／BEOL，參數照 cf-precheck `checks/klayout_drc.py`；產生比對基準（`make precheck-sram-ref`）與 negative test 的資料。**不是判定**：判定只認官方 image 的結果 |
| `make_fixture.py` | negative test 用的 GDS：只有一顆鏡像（DEF FS）放置的自產 SRAM 的 `user_project_wrapper` |
| `neg_precheck.py` | negative test（`make neg-precheck`，在 `make regress` 裡） |

deck 本身是 GPLv3，不放進 repo：`make precheck-deck` 從 PyPI 下載固定版本的 `cf-precheck` wheel，核對 wheel 與 deck 的 sha256（`env/versions.mk` 的 `CF_PRECHECK_*`）後放到 `.tools/cf-precheck-<版本>/`。官方 image 每次跑都會 `pip install --upgrade cf-precheck`，升版時要重新讀 deck、更新這三個值，並重看 skill `tapeout-precheck-caravel` 規則 3 的防護。

## 正式的流程

`make precheck-caravel`（約 1 小時，Rosetta 模擬）：`make_project.py` → `run_precheck.sh` → `check_precheck.py`，比對基準用同一個容器產生的 `sram_ref/`，`--ref-gds` 指向 precheck 用的 PDK（`3e0e31dc`）裡的 SRAM。lima VM 要 16 GiB 記憶體：10 GiB 時 wrapper 的 KLayout BEOL 與 Magic 抽取被 OOM killer 砍掉（`docs/notes/caravel_precheck_phase7.md` 第 10 節）。這顆 GDS 和 flow 用的 PDK（`8afc834`）裡那顆 sha1 不同，所以比對基準一定要綁到實際跑的 GDS。`PRECHECK_VERIFY=1` 給還沒重新 harden 的 run 做查證。專案目錄在 `$(PRECHECK_WORK)/<repo 目錄名>`（例如 `../arvinsa-rtl-gds-p7precheck/arvinsa-rtl-gds`），兩個 worktree 同時跑不會互相覆蓋（ADR-0019 決定 25）；`make regress-caravel` 的 `env-check-flow` 先檢查 VM（docker context、image、16 GiB、PDK）。

第一次正式判定（2026-10-14，`550869c` 的確認 harden，53 分鐘）：`precheck: PASS (ADR-0019 decision 5)`，`runs/p7_formal_precheck.log`；image digest、版本與各項結果在 `docs/notes/caravel_precheck_phase7.md` 第 10b 節。

## 比對基準

`make precheck-sram-ref`：在本機用固定版本的 deck 跑 PDK 的 `sky130_sram_2kbyte_1rw1r_32x512_8`，輸出到 `runs/precheck_sram_ref/`。正式判定（Phase 7 步驟 7）時，比對基準在跑 precheck 的同一個 image 裡用同一份 deck 產生，checker 會用規則清單確認兩者是同一版 deck。

## negative test

`make neg-precheck`（25 個案例，約 5 分鐘）：用 `make_fixture.py` 做一份只有 SRAM 的 `user_project_wrapper`，用 deck 跑出真的 FEOL／BEOL 報表，加上一份其他項目都 pass 的 `project.json`，再逐項植入錯誤。每個植入的錯誤都必須在**它自己那一列** FAIL，三個正向案例（原樣、沒有違規、比對基準多一條其他規則）必須 PASS。案例清單在 `neg_precheck.py` 的說明。
