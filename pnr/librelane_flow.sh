# Sourced by pnr/*/run.sh. librelane_flow <name> <config.json>: runs the LibreLane Classic flow with
# the caller's LL_DIR, TAG, ROOT, RUN_DIR, PDK, SCL and OUT; sets flow_rc and flow_attempts. The output of
# the last attempt is $OUT/console.log; earlier attempts are kept as $OUT/console_attempt<N>.log.
#
# Bounded retry for one known OpenROAD problem, and only for it: the global_route after a repair
# inside OpenROAD.RepairDesignPostGRT or OpenROAD.ResizerTimingPostGRT sometimes stops with
#   [ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (...) usage=65534 ...
# With the same input state it is random (2026-10-03, soc_top RepairDesignPostGRT: 4 single-step
# re-runs, 2 stopped there and 2 passed with identical repair and wirelength; 2026-10-07, PicoRV32
# ResizerTimingPostGRT (ADR-0014/0016): 4 re-runs, 1 stopped, 3 passed with identical DEFs;
# docs/notes/grt0229_repro.md). The same holds for
#   [ERROR GRT-0116] Global routing finished with congestion.
# when the final congestion report just before it has a total overflow of at most 10 (2026-10-08,
# PicoRV32 ResizerTimingPostGRT at 5aaf036: overflow 2 at 37 % usage; 4 single-step re-runs of that
# input all passed with overflow 0 and slightly different wirelength). A larger overflow is real
# congestion and is not retried. The flow is then resumed from that step (--from), at most 3
# attempts in all. Any other failure is not retried.
# Each retry is recorded in $OUT/retries.txt. The decision reads the log of the last step directory,
# not the console: the console wraps lines, so the message is split there.
# pnr/ is on PYTHONPATH so that LibreLane finds the repo plugin pnr/librelane_plugin_arvinsa (the
# soc_top configs substitute its CTS step, ADR-0016); without it LibreLane stops with an unknown step.
# keep_prev_run <dir>...: before a new run, each existing <dir> becomes <dir>.prev and an older
# <dir>.prev is removed. A rerun with the same tag used to delete the run it replaced, with the
# evidence of a failed run (Phase 3.5: the first harden-soc's log was lost that way). One level only:
# a soc_top run is about 4 GB. Checked by make test-flow-retry.
keep_prev_run() {
  local d
  for d in "$@"; do
    rm -rf "$d.prev"
    if [ -e "$d" ]; then mv "$d" "$d.prev"; fi
  done
}

librelane_flow() {
  local name="$1" config="$2" from="" n last step log overflow why
  flow_attempts=0
  rm -f "$OUT/retries.txt"
  while :; do
    flow_attempts=$((flow_attempts + 1))
    flow_rc=0
    (cd "$LL_DIR" && nix-shell --run "PYTHONPATH='$ROOT/pnr' python3 -m librelane --run-tag '$TAG' --design-dir '$ROOT' --pdk '$PDK' --scl '$SCL' --condensed $from '$config'") \
      > "$OUT/console.log" 2>&1 || flow_rc=$?
    [ "$flow_rc" = 0 ] && return 0
    [ "$flow_attempts" -ge 3 ] && return 0
    last=$(cd "$RUN_DIR" 2>/dev/null && ls -d [0-9]*-* 2>/dev/null | sort -n | tail -1)
    case "$last" in
      *-openroad-repairdesignpostgrt|*-openroad-repairdesignpostgrt-[0-9]*) step=OpenROAD.RepairDesignPostGRT ;;
      *-openroad-resizertimingpostgrt|*-openroad-resizertimingpostgrt-[0-9]*) step=OpenROAD.ResizerTimingPostGRT ;;
      *) return 0 ;;
    esac
    [ -e "$RUN_DIR/$last/state_out.json" ] && return 0
    log="openroad-$(echo "${step#OpenROAD.}" | tr '[:upper:]' '[:lower:]').log"
    # || true: under the callers' set -euo pipefail a log without a congestion report (GRT-0229) must not stop the script
    overflow=$(grep -E '^Total[[:space:]]+[0-9]+' "$RUN_DIR/$last/$log" 2>/dev/null | tail -1 | awk '{print $NF}' || true)
    if grep -q '^\[ERROR GRT-0229\] Vertical edge usage exceeds the maximum allowed\..*usage=65534' "$RUN_DIR/$last/$log" 2>/dev/null; then
      why="GRT-0229"
    elif grep -q '^\[ERROR GRT-0116\] Global routing finished with congestion' "$RUN_DIR/$last/$log" 2>/dev/null \
         && [ -n "$overflow" ] && [ "$overflow" -le 10 ] 2>/dev/null; then
      why="GRT-0116 (total overflow $overflow)"
    else
      return 0
    fi
    n=$flow_attempts
    mv "$OUT/console.log" "$OUT/console_attempt$n.log"
    echo "$name: attempt $n stopped with the known intermittent $why in $step ($last; console_attempt$n.log); resuming from that step" \
      | tee -a "$OUT/retries.txt"
    from="--from $step"
  done
}
