#!/usr/bin/env bash
# make ci-sram-ref: Phase 0 golden run (project-plan.md §8). Re-runs the LibreLane CI design
# test_sram_macro (2 x sky130_sram_1kbyte macro, 25 ns) on this machine with the pinned LibreLane,
# then checks the metrics against fixed signoff values, the upstream LibreLane 3.0.14 CI run and
# this machine's golden run (signoff/golden/ci_sram_ref/, see README.md there). Requires `make flow-setup`.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$(pwd)"

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
CI_COMMIT="$(pin LIBRELANE_CI_COMMIT)"
PDK="$(pin PDK)"
SCL="$(pin STD_CELL_LIBRARY)"
LL_DIR="${LIBRELANE_DIR:-$ROOT/.tools/librelane}"
SRC="$ROOT/.tools/librelane-ci-designs"
OUT="$ROOT/runs/ci_sram_ref"
TAG="$PDK-$SCL"
GOLDEN="$ROOT/signoff/golden/ci_sram_ref/upstream.metrics.json"
LOCAL_GOLDEN="$ROOT/signoff/golden/ci_sram_ref/local.metrics.json"

if ! command -v nix-shell >/dev/null 2>&1; then
  if [ -x /nix/var/nix/profiles/default/bin/nix-shell ]; then
    PATH="/nix/var/nix/profiles/default/bin:$PATH"
  else
    echo "ci-sram-ref: FAIL - Nix is not installed. Run: make nix-install"
    exit 1
  fi
fi
if [ ! -d "$LL_DIR/.git" ]; then
  echo "ci-sram-ref: FAIL - LibreLane not found at $LL_DIR. Run: make flow-setup"
  exit 1
fi

# Fetch only test_sram_macro at the pinned commit (blobless clone + sparse checkout).
if [ ! -d "$SRC/.git" ]; then
  echo "ci-sram-ref: fetching librelane-ci-designs (test_sram_macro only)"
  git clone --quiet --filter=blob:none --no-checkout https://github.com/librelane/librelane-ci-designs "$SRC"
  git -C "$SRC" sparse-checkout set test_sram_macro
fi
# The pinned commit is not on every branch, so fetch it by SHA when the clone lacks it.
git -C "$SRC" cat-file -e "$CI_COMMIT^{commit}" 2>/dev/null || git -C "$SRC" fetch --quiet --filter=blob:none origin "$CI_COMMIT"
git -C "$SRC" -c advice.detachedHead=false checkout --quiet "$CI_COMMIT"
have="$(git -C "$SRC" rev-parse HEAD)"
if [ "$have" != "$CI_COMMIT" ]; then
  echo "ci-sram-ref: FAIL - $SRC is at $have, expected $CI_COMMIT"
  exit 1
fi

# LibreLane writes the run under the design directory, so run on a fresh copy inside runs/.
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$SRC/test_sram_macro" "$OUT/design"
RUN_DIR="$OUT/design/runs/$TAG"

echo "ci-sram-ref: running LibreLane Classic flow on test_sram_macro (about 3 minutes on this machine); log: $OUT/flow.log"
flow_rc=0
(cd "$LL_DIR" && nix-shell --run "python3 -m librelane --run-tag '$TAG' --pdk '$PDK' --scl '$SCL' --condensed '$OUT/design/config.json'") \
  > "$OUT/flow.log" 2>&1 || flow_rc=$?
(cd "$LL_DIR" && nix-shell --run "python3 -m librelane.state latest '$RUN_DIR' --extract-metrics-to '$OUT/metrics.json'") \
  > "$OUT/extract.log" 2>&1 || true

if [ "$flow_rc" != 0 ]; then
  echo "ci-sram-ref: FAIL - LibreLane exited with $flow_rc; see $OUT/flow.log"
  tail -20 "$OUT/flow.log"
  exit 1
fi
if [ ! -s "$OUT/metrics.json" ]; then
  echo "ci-sram-ref: FAIL - no metrics extracted; see $OUT/extract.log"
  exit 1
fi

python3 pnr/ci_sram_ref/check_metrics.py "$OUT/metrics.json" "$GOLDEN" "$LOCAL_GOLDEN" | tee "$OUT/check.txt"
grep -q '^ci-sram-ref: PASS$' "$OUT/check.txt"
