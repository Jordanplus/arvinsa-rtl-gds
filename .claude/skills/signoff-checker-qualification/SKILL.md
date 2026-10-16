---
name: signoff-checker-qualification
description: 新寫或修改任何 PASS／FAIL checker（signoff metrics、RTL testbench、EQY、自寫腳本）、建立或更新 golden 與它的誤差、要用植入錯誤（negative test／bug injection）證明 checker 抓得到時使用。也用在這些情況：同樣設定重跑結果不同（cell 數、diode 數、面積也變，或 key 只出現在一邊；`[golden_layout_tolerance]`、`[golden_optional]`）；改完 checker 後某一列對每個 run 都 FAIL（新變數或迴圈變數蓋掉同一個 scope 既有的名稱）；limits 檔寫死的計數（unannotated、disconnected）每次改 CTS 或換設計就 FAIL；植入錯誤卻 PASS，或 FAIL 的原因和植入無關；checker 的 FAIL 訊息像結果不對、其實是工具當掉；新 checker 寫完要請沒寫它的 agent 做漏洞審查。附已知的 checker 漏洞類型表（工具靜默略過、只證明設定被讀到沒證明生效、綁死 step 名稱、比對的對象是空的、NaN 被比較吞掉、測試被縮水或跳過仍 PASS、只比最終結果讓中間的介面錯誤互相掩蓋、產生器的公式沒有獨立驗證（例如由量測 JSON 產生的 .lib）、暫用別的設計的 golden 誤差（每個設計至少 4 個樣本）等），新 checker 要逐條對照。Use when writing or changing a checker or testbench, maintaining golden results and their tolerances, or qualifying a checker with bug injection.
---

# Checker 設計、golden 與 testbench qualification

通用方法；各領域的具體 checker 放在對應 skill（例如 DRC baseline 在 `drc-signoff`）。本 repo 實例：`signoff/scripts/check_signoff.py`、`signoff/limits/*.toml`、`signoff/golden/*/README.md`、`dv/scripts/dvlib.py`、`signoff/eqy/run_eqy.py`、`pnr/soc_top/check_soc.py`、`*/neg_*.py`。

名詞：**checker** = 判 PASS／FAIL 的程式或規則；**golden** = 確認過正確的一次 run 的完整 metrics，之後逐項比對；**negative test（bug injection）** = 故意植入錯誤，確認 checker 真的 FAIL；**testbench qualification** = 植入錯誤後被抓到的比例。

## 規則（已驗證）

規則 11、12 例外：它們是流程回顧後使用者決定的提早檢查（ADR-0020），成本與省下的時間是從 commit 時間推算，不是實驗結果（`docs/notes/problem_review/review_skills.md` 1.3 的說明）。

1. **只認明確 PASS**：少一個 metric、少一張表、表被截斷、工具沒跑完，都是 FAIL（Phase 2 獨立審查：截斷的 disconnected pin 表原本判 PASS）。
2. **型別要嚴格**：`false` 不能冒充 0；slack 是 inf 或極大值（例如 1e30，代表沒有 constraint 的路徑）要 FAIL → `[corners] slack_max`。
3. **來源追溯**（`project-plan.md` §7.2）：
   - harden 的開始與結束都跑 `signoff/scripts/provenance.py`：工作目錄必須已全部 commit（含未追蹤檔）、submodule 在記錄的 commit、LibreLane 與 PDK 是 `env/versions.mk` 釘的版本；結束時 HEAD 不變，且 `resolved.json` 實際用的 LibreLane 版本與 PDK 也對。工作目錄不乾淨時 flow 照跑，但整體判 FAIL。
   - harden 把**整體**結果（PASS／FAIL）寫進 `<run>_signoff/result.txt`；後續步驟（`run_guard.py` 管的下游步驟：soc_top、PicoRV32 與 Caravel wrapper 的 EQY、gate-level 模擬、它們的 negative test、`neg_pnr.py`、max power pattern 的 IR；目前的清單以 `signoff/scripts/neg_run_guard.py` 的 `STEPS` 為準）只認這個檔案是 `harden-<x>: PASS`。只查其中一份 checker 輸出（例如 `signoff.txt`）不夠：soc 專用檢查或輸入一致性 FAIL 的 run 仍會被拿去用。
   - 比對 run 實際用的設定（`resolved.json`：`cpu_params.py --resolved`、`check_inputs.py --resolved`）。
   - **追溯範圍要涵蓋實際執行的程式與資料**：LibreLane 在 nix-shell 裡跑的是 clone 的原始碼，signoff SDC 也 `source` clone 裡的 `base.sdc`；只比 clone 的 commit 時，clone 裡改過的檔案不會被發現（Phase 3 獨立審查實際試過）。Phase 4 已加：clone 的 `git status --porcelain` 為空、PDK 6 個目錄的內容摘要、`resolved.json` 的 PDK 路徑都在檢查範圍內。做法與陷阱在 `flow-regression-reproducibility`。
   - **下游也要確認 run 是這個 commit 產生的**：`provenance.json` 的 `repo_head` 必須等於目前的 `HEAD`。只看 `result.txt` 時，改了 RTL 後單獨跑 `make eqy-soc` 仍會用舊 netlist 而 PASS。Phase 4 已加 `signoff/scripts/run_guard.py` 與 `neg_run_guard.py`。
4. **「不是 0」的計數要寫出組成**並固定下來：Phase 2 unannotated 114 = 35 PCPI port + 41 tie HI + 38 clkload；soc_top = clkload + 32 個 `sram0/dout1` + 未用的 tie 輸出（soc_explore4：92 + 32 + 11）。
   - **逐項分類，會隨 layout 變的類別不寫死總數**（已驗證 4 次，每次都讓 harden FAIL、要人工重新計數：Phase 4 第 5 次 harden 上限寫「剛好 134」、實際 133，`docs/phase_exit/phase4.md` 第 100 行；Phase 5 Hazard3 的上限抄 PicoRV32 的 133、實際 125，本檔經驗紀錄 2026-10-07；ADR-0016 改 CTS 後兩個 CPU 變成 118／126，`docs/decisions/0016-cts-no-macro-latency-balancing.md` 第 52 行。`review_p4_5.md` R5）：
     - checker 把每一個列出來、依組成分類（CTS dummy load、macro 沒用的輸出、tie cell 沒用的另一個輸出、沒用的 port），不屬於任何已知類別的就 FAIL。
     - 由 RTL 與 DEF 範本決定的類別（沒用的 port、`sram0/dout1`）可以寫死數量；會隨 layout 變的類別（CTS dummy load）不寫死，改和同一個 run 的 netlist 裡實際的數量比（例如數 `clkload*` instance）。
     - 換設計或換 core 後，組成用新 run 重新計數，不能抄別的設計的數字（`core-migration-hazard3` 規則 22；`review_skills.md` R18）。
     - 為什麼：寫死總數時，每次改 CTS 或換設計都會 false fail（設計沒問題卻 FAIL）；真正多出來的一個未知 driver，反而被「照新 run 重新數一次、更新上限」這個步驟蓋過去。
     - 自動檢查：沒有。`check_signoff.py` 目前仍比 limits 檔的總數（`timing__unannotated_net__count`、`design__disconnected_pin__count`；放寬清單 V07），組成只寫在 limits 檔的註解裡；disconnected pin 在 wrapper 另由 `check_soc.py` 逐支核對是 wrapper 頂層沒用到的 port，unannotated 沒有逐項核對。照 ADR-0020 決定 2、ADR-0021 決定 3，下一個專案開始時改成逐項分類的 checker，並加植入錯誤（多一個未知類別的 driver；dummy load 數改變但總數湊成一樣）。
5. **golden**：逐項比對全部 metrics（key 集合也要相同）。不可重現的那一步（多執行緒 detailed routing）之後算出來的數字，依下一點分類後才給誤差：隨繞線微小變動的連續量（slack、skew、線長、via、功耗、IR）給很小的誤差，約 run 之間實際差異的 30–200 倍；count／area 一律不給誤差（`check_signoff.py` 會拒絕這種設定）。至少重跑一次確認可重現性，但一次相同不代表可重現；新設計照規則 11，至少 4 個樣本。
   - **不可重現的步驟也會改變數量時**（Phase 5 Hazard3，ADR-0015）：第 41 步的 global routing 偶發不同（同一份輸入 27 次裡 5 次），detailed routing 也會讓繞線後的 antenna 修補多一輪、多插 diode，cell 數、diode 數、面積跟著變，「count／area 不給誤差」幾乎每次 FAIL。做法：
     - 先逐步比對 DEF 與 log 找到分歧的那一步，再把那一步單獨重跑幾次量頻率，確認是隨機而不是設定造成的；
     - 收集足夠的樣本：除了完整 harden，也可以拿分歧步驟重跑出來的不同結果，接著跑完後面的步驟；
     - 數量與面積放在另一個表（`[golden_layout_tolerance]`），連續量仍在原表；違規、錯誤類的計數與 `[equal]` 的 key 一律不給誤差，由 checker 拒絕（`VIOLATION_WORDS`）；
     - 雜訊大時，誤差用實際最大差異的約 5 倍，不用 30–200 倍（30 倍會讓 slack 誤差到 1.9 ns，等於不比）；
     - 每輪、每個 warning 這類可能只出現在一邊的 key，列進 `[golden_optional]`，只限 `__iter:` 與 `flow__warnings__count:<id>`；
     - 用 negative test 證明誤差邊界與拒絕規則都有效（`neg_pnr.py` P50、P51），並寫明 golden 抓不到「所有 metric 都只動在誤差內」的改變。
   - **族群要依「哪一步產生的」來分，不能只看「到目前有沒有變過」**：不可重現那一步（detailed routing）算出來的每個 metric 都先分類——最終 signoff 數字（`route__drc_errors`）完全相同；中間過程數字（`route__drc_errors__iter:*`，繞線器各輪剩下的 DRC 數）給誤差。Phase 4 的教訓：Phase 2 的 5 次 run 與 Phase 4 regress 1 這組都沒變，於是被列為「必須完全相同」；regress 2 才變（11 → 14），整個 regression FAIL 一次（約 30 分鐘後才 FAIL，重跑又要 2 小時）。中間過程數字給的誤差要寫明它其實等於不比（例如 ±100，高於看過的所有值），並用 negative test 證明最終數字仍被保護（`neg_pnr.py` P31）。
6. **更新 golden**：先確認所有 limits 與自寫 checker PASS → 逐項說明與舊 golden 的差異 → 複製並記 sha256 → 再跑一次確認新 golden PASS。golden 比對本身的 negative test：P12（instance 數 −10%）、P31（最終 DRC 數 +1、中間輪「誤差 + 1」都 FAIL，+3 PASS；誤差從 limits 檔讀）、P50（layout 誤差的邊界、碰到違規計數的 pattern）、P51（可選 key、一般 key 缺少、碰到 corner key 的 pattern）。
7. **negative test 設計**：
   - 每個 checker 至少一個真錯誤，加一個 positive test（沒植入時 PASS）。
   - 植入點必須只命中一處；命中 0 或多處時，negative test 本身 FAIL（`edit()` 的寫法見 `neg_eqy.py`）。
   - 必須在**預期的** checker、以**預期的原因** FAIL；在別處 FAIL（缺檔、工具錯誤）不算抓到（`project-plan.md` §7.3）。
   - **先確認植入真的改變了結果**，再看 checker（見下表 P05、P13）。最直接的確認方式：植入後用同一個工具印出被改的那一項（例如 `report_checks -to <port>` 變成 `No paths found`）。
   - **「刪除／unset」不等於「從來沒有」**：要模擬「漏寫 constraint」或「漏接線」，就產生一份真的少了那一行的輸入，不要用工具的 unset／remove 指令（P13：OpenSTA `unset_output_delay` 之後 check_setup 仍當作有設）。
   - **說明與程式要一致**：每個案例在程式裡逐一檢查它聲稱涵蓋的每個 checker；docstring／README 寫了、程式沒測的，等於沒有（P10 原本只測 KLayout，說明卻寫也測 Magic）。
   - **假 run（fake run）要先有 positive control**：沒植入時假 run 必須整體 PASS。否則某一列（例如缺 STA 目錄的 `sta_setup`）永遠 FAIL，「整體 FAIL」這項檢查就沒有作用。每個案例要檢查：FAIL 的只有被植入的那一列，而且整體判 FAIL（Phase 3 的 P08–P10、P14、P15 沒做到）。
   - **確認 FAIL 的位置和植入有關**：FAIL 訊息裡要有被植入的 instance、net 或座標，不能只看「有 FAIL」。
   - **檢查抓到它的是哪個機制**：同一個錯誤可能被別的機制碰巧抓到（例如 EQY 在把電路切成 partition 的步驟就拒絕，沒有走到證明）。案例要測哪個機制，就檢查 FAIL 的原因來自那個機制（`neg_eqy.py REQUIRE`）；做不出只由該機制抓到的錯誤時，要在文件寫明「沒有案例證明 X」，不要寫成已涵蓋（Phase 5 獨立審查）。
   - **守門條件本身要有測試**：checker 或重試規則的每一道條件（例如「只在 usage=65534 時重試」），都要有一個情境在條件拿掉時 FAIL。驗證方法：把條件刪掉，跑一次測試，確認真的 FAIL（Phase 5：`test-flow-retry` 原本兩道條件都沒測到）。
   - **位置檢查本身要能分出不同案例**：對每一對植入點不同的案例，A 的 FAIL 名稱不能全部落在 B 的「附近」範圍內，否則範圍大到什麼都接受（`neg_eqy.py` 的交叉檢查；Phase 4 審查前 bus pin 整條一起算，`din5_stuck0` 的範圍含全部 32 個 bit）。
   - **檢查要看全部問題，不要只看第一個**：checker 只印第一個問題時，案例能 PASS 可能只是報告順序剛好（P23：29 ns 時 ss corner 的 min pulse width 也 FAIL，只因 nom_tt 排第一才看到 min_period；P21 只看第一個不符的違規的規則）。讓 checker 印出全部問題的種類，檢查「種類集合」。
   - **比對粒度要分得出同類的新錯誤**：只比「種類」（例如 DRC 規則名）時，同種類多一個錯誤會漏掉；改比位置或逐筆比對（`drc-signoff` 規則 2）。
   - **修 checker 漏洞時，negative test 要證明「舊 checker 會漏、新 checker 會抓」**：植入的錯誤若連舊 checker 也抓得到，就沒有測到漏洞。P21 第一版植入的 li1 細線被 Magic 報成 SRAM 單獨時沒有的規則（`li.c1`），舊的「只比種類」也會 FAIL；改成 SRAM 單獨時也有的 `li.3` 才是在測位置比對。同理，P07 改成兩個 net 各 11 mV：各自低於 20 mV、合計超過，舊的單 net 檢查會漏。
   - **一個植入會牽動不只一列時，明列哪幾列、為什麼**：假 run 中把 `sram0` 在 DEF 移 10 µm，`placement` 與 `magic_drc`（以 DEF 位置當比對原點）都 FAIL；`sram0` 改名，`macro` 與 `port1_tieoff`（找不到 `sram0`）都 FAIL。檢查寫成「FAIL 的列剛好是這幾列」，不要放寬成「至少這一列 FAIL」。
   - **新的測試（firmware、directed test）也要被植入錯誤證明有效**：在 netlist 植入它要補的錯誤，只跑新測試（`dv-directed-tests` 規則 6）。
   - **自寫 checker 取代了工具原本的檢查時**（例如 `ERROR_ON_MAGIC_DRC=false` 改由 `check_soc.py magic_drc` 檢查），這支自寫 checker 必須有自己的植入錯誤。
   - **借用另一個工具的植入方式時，先確認新工具讀得進植入後的檔案**：同一份植入錯誤的 netlist，Yosys（EQY）接受、Icarus（GL 模擬）因為 wire 先使用後宣告而編譯失敗（`neg_gl_soc.py csb0_inverted` 第一版）。編譯失敗不算抓到，所以 checker 正確判 FAIL，但這個案例等於沒測。
   - checker 自己也包括「來源追溯」這類流程檢查：`neg_provenance.py` 在本機 clone 上植入未提交檔案、版本或內容不符、經 symlink 讀範圍外的檔等狀況，另有 positive test（案例清單在該腳本開頭的說明）。
8. **獨立審查**：讓沒寫 checker 的 agent 另外想植入錯誤；修正後把舊案例全部重跑（Phase 1 兩輪、Phase 2 一輪）。
9. **上一階段留下的項目要列入本階段的檢查清單**：exit review 的「留到下一階段」與「已知限制」逐條帶進下一階段的 exit 表（Phase 2 延到 Phase 3 的來源追溯，到 Phase 3 收尾才發現還沒做）。
10. **跑完整條流程的 target（`make phase<N>`）要在乾淨 checkout 從頭跑到底才算驗證過**：
   - 中途停下的 run 只驗證了停下之前的 target。之後在 main worktree（平常開發用的那份 repo）逐一補跑的 target 不算，因為 main worktree 有忽略版控的 build 產出（`fw/build/` 等）。
   - 每個 target 都要在 Makefile 宣告它需要的建置步驟。例如 `gl-soc` 需要 `fw`：第一次 `make phase3` 停在 harden-soc，沒有發現這個缺漏；第二次在乾淨 checkout 跑到 gl-soc，12/13 支測試報找不到 firmware。
   - 檢查方式：`cat .gitignore`，對每個被忽略的目錄 grep 有哪些腳本讀它，確認對應的 target 有宣告建置步驟。
   - 新寫的 negative test 腳本要先單獨跑完一次，再加進 phase target（`neg_gl_soc.py` 沒跑過就加進 `make phase3`，第三次 `make phase3` 才發現上面那個編譯錯誤）。
11. **golden 的誤差至少用 4 個樣本定，並記下樣本數**（使用者決定的提早檢查 E2，效益為推算；流程回顧 ADR-0020；流程文件 4.6。比規則 5 的「至少重跑一次」嚴格，新設計照這條）。
   - 為什麼：Phase 2 用 3 次 run 定的誤差，Phase 4 regress 第 2 次就 FAIL（繞線器中間各輪的 DRC 數，規則 5 第二點）；Phase 5 Hazard3 的 golden 比對又 FAIL（ADR-0015）；PicoRV32 暫用 Hazard3 的誤差被獨立審查抓到，又補樣本、多跑兩輪 regress（`docs/phase_exit/phase4.md`、`phase5.md`）。新的不可重現來源（Phase 5 的 global routing）要等設計變大才出現，所以每個設計都要各自量。
   - 做什麼：每個設計第一次建 golden 時，同一個設定至少 4 個樣本，其中一次在乾淨 checkout；樣本可以是完整 harden，或把不可重現的那一步單獨重跑後，再接著跑完後面的步驟（規則 5 第一點）。依每一類 metric 的實際差異定誤差；golden 的 README 寫明每一類用了幾個樣本、哪幾個 run。不能暫用別的設計的誤差；量不出大小時（本 repo wrapper 三組比較每個值都完全相同）寫明理由並記進放寬清單（ADR-0019 決定 26）。
   - 通過條件：樣本彼此都在誤差內。
   - 成本：每個設計多 2–3 次 harden（本 repo 每次約 15–40 分鐘）。
   - 自動檢查：沒有（「README 寫了樣本數、樣本 ≥ 4」可以做成 `check_signoff.py` 的檢查，下一個專案開始時做）。
12. **新 checker 寫完就做獨立漏洞審查，不要等 Phase 收尾**（使用者決定的提早檢查 E3，效益為推算；流程回顧 ADR-0020；流程文件 4.8；規則 8 的時間點）。
   - 為什麼：每個 Phase 收尾的審查都找到一批漏洞，修完要整套 regression 重跑：Phase 4 有 10 個、Phase 3.5 有 12 個、Phase 5 有 8 個、Phase 6 有 7 個、Phase 7 有 8 個加 1 個缺口（各 Phase exit review 的「獨立審查」；ADR-0019 決定 26）。Phase 7 那次三條 regression 要重跑，wrapper 一條約 6 小時；回顧推算每批審查約 1–2 小時 agent 時間。
   - 做什麼：每支新的或大改的 checker，寫完、第一次正式 harden 或放進 regression 之前，請一個沒寫它的 agent 找「該 FAIL 卻 PASS」的漏洞：做植入錯誤的實驗加對照組，不能只讀程式；逐條對照下面的漏洞類型表。審查紀錄（日期、找到什麼、怎麼修、對應的 negative test）寫在該 checker 的 README 或 ADR。Phase 收尾時只審最後改過的 checker（`phase-exit-review` 規則 10）。
   - 通過條件：每支新 checker 有審查紀錄與 negative test；收尾審查沒有新的高、中嚴重度漏洞。
   - 自動檢查：沒有（審查要 agent 做實驗）；「每支 checker 都有審查紀錄」可以做成 checker，下一個專案開始時做。
13. **改 checker 時，新變數（包括迴圈變數）不能和同一個 scope 裡既有的名稱重複；scope 指函式內或模組層，兩者都一樣**（已驗證，出現三次）：判 PASS／FAIL 的長函式或腳本裡，後面的列常用前面算好的變數。Python 的 `for` 迴圈變數在迴圈結束後仍留在同一個 scope，`if` 區塊也不會隔開名稱，所以巢狀區塊裡的迴圈一樣會蓋掉外面的值。
   - Phase 6：修審查漏洞時把 `files`（RTL 檔案清單）改成 view 檔名的字典，`check_inputs.py` 的 `resolved` 列對每個 run 都 FAIL（Phase 6 exit review「本階段找到並修正的 checker 問題」6）。
   - Phase 7：修 H8 時新加 `defines`（`` `define `` 巨集的值），蓋掉同一個函式後面 `resolved` 列要比的 `VERILOG_DEFINES`，同樣每個 run 都 FAIL（Phase 7 exit review）。
   - Phase 7（`cbf2c5e`，2026-10-13）：`check_soc.py` 的 wrapper `ir_sources` 檢查用 `for x, y, size, _ in pts` 走過電壓源位置，蓋掉前面從 DEF 讀到的 `sram0` 原點 `x, y`；`magic_drc` 拿最後一個電壓源的座標當 SRAM 外框，`p7_harden5` 的 5,572,955 個 SRAM 內違規全被判成在 SRAM 範圍外（FAIL，沒有誤判 PASS）。commit 訊息寫「module level」，實際兩處都在 `main()` 裡（`git show cbf2c5e^:pnr/soc_top/check_soc.py` 第 494 行 `def main`、第 530 行讀原點、第 552 行迴圈），是同一個函式裡的巢狀迴圈；改名 `px, py` 後 0 個在範圍外。
   - 怎麼做：加變數或迴圈前，在同一個函式（在模組層就整個檔案的模組層）grep 名稱；改完在實際的 run 上跑 positive control（`neg_pnr.py` P00、C00 會跑 `check_inputs.py --resolved`），再開 regression（`phase-exit-review` 規則 2）。
   - 自動檢查：沒有。`make py-check`（`scripts/check_py_names.py`）只抓未定義的名稱，看不出變數撞名；目前的防線是 P00／C00 這類「在實際的 run 上必須 PASS」的 positive control（Phase 7 `defines` 是它抓到的），以及 checker 判 FAIL 後人去查（`cbf2c5e`）。照 ADR-0020 決定 2、ADR-0021 決定 3，下一個專案開始時在 `py-check` 加 lint（例如 pylint 的 `redefined-outer-name`，先試誤報率），並用 `cbf2c5e` 之前的寫法當植入錯誤（`review_p6_7.md` 建議 3）。

## 已知的 checker 漏洞類型（新 checker 要逐條對照）

| 類型 | 例子 | 出處 |
|---|---|---|
| 工具靜默略過某些情況 | EQY：gate 端某 bit 是常數時只記一行 `found constant gate bit` 就不證明；輸出被植入 stuck-at-0（固定為 0）時，15136 個 partition 全部證明通過 | `neg_eqy.py wdata3_stuck0`，`signoff/eqy/README.md` |
| 工具的檢查範圍比名稱小 | PSM（power grid checker）只查電源網路自己的 shape 連不連通，不查 macro 電源 pin；LibreLane 的 filtered unannotated 只認頂層 port；`check_soc.py sram_lib` 只認 `Reading cell library` 一種 log 訊息、只比路徑結尾，經 `EXTRA_LIBS` 多讀一份 SRAM .lib 看不到，`check_inputs.py` 也只看 MACROS 不看 `LIB`／`EXTRA_LIBS` | P05；`filter_unannotated.py` 70–85 行；Phase 3.5 審查，Phase 5 開頭修：收集三種讀 .lib 的訊息、打開檔案看誰定義了 macro cell、解開 symlink 比完整路徑（P33–P36） |
| 植入沒有生效 | `PDN_CONNECT_MACROS_TO_GRID=false` 產生的電源網路與原本逐字相同；`unset_output_delay` 不加 `-clock` 什麼都沒刪，加了 `-clock` 之後路徑消失、但 check_setup 仍當作有 output delay | P05 第一版、P13 第一、二版、N6 第一版（要替換的字串在新 .lib 裡已不存在）、P17 Phase 3.5 版（檔案在讀之前就被 `open(f, "w")` 清空；植入點檢查 `edit_once` 因此出現錯誤，而不是什麼都沒改就判 PASS） |
| 說明與程式不符 | P10 的說明寫「KLayout 與 Magic DRC 都會 FAIL」，程式只檢查 KLayout | P10 第一版 |
| 比對的文字被輸出格式拆開 | LibreLane console 自動換行，`GRT-0229 ... usage=65534` 分在兩行，單行 regex 永遠對不到，重試永遠不會發生 | `pnr/librelane_flow.sh` 第一版；用模擬的 nix-shell 測 7 種情境（`make test-flow-retry`） |
| checker 綁死 step 名稱 | `review_criteria.py` 用 `OpenROAD.CTS` 找 CTS 的目錄，config 用 `substituting_steps` 換掉 CTS step 後就找不到；GRT-0229 的重試只認 `RepairDesignPostGRT`，flow 多開的 `ResizerTimingPostGRT` 出同一個錯誤時不重試。flow 換掉或多開 step 時，要 grep 所有用到 step 名稱的 checker 與腳本 | ADR-0016（`review_criteria.py` 改成依 `substituting_steps` 找）；`pnr/librelane_flow.sh` 與 `make test-flow-retry`（Phase 5） |
| 重試留下的中止目錄頂替完成的那次 | GRT-0229 重試後，同一個 step 有兩個目錄（中止的沒有 `state_out.json`）。`review_criteria.py` 的 uncertainty 檢查原本「任一個目錄」的 log 有那一行就 PASS：中止那次的 log 頂替了完成那次，P49 在這種 run 上沒被抓到。看 step 目錄的 checker 只採計有 `state_out.json` 的目錄；negative test 要造出「中止的目錄有、完成的沒有」 | P55（Phase 5，`neg-pnr` PicoRV32 54/55） |
| 下游只查部分檢查結果 | `run_eqy.py`、`run_gl_soc.py` 只看 `signoff.txt`，不看 soc 專用檢查、輸入一致性 | Phase 3 收尾自查 |
| 工具快取了舊資料 | 換 LEF 後重跑 `CheckAntennas`，讀的仍是 ODB 裡的舊 antenna 資料；characterization 的模擬快取不確認上次 ngspice 成功，波形太短時讀取一律當成正確 | P06 第一版；Phase 3.5 審查，Phase 5 開頭修（N15） |
| 比對粒度太粗 | `check_soc.py magic_drc` 在 SRAM 範圍內只比規則種類，多一個同種類的錯誤照樣 PASS | Phase 3 獨立審查（假報告實驗） |
| 前處理把要檢查的東西抹掉 | EQY 的 `sat` strategy 先 `formalff -clk2ff`，所有 flip-flop 變成同一個隱含 clock；flip-flop 的 CLK 改接反相 clock，EQY 與「只比 cell 種類」的結構比對都 PASS | Phase 4 審查；`run_eqy.py` clock_sources、`neg_eqy.py flop_clk_inverted` |
| 只看「在不在」，不看大小或位置 | IR 電壓源只檢查點在 strap 上：大小改成 2000 µm（等於整條 strap 理想供電）或移到 strap 中間都 PASS；`char.json` 只檢查 PVT 名稱齊全，某個 PVT 的紀錄換成 tt 的資料照樣 PASS（hold arc 樂觀 0.4 ns） | Phase 4 審查；P27、P28；Phase 3.5 審查，Phase 5 開頭修（N9） |
| 總和允許負項 | `[max_sum]` VDD 19 mV + GND −15 mV = 4 mV 判 PASS | Phase 4 審查；P29 |
| 容許值套到不需要的類別 | DRC 位置比對的 100 nm 對 30 種規則都放寬，實際只有 2 種需要；li.3 看不到的面積從 0.9% 變 6.5% | Phase 4 審查；`check_soc.py DRC_POS_TOL_RULES` |
| 摘要列永遠 PASS | golden 比對的摘要列不扣掉不符的 key，236 列 FAIL 時仍印 `[PASS] golden 434 metrics: 429 identical` | Phase 4 文件審查；`check_signoff.py` |
| 路徑比對不解開 symlink | provenance 只比 PDK_ROOT 字串結尾：另一份同名版本目錄、或經 `~/.ciel/sky130A` symlink 讀範圍外的檔，都 PASS | Phase 4 審查；`neg_provenance.py resolved_other_install`、`resolved_symlink` |
| 只在結尾檢查一次 | `make regress` 只在最後讀 HEAD：中途 commit 時前段 target 跑的是舊 commit；`make -i regress` 讓 FAIL 的子 make 回 0 | Phase 4 審查；`neg_regress.py` |
| 追溯範圍比實際執行的程式小 | `provenance.py` 只比 LibreLane clone 的 commit，clone 裡改了 `base.sdc` 仍 PASS | Phase 3 獨立審查（實驗） |
| 下游不確認輸入來自哪個 commit | `run_eqy.py` 只看 `result.txt`，改 RTL 後單獨跑仍用舊 netlist | Phase 3 獨立審查（讀程式） |
| 測試環境本身就 FAIL | neg-pnr 的假 run 沒有 STA 目錄，`sta_setup` 永遠 FAIL，「整體 FAIL」這項檢查失效 | Phase 3 獨立審查（run.log） |
| 用到只有 main worktree 才有的檔案 | `make gl-soc` 讀 `fw/build/*.hex`，卻沒有宣告對 `fw` 的相依；main worktree 有舊的 build 產出，所以只在乾淨 checkout 才 FAIL | 第二次 `make phase3`（規則 10） |
| 植入方式只在一個工具驗證過 | `neg_eqy.edit()` 把 `wire` 宣告加在 module 最後：Yosys 接受，Icarus 報 `Check for declaration after use` | `neg_gl_soc.py csb0_inverted` 第一版 |
| 覆蓋不到的功能 | GL 模擬只看得到 firmware 用到的功能（`rdcycleh`、bus-error IRQ 漏掉） | Phase 2 限制 7；Phase 4 用 `counters`、`buserr` 補 |
| 工具報的名稱與植入點的名稱不同 | EQY 報合成 netlist 的名稱，最終 netlist 在 flip-flop 與 port 之間多了好幾級 buffer；只比植入的 instance 會誤判「不在植入點」 | Phase 4 `neg_eqy.py` 位置檢查（走過 buffer 鏈） |
| 檢查只看一半的量 | LibreLane 的 `ir__drop__worst` 只有 VDD；20 mV 的預算是 VDD 與 VSS 兩端 IR drop 的合計 | Phase 4 IR 研究 |
| 產生器的公式沒有獨立驗證 | `gen_char_lib.py` 由 `char.json` 產生 .lib：`--check` 只比「同一支程式的輸出」，公式寫錯時 .lib 與 JSON 照樣一致；N5–N8 的測試資料每格相同、又被下限蓋過，取最大與取最小弄反、少乘 1.6 都 PASS。要用不 import 產生器的獨立重算，或每格不同、高過下限的測試資料 | Phase 3.5 獨立審查；Phase 5 開頭修：`check_char_lib.py`，改壞公式的產生器 M1–M5 都要 FAIL（N12） |
| 檢查分不出 FAIL 的原因 | P17 只看 `char_lib` 列 FAIL：char 目錄多一個 `.DS_Store` 也 FAIL，這項檢查照樣通過；N8 檢查的 PVT 名稱一定出現在「expected exactly」那串清單裡 | Phase 3.5 獨立審查；Phase 5 開頭修：檢查訊息內容（P17 要 STALE 並指名檔案、N8 解析缺的是哪一個），沒有 positive control 的補上（P32） |
| 非有限的數值被比較吞掉 | `char.json` 的 setup 是 NaN 時，`max(下限, nan)` 默默變成下限；hold arc 寫出 `nan` 的 .lib 也被接受。用 `abs(v - want) > tol` 判斷「不符」時，NaN 永遠不算不符（Phase 6 修 H7 時自己踩到）：寫成 `not abs(v - want) <= tol` | Phase 3.5 獨立審查；Phase 5 開頭修（N11）；Phase 6 `check_char_lib.py power_problems`，C6；Phase 7 審查 H4：`max(drops, key=...)` 遇到 NaN 一律比較為假，NaN 排第二時被略過、判 PASS，排第一時才 FAIL（結果看順序）。取值時用 `math.isfinite` 擋下 |
| 失敗時留下新舊混合的輸出 | characterization 有一個 PVT 失敗、印 FAIL，`char.json` 已經寫入其他 PVT 的新結果，失敗的 PVT 留舊紀錄，之後照樣產生 5 份 .lib | Phase 3.5 獨立審查；Phase 5 開頭修：有失敗就不寫檔（N16） |
| 被測的模型本身太樂觀 | IR 用「所有 pin 形狀都是理想電源」，算出 0.3 mV，任何門檻都會 PASS | Phase 4 IR 研究（`pdn-ir-drop` 規則 10） |
| 只證明「設定被讀到」，沒證明「生效」 | `review_criteria.py` 的 uncertainty 檢查只找 SDC 印出的那一行：把 15 個 corner 報表裡的 uncertainty 全刪掉仍 PASS；setup／hold 的 0.25 又剛好等於 LibreLane 預設，單看數字分不出來。要從工具的結果核對實際套用的值 | Phase 5 獨立審查；`review_criteria.py uncertainty_applied`（50,670 條路徑逐條比對），P56 |
| 靠名稱辨識工具產生的結構 | `cts_macro_latency` 只認 `delaybuf_*` 這個 instance 名稱，改名 `clkdly_` 就 PASS；目錄只認沒有 `-1` 字尾的名稱，重複的 step 漏掉。改成結構判斷：`sram0/clk0` 上方只驅動下一級的 clock buffer 連續幾級（有做 latency 對齊 11、12 級，沒做 0 級）。注意 latency 對齊**不會**讓級數變多（對齊就是讓延遲相同），比級數分不出來 | Phase 5 獨立審查；`check_soc.py sram_clock_chain`，P58–P60 |
| 誤差表的保護不完整 | `[golden_layout_tolerance]` 的受保護字沒有 `floating`、`warning`：floating net 2 → 40 可以被放進誤差表；`[golden_optional]` 接受 `flow__warnings__count:*`，任何新種類的 warning 都會被略過 | Phase 5 獨立審查；`check_signoff.py VIOLATION_WORDS`，P50、P51 新增的子案例 |
| 強制機制的觸發條件比規則的範圍小 | Stop hook 只在看到 `criteria_review.txt` 時才要求 review：沒跑 `review_criteria.py` 的 `harden-core`，以及它當掉、沒有結果行時，都放行。觸發條件要用「每次 harden 一定會寫的檔案」（`result.txt`），並把「當掉」也當成要擋的情況 | Phase 5 獨立審查；`require_criteria_review.py`，`make test-review-hook` |
| 抓到的機制和案例宣稱的不同 | `reset_b_tied1` 寫「只有證明抓得到」，實際上 EQY 在切 partition 的步驟就因名稱衝突拒絕（0 個 partition），根本沒有證明。要檢查抓到它的原因；改用 tie cell 或繞過同步器，結果也一樣 | Phase 5 獨立審查；`neg_eqy.py REQUIRE`，`signoff/eqy/README.md` |
| 測試沒有測到守門條件本身 | `test-flow-retry` 11/11：把「只在 usage=65534 時重試」或「已完成的 step 不重試」任一條件拿掉，測試仍 11/11。每一道條件都要有一個「條件拿掉就 FAIL」的情境 | Phase 5 獨立審查；`make test-flow-retry` 的 `grtreal`、`grtdone`，拿掉條件後實際跑一次會 FAIL |
| 比對的對象是空的，checker 空過 | `check_soc.py magic_drc` 只檢查「SRAM 範圍內每個違規都在 SRAM 單獨的報告裡找得到」：最終 GDS 的 SRAM 是空的（LEF 沒有 `FOREIGN`），範圍內 0 個違規，PASS。LVS 把 SRAM 當 black box、KLayout DRC 也看不到。比對型的 checker 要同時要求被比對的集合夠大（這裡：範圍內至少是 SRAM 單獨的 50%），並直接檢查前提（`macro_gds`：最終 GDS 的 SRAM 等於 macro 的 GDS） | Phase 6；`check_soc.py DRC_IN_MIN_FRAC`、`macro_gds`，P67–P69 |
| 黑盒子看不到的一致性，沒有別處在比 | LVS 透過 LEF 看 macro（black box），view QA 只比 LEF、.lib、Verilog、SPICE 的名稱與方向：LEF 兩支腳位的 RECT 對調、LEF 沒有 OBS，所有 checker 都 PASS，做出來的晶片會接錯 bit。一個工具用抽象圖代替實體時，要另外比抽象圖與實體（腳位文字落在 RECT 內、金屬在 OBS 內） | Phase 6 獨立審查 H1、H2；`check_macro_views.py pinpos`／`obs`，Q14–Q17、P71、P72 |
| 指紋不精確，卻自稱「內容相同」 | `check_macro_gds.py` 的指紋只算每層圖形數與外框座標的加權和：兩個文字互換、同外框的多邊形、兩個框反向各移 10 nm 都 PASS。比對內容要雜湊完整描述（每個頂點、文字字串） | Phase 6 獨立審查 H6；`gds_cells.py`，P75、P76 |
| 只讀表格的第一個數字 | view QA 與 `check_char_lib.py` 的 power 表只取 `values("` 後的第一個數字：`values("12.18, 1.0e11")`、前面有 `index_1` 的表都 PASS。讀整個表，或要求 scalar 表只有一個數字 | Phase 6 獨立審查 H7；Q19、Q20、neg-openram C6、C7 |
| 把工具的特例清單抄一份寫死 | `macro_klayout_drc.py` 只防 SRAM 的名稱排除，deck 另外依名稱排除 IO cell、放寬 s8 cell 的 m1.4：同一個 nwell.6 錯誤，cell 取 IO 的名稱就 0 個。從工具自己的設定檔解析清單，並在解析不到時 FAIL | Phase 6 獨立審查 H5；`deck_patterns()`，K7、K8 |
| 產生器的輸入沒有來源追溯 | .lib 範本（`_TT_template.lib`）與 OpenRAM 的 TT .lib 不在 `macro_source` 的清單裡，`gen_char_lib --check` 只比「同一個範本的輸出」：範本電容改成 1/10 再重新產生，所有列都 PASS。產生鏈上的每一個中間檔都要對回它的來源 | Phase 6 獨立審查 H3；`check_inputs.py lib_template`，P73、P74 |
| 只檢查版本字串 | xPack 檢查只比 `-dumpversion`：一支只會 `echo 15.2.0` 的腳本 PASS。要核對產品本身，例如 `--version` 寫 xPack，而且找得到 newlib 的 `libc.a` | Phase 5 獨立審查；`env/check_env.sh`，`neg-regress xpack_fake` |
| 暫用另一個設計的數字 | PicoRV32 的 layout 誤差暫用 Hazard3 量到的值：diode +54、standard cell +69 這種真實改變也 PASS。沒有這顆設計自己量到的差異就不給誤差，量到再訂 | Phase 5 獨立審查；`signoff/limits/soc_top.toml`，P50（沒有誤差項時 +1 就 FAIL） |
| 比對到資料，不是指令；只看第一個指令 | 全域守門 hook 用 regex 找 `make harden`，把 heredoc 裡「README 提到 `make harden-soc`」也當成要開 harden 而擋下。比對前先拿掉 heredoc 內容與引號內字串。同一個 hook 在 `git push origin main && git push gitlab main` 只看第一個 push，誤報「gitlab 還沒推」：一行裡的每一個指令都要看 | 2026-10-08；`~/.claude/hooks/guard-bash.py shell_text()`，`test_guard_bash.py` |
| checker 的某個模式只有植入錯誤的案例在跑 | `check_inputs.py --resolved` 只被 P20、P36、P39、P42 呼叫，四個都是「植入後必須 FAIL」。`37c99b4` 修審查漏洞時重複使用了變數名稱 `files`（RTL 檔案清單被 view 檔名的字典蓋掉），`resolved` 列對每個 run 都 FAIL，四個案例照樣「抓到」。直到乾淨 worktree regress 的 harden 才露出來，兩輪各浪費一次 harden。checker 的每個模式（每組參數）都要有一個沒植入時必須 PASS 的對照；改 checker 之後先跑對照，不要只跑植入錯誤的案例 | Phase 6 結案；P00 加上 `check_inputs.py --resolved` 必須 PASS，用修正前的 checker 實際跑過，P00 FAIL |
| 核准紀錄只存在被檢查的檔案裡，自己算得出來 | `check_pin_plan.py` 的核准：規劃改了以後，用 `--digest` 重算 `plan_sha256` 填回 `[approval]` 就 PASS，不需要使用者；ADR 只要找得到引文，引文「可以」兩個字在 ADR 裡出現 4 次。核准的版本（digest）要記在另一份會進 diff 的文件（ADR 的同一行有原話、日期與 digest），改核准一定會留下痕跡 | Phase 7 審查 H1；`check_pin_plan.py approval`，`neg-pin-plan` A4 |
| 檢查只看結果，不看輸入是怎麼產生的 | IR 用 max power pattern 檢查：VCD 用別的週期錄（時間 × 1.1）、已被 run guard 拒絕的 run、只給三個 window 中 IR 最小的一個，全部 PASS（正式結果離上限只剩 0.44 mV）。檢查前先核對輸入：產生條件（從 VCD 量 clock 週期 = `CLOCK_PERIOD`）、來源（run guard）、完整性（window 齊全） | Phase 7 審查 H2、H3；`ir_pattern.check_inputs()`，`make neg-ir-soc`／`neg-ir-caravel` 的 `period`、`one_window`，`neg-run-guard` 的 IR 兩支 |
| 例外欄位接受任何字串 | `[max_sum]` 的 `judged_by = "make no-such-target"` 讓一個上限變成 INFO，不檢查那個 target 存不存在、有沒有在 regression 裡跑。把上限交給別的 checker 時，要確認那個 checker 確實存在、會被執行 | Phase 7 審查 H5；`check_signoff.py judged_by_error()`，P81 |
| 時間比較丟掉時區 | `check_precheck.py` 把 `project.json` 的時間戳 `replace(tzinfo=None)` 後比，+08:00 的時間戳在結果目錄開始前寫入也 PASS。先換成同一個時區（UTC）再比，沒有時區就 FAIL | Phase 7 審查 H6；`neg-precheck` `results_after_tz`、`no_tz` |
| 非正式的結果被當成正式結果 | `check_precheck.py` 遇到 `verification: true`（沒過 run guard）或根本沒有來源檔的專案，仍印 `precheck: PASS`。預設模式要求正式來源；非正式的檢查要另給旗標，結論也要標明不列入 signoff 證據 | Phase 7 審查 H7；`--verification`，`neg-precheck` `verification_source`、`no_source`、`source_gds`、`verification_flag` |
| 向量只檢查一個 bit | `check_inputs.py inout_dont_touch` 只看 `analog_io[0]`：`RSZ_DONT_TOUCH_RX = ^analog_io\[0\]$` 也 PASS，harden 卻會在 `analog_io[9]` 中止（RSZ-0074）。範圍要展開到每個 bit（巨集從 `` `define `` 取值，算不出來就 FAIL） | Phase 7 審查 H8；P79 `bit0` |
| 例外只放寬、不要求 | `check_soc.py max_slew` 允許 Caravel 輸入腳位超過上限到「外部 transition + 0.05 ns」，但不要求它出現：driving cell 蓋掉 `set_input_transition` 時腳位 slew 變成約 0.02 ns，報表裡消失，照樣 PASS。放寬的例外要反過來確認被例外的東西確實存在、數值符合依據 | Phase 7 文件核對（`timing-constraints-sdc` 規則 14 的對策沒做）；`max_slew` 的反向檢查，C80d |
| 測試被縮水或跳過，仍判 PASS | RTL testbench 的 self-checking 測試只看 firmware 最後寫的 PASS：Phase 1 第 1 輪獨立審查植入的錯誤裡，firmware 測試主體被跳過仍印 PASS；第 2 輪 memtest 刪掉 March C− 階段、Boot ROM march 少測最後一個 word，`make regress-rtl` 兩個模擬器都 PASS。每支測試宣告它要做的動作，由 checker 計數比對（每個 SRAM word 的讀寫次數、UART stall 次數、PASS 不能早於 cycle 下限）。cycle 下限抓不到「刪掉一段」：image 變小、測試區變大，總時間反而變長，要靠存取次數。精確計數跟 CPU 綁在一起，換 core 要重新量（`core-migration-hazard3` 規則 10） | `docs/phase_exit/phase1.md` 第 18–23 行；`dv/README.md` 第 68–78 行（`coverage`、`min_cycles`）、第 145–147 行（M01、B01、B02）；`review_p0_35.md` 建議 3 |
| 只比最終結果，中間的介面錯誤互相掩蓋 | Phase 1 第 2 輪：SRAM 一筆交易存取兩次、IRQ 線晚放、UART 除數 reset 值錯（Boot ROM 之後又寫一次，輸出照樣正確）、先寫 DONE 再寫 SIG，最終的 UART 與 GPIO 輸出都對，regress 都 PASS。macro 與周邊的介面要有腳位層的協定 monitor（每筆交易只存取一次、handshake 時序、reset 值）；兩個錯誤可能互相蓋掉時，在中間狀態就比（`uart_div` 在 reset 釋放時就比除數，不等 UART 輸出） | `docs/phase_exit/phase1.md` 第 23 行；`dv/README.md` 第 15–17 行（`sram_port`、`irq_line`、`uart_div`）、第 148 行（B03）；`review_p0_35.md` 建議 3 |
| checker 的訊息分不出工具當掉與結果不對 | Phase 7 結案：本機 KLayout 0.30.7 跑 precheck deck 當掉（log 有 `ERROR: Signal number: 11`），`neg-precheck` 印的卻是 `the reference's klayout_feol report has no item`，讀起來像比對結果不對，人會先去查設計；那次 Hazard3 的第二次執行作廢。包外部工具的 checker，報表沒有項目或缺檔時，先掃同一步的 log 有沒有當掉的訊號（`Signal number`、`Segmentation fault`、`Killed`），有就印「工具當掉（見 <log>）」並 FAIL；negative test 植入一份含 `Signal number: 11` 的 log 與空報表，檢查訊息有指出當掉。KLayout 為什麼當掉是推測（記憶體壓力，只出現一次），留在 `tapeout-precheck-caravel` 經驗紀錄。自動檢查：沒有（`neg_precheck.py` 第 104 行與 `check_precheck.py` 都沒有當掉偵測；照 ADR-0020 決定 2、ADR-0021 決定 3，下一個專案做成 checker） | `docs/phase_exit/phase7.md` 第 34 行；`runs/p7close2_h3_neg_precheck_ref_klayout_sig11.log` 第 1193 行（不進版控）；`review_p6_7.md` 建議 8 |

## 用完後

1. 新的 checker 漏洞或 golden 現象加進「經驗紀錄」，原因標明已驗證／推測。
2. 同一類型出現第二次或已用實驗確認，就搬進上面的表。
3. 確認引用的檔案仍存在。這次若「該用沒用」，修 description。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | arvinsa-rtl-gds neg-eqy | `wdata3_stuck0` 植入後 EQY 仍 `DONE (PASS)` | 已驗證：EQY 把對應到常數的 bit 視為已對應、不證明 | `run_eqy.py` 出現 `found constant` 即 FAIL；正向 run 為 0 筆 | `runs/neg_eqy_picorv32_core/wdata3_stuck0/eqy/summary.json` |
| 2026-10-03 | neg-pnr P05 | 拿掉 macro 電源設定後 PowerGridViolations 仍 PASS | 已驗證：電源網路 DEF 逐字相同 | 改成刪 SRAM 電源環上的 via → LVS FAIL | `pnr/soc_top/neg_pnr.py` |
| 2026-10-03 | neg-pnr P03 | 加上 `signoff.sdc`（`set_max_transition 1.0`）後，P03 用 `MAX_TRANSITION_CONSTRAINT=0.05` 植入會被後面的 SDC 蓋掉（推測，尚未實跑；依 base.sdc 先、signoff.sdc 後的順序推得） | 植入點不是 checker 實際讀到的值 | P01–P03 改成在 run 實際用的 signoff SDC 後面追加 | `pnr/soc_top/neg_pnr.py sdc_with()` |
| 2026-10-03 | neg-pnr P13 第一版 | `unset_output_delay [all_outputs]` 之後 check_setup 沒有新警告，case 結果是沒抓到 | 已驗證：OpenSTA `Sdc.tcl` `unset_port_delay` 沒給 `-clock` 時 clk = NULL，只刪沒有 clock 的 delay | 改 `-clock` 仍無警告（見下一列） | `runs/neg_pnr/P13/run.log` |
| 2026-10-03 | P13 探針（單獨重跑 STA 那一步） | `unset_output_delay -clock clk` 後 `report_checks -to uart_tx` 為 `No paths found`，但 `check_setup -unconstrained_endpoints` 與 `-no_output_delay` 都沒有輸出 | 已驗證：unset 之後 OpenSTA 仍視為有 output delay；SDC 直接少寫 `set_output_delay` 時 check_setup 報 `There are 42 unconstrained endpoints` | P13 改為產生少一行的 SDC | `pnr/soc_top/neg_pnr.py sdc_without_output_delay()` |
| 2026-10-03 | neg-pnr P10 | 說明寫也測 Magic DRC，程式只檢查 KLayout | 已驗證（讀程式） | 補上 Magic.DRC 重跑 + `check_soc.py magic_drc` 必須報框外違規 | `pnr/soc_top/neg_pnr.py p10()` |
| 2026-10-03 | Phase 3 收尾 | 下游只查 `signoff.txt`；`project-plan.md` §7.2 的來源追溯（Phase 2 延到 Phase 3）沒做 | 已驗證（讀程式） | `result.txt` + `provenance.py`；`neg_provenance.py` 11/11 | `signoff/scripts/provenance.py` |
| 2026-10-04 | 第二次 `make phase3`（乾淨 worktree，commit 658b6dd） | `gl-soc: FAIL`，12 支測試報 `firmware image fw/build/hello.hex not found` | 已驗證：Makefile 的 `gl-soc`／`neg-gl-soc` 沒有宣告對 `fw` 的相依；第一次 `make phase3` 停在 harden-soc，沒走到這一步 | 兩個 target 加上 `fw`；新增規則 10；summary 改成 `n/N tests passed`（原本 `FAIL 1/13 tests` 容易讀成 1 支 FAIL） | `runs/p3_phase3_clean2.log` |
| 2026-10-04 | 第三次 `make phase3`（乾淨 worktree，commit acbc126） | `neg-gl-soc: FAIL 3/4`，`csb0_inverted` 編譯失敗 | 已驗證：植入的 `wire neg_eqy_inv` 宣告在使用之後，Icarus 拒絕（Yosys 接受，所以 EQY 那邊沒發現）；`neg_gl_soc.py` 在加進 `make phase3` 前沒有單獨跑過 | 宣告移到 `sram0` 前；修正後 GL 11/11 支測試報不一致、EQY 照樣 FAIL；規則 7、10 補一條 | `runs/p3_phase3_clean3.log` |
| 2026-10-04 | Phase 3 獨立審查（2 個 agent） | 文件 6 個數字寫錯；checker 漏洞 5 個（magic_drc 只比種類、provenance 不看 clone 內容、下游不比 commit、假 run 缺 positive control、neg-eqy 不比位置） | 已驗證（我重新核對程式與實驗輸出） | 文件更正；漏洞列為 Phase 3 已知限制 12–16、Phase 4 開頭修；規則 3、7 補 5 條 | `docs/phase_exit/phase3.md` |
| 2026-10-04 | Phase 4 修 5 個漏洞 | 加上「只有被植入的那一列 FAIL」的檢查後，P09、P14 各多一列 FAIL | 已驗證：兩列共用同一個輸入（DEF 位置、`sram0` 實例） | 檢查改成「剛好這幾列」並寫明原因（規則 7） | `pnr/soc_top/neg_pnr.py` |
| 2026-10-04 | Phase 4 P21 第一版 | SRAM 範圍內植入的錯誤被 `li.c1` 抓到，但這條規則不在 SRAM 基準裡 | 已驗證：不是在測位置比對 | 改 `li.3`（規則 7） | `drc-signoff` negative test 一節 |
| 2026-10-04 | Phase 4 獨立審查（checker 漏洞，agent） | 10 項：clock 接線沒人檢查、IR 電壓源大小與位置、provenance symlink、regress 開頭沒記 HEAD、`make -i`、P21／P23 只看第一個問題、neg-eqy 位置範圍太寬、`[max_sum]` 負項、DRC 容許值太寬、py-check 不看跨檔名稱 | 已驗證（審查者用 python 小實驗與程式碼；主控重讀程式確認） | 除了 run_guard 不查工作目錄（regress 已由 provenance-final 擋）與 py-check 跨檔（記為限制）都修正並加 negative test | `docs/phase_exit/phase4.md` 獨立審查一節 |
| 2026-10-04 | Phase 4 `make regress` 第 2 次（乾淨 checkout，`c635ffb`） | harden-soc FAIL：`[FAIL] golden route__drc_errors__iter:2: run=14 expected=11`；其他 433 個在誤差內或相同，signoff 全部 PASS | 已驗證：第 45 步的輸入完全相同（byte-identical），多執行緒繞線在 antenna 修補後的重繞分歧；這組中間數字被錯列為「必須完全相同」 | 使用者決定給 ±100（兩個設計），最終 DRC 數仍完全相同；P31（規則 5） | `signoff/golden/soc_top/README.md` 可重現性 |
| 2026-10-05 | Phase 3.5 `neg_char.py` N6 | 手改 .lib 的植入改成新 margin 後什麼都沒改到（要替換的 `2.7500` 已不在 .lib 裡），`--check` 認定沒有過期，N6 FAIL | 已驗證：植入沒有檢查替換次數 | 改成編輯 `timing_type : rising_edge;` 並檢查替換次數；N1–N6 6/6 PASS（「植入沒有生效」一列） | `ip/sram/char/neg_char.py` |
| 2026-10-05 | Phase 5 開頭：修 Phase 3.5 審查的 12 個漏洞 | 每個漏洞補 negative test：neg-char N9–N16、neg-pnr P33–P36，P17 的檢查收緊、P32 加 positive control、py-check 自我測試 11 段；新案例先在修正前的 checker 上確認抓不到 | 已驗證 | 漏洞類型表的「（未修）」改成修正方式與案例；修 `check_soc.py` 時寫錯的訊息（字串接 list）讓 P30 FAIL，被既有的案例抓到 | `docs/phase_exit/phase5.md` |
| 2026-10-07 | Phase 5 建 Hazard3 golden（第 5 次 harden，`3a28d54`） | ① `soc_top_hazard3.toml` 從 PicoRV32 版複製，`timing__unannotated_net__count` 133 是 PicoRV32 的組成，Hazard3 的 run 是 125；② golden 的 `design__instance__count__hold_buffer` 是 0，netlist 卻有 2,739 顆 hold buffer | 已驗證：① 規則 4 的組成換了設計就要重新計數（15 個 corner 都是 81 clkload + 32 `sram0/dout1` + 12 tie）；② 這個 metric 取最後一個 resizer 步驟報的數字，開了 `RUN_POST_GRT_RESIZER_TIMING` 後是那一步的 0，而且 `RSZ-0032` 本來就不是總數（`drv-timing-closure` 規則 7） | 上限改 125 並寫明組成；golden README 註明這個 metric 的意思；換 core 的規則寫進 `core-migration-hazard3` 規則 22 | `signoff/limits/soc_top_hazard3.toml`、`signoff/golden/soc_top_hazard3/README.md` |
| 2026-10-07 | Phase 5 Hazard3 第 6 次 harden（新 golden 的確認 run） | golden 比對 FAIL 61 個 metric，含數量、面積與 key 集合；signoff 全部 PASS | 已驗證：規則 5 假設「不可重現的只有 detailed routing」，這次第 41 步的 global routing 偶發不同（之後只重跑那一步，合計 27 次裡 5 次不同，約 19%），之後的 cell 數跟著變 | 規則 5 的前提對 Hazard3 版不成立；ADR-0015，規則 5 加了「不可重現的步驟也會改變數量時」 | `flow-regression-reproducibility` 經驗紀錄 |
| 2026-10-07 | Phase 5 Hazard3 第 7 次 harden | golden 比對 FAIL 11 個 metric（diode、cell 數、面積），signoff 全部 PASS | 已驗證：detailed routing 的差異經由繞線後的 antenna 修補（多一輪、多 1 顆 diode）改變數量；規則 5 原本只看過它改變中間輪 DRC 數。加上第 6 次的第 41 步，Hazard3 版三次 harden 只有來源 run 自己與 golden 完全相同 | 使用者決定改 golden 規則：ADR-0015（`[golden_layout_tolerance]`、`[golden_optional]`，約實際最大差異的 5 倍，P50、P51） | `flow-regression-reproducibility` 經驗紀錄 |
| 2026-10-07 | Phase 5 ADR-0016（`adac1a9`、`2caad0e`） | 新 checker `check_soc.py cts_macro_latency`（config 有替換、run 只有自訂 CTS step、log 有 plugin 那一行、netlist 沒有 `delaybuf_*`）；正式 harden 兩個 CPU 都在第 44 步 GRT-0229 中止、沒有重試 | 已驗證：重試規則綁 `RepairDesignPostGRT` 一個 step 名稱；`review_criteria.py` 的 step 清單也綁名稱（這次先改好才沒漏） | negative test P52–P54（netlist 多一顆 `delaybuf_0_clk`、log 少一行、config 少替換）；先用舊做法的 run 確認 FAIL；`make test-flow-retry` 加 3 種情境並檢查 `--from`，新情境用舊腳本 8/11 FAIL；漏洞類型表加「checker 綁死 step 名稱」 | `pnr/soc_top/neg_pnr.py`、`pnr/test_librelane_flow.sh` |
| 2026-10-07 | Phase 5 PicoRV32 確認重跑（`1d13775`）的 `neg-pnr` | `[FAIL] P49: expected FAIL at review_criteria.py uncertainty`（54/55）；Hazard3 同一個 commit 55/55 | 已驗證：PicoRV32 這次第 44 步重試過，`ResizerTimingPostGRT` 有 44（中止）、45（完成）兩個目錄；P49 刪的是 45 的那一行，`review_criteria.py` 接受 44 的 | `review_criteria.py` 只採計有 `state_out.json` 的目錄、每個都要有那一行；加 P55（自己造一個中止目錄，不靠 run 剛好有重試）：舊版兩個 CPU 都漏、新版都抓到，P49 也抓到 | `runs/p5_pico_neg-pnr.log`、`pnr/soc_top/neg_pnr.py` |
| 2026-10-08 | Phase 5 exit 的獨立審查（agent，在 run 的副本上做實驗） | 8 個 checker 漏洞：uncertainty 只看印出的行、`cts_macro_latency` 靠名稱、誤差表保護字與萬用字元、Stop hook 不涵蓋 harden-core 與當掉、`reset_b_tied1` 不是靠證明、`test-flow-retry` 沒測條件、xPack 只看版本字串、PicoRV32 暫用 Hazard3 的誤差；沒有一個讓本階段結果變成 false pass（實際有錯、checker 卻判 PASS） | 已驗證：逐項做出壞掉的輸入、跑 checker、看到 PASS | 全部修正，各有 negative test（P50、P51 新增的子案例、P56–P62、test-review-hook、test-flow-retry、neg-regress）；漏洞類型表加 9 種；規則 7 加兩條 | `docs/phase_exit/phase5.md`「獨立審查」，commit `1dee974` |
| 2026-10-08 | Phase 5 PicoRV32 的乾淨 `make regress-picorv32`（`5aaf036`） | `harden-soc` FAIL：golden 10 個 layout metric 不同（diode 100 → 99、cell ±1、`global_route__vias` 20 → 11），其他全 PASS | 已驗證：PicoRV32 的 layout 誤差依決定清空，這是第一次量到 PicoRV32 在 run 之間的差異 | 使用者決定再量 2 次，用 4 個樣本的最大差異 × 5 訂誤差（ADR-0015 的方法） | p5fin_pico worktree `runs/p5fin_pico_regress_signoff/criteria_review.md` |
| 2026-10-08 | Phase 5 結案（`71b1454`） | PicoRV32 SoC 加寬 met5 後共 6 次 run，layout 只有兩種結果（3 次與 golden 相同、3 次差 1 顆 diode）；依 4 個樣本訂的誤差這次沒用上（435 個逐項相同）。picorv32_core 之前兩次各有 71 個在誤差內，這次 325 個逐項相同 | 已驗證 | 誤差仍照「實際最大差異 × 5」；只有一兩個樣本時，結果剛好相同不代表一直相同（規則 5） | `docs/phase_exit/phase5.md`「可重現性」 |
| 2026-10-10 | Phase 6 步驟 4b 第一輪 harden | 最終 GDS 的 SRAM 是空的，`magic_drc` 仍 PASS（框內 0 個）；只有 XOR 抓到 | 已驗證（`check_soc.py` 在該 run 上，加下限後 FAIL：`only 0 inside, < 50% of the SRAM alone`） | 漏洞類型表加「比對的對象是空的」；`DRC_IN_MIN_FRAC`、`macro_gds`；P67–P69 | `runs/p6_4b_harden_*.log`（`magic_drc … inside 0` PASS），commit `3ceca55`；加下限後重新檢查的那個 run 目錄（`runs/soc_top.prev`）已被之後的 harden 覆蓋，沒有留存輸出，同一情況由 P69（拿掉框內違規）重現，4d 的 `neg-pnr` 71/71 |
| 2026-10-11 | Phase 6 獨立審查（12 個植入實驗，確認 7 個漏洞 H1–H7） | 見上表新增的五類，以及 `macro_drc.py` 只比總數（H4，`比對粒度太粗`） | 已驗證（每個都有植入實驗與對照組；我重跑 H1、H3、H6、H7） | 全部修正並各加 negative test（使用者 2026-10-11：「全部修，再跑兩輪」，ADR-0018 決定 19）。修 H7 時第一版仍 PASS：NaN 被 `abs(..) > tol` 放行，實驗才發現 | `docs/phase_exit/phase6.md`「獨立審查」 |
| 2026-10-11 | Phase 6 結案 regress（乾淨 worktree，`904e18e`） | 兩輪都在 harden-soc FAIL：`soc-inputs: FAIL`，只有 `[FAIL] resolved` 一列，訊息沒說哪一項不符；layout 與 golden 441 個 metric 逐項相同 | 已驗證：`37c99b4` 在 `macro_source` 區塊把 `files` 改成 view 檔名的字典，後面 `resolved` 拿它比 RTL 清單；修正版在兩個 worktree 的 run 上 PASS，舊版讓新 P00 FAIL | 字典改名 `views`；`resolved` FAIL 時列出不符的欄位；P00 加 `--resolved` 對照；漏洞類型表加一類 | `runs/p6close_regress_*.console`、`pnr/soc_top/check_inputs.py` |
| 2026-10-14 | Phase 7 獨立審查（`84fe505`，第一輪結案 regress 期間）與修正 | 8 個漏洞與 1 個缺口（H1–H8、IO pin 的 slew），每個都有植入實驗與對照組；修 H8 時自己又把 `check_inputs.py` 的 `resolved` 列改壞（新變數 `defines` 蓋掉預期值） | 已驗證：修正前的程式重現漏洞、修正後新的 negative test 抓到；`defines` 由 `p7close_h3` worktree 的 positive control 與 `neg-pnr` P00 抓到 | 漏洞類型表加 7 類；規則 13（第二次出現的變數撞名）；ADR-0019 決定 26 | `runs/p7_review/checker_holes.md`；`docs/phase_exit/phase7.md` |
| 2026-10-15 | Phase 0–7 問題總檢討（`docs/notes/problem_review/`，ADR-0021） | ① 變數撞名第三例 `cbf2c5e` 沒記，規則 13 只講「同一個函式」；② limits 檔寫死 unannotated 總數，4 次讓 harden false fail；③ RTL testbench 的兩種漏洞與「工具當掉被說成結果不對」不在漏洞類型表；④ 規則 3、7 寫死的案例數已和腳本不符（run guard 寫 14 個，`neg_run_guard.py` 的 `STEPS` 已是 16 項） | 已驗證：① `git show cbf2c5e`；複查時發現 commit 訊息與審查報告說的「模組層」不對，兩處都在 `main()` 裡；② `phase4.md` 第 100 行、ADR-0016 第 52 行、本表 2026-10-07；③ `phase1.md` 第 18–23 行、`phase7.md` 第 34 行；④ `verify_and_merge.md` 1.4 第 11 項 | 規則 4 加逐項分類、規則 13 改範圍並加第三例、漏洞類型表加三列，四項都寫明「沒有自動檢查」；規則 3、7 改成指向腳本；規則 11、12 標明是使用者決定 | `docs/notes/problem_review/verify_and_merge.md` §3 B5、B7、B9、B10、B11、C1 |
