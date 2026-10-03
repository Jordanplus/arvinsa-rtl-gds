# Phase 0 環境建置

狀態（2026-10-03）：本機工具與釘版 IP 已就緒（`make env-check` PASS）；**Nix、LibreLane、sky130A PDK 尚未安裝**。
工具與版本總表見 `toolchain.md`，釘版值見 `env/versions.mk`。

## 1. 已就緒（不需 Nix）

| 項目 | 版本 |
|---|---|
| Verilator | 5.050 |
| Icarus Verilog | 13.0 |
| Yosys（只做本機 sanity check，正式流程用 LibreLane 內建版本） | 0.69 |
| riscv64-elf-gcc | 16.1，rv32 multilib 可用，無 newlib |
| Python | 3.14（需 ≥ 3.11，只用標準函式庫） |
| GNU make | 3.81（macOS 內建；Makefile 已相容） |

## 2. 使用者執行：`make nix-install`

安裝程式會建立 `/nix` APFS volume 與 build 使用者，**會要求輸入管理者密碼**，所以要在自己的終端機執行：

```bash
cd ~/claude_prjs/arvinsa-rtl-gds
make nix-install DRY_RUN=1   # 可選：只下載安裝程式並印出將執行的指令，不安裝
make nix-install             # 實際安裝，約 5 分鐘
```

`make nix-install`（`env/install_nix.sh`）做的事：

1. 已安裝 Nix 時直接結束；若 FOSSi binary cache 沒設定，會印出要加進 `/etc/nix/nix.conf` 的設定並 FAIL。
2. 從 GitHub releases 直接下載釘版的 `nix-installer-aarch64-darwin`（版本與 sha256 見 `env/versions.mk`），快取在 `.tools/nix-installer/<版本>/`。下載可續傳、會自動重試，沒有速度門檻；中斷時重跑 `make nix-install` 會從斷點接續。
3. 驗證 sha256，不符就 FAIL 並刪除壞檔。
4. 執行 `install --no-confirm`，同時寫入 FOSSi binary cache 與 flakes 設定。安裝程式會自己用 sudo 提權，並要求輸入密碼；Nix 本體已內含在安裝程式裡，安裝時不會再下載。
5. 安裝後檢查 `nix` 執行檔與 cache 設定都存在，才印 PASS。

為什麼不用官方的一行指令：官方啟動 script 下載主程式時，若 15 秒內平均低於 250 KB/s 就會中止。2026-10-03 實測本機到 GitHub releases 約 135 KB/s，因此第一次安裝失敗（`curl: (28) Operation too slow`）。

指令出處：[LibreLane macOS 安裝文件](https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html)。
**裝完後關掉所有終端機視窗再開新的。**

## 3. 安裝 Nix 之後：`make flow-setup`（使用者或 Claude 都可以執行）

```bash
make env-check
make flow-setup              # 第一次約 10 分鐘以上，會下載 sky130A PDK
```

`make flow-setup`（`env/setup_flow.sh`）做的事：

1. 把 LibreLane `3.0.14` clone 到 `.tools/librelane`（gitignore），並確認 commit 與 `env/versions.mk` 一致。
2. 進入 LibreLane 的 nix-shell，執行 `librelane --smoke-test`（過程中由 ciel 下載釘版的 sky130A PDK）；log 在 `runs/flow_setup/smoke_test.log`。
3. 把 nix-shell 內 Yosys、OpenROAD、Magic、KLayout、Netgen、Verilator、LibreLane 的版本寫到 `runs/flow_setup/versions.txt`，用來更新 `toolchain.md` §2。

之後依 project-plan.md §8 Phase 0：重跑 `librelane-ci-designs/test_sram_macro` 當 golden、確認 PDK 內 SRAM LEF 含 `FOREIGN`、執行 `make env-check-flow`。
