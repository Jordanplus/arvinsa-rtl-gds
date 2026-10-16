#!/bin/sh
# GPIO 33-37 and the management SoC's GPIO configuration transfer: build and run tb_gpio_xfer.v, read the
# gate-level netlists, and compare everything with the logs kept in this directory (README.md here).
#
# usage: sh docs/evidence/arvinsa-rtl-gds/runs/p7_gpio_xfer/run.sh [OUT_DIR]
#   OUT_DIR   where the new logs go (default: a new temporary directory); give this directory to overwrite the kept logs
#   CARAVEL   caravel-lite 2024.09.12-1 directory (default <repo>/.tools/caravel-lite, which git ignores;
#             how to get it: docs/report/figures/scripts/caravel_chip.py docstring)
#   PDK_ROOT  ciel PDK root (default ~/.ciel); its sky130A should be SKY130_PDK_HASH of env/versions.mk
# Needs iverilog / vvp (Icarus Verilog 13.0) and python3. Exit 1 when a log differs from the kept one.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../../../.." && pwd)
CARAVEL=${CARAVEL:-$REPO/.tools/caravel-lite}
R=$CARAVEL/verilog/rtl
G=$CARAVEL/verilog/gl
PDK=${PDK_ROOT:-$HOME/.ciel}/sky130A
P=$PDK/libs.ref
OUT=${1:-$(mktemp -d)}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
BUILD=$(mktemp -d)

blob=$(git hash-object "$CARAVEL/def/chip_io.def")
if [ "$blob" != 9af4f4037af382bb01eb3ff256e4a251a585ce6a ]; then
    echo "run.sh: $CARAVEL is not caravel-lite 2024.09.12-1 (def/chip_io.def blob $blob)" >&2
    exit 1
fi

home() { sed "s|$HOME|~|g"; }   # the repo is public: no home directory in the kept logs

{
    echo "iverilog: $(iverilog -V 2>&1 | head -1)"
    echo "python3:  $(python3 --version 2>&1)"
    echo "caravel-lite: def/chip_io.def git blob $blob (tag 2024.09.12-1, commit 5593d992)"
    echo "sky130A: $(python3 -I -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$PDK" | grep -o '[0-9a-f]\{40\}' || echo unknown)"
    echo "env/versions.mk: $(grep '^SKY130_PDK_HASH' "$REPO/env/versions.mk" | tr -s ' ')"
    echo "sha256:"
    (cd "$CARAVEL/.." && shasum -a 256 caravel-lite/verilog/rtl/caravel_core.v caravel-lite/verilog/rtl/housekeeping.v \
        caravel-lite/verilog/rtl/gpio_control_block.v caravel-lite/verilog/rtl/gpio_defaults_block.v \
        caravel-lite/verilog/rtl/user_defines.v caravel-lite/verilog/gl/housekeeping.v caravel-lite/verilog/gl/caravel_core.v)
    (cd "$REPO" && shasum -a 256 rtl/caravel/user_defines.v)
} > "$OUT/versions.txt"

# $1 = user_defines.v, $2 = output. Compiled from this directory so the logs name the testbench without a path.
build() {
    (cd "$HERE" && iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY=#1 -I "$R" -o "$2" \
        "$R/defines.v" "$1" \
        "$P/sky130_fd_sc_hd/verilog/primitives.v" "$P/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v" \
        "$P/sky130_fd_sc_hvl/verilog/primitives.v" "$P/sky130_fd_sc_hvl/verilog/sky130_fd_sc_hvl.v" \
        "$R/caravel_core.v" "$R/caravel_clocking.v" "$R/clock_div.v" "$R/digital_pll.v" \
        "$R/housekeeping.v" "$R/housekeeping_spi.v" "$R/gpio_control_block.v" "$R/gpio_defaults_block.v" \
        "$R/gpio_logic_high.v" "$R/mgmt_protect.v" "$R/mgmt_protect_hv.v" "$R/mprj_logic_high.v" \
        "$R/mprj2_logic_high.v" "$R/mprj_io_buffer.v" "$R/manual_power_connections.v" "$R/empty_macro.v" \
        "$R/spare_logic_block.v" "$R/simple_por.v" "$R/xres_buf.v" "$R/user_id_programming.v" \
        stubs.v tb_gpio_xfer.v)
}

# this project's user_defines.v (GPIO 33-37 in user mode at power-up)
build "$REPO/rtl/caravel/user_defines.v" "$BUILD/core.vvp" 2>&1 | home > "$OUT/compile.log"
for c in 0 1 2 3 4 5; do
    vvp -n "$BUILD/core.vvp" +case=$c 2>&1 | home > "$OUT/case$c.log"
done
# control: the caravel-lite template user_defines.v (GPIO 5-37 in management mode), no transfer. The checks of
# the testbench must say NO here, which shows they can fail.
build "$R/user_defines.v" "$BUILD/template.vvp" 2>&1 | home > "$OUT/compile_template.log"
vvp -n "$BUILD/template.vvp" +case=2 2>&1 | home > "$OUT/control_template_defines.log"

# gate-level netlists: reset values of housekeeping's stored GPIO configuration, and the reset nets
python3 -I "$HERE/gl_reset_values.py" "$G/housekeeping.v" > "$OUT/gl_reset_values.log"
{
    python3 -I "$HERE/gl_trace_net.py" "$G/caravel_core.v" housekeeping porb
    python3 -I "$HERE/gl_trace_net.py" "$G/caravel_core.v" housekeeping wb_rstn_i
    python3 -I "$HERE/gl_trace_net.py" "$G/caravel_core.v" clock_ctrl resetb
} > "$OUT/gl_reset_nets.log"
rm -rf "$BUILD"

echo "run.sh: logs in $OUT" | home
[ "$OUT" = "$HERE" ] && exit 0
status=0
for f in versions.txt compile.log case0.log case1.log case2.log case3.log case4.log case5.log compile_template.log \
         control_template_defines.log gl_reset_values.log gl_reset_nets.log; do
    if diff -u "$HERE/$f" "$OUT/$f" > /dev/null; then
        echo "  $f: same as the kept log"
    else
        echo "  $f: DIFFERS from the kept log (diff -u $HERE/$f $OUT/$f)" | home
        status=1
    fi
done
exit $status
