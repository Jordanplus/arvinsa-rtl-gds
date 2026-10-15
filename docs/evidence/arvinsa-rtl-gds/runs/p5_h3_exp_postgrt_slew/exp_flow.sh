#!/bin/bash
# Session-only: one LibreLane experiment on the Hazard3 SoC (worktree p5h3, commit 1292ca4), from a step of
# harden 4 to OpenROAD.STAPostPNR. usage: exp_flow.sh <tag> <from step> <initial state json> [-c KEY=VALUE ...]
# Writes runs/<tag> in the worktree; harden 4 (runs/soc_top_hazard3) is only read. A process above
# CAP_MB, or the whole run after TMAX seconds, is stopped.
set -u
W=~/claude_prjs/arvinsa-rtl-gds-p5h3
LL=~/claude_prjs/arvinsa-rtl-gds/.tools/librelane
S=<claude-session-tmp>/scratchpad
TAG=$1; FROM=$2; STATE=$3; shift 3
CAP_MB=12288; TMAX=3600
LOG=$S/$TAG.log; WATCH=$S/$TAG.mem
export PATH=/nix/var/nix/profiles/default/bin:$PATH
rm -rf "$W/runs/$TAG"; : > "$WATCH"
( cd "$LL" && nix-shell --run "python3 -m librelane --run-tag '$TAG' --design-dir '$W' --pdk sky130A --scl sky130_fd_sc_hd --condensed --from $FROM --to OpenROAD.STAPostPNR --with-initial-state '$STATE' $* '$W/pnr/soc_top/config_hazard3.json'" ) > "$LOG" 2>&1 &
MK=$!; t0=$(date +%s)
while kill -0 $MK 2>/dev/null; do
  for P in $(pgrep -f "runs/$TAG/"); do
    mb=$(top -l 1 -pid $P -stats mem 2>/dev/null | tail -1 | tr -d ' ' | awk '/G/{sub(/G.*/,"");print int($1*1024);next} /M/{sub(/M.*/,"");print int($1);next} {print 0}')
    [ "${mb:-0}" -gt 1024 ] && echo "$(( $(date +%s) - t0 )) $P ${mb}MB" >> "$WATCH"
    if [ "${mb:-0}" -gt $CAP_MB ]; then echo "MEMORY STOP pid $P ${mb}MB" >> "$WATCH"; kill -TERM $P; fi
  done
  if [ $(( $(date +%s) - t0 )) -gt $TMAX ]; then echo "TIME STOP after ${TMAX}s" >> "$WATCH"; pkill -TERM -f "runs/$TAG/"; kill -TERM $MK; fi
  sleep 15
done
wait $MK; rc=$?
echo "$TAG rc=$rc $(( $(date +%s) - t0 ))s" | tee -a "$LOG"
