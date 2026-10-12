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
   - colima 0.10.3 與 docker CLI 29.9.0 已用 Homebrew 安裝（2026-10-12）。
   - 容器每次會 `pip install --upgrade cf-precheck`，每次執行都要記下實際的 cf-precheck 版本與 image digest。
5. **`klayout_feol`／`klayout_beol` 的判定：其他 11 項全 PASS，這兩項只允許 OpenRAM bitcell 造成的兩條規則，而且要和 PDK 預建 macro 一致**（使用者 2026-10-12：「其他全 PASS＋這兩條比對預建 (建議)」）。
   - 原因（已驗證，筆記第 7 節）：precheck 的 deck（release `2026.03.30_01.00`）在 cf-precheck commit `08f559e30a`（2026-05-07）拿掉了 SRAM 核心區（`areaid.ce`）對「mcon 要被 li 蓋住」的豁免（`MR_mcon.CON.10`），並新增 `MR_licon.SP.6`。PDK 預建的 `sky130_sram_2kbyte_1rw1r_32x512_8` 與自產 macro 一樣，FEOL 3 個、BEOL 264 個（依 cell 計），全部在 OpenRAM bitcell 與 replica column 裡；沒有參數能關掉。
   - 判定方式：兩項的違規只能是 `MR_licon.SP.6` 與 `MR_mcon.CON.10`，每一個都落在 SRAM 外框內，而且在 PDK 預建 macro 單獨檢查時的同一個 cell、同一個相對位置也有。做法比照 `check_soc.py magic_drc` 的「框內比對」。checker 與 negative test 在實作時一起加。
   - 列為 Phase 7 的已知限制：用這兩條規則的官方結果仍是 FAIL。
6. **向 ChipFoundry 反映由使用者決定是否送出**（使用者 2026-10-12：「我擬稿，你自己決定發不發 (建議)」）。草稿在 `runs/p7_chipfoundry_issue_draft.md`（不進版控）。
7. **LVS 把 SRAM 當 black box**（業界做法，與現行 SoC LVS 相同，沒有另外問）：`lvs_config.json` 的 `EXTRACT_ABSTRACT` 加入 SRAM。ChipFoundry 的 PDK `3e0e31dc` 對 bitcell 的元件命名和 `8afc834` 相同（筆記第 4 節），transistor-level 比對會遇到 Phase 6 的同一個不一致；ChipFoundry 自己的 `caravel_user_sram` 範例也用 black box。SRAM 內部的一致性仍由 repo 的 view QA 與 `check_macro_gds.py` 負責。

## 後果

- Phase 7 的 exit 條件改寫為：「官方 image 的 precheck 13 項中，11 項 PASS；`klayout_feol`／`klayout_beol` 只有決定 5 的兩條規則，而且與 PDK 預建 macro 一致」。`project-plan.md` §8 同步更新。
- 本機與官方的工具版本不同（Magic 8.3.623 vs 8.3.471、KLayout 0.30.7 vs 0.29.12、Netgen 1.5.316 vs 1.5.272、PDK `8afc834` vs `3e0e31dc`）。repo 自己的 flow 照舊用釘版的工具；precheck 的判定只認官方 image 的結果。
- Magic DRC（precheck 的選用項目）不跑；下線時 ChipFoundry 會怎麼看自產 SRAM 內部的 Magic 違規，要另外問。
