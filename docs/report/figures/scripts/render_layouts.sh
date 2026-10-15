#!/usr/bin/env bash
# Raw KLayout renders of the closing-run GDS files (commit 2b04451 worktrees) for the report.
# usage: render_layouts.sh <raw_dir>      then: python3 layout_figs.py <raw_dir>
# Each render writes <raw_dir>/<name>.png (box in um passed explicitly, w:h = box aspect, so the
# picture covers exactly that box) and <name>.png.json (layers shown, top cell, its bbox).
set -euo pipefail
RAW=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
PRJ=$(dirname "$REPO")
LYP=$HOME/.ciel/sky130A/libs.tech/klayout/tech/sky130A.lyp
SH=$HERE/gds_shot.py
WRAP=$PRJ/arvinsa-rtl-gds-p7close2_caravel/runs/user_project_wrapper/final/gds/user_project_wrapper.gds
H3=$PRJ/arvinsa-rtl-gds-p7close2_h3/runs/soc_top_hazard3/final/gds/soc_top.gds
PICO=$PRJ/arvinsa-rtl-gds-p7close2_pico/runs/picorv32_core/final/gds/picorv32.gds
SRAM=$REPO/ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/openram/arv_sram_2kbyte_1rw1r_32x512_8.gds
M25=69/20,70/20,71/20,72/20
NOPDN=71/20,71/44,72/20
shot() {  # gds out w h box [extra -rd args]
  local g=$1 o=$2 w=$3 h=$4 b=$5; shift 5
  echo "klayout -z -rd gds=$g -rd out=$RAW/$o -rd lyp=$LYP -rd w=$w -rd h=$h -rd box=$b $* -r $SH"
}
CMDS="
$(shot "$WRAP" wrap_full_all.png 2000 2395 -60,-60,2980,3580)
$(shot "$WRAP" wrap_full_m2m5.png 2000 2395 -60,-60,2980,3580 -rd layers=$M25)
$(shot "$WRAP" wrap_zoom.png 2400 1920 -20,-20,1180,940 -rd hide=$NOPDN)
$(shot "$H3" h3.png 2400 1938 -20,-20,1020,820)
$(shot "$PICO" pico.png 2000 2038 -15,-15,548.575,559.295)
$(shot "$SRAM" sram_full.png 2400 1507 -10,-10,704.27,438.415 -rd hide=69/20,69/44,71/20,71/44)
$(shot "$SRAM" sram_zoom.png 1600 1000 128,98,168,123)
"
cd "$REPO/.tools/librelane"
PATH=/nix/var/nix/profiles/default/bin:$PATH nix-shell --run "set -e; $CMDS"
