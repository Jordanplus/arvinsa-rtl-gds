#!/usr/bin/env bash
# =============================================================================
# rtl/scripts/lint.sh -- Verilator lint for soc_top (make lint).
# Contract: docs/spec/soc_spec.md section 8.
#   verilator --lint-only -Wall --top-module soc_top rtl/lint/waivers.vlt
#             -f rtl/rtl.f <SRAM blackbox>
# Variants: default, -DUSE_POWER_PINS, and every RTL bug injection define, for the
# PicoRV32 build (rtl/rtl.f) and the Hazard3 build (rtl/rtl_hazard3.f, -DSOC_CPU_HAZARD3,
# variant names hazard3[+<define>]; Phase 5, ADR-0011). A bug define is linted on the
# CPUs its dv/bugs.toml entry applies to (cpus = [...], default both).
# Any warning or error in any variant -> FAIL (exit 1).
# RTL-owned files (rtl/soc, rtl/bus, rtl/periph, rtl/cpu) may not carry any waiver.
# Bug injection defines: the single list is dv/bugs.toml (define = "BUG_...").
# Both directions are checked: every define there has an `ifdef/`ifndef/
# `elsif in the RTL-owned files, and every BUG_* used in those files has a
# dv/bugs.toml entry (no injected bug without a negative test).
# Logs: runs/rtl/lint/<variant>.log
# Compatible with bash 3.2.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT=runs/rtl/lint
FILELIST=rtl/rtl.f
FILELIST_H3=rtl/rtl_hazard3.f
WAIVERS=rtl/lint/waivers.vlt
SRAM_BB=ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sky130_sram_2kbyte_1rw1r_32x512_8.bb.v
OWN_SRC="rtl/soc rtl/bus rtl/periph rtl/cpu"
BUGS_TOML=dv/bugs.toml
BUGS=$( (grep -oE '^[[:space:]]*define[[:space:]]*=[[:space:]]*"BUG_[A-Za-z0-9_]+"' "$BUGS_TOML" || true) \
        | grep -oE 'BUG_[A-Za-z0-9_]+' | sort -u | tr '\n' ' ' || true)
RTL_BUGS=$( (grep -rhoE '`(ifdef|ifndef|elsif)[[:space:]]+BUG_[A-Za-z0-9_]+' $OWN_SRC || true) \
        | grep -oE 'BUG_[A-Za-z0-9_]+' | sort -u | tr '\n' ' ' || true)
# Bug defines per CPU (dv/bugs.toml cpus), from the DV loader so both read the file the same way.
bugs_for() {
    python3 -c 'import sys; sys.path.insert(0, "dv/scripts"); import dvlib
print(" ".join(sorted({b["define"] for b in dvlib.load_bugs().values() if b["define"] and dvlib.applies(b, sys.argv[1])})))' "$1"
}
BUGS_P=$(bugs_for picorv32)
BUGS_H=$(bugs_for hazard3)
VARIANTS="default USE_POWER_PINS $BUGS_P hazard3 hazard3+USE_POWER_PINS"
for b in $BUGS_H; do VARIANTS="$VARIANTS hazard3+$b"; done

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
OWN_WAIVER_RE='^[[:space:]]*lint_off.*rtl/(soc|bus|periph|cpu)'
if grep -nE "$OWN_WAIVER_RE" "$WAIVERS" >/dev/null 2>&1; then
    echo "  FAIL  policy: $WAIVERS waives an RTL-owned file:"
    grep -nE "$OWN_WAIVER_RE" "$WAIVERS" | sed 's/^/        /'
    fail=1
fi

# 2. Bug injection defines: dv/bugs.toml and the RTL must name the same set.
if [ -z "$BUGS" ]; then
    echo "  FAIL  no define = \"BUG_...\" entries found in $BUGS_TOML"
    fail=1
fi
for b in $BUGS; do
    if ! grep -rqE "\`(ifdef|ifndef|elsif)[[:space:]]+$b([^0-9A-Za-z_]|\$)" $OWN_SRC; then
        echo "  FAIL  $b: in $BUGS_TOML but no \`ifdef/\`elsif $b in $OWN_SRC"
        fail=1
    fi
done
for b in $RTL_BUGS; do
    case " $BUGS " in
        *" $b "*) ;;
        *)  echo "  FAIL  $b: used in $OWN_SRC but no dv/bugs.toml entry has define = \"$b\" (injected bug without a negative test)"
            fail=1 ;;
    esac
done
echo "lint: bug injection defines (dv/bugs.toml = RTL): $BUGS"

# 3. Lint every variant.
for v in $VARIANTS; do
    defs=""
    flist="$FILELIST"
    case "$v" in
        default) ;;
        hazard3) defs="-DSOC_CPU_HAZARD3"; flist="$FILELIST_H3" ;;
        hazard3+*) defs="-DSOC_CPU_HAZARD3 -D${v#hazard3+}"; flist="$FILELIST_H3" ;;
        *) defs="-D$v" ;;
    esac
    log="$OUT/$v.log"
    set +e
    verilator --lint-only -Wall --top-module soc_top $defs \
        "$WAIVERS" -f "$flist" "$SRAM_BB" >"$log" 2>&1
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
