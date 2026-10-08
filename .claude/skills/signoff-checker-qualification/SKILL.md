---
name: signoff-checker-qualification
description: 新寫或修改任何 PASS／FAIL checker（signoff metrics、DV、EQY、自寫腳本）、建立或更新 golden（確認過正確的一次 run 的完整 metrics）、決定 golden 比對哪些 metric 可以有誤差、處理同樣設定重跑結果不同（包括 cell 數、diode 數、面積也跟著變，或 key 只出現在一邊：`[golden_layout_tolerance]`、`[golden_optional]`），或要用植入錯誤（negative test／bug injection）證明 checker 抓得到時使用，包括檢查「由程式產生的檔案」（例如由量測 JSON 產生的 .lib）時產生器公式本身要獨立驗證；附已知的 checker 漏洞類型表（包括 checker 或重試規則綁死 step 名稱，flow 換掉或多開 step 時靜默失效；重試留下的中止 step 目錄頂替完成的那次；只證明設定被讀到、沒證明生效（SDC 印了 uncertainty 但 STA 沒套用）；靠 instance 名稱辨識工具產生的結構；誤差表的保護字與萬用字元；強制機制（Stop hook）的觸發條件比規則小；抓到錯誤的機制和案例宣稱的不同；守門條件本身沒有測試；只檢查版本字串；暫用另一個設計的誤差），新 checker 要逐條對照。Use when writing or changing a checker, maintaining golden results and their tolerances, or qualifying a checker with bug injection.
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
   - **不可重現的步驟也會改變數量時**（Phase 5 Hazard3，ADR-0015）：第 41 步的 global routing 偶發不同（同一份輸入 27 次裡 5 次），detailed routing 也會讓繞線後的 antenna 修補多一輪、多插 diode，cell 數、diode 數、面積跟著變，「count／area 不給誤差」幾乎每次 FAIL。做法：
     - 先逐步比對 DEF 與 log 找到分歧的那一步，再單步重跑量頻率，確認是隨機而不是設定造成的；
     - 收集足夠的樣本：除了完整 harden，也可以拿分歧步驟重跑出來的不同結果，接著跑完後面的步驟；
     - 數量與面積放在另一個表（`[golden_layout_tolerance]`），連續量仍在原表；違規、錯誤類的計數與 `[equal]` 的 key 一律不給誤差，由 checker 拒絕（`VIOLATION_WORDS`）；
     - 雜訊大時，誤差用實測最大差異的約 5 倍，不用 30–200 倍（30 倍會讓 slack 誤差到 1.9 ns，等於不比）；
     - 每輪、每個 warning 這類可能只出現在一邊的 key，列進 `[golden_optional]`，只限 `__iter:` 與 `flow__warnings__count:<id>`；
     - 用 negative test 證明誤差邊界與拒絕規則都有效（`neg_pnr.py` P50、P51），並寫明 golden 抓不到「所有 metric 都只動在誤差內」的改變。
   - **族群要依「哪一步產生的」來分，不能只看「到目前有沒有變過」**：不可重現那一步（detailed routing）算出來的每個 metric 都先分類——最終 signoff 數字（`route__drc_errors`）完全相同；中間過程數字（`route__drc_errors__iter:*`，繞線器各輪剩下的 DRC 數）給誤差。Phase 4 的教訓：Phase 2 的 5 次 run 與 Phase 4 regress 1 這組都沒變，於是被列為「必須完全相同」；regress 2 才變（11 → 14），整個 regression FAIL 一次（約 30 分鐘後才 FAIL，重跑又要 2 小時）。中間過程數字給的誤差要寫明它其實等於不比（例如 ±100，高於看過的所有值），並用 negative test 證明最終數字仍被保護（`neg_pnr.py` P31）。
6. **更新 golden**：先確認所有 limits 與自寫 checker PASS → 逐項說明與舊 golden 的差異 → 複製並記 sha256 → 再跑一次確認新 golden PASS。golden 比對本身的 negative test：P12（instance 數 −10%）、P31（最終 DRC 數 +1、中間輪「誤差 + 1」都 FAIL，+3 PASS；誤差從上限檔讀）、P50（版圖誤差的邊界、碰到違規計數的 pattern）、P51（可選 key、一般 key 缺少、碰到 corner key 的 pattern）。
7. **negative test 設計**：
   - 每個 checker 至少一個真錯誤，加一個正向對照（沒植入時 PASS）。
   - 植入點必須只命中一處；命中 0 或多處時，negative test 本身 FAIL（`edit()` 的寫法見 `neg_eqy.py`）。
   - 必須在**預期的** checker、以**預期的原因** FAIL；在別處 FAIL（缺檔、工具錯誤）不算抓到（`project-plan.md` §7.3）。
   - **先確認植入真的改變了結果**，再看 checker（見下表 P05、P13）。最直接的確認方式：植入後用同一個工具印出被改的那一項（例如 `report_checks -to <port>` 變成 `No paths found`）。
   - **「刪除／unset」不等於「從來沒有」**：要模擬「漏寫約束」或「漏接線」，就產生一份真的少了那一行的輸入，不要用工具的 unset／remove 指令（P13：OpenSTA `unset_output_delay` 之後 check_setup 仍當作有設）。
   - **說明與程式要一致**：每個案例在程式裡逐一斷言它聲稱涵蓋的每個 checker；docstring／README 寫了、程式沒測的，等於沒有（P10 原本只測 KLayout，說明卻寫也測 Magic）。
   - **假 run（fake run）要先有 positive control**：沒植入時假 run 必須整體 PASS。否則某一列（例如缺 STA 目錄的 `sta_setup`）永遠 FAIL，「整體 FAIL」的斷言就沒有作用。每個案例要斷言：FAIL 的只有被植入的那一列，而且整體判 FAIL（Phase 3 的 P08–P10、P14、P15 沒做到）。
   - **確認 FAIL 的位置和植入有關**：FAIL 訊息裡要有被植入的 instance、net 或座標，不能只看「有 FAIL」。
   - **斷言抓到它的機制**：同一個錯誤可能被別的機制碰巧抓到（例如 EQY 在分區步驟就拒絕，沒有走到證明）。案例要測哪個機制，就斷言那個機制的原因（`neg_eqy.py REQUIRE`）；做不出只由該機制抓到的錯誤時，要在文件寫明「沒有案例證明 X」，不要寫成已涵蓋（Phase 5 獨立審查）。
   - **守門條件本身要有測試**：checker 或重試規則的每一道條件（例如「只在 usage=65534 時重試」），都要有一個情境在條件拿掉時 FAIL。驗證方法：把條件刪掉，跑一次測試，確認真的 FAIL（Phase 5：`test-flow-retry` 原本兩道條件都沒測到）。
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
| 工具的檢查範圍比名稱小 | PSM（power grid checker）只查電源網路自己的 shape 連不連通，不查 macro 電源 pin；LibreLane 的 filtered unannotated 只認頂層 port；`check_soc.py sram_lib` 只認 `Reading cell library` 一種 log 訊息、只比路徑結尾，經 `EXTRA_LIBS` 多讀一份 SRAM .lib 看不到，`check_inputs.py` 也只看 MACROS 不看 `LIB`／`EXTRA_LIBS` | P05；`filter_unannotated.py` 70–85 行；Phase 3.5 審查，Phase 5 開頭修：收集三種讀 .lib 的訊息、打開檔案看誰定義了 macro cell、解開 symlink 比完整路徑（P33–P36） |
| 植入沒有生效 | `PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路與原本逐字相同；`unset_output_delay` 不加 `-clock` 什麼都沒刪，加了 `-clock` 之後路徑消失、但 check_setup 仍當作有 output delay | P05 第一版、P13 第一、二版、N6 第一版（要替換的字串在新 .lib 裡已不存在）、P17 Phase 3.5 版（檔案在讀之前就被 `open(f, "w")` 清空；植入點檢查 `edit_once` 因此報錯，而不是什麼都沒改就判 PASS） |
| 說明與程式不符 | P10 的說明寫「KLayout 與 Magic DRC 都會 FAIL」，程式只斷言 KLayout | P10 第一版 |
| 比對的文字被輸出格式拆開 | LibreLane console 折行，`GRT-0229 ... usage=65534` 分在兩行，單行 regex 永遠對不到，重試永遠不會發生 | `pnr/librelane_flow.sh` 第一版；用模擬的 nix-shell 測 7 種情境（`make test-flow-retry`） |
| checker 綁死 step 名稱 | `review_criteria.py` 用 `OpenROAD.CTS` 找 CTS 的目錄，config 用 `substituting_steps` 換掉 CTS step 後就找不到；GRT-0229 的重試只認 `RepairDesignPostGRT`，flow 多開的 `ResizerTimingPostGRT` 出同一個錯誤時不重試。flow 換掉或多開 step 時，要 grep 所有用到 step 名稱的 checker 與腳本 | ADR-0016（`review_criteria.py` 改成依 `substituting_steps` 找）；`pnr/librelane_flow.sh` 與 `make test-flow-retry`（Phase 5） |
| 重試留下的中止目錄頂替完成的那次 | GRT-0229 重試後，同一個 step 有兩個目錄（中止的沒有 `state_out.json`）。`review_criteria.py` 的 uncertainty 檢查原本「任一個目錄」的 log 有那一行就 PASS：中止那次的 log 頂替了完成那次，P49 在這種 run 上沒被抓到。看 step 目錄的 checker 只採計有 `state_out.json` 的目錄；negative test 要造出「中止的目錄有、完成的沒有」 | P55（Phase 5，`neg-pnr` PicoRV32 54/55） |
| 下游只查部分判定 | `run_eqy.py`、`run_gl_soc.py` 只看 `signoff.txt`，不看 soc 專用檢查、輸入一致性 | Phase 3 收尾自查 |
| 工具快取了舊資料 | 換 LEF 後重跑 `CheckAntennas`，讀的仍是 ODB 裡的舊 antenna 資料；特性化的模擬快取不確認上次 ngspice 成功，波形太短時讀取一律判對 | P06 第一版；Phase 3.5 審查，Phase 5 開頭修（N15） |
| 比對粒度太粗 | `check_soc.py magic_drc` 在 SRAM 外框內只比規則種類，多一個同種類的錯誤照樣 PASS | Phase 3 獨立審查（假報告實驗） |
| 前處理把要檢查的東西抹掉 | EQY 的 `sat` strategy 先 `formalff -clk2ff`，所有 flip-flop 變成同一個隱含 clock；flip-flop 的 CLK 改接反相 clock，EQY 與「只比 cell 種類」的結構比對都 PASS | Phase 4 審查；`run_eqy.py` clock_sources、`neg_eqy.py flop_clk_inverted` |
| 只看「在不在」，不看大小或位置 | IR 電壓源只檢查點在 strap 上：大小改成 2000 µm（等於整條 strap 理想供電）或移到 strap 中間都 PASS；`char.json` 只檢查 PVT 名稱齊全，某個 PVT 的紀錄換成 tt 的資料照樣 PASS（hold 弧樂觀 0.4 ns） | Phase 4 審查；P27、P28；Phase 3.5 審查，Phase 5 開頭修（N9） |
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
| 產生器的公式沒有獨立驗證 | `gen_char_lib.py` 由 `char.json` 產生 .lib：`--check` 只比「同一支程式的輸出」，公式寫錯時 .lib 與 JSON 照樣一致；N5–N8 的測試資料每格相同、又被下限蓋過，取最大與取最小弄反、少乘 1.6 都 PASS。要用不 import 產生器的獨立重算，或每格不同、高過下限的測試資料 | Phase 3.5 獨立審查；Phase 5 開頭修：`check_char_lib.py`，改壞公式的產生器 M1–M5 都要 FAIL（N12） |
| 斷言分不出 FAIL 的原因 | P17 只看 `char_lib` 列 FAIL：char 目錄多一個 `.DS_Store` 也 FAIL，判定照樣成立；N8 斷言的 PVT 名稱一定出現在「expected exactly」那串清單裡 | Phase 3.5 獨立審查；Phase 5 開頭修：斷言訊息內容（P17 要 STALE 並指名檔案、N8 解析缺的是哪一個），沒有 positive control 的補上（P32） |
| 非有限的數值被比較吞掉 | `char.json` 的 setup 是 NaN 時，`max(下限, nan)` 默默變成下限；hold 弧寫出 `nan` 的 .lib 也被接受 | Phase 3.5 獨立審查；Phase 5 開頭修（N11） |
| 失敗時留下新舊混合的輸出 | 特性化有一個 PVT 失敗、印 FAIL，`char.json` 已經寫入其他 PVT 的新結果，失敗的 PVT 留舊紀錄，之後照樣產生 5 份 .lib | Phase 3.5 獨立審查；Phase 5 開頭修：有失敗就不寫檔（N16） |
| 被測的模型本身太樂觀 | IR 用「所有 pin 形狀都是理想電源」，算出 0.3 mV，任何門檻都會 PASS | Phase 4 IR 研究（`pdn-ir-drop` 規則 10） |
| 只證明「設定被讀到」，沒證明「生效」 | `review_criteria.py` 的 uncertainty 檢查只找 SDC 印出的那一行：把 15 個 corner 報表裡的 uncertainty 全刪掉仍 PASS；setup／hold 的 0.25 又剛好等於 LibreLane 預設，單看數字分不出來。要從工具的結果核對實際套用的值 | Phase 5 獨立審查；`review_criteria.py uncertainty_applied`（50,670 條路徑逐條比對），P56 |
| 靠名稱辨識工具產生的結構 | `cts_macro_latency` 只認 `delaybuf_*` 這個 instance 名稱，改名 `clkdly_` 就 PASS；目錄只認沒有 `-1` 字尾的名稱，重複的 step 漏掉。改成結構判斷：`sram0/clk0` 上方只驅動下一級的 clock buffer 連續幾級（有做 latency 對齊 11、12 級，沒做 0 級）。注意 latency 對齊**不會**讓級數變多（對齊就是讓延遲相同），比級數分不出來 | Phase 5 獨立審查；`check_soc.py sram_clock_chain`，P58–P60 |
| 誤差表的保護不完整 | `[golden_layout_tolerance]` 的受保護字沒有 `floating`、`warning`：floating net 2 → 40 可以被放進誤差表；`[golden_optional]` 接受 `flow__warnings__count:*`，任何新種類的 warning 都會被略過 | Phase 5 獨立審查；`check_signoff.py VIOLATION_WORDS`，P50、P51 的變體 |
| 強制機制的觸發條件比規則的範圍小 | Stop hook 只在看到 `criteria_review.txt` 時才要求 review：沒跑 `review_criteria.py` 的 `harden-core`，以及它當掉、沒有結果行時，都放行。觸發條件要用「每次 harden 一定會寫的檔案」（`result.txt`），並把「當掉」也當成要擋的情況 | Phase 5 獨立審查；`require_criteria_review.py`，`test-review-hook` 12/12 |
| 抓到的機制和案例宣稱的不同 | `reset_b_tied1` 寫「只有證明抓得到」，實際上 EQY 在分區步驟就因名稱衝突拒絕（0 個分區），根本沒有證明。要斷言抓到它的原因；改用 tie cell 或繞過同步器，結果也一樣 | Phase 5 獨立審查；`neg_eqy.py REQUIRE`，`signoff/eqy/README.md` |
| 測試沒有測到守門條件本身 | `test-flow-retry` 11/11：把「只在 usage=65534 時重試」或「已完成的 step 不重試」任一條件拿掉，測試仍 11/11。每一道條件都要有一個「條件拿掉就 FAIL」的情境 | Phase 5 獨立審查；`grtreal`、`grtdone`（13/13），拿掉條件後實測 FAIL |
| 只檢查版本字串 | xPack 檢查只比 `-dumpversion`：一支只會 `echo 15.2.0` 的腳本 PASS。要核對產品本身，例如 `--version` 寫 xPack，而且找得到 newlib 的 `libc.a` | Phase 5 獨立審查；`env/check_env.sh`，`neg-regress xpack_fake` |
| 暫用另一個設計的數字 | PicoRV32 的版圖誤差暫用 Hazard3 量到的值：diode +54、standard cell +69 這種真實改變也 PASS。沒有這顆設計的實測就不給誤差，量到再訂 | Phase 5 獨立審查；`signoff/limits/soc_top.toml`，P50（沒有誤差項時 +1 就 FAIL） |
| 比對到資料，不是指令；只看第一個指令 | 全域守門 hook 用 regex 找 `make harden`，把 heredoc 裡「README 提到 `make harden-soc`」也當成要開 harden 而擋下。比對前先拿掉 heredoc 內容與引號內字串。同一個 hook 在 `git push origin main && git push gitlab main` 只看第一個 push，誤報「gitlab 還沒推」：一行裡的每一個指令都要看 | 2026-10-08；`~/.claude/hooks/guard-bash.py shell_text()`，`test_guard_bash.py` |

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
| 2026-10-05 | Phase 5 開頭：修 Phase 3.5 審查的 12 個漏洞 | 每個漏洞補 negative test：neg-char N9–N16、neg-pnr P33–P36，P17 斷言收緊、P32 加 positive control、py-check 自我測試 11 段；新案例先在修正前的 checker 上確認抓不到 | 已驗證 | 漏洞類型表的「（未修）」改成修法與案例；修 `check_soc.py` 時寫錯的訊息（字串接 list）讓 P30 FAIL，被既有的案例抓到 | `docs/phase_exit/phase5.md` |
| 2026-10-07 | Phase 5 建 Hazard3 golden（第 5 次 harden，`3a28d54`） | ① `soc_top_hazard3.toml` 從 PicoRV32 版複製，`timing__unannotated_net__count` 133 是 PicoRV32 的組成，Hazard3 的 run 是 125；② golden 的 `design__instance__count__hold_buffer` 是 0，網表卻有 2,739 顆 hold buffer | 已驗證：① 規則 4 的組成換了設計就要重數（15 個 corner 都是 81 clkload + 32 `sram0/dout1` + 12 tie）；② 這個 metric 取最後一個 resizer 步驟報的數字，開了 `RUN_POST_GRT_RESIZER_TIMING` 後是那一步的 0，而且 `RSZ-0032` 本來就不是總數（`drv-timing-closure` 規則 7） | 上限改 125 並寫明組成；golden README 註明這個 metric 的意思；換 core 的規則寫進 `core-migration-hazard3` 規則 22 | `signoff/limits/soc_top_hazard3.toml`、`signoff/golden/soc_top_hazard3/README.md` |
| 2026-10-07 | Phase 5 Hazard3 第 6 次 harden（新 golden 的確認 run） | golden 比對 FAIL 61 個 metric，含數量、面積與 key 集合；signoff 全部 PASS | 已驗證：規則 5 假設「不可重現的只有 detailed routing」，這次第 41 步的 global routing 偶發不同（之後單步重跑合計 27 次裡 5 次不同，約 19%），之後的 cell 數跟著變 | 規則 5 的前提對 Hazard3 版不成立；ADR-0015，規則 5 加了「不可重現的步驟也會改變數量時」 | `flow-regression-reproducibility` 經驗紀錄 |
| 2026-10-07 | Phase 5 Hazard3 第 7 次 harden | golden 比對 FAIL 11 個 metric（diode、cell 數、面積），signoff 全部 PASS | 已驗證：detailed routing 的差異經由繞線後的 antenna 修補（多一輪、多 1 顆 diode）改變數量；規則 5 原本只看過它改變中間輪 DRC 數。加上第 6 次的第 41 步，Hazard3 版三次 harden 只有來源 run 自己與 golden 完全相同 | 使用者決定改 golden 規則：ADR-0015（`[golden_layout_tolerance]`、`[golden_optional]`，約實測最大差異的 5 倍，P50、P51） | `flow-regression-reproducibility` 經驗紀錄 |
| 2026-10-07 | Phase 5 ADR-0016（`adac1a9`、`2caad0e`） | 新 checker `check_soc.py cts_macro_latency`（config 有替換、run 只有自訂 CTS step、log 有 plugin 那一行、網表沒有 `delaybuf_*`）；正式 harden 兩個 CPU 都在第 44 步 GRT-0229 中止、沒有重試 | 已驗證：重試規則綁 `RepairDesignPostGRT` 一個 step 名稱；`review_criteria.py` 的 step 清單也綁名稱（這次先改好才沒漏） | negative test P52–P54（網表多一顆 `delaybuf_0_clk`、log 少一行、config 少替換）；先用舊做法的 run 確認 FAIL；`make test-flow-retry` 加 3 種情境並檢查 `--from`，新情境用舊腳本 8/11 FAIL；漏洞類型表加「checker 綁死 step 名稱」 | `pnr/soc_top/neg_pnr.py`、`pnr/test_librelane_flow.sh` |
| 2026-10-07 | Phase 5 PicoRV32 確認 harden（`1d13775`）的 `neg-pnr` | `[FAIL] P49: expected FAIL at review_criteria.py uncertainty`（54/55）；Hazard3 同一個 commit 55/55 | 已驗證：PicoRV32 這次第 44 步重試過，`ResizerTimingPostGRT` 有 44（中止）、45（完成）兩個目錄；P49 刪的是 45 的那一行，`review_criteria.py` 接受 44 的 | `review_criteria.py` 只採計有 `state_out.json` 的目錄、每個都要有那一行；加 P55（自己造一個中止目錄，不靠 run 剛好有重試）：舊版兩個 CPU 都漏、新版都抓到，P49 也抓到 | `runs/p5_pico_neg-pnr.log`、`pnr/soc_top/neg_pnr.py` |
| 2026-10-08 | Phase 5 exit 的獨立審查（agent，在 run 的副本上做實驗） | 8 個 checker 漏洞：uncertainty 只看印出的行、`cts_macro_latency` 靠名稱、誤差表保護字與萬用字元、Stop hook 不涵蓋 harden-core 與當掉、`reset_b_tied1` 不是靠證明、`test-flow-retry` 沒測條件、xPack 只看版本字串、PicoRV32 暫用 Hazard3 的誤差；沒有一個讓本階段結果變成假 PASS | 已驗證：逐項做出壞掉的輸入、跑 checker、看到 PASS | 全部修正，各有 negative test（P50、P51 變體、P56–P62、test-review-hook、test-flow-retry、neg-regress）；漏洞類型表加 9 種；規則 7 加兩條 | `docs/phase_exit/phase5.md`「獨立審查」，commit `1dee974` |
| 2026-10-08 | Phase 5 PicoRV32 的乾淨 `make regress-picorv32`（`5aaf036`） | `harden-soc` FAIL：golden 10 個版圖 metric 不同（diode 100 → 99、cell ±1、`global_route__vias` 20 → 11），其他全 PASS | 已驗證：PicoRV32 的版圖誤差依決定清空，這是第一次量到 PicoRV32 在 run 之間的差異 | 使用者決定再量 2 次，用 4 個樣本的最大差異 × 5 訂誤差（ADR-0015 的方法） | p5fin_pico worktree `runs/p5fin_pico_regress_signoff/criteria_review.md` |
| 2026-10-08 | Phase 5 結案（`71b1454`） | PicoRV32 SoC 加寬 met5 後共 6 次 run，版圖只有兩種結果（3 次與 golden 相同、3 次差 1 顆 diode）；依 4 個樣本訂的誤差這次沒用上（435 個逐項相同）。picorv32_core 之前兩次各有 71 個在誤差內，這次 325 個逐項相同 | 已驗證 | 誤差仍照「實測最大差異 × 5」；只有一兩個樣本時，結果剛好相同不代表一直相同（規則 5） | `docs/phase_exit/phase5.md`「可重現性」 |
