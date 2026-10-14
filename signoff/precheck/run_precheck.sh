#!/bin/zsh
# ChipFoundry precheck on a project directory, the way `cf precheck` runs it (cf-cli 88025a8f main.py 4890-4925), in
# the official image under the lima VM cf-precheck (ADR-0019 decision 4; docs/notes/caravel_precheck_phase7.md section
# 8). In the same container, after cf-precheck, the image's own deck and KLayout check the PDK SRAM alone: the
# reference of check_precheck.py (<project>/sram_ref/, with input.sha1 and the deck's sha256).
# usage: run_precheck.sh <project dir under PRECHECK_WORK> [extra cf-precheck args]
# Writes <project>/precheck_run.txt (start, image digest, PDK, cf-precheck version, exit code, minutes, end) and
# <project>/precheck_console.log. PRECHECK_WORK (default ../arvinsa-rtl-gds-p7precheck) is the VM's only mount and
# holds pdks/ (open_pdks 3e0e31dc, ciel, with sky130_sram_macros). Not a judgement: make precheck-check judges.
set -u
P=${1:A}; shift
W=${PRECHECK_WORK:-${0:A:h:h:h:h}/arvinsa-rtl-gds-p7precheck}
case $P in $W/*) ;; *) echo "run-precheck: FAIL $P is not under $W (the VM sees only that)"; exit 1 ;; esac
PDK_ROOT=$W/pdks; PDK=$PDK_ROOT/sky130A
IMG=chipfoundry/mpw_precheck:latest
SRAM=sky130_sram_2kbyte_1rw1r_32x512_8
OUT=$P/precheck_run.txt
{ echo "start $(date '+%F %T')"; echo "image $(docker image inspect $IMG --format '{{index .RepoDigests 0}}')"; echo "pdk $(readlink $PDK)"; } > $OUT
s=$(date +%s)
docker run --rm --init --platform linux/amd64 -v $P:$P -v $PDK_ROOT:$PDK_ROOT -e PDK_ROOT=$PDK_ROOT -e PDK_PATH=$PDK -e PDKPATH=$PDK $IMG \
  bash -c "pip3 install --upgrade -q --root-user-action=ignore cf-precheck 2>/dev/null; echo cf-precheck \$(pip3 show cf-precheck | sed -n 's/^Version: //p');
cf-precheck -i $P -p $PDK -c /opt/caravel $*; rc=\$?;
D=\$(python3 -c 'import cf_precheck, os; print(os.path.dirname(cf_precheck.__file__))')/drc_scripts/sky130A_mr.drc
G=$PDK/libs.ref/sky130_sram_macros/gds/$SRAM.gds; R=$P/sram_ref; rm -rf \$R; mkdir -p \$R
sha256sum \$D > \$R/deck.sha256; echo \"$SRAM.gds: \$(sha1sum \$G | cut -d' ' -f1)\" > \$R/input.sha1; klayout -v > \$R/klayout.version
for c in feol beol; do klayout -b -r \$D -rd input=\$G -rd topcell=$SRAM -rd report=\$R/klayout_\${c}_check.xml -rd thr=\$(nproc) -rd \$c=true > \$R/klayout_\${c}_check.log 2>&1;
  echo sram_ref \$c rc=\$? items=\$(grep -c '<item>' \$R/klayout_\${c}_check.xml); grep -c '<item>' \$R/klayout_\${c}_check.xml | tr -d '\n' > \$R/klayout_\${c}_check.total; done
exit \$rc" > $P/precheck_console.log 2>&1
rc=$?
{ grep -m1 '^cf-precheck ' $P/precheck_console.log; grep '^sram_ref ' $P/precheck_console.log; echo "rc=$rc $(( ($(date +%s)-s)/60 )) min end $(date '+%F %T')"; } >> $OUT
cat $OUT
