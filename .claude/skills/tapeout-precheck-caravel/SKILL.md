---
name: tapeout-precheck-caravel
description: 跑 ChipFoundry 收件前的自動檢查（precheck、`cf precheck`、`cf-precheck`、`mpw_precheck`）與判讀結果時使用。症狀：`klayout_beol` 報 `MR_mcon.CON.10`（mcon should covered by li）、`klayout_feol` 報 `MR_licon.SP.6`（OpenRAM bitcell，PDK 附的 SRAM 也有；用 `make precheck-check` 檢查），PDK 附的 SRAM 另有 nsdm／psdm 違規；`klayout_beol failed (stat=-9)`、LVS 報 `extraction did not complete successfully`、`OEB FAILED (stat=5)`（VM 記憶體不夠被 OOM kill）；LVS log 結尾 `possible errors SOFT ... CVC`；checker 報 `the results directory checked this GDS`（讀到前一次 run 的報表）；flow 的 KLayout DRC 是 0 而 precheck FAIL（deck 比 flow 的新）；Apple Silicon 沒有 amd64 Docker（用 lima VM）；SRAM 在 LVS 用 `EXTRACT_ABSTRACT` 當 black box；wrapper 設計第一次試跑的 harden 完成後就跑一次完整 precheck。wrapper 範本、GPIO、供電、li1 密度與 fill 看 caravel-user-project-integration。Use for running and judging ChipFoundry cf-precheck (amd64 docker image, newer KLayout deck, OpenRAM bitcell rules, LVS black box, stale reports).
---

# ChipFoundry precheck 怎麼跑、結果怎麼看

本 skill 只管 precheck 怎麼跑、結果怎麼判斷。設計放進 Caravel `user_project_wrapper` 的做法（範本 DEF、GPIO、`wb_clk_i`、供電、decap／li1、fill 與密度下限、IO constraint 試算、下線規定對照表）看 `caravel-user-project-integration`；macro 本身的 view QA 看 `macro-qualification`；DRC 的一般判讀看 `drc-signoff`；LVS 的一般做法看 `lvs-signoff`。本 repo 實例：ADR-0019、`docs/notes/caravel_precheck_phase7.md`、`signoff/precheck/README.md`。

名詞：
- **Caravel**：ChipFoundry（2025 年接手 Efabless 的 sky130 共乘下線）的 harness 晶片。pad、電源與一顆管理用的 RISC-V 都做好了，使用者的設計放在 `user_project_wrapper` 裡。
- **precheck**：ChipFoundry 收件前的自動檢查。現在是 pip 套件 `cf-precheck`，由 `cf` 指令（pip 套件 `chipfoundry-cli`）用 Docker 呼叫。
- **flat 方式**：CPU 的 standard cell 與 SRAM macro 直接放在 wrapper 層繞線，不先把 SoC harden 成 macro（`project-plan.md` §5.5）。官方範例都是先 harden 成 macro。

## 規則（已驗證）

1. **precheck 只有官方 image 的結果算正式結果，並記下實際版本**。
   - `cf precheck` 沒有 Docker 就停止；image 是 `chipfoundry/mpw_precheck:latest`，只有 linux/amd64（cf-cli `main.py` 第 4887、4893、4916 行；Docker Hub 2026-10-12）。Apple Silicon 要用模擬：本 repo 用 lima 直接建 vz＋Rosetta 的 VM，docker context `lima-cf-precheck`（`env/check_env.sh`、`signoff/precheck/run_precheck.sh`）；colima 是包在 lima 外面的同一套，但要從 GitHub 下載 VM image（ADR-0019 決定 4）。
   - 容器每次先 `pip install --upgrade cf-precheck`，同一個 image 不同天跑，版本可能不同。每次記下 image digest 與 cf-precheck 版本。
   - image 的工具版本（Magic 8.3.471、KLayout 0.29.12、Netgen 1.5.272、PDK open_pdks `3e0e31dc`）和 flow 的不同；本機用 flow 的工具跑出來的結果只能加快修 bug，不能當正式結果。
   - **VM 的記憶體要夠**（已驗證，2026-10-14，三次 OOM kill）：
     - 症狀：`klayout_beol failed (stat=-9)`，沒有報表；`lvs` 的 `Error: extraction did not complete successfully`，`logs/ext.log` 停在 `Extracting <top> into <top>.ext`，沒有 `exttospice finished.`；`OEB FAILED (stat=5)`。
     - 怎麼發現：在 VM 裡 `sudo dmesg | grep 'Killed process'`，會看到 `klayout`、`magicdnull` 與它們的 `anon-rss`。
     - 怎麼繞過：加大 VM 記憶體（`limactl edit --memory <GiB>`），並減少 layout 的 instance 數。本 repo 的 wrapper 有 246 萬個 decap 時，KLayout 與兩次 Magic 各用到約 9.2 GB，10 GiB 不夠；VM 改成 16 GiB、decap 改成 `ef_decap_12`（instance 約少四分之三，`caravel-user-project-integration` 規則 4）之後才 PASS。兩件事同一天一起做，沒有分開實驗，哪一個是必要的不知道（ADR-0019 決定 24）。
     - 怎麼防止再發生：這三項沒跑完時 `project.json` 是 fail，`make precheck-check` 一定 FAIL，不會漏；但看不出是記憶體，所以先看 `dmesg` 再查設計。VM 記憶體本身由 `env/check_env.sh` 檢查：`make regress-caravel`（`--flow`、`CPU=caravel`）在 docker context `lima-cf-precheck` 小於 15 GB 時 FAIL（`precheck VM not ready ... need >= 15 GB`），其他情況只提示。
   - cf-precheck 的版本由 `make precheck-check` 比對 `env/versions.mk` 的 `CF_PRECHECK_VERSION`，不同就 FAIL（`neg-precheck` 的 `other_version`）；image 升級了 cf-precheck 時先讀新版的變更，再更新版本與規則 3 的比對基準。
2. **flow 的 KLayout DRC 是 0，不代表 precheck 的 KLayout DRC 會過**：precheck 用內建的 `drc_scripts/sky130A_mr.drc`（2026-10 時是 release `2026.03.30_01.00`），flow 用 PDK 的 deck（`8afc834` 是 `2024.2.11_01.09`），規則名稱與內容都不同。每一顆 macro 交給 wrapper 之前，先用 precheck 的 deck 單獨跑 `feol`／`beol`／`offgrid`（參數照 `checks/klayout_drc.py`：`input`、`topcell`＝GDS 檔名、`report`、`thr`），幾十秒就有結果。
   - 先讀過 deck 再執行：它是第三方的 Ruby 腳本。
3. **OpenRAM bitcell 在新 deck 的兩條規則**（工具缺陷的對策，CLAUDE.md 規則 10）：
   - **症狀**：`klayout_beol` 報 `MR_mcon.CON.10 : mcon should covered by li`、`klayout_feol` 報 `MR_licon.SP.6 : poly_licon minimum space to psdm`，位置在 `sky130_fd_bd_sram__openram_dp_cell*` 與 `*_replica_column*`。PDK 附的 `sky130_sram_2kbyte_1rw1r_32x512_8` 與 OpenRAM 產生的 macro 一樣，BEOL 264、FEOL 3（依 cell 計）。
   - **怎麼發現**：precheck 的 `outputs/reports/klayout_{feol,beol}_check.xml` 的 `<category>` 與 `<cell>`；或規則 2 的 macro 單獨檢查。
   - **原因**：cf-precheck commit `08f559e30a`（2026-05-07）把 `mconnotace.not(li)`（不檢查 SRAM 核心區 `areaid.ce`，81/2）改成 `mcon.not(li)`；`MR_licon.SP.6` 是新規則。`$sram_exclude` 只管 nsdm／psdm，而且只認 `sky130_sram_*` 名稱，關不掉這兩條。
   - **怎麼繞過**：沒有能讓官方結果 PASS 的設定。本 repo 的 PASS 條件（ADR-0019 決定 5）：這兩項只允許這兩條規則，每一個違規都在 SRAM 的範圍內，而且 PDK 附的 macro 單獨檢查時同一個 cell、同一個相對位置也有。向 ChipFoundry 反映的草稿由使用者決定是否送出，到 Phase 7 結案仍是草稿、列為下線前要做（ADR-0019 決定 6、26）。
   - **比對要展開到位置，不能比 cell**（已驗證，2026-10-14）：deck 用 deep 模式，一個違規只在找到它的那層 cell 回報一次，掛在哪層會隨 macro 的階層不同（OpenRAM 產生的 macro 有 2 個 BEOL 違規掛在 `dummy_array`，PDK 附的 macro 掛在 `replica_bitcell_array`），cell 名稱也有各自的 prefix。新版 OpenRAM 產生的 macro 外框較大，bitcell array 在 macro 裡的位置也不同（本 repo 差 (5.61, 9.32) µm）。做法：把違規展開到所在 cell 的每個 instance，換回 macro 座標，以 bitcell array（`sky130_fd_bd_sram__openram_dp_cell` 所有 instance 的外框）左下角為原點；位移由 GDS 的 instance 位置決定，不從違規位置擬合。兩顆 macro 單獨檢查時 FEOL 16,900、BEOL 50,184 個位置完全相同。
   - **比對基準只比允許的規則**（已驗證，2026-10-14）：precheck 的 PDK（`3e0e31dc`）裡的 `sky130_sram_2kbyte_1rw1r_32x512_8`（sha1 `de2cf967…`）FEOL 另有控制邏輯的 `MR_psdm.SP.1`、`MR_nsdm.WID.2`、`MR_psdm.WID.2` 共 10 個（flow 的 `8afc834` 那顆沒有），ChipFoundry 自己那版 PDK 附的 SRAM 也過不了 FEOL。比對基準要用 precheck 實際用的那顆 macro，在同一個 image 用同一份 deck 跑（`signoff/precheck/run_precheck.sh`），它的其他規則印出、不列入比對；設計仍然只能有允許的規則（ADR-0019 決定 24）。
   - **怎麼防止再發生**：`make precheck-check`（`signoff/precheck/check_precheck.py`）照上面的方法檢查，並確認其他 11 項 PASS、檢查項目齊全（precheck 升版加了新檢查會 FAIL）、報表與比對基準是同一版 deck（規則清單相同）、專案來自通過 run guard 的正式 harden（`arvinsa_source.json`；不列入 signoff 證據的非正式專案要加 `--verification`，結論會標明不是 signoff 結果）、時間戳換成 UTC 再比（Phase 7 審查 H6、H7）；negative test `make neg-precheck`（在 `make regress` 裡；案例表在 `signoff/precheck/neg_precheck.py` 開頭，`ref_other_rule` 確認比對基準的其他規則不會放過設計的同一條違規）。本機的 deck 由 `make precheck-deck` 依 `env/versions.mk` 的版本與 sha256 取得。deck 升版時：先讀 deck，更新 `CF_PRECHECK_*`，重跑規則 2 的兩顆對照與 `make neg-precheck`。
4. **SRAM 的 LVS 用 black box**：precheck 的 LVS 是 Magic 萃取到電晶體層級加 Netgen。ChipFoundry 的 PDK `3e0e31dc` 對 bitcell 的元件命名和 `8afc834` 相同（`special_pfet_latch`、`special_nfet_01v8`），OpenRAM 的 netlist（2022 PDK 的命名）對不上。在 `lvs/user_project_wrapper/lvs_config.json` 的 `EXTRACT_ABSTRACT` 加入 SRAM 的 cell 名稱，ChipFoundry 自己的 `caravel_user_sram` 範例也這樣做。代價：SRAM 內部不檢查，要靠 view QA 與 `check_macro_gds.py`。
   - 已實跑（2026-10-14）：`lvs_config.json` 的路徑都以 `$PDK_ROOT`／`$UPRJ_ROOT` 開頭（`signoff/precheck/make_project.py`），Netgen `Circuits match uniquely`。
   - LVS log 結尾的 `WARNING: possible errors SOFT - ... CVC <n>` 不是比對失敗：同一支腳本最後跑的 CVC（電路合理性檢查）看不到 black box 的輸出驅動，`logs/cvc.log` 的 `HI-Z Inputs` 就是 SRAM 輸出（本 repo 32 個 `dout0` net 加上接在上面的 buffer 內部節點，74 個 MOS）。要確認時，從 `outputs/reports/<top>.gds.spice.gz` 對 SRAM instance 的腳位，HI-Z 的頂層 net 應全部是 SRAM 的輸出；有不是的就是真的浮接。沒有自動檢查：cf-precheck 不把 CVC 算進 LVS 的 PASS／FAIL，`make precheck-check` 也不讀它。
   - 怎麼防止再發生：`signoff/precheck/make_project.py` 產生 `lvs_config.json`（`EXTRACT_ABSTRACT` 與 `$PDK_ROOT`／`$UPRJ_ROOT` 開頭的路徑），不手寫；precheck 的 `lvs` 不是 pass 時 `make precheck-check` FAIL（`neg-precheck` 的 `other_check`）。bitcell 命名對不上時 Netgen 的確切訊息沒有存下（本 repo 一開始就用 black box），換 PDK 或 OpenRAM 版本要拿掉 black box 時，先單獨跑一次 SRAM 的 LVS 記下訊息。

5. 規則 5 移到 `caravel-user-project-integration` 規則 1（先定 block 位置，再選 GPIO）。
6. 規則 6 移到 `caravel-user-project-integration` 規則 2（`wb_clk_i`）。
7. 規則 7 移到 `caravel-user-project-integration` 規則 3（user area 的供電結構）。
8. 規則 8 移到 `caravel-user-project-integration` 規則 4（wrapper 頂層的 decap 與 li1 密度）。

### 提早檢查（流程回顧，ADR-0020，使用者決定）

2026-10-14 回顧（`docs/notes/flow_retro/retro_p6_7.md`）的結論之一：Phase 7 第一天的查證列出了 ChipFoundry 的檢查項目、密度上限與官方 SDC，但沒有套到自己的設計上算數字；單顆 vccd1 pad、IO pin 的 input transition 與 IO 路徑的 hold、li1 密度、precheck 那版 PDK 附的 SRAM、metal fill 誰補，全部在 harden 之後才發現，粗估重做約 2 天、3 項放寬。每項試算只要 10 分鐘到半天。使用者決定加下面三條（流程文件 4.1、4.5、4.6）。

9. 規則 9 移到 `caravel-user-project-integration` 規則 5（下線規定對照表）。
10. 規則 10 移到 `caravel-user-project-integration` 規則 6（官方 wrapper SDC 的試算）。
11. **wrapper 設計第一次試跑的 harden 完成後，就用試跑產生的 GDS 跑一次完整的 precheck；下線服務商的密度上下限做成 harden 內的 checker**（提早檢查 D5）。
    - 做什麼：非正式地跑一次 `make precheck-caravel`（不列入 signoff 證據，`check_precheck.py --verification` 的結論會標明不是 signoff 結果，規則 3），量 VM 的記憶體峰值（規則 1）；fill 與 decap cell 依結果決定（`caravel-user-project-integration` 規則 4）。li1 與金屬密度的上下限（`caravel-user-project-integration` 規則 5 對照表的結果）在 harden 內檢查，不要等 precheck。
    - 通過條件：除了已由使用者決定的項目全 PASS；VM 記憶體峰值低於配置。
    - 為什麼：li1 75% 與 VM OOM 都到 Phase 7 步驟 7 才發現，整段約 14 小時、多兩次 harden（ADR-0019 決定 24）；本機算 li1 密度只要 84 秒，整套 precheck 約 1.5 小時（回顧 `retro_p6_7.md` #8）。
    - 自動檢查：harden 內的密度 checker 目前沒有（`caravel-user-project-integration` 規則 4 的「怎麼防止再發生」），下一個專案開始時做成 checker 並加 negative test。

## 規則（已驗證，2026-10-15 問題總檢討後補寫，ADR-0021）

12. **precheck 的報表要綁到這一次的 GDS：讀到前一次 run 的報表也會 PASS**（工具缺陷的對策，CLAUDE.md 規則 10；Phase 7 步驟 6 獨立審查找到，`docs/phase_exit/phase7.md`「precheck 判定的 4 個漏洞」）。
    - **症狀**：專案目錄的 `precheck_results/<開始時間>/` 報表與 `.cf/project.json` 是分開寫的；只看「最新的結果目錄」或只看 `project.json` 的 status，舊報表配新 GDS（precheck 中途停掉、GDS 在 precheck 之後被換掉）照樣會被判 PASS。checker 擋下時印 `the results directory checked this GDS (logs/gds.info: ...)` 或 `gds/<top>.gds sha1 ... = the checked file's ...` 的 FAIL 行。
    - **怎麼發現**：cf-precheck 把這次檢查的 GDS sha1 寫在結果目錄的 `logs/gds.info`、`project.json` 的 `input_file_hash`（`runner.py` 第 23–31 行，`docs/notes/caravel_precheck_phase7.md` 第 112 行）；三者（`gds/<top>.gds` 的 sha1、`input_file_hash`、`gds.info`）要相同，`project.json` 要在結果目錄的開始時間之後寫入（時間戳換成 UTC 再比）。
    - **怎麼繞過**：`make precheck-caravel` 每次用 `make_project.py` 重建專案目錄，precheck 中途停掉就沒有結果，checker 判 FAIL；不要在舊的專案目錄重跑，也不要手動換 GDS。
    - **怎麼防止再發生**：`make precheck-check` 的「檢查的是這份 GDS」一列（`signoff/precheck/README.md`「檢查內容」）；`neg-precheck` 的 `stale_results`、`other_gds`、`results_after`、`results_after_tz`、`no_tz`（在 `make regress` 裡）。cf-precheck 升版改了 `logs/gds.info` 或 `input_file_hash` 的位置時，checker 讀不到就 FAIL（不會放過），照規則 1 的升版步驟更新。

## 待確認

讀過原始碼、還沒實跑：
- `magic_drc` 是選用，預設不跑；只有 PDK 的 `sky130_sram_*` 會換成 maglef，OpenRAM 產生的 SRAM 用完整規則會 FAIL。下線時 ChipFoundry 怎麼看要另外問。

wrapper 本身要滿足的檢查（`xor`、`gpio_defines`、`oeb`、`klayout_met_min_ca_density`）與官方範例的 flow 版本，移到 `caravel-user-project-integration`「待確認」。

## 用完後

1. 新的現象加進「經驗紀錄」，原因標明已驗證／推測。
2. 「待確認」的項目實跑確認後搬進規則；同一現象出現兩次或用實驗確認才寫成規則（CLAUDE.md 規則 3）。
3. precheck 或 deck 升版時，逐條重看規則 3 的對策是否還成立（CLAUDE.md 規則 10）。

## 經驗紀錄

這張表 2026-10-15 拆分（ADR-0021 決定 5）：wrapper 整合的列（2026-10-12 的 GPIO、`PDN-0239`、`RSZ-0074`、IO pin 的 max slew、`GRT-0036`、disconnected pin、IO 路徑的 hold，2026-10-13 的 IR what-if，2026-10-15 的 fill 試跑）搬到 `caravel-user-project-integration` 的經驗紀錄；這裡留 precheck 怎麼跑、結果怎麼看的列。

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-12 | arvinsa-rtl-gds Phase 7 開始（查證） | precheck 的 deck 檢查 SRAM：OpenRAM 產生的 macro 與 PDK 附的 macro 都是 FEOL 3（`MR_licon.SP.6`）、BEOL 264（`MR_mcon.CON.10`）、offgrid 0；flow 的舊 deck 兩顆都是 0 | 已驗證：比對兩份 deck 與 cf-precheck commit `08f559e30a` 的 diff | ADR-0019 決定 5：這兩條比對 PDK 附的 macro；向 ChipFoundry 反映的草稿由使用者決定是否送出 | `docs/notes/caravel_precheck_phase7.md` 第 7 節 |
| 2026-10-14 | arvinsa-rtl-gds Phase 7 步驟 6（檢查 precheck 結果的 checker） | 決定 5 要「同一個 cell、同一個相對位置」比對 PDK 附的 macro；兩顆 macro 單獨檢查的報表依 cell 分：BEOL OpenRAM 產生的 2 個掛在 `arv_…_dummy_array`／`_0`，PDK 附的 2 個掛在 `sky130_…_replica_bitcell_array`，cell 名稱的 prefix 也不同；展開後位置全部不同 | 已驗證：deep 模式在找到違規的那層 cell 回報；新版 OpenRAM 的 macro 外框較大，bitcell array 差 (5.61, 9.32) µm。以 bitcell array 左下角為原點後，FEOL 16,900、BEOL 50,184 個位置完全相同 | 規則 3「比對要展開到位置」；`signoff/precheck/`（`make precheck-check`、`make neg-precheck`） | `signoff/precheck/README.md`、ADR-0019 決定 5 |
| 2026-10-14 | arvinsa-rtl-gds Phase 7 步驟 7（官方 image 跑 wrapper，非正式，`f4ea9de`） | 8 項 PASS、FEOL 符合決定 5；`klayout_beol failed (stat=-9)`、LVS `Error: extraction did not complete successfully`、`OEB FAILED (stat=5)`；`klayout_met_min_ca_density` 211 個 `li1.pd.1d`；checker 另外報出比對基準有 `MR_nsdm.WID.2` 等其他規則 | 已驗證：VM 10 GiB，KLayout 與兩次 Magic 各約 9.2 GB 被 OOM kill（`dmesg`）；li1 75%，其中 `decap_3`（87% li1）2,461,688 個佔 9.24 mm²；`3e0e31dc` 那版 PDK 附的 SRAM 控制邏輯有 10 個 nsdm／psdm 違規 | VM 改 16 GiB（規則 1）；`DECAP_CELLS` 改 `ef_decap_12`、`FILL_CELLS` 加 fill_8／fill_4（ADR-0019 決定 24，重新 harden 後驗證）；比對基準只比允許規則（規則 3），neg-precheck 25 個案例 | `docs/notes/caravel_precheck_phase7.md` 第 10 節、`runs/p7_precheck_verify/` |
| 2026-10-14 | arvinsa-rtl-gds Phase 7 步驟 7（`7eff65a` 非正式、`550869c` 正式） | decap 改 `ef_decap_12` 後：`klayout_met_min_ca_density` PASS（`li1_ca_density is 0.6010`）、BEOL／LVS／OEB 跑完 PASS，`make precheck-caravel` PASS；LVS log 結尾 `possible errors SOFT - ... CVC 4`，`HI-Z Inputs: 74` | 已驗證：li1 75.1% → 39.9%（前後比較）；CVC 的 HI-Z 是 SRAM black box 的 `dout0[31:0]`（抽取 SPICE 對腳位） | 規則 8（現 `caravel-user-project-integration` 規則 4）；本 skill 規則 4 補上 CVC 的判讀 | `docs/notes/caravel_precheck_phase7.md` 第 10a、10b 節、ADR-0019 決定 24 |
| 2026-10-15 | arvinsa-rtl-gds Phase 7 結案第二輪的 Hazard3 regress 重跑（`2b04451`，worktree p7close2_h3；同時跑 wrapper 的 regress 與 PicoRV32 的 regress） | `neg-precheck` FAIL（0.9 分鐘）：`neg-precheck: FAIL the reference's klayout_feol report has no item`；本機 KLayout 0.30.7 跑 precheck deck（`sky130A_mr.drc` 第 955 行的 `drc`）時 `ERROR: Signal number: 11`、`Address: 0x0`，backtrace 在多執行緒的 `db::local_processor` | 推測（沒有重現）：記憶體壓力，當時 swap 7.6／9.2 GB；同一個 GDS（sha1 與基準相同）、同一份 deck 在前三次 `neg-precheck` 都 31/31 PASS | 整條 regress 等負載降下來再重跑：第三次執行（07:51，只剩這一條 regress）同一項 31/31 PASS，與推測一致但不算證明；只出現一次，依規則不加重試。沒有自動檢查：checker 會 FAIL（報表沒有項目），但看不出是工具當掉，要看 `ref/klayout_feol_check.log` | main worktree 的 `runs/p7close2_h3_neg_precheck_ref_klayout_sig11.log`、`runs/p7close2_regress_hazard3.sig11.console` |
