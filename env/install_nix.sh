#!/usr/bin/env bash
# make nix-install: install Nix with the FOSSi binary cache, as required by LibreLane on macOS.
# Source of the command: https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html
# The installer needs an administrator password (sudo), so run this in your own terminal.
# DRY_RUN=1 downloads the installer and prints the command without running it.
set -euo pipefail
cd "$(dirname "$0")/.."

INSTALLER_URL="https://artifacts.nixos.org/nix-installer"
CACHE_HOST="nix-cache.fossi-foundation.org"
EXTRA_CONF="
    extra-substituters = https://${CACHE_HOST}
    extra-trusted-public-keys = ${CACHE_HOST}:3+K59iFwXqKsL7BNu6Guy0v+uTlwsxYQxjspXzqLYQs=
    extra-experimental-features = nix-command flakes
"
NIX_BIN=/nix/var/nix/profiles/default/bin/nix
DRY_RUN="${DRY_RUN:-0}"

cache_configured() {
  grep -qs "$CACHE_HOST" /etc/nix/nix.conf /etc/nix/nix.custom.conf
}

if [ "$(uname -s)" != "Darwin" ]; then
  echo "nix-install: FAIL - this target is for macOS; on Linux follow the LibreLane Nix guide for your distribution."
  exit 1
fi

if command -v nix >/dev/null 2>&1 || [ -x "$NIX_BIN" ]; then
  echo "nix-install: Nix is already installed ($("${NIX_BIN}" --version 2>/dev/null || nix --version))."
  if cache_configured; then
    echo "nix-install: PASS - FOSSi binary cache is configured."
    exit 0
  fi
  echo "nix-install: FAIL - FOSSi binary cache is NOT configured. Add these lines to /etc/nix/nix.conf,"
  echo "then restart the daemon with: sudo pkill nix-daemon"
  printf '%s\n' "$EXTRA_CONF"
  exit 1
fi

tmp="$(mktemp -t nix-installer)"
trap 'rm -f "$tmp"' EXIT
echo "nix-install: downloading installer from $INSTALLER_URL"
curl --proto '=https' --tlsv1.2 -fsSL "$INSTALLER_URL" -o "$tmp"

if [ "$DRY_RUN" = "1" ]; then
  echo "nix-install: DRY_RUN - installer downloaded ($(wc -c < "$tmp" | tr -d ' ') bytes); would run:"
  echo "  sh $tmp install --no-confirm --extra-conf \"$EXTRA_CONF\""
  exit 0
fi

echo "nix-install: running installer (it will ask for your administrator password)"
sh "$tmp" install --no-confirm --extra-conf "$EXTRA_CONF"

if [ -x "$NIX_BIN" ] && cache_configured; then
  echo "nix-install: PASS - $("$NIX_BIN" --version)"
  echo "Next: close ALL terminal windows, open a new one, then run: make env-check && make flow-setup"
else
  echo "nix-install: FAIL - installer finished but $NIX_BIN or the FOSSi cache setting is missing."
  exit 1
fi
