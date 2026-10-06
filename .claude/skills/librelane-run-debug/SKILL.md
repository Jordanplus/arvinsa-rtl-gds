---
name: librelane-run-debug
description: 跑 LibreLane（nix-shell 呼叫）、run 失敗找原因、從中間 step 接續、只重跑單一 step（驗證設定、做 negative test）、某一步跑很久不知道是不是卡住（CPU 使用率低、記憶體一直漲、swap 用滿、最後只報 failed with an unexpected error）、要在單一 step 的工具指令裡加除錯輸出（`librelane.steps eject`）、重跑時保留上一次的 run（`run.sh` 的 `keep_prev_run` 只留一層 `.prev`），或錯誤時有時無（例如 `GRT-0229`）時使用。涵蓋 step 目錄結構、log 與 metrics 讀法（flow 中途 `state_out.json` 的 metrics 可能是前面步驟留下的舊值；`RSZ-0032` 的 hold buffer 數不是總數）、常見錯誤訊息與陷阱、隨機錯誤要先證明是隨機的才能加重試；設定值該設多少看各主題 skill。Use when running, resuming, re-running a single step of, or debugging a LibreLane flow run, including hangs and intermittent errors.
---

# LibreLane 執行、接續、單步重跑與除錯

只講「怎麼跑、怎麼查」。設多少、判什麼，看各主題的 skill（`drv-timing-closure`、`drc-signoff`、`antenna-signoff`……）。本 repo 的實例：`pnr/picorv32_core/run.sh`、`pnr/soc_top/run.sh`、`pnr/soc_top/neg_pnr.py`。

## 規則（已驗證）

1. **執行**
   - `cd .tools/librelane && nix-shell --run "python3 -m librelane --run-tag <tag> --design-dir <repo root> --pdk sky130A --scl sky130_fd_sc_hd --condensed <config.json>"`；config 內路徑用 `dir::`（相對 `--design-dir`）、`pdk_dir::`。
   - 路徑一律用絕對路徑變數組好再傳；不要在 `cd` 之後用 `$PWD`（soc_explore1 第一次因此找不到 config）。
   - JSON 註解用 `"//KEY"`。
   - 純量設定可用命令列 `-c KEY=VALUE` 覆寫（soc_explore7）；list 參數經 nix-shell 引號處理會變形，要寫進 config（Phase 2 試跑 #2）。
2. **接續**：`--run-tag <同一個> --from <Step id>` 會沿用同一 run 目錄裡前一步的 state，step 編號接著往下長（soc_explore2 從 `Magic.StreamOut` 接續）。只有改動不影響前面 step 時才能用。失敗那一步的目錄會留著，接續的那一步用下一個編號（`41-openroad-repairdesignpostgrt` 失敗、接續後是 `42-openroad-repairdesignpostgrt`），所以之後每一步的編號都多 1；checker 不要寫死 step 編號。
3. **單步重跑**：`python3 -m librelane.steps run --id <Step> -c <step dir>/config.json -i <step dir>/state_in.json -o <out>`。改 config／state 的**複本**，原 run 不動。多步串接：每步把前一步的 `state_out.json` 當下一步的 `-i`。範本：`pnr/soc_top/neg_pnr.py` 的 `rerun()`、`rerun_chain()`。
   - 要改工具本身的指令（加除錯輸出、在指令前後插 Tcl）時，把這一步匯出成不經 LibreLane 的 script：在一個空目錄放 `config.json`、`state_in.json` 的複本，在 nix-shell 裡 `python3 -m librelane.steps eject -c config.json -i state_in.json -o run.sh`。得到設好環境變數的 `run.sh` 與 LibreLane Tcl 的複本 `scripts/`；改複本、在 nix-shell 裡執行 `run.sh`，輸入讀原 run（唯讀），輸出寫在這個目錄（Phase 5，`docs/notes/repair_design_loop.md`）。
   - 用 `script -q /dev/null ./run.sh` 執行，輸出才不會被緩衝；可能失控的實驗（修復停不下來）一定要另外監看記憶體，超過上限自動停（下方已知陷阱）。
4. **metrics**：`python3 -m librelane.state latest <run dir> --extract-metrics-to <json>`。DRV 計數是各 corner 的最大值；`power__total` 是最後寫入的 corner（max_ff），不是 nom_tt（Phase 2 exit review）。
   - state 的 metrics 會一路沿用：每一步只更新自己寫出的 key，沒寫的 key 保留前面步驟的值。所以 flow 中途某一步 `state_out.json` 裡的數字，不一定是那一步量的（Phase 5：第 38 步 `STAMidPNR` 只量 nom_tt，state 裡的 nom_ss_n40C −15.5 ns 是第 12 步 `STAPrePNR` 留下的，`multicorner-sta` 規則 7）。要知道某一步自己量到什麼，看該步目錄的 `or_metrics_out.json`；最終結果看 `final/metrics.json`。
5. **隨機失敗要先證明是隨機的**：
   - 某一步失敗、但同樣設定之前跑過沒事時，拿失敗那次的 `state_in.json` 單步重跑至少 3–4 次。
   - 有的過、有的不過，才算隨機；再比較通過的幾次輸出是否完全相同。
   - 確定後，才可以加**有上限**的重試，而且只針對那一個訊息，每次重試都要記錄（`pnr/librelane_flow.sh`：`RepairDesignPostGRT` 的 GRT-0229，同一份輸入 2/4 中止）。其他失敗一律不重試。重試的判斷本身也要測：`make test-flow-retry` 用模擬的 nix-shell 跑 7 種情境（只有 GRT-0229 才重試、最多 2 次、其他錯誤不重試）。
   - 反過來說，**只跑一次就把錯誤歸因到某個設定，是不可靠的**：GRT-0229 原本被歸因到 `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH`（soc_explore3 只跑了一次），後來發現不設也有一半機率出現。結論是「某設定造成某錯誤」之前，同一設定至少跑兩次，或單步重跑確認。
6. **重跑會覆蓋上一次的 run，失敗的證據要保留**：同一個 run tag 重跑時，舊做法 `rm -rf` 整個 run 目錄與 `_signoff` 輸出目錄。Phase 3.5 第 1 次 harden-soc（`RepairDesignPostGPL` 75 分鐘後異常結束）的 run 就在第 2 次開跑時被刪，只剩 ADR-0010 的摘要。
   - Phase 5 起 `pnr/*/run.sh` 用 `keep_prev_run`（`pnr/librelane_flow.sh`）把上一次的 run 搬成 `<dir>.prev`，更舊的 `.prev` 刪掉（只留一層：一次 soc_top run 約 4 GB）；`make test-flow-retry` 有這個情境。
   - 連跑兩次以上才會遇到的事（例如要比較三次 run），自己先把 `.prev` 改名保存；要引用的數字先寫進 ADR 或 phase_exit 文件。

## 已知陷阱

| 陷阱 | 對策 | 出處 |
|---|---|---|
| 同一個 step 跑第二次，目錄名稱多 `-1`、`-2` 字尾（`47-openroad-checkantennas-1`） | 找 step 目錄時比對可選的 `-N` 字尾，取編號最大的 | P06 第一版挑錯成 routing 前那次 |
| step 讀的是 ODB；LEF 內容（例如 antenna 資料）在 floorplan 時就存進 ODB | 事後換 LEF 不會生效；要驗證就直接 `openroad` 讀 LEF＋DEF | P06 |
| `STA_EXTRA_CORNER_TCL_FILE` 只在 STA step 生效（`librelane/scripts/openroad/sta/corner.tcl` 59–61 行） | resizer、CTS 看不到 derate；signoff 才看得到 | ADR-0007 |
| Magic `[E] Error while reading cell ... Unknown layer/datatype` | 讀 OpenRAM SRAM GDS 的專用 layer，不會讓 flow 失敗（CI 參考設計也有） | soc_explore2 |
| `Magic DRC errors found - deferred` | deferred = 延後到 flow 最後才報錯；看完整錯誤清單再判斷 | soc_explore2 |
| console 輸出、OpenROAD step log 都會緩衝 | 進度看 step 目錄編號、`ps` 的 CPU 時間；不要只看 console | soc_explore6 |
| LibreLane 的 console 輸出（rich 排版）會折行，一個錯誤訊息被拆成兩行：`[GRT-0229] Vertical edge usage exceeds the` ／ `maximum allowed. (79, 0) usage=65534` | 程式要比對訊息時，讀該 step 目錄自己的 log（一行完整），不要 grep console | `pnr/librelane_flow.sh` 第一版用 console 比對，永遠不會重試（模擬測試前讀碼發現） |
| `pkill -f <字串>` 會誤殺命令字串含相同字的其他程序 | 用完整、唯一的字串（例如 `run-tag soc_explore8`） | 本專案 Phase 3 eqyB 被誤殺 |
| `OpenROAD.RepairDesignPostGRT` 修復後的 global routing 隨機中止：`[ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200`；位置是 clk pin 所在的 GCell | 已驗證是隨機的（同一份輸入 2/4 中止，修復結果 4 次相同）；`pnr/librelane_flow.sh` 只對這個訊息從該步接續，最多 3 次 | `make phase3` 第一次（worktree）、單步重跑 r1–r4 |
| 實驗性選項 `RUN_POST_GRT_DESIGN_REPAIR` 搭配很大的 slew 餘裕（50%）或很短的長線限制（120 µm）時，單執行緒跑十幾分鐘以上不結束 | 先限時觀察：同一步正常約 1 分鐘；超過 10 分鐘就停掉換設定 | soc_explore6、8 |
| 同上，起因是 corner 變多：resizer 看 15 個 corner（加了溫度反轉）時 `RepairDesignPostGRT` 35 分鐘以上不結束 | 停掉後拿同一份 `state_in.json` 單步重跑、只改 `RSZ_CORNERS` 回 9 個 → 58 秒，確認原因後才改 config（`multicorner-sta` 規則 3） | Phase 4 第 1 次 harden-soc |
| 診斷「是不是卡住」：log 有緩衝，看不到進度 | `ps -o cputime` 看 CPU 時間是否持續增加；記憶體看 physical footprint（下一列）；macOS `sample <pid> 2` 看 call stack 卡在哪個函式 | Phase 4（看到每加一顆 buffer 就做一次增量 global routing） |
| 某一步跑很久、CPU 使用率只有三四成：可能不是在算，而是記憶體失控、大部分時間在等 swap。`ps` 的 RSS 只算還留在實體記憶體的部分，會嚴重低估（Phase 5：RSS 418 MB，physical footprint 92.9 GB） | 看 `vmmap --summary <pid>` 的 Physical footprint 或 `top -l 1 -pid <pid> -stats mem`，再看 `sysctl vm.swapusage`。footprint 遠超過實體記憶體、swap 接近用滿就立刻停掉（整台機器的其他工作也會被拖慢）。重現時用單步重跑加記憶體上限與時間上限。Phase 5 的原因是 resizer 的無窮迴圈（`drv-timing-closure` 規則 10），其他幾次「修復不結束」推測同類（經驗紀錄） | Phase 5 第 1 次 harden-soc，`docs/notes/repair_design_loop.md` |
| `[INFO RSZ-0032] Inserted N hold buffers.` 的 N 不是這一步插的總數：hold 修復進度表的 Buffers 欄中途會從 2624 掉回 2，最後只剩幾顆 | 數輸出網表裡 `hold<N>` 開頭的 instance，和上一步的網表比較 | Phase 5 第 2 次 harden：log 寫 11，`ResizerTimingPostCTS` 前後網表 0 → 2700 |
| 停掉一個 run 時誤殺別的程序 | 用 `ps -eo pid,pgid,command` 找這個 run 的 process group，`kill -TERM -<pgid>` 只停那一組 | Phase 4（同時有 agent 在跑 openroad） |

## 時間預估（Apple Silicon，10 核）

soc_top 全 flow 約 20–30 分鐘（正式 run 實測 18 與 28 分；Magic 完整 GDS DRC 約 3–4.5 分）；PicoRV32 單獨約 15 分；單一 STA step 約 1–2 分；SpiceExtraction＋LVS 約 1 分。

## 用完後

1. 把這次新遇到的現象加進下方「經驗紀錄」（原文訊息、根因標明已驗證／推測、證據路徑）。
2. 同一現象出現兩次以上，或根因已用實驗確認，才搬進「規則」或「已知陷阱」。
3. 確認上面引用的檔案、行號、LibreLane 版本（`env/versions.mk`）還成立；LibreLane 升版時逐條檢查。
4. 這次如果「該用卻沒想到用」這個 skill，修改 description。

## 經驗紀錄

| 日期 | 專案／run | 現象（原文訊息） | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | arvinsa-rtl-gds soc_explore1 | `Path '.../.tools/librelane/pnr/soc_top/config.json' does not exist` | 已驗證：`cd` 進 LibreLane 目錄後 `$PWD` 變了 | 用絕對路徑變數 | 本 skill 規則 1 |
| 2026-10-03 | soc_explore6、8 | `OpenROAD.RepairDesignPostGRT` 單執行緒 13–26 分鐘不結束 | 推測：修復量變大時 resizer 走到很慢的路徑 | 停掉；GRT 餘裕改 40%、不縮長線限制 | `pnr/soc_top/README.md` 試跑紀錄 |
| 2026-10-03 | `make phase3` 第一次（乾淨 worktree，commit 654c303） | `OpenROAD.RepairDesignPostGRT failed ... [GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200` | 已驗證：隨機（第 39 步以前的 DEF 與 golden run 逐 byte 相同；同一份 `state_in.json` 單步重跑 4 次 2 次中止）。推測：global router 在 clk pin 的 GCell（pin 在 die 下緣，clk net 用 CTS NDR）用量計算有 bug | 有上限的重試（`pnr/librelane_flow.sh`）；更正 explore3 的錯誤歸因 | `runs/p3_phase3_clean.log`、`docs/notes/grt0229_repro.md` |
| 2026-10-05 | Phase 3.5 harden-soc 第 1 次 | `RepairDesignPostGPL` 的 step log 74 分鐘沒有更新，看起來像卡住；結束時才一次寫出進度表（其實停在第 9000 個 driver） | 已驗證：OpenROAD 經 LibreLane 執行時輸出有緩衝；macOS `sample <pid>` 看到一直在 `repairNetWire`／`insertBufferBeforeLoads` | 判斷是否卡住：`ps` 看 CPU 時間有沒有增加、`sample` 看 call stack，再用單步重跑（規則 3）比較不同輸入；原因見 `openram-macro-characterization` 規則 14 | ADR-0010 |
| 2026-10-05 | Phase 3.5 harden-soc 第 2 次 | 要回頭查第 1 次（`RepairDesignPostGPL` 異常結束）的 log，`runs/soc_top` 已是第 2 次的內容 | 已驗證：`pnr/soc_top/run.sh` 開跑前 `rm -rf "$RUN_DIR" "$OUT"` | 規則 6；需要的數字已寫進 ADR-0010；`run.sh` 改成搬走留到 Phase 5 | `pnr/soc_top/run.sh` 第 47 行 |
| 2026-10-05 | Phase 5 開頭 | `run.sh` 改成 `keep_prev_run`：上一次的 run 變成 `runs/<tag>.prev` | 已驗證（`make test-flow-retry` 8/8，含這個情境） | 規則 6 | `pnr/librelane_flow.sh` |
| 2026-10-05／06 | Phase 5 第 1 次 harden-soc（Hazard3，`../arvinsa-rtl-gds-p5h3`） | `OpenROAD.RepairDesignPostGPL failed with an unexpected error`：跑約 108 分鐘（process_stats 1:47:50）、physical footprint 92.9 GB、swap 28.0／28.7 GB，手動停止；`ps` 的 RSS 只有 418 MB（後三個數字是前一個 session 的 `vmmap`／`sysctl`／`ps` 輸出，run 目錄沒存） | 已驗證：resizer 在一條 net 上無限插 buffer（`drv-timing-closure` 規則 10）；`eject` 後加 `set_debug_level RSZ repair_net 1` 與 4 GB 上限，66 秒就重現並找到那條 net | 規則 3（`eject`）；已知陷阱（記憶體失控、RSS 低估）。推測：soc_explore6、8 與 Phase 4 第 1 次 harden 的「不結束」也是同一類，當時沒看記憶體 | `docs/notes/repair_design_loop.md` |
| 2026-10-06 | Phase 5 第 2 次 harden-soc（Hazard3，`2251c4a`） | 分析 ss_n40C setup 違規時，第 38 步 `state_out.json` 顯示 nom_ss_n40C −15.5 ns、nom_ss_100C −1.89 ns，和前一步 resizer 的 `RSZ-0098 No setup violations found` 矛盾 | 已驗證：`STAMidPNR` 只量 `DEFAULT_CORNER`（該步 log 只讀 nom_tt 的 .lib，`or_metrics_out.json` 只有 nom_tt），state 裡 ss 的值是第 12 步 `STAPrePNR` 寫的、沿用到第 55 步 | 規則 4；量繞線前的其他 corner 用 `multicorner-sta` 規則 8（`eject` 後換成自己的 Tcl） | `runs/soc_top_hazard3/38-openroad-stamidpnr-2/`（`../arvinsa-rtl-gds-p5h3`） |
