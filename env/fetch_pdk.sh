#!/usr/bin/env bash
# make pdk-fetch: install the pinned sky130 PDK (ciel's default library set) into ${PDK_ROOT:-~/.ciel}.
# The tarballs are downloaded with curl (all in parallel, resumable, sha256-checked against
# env/sky130_pdk_assets.sha256) into .tools/pdk-cache/, then ciel installs them from a local
# mirror through its documented --data-source option. Why not let LibreLane/ciel download:
# ciel uses one connection and cannot resume, and on this network (50-175 KB/s per connection
# to GitHub, measured 2026-10-03) an interruption restarts the whole ~340 MB.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
HASH="$(pin SKY130_PDK_HASH)"
PDK_DIR_ROOT="${PDK_ROOT:-$HOME/.ciel}"
LL_DIR="${LIBRELANE_DIR:-$ROOT/.tools/librelane}"
CACHE="$ROOT/.tools/pdk-cache/sky130-$HASH"
SUMS="$ROOT/env/sky130_pdk_assets.sha256"
BASE="https://github.com/fossi-foundation/ciel-releases/releases/download/sky130-$HASH"
VERSION_DIR="$PDK_DIR_ROOT/ciel/sky130/versions/$HASH"
LIBS="sky130_fd_io sky130_fd_pr sky130_fd_sc_hd sky130_fd_sc_hvl sky130_ml_xx_hd sky130_sram_macros"

installed() {
  local lib
  [ "$(cd "$PDK_DIR_ROOT/sky130A" 2>/dev/null && pwd -P)" = "$(cd "$VERSION_DIR/sky130A" 2>/dev/null && pwd -P)" ] || return 1
  [ -d "$VERSION_DIR/sky130A/libs.tech" ] || return 1
  for lib in $LIBS; do [ -d "$VERSION_DIR/sky130A/libs.ref/$lib" ] || return 1; done
}

if installed; then
  echo "pdk-fetch: PASS - sky130A $HASH already installed at $PDK_DIR_ROOT"
  exit 0
fi

if ! command -v nix-shell >/dev/null 2>&1; then
  if [ -x /nix/var/nix/profiles/default/bin/nix-shell ]; then
    PATH="/nix/var/nix/profiles/default/bin:$PATH"
  else
    echo "pdk-fetch: FAIL - Nix is not installed. Run: make nix-install"
    exit 1
  fi
fi
if [ ! -d "$LL_DIR/.git" ]; then
  echo "pdk-fetch: FAIL - LibreLane not found at $LL_DIR (ciel comes from its nix-shell). Run: make flow-setup"
  exit 1
fi

mkdir -p "$CACHE"
have_ok() { (cd "$CACHE" && [ -f "$1" ] && grep "  $1\$" "$SUMS" | shasum -a 256 -c --status); }

# 1. Parallel, resumable downloads into <file>.part; a file is moved into place only after its sha256 matches.
pids=""
for f in $(awk '{print $2}' "$SUMS"); do
  if have_ok "$f"; then continue; fi
  curl -fL --retry 10 --retry-delay 5 --retry-all-errors -C - -sS -o "$CACHE/$f.part" "$BASE/$f" \
    > "$CACHE/$f.log" 2>&1 &
  pids="$pids $!"
done
if [ -n "$pids" ]; then
  echo "pdk-fetch: downloading $(echo $pids | wc -w | tr -d ' ') tarballs in parallel into $CACHE"
  while [ -n "$(jobs -r)" ]; do
    sleep 30
    echo "pdk-fetch: $(du -sk "$CACHE" | awk '{printf "%.0f", $1/1024}') MiB in cache"
  done
  rc=0
  for p in $pids; do wait "$p" || rc=1; done
  if [ "$rc" != 0 ]; then
    echo "pdk-fetch: FAIL - a download failed (rerun to resume); logs: $CACHE/*.log"
    exit 1
  fi
fi
for f in $(awk '{print $2}' "$SUMS"); do
  if have_ok "$f"; then continue; fi
  if [ -f "$CACHE/$f.part" ] && (cd "$CACHE" && grep "  $f\$" "$SUMS" | sed 's/\.tar\.zst$/.tar.zst.part/' | shasum -a 256 -c --status); then
    mv "$CACHE/$f.part" "$CACHE/$f"
  else
    rm -f "$CACHE/$f.part"
    echo "pdk-fetch: FAIL - sha256 mismatch for $f (deleted; rerun to download again)"
    exit 1
  fi
done
echo "pdk-fetch: all tarballs present and sha256-verified"

# 2. Local mirror in ciel's static-web layout: <base>/sky130/<hash>/manifest.json.
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
mkdir -p "$CACHE/sky130/$HASH"
python3 - "$SUMS" "$PORT" > "$CACHE/sky130/$HASH/manifest.json" <<'PY'
import json, sys
names = [line.split()[1] for line in open(sys.argv[1]) if line.strip()]
assets = [{"content": n[:-len(".tar.zst")], "filename": n,
           "url": f"http://127.0.0.1:{sys.argv[2]}/{n}"} for n in names]
print(json.dumps({"version": 1, "assets": assets}, indent=1))
PY
python3 -m http.server --bind 127.0.0.1 --directory "$CACHE" "$PORT" > "$CACHE/http.log" 2>&1 &
SRV=$!
trap 'kill "$SRV" 2>/dev/null || true' EXIT
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -fs "http://127.0.0.1:$PORT/sky130/$HASH/manifest.json" >/dev/null && break
  sleep 1
done

# 3. ciel only checks that library directories exist, so a half-unpacked earlier attempt would be
#    taken as installed: start this version from scratch.
rm -rf "$VERSION_DIR"
echo "pdk-fetch: installing sky130 $HASH with ciel from the local mirror"
(cd "$LL_DIR" && nix-shell --run "python3 -m ciel enable --pdk-family sky130 --pdk-root '$PDK_DIR_ROOT' --data-source 'static-web:http://127.0.0.1:$PORT' $HASH") \
  > "$CACHE/ciel_enable.log" 2>&1 || {
  echo "pdk-fetch: FAIL - ciel enable failed; see $CACHE/ciel_enable.log"
  tail -20 "$CACHE/ciel_enable.log"
  exit 1
}

if installed; then
  echo "pdk-fetch: PASS - sky130A $HASH installed at $PDK_DIR_ROOT ($(du -sh "$VERSION_DIR" | cut -f1))"
else
  echo "pdk-fetch: FAIL - ciel finished but $VERSION_DIR is incomplete or $PDK_DIR_ROOT/sky130A does not point to it"
  exit 1
fi
