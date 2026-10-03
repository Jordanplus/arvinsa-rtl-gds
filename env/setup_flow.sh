#!/usr/bin/env bash
# make flow-setup: fetch LibreLane at the pinned tag, enter its nix-shell and run the smoke test
# (the smoke test downloads the pinned sky130A PDK with ciel). Requires `make nix-install` first.
# Tool versions inside the nix-shell are written to runs/flow_setup/versions.txt for toolchain.md.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
TAG="$(pin LIBRELANE_TAG)"
COMMIT="$(pin LIBRELANE_COMMIT)"
DIR="${LIBRELANE_DIR:-$ROOT/.tools/librelane}"
OUT="$ROOT/runs/flow_setup"

if ! command -v nix-shell >/dev/null 2>&1; then
  if [ -x /nix/var/nix/profiles/default/bin/nix-shell ]; then
    PATH="/nix/var/nix/profiles/default/bin:$PATH"
  else
    echo "flow-setup: FAIL - Nix is not installed. Run: make nix-install"
    exit 1
  fi
fi

if [ ! -d "$DIR/.git" ]; then
  echo "flow-setup: cloning LibreLane $TAG into $DIR"
  git clone --quiet --branch "$TAG" --depth 1 https://github.com/librelane/librelane "$DIR"
fi
have="$(git -C "$DIR" rev-parse HEAD)"
if [ "$have" != "$COMMIT" ]; then
  echo "flow-setup: FAIL - $DIR is at $have, expected $COMMIT (LibreLane $TAG)"
  exit 1
fi

mkdir -p "$OUT"
cd "$DIR"
echo "flow-setup: entering nix-shell (first run takes about 10 minutes) and running librelane --smoke-test"
nix-shell --run "librelane --smoke-test" > "$OUT/smoke_test.log" 2>&1 || {
  echo "flow-setup: FAIL - librelane --smoke-test failed; see $OUT/smoke_test.log"
  exit 1
}
nix-shell --run '
  for c in "yosys -V" "openroad -version" "magic --version" "klayout -v" "verilator --version" "librelane --version"; do
    printf "%s: " "$c"; $c 2>&1 | head -1 || echo "(not found)"
  done
  printf "netgen: "; echo quit | netgen -batch 2>&1 | grep -m1 -i "netgen" || echo "(not found)"
' > "$OUT/versions.txt" 2>&1 || true
echo "flow-setup: PASS - smoke test OK; log: $OUT/smoke_test.log"
echo "Tool versions (copy into toolchain.md §2):"
cat "$OUT/versions.txt"
