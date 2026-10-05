---
name: librelane-run-debug
description: 跑 LibreLane（nix-shell 呼叫）、run 失敗找原因、從中間 step 接續、只重跑單一 step（驗證設定、做 negative test）、某一步跑很久不知道是不是卡住，或錯誤時有時無（例如 `GRT-0229`）時使用。涵蓋 step 目錄結構、log 與 metrics 讀法、常見錯誤訊息與陷阱、隨機錯誤要先證明是隨機的才能加重試；設定值該設多少看各主題 skill。Use when running, resuming, re-running a single step of, or debugging a LibreLane flow run, including hangs and intermittent errors.
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
4. **metrics**：`python3 -m librelane.state latest <run dir> --extract-metrics-to <json>`。DRV 計數是各 corner 的最大值；`power__total` 是最後寫入的 corner（max_ff），不是 nom_tt（Phase 2 exit review）。
5. **隨機失敗要先證明是隨機的**：
   - 某一步失敗、但同樣設定之前跑過沒事時，拿失敗那次的 `state_in.json` 單步重跑至少 3–4 次。
   - 有的過、有的不過，才算隨機；再比較通過的幾次輸出是否完全相同。
   - 確定後，才可以加**有上限**的重試，而且只針對那一個訊息，每次重試都要記錄（`pnr/librelane_flow.sh`：`RepairDesignPostGRT` 的 GRT-0229，同一份輸入 2/4 中止）。其他失敗一律不重試。重試的判斷本身也要測：`make test-flow-retry` 用模擬的 nix-shell 跑 7 種情境（只有 GRT-0229 才重試、最多 2 次、其他錯誤不重試）。
   - 反過來說，**只跑一次就把錯誤歸因到某個設定，是不可靠的**：GRT-0229 原本被歸因到 `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH`（soc_explore3 只跑了一次），後來發現不設也有一半機率出現。結論是「某設定造成某錯誤」之前，同一設定至少跑兩次，或單步重跑確認。

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
| 診斷「是不是卡住」：log 有緩衝，看不到進度 | `ps -o cputime,rss` 看 CPU 時間與記憶體是否持續增加；macOS `sample <pid> 2` 看 call stack 卡在哪個函式 | Phase 4（看到每加一顆 buffer 就做一次增量 global routing） |
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
