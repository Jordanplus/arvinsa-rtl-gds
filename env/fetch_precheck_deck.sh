#!/usr/bin/env bash
# make precheck-deck: the KLayout DRC deck of ChipFoundry's precheck (drc_scripts/sky130A_mr.drc of the pip package
# cf-precheck) into .tools/cf-precheck-<version>/ (Phase 7, ADR-0019 decision 5). The deck is GPLv3 and is not kept
# in the repo. The wheel must have CF_PRECHECK_WHEEL_SHA256 and the deck CF_PRECHECK_DECK_SHA256 (env/versions.mk).
# Read the deck before running it on a new version: it is a third-party Ruby script (skill tapeout-precheck-caravel).
set -euo pipefail
cd "$(dirname "$0")/.."
pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }
VER="$(pin CF_PRECHECK_VERSION)"; WSHA="$(pin CF_PRECHECK_WHEEL_SHA256)"; DSHA="$(pin CF_PRECHECK_DECK_SHA256)"
DEST=".tools/cf-precheck-$VER"
WHEEL="cf_precheck-$VER-py3-none-any.whl"
sha_ok() { echo "$1  $2" | shasum -a 256 -c --status; }

if [ -f "$DEST/sky130A_mr.drc" ] && sha_ok "$DSHA" "$DEST/sky130A_mr.drc"; then
  echo "precheck-deck: PASS - $DEST/sky130A_mr.drc already installed (cf-precheck $VER)"
  exit 0
fi
rm -rf "$DEST" "$DEST.tmp"; mkdir -p "$DEST.tmp"
python3 -m pip download --quiet --no-deps --only-binary=:all: "cf-precheck==$VER" -d "$DEST.tmp"
sha_ok "$WSHA" "$DEST.tmp/$WHEEL" || { echo "precheck-deck: FAIL - $WHEEL sha256 is not CF_PRECHECK_WHEEL_SHA256"; exit 1; }
unzip -q -o "$DEST.tmp/$WHEEL" 'cf_precheck/drc_scripts/sky130A_mr.drc' -d "$DEST.tmp"
sha_ok "$DSHA" "$DEST.tmp/cf_precheck/drc_scripts/sky130A_mr.drc" \
  || { echo "precheck-deck: FAIL - sky130A_mr.drc sha256 is not CF_PRECHECK_DECK_SHA256"; exit 1; }
mkdir -p "$DEST"
mv "$DEST.tmp/cf_precheck/drc_scripts/sky130A_mr.drc" "$DEST/"
rm -rf "$DEST.tmp"
echo "precheck-deck: PASS - $DEST/sky130A_mr.drc (cf-precheck $VER, sha256 ${DSHA:0:16})"
