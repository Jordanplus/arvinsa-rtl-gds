---
name: chip-floorplan-pin-planning
description: 晶片層級（或外殼層級，例如 Caravel user_project_wrapper）的 pad、block 位置與 pin 指定的規劃，要在寫頂層 RTL 的腳位對應、GPIO 模式與 LibreLane config 之前做時使用；開新的頂層設計、決定用哪幾支 GPIO 或 pad、搬動 macro 或 block、改 `FP_DEF_TEMPLATE`／`MACROS` 的位置時都先讀。涵蓋順序（pad（含電源 pad 與電源進入點）→ block 位置 → pin 指定 → RTL → harden）、外殼固定時電源從哪幾邊進來要在 pad 階段查清楚並列出供電模型（IR 壓降隨 block 離電源進入點的距離變化，Caravel wrapper 左下角的 SoC 在整圈供電 6.87 mV、只從上側 143 mV）、規劃文件 `pnr/<design>/pin_plan.toml` 與使用者核准（日期、原話、ADR、plan_sha256）、只跑到套用 DEF 範本或 global placement 就出 floorplan 圖給使用者確認（`scripts/plot_floorplan.py`，模組框要 `SYNTH_HIERARCHY_MODE` deferred_flatten 的探索設定）、checker `make pin-plan` 與 hook `require_pin_plan.py` 擋下時怎麼辦（「這份 pad／block／pin 規劃還沒經使用者核准」、「plan_sha256 differs」、「no pnr/<design>/pin_plan.toml」），以及看圖時的陷阱（PDN 之後的 DEF 還沒有範本腳位、範本套用後腳位是 FIXED 不是 PLACED、跑到 `Odb.ApplyDEFTemplate` 時標準元件還沒有位置、整顆 die 鋪滿 tap cell、tie cell 分布在各腳位旁）。die 內的密度與壅塞看 floorplan-congestion；Caravel 的固定腳位與 GPIO 位置看 tapeout-precheck-caravel。Use for chip-level pad, block-placement and pin-assignment planning before top-level RTL and harden, its approval, checker and edit hook.
---

# 晶片層級的 pad、block 與 pin 規劃

die 內的 placement 密度、macro 周圍的 row、壅塞看 `floorplan-congestion`；Caravel 的固定腳位座標、保留的 GPIO、GPIO 模式看 `tapeout-precheck-caravel`；macro 本身的 view 看 `hard-macro-integration`。本 repo 實例：ADR-0019 決定 10、12、13，`pnr/user_project_wrapper/pin_plan.toml`。

名詞：
- **pad**：晶片對外的接點（含 IO cell）。外殼固定時（Caravel），pad 與外殼腳位的位置都已經給定。
- **電源進入點**：外部電源經過電源 pad、晶片頂層的電源走線，接到本設計電源網路的位置（Caravel：wrapper 外圍的 core ring 上，實際在哪幾邊、哪些點接入）。靜態 IR 的供電點模型（`VSRC_LOC_FILES`）就是在描述它。
- **block 位置**：macro（SRAM）與主要邏輯放在 die 的哪一區。
- **pin 指定**：哪個訊號走哪一支腳位或 GPIO，用什麼模式（輸入、輸出、上拉／下拉）。

## 規則（已驗證）

1. **順序：pad（含電源 pad 與電源進入點）→ block 位置 → pin 指定 → 頂層 RTL 的腳位對應 → harden**（使用者 2026-10-12：「block擺放位置應該在後段開始前就應該先確認之後出pin決定好」、「要想個辦法確保之後一定會先探討pad & pin location」；電源見規則 2）。
   - block 位置依有時序要求、位元數多的介面決定（Caravel 是 Wishbone，在下緣左段）。
   - pin 從離 block 最近的可用腳位挑；慢速訊號也不例外（「加 buffer 就好」是 Phase 7 犯過的錯，ADR-0019 決定 10）。
   - pad 不固定的設計（自己做 pad ring）：先依封裝與板子定 pad 順序，再走上面的順序。checker 目前只實作 pad 固定的情況（`pads.source = "fixed"`），pad 不固定的設計要先補 checker。
2. **電源進入點和訊號 pad 一樣，在 pad 階段就查清楚、列出可能的供電模型，再定 block 位置**（使用者 2026-10-12：「這也是跟之前floorplan一樣問題，Caravel pad都是固定，應該早就要決定可以有哪些供電選擇」）。
   - 為什麼：IR 壓降取決於 block 離電源進入點多遠。Phase 7 到 harden 跑完才量：SoC 在 wrapper 左下角，最壞組合（ff 電流加 ss 電阻）在「整圈供電」6.87 mV、只從左側 9.77、下側 20.65、右側 39.2、上側 143 mV（上限 20 mV）。block 位置早已依 Wishbone 定好、RTL 與 pin 也做完，這時才發現結果取決於 Caravel 實際從哪邊供電（`tapeout-precheck-caravel` 經驗紀錄）。
   - 怎麼做：
     1. pad 階段查清楚外殼或封裝的電源 pad 位置、晶片頂層怎麼把電源接到本設計（哪幾邊、哪些點），附出處；查不到的部分列成幾種可能的模型（例如整圈、只有某一側），並標出最悲觀的那一個。
     2. 定 block 位置時，把供電一起考慮：在每個可能的模型下，block 離電源進入點的距離；靠近電源進入點與靠近有時序要求的介面衝突時，列選項請使用者決定。
     3. 採用哪個供電模型（signoff 的 IR 用它）要在核准規劃時一起決定，寫進 `pin_plan.toml`（建議一節 `[power]`：電源 pad、進入點、採用的模型與依據）與 ADR。
   - 怎麼估：完成的版圖上，用單步 `OpenROAD.IRDropReport` 換 `VSRC_LOC_FILES` 加上 `pdn-ir-drop` 的最壞組合（`ir_worst.py`），每個模型約 2 分鐘（nom_tt）加 4.5 分鐘（最壞組合）。floorplan 階段（global placement 之後、還沒有 SPEF）能不能估得夠準，**還沒有驗證**；驗證之前，至少在第一次探索 harden 跑完時就量，不要等到正式 harden。
   - 沒有自動防護：`check_pin_plan.py` 還不檢查 `[power]`，目前只靠本規則與 `pdn-ir-drop` 的 IR 檢查（harden 後才會 FAIL）。
3. **規劃寫成 `pnr/<design>/pin_plan.toml`，使用者核准後才動 RTL 與 config**。
   - 內容：`[pads]`（來源、範本 DEF、保留腳位）、`[block]`（config、macro、instance、位置、pin 到 macro 外框的距離上限 `max_pin_distance_um`）、`[gpio]` 預設模式、每支 `[[pin]]`（訊號、GPIO、模式、RTL 裡對應的 localparam；超過距離上限要寫 `reason`）、`[rtl]`、`[governs]`（受管轄的檔案）、`[approval]`。
   - 核准：使用者看過規劃與 floorplan 圖之後，填 `date`、`quote`（使用者原話）、`adr`（原話要出現在該 ADR 裡）、`plan_sha256`（`scripts/check_pin_plan.py --digest pnr/<design>/pin_plan.toml`）。`[approval]` 以上的內容改了，sha256 就對不上，要重新請使用者核准。
   - `quote` 只能填使用者自己的話；不能由 Claude 代填「同意」。
4. **出圖確認的檢查點**：不跑完整 harden，只跑到需要看的那一步就出圖。
   - 看腳位與 PDN：`--to Odb.ApplyDEFTemplate`（Phase 7 約 1–2 分鐘）。
   - 看邏輯實際聚在哪：`--to OpenROAD.GlobalPlacement`（Phase 7 約 3 分鐘）。要畫模組框，用一份暫時的 config 複本把 `SYNTH_HIERARCHY_MODE` 設成 `deferred_flatten`，cell 名稱才會帶模組路徑；這份只用來看圖，不進版控、不用於 signoff。
   - 畫圖：`scripts/plot_floorplan.py <def> <png> --plan pnr/<design>/pin_plan.toml`，規劃的 pin 以紅色標出訊號名稱。
5. **四層強制**（ADR-0019 決定 13）：
   - 規則：`CLAUDE.md` 規則 14、本 skill、流程文件 4.1。
   - 規劃文件：規則 3。
   - checker：`make pin-plan`（全部設計，含「非 legacy 的設計都要有規劃」），`make harden D=<design>` 先跑 `--design <design>`，`make regress` 也跑；植入錯誤 `make neg-pin-plan`（25 個案例，含 hook）。
   - hook：`.claude/hooks/require_pin_plan.py`（PreToolUse：Edit、Write、MultiEdit）。規劃沒核准時，擋下 `[governs]` 裡的檔案；config 只在改到擺放或腳位設定（`MACROS`、`location`、`FP_DEF_TEMPLATE`、`DIE_AREA`、`IO_PIN_*`、`FP_PIN_*` 等）時擋。沒有規劃的新設計，改 config 的擺放設定也會被擋。
   - 沒有自動防護的部分：用 Bash（`sed -i`、腳本）改檔，hook 看不到，要到 harden 或 regress 的 checker 才會擋下；Codex 沒有 hook，只靠 checker。
6. **被擋下時**：不要繞過 hook（例如改用 Bash 寫檔）。照訊息補規劃或請使用者核准；規劃本身要改，先改 `pin_plan.toml` 與圖，再請使用者重新核准。

## 已知陷阱（Phase 7 實跑確認）

- **PDN 之後的 DEF 還沒有範本的腳位**：LibreLane Classic flow 先產生 PDN（`OpenROAD.GeneratePDN`），後面才套用 DEF 範本（`Odb.ApplyDEFTemplate`）。跑到 PDN 就停，`io_in` 等腳位沒有座標。證據：`p7_floorplan1`（停在 PDN）沒有腳位座標，`p7_floorplan2`（停在套用範本）有 637 支已擺放的腳位。不要靠 step 編號判斷，要看 DEF 裡腳位有沒有座標。
- **範本套用後腳位是 `FIXED`，不是 `PLACED`**：解析 DEF 的腳本要兩種都認（`scripts/check_pin_plan.py`、`scripts/plot_floorplan.py` 都已處理）。
- **跑到 `Odb.ApplyDEFTemplate` 時，標準元件還沒有位置**：要看邏輯分布，要跑到 `OpenROAD.GlobalPlacement`。有範本時，`OpenROAD.GlobalPlacementSkipIO` 的目錄只有 state，沒有 log（Phase 7 觀察）。
- **扁平放進大外殼時，整顆 die 鋪滿 tap cell**：Caravel wrapper（2920 × 3520 µm）有 15.5 萬個 component，其中約 14 萬是 tap／endcap，邏輯只有約 1.2 萬顆。會影響 harden 時間，要在 harden 前處理（Phase 7 待辦 5）。
- **沒用到的輸出腳位接常數時，tie cell（`conb_1`）會放在各自的腳位旁**，所以「頂層 glue」的 cell 會分布在整個 die 邊緣，這是正常的（Phase 7：191 顆 `conb_1`、48 顆 `buf_2`）。

## 用完後

1. 新的現象加進「經驗紀錄」，根因標明已驗證或推測。
2. 換 LibreLane 版本時，重看「已知陷阱」裡跟 step 順序有關的兩條。
3. 新的外殼（不是 Caravel）或 pad 不固定的設計，先擴充 `check_pin_plan.py` 與 `neg_pin_plan.py`，再開始規劃。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-12 | arvinsa-rtl-gds Phase 7 步驟 3–4 | wrapper RTL 先選了 GPIO 8–20，到 floorplan 才發現離 block 2–3 mm，RTL、`user_defines.v`、testbench 重做 | 已驗證：流程順序錯誤（先寫 RTL 才看腳位位置），使用者指出 | 改 GPIO 33–37；建本 skill 與四層強制（ADR-0019 決定 13） | ADR-0019 決定 10、13；`tapeout-precheck-caravel` 經驗紀錄 |
| 2026-10-12 | `p7_floorplan1`、`p7_floorplan2` | 停在 PDN 的 DEF 沒有 `io_in` 的座標 | 已驗證：套用範本在 PDN 之後；停在套用範本的 run 有 637 支腳位 | 出圖改跑到 `Odb.ApplyDEFTemplate` 或更後面 | `runs/p7_floorplan1`、`runs/p7_floorplan2` |
| 2026-10-12 | `p7_floorplan3`、`p7_floorplan4` | 停在套用範本時 cell 沒有位置；跑到 global placement（165 秒）後，邏輯聚在左下角，離 GPIO 33–37 與 Wishbone 都近 | 已驗證：global placement 在套用範本之後 | 模組框用 deferred_flatten 的暫時 config | `runs/layout_png/p7_floorplan4_modules.png` |
| 2026-10-12 | Phase 7 `p7_harden2`（wrapper 探索 harden 跑完後） | IR 的供電點模型差異很大：最壞組合整圈 6.87、左 9.77、下 20.65、右 39.2、上 143 mV（上限 20 mV） | 已驗證（單步 `IRDropReport` 加 `ir_worst.py`，5 種模型）：SoC 在左下角，壓降隨離供電點的距離變化；Caravel 實際從哪邊供電在 pad 階段沒有查，ADR-0019 決定 11 只寫「供電從 core ring 進來」 | 使用者指出應該在 floorplan 時就決定，加規則 2；Caravel 的實際接點查證中，之後列選項請使用者決定，寫進 `pin_plan.toml`（重新核准） | session scratchpad `ir_ring/`（5 種模型的 vsrc、IR 結果） |
| 2026-10-13 | Phase 7 IR（接續上一列） | 供電進入點晚查的代價：Caravel 原始碼查證、5 種供電模型、4 種 met4 寬度、5 個 block 位置的 what-if，約一天；最後 block 不用移，是因為改用 max power pattern 量電流（19.9 mV），不是位置選得好 | 已驗證：見 `tapeout-precheck-caravel` 規則 7 | 規則 2 的做法：pad 階段就用外殼的供電結構估 IR（電流也要先用 max power pattern 量），再定 block 位置 | ADR-0019 決定 18–20 |
