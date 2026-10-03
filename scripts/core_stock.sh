#!/usr/bin/env bash
# scripts/core_stock.sh -- L1a: run the upstream PicoRV32 regression (soc_spec.md 8, 9).
#
# The pinned submodule third_party/picorv32 is exported with `git archive` into
# runs/core_stock/src, so the submodule working tree is never modified. The upstream
# Makefile is run unmodified in that copy; only make-variable overrides given on the
# command line (MAKE_ARGS below) differ from upstream defaults.
#
# A target PASSes only when ALL of the following hold:
#   - make exits with 0, and
#   - the explicit success text printed by the upstream testbench is in the log
#     (`ALL TESTS PASSED.` printed by testbench.v / testbench_wb.v), and
#   - no failure text is in the log.
# A missing success text is a FAIL. test_ez is the exception: upstream testbench_ez.v
# prints no success text at all, so a derived check on its bus trace is used instead.
#
# Output: runs/core_stock/summary.txt, runs/core_stock/logs/<target>.log
# Exit code: 0 when every required target PASSes, non-zero otherwise.
# Compatible with bash 3.2 and GNU make 3.81; Python is stdlib only.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

WORK=runs/core_stock
SRC=$WORK/src
LOGS=$WORK/logs
SUMMARY=$WORK/summary.txt
ROWS=$WORK/rows.tmp
SUBMODULE=third_party/picorv32
TOOLCHAIN_PREFIX=riscv64-elf-

# Make-variable overrides applied to every upstream make call.
# TOOLCHAIN_PREFIX is mandatory: the upstream default points at /opt/riscv32i/bin/.
# Nothing else is needed with GCC 16.1 / binutils 2.46.1 / Yosys 0.69 (verified
# 2026-10-03): -Werror in the upstream GCC_WARNS does not trip and -march=rv32imc
# assembles without _zicsr. Keep this list minimal; every entry must be explained in
# docs/notes/core_stock.md.
MAKE_ARGS=("TOOLCHAIN_PREFIX=$TOOLCHAIN_PREFIX")

# Targets that must PASS (exit code of this script depends on them).
REQUIRED_TARGETS="test test_ez test_wb test_synth"

# ---------------------------------------------------------------- helpers

pin() { sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" env/versions.mk; }

first_line() { sed -n 1p; }

fail_early() {
  echo "core-stock: preflight FAIL: $*" >&2
  mkdir -p "$WORK"
  {
    echo "core-stock (L1a) summary"
    echo "core-stock: FAIL (preflight: $*)"
  } > "$SUMMARY"
  exit 2
}

# ---------------------------------------------------------------- preflight

for tool in git make python3 iverilog vvp yosys \
            "${TOOLCHAIN_PREFIX}gcc" "${TOOLCHAIN_PREFIX}objcopy"; do
  command -v "$tool" >/dev/null 2>&1 || fail_early "tool not found: $tool"
done

want=$(pin PICORV32_COMMIT)
have=$(git -C "$SUBMODULE" rev-parse HEAD 2>/dev/null || echo none)
if [ -z "$want" ] || [ "$have" != "$want" ]; then
  fail_early "submodule $SUBMODULE is at ${have:0:12}, env/versions.mk pins ${want:0:12}"
fi

# ---------------------------------------------------------------- export

# Only paths below runs/core_stock are removed.
rm -rf "$SRC" "$LOGS" "$SUMMARY" "$ROWS"
mkdir -p "$SRC" "$LOGS"
git -C "$SUBMODULE" archive HEAD | tar -x -C "$SRC"
: > "$ROWS"

T_START=$SECONDS

# ---------------------------------------------------------------- checkers

# Success protocol shared by testbench.v and testbench_wb.v (make test, test_wb,
# test_synth): firmware prints "<name>..OK" per instruction test and "DONE", then
# writes 123456789 to 0x20000000 and executes ebreak; the testbench prints
# "TRAP after N clock cycles" and then "ALL TESTS PASSED." (or "ERROR!").
# Sets CHECK_OK (1/0) and CHECK_EVIDENCE.
eval_riscv_tb() {
  local log=$1 name f n_total=0 n_ok=0 missing="" cycles bad
  CHECK_OK=1
  CHECK_EVIDENCE=""
  if ! grep -aqx 'ALL TESTS PASSED\.' "$log"; then
    CHECK_OK=0; CHECK_EVIDENCE="${CHECK_EVIDENCE}missing 'ALL TESTS PASSED.'; "
  fi
  if ! grep -aqx 'DONE' "$log"; then
    CHECK_OK=0; CHECK_EVIDENCE="${CHECK_EVIDENCE}missing firmware 'DONE'; "
  fi
  cycles=$(sed -n 's/^TRAP after \([0-9][0-9]*\) clock cycles$/\1/p' "$log" | first_line)
  if [ -z "$cycles" ]; then
    CHECK_OK=0; CHECK_EVIDENCE="${CHECK_EVIDENCE}missing 'TRAP after N clock cycles'; "
  fi
  for f in "$SRC"/tests/*.S; do
    name=$(basename "$f" .S)
    n_total=$((n_total + 1))
    if grep -aFxq "${name}..OK" "$log"; then
      n_ok=$((n_ok + 1))
    else
      missing="$missing $name"
    fi
  done
  if [ "$n_total" -eq 0 ] || [ "$n_ok" -ne "$n_total" ]; then
    CHECK_OK=0; CHECK_EVIDENCE="${CHECK_EVIDENCE}per-test OK ${n_ok}/${n_total}, missing:${missing}; "
  fi
  bad=$(grep -aE 'ERROR!|\.\.ERROR$|^TIMEOUT$|OUT-OF-BOUNDS' "$log" | first_line || true)
  if [ -n "$bad" ]; then
    CHECK_OK=0; CHECK_EVIDENCE="${CHECK_EVIDENCE}failure text in log: '$bad'; "
  fi
  if [ "$CHECK_OK" = 1 ]; then
    CHECK_EVIDENCE="'ALL TESTS PASSED.', DONE, ${n_ok}/${n_total} instruction tests OK, TRAP after ${cycles} cycles"
  fi
}

# testbench_ez.v prints no success text (it only logs bus transactions and calls
# $finish after 1000 cycles), so the success criterion is derived from the program in
# the testbench: "li x1,1020; sw x0,0(x1); loop: lw x2,0(x1); addi x2,x2,1; sw x2,0(x1)".
# PASS = first ifetch is 0x3fc00093, every bus line is well-formed (no X/Z), the
# values written to 0x3fc are 0,1,2,... without gaps (at least EZ_MIN_COUNT writes),
# every read of 0x3fc returns the last written value, no failure text.
EZ_MIN_COUNT=32
eval_ez() {
  local log=$1 out="$WORK/ez_check.out"
  if python3 - "$log" "$EZ_MIN_COUNT" > "$out" <<'PY'
import re
import sys

log, min_count = sys.argv[1], int(sys.argv[2])
bus = re.compile(r"^(ifetch|read|write)\s+0x([0-9a-fA-F]{8}): 0x([0-9a-fA-F]{8})(?: \(wstrb=([01]{4})\))?$")
loose = re.compile(r"^(ifetch|read|write)\s")
errors = []
first_ifetch = None
last_written = None
count = 0
with open(log, errors="replace") as f:
    for line in f:
        line = line.rstrip("\n")
        if re.search(r"ERROR|TIMEOUT|OUT-OF-BOUNDS", line):
            errors.append("failure text: " + line)
        if not loose.match(line):
            continue
        m = bus.match(line)
        if not m:
            errors.append("malformed bus line (X/Z?): " + line)
            continue
        kind, addr, data, wstrb = m.group(1), int(m.group(2), 16), int(m.group(3), 16), m.group(4)
        if kind == "ifetch" and first_ifetch is None:
            first_ifetch = (addr, data)
        if addr == 0x3FC and kind == "write":
            if wstrb != "1111":
                errors.append("write to 0x3fc with wstrb=" + str(wstrb))
            if data != count:
                errors.append("write #%d to 0x3fc has value %d, expected %d" % (count, data, count))
                count = data
            count += 1
            last_written = data
        elif addr == 0x3FC and kind == "read":
            if data != last_written:
                errors.append("read of 0x3fc returned %d, last written %s" % (data, last_written))
if first_ifetch != (0, 0x3FC00093):
    got = "none" if first_ifetch is None else "addr 0x%08x data 0x%08x" % first_ifetch
    errors.append("first ifetch is %s, expected addr 0x00000000 data 0x3fc00093" % got)
if count < min_count:
    errors.append("only %d writes to 0x3fc, expected >= %d" % (count, min_count))
if errors:
    print("; ".join(errors[:3]))
    sys.exit(1)
print("derived check (upstream prints no success text): counter at 0x3fc counted 0..%d, %d writes, all reads consistent, no X/Z" % (last_written, count))
PY
  then
    CHECK_OK=1
  else
    CHECK_OK=0
  fi
  CHECK_EVIDENCE=$(cat "$out")
  rm -f "$out"
}

# ---------------------------------------------------------------- runner

N_PASS=0
N_FAIL=0
N_NA=0
FAILED_REQUIRED=0

record() { # target status rc secs evidence
  printf '%-15s %-4s rc=%-3s %4ss  %s\n' "$1" "$2" "$3" "$4" "$5" >> "$ROWS"
  echo "[core-stock] $1: $2 ($4 s) $5"
  case "$2" in
    PASS) N_PASS=$((N_PASS + 1)) ;;
    FAIL) N_FAIL=$((N_FAIL + 1)) ;;
    N/A)  N_NA=$((N_NA + 1)) ;;
  esac
}

run_target() { # target
  local t=$1 log="$LOGS/$1.log" rc=0 t0=$SECONDS status ev
  echo "[core-stock] make ${MAKE_ARGS[*]} $t ..."
  ( cd "$SRC" && make "${MAKE_ARGS[@]}" "$t" ) > "$log" 2>&1 || rc=$?
  case "$t" in
    test_ez) eval_ez "$log" ;;
    *)       eval_riscv_tb "$log" ;;
  esac
  if [ "$t" = test_synth ] && [ ! -s "$SRC/synth.v" ]; then
    CHECK_OK=0; CHECK_EVIDENCE="${CHECK_EVIDENCE}; synth.v missing or empty"
  fi
  if [ "$rc" -ne 0 ]; then
    status=FAIL
    ev="make exited with $rc; last log line: $(tail -n 1 "$log" | cut -c1-160); $CHECK_EVIDENCE"
  elif [ "$CHECK_OK" = 1 ]; then
    status=PASS
    ev=$CHECK_EVIDENCE
  else
    status=FAIL
    ev=$CHECK_EVIDENCE
  fi
  record "$t" "$status" "$rc" "$((SECONDS - t0))" "$ev"
  if [ "$status" = FAIL ]; then FAILED_REQUIRED=1; fi
}

# ---------------------------------------------------------------- run

for t in $REQUIRED_TARGETS; do
  run_target "$t"
done

# test_rvf needs rvfimon.v (module picorv32_rvfimon, instantiated by testbench.v under
# RISCV_FORMAL), which the PicoRV32 repo does not ship. The upstream README only points
# to YosysHQ/riscv-formal as the formal-verification framework; that rvfimon.v comes
# from it is background knowledge that cannot be checked offline. Neither that repo nor
# any rvfimon.v is in this repo, and riscv-formal is not in toolchain.md. Run it only
# if the file is available offline inside the repo. Otherwise run make once anyway and accept N/A
# only for the exact "No rule to make target 'rvfimon.v'" failure (not a FAIL);
# any other failure is a FAIL.
# Note: the upstream test_rvf rule runs vvp with +vcd, so a real run writes a very
# large testbench.vcd (about 370 MB with a stub monitor) into runs/core_stock/src.
RVFIMON=$(find "$ROOT" -name 'rvfimon.v' -not -path "$ROOT/runs/*" 2>/dev/null | first_line || true)
if [ -n "$RVFIMON" ]; then
  cp "$RVFIMON" "$SRC/rvfimon.v"
  run_target test_rvf
else
  rvf_rc=0
  ( cd "$SRC" && make "${MAKE_ARGS[@]}" test_rvf ) > "$LOGS/test_rvf.log" 2>&1 || rvf_rc=$?
  if [ "$rvf_rc" -ne 0 ] && grep -aq "No rule to make target .rvfimon\.v" "$LOGS/test_rvf.log"; then
    record test_rvf N/A "$rvf_rc" 0 "rvfimon.v not in repo (riscv-formal is not in the repo or toolchain.md and needs a network clone); $(grep -a 'No rule to make target' "$LOGS/test_rvf.log" | first_line)"
  else
    record test_rvf FAIL "$rvf_rc" 0 "make test_rvf failed for an unexpected reason, see $LOGS/test_rvf.log"
    FAILED_REQUIRED=1
  fi
fi

# ---------------------------------------------------------------- post checks

DIRTY=$(git -C "$SUBMODULE" status --porcelain)
HAVE_AFTER=$(git -C "$SUBMODULE" rev-parse HEAD)
if [ -z "$DIRTY" ] && [ "$HAVE_AFTER" = "$want" ]; then
  record submodule_clean PASS 0 0 "git -C $SUBMODULE status --porcelain is empty, HEAD is still ${want:0:12}"
else
  record submodule_clean FAIL 0 0 "submodule modified: $(printf '%s' "$DIRTY" | first_line) HEAD=${HAVE_AFTER:0:12}"
  FAILED_REQUIRED=1
fi

# ---------------------------------------------------------------- summary

TOOLCHAIN_DOC="n/a (env/check_toolchain_doc.py not found)"
if [ -f env/check_toolchain_doc.py ]; then
  if TC_OUT=$(python3 env/check_toolchain_doc.py 2>&1); then
    TOOLCHAIN_DOC="PASS ($(printf '%s' "$TC_OUT" | first_line))"
  else
    TOOLCHAIN_DOC="STALE (informational, fix toolchain.md): $(printf '%s' "$TC_OUT" | tr '\n' ' ')"
  fi
fi

if [ "$FAILED_REQUIRED" = 0 ]; then RESULT=PASS; else RESULT=FAIL; fi
{
  echo "core-stock (L1a) summary"
  echo "date:        $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "repo HEAD:   $(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "picorv32:    $have (pinned $want)"
  echo "source:      git archive of the submodule, extracted to $SRC"
  echo "overrides:   ${MAKE_ARGS[*]}  (no other make-variable overrides)"
  echo "tools used:"
  echo "  iverilog:  $(iverilog -V 2>&1 | first_line)"
  echo "  vvp:       $(vvp -V 2>&1 | first_line)"
  echo "  yosys:     $(yosys -V 2>&1 | first_line)"
  echo "  gcc:       $("${TOOLCHAIN_PREFIX}gcc" --version 2>&1 | first_line)"
  echo "  objcopy:   $("${TOOLCHAIN_PREFIX}objcopy" --version 2>&1 | first_line)"
  echo "  python3:   $(python3 --version 2>&1 | first_line)"
  echo "  make:      $(make --version 2>&1 | first_line)"
  echo "  bash:      $(bash --version 2>&1 | first_line)"
  echo "toolchain.md: $TOOLCHAIN_DOC"
  echo "targets:"
  sed 's/^/  /' "$ROWS"
  echo "runtime:     $((SECONDS - T_START)) s total"
  echo "counts:      PASS=$N_PASS FAIL=$N_FAIL N/A=$N_NA (required: $REQUIRED_TARGETS submodule_clean)"
  echo "core-stock: $RESULT"
} > "$SUMMARY"
rm -f "$ROWS"

echo
cat "$SUMMARY"
[ "$RESULT" = PASS ]
