#!/bin/zsh
# Run ChipFoundry precheck the way `cf precheck` does (cf-cli 88025a8f main.py 4890-4925), on the lima VM cf-precheck.
# usage: run_precheck.sh <project dir> [extra cf-precheck args]; writes <project>/precheck_run.txt
set -u
P=$1; shift
W=~/claude_prjs/arvinsa-rtl-gds-p7precheck
PDK_ROOT=$W/pdks; PDK=$PDK_ROOT/sky130A
IMG=chipfoundry/mpw_precheck:latest
OUT=$P/precheck_run.txt
{ echo "start $(date '+%F %T')"; echo "image $(docker image inspect $IMG --format '{{index .RepoDigests 0}}')"; echo "pdk $(readlink $PDK)"; } > $OUT
s=$(date +%s)
docker run --rm --init --platform linux/amd64 -v $P:$P -v $PDK_ROOT:$PDK_ROOT -e PDK_ROOT=$PDK_ROOT -e PDK_PATH=$PDK -e PDKPATH=$PDK $IMG \
  bash -c "pip3 install --upgrade -q --root-user-action=ignore cf-precheck 2>/dev/null; echo cf-precheck \$(pip3 show cf-precheck | sed -n 's/^Version: //p'); exec cf-precheck -i $P -p $PDK -c /opt/caravel $*" > $P/precheck_console.log 2>&1
rc=$?
{ grep -m1 '^cf-precheck ' $P/precheck_console.log; echo "rc=$rc $(( ($(date +%s)-s)/60 )) min end $(date '+%F %T')"; } >> $OUT
cat $OUT
