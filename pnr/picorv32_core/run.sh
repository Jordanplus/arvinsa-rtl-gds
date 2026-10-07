#!/usr/bin/env bash
# make harden-core: Phase 2 (project-plan.md §8). Hardens PicoRV32 alone (no SRAM) with the
# pinned LibreLane Classic flow, using the SoC's CPU parameters, then checks the signoff metrics.
#   1. pnr/picorv32_core/cpu_params.py : config.json SYNTH_PARAMETERS == soc_top u_cpu parameters
#   2. LibreLane run                   : runs/picorv32_core (tag picorv32_core, design dir = repo root)
#   3. signoff/scripts/check_signoff.py: limits in signoff/limits/picorv32_core.toml and the golden
#                                        run in signoff/golden/picorv32_core/metrics.json
#   4. pnr/picorv32_core/check_disconnected.py: the disconnected pins are exactly the unused PCPI inputs
#   5. cpu_params.py --resolved           : the run really used config.json's SYNTH_PARAMETERS
#   0/6. signoff/scripts/provenance.py    : before and after the run: committed working tree, pinned
#                                           LibreLane and PDK (project-plan.md §7.2)
#   7. signoff/scripts/review_criteria.py --design picorv32_core: the signoff criteria were applied
#      (config settings in the run, the uncertainty every signoff path got, corners, checkers ran);
#      part 2 is Claude's review in criteria_review.md (CLAUDE.md rule 9; Phase 5 exit review: the
#      core harden had no review and the Stop hook did not ask for one)
# A LibreLane FAIL does not skip steps 3-7 (as pnr/soc_top/run.sh since Phase 5).
# Checker outputs go to runs/picorv32_core_signoff/; the verdict line is also written to result.txt,
# which the later steps (gl-core, eqy-core) require to be `harden-core: PASS`.
# Requires `make flow-setup` (Nix, LibreLane, PDK).
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

# The previous run of this tag is kept as $RUN_DIR.prev and $OUT.prev (keep_prev_run).
source pnr/librelane_flow.sh
keep_prev_run "$RUN_DIR" "$OUT"
mkdir -p "$OUT"

echo "harden-core: source tracking (committed working tree, pinned LibreLane and PDK)"
python3 signoff/scripts/provenance.py --record "$OUT/provenance.json" | tee "$OUT/provenance.txt" || true
if ! grep -q '^provenance: PASS$' "$OUT/provenance.txt"; then
  echo "harden-core: provenance FAIL - this run cannot be a signoff run (the verdict will be FAIL); the flow and the other checks still run"
fi

echo "harden-core: CPU parameters (config.json vs rtl/soc/soc_top.v u_cpu)"
python3 pnr/picorv32_core/cpu_params.py | tee "$OUT/cpu_params.txt"
grep -q '^cpu-params: PASS$' "$OUT/cpu_params.txt"

echo "harden-core: running LibreLane Classic flow on picorv32 (about 12-15 minutes on this machine); full log: $RUN_DIR/flow.log"
librelane_flow harden-core "$ROOT/pnr/picorv32_core/config.json"
[ "$flow_attempts" -gt 1 ] && echo "harden-core: LibreLane needed $flow_attempts attempts (known GRT-0229 retry, see $OUT/retries.txt)"
(cd "$LL_DIR" && nix-shell --run "python3 -m librelane.state latest '$RUN_DIR' --extract-metrics-to '$OUT/metrics.json'") \
  > "$OUT/extract.log" 2>&1 || true

if [ "$flow_rc" != 0 ]; then
  echo "harden-core: LibreLane exited with $flow_rc (the verdict will be FAIL); see $OUT/console.log"
  tail -20 "$OUT/console.log"
  echo "harden-core: the checkers still run on what the flow produced"
fi
if [ -s "$OUT/metrics.json" ]; then
  python3 signoff/scripts/check_signoff.py "$OUT/metrics.json" "$LIMITS" "$GOLDEN" | tee "$OUT/signoff.txt" || true
else
  echo "signoff: FAIL - no metrics extracted; see $OUT/extract.log" | tee "$OUT/signoff.txt"
fi
python3 pnr/picorv32_core/check_disconnected.py "$RUN_DIR" | tee "$OUT/disconnected.txt" || true
python3 pnr/picorv32_core/cpu_params.py --resolved "$RUN_DIR/resolved.json" > "$OUT/cpu_params_resolved.txt" 2>&1 || true
tail -1 "$OUT/cpu_params_resolved.txt"
python3 signoff/scripts/provenance.py --verify "$OUT/provenance.json" --resolved "$RUN_DIR/resolved.json" \
  > "$OUT/provenance_end.txt" 2>&1 || true
tail -1 "$OUT/provenance_end.txt"
python3 signoff/scripts/review_criteria.py --design picorv32_core --run "$RUN_DIR" --out "$OUT" \
  | tee "$OUT/criteria_review.txt" || true
if [ "$flow_rc" = 0 ] && grep -q '^signoff: PASS$' "$OUT/signoff.txt" && grep -q '^disconnected-pins: PASS$' "$OUT/disconnected.txt" \
   && grep -q '^cpu-params: PASS$' "$OUT/cpu_params_resolved.txt" && grep -q '^criteria-review: PASS$' "$OUT/criteria_review.txt" \
   && grep -q '^provenance: PASS$' "$OUT/provenance.txt" && grep -q '^provenance: PASS$' "$OUT/provenance_end.txt"; then
  echo "harden-core: PASS" | tee "$OUT/result.txt"
else
  echo "harden-core: FAIL" | tee "$OUT/result.txt"
  exit 1
fi
