#!/usr/bin/env bash
# make env-check: verify local tools and pinned IP for Phase 1 (strict),
# and report the LibreLane/Nix flow environment (strict only with --flow).
set -euo pipefail
cd "$(dirname "$0")/.."

FLOW_STRICT=0
[ "${1:-}" = "--flow" ] && FLOW_STRICT=1

fail=0
ok()   { printf '  [OK]      %s\n' "$1"; }
bad()  { printf '  [FAIL]    %s\n' "$1"; fail=1; }
pend() { printf '  [PENDING] %s\n' "$1"; }

ver_ge() { python3 - "$1" "$2" <<'PY'
import re, sys
def parse(v): return tuple(int(x) for x in re.findall(r'\d+', v)[:3])
sys.exit(0 if parse(sys.argv[1]) >= parse(sys.argv[2]) else 1)
PY
}
pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }

echo "== Local tools (Phase 1) =="
check_tool() { # name, version-command, min
  local name="$1" cmd="$2" min="$3" v
  if ! command -v "$name" >/dev/null 2>&1; then bad "$name not found"; return; fi
  v=$(eval "$cmd" 2>&1 | head -1 || true)
  if ver_ge "$v" "$min"; then ok "$name: $v (>= $min)"; else bad "$name: $v (< $min)"; fi
}
check_tool verilator "verilator --version" "$(pin VERILATOR_MIN)"
check_tool iverilog  "iverilog -V 2>&1 | sed -n 's/.*version \([0-9.]*\).*/\1/p'" "$(pin ICARUS_MIN)"
check_tool yosys     "yosys -V | sed -n 's/^Yosys \([0-9.]*\).*/\1/p'" "$(pin YOSYS_MIN)"
check_tool "$(pin RISCV_PREFIX)gcc" "$(pin RISCV_PREFIX)gcc -dumpversion" "$(pin RISCV_GCC_MIN)"
check_tool python3   "python3 -c 'import platform; print(platform.python_version())'" "$(pin PYTHON_MIN)"
if python3 -c 'import tomllib' 2>/dev/null; then ok "python3 tomllib"; else bad "python3 tomllib missing"; fi
if "$(pin RISCV_PREFIX)gcc" -print-multi-lib | grep -q 'rv32im/ilp32'; then ok "riscv gcc multilib rv32im/ilp32"; else bad "riscv gcc lacks rv32im/ilp32 multilib"; fi

echo "== Pinned IP =="
want=$(pin PICORV32_COMMIT)
have=$(git -C third_party/picorv32 rev-parse HEAD 2>/dev/null || echo none)
if [ "$have" = "$want" ]; then ok "picorv32 submodule @ ${want:0:12}"; else bad "picorv32 submodule is ${have:0:12}, expected ${want:0:12} (run: git submodule update --init)"; fi
f="ip/sram/$(pin SRAM_MACRO)/upstream/$(pin SRAM_MACRO).v"
sum=$(shasum -a 256 "$f" 2>/dev/null | cut -d' ' -f1 || echo none)
if [ "$sum" = "$(pin SRAM_MODEL_SHA256)" ]; then ok "SRAM model sha256 matches"; else bad "SRAM model sha256 mismatch: $f"; fi

echo "== toolchain.md =="
if python3 env/check_toolchain_doc.py; then :; else fail=1; fi

echo "== RTL-to-GDS flow (Phase 0, needs Nix) =="
flow_missing=0
if command -v nix >/dev/null 2>&1; then ok "nix: $(nix --version)"; else pend "nix not installed (see env/setup.md)"; flow_missing=1; fi
if command -v librelane >/dev/null 2>&1; then ok "librelane: $(librelane --version 2>&1 | head -1)"; else pend "librelane not on PATH (run inside the LibreLane nix-shell)"; flow_missing=1; fi
pdk_dir="${PDK_ROOT:-$HOME/.ciel}/$(pin PDK)"
if [ -d "$pdk_dir" ]; then ok "PDK dir: $pdk_dir"; else pend "PDK not found at $pdk_dir"; flow_missing=1; fi
if [ "$FLOW_STRICT" = 1 ] && [ "$flow_missing" = 1 ]; then fail=1; fi

echo
if [ "$fail" = 0 ]; then echo "env-check: PASS"; else echo "env-check: FAIL"; exit 1; fi
