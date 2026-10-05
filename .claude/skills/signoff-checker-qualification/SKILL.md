---
name: signoff-checker-qualification
description: 新寫或修改任何 PASS／FAIL checker（signoff metrics、DV、EQY、自寫腳本）、建立或更新 golden（確認過正確的一次 run 的完整 metrics）、決定 golden 比對哪些 metric 可以有誤差、處理同樣設定重跑結果不同，或要用植入錯誤（negative test／bug injection）證明 checker 抓得到時使用；附已知的 checker 漏洞類型表，新 checker 要逐條對照。Use when writing or changing a checker, maintaining golden results and their tolerances, or qualifying a checker with bug injection.
---

# Checker 設計、golden 與 testbench qualification

通用方法；各領域的具體 checker 放在對應 skill（例如 DRC baseline 在 `drc-signoff`）。本 repo 實例：`signoff/scripts/check_signoff.py`、`signoff/limits/*.toml`、`signoff/golden/*/README.md`、`dv/scripts/dvlib.py`、`signoff/eqy/run_eqy.py`、`pnr/soc_top/check_soc.py`、`*/neg_*.py`。

名詞：**checker** = 判 PASS／FAIL 的程式或規則；**golden** = 確認過正確的一次 run 的完整 metrics，之後逐項比對；**negative test（bug injection）** = 故意植入錯誤，確認 checker 真的 FAIL；**testbench qualification** = 植入錯誤後被抓到的比例。

## 規則（已驗證）

1. **只認明確 PASS**：少一個 metric、少一張表、表被截斷、工具沒跑完，都是 FAIL（Phase 2 獨立審查：截斷的斷線 pin 表原本判 PASS）。
2. **型別要嚴格**：`false` 不能冒充 0；slack 是 inf 或極大值（例如 1e30，代表沒有受約束的路徑）要 FAIL → `[corners] slack_max`。
3. **來源追溯**（`project-plan.md` §7.2）：
   - harden 的開始與結束都跑 `signoff/scripts/provenance.py`：工作目錄必須已全部 commit（含未追蹤檔）、submodule 在記錄的 commit、LibreLane 與 PDK 是 `env/versions.mk` 釘的版本；結束時 HEAD 不變，且 `resolved.json` 實際用的 LibreLane 版本與 PDK 也對。工作目錄不乾淨時 flow 照跑，但整體判 FAIL。
   - harden 把**整體**判定寫進 `<run>_signoff/result.txt`；後續步驟（`run_guard.py` 管的 9 個下游步驟：EQY、gate-level 模擬、它們的 negative test、`neg_pnr.py`）只認這個檔案是 `harden-<x>: PASS`。只查其中一份 checker 輸出（例如 `signoff.txt`）不夠：soc 專用檢查或輸入一致性 FAIL 的 run 仍會被拿去用。
   - 比對 run 實際用的設定（`resolved.json`：`cpu_params.py --resolved`、`check_inputs.py --resolved`）。
   - **追溯範圍要涵蓋實際執行的程式與資料**：LibreLane 在 nix-shell 裡跑的是 clone 的原始碼，signoff SDC 也 `source` clone 裡的 `base.sdc`；只比 clone 的 commit 時，clone 裡改過的檔案不會被發現（Phase 3 獨立審查實測）。Phase 4 已加：clone 的 `git status --porcelain` 為空、PDK 6 個目錄的內容摘要、`resolved.json` 的 PDK 路徑都在檢查範圍內。做法與陷阱在 `flow-regression-reproducibility`。
   - **下游也要確認 run 是這個 commit 產生的**：`provenance.json` 的 `repo_head` 必須等於目前的 `HEAD`。只看 `result.txt` 時，改了 RTL 後單獨跑 `make eqy-soc` 仍會用舊網表而 PASS。Phase 4 已加 `signoff/scripts/run_guard.py` 與 `neg_run_guard.py`。
4. **「不是 0」的計數要寫出組成**並固定下來：Phase 2 unannotated 114 = 35 PCPI port + 41 tie HI + 38 clkload；soc_top = clkload + 32 個 `sram0/dout1` + 未用的 tie 輸出（soc_explore4：92 + 32 + 11）。
5. **golden**：逐項比對全部 metrics（key 集合也要相同）。不可重現的那一步（多執行緒 detailed routing）之後算出來的數字，依下一點分類後才給誤差：隨繞線微小變動的連續量（slack、skew、線長、via、功耗、IR）給很小的誤差，約實測差異的 30–200 倍；count／area 一律不給誤差（`check_signoff.py` 會拒絕這種設定）。至少重跑一次確認可重現性，但一次相同不代表可重現。
   - **族群要依「哪一步產生的」來分，不能只看「到目前有沒有變過」**：不可重現那一步（detailed routing）算出來的每個 metric 都先分類——最終 signoff 數字（`route__drc_errors`）完全相同；中間過程數字（`route__drc_errors__iter:*`，繞線器各輪剩下的 DRC 數）給誤差。Phase 4 的教訓：Phase 2 的 5 次 run 與 Phase 4 regress 1 這組都沒變，於是被列為「必須完全相同」；regress 2 才變（11 → 14），整個 regression FAIL 一次（約 30 分鐘後才 FAIL，重跑又要 2 小時）。中間過程數字給的誤差要寫明它其實等於不比（例如 ±100，高於看過的所有值），並用 negative test 證明最終數字仍被保護（`neg_pnr.py` P31）。
6. **更新 golden**：先確認所有 limits 與自寫 checker PASS → 逐項說明與舊 golden 的差異 → 複製並記 sha256 → 再跑一次確認新 golden PASS。golden 比對本身的 negative test：P12（instance 數 −10%）、P31（最終 DRC 數 +1、中間輪 +101 都 FAIL，+3 PASS）。
7. **negative test 設計**：
   - 每個 checker 至少一個真錯誤，加一個正向對照（沒植入時 PASS）。
   - 植入點必須只命中一處；命中 0 或多處時，negative test 本身 FAIL（`edit()` 的寫法見 `neg_eqy.py`）。
   - 必須在**預期的** checker、以**預期的原因** FAIL；在別處 FAIL（缺檔、工具錯誤）不算抓到（`project-plan.md` §7.3）。
   - **先確認植入真的改變了結果**，再看 checker（見下表 P05、P13）。最直接的確認方式：植入後用同一個工具印出被改的那一項（例如 `report_checks -to <port>` 變成 `No paths found`）。
   - **「刪除／unset」不等於「從來沒有」**：要模擬「漏寫約束」或「漏接線」，就產生一份真的少了那一行的輸入，不要用工具的 unset／remove 指令（P13：OpenSTA `unset_output_delay` 之後 check_setup 仍當作有設）。
   - **說明與程式要一致**：每個案例在程式裡逐一斷言它聲稱涵蓋的每個 checker；docstring／README 寫了、程式沒測的，等於沒有（P10 原本只測 KLayout，說明卻寫也測 Magic）。
   - **假 run（fake run）要先有 positive control**：沒植入時假 run 必須整體 PASS。否則某一列（例如缺 STA 目錄的 `sta_setup`）永遠 FAIL，「整體 FAIL」的斷言就沒有作用。每個案例要斷言：FAIL 的只有被植入的那一列，而且整體判 FAIL（Phase 3 的 P08–P10、P14、P15 沒做到）。
   - **確認 FAIL 的位置和植入有關**：FAIL 訊息裡要有被植入的 instance、net 或座標，不能只看「有 FAIL」。
   - **位置檢查本身要能分出不同案例**：對每一對植入點不同的案例，A 的 FAIL 名稱不能全部落在 B 的「附近」範圍內，否則範圍大到什麼都接受（`neg_eqy.py` 的交叉檢查；Phase 4 審查前 bus pin 整條一起算，`din5_stuck0` 的範圍含全部 32 個 bit）。
   - **斷言要看全部問題，不要只看第一個**：checker 只印第一個問題時，案例能 PASS 可能只是報告順序剛好（P23：29 ns 時 ss corner 的 min pulse width 也 FAIL，只因 nom_tt 排第一才看到 min_period；P21 只看第一個不符的違規的規則）。讓 checker 印出全部問題的種類，斷言「種類集合」。
   - **比對粒度要分得出同類的新錯誤**：只比「種類」（例如 DRC 規則名）時，同種類多一個錯誤會漏掉；改比位置或逐筆比對（`drc-signoff` 規則 2）。
   - **修 checker 漏洞時，negative test 要證明「舊 checker 會漏、新 checker 會抓」**：植入的錯誤若連舊 checker 也抓得到，就沒有測到漏洞。P21 第一版植入的 li1 細線被 Magic 報成 SRAM 單獨時沒有的規則（`li.c1`），舊的「只比種類」也會 FAIL；改成 SRAM 單獨時也有的 `li.3` 才是在測位置比對。同理，P07 改成兩個 net 各 11 mV：各自低於 20 mV、合計超過，舊的單 net 判定會漏。
   - **一個植入會牽動不只一列時，明列哪幾列、為什麼**：假 run 中把 `sram0` 在 DEF 移 10 µm，`placement` 與 `magic_drc`（以 DEF 位置當比對原點）都 FAIL；`sram0` 改名，`macro` 與 `port1_tieoff`（找不到 `sram0`）都 FAIL。斷言寫成「FAIL 的列剛好是這幾列」，不要放寬成「至少這一列 FAIL」。
   - **新的測試（firmware、directed test）也要被植入錯誤證明有效**：在網表植入它要補的錯誤，只跑新測試（`dv-directed-tests` 規則 6）。
   - **自寫 checker 取代了工具原本的判定時**（例如 `ERROR_ON_MAGIC_DRC=false` 改由 `check_soc.py magic_drc` 判），這支自寫 checker 必須有自己的植入錯誤。
   - **借用另一個工具的植入方式時，先確認新工具讀得進植入後的檔案**：同一份植入錯誤的網表，Yosys（EQY）接受、Icarus（GL 模擬）因為 wire 先使用後宣告而編譯失敗（`neg_gl_soc.py csb0_inverted` 第一版）。編譯失敗不算抓到，所以 checker 正確判 FAIL，但這個案例等於沒測。
   - checker 自己也包括「來源追溯」這類流程檢查：`neg_provenance.py` 在本機 clone 上植入未提交檔案、版本或內容不符、經 symlink 讀範圍外的檔等 16 種狀況（另有 3 個 positive test）。
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
| 植入沒有生效 | `PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路與原本逐字相同；`unset_output_delay` 不加 `-clock` 什麼都沒刪，加了 `-clock` 之後路徑消失、但 check_setup 仍當作有 output delay | P05 第一版、P13 第一、二版、N6 第一版（要替換的字串在新 .lib 裡已不存在） |
| 說明與程式不符 | P10 的說明寫「KLayout 與 Magic DRC 都會 FAIL」，程式只斷言 KLayout | P10 第一版 |
| 比對的文字被輸出格式拆開 | LibreLane console 折行，`GRT-0229 ... usage=65534` 分在兩行，單行 regex 永遠對不到，重試永遠不會發生 | `pnr/librelane_flow.sh` 第一版；用模擬的 nix-shell 測 7 種情境（`make test-flow-retry`） |
| 下游只查部分判定 | `run_eqy.py`、`run_gl_soc.py` 只看 `signoff.txt`，不看 soc 專用檢查、輸入一致性 | Phase 3 收尾自查 |
| 工具快取了舊資料 | 換 LEF 後重跑 `CheckAntennas`，讀的仍是 ODB 裡的舊 antenna 資料 | P06 第一版 |
| 比對粒度太粗 | `check_soc.py magic_drc` 在 SRAM 外框內只比規則種類，多一個同種類的錯誤照樣 PASS | Phase 3 獨立審查（假報告實驗） |
| 前處理把要檢查的東西抹掉 | EQY 的 `sat` strategy 先 `formalff -clk2ff`，所有 flip-flop 變成同一個隱含 clock；flip-flop 的 CLK 改接反相 clock，EQY 與「只比 cell 種類」的結構比對都 PASS | Phase 4 審查；`run_eqy.py` clock_sources、`neg_eqy.py flop_clk_inverted` |
| 只看「在不在」，不看大小或位置 | IR 電壓源只檢查點在 strap 上：大小改成 2000 µm（等於整條 strap 理想供電）或移到 strap 中間都 PASS | Phase 4 審查；P27、P28 |
| 總和允許負項 | `[max_sum]` VDD 19 mV + GND −15 mV = 4 mV 判 PASS | Phase 4 審查；P29 |
| 容許值套到不需要的類別 | DRC 位置比對的 100 nm 對 30 種規則都放寬，實測只有 2 種需要；li.3 看不到的面積從 0.9% 變 6.5% | Phase 4 審查；`check_soc.py DRC_POS_TOL_RULES` |
| 摘要列永遠 PASS | golden 比對的摘要列不扣掉不符的 key，236 列 FAIL 時仍印 `[PASS] golden 434 metrics: 429 identical` | Phase 4 文件審查；`check_signoff.py` |
| 路徑比對不解開 symlink | provenance 只比 PDK_ROOT 字串結尾：另一份同名版本目錄、或經 `~/.ciel/sky130A` symlink 讀範圍外的檔，都 PASS | Phase 4 審查；`neg_provenance.py resolved_other_install`、`resolved_symlink` |
| 只在結尾檢查一次 | `make regress` 只在最後讀 HEAD：中途 commit 時前段 target 跑的是舊 commit；`make -i regress` 讓 FAIL 的子 make 回 0 | Phase 4 審查；`neg_regress.py` |
| 追溯範圍比實際執行的程式小 | `provenance.py` 只比 LibreLane clone 的 commit，clone 裡改了 `base.sdc` 仍 PASS | Phase 3 獨立審查（實驗） |
| 下游不確認輸入來自哪個 commit | `run_eqy.py` 只看 `result.txt`，改 RTL 後單獨跑仍用舊網表 | Phase 3 獨立審查（讀程式） |
| 測試環境本身就 FAIL | neg-pnr 的假 run 沒有 STA 目錄，`sta_setup` 永遠 FAIL，「整體 FAIL」斷言失效 | Phase 3 獨立審查（run.log） |
| 依賴開發目錄才有的檔案 | `make gl-soc` 讀 `fw/build/*.hex`，卻沒有宣告依賴 `fw`；開發目錄有舊的建置產物，所以只在乾淨 checkout 才 FAIL | 第二次 `make phase3`（規則 10） |
| 植入方式只在一個工具驗證過 | `neg_eqy.edit()` 把 `wire` 宣告加在 module 最後：Yosys 接受，Icarus 報 `Check for declaration after use` | `neg_gl_soc.py csb0_inverted` 第一版 |
| 覆蓋不到的功能 | GL 模擬只看得到 firmware 用到的功能（`rdcycleh`、bus-error IRQ 漏掉） | Phase 2 限制 7；Phase 4 用 `counters`、`buserr` 補 |
| 工具報的名稱與植入點的名稱不同 | EQY 報合成網表的名稱，最終網表在 flip-flop 與 port 之間多了好幾級 buffer；只比植入的 instance 會誤判「不在植入點」 | Phase 4 `neg_eqy.py` 位置檢查（走過 buffer 鏈） |
| 判定只看一半的量 | LibreLane 的 `ir__drop__worst` 只有 VDD；20 mV 的預算是 VDD 降壓 + GND 抬升 | Phase 4 IR 研究 |
| 被測的模型本身太樂觀 | IR 用「所有 pin 形狀都是理想電源」，算出 0.3 mV，任何門檻都會 PASS | Phase 4 IR 研究（`pdn-ir-drop` 規則 10） |

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
| 2026-10-04 | Phase 4 修 5 個漏洞 | 加上「只有被植入的那一列 FAIL」的斷言後，P09、P14 各多一列 FAIL | 已驗證：兩列共用同一個輸入（DEF 位置、`sram0` 實例） | 斷言改成「剛好這幾列」並寫明原因（規則 7） | `pnr/soc_top/neg_pnr.py` |
| 2026-10-04 | Phase 4 P21 第一版 | 外框內植入被 `li.c1` 抓到，但這條規則不在 SRAM 基準裡 | 已驗證：不是在測位置比對 | 改 `li.3`（規則 7） | `drc-signoff` negative test 一節 |
| 2026-10-04 | Phase 4 獨立審查（checker 漏洞，agent） | 10 項：clock 接線沒人檢查、IR 電壓源大小與位置、provenance symlink、regress 開頭沒記 HEAD、`make -i`、P21／P23 只看第一個問題、neg-eqy 位置範圍太寬、`[max_sum]` 負項、DRC 容許值太寬、py-check 不看跨檔名稱 | 已驗證（審查者用 python 小實驗與程式碼；主控重讀程式確認） | 除了 run_guard 不查工作目錄（regress 已由 provenance-final 擋）與 py-check 跨檔（記為限制）都修正並加 negative test | `docs/phase_exit/phase4.md` 獨立審查一節 |
| 2026-10-04 | Phase 4 `make regress` 第 2 次（乾淨 checkout，`c635ffb`） | harden-soc FAIL：`[FAIL] golden route__drc_errors__iter:2: run=14 expected=11`；其他 433 個在誤差內或相同，signoff 全部 PASS | 已驗證：第 45 步輸入逐 byte 相同，多執行緒繞線在 antenna 修補後的重繞分歧；這組中間數字被錯列為「必須完全相同」 | 使用者決定給 ±100（兩個設計），最終 DRC 數仍完全相同；P31（規則 5） | `signoff/golden/soc_top/README.md` 可重現性 |
| 2026-10-05 | Phase 3.5 `neg_char.py` N6 | 手改 .lib 的植入改成新餘量後什麼都沒改到（要替換的 `2.7500` 已不在 .lib 裡），`--check` 判沒有過期，N6 FAIL | 已驗證：植入沒有檢查替換次數 | 改成編輯 `timing_type : rising_edge;` 並斷言替換次數；N1–N6 6/6 PASS（「植入沒有生效」一列） | `ip/sram/char/neg_char.py` |
