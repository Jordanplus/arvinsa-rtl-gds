# Phase 2 exit review：單獨 harden PicoRV32

日期：2026-10-03　結論：**PASS**（六項 exit criteria 全部達成）

Exit criteria 出處：`project-plan.md` §8 Phase 2（GDS 產出；abstract DRC = 0、LVS PASS、9 corner setup/hold @ 40 ns；GL ISA regression PASS；據此決定 `DIE_AREA`）。
以下數字來自最後一次 `make phase2`（2026-10-03 16:45–17:09，端到端 PASS，23 分 31 秒）。

| # | Exit criterion | 結果 | 證據 |
|---|---|---|---|
| 1 | GDS 產出 | PASS | `runs/picorv32_core/final/gds/picorv32.gds`；die 533.575 × 544.295 µm |
| 2 | abstract DRC = 0 | PASS | Magic DRC 0、KLayout DRC 0、繞線 DRC 0。這顆 core 沒有 macro，所以 DRC 是對完整 GDS 做的，比 abstract（只看 macro 外框）更嚴格 |
| 3 | LVS PASS | PASS | `design__lvs_error__count` = 0；XOR（Magic 與 KLayout 各自產生的 GDS 互相比對）差異 0 |
| 4 | 9 個 corner 的 setup／hold ≥ 0 @ 40 ns | PASS | setup 最差 +6.175 ns（`max_ss_100C_1v60`），hold 最差 +0.039 ns（`min_ff_n40C_1v95`）；`SETUP_VIOLATION_CORNERS`／`HOLD_VIOLATION_CORNERS` 設為全部 corner，LibreLane 自己的 checker 也在 9 個 corner 判定 |
| 5 | GL ISA regression PASS | PASS | `make gl-core`：上游 `testbench.v -DSYNTH_TEST` 在最終網表上 `ALL TESTS PASSED`，45/45 指令測試 OK，`TRAP after 423620 cycles`；RTL 與 GL 的 117381 筆 bus transaction 逐筆相同。覆蓋範圍的限制見「已知限制」第 7 點 |
| 6 | 決定 `DIE_AREA` | PASS | ADR-0006：`DIE_AREA = 0 0 1000 800`，估計 logic 區使用率 51%（`make soc-area`：soc_top standard cell 估 226985 µm²） |

`project-plan.md` §7.2 的其他 signoff 項目：max slew／cap／fanout 違規在 9 個 corner 都是 0，antenna 違規 0，nom_tt setup slack 14.91 ns ≥ 週期的 10%（4 ns），power grid 違規 0，unmapped cell 0。`timing__unannotated_net__count` 不是 0 而是 114，原因與處理見「與計畫不同的地方」。完整門檻在 `signoff/limits/picorv32_core.toml`。

## 實測面積與時序（golden：`signoff/golden/picorv32_core/metrics.json`）

| 項目 | 值 |
|---|---|
| 合成後（Yosys） | 10764 顆 cell，136522 µm² |
| PnR 後 standard cell | 21748 顆，196970 µm²（含 tap，不含 fill），core 使用率 72.2%；flip-flop 2382 顆 |
| 其中 timing repair buffer | 48598 µm²（含 2230 顆 hold buffer，約 22300 µm²） |
| core／die | 272662 µm²／533.575 × 544.295 µm |
| setup worst slack | nom_tt 14.910 ns；最差 max_ss 6.175 ns |
| hold worst slack | 0.039 ns（min_ff） |
| 功耗（OpenSTA，沒有給 switching activity 檔，用預設值估） | nom_tt 10.0 mW，max_ff 11.9 mW。注意 metric `power__total` 是 9 個 corner 依序寫入後留下的最後一個值，也就是 max_ff 的值（`librelane/steps/openroad.py` 第 808–810 行），不是 nom_tt |
| 總線長 | 708673 µm |
| 執行時間 | `make phase2` 共 23.5 分鐘：harden-core 約 14.7 分鐘、gl-core 2.5 分鐘、neg-gl-core 6.2 分鐘、soc-area 約 10 秒 |

## 怎麼收斂到 DRV = 0

第一次試跑時 setup／hold 就已經 PASS，但 DRV 大量超標（DRV 指 max slew、max cap、max fanout 這類電性規則；以下數字是最差那個 corner 的違規數）：slew 5544、cap 71、fanout 83。共試跑 9 次，找出四個根因並逐一處理，細節與每次的數字見 `pnr/picorv32_core/README.md`：

1. resizer 把驅動力很弱的 clock 延遲 cell（`clkdlybuf4s25_1`）當一般 buffer 用：PDK 排除清單只排除 `clkdlybuf4s15_1`、`clkdlybuf4s18_1` → `EXTRA_EXCLUDED_CELLS`。
2. 繞線前的線電容估計只有實際的一半，resizer 修得不夠 → `LAYERS_RC`（LibreLane 原始碼內註解掉的 sky130 表）。
3. slew／cap 修復只在 CTS 之前做一次，之後 hold buffer 與繞線又加了負載 → `RUN_POST_GRT_DESIGN_REPAIR` 加上 30% slew 餘裕。
4. clock tree：末端 dummy load 讓 fanout 超過 10，以及 H-tree 中段沒放 buffer，讓第 2 層 buffer 帶 16 → `CTS_SINK_CLUSTERING_SIZE 8`、`CTS_DISTANCE_BETWEEN_BUFFERS 50`。

有一個試過但退回的做法：排除 `buf_1` 之後，resizer 改用延遲 cell 當 buffer，ss corner 的 setup 反而 FAIL（第 4 次試跑）。

## 可重現性：detailed routing 不是每次都一樣

| run | 與 golden 比較 |
|---|---|
| 試跑 #9（設定多一項沒有作用的 `CTS_MAX_CAP`） | 325 個 metrics 完全相同 |
| 正式 run 第 1 次 | golden 來源 |
| 正式 run 第 2 次（第一次 `make phase2`） | 71 個 metrics 有極小差異。當時 golden 規則是全部逐項相同，所以這次 `make phase2` 在 harden-core 判 FAIL，後面的 gl-core 等步驟沒有執行 |
| 正式 run 第 3 次（`make harden-core`） | 325 個完全相同 |
| 正式 run 第 4 次（最後一次 `make phase2`） | 325 個完全相同；接著 gl-core、neg-gl-core、soc-area 都 PASS |

第 2 次與第 3 次的 `resolved.json` 完全相同。逐步比對中間產出的 DEF，第 13–41 步（floorplan 到 post-GRT repair）逐 byte 相同，從第 45 步 `OpenROAD.DetailedRouting`（多執行緒）開始不同。差異很小：slack ≤ 0.0003 ns、線長 6 µm、via 4 個。

處理方式：golden 比對只對實測確實出現差異的族群給明確誤差，誤差約為實測差異的 30–200 倍。這些族群與誤差是：slack 與 clock skew ±0.01 ns，線長、via、功耗、IR drop ±0.1%。其他 metrics 仍必須完全相同，signoff 門檻也不受影響。細節在 `signoff/golden/picorv32_core/README.md`。改成單執行緒 detailed routing 或許能消除差異，但會讓 regression 太慢，所以沒有採用。

## Checker qualification（植入錯誤後，checker 會不會 FAIL）

做法分三輪：
1. 開發時自己做 negative test。
2. 一個沒有參與撰寫的 agent 另外想了 47 個植入錯誤，其中找到漏網的情況。
3. 修正 checker 後，把 `cpu_params.py`、`check_disconnected.py`、`check_signoff.py` 前兩輪的所有案例，在修正後的版本上全部重跑。`run_gl_core.py` 的比對邏輯沒有改（只加了來源檢查），網表案例沿用第 2 輪的結果。

下表是第 3 輪的結果。「真錯誤」指 checker 應該 FAIL 的案例，「正向對照」指沒有錯誤、應該 PASS 的案例。

| checker | 植入錯誤（舉例） | 結果 |
|---|---|---|
| LibreLane 內建 setup checker（9 corner） | 試跑 #4 實際發生：ss corner setup 違規 30 條 | flow 中止，訊息為 `Setup violations found in the following corners: max_ss, min_ss, nom_ss`（證明 `SETUP_VIOLATION_CORNERS = ["*"]` 有作用；預設只看 tt，這三個 corner 會漏掉） |
| `cpu_params.py`（CPU 參數一致） | 14 個真錯誤，例如：參數值改變、少一個或多一個參數、只改 `memmap.vh`、`defparam`、`` `ifdef SYNTHESIS `` 分支不同、config 的 `pdk::` 條件區塊、harden run 實際用的參數不同、格式錯誤 | 14/14 FAIL。2 個正向對照 PASS：數值相等的不同寫法（`65536`、`'h1_0`、`32'd1`），以及兩邊都寫超出 bit 寬的同一個值。另有 2 個合法但寫法不同的情況保守判 FAIL：位置式傳參數、config 寫超出 bit 寬的值。config 加 `VERILOG_DEFINES` 不在這支 checker 的範圍（見已知限制第 9 點） |
| `check_disconnected.py`（沒接線的 pin） | 9 個真錯誤，例如：少一個或多一個 PCPI pin、std-cell 的輸入或電源 pin 沒接、頂層改名、表格被截斷、沒有表格、LibreLane 忽略清單被改 | 9/9 FAIL。正向對照（同一個 PCPI pin 重複列出）PASS。表格改用 ASCII 框線、出現兩份表格時保守判 FAIL |
| `check_signoff.py`（signoff 門檻 + golden） | 50 個真錯誤，例如：LVS／DRC／XOR = 1、任一 corner setup／hold < 0、少一個 corner、corner 名單重複或缺少、slack 是 NaN／inf／1e30（STA 沒有受約束路徑時的值）、`false` 冒充 0、unannotated 114 → 115、每種有誤差的 metric 剛好超出誤差、誤差設定寫錯（0、inf、同時寫兩種）、誤差規則套到 count／area 類 metric、多或少一個 metric | 50/50 FAIL。3 個正向對照 PASS：第 2 次正式 run 的實際差異、誤差範圍內的 slack 變動、35 寫成 35.0。「整體 slack < 0 但每個 corner 都 ≥ 0」這種前後矛盾的 metrics 判 PASS，見已知限制第 9 點 |
| `run_gl_core.py`（GL ISA regression） | 網表植入 10 個錯誤：`mem_wdata[3]` 卡 0、`mem_instr` 反相、除法器 quotient 兩個 bit 對調、ALU mux 輸入對調、暫存器 x8 bit 24 卡 0、`irq_mask[4]` 卡 1、timer bit 3 卡 0、`count_cycle[45]` 卡 1、`count_instr[40]` 卡 1、bus-error IRQ pending 卡 0；另有 3 個來源檢查案例 | 7/10 FAIL，另外 3 個漏網，見已知限制第 7 點。其中 3 個錯誤（`mem_instr`、`irq_mask`、timer）上游 testbench 自己的檢查抓不到，仍印 `ALL TESTS PASSED`，只有 RTL vs GL bus trace 比對抓到。來源檢查 3/3 FAIL：harden run signoff 不是 PASS、沒有 signoff 結果、run 用的參數與 config 不同 |

### 獨立審查找到並已修正的問題

| 問題 | 修正 |
|---|---|
| `cpu_params.py` 看不到 `defparam`、`` `ifdef SYNTHESIS `` 分支、config 的 `pdk::` 條件區塊；也不確認 harden run 實際用了哪些參數 | 讀兩次 soc_top（有／沒有 `SYNTHESIS` define），兩次必須相同；RTL 出現 `defparam` 就 FAIL；有條件區塊就 FAIL；`--resolved` 比對 run 的 `resolved.json`（`run.sh` 與 `run_gl_core.py` 都會檢查） |
| `make gl-core` 不確認網表來自 signoff PASS 的 run | 要求 `runs/picorv32_core_signoff/` 裡的 signoff 與 disconnected 結果都是 PASS |
| `check_signoff.py` 接受 inf／1e30 slack、`false`、誤差 inf、套到 count／area 的誤差規則、重複的 corner 名單 | 全部改為 FAIL（`slack_max` = 一個時脈週期；型別檢查；誤差設定與保護名單檢查；corner 名單必須與 metrics 裡的 corner 完全一致） |
| `check_disconnected.py` 在表格被截斷時判 PASS | 要求表格結尾框線；並檢查 LibreLane 的忽略清單仍是預設值 |
| `timing__unannotated_net_filtered__count` 實際上只檢查得到頂層 port | 改成原始數必須剛好 114，組成寫在 limits 檔 |
| 文件：唯一一次 `make phase2` 其實 FAIL 卻寫 PASS；hold buffer 成因寫錯；`power__total` 機制寫錯；DEF 比對的對象寫錯；使用率定義不清；多處數字不精確 | 全部更正 |

## 與計畫不同的地方

- limits 檔用 TOML（`signoff/limits/picorv32_core.toml`），計畫寫 YAML；理由同 ADR-0005（Python 內建 `tomllib`）。
- §7.2 要求 `timing__unannotated_net__count` = 0。實際是 114，而且每一個都有確定的來源：35 個不用的 PCPI 輸入 port、41 個 tie cell（`conb_1`）輸出、38 個 CTS dummy load 輸出。它們都沒有接到繞線，所以沒有寄生值可以標註。limits 改成「剛好 114」，多一個或少一個都 FAIL。
- golden 比對：§7.2 沒有規定細節。這裡是逐項比對，加上對 detailed routing 雜訊的明確誤差（見上）。
- 計畫 §7.5 的 `make harden D=<design>`（tag = git sha）在這一階段先做成固定 tag 的 `make harden-core`；通用的 harden target 與「工作目錄有未提交修改即 FAIL」的來源追溯（§7.2）留到 Phase 3 做 soc_top 時一起做。
- 計畫 §7.2 的 IR drop ≤ 5% VDD checker 尚未自寫；本階段 worst IR drop 為 0.29 mV（`ir__drop__worst`），只列為資訊。

## 已知限制（帶到後續階段）

1. **hold buffer 的面積成本**：hold 修復前真正 slack < 0 的路徑很少（WNS −0.059 ns，插約 46 顆 buffer 後 TNS 就是 0）。但 resizer 要把 2100 個 endpoint 都推到 0.1 ns 的修復餘裕，最後插了 2230 顆 `dlygate4sd3_1`，約占 standard cell 面積的 11%。Phase 3 面積吃緊時，主要可調的是這個餘裕（`PL_RESIZER_HOLD_SLACK_MARGIN`）。
2. **CTS 的 dummy load 不能關**：OpenROAD 有 `-dont_use_dummy_load`，LibreLane 3.0.14 沒有對應變數；目前靠 clustering 8 控制末端 fanout。
3. **`RUN_POST_GRT_DESIGN_REPAIR` 是 LibreLane 標示的 experimental 功能**：目前穩定約 25 秒。這一步之後的增量 global routing 會印出 `EST-0026 Missing route to pin`，印到 OpenROAD 的上限 1000 次就停止，實際次數不明。最終的 detailed routing、LVS、STA 都 PASS。升級 LibreLane 時要重看。
4. **clock 路徑變長**：`CTS_DISTANCE_BETWEEN_BUFFERS 50` 讓 clock 路徑從 3–4 級 buffer 變 9–10 級。40 ns 下沒有影響，但若要挑戰 25 ns stretch goal，要重新評估。
5. **489 個 lint warning**：446 個 `TIMESCALEMOD` 來自 LibreLane 為 standard cell 產生的 blackbox 檔，43 個在上游 `picorv32.v`；lint error 0。
6. **上游 firmware 的 X 資料**：上游 IRQ 程式會把從沒寫過的暫存器存起來再讀回（PicoRV32 不 reset register file）。trace 中有 84 筆 data 是 X：62 筆在 `irq_regs`（0x204–0x27c），22 筆在 IRQ stack（0x450–0x478）。checker 只允許 data 欄位出現 X，而且 RTL 與 GL 必須完全相同；位址、byte mask、I/D 不得有 X。
7. **GL ISA regression 沒覆蓋到的功能**：上游 firmware 從不讀 `rdcycleh`／`rdinstreth`（64-bit 計數器的高半部），也從不做非對齊存取（會觸發 bus-error IRQ）。所以網表在這些地方壞掉時 gl-core 仍會 PASS。驗證 agent 植入 `count_cycle[45]` 卡 1、`count_instr[40]` 卡 1、bus-error IRQ 卡 0 三個錯誤，都沒被抓到，並另外用定向測試確認這三個錯誤在功能上看得見。SoC 自己的 firmware 也沒有讀計數器，而且讓 bus-error IRQ 保持 masked。要補這個缺口，有兩條路：
   - 用 formal equivalence（計畫 Phase 4 的 L4 `Yosys.EQY`）證明網表與 RTL 等價。
   - 補定向測試：`rdcycleh`／`rdinstreth`，以及 IRQ unmasked 與 masked 兩種情況下的非對齊 load／store／fetch。

   **決定（2026-10-03，使用者）**：採用 formal equivalence，提前到 Phase 3 先做。理由是本專案的目的是先把完整流程建立起來。
   GL 模擬本身是 functional + unit delay，只驗邏輯功能；時序以 9 corner STA 為準。
8. **golden 只在同一環境下逐項比對**：與 `ci_sram_ref` 一樣，換平台（例如 x86_64 Linux）擺放與繞線細節會不同，需要依 golden README 的步驟重新建立。`ci_sram_ref` 的 golden 仍是全部逐項相同；在那個較小的設計上連跑 3 次都相同，但 detailed routing 的非確定性也可能出現在那裡。
9. **checker 的範圍**：
   - `cpu_params.py` 只管 CPU 參數。config 的其他設定（例如加了 `VERILOG_DEFINES`）改變網表時，要靠 golden 比對的 cell 數、面積抓。只改 flow 開關、不影響 metrics 的變更（例如 DRC 設定）golden 抓不到，要靠 code review。
   - `check_signoff.py` 不檢查「整體 slack」與「各 corner slack」是否一致。LibreLane 的整體值就是各 corner 取最差，所以不會不一致。
10. **DIE_AREA 是估計值**：假設 SoC 周邊在 PnR 中的面積成長比例與 CPU 相同；Phase 3 依 ADR-0006 的條件重新檢討。

## 交付物

`pnr/picorv32_core/`（`config.json`、`run.sh`、`cpu_params.py`、`check_disconnected.py`、README）、`signoff/scripts/check_signoff.py`、`signoff/limits/picorv32_core.toml`、`signoff/golden/picorv32_core/`、`dv/gl_core/`（GL regression 與 negative test）、`scripts/soc_area_estimate.py`、ADR-0006、Makefile 的 `harden-core`／`gl-core`／`neg-gl-core`／`soc-area`／`phase2`。
