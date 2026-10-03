---
name: signoff-checker-qualification
description: 新寫或修改任何 PASS／FAIL checker（signoff metrics、DV、EQY、自寫腳本）、建立或更新 golden、處理 run 之間不可重現的差異，或要用植入錯誤（negative test／bug injection）證明 checker 抓得到錯誤時使用。Use when writing or changing a checker, maintaining golden results, or qualifying a checker with bug injection.
---

# Checker 設計、golden 與 testbench qualification

通用方法；各領域的具體 checker 放在對應 skill（例如 DRC baseline 在 `drc-signoff`）。本 repo 實例：`signoff/scripts/check_signoff.py`、`signoff/limits/*.toml`、`signoff/golden/*/README.md`、`dv/scripts/dvlib.py`、`signoff/eqy/run_eqy.py`、`pnr/soc_top/check_soc.py`、`*/neg_*.py`。

名詞：**checker** = 判 PASS／FAIL 的程式或規則；**golden** = 確認過正確的一次 run 的完整 metrics，之後逐項比對；**negative test（bug injection）** = 故意植入錯誤，確認 checker 真的 FAIL；**testbench qualification** = 植入錯誤後被抓到的比例。

## 規則（已驗證）

1. **只認明確 PASS**：少一個 metric、少一張表、表被截斷、工具沒跑完，都是 FAIL（Phase 2 獨立審查：截斷的斷線 pin 表原本判 PASS）。
2. **型別要嚴格**：`false` 不能冒充 0；slack 是 inf 或極大值（例如 1e30，代表沒有受約束的路徑）要 FAIL → `[corners] slack_max`。
3. **來源追溯**（`project-plan.md` §7.2）：
   - harden 的開始與結束都跑 `signoff/scripts/provenance.py`：工作目錄必須已全部 commit（含未追蹤檔）、submodule 在記錄的 commit、LibreLane 與 PDK 是 `env/versions.mk` 釘的版本；結束時 HEAD 不變，且 `resolved.json` 實際用的 LibreLane 版本與 PDK 也對。工作目錄不乾淨時 flow 照跑，但整體判 FAIL。
   - harden 把**整體**判定寫進 `<run>_signoff/result.txt`；後續步驟（`run_gl_core.py`、`run_eqy.py`、`run_gl_soc.py`、`neg_pnr.py`）只認這個檔案是 `harden-<x>: PASS`。只查其中一份 checker 輸出（例如 `signoff.txt`）不夠：soc 專用檢查或輸入一致性 FAIL 的 run 仍會被拿去用。
   - 比對 run 實際用的設定（`resolved.json`：`cpu_params.py --resolved`、`check_inputs.py --resolved`）。
   - **追溯範圍要涵蓋實際執行的程式與資料**：LibreLane 在 nix-shell 裡跑的是 clone 的原始碼，signoff SDC 也 `source` clone 裡的 `base.sdc`；只比 clone 的 commit 時，clone 裡改過的檔案不會被發現（Phase 3 獨立審查實測）。要加「clone 的 `git status --porcelain` 為空」，PDK 則對 run 用到的檔案做 sha256 清單比對（Phase 4）。
   - **下游也要確認 run 是這個 commit 產生的**：`provenance.json` 的 `repo_head` 必須等於目前的 `HEAD`。只看 `result.txt` 時，改了 RTL 後單獨跑 `make eqy-soc` 仍會用舊網表而 PASS（Phase 4）。
4. **「不是 0」的計數要寫出組成**並固定下來：Phase 2 unannotated 114 = 35 PCPI port + 41 tie HI + 38 clkload；soc_top = clkload + 32 個 `sram0/dout1` + 未用的 tie 輸出（soc_explore4：92 + 32 + 11）。
5. **golden**：逐項比對全部 metrics（key 集合也要相同）；只對**實測會變**的族群給誤差（detailed routing 多執行緒不可重現：slack、skew、線長、via、功耗、IR），約實測差異的 30–200 倍；count／area 一律不給誤差（`check_signoff.py` 會拒絕這種設定）。至少重跑一次確認可重現性。
6. **更新 golden**：先確認所有 limits 與自寫 checker PASS → 逐項說明與舊 golden 的差異 → 複製並記 sha256 → 再跑一次確認新 golden PASS。
7. **negative test 設計**：
   - 每個 checker 至少一個真錯誤，加一個正向對照（沒植入時 PASS）。
   - 植入點必須只命中一處；命中 0 或多處時，negative test 本身 FAIL（`edit()` 的寫法見 `neg_eqy.py`）。
   - 必須在**預期的** checker、以**預期的原因** FAIL；在別處 FAIL（缺檔、工具錯誤）不算抓到（`project-plan.md` §7.3）。
   - **先確認植入真的改變了結果**，再看 checker（見下表 P05、P13）。最直接的確認方式：植入後用同一個工具印出被改的那一項（例如 `report_checks -to <port>` 變成 `No paths found`）。
   - **「刪除／unset」不等於「從來沒有」**：要模擬「漏寫約束」或「漏接線」，就產生一份真的少了那一行的輸入，不要用工具的 unset／remove 指令（P13：OpenSTA `unset_output_delay` 之後 check_setup 仍當作有設）。
   - **說明與程式要一致**：每個案例在程式裡逐一斷言它聲稱涵蓋的每個 checker；docstring／README 寫了、程式沒測的，等於沒有（P10 原本只測 KLayout，說明卻寫也測 Magic）。
   - **假 run（fake run）要先有 positive control**：沒植入時假 run 必須整體 PASS。否則某一列（例如缺 STA 目錄的 `sta_setup`）永遠 FAIL，「整體 FAIL」的斷言就沒有作用。每個案例要斷言：FAIL 的只有被植入的那一列，而且整體判 FAIL（Phase 3 的 P08–P10、P14、P15 沒做到）。
   - **確認 FAIL 的位置和植入有關**：FAIL 訊息裡要有被植入的 instance、net 或座標，不能只看「有 FAIL」。
   - **比對粒度要分得出同類的新錯誤**：只比「種類」（例如 DRC 規則名）時，同種類多一個錯誤會漏掉；改比位置或逐筆比對（`drc-signoff` 規則 2）。
   - **自寫 checker 取代了工具原本的判定時**（例如 `ERROR_ON_MAGIC_DRC=false` 改由 `check_soc.py magic_drc` 判），這支自寫 checker 必須有自己的植入錯誤。
   - **借用另一個工具的植入方式時，先確認新工具讀得進植入後的檔案**：同一份植入錯誤的網表，Yosys（EQY）接受、Icarus（GL 模擬）因為 wire 先使用後宣告而編譯失敗（`neg_gl_soc.py csb0_inverted` 第一版）。編譯失敗不算抓到，所以 checker 正確判 FAIL，但這個案例等於沒測。
   - checker 自己也包括「來源追溯」這類流程檢查：`neg_provenance.py` 在本機 clone 上植入未提交檔案、版本不符等 9 種狀況（另有 2 個 positive test）。
8. **獨立審查**：讓沒寫 checker 的 agent 另外想植入錯誤；修正後把舊案例全部重跑（Phase 1 兩輪、Phase 2 一輪）。
9. **上一階段留下的項目要列入本階段的檢查清單**：exit review 的「留到下一階段」與「已知限制」逐條帶進下一階段的 exit 表（Phase 2 延到 Phase 3 的來源追溯，到 Phase 3 收尾才發現還沒做）。
10. **端到端 target（`make phase<N>`）要在乾淨 checkout 從頭跑到底才算驗證過**：
   - 中途停下的 run 只驗證了停下之前的 target。之後在開發目錄逐一補跑的 target 不算，因為開發目錄有忽略版控的建置產物（`fw/build/` 等）。
   - 每個 target 都要在 Makefile 宣告它需要的建置步驟。例如 `gl-soc` 需要 `fw`：第一次 `make phase3` 停在 harden-soc，沒有發現這個缺漏；第二次在乾淨 checkout 跑到 gl-soc，12/13 支測試報找不到 firmware。
   - 檢查方式：`cat .gitignore`，對每個被忽略的目錄 grep 有哪些腳本讀它，確認對應的 target 有宣告建置步驟。
   - 新寫的 negative test 腳本要先單獨跑完一次，再加進 phase target（`neg_gl_soc.py` 沒跑過就加進 `make phase3`，第三次 `make phase3` 才發現上面那個編譯錯誤）。

## 已知的 checker 漏洞類型（新 checker 要逐條對照）

| 類型 | 例子 | 出處 |
|---|---|---|
| 工具靜默略過某些情況 | EQY：gate 端某 bit 是常數時只記一行 `found constant gate bit` 就不證明；輸出被植入卡 0 時，15136 個分區全部證明通過 | `neg_eqy.py wdata3_stuck0`，`signoff/eqy/README.md` |
| 工具的檢查範圍比名稱小 | PSM（power grid checker）只查電源網路自己的 shape 連不連通，不查 macro 電源 pin；LibreLane 的 filtered unannotated 只認頂層 port | P05；`filter_unannotated.py` 70–85 行 |
| 植入沒有生效 | `PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路與原本逐字相同；`unset_output_delay` 不加 `-clock` 什麼都沒刪，加了 `-clock` 之後路徑消失、但 check_setup 仍當作有 output delay | P05 第一版、P13 第一、二版 |
| 說明與程式不符 | P10 的說明寫「KLayout 與 Magic DRC 都會 FAIL」，程式只斷言 KLayout | P10 第一版 |
| 比對的文字被輸出格式拆開 | LibreLane console 折行，`GRT-0229 ... usage=65534` 分在兩行，單行 regex 永遠對不到，重試永遠不會發生 | `pnr/librelane_flow.sh` 第一版；用模擬的 nix-shell 測 7 種情境（`make test-flow-retry`） |
| 下游只查部分判定 | `run_eqy.py`、`run_gl_soc.py` 只看 `signoff.txt`，不看 soc 專用檢查、輸入一致性 | Phase 3 收尾自查 |
| 工具快取了舊資料 | 換 LEF 後重跑 `CheckAntennas`，讀的仍是 ODB 裡的舊 antenna 資料 | P06 第一版 |
| 比對粒度太粗 | `check_soc.py magic_drc` 在 SRAM 外框內只比規則種類，多一個同種類的錯誤照樣 PASS | Phase 3 獨立審查（假報告實驗） |
| 追溯範圍比實際執行的程式小 | `provenance.py` 只比 LibreLane clone 的 commit，clone 裡改了 `base.sdc` 仍 PASS | Phase 3 獨立審查（實驗） |
| 下游不確認輸入來自哪個 commit | `run_eqy.py` 只看 `result.txt`，改 RTL 後單獨跑仍用舊網表 | Phase 3 獨立審查（讀程式） |
| 測試環境本身就 FAIL | neg-pnr 的假 run 沒有 STA 目錄，`sta_setup` 永遠 FAIL，「整體 FAIL」斷言失效 | Phase 3 獨立審查（run.log） |
| 依賴開發目錄才有的檔案 | `make gl-soc` 讀 `fw/build/*.hex`，卻沒有宣告依賴 `fw`；開發目錄有舊的建置產物，所以只在乾淨 checkout 才 FAIL | 第二次 `make phase3`（規則 10） |
| 植入方式只在一個工具驗證過 | `neg_eqy.edit()` 把 `wire` 宣告加在 module 最後：Yosys 接受，Icarus 報 `Check for declaration after use` | `neg_gl_soc.py csb0_inverted` 第一版 |
| 覆蓋不到的功能 | GL 模擬只看得到 firmware 用到的功能（`rdcycleh`、bus-error IRQ 漏掉） | Phase 2 限制 7 |

## 用完後

1. 新的 checker 漏洞或 golden 現象加進「經驗紀錄」，根因標明已驗證／推測。
2. 同一類型出現第二次或已用實驗確認，就搬進上面的表。
3. 確認引用的檔案仍存在。這次若「該用沒用」，修 description。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | arvinsa-rtl-gds neg-eqy | `wdata3_stuck0` 植入後 EQY 仍 `DONE (PASS)` | 已驗證：EQY 把對應到常數的 bit 視為已對應、不證明 | `run_eqy.py` 出現 `found constant` 即 FAIL；正向 run 為 0 筆 | `runs/neg_eqy_picorv32_core/wdata3_stuck0/eqy/summary.json` |
| 2026-10-03 | neg-pnr P05 | 拿掉 macro 電源設定後 PowerGridViolations 仍 PASS | 已驗證：電源網路 DEF 逐字相同 | 改成刪 SRAM 電源環上的 via → LVS FAIL | `pnr/soc_top/neg_pnr.py` |
| 2026-10-03 | neg-pnr P03 | 加上 `signoff.sdc`（`set_max_transition 1.0`）後，P03 用 `MAX_TRANSITION_CONSTRAINT=0.05` 植入會被後面的 SDC 蓋掉（推測，尚未實跑；依 base.sdc 先、signoff.sdc 後的順序推得） | 植入點不是 checker 實際讀到的值 | P01–P03 改成在 run 實際用的 signoff SDC 後面追加 | `pnr/soc_top/neg_pnr.py sdc_with()` |
| 2026-10-03 | neg-pnr P13 第一版 | `unset_output_delay [all_outputs]` 之後 check_setup 沒有新警告，case 判漏抓 | 已驗證：OpenSTA `Sdc.tcl` `unset_port_delay` 沒給 `-clock` 時 clk = NULL，只刪沒有 clock 的 delay | 改 `-clock` 仍無警告（見下一列） | `runs/neg_pnr/P13/run.log` |
| 2026-10-03 | P13 探針（單步重跑 STA） | `unset_output_delay -clock clk` 後 `report_checks -to uart_tx` 為 `No paths found`，但 `check_setup -unconstrained_endpoints` 與 `-no_output_delay` 都沒有輸出 | 已驗證：unset 之後 OpenSTA 仍視為有 output delay；SDC 直接少寫 `set_output_delay` 時 check_setup 報 `There are 42 unconstrained endpoints` | P13 改為產生少一行的 SDC | `pnr/soc_top/neg_pnr.py sdc_without_output_delay()` |
| 2026-10-03 | neg-pnr P10 | 說明寫也測 Magic DRC，程式只斷言 KLayout | 已驗證（讀程式） | 補上 Magic.DRC 重跑 + `check_soc.py magic_drc` 必須報框外違規 | `pnr/soc_top/neg_pnr.py p10()` |
| 2026-10-03 | Phase 3 收尾 | 下游只查 `signoff.txt`；`project-plan.md` §7.2 的來源追溯（Phase 2 延到 Phase 3）沒做 | 已驗證（讀程式） | `result.txt` + `provenance.py`；`neg_provenance.py` 11/11 | `signoff/scripts/provenance.py` |
| 2026-10-04 | 第二次 `make phase3`（乾淨 worktree，commit 658b6dd） | `gl-soc: FAIL`，12 支測試報 `firmware image fw/build/hello.hex not found` | 已驗證：Makefile 的 `gl-soc`／`neg-gl-soc` 沒有依賴 `fw`；第一次 `make phase3` 停在 harden-soc，沒走到這一步 | 兩個 target 加上 `fw`；新增規則 10；summary 改成 `n/N tests passed`（原本 `FAIL 1/13 tests` 容易讀成 1 支 FAIL） | `runs/p3_phase3_clean2.log` |
| 2026-10-04 | 第三次 `make phase3`（乾淨 worktree，commit acbc126） | `neg-gl-soc: FAIL 3/4`，`csb0_inverted` 編譯失敗 | 已驗證：植入的 `wire neg_eqy_inv` 宣告在使用之後，Icarus 拒絕（Yosys 接受，所以 EQY 那邊沒發現）；`neg_gl_soc.py` 在加進 `make phase3` 前沒有單獨跑過 | 宣告移到 `sram0` 前；修正後 GL 11/11 支測試報不一致、EQY 照樣 FAIL；規則 7、10 補一條 | `runs/p3_phase3_clean3.log` |
| 2026-10-04 | Phase 3 獨立審查（2 個 agent） | 文件 6 個數字寫錯；checker 漏洞 5 個（magic_drc 只比種類、provenance 不看 clone 內容、下游不比 commit、假 run 缺 positive control、neg-eqy 不比位置） | 已驗證（我重新核對程式與實驗輸出） | 文件更正；漏洞列為 Phase 3 已知限制 12–16、Phase 4 開頭修；規則 3、7 補 5 條 | `docs/phase_exit/phase3.md` |
