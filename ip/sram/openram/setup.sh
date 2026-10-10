#!/usr/bin/env bash
# make openram-setup: install the pinned OpenRAM toolchain for Phase 6 (ADR-0018) into .tools/:
#   .tools/openram                          OpenRAM at OPENRAM_COMMIT (detached) with ip/sram/openram/patches/*.patch
#                                           applied in order as working-tree changes (ADR-0018 decision 8)
#   .tools/openram-pdk-<hash8>/sky130A      OpenRAM's own pinned PDK (OPENRAM_PDK_HASH): libs.tech + sky130_fd_pr only
#   .tools/openram-pdk-<hash8>/sky130_fd_bd_sram   at SKY130_FD_BD_SRAM_COMMIT
#   .tools/openram-pdk-<hash8>/skywater-pdk/...dlxtn  the one cell `make sky130-install` copies from skywater-pdk;
#                                           OpenRAM's Python never uses it, so it is cut out of the flow PDK instead
#                                           of cloning skywater-pdk (docs/notes/openram_phase6_bringup.md)
#   .tools/openram-venv                     Python packages (ip/sram/openram/requirements.txt)
# Tools (Magic, Netgen, KLayout) come from LibreLane's nix-shell, as for the rest of the flow.
# Known defect handled here: `make sky130-install` copies with `cp $?` (only files newer than the target directory);
# OpenRAM's technology/sky130/*_lib directories exist in its checkout, so a freshly cloned cell library can be
# older and silently not copied (make still exits 0). All sources are touched first, and the install is checked.
set -euo pipefail
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }

OR_COMMIT="$(pin OPENRAM_COMMIT)"
BD_COMMIT="$(pin SKY130_FD_BD_SRAM_COMMIT)"
HASH="$(pin OPENRAM_PDK_HASH)"
OR_DIR="$ROOT/.tools/openram"
PDK="$ROOT/.tools/openram-pdk-${HASH:0:8}"
VENV="$ROOT/.tools/openram-venv"
CACHE="$ROOT/.tools/pdk-cache/sky130-$HASH"
FLOW_PDK="${PDK_ROOT:-$HOME/.ciel}/sky130A"
LL_DIR="${LIBRELANE_DIR:-$ROOT/.tools/librelane}"
fail() { echo "openram-setup: FAIL - $*"; exit 1; }

# 1. A git checkout at a pinned commit; tracked files must be unmodified (untracked install outputs are fine).
checkout() {  # repo dir commit
  local repo="$1" dir="$2" commit="$3"
  [ -d "$dir/.git" ] || git clone -q "$repo" "$dir"
  git -C "$dir" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$dir" fetch -q origin
  [ -z "$(git -C "$dir" status --porcelain --untracked-files=no)" ] || fail "$dir has modified tracked files"
  git -C "$dir" checkout -q --detach "$commit"
  [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ] || fail "$dir is not at $commit"
}
# OpenRAM: pinned commit + the repo's patches. If the tracked files are not exactly that, go back to the pinned
# commit (discarding tracked edits in .tools/openram only; the installed cell library is untracked and stays)
# and apply the patches again.
[ -d "$OR_DIR/.git" ] || git clone -q "$(pin OPENRAM_REPO)" "$OR_DIR"
git -C "$OR_DIR" cat-file -e "$OR_COMMIT^{commit}" 2>/dev/null || git -C "$OR_DIR" fetch -q origin
tree_ok() { python3 -c "import sys; sys.path.insert(0, 'ip/sram/openram'); import check_install as c
sys.exit(1 if c.tree_problems('$OR_DIR', '$OR_COMMIT', c.patch_files()) else 0)"; }
if ! tree_ok; then
  echo "openram-setup: resetting $OR_DIR to ${OR_COMMIT:0:8} and applying ip/sram/openram/patches"
  git -C "$OR_DIR" checkout -q -f --detach "$OR_COMMIT"
  for p in ip/sram/openram/patches/*.patch; do
    git -C "$OR_DIR" apply "$ROOT/$p" || fail "$p does not apply"
  done
  tree_ok || fail "$OR_DIR is not ${OR_COMMIT:0:8} + the patches after applying them"
fi
mkdir -p "$PDK"
checkout "$(pin SKY130_FD_BD_SRAM_REPO)" "$PDK/sky130_fd_bd_sram" "$BD_COMMIT"

# 2. OpenRAM's PDK: two ciel-release tarballs, resumable, sha256-checked against env/versions.mk.
mkdir -p "$CACHE"
fetch() {  # name sha256
  local f="$CACHE/$1.tar.zst"
  if [ ! -f "$f" ] || [ "$(shasum -a 256 "$f" | awk '{print $1}')" != "$2" ]; then
    curl -fL --retry 10 --retry-delay 5 --retry-all-errors -C - -sS -o "$f.part" \
      "https://github.com/fossi-foundation/ciel-releases/releases/download/sky130-$HASH/$1.tar.zst"
    [ "$(shasum -a 256 "$f.part" | awk '{print $1}')" = "$2" ] || fail "$1.tar.zst sha256 mismatch"
    mv "$f.part" "$f"
  fi
}
fetch common "$(pin OPENRAM_PDK_COMMON_SHA256)"
fetch sky130_fd_pr "$(pin OPENRAM_PDK_FD_PR_SHA256)"
if ! grep -q "$HASH" "$PDK/sky130A/SOURCES" 2>/dev/null || [ ! -d "$PDK/sky130A/libs.ref/sky130_fd_pr" ]; then
  rm -rf "$PDK/sky130A"
  (cd "$PDK" && tar --zstd -xf "$CACHE/common.tar.zst" && tar --zstd -xf "$CACHE/sky130_fd_pr.tar.zst")
fi
grep -q "$HASH" "$PDK/sky130A/SOURCES" || fail "$PDK/sky130A/SOURCES does not name $HASH"

# 3. dlxtn_1 (GDS + SPICE) cut out of the flow PDK's sky130_fd_sc_hd.
DLX="$PDK/skywater-pdk/libraries/sky130_fd_sc_hd/latest/cells/dlxtn"
mkdir -p "$DLX"
awk '/^\.subckt sky130_fd_sc_hd__dlxtn_1 /{f=1} f{print} f&&/^\.ends/{exit}' \
  "$FLOW_PDK/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice" > "$DLX/sky130_fd_sc_hd__dlxtn_1.spice"
grep -q '^\.ends' "$DLX/sky130_fd_sc_hd__dlxtn_1.spice" || fail "dlxtn_1 not found in the flow PDK's SPICE"
if [ ! -s "$DLX/sky130_fd_sc_hd__dlxtn_1.gds" ]; then
  (cd "$LL_DIR" && nix-shell --run "klayout -b -rd src='$FLOW_PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds' \
     -rd cell=sky130_fd_sc_hd__dlxtn_1 -rd dst='$DLX/sky130_fd_sc_hd__dlxtn_1.gds' -r '$ROOT/ip/sram/openram/extract_cell.py'") \
    > "$PDK/dlxtn.log" 2>&1 || fail "KLayout could not cut dlxtn_1 (see $PDK/dlxtn.log)"
fi

# 4. Python packages.
[ -x "$VENV/bin/python3" ] || python3 -m venv "$VENV"
"$VENV/bin/python3" -m pip --version >/dev/null 2>&1 || "$VENV/bin/python3" -m ensurepip >/dev/null  # a venv made by uv has no pip
"$VENV/bin/python3" -m pip install -q -r ip/sram/openram/requirements.txt
"$VENV/bin/python3" -c 'import numpy, scipy, sklearn'

# 5. Cell library install, with every source made newer than the targets (see the header).
find "$PDK/sky130_fd_bd_sram/cells" "$PDK/skywater-pdk" -type f -exec touch {} +
(cd "$OR_DIR" && PDK_ROOT="$PDK" OPENRAM_HOME="$OR_DIR/compiler" make sky130-install) > "$PDK/install.log" 2>&1 \
  || fail "make sky130-install (see $PDK/install.log)"
python3 ip/sram/openram/check_install.py "$OR_DIR" "$PDK/sky130_fd_bd_sram" || fail "cell library install incomplete"
echo "openram-setup: PASS - OpenRAM ${OR_COMMIT:0:8}, sky130_fd_bd_sram ${BD_COMMIT:0:7}, PDK ${HASH:0:8} at $PDK"
