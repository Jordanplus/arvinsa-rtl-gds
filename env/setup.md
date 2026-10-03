# Phase 0 環境建置

狀態（2026-10-03）：本機工具與釘版 IP 已就緒（`make env-check` PASS）；**Nix、LibreLane、sky130A PDK 尚未安裝**。

## 1. 已就緒（不需 Nix）

| 項目 | 版本 |
|---|---|
| Verilator | 5.050 |
| Icarus Verilog | 13.0 |
| Yosys（只做本機 sanity check，正式流程用 LibreLane 內建版本） | 0.69 |
| riscv64-elf-gcc | 16.1，rv32 multilib 可用，無 newlib |
| Python | 3.14（需 ≥ 3.11，只用標準函式庫） |
| GNU make | 3.81（macOS 內建；Makefile 已相容） |

釘版資訊見 `env/versions.mk`。

## 2. 需要使用者執行：安裝 Nix（需要 sudo 密碼）

安裝程式會建立 `/nix` APFS volume 與 build 使用者，必須輸入管理者密碼，所以要在自己的終端機執行：

```bash
curl --proto '=https' --tlsv1.2 -fsSL https://artifacts.nixos.org/nix-installer | sh -s -- install --no-confirm --extra-conf "
    extra-substituters = https://nix-cache.fossi-foundation.org
    extra-trusted-public-keys = nix-cache.fossi-foundation.org:3+K59iFwXqKsL7BNu6Guy0v+uTlwsxYQxjspXzqLYQs=
    extra-experimental-features = nix-command flakes
"
```

出處：[LibreLane macOS 安裝文件](https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html)。裝完後關掉所有終端機再重開。

## 3. 安裝 Nix 之後（可由 Claude 接手）

```bash
git clone https://github.com/librelane/librelane ~/claude_prjs/librelane
cd ~/claude_prjs/librelane && git checkout 3.0.14
nix-shell                      # 第一次約 10 分鐘，走 FOSSi binary cache
librelane --smoke-test         # 會用 ciel 下載 sky130A（PDK hash 見 env/versions.mk）
```

接著依 project-plan.md §8 Phase 0：重跑 `librelane-ci-designs/test_sram_macro` 當 golden、確認 PDK 內 SRAM LEF 含 `FOREIGN`、執行 `make env-check-flow`。
