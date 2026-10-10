# ADR-0018：Phase 6 用 OpenRAM 自產 SRAM macro

- 狀態：已採用（2026-10-08）。四個選項由使用者在 2026-10-08 一次決定（全部採建議）。
- 範圍：用 OpenRAM 自己產生 2 KB SRAM macro 與每個 PVT 的 .lib，取代預建的 `sky130_sram_2kbyte_1rw1r_32x512_8`（ADR-0003），重跑 Phase 3–5 的 signoff。`project-plan.md` §8 Phase 6 的 exit criteria：「自產 macro DRC／LVS 結果 ≤ 預建 baseline；SoC 以自產 macro 完成 signoff」；§10 第 5 項。ADR-0010 決定 4 與已知限制 1、4 要求 Phase 6 修正讀取失敗，並在 5 個 PVT 驗證讀取正確。
- skill：`openram-macro-characterization`（Phase 3.5 建立，Phase 6 補自產 macro 的規則，CLAUDE.md 規則 7）。

## 查證結果（2026-10-08，OpenRAM、sky130_fd_bd_sram、open_pdks、sky130_sram_macros 的 clone，唯讀調查）

版本縮寫：OpenRAM stable = `b2b069ce`（2026-08-16），dev = `3608704c`（2026-10-01）。最新 release 與 PyPI 都停在 `v1.2.48`（2024-01-21）。

1. **x86_64 Linux 的限制來自打包，不是程式本身**：
   - `flake.nix:10` 的 `systems = [ "x86_64-linux" ]`；2026-04-30 起官方安裝只剩 `nix develop`（commit `cbd2bd7c` 刪掉 conda 安裝程式；`docs/source/basic_setup.md` 把 Docker 標成 deprecated）。
   - `compiler/options.py:154-156`：`use_nix = True` 是預設；關掉後「OpenRAM uses whatever tools are already in PATH」。
   - 模擬器依 Xyce → ngspice 的順序找（`compiler/characterizer/__init__.py:36`）；nixpkgs 的 Xyce 只支援 x86_64-linux。
   - OpenRAM 是純 Python（PyPI wheel 是 `py3-none-any`）。本機已有 Magic 8.3.623、Netgen 1.5.316、KLayout 0.30.7、ngspice 47（`toolchain.md`）；OpenRAM `flake.lock` 釘的是 Magic 8.3.629、Netgen 1.5.318。macOS 原生執行沒有官方支援，**能不能跑要實測**（下面計畫步驟 1）。**2026-10-08 實測可行**：小 macro 與 2 KB macro 都在本機產生；小 macro 和 Colab 官方環境的 GDS XOR 為 0（`docs/notes/openram_phase6_bringup.md`）。
   - 已知一處不相容：`compiler/verify/run_script.py:54-66` 用 GNU 才有的 `tail --pid`，只在 verbose > 1 時執行。
2. **「2 KB 約 4.4 小時」大部分是驗證**：預建 macro 的產生 log（`sky130_sram_macros@5ad1c96`）總計 15741.7 s，其中 DRC／LVS 13100 s（LVS 約 3.4 小時）、繞線 2624 s，解析模式的時序計算 1 s。
3. **預建 macro 無法完全重現**：它是 OpenRAM v1.1.15（2021-06-13）加一份額外的 technology 設定目錄（google 的 `sky130_fd_bd_sram/tools/openram/technology`，該 repo 已封存）產生的。設定檔留在 `configs/sky130_sram_2kbyte_1rw1r_32x512_8.py`（word_size 32、num_words 512、write_size 8、1rw1r，`Words per row: 4`）。自產 macro 的電路不會和預建的完全相同，Phase 3.5 的數字不能直接套用，要重量。
4. **讀取失敗的電路，自產 macro 照預設設定仍然一樣**（ADR-0010「ss −40°C 讀取失敗」）：
   - sense amp 是 sky130_fd_bd_sram 的固定 cell `sky130_fd_bd_sram__openram_sense_amp`（`technology/sky130/tech/tech.py:231`）：cross-coupled latch 加兩顆 EN 控制的 PMOS 接 BL／BR，沒有預充電或等化電晶體（`cells/openram_sense_amp/*.base.spice`，已核對）。電路最後一次修改是 2021-10。
   - column mux 是 OpenRAM 參數產生的每行兩顆 NMOS（`compiler/modules/column_mux.py:73-91`）；2023 年後 stable、dev 都沒有功能修改。
   - `words_per_row` 可在設定檔指定（`compiler/sram_config.py:18,89`）；`words_per_row = 1` 時沒有 column address，不產生 column mux（`port_data.py:235-245`），代價是陣列變成 512 列 × 32 行、bitline 長 4 倍。
   - VLSIDA/OpenRAM 的 issue 沒有低溫或低電壓讀取失敗的回報。OpenRAM 的 sky130 矽量測（ISCAS 2023，1 KB 1rw1r）只做到約 0°C。
5. **OpenRAM 的預設特性化 corner 不含 −40°C**：溫度 [0, 25, 100] °C、電壓 [1.7, 1.8, 1.9] V，一次只變一個（`technology/sky130/tech/tech.py:736-741`）。本專案的 .lib 仍用 Phase 3.5 的自寫流程（`ip/sram/char/`）在本機量，skill 規則 3 列的 OpenRAM 特性化缺陷照舊成立。
6. **GDS cell 名稱衝突的前提已過時**：OpenRAM 從 commit `229a3b5b`（2022-03-11）起在非 library cell 的名稱前加 `output_name_` 前綴（`compiler/base/hierarchy_design.py:29-33`）；open_pdks commit `18dbe61`（2025-05-11）因此拿掉 `gds_import_sram.tcl` 的改名。本機 PDK 的 2 KB GDS 有 161 個 cell，只有 10 個 `sky130_fd_bd_sram__openram_*` 沒有前綴。LibreLane 3.0.14 的 KLayout 輸出預設 `KLAYOUT_CONFLICT_RESOLUTION=RenameCell`（`librelane/steps/klayout.py:279-286`）。
7. **sky130 安裝**：`make sky130-install` 會 clone VLSIDA/sky130_fd_bd_sram（dev 釘 `fc63b12`，2026-04-22「update dp cells for new magic extraction」；stable 釘 `dd64256`），並檢查 `$PDK_ROOT/sky130A` 與 `$PDK_ROOT/skywater-pdk` 存在；`make sky130-pdk` 用 ciel 裝 2022-07-29 的 PDK（`e8294524…`）。OpenRAM 實際讀的 PDK 檔只有 `libs.tech/` 的 ngspice、magic、netgen 設定（`technology/sky130/__init__.py:23-43`）。
8. **維護狀態**：regress CI 已手動停用；維護者在 issue #262 說目前沒有人有經費維護。未解的 sky130 問題：#298（輸入 pin 的 `max_transition` 0.04 ns，OpenROAD 報 `RSZ-0090`）、#281（`use_pex=True` 萃取失敗）。

## 使用者決定（2026-10-08）

1. **執行平台：本機 macOS 原生先試，Colab 當對照**。本機設 `use_nix=False`，用已有的 Magic、Netgen、KLayout、ngspice；可行就以本機為主，另在 Colab（`google-colab-cli`，使用者 2026-10-08 指定：只能在 Linux 跑時用 Colab）裝官方 nix 環境，用同一個 commit、同一份設定產生同一顆 macro，比對網表與 LVS，排除 macOS 版工具造成的差異。本機不可行就全部改在 Colab。
2. **OpenRAM 用 dev `3608704c`**（釘 commit，不追最新）：含 dual-port bitcell 配合新版 Magic 的 LVS 修正（1rw1r 會用到）、spare column 短路修正、繞線加速。
3. **讀取失敗：先重現，再試 `words_per_row = 1`**。先用預建 macro 的設定產生，用 SPICE 確認讀取失敗同樣出現；再產生一顆 `words_per_row = 1`（沒有 column mux），5 個 PVT 都量，看結果再決定用哪一顆。
4. **規格維持 2 KB 1rw1r 32×512**：和預建 macro 相同，DRC／LVS／時序可以直接比；RTL 不改（port 1 仍接死）。（`clk1` 的接法由決定 9 修改。）
5. **（2026-10-08，步驟 1 之後）macro 的產生與 DRC／LVS 用 OpenRAM 釘的 2022 PDK（open_pdks `e8294524`），SoC flow 維持 `8afc834`**。依據（`docs/notes/openram_phase6_bringup.md`）：
   - 2022 PDK 下，本機與 Colab 官方環境的小 macro 都是 DRC 0、LVS `Circuits match uniquely`；`PYTHONHASHSEED=0` 時兩邊 GDS XOR 0。
   - `8afc834` 下 LVS 不過，原因是兩版 PDK 之間的改變：bitcell PMOS 從 `special_pfet_pass` 改名為 `special_pfet_latch`（PDK 模型檔的原文註記），`w<0.42` 的 NMOS 改萃取成 `special_nfet_01v8`；另外 bd_sram 的 dummy cell 等還有萃取差異沒查清。
   - SoC 的 LVS 照舊把 SRAM 當 black box；全晶片 Magic DRC 用 `8afc834` 對 baseline 比。
   - SPICE 特性化用 `8afc834` 的模型（和 SoC 的 STA 一致）。舊名稱的轉接 subckt 在 ngspice 報 `unknown subckt`（實測），所以網表要先把 `special_pfet_pass` 改成 `special_pfet_latch`，並由 checker 確認沒有殘留。
   - 產生 macro 一律設 `PYTHONHASHSEED=0`：不設時同一份設定連跑兩次，GDS 的 met2／met3／via2 繞線不同。
6. **（2026-10-08，步驟 2 之後）自產 macro 多出的 4 種 DRC 錯誤：先做 SPICE，選定 macro 後再修**。
   - 事實（`docs/notes/openram_phase6_bringup.md`）：整顆 GDS 的 Magic full DRC（PDK `8afc834`）自產 2,234,537、預建 2,235,078，但自產多 4 種預建沒有的錯誤，共 37 個方框：met2.2、met3.2、via2.2 繞線間距 3 處，以及 Deep N-well 保護環 nwell.5a 一圈（OpenRAM `add_dnwell` 內側只有 0.42 µm，規則 1.03 µm）。OpenRAM 自己的 DRC 只報 5（沒有 nwell.5a）。本機與 Colab 產出的 GDS XOR 為 0，所以和平台無關。
   - 現在加「整顆 full 規則 DRC、逐種類對預建 baseline」的 checker，這 4 種判 FAIL，列為已知未修。
   - 步驟 3 選定一顆 macro 後只修那一顆：保護環用 repo 內的 OpenRAM patch（`make openram-setup` 自動套用），繞線 3 處先查根因再決定做法。
7. **（2026-10-08，步驟 3a／3b 之後）用預設設定（words per row 4）並把 column mux 改成 transmission gate（PMOS＋NMOS）**，以 repo 內的 OpenRAM patch 實作（`make openram-setup` 套用）；先用小 macro 試可行性，不行再回頭考慮 wpr1。依據（`docs/notes/openram_phase6_bringup.md` 步驟 3a、3b）：
   - 預設設定：ss −40°C 1.60 V、ss 25°C 1.60 V、tt −40°C 1.60 V 讀成前一次的值，和預建 macro 相同（同一支程式的對照組重現）。
   - wpr1（沒有 column mux）：5 個 STA PVT 與 ss 25°C 1.60 V 都讀對，tt −40°C 1.60 V 只剩最後一列 bit 31 讀錯（20／30／44 ns 相同，原因未明）；但尺寸 446.99 × 1152.58 µm 放不進 1000 × 800 µm 的 die，整顆 DRC 多 latch-up tap 距離（LU.2.1、LU.3 各 80）。
   - 拿掉 column mux 就消掉主要的失敗，符合「純 NMOS column mux 讓 sense amp 內部節點只能到 VDD − Vt」的機制；transmission gate 保留形狀、針對這個機制修。
8. **（2026-10-08，網表 what-if 之後；修改決定 7 的做法）改用 sense amp 輸入端預充電**：在 `port_data` 的 column mux 與 sense amp 之間多放一排 OpenRAM 現成的 precharge cell（每個 bit 一個，接 `bl_out`／`br_out` 與同一個 `p_en_bar`），不改 column mux。依據：電路圖 what-if 中 transmission gate（W1）與這個做法（W2）都讓 ss −40°C 1.60 V、ss 25°C 1.60 V、tt −40°C 1.60 V 讀對（`docs/notes/openram_phase6_bringup.md`）；W2 重用既有模組、不動選擇線，版圖改動較小。仍以 repo 內的 OpenRAM patch 實作。
9. **（2026-10-08，步驟 3p2 之後）SRAM 的 `clk1` 改接系統時脈，`csb1=1`、`addr1=0` 不變**；SPICE 特性化的激勵同步改成 `clk1` 與 `clk0` 同波形。依據（`docs/notes/openram_phase6_bringup.md` 步驟 3p2「根因」）：
   - OpenRAM 的 `control_logic_r` 用 `clk1` 上升邊緣把 `csb1` 鎖進 DFF 得到 `cs`，`wl_en = (NOT clk) AND cs`，沒有 reset。`clk1` 恆為 0 時 DFF 從不鎖存，`cs` 停在上電值；落在 1 時 port 1 某一列的 wordline 一直開著、port 1 bitline 不預充電，port 0 寫該列可能失敗。預建 macro 是同一套電路（`sky130_sram_2kbyte_1rw1r_32x512_8.spice` 的 `control_logic_r`）。
   - 套 patch 0001 的 2 KB 在 tt 25°C 讀錯 3 筆就是這個原因（SPICE 的 DC 解落在 `cs=1`）；只把 `clk1` 改成打時脈（E2）就 7 筆全對。
   - RTL 改動放在步驟 4a，和換 macro 一起重新 harden，避免 Phase 5 的 golden 在中間對不上。
10. **（2026-10-09，步驟 3c 期間）SRAM 的 internal_power 用 SPICE 量**：3c 之後，用同一套 ngspice 流程量 VDD 電流，分讀、寫、閒置（`csb0=1`）三種情況，換算成每次時脈邊緣的能量寫進 .lib，取代解析值（OpenRAM dev 寫成 1.036316e+11；預建 macro 的 13.8 也只是不分條件的解析估計，ADR-0007 限制 3）。
    - **（2026-10-09）方法：修剪網表加外插，完整網表校一次**。修剪網表只有 bit 0、31 的 column 掛滿 128 顆 cell，直接量會低估 bitline 的能量與漏電；用兩種修剪（保留 2 個 bit 與 4 個 bit 的完整 column）量同一個序列，以每個 bit 的差值外插到 32 bit（讀寫只用第 0、127 列，wordline 負載兩種修剪都完整）；漏電同樣外插。另外在 tt 用完整網表跑一次，量外插的誤差，記進本 ADR。完整網表 ngspice 光讀檔就超過 35 分鐘（skill 規則 4），5 個 PVT 都用完整網表不實際。（漏電的量法由決定 11 修改；修剪＋外插由決定 12 取消。）
11. **（2026-10-09，步驟 3e、3f 之後）維持 1rw1r；.lib 的漏電用標準待機狀態量，port 1 閒置造成的靜態電流列為已知限制，1RW 留到之後**。依據（`docs/notes/openram_phase6_bringup.md` 步驟 3e「漏電」與 3f）：
    - port 1 永遠不選（`csb1=1`）時，`p_en_bar1 = NAND(clk_buf AND cs1, rbl_bl_delay)` 恆為 1，port 1 的 bitline 與 sense amp 輸入端沒有任何電路驅動。tt 模擬中 port 0 動作後，32 顆 port 1 sense amp 有 13 顆輸出反相器的輸入停在 0.75 V，上下同時導通，約 0.2 mW；是哪幾顆由網表與動作歷程決定，兩種修剪的結果互換，外插得到負值（−2.8 mW）。這只影響功耗，port 1 的輸出不接，SoC 只用 port 0（ADR-0003）。
    - .lib 的 `cell_leakage_power`：`csb1=0`、最後一個週期是 port 0 讀取，兩個時脈在它的上升邊緣之後停在高電位，兩個 port 都在 precharge、沒有 wordline 打開（SRAM 規格書的待機狀態）；tt 兩種修剪 0.00044／0.00045 mW，一致。動態能量照決定 10 量；靜態電流（含上述穿透電流）只用來扣除，另記在 `power.json`（扣除方法由決定 12 修改）。
    - 改成 1RW 可以從源頭去掉 port 1，但用釘住的 OpenRAM 試產（3f）：sky130 單 port array 要求資料 column 加 replica column 為偶數，要加 1 個 spare column（多出 `spare_wen0` 與 din0／dout0 各 1 bit）；OpenRAM 自己的 DRC 657、LVS 不一致（column cap `sp_colend`／`sp_colenda` 把每個 column 的 BL、BR 接成同一個 net，上游 `ec28bc6d`「correcting col_cap pin order」已在本版本內）；整顆 Magic DRC 多 16 種預建 macro 沒有的規則。上游測試清單（`compiler/tests/Makefile` 的 `BROKEN_STAMPS`）也把 sky130 單 port 的 bank／SRAM layout 測試都列為壞掉。要用 1RW 得先修補 OpenRAM，工作量無法預估。
    - 使用者 2026-10-09 選擇維持 1rw1r，1RW 留到下一顆設計或上游修好後再評估。
12. **（2026-10-09，步驟 3e 正式量測之後；修改決定 10、11 的做法）讀寫能量扣「局部基準」，5 個 PVT 都用完整網表，不外插**。依據（`docs/notes/openram_phase6_bringup.md` 步驟 3e「正式量測」）：
    - port 1 浮接造成的靜態電流會隨動作改變，不是固定的（修剪網表 tt b4：讀寫期間 0.08 mW、時脈停住後 0.003 mW；ff 100°C：0.4 升到 2.7 mW）。決定 11 用時脈停住後的值整段扣除，ff 100°C 的讀寫能量變成負值，tt 每個邊緣多算約 1 pJ。決定 11 寫「它從第一個邊緣起就固定」是只看一次節點電壓得到的推論，沒有用電流驗證過，是錯的。
    - 局部基準：每個邊緣窗口扣「窗口起點前與終點前各 3 ns 靜止電流」連成的直線（以兩段的中點內插）。用同一批波形重算：5 個 PVT 都是正值、兩種修剪一致，tt 外插對完整網表的誤差從最大 11% 降到 4.2%。
    - 外插會把雜訊放大 15 倍（ff −40°C read_fall 的 b4 比 b2 少 0.1 pJ，外插 −21%），漏電外插比完整網表少 54%（原因未查）。完整網表實測：讀寫 deck 約 86 分鐘、漏電 deck 約 36 分鐘（7 個模擬同時跑時），比決定 10 估的可行。
    - 使用者 2026-10-09 選擇：局部基準；5 個 PVT 都用完整網表（`make openram-power`，同時 4 個）。
13. **（2026-10-10，步驟 3e；修改決定 12 的漏電做法）bitcell 用 `.ic` 給初始值；漏電改用「修剪網表的待機 deck ＋ 單顆 bitcell 漏電 × 被拿掉的顆數」；讀寫能量仍用完整網表**。依據（`docs/notes/openram_phase6_bringup.md` 步驟 3e「半穩態 bitcell 與快速量法」）：
    - 完整網表 ss −40°C 的漏電量測窗裡功率突然上升（0.5 µW → 尖峰 0.2 mW → 0.28 µW）。根因（已驗證）：沒被寫過的 bitcell 在 ngspice 的 DC 工作點得到 `Q = Q_bar`（0.64 V）的平衡解，低溫時過很久才倒向一邊。處理：每顆 bitcell 用 `.ic` 設 `Q=0`、`Q_bar=VDD`（`sramchar.bitcell_ic()`，數量必須等於網表的 bitcell 數），N20。
    - 完整網表的漏電 deck 每個 PVT 要 0.5–5 小時，3e 在完整網表上依序遇到四個問題、每次整套重跑，拖了兩天。改成相加：修剪網表（保留 2 個 bit，1264 顆 bitcell）的待機 deck，加上單顆 bitcell 待機 deck（幾秒）× 15120；兩種修剪（2 bit／4 bit）的總和差 2–2.5%，不放大雜訊（決定 12 的外插是相減）。
    - 使用者 2026-10-10：「一顆2KB SRAM不可能要搞兩天」；選快速量法，並要求新方法先在修剪網表跑完所有 corner（skill 規則 27）。當時也選了用 DC 工作點量漏電（取代暫態量測窗），實作後不可行，由決定 14 取代。
14. **（2026-10-10，步驟 3e；DC 工作點不可行）漏電維持暫態量測窗（時脈停住後 60–80 ns），平穩度判準加絕對門檻：前後半差超過 5% 時，只放行「往下降、降幅 ≤ 10 nW」（`power.LEAK_FLAT_ABS`），往上升一律 FAIL**。依據（筆記步驟 3e「DC 工作點」「長時間停住」「絕對門檻」）：
    - DC 工作點（暫態到停住狀態，所有節點當 `.nodeset` 再算 `.op`）：Newton 從 nodeset 出發直接疊代不收斂（疊代上限 2000、加分流電阻、從 `.ic` 固定後的 DC 解出發都一樣），ngspice 退回 gmin stepping 或 transient op，DFF 與控制訊號翻掉，電流 1.8–9.6 µA 隨設定跳（暫態 0.25 µA），解不唯一；用 `.ic` 固定節點則把 µV 級的差放大成 1.4 mA。
    - ss −40°C 量測窗不平（6.0%）的原因：讀寫動作把 295 個節點耦合到地以下（dummy row cell 內部節點、NAND 串聯中間節點，最低 −0.36 V），低溫時靠接面漏電慢慢回升，漏電往下降：停住 300 ns 時修剪 deck 從 77 降到 50 nW，仍在降。延長暫態：放寬步長在停住 20 ns 後與 100 ps 步長差 0.5–1.7%，但 Newton 失敗反覆把步長砍到約 8 ps，2 µs 跑超過 30 分鐘未完。
    - 使用者 2026-10-10 先選延長暫態，看到成本後改選：「改用第二個選項，量測窗加絕對門檻」；並要求「要把這個選擇的原因寫到OpenRAM裡面」（寫在本決定與 skill `openram-macro-characterization` 規則 25）。
    - 門檻 10 nW：ss −40°C 實測降幅 4.6 nW 的 2 倍（使用者選項舉例 5 nW，離實測值太近，重跑雜訊可能在 PASS／FAIL 之間跳）。只放行下降，因為下降時量到的值偏高（保守），上升時偏低。N20 加三個案例（下降 4.6 nW PASS；上升 4.6 nW、下降 25 nW 必須 FAIL）。
    - 這個門檻只保證「量測窗內」的方向；窗後的緩慢變化看不到（見已知限制：tt 25°C 往上升）。
15. **（2026-10-10，步驟 3e；修改決定 13 的單顆 bitcell deck）單顆 bitcell 的漏電 deck 用 `gmin=1e-17`，並用 1e-18 再跑一次核對（差 > 1% 就 FAIL）；修剪網表的 deck 維持 ngspice 預設 gmin，−40°C 的偏差列為已知限制**。依據（筆記步驟 3e「gmin」）：
    - 單顆 bitcell 漏電 ÷ VDD² 在 ff −40°C、ss −40°C、tt 25°C 都是 13.1 pS（42.7 pW＠tt），不隨溫度變：是 ngspice 在每個 pn 接面並聯的 `gmin`（預設 1e-12 S），不是電晶體漏電（gmin 1e-17：tt 0.53 pW、ss −40°C 0.21 pW）。× 15120 顆後 .lib 漏電高估：tt 2.4 倍、ss 100°C 1.4 倍、ff −40°C 4 倍、ss −40°C 7 倍；ff 100°C 幾乎不變（真正的漏電 556 pW 蓋過 gmin）。1e-17 與 1e-18 在 5 個 PVT 都差 < 0.2%，1e-15 時 ss −40°C 仍多 16%。
    - 修剪網表的 deck 兩份都改 1e-15 時：tt −1%、ss 100°C −3%、ff 100°C 不變、ff −40°C −32%（23 分鐘，其他 5–8 分鐘）、ss −40°C `Timestep too small` 跑不完。
    - 使用者 2026-10-10 先問「先看問題是不是都是-40」「我目前看來都是-40有問題」；看到收斂問題只在 −40°C、gmin 高估在 4 個 PVT 之後選：「好，照選項 1 做，-40 寫進已知限制」。
    - 新增 checker `power.cell_gmin_problem()`（`bitcell leakage depends on gmin`）與 negative test N21（拿掉 gmin 設定的單顆 deck 必須 FAIL；植入「checker 永遠 PASS」時 N21 FAIL）。
    - 快速量法對完整網表（skill 規則 27 的「驗證一次」）：完整網表用預設 gmin，只有 gmin 影響可忽略的 ff 100°C 能比——完整網表舊波形（`runs/.../power/full/ff_100C_1v95/leak`，量測窗前後半差 0.24%）404.30 µW，快速量法 409.14 µW，+1.2%。其他 corner 的完整網表值含 16384 顆 × gmin，不能當參考。
    - 結果（`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/char/power.json`）：整顆漏電 tt 462 nW（原 1099）、ss 100°C 1256（1760）、ff −40°C 252（999）、ss −40°C 81（584）、ff 100°C 409.1 µW（409.9）。

## 計畫

0. skill `openram-macro-characterization` 補自產 macro 的一節；本 ADR；`project-plan.md` §8、§11 與 `toolchain.md` 更正。
1. 本機試跑：小規格 macro（例如 16×32）在 macOS 產生到 GDS／LEF／網表，DRC、LVS 能跑；同時在 Colab 試裝官方 nix 環境。
2. 用預建 macro 的設定產生 2 KB 1rw1r，跑 DRC、LVS，和預建 baseline（DRC 32、LVS match）比；Colab 產生同一顆比對。
3. SPICE（`ip/sram/char/`）：自產網表的讀取正確性在 5 個 PVT（加上 ss 25°C 1.60 V），確認失敗是否重現；產生 `words_per_row = 1` 版本重做；選定一顆後量 5 個 PVT 的時序、產生 .lib、植入錯誤與確認模擬。
4. 換進 soc_top（Hazard3 與 PicoRV32）：LEF／GDS／.lib／行為模型、antenna LEF（ADR-0008）、`hard-macro-integration` 清單；harden、criteria review、下游驗證、bug injection、重建 golden、乾淨 checkout 兩輪 regress。
5. 獨立審查、exit review、經驗寫回 skill。

## 已知限制

- macOS 原生沒有官方支援（決定 1 用 Colab 對照來處理）。
- 自產 macro 和預建的不是同一顆電路（查證 3）；「≤ 預建 baseline」比的是同規格的數量，不是逐項相同。
- Phase 5 結案的 SoC（預建 macro，`clk1=1'b0`）有決定 9 的上電風險，不追溯修改；以步驟 4 的版本取代。
- 自產 macro 的 .lib：OpenRAM dev 寫出的 internal_power 是 1.036316e+11（數量級錯誤，根因未查），特性化範本改用預建 macro 的值 13.8（`ip/sram/openram/lib_template.py`）；兩者都是解析值，IR drop 分析的 SRAM 電流仍不可信（ADR-0007 限制 3）。時序的公式與下限沿用 ADR-0010（padded.lib 的下限是預建 macro 的假設值）。
- `words_per_row = 1` 的形狀與時序未知，可能放不進現在的 floorplan（die 1000 × 800 µm，ADR-0006）。
- port 1 閒置時浮接的 sense amp 會漏出穿透電流（決定 11），.lib 的 `cell_leakage_power` 不含它：tt 模擬量到約 0.2 mW（13/32 bit），32 bit 全部出現時估計約 0.5 mW（由 13 bit 的電流按比例推算，未模擬）；各 PVT 量到的值在 `ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/char/power.json` 的 `static_mw`。SoC 的功耗估計要另外加上它。實際晶片上這些節點的電壓由漏電與耦合決定，模擬無法準確預測。
- 1RW macro 在釘住的 OpenRAM 版本無法產生 DRC／LVS 乾淨的 layout（決定 11）。
- .lib 的 `cell_leakage_power` 不是穩態值（決定 14、15；絕對值都 < 1 µW，ff 100°C 409 µW 除外，對 SoC 功耗估計沒有實際影響）：
  - tt 25°C 可能**偏低** 26% 以上：修剪 deck 停住 342 ns 時 0.571 µW，量測窗（142–162 ns）0.454 µW，仍在上升（最後每 20 ns 約 +0.8%），穩態值未知。使用者 2026-10-10 選擇寫成已知限制。
  - ss −40°C 偏高：量測窗之後仍在下降（停住 300 ns 時修剪 deck 50 nW，窗內 77 nW）。
  - −40°C 的修剪 deck 用預設 gmin 偏高：ff −40°C 約 48%（246 對 166 nW）；ss −40°C 用小 gmin 跑不完，偏差未知。
  - 20 ns 量測窗看不出緩慢漂移（窗內 tt 只升 2.5%、ss −40°C 300 ns 時窗內只差 1.6%），平穩度 checker 只能抓窗內的階躍與明顯斜率。
  - 修剪 deck 換 gmin 時，1264 顆保留的 bitcell 照單顆結果應少約 54 nW（tt），實際只少 4.3 nW，原因未查。
- OpenRAM 產生的 .lib internal_power 數量級錯誤，上游另有回報且未修（VLSIDA/OpenRAM issue #294，2026-04-30 open：sky130 224 byte 1rw 寫成 1.034875e+10、1 KB 寫成 4.603410e+10；較早的 #157「Internal power is super large」2022 已關閉）。
