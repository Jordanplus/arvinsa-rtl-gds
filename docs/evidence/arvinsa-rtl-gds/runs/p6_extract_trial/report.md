## 報告檔沒寫成
`report.md` 沒有寫出來：執行環境擋下了 subagent 寫報告檔（Write 回 `Subagents should return findings as text, not write report files`）。我沒有改用 Bash 繞過這個限制。完整報告在下面，要存檔請貼到 `<claude-session-tmp>/scratchpad/p6extract/report.md`。

## 重點
1. **萃取做完了**：Magic 8.3.623 加 flow PDK（open_pdks `8afc834`）萃取出貨 GDS，含對地與 coupling 電容，花 31.6 分鐘、峰值 0.4 GB。另外用了 OpenRAM 自己做 LVS 時萃取的無寄生網表；它和出貨 GDS 只差檔頭時間戳記。
2. **無寄生萃取網表**：4 個 PVT 讀寫全對，延遲比電路圖慢 6–8%。
3. **含寄生的階層式網表重現了 Phase 3.5 的失敗**，訊息：`doAnalyses: TRAN:  Timestep too small; time = 2.19037e-09, timestep = 1.25e-22: trouble with node "vwm2#branch"`。
4. **根因（已用前後比較確認）**：Magic 的階層式輸出（`ext2spice hierarchy on`）在上層 subckt 放負值電容，用來修正 cell 重疊處重複算的電容。結果未修剪網表有 263 個節點的總電容是負的，例如 `port_data_0/bl_127` −108 fF；修剪後增加到 995 個。同一份網表只拿掉負值電容，就能跑過第一個 clock 邊緣。平面輸出（`hierarchy off`）沒有負值電容，可以直接模擬。
5. **含寄生的讀取延遲約是電路圖的 2 倍**：tt 25°C 1.80 V 讀寫正確，settle 5.32 ns，電路圖 2.67 ns（+100%）。.lib 加在延遲上的 ×1.6 走線餘量蓋不住這個差距；現在是 .lib 的下限（tt 10 ns、ss 15 ns）在保護。
6. **ss −40°C 1.60 V 在 20 ns 週期判 FAIL，但讀出的值是對的，只是太晚**：讀出值在下降緣後 10.86–10.91 ns 才到，比 10 ns 的低電位半週期長，所以取樣點還是 0 V。這不是以前「讀到前一次的值」那種錯（電路圖是 5.37 ns，約 +103%）。
7. **沒跑到**：ss 25°C 1.60 V、tt −40°C 這兩個含寄生的 PVT（平面網表每個要 32 分鐘），限時內排不進去。
8. 寫入在所有萃取網表都正確（寫進去的值都讀回來了），Phase 3.5 已知限制 4 的寫入失敗沒有出現。
9. repo 沒動、沒有 commit、沒在 `runs/` 建檔。`git status` 看到的 `arvinsa-rtl-gds-flow.md`、`scripts/progress.py` 修改不是我做的。

---

# 報告：自產 SRAM 版圖萃取網表的讀寫正確性試跑（ADR-0018 決定 19，限時 3 小時）

2026-10-11 13:02 開始，15:30 停止模擬。macro 是 `arv_sram_2kbyte_1rw1r_32x512_8`（`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/openram/`）。
工作目錄是 `<claude-session-tmp>/scratchpad/p6extract/`，以下寫成 `p6extract/`。

## 1. 結論

- **萃取**：用 Magic 從出貨 GDS 萃取，做了三種輸出：階層式無電容、階層式含電容（有 coupling 與沒有 coupling 兩版）、平面式含 coupling。另外直接拿 OpenRAM 做 LVS 時萃取的網表當無寄生版本；它的 GDS 與出貨 GDS 只差檔頭 12 個 byte（GDS 時間戳記，`cmp -l` 確認）。
- **無寄生萃取網表**：tt 25°C 1.80 V、ss −40°C 1.60 V、ss 25°C 1.60 V、tt −40°C 1.60 V 都讀寫正確，延遲比電路圖慢 6–8%。
- **含寄生、平面網表**：
  - tt 25°C 1.80 V 讀寫正確，延遲約是電路圖的 2 倍（+100%）。
  - ss −40°C 1.60 V 讀出的值正確，但在下降緣後 10.9 ns 才到；20 ns 測試週期的低電位半週期只有 10 ns，所以 checker 判 FAIL。這是讀出時間不夠，不是讀錯值。
- **含寄生、階層式網表**：重現 Phase 3.5 的 `Timestep too small`。根因是階層式輸出的負值電容讓部分節點總電容為負。證據是同一份網表只拿掉負值電容就能跑過，而平面輸出沒有負值電容。
- **對下線風險的含意**（推測，根據 .lib 數字，沒有在 SoC 上驗）：
  - 出貨 .lib 的 falling_edge 延遲：tt 是 10 ns 下限，ss −40°C／ss 100°C 是 15 ns。萃取量到的 5.3 ns（tt）與 10.9 ns（ss −40°C）都還在這之內。
  - 但 ADR-0010 的「×1.6 走線餘量」不夠。它的依據是只換 bitcell 的試驗（+48%）；整顆版圖萃取是 +100%。
  - hold 那一側（上升緣到 dout0 開始變化）萃取值比電路圖晚（tt：1.67 ns 對 1.16 ns），.lib 用電路圖值 ×0.9，偏保守、仍成立。

## 2. 方法

- 所有模擬都用 repo 的 `ip/sram/char`（`sramchar.py`、`characterize.py`，沒有修改）：
  - 激勵是 `characterize.delay_seq(pvt, clk slew 0.2 ns, load 0.02 pF)`，就是 `read_check.py` 用的序列：週期 20 ns；先寫 511／508／3／0，再讀 7 次；`clk1` 與 `clk0` 同波形，`csb1=1`。
  - checker 是 `sramchar.check_reads`：在下一個上升緣前 0.05 ns 檢查 32 bit，1 要 ≥ 0.8 VDD，0 要 ≤ 0.2 VDD。
  - 延遲用 `characterize.delay_metrics`，只量 bit 0 與 31。
- 修剪和電路圖相同：保留第 0、127 列，以及 bit 0、31 的 8 個 column，共 1264 顆 bitcell。
- 電路圖對照：用 `runs/openram/read_check_clk1_self/read_check_work/<pvt>/delay_s0.2_l0.02/wave.txt` 重算。該次網表 sha256 `368c74be…` 等於出貨的 `.sp`，改名後的 `netlist.spice` 也逐位元相同（`1b02740b…`），所以沒有重跑電路圖。
- 驅動腳本是 `p6extract/sim_ext.py`，它呼叫 repo 的函式。另外加了這些處理：
  - **幾何單位**：Magic 的 `ngspice(si)` style 寫 SI 單位（`w=0.21u`），PDK 的 `.option scale=1e-6` 會把它縮成 1e-12。沒轉換時 ngspice 報 `could not find a valid modelname`。轉成 µm／µm² 後就正常了。
  - **修剪**：`trim_extracted` 的副本，只拿掉「至少要改名一個節點」的檢查，因為無電容網表沒有 substrate 節點，原版會報 `trim_extracted: FAIL - no substrate or dropped-cell net renamed in the top cell`。
  - **修剪後的負值修正電容**：bitcell 陣列裡每條 bl／br／wl 的負值修正電容，依保留顆數比例縮小。
  - **只接電容的節點**：top cell 的 `VSUBS` 接到 `vssd1`。一個浮接的 metal2 節點 `control_logic_r_0/m2_2798_0#` 經 1 TΩ 接地。
- 平面網表另用 `p6extract/flattrim.py` 修剪，用階層網表查 cell 對應的列與行。被修剪 column 上只接 drain 的 NMOS（62400 顆）也拿掉，否則 ngspice 解析 96654 顆元件 13 分鐘都還沒開始模擬。

| 代號 | 網表 | 寄生 |
|---|---|---|
| sch | 電路圖 `.sp` | 無 |
| orlvs | `runs/openram/arv_sram_2kbyte_1rw1r_32x512_8/tmp/arv_sram_2kbyte_1rw1r_32x512_8.spice`（OpenRAM 做 LVS 時萃取，2022 PDK 的 tech） | 無 |
| cn | 本次階層式萃取，`ext2spice hierarchy on` | 對地電容 9798 顆，其中 9229 顆是負值 |
| cc | 本次階層式萃取 | 對地＋coupling 電容 80862 顆，其中 11799 顆是負值 |
| ccpos | cc 拿掉全部負值電容 | 偏大，用來確認根因 |
| flat | 本次萃取，`ext2spice hierarchy off` | 449746 顆，沒有負值；修剪後 389518 顆電容、34254 顆元件 |

## 3. 結果

延遲單位 ns，從 clk0 下降緣量起。settle 是 .lib 採用的「進入有效電位」時間的最大值，d50 是到 50% 的時間，括號內是和同一 PVT 電路圖的差。

| PVT | 網表 | 讀寫 | settle | d50 | 上升緣→dout 開始變化（最小） | 模擬時間 |
|---|---|---|---|---|---|---|
| tt 25°C 1.80 V | sch | 對 | 2.666 | 2.511 | 1.158 | — |
| | orlvs | 對 | 2.879（+8.0%） | 2.762（+10.0%） | 1.181 | 6.6 分 |
| | ccpos | 對 | 5.457（+104.7%） | 5.338（+112.6%） | 1.781 | 16.7 分 |
| | **flat** | **對** | **5.324（+99.7%）** | **5.193（+106.8%）** | 1.667 | 32.4 分，2.2 GB |
| | cc | 停在 2.19 ns，`Timestep too small` | | | | 7.8 分 |
| | cn | DC 工作點失敗（singular matrix） | | | | 5 分 |
| ss −40°C 1.60 V | sch | 對 | 5.370 | 5.210 | 2.765 | — |
| | orlvs | 對 | 5.731（+6.7%） | 5.572（+6.9%） | 2.845 | 6.2 分 |
| | **flat** | **7 次讀取都判 FAIL；讀出值正確但晚到** | 約 10.86–10.91（約 +103%）＊ | | | 32 分，2.3 GB |
| ss 25°C 1.60 V | sch | 對 | 5.325 | 5.184 | 2.429 | — |
| | orlvs | 對 | 5.704（+7.1%） | 5.553（+7.1%） | 2.510 | 5.6 分 |
| tt −40°C 1.60 V | sch | 對 | 3.438 | 3.330 | 1.596 | — |
| | orlvs | 對 | 3.643（+6.0%） | 3.531（+6.1%） | 1.636 | 6.2 分 |

＊ ss −40°C 平面網表從波形量到的：

```
cycle 4 r511: fall 92.25 next rise 102.25 | b0:exp1 vmax=1.60 t80=10.86; b31:exp0 vmax=0.00; b2:exp1 vmax=1.60 t80=10.86
cycle 5 r508: ... b31:exp1 vmax=1.60 t80=10.86; b1:exp1 vmax=1.60 t80=10.91
cycle 10 r508: ... b31:exp1 vmax=0.54（波形在 222.75 ns 結束）
```

應該是 1 的 bit 在下降緣後 10.86–10.91 ns 到達 0.8 VDD，應該是 0 的 bit 一直是 0 V。值是對的，但晚於 10 ns 的低電位半週期，checker 原文是 `cycle 4 r511: expected 0x5a5aa5a5, wrong bits 0:0.00V 2:0.00V ...`，7 次讀取都一樣。

## 4. 卡住的地方與確切訊息

1. **單位錯**：`Error on line 654 ... could not find a valid modelname`。原因是 `ngspice(si)` 的 SI 單位碰上 PDK 的 `scale=1e-6`；轉換單位後解決。
2. **cn 的 DC 工作點失敗**：`Warning: singular matrix:  check node xsram.arv_sram_2kbyte_1rw1r_32x512_8_control_logic_rw_0/.../pnand3_0/z`，gmin stepping 與 source stepping 都失敗，`No. of Data Rows : 0`。原因是 ext2spice 把上層的修正電容寫到子 cell 內部節點的名稱上，但那個節點不是子 cell 的 port，所以接不到真正的 net。這樣的節點共 3791 個，只接電容，沒有 DC 路徑。cc（有 coupling）沒有這個現象。
3. **cc 的 DC 工作點**：`singular matrix: check node ..._control_logic_r_0/m2_2798_0#`，dynamic gmin stepping 失敗。這是 read port 控制邏輯裡一段浮接的 metal2（3.3 fF）。經 1 TΩ 接地後，工作點靠 dynamic gmin stepping 收斂（約 6.5 分鐘）。這段浮接金屬本身沒有追查。
4. **cc 的暫態**：`doAnalyses: TRAN:  Timestep too small; time = 2.19037e-09, timestep = 1.25e-22: trouble with node "vwm2#branch"`，停在第一個上升緣（2.125–2.375 ns），和 ADR-0010 已知限制 3 相同。
   - 試過的選項：deck 原本就有 `.options method=gear reltol=1e-3`。時間不夠，沒有逐一試 `reltol`、gmin、`uic`；改走根因路線。
   - 根因，已用前後比較確認：`p6extract/capsum.py` 把電容攤平後算每個節點的總電容。cc 未修剪有 263 個節點為負，例如 `bank_0/port_data_0/bl_127` −107.9 fF、`bl_20` −77.5 fF、`w_en0` −36.0 fF；修剪後 995 個為負。拿掉負值電容（ccpos）後同一 deck 能跑完；平面輸出沒有負值電容，也能跑完。
   - 推測：Phase 3.5 的 PDK macro 萃取（`extract_sram.py` 用階層式）是同一個原因，沒有回去驗證。
5. **平面網表解析太慢**：96654 顆元件時 ngspice 解析 13 分鐘沒有進入模擬（RSS 177 MB），我中止了。拿掉被修剪 column 上只接 drain 的 NMOS 後剩 34254 顆，讀檔加工作點約 11 分鐘、暫態約 21 分鐘。
6. **工具小問題**：Magic 的 Tcl 沒有 `clock` 指令（`invalid command name "clock"`），script 在 `extract all` 之後就結束了。`.ext` 已經產生，所以另外寫了只做 ext2spice 的 script 補跑，每次約 1.5 分鐘。

## 5. 指令與輸出原文

- **萃取**：

  ```
  cd .tools/librelane && PDK_ROOT=~/.ciel nix-shell --run "/usr/bin/time -l magic -dnull -noconsole -rcfile ~/.ciel/sky130A/libs.tech/magic/sky130A.magicrc p6extract/ext/extract.tcl"
  ```

  - script 內容：`gds flatglob *_?mos_m*`、`gds flatten true`、`gds read`、`load`、`extract style ngspice(si)`、`extract do capacitance`、`extract do coupling`、`extract no resistance`、`extract unique all`、`extract all`。
  - 輸出：`Using technology "sky130A", version 1.0.530-0-g8afc834`，`Total of 5 warnings.`，`1894.26 real`，`422133760 maximum resident set size`。
  - 沒有 coupling 的版本：`p6extract/ext2/extract.tcl`，215 s。
- **輸出網表**：`p6extract/ext/e2s.tcl`（`ext2spice hierarchy on`、`cthresh 0.01`，產生 `cap_coupling.spice`），以及 `p6extract/ext/e2s_flat.tcl`（`hierarchy off`，產生 `flat_cap_coupling.spice`，270 MB，54 s）。
- **準備網表**：`python3 sim_ext.py prep ext/cap_coupling.spice cc/trimmed.spice` 的輸出：

  ```
  trim: renamed 60480 substrate/dropped-cell nets in the top cell to vssd1
  floating capacitor-only nodes: 35713 VSUBS lines of the top cell tied to vssd1
  scaled 1569 negative bitcell-array corrections
  trimmed kept 1264 dropped 15120
  ```

  平面網表：`python3 flattrim.py ext/flat_cap_coupling.spice ext/cap_coupling.spice flat/trimmed.spice` 的輸出是 `kept 1264 of 16384 cells; 181440 device lines commented out`。
- **模擬**：`python3 sim_ext.py run <net>/trimmed.spice <pvt> <net>/<pvt> --timeout 2400`，一次只跑一個（`p6extract/queue.sh`），完整紀錄在 `p6extract/queue.log`。每個 run 的 `result.json`、`ngspice.log`、`deck.sp`、`wave.txt` 在 `p6extract/<net>/<pvt>*/`；失敗的 cc tt 保留在 `cc/tt_025C_1v80/`。

## 6. 建議下一步（附估計時間）

1. **補 ss −40°C 的讀取正確性判定**（約 1 小時）：同一份平面網表把測試週期拉長到 40 ns（`delay_seq` 的 `period`），重跑 ss −40°C；再把 ss 25°C 1.60 V、tt −40°C 1.60 V 跑完。每個約 35 分鐘，必須依序跑。
2. **改萃取方式**（約 1 小時，要交給你決定，屬於 CLAUDE.md 規則 13 的分岔）：`extract_sram.py` 和之後的萃取都改用平面輸出加平面修剪，或者在階層式輸出後檢查「節點總電容為負」並判 FAIL。另外要補 negative test：植入一個負值修正電容，確認 checker 抓得到。
3. **重新檢討 .lib 的 ×1.6 走線餘量**（約半天）：要先選 A 或 B，選項請你決定。
   - A：用平面萃取網表重新量 5 個 STA PVT 的延遲。
   - B：把餘量改成依萃取結果推導的值（約 ×2.1–2.2，再加上量測誤差）。
   - 目前 .lib 的下限（10／15 ns）仍蓋住萃取值，對現有 harden 沒有立即影響。這一點是推測，還要在 SoC 的 43 ns 週期下確認半週期仍夠。
4. **寫回 skill**（約 30 分鐘）：寫到 `openram-macro-characterization` 的經驗紀錄，內容是本次的症狀、根因、繞過方式與證據。這次限定不能動 repo，所以沒有寫。
5. **浮接金屬**（約 30 分鐘）：查 `control_logic_r_0/m2_2798_0#` 是什麼，看 KLayout deck 的浮接金屬檢查有沒有報。

## 7. 檔案（都在 `p6extract/`）

- `sim_ext.py`、`trimlib.py`、`flattrim.py`、`capsum.py`、`queue.sh`、`queue.log`、`sch_metrics.txt`
- `ext/`：本次萃取。`extract.log`、`cap_coupling.spice`、`flat_cap_coupling.spice`、`nocap.spice`，以及 `.ext` 檔（在 `ext/work`）
- `ext2/`：沒有 coupling 的萃取
- 模擬結果：`orlvs/`、`cn/`、`cc/`、`ccpos/`、`flat/`
- 總共 1.4 GB
