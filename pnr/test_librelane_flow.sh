#!/usr/bin/env bash
# make test-flow-retry: checks the bounded retry in pnr/librelane_flow.sh with a mocked nix-shell
# (no LibreLane run). Each scenario is the outcome of successive LibreLane attempts:
#   grt       stops in OpenROAD.RepairDesignPostGRT with the known GRT-0229 usage=65534 line
#   grt44     stops in OpenROAD.ResizerTimingPostGRT with the same line (ADR-0014 runs that step)
#   grtother  stops in RepairDesignPostGRT with another error -> must not be retried
#   other     stops in another step                          -> must not be retried
#   ok        finishes
# and keep_prev_run (pnr/librelane_flow.sh): an existing run directory becomes <dir>.prev, an older
# <dir>.prev is removed, and a directory that does not exist leaves nothing behind.
# Each scenario also checks the --from of every attempt ("-" = the whole flow).
# Prints `test-flow-retry: PASS n/n` / `test-flow-retry: FAIL ...`; exit code 0 only on PASS.
set -euo pipefail
cd "$(dirname "$0")/.."
T="$(pwd)/runs/test_flow_retry"
pass=0; total=0

scenario() {  # scenario "<outcomes>" <want rc 0|fail> <want attempts> <want retries> <want --from list>
  local outcomes="$1" want_rc="$2" want_att="$3" want_retry="$4" want_from="$5" got
  total=$((total + 1))
  got=$(T="$T" OUTCOMES="$outcomes" bash -c '
    set -euo pipefail
    rm -rf "$T"; mkdir -p "$T/out" "$T/run" "$T/ll"
    OUT=$T/out RUN_DIR=$T/run LL_DIR=$T/ll TAG=t ROOT=$T PDK=p SCL=s
    echo 0 > "$T/calls"; : > "$T/froms"; mkdir -p "$RUN_DIR/40-openroad-checkantennas"
    nix-shell() {
      local calls o step d f
      calls=$(cat "$T/calls"); echo $((calls + 1)) > "$T/calls"
      f=$(echo "$2" | grep -o -- "--from [A-Za-z.]*" | cut -d" " -f2); echo "${f:--}" >> "$T/froms"
      o=$(echo "$OUTCOMES" | cut -d" " -f$((calls + 1))); step=$((41 + calls))
      case "$o" in
        grt|grtother|ok) d="$RUN_DIR/$step-openroad-repairdesignpostgrt" ;;
        grt44) d="$RUN_DIR/$step-openroad-resizertimingpostgrt" ;;
        *) d="$RUN_DIR/$step-openroad-detailedrouting" ;;
      esac
      mkdir -p "$d"
      case "$o" in
        grt) echo "[ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200" \
               > "$d/openroad-repairdesignpostgrt.log"; return 2 ;;
        grt44) echo "[ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200" \
               > "$d/openroad-resizertimingpostgrt.log"; return 2 ;;
        grtother) echo "[ERROR GRT-0001] another error" > "$d/openroad-repairdesignpostgrt.log"; return 2 ;;
        other) return 2 ;;
        ok) touch "$d/state_out.json"; return 0 ;;
      esac
    }
    source pnr/librelane_flow.sh
    librelane_flow test cfg.json > /dev/null
    echo "$flow_rc $flow_attempts $(cat "$OUT/retries.txt" 2>/dev/null | wc -l | tr -d " ") $(paste -sd, "$T/froms")"')
  local rc att retry froms; read -r rc att retry froms <<< "$got"
  local ok=0 rc_ok=0
  if [ "$want_rc" = 0 ]; then [ "$rc" = 0 ] && rc_ok=1; else [ "$rc" != 0 ] && rc_ok=1; fi
  if [ "$rc_ok" = 1 ] && [ "$att" = "$want_att" ] && [ "$retry" = "$want_retry" ] && [ "$froms" = "$want_from" ]; then ok=1; fi
  [ "$ok" = 1 ] && pass=$((pass + 1))
  echo "  [$([ "$ok" = 1 ] && echo PASS || echo FAIL)] '$outcomes': rc=$rc attempts=$att retries=$retry from=$froms (want rc=$want_rc attempts=$want_att retries=$want_retry from=$want_from)"
}

R=OpenROAD.RepairDesignPostGRT; Z=OpenROAD.ResizerTimingPostGRT
scenario "ok" 0 1 0 "-"
scenario "grt ok" 0 2 1 "-,$R"
scenario "grt grt ok" 0 3 2 "-,$R,$R"
scenario "grt grt grt" fail 3 2 "-,$R,$R"
scenario "other" fail 1 0 "-"
scenario "grtother" fail 1 0 "-"
scenario "grt other" fail 2 1 "-,$R"
scenario "grt44 ok" 0 2 1 "-,$Z"
scenario "grt grt44 ok" 0 3 2 "-,$R,$Z"
scenario "grt44 grt44 grt44" fail 3 2 "-,$Z,$Z"

total=$((total + 1))
P="$T/prev"; rm -rf "$P"; mkdir -p "$P/run" "$P/run.prev"; echo new > "$P/run/x"; echo old > "$P/run.prev/x"
( source pnr/librelane_flow.sh; keep_prev_run "$P/run" "$P/missing" )
if [ ! -e "$P/run" ] && [ "$(cat "$P/run.prev/x")" = new ] && [ ! -e "$P/missing" ] && [ ! -e "$P/missing.prev" ]; then
  pass=$((pass + 1)); echo "  [PASS] keep_prev_run: run -> run.prev (older run.prev removed), a missing directory leaves nothing"
else
  echo "  [FAIL] keep_prev_run: $(ls -A "$P" | tr '\n' ' ')"
fi
rm -rf "$T"
[ "$pass" = "$total" ] && echo "test-flow-retry: PASS $pass/$total" && exit 0
echo "test-flow-retry: FAIL $pass/$total"; exit 1
