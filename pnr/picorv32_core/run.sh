#!/usr/bin/env bash
# make harden-core: Phase 2 (project-plan.md §8). Hardens PicoRV32 alone (no SRAM) with the
# pinned LibreLane Classic flow, using the SoC's CPU parameters, then checks the signoff metrics.
#   1. pnr/picorv32_core/cpu_params.py : config.json SYNTH_PARAMETERS == soc_top u_cpu parameters
#   2. LibreLane run                   : runs/picorv32_core (tag picorv32_core, design dir = repo root)
#   3. signoff/scripts/check_signoff.py: limits in signoff/limits/picorv32_core.toml and the golden
#                                        run in signoff/golden/picorv32_core/metrics.json
#   4. pnr/picorv32_core/check_disconnected.py: the disconnected pins are exactly the unused PCPI inputs
#   5. cpu_params.py --resolved           : the run really used config.json's SYNTH_PARAMETERS
# Checker outputs go to runs/picorv32_core_signoff/. Requires `make flow-setup` (Nix, LibreLane, PDK).
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$(pwd)"

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
PDK="$(pin PDK)"
SCL="$(pin STD_CELL_LIBRARY)"
LL_DIR="${LIBRELANE_DIR:-$ROOT/.tools/librelane}"
TAG=picorv32_core
RUN_DIR="$ROOT/runs/$TAG"
OUT="$ROOT/runs/${TAG}_signoff"
LIMITS="$ROOT/signoff/limits/picorv32_core.toml"
GOLDEN="$ROOT/signoff/golden/picorv32_core/metrics.json"

if ! command -v nix-shell >/dev/null 2>&1; then
  if [ -x /nix/var/nix/profiles/default/bin/nix-shell ]; then
    PATH="/nix/var/nix/profiles/default/bin:$PATH"
  else
    echo "harden-core: FAIL - Nix is not installed. Run: make nix-install"
    exit 1
  fi
fi
if [ ! -d "$LL_DIR/.git" ]; then
  echo "harden-core: FAIL - LibreLane not found at $LL_DIR. Run: make flow-setup"
  exit 1
fi

# Only these two run directories are removed.
rm -rf "$RUN_DIR" "$OUT"
mkdir -p "$OUT"

echo "harden-core: CPU parameters (config.json vs rtl/soc/soc_top.v u_cpu)"
python3 pnr/picorv32_core/cpu_params.py | tee "$OUT/cpu_params.txt"
grep -q '^cpu-params: PASS$' "$OUT/cpu_params.txt"

echo "harden-core: running LibreLane Classic flow on picorv32 (about 12-15 minutes on this machine); full log: $RUN_DIR/flow.log"
flow_rc=0
(cd "$LL_DIR" && nix-shell --run "python3 -m librelane --run-tag '$TAG' --design-dir '$ROOT' --pdk '$PDK' --scl '$SCL' --condensed '$ROOT/pnr/picorv32_core/config.json'") \
  > "$OUT/console.log" 2>&1 || flow_rc=$?
(cd "$LL_DIR" && nix-shell --run "python3 -m librelane.state latest '$RUN_DIR' --extract-metrics-to '$OUT/metrics.json'") \
  > "$OUT/extract.log" 2>&1 || true

if [ "$flow_rc" != 0 ]; then
  echo "harden-core: FAIL - LibreLane exited with $flow_rc; see $OUT/console.log"
  tail -20 "$OUT/console.log"
  exit 1
fi
if [ ! -s "$OUT/metrics.json" ]; then
  echo "harden-core: FAIL - no metrics extracted; see $OUT/extract.log"
  exit 1
fi

python3 signoff/scripts/check_signoff.py "$OUT/metrics.json" "$LIMITS" "$GOLDEN" | tee "$OUT/signoff.txt" || true
python3 pnr/picorv32_core/check_disconnected.py "$RUN_DIR" | tee "$OUT/disconnected.txt" || true
python3 pnr/picorv32_core/cpu_params.py --resolved "$RUN_DIR/resolved.json" > "$OUT/cpu_params_resolved.txt" 2>&1 || true
tail -1 "$OUT/cpu_params_resolved.txt"
if grep -q '^signoff: PASS$' "$OUT/signoff.txt" && grep -q '^disconnected-pins: PASS$' "$OUT/disconnected.txt" \
   && grep -q '^cpu-params: PASS$' "$OUT/cpu_params_resolved.txt"; then
  echo "harden-core: PASS"
else
  echo "harden-core: FAIL"
  exit 1
fi
