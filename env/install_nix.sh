#!/usr/bin/env bash
# make nix-install: install Nix with the FOSSi binary cache, as required by LibreLane on macOS.
#
# Equivalent to the LibreLane macOS guide command
#   curl ... https://artifacts.nixos.org/nix-installer | sh -s -- install --no-confirm --extra-conf "..."
# (https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html)
# but downloads the pinned nix-installer binary directly from GitHub releases. The official wrapper
# aborts when the download is slower than 250 KB/s for 15 s; this script resumes and retries instead,
# caches the binary in .tools/nix-installer/<version>/ and verifies the sha256 pinned in env/versions.mk.
# The installer binary embeds the Nix tarball and escalates itself with sudo (asks for your password).
#
# DRY_RUN=1   download + verify only, print the install command.
# NIX_INSTALLER_BASE_URL=<url>   optional mirror for the release directory.
set -euo pipefail
cd "$(dirname "$0")/.."

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
VERSION="$(pin NIX_INSTALLER_VERSION)"
SHA_PINNED="$(pin NIX_INSTALLER_SHA256_AARCH64_DARWIN)"
BASE_URL="${NIX_INSTALLER_BASE_URL:-https://github.com/NixOS/nix-installer/releases/download/$VERSION}"
CACHE_HOST="nix-cache.fossi-foundation.org"
EXTRA_CONF="
    extra-substituters = https://${CACHE_HOST}
    extra-trusted-public-keys = ${CACHE_HOST}:3+K59iFwXqKsL7BNu6Guy0v+uTlwsxYQxjspXzqLYQs=
    extra-experimental-features = nix-command flakes
"
NIX_BIN=/nix/var/nix/profiles/default/bin/nix
DRY_RUN="${DRY_RUN:-0}"

cache_configured() { grep -qs "$CACHE_HOST" /etc/nix/nix.conf /etc/nix/nix.custom.conf; }

if [ "$(uname -s)" != "Darwin" ]; then
  echo "nix-install: FAIL - this target is for macOS; on Linux follow the LibreLane Nix guide."
  exit 1
fi
if [ "$(uname -m)" != "arm64" ]; then
  echo "nix-install: FAIL - nix-installer $VERSION ships no x86_64-darwin binary; Intel Macs are not supported here."
  exit 1
fi

# ---- already installed? ----
if command -v nix >/dev/null 2>&1 || [ -x "$NIX_BIN" ]; then
  echo "nix-install: Nix is already installed ($("$NIX_BIN" --version 2>/dev/null || nix --version))."
  if cache_configured; then
    echo "nix-install: PASS - FOSSi binary cache is configured."
    exit 0
  fi
  echo "nix-install: FAIL - FOSSi binary cache is NOT configured. Add these lines to /etc/nix/nix.conf,"
  echo "then restart the daemon with: sudo pkill nix-daemon"
  printf '%s\n' "$EXTRA_CONF"
  exit 1
fi

# ---- download (resumable) and verify ----
NAME="nix-installer-aarch64-darwin"
DIR=".tools/nix-installer/$VERSION"
BIN="$DIR/$NAME"
mkdir -p "$DIR"
sha_of() { shasum -a 256 "$1" | cut -d' ' -f1; }

if [ -f "$BIN" ] && [ "$(sha_of "$BIN")" = "$SHA_PINNED" ]; then
  echo "nix-install: using cached $BIN (sha256 OK)"
else
  rm -f "$BIN"
  echo "nix-install: downloading $NAME $VERSION (about 25 MB; resumable, no speed limit)"
  attempt=1
  until curl --proto '=https' --tlsv1.2 -fL --retry 5 --retry-delay 5 --connect-timeout 30 \
               -C - --progress-bar -o "$BIN.part" "$BASE_URL/$NAME"; do
    if [ "$attempt" -ge 5 ]; then
      echo "nix-install: FAIL - download did not complete after $attempt attempts; rerun 'make nix-install' to resume."
      exit 1
    fi
    attempt=$((attempt + 1))
    echo "nix-install: download interrupted, resuming (attempt $attempt)"
    sleep 5
  done
  got="$(sha_of "$BIN.part")"
  if [ "$got" != "$SHA_PINNED" ]; then
    echo "nix-install: FAIL - sha256 mismatch: got $got, expected $SHA_PINNED (pinned in env/versions.mk)"
    rm -f "$BIN.part"
    exit 1
  fi
  mv "$BIN.part" "$BIN"
  chmod +x "$BIN"
  echo "nix-install: downloaded and verified sha256 $got"
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "nix-install: DRY_RUN - $("$BIN" --version); would run:"
  echo "  $BIN install --no-confirm --extra-conf \"$EXTRA_CONF\""
  exit 0
fi

# ---- install ----
echo "nix-install: running $("$BIN" --version) (it escalates with sudo and will ask for your administrator password)"
"$BIN" install --no-confirm --extra-conf "$EXTRA_CONF"

if [ -x "$NIX_BIN" ] && cache_configured; then
  echo "nix-install: PASS - $("$NIX_BIN" --version)"
  echo "Next: close ALL terminal windows, open a new one, then run: make env-check && make flow-setup"
else
  echo "nix-install: FAIL - installer finished but $NIX_BIN or the FOSSi cache setting is missing."
  exit 1
fi
