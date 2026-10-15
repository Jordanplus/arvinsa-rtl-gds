#!/bin/bash
# Phase 5 experiment (session-only): re-run steps 32-37 (RepairDesignPostGPL .. ResizerTimingPostCTS) of
# Hazard3 harden 4 (44 ns) from the state after step 31, with DESIGN_REPAIR_MAX_WIRE_LENGTH = $1 um
# (harden 4: 200), then sta44/sta_wl.sh on the output. The original run is only read.
set -u
R=~/claude_prjs/arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3
LL=~/claude_prjs/arvinsa-rtl-gds/.tools/librelane
S=<claude-session-tmp>/scratchpad
WL=$1
E=$S/exp_wl/wl$WL
CAP_MB=8192
TMAX=1800
rm -rf "$E"; mkdir -p "$E"
: > "$E/summary.txt"
export PATH=/nix/var/nix/profiles/default/bin:$PATH

run() {  # step id, config, state_in, out dir
  ( cd "$LL" && nix-shell --run "python3 -m librelane.steps run --id $1 -c '$2' -i '$3' -o '$4'" ) >> "$E/run.log" 2>&1 &
  local pid=$! t0
  t0=$(date +%s)
  while kill -0 $pid 2>/dev/null; do
    for P in $(pgrep -f "$4"); do
      m=$(top -l 1 -pid $P -stats mem 2>/dev/null | tail -1 | tr -d ' ')
      mb=$(echo "$m" | awk '/G/{sub(/G.*/,"");print int($1*1024);next} /M/{sub(/M.*/,"");print int($1);next} {print 0}')
      if [ "${mb:-0}" -gt $CAP_MB ]; then
        echo "MEMORY STOP $1 $(( $(date +%s) - t0 ))s pid $P ${mb}MB" >> "$E/summary.txt"
        pkill -TERM -f "$4"
      fi
    done
    if [ $(( $(date +%s) - t0 )) -gt $TMAX ]; then
      echo "TIME STOP $1 after ${TMAX}s" >> "$E/summary.txt"
      pkill -TERM -f "$4"
    fi
    sleep 10
  done
  wait $pid
  local rc=$?
  echo "$1 rc=$rc $(( $(date +%s) - t0 ))s" >> "$E/summary.txt"
  return $rc
}

prev=$R/31-openroad-stamidpnr/state_out.json
for s in 32-openroad-repairdesignpostgpl:OpenROAD.RepairDesignPostGPL 33-odb-manualglobalplacement:Odb.ManualGlobalPlacement \
         34-openroad-detailedplacement:OpenROAD.DetailedPlacement 35-openroad-cts:OpenROAD.CTS \
         37-openroad-resizertimingpostcts:OpenROAD.ResizerTimingPostCTS; do
  d=${s%%:*}; id=${s#*:}
  python3 - "$R/$d/config.json" "$E/$d.config.json" "$WL" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
if "DESIGN_REPAIR_MAX_WIRE_LENGTH" in c:
    c["DESIGN_REPAIR_MAX_WIRE_LENGTH"] = float(sys.argv[3])
json.dump(c, open(sys.argv[2], "w"), indent=1)
PY
  run "$id" "$E/$d.config.json" "$prev" "$E/$d" || { echo "stopped at $id" >> "$E/summary.txt"; cat "$E/summary.txt"; exit 1; }
  prev=$E/$d/state_out.json
done
nix-shell "$LL/shell.nix" --run "cd '$S/sta44' && STA_ODB='$E/37-openroad-resizertimingpostcts/soc_top.odb' PATH_RPT='$E/path.rpt' ./sta_wl.sh" > "$E/sta.log" 2>&1
echo "sta rc=$?" >> "$E/summary.txt"
cat "$E/summary.txt"
