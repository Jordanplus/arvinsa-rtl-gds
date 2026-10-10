---
name: openram-macro-characterization
description: SRAM macro（OpenRAM 產生的預建 macro 或自產 macro）的時序要用 SPICE 實測、產生多 corner 的 .lib 時使用：判斷廠商 .lib 是不是解析模型、macro 在低溫或 ss 低電壓（室溫也會）讀出前一次的值（sense amp 沒有預充電、column mux 只有 NMOS）與不能動的 corner 怎麼給佔位 .lib、換上新 .lib 後 repair_design 跑很久或異常結束（延遲表的負載斜率）、用 ngspice 量 clk→dout 延遲與 dout 在上升緣後被拉回的時間、setup/hold、最小週期與 pulse width（搜尋範圍不涵蓋真值時怎麼往外找）、網表修剪與模擬步長怎麼驗證、從 GDS 萃取寄生電容（Magic）、OpenRAM 自己特性化的缺陷、量測結果怎麼寫成 .lib 並用植入錯誤證明量得對（含不 import 產生器的獨立重算、在 .lib 採用值上的確認模擬、模擬快取與量測 JSON 的檢查），以及 ngspice 讀大網表很慢、完整網表平行跑時每一步慢 10–40 倍且 CPU 只有約 64%（記憶體不夠在壓縮，要先算每個 run 約 4.2 GB 再決定平行數）、bus 節點名稱報 bad v() syntax、萃取網表報 singular matrix 或 Timestep too small 這類問題。用 OpenRAM 自產 macro 時的平台（官方 nix 環境只有 x86_64-linux、use_nix 關掉改用本機工具）、重現預建 macro、words_per_row 與讀取電路、GDS cell 名稱前綴，以及 OpenRAM 的 LVS 用新 PDK 報 Netlists do not match（special_nfet_01v8、special_pfet_latch 與 special_pfet_pass）、log 有 ERROR 但 exit 0、sky130-install 後報 Custom cell pin names do not match spice file、同一設定兩次產生的 GDS 不同（PYTHONHASHSEED）、use_nix 時 could not find a flake.nix file。OpenRAM 的 DRC 只報 WARNING 且不是 full 規則（met2.2、met3.2、via2.2 繞線間距，Deep N-well 保護環 nwell.5a 漏報），用 patch 修改 OpenRAM（Should use a pin iterator since more than one pin），以及 OpenRAM dev 的 .lib internal_power 大到 1e9–1e11（gen_char_lib 報 internal_power outside (0, 1000]）要換掉才能當範本、用 SPICE 量 internal power 與漏電時漏電隨網表改變或外插成負值（沒用到的 port 浮接，sense amp 上下同時導通；漏電要在所有 port precharge、時脈停在高電位的待機狀態量；它會隨動作改變，讀寫能量要扣局部基準，不能整段扣同一個值；不要用兩種修剪網表的差值外插功耗，漏電用修剪網表加單顆 bitcell 漏電乘顆數）、漏電量測窗裡功率突然上升或 power.py 報 leakage window not settled（沒寫過的 bitcell Q 與 Q_bar 相同、停在半穩態，要用 .ic 給初始值；低溫時節點被耦合到地以下、漏電一直緩降，量測窗加只放行下降的絕對門檻）、想用 DC 工作點（.nodeset 加 .op）量漏電時報 doAnalyses out of memory、KLU mode cannot create a new element、Nodeset on non-existent node 或走 dynamic gmin stepping 後鎖存器翻掉（不要用 DC 工作點）、bitcell 漏電幾乎不隨溫度變而且漏電除以 VDD 平方跨 corner 相同或 power.py 報 bitcell leakage depends on gmin（ngspice 的 gmin 蓋過漏電，單顆 bitcell deck 用 gmin 1e-17 並以 1e-18 核對；大 deck 調小 gmin 在低溫報 Timestep too small）、完整網表一份 deck 跑好幾小時而且一再重跑（新量測方法要先在修剪網表跑完所有 corner、checker 都 PASS，完整網表只驗證一次），以及 sky130 1RW 單 port macro 報 must have an even number of cols including replica cols、加 spare column 後 DRC 與 LVS 失敗（column cap 的 BL、BR 接在一起）。macro 怎麼放進設計看 hard-macro-integration，餘量怎麼定看 signoff-criteria。Use for SPICE characterization of SRAM macros (ngspice + sky130), per-corner Liberty generation, netlist trimming, parasitic extraction and OpenRAM characterizer pitfalls.
---

# SRAM macro 的 SPICE 特性化與 .lib

macro 整合清單看 `hard-macro-integration`；量到的數字要加多少餘量看 `signoff-criteria`；corner 清單看 `multicorner-sta`。本 repo 實例：ADR-0010、`ip/sram/char/`（腳本與方法）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`（結果）；自產 macro：ADR-0018、`ip/sram/openram/`（`make openram-setup`、`make openram-macro`、`make neg-openram`）。

名詞：
- **特性化（characterization）**：用電路模擬量出 macro 的延遲、setup/hold、最小週期等，寫成 STA 讀的 Liberty（.lib）。
- **解析模型（analytical model）**：OpenRAM 不跑 SPICE、用公式（Elmore RC 估算）算出的 .lib。
- **修剪（trim）**：模擬時只保留記憶體陣列的第一／最後一列，以及被量測的 bit（0、31）所在的全部行，其他 bitcell 拿掉（sky130 2 KB：每個 bit 4 行共 8 行，16384 → 1264 顆）；被量測的 bit 那條 bitline 與 wordline 的負載完整。

## 規則（已驗證）

1. **先判斷廠商 .lib 是不是 SPICE 量的**。OpenRAM 解析模型的特徵：
   - macro 的產生 log 寫 `Analytical model enabled`、`Characterization is disabled`；
   - 延遲表每一列相同（不隨 input slew 變）；
   - `minimum_period` = 最大延遲 × 2 × 1.85（OpenRAM `compiler/characterizer/elmore.py`）。
   sky130 PDK 內附 `libs.ref/sky130_sram_macros/lib/` 的全部 .lib（含 `sram_1rw1r_32_256_8_sky130` 的 SS／FF 檔）都是這種，最小週期 0.091–1.956 ns，不可用於 signoff。
2. **量 macro 隨附的網表**（`libs.ref/sky130_sram_macros/spice/`，與 GDS 同一顆電路），不要用 OpenRAM 重新產生的電路代替（OpenRAM 版本不同，電路可能不同）。先確認網表自足：bitcell 等 subckt 都有定義，用到的元件都在 PDK 模型裡。sky130 SRAM 用 `special_nfet_latch`、`special_pfet_latch`、`special_nfet_01v8`，它們隨 corner 變的參數在 `libs.tech/ngspice/corners/<c>/specialized_cells.spice`，要用 `.lib sky130.lib.spice <corner>` 整段載入。
3. **OpenRAM 自己的 SPICE 特性化（`-c`）不能直接當 signoff 依據**（VLSIDA/OpenRAM `stable` 的 `compiler/characterizer/`）：
   - setup/hold 只模擬輸入端那顆 DFF，沒算 macro 內部 clock buffer；只在第一個 corner 量，其他 corner 沿用；clock 的 slew 沒有施加。
   - `cell_rise`／`rise_transition` 用 fall 的值覆蓋（`delay.alter_lh_char_data`）。
   - `min_pulse_width` 直接取 `min_period / 2`。
   - 預設不含走線 RC（`use_pex=False`）；不測兩個 port 同時存取。
4. **ngspice＋sky130 的設定與速度**：
   - 把 PDK 的 `libs.tech/ngspice/spinit` 複製成工作目錄的 `.spiceinit`（`ngbehavior=hsa`、KLU）。
   - ngspice-47 讀 2 KB macro 的完整網表（約 15 萬顆 MOSFET）時，光是解析元件（`INP2M`）就超過 35 分鐘還沒開始模擬。早期試跑的修剪（bitcell 16384 → 508）讀檔加模擬 440 ns 共 7 分鐘；正式版保留 1264 顆（見名詞「修剪」）。
   - 修剪的結果要和完整網表在同一個量測點比對一次再採用。
   - 完整網表平行跑之前先算記憶體：2 KB 完整網表每個 ngspice 約 4.2 GB（電路本身），超過實體記憶體時系統一直壓縮／解壓縮記憶體，每個時間點慢 10–40 倍，CPU 只吃到約 64%，看起來像卡住。24 GB 的機器同時跑 3 個時每 2 分鐘約 170 個時間點，5 個時只有 13–31 點（已驗證，2026-10-09）。怎麼發現：`top -l 1 -stats pid,command,mem,cmprs` 的 CMPRS、`vm_stat` 的 Compressions 短時間內大增。另外 deck 要用 `save` 只存要寫出的向量（電壓源電流寫成 `<名稱>#branch`；`sramchar.deck(save_only=True)`），否則 ngspice 存下每個節點的每個時間點，記憶體隨時間增加。
   - 長模擬的進度看 `ngspice.log` 的 `Reference value`（目前模擬到的時間；檔案是成批寫入，會落後一些）。
5. **`.tran` 的 TSTEP 會壓住最大步長**：`.tran 10p` 跑 33 分鐘，`.tran 100p` 跑 7 分鐘，延遲差 1.8%（TT 2.348 vs 2.305 ns）。換步長要用小步長的結果驗證一次，並把誤差記下來算進餘量。
6. **ngspice 控制語言的兩個陷阱**：
   - 節點名稱有 `[ ]`（bus）時，`wrdata v(dout0[31])` 報 `bad v() syntax`（`[ ]` 被當成向量索引）；用 `E` 電壓源接到沒有括號的節點名稱再輸出。
   - `meas tran ... TARG ... FALL=1` 從 t=0 起算，不是從觸發點之後；要加 `TD=<觸發時間>`。
7. **OpenRAM SRAM 的 dout 在每個有效週期（`csb=0`）的上升緣後約 1 ns 就被拉回 0**，讀 1 時要到下降緣之後才升上來（sky130 2 KB、TT：上升緣後 1.02–1.29 ns 拉低，下降緣後 2.2–2.3 ns 讀出 1）。
   - 廠商 .lib 只有 `falling_edge` 一條弧，STA 以為資料保持到下一個下降緣；接收端 flop 的 clock 比 macro 的 clock 晚到約 1 ns 就會抓錯，STA 卻不會報。
   - .lib 要加一條 `rising_edge` 弧，最小延遲取上升緣到 dout 開始變化的時間，讓 STA 對接收端做 hold 檢查。
   - 行為模型的 `T_HOLD`（上升緣後 1 ns 把 dout 設成 X）模擬的就是這件事。
8. **從 GDS 萃取寄生（Magic）**：
   - 沒設 `PDK_ROOT` 時 magicrc 找不到 tech 檔，Magic 仍然 exit 0 而且沒有輸出；腳本要檢查輸出檔存在，不能只看 exit code。
   - 2 KB macro 的電容萃取（`extract do capacitance`、`extract do coupling`、`ext2spice cthresh 0.01`）花 26 分鐘、1.4 GB 記憶體，產生 7.9 萬顆電容；bitcell 的特殊元件都能正確辨識。

9. **setup/hold 要在整顆 macro 上量，不能只量輸入那顆 DFF**：macro 內部的 clock buffer 讓 DFF 晚一點才抓資料，所以 pin 上的 setup 變小（可為負）、hold 變大。sky130 2 KB、TT：setup −0.16～−0.22 ns、hold +0.20～+0.24 ns；PDK 解析模型（OpenRAM 只量 DFF）寫 setup 0.103、hold −0.056，hold 少算約 0.3 ns。量法：在測試週期把一組輸入的轉態時間往前或往後移，用寫入再讀回的資料判斷新值或舊值，二分搜尋（`ip/sram/char/characterize.py` 的 lanes）。
10. **Magic 萃取的 SRAM 網表不能直接模擬**（sky130 2 KB，Magic 8.3.623，`ext2spice lvs` + `cthresh 0.01`）：
    - 每顆 bitcell 的儲存節點被當成 port 一路傳到最上層，在最上層是一般網路，並有電容接到基板網路 `<...>/VSUBS`；
    - VSUBS 沒有接任何元件（只接電容），直流工作點會 singular；
    - 修剪掉的 bitcell，其儲存節點也變成浮接；
    - 做法：在最上層把 VSUBS 與被修剪 cell 的儲存節點都改名成地（`sramchar.trim_extracted`）。改完之後仍有其他只接電容的金屬網路（例如 `control_logic_r_0/m2_2554_0#`），要加 `.options rshunt=1e12`。

11. **量測方法要先驗證誤差，再用植入錯誤證明腳本量得對**（sky130 2 KB，TT；`ip/sram/char/`）：
    - 誤差來源逐一比對：模擬步長（100 ps 對 10 ps）、修剪對完整網表、UIC 對直流工作點、延遲表只模擬十字 5 點時四角的推算。四項都要偏保守的方向，數字寫進 ADR。方向要對 .lib 實際用的那個量逐一判斷：sky130 2 KB 的讀出穩定時間四項都偏保守，但 dout 開始變化（hold 弧）在延遲表兩個 5 fF 角偏晚 0.5–1.0%，是樂觀的方向，要由 hold 弧的係數（× 0.9）涵蓋（2026-10-05 獨立審查）。
    - 和完整網表或小步長比對時，記下比的是哪個量、用的是哪一版修剪網表；換了修剪範圍要重比。
    - 植入錯誤至少涵蓋：延遲變大（sense amp 加電容）→ 量到的延遲必須變大；bitcell 卡住 → 讀出檢查 FAIL；搜尋的「移動轉態時間」失效 → 必須報錯而不是給一個數字；網表數量、JSON 缺項、.lib 被手改 → FAIL／STALE（`make neg-char`）。
    - 植入的字串要先確認在檔案裡找得到、而且改到預期的次數；否則植入什麼都沒做，測不到要測的東西（N6 第一版：`--check` 判沒有過期，N6 FAIL，見經驗紀錄）。
12. **.lib 的時序弧要和實測行為對得上**：dout 在上升緣後會變化（規則 7），所以除了 `falling_edge` 弧還要 `rising_edge` 弧；接進 SoC 後要有 negative test 證明 STA 真的用到它（本 repo 的 P32：把它設成 0，hold 必須 FAIL）。
13. **每個 PVT 先證明讀寫正確，再量時序**（sky130 2 KB，PDK 網表；ADR-0010「ss −40°C 讀取失敗」）：
    - sense amp 沒有自己的預充電、靠只有 NMOS 的 column mux 從 bitline 拉回內部節點時（OpenRAM 的 sky130 cell 就是這樣），低溫或慢製程會拉不回滿 VDD，連續兩次讀取的值不同時讀成前一次的值。STA corner 只有 −40°C 與 100°C 時，中間溫度要另外模擬（sky130 在 ss 25°C 也失敗）。
    - sky130 的實例（機制、失敗與正常的條件、電路圖實驗確認有效的修法）：`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` S25。
    - 整理多組條件的結果時，每一列都寫完整的製程、溫度、電壓。ss 25°C 1.60 V（全部 bit 錯）曾和 ss 25°C 1.80 V（只有修剪的 bit 錯）混在一起，漏列了室溫失敗（獨立審查發現）。
    - 測試序列要有「連續讀取不同值」的讀取，否則看不到這個錯；每個 PVT 先跑一次，有錯就只記下錯的讀取（`read_fail`），不量時序。
    - 不能動的 PVT 仍要給 STA 一份 .lib（`hard-macro-integration` 第 5 項）：用同製程、能動的 PVT 的數字，hold 弧取所有 PVT 最早的值，檔頭寫明 PLACEHOLDER；並列為下線風險。
    - 修剪後只剩 2 顆 bitcell 的 bitline 電容太小，會讓這個錯更早出現（ss 25°C 1.80 V、ss 60°C 1.60 V 只有這些 bit 錯），判斷時要看完整 bitline 的那幾個 bit。
14. **.lib 延遲表的負載斜率會被 OpenROAD 當成 driver 的強度**（sky130 2 KB；ADR-0010「延遲表為什麼不隨負載變化」）：
    - 讀出穩定時間是 dout 進入有效電壓範圍的時刻，不是 RC 延遲，會隨負載跳動（ss 100°C 5 → 20 fF 跳 1.3 ns）。直接寫進表裡，等於 60–140 kΩ 的 driver。
    - 這樣的表讓 `repair_design` 停不下來：同一份輸入單步重跑，卡在第 9000 個 driver 之後；加大輸出 pin 的 `max_transition` 沒用；延遲表與 hold 弧表一起在負載方向攤平後 52–98 秒完成（差別是機器負載；沒有分開測是哪一張表）。插在輸出 net 上是推論（`sample` 看不到 net 名稱）。
    - 做法：每列（clock slew）取負載中的最大延遲、hold 弧取最小值，`max_capacitance` 設成特性化過的最大負載。產生 .lib 後先用單步重跑 `OpenROAD.RepairDesignPostGPL` 確認時間正常，再跑完整流程（`librelane-run-debug` 規則 3）。
15. **搜尋範圍不涵蓋真值時，往外一次多測幾點，不要整個重新二分**（`ip/sram/char/characterize.py` 的 `bisect`）：
    - 其他 PVT 的搜尋以 tt 結果為中心，但 ss 的高、低電位時間與週期比 tt 大 1 ns 以上，ff 的低電位時間與週期小 1 ns 以上，都在範圍外。
    - 舊做法每往外移一次範圍就從頭二分 6 輪（每輪約 50 分鐘，約 5 小時）；ss 的最小週期若往外移 3 次，將近 20 小時。
    - 現在的做法：二分縮到解析度後，某一側（FAIL 或 PASS）還沒看到，就在那一側一次模擬 `EXTEND_POINTS`（2）個點、涵蓋一個初始寬度，最多 `MAX_EXTEND`（3）次，仍看不到就報錯；看到之後在最近的 FAIL 與 PASS 之間接著二分。結果不單調（大的值 FAIL、小的值 PASS）也報錯。clock 的高、低電位時間不探測到 `PULSE_FLOOR`（0.4 ns）以下。
    - 改搜尋法之前，先用假的模擬器（給定真值的函式）比對新舊版：範圍內的探測點完全相同，所以已跑完的模擬可以直接沿用。
16. **產生 .lib 的程式本身也要有 checker，而且要獨立於它**（2026-10-05 獨立審查找到 9 個漏洞，Phase 5 開頭修；`ip/sram/char/`）：
    - `--check` 只比「同一支程式的輸出」，公式寫錯（取最大與取最小弄反、少乘係數）照樣一致。另寫一支不 import 產生器的程式，從量測 JSON 重算 .lib 的每個數字再比對（`check_char_lib.py`），用改壞公式的產生器（M1–M5）證明抓得到（N12）。
    - 測試用的假資料每格要不同、部分高過下限：每格相同又全被下限蓋過時，公式錯誤產生的 .lib 一模一樣（N5–N8 原本的 `fake_doc`）。
    - 量測 JSON 是 regress 不會重跑的信任起點：檢查每筆紀錄是它的 PVT、數值有限且 pass > fail 不超過解析度（NaN 經 `max()` 會變成下限），以及來源欄位（網表 sha256、PDK 版本、ngspice 版本、修剪數、步長與搜尋設定，N9–N11）。
    - 二分搜尋只在探到的點檢查單調：最後要在 .lib 採用的值上各跑一次確認模擬，全部讀寫正確（`confirm_char_lib.py` → `confirm.json`，N14）。
    - 模擬快取：只有 log 沒有錯誤、波形涵蓋到 `.tran` 結束時間才重用；讀出檢查的時間點超過波形結尾要報錯（`value_at` 超過結尾會回傳最後一個值，N15）。
    - 有 PVT 失敗就不寫量測 JSON，避免新舊紀錄混合（N16）。
    - 範本替換的次數要每支 pin、每個 rise／fall 分開數（N13）。

17. **用 OpenRAM 產生 macro 時，DRC／LVS 用 OpenRAM 自己釘的 PDK**（sky130：OpenRAM Makefile 的 `SKY130_CIEL`；本 repo 實例 ADR-0018 決定 5、`docs/notes/openram_phase6_bringup.md`）。
    - 症狀：用較新的 PDK 跑 OpenRAM 的 LVS，`Final result: Netlists do not match.`，連最簡單的 `pinv` 都不一致：萃取出 `sky130_fd_pr__special_nfet_01v8`、電路圖是 `sky130_fd_pr__nfet_01v8`；bitcell 萃取出 `special_pfet_latch`、cell 的 LVS 網表是 `special_pfet_pass`；`special_nfet_latch (12->10) **Mismatch**`。
    - 根因（只換 PDK 的對照實驗）：PDK 改了元件名稱與萃取規則，OpenRAM 的固定 cell 庫還是舊名稱（sky130 的改名細節：`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` S26）。只移植 OpenRAM stable 的窄 NMOS 修正、或只改 PMOS 名稱，都還不夠。
    - 怎麼發現：OpenRAM log 的 `LVS mismatch`，以及 LVS 報告各 cell 的 `Subcircuit summary`。
    - 繞過：產生與 DRC／LVS 用 OpenRAM 釘的 PDK；SoC flow 照舊用 flow 的 PDK（SRAM 在 SoC LVS 是 black box）。
    - SPICE 用新 PDK 的模型時，網表要先把舊元件名稱改成新名稱：PDK 留的舊名稱轉接 subckt，ngspice 報 `unknown subckt`（實測；`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` S26）。本 repo 由 `read_check.py` 改名並確認沒有殘留。
    - 防復發：LVS 不一致由產生腳本判 FAIL（`gen_macro.py`，`neg-openram` O2）。網表改名的 checker 在 Phase 6 步驟 3 建立。
18. **OpenRAM 在 DRC／LVS 失敗時 exit code 仍是 0**，GDS、LEF、.lib 照常輸出。
    - 症狀：log 第一行 `ERROR: file magic.py: line 387: <name>	LVS mismatch (results in /tmp/.../<name>.lvs.report)`，`sram_compiler.py` rc=0。
    - 怎麼發現與防復發：產生腳本讀 log 的 `ERROR` 行、DRC 報告的 `Total DRC errors found:`、LVS 報告的 `Final result:`，三項都要有且合格才 PASS（`gen_macro.py` `judge()`，`neg-openram` O1–O8）。只看 exit code 等於沒檢查。
    - DRC 錯誤只記成 `WARNING: file magic.py: line 254: DRC Errors <name>\t5`，不是 `ERROR`；所以只讀 `ERROR` 行不夠，要讀 DRC 報告的數字（sky130 2 KB 實例）。
    - DRC／LVS 報告預設放在 `/tmp/openram_<user>_<pid>_temp/`，結束時刪掉。設定檔寫 `keep_temp = True` 可以保留；要指定位置得用環境變數 `OPENRAM_TMP`。設定檔裡的 `openram_temp` 不會生效，也不報錯：`read_config` 只採用 `OPTS` 還沒有的鍵（`compiler/globals.py:361`），而 `openram_temp` 在啟動時就設好了。
19. **OpenRAM 的 `make sky130-install` 會少複製 cell，而且 exit 0**。
    - 症狀：之後產生 macro 時 `Custom cell pin names do not match spice file: ['BL0', 'BR0', 'BL1', 'BR1', 'WL0', 'WL1', 'VDD', 'GND'] vs []`。
    - 根因（已驗證）：Makefile 用 `cp -va $?` 複製，`$?` 只含比目標目錄新的檔案；`technology/sky130/gds_lib` 等目錄在 OpenRAM checkout 時就存在，比後來 clone 的 cell 庫新，所以 260 個 cell GDS 一個都沒複製。
    - 繞過：安裝前 `touch` cell 庫的全部檔案（`ip/sram/openram/setup.sh`）。
    - 防復發：安裝後逐一確認 cell 庫的 GDS 與 SPICE 都在 OpenRAM 的 `gds_lib`／`sp_lib`（`check_install.py`，`neg-openram` I1–I4；產生 macro 前也會檢查）。
20. **同一份設定要產生相同的 macro，必須固定 `PYTHONHASHSEED`**。
    - 症狀：同一份設定連跑兩次，GDS 的 met2、met3、via2 不同（KLayout XOR），網表與 LEF 只有輸出順序不同。
    - 根因（已驗證）：Python 的 hash 隨機化影響繞線的走訪順序。設 `PYTHONHASHSEED=0` 後連跑兩次逐位元相同；不同機器（macOS Python 3.14、Colab Linux Python 3.13）的 GDS XOR 也是 0，網表排序後相同。
    - 繞過與防護：產生腳本一律設 `PYTHONHASHSEED=0`，並在 `summary.json` 記錄每個產出檔的 sha256。重產比對 sha256 的 checker 要等第一顆正式 macro 有基準值再加；目前沒有自動防護。
    - GDS 不能直接比 sha256：檔頭的 BGNLIB 與每個 cell 的 BGNSTR 都記錄產生時間（sky130 2 KB 兩次產生差 948 個位元組，KLayout XOR 為 0）。比對 GDS 要用 XOR，或先把時間戳記清掉；LEF、SPICE、Verilog 可以直接比 sha256。
21. **OpenRAM 的官方環境（`nix develop`）在已經進入 devShell 時，`use_nix` 要關掉**。
    - 症狀：預設 `use_nix = True` 時，`Unable to find the total error line in Magic output`；`<name>.drc.err` 是 `does not contain a 'flake.nix' ... could not find a flake.nix file`。
    - 根因（已驗證）：`use_nix = True` 會在暫存目錄裡為每個工具再包一層 `nix develop`，那裡沒有 flake。
    - 另外，官方 devShell 只建一個空的 venv（`compiler/.venv`），要自己 `pip install -r requirements.txt`，否則報 `No module named 'numpy'`。
    - 繞過：設 `use_nix = False`，工具仍是 devShell 的版本；本 repo 的產生腳本一律附加這個設定。
22. **OpenRAM 自己的 DRC 不夠：繞線會留下金屬間距錯誤，而且它不用 full 規則**（sky130；本 repo 實例 ADR-0018 決定 6、`docs/notes/openram_phase6_bringup.md`）。
    - 症狀：OpenRAM log `WARNING: file magic.py: line 254: DRC Errors <name>\t<n>`（不是 `ERROR`），錯誤是 met2.2（< 0.14 µm）、met3.2（< 0.3 µm）、via2.2 間距；同一個 met2.2 形狀（y 約 19.0–19.6 µm）在 2 KB 預設版與 8 bit × 64 word 小 macro 都出現（兩次）。根因沒有查證。
    - 另外，整顆 GDS 用 Magic `drc style drc(full)` 才看得到的錯誤，OpenRAM 的 DRC 不報：sky130 2 KB 的 Deep N-well 保護環內側不夠（nwell.5a），兩版 PDK 的 full 規則都抓得到，OpenRAM 的 DRC 沒有（規則數值：`signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md` S27）。
    - 怎麼發現與防復發：整顆 GDS 跑 full 規則 DRC，逐種類和預建 macro 比（`macro_drc.py`，`neg-openram` D1–D3）。bitcell 陣列本身就有大量 SRAM 特殊規則的「錯誤」（sky130 2 KB 約 220 萬，S27），只比總數看不出新問題，要比「種類」。
    - 繞過：還沒有（ADR-0018 決定 6：選定 macro 後再修）。
23. **改 OpenRAM 只能用 repo 內的 patch，並檢查工作樹恰好是「釘選 commit＋patch」**（本 repo 實例 `ip/sram/openram/patches/`、`check_install.py` 的 `tree_problems()`）。
    - 只看「HEAD 是釘選 commit、沒有修改」會擋掉合法的 patch；只看「有套 patch」又抓不到多改或少套。做法：用暫時的 git index 分別算出「釘選 commit＋patch」與「工作樹的追蹤檔案」的 tree，比對兩個 tree 的雜湊；沒進版控的安裝檔（cell 庫）不影響判斷。
    - 防復發：`neg-openram` T1（patch 以外的修改）、T2（patch 沒套）、T3（HEAD 不是釘選 commit）。產生 macro 的 `summary.json` 記錄 patch 檔名與 sha256。
    - OpenRAM 的 `get_pin()` 遇到同名接腳有兩支時會報 `Should use a pin iterator since more than one pin`；加同名控制接腳（例如第二支 `p_en_bar`）時，上一層要改用 `get_pins()` 逐一連接。
24. **OpenRAM dev 的解析 .lib，internal_power 的數量級是錯的，不能直接當範本**（OpenRAM dev `3608704c`，sky130；本 repo 實例 ADR-0018、`ip/sram/openram/lib_template.py`）。
    - 症狀：自產 macro 的 `<name>_TT_1p8V_25C.lib` 裡，`clk0`／`clk1` 的 12 個 `rise_power`／`fall_power` 全是同一個值，而且在 1e9–1e11（2 KB 1.036316e+11、2 KB words per row 1 9.966369e+10、8×16 1.098946e+09）；預建 macro（OpenRAM v1.1.15）同位置是 13.8。其他內容（腳位、電容、面積、port 1 解析時序）和預建 .lib 同結構、數值合理。根因沒有查（`compiler/characterizer/elmore.py` 的 `analytical_power` 之後）。
    - 為什麼要管：.lib 範本的 power 會原樣進每一份 .lib，SoC 的 IR drop 分析用它當 SRAM 電流（`pdn-ir` 規則 4）。
    - 怎麼發現：產生 macro 時的 view QA 就會 FAIL（`check_macro_views: FAIL ... internal_power 1.036316e+11 outside (0, 1000]`，`make openram-macro` 第二步，`hard-macro-integration` 清單第 0 項）；拿它當特性化範本時 `gen_char_lib.py` 也會報 `template ...: internal_power ... outside (0, 1000]`。
    - 繞過：`lib_template.py` 把範本的 internal_power 換成預建 macro 同一腳位、同一 `when` 的值，其他文字一字不改（`make openram-lib-template`）。兩者都是解析值，仍不可信（ADR-0007 限制 3）。
    - 防復發：`gen_char_lib.power_problems()`（範本的 power 必須在 (0, `POWER_MAX`]），`neg-openram` L1（OpenRAM 原始值當範本）、L2（兩份 .lib 的 power 項目對不上）。
    - 上游也有人回報同一件事，目前仍未修（VLSIDA/OpenRAM issue #294，2026-04-30）。量測值取代範本的做法見規則 25。
25. **SRAM 的漏電要在待機狀態量；沒用到的 port 會浮接，它的靜態電流另外記**（sky130 2 KB 1rw1r 自產，port 1 `csb1=1`；本 repo 實例 ADR-0018 決定 11、`docs/notes/openram_phase6_bringup.md` 步驟 3e）。
    - 症狀：序列結束、時脈停住後量到的「漏電」隨網表小改而變（修剪的 bit 不同、串一個 0 V 電壓源量電流），兩種修剪誰大誰小會互換，外插到 32 bit 出現負值（−2.8 mW）；電流集中在閒置 port 的 `port_data`。
    - 根因（已驗證：sense amp 節點的電壓探針、待機狀態的對照）：OpenRAM 的 control logic 只在該 port 被選中時 precharge（`p_en_bar = NAND(clk_buf AND cs, rbl_bl_delay)`）。從不選的 port，bitline 與 sense amp 輸入端沒有電路驅動（`EN=0` 時隔離 PMOS 導通，`dint_bar` 接到浮接的 `br_out`），在第一個時脈邊緣就被另一個 port 的動作耦合到中間電壓，sense amp 輸出反相器上下同時導通（tt 13/32 bit，0.2 mW）。是哪幾顆由網表與動作歷程決定，所以不能外插。
    - 做法：.lib 的 `cell_leakage_power` 另跑一份 deck 量：所有 port 都選中、最後一個週期是讀取、時脈在它的上升邊緣之後停在高電位（precharge 開、wordline 關，即 SRAM 規格書的待機狀態），量測窗離停住的邊緣夠遠。SoC 實際接法下的靜態電流只用來從動態能量扣除，另外記錄並寫進已知限制，因為實際晶片上這些節點的電壓由漏電與耦合決定，模擬無法準確預測。
    - 量測窗的平穩度判準用「相對差，加上只放行下降的絕對門檻」（使用者 2026-10-10 選擇；本 repo 實例 ADR-0018 決定 14，`power.unsettled()`）：
      - 為什麼：低溫時讀寫動作把部分節點耦合到地以下（dummy row cell 內部、NAND 串聯中間節點，sky130 ss −40°C 最低 −0.36 V），靠接面漏電回升要 µs 等級，漏電一直緩降；只用相對差會讓絕對值很小的 corner FAIL。
      - 只放行下降：下降時量到的值偏高（保守），上升時偏低。門檻取實測降幅的約 2 倍，離實測值太近會讓重跑在 PASS／FAIL 之間跳。
      - 限制：短量測窗看不出緩慢漂移（sky130 tt 窗內只升 2.5%，200 ns 後多 26%），平穩度 checker 只抓得到窗內的階躍與明顯斜率；.lib 漏電不是穩態值要寫進已知限制。
      - 延長暫態不是好的替代：停住後 Newton 反覆失敗把步長砍到約 8 ps，放寬步長上限也只到平均約 0.7 ns，sky130 2 KB 修剪網表 2 µs 跑 30 分鐘以上。
    - 不要用 DC 工作點（`.nodeset` ＋ `.op`）量 SRAM 的待機漏電（ngspice-47＋KLU，sky130 2 KB 修剪網表，已驗證）：
      - 症狀：`doAnalyses: out of memory` 與 `KLU mode cannot create a new element. Please specify an existing element for .nodeset`（nodeset 指到電壓源直接驅動的頂層節點）；`Nodeset on non-existent node`（元件內部節點，名稱含 `#`）。濾掉這些之後 `.op` 跑得完，但 log 出現 `Starting dynamic gmin stepping` 或 `Transient op started`：直接疊代沒收斂，退回的方法把 DFF 與控制訊號翻掉，電流隨設定差 3 個數量級。
      - 怎麼發現：比對 DC 解與暫態最後狀態的每個節點（接近電源或地的節點要在同一邊），並看 log 有沒有上面兩個 Note。
      - 繞過：用暫態量測窗（上一項）。用 `.ic` 固定節點也不行：µV 級的差經強驅動器放大成 mA。
      - 防復發：沒有自動防護（目前的流程不用 DC 工作點）；要再嘗試時先做上面的逐節點比對。
    - 扣除要用局部基準：每個邊緣窗口扣「窗口起點前、終點前各一段已靜止的電流」連成的直線（以兩段的中點內插，取在邊界上會落後半段）。這個靜態電流會隨動作改變（tt 讀寫期間 0.08 mW、時脈停住後 0.003 mW；ff 100°C 0.4 升到 2.7 mW），用時脈停住後的值整段扣，ff 100°C 的讀寫能量變成負值（已驗證，ADR-0018 決定 12）。
    - 量功耗不要用兩種修剪網表的差值外插：外插把雜訊放大（2 bit → 32 bit 是 ×15，0.1 pJ 的差變成 −21%），漏電外插比完整網表少 54%。讀寫能量用完整網表量（2 KB 一份讀寫 deck 約 86 分鐘）。漏電改用相加：修剪網表的待機 deck（周邊電路與保留的 bitcell）加上「單顆 bitcell 的待機漏電 × 被拿掉的顆數」，單顆 bitcell 的 deck 只有幾秒（bitline 接 VDD、wordline 接地，`power.cell_deck()`）；這樣量的是電路本身，不是兩個網表的差，雜訊不會被放大。採用前要和完整網表的結果比對一次（規則 27）。
    - 不要為了消除它把閒置 port 改成每個週期都讀取（`csb1=0`）：每個週期多一次讀取的能量（2 KB tt 約 11 pJ），而且 port 0 寫同一列時另一個 port 的 wordline 也開著，可能寫不進去。要去掉它得改用沒有該 port 的 macro（規則 26）。
    - 防復發：每個量測值必須是有限值且 ≥ 0（`power.py` 的 `record_problems()` 與 `gen_char_lib.power_record_problems()`，`neg-char` N17）；已知答案測試 `neg-char` N19 的靜態電流在整段模擬中上升 100 倍，植入「整段扣時脈停住後的值」「漏電量測窗包含停住的邊緣」「不扣靜態電流」都 FAIL。
26. **sky130 1RW（單 port）macro 在釘住的 OpenRAM dev 產不出 DRC／LVS 乾淨的 layout**（OpenRAM dev `3608704c`；本 repo 實例 ADR-0018 決定 11、`docs/notes/openram_phase6_bringup.md` 步驟 3f）。
    - 症狀：`ERROR: file sky130_replica_bitcell_array.py: line 30: must have an even number of cols including replica cols; you can add a spare col to fix this`（資料 column 加 replica column 是奇數，例如 128＋1）。加 `num_spare_cols = 1` 後可以產生，但 OpenRAM 的 DRC 657（log 是 `WARNING: ... DRC Errors`）、`ERROR: file magic.py: line 387: ... LVS mismatch`；`.lvs.json` 中 column cap（`sp_colend`／`sp_colenda`）的 `bl`、`br` 接到同一個 net，gnd／vdd 對調；整顆 full 規則 DRC 多出預建 macro 沒有的種類（繞線類 `met1.1`、`met1.2`、`met2.2`、`met3.2`、`mcon.1`、`nwell.5a`）。上游 `compiler/tests/Makefile` 的 `BROKEN_STAMPS` 把 sky130 單 port 的 bank／SRAM layout 測試都列為壞掉；上游 `ec28bc6d`「correcting col_cap pin order」已在這個版本內，問題仍在。
    - 怎麼發現：`gen_macro.py` 的 `summary.json`（DRC 數、LVS 結果，規則 18）；LVS 不一致時讀 `tmp/<name>.lvs.json`，只看 `badnets`／`badelements` 非空或元件、net 數不同的子電路（大部分子電路只是 vdd 被拆成幾個 net，不是真正的差異）。
    - 繞過：用 1rw1r macro、只用 port 0，port 1 的 `clk1` 接系統時脈、`csb1=1`（ADR-0018 決定 9），並照規則 25 量漏電。不改 OpenRAM 的單 port layout（要修補 column cap 的接線與繞線 DRC，工作量無法預估）。
    - 防復發：產生腳本對 DRC／LVS 判 FAIL（`gen_macro.py`，`neg-openram` O1–O8）。OpenRAM 換釘選 commit 時重跑 `ip/sram/openram/configs/arv_sram_2kbyte_1rw_32x512_8.py`，DRC、LVS 都 PASS 才考慮改用 1RW。

27. **新的量測方法先在修剪網表上把所有 corner 跑過、所有 checker 都 PASS，才上完整網表；完整網表只用來驗證一次**（使用者 2026-10-10；本 repo 實例 ADR-0018 決定 13、`docs/notes/openram_phase6_bringup.md` 步驟 3e）。
    - 為什麼：2 KB 完整網表一份 deck 要 0.5–5 小時、約 4.2 GB（規則 4）。3e 在完整網表上依序發現四個問題（扣除方法、平行數造成記憶體抖動、系統記憶體不足停掉工作、半穩態 bitcell），每個都要整套重跑，前後拖了兩天；這四個在修剪網表上幾分鐘到半小時就看得到（半穩態 bitcell 在修剪網表 ss −40°C 28 分鐘就出現）。
    - 做法：(1) 修剪網表跑 5 個 corner，量測值、讀值檢查、平穩度等 checker 全部 PASS；(2) 有 corner 的數值和其他 corner 的趨勢不合，先查清楚；(3) 完整網表只跑一次，和修剪網表的結果比對誤差並記進 ADR；(4) 之後同一顆 macro 的正式數字，能用修剪網表加上已驗證的修正就不要再跑完整網表。
    - 半穩態 bitcell（ngspice 的行為）：
      - 症狀：漏電量測窗裡功率在某個時間突然上升（ss −40°C 0.5 µW → 尖峰 0.2 mW → 0.28 µW）；沒被寫過的 bitcell `Q` 與 `Q_bar` 相同（ss −40°C 0.64 V，約 0.4 VDD），兩個反相器都導通；完整網表 ss −40°C 讀寫 deck 跑 4 小時以上（其他 corner 約 1.5 小時，兩者的關聯是推測）。
      - 根因（已驗證：修剪網表存全部節點，翻轉前 6 顆 bitcell 在 0.638 V，翻轉後 `Q=0`、`Q_bar=1.6 V`）：deck 不用 `uic` 時 ngspice 先算 DC 工作點，對稱的鎖存器得到 `Q = Q_bar` 的平衡解；低溫時漏電小，要很久才倒向一邊，時間點不可預測。實際晶片上電時元件差異會讓它立刻倒向一邊，所以這是模擬才有的狀態。
      - 怎麼發現：`power.py` 的漏電平穩度 checker（量測窗前後兩半的平均差超過 5% 就 FAIL：`leakage window ... not settled`）；存全部節點後找 `Q`、`Q_bar` 都在 25–75% VDD 的 bitcell。
      - 繞過：所有 bitcell 用 `.ic` 設定初始值（`sramchar.bitcell_ic()`：`Q=0`、`Q_bar=VDD`，數量必須等於網表裡的 bitcell 數）。
      - 防復發：`neg-char` N20（量測窗裡有階躍或 20% 斜率必須 FAIL，平坦、1% 緩降、階躍在窗外必須 PASS；少一顆 bitcell 的網表 `bitcell_ic()` 必須 FAIL）。讀寫 deck 沒有加 `.ic`（決定 13 只重跑漏電）；它的能量看不到翻轉造成的尖峰，影響估計小於 1%。
28. **ngspice 的 `gmin` 會蓋過 SRAM bitcell 的漏電；量漏電的 deck 要把 gmin 調小，並用再小 10 倍的 gmin 核對**（ngspice-47，sky130 dp bitcell；本 repo 實例 ADR-0018 決定 15、`docs/notes/openram_phase6_bringup.md` 步驟 3e「gmin」）。
    - 症狀：單顆 bitcell 的待機漏電幾乎不隨溫度變，漏電 ÷ VDD² 在各 PVT 是同一個常數（sky130：13.1 pS，約 13 個反向偏壓接面 × 預設 gmin 1e-12 S）；× 上萬顆後 .lib 漏電高估好幾倍（sky130 2 KB：tt 2.4 倍、−40°C 4–7 倍）。只有漏電本身夠大的 corner（sky130 ff 100°C）不受影響。checker 訊息：`bitcell leakage depends on gmin`。
    - 根因（已驗證：gmin 從 1e-12 掃到 1e-18，漏電降 50–100 倍後收斂；200 ns 長模擬數值不變，不是沒穩定）：ngspice 在每個 pn 接面並聯 gmin 幫助收斂，反向偏壓 V 的接面多流 gmin × V。
    - 怎麼發現：`power.py` 單顆 deck 用 `CELL_GMIN` 與 `CELL_GMIN_CHECK`（小 10 倍）各跑一次，差超過 1% 就 FAIL；人工判斷時看漏電 ÷ VDD² 是否跨 corner 相同。
    - 繞過：單顆 bitcell 的 deck 用 gmin 1e-17（1e-17 與 1e-18 差 < 0.2%；1e-15 在 sky130 ss −40°C 仍多 16%）。整個周邊電路的大 deck 不要跟著調小：sky130 ss −40°C 用 1e-15 就 `Timestep too small`，ff −40°C 慢 3–5 倍；它在 −40°C 的偏高（ff −40°C 約 48%）寫進已知限制。
    - 防復發：`neg-char` N21（拿掉 gmin 設定的單顆 deck 必須被 `cell_gmin_problem()` 抓到，`CELL_GMIN` 必須 PASS；植入「checker 永遠 PASS」時 N21 FAIL）。ngspice 升版時重跑 gmin 掃描，確認 1e-17 仍在收斂區。

## 用 OpenRAM 自產 macro：開工前查證（2026-10-08，原始碼查證，尚未實跑）

其中平台、PDK、安裝與可重現性已在 2026-10-08 實跑確認，寫成上面的規則 17–21；下面保留查證時的原始整理。

本 repo 實例：ADR-0018（出處逐條列在「查證結果」）。實跑確認後，下面各點才搬進規則本文或改寫（CLAUDE.md 規則 3）。

- **平台**（2026-10-08 在 macOS arm64 實測可行）：OpenRAM 官方環境（`nix develop`）只宣告 x86_64-linux（`flake.nix`），Xyce 也只有 x86_64-linux；但 OpenRAM 是純 Python，設 `use_nix = False` 就用 PATH 上的 Magic、Netgen、KLayout、模擬器（Xyce 找不到時用 ngspice）。在非官方平台跑時，要在官方環境產生同一顆 macro 比對網表與 LVS，排除工具版本造成的差異。
- **重現預建 macro**：先找它的產生設定檔與 log（OpenRAM 版本、`Words per row`、額外的 technology 目錄）。設定或 technology 目錄找不齊時，自產的電路和預建的不同，預建 macro 量到的數字不能沿用。
- **產生時間大部分是 LVS**：sky130 2 KB 的 log 裡 LVS 約 3.4 小時、繞線 44 分鐘、解析模式的時序計算 1 秒。不要把總時間當成「產生」的時間來排程。
- **讀取電路沿用同一套 cell**：sense amp 是 `sky130_fd_bd_sram` 的固定 cell（沒有預充電），column mux 是參數產生的純 NMOS；照預設設定自產，規則 13 的讀取失敗不會自己消失。`words_per_row = 1` 不產生 column mux，代價是 bitline 變長、macro 變瘦長。
- **OpenRAM 預設的特性化 corner 不含 −40°C**（溫度 0／25／100°C、電壓 1.7／1.8／1.9 V，一次只變一個）；要用 `use_specified_corners` 自己列。本 repo 的 .lib 仍用自寫的 ngspice 流程（規則 3 的缺陷照舊）。
- **GDS cell 名稱**：OpenRAM 2022-03 起在產生的 cell 名稱前加 `output_name_` 前綴，只有 `sky130_fd_bd_sram__openram_*` 這類 library cell 沒有前綴。macro 名稱不要和 PDK 預建的同名；檢查最終 GDS 裡沒有前綴的 cell 只有一份定義，且內容和 macro GDS 相同。
- **OpenRAM 目前沒有人維護**（regress CI 停用）；釘 commit，不追最新，分支差異（例如 dual-port bitcell 的 LVS 修正只在 dev）要逐項看過再選。

## 待補

- clock pin 的 insertion delay（.lib 的 clock tree path）：OpenROAD CTS 會用它決定 macro 的 latency 對齊目標（`TritonCTS::computeInsertionDelay`）。目前的 .lib 沒有這個資料，soc_top 直接關掉對齊（ADR-0016）；Phase 6 自產 SRAM 若要讓 CTS 對齊到內部 clock，要先從 SPICE 量出內部 clock 路徑延遲。

- 寄生：萃取網表無法收斂（經驗紀錄 2026-10-05），寄生的影響目前只有「換上萃取 bitcell」的估計；Phase 6 用 OpenRAM 環境再量。
- 其他 PVT 的步長與修剪誤差只在 TT 驗證過。
- hold 弧的值和週期有關（週期 10–16 ns 時「讀之後接寫」比 .lib 早變化），.lib 只對週期 ≥ 20 ns 量過（ADR-0010 已知限制 11）。
- Phase 6：自產 macro 實跑後的規則（上一節的查證要先實測確認）。

## 不在這裡

- macro 的 MACROS 宣告、LEF、擺放 → `hard-macro-integration`
- 量到的數字要加多少餘量、怎麼對照矽量測 → `signoff-criteria`
- STA 用哪些 corner、每個 corner 的 hook → `multicorner-sta`

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | Phase 3.5 試跑（完整網表） | ngspice 35 分鐘以上停在 `INP2M` | 已驗證（`sample` 取樣）：逐顆 MOSFET 解析 sky130 模型 | 改用修剪網表（規則 4） | scratchpad 試跑，ADR-0010 |
| 2026-10-04 | Phase 3.5 試跑（修剪網表，TT） | `.tran 10p` 33 分鐘；`wrdata` 報 `bad v() syntax`；量下降延遲時抓到錯的邊緣 | 已驗證：TSTEP 壓住步長；`[ ]` 是向量索引；`FALL=1` 從 t=0 起算 | 規則 5、6 | 同上 |
| 2026-10-04 | Phase 3.5 試跑（修剪網表，TT） | dout 在上升緣後約 1 ns 拉回 0 | 已驗證（波形） | 規則 7：.lib 加 `rising_edge` 弧 | 同上 |
| 2026-10-04 | Phase 3.5 寄生萃取 | 第一次萃取 5 秒就結束、exit 0、沒有輸出 | 已驗證：沒設 `PDK_ROOT` | 規則 8 | 同上 |
| 2026-10-05 | Phase 3.5 驗證（TT，delay 序列） | 步長 100 ps 對 10 ps：穩定時間 +1.6%、開始變化 −0.7%；修剪對完整網表：讀出延遲 +2.0%；UIC 對直流工作點 +0.5%；十字 5 點推算四角 ≤ 1% | 已驗證：讀出穩定時間的誤差都偏保守；dout 開始變化在兩個 5 fF 角偏晚 0.5–1.0%（樂觀，2026-10-05 獨立審查更正）；修剪那一項用的是早期 508 顆的網表、量的是 50% 延遲 | 記入 ADR-0010 的餘量；規則 11 | `docs/phase_exit/phase3_5.md` |
| 2026-10-05 | Phase 3.5 TT 特性化 | setup 為負、hold 為正（規則 9）；最小 high 0.80 ns、low 2.80 ns、週期 5.62 ns | 已驗證（二分搜尋到 0.02–0.04 ns） | 規則 9 | `ip/sram/.../char/char.json` |
| 2026-10-05 | Phase 3.5 萃取網表 | 修剪後 singular matrix（VSUBS、被修剪 cell 的儲存節點）；處理後、加 rshunt，暫態仍在第一個 clock 邊緣報 `Timestep too small`（出事的節點每次不同） | 前半已驗證（規則 10）；後半未解決 | 萃取網表暫不用於特性化 | 同上 |
| 2026-10-05 | Phase 3.5 寄生估計 | 電路圖網表換上 Magic 萃取的 bitcell（含 cell 內寄生與接面面積）後，TT 寫入第 0 列第 0 行失敗：預充電只到 1.68 V，寫入時兩條 bitline 同時偏低，儲存節點停在約 0.4 V 後倒向錯的一邊 | 未解決：可能是真的餘量問題，也可能是只換 bitcell、周邊沒有寄生造成的不一致 | 使用者 2026-10-05 決定：記為下線前風險，Phase 6 用 OpenRAM 環境確認（ADR-0010 已知限制 4） | 同上 |
| 2026-10-05 | Phase 3.5 操作 | 重開特性化時用 `pkill -f 'ngspice -b deck.sp'`，把另一個也叫 `deck.sp` 的參考模擬一起砍掉 | 已驗證（操作失誤） | 停止程序用 PID 或父程序，不用檔名比對 | — |
| 2026-10-05 | Phase 3.5 特性化的植入錯誤 | N6（手改 .lib 必須被 `--check` 抓到）改成新餘量後，要替換的字串 `2.7500` 已不在 .lib 裡，植入什麼都沒做，`--check` 判沒有過期，N6 FAIL | 已驗證：餘量改變後 .lib 的數字跟著變 | 改成編輯 `timing_type : rising_edge;` 並檢查替換次數（規則 11）；N1–N6 6/6 PASS | `ip/sram/char/neg_char.py` |
| 2026-10-05 | Phase 3.5 ss −40°C 診斷 | 6 個各約 25 分鐘的模擬全部在最後報 `Error: no such vector xsram.xbank0.xport_data0.bl_0`，沒有波形 | 已驗證：子電路的 port 節點用上一層的網路名稱（`xsram.xbank0.bl_0_0`），只有子電路內部節點才是 `<instance>.<node>`；`wrdata` 到模擬結束才檢查名稱 | 長模擬前先跑一個 1 ns 的同一份 deck 確認每個探測節點都存在 | scratchpad `diag2.py` 的 `check_names` |
| 2026-10-05 | Phase 3.5 ss −40°C | 延遲模擬每次讀取都錯；tt −40°C、ss −40°C 到 1.95 V 都讀成前一次的值 | 已驗證（修剪網表，量 bit 0 的 column mux 輸出與 sense amp 內部節點）：sense amp 沒有預充電、column mux 只有 NMOS（規則 13）；完整網表在 ss −40°C 1.70 V 失敗的讀取與節點電壓相同（不是修剪造成） | 使用者決定：ss −40°C 用佔位 .lib，列為頭號下線風險，Phase 6 修正 | ADR-0010 |
| 2026-10-05 | Phase 3.5 harden-soc 第 1 次（`ccc536c`） | `OpenROAD.RepairDesignPostGPL` 75 分鐘後 `failed with an unexpected error`（同一步正常約 40 秒；這個 run 的 log 在重跑時被刪，訊息是當時看到的） | 已驗證（單步重跑 4 種 .lib）：dout0 延遲表的負載斜率等於 60–140 kΩ 的 driver | 規則 14：負載方向取最大值 | ADR-0010 |
| 2026-10-05 | Phase 3.5 最終版圖的 what-if | dout0 transition 用 0.5 ns（使用者決定）；改成電路圖量到的值後，SRAM 半週期路徑 slack：ss −40°C 用 tt 量到的 1.3 ns（這個 PVT 讀取失敗、沒有量測）時 +0.38 → +0.03，ss 100°C 3.15 ns 時 +0.92 → +0.17 | 已驗證（OpenSTA 只換 .lib） | 記入 ADR-0010 已知限制 5；macro 輸出 transition 這種沒有把握的假設，要用 what-if 量出它對 slack 的影響 | ADR-0010 |
| 2026-10-05 | Phase 3.5 非 tt 的 PVT | ss、ff 的最小 pulse 寬度與週期都在以 tt 為中心的搜尋範圍外；舊版每往外移一次就從頭二分 6 輪，預估 ss 的最小週期要近 20 小時 | 已驗證（假模擬器比對新舊版：範圍內探測點相同） | 規則 15：往外一次測 2 點，最多 3 次；ss 100°C、ff −40°C、ff 100°C 用新版重開，沿用已跑完的模擬 | `ip/sram/char/characterize.py`、`ip/sram/char/README.md` |
| 2026-10-05 | Phase 3.5 獨立審查（兩個 agent） | 文件：ss 25°C 1.60 V 的讀取失敗漏列（和 1.80 V 混在一起）、寄生數字（+42%）重算是 +45–48%、「誤差都偏保守」不成立（hold 弧兩角偏樂觀 ≤ 1%）、`max_capacitance` 0.02756 → 0.05 pF 沒寫；checker：12 個漏洞，其中 9 個在特性化流程（見「待補」） | 已驗證（波形重算、獨立重算 5 份 .lib、改壞的輸入實際跑 checker） | 文件更正；規則 11、13 補充；漏洞列為已知限制，Phase 5 開頭修（使用者決定）；獨立重算確認這次的 .lib 正確 | `docs/phase_exit/phase3_5.md`「獨立審查」 |
| 2026-10-05 | Phase 5 開頭：修 Phase 3.5 審查的特性化漏洞 | 9 個漏洞（見規則 16） | 已驗證：每個新植入錯誤在修正前的程式上抓不到、修正後抓到（N9、N11、N13、N15、N16；N12 的 5 種公式錯誤全部抓到）；新的 `check_char_lib.py` 對現有 5 份 .lib PASS | 規則 16；`make sram-confirm` | `ip/sram/char/README.md` |
| 2026-10-08 | Phase 6 步驟 1，小 macro（1rw1r 8×16），本機 macOS 與 Colab | `make sky130-install` rc=0，產生時 `Custom cell pin names do not match spice file: [...] vs []` | 已驗證：`cp $?` 只複製比目標目錄新的檔案 | 規則 19；`touch` 後重裝，`check_install.py` | `docs/notes/openram_phase6_bringup.md` 第 1 項 |
| 2026-10-08 | 同上 | log `ERROR: ... LVS mismatch`，rc=0 | 已驗證 | 規則 18；`gen_macro.py` 讀 log 與報告 | 同上第 2 項 |
| 2026-10-08 | 同上 | 新 PDK（open_pdks `8afc834`）下 LVS 45 個 cell 不一致 | 已驗證（只換 PDK 的對照）：元件改名與萃取規則改變 | 規則 17；macro 用 OpenRAM 釘的 PDK（ADR-0018 決定 5） | 同上第 3 項與兩張對照表 |
| 2026-10-08 | Colab 官方環境 | `use_nix = True` 時 `could not find a flake.nix file`；venv 缺 numpy | 已驗證 | 規則 21 | 同上第 4、5 項 |
| 2026-10-08 | 本機連跑兩次、本機對 Colab | 同設定 GDS 的 met2／met3／via2 不同 | 已驗證：`PYTHONHASHSEED=0` 後逐位元相同（跨平台 GDS XOR 0） | 規則 20 | 同上第 6 項 |
| 2026-10-08 | Phase 6 步驟 3a，自產 2 KB（OpenRAM dev，預設 words per row 4） | ss −40°C 1.60 V、ss 25°C 1.60 V、tt −40°C 1.60 V 讀成前一次的值；同一支程式跑 PDK macro 在 ss −40°C、ss 25°C 也讀錯（對照） | 已驗證（對照組重現 ADR-0010）：自產 macro 用同一套 sense amp 與純 NMOS column mux，規則 13 照樣成立 | 先試 words_per_row = 1（ADR-0018 決定 3） | `docs/notes/openram_phase6_bringup.md` 步驟 3a、`ip/sram/openram/read_check.py` |
| 2026-10-08 | Phase 6 步驟 3p1，小 macro（1rw1r 8×64、words per row 4） | 未套 patch 時 OpenRAM DRC 12（met2.2、met3.2），套 sense amp 輸入端預充電 patch 後 2；met2.2 在 y 約 19.0–19.6 µm，和 2 KB 預設版同形狀 | 已觀察兩次；根因未查 | 規則 22；`macro_drc.py` 比種類，patch 版沒有新種類 | `docs/notes/openram_phase6_bringup.md` 步驟 3p1 |
| 2026-10-08 | Phase 6 步驟 3p1 | port_data 多一支 `p_en_bar` 後，bank 的 `get_pin("p_en_bar")` 報 `Should use a pin iterator since more than one pin` | 已驗證：`get_pin` 遇到同名多支接腳就報錯（`compiler/base/hierarchy_layout.py:589`） | 規則 23；bank 改 `get_pins()`（patch 0001） | 同上 |
| 2026-10-08 | Phase 6 步驟 3p2，自產 2 KB＋patch 0001 | 只有 tt 25°C 1.80 V 讀錯 3 筆（第 0 列，bitline 本身就是錯的值，不是輸出停在前一筆）；拿掉 port 1 的預充電排就讀對 | 已驗證（探針＋E1／E2 單一變因）：激勵照 SoC 把 port 1 接 `clk1=0`、`csb1=1`，`control_logic_r` 的 cs DFF 從不鎖存（`wl_en = (NOT clk) AND cs`，無 reset），SPICE 的 DC 解落在 cs=1 時 port 1 第 0 列 wordline 一直開，port 0 寫入失敗；預建 macro 同電路 | ADR-0018 決定 9：`clk1` 接系統時脈；`sramchar.py` 激勵改 `clk1`＝`clk0`，7/7 讀對；規則本文與防復發 checker 待步驟 4a | `docs/notes/openram_phase6_bringup.md` 步驟 3p2、`runs/openram/whatif/{probe,probe_e1,e2}` |
| 2026-10-09 | Phase 6 步驟 3e，自產 2 KB tt 功耗試跑 | 時脈停住後的漏電 b2 0.2032 mW、b4 0.0033 mW，外插 −2.80 mW；串 0 V 電壓源量電流後變成 b2 24 µA、b4 110 µA（互換），全在 `port_data1` | 已驗證（sense amp 電壓探針：13 顆 `dint_bar` 0.748 V，自 3 ns 起；待機狀態對照 b2／b4 0.00044／0.00045 mW 一致）：閒置 port 1 從不 precharge，sense amp 浮接到中間電壓 | 規則 25；ADR-0018 決定 11（使用者選標準待機漏電＋已知限制）；`power.py` 加漏電 deck，N19 補已知答案 | `docs/notes/openram_phase6_bringup.md` 步驟 3e、`runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/` |
| 2026-10-09 | Phase 6 步驟 3f，2 KB 1RW 試產 | 先報 `must have an even number of cols including replica cols`；加 spare column 後 OpenRAM DRC 657、LVS 不一致（column cap 的 BL／BR 同一個 net），full 規則 DRC 多 16 種 | 已驗證（實跑一次）；根因在 OpenRAM 的 sky130 單 port layout，未往下查 | 規則 26；使用者決定維持 1rw1r（ADR-0018 決定 11）；試產設定留在 `configs/` 供升版時重跑 | `docs/notes/openram_phase6_bringup.md` 步驟 3f、`runs/openram/arv_sram_2kbyte_1rw_32x512_8/` |
| 2026-10-09 | Phase 6 步驟 3e 正式量測（修剪＋外插） | power.py 判 PASS，但 ff 100°C 讀寫能量為負、port 1 閒置 12 pJ；ff −40°C read_fall 外插 −0.6 pJ；tt 漏電外插比完整網表少 54% | 已驗證（每個邊緣前的靜止電流）：浮接 port 1 的靜態電流隨動作改變，不是固定的；外插放大雜訊 | 規則 25 補充；ADR-0018 決定 12（使用者選局部基準＋完整網表）；power.py 自己檢查負值；N19 改成上升的靜態電流 | `docs/notes/openram_phase6_bringup.md` 步驟 3e「正式量測」 |
| 2026-10-09 | Phase 6 步驟 3e，完整網表 5 個 PVT（4 個同時跑） | `make openram-power` 在 4 小時後 `subprocess.TimeoutExpired: ... timed out after 7200 seconds` 中斷，沒有 `power: FAIL` 行；同時跑時漏電 deck 81–98 分鐘（單獨約 36 分鐘），ss／ff 的讀寫 deck 超過 2 小時 | 已驗證：`sramchar.run` 預設逾時 2 小時，逾時例外沒有轉成 RuntimeError | `run` 逾時改拋 RuntimeError（呼叫端照常報 FAIL）；`power.py` 逾時 8 小時；已完成的模擬由快取重用 | `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/openram-power.log` |
| 2026-10-09 | Phase 6 步驟 3e，完整網表 5 個 PVT 同時跑（重跑） | 每個時間點 4–17 秒（tt 先前約 0.4 秒），預估 6.5–23 小時；ngspice 只吃 64% CPU，`sample` 顯示 12% 在 `AddRealValueToVector` | 已驗證（`top -stats mem,cmprs`、`vm_stat`）：記憶體不夠，10 秒內約 390 萬次壓縮／解壓縮。2 KB 完整網表的電路本身每個 run 約 4.2 GB（加 `save` 後剛開始暫態時量到），沒有 `save` 時存下每個節點的波形，900 個時間點時再多約 1 GB；5 個 run 超過 24 GB 實體記憶體。（第一次只加 `save` 仍是 5 個同時跑，記憶體一樣塞滿，是錯的修法） | `sramchar.deck(save_only=True)` 只存寫出的向量（電壓源電流寫 `vvdd#branch`）；`power.py` 預設同時 3 個；改成同時 3 個後每 2 分鐘約 170 個時間點（之前 13–31），寫進規則 4 | `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/power/full/` |
| 2026-10-10 | Phase 6 步驟 3e，DC 工作點量漏電（修剪網表 tt） | `doAnalyses: out of memory`、`KLU mode cannot create a new element`、`Nodeset on non-existent node`；濾掉後 `Starting dynamic gmin stepping`／`Transient op started`，I(VDD) 1.8 µA–3.8 mA（暫態 0.25 µA） | 已驗證（逐節點比對 DC 解與暫態，鎖存器翻掉）；直接疊代不收斂的根因未查 | 規則 25「不要用 DC 工作點」；使用者改選量測窗加絕對門檻（ADR-0018 決定 14） | `docs/notes/openram_phase6_bringup.md` 步驟 3e「DC 工作點」、`runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/dcop/` |
| 2026-10-10 | Phase 6 步驟 3e，ss −40°C 漏電量測窗 | `leakage window ... not settled: its halves differ by 6.0%`；停住 300 ns 漏電仍在降；tt 停住 342 ns 反而升 26% | 已驗證（存全部節點：295 個節點 < −50 mV 慢慢回升；長停住實驗）；tt 上升的原因未查 | 規則 25 量測窗判準（只放行下降的絕對門檻）、`power.unsettled()`、N20 加三個案例；tt 偏低寫進已知限制 | 筆記步驟 3e「長時間停住」「絕對門檻」、`leakdbg/longpark/` |
| 2026-10-10 | Phase 6 步驟 3e，單顆 bitcell 漏電 | 漏電 ÷ VDD² 在 tt、ss −40°C、ff −40°C 都是 13.1 pS；快速量法在 ff −40°C 比完整網表高 31% | 已驗證（gmin 1e-12 → 1e-18 掃描，1e-17 起收斂）：ngspice gmin 主導 | 規則 28；單顆 deck gmin 1e-17、`cell_gmin_problem()`、N21（ADR-0018 決定 15） | 筆記步驟 3e「gmin」、`leakdbg/gmin/` |
