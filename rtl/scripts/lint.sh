#!/usr/bin/env bash
# =============================================================================
# rtl/scripts/lint.sh -- Verilator lint for soc_top (make lint).
# Contract: docs/spec/soc_spec.md section 8.
#   verilator --lint-only -Wall --top-module soc_top rtl/lint/waivers.vlt
#             -f rtl/rtl.f <SRAM blackbox>
# Variants: default, -DUSE_POWER_PINS, and every RTL bug injection define.
# Any warning or error in any variant -> FAIL (exit 1).
# RTL-owned files (rtl/soc, rtl/bus, rtl/periph) may not carry any waiver.
# Logs: runs/rtl/lint/<variant>.log
# Compatible with bash 3.2.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT=runs/rtl/lint
FILELIST=rtl/rtl.f
WAIVERS=rtl/lint/waivers.vlt
SRAM_BB=ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sky130_sram_2kbyte_1rw1r_32x512_8.bb.v
OWN_SRC="rtl/soc rtl/bus rtl/periph"
BUGS="BUG_R01 BUG_R02 BUG_R03 BUG_R04 BUG_R05 BUG_R07 BUG_R08 BUG_R09 BUG_R10 BUG_R11 BUG_R12 BUG_R13 BUG_R14 BUG_R15"
VARIANTS="default USE_POWER_PINS $BUGS"

if ! command -v verilator >/dev/null 2>&1; then
    echo "LINT: FAIL (verilator not found in PATH)"
    exit 1
fi

mkdir -p "$OUT"
fail=0

echo "lint: $(verilator --version)"

# 1. Policy: RTL-owned files carry no waiver (inline or in waivers.vlt).
if grep -rn 'lint_off' $OWN_SRC >/dev/null 2>&1; then
    echo "  FAIL  policy: inline lint_off found in RTL-owned files:"
    grep -rn 'lint_off' $OWN_SRC | sed 's/^/        /'
    fail=1
fi
OWN_WAIVER_RE='^[[:space:]]*lint_off.*rtl/(soc|bus|periph)'
if grep -nE "$OWN_WAIVER_RE" "$WAIVERS" >/dev/null 2>&1; then
    echo "  FAIL  policy: $WAIVERS waives an RTL-owned file:"
    grep -nE "$OWN_WAIVER_RE" "$WAIVERS" | sed 's/^/        /'
    fail=1
fi

# 2. Every bug injection define must exist in RTL-owned sources.
for b in $BUGS; do
    if ! grep -rqE "\`ifn?def[[:space:]]+$b([^0-9A-Za-z_]|\$)" $OWN_SRC; then
        echo "  FAIL  $b: no \`ifdef $b in $OWN_SRC"
        fail=1
    fi
done

# 3. Lint every variant.
for v in $VARIANTS; do
    defs=""
    if [ "$v" != "default" ]; then
        defs="-D$v"
    fi
    log="$OUT/$v.log"
    set +e
    verilator --lint-only -Wall --top-module soc_top $defs \
        "$WAIVERS" -f "$FILELIST" "$SRAM_BB" >"$log" 2>&1
    rc=$?
    set -e
    nwarn=$(grep -c '^%Warning' "$log" || true)
    nerr=$(grep -c '^%Error' "$log" || true)
    if [ "$rc" -ne 0 ] || [ "$nwarn" -ne 0 ] || [ "$nerr" -ne 0 ]; then
        echo "  FAIL  $v (rc=$rc, warnings=$nwarn, errors=$nerr), log: $log"
        grep -E '^%(Warning|Error)' "$log" | head -20 | sed 's/^/        /'
        fail=1
    else
        echo "  PASS  $v"
    fi
done

nvar=$(echo $VARIANTS | wc -w | tr -d ' ')
if [ "$fail" -ne 0 ]; then
    echo "LINT: FAIL (see $OUT/)"
    exit 1
fi
echo "LINT: PASS ($nvar variants, 0 warnings, 0 errors)"
