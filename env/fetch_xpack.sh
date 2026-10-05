#!/usr/bin/env bash
# make xpack-fetch: install the pinned xPack RISC-V toolchain (riscv-none-elf-gcc with newlib; Phase 5,
# ADR-0011) into .tools/xpack-riscv-none-elf-gcc-<version>/. One ~400 MB tarball from GitHub: on this
# network one connection gets 50-175 KB/s and may drop (env/fetch_pdk.sh), so it is fetched as RANGES
# byte ranges in parallel. Each range is resumable: curl writes the bytes it got to a temporary file,
# which is appended to the range's part, and the next attempt asks for the rest. The joined file must
# have XPACK_RISCV_SIZE bytes and the sha256 XPACK_RISCV_SHA256 of env/versions.mk before it is unpacked.
set -euo pipefail
cd "$(dirname "$0")/.."
pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
VER="$(pin XPACK_RISCV_VERSION)"; SHA="$(pin XPACK_RISCV_SHA256)"; SIZE="$(pin XPACK_RISCV_SIZE)"
NAME="xpack-riscv-none-elf-gcc-$VER-darwin-arm64.tar.gz"
URL="https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v$VER/$NAME"
DEST=".tools/xpack-riscv-none-elf-gcc-$VER"
CACHE=".tools/xpack-cache"
RANGES=8

if [ -x "$DEST/bin/riscv-none-elf-gcc" ]; then
  echo "xpack-fetch: PASS - $DEST already installed ($("$DEST/bin/riscv-none-elf-gcc" --version | head -1))"
  exit 0
fi
mkdir -p "$CACHE"
sha_ok() { echo "$SHA  $1" | shasum -a 256 -c --status; }
size_of() { if [ -f "$1" ]; then stat -f %z "$1"; else echo 0; fi; }

fetch_range() {  # fetch_range <part> <first byte> <last byte>
  local part="$1" a="$2" b="$3" have tries=0
  while :; do
    have=$(size_of "$part")
    [ "$have" -ge $((b - a + 1)) ] && return 0
    tries=$((tries + 1))
    [ "$tries" -gt 100 ] && return 1
    curl -fL -sS --connect-timeout 30 --speed-time 60 --speed-limit 500 -r "$((a + have))-$b" -o "$part.tmp" "$URL" \
      2>> "$part.log" || sleep 5
    if [ -f "$part.tmp" ]; then cat "$part.tmp" >> "$part"; rm -f "$part.tmp"; fi
  done
}

if ! { [ -f "$CACHE/$NAME" ] && sha_ok "$CACHE/$NAME"; }; then
  rm -f "$CACHE/$NAME"
  chunk=$(( (SIZE + RANGES - 1) / RANGES ))
  pids=""
  for i in $(seq 0 $((RANGES - 1))); do
    a=$((i * chunk)); b=$(( (i + 1) * chunk - 1 )); [ "$b" -ge "$SIZE" ] && b=$((SIZE - 1))
    fetch_range "$CACHE/$NAME.part$i" "$a" "$b" &
    pids="$pids $!"
  done
  echo "xpack-fetch: downloading $NAME ($((SIZE / 1048576)) MiB) as $RANGES ranges into $CACHE"
  while [ -n "$(jobs -r)" ]; do
    sleep 30
    got=0; for i in $(seq 0 $((RANGES - 1))); do got=$((got + $(size_of "$CACHE/$NAME.part$i"))); done
    echo "xpack-fetch: $((got / 1048576)) / $((SIZE / 1048576)) MiB"
  done
  rc=0; for p in $pids; do wait "$p" || rc=1; done
  [ "$rc" = 0 ] || { echo "xpack-fetch: FAIL - a range did not finish (rerun to resume); logs $CACHE/*.log"; exit 1; }
  for i in $(seq 0 $((RANGES - 1))); do cat "$CACHE/$NAME.part$i"; done > "$CACHE/$NAME"
  if [ "$(size_of "$CACHE/$NAME")" != "$SIZE" ] || ! sha_ok "$CACHE/$NAME"; then
    rm -f "$CACHE/$NAME" "$CACHE/$NAME".part*
    echo "xpack-fetch: FAIL - size or sha256 mismatch (parts deleted; rerun to download again)"
    exit 1
  fi
  rm -f "$CACHE/$NAME".part* "$CACHE/$NAME".part*.log
fi
rm -rf "$DEST.tmp"; mkdir -p "$DEST.tmp"
tar -xzf "$CACHE/$NAME" -C "$DEST.tmp"
mv "$DEST.tmp/xpack-riscv-none-elf-gcc-$VER" "$DEST"
rmdir "$DEST.tmp"
echo "xpack-fetch: PASS - $DEST ($("$DEST/bin/riscv-none-elf-gcc" --version | head -1))"
