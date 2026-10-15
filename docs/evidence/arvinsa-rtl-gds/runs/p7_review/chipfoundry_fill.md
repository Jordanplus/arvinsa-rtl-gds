# ChipFoundry Caravel 共乘下線：user_project_wrapper 的 metal fill 由誰補？

查證日期：2026-10-14（限時 30 分鐘；只讀網路與 GitHub，沒有跑任何 EDA 工具）
問題背景：wrapper 覆蓋率 li1 39.9%、met1 18.1%、met2 1.6%、met3 0.8%、met4 26.7%、met5 27.3%；cf-precheck 1.3.7 的 `klayout_met_min_ca_density` 只檢查上限，所以 PASS。

## 結論先講

1. **metal fill 由晶片整合方在 tapeout 階段對整顆 Caravel 自動補，user 不需要、也不被要求自己補。**
   - 證據：Efabless 時代有明確說法（Efabless 的 Tim Edwards 在 GitHub issue 的留言）和程式碼（`caravel` repo 的 `make generate_fill`，fill 範圍是整顆晶片 3588 × 5188 µm）。
   - ChipFoundry 接手後的 `chipfoundry/caravel` 還保留同一套 fill 與 fill 後的密度檢查腳本，內容沒改。ChipFoundry 組織下 2025-12 的一個共乘 repo 也在產生最終 OASIS 前跑 `make generate_fill`。
   - **缺口**：沒找到 ChipFoundry 自己寫的文件說「我們會幫 caravel_user_project 補 fill」。cf-cli 只說會有 server 端的 tapeout 處理和 tapeout report。所以 ChipFoundry 時代的部分是根據沿用的程式碼推論，不是官方明文。
2. **補 fill 之後還有一道下限檢查，這道檢查不在 precheck 裡，失敗時要回頭改設計。**
   - fill 之後用 700 × 700 µm 的 window 檢查：li1、met1–met4 ≥ 35%，met5 ≥ 45%。
   - Efabless 時代真的有全數位、全 OpenLane 的設計卡在這一步（met2 34%、met5 44.9%）。
3. **sky130 公開 PDK 文件（periphery rules）並沒有寫「met1–4 ≥ 35%、met5 ≥ 45%」。**
   - 這組數字來自 Efabless／open_pdks 的 `check_density.py`。
   - 公開文件裡，met1–met4 只有一條意義不清的「Min oxide pattern density 0.7」（標為建議規則），li1 和 met5 完全沒有密度規則。
   - 所以 repo 裡「35%／45%」的出處應改寫成 Efabless／open_pdks 的 tapeout 檢查腳本，不是 PDK periphery rules。
4. **建議**：不要自己在 wrapper 加 metal fill。改做以下三件事：
   - 向 ChipFoundry 書面確認 fill 由他們做。
   - 看 tapeout report 裡 fill 之後的密度結果。
   - 有空時在本機用 open_pdks 的 `generate_fill.py`＋`check_density.py` 對 wrapper 跑一次，預估 fill 之後的密度（耗資源，等 regress 跑完再做）。

## 1. sky130 PDK 的密度規則（公開文件）

出處：`google/skywater-pdk` @ `7198cf6`（2023-05-29），`docs/rules/periphery-rules.rst`
（https://github.com/google/skywater-pdk/blob/main/docs/rules/periphery-rules.rst）

| 規則 | 內容 | 旗標 | 值 | 行號 |
|---|---|---|---|---|
| m1.pd.1／m2.pd.1／m3.pd.1／m4.pd.1 | "Min MMx_oxide_Pattern_density" | RR（m1 另有 AL） | 0.7 | 2074–2077、2313–2316、2567–2570、2853–2856 |
| mX.pd.2a | 檢查時把晶片切成邊長多少的正方形 window | A | 700 µm | 2079、2318、2572、2858 |
| mX.pd.2b | window 的步進 | A | 70（µm） | 2084、2323、2577、2863 |
| m1.13～m4.13 | Max pattern density | CU | 0.77 | 2098–2102 等 |
| m1.14／m1.14a | 上一列的 window 與步進 | CU | 50 µm／25 µm | 2103–2112 |
| m1.-（m2–m4 同） | window 被 waffleDrop（不放 fill 的區域）覆蓋多少比例時，金屬密度要到多少（例：整個 700 µm window 都是 waffleDrop 時要 ≥ 70%） | RC | — | 2015–2028 |
| li.*、m5.* | **沒有任何密度規則** | — | — | li 1695–1743、m5 2967–2995 |

旗標的意思（同檔 20–94 行）：
- RR = Recommended rule at any IP level（建議規則）
- RC = Recommended at chip level, required at IP level
- AL = 只適用鋁製程後段
- CU = 只適用銅製程後段（sky130 是鋁後段，所以 0.77 上限、50 µm window 這組不適用）
- A = 寫在 CL 演算法裡，DRC 不一定檢查

解讀（推測，請注意）：
- "oxide pattern density" 指沒有金屬的比例（clear area）。照字面看，「oxide 最少 0.7」等於「金屬最多 30%」，跟實務上 60% 的上限對不起來。
- 這條規則的確切意思，從公開文件判斷不了。
- 公開文件裡**沒有金屬密度的最低限制**。

實際在用的數字，出處在工具腳本，不在 PDK 文件：

| 來源 | 檢查什麼 | li1 | met1–met4 | met5 | window |
|---|---|---|---|---|---|
| cf-precheck 1.3.7 `met_min_ca_density.lydrc`（`chipfoundry/cf-precheck` @ `6c401ed`，`src/cf_precheck/drc_scripts/met_min_ca_density.lydrc`:69–130） | 上限（clear area ≥ 0.4 → 金屬 ≤ 60%；met5 clear ≥ 0.24 → ≤ 76%） | ≤ 60% | ≤ 60% | ≤ 76% | **整個 wrapper 平均**（`full_area = chip_boundary.area`，chip_boundary 是 layer 235/4，第 69、71 行） |
| Efabless／ChipFoundry `caravel/scripts/check_density.py`（`efabless/caravel` @ `27cbe49`，與 `chipfoundry/caravel` @ `01fb61d` 逐字相同） | fill 之後的上下限（第 20 行："Run density checks on the final (filled) GDS"） | 35–60% | 35–60% | 45–76% | 700 × 700 µm window，金屬層每 350 µm 步進（第 330–342 行），再加整顆晶片平均（第 546 行之後）；門檻在第 415–543、553 行之後 |
| open_pdks `sky130/custom/scripts/check_density.py`（`RTimothyEdwards/open_pdks` @ `0ec4fa6`，第 449–672 行） | 同上 | 35–60% | 35–60% | 45–76% | 同上 |

→ repo 裡寫的「met1–4 35%、met5 45%」和這兩支腳本一致，li1 也是 35%。但它們是 **fill 之後**才檢查、用 700 µm window 的值，不是 PDK periphery rules 的條文。

## 2. 下線前誰做 fill：證據

### 2a. Efabless 時代（強證據：Efabless 員工的明文說法加上程式碼）

- **Efabless 的 Tim Edwards（open_pdks／Magic 作者）在 `efabless/caravel_user_project#169` 留言**（2022-10-07，https://github.com/efabless/caravel_user_project/issues/169）：
  > "The precheck density check is intended to catch areas of too much metal. The opposite check, for too little metal, is assumed to be taken care of by automatic fill pattern generation. There is a final check for under-density of metal after the fill pattern generation, but it's not part of precheck, and it is a pretty rare case that fails under-density. But if you're already over-density in metal, then adding fill patterns isn't going to make anything better."
- **同一個人在 `efabless/mpw_precheck#141`**（2022-09-12，https://github.com/efabless/mpw_precheck/issues/141）：
  - 使用者說 "the tapeout step (metal fill) is failing"。
  - Tim 說 `check_density.py` "is intended to be run on a layout after fill generation"，並提到 user project 自己的 met4 只有 6.9%。
  - 也就是說，user area 金屬很少是常態，靠 tapeout 階段的 fill 補上。
- **`efabless/caravel#397`**（2022-12，https://github.com/efabless/caravel/issues/397）：
  - 一個 "fully digital, 100% Openlane generated" 的設計 "passes precheck, but slightly fails M2&M5 density checks **after** metal fill during tapeout"（m2_ca 0.6592 → 金屬 34%；m5_ca 0.5514 → 金屬 44.9%）。
  - 原因之一是 fill 腳本在每個 700 µm tile 的邊界留下約 4 µm 寬、沒補到的帶狀區。
  - → **fill 是 Efabless 的 tapeout job 做的；做完後的下限檢查會擋人。**
- **程式碼**（`efabless/caravel` @ `27cbe49`）：
  - `Makefile`:1138–1155：`make generate_fill` 呼叫 `scripts/generate_fill.py $(USER_ID) $(PROJECT) ...`。
  - `generate_fill.py`:187–198：讀 `gds/<project>.gds`（整顆 Caravel，user area 已經放進去），`fullbox { 0 0 717600 1037600 }`。依 Magic 內部單位推算為 3588 × 5188 µm，也就是整顆晶片（推算）。
  - 第 175 行：700 µm 一塊切開，每塊用 Magic 的 `cif ostyle wafflefill(tiled)` 產生 fill。
  - `compositor.py`:178–196：`make final` 把 `<project>_fill_pattern.gds` 和晶片合成最終 GDS。
  - 之後 `check_density.py` 對 "final (filled) GDS" 檢查。
  - → **fill 對整顆晶片做，包含 user_project_wrapper 的區域。**

### 2b. ChipFoundry 時代（2025 起）（中等證據：沿用的程式碼，沒有官方明文）

- `chipfoundry/caravel` @ `01fb61d`（2026-03-30）：
  - `Makefile`:1141–1151 的 `generate_fill` target 還在。
  - `scripts/generate_fill.py` 第 175、198 行：一樣是 700 µm tile、整顆晶片的範圍。
  - `scripts/check_density.py` 和 Efabless 版逐字相同。
  - `generate_fill.py` 最後一次修改是 2023-09（`19ce6de3cc`），仍是 Efabless 時期的版本。
- `chipfoundry/nydesign-ci2605`（ChipFoundry 組織下的 Tiny Tapeout 共乘晶片 repo），`.github/workflows/precheck.yaml`:77–146（commit `9ab64b1`，2025-12-04）：
  - 先 checkout `chipfoundry/caravel`，再依序跑 `make openframe`、`make generate_fill`、`make final`、`strm2oas`，最後做 FOM／poly／metal／tiled metal density DRC。
  - → 在 ChipFoundry 的共乘上，最終 OASIS 仍是「整合者對整顆晶片補 fill，再檢查密度」。
  - 注意：這是 openframe／Tiny Tapeout 的晶片，由晶片整合方自己跑；不是 caravel_user_project 使用者的提交流程。
- `chipfoundry/cf-cli` @ `88025a8`，`README.md`:
  - 703–721：`cf confirm` "send your current GDS file to the foundry for tapeout processing"。
  - 723–731：`cf view-tapeout-report` 開啟 server 端產生的 consolidated tapeout report。
  - 這兩段只說 server 端有 tapeout 處理，**沒寫 fill**。整個 repo 搜 `fill`／`density`，只有 precheck 的 `klayout_met_min_ca_density`（`chipfoundry_cli/check_refs.py`:29）。
- `chipfoundry/caravel_user_project` @ `b510613`：README 與 docs 都沒提 fill 或 tapeout 階段的處理。
  - `openlane/user_project_wrapper/config.json`:16 的 `"RUN_FILL_INSERTION": false` 是 OpenLane 的 **filler／decap standard cell** 插入，不是 metal fill。別混為一談。
- `chipfoundry/cf-precheck` README 的 check 清單（第 96–111 行）只有上限的 `klayout_metal_minimum_clear_area_density`，沒有下限檢查。這和 Tim「下限留給 fill 之後再查」的說法一致。
- 第二手資料（沒驗證到原文）：搜尋引擎摘要一份 Efabless 平台教學頁（https://luis-spader.notion.site/6-6-Submitting-Precheck-and-Tapeout-Jobs-137f827762b680b5bc59d983688e3ca5），內容是 "the tape out job runs some additional tests and also generates the metal fill"。頁面是 JS 渲染，WebFetch 讀不到原文，**不能當主要依據**。

## 3. tapeout 階段會不會對 user area 自動加 fill？使用者要不要自己加？

- **會自動加。** Efabless 時代有明文，ChipFoundry 時代是由沿用的程式碼推論。fill 範圍是整顆晶片，user area 也在裡面（2a、2b）。
- **使用者不必自己加。** 沒找到要求使用者補 fill 的文件。Tim 的說法是下限「assumed to be taken care of by automatic fill pattern generation」。
- **有沒有「禁止自己加 fill」**：沒找到明文禁止。程式碼上自己加的 fill 也相容：
  - Magic `wafflefill` style 把既有的 fill layer（`lifill`、`m1fill`…，GDS datatype 28）和 `fillblock` 都當成障礙物，不會疊上去。出處：cf-precheck 附帶的 `be_checks/tech/sky130A/sky130A.tech`:1983、2029。實際 fill 用的是 PDK 的同名 tech 檔，推測內容相同。
  - `fillblock` 可以用來擋住不想放 fill 的區域（例如類比敏感區），同檔 291、422、1403–1415 行。
  - 但自己加 fill 的風險：會被算進 precheck 的上限（60%／76%）；fill 形狀本身的 DRC，Efabless 在 2024 年還說要另寫 deck（`efabless/caravel#544`，https://github.com/efabless/caravel/issues/544）。**不建議自己加。**

## 4. 我們的 wrapper 在下線前要做什麼

| 情況 | 該做的事 | 依據強度 |
|---|---|---|
| **A. 官方會補（目前最可能）** | 不自己加 metal fill。提交後看 `cf view-tapeout-report` 裡 fill 之後的密度結果；FAIL 時依報告修。 | Efabless 時代：強（明文＋程式碼＋實際失敗案例）。ChipFoundry 時代：中（同一套腳本仍在 `chipfoundry/caravel`，ChipFoundry 組織的共乘 repo 也照用；沒有官方明文） |
| **B. 使用者要自己補** | 用 open_pdks 的 `generate_fill.py` 產生 fill（datatype 28），合進 wrapper GDS，再重跑 precheck 確認上限與 DRC。 | 弱：沒找到任何 ChipFoundry 或 Efabless 文件要求這麼做 |
| **C. 查不到、要問** | 寫信或在 ChipFoundry 平台問：「caravel_user_project 的 metal fill 是否由 ChipFoundry 在 tapeout 階段對整顆晶片產生？fill 之後的密度門檻（li1／met1–4 35%、met5 45%、700 µm window）是否沿用 `caravel/scripts/check_density.py`？」答覆記進 ADR-0019。 | 這是補上 ChipFoundry 時代缺口的唯一方法；建議和 A 一起做 |

**我們特有的風險**（推測與估算，沒有實測）：
- 我們的 met2 只有 1.6%、met3 只有 0.8%，幾乎全部要靠 fill 撐到 35%。
- `wafflefill` 在空曠區的粗 fill 是 2 µm 方塊、間距 0.8 µm（sky130A.tech:2033 `slots 0 2000 800 ...`，單位 nm）。
  - 理論上限約 2² ÷ 2.8² ≈ 51%。
  - met5 是 5 µm 方塊、間距 1.6 µm（第 2250 行），約 57%。
  - 已有金屬旁邊要先留 3 µm 不能放 fill（第 2029–2030 行 `grow 3000`）。
- 估計空曠區可以超過 35%，但風險在三處：
  - SRAM macro 上方與 PDN strap 密集的 window：既有金屬不多，又被不能放 fill 的範圍吃掉面積。
  - 700 µm tile 邊界沒補到的帶狀區（#397 的 4 µm 帶）。
  - #397 那顆全數位設計 fill 之後是 met2 34%、met5 44.9%，就是落在門檻邊緣。
- 想提早知道結果，可以在 regress 結束後，用 PDK 的 `$PDK_ROOT/sky130A/libs.tech/magic/generate_fill.py <wrapper.gds> -dist` 和 `check_density.py` 對 wrapper 單獨試跑。Tim 說這兩支腳本是為整顆晶片設計的，對單一 wrapper 的結果只能當參考。
  - 這一步耗 CPU 與記憶體，這次沒有跑。

## 證據清單（commit 固定）

- google/skywater-pdk @ 7198cf647113f56041e02abf3eb623692820c5e1 — docs/rules/periphery-rules.rst（行號見第 1 節）
- efabless/caravel @ 27cbe49c90ba5362ad52c9968dd98e035c30c74f — Makefile:1138–1155；scripts/generate_fill.py:175、187–198；scripts/compositor.py:178–196；scripts/check_density.py:20、330–342、415–543
- chipfoundry/caravel @ 01fb61d4397c5e7308c3e277031b326eca6ce475 — Makefile:1141–1151；scripts/generate_fill.py:175、198；scripts/check_density.py（與 Efabless 版相同）
- RTimothyEdwards/open_pdks @ 0ec4fa67eade28cd0a4352c04df981840809427b — sky130/custom/scripts/generate_fill.py、check_density.py:449–672
- chipfoundry/cf-precheck @ 6c401ed5134a6466c7eed3e5524ebaacad4cea2a（`__init__.py`:1 版本 1.3.7）— drc_scripts/met_min_ca_density.lydrc:69–130；be_checks/tech/sky130A/sky130A.tech:1791–1830、1983–1989、2029–2034、2250；README.md:96–111
- chipfoundry/caravel_user_project @ b510613cec367828966b37583f9090ac5ddb6491 — openlane/user_project_wrapper/config.json:16
- chipfoundry/cf-cli @ 88025a8fe92111de17795977f6dc92528ba962ec — README.md:703–731
- chipfoundry/nydesign-ci2605 — .github/workflows/precheck.yaml:77–146（commit 9ab64b192ada860e646e37de2152595b9642feca）
- GitHub issues：efabless/caravel_user_project#169、efabless/mpw_precheck#141、efabless/caravel#397、efabless/caravel#544

本機 clone（scratchpad，非 repo）：`<claude-session-tmp>/scratchpad/cf_fill/`
