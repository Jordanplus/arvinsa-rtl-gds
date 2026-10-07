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
check_tool ngspice   "ngspice --version 2>&1 | sed -n 's/.*ngspice-\([0-9]*\).*/\1/p'" "$(pin NGSPICE_MIN)"
if command -v c++ >/dev/null 2>&1; then ok "c++ (for Verilator --binary): $(c++ --version 2>&1 | head -1)"; else bad "c++ not found (install Xcode Command Line Tools: xcode-select --install)"; fi
if python3 -c 'import tomllib' 2>/dev/null; then ok "python3 tomllib"; else bad "python3 tomllib missing"; fi
if "$(pin RISCV_PREFIX)gcc" -print-multi-lib | grep -q 'rv32im/ilp32'; then ok "riscv gcc multilib rv32im/ilp32"; else bad "riscv gcc lacks rv32im/ilp32 multilib"; fi

echo "== Pinned IP =="
want=$(pin PICORV32_COMMIT)
have=$(git -C third_party/picorv32 rev-parse HEAD 2>/dev/null || echo none)
if [ "$have" = "$want" ]; then ok "picorv32 submodule @ ${want:0:12}"; else bad "picorv32 submodule is ${have:0:12}, expected ${want:0:12} (run: git submodule update --init)"; fi
f="ip/sram/$(pin SRAM_MACRO)/upstream/$(pin SRAM_MACRO).v"
sum=$(shasum -a 256 "$f" 2>/dev/null | cut -d' ' -f1 || echo none)
if [ "$sum" = "$(pin SRAM_MODEL_SHA256)" ]; then ok "SRAM model sha256 matches"; else bad "SRAM model sha256 mismatch: $f"; fi
simf="ip/sram/$(pin SRAM_MACRO)/sim/$(pin SRAM_MACRO).v"
if python3 ip/sram/gen_sim_model.py "$f" "$simf" --check >/dev/null; then ok "SRAM sim model regenerates identically"; else bad "SRAM sim model is stale: run ip/sram/gen_sim_model.py"; fi

echo "== toolchain.md =="
if python3 env/check_toolchain_doc.py; then :; else fail=1; fi

echo "== RTL-to-GDS flow (Phase 0, needs Nix) =="
flow_missing=0
if command -v nix >/dev/null 2>&1; then ok "nix: $(nix --version)"
elif [ -x /nix/var/nix/profiles/default/bin/nix ]; then ok "nix: $(/nix/var/nix/profiles/default/bin/nix --version) (not on this shell's PATH; open a new terminal)"
else pend "nix not installed (run: make nix-install)"; flow_missing=1; fi
ll_dir="${LIBRELANE_DIR:-.tools/librelane}"
ll_have=$(git -C "$ll_dir" rev-parse HEAD 2>/dev/null || echo none)
if [ "$ll_have" = "$(pin LIBRELANE_COMMIT)" ]; then
  ok "LibreLane $(pin LIBRELANE_TAG) clone at $ll_dir (tools run inside its nix-shell)"
  if [ "$FLOW_STRICT" = 1 ]; then
    # Strict mode also starts the nix-shell once and asks LibreLane for its version.
    llv=$(cd "$ll_dir" && PATH="/nix/var/nix/profiles/default/bin:$PATH" nix-shell --run 'librelane --version' 2>/dev/null | head -1 || true)
    case "$llv" in *"$(pin LIBRELANE_TAG)"*) ok "librelane --version in nix-shell: $llv";; *) bad "librelane --version in nix-shell gave '$llv'";; esac
  fi
elif [ "$ll_have" = none ]; then pend "LibreLane not set up (run: make flow-setup)"; flow_missing=1
else bad "LibreLane at $ll_dir is $ll_have, expected $(pin LIBRELANE_COMMIT)"; fi
pdk_dir="${PDK_ROOT:-$HOME/.ciel}/$(pin PDK)"
if [ -d "$pdk_dir" ]; then
  ok "PDK dir: $pdk_dir"
  # The PDK must be the version pinned for LibreLane, and its SRAM macro must match our pinned copy.
  case "$(cd "$pdk_dir" && pwd -P)" in
    */versions/"$(pin SKY130_PDK_HASH)"/*) ok "PDK version $(pin SKY130_PDK_HASH | cut -c1-12)";;
    *) bad "PDK at $pdk_dir is not version $(pin SKY130_PDK_HASH) (run: make pdk-fetch)";;
  esac
  sram_ref="$pdk_dir/libs.ref/sky130_sram_macros"
  if grep -q "^[[:space:]]*FOREIGN $(pin SRAM_MACRO) " "$sram_ref/lef/$(pin SRAM_MACRO).lef" 2>/dev/null; then
    ok "PDK SRAM LEF has FOREIGN"
  else
    bad "PDK SRAM LEF missing or without FOREIGN: $sram_ref/lef/$(pin SRAM_MACRO).lef"
  fi
  psum=$(shasum -a 256 "$sram_ref/verilog/$(pin SRAM_MACRO).v" 2>/dev/null | cut -d' ' -f1 || echo none)
  if [ "$psum" = "$(pin SRAM_MODEL_SHA256)" ]; then ok "PDK SRAM model == pinned ip/sram copy"; else bad "PDK SRAM model differs from the pinned ip/sram copy"; fi
else
  pend "PDK not found at $pdk_dir (run: make pdk-fetch)"; flow_missing=1
fi
# xPack toolchain with newlib, needed by make core-hazard3 (Phase 5, ADR-0011). A clean worktree has
# no .tools/: XPACK_DIR points at an installed copy, like LIBRELANE_DIR. Strict (FAIL) only with --flow
# and CPU=hazard3 (make regress), where core-hazard3 needs it; otherwise reported.
xp_dir="${XPACK_DIR:-.tools/xpack-riscv-none-elf-gcc-$(pin XPACK_RISCV_VERSION)}"
xp_want="$(pin XPACK_RISCV_VERSION | cut -d- -f1)"
xp_have=$("$xp_dir/bin/riscv-none-elf-gcc" -dumpversion 2>/dev/null || echo none)
if [ "$xp_have" = "$xp_want" ]; then ok "xPack riscv-none-elf-gcc $xp_have at $xp_dir"
elif [ "$FLOW_STRICT" = 1 ] && [ "${CPU:-picorv32}" = hazard3 ]; then
  bad "xPack riscv-none-elf-gcc $xp_want not at $xp_dir (found: $xp_have; run: make xpack-fetch, or set XPACK_DIR)"
else pend "xPack riscv-none-elf-gcc $xp_want not at $xp_dir (needed by make core-hazard3; run: make xpack-fetch)"; fi
if [ "$FLOW_STRICT" = 1 ] && [ "$flow_missing" = 1 ]; then fail=1; fi

echo
if [ "$fail" = 0 ]; then echo "env-check: PASS"; else echo "env-check: FAIL"; exit 1; fi
