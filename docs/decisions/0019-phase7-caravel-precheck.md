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

11. **wrapper 的 PDN strap 沿用 `soc_top` 的設定**（使用者 2026-10-12：「沿用 soc_top 的設定 (建議)」）：met4 1.6 µm、met5 4.8 µm（ADR-0017）、pitch 用 LibreLane 預設（約 153 µm）。core ring 照 Caravel 固定設定（寬 3.1 µm、offset 12.45 µm、spacing 1.7 µm，4 組電源 net），標準元件與 SRAM 接 `vccd1`／`vssd1`。供電從 core ring 進來，IR 的供電點模型改成 ring 上（取代 `soc_top` 一側供電的假設），步驟 5 實作。
12. **SRAM 與 CPU 邏輯放在左下角，靠近 Wishbone 腳位**（使用者 2026-10-12：「左下角，靠近 Wishbone (建議)」）：Wishbone 與 LA 腳位在下緣 x = 0–870 µm，Wishbone 有時序要求，而且是 32 位元的匯流排。SRAM 固定在左下角附近，placement 密度維持 55%，讓邏輯聚在 SRAM 與 Wishbone 周圍。GPIO 依這個位置重選（決定 10）。

## 後果

- Phase 7 的 exit 條件改寫為：「官方 image 的 precheck 13 項中，11 項 PASS；`klayout_feol`／`klayout_beol` 只有決定 5 的兩條規則，而且與 PDK 預建 macro 一致」。`project-plan.md` §8 同步更新。
- 本機與官方的工具版本不同（Magic 8.3.623 vs 8.3.471、KLayout 0.30.7 vs 0.29.12、Netgen 1.5.316 vs 1.5.272、PDK `8afc834` vs `3e0e31dc`）。repo 自己的 flow 照舊用釘版的工具；precheck 的判定只認官方 image 的結果。
- Magic DRC（precheck 的選用項目）不跑；下線時 ChipFoundry 會怎麼看自產 SRAM 內部的 Magic 違規，要另外問。
