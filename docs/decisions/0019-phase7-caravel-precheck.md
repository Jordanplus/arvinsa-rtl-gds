# ADR-0019：Phase 7 把 Hazard3 SoC 扁平放進 Caravel `user_project_wrapper`，目標是 ChipFoundry precheck PASS（不下線）

- 狀態：已採用（2026-10-12）。決定 1–3 由使用者在同一輪選擇（全部採建議），決定 4–5 在查證後的第二、三輪。
- 範圍：`project-plan.md` §5.5、§8 Phase 7。exit 條件原文：「ChipFoundry 收件前的自動檢查（precheck）PASS」；決定 4 調整了其中兩項的判定方式。
- skill：`tapeout-precheck-caravel`（CLAUDE.md 規則 7，Phase 7 開始時建立）。
- 查證：`docs/notes/caravel_precheck_phase7.md`（cf-precheck `6c401ed5`、cf-cli `88025a8f`、caravel_user_project `b510613c`、caravel_user_sram `adf59a8f`）。

## 決定

1. **只做到 precheck PASS，不下線**（使用者 2026-10-12：「做到 precheck PASS，不下線 (建議)」）。
   - 理由：與 `project-plan.md` §8 的 exit criterion 相同；是否下線、梯次、費用都還沒定（§9 R12）。ChipFoundry 的 shuttle 照常開，但價格與截止日沒有公開。
   - 不做的事：送件、`cf push`、用平面萃取網表重新特性化 SRAM（Phase 6 已知限制 1 寫明是「下線前」要做）。
2. **CPU 用 Hazard3**（使用者 2026-10-12：「Hazard3 (建議)」）。
   - 理由：Phase 5 起的主要設計，`make regress` 的預設。`project-plan.md` §8 Phase 7 寫的 PicoRV32 是 Phase 5 之前寫的，同步更新。
   - 放法照 §5.5 的扁平放法：CPU 與周邊的 standard cell 直接在 wrapper 層擺放與繞線，SRAM macro 直接放在 wrapper 層。官方範例都是「先 harden 成 macro 再放進 wrapper」，扁平放法沒有現成範例。
3. **precheck 環境先查再決定**（使用者 2026-10-12：「先查清楚再決定 (建議)」）。查證結果見筆記第 1、6 節：`cf precheck` 一定用 Docker 跑 `chipfoundry/mpw_precheck:latest`，image 只有 linux/amd64；本機是 arm64、沒有 Docker；repo 的 nix 工具缺 CVC、GNU awk／sed、`pyverilog`，完整 precheck 不能原生跑。
4. **正式判定在本機用 colima＋Rosetta 跑官方 image**（使用者 2026-10-12：「本機 colima＋Rosetta (建議)」）。
   - 安裝限時 1 小時；跑不動就改 GitHub Actions（repo 是 public，免費、原生 x86；要把 wrapper GDS 上傳成附件）。
   - colima 0.10.3 與 docker CLI 29.9.0 已用 Homebrew 安裝（2026-10-12）。**實際改用 lima 直接建 VM**（同樣是 vz＋Rosetta；colima 就是包在 lima 外面）：colima 要從 GitHub release 下載 332 MB 的 VM image，本機到 GitHub release 只有約 80 KB/s，lima 的 ubuntu image 本機已有快取（筆記第 8 節）。官方範例跑一次 19 分鐘，除了範例本來就沒填的 GPIO 設定，其他 11 項 PASS（筆記 8a）。
   - 容器每次會 `pip install --upgrade cf-precheck`，每次執行都要記下實際的 cf-precheck 版本與 image digest。
5. **`klayout_feol`／`klayout_beol` 的判定：其他 11 項全 PASS，這兩項只允許 OpenRAM bitcell 造成的兩條規則，而且要和 PDK 預建 macro 一致**（使用者 2026-10-12：「其他全 PASS＋這兩條比對預建 (建議)」）。
   - 原因（已驗證，筆記第 7 節）：precheck 的 deck（release `2026.03.30_01.00`）在 cf-precheck commit `08f559e30a`（2026-05-07）拿掉了 SRAM 核心區（`areaid.ce`）對「mcon 要被 li 蓋住」的豁免（`MR_mcon.CON.10`），並新增 `MR_licon.SP.6`。PDK 預建的 `sky130_sram_2kbyte_1rw1r_32x512_8` 與自產 macro 一樣，FEOL 3 個、BEOL 264 個（依 cell 計），全部在 OpenRAM bitcell 與 replica column 裡；沒有參數能關掉。
   - 判定方式：兩項的違規只能是 `MR_licon.SP.6` 與 `MR_mcon.CON.10`，每一個都落在 SRAM 外框內，而且在 PDK 預建 macro 單獨檢查時的同一個 cell、同一個相對位置也有。做法比照 `check_soc.py magic_drc` 的「框內比對」。checker 與 negative test 在實作時一起加。
   - 列為 Phase 7 的已知限制：用這兩條規則的官方結果仍是 FAIL。
6. **向 ChipFoundry 反映由使用者決定是否送出**（使用者 2026-10-12：「我擬稿，你自己決定發不發 (建議)」）。草稿在 `runs/p7_chipfoundry_issue_draft.md`（不進版控）。
7. **LVS 把 SRAM 當 black box**（業界做法，與現行 SoC LVS 相同，沒有另外問）：`lvs_config.json` 的 `EXTRACT_ABSTRACT` 加入 SRAM。ChipFoundry 的 PDK `3e0e31dc` 對 bitcell 的元件命名和 `8afc834` 相同（筆記第 4 節），transistor-level 比對會遇到 Phase 6 的同一個不一致；ChipFoundry 自己的 `caravel_user_sram` 範例也用 black box。SRAM 內部的一致性仍由 repo 的 view QA 與 `check_macro_gds.py` 負責。

8. **SoC 的 clock 與 reset 接 `wb_clk_i`／`wb_rst_i`**（使用者 2026-10-12：「wb_clk_i／wb_rst_i (建議)」）。和 host write port 同一個 clock，不跨 clock domain；週期維持 44 ns。`resetn = ~wb_rst_i`（`wb_rst_i` 由管理用 SoC 在 `wb_clk_i` 下產生）。
9. **host write port 由 Wishbone slave 驅動**（使用者 2026-10-12：「Wishbone slave (建議)」）。`soc_top` 不改，wrapper 加一個轉接：
   - 位址 `0x3000_0000` 的控制暫存器，bit 0 = `host_en`，**reset 值為 1**：`wb_rst_i` 之後 CPU 停住，等管理用 CPU 寫 0 才依 `boot_mode` 從 boot ROM 開機。理由：reset 值為 0 時，CPU 會在管理用 CPU 寫入之前先跑幾個 cycle（例如先寫 GPIO），和 repo 驗證時「載入期間 CPU 一直停住」的條件不同；代價是晶片上一定要管理用韌體放開 CPU。這是實作細節，不是使用者選的，使用者可以改回 0；
   - `0x3000_1000`–`0x3000_17FF` 對應 SRAM 的 512 個 word，只有 `host_en=1` 時讀寫 SRAM，否則寫入忽略、讀回 0；
   - 讀取在 `host_cs` 後兩個上升緣取 `host_rdata`（`rtl/bus/soc_bus.v`「A read sampled at T0 ... captured into rdata_q at T1」）才回 `wbs_ack_o`；寫入一個 cycle 回 ack。`wbs_sel_i` 接 `host_wmask`。
10. **對外訊號：`uart_tx`、`uart_rx`、`trap`、`boot_mode` 放左緣最下面的 GPIO 33–37；`gpio_out` 只走 logic analyzer；全部 SoC 腳位都鏡像到 logic analyzer**（使用者 2026-10-12：「5 支放 GPIO 33–37，gpio_out 只走 LA (建議)」）。
    - 經過：第一次決定（使用者 2026-10-12：「接實體 GPIO＋一份接 LA (建議)」）時，我提出 GPIO 8–20，沒有先看腳位在範本上的位置；到 floorplan（決定 12）才發現 8–20 在右緣與上緣，離 block 2–3 mm。使用者指出流程順序錯了：「我以為block擺放位置應該在後段開始前就應該先確認之後出pin決定好」、「我在意的是流程問題」。Caravel 的 pad 與 wrapper 腳位位置是固定的（XOR 檢查），能選的只有用哪幾支 GPIO，所以先定 block 位置（決定 12），再依位置重選 GPIO。
    - 範本上的位置（`pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def`）：GPIO 0–14 右緣、15–23 上緣、24–37 左緣由上往下；37 在 y = 162 µm，往上每支約 200–260 µm。離左下角 block 最近的是 33–37（y 162–1075 µm）。
    - 腳位規劃依 `run_oeb_check` 的接線要求（cf-precheck `6c401ed5`，第 843–900 行）：

    | GPIO | y（µm） | 訊號 | 模式 | `io_out`／`io_oeb` |
    |---|---|---|---|---|
    | 37 | 162 | `uart_tx` | user output | `uart_tx`／0 |
    | 36 | 358 | `uart_rx` | user input nopull | 0／1（這個模式也要求兩者有接） |
    | 35 | 553 | `trap` | user output | `trap`／0 |
    | 33–34 | 1075、814 | `boot_mode[0]`、`boot_mode[1]` | user input pulldown（沒接時為 0） | 0／0（這個模式規定兩者都要是 0） |
    | 5–32 | — | 不用 | management input nopull（和 caravel-lite `verilog/rtl/user_defines.v` 第 50–52 行的預設相同；GPIO 5、6 是管理用 UART 的 `ser_rx`／`ser_tx`，`caravel.v` 第 92–93 行，由管理用韌體在開機後改設定） | 0／1（management 模式忽略，只有 warning） |

    `la_data_out[12:0]` = `{boot_mode, trap, gpio_out, uart_rx, uart_tx}`，`la_data_out[13]` = `host_en`，其餘 0（LA 腳位在下緣，就在 Wishbone 旁）；`gpio_out` 從晶片外看不到，由管理用 CPU 讀 LA。`user_irq` 接 0，`analog_io` 不接。

11. **wrapper 的 PDN strap 沿用 `soc_top` 的設定**（met4 寬度後來由決定 18 改成 4.8 µm）（使用者 2026-10-12：「沿用 soc_top 的設定 (建議)」）：met4 1.6 µm、met5 4.8 µm（ADR-0017）、pitch 用 LibreLane 預設（約 153 µm）。core ring 照 Caravel 固定設定（寬 3.1 µm、offset 12.45 µm、spacing 1.7 µm，4 組電源 net），標準元件與 SRAM 接 `vccd1`／`vssd1`。供電從 core ring 進來，IR 的供電點模型改成 ring 上（取代 `soc_top` 一側供電的假設），步驟 5 實作。
12. **SRAM 與 CPU 邏輯放在左下角，靠近 Wishbone 腳位**（使用者 2026-10-12：「左下角，靠近 Wishbone (建議)」）：Wishbone 與 LA 腳位在下緣 x = 0–870 µm，Wishbone 有時序要求，而且是 32 位元的匯流排。SRAM 固定在左下角附近，placement 密度維持 55%，讓邏輯聚在 SRAM 與 Wishbone 周圍。GPIO 依這個位置重選（決定 10）。
13. **pad／block／pin 規劃一定在 RTL 與 harden 之前，用四層機制強制**（使用者 2026-10-12：「現在情況應該是出pin位置因為pad都是固定的受到限制，所以這個流程上的修正很重要，要想個辦法確保之後一定會先探討pad & pin location」；選項回答「四層都做 (建議)」、「新建 chip-floorplan-pin-planning」）：
    - 規則：`CLAUDE.md` 規則 14、新 skill `chip-floorplan-pin-planning`、流程文件 4.1。
    - 規劃文件：`pnr/<design>/pin_plan.toml`（pad 來源、block 位置、每支 pin 的訊號與模式、它管轄的檔案），使用者看過 floorplan 圖（`scripts/plot_floorplan.py`）後，在 `[approval]` 填日期、原話、記錄的 ADR，以及規劃內容的 sha256（核准後規劃再改，核准就失效）。
    - checker：`make pin-plan`（`scripts/check_pin_plan.py`），比對 RTL 的腳位常數、`user_defines.v`、LibreLane config 的 macro 位置與範本 DEF 是否照規劃；`make harden D=<design>` 先跑它，`make regress` 也跑；植入錯誤 `make neg-pin-plan`。
    - hook：`.claude/hooks/require_pin_plan.py`（PreToolUse），規劃沒核准時，擋下對它管轄的檔案（config 只擋擺放與腳位設定）的 Edit／Write；沒有規劃的新設計也不能改 config 的擺放設定。用 Bash 改檔看不到，靠 checker 在 harden 與 regress 擋。Codex 沒有 hook，靠 checker。
    - `soc_top`、`picorv32_core` 是規則之前的設計，列為 legacy，不需要規劃。
14. **wrapper 邊界的時序約束用官方 Caravel 的數值，不用 multicycle**（使用者 2026-10-12：先問「照官方的有multicycle是不是我們的頻率應該可以再上去」，看過分析後選「官方數值，不用 multicycle (建議)」）：
    - 數值來源：caravel_user_project（`b510613`）`openlane/user_project_wrapper/signoff.sdc`，get_cup_sdc.py 在 2023-06-20 從 Caravel 的 STA 抽出。採用其中的 clock source latency（max 5.57、min 4.65 ns）、clock 腳位 transition 0.61 ns、`wb_rst_i` input delay 半週期、Wishbone 與 LA 的 input／output delay 與 input transition、`io_in` 的 input transition、輸出負載 0.19 pF。實作在 `pnr/user_project_wrapper/caravel_io.sdc`，PnR 與 signoff 的 SDC 都 source 它。
    - 不採用：`wbs_ack_o`／`wbs_cyc_i`／`wbs_stb_i` 的 2-cycle multicycle（host bridge 在第一個 cycle 取樣，所有路徑都要單一 cycle 收斂）；官方的 uncertainty、derate（用 `clock_uncertainty.sdc` 與 `base.sdc`）；`IO_SYNC = 0` 讓 GPIO 不受約束的做法（`io_in`／`io_out`／`io_oeb` 維持 `base.sdc` 的 20% delay，不留下未受約束的路徑）。
    - multicycle 不會提高頻率：限制頻率的是 SoC 內部 SRAM 下降緣讀出到上升緣接收的半週期路徑（`arvinsa-rtl-gds-p6final_h3` 的 signoff，44 ns，`min_ss_n40C_1v60` slack 0.66 ns，四個慢 corner 最差都是這條），multicycle 只放寬三支 Wishbone 腳位的邊界路徑。
    - 實作上的發現：OpenSTA 對設了 driving cell 的腳位會忽略 `set_input_transition`，不管順序（`base.sdc` 對所有輸入設 `inv_2`）。`caravel_base.sdc` 在 source `base.sdc` 時暫時停用 `set_driving_cell`，只有 `wb_rst_i`（官方沒有數值）保留 `inv_2`。驗證：`p7_floorplan4` 網表上，每類輸入腳位的 slew 都等於官方數值（例如 `wbs_dat_i` 0.84／0.07 ns、`wb_clk_i` 0.61 ns），PnR 與 signoff 兩份 SDC 的報表相同；`check_setup` 只報 29 個 `analog_io`（不接，決定 10）。查證過程在 skill `timing-constraints-sdc` 的經驗紀錄。
15. **clock 的 jitter 與 duty cycle 維持 `clock_uncertainty.sdc` 的假設（jitter 0.15 ns、duty 45/55%），記成下線風險**（使用者 2026-10-12：「維持假設，記成下線風險 (建議)」）：
    - 依據：`wb_clk_i` 是管理用 CPU 的核心時脈。Caravel `verilog/rtl/caravel_clocking.v`（chipfoundry／efabless `main`，兩者相同）第 93–94 行：開機時用外部時脈 `ext_clk`（duty 由板子上的振盪器決定），firmware 啟用 PLL 後用 `clock_div` 除頻（`clock_div.v` 第 83、106 行，設計成 50% duty；除數 0 時直通 PLL）。45/55% 涵蓋常見振盪器規格；PLL 的 jitter 沒有找到數字。
    - 下線風險與使用限制：PLL jitter 未知；44 ns 的週期代表管理端的核心時脈不能超過 22.7 MHz（Caravel 文件寫核心時脈上限「TBD，約 50 MHz」），測試 firmware 與板子要照這個設定，寫進 Phase 7 exit review 的已知限制。有 Caravel 的量測資料時再更新假設。
    - `user_project_wrapper` 的規劃（`pnr/user_project_wrapper/pin_plan.toml`：SRAM 在 (350.98, 413.44) µm，GPIO 37／36／35／34／33 = `uart_tx`／`uart_rx`／`trap`／`boot_mode[1]`／`boot_mode[0]`，`gpio_out` 只走 LA）經使用者核准：使用者 2026-10-12 看過規劃表與 floorplan 圖 `runs/layout_png/p7_floorplan4_modules.png`（run `p7_floorplan4`，跑到 global placement）後回覆「可以」。
16. **slew 上限：wrapper 內部照舊，Caravel 直接驅動的邊界 net 另判**（使用者 2026-10-12：「內部照舊，邊界另判 (建議)」）：
    - 起因：Caravel 的官方 SDC（決定 14）給 `la_oenb`、`wbs_adr_i`、`la_data_in`、`wbs_dat_i` 的 input transition 是 0.97／0.92／0.86／0.84 ns，超過本 repo 的上限（PnR 0.70、signoff 0.75 ns，ADR-0009）。探索 run `p7_harden2` 第 38 步（tt）有 384 個 max slew 違規，全部在這四組腳位與直接接在上面的第一顆 cell（64 個，多是 hold delay cell）；第一顆 cell 的 slew 0.840–0.920 ns，幾乎等於腳位的值。wrapper 內部沒有其他違規。slew 由 Caravel 那一端決定，wrapper 內部修不掉；官方範例的上限是 1.5 ns（`MAX_TRANSITION_CONSTRAINT`），所以不算違規。STA 本來就用這些真實的 transition 算 timing，這個決定只影響判定，不影響時序與版圖。
    - 判法：wrapper 內部的 net 維持 0.70／0.75 ns。違規的 pin 若是有外部 transition 的輸入腳位本身，或接在這種腳位 net 上的 cell 輸入，允許到「該腳位的 transition + 0.05 ns」；0.05 ns 是其他 net 從 PnR 目標到 signoff 上限的餘量（0.70 → 0.75 ns）。其他任何違規都 FAIL。
    - 實作：`check_soc.py max_slew`（每個 STA corner 讀 `checks.rpt` 的違規清單，數量要和報表的計數相同；soc_top 沒有邊界例外，違規數必須是 0）；wrapper config 的 `MAX_SLEW_VIOLATION_CORNERS` 改回 LibreLane 預設（不讓 flow 因 slew 失敗），改由這一列判定。negative test：`neg_pnr.py` P80（soc_top 植入一個內部違規）；邊界 pin 超過 transition + 0.05 ns、內部違規、計數對不上三種情況已在 `p7_harden2` 的報表上手動確認會 FAIL，`neg_pnr` 支援 wrapper 時（步驟 8）加成正式案例。
    - 被否決的選項：整體改成官方的 1.5 ns（內部 net 的 signoff 也只檢查到 1.5 ns，與 ADR-0009 不一致）；整體放寬到 1.0 ns（除了容得下 Caravel 以外沒有依據）。
17. **wrapper 的 global routing 後修 hold 餘量 0.05 → 0.2 ns；resizer 的 corner 維持 ADR-0013 的 12 個**（使用者 2026-10-12 先選「加 ff_100C＋餘量 0.2 (建議)」；實測跑不完後改選「回 12 corner＋餘量 0.2 (建議)」）：
    - 起因：探索 run `p7_harden2`（RSZ-0074 修好後從第 41 步接續）signoff 只剩一條 hold 違規，Caravel 送進來的 `wbs_adr_i[4]` → `_21509_`：`max_ff_100C` −0.071、`max_ff_n40C` −0.043、`nom_ff_100C` −0.024、`min_ff_100C` −0.001 ns（`runs/p7_harden2_out/attempt2_margin005/`）。這是 wrapper 才有的路徑：依決定 14 的官方約束，資料由 Caravel 的時脈（min latency 4.65 ns）加 0.79 ns 送出，wrapper 的暫存器在 5.57 ns 加內部 clock tree 約 2 ns 才取樣，ff 下資料要延遲約 2.4 ns 才夠 hold，路徑上已經有 5 顆 `dlygate4sd3_1`。
    - 原因兩個：global routing 後的 hold 修復（`GRT_RESIZER_HOLD_SLACK_MARGIN` 預設 0.05 ns）修完估計 +0.058 ns，同一條路徑繞線、RCX 後在 resizer 看得到的 `max_ff_n40C` 是 −0.043 ns，估計樂觀約 0.1 ns；resizer 的 corner 不含 ff_100C，這條路徑在 ff_100C 比 ff_n40C 再差 0.028 ns。
    - 先試的做法（退回）：`RSZ_CORNERS` 加 3 個 ff_100C。LibreLane 所有 resizer 步驟共用這份清單（`librelane/steps/openroad.py` 第 2397 行），修 slew／cap 的 `RepairDesignPostGRT` 不再把 17 顆 `a221oi_1` 放大成 `a221oi_4`，改在後面插長串 buffer（最長 254 顆），buffer 866 → 4759 顆，global routing 壅塞失敗（`GRT-0116`，總溢位 771；run `p7_harden3`）。同一份輸入單步重跑（只跑到 `repair_design`）兩邊數字完全相同；resizer 的目標 slew corner 兩邊都是 `max_ss_n40C_1v60`，ff_100C 的 .lib 也有完整 428 個 cell。為什麼不放大，查到時限為止沒有找到（`tapeout-precheck-caravel`、`drv-timing-closure` 經驗紀錄）。
    - 做法：`GRT_RESIZER_HOLD_SLACK_MARGIN` 0.2 ns（量到的約 0.1 ns 落差，加上 ff_100C 的 0.028 ns，再留餘裕）。只改 wrapper 的 config。ff_100C 由 signoff STA（15 個 corner）判，這次的違規就是它抓到的。
    - 代價與風險：resizer 沒有直接看 ff_100C（`drv-timing-closure` 規則 11 的教訓），只靠餘量；輸入腳位路徑多插延遲 cell，ss 的 setup 可能略降（`p7_harden2` 最差 setup +0.648 ns）。驗證：`p7_harden4`（從 `p7_harden2` 第 40 步的狀態重跑，137 分鐘，flow 沒有延後錯誤）：post-GRT hold 修復修完 +0.204 ns，signoff 15 個 corner 的 hold 都沒有違規，最差 +0.148 ns（`max_ff_100C`，`wbs_adr_i[8]`）；setup 最差 +0.648 → +0.592 ns；LVS、antenna PASS，KLayout DRC 0，Magic DRC 數目與 `p7_harden2` 相同（後者已確認全部在 SRAM 內）。之後正式 harden。
    - 被否決的選項：寫 plugin 只讓修 timing 的步驟看 15 個 corner（約半天，`repair_timing` 也會放大 cell，同樣的異常可能出現）；先查根因（可能查不到，時程不確定）。

18. **IR：照 Caravel 實際的供電網路量；block 不移，met4 strap 1.6 → 4.8 µm，含 Caravel 網路的壓降寫成對板子的供電要求**（使用者 2026-10-13：先選「移動 block」，看過各位置的實測後改選「不移 block＋met4 4.8＋供電要求 (建議)」）：
    - 查證（agent 讀原始碼，我抽查原文）：ChipFoundry 現用的 Caravel（`chipfoundry/caravel_user_project` `b510613c` 的 `MPW_TAG ?= CC2509` → `chipfoundry/caravel` `a0b50ad1`；所引檔案與 `efabless/caravel` `27cbe49c` 相同）。wrapper 的 vccd1／vssd1 ring 只從左右兩側接到 Caravel：`lef/manual_power_connections.lef` 的 met3 跨接線左 54、右 53 條（間距約 65 µm），上下兩邊沒有接點；`caravel_core` 的 PDN 刻意不跨過 wrapper（`openlane/caravel_core/interactive.tcl` 第 26–33 行）。vccd1、vssd1 各只有一顆 pad，都在晶片右側：`def/chip_io.def` 第 17057–17058 行 `user1_vccd_lvclamp_pad` (3390.035, 4538)、第 16653–16654 行 `user1_vssd_lvclamp_pad` (3390.035, 2299)，換到 wrapper 座標約 y = 3290、1051。電流經 Caravel 自己 5 µm 寬的 met4 ring 與跨接線才到 wrapper。官方沒有 user area 的 IR 預算或說明（efabless/caravel issue #416 討論過舊版只從四角接）。
    - 量法：把 `caravel_core.def` 中 vccd1／vssd1 在 wrapper 外的 met4／met5 形狀與 via、跨接線、pad 的 met5 strap 平移到 wrapper 座標，加進 IR 用的 DEF 複本，供電點放在兩顆 pad 的 strap 上；PDN 的 what-if 用 `pdn-ir-drop` 規則 13 的方法（現行設定重產的 SPECIALNETS 與原版圖逐行相同，IR 與手建的模型相同）。對照組：同一份 ODB、供電點放回 wrapper ring，結果與原本相同（5.17 mV；完整位數差 0.01–0.02%，是 DEF 轉 ODB 的來回造成的）。
    - 結果（`p7_harden2` 版圖，最壞組合 = ff 電流＋SRAM port 1 浮接電流＋ss 金屬電阻，上限 20 mV）：
      | 情況 | 最壞組合 |
      |---|---|
      | 供電點在 wrapper ring（整圈／左右兩側／只有上側） | 6.87／8.37／143 mV |
      | 含 Caravel 網路，block 在左下（現行），met4 1.6／3.2／4.8／6.4 µm | 104.2／82.2／72.2／66.4 mV |
      | 含 Caravel 網路，block 平移到右側中段／右上／對齊 vssd1 pad／右下（met4 1.6） | 76.4／73.1／78.2／102.8 mV |
      | 右側中段＋met4 4.8 | 58.2 mV |
      壓降幾乎都在 pad 到 wrapper 邊緣（nom_tt：wrapper 右上角 5–9 mV、右下角約 30 mV，wrapper 內部只多 2–5 mV）。兩顆 pad 相距約 2.2 mm，block 放哪裡都至少離其中一顆很遠，所以 20 mV 在這個供電結構下做不到。
    - 做法：
      - `PDN_VWIDTH` 1.6 → 4.8 µm（只改 wrapper；與 met5 同寬）。
      - wrapper 內部：IR 步驟打開，供電點放在 wrapper ring 左右兩側與每條 met5 strap 的交點（Caravel 跨接線所在的兩側；直接用跨接線的位置時 OpenROAD PSM 讀完供電點檔就 Signal 11，原因沒查到），照舊判 20 mV（`ir_worst.py`，判法見決定 19；`check_soc.py ir_sources`）。
      - 含 Caravel 網路的壓降由新的 checker 判，判法見決定 19（慢 corner，上限 50 mV）；**決定 20 改成用 max power pattern 判 20 mV，下面的供電要求已取消**。原本這個上限就是**使用限制**：pad 端 vccd1 − vssd1 至少要 1.60 + 0.050 = 1.65 V（1.8 V 的 −8.3%），signoff 的 1.60 V 時序才成立。寫進 Phase 7 exit review 的已知限制。Caravel 穩壓器實際的精度沒有查證。（最初以最壞組合訂 75 mV、≥ 1.675 V，決定 19 改掉。）
    - 被否決的選項：移動 block（最多再改善約 14 mV，要重做 pin 規劃、RTL 與核准，Wishbone 與時脈要跨 2–3 mm）；不改 PDN、只寫供電要求（104 mV，要求 ≥ 1.71 V）；換算成時序餘量（SRAM 沒有低電壓的特性化資料，半天到一天）。
    - 流程上的教訓：電源進入點應該在 pad 階段就查（使用者 2026-10-12：「Caravel pad都是固定，應該早就要決定可以有哪些供電選擇」；2026-10-13：「這就是我說的一開始就應該考慮」），已寫進 `chip-floorplan-pin-planning` 規則 2。

19. **IR 用慢 corner 判：電流、電壓、金屬電阻都取同一個慢 corner；「ff 電流＋ss 電阻」的最壞組合照跑但只當參考**（使用者 2026-10-13 問「你的2,3我們為什麼抓這麼保守」，看過實測後選「用慢 corner 判 (建議)」；同日要求把「建立量測以決定 max power」的方法寫進 `signoff-criteria`）。取代 Phase 5 exit review 的判法（使用者 2026-10-08：每次 harden 判最壞組合），soc_top 也適用：
    - 依據：IR 預算 =「最低供電 − 慢 corner 的特性化電壓 1.60 V」（`pdn-ir-drop` 規則 4），保護的是慢 corner 的 setup。ff corner 的 setup 有約 8 ns 餘量，電壓低反而讓 hold 更寬鬆，不在這個預算內。最壞組合拿 ff 的電流（`p7_harden2`：ff 100°C 17.95 mW 加 SRAM port 1 浮接 5.34 mW）去比慢 corner 的預算，是兩個保守假設疊在一起；慢 corner 的電流是 ss 的 10.7–11.3 mW（浮接 0.03–0.15 mW），換成電流約是最壞組合的 0.6 倍。
    - 實測（`p7_harden2` 版圖，含 Caravel 網路，取 `max_ss_100C` 較差）：met4 1.6 µm 65.6 mV（最壞組合 104.2），met4 4.8 µm 45.2 mV（最壞組合 72.2）。
    - 做法：`pnr/soc_top/ir_worst.py` 判 `max_ss_n40C_1v60` 與 `max_ss_100C_1v60`（1.60 V，各自的 ss `LAYERS_RC`，加上該 PVT 的 SRAM 浮接電流），兩個取大的比 `[max_sum]`；`max_ff_n40C_1v95`／`max_ff_100C_1v95` 配 ss 電阻照跑，印成 `[INFO]`，不影響判定（EM 與紀錄用）。negative test P77（拿掉 `ss_100C` 的浮接電流）、P78（上限在兩個慢 corner 之間）改成慢 corner；P61 不變。上限：wrapper 內部與 soc_top 維持 20 mV；含 Caravel 網路 50 mV（決定 18 的供電要求）。
    - 被否決的選項：維持最壞組合（含 Caravel 網路 72 mV，供電要求 ≥ 1.675 V）；兩個都判（慢 corner 50 mV、最壞組合 75 mV）。
    - 量測方法（先重現 flow 的功耗、按類別拆解、.lib 沒有的電流按 PVT 加、切換率是假設、手算交叉檢查、供電點從真實 pad 起算）寫進 `signoff-criteria`「IR 用多大的電流」。

20. **IR 的電流用 CPU max power pattern 的實際切換活動，含 Caravel 網路在慢 corner 判 20 mV；決定 18 的供電要求取消**（使用者 2026-10-13：「一般IR都會用CPU max power pattern去做不是嗎」→ 先量一次；看過結果後「這才是正確的評估IR 的方式，請一樣更新到我們的對應skill與流程」；上限選「回到 20 mV，時脈改 44 ns 再錄 (建議)」）：
    - 依據：IR 的電流原本用 OpenSTA 的預設切換率（vectorless），沒有驗證過。業界做 static IR 用讓 CPU 滿負載的測試程式（max power pattern），從 gate-level 模擬取得實際的切換活動（VCD），再算功耗與 IR。
    - pattern：`fw/tests/maxpower`，三段滿負載迴圈各約 5000 個週期，用 GPIO 標記（0x5A：ALU＋每幾個週期一次 SRAM 讀寫、資料每次 32 位元全翻轉；0x5B：再加乘法器；0x5C：只有暫存器運算，每個週期取一道 32 位元指令）。這顆 SoC 從 SRAM 取指令，每道指令約 3 個週期，三段的功耗只差不到 3%，最耗電的空間本來就窄。
    - 實測（`p7_harden2` 網表、met4 4.8 µm 的 what-if 版圖、含 Caravel 網路、`max_ss_100C`；VCD 是 testbench 的 40 ns 時脈，比 44 ns 保守約 10%）：預設切換率 11.4 mW、45.2 mV（對照組，重現決定 19 的數字）；0x5A 5.11 mW、19.74 mV；0x5B 4.99 mW、19.39 mV；0x5C 5.13 mW、19.88 mV。VCD 標到全部 73058 個 pin。預設切換率高估約 2.2 倍。
    - 做法：
      - VCD 用與 signoff 約束相同的 44 ns 時脈錄（testbench 的 `TB_CLK_HALF_NS`），每一段只錄 `dut_gl`、只錄那一段。
      - harden 之後（VCD 要來自最終網表，接在 gl 模擬之後）：錄各段的 VCD，含 Caravel 網路的 IR 讀 VCD，在兩個慢 corner 判，取各段與各 corner 的最大值 ≤ 20 mV（`[max_sum] ir_caravel_vdd_drop_plus_gnd_rise`）。也檢查 VCD 全部標註、每段長度、整支 maxpower 的 gate-level 模擬與 RTL 逐週期一致；預設切換率的結果只列為參考。
      - harden 內的 `ir_worst.py`（供電點在 wrapper ring、預設切換率、慢 corner、20 mV）保留，當作早期檢查。
      - 對板子的供電要求回到原本的假設：pad 端最低 1.62 V（決定 18 的 ≥ 1.65 V 取消）。
    - 已知限制：pattern 沒有包含 Wishbone 主機端的存取；零延遲的 gate-level 模擬不含 glitch 造成的切換；「最耗電」是三種 pattern 取最大，不是證明。

## 後果

- Phase 7 的 exit 條件改寫為：「官方 image 的 precheck 13 項中，11 項 PASS；`klayout_feol`／`klayout_beol` 只有決定 5 的兩條規則，而且與 PDK 預建 macro 一致」。`project-plan.md` §8 同步更新。
- 本機與官方的工具版本不同（Magic 8.3.623 vs 8.3.471、KLayout 0.30.7 vs 0.29.12、Netgen 1.5.316 vs 1.5.272、PDK `8afc834` vs `3e0e31dc`）。repo 自己的 flow 照舊用釘版的工具；precheck 的判定只認官方 image 的結果。
- Magic DRC（precheck 的選用項目）不跑；下線時 ChipFoundry 會怎麼看自產 SRAM 內部的 Magic 違規，要另外問。
