#!/usr/bin/env bash
# make harden-soc: Phase 3 (project-plan.md §8). Hardens soc_top with the prebuilt SRAM macro using
# the pinned LibreLane Classic flow, then checks the signoff metrics.
# CPU=picorv32 (default) or CPU=hazard3 (Phase 5, ADR-0011) picks the CPU of soc_top:
#   CPU       config                          RTL file list     run tag (runs/<tag>)  limits / golden
#   picorv32  pnr/soc_top/config.json         rtl/rtl.f         soc_top               soc_top
#   hazard3   pnr/soc_top/config_hazard3.json rtl/rtl_hazard3.f soc_top_hazard3       soc_top_hazard3
#   config_hazard3.json differs from config.json only in VERILOG_FILES, VERILOG_INCLUDE_DIRS and
#   VERILOG_DEFINES (check_inputs.py row cpu_config): the flow settings are the same.
#   1. pnr/soc_top/check_inputs.py     : config VERILOG_FILES == the RTL file list, SRAM .lib (char/) up to date
#   2. LibreLane run                   : runs/<tag> (design dir = repo root)
#   3. signoff/scripts/check_signoff.py: limits in signoff/limits/<tag>.toml and the golden run in
#                                        signoff/golden/<tag>/metrics.json
#   4. pnr/soc_top/sram_drc_alone.py   : Magic DRC of the SRAM alone (about 2.5 minutes), the
#                                        reference for the Magic DRC comparison of check_soc.py
#      pnr/soc_top/check_soc.py        : SRAM placement, port 1 tie-off, disconnected pins,
#                                        STA check_setup, min pulse width and period, Magic DRC
#                                        inside the SRAM only where the SRAM alone has it
#   5. check_inputs.py --resolved      : the run really used rtl/rtl.f, the SRAM .lib and the antenna LEF
#   0/6. signoff/scripts/provenance.py : before and after the run: committed working tree, pinned
#                                        LibreLane and PDK (project-plan.md §7.2)
# Checker outputs go to runs/<tag>_signoff/; the verdict line is also written to result.txt, which
# the later steps (eqy-soc, gl-soc) require to be `harden-soc: PASS`.
# Requires `make flow-setup` (Nix, LibreLane, PDK).
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$(pwd)"

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
PDK="$(pin PDK)"
SCL="$(pin STD_CELL_LIBRARY)"
LL_DIR="${LIBRELANE_DIR:-$ROOT/.tools/librelane}"
CPU="${CPU:-picorv32}"
case "$CPU" in
  picorv32) TAG=soc_top; CONFIG="$ROOT/pnr/soc_top/config.json" ;;
  hazard3)  TAG=soc_top_hazard3; CONFIG="$ROOT/pnr/soc_top/config_hazard3.json" ;;
  *) echo "harden-soc: FAIL - CPU must be picorv32 or hazard3 (got '$CPU')"; exit 1 ;;
esac
RUN_DIR="$ROOT/runs/$TAG"
OUT="$ROOT/runs/${TAG}_signoff"
LIMITS="$ROOT/signoff/limits/$TAG.toml"
GOLDEN="$ROOT/signoff/golden/$TAG/metrics.json"

if ! command -v nix-shell >/dev/null 2>&1; then
  if [ -x /nix/var/nix/profiles/default/bin/nix-shell ]; then
    PATH="/nix/var/nix/profiles/default/bin:$PATH"
  else
    echo "harden-soc: FAIL - Nix is not installed. Run: make nix-install"
    exit 1
  fi
fi
if [ ! -d "$LL_DIR/.git" ]; then
  echo "harden-soc: FAIL - LibreLane not found at $LL_DIR. Run: make flow-setup"
  exit 1
fi

# The previous run of this tag is kept as $RUN_DIR.prev and $OUT.prev (keep_prev_run).
source pnr/librelane_flow.sh
keep_prev_run "$RUN_DIR" "$OUT"
mkdir -p "$OUT"

echo "harden-soc: source tracking (committed working tree, pinned LibreLane and PDK)"
python3 signoff/scripts/provenance.py --record "$OUT/provenance.json" | tee "$OUT/provenance.txt" || true
if ! grep -q '^provenance: PASS$' "$OUT/provenance.txt"; then
  echo "harden-soc: provenance FAIL - this run cannot be a signoff run (the verdict will be FAIL); the flow and the other checks still run"
fi

echo "harden-soc: CPU=$CPU, inputs ($(basename "$CONFIG") vs the RTL file list, SRAM .lib vs char.json and the PDK .lib)"
python3 pnr/soc_top/check_inputs.py --cpu "$CPU" | tee "$OUT/inputs.txt"
grep -q '^soc-inputs: PASS$' "$OUT/inputs.txt"

echo "harden-soc: running LibreLane Classic flow on soc_top with $CPU (about 20-30 minutes on this machine); full log: $RUN_DIR/flow.log"
librelane_flow harden-soc "$CONFIG"
[ "$flow_attempts" -gt 1 ] && echo "harden-soc: LibreLane needed $flow_attempts attempts (known GRT-0229 retry, see $OUT/retries.txt)"
(cd "$LL_DIR" && nix-shell --run "python3 -m librelane.state latest '$RUN_DIR' --extract-metrics-to '$OUT/metrics.json'") \
  > "$OUT/extract.log" 2>&1 || true

if [ "$flow_rc" != 0 ]; then
  echo "harden-soc: FAIL - LibreLane exited with $flow_rc; see $OUT/console.log"
  tail -20 "$OUT/console.log"
  exit 1
fi
if [ ! -s "$OUT/metrics.json" ]; then
  echo "harden-soc: FAIL - no metrics extracted; see $OUT/extract.log"
  exit 1
fi

python3 signoff/scripts/check_signoff.py "$OUT/metrics.json" "$LIMITS" "$GOLDEN" | tee "$OUT/signoff.txt" || true
python3 pnr/soc_top/sram_drc_alone.py "$RUN_DIR" "$OUT/sram_drc_alone" | tee "$OUT/sram_drc_alone.txt" || true
python3 pnr/soc_top/check_soc.py "$RUN_DIR" --sram-drc "$OUT/sram_drc_alone/step/reports/drc.magic.rpt" --config "$CONFIG" | tee "$OUT/soc_checks.txt" || true
python3 pnr/soc_top/check_inputs.py --cpu "$CPU" --resolved "$RUN_DIR/resolved.json" > "$OUT/inputs_resolved.txt" 2>&1 || true
tail -1 "$OUT/inputs_resolved.txt"
python3 signoff/scripts/provenance.py --verify "$OUT/provenance.json" --resolved "$RUN_DIR/resolved.json" \
  > "$OUT/provenance_end.txt" 2>&1 || true
tail -1 "$OUT/provenance_end.txt"
if grep -q '^signoff: PASS$' "$OUT/signoff.txt" && grep -q '^soc-checks: PASS$' "$OUT/soc_checks.txt" \
   && grep -q '^soc-inputs: PASS$' "$OUT/inputs_resolved.txt" \
   && grep -q '^provenance: PASS$' "$OUT/provenance.txt" && grep -q '^provenance: PASS$' "$OUT/provenance_end.txt"; then
  echo "harden-soc: PASS" | tee "$OUT/result.txt"
else
  echo "harden-soc: FAIL" | tee "$OUT/result.txt"
  exit 1
fi
