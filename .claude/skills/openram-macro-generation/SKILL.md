---
name: openram-macro-generation
description: 用 OpenRAM 產生 SRAM macro（sky130）時使用。症狀：OpenRAM 的 LVS 報 `Netlists do not match`（新 PDK 的 `special_nfet_01v8`、`special_pfet_latch`）；log 有 `ERROR ... LVS mismatch` 但 exit 0；DRC 只記成 `WARNING ... DRC Errors`；`make sky130-install` 後報 `Custom cell pin names do not match spice file`；同一設定兩次產生的 GDS 不同（`PYTHONHASHSEED`）；`use_nix` 時 `could not find a flake.nix file`；macro 進了 SoC 後 flow 的 KLayout DRC 報 `nwell.6`、`psdm.1`、`m2.2`；拉開 abut 的 cell 後 LVS 的 clk 變成另一個 net、KLayout 報 `nwell.2a`；`Should use a pin iterator since more than one pin`；dev 的 .lib internal_power 1e9–1e11；1RW 報 `must have an even number of cols including replica cols`。涵蓋固定版本的 PDK 與 commit、repo 內的 patch 與 worktree 檢查、DRC／LVS 不看 exit code、KLayout deck 依名稱排除 SRAM cell、讀取電路。characterization 看 openram-macro-characterization，view QA 看 macro-qualification。Use for generating SRAM macros with OpenRAM on sky130 (pinned PDK, patches, DRC/LVS, reproducibility).
---

# 用 OpenRAM 產生 SRAM macro

2026-10-15 從 `openram-macro-characterization` 拆出（ADR-0021 決定 5）。產生之後的 SPICE characterization 與 .lib 看 `openram-macro-characterization`；layout 萃取看 `sram-layout-extraction`；交給 flow 前的 view QA（`CLAUDE.md` 規則 12）與 go／no-go 看 `macro-qualification`。本 repo 實例：ADR-0018、`ip/sram/openram/`（`make openram-setup`、`make openram-macro`、`make neg-openram`；negative test 的案例表在 `ip/sram/openram/neg_openram.py` 開頭）、`docs/notes/openram_phase6_bringup.md`。

## 規則（已驗證）

1. **用 OpenRAM 產生 macro 時，DRC／LVS 用 OpenRAM 自己釘的 PDK**（原 `openram-macro-characterization` 規則 17；sky130：OpenRAM Makefile 的 `SKY130_CIEL`；本 repo 實例 ADR-0018 決定 5、`docs/notes/openram_phase6_bringup.md`）。
    - 症狀：用較新的 PDK 跑 OpenRAM 的 LVS，`Final result: Netlists do not match.`，連最簡單的 `pinv` 都不一致：萃取出 `sky130_fd_pr__special_nfet_01v8`、schematic netlist 裡是 `sky130_fd_pr__nfet_01v8`；bitcell 萃取出 `special_pfet_latch`、cell 的 LVS netlist 是 `special_pfet_pass`；`special_nfet_latch (12->10) **Mismatch**`。
    - 原因（只換 PDK 的對照實驗）：PDK 改了元件名稱與萃取規則，OpenRAM 的固定 cell library 還是舊名稱（sky130 的改名細節：`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` S26）。只移植 OpenRAM stable 的窄 NMOS 修正、或只改 PMOS 名稱，都還不夠。
    - 怎麼發現：OpenRAM log 的 `LVS mismatch`，以及 LVS 報告各 cell 的 `Subcircuit summary`。
    - 怎麼繞過：產生與 DRC／LVS 用 OpenRAM 釘的 PDK；SoC flow 照舊用 flow 的 PDK（SRAM 在 SoC LVS 是 black box）。
    - SPICE 用新 PDK 的模型時，netlist 要先把舊元件名稱改成新名稱：PDK 留的舊名稱轉接 subckt，ngspice 報 `unknown subckt`（實際跑過；`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` S26）。本 repo 由 `read_check.py` 改名並確認沒有殘留。
    - 怎麼防止再發生：LVS 不一致由產生腳本判 FAIL（`gen_macro.py`，`neg-openram` O2）；netlist 改名後還有舊名稱時 `ip/sram/openram/read_check.py` 判 FAIL（`read_check: FAIL - special_pfet_pass left in ...`）。
2. **OpenRAM 在 DRC／LVS 失敗時 exit code 仍是 0**，GDS、LEF、.lib 照常輸出（原 `openram-macro-characterization` 規則 18）。
    - 症狀：log 第一行 `ERROR: file magic.py: line 387: <name>	LVS mismatch (results in /tmp/.../<name>.lvs.report)`，`sram_compiler.py` rc=0。
    - 怎麼發現、怎麼防止再發生：產生腳本讀 log 的 `ERROR` 行、DRC 報告的 `Total DRC errors found:`、LVS 報告的 `Final result:`，三項都要有且合格才 PASS（`gen_macro.py` `judge()`，`neg-openram` O1–O8）。只看 exit code 等於沒檢查。
    - DRC 錯誤只記成 `WARNING: file magic.py: line 254: DRC Errors <name>\t5`，不是 `ERROR`；所以只讀 `ERROR` 行不夠，要讀 DRC 報告的數字（sky130 2 KB 實例）。
    - DRC／LVS 報告預設放在 `/tmp/openram_<user>_<pid>_temp/`，結束時刪掉。設定檔寫 `keep_temp = True` 可以保留；要指定位置得用環境變數 `OPENRAM_TMP`。設定檔裡的 `openram_temp` 不會生效，也沒有錯誤訊息：`read_config` 只採用 `OPTS` 還沒有的鍵（`compiler/globals.py:361`），而 `openram_temp` 在啟動時就設好了。
3. **OpenRAM 的 `make sky130-install` 會少複製 cell，而且 exit 0**（原 `openram-macro-characterization` 規則 19）。
    - 症狀：之後產生 macro 時 `Custom cell pin names do not match spice file: ['BL0', 'BR0', 'BL1', 'BR1', 'WL0', 'WL1', 'VDD', 'GND'] vs []`。
    - 原因（已驗證）：Makefile 用 `cp -va $?` 複製，`$?` 只含比目標目錄新的檔案；`technology/sky130/gds_lib` 等目錄在 OpenRAM checkout 時就存在，比後來 clone 的 cell library 新，所以 260 個 cell GDS 一個都沒複製。
    - 怎麼繞過：安裝前 `touch` cell library 的全部檔案（`ip/sram/openram/setup.sh`）。
    - 怎麼防止再發生：安裝後逐一確認 cell library 的 GDS 與 SPICE 都在 OpenRAM 的 `gds_lib`／`sp_lib`（`check_install.py`，`neg-openram` I1–I4；產生 macro 前也會檢查）。
4. **同一份設定要產生相同的 macro，必須固定 `PYTHONHASHSEED`**（原 `openram-macro-characterization` 規則 20）。
    - 症狀：同一份設定連跑兩次，GDS 的 met2、met3、via2 不同（KLayout XOR），netlist 與 LEF 只有輸出順序不同。
    - 原因（已驗證）：Python 的 hash 隨機化影響繞線的走訪順序。設 `PYTHONHASHSEED=0` 後連跑兩次逐位元相同；不同機器（macOS Python 3.14、Colab Linux Python 3.13）的 GDS XOR 也是 0，netlist 排序後相同。
    - 怎麼繞過、怎麼防止再發生：產生腳本一律設 `PYTHONHASHSEED=0`，並在 `summary.json` 記錄每個產出檔的 sha256。第一顆正式 macro（`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/`）已經有基準值，重新產生後比對 sha256 的 checker 還沒做；目前沒有自動檢查，下一個專案開始時做。
    - GDS 不能直接比 sha256：檔頭的 BGNLIB 與每個 cell 的 BGNSTR 都記錄產生時間（sky130 2 KB 兩次產生差 948 個位元組，KLayout XOR 為 0）。比對 GDS 要用 XOR，或先把時間戳記清掉；LEF、SPICE、Verilog 可以直接比 sha256。
5. **OpenRAM 的官方環境（`nix develop`）在已經進入 devShell 時，`use_nix` 要關掉**（原 `openram-macro-characterization` 規則 21）。
    - 症狀：預設 `use_nix = True` 時，`Unable to find the total error line in Magic output`；`<name>.drc.err` 是 `does not contain a 'flake.nix' ... could not find a flake.nix file`。
    - 原因（已驗證）：`use_nix = True` 會在暫存目錄裡為每個工具再包一層 `nix develop`，那裡沒有 flake。
    - 另外，官方 devShell 只建一個空的 venv（`compiler/.venv`），要自己 `pip install -r requirements.txt`，否則報 `No module named 'numpy'`。
    - 怎麼繞過：設 `use_nix = False`，工具仍是 devShell 的版本；本 repo 的產生腳本一律附加這個設定。
6. **OpenRAM 自己的 DRC 不夠：它不用 full 規則，也不跑 flow 的 KLayout deck；sky130 產生器有幾個固定會出的 layout 錯誤**（原 `openram-macro-characterization` 規則 22；OpenRAM dev `3608704c`，sky130；本 repo 實例 ADR-0018 決定 6、17，`docs/notes/openram_phase6_bringup.md` 步驟 4b、3m）。
    - 症狀：OpenRAM log `WARNING: file magic.py: line 254: DRC Errors <name>\t<n>`（不是 `ERROR`）；Magic `drc style drc(full)` 才看得到 nwell.5a（Deep N-well 保護環內側 < 1.03 µm）、met2.2；macro 進了 SoC GDS 後，flow 的 KLayout DRC 才報 nwell.6、psdm.1、m2.2。
    - 原因（已驗證：patch 前後比較，小 macro 與 2 KB 各一次）：
      - 保護環：`add_dnwell` 用中心線壓在 Deep N-well 邊界的 path 畫 nwell 環，內外各一半（sky130 內側 0.42 µm）→ nwell.5a、nwell.6。patch 0002：sky130 改成 4 個矩形，外 0.42、內 1.03 µm。
      - met2.2：`sram_1bank.place_dffs` 讓 write mask DFF 和 column address DFF abut（緊鄰、中間沒有間隙），column address channel route 的垂直 met2 離 write mask DFF 第一支腳的 via 0.055 µm。patch 0003：兩組 DFF 之間留一個 met2 pitch。
      - psdm.1：`pgate.add_pwell_contact` 用 NMOS 源汲極接點的 active 高度（0.29 µm）算 tap 接點中心，tap 接點（directions V、V）是 0.41 µm；psdm 壓進 gnd 軌下的 nimplant，對 gnd 軌鏡射的兩排 psdm 只隔 0.26 µm（規則 0.38）。delay chain、control logic、predecoder 都有。patch 0004：用 tap 接點自己的高度。
    - **在 OpenRAM 裡把 abut 的 cell 拉開，要補回 abut 時接上的東西**：DFF 陣列的 M3 clk 軌、超出 cell 邊界的 nwell／nsdm／psdm 都靠 abut 相接。patch 0003 第一版只拉開，OpenRAM LVS 報 write mask／data DFF 的 clk 是另一個 net（`data_dff_0/clk`），KLayout 報 nwell.2a、nsdm.1（間隙只剩 0.06 µm）。補救方式：間隙補 M3 clk 與這三層，形狀從 cell 的 GDS 讀（`getAllShapes`），不要寫死座標。
    - 怎麼發現、怎麼防止再發生：`make openram-macro` 在 OpenRAM 之後跑兩種整顆 DRC。`macro_drc.py`：Magic full 規則，按規則種類分別和 PDK 附的 macro 比（bitcell 陣列本身約 220 萬個 SRAM 特殊規則的「錯誤」，只比總數看不出新問題）。比的是每種規則**合併後的違規區域**（塊數 ≤ PDK 附的 macro、面積 ≤ PDK 附的 macro + 0.05%），不是 marker 數：Magic 會在被列出 cell 的座標每 157.28 µm 把違規切成兩個 marker，陣列位置一變 marker 數就變（Phase 6 OpenRAM 產生的 SRAM 多 130／260／65 個 marker，合併後與 PDK 附的 macro 完全相同；`drc-signoff` 規則 2；`neg-openram` 的 D 系列）。`macro_klayout_drc.py`：flow 的 KLayout deck，要 0；deck 依名稱特別處理的 cell 從 deck 解析（`neg-openram` 的 K 系列，其中幾個真的跑 KLayout）。
    - **KLayout deck 依名稱排除 `*sky130_sram_*kbyte_*` 的 cell**（`sky130A_mr.drc` 的 `select("-*sky130_sram_*kbyte_*")`）：nwell.6 無條件排除，nsdm／psdm 在 `sram_exclude=true` 時排除（預設 false）。用 PDK 附的 macro 當對照要先改名再跑（sky130 2 KB 改名後仍是 0）；OpenRAM 產生的 macro 不能取這種名字（`macro_klayout_drc.py` 遇到就 FAIL，K6）。
    - 快速驗證：改 layout 產生器時先用小 macro 試（`word_size 16`、`num_words 64`、`words_per_row 2`、`write_size 8`，有 column address、write mask、data 三組 DFF），OpenRAM DRC／LVS 加 KLayout 約 3 分鐘；2 KB 要 45 分鐘。
    - 只改 layout 的 patch，schematic netlist 的子電路逐字相同，但 OpenRAM 輸出的子電路順序與檔頭會變，sha256 不同（sky130 2 KB：97 個子電路，兩次）。characterization 綁的是 netlist sha256，所以用「與順序、註解無關的內容雜湊」判斷是不是同一個電路（本 repo `gen_macro.py` 的 `spice_content_sha256`，`neg-openram` C3–C5、`neg-pnr` P70）。比對子電路時 `.subckt`／`.ends` 要不分大小寫：OpenRAM 的 bd_sram cell（DFF 等）用小寫，只抓大寫會少算還以為相同。
7. **改 OpenRAM 只能用 repo 內的 patch，並檢查 worktree 恰好是「釘選 commit＋patch」**（原 `openram-macro-characterization` 規則 23；本 repo 實例 `ip/sram/openram/patches/`、`check_install.py` 的 `tree_problems()`）。
    - 只看「HEAD 是釘選 commit、沒有修改」會擋掉合法的 patch；只看「有套 patch」又抓不到多改或少套。做法：用暫時的 git index 分別算出「釘選 commit＋patch」與「worktree 的追蹤檔案」的 tree，比對兩個 tree 的雜湊；沒進版控的安裝檔（cell library）不影響判斷。
    - 怎麼防止再發生：`neg-openram` T1（patch 以外的修改）、T2（patch 沒套）、T3（HEAD 不是釘選 commit）。產生 macro 的 `summary.json` 記錄 patch 檔名與 sha256。
    - OpenRAM 的 `get_pin()` 遇到同名接腳有兩支時會報 `Should use a pin iterator since more than one pin`；加同名控制接腳（例如第二支 `p_en_bar`）時，上一層要改用 `get_pins()` 逐一連接。
8. **OpenRAM dev 的解析 .lib，internal_power 的數量級是錯的，不能直接當範本**（原 `openram-macro-characterization` 規則 24；OpenRAM dev `3608704c`，sky130；本 repo 實例 ADR-0018、`ip/sram/openram/lib_template.py`）。
    - 症狀：OpenRAM 產生的 `<name>_TT_1p8V_25C.lib` 裡，`clk0`／`clk1` 的 12 個 `rise_power`／`fall_power` 全是同一個值，而且在 1e9–1e11（2 KB 1.036316e+11、2 KB words per row 1 9.966369e+10、8×16 1.098946e+09）；PDK 附的 macro（OpenRAM v1.1.15）同位置是 13.8。其他內容（腳位、電容、面積、port 1 解析時序）和 PDK 附的 .lib 同結構、數值合理。原因沒有查（`compiler/characterizer/elmore.py` 的 `analytical_power` 之後）。
    - 為什麼要管：.lib 範本的 power 會原樣進每一份 .lib，SoC 的 IR drop 分析用它當 SRAM 電流（`pdn-ir-drop` 規則 4）。
    - 怎麼發現：產生 macro 時的 view QA 就會 FAIL（`check_macro_views: FAIL ... internal_power 1.036316e+11 outside (0, 1000]`，`make openram-macro` 第二步，`macro-qualification` 規則 1）；拿它當 characterization 的範本時 `gen_char_lib.py` 也會報 `template ...: internal_power ... outside (0, 1000]`。
    - 怎麼繞過：`lib_template.py` 把範本的 internal_power 換成 PDK 附的 macro 同一腳位、同一 `when` 的值，其他文字一字不改（`make openram-lib-template`）。兩者都是解析值，仍不可信（ADR-0007 限制 3）。
    - 怎麼防止再發生：`gen_char_lib.power_problems()`（範本的 power 必須在 (0, `POWER_MAX`]），`neg-openram` L1（OpenRAM 原始值當範本）、L2（兩份 .lib 的 power 項目對不上）。
    - 上游也有人回報同一件事，目前仍未修（VLSIDA/OpenRAM issue #294，2026-04-30）。量測值取代範本的做法見 `openram-macro-characterization` 規則 25。
9. **sky130 1RW（單 port）macro 在釘住的 OpenRAM dev 產不出 DRC／LVS 乾淨的 layout**（原 `openram-macro-characterization` 規則 26；OpenRAM dev `3608704c`；本 repo 實例 ADR-0018 決定 11、`docs/notes/openram_phase6_bringup.md` 步驟 3f）。
    - 症狀：`ERROR: file sky130_replica_bitcell_array.py: line 30: must have an even number of cols including replica cols; you can add a spare col to fix this`（資料 column 加 replica column 是奇數，例如 128＋1）。加 `num_spare_cols = 1` 後可以產生，但 OpenRAM 的 DRC 657（log 是 `WARNING: ... DRC Errors`）、`ERROR: file magic.py: line 387: ... LVS mismatch`；`.lvs.json` 中 column cap（`sp_colend`／`sp_colenda`）的 `bl`、`br` 接到同一個 net，gnd／vdd 對調；整顆 full 規則 DRC 多出 PDK 附的 macro 沒有的種類（繞線類 `met1.1`、`met1.2`、`met2.2`、`met3.2`、`mcon.1`、`nwell.5a`）。上游 `compiler/tests/Makefile` 的 `BROKEN_STAMPS` 把 sky130 單 port 的 bank／SRAM layout 測試都列為壞掉；上游 `ec28bc6d`「correcting col_cap pin order」已在這個版本內，問題仍在。
    - 怎麼發現：`gen_macro.py` 的 `summary.json`（DRC 數、LVS 結果，規則 2）；LVS 不一致時讀 `tmp/<name>.lvs.json`，只看 `badnets`／`badelements` 非空或元件、net 數不同的子電路（大部分子電路只是 vdd 被拆成幾個 net，不是真正的差異）。
    - 怎麼繞過：用 1rw1r macro、只用 port 0，port 1 的 `clk1` 接系統時脈、`csb1=1`（ADR-0018 決定 9），並照 `openram-macro-characterization` 規則 25 量漏電。不改 OpenRAM 的單 port layout（要修補 column cap 的接線與繞線 DRC，工作量無法預估）。
    - 怎麼防止再發生：產生腳本對 DRC／LVS 判 FAIL（`gen_macro.py`，`neg-openram` O1–O8）。OpenRAM 換釘選 commit 時重跑 `ip/sram/openram/configs/arv_sram_2kbyte_1rw_32x512_8.py`，DRC、LVS 都 PASS 才考慮改用 1RW。

## 開工前查證（2026-10-08，原 `openram-macro-characterization` 同名一節）

2026-10-08 查證時的原始整理；平台、PDK、安裝與可重現性已在 2026-10-08 實跑確認，寫成上面的規則 1–5（原規則 17–21）。本 repo 實例：ADR-0018（出處逐條列在「查證結果」）。2026-10-15 依問題總檢討（`review_skills.md` 1.3）分成兩類；仍未驗證的，實跑確認後才搬進正式規則（CLAUDE.md 規則 3）。

### 已實跑

- **平台**（2026-10-08 在 macOS arm64 實際跑過，可行）：OpenRAM 官方環境（`nix develop`）只宣告 x86_64-linux（`flake.nix`），Xyce 也只有 x86_64-linux；但 OpenRAM 是純 Python，設 `use_nix = False` 就用 PATH 上的 Magic、Netgen、KLayout、模擬器（Xyce 找不到時用 ngspice）。在非官方平台跑時，要在官方環境產生同一顆 macro 比對 netlist 與 LVS，排除工具版本造成的差異。
- **讀取電路沿用同一套 cell**（Phase 6 步驟 3a 實跑：OpenRAM 產生的 macro 用同一套 sense amp 與純 NMOS column mux，`openram-macro-characterization` 規則 13 的讀取失敗照樣出現，經驗紀錄 2026-10-08）：sense amp 是 `sky130_fd_bd_sram` 的固定 cell（沒有預充電），column mux 是參數產生的純 NMOS；照預設設定產生，讀取失敗不會自己消失。`words_per_row = 1` 不產生 column mux，代價是 bitline 變長、macro 變瘦長。本 repo 的修正方式：sense amp 輸入端預充電（patch 0001，ADR-0018 決定 8）；`words_per_row = 1` 的版本放不進 die，沒有採用（ADR-0018）。
- **GDS cell 名稱**（Phase 6–7 看到 OpenRAM 產生的 macro 裡，cell 有 `arv_…` prefix、bitcell 沒有，`signoff/precheck/README.md`）：OpenRAM 2022-03 起在產生的 cell 名稱前加 `output_name_` prefix，只有 `sky130_fd_bd_sram__openram_*` 這類 library cell 沒有 prefix。macro 名稱不要和 PDK 附的 macro 同名；檢查最終 GDS 裡沒有 prefix 的 cell 只有一份定義，且內容和 macro GDS 相同。

### 仍未驗證（讀原始碼或 log）

- **重現 PDK 附的 macro**：先找它的產生設定檔與 log（OpenRAM 版本、`Words per row`、額外的 technology 目錄）。設定或 technology 目錄找不齊時，自己產生的電路和 PDK 附的不同，PDK 附的 macro 量到的數字不能沿用。
- **產生時間大部分是 LVS**：sky130 2 KB 的 log 裡 LVS 約 3.4 小時、繞線 44 分鐘、解析模式的時序計算 1 秒。不要把總時間當成「產生」的時間來排程。
  本 repo 用 OpenRAM 產生 2 KB 時，OpenRAM DRC／LVS 加 KLayout 約 45 分鐘（規則 6），和 PDK 附的 macro log 的 3.4 小時差很多，原因沒查。
- **OpenRAM 預設的 characterization corner 不含 −40°C**（溫度 0／25／100°C、電壓 1.7／1.8／1.9 V，一次只變一個）；要用 `use_specified_corners` 自己列。本 repo 的 .lib 仍用自寫的 ngspice 流程（`openram-macro-characterization` 規則 3 的缺陷照舊）。
- **OpenRAM 目前沒有人維護**（regress CI 停用）；釘 commit，不追最新，分支差異（例如 dual-port bitcell 的 LVS 修正只在 dev）要逐項看過再選。

## 用完後

1. 新的現象加進「經驗紀錄」，原因標明已驗證／推測。
2. OpenRAM 或 PDK 換釘選版本時，逐條重看規則 1–9 的對策是否還成立（CLAUDE.md 規則 10），並重跑 `make neg-openram`。

## 經驗紀錄

2026-10-15 從 `openram-macro-characterization` 的經驗紀錄搬來（ADR-0021 決定 5）。

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-08 | Phase 6 步驟 1，小 macro（1rw1r 8×16），本機 macOS 與 Colab | `make sky130-install` rc=0，產生時 `Custom cell pin names do not match spice file: [...] vs []` | 已驗證：`cp $?` 只複製比目標目錄新的檔案 | 規則 3（原規則 19）；`touch` 後重裝，`check_install.py` | `docs/notes/openram_phase6_bringup.md` 第 1 項 |
| 2026-10-08 | 同上 | log `ERROR: ... LVS mismatch`，rc=0 | 已驗證 | 規則 2（原規則 18）；`gen_macro.py` 讀 log 與報告 | 同上第 2 項 |
| 2026-10-08 | 同上 | 新 PDK（open_pdks `8afc834`）下 LVS 45 個 cell 不一致 | 已驗證（只換 PDK 的對照）：元件改名與萃取規則改變 | 規則 1（原規則 17）；macro 用 OpenRAM 釘的 PDK（ADR-0018 決定 5） | 同上第 3 項與兩張對照表 |
| 2026-10-08 | Colab 官方環境 | `use_nix = True` 時 `could not find a flake.nix file`；venv 缺 numpy | 已驗證 | 規則 5（原規則 21） | 同上第 4、5 項 |
| 2026-10-08 | 本機連跑兩次、本機對 Colab | 同設定 GDS 的 met2／met3／via2 不同 | 已驗證：`PYTHONHASHSEED=0` 後逐位元相同（跨平台 GDS XOR 0） | 規則 4（原規則 20） | 同上第 6 項 |
| 2026-10-08 | Phase 6 步驟 3a，OpenRAM 產生的 2 KB（OpenRAM dev，預設 words per row 4） | ss −40°C 1.60 V、ss 25°C 1.60 V、tt −40°C 1.60 V 讀成前一次的值；同一支程式跑 PDK macro 在 ss −40°C、ss 25°C 也讀錯（對照） | 已驗證（對照組重現 ADR-0010）：OpenRAM 產生的 macro 用同一套 sense amp 與純 NMOS column mux，`openram-macro-characterization` 規則 13 照樣成立 | 先試 words_per_row = 1（ADR-0018 決定 3） | `docs/notes/openram_phase6_bringup.md` 步驟 3a、`ip/sram/openram/read_check.py` |
| 2026-10-08 | Phase 6 步驟 3p1，小 macro（1rw1r 8×64、words per row 4） | 未套 patch 時 OpenRAM DRC 12（met2.2、met3.2），套 sense amp 輸入端預充電 patch 後 2；met2.2 在 y 約 19.0–19.6 µm，和 2 KB 預設版同形狀 | 已觀察兩次；原因未查 | 規則 6（原規則 22）；`macro_drc.py` 比種類，patch 版沒有新種類 | `docs/notes/openram_phase6_bringup.md` 步驟 3p1 |
| 2026-10-08 | Phase 6 步驟 3p1 | port_data 多一支 `p_en_bar` 後，bank 的 `get_pin("p_en_bar")` 報 `Should use a pin iterator since more than one pin` | 已驗證：`get_pin` 遇到同名多支接腳就出現錯誤（`compiler/base/hierarchy_layout.py:589`） | 規則 7（原規則 23）；bank 改 `get_pins()`（patch 0001） | 同上 |
| 2026-10-09 | Phase 6 步驟 3f，2 KB 1RW 試跑 | 先報 `must have an even number of cols including replica cols`；加 spare column 後 OpenRAM DRC 657、LVS 不一致（column cap 的 BL／BR 同一個 net），full 規則 DRC 多 16 種 | 已驗證（實跑一次）；原因在 OpenRAM 的 sky130 單 port layout，未往下查 | 規則 9（原規則 26）；使用者決定維持 1rw1r（ADR-0018 決定 11）；試跑的設定留在 `configs/` 供升版時重跑 | `docs/notes/openram_phase6_bringup.md` 步驟 3f、`runs/openram/arv_sram_2kbyte_1rw_32x512_8/` |
| 2026-10-10 | Phase 6 步驟 4b 第二輪 harden（SRAM 真的進了 SoC GDS） | flow 的 KLayout DRC 在 SRAM 裡報 27：nwell.6 4、psdm.1 22、m2.2 1；PDK 附的 macro 0（改名後也是 0）；OpenRAM DRC 與 Magic full 對 PDK 附的 macro 的 baseline 都沒報這幾種 | 已驗證（macro 單獨跑 KLayout、flatten 後量形狀）：保護環 path、DFF abut、tap 接點高度（規則 6（原規則 22）） | 規則 6（原規則 22）；patch 0002–0004；`macro_klayout_drc.py`、K0–K6 | 筆記步驟 4b 第二輪、3m |
| 2026-10-10 | Phase 6 步驟 3m，2 KB 重新產生（patch 0002＋0003 第一版） | OpenRAM `LVS mismatch`，最上層 `data_dff_0/clk` 另成一個 net；KLayout nwell.2a 2、nsdm.1 2 | 已驗證：DFF 陣列的 M3 clk 軌與超出邊界的 nwell／nsdm／psdm 靠 abut 相接 | 規則 6（原規則 22）（拉開要補回）；patch 0003 補洞，小 macro LVS match、KLayout 0 | 同上 |
| 2026-10-10 | Phase 6 步驟 3m，查 deck 的名稱排除 | 先以為 PDK 附的 macro 的 KLayout 0 是因為 deck 依名稱排除 SRAM cell | 已驗證（讀 deck 原文）：只有 nwell.6 無條件排除，nsdm／psdm 要 `sram_exclude=true`；PDK 附的 macro 改名後仍是 0 | 規則 6（原規則 22） 寫明排除範圍；checker 對排除樣式的名稱 FAIL（K6） | `sky130A_mr.drc` 第 299、557、639 行 |
