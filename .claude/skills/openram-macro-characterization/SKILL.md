---
name: openram-macro-characterization
description: SRAM macro 的時序與功耗要用 SPICE（ngspice＋sky130）實測、產生多 corner 的 .lib 時使用。症狀：ngspice 讀大網表停在 `INP2M`；完整網表平行跑時每步慢 10–40 倍、CPU 約 64%（記憶體不夠，每個 run 約 4.2 GB）；`bad v() syntax`；長模擬到結尾才報 `no such vector`；`meas ... FALL=1` 量到錯的邊緣；低溫或 ss 低電壓（室溫也會）讀成前一次的值；換上新 .lib 後 `repair_design` 跑很久或 failed with an unexpected error（延遲表的負載斜率）；`leakage window ... not settled`；`bitcell leakage depends on gmin`；`.nodeset` 加 `.op` 報 `doAnalyses` out of memory。涵蓋判斷廠商 .lib 是不是解析模型（`Analytical model enabled`）、OpenRAM 自己特性化的缺陷、dout 在上升緣後被拉回、setup／hold、最小週期與 pulse width 的搜尋、量測條件要涵蓋 SoC 的週期與負載、不能動的 corner 的佔位 .lib、待機漏電與閒置 port、.lib 產生器的獨立重算與植入錯誤。產生 macro 看 openram-macro-generation，萃取看 sram-layout-extraction，接進設計看 hard-macro-integration。Use for SPICE characterization of SRAM macros (ngspice + sky130), per-corner Liberty, leakage and power measurement.
---

# SRAM macro 的 SPICE 特性化與 .lib

2026-10-15 依功能拆成三個 skill（ADR-0021 決定 5）：用 OpenRAM 產生 macro 看 `openram-macro-generation`；從 GDS 萃取寄生與萃取網表的模擬看 `sram-layout-extraction`；這裡留 SPICE 量測與 .lib。macro 交給 flow 前的 view QA 與 go／no-go 看 `macro-qualification`，接進設計看 `hard-macro-integration`；量到的數字要加多少餘量看 `signoff-criteria`；corner 清單看 `multicorner-sta`。本 repo 實例：ADR-0010、`ip/sram/char/`（腳本與方法）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`（結果）；自產 macro：ADR-0018、`ip/sram/openram/`。

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
   - 完整網表平行跑之前先算記憶體：2 KB 完整網表每個 ngspice 約 4.2 GB（電路本身），超過實體記憶體時系統一直壓縮／解壓縮記憶體，每個時間點慢 10–40 倍，CPU 只吃到約 64%，看起來像卡住（已驗證，2026-10-09；本 repo 同時跑 3 個與 5 個的實測見經驗紀錄同日兩列）。怎麼發現：`top -l 1 -stats pid,command,mem,cmprs` 的 CMPRS、`vm_stat` 的 Compressions 短時間內大增。另外 deck 要用 `save` 只存要寫出的向量（電壓源電流寫成 `<名稱>#branch`；`sramchar.deck(save_only=True)`），否則 ngspice 存下每個節點的每個時間點，記憶體隨時間增加。
   - 長模擬的進度看 `ngspice.log` 的 `Reference value`（目前模擬到的時間；檔案是成批寫入，會落後一些）。
5. **`.tran` 的 TSTEP 會壓住最大步長**：`.tran 10p` 跑 33 分鐘，`.tran 100p` 跑 7 分鐘，延遲差 1.8%（TT 2.348 vs 2.305 ns）。換步長要用小步長的結果驗證一次，並把誤差記下來算進餘量。
   - 自動防護：沒有（deck 產生器不檢查 TSTEP，換步長時靠人工用小步長比對）。
6. **ngspice 控制語言的兩個陷阱**：
   - 節點名稱有 `[ ]`（bus）時，`wrdata v(dout0[31])` 報 `bad v() syntax`（`[ ]` 被當成向量索引）；用 `E` 電壓源接到沒有括號的節點名稱再輸出。
   - `meas tran ... TARG ... FALL=1` 從 t=0 起算，不是從觸發點之後；要加 `TD=<觸發時間>`。
     - 這個錯不會報錯，只會量到錯的數字。怎麼發現：量到的延遲和波形對照（負值、比週期還長、和相鄰格點差很多）。自動防護：沒有（`neg-char` 沒有這個案例；下一個專案加一個植入錯誤，問題總檢討 B11）。
   - 探測的節點名稱不存在時，ngspice 到模擬結束才報 `Error: no such vector <name>`，整段模擬白跑、沒有波形（已驗證，2026-10-05：6 個各約 25 分鐘的模擬，經驗紀錄同日）。子電路的 port 節點攤平後用的是上一層的網路名稱（例：`xsram.xbank0.bl_0_0`），只有子電路內部節點才是 `<instance>.<node>`。做法：長模擬前先用同一份 deck 跑 1 ns，確認每個 `wrdata`／`meas` 的節點都存在。自動防護：沒有（目前是操作習慣；可以在 deck 產生器加 1 ns 預跑，下一個專案做）。
7. **OpenRAM SRAM 的 dout 在每個有效週期（`csb=0`）的上升緣後約 1 ns 就被拉回 0**，讀 1 時要到下降緣之後才升上來（sky130 2 KB、TT：上升緣後 1.02–1.29 ns 拉低，下降緣後 2.2–2.3 ns 讀出 1）。
   - 廠商 .lib 只有 `falling_edge` 一條弧，STA 以為資料保持到下一個下降緣；接收端 flop 的 clock 比 macro 的 clock 晚到約 1 ns 就會抓錯，STA 卻不會報。
   - .lib 要加一條 `rising_edge` 弧，最小延遲取上升緣到 dout 開始變化的時間，讓 STA 對接收端做 hold 檢查。
   - 行為模型的 `T_HOLD`（上升緣後 1 ns 把 dout 設成 X）模擬的就是這件事。
8. 規則 8 移到 `sram-layout-extraction` 規則 1（從 GDS 萃取寄生）。

9. **setup/hold 要在整顆 macro 上量，不能只量輸入那顆 DFF**：macro 內部的 clock buffer 讓 DFF 晚一點才抓資料，所以 pin 上的 setup 變小（可為負）、hold 變大。sky130 2 KB、TT：setup −0.16～−0.22 ns、hold +0.20～+0.24 ns；PDK 解析模型（OpenRAM 只量 DFF）寫 setup 0.103、hold −0.056，hold 少算約 0.3 ns。量法：在測試週期把一組輸入的轉態時間往前或往後移，用寫入再讀回的資料判斷新值或舊值，二分搜尋（`ip/sram/char/characterize.py` 的 lanes）。
10. 規則 10 移到 `sram-layout-extraction` 規則 2（Magic 萃取的網表不能直接模擬）。

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
    - 這樣的表讓 `repair_design` 停不下來：同一份輸入單步重跑，卡在第 9000 個 driver 之後；加大輸出 pin 的 `max_transition` 沒用；延遲表與 hold 弧表一起在負載方向攤平後 52–98 秒完成（差別是機器負載；沒有分開測是哪一張表）。卡在輸出 net 上是推測（`sample` 看不到 net 名稱，沒有確認）。
    - 做法：每列（clock slew）取負載中的最大延遲、hold 弧取最小值，`max_capacitance` 設成特性化過的最大負載。產生 .lib 後先用單步重跑 `OpenROAD.RepairDesignPostGPL` 確認時間正常，再跑完整流程（`librelane-run-debug` 規則 3）。
15. **搜尋範圍不涵蓋真值時，往外一次多測幾點，不要整個重新二分**（`ip/sram/char/characterize.py` 的 `bisect`）：
    - 其他 PVT 的搜尋以 tt 結果為中心，但 ss 的高、低電位時間與週期比 tt 大 1 ns 以上，ff 的低電位時間與週期小 1 ns 以上，都在範圍外。
    - 舊做法每往外移一次範圍就從頭二分 6 輪（每輪約 50 分鐘）；本 repo 估計 ss 的最小週期要近 20 小時（經驗紀錄 2026-10-05）。
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

17. 規則 17 移到 `openram-macro-generation` 規則 1（DRC／LVS 用 OpenRAM 釘的 PDK）。
18. 規則 18 移到 `openram-macro-generation` 規則 2（DRC／LVS 失敗時 exit code 仍是 0）。
19. 規則 19 移到 `openram-macro-generation` 規則 3（`make sky130-install` 少複製 cell）。
20. 規則 20 移到 `openram-macro-generation` 規則 4（`PYTHONHASHSEED`）。
21. 規則 21 移到 `openram-macro-generation` 規則 5（`use_nix`）。
22. 規則 22 移到 `openram-macro-generation` 規則 6（OpenRAM 自己的 DRC 不夠）。
23. 規則 23 移到 `openram-macro-generation` 規則 7（repo 內的 patch 與工作樹檢查）。
24. 規則 24 移到 `openram-macro-generation` 規則 8（dev 的 .lib internal_power）。
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
    - 不要為了消除它把閒置 port 改成每個週期都讀取（`csb1=0`）：每個週期多一次讀取的能量（2 KB tt 約 11 pJ），而且 port 0 寫同一列時另一個 port 的 wordline 也開著，可能寫不進去（推測，沒有實測）。要去掉它得改用沒有該 port 的 macro（`openram-macro-generation` 規則 9）。
    - 防復發：每個量測值必須是有限值且 ≥ 0（`power.py` 的 `record_problems()` 與 `gen_char_lib.power_record_problems()`，`neg-char` N17）；已知答案測試 `neg-char` N19 的靜態電流在整段模擬中上升 100 倍，植入「整段扣時脈停住後的值」「漏電量測窗包含停住的邊緣」「不扣靜態電流」都 FAIL。
26. 規則 26 移到 `openram-macro-generation` 規則 9（sky130 1RW macro 的限制）。

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
29. 規則 29 移到 `sram-layout-extraction` 規則 3（特性化之前先試版圖萃取）。

## 規則（已驗證，2026-10-15 問題總檢討後補寫，ADR-0021）

30. **特性化的週期、輸出負載與 input slew 要涵蓋 SoC 實際的工作點；.lib 的 `min_capacitance`／`max_capacitance` 設成特性化過的範圍**（出現兩次：Phase 3.5 的 ADR-0010 已知限制 11–13，Phase 6 的 ADR-0018 決定 20；問題總檢討 `docs/notes/problem_review/review_p0_35.md` 建議 7）。
    - 為什麼：超出特性化範圍時 STA 外插、不警告。Phase 3.5：hold 弧只在 20 ns 週期量，週期 10–16 ns 時「讀之後接寫」比 .lib 早變化（ADR-0010 已知限制 11）；最終版圖 dout0 最小負載 3.35 fF 低於特性化的 5 fF，而 `min_capacitance` 沿用 PDK 的 1.72 fF，所以 STA 不會警告（已知限制 12）；`max_capacitance` 改成特性化的最大負載，一開始沒寫進文件（獨立審查，ADR-0010）。Phase 6：萃取網表在 ss −40°C 用 20 ns 週期判讀取 FAIL，改用 SoC 的週期才讀對（`sram-layout-extraction` 規則 2 最後一點）。
    - 做法：從 SoC 的 STA 報告取 macro 每支輸出的最小、最大負載與輸入（clock、位址、資料）的 slew，週期用 SoC 的 signoff 週期；量測格點要涵蓋這些值。.lib 的 `min_capacitance`／`max_capacitance` 設成特性化過的範圍，讓 STA 在範圍外報違規，而不是外插。讀寫正確的判定用 SoC 實際週期；短週期 FAIL 時先拉長週期，分辨是變慢還是讀不出來。週期或 SoC 的負載改變（換 core、改週期、重新 floorplan）時重新對照。
    - 通過條件：SoC 的最小／最大負載、slew、週期都在特性化範圍內；超出的部分寫成已知限制並估計影響。
    - 自動防護：沒有（目前靠人工比對 STA 報告與量測格點）。下一個專案開始時可以加進 `check_char_lib.py`：讀 SoC 的 STA 報告，比對 macro 腳位的負載、slew 與 .lib 的範圍。

## 待補

- clock pin 的 insertion delay（.lib 的 clock tree path）：OpenROAD CTS 會用它決定 macro 的 latency 對齊目標（`TritonCTS::computeInsertionDelay`）。目前的 .lib 沒有這個資料，soc_top 直接關掉對齊（ADR-0016）；自產 SRAM 若要讓 CTS 對齊到內部 clock，要先從 SPICE 量出內部 clock 路徑延遲（Phase 6–7 沒做）。
- 其他 PVT 的步長與修剪誤差只在 TT 驗證過。
- hold 弧的值和週期有關（週期 10–16 ns 時「讀之後接寫」比 .lib 早變化），.lib 只對週期 ≥ 20 ns 量過（ADR-0010 已知限制 11；規則 30）。
- 用萃取網表重新特性化：移到 `sram-layout-extraction`「待補」。原本的「Phase 6：自產 macro 實跑後的規則」已寫成 `openram-macro-generation` 規則 1–9，2026-10-15 刪去。

## 不在這裡

- 用 OpenRAM 產生 macro、釘版 PDK、patch、DRC／LVS → `openram-macro-generation`
- 從 GDS 萃取寄生、萃取網表的模擬 → `sram-layout-extraction`
- view QA、選定前的 go／no-go、換 macro 檢查單 → `macro-qualification`
- macro 的 MACROS 宣告、LEF、擺放 → `hard-macro-integration`
- 量到的數字要加多少餘量、怎麼對照矽量測 → `signoff-criteria`
- STA 用哪些 corner、每個 corner 的 hook → `multicorner-sta`

## 用完後 / 經驗紀錄

這張表 2026-10-15 拆分（ADR-0021 決定 5）：寄生萃取的列（2026-10-04 寄生萃取、2026-10-05 萃取網表與寄生估計、2026-10-11 版圖萃取試跑）搬到 `sram-layout-extraction`；OpenRAM 產生 macro 的列（2026-10-08 安裝、LVS、PDK、nix、`PYTHONHASHSEED`、步驟 3a、3p1 兩列，2026-10-09 步驟 3f，2026-10-10 步驟 4b、3m 兩列）搬到 `openram-macro-generation`；這裡留量測與 .lib 的列。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | Phase 3.5 試跑（完整網表） | ngspice 35 分鐘以上停在 `INP2M` | 已驗證（`sample` 取樣）：逐顆 MOSFET 解析 sky130 模型 | 改用修剪網表（規則 4） | scratchpad 試跑，ADR-0010 |
| 2026-10-04 | Phase 3.5 試跑（修剪網表，TT） | `.tran 10p` 33 分鐘；`wrdata` 報 `bad v() syntax`；量下降延遲時抓到錯的邊緣 | 已驗證：TSTEP 壓住步長；`[ ]` 是向量索引；`FALL=1` 從 t=0 起算 | 規則 5、6 | 同上 |
| 2026-10-04 | Phase 3.5 試跑（修剪網表，TT） | dout 在上升緣後約 1 ns 拉回 0 | 已驗證（波形） | 規則 7：.lib 加 `rising_edge` 弧 | 同上 |
| 2026-10-05 | Phase 3.5 驗證（TT，delay 序列） | 步長 100 ps 對 10 ps：穩定時間 +1.6%、開始變化 −0.7%；修剪對完整網表：讀出延遲 +2.0%；UIC 對直流工作點 +0.5%；十字 5 點推算四角 ≤ 1% | 已驗證：讀出穩定時間的誤差都偏保守；dout 開始變化在兩個 5 fF 角偏晚 0.5–1.0%（樂觀，2026-10-05 獨立審查更正）；修剪那一項用的是早期 508 顆的網表、量的是 50% 延遲 | 記入 ADR-0010 的餘量；規則 11 | `docs/phase_exit/phase3_5.md` |
| 2026-10-05 | Phase 3.5 TT 特性化 | setup 為負、hold 為正（規則 9）；最小 high 0.80 ns、low 2.80 ns、週期 5.62 ns | 已驗證（二分搜尋到 0.02–0.04 ns） | 規則 9 | `ip/sram/.../char/char.json` |
| 2026-10-05 | Phase 3.5 操作 | 重開特性化時用 `pkill -f 'ngspice -b deck.sp'`，把另一個也叫 `deck.sp` 的參考模擬一起砍掉 | 已驗證（操作失誤） | 停止程序用 PID 或父程序，不用檔名比對 | — |
| 2026-10-05 | Phase 3.5 特性化的植入錯誤 | N6（手改 .lib 必須被 `--check` 抓到）改成新餘量後，要替換的字串 `2.7500` 已不在 .lib 裡，植入什麼都沒做，`--check` 判沒有過期，N6 FAIL | 已驗證：餘量改變後 .lib 的數字跟著變 | 改成編輯 `timing_type : rising_edge;` 並檢查替換次數（規則 11）；N1–N6 6/6 PASS | `ip/sram/char/neg_char.py` |
| 2026-10-05 | Phase 3.5 ss −40°C 診斷 | 6 個各約 25 分鐘的模擬全部在最後報 `Error: no such vector xsram.xbank0.xport_data0.bl_0`，沒有波形 | 已驗證：子電路的 port 節點用上一層的網路名稱（`xsram.xbank0.bl_0_0`），只有子電路內部節點才是 `<instance>.<node>`；`wrdata` 到模擬結束才檢查名稱 | 長模擬前先跑一個 1 ns 的同一份 deck 確認每個探測節點都存在 | scratchpad `diag2.py` 的 `check_names` |
| 2026-10-05 | Phase 3.5 ss −40°C | 延遲模擬每次讀取都錯；tt −40°C、ss −40°C 到 1.95 V 都讀成前一次的值 | 已驗證（修剪網表，量 bit 0 的 column mux 輸出與 sense amp 內部節點）：sense amp 沒有預充電、column mux 只有 NMOS（規則 13）；完整網表在 ss −40°C 1.70 V 失敗的讀取與節點電壓相同（不是修剪造成） | 使用者決定：ss −40°C 用佔位 .lib，列為頭號下線風險，Phase 6 修正 | ADR-0010 |
| 2026-10-05 | Phase 3.5 harden-soc 第 1 次（`ccc536c`） | `OpenROAD.RepairDesignPostGPL` 75 分鐘後 `failed with an unexpected error`（同一步正常約 40 秒；這個 run 的 log 在重跑時被刪，訊息是當時看到的） | 已驗證（單步重跑 4 種 .lib）：dout0 延遲表的負載斜率等於 60–140 kΩ 的 driver | 規則 14：負載方向取最大值 | ADR-0010 |
| 2026-10-05 | Phase 3.5 最終版圖的 what-if | dout0 transition 用 0.5 ns（使用者決定）；改成電路圖量到的值後，SRAM 半週期路徑 slack：ss −40°C 用 tt 量到的 1.3 ns（這個 PVT 讀取失敗、沒有量測）時 +0.38 → +0.03，ss 100°C 3.15 ns 時 +0.92 → +0.17 | 已驗證（OpenSTA 只換 .lib） | 記入 ADR-0010 已知限制 5；macro 輸出 transition 這種沒有把握的假設，要用 what-if 量出它對 slack 的影響 | ADR-0010 |
| 2026-10-05 | Phase 3.5 非 tt 的 PVT | ss、ff 的最小 pulse 寬度與週期都在以 tt 為中心的搜尋範圍外；舊版每往外移一次就從頭二分 6 輪，預估 ss 的最小週期要近 20 小時 | 已驗證（假模擬器比對新舊版：範圍內探測點相同） | 規則 15：往外一次測 2 點，最多 3 次；ss 100°C、ff −40°C、ff 100°C 用新版重開，沿用已跑完的模擬 | `ip/sram/char/characterize.py`、`ip/sram/char/README.md` |
| 2026-10-05 | Phase 3.5 獨立審查（兩個 agent） | 文件：ss 25°C 1.60 V 的讀取失敗漏列（和 1.80 V 混在一起）、寄生數字（+42%）重算是 +45–48%、「誤差都偏保守」不成立（hold 弧兩角偏樂觀 ≤ 1%）、`max_capacitance` 0.02756 → 0.05 pF 沒寫；checker：12 個漏洞，其中 9 個在特性化流程（見「待補」） | 已驗證（波形重算、獨立重算 5 份 .lib、改壞的輸入實際跑 checker） | 文件更正；規則 11、13 補充；漏洞列為已知限制，Phase 5 開頭修（使用者決定）；獨立重算確認這次的 .lib 正確 | `docs/phase_exit/phase3_5.md`「獨立審查」 |
| 2026-10-05 | Phase 5 開頭：修 Phase 3.5 審查的特性化漏洞 | 9 個漏洞（見規則 16） | 已驗證：每個新植入錯誤在修正前的程式上抓不到、修正後抓到（N9、N11、N13、N15、N16；N12 的 5 種公式錯誤全部抓到）；新的 `check_char_lib.py` 對現有 5 份 .lib PASS | 規則 16；`make sram-confirm` | `ip/sram/char/README.md` |
| 2026-10-08 | Phase 6 步驟 3p2，自產 2 KB＋patch 0001 | 只有 tt 25°C 1.80 V 讀錯 3 筆（第 0 列，bitline 本身就是錯的值，不是輸出停在前一筆）；拿掉 port 1 的預充電排就讀對 | 已驗證（探針＋E1／E2 單一變因）：激勵照 SoC 把 port 1 接 `clk1=0`、`csb1=1`，`control_logic_r` 的 cs DFF 從不鎖存（`wl_en = (NOT clk) AND cs`，無 reset），SPICE 的 DC 解落在 cs=1 時 port 1 第 0 列 wordline 一直開，port 0 寫入失敗；預建 macro 同電路 | ADR-0018 決定 9：`clk1` 接系統時脈；`sramchar.py` 激勵改 `clk1`＝`clk0`，7/7 讀對；規則本文與防復發 checker 待步驟 4a | `docs/notes/openram_phase6_bringup.md` 步驟 3p2、`runs/openram/whatif/{probe,probe_e1,e2}` |
| 2026-10-09 | Phase 6 步驟 3e，自產 2 KB tt 功耗試跑 | 時脈停住後的漏電 b2 0.2032 mW、b4 0.0033 mW，外插 −2.80 mW；串 0 V 電壓源量電流後變成 b2 24 µA、b4 110 µA（互換），全在 `port_data1` | 已驗證（sense amp 電壓探針：13 顆 `dint_bar` 0.748 V，自 3 ns 起；待機狀態對照 b2／b4 0.00044／0.00045 mW 一致）：閒置 port 1 從不 precharge，sense amp 浮接到中間電壓 | 規則 25；ADR-0018 決定 11（使用者選標準待機漏電＋已知限制）；`power.py` 加漏電 deck，N19 補已知答案 | `docs/notes/openram_phase6_bringup.md` 步驟 3e、`runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/` |
| 2026-10-09 | Phase 6 步驟 3e 正式量測（修剪＋外插） | power.py 判 PASS，但 ff 100°C 讀寫能量為負、port 1 閒置 12 pJ；ff −40°C read_fall 外插 −0.6 pJ；tt 漏電外插比完整網表少 54% | 已驗證（每個邊緣前的靜止電流）：浮接 port 1 的靜態電流隨動作改變，不是固定的；外插放大雜訊 | 規則 25 補充；ADR-0018 決定 12（使用者選局部基準＋完整網表）；power.py 自己檢查負值；N19 改成上升的靜態電流 | `docs/notes/openram_phase6_bringup.md` 步驟 3e「正式量測」 |
| 2026-10-09 | Phase 6 步驟 3e，完整網表 5 個 PVT（4 個同時跑） | `make openram-power` 在 4 小時後 `subprocess.TimeoutExpired: ... timed out after 7200 seconds` 中斷，沒有 `power: FAIL` 行；同時跑時漏電 deck 81–98 分鐘（單獨約 36 分鐘），ss／ff 的讀寫 deck 超過 2 小時 | 已驗證：`sramchar.run` 預設逾時 2 小時，逾時例外沒有轉成 RuntimeError | `run` 逾時改拋 RuntimeError（呼叫端照常報 FAIL）；`power.py` 逾時 8 小時；已完成的模擬由快取重用 | `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/openram-power.log` |
| 2026-10-09 | Phase 6 步驟 3e，完整網表 5 個 PVT 同時跑（重跑） | 每個時間點 4–17 秒（tt 先前約 0.4 秒），預估 6.5–23 小時；ngspice 只吃 64% CPU，`sample` 顯示 12% 在 `AddRealValueToVector` | 已驗證（`top -stats mem,cmprs`、`vm_stat`）：記憶體不夠，10 秒內約 390 萬次壓縮／解壓縮。2 KB 完整網表的電路本身每個 run 約 4.2 GB（加 `save` 後剛開始暫態時量到），沒有 `save` 時存下每個節點的波形，900 個時間點時再多約 1 GB；5 個 run 超過 24 GB 實體記憶體。（第一次只加 `save` 仍是 5 個同時跑，記憶體一樣塞滿，是錯的修法） | `sramchar.deck(save_only=True)` 只存寫出的向量（電壓源電流寫 `vvdd#branch`）；`power.py` 預設同時 3 個；改成同時 3 個後每 2 分鐘約 170 個時間點（之前 13–31），寫進規則 4 | `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/power/full/` |
| 2026-10-10 | Phase 6 步驟 3e，DC 工作點量漏電（修剪網表 tt） | `doAnalyses: out of memory`、`KLU mode cannot create a new element`、`Nodeset on non-existent node`；濾掉後 `Starting dynamic gmin stepping`／`Transient op started`，I(VDD) 1.8 µA–3.8 mA（暫態 0.25 µA） | 已驗證（逐節點比對 DC 解與暫態，鎖存器翻掉）；直接疊代不收斂的根因未查 | 規則 25「不要用 DC 工作點」；使用者改選量測窗加絕對門檻（ADR-0018 決定 14） | `docs/notes/openram_phase6_bringup.md` 步驟 3e「DC 工作點」、`runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/dcop/` |
| 2026-10-10 | Phase 6 步驟 3e，ss −40°C 漏電量測窗 | `leakage window ... not settled: its halves differ by 6.0%`；停住 300 ns 漏電仍在降；tt 停住 342 ns 反而升 26% | 已驗證（存全部節點：295 個節點 < −50 mV 慢慢回升；長停住實驗）；tt 上升的原因未查 | 規則 25 量測窗判準（只放行下降的絕對門檻）、`power.unsettled()`、N20 加三個案例；tt 偏低寫進已知限制 | 筆記步驟 3e「長時間停住」「絕對門檻」、`leakdbg/longpark/` |
| 2026-10-10 | Phase 6 步驟 3e，單顆 bitcell 漏電 | 漏電 ÷ VDD² 在 tt、ss −40°C、ff −40°C 都是 13.1 pS；快速量法在 ff −40°C 比完整網表高 31% | 已驗證（gmin 1e-12 → 1e-18 掃描，1e-17 起收斂）：ngspice gmin 主導 | 規則 28；單顆 deck gmin 1e-17、`cell_gmin_problem()`、N21（ADR-0018 決定 15） | 筆記步驟 3e「gmin」、`leakdbg/gmin/` |
