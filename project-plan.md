# Open EDA RTL-to-GDS 專案規劃

版本：v0.3（2026-10-03）　狀態：規劃完成、尚未實作
修訂紀錄：
- v0.3：§5.5 改寫為白話說明（Phase 7 chip-level）；更正 v0.2 中「TinyTapeout 格子太小、放不下 SRAM」的錯誤說法。
- v0.2：納入獨立審查意見（SRAM .lib 可信度、多 corner 設定、DRC／LVS 驗收寫法、firmware 容量、negative test 設計）。

## 0. 一頁摘要

- **目標**：以 100% 開源工具鏈建立一條可重複執行、有 regression test 的 RTL-to-GDS 流程，
  含 SRAM macro 整合，並以開源 RISC-V SoC 當 test vehicle 跑通到 signoff（DRC／LVS／STA PASS）。
- **原始需求的修正**：原訂 SkyWater 90nm（SKY90-FD）開源 PDK 經查證**不可用**（§1.2），
  經確認改用同為 SkyWater 的 **sky130A**（130nm）。流程與設定刻意保持 PDK 無關，
  日後若取得 sky90 NDA PDK 可替換（§9 R1）。
- **三個已確認的決策（2026-10-02）**：
  1. PDK：sky130A，標準元件庫 `sky130_fd_sc_hd`。
  2. RISC-V core：第一階段 **PicoRV32**（純 Verilog、極小、記憶體介面最單純），
     第二階段換 **Hazard3**（活躍維護、RP2350 量產實證）驗證流程可換 core。
  3. RAM：第一階段用 **PDK 內附的預建 OpenRAM macro**（`sky130_sram_2kbyte_1rw1r_32x512_8`），
     第二階段在 x86_64 Linux 用 **OpenRAM 自產**客製 SRAM 與多 corner .lib。
- **最重要的工程判斷**（來自審查，已查證）：預建 SRAM macro 的 .lib 是**解析模型（analytical model）、未經 SPICE 特性化**，
  數值明顯樂觀；因此 silicon 時序目標定 **40 ns（25 MHz）**，25 ns 為 stretch goal，並以保守 padded .lib 做 STA（§6.2）。
- **工具鏈**：LibreLane 3.x（OpenLane 2 的後繼，Nix 原生跑在 Apple Silicon macOS）＋
  Yosys／OpenROAD／Magic／KLayout／Netgen（LibreLane 內建）＋ Verilator／Icarus（模擬）＋ riscv64-elf-gcc（firmware）。

## 1. 背景與關鍵發現

### 1.1 需求
使用者需求原文：「規劃完整 open（EDA + skywater 90nm PDK + RAM）的 RTL to GDS 專案，從網路找 Open RISC-V 來建立流程測試」。
拆解為四件事：(a) 全開源 EDA 流程；(b) SkyWater PDK；(c) 設計中含 RAM（SRAM macro）；(d) 用開源 RISC-V core 當 test vehicle 驗證流程。

### 1.2 SKY90-FD 開源 PDK 現況（查證於 2026-10-02）

| 項目 | 事實 | 出處 |
|---|---|---|
| 計畫宣布 | 2022-07 Google／SkyWater 宣布將開源 90nm FD-SOI PDK（Apache-2.0） | [Google Open Source Blog 2022-07](https://opensource.googleblog.com/2022/07/SkyWater-and-Google-expand-open-source-program-to-new-90nm-technology.html) |
| 主 repo | `google/sky90fd-pdk` 狀態 **Experimental Preview / alpha**；**2026-02-13 封存為 read-only**；最後 push 2023-05-11 | [github.com/google/sky90fd-pdk](https://github.com/google/sky90fd-pdk) |
| 標準元件庫 | `google/skywater-pdk-libs-sky90fd_fd_sc` **2023-09-30 封存**，僅 3 commits，只有 README／LICENSE，**沒有任何 cell（無 .lib／.lef／GDS／Verilog）** | [github.com/google/skywater-pdk-libs-sky90fd_fd_sc](https://github.com/google/skywater-pdk-libs-sky90fd_fd_sc) |
| 工具支援 | OpenRAM `technology/` 只有 freepdk45、gf180mcu、scn3me_subm、scn4m_subm、sky130；LibreLane 內建只有 sky130A/B、gf180mcuD；ORFS platforms 無 sky90 | [OpenRAM technology/](https://github.com/VLSIDA/OpenRAM/tree/stable/technology)、[LibreLane PDK 文件](https://librelane.readthedocs.io/en/latest/usage/about_pdks.html) |
| 唯一的 sky90 開源設計案例 | CORE-V Wally 用 sky90 **NDA 版** PDK，合成需 Synopsys Design Compiler；README 明言「sky130 足以合成 core 但缺記憶體」 | [openhwgroup/cvw README](https://github.com/openhwgroup/cvw) |

結論：**目前不存在可供開源數位流程使用的 SkyWater 90nm PDK**，無標準元件、無 SRAM 產生器支援。

### 1.3 替代 PDK 比較（已選 sky130A）

| PDK | 開源 | 流程支援 | SRAM 來源 | 評估 |
|---|---|---|---|---|
| **sky130A**（SkyWater 130nm） | ✅ Apache-2.0 | LibreLane／ORFS 原生、社群案例最多（ChipFoundry／Caravel、TinyTapeout） | PDK 內附預建 OpenRAM macro ＋ OpenRAM 自產 | **選用**：同為 SkyWater、生態最成熟 |
| IHP sg13g2（130nm BiCMOS） | ✅ | LibreLane／ORFS 支援 | 晶圓廠提供 `RM_IHPSG13_1P_*` macro | 備案：macro power pin 只在 Metal4，LibreLane PDN 整合有已知問題需 workaround（[範例 issue](https://github.com/2AMLogic/sg13cmos5l-protocol-emulator/issues/60)） |
| gf180mcuD（180nm） | ✅ | LibreLane 支援 | OpenRAM **不支援** gf180 SRAM（僅實驗性 ROM） | 不符「含 RAM」需求 |

## 2. 技術選型

| 元件 | 選擇 | 版本／狀態（2026-10 查證） | 理由 | 出處 |
|---|---|---|---|---|
| RTL-to-GDS flow | **LibreLane**（Classic flow） | 3.0.14，2026-09-06 release；FOSSi Foundation 維護 | 唯一在 Apple Silicon macOS **原生**（Nix）執行的完整流程；內建 Yosys／OpenROAD／Magic／KLayout／Netgen；macro 整合有正式 `MACROS` 設定 | [librelane/librelane](https://github.com/librelane/librelane)、[macOS 安裝](https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html) |
| 備援 flow | OpenROAD-flow-scripts（ORFS） | 活躍 | Linux／Docker；內建 `sky130hd/ibex`、`riscv32i` 範例可對照 | [ORFS sky130hd designs](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/master/flow/designs/sky130hd) |
| PDK | sky130A + `sky130_fd_sc_hd` | 由 `ciel` 下載 LibreLane 綁定版本（預設 `~/.ciel`）；**已含 `libs.ref/sky130_sram_macros`**（LibreLane CI 範例即引用 `pdk_dir::libs.ref/sky130_sram_macros/…`） | LibreLane 預設、hd 庫密度最高 | [LibreLane PDK 文件](https://librelane.readthedocs.io/en/latest/usage/about_pdks.html)、[librelane-ci-designs/test_sram_macro](https://github.com/librelane/librelane-ci-designs/tree/main/test_sram_macro) |
| SRAM（第一階段） | PDK 內附預建 OpenRAM macro | open_pdks 現改從 **`fossi-foundation/sky130_sram_macros`** 安裝（`SRAM_URL = ${FOSSI_URL}/sky130_sram_macros`）；fossi fork 含 2025-05 dnwell 包覆 DRC 修正、2025-07 所有 LEF 加 `FOREIGN`；舊的 `efabless/sky130_sram_macros` 停在 2024-10，**不要直接用** | 每顆附 `.gds .lef .v .sp .lvs.sp .html .log` 與 **單一 TT corner** `.lib`（解析模型） | [open_pdks sky130/Makefile.in](https://github.com/fossi-foundation/open-pdks/blob/main/sky130/Makefile.in)、[fossi-foundation/sky130_sram_macros](https://github.com/fossi-foundation/sky130_sram_macros) |
| SRAM（第二階段） | OpenRAM 自產 | stable 分支 2026-10 活躍；release v1.2.48（2024-01） | 可客製尺寸／port，可產 SS／FF .lib；但 `flake.nix` 只支援 **x86_64-linux**，Docker 已 deprecated → 需 Colab 或 Linux VM | [VLSIDA/OpenRAM](https://github.com/VLSIDA/OpenRAM)、[basic_setup.md](https://github.com/VLSIDA/OpenRAM/blob/stable/docs/source/basic_setup.md) |
| RISC-V core（第一階段） | **PicoRV32** | repo **2026-09 封存**（README：no longer under active development），ISC | Verilog-2005、RV32I/IM/IMC 可選、簡單 valid/ready 記憶體介面、附 firmware tests、`testbench.v`、rvfi monitor；封存不影響當 test vehicle | [YosysHQ/picorv32](https://github.com/YosysHQ/picorv32) |
| RISC-V core（第二階段） | **Hazard3** | 2026-08 仍活躍，Apache-2.0 | RV32IMAC+Zb*、3-stage、AHB5；RP2350 量產實證；`hazard3_cpu_1port.v`／`hazard3_cpu_2port.v`、`example_soc/` 可參考 | [Wren6991/Hazard3](https://github.com/Wren6991/Hazard3) |
| 未選 core | Ibex（lowRISC） | 活躍 | 驗證最完整、ORFS 有範例；但 SystemVerilog 需 sv2v／yosys-slang，首次打通流程摩擦較大 | [lowRISC/ibex](https://github.com/lowRISC/ibex) |
| RTL／GL 模擬 | Verilator、Icarus | 本機 Verilator 5.050、Icarus 13.0；lint 用 **LibreLane nix 內的 Verilator** 以求一致 | Verilator 跑 RTL／長 GL regression；Icarus 跑 X 敏感的 GL smoke | 本機 |
| Firmware 工具鏈 | `riscv64-elf-gcc` 16.x（Homebrew，已安裝） | multilib：rv32i／rv32im／rv32iac／rv32imac／rv32imafc；`-march=rv32imc -mabi=ilp32` 編譯與連結已實測 OK；**無 newlib**（`--without-headers`） | PicoRV32 原廠 firmware 是 `-ffreestanding -nostdlib -lgcc`，可直接用；Hazard3 的 coremark／embench 需 libc → Phase 5 前加裝 xPack `riscv-none-elf-gcc` | 本機 |

## 3. 本機環境現況

| 項目 | 現況 | 需要動作 |
|---|---|---|
| 硬體／OS | macOS 26.7.1、Apple Silicon arm64、24 GB RAM、1.4 TB 可用 | 符合 LibreLane 建議（M1+、16 GiB） |
| Nix | 未安裝 | Phase 0 安裝（Determinate installer + FOSSi binary cache，見 §8 Phase 0） |
| LibreLane／OpenROAD／Magic／KLayout／Netgen | 未安裝 | Phase 0 經 `nix-shell` 取得（約 10 分鐘，走 binary cache） |
| sky130A PDK（含 SRAM macro） | 未下載 | Phase 0 由 `ciel` 下載（數 GB） |
| Yosys 0.69（Homebrew） | 已安裝 | 只做獨立快速檢查；**正式流程一律用 LibreLane 內建版本**，避免版本混用 |
| Verilator 5.050、Icarus 13.0、Python 3.14 | 已安裝 | — |
| riscv64-elf-gcc 16.1 | 已安裝，rv32 可用 | 原廠 Makefile 有 `-Werror`，GCC 16 可能出新 warning，必要時覆寫 CFLAGS |
| Docker | 未安裝 | 不需要（LibreLane 走 Nix） |
| x86_64 Linux（OpenRAM 用） | 無 | Phase 6 用 Colab CLI（已有 `~/.local/bin/colab`）或 Lima VM |

## 4. 專案目錄結構（規劃）

```
arvinsa-rtl-gds/
├── project-plan.md                 # 本文件
├── README.md                       # 快速開始、make help
├── Makefile                        # 唯一入口（§7.5）；SHELL=bash、-eu -o pipefail、.DELETE_ON_ERROR
├── env/
│   ├── versions.mk                 # LibreLane tag、PDK hash（ciel）、core／macro commit、toolchain 版本全部釘版
│   ├── check_env.sh                # make env-check 的實作
│   └── setup.md                    # Phase 0 安裝步驟與 smoke test 記錄
├── third_party/                    # 全部 git submodule、釘 SHA、唯讀
│   ├── picorv32/
│   └── hazard3/                    # Phase 5
├── ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/
│   ├── sky130_sram_2kbyte_1rw1r_32x512_8.bb.v   # (* blackbox *)，給 flow 用
│   ├── gen_padded_lib.py            # 由 PDK 的 TT .lib 產生保守 padded.lib（§6.2）
│   ├── padded.lib                   # 產出物，進版控並記錄參數
│   └── sim/                         # VERBOSE=0、加 `timescale 的行為模型副本 + 對 PDK 原檔的 diff
├── rtl/
│   ├── soc/                        # soc_top.v（SRAM instance 直接放這層，名稱 sram0）
│   ├── bus/                        # 位址解碼、rdata register、host write port
│   ├── periph/                     # uart_tx.v、uart_rx.v、gpio.v、test_ctrl.v
│   ├── bootrom/                    # 由 hex 以 script 產生的 case-ROM Verilog
│   └── include/memmap.vh           # 唯一的 memory map 來源（firmware 的 soc.h 由此產生）
├── fw/
│   ├── common/                     # start.S、link.ld、soc.h（產生）、Makefile（含 size checker）
│   └── tests/<name>/               # 每支測試一個目錄
├── dv/
│   ├── tb/tb_soc.v                 # RTL／GL／SDF 共用，用 `define 切換
│   ├── monitors/                   # uart line monitor、signature、X checker、bus assertion、trace dump
│   ├── filelists/rtl.f gl.f        # gl.f 取自 LibreLane resolved config 的 CELL_VERILOG_MODELS
│   ├── tests.yaml                  # 每條 regression test：指令、checker、cycle 上限、golden
│   ├── bugs/bugs.yaml              # bug injection 矩陣（§7.3）：id、層級、植入方式、預期 FAIL 的 checker 與 regex
│   └── scripts/                    # run_sim.py、check_log.py、trace_diff.py、summarize.py（JUnit XML）
├── pnr/
│   ├── ci_sram_ref/                # Phase 0：重跑 LibreLane CI 的 test_sram_macro 當 golden
│   ├── picorv32_core/              # Phase 2：單獨 harden picorv32
│   ├── soc_top/                    # config.yaml、pin_order.cfg、sdc/、sta_extra_corner.tcl
│   └── hazard3_soc/                # Phase 5
├── signoff/
│   ├── golden/<design>/metrics.json
│   ├── limits/<design>.yaml        # §7.2 門檻
│   ├── waivers/<design>.yaml       # 例如 SRAM 內部 full-GDS DRC baseline
│   └── scripts/                    # metrics 比對、antenna／IR／placement checker
├── runs/ sim_build/                # gitignore
└── docs/
    ├── decisions/                  # ADR：每個重大決策一檔（PDK、core、SRAM、時序目標…）
    └── phase_exit/                 # 每階段 exit review 紀錄
```

## 5. Test vehicle 設計規格（Phase 1–4，PicoRV32 SoC）

### 5.1 方塊
- **CPU**：PicoRV32，RV32IMC，`ENABLE_IRQ=1`，`BARREL_SHIFTER=1`（參數比照原廠 `scripts/` 的合成設定，去掉 `ENABLE_TRACE`）。
- **SRAM**：1 顆 `sky130_sram_2kbyte_1rw1r_32x512_8`（2 KB，32-bit word，byte write mask）。
  - LEF 尺寸 **683.1 × 416.54 µm**；power pin `vccd1`/`vssd1` 在 met3 與 met4；OBS 佈滿 met1–met4；**LEF 無 ANTENNA 屬性**。
  - port 0（1RW）pin 在左邊（met3：clk0、csb0、web0、addr0[8:2]）與下邊（met4：din0、dout0、wmask0、addr0[1:0]）；
    port 1 pin 在右邊與上邊。
  - **只用 port 0**；port 1 **必須 tie-off**：`csb1=1`、`clk1=0`、`addr1=0`，`dout1` 不接（LibreLane CI 範例作法）。
    浮接會觸發 `Checker.DisconnectedPins` FAIL、GL sim 出 X、silicon 上是浮動 CMOS 輸入。
  - **SRAM instance 直接放在 `soc_top` 這一層，名稱 `sram0`**，讓 RTL 後門路徑、GL 網表名稱、`MACROS.instances` 三處一致，避免 flatten 後出現 escaped name。
  - **dout0 之後加一級 rdata register（多一個 wait state）**：行為模型在每個 posedge 後 `#(T_HOLD) dout0 = 32'bx`，
    讀出資料只在讀取後第一個 posedge 有效；.lib 中 dout0 為 `falling_edge` launch，SRAM→CPU 是半週期路徑。
    加 register 後半週期路徑只到一顆 flop，不穿過 PicoRV32 的 `mem_rdata_latched` 組合邏輯。
- **Boot ROM**（混合方案）：≤ 64–128 words，Yosys 合成為 case-ROM（由 hex 以 script 產生 Verilog，避開 `$readmemh` 相對路徑問題）。
  內容：reset vector → SRAM march test（signature 輸出到 GPIO）→ loader（UART RX 或 host write port）→ 跳到 SRAM。
- **Host write port**：CPU 在 reset 期間可由外部寫 SRAM；Phase 7 接 Caravel Wishbone 時不必改 RTL。
- **周邊**：UART TX／RX（取材 `picosoc/simpleuart.v`）、8-bit GPIO output、`TEST_CTRL` MMIO（PASS magic + CRC32 signature）、`trap` 輸出腳位。
- **Memory map（草案，單一來源 `rtl/include/memmap.vh`）**：
  `0x0000_0000` SRAM（2 KB）、`0x0001_0000` Boot ROM、`0x0200_0000` UART、`0x0300_0000` GPIO、`0x0400_0000` TEST_CTRL。

### 5.2 程式載入
- Regression：testbench 以 `$readmemh` 後門預載 SRAM 行為模型的 `mem` 陣列，並以 `+skip_boot` 跳過 loader。
- 至少一支 front-door 測試：程式經 UART RX 或 host write port 載入，走完 Boot ROM 全路徑。
- Silicon：Boot ROM 自我測試輸出 signature；loader 載入程式。

### 5.3 firmware 容量
PicoRV32 原廠 `firmware/sections.lds` 設 `LENGTH = 0x18000`（96 KB，另留 32 KB stack），**2 KB SRAM 裝不下**。因此：
- **L1a（core 層級 ISA regression）**：原封不動在 `third_party/picorv32` 跑上游 `make test`（含 rvfi monitor 的 `test_rvf`、`test_synth`）。
- **L1b（SoC 層級）**：自寫測試，每支 ≤ 2 KB − stack − signature 區；firmware Makefile 含 size checker，超過即 FAIL。
- memtest 不得覆寫自己所在區域：從 Boot ROM 執行，或 code 區與測試區分開。

### 5.4 時序與面積目標
- **silicon 目標 `CLOCK_PERIOD = 40 ns`（25 MHz）；25 ns 為 stretch goal。** 依據：
  - 預建 macro 的 .lib 是解析模型：產生 log 寫 `Analytical model enabled`、`Characterization is disabled (using analytical delay models)`；
    .lib 的 clk→dout0 只有 0.38–0.53 ns、`min_period 1.956`，明顯樂觀。
  - OpenRAM 團隊 ISCAS'23 論文對 1 KB 1rw1r macro 的矽量測：≥1.7 V、雙 port 同時讀時 < 34 MHz 無錯誤
    （[OpenRAM in SkyWater 130nm](https://escholarship.org/content/qt9dc0v8g3/qt9dc0v8g3.pdf)）。
  - LibreLane CI 範例 `test_sram_macro` 以 25 ns 收斂（2 × 1 KB、DIE_AREA 750 × 1250 µm）。
- `FP_SIZING=absolute`；`DIE_AREA` **待 Phase 2 實測 PicoRV32 cell 數後決定**。粗估：SRAM 含 10 µm halo 約 0.30 mm²，
  PicoRV32（IMC+IRQ+MUL/DIV）+ 周邊以 50% 密度估 0.4–0.55 mm²，合計約 1.0 × 0.9 mm 起。
- **擺放**：SRAM 放右上角、orientation N，讓 port 0 的左邊／下邊面對 logic；右邊與上邊留 ≥ 20–30 µm channel 給 port 1 tie 線與 PDN；
  以 `pin_order.cfg` 把 IO pin 限制在左邊與下邊。下邊的 met4 pin 易與 met4 PDN strap 衝突，留意 `Checker.TrDRC` 與 `DisconnectedPins`。

### 5.5 交付層級與 Phase 7（chip-level，可選）

**主線（Phase 0–6）的產出是 macro-level hardening，還不是一顆晶片。**
產出物是一個 hard macro，也就是一塊已經擺好元件、繞好線的電路方塊，含 GDS、LEF、.lib、網表。
它沒有 I/O pad 和 seal ring，也沒有把程式載進去、把結果讀出來的通道，所以不能單獨下線。

**Phase 7 要解決的是：做好的電路怎麼變成一顆能下線、能拿回來測的晶片。**
這個階段是可選的，Phase 0–6 都不依賴它。做法是借用現成的載具晶片，而不是自己從頭做 padframe。

#### 首選：ChipFoundry Caravel

- **Caravel 是什麼**：一顆現成的載具晶片，pad、電源和一顆管理用的 RISC-V 都已經做好，中間留一塊空白的使用者區。
  把設計放進使用者區，再和其他人的設計一起搭 MPW shuttle（很多設計共用同一套光罩一起下線）。
- **使用者區的外框**叫 `user_project_wrapper`，大小固定為 **2920 × 3520 µm**
  （[chipfoundry/caravel_user_project](https://github.com/chipfoundry/caravel_user_project/blob/main/openlane/user_project_wrapper/config.json) 的 `DIE_AREA`，2026-10-03 查證）。
- **ChipFoundry** 是 Efabless 於 2025 年停止營運後，接手 sky130 共乘下線服務的公司（§9 R12）。
- **為什麼是首選**：使用者區夠大，SRAM 與 CPU 可以寬鬆擺放；管理 CPU 可經 Wishbone 匯流排存取使用者區，
  正好對上 §5.1 預留的 host write port，讓管理 CPU 把程式寫進我們的 SRAM，到 Phase 7 不必改 RTL。

#### 設計放進使用者區的方式：扁平放法（flat wrapper）

```
巢狀放法：不採用
user_project_wrapper
└── soc_top：先 harden 成一個 macro
    ├── PicoRV32 與周邊電路
    └── SRAM macro

扁平放法：計畫採用
user_project_wrapper
├── PicoRV32 與周邊電路：直接在這一層擺放與繞線
└── SRAM macro：直接放在這一層
```

不用巢狀放法，是因為金屬層不夠分：
1. sky130 除了 local interconnect（li1）之外只有 met1–met5 五層金屬，電源網路（PDN）用最上面的 met4、met5。
2. 若 `soc_top` 先做成 macro，met5 要留給外層 wrapper，`soc_top` 自己只能用 met4 配電。
3. SRAM 的電源環也在 met4。LibreLane 的 PDN 是用 via 連接上下兩層，同一層的兩條線預設不會接，SRAM 可能根本沒接到電。
4. 扁平放法讓 wrapper 用 met5 從 SRAM 上方打 via，往下接到 met4 電源環，問題就不存在。

#### 收件門檻與工時

- **平台 precheck PASS**：ChipFoundry 收件前會自動跑一套檢查，例如 DRC、LVS，以及 wrapper 的尺寸與腳位是否和官方範本一致；沒有 PASS 就不收件。
- **工時「另估」**：要不要真的下線、搭哪一梯次、費用多少都還沒討論，因此不估工時。

#### 備選：TinyTapeout（待確認）

v0.2 曾寫「TinyTapeout 格子太小、放不下 SRAM」，**這個說法是錯的**，v0.3 更正如下（2026-10-03 查證）：

- sky130A 現行格子尺寸最大到 8x4 = 1378.16 × 511.36 µm；5x4（856.52 × 511.36 µm）以上就放得下 2 KB SRAM（683.1 × 416.54 µm）
  （[tt-support-tools `tech/sky130A/tile_sizes.yaml`](https://github.com/TinyTapeout/tt-support-tools/blob/main/tech/sky130A/tile_sizes.yaml)）。
- SKY25a 梯次已有 OpenRAM 開發者把小型 OpenRAM SRAM（約 300 × 150 µm）放進 2x2 格子做測試晶片
  （[tt_um_openram_top](https://github.com/TinyTapeout/tinytapeout-sky-25a-sources/tree/main/tt_um_openram_top)）。
- 但 TinyTapeout 官方 memory 規格頁對 sky130 只列出 DFF、latch、DFFRAM 與外接 SPI RAM，**沒有把 OpenRAM SRAM macro 列為正式選項**
  （[tinytapeout.com/specs/memory](https://tinytapeout.com/specs/memory/)）。

要改走 TinyTapeout，需先確認：
1. precheck 是否接受 SRAM macro 內部的特殊 DRC 規則（§6.3）。
2. 4 列高大格子的費用。
3. 格子本身是嵌在 TinyTapeout 大晶片裡的一個區塊，等於上面說的巢狀情況，SRAM 的配電方式要照 TinyTapeout 的規範另外確認。
4. 每個格子的 I/O 腳數是否夠用（程式載入、UART、signature 輸出）。

## 6. 流程設定要點（LibreLane）

### 6.1 Macro 宣告
```yaml
MACROS:
  sky130_sram_2kbyte_1rw1r_32x512_8:
    gds: [pdk_dir::libs.ref/sky130_sram_macros/gds/sky130_sram_2kbyte_1rw1r_32x512_8.gds]
    lef: [pdk_dir::libs.ref/sky130_sram_macros/lef/sky130_sram_2kbyte_1rw1r_32x512_8.lef]
    vh:  [dir::../../ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sky130_sram_2kbyte_1rw1r_32x512_8.bb.v]
    lib: {"*": [dir::../../ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/padded.lib]}
    instances:
      sram0: {location: [X, Y], orientation: N}
```
- flow 一律用 `(* blackbox *)` 的 `.bb.v`；**行為模型 `.v` 不得進 `VERILOG_FILES`**（含 `#(DELAY)` 會觸發 `Checker.LintTimingConstructs`，Yosys 也會試著合成 `mem`）。
- `nl`／`pnl` 留空（SRAM 沒有 gate-level netlist），`STA_MACRO_PRIORITIZE_NL` 維持預設。
- 電源：RTL 以 `` `ifdef USE_POWER_PINS `` 接 `vccd1`/`vssd1`，再加 `PDN_MACRO_CONNECTIONS` 當保險；`PDN_CONNECT_MACROS_TO_GRID` 預設 True。
  LibreLane 有尚未關閉的 PDN 未連到 macro 的 issue，靠 `Checker.PowerGridViolations` 與 negative test 守住。

### 6.2 多 corner STA 與 SRAM .lib
LibreLane 對 sky130 的實際預設（`librelane/config/pdk_compat.py`）：`STA_CORNERS` 9 個（nom/min/max × tt/ss/ff）；
`TIMING_VIOLATION_CORNERS = ["*tt*"]`，即 **setup checker 預設只在 TT corner 判 FAIL**；max slew／max cap 預設不判 FAIL。
某 corner 若找不到 macro 的 .lib 又沒有 nl+spef，該 corner 會把 macro 當 black box 且**不報錯**（文件：may miss boundary timing violations）。

因此：
1. `gen_padded_lib.py` 從 PDK 的 TT .lib 產生 **padded.lib**（工程假設值，例如 clk0↓→dout0 ≥ 5 ns、setup ≥ 1 ns、min_period ≥ 30 ns），
   以 `lib: {"*": …}` 餵給全部 9 個 corner；參數記在 ADR，Phase 6 以 OpenRAM SPICE 特性化結果校正。
2. 設定（變數名以 LibreLane 3.0.14 文件為準）：
   ```yaml
   SETUP_VIOLATION_CORNERS: ["*"]
   HOLD_VIOLATION_CORNERS:  ["*"]
   MAX_SLEW_VIOLATION_CORNERS: ["*"]
   MAX_CAP_VIOLATION_CORNERS:  ["*"]
   STA_EXTRA_CORNER_TCL_FILE: dir::sta_extra_corner.tcl   # 官方標示 Experimental
   ```
3. `sta_extra_corner.tcl` 依 corner 名稱對 `sram0` 加 derate：`*ss*` → `set_timing_derate -late -cell_delay 1.5`，`*ff*` → `-early 0.7`。
   因為是實驗性 hook，**必須有 negative test**（derate 設 10 → setup 必 FAIL）證明它有作用。
4. 已知殘餘風險：TT .lib 套到 FF 時，SRAM→flop 的 hold 偏樂觀；在報告中明示。

### 6.3 DRC／LVS／XOR 策略
事實：2 KB macro 自身產生 log 記 `DRC Errors … 32`（1 KB 為 10），LVS match；sky130 SRAM 用特殊 DRC ruleset；
LibreLane CI 範例至今設 `MAGIC_DRC_USE_GDS: false`、`QUIT_ON_MAGIC_DRC: false`、`RUN_KLAYOUT_XOR: false`；
`MAGIC_EXT_USE_GDS` 預設 false，所以 **LVS 中 SRAM 是 black box，只驗到 pin 連接**。

採用：
- (a) Magic DRC 以 LEF abstract 做（`MAGIC_DRC_USE_GDS=false`），`ERROR_ON_MAGIC_DRC` 保持 true，要求 = 0。
- (b) full-GDS DRC 另跑成不擋流程的報告，自寫 checker 要求：所有 violation 都在 SRAM bbox 內，且數量 ≤ macro 單獨跑的 baseline（記在 `signoff/waivers/`）。
- (c) LVS PASS，報告註明 SRAM 為 black box。
- (d) XOR 先實測；若差異只出在 SRAM 內，用 baseline 或區域排除，不全域關掉。
- **不要**全域設 `QUIT_ON_MAGIC_DRC=false` 或 `ERROR_ON_MAGIC_DRC=false`，那會把 top-level 真正的 DRC 一起蓋掉。

### 6.4 Antenna
SRAM LEF 無 `ANTENNA` 屬性，antenna checker 看不到接到 SRAM 輸入的 net，「antenna = 0」不代表安全。
開 `RUN_HEURISTIC_DIODE_INSERTION`（或在 SRAM 輸入前就近放 buffer），並自寫 checker：接到 SRAM input pin 的 net wire length ≤ 門檻。

## 7. 驗證計畫

### 7.1 驗證層級與 checker

| 層級 | 內容 | checker（PASS 條件） |
|---|---|---|
| L0 Lint | `Verilator.Lint`（LibreLane nix 內版本）+ `Checker.LintErrors/LintWarnings` | 0 error；warning 白名單外為 0 |
| L1a Core ISA regression | 上游 picorv32 `make test`、`make test_rvf`（rvfi monitor 即時檢查 ISA 語意）、`make test_synth` | 上游 testbench PASS |
| L1b SoC RTL sim | 自寫 firmware：hello、memtest（march C−、address-in-address、byte-lane、涵蓋全部位址）、irq、uart、front-door load | 見下列 sim checker 全 PASS |
| L2 Synth + GL sim | Yosys 網表；`Checker.YosysUnmappedCells`、`YosysSynthChecks`（無 latch）、`NetlistAssignStatements`；GL sim 以 `sky130_fd_sc_hd` Verilog model（`-DFUNCTIONAL -DUNIT_DELAY=#1`）+ SRAM 行為模型 | checker 全 PASS；**RTL vs GL bus transaction trace 逐 cycle 一致**（主 checker）；cell count／FF 數在 golden ±10% |
| L3 PnR signoff | LibreLane Classic 全流程 + §7.2 metrics 比對 | §7.2 全 PASS |
| L4 Equivalence | `Yosys.EQY`（RTL vs 最終網表） | PASS |
| L5 Post-layout GL sim | powered netlist（`-DUSE_POWER_PINS`，TB 驅 VPWR/VGND）；SDF 只作參考 | firmware PASS；SDF annotation 警告數 = baseline |

**sim 層級 checker（L1b／L2／L5 共用）**：
1. 測試結束協定：firmware 寫 `TEST_CTRL` 的 PASS magic + CRC32 signature；只認明確 PASS，沒寫、寫兩次、signature 不符都 FAIL。
2. `trap` 一拉起即 FAIL。
3. 每支測試在 `tests.yaml` 設 cycle 上限，timeout 即 FAIL。
4. UART line monitor：依 baud rate 解碼 TX 實際波形比對 golden，framing error 即 FAIL（不能只看 bus write）。
5. GPIO signature 序列比對。
6. Bus protocol assertion：valid 拉起後到 ready 前 addr/wdata/wstrb 不可變；wstrb 只能是合法樣式；存取未映射位址或寫 ROM 即 FAIL。
7. X/Z checker（Icarus）：reset 後 N cycle 檢查 bus 輸出與 IO；在 CPU 取用的那個 cycle 檢查 `mem_rdata`；不檢查 `dout0`（T_HOLD 期間本來就是 X）。
8. Log scanner：ERROR／FATAL、SRAM 模型的 "Writing and reading … simultaneously"、iverilog port width warning、SDF "Unable to find"；白名單外全 FAIL。
9. RTL vs GL trace diff：同一份 firmware，比對 (cycle, addr, wdata, wstrb, rdata)。
10. firmware size 預算 checker。

**GL sim 注意**：sky130 timing model 的 UDP 靠 `$setuphold` 產生 delayed net，Icarus 支援有限，所以一定用 `FUNCTIONAL`；
SRAM 模型在 posedge 用 blocking assignment 取樣，flop 若 zero-delay 會 race，所以要 `UNIT_DELAY`。
SRAM 模型沒有 `timescale`、`VERBOSE=1`，以 `ip/sram/.../sim/` 的副本處理並記 diff。
Verilator 是 2-state 看不到 X：X 敏感的 GL smoke 用 Icarus；長測試用 Verilator 加 `--x-assign unique --x-initial unique` 多 seed。
**Icarus 的 SDF sim 不能當 signoff 證據**（不支援 TIMINGCHECK、delayed-net 結構下 IOPATH 標註不可靠、SRAM 模型無 specify）；
真要做就用 CVC（x86_64 Linux），signoff 以 9 corner STA + margin 為準。

### 7.2 Signoff metrics（讀 `final/metrics.json`，對照 `signoff/limits/` 與 golden）

| 類別 | metric 與門檻 |
|---|---|
| timing | `timing__setup__ws__corner:*` ≥ 0（9 corner 全部）；nom_tt setup WS ≥ 10% 週期；`timing__hold__ws__corner:*` ≥ 0；max slew／cap／fanout violation = 0 |
| STA 完整性 | `timing__unannotated_net__count` = 0；無 unconstrained endpoint |
| 防止邏輯被整個優化掉 | `design__instance__count` 在 golden ±10%；FF 數在預期範圍；SRAM instance 數 = 1 |
| 實體 | `route__drc_errors` = 0；antenna violating nets/pins = 0（LibreLane 只報告不判 FAIL，自寫）；IR drop ≤ 5% VDD（自寫）；`route__wirelength__max` ≤ 門檻 |
| 擺放 | 從 DEF 抓 `sram0` 的 (x, y, orient) 與 config 比對，不可漂移 |
| signoff | `magic__drc_error__count` = 0（abstract）；full-GDS DRC 依 §6.3 baseline；`design__lvs_error__count` = 0；XOR = baseline |
| 來源追溯 | 每次 run 記錄 git sha、LibreLane 版本、PDK hash；signoff run 時工作目錄有未提交修改即 FAIL |

### 7.3 Negative test（bug injection）矩陣
原則：每一列必須「在**預期的** checker FAIL，且訊息符合 regex」才算該 negative test PASS；FAIL 在別處視為 negative test 本身 FAIL。
植入方式：RTL 只在自寫 glue logic 用 `` `ifdef BUG_xx ``，`third_party/` 一律不動；netlist／GDS 用 script 改；
LibreLane 用 `--override-config`、`--with-initial-state`，或 `python3 -m librelane.steps run --id <Step>` 只跑單一 step。

| ID | 層級 | 植入 | 預期 FAIL 的 checker |
|---|---|---|---|
| R01 | RTL | wmask[0]↔[1] 對調 | sb/sh 測試、memtest byte-lane |
| R02 | RTL | addr0[8] stuck-0 | memtest address-in-address（同時證明 memtest 涵蓋上半部位址） |
| R03 | RTL | mem_ready 提早一拍 | X checker（Icarus）、trap 或 timeout |
| R04 | RTL | UART divider 偏 5% | UART line monitor（signature 可能仍 PASS，這正是要證明的點） |
| R05 | RTL | IRQ 斷線 | irq 測試 timeout |
| R06 | FW | 不寫 PASS（無窮迴圈）／執行非法指令 | timeout／trap（確認不會被當成 PASS） |
| R07 | RTL | 位址解碼重疊 | bus assertion |
| G01 | GL | 修改 pnl，對調兩條 din0 net | GL memtest + `Checker.LVS`（交叉驗證） |
| G02 | GL | TB 以 `force` 讓一顆內部 flop stuck | GL regression |
| P01 | STA | SDC `set_clock_uncertainty -setup` 加大 | `Checker.SetupViolations`（只重跑 `--from OpenROAD.STAPostPNR --to Checker.SetupViolations`） |
| P02 | STA | SDC `-hold` 加大 | `Checker.HoldViolations` |
| P03 | STA | `MAX_TRANSITION_CONSTRAINT` 設很小 | `Checker.MaxSlewViolations`（需先完成 §6.2 設定；順便證明預設設定的漏洞） |
| P04 | STA | SRAM derate 設 10 | setup FAIL（證明 extra corner tcl 有作用） |
| P05 | PDN | `PDN_CONNECT_MACROS_TO_GRID=false` **並**移除 RTL 電源連接 | `PowerGridViolations` 和／或 LVS（記錄實際是哪一個）。註：只拔 `PDN_MACRO_CONNECTIONS` 很可能不會 FAIL |
| P06 | 實體 | 關掉 antenna repair 與 diode 插入 | 自寫 antenna checker |
| P07 | 實體 | PDN pitch 放大 4 倍 | 自寫 IR checker |
| P08 | 實體 | csb1 浮接 | `Checker.DisconnectedPins` |
| P09 | 實體 | 改 SRAM 座標／halo 設 0 | 擺放 checker／`IllegalOverlap`／`TrDRC` |
| P10 | signoff | 在 GDS 加一個 met2 最小寬度違規 | `Checker.MagicDRC`／`KLayoutDRC` |
| P11 | signoff | 只改 KLayout 那份 GDS | `Checker.XOR` |
| P12 | 合成 | 讓某個輸出變常數 | cell count／FF 數下限 checker |

不採用「`CLOCK_PERIOD` 設 2 ns」：FAIL 位置不確定（resizer 跑很久、slew/cap 先爆、甚至 crash）且耗時，改用 P01。

### 7.4 回歸穩定性
- `env/versions.mk` 釘住 LibreLane、PDK hash（ciel）、core／macro commit、toolchain；變動需同時更新 lock、golden 與 ADR。
- 每個 job 輸出 `result.json`；**只認明確 PASS**，「沒看到 FAIL」不等於 PASS。
- golden 更新需 `make golden-update` 明確執行並經 review。

### 7.5 Makefile targets（分層）

| 層級 | target | 內容 | 時間預算 |
|---|---|---|---|
| smoke（每次 commit） | `make smoke` | `env-check lint fw regress-rtl-smoke` | < 5 分 |
| | `make regress-rtl` | L1b 全部 | |
| | `make core-stock` | L1a：上游 `test`、`test_rvf` | |
| nightly | `make neg-rtl` | R01–R07，結果反轉判定 | |
| | `make harden D=soc_top` | LibreLane，tag = git sha | |
| | `make signoff-check D=…` | metrics 對照 limits 與 golden（`python3 -m librelane.common.metrics compare`） | |
| | `make regress-gl-smoke` | Icarus、X 敏感、trace diff | |
| weekly／full | `make neg-pnr` | P01–P12（盡量只跑單一 step） | |
| | `make regress-gl-full` | Verilator 多 seed | |
| | `make sim-sdf` | 可選，CVC on x86 | |
| 維護 | `make golden-update`、`make report` | 更新 golden（需 review）；彙整 PASS/FAIL 表與 JUnit | |

## 8. 階段里程碑與 exit criteria

| Phase | 內容 | Exit criteria | 粗估工時 |
|---|---|---|---|
| **0 環境** | 安裝 Nix（Determinate installer + FOSSi cache：`extra-substituters = https://nix-cache.fossi-foundation.org`）；`git clone https://github.com/librelane/librelane && cd librelane && nix-shell && librelane --smoke-test`；`ciel` 下載 sky130A；**重跑 `librelane-ci-designs/test_sram_macro` 當 golden**；確認 PDK 內 SRAM LEF 含 `FOREIGN`；記錄 PDK hash（以 LibreLane tag 的 `pdk_hashes.yaml` 為準）；確認 toolchain 能編 picorv32 firmware；建 repo 骨架與 `versions.mk` | smoke test PASS；`test_sram_macro` 以 25 ns 全 PASS；版本與 hash 全部記錄 | 1 天 |
| **1 RTL + firmware** | submodule picorv32；寫 `soc_top`（SRAM `sram0` 在頂層、rdata register、port 1 tie-off）、bus、周邊、Boot ROM、host write port；memmap 單一來源；L1a 上游測試；L1b 自寫測試與全部 sim checker；R01–R07 | L0、L1a、L1b PASS；R01–R07 全部在預期 checker FAIL | 3–4 天 |
| **2 流程打通（單獨 harden PicoRV32）** | 單獨 harden `picorv32`（不含 SRAM；參數同 §5.1），在 final 網表上跑上游 `testbench.v -DSYNTH_TEST`（完整 GL ISA regression），取得實測面積與時序 | GDS 產出；abstract DRC = 0、LVS PASS、9 corner setup/hold = 0 @ 40 ns；GL ISA regression PASS；據此決定 `DIE_AREA` | 1–2 天 |
| **3 整合預建 SRAM macro** | §6 全部設定（MACROS、padded.lib、corner 設定、derate tcl、DRC 策略、antenna）；手動 placement；P01–P12 | GDS 含 macro；§7.2 全 PASS（含 9 corner）；full-GDS DRC 只在 SRAM 內且 ≤ baseline；L2 GL sim（含 SRAM 模型）PASS；P01–P12 全部在預期 checker FAIL | 3–5 天 |
| **3.5（可選）OpenRAM .lib 校正** | 提前建 OpenRAM 環境（Phase 6 的環境），對同一 2 KB config 跑 SPICE 特性化產 TT/SS/FF .lib，取代 padded.lib 的假設值。**2026-10-04 使用者決定改為本機 ngspice 直接量 PDK 附的 macro 網表，5 個 PVT 全部實測，OpenRAM 環境延到 Phase 6（ADR-0010）** | 多 corner .lib 進版控；重跑 Phase 3 signoff PASS | 2–3 天（含數小時執行） |
| **4 signoff 收斂與文件** | 嘗試壓到 25 ns；L4 EQY；L5 GL sim；IR drop／antenna checker；`make regress` 一鍵；README、ADR、phase_exit | `make regress` 全 PASS；第三人可依 README 重現 | 2–3 天 |
| **5 換 Hazard3** | submodule Hazard3；**AHB5 寫入資料在 data phase，接 1RW SRAM 需 write buffer 或 wait state**；建議用 `hazard3_cpu_2port`，SRAM port 1 負責 I-fetch（1rw1r 的自然用法）；測試以 Hazard3 的 rvcpp ISS trace 比對；加裝 xPack toolchain（newlib） | L0–L5 全 PASS；flow 設定只需改 design 層 | 4–6 天 |
| **6 OpenRAM 自產 SRAM** | x86_64 Linux（Colab 優先，備案 Lima）：`nix develop` + `make sky130-pdk` + `make sky130-install`（需 `sky130_fd_bd_sram`，不在 ciel 預設內）；產 2 KB（或客製）macro + 多 corner .lib；對 macro 跑 DRC／LVS；GDS cell 名稱衝突 checker（open_pdks 以 `gds_import_sram.tcl` 處理 SRAM 共用 cell 名）；取代預建 macro 重跑 Phase 3–4 | 自產 macro DRC／LVS 結果 ≤ 預建 baseline；SoC 以自產 macro 完成 signoff | 4–6 天（2 KB 解析模式即約 4.4 小時，SPICE 特性化更久） |
| **7 chip-level（可選）** | 把 SoC 放進 ChipFoundry Caravel 的使用者區，搭 MPW shuttle 下線；採扁平放法，PicoRV32 與 SRAM 直接放在 wrapper 層（理由見 §5.5）；TinyTapeout 為待確認的備選 | ChipFoundry 收件前的自動檢查（precheck）PASS | 另估（是否下線、梯次、費用未定） |

## 9. 風險與對策

| # | 風險 | 影響 | 對策 |
|---|---|---|---|
| R1 | 使用者原訂 sky90；開源版不存在 | 製程節點與原需求不同 | 已改 sky130A；PDK 相依集中在 `pnr/*/config.yaml`（`PDK`／`STD_CELL_LIBRARY`／`MACROS` 路徑）與 `ip/sram/`，日後取得 sky90 NDA PDK 可替換；但 sky90 無開源 SRAM 產生器，RAM 需另解 |
| R2 | 預建 SRAM .lib 為解析模型且只有 TT；LibreLane 預設只在 TT 判 setup FAIL | STA PASS 不代表 silicon 能動 | §6.2：padded.lib 餵 9 corner、全 corner 判 FAIL、derate hook + negative test；silicon 目標 40 ns；Phase 3.5/6 以 SPICE 特性化校正 |
| R3 | SRAM 特殊 DRC ruleset；LVS 中 SRAM 為 black box | DRC「= 0」寫不到；LVS 只驗 pin | §6.3 分 abstract／full-GDS 兩層、baseline + waiver；報告明示 |
| R4 | port 1 浮接 | DisconnectedPins FAIL、GL X、silicon 浮動輸入 | tie-off（§5.1）；P08 守住 |
| R5 | PDN 未連到 macro；met4 pin 與 strap 衝突 | floorplan／LVS FAIL 或 silicon 無電 | USE_POWER_PINS + PDN_MACRO_CONNECTIONS；手動 placement 留 channel；PowerGridViolations + P05 |
| R6 | SRAM LEF 無 ANTENNA 屬性 | antenna = 0 是假象 | heuristic diode insertion；自寫 wire length checker；P06 |
| R7 | OpenRAM 只支援 x86_64-linux；本機 Apple Silicon | Phase 3.5/6 無法在本機跑 | Colab（x86 原生，但有斷線風險 → 分段執行、checkpoint）；備案 Lima（x86 模擬慢數倍）或雲端 x86 VM |
| R8 | 2 KB 裝不下原廠 firmware | L1 設計失效 | §5.3 拆 L1a／L1b + size checker |
| R9 | Icarus SDF sim 證據力弱 | L5 無法當 signoff | signoff 以 9 corner STA 為準；SDF 僅參考；CVC 可選 |
| R10 | 40 ns 仍不收斂 | 時序 FAIL | 放寬 clock；`SYNTH_STRATEGY` 改 delay 導向；rdata register 已內建 |
| R11 | PicoRV32 封存；toolchain 無 newlib；GCC 16 + `-Werror` | 無人修 bug；Hazard3 benchmark 編不出；原廠 Makefile 可能失敗 | 釘 commit；Phase 5 前裝 xPack；必要時覆寫 CFLAGS |
| R12 | Efabless 已停止營運（2025），shuttle 由 ChipFoundry 承接 | Phase 7 平台變動 | 以 ChipFoundry 現行 Caravel 文件為準；TinyTapeout 為備選，SRAM 支援、配電方式與費用待確認（§5.5） |
| R13 | 磁碟／時間：Nix store + PDK 約 10–20 GB；full flow 數十分鐘 | 迭代慢 | 1.4 TB 可用；regression 分 smoke／nightly／weekly（§7.5） |

## 10. 驗收標準（Definition of Done）
1. `make regress` 在乾淨 checkout 上一鍵 PASS，並產出 `signoff/` 與 `dv/` 的報告（含 JUnit）。
2. PicoRV32 SoC（含預建 SRAM macro）GDS：abstract DRC = 0、full-GDS DRC 只在 SRAM 內且 ≤ baseline、LVS PASS（SRAM black box 註明）、
   **9 個 corner** setup/hold = 0 @ 40 ns、EQY PASS、GL sim（RTL vs GL trace 一致）PASS。
3. §7.3 每條 bug injection 都在**預期的** checker FAIL。
4. Hazard3 以同一套 flow 設定完成 signoff（Phase 5）。
5. OpenRAM 自產 macro（含多 corner .lib）取代預建 macro 後重新完成 signoff（Phase 6）。
6. `versions.mk` 與 README 足以讓第三人在另一台 Apple Silicon Mac 重現。

## 11. 假設與待確認事項
- （待確認）OpenRAM 在 Colab 安裝 Nix 的可行性（需 root 與 `/nix`）；備案 apt 安裝 ngspice／magic／netgen／klayout 或 Lima。
- （待確認）LibreLane 3.0.14 中 `SETUP_VIOLATION_CORNERS` 等變數的確切名稱與 `STA_EXTRA_CORNER_TCL_FILE` 的行為（文件標 Experimental）。
- （待確認）PicoRV32 IMC+IRQ 在 sky130hd 的實際 cell 數與面積（Phase 2 實測後定 `DIE_AREA`）。
- （待確認，僅在 Phase 7 考慮 TinyTapeout 時需要）§5.5 列出的四項條件：precheck 對 SRAM DRC 的處理、大格子費用、配電方式、I/O 腳數。
- （工程假設）padded.lib 的數值（clk→dout ≥ 5 ns、setup ≥ 1 ns、min_period ≥ 30 ns）；Phase 3.5/6 校正。
- （已確認）ciel 的 sky130A 含 `libs.ref/sky130_sram_macros`；open_pdks 來源為 fossi fork。
- （已確認）LibreLane 變數：`MAGIC_DRC_USE_GDS`（預設 True）、`ERROR_ON_MAGIC_DRC`、`ERROR_ON_KLAYOUT_DRC`、`PDN_MACRO_CONNECTIONS`、`PDN_CONNECT_MACROS_TO_GRID`（預設 True）、`MACRO_PLACEMENT_CFG`；`TIMING_VIOLATION_CORNERS = ["*tt*"]`。
- （已確認）2 KB macro：LEF 683.1 × 416.54 µm；power 在 met3／met4；LEF `ANTENNA` 0 筆、`FOREIGN` 1 筆（fossi fork）；.lib 解析模型；自身 DRC 32、LVS match；行為模型 `VERBOSE=1`、`#(T_HOLD) dout = 'bx`、無 `timescale`。
- （已確認）riscv64-elf-gcc rv32 multilib 可用、無 newlib。

## 12. 參考資料
- SKY90-FD：[Google 2022-07 公告](https://opensource.googleblog.com/2022/07/SkyWater-and-Google-expand-open-source-program-to-new-90nm-technology.html)、[google/sky90fd-pdk](https://github.com/google/sky90fd-pdk)、[sky90fd_fd_sc](https://github.com/google/skywater-pdk-libs-sky90fd_fd_sc)
- LibreLane：[repo](https://github.com/librelane/librelane)、[macOS 安裝](https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html)、[Flows 參考](https://librelane.readthedocs.io/en/latest/reference/flows.html)、[Using Macros](https://librelane.readthedocs.io/en/latest/usage/using_macros.html)、[PDKs](https://librelane.readthedocs.io/en/latest/usage/about_pdks.html)、[變數參考](https://librelane.readthedocs.io/en/latest/reference/step_config_vars.html)、[pdk_compat.py](https://github.com/librelane/librelane/blob/main/librelane/config/pdk_compat.py)、[librelane-ci-designs/test_sram_macro](https://github.com/librelane/librelane-ci-designs/tree/main/test_sram_macro)
- SRAM：[fossi-foundation/sky130_sram_macros](https://github.com/fossi-foundation/sky130_sram_macros)、[VLSIDA/OpenRAM](https://github.com/VLSIDA/OpenRAM)、[OpenRAM in SkyWater 130nm（ISCAS'23）](https://escholarship.org/content/qt9dc0v8g3/qt9dc0v8g3.pdf)、[OpenLane 1 OpenRAM 教學](https://openlane.readthedocs.io/en/2023.09.07/tutorials/openram.html)、[open_pdks](https://github.com/fossi-foundation/open-pdks)
- Cores：[YosysHQ/picorv32](https://github.com/YosysHQ/picorv32)（[sections.lds](https://github.com/YosysHQ/picorv32/blob/main/firmware/sections.lds)）、[Wren6991/Hazard3](https://github.com/Wren6991/Hazard3)、[lowRISC/ibex](https://github.com/lowRISC/ibex)、[openhwgroup/cvw](https://github.com/openhwgroup/cvw)
- 其他：[ORFS](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts)、[IHP sg13g2 SRAM 整合 issue](https://github.com/2AMLogic/sg13cmos5l-protocol-emulator/issues/60)、[caravel_mgmt_soc_litex（CVC SRAM model）](https://github.com/efabless/caravel_mgmt_soc_litex)、[TinyTapeout sky130 shuttle](https://tinytapeout.com/news/sky130-confirmed/)、[TinyTapeout memory 規格](https://tinytapeout.com/specs/memory/)、[TinyTapeout sky130A 格子尺寸](https://github.com/TinyTapeout/tt-support-tools/blob/main/tech/sky130A/tile_sizes.yaml)
- Chip-level：[chipfoundry/caravel_user_project](https://github.com/chipfoundry/caravel_user_project)
