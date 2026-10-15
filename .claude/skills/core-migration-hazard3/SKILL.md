---
name: core-migration-hazard3
description: 把 SoC 的 CPU 換成另一顆 core 時使用，例子是 PicoRV32（native bus）換成 Hazard3（AHB5 介面的 RISC-V core）。常見症狀：Yosys `check -assert` 報 `core_haddr_d` 沒有 driver（`chparam` 要在 `hierarchy` 之前）、`bus_assert` 報 `addr/wdata/wstrb changed while mem_valid=1`（AHB 讀取時 hwdata 要擋掉）、`exc`／`irq` 測試或 cycle 下限 FAIL（mtval 固定 0、準位中斷只進 1 次、CPI 變小）、植入錯誤在新 core 上漏網（變體映像用了舊 core 的開機程式）、rvcpp 在 riscv-tests 結尾逾時（沒有 fence）、上游測試編不過（要 newlib）。涵蓋 1port／2port、AHB5 寫入資料晚一個 cycle 接 1RW 同步 SRAM、參數陷阱（CSR_COUNTER、mcountinhibit、RESET_REGFILE、EXTENSION_A、hazard3_config.vh 不能用 define 改）、port tie-off、reset 同步器、舊 core 建置保持不變（define＋前置處理比對）、RVFI 逐指令比對、授權，以及 PnR 不能沿用舊 core 調好的設定（resizer corner、弱 cell、上限檔、golden、IR 重量、共用 flow 設定改了每個變體都重 harden）、新 core 先單獨 harden 看全部 signoff corner。Use when migrating an SoC CPU core (PicoRV32 to Hazard3 over AHB5), covering bus timing, configuration pitfalls, verification and PnR re-qualification.
---

# 把 CPU 換成 Hazard3

SoC 層級的驗證改法看 `dv-directed-tests`、`gate-level-simulation`；合成看 `rtl-synthesis-lint`；時序收斂看 `drv-timing-closure`；等價驗證看 `formal-equivalence-eqy`；換 core 後的整合檢查（SRAM 介面）看 `hard-macro-integration`。本 repo 實例：ADR-0011、`docs/phase_exit/phase5.md`（Phase 5 exit review）。

名詞：
- **AHB5**：Arm 的 pipelined 匯流排。一筆傳輸分 address phase（`haddr`、`hwrite`、`hsize`、`htrans`）與下一個 cycle 的 data phase（`hwdata`、`hrdata`）；`hready` 為 0 時 data phase 延長，下一筆的 address phase 也停住。
- **native bus**：PicoRV32 的 `mem_valid`／`mem_ready` 介面，位址、寫入資料、byte strobe 同時送出，`mem_valid` 一直拉著直到 `mem_ready`。
- **RVFI**（RISC-V Formal Interface）：core 每退休一條指令就輸出一組訊號（PC、指令、寫回的暫存器與值、記憶體存取），可以拿來和指令集模擬器逐條比對。
- **ISS**（instruction set simulator）：只模擬指令語意的軟體模型，當參考答案。Hazard3 附的是 `rvcpp`（C++）。
- **reset synchronizer**：讓外部 reset 解除的時間對齊 clock 的電路（非同步拉下、同步放開），避免 recovery／removal 時序違規與毛刺。

## 規則（已驗證：Hazard3 stable `v1.1.1`，commit `8af9929`，查 RTL、文件與本機實驗）

1. **釘 stable，submodule 唯讀**：作者建議 ASIC 用 stable（`Readme.md:45`）。檔案清單 `hdl/hazard3.f` 是 fpgascripts 的 `listfiles` 格式，不是 Verilog 的 `-f`，要轉成專案自己的清單格式；它不含 debug（`hdl/debug/`）與匯流排元件。
2. **參數不能用 `` `define `` 改**：`hazard3_config.vh` 是被 include 進 module 的參數列表（`hazard3_cpu_1port.v:16-18`）。用 instance 參數，或合成時 `chparam`（LibreLane 的 `SYNTH_PARAMETERS`）；Yosys 要先 `chparam` 再 `hierarchy -top`，順序反過來 `check -assert` 會報 `core_haddr_d` 沒有 driver。
3. **預設值的陷阱**（`hdl/hazard3_config.vh`）：
   - `CSR_COUNTER = 0`（第 121 行）：沒有 `cycle`／`instret`，要用就設 1。
   - 設了也不會動：`mcountinhibit` reset 為 1（`hazard3_csr.v:603-605`，「Counters inhibited by default」），firmware 要先 `csrci mcountinhibit, 5`。
   - `EXTENSION_A = 1`（第 37 行）：不需要原子指令就關掉，否則要測它。
   - `RESET_REGFILE = 0`（第 236 行，文件寫預設 1，以 `.vh` 為準）：暫存器堆沒有 reset，4-state 模擬會有 X，firmware 要自己清。
4. **沒用到的 port 也不能浮接**（`doc/sections/configuration_and_integration.adoc` 對應段落）：
   - `DEBUG_SUPPORT=0` 時 `dbg_*` 輸入接 0，**`dbg_sbus_vld` 一定要 0**：1port wrapper 把 debug system bus 放進仲裁（`hazard3_cpu_1port.v:232`）。
   - `pwrup_ack` 接回 `pwrup_req`、`unblock_in` 接回 `unblock_out`（沒開 Xh3power），`fence_rdy` 接 1，`clk_always_on` 接 `clk`，`mhartid_val`、`eco_version` 接 0。
   - 沒有 global monitor 時 `hexokay` 接 1；不回錯誤時 `hresp` 接 0。
5. **AHB5 寫入資料晚一個 cycle，1RW 同步 SRAM 要在同一個上升緣同時拿到位址與資料**：
   - Hazard3 的 store 不經 buffer 直接送上匯流排（`doc/sections/bus_behaviour.adoc:49`），`hwdata` 在 data phase 才出現。
   - OpenRAM macro 在同一個上升緣取樣 `csb/web/addr/din/wmask`，所以不能直接接：做法有 (a) 轉成 native bus 的轉接器（store 等到 data phase 才送）、(b) write buffer、(c) store 的 data phase 用 wait state 擋住下一筆。
   - 子字組寫入：`hwdata` 會把 byte／halfword 複製到每個 lane，byte strobe 要自己由 `hsize` 與 `haddr[1:0]` 算（`hazard3_core.v:1432-1440`）；讀取的 lane 挑選與符號延伸由 core 做。
6. **有副作用的周邊只能在「`htrans[1]=1` 且 `hready=1`」那個 cycle 取樣**：`hready=0` 時同一筆的 address phase 會停在匯流排上好幾個 cycle，否則一次讀取（例如 UART RX 資料暫存器）會被當成好幾次。
7. **沒有 `trap` 輸出腳，例外都進 `mtvec`**：
   - 非法指令、不對齊存取都是 exception（不對齊的存取根本不發到匯流排，`hazard3_core.v:779-786`）。
   - 依賴 trap 腳的 checker 與 negative test 要改成由 firmware 的 exception handler 回報。
   - 直接模式下 exception 與中斷進同一個位址，handler 要讀 `mcause` 區分。
8. **中斷是 level-sensitive 的標準 RISC-V 模型**（`mip.meip`，`mret` 返回）：
   - 沒開 Xh3irq 時所有 `irq` 位元 OR 起來，經一個 flop 變成 `meip`，多 1 cycle（`hazard3_csr.v:466-479`）。
   - IRQ 要維持到來源被清掉；handler 要盡早清，否則返回後可能再進一次。
   - 依賴 PicoRV32「latched IRQ、進入次數固定」的測試，期望值要重新量。
9. **reset 是非同步、active low**（core 內 59 處 `negedge rst_n`）：外部要做 reset synchronizer（`configuration_and_integration.adoc:50, 60, 96`）。由組合邏輯產生的 reset（例如 `resetn & ~host_en`）不能直接接；同步化之後，reset 生效的那個 edge 也跟著變，依賴它的測試要重新定義。
10. **CPI 小很多**：Hazard3 多數指令 1 cycle（`doc/sections/instruction_timings.adoc`），PicoRV32 每條至少 3 cycle。測試裡「至少要跑 N cycle」這類檢查會因為太早完成而 FAIL，cycle 數的上下限要重量。
11. **上游測試要 newlib 工具鏈**：`test/sim/sw_testcases` 全部 `#include <stdio.h>`，`init.S` 要 newlib 的 `_start`；沒有 newlib 的工具鏈（例如 Homebrew `riscv64-elf-gcc`）編不了。riscv-arch-test 的流程是「DUT 的 signature 對 Spike 的 signature」，要 `riscof` 與 `spike`。
12. **rvcpp 是退休指令 trace，不是匯流排 trace**：
    - `--trace` 印每條退休指令的 PC、寫回值、CSR 與 trap（`test/sim/rvcpp/rv_core.cpp:1030-1070`），沒有記憶體寫入的位址資料。
    - 記憶體配置寫死（RAM `0x80000000`，`main.cpp:27-29`），SoC 位址不同要複製一份改。
    - 上游沒有 RTL 對 rvcpp 的逐指令比對工具：定義 `HAZARD3_RVFI_STANDALONE`，`hazard3_cpu_*` 頂層會多出 RVFI port（`hazard3_cpu_1port.v:10`），自己轉成 rvcpp 的格式再比。
    - rvcpp 的 cycle 是固定 1 IPC 的粗略模型，不能和 RTL 的 cycle 比。
13. **工具相容**（本機實測，Phase 5 前置調查）：
    - Icarus `-g2005`、Verilator 5.050 `--lint-only`、Yosys（`proc; check -assert`，無 latch）都直接吃得下。
    - Verilator `-Wall` 只有未使用的參數與訊號類警告，可用「按檔案、按規則」的 waiver 處理。
    - 暫存器堆是 `reg mem[0:31]`，合成成約 1000 個 enable flop（沒有 macro）。
14. **`mtval` 固定為 0**（`doc/sections/csr.adoc:257-261`）：exception 的測試不能期待 `mtval` 是出錯的位址，只能檢查它讀回 0（這樣卡在 1 的位元仍抓得到）。本 repo Phase 5 的 `exc` 測試第一版就是期待位址而 FAIL。
15. **讓舊 core 的建置保持不變**：所有新 core 專用的 RTL 都放在一個 define 下（本 repo：`SOC_CPU_HAZARD3`），再用 `verilator -E` 把舊建置修改前後的 RTL 做前置處理、去掉註解與空白後比對，證明完全相同（Phase 5：只差一個分號換行）。舊建置就能繼續用原本的 golden。
16. **AHB 讀取時的 `hwdata` 沒有意義、會變動甚至是 X**：轉成 native bus 時，讀取要把 `mem_wdata` 固定（本 repo 接 0），否則「valid 期間 addr/wdata/wstrb 不可變」的協定 checker 會 FAIL（Phase 5 第一次模擬就被 `bus_assert` 抓到）。
17. **工具鏈與 lint 的細節**（本機實測）：
    - GCC 16 的 `-march=rv32imc` 不含 Zicsr，CSR 指令要寫 `rv32imc_zicsr`。
    - Verilator 5.050 對 include 進來的標頭檔（`hazard3_config.vh` 等），waiver 要寫在「include 它的 `.v`」上；寫在標頭檔本身沒有作用。
    - Yosys 會對 Hazard3 報兩種可以接受的警告：小陣列展開成暫存器（fetch FIFO 等），以及舊式 `translate_off` 註解（只包住參數檢查的 `$fatal`）。合成檢查要用「檔案＋訊息」的白名單放行，不要整體關掉警告。
18. **中斷進入次數與 CPI 都要重量**（本 repo 實測，Icarus）：
    - 準位中斷、handler 第一個 store 就清掉來源：每次觸發剛好進入 1 次（PicoRV32 閂住中斷是 2 次）。只亮一個 cycle 的脈衝中斷在 Hazard3 上根本不會被接收。
    - 即使轉接器讓每筆存取多 1 cycle，DONE 的 cycle 數仍只有 PicoRV32 的約 50–70%（hello 2377 對 3466、memtest 423k 對 871k）。「至少要跑 N cycle」的下限要依 CPU 分開訂。
19. **依 CPU 分開的 firmware 建置，每條規則都要換掉開機程式**：本 repo 的 firmware 錯誤變體規則寫死了 PicoRV32 的 `start.o`，Hazard3 的變體映像裡出現 PicoRV32 自訂指令，handler 一直重進，S01、M01 兩個植入錯誤因此「漏網」。看到植入錯誤在新 core 上漏網，先確認映像本身對不對。
20. **core 層級驗證（riscv-tests＋ISS 逐指令比對）的做法與陷阱**（本 repo `dv/core_hazard3/`，Phase 5 實測）：
    - 要測的是 SoC 用的設定：從 `hazard3_config.vh` 的預設值加上 SoC 實例的覆寫值自動產生測試台的設定檔，不要手抄（`config_min.vh` 的 `REDUCED_BYPASS`、`RESET_REGFILE` 等就和預設不同）；`W_ADDR`／`W_DATA` 由 `tb.v` 自己宣告，要排除。
    - 上游的 Verilator 測試台 Makefile 可以在命令列覆寫 `BUILD_DIR`、`TBEXEC`、`VINCDIR`、`FILE_LIST`、`VERILATOR`，所有輸出放在 repo 的 `runs/`，submodule 不留任何檔案；riscv-tests 也用 `make -f <src>/isa/Makefile src_dir=...` 在外面建置。riscv-tests 還需要它自己的 `env` 子模組。
    - 上游 `tb.v` 沒有輸出 RVFI：定義 `HAZARD3_RVFI_STANDALONE`，再用 SystemVerilog `bind` 把記錄模組掛進 `tb`，C++ 不用改；上游的 RVFI 程式碼有 `PINMISSING`、`WIDTHTRUNC` 兩種警告，只關這兩種。
    - `rvfi_intr` 表示 trap handler 的第一條指令（exception 也算，riscv-formal 的定義），rvcpp 只在中斷時標記；比對時要把 exception 後的下一條也視為 handler 入口。
    - rvcpp 沒有實作 `fence`（MISC-MEM 一律非法），每支 riscv-tests 都會在結尾的 `RVTEST_PASS` 走錯；用一個最小修補檔讓 `fence` 成為 no-op（`fence.i` 維持非法），並寫明參考模型做了這個修改。
    - rvcpp 的 CSR 模型是全功能設定（4 個 PMP 區域、不同的計數器行為），會在測試環境初始化時探測 PMP 的地方與我們的設定岔開，也通不過 rv32mi 的 csr、illegal、instret_overflow、zicntr。所以逐指令比對只做 user-level（rv32ui／uc／um），從第一個 `test_N` 標籤開始；rv32mi 只用 riscv-tests 的自我檢查。
    - 測試台在 CPU 寫結束暫存器時就停止，3 級 pipeline 裡最多 2 條較早的指令來不及送出 RVFI：ISS 的 trace 結尾可以多 2 條，RTL 不能比 ISS 長。
    - 選配功能沒開的測試（PMP、`fence.i`）要列為「必須 FAIL」，不是直接跳過：它們變成 PASS 就代表設定被改了。
21. **授權**：`hdl/` 全部 Apache-2.0；`example_soc/libfpga`（`ahb_sync_sram.v` 等）是 WTFPL，抄進來要另附授權說明；`example_soc/fpga/pll_*.v` 沒有授權標示，不要用。
22. **PnR 與 signoff：PicoRV32 版調好的設定不能直接沿用**（Phase 5 已驗證，各自的 ADR）
    - resizer 要看到 signoff 的所有慢 corner（ADR-0013）：Hazard3 有比 PicoRV32 長的整週期路徑，用另一個 corner 加餘量代替會漏（`drv-timing-closure` 規則 15）。
    - resizer 會換上的弱 cell 要用新 core 的 run 重查（ADR-0012、`drv-timing-closure` 規則 10）：讓 Hazard3 版第一次 harden 卡住的是兩版共用、RTL 沒改的 UART。
    - CTS 後的 setup 估計在長路徑偏樂觀，開 `RUN_POST_GRT_RESIZER_TIMING`（ADR-0014、`drv-timing-closure` 規則 12）。
    - 上限檔裡依設計結構推導的數字（沒有寄生資料的 driver 數）要用新 core 的 run 重新數，不能從舊 core 的上限檔複製（兩個 CPU 的值不同，ADR-0016 改 CTS 後又各變一次；現值與組成在 `signoff/limits/soc_top*.toml`，寫法看 `signoff-checker-qualification` 規則 4）。golden 另建一份（`signoff/golden/soc_top_hazard3/`），而且要用幾次相同設定的 run 重新量可重現性：Hazard3 版有兩個會改變 cell 數、diode 數的不可重現步驟，PicoRV32 版沒看過（ADR-0015）。
    - 兩個 CPU 的最差 setup 都是 SRAM 讀出的半週期路徑，週期能縮多少受 duty cycle 預算限制（`signoff-criteria` 的 knowledge 檔）。
    - **共用 flow 設定改了，每個變體都要重新 harden**（Phase 5，根因由 ADR-0016 的實驗確認）：為新 core 改的 flow 設定，如果舊 core 也共用（本 repo 的 `check_inputs.py cpu_config` 要求兩份 config 只差 RTL），改完就在每個變體各 harden 一次，不要等結案的 regression。Phase 5 為 Hazard3 改的設定（ADR-0013／0014、44 ns）拿回去跑 PicoRV32，signoff setup −0.113 ns FAIL，根因是兩個 CPU 共用的 CTS 對 SRAM latency 對齊（ADR-0016）。自動防護：開發中沒有；最後一道是結案時的 `make regress-picorv32`（流程上的防線，`cpu_config` 只確認兩份 config 只差 RTL，不會提醒重 harden）。
    - **換 core 後 IR 的依據要重量，不能沿用舊 core 的餘量**（Phase 5 已驗證；`pdn-ir-drop` 規則 12）：Hazard3 的 nom_tt IR 約是 PicoRV32 的 2.5 倍，舊判法（只判 nom_tt）仍 PASS，最壞組合卻超過 20 mV，met5 strap 因此加寬（ADR-0017）。現在的判法是慢 corner 加 CPU max power pattern，pattern 的 VCD 要用新 core 的最終網表重錄。自動防護：每次 harden 的 `ir_worst.py` 與 harden 後的 `make ir-soc`／`ir-caravel` 會在新 core 的 run 上重判。
23. **新 core 放進 SoC 之前先單獨 harden，看全部 signoff corner 的 STA**（提早檢查 D3，流程回顧 ADR-0020；流程文件 4.4；換 core 的方法通用，不限 Hazard3）。
    - 為什麼：Phase 5 直接在 SoC 裡換上 Hazard3，harden 1–5 依序是 resizer 停不下來（弱 cell，ADR-0012）、ss −40°C −4.158 ns（ADR-0013）、−0.381 ns（週期改 44 ns）、−1.131 ns（繞線後才出現的差距，ADR-0014）、PASS；exit criteria「flow 設定只需改 design 層」沒達成，使用者接受為與計畫不同（`docs/phase_exit/phase5.md`）。差 4.158 ns 的是乘除法單元到 register file 的整週期長路徑，ss −40°C 與 ss 100°C 的資料到達時間差約 15%，單獨看新 core 就看得到。
    - 做什麼：新 core 單獨合成並 harden（至少在合成網表上跑全部 signoff corner 的 STA，resizer 看全部 signoff corner，`drv-timing-closure` 規則 15），跑弱 cell 查表（規則 22 第二點），列出低溫 ss 對高溫 ss 延遲比例最大的長路徑。
    - 通過條件：目標週期在所有 signoff corner 都 PASS，或已知差多少、進 SoC 之前由使用者決定。
    - 成本：單獨 harden 一次約 30–40 分鐘（回顧推算）。
    - 自動防護：沒有（流程步驟）；單獨 harden 本身照 4.6 的 checker 判。

## 已知限制（原「待補」；`docs/phase_exit/phase5.md` 已知限制 11 引用這裡）

Phase 5 已在 2026-10-08 結案（`docs/phase_exit/phase5.md`），原本列的 golden 誤差、`neg-eqy-core` 重跑、乾淨 checkout 的 regression 都已做完。沒做的：
- 2port（指令從 SRAM port 1 讀）：沒有用（ADR-0011 選 1port 加轉接器）。要用的話，port 1 要先特性化，pin 在 macro 上邊與右邊（本 repo 的 floorplan 下面對 die 邊緣），可能要重擺 macro。
- riscv-arch-test（`riscof` + `spike`）與 formal（`test/formal/`，要 `sby` 與 SMT solver）在本機沒跑過；core 層級只有 riscv-tests 與 rvcpp 逐指令比對（規則 20）。

## 不在這裡

- SoC 匯流排、周邊、DV checker 的一般寫法 → `dv-directed-tests`、`gate-level-simulation`
- SRAM macro 的整合與 .lib → `hard-macro-integration`、`openram-macro-characterization`；換 macro 的檢查單 → `macro-qualification`
- 合成參數與 lint waiver 的格式 → `rtl-synthesis-lint`

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-05 | Phase 5 前置調查（Hazard3 `v1.1.1` clone，本機實驗） | `sw_testcases/hellow` 編不過（`#include <stdio.h>`）；Yosys `chparam` 放在 `hierarchy` 之後 `check -assert` 報 `core_haddr_d` 沒有 driver | 已驗證：Homebrew 工具鏈沒有 newlib；參數要在展開階層前設定 | 規則 2、11；Phase 5 裝 xPack 工具鏈（使用者決定） | ADR-0011 |
| 2026-10-05 | Phase 5：Hazard3 版 SoC 第一次 RTL 模擬 | `bus_assert` FAIL：`addr/wdata/wstrb changed while mem_valid=1`（讀取時 wdata 變成 X 或亂變） | 已驗證：AHB 讀取時 hwdata 沒有驅動 | 規則 16：讀取時 mem_wdata = 0；之後 hello PASS | `rtl/cpu/soc_ahb2native.v` |
| 2026-10-05 | Phase 5：Hazard3 版 DV | `exc` FAIL 0x30（mtval 不是位址）；`irq` FAIL 0x20（進入 1 次不是 2 次）；memtest／muldiv／bootrom_march 早於 min_cycles；S01、M01 在 Hazard3 上漏網 | 已驗證：mtval 固定為 0；中斷是準位且只進 1 次；CPI 較小；變體映像用了 PicoRV32 的 start.o | 規則 14、18、19；Hazard3 regression 30/30；第一次完整植入錯誤 29/33，修正後重跑漏網與新增的 7 個全部抓到；全部重跑：Hazard3 36/36、PicoRV32 33/33（2026-10-05） | `dv/tests.toml`、`dv/bugs.toml`、`runs/neg_hazard3/summary.json` |
| 2026-10-05 | Phase 5：core 層級驗證（`make core-hazard3`） | rvcpp 在每支 riscv-tests 結尾 timeout；套修補後仍在初始化的 `pmpaddr0` 處與 RTL 岔開；比對 `intr` 旗標 FAIL；結尾長度差 1 | 已驗證：rvcpp 沒有 fence、CSR 模型是全功能設定、`rvfi_intr` 含 exception、pipeline 尾端 | 規則 20；riscv-tests 65/65、不支援 2 支照預期 FAIL、EXTENSION_M=0 植入錯誤 8/8、逐指令比對 48/48（13,881 條） | `dv/core_hazard3/` |
| 2026-10-05／06 | Phase 5：第一次 `make harden-soc CPU=hazard3`（`4461661`） | `OpenROAD.RepairDesignPostGPL failed with an unexpected error`，約 108 分鐘、記憶體 92.9 GB（PicoRV32 版同一步 43 秒） | 已驗證：卡住的不是 CPU 的邏輯，是 RTL 沒改的 UART（`simpleuart.v` 的 `send_divcnt` 比較，兩版共用同一個檔案、不在 `SOC_CPU_HAZARD3` 下）：整顆 SoC 重新合成後，它的比較邏輯用了一顆 `a2111oi_2`，在 ss 100°C 略超過修復的 slew 上限；resizer 把它換成更弱的 `a2111oi_1`，接著進入無窮迴圈（`drv-timing-closure` 規則 10）。兩版的弱 cell 數也不同（`a2111oi_2` 1 → 2、`o41ai_2` 1 → 0） | 換 core 後第一次 harden 前，先對新的合成網表做規則 10 的弱 cell 檢查；修正方式由使用者決定（ADR-0012：排除弱 cell） | `docs/notes/repair_design_loop.md` |
| 2026-10-07 | Phase 5 Hazard3 第 2–5 次 harden（`2251c4a` → `3a28d54`） | 第 2 次 ss_n40C setup −4.16 ns；第 3 次（resizer 看 ss_n40C）−0.381；第 4 次（44 ns）−1.131；第 5 次（開 `RUN_POST_GRT_RESIZER_TIMING`）全部 corner PASS，最差 +0.530 ns；上限檔的 unannotated 數 133 不符 | 已驗證（各自的 ADR 與單步實驗） | 規則 22；ADR-0013、ADR-0014；建 Hazard3 golden | `docs/decisions/0013-*.md`、`0014-*.md`；`signoff/golden/soc_top_hazard3/README.md` |
| 2026-10-07 | Phase 5：為 Hazard3 改的 flow 設定（ADR-0013／0014、44 ns）拿回去跑 PicoRV32（`c976976`） | PicoRV32 signoff setup −0.113 ns（舊設定 43 ns 時 +0.384）：SRAM 半週期路徑的 32 條 `sram_dout0` 各多 1 顆 hold delay cell | 已驗證：根因是 CTS 對 SRAM 的 latency 對齊（ADR-0016），兩個 CPU 共用；Hazard3 也因此拿回 0.59 ns | 兩份 config 一起改（`cpu_config` 要求兩份只差 RTL）；改 flow 設定後兩個 CPU 都要重新 harden，不能只驗新 core | ADR-0016、`runs/p5_pico_h1_signoff/criteria_review.md`（p5h3 worktree） |
| 2026-10-08 | Phase 5 收尾 | Hazard3 的 IR 約是 PicoRV32 的 2.5 倍（nom_tt 18.28 對 7.40 mV），flow 只判 nom_tt 所以 PASS；最壞組合 25.75 mV 超過 20 mV | 已驗證（`pdn-ir-drop` 規則 12） | 換 core 後要重量最壞組合 IR，不能沿用舊 core 的餘量；這次 met5 strap 加寬到 4.8 µm（ADR-0017） | `docs/phase_exit/phase5.md` |
| 2026-10-15 | Phase 0–7 問題總檢討（ADR-0021，`verify_and_merge.md` A4、B8、C3） | 規則 22 引用「`drv-timing-closure` 規則 9、11」，該是規則 15；「共用 flow 設定改了兩個 CPU 都重 harden」與「換 core 時 IR 重量」只在經驗紀錄（2026-10-07、10-08 兩列）；上限檔的 133／125 已被 ADR-0016 改過；「待補」仍寫 Phase 5 未完成 | 已驗證（`review_p4_5.md` R6、R11；`review_skills.md` 1.2 R8、3.1 Q16） | 規則 22 改引用、加兩點、數字改指向上限檔；「待補」改成「已知限制」；開頭的「Phase 5 進行中」與經驗紀錄的「待使用者決定」改成現況 | 本檔 |
