#!/usr/bin/env python3
"""Bug injection for the macro view QA (scripts/check_macro_views.py): make neg-macro-views.

A small consistent macro (LEF, .lib, Verilog, SPICE) must PASS (positive control); each case injects one
error and must FAIL with the expected reason:
  Q1 internal_power ten orders of magnitude off (the OpenRAM dev .lib of 2026-10-08: 1.036316e+11)
  Q2 a pin capacitance in the wrong unit        Q3 a nan in a table          Q4 a negative delay
  Q5 .lib area that is not the LEF size         Q6 GDS box not the LEF SIZE  Q7 a bus bit missing in the Verilog
  Q8 a direction that differs from the LEF      Q9 a power pin missing in the SPICE
  Q10 a view with another top name              Q11 no internal_power at all
Prints PASS n/n; exit 0 only when every case behaves as expected.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_macro_views as cmv  # noqa: E402

NAME = "neg_mac"
LEF = """MACRO neg_mac
   CLASS BLOCK ;
   SIZE 10.0 BY 20.0 ;
   PIN din0[0]
      DIRECTION INPUT ;
   END din0[0]
   PIN din0[1]
      DIRECTION INPUT ;
   END din0[1]
   PIN clk0
      DIRECTION INPUT ;
   END clk0
   PIN dout0
      DIRECTION OUTPUT ;
   END dout0
   PIN vccd1
      DIRECTION INOUT ;
      USE POWER ;
   END vccd1
   PIN vssd1
      DIRECTION INOUT ;
      USE GROUND ;
   END vssd1
END neg_mac
"""
LIB = """library (neg_mac_lib){
    capacitive_load_unit(1, pF) ;
cell (neg_mac){
    area : 200.0;
    cell_leakage_power : 0.01;
    pg_pin(vccd1) { voltage_name : VCCD1; pg_type : primary_power; }
    pg_pin(vssd1) { voltage_name : VSSD1; pg_type : primary_ground; }
    bus(din0){
        bus_type  : data;
        direction  : input;
        capacitance : 0.0045;
        pin(din0[1:0]){
        }
    }
    pin(dout0){
        direction  : output;
        timing(){
            timing_type : falling_edge;
            cell_rise(CELL_TABLE) {
                values("0.30, 0.40");
            }
            rise_transition(CELL_TABLE) {
                values("0.05, 0.06");
            }
        }
    }
    pin(clk0){
        clock : true;
        direction  : input;
        capacitance : 0.0069;
        internal_power(){
            when : "!csb0";
            rise_power(scalar){
                values("1.380840e+01");
            }
            fall_power(scalar){
                values("1.380840e+01");
            }
        }
    }
}
}
"""
VERILOG = """module neg_mac(
`ifdef USE_POWER_PINS
    vccd1,
    vssd1,
`endif
    clk0, din0, dout0
  );
  parameter DATA_WIDTH = 2 ;
`ifdef USE_POWER_PINS
    inout vccd1;
    inout vssd1;
`endif
  input  clk0;
  input [DATA_WIDTH-1:0]  din0;
  output dout0;
endmodule
"""
SPICE = """.SUBCKT neg_mac
+ din0[0] din0[1] clk0 dout0 vccd1
+ vssd1
* INPUT : din0[0]
* INPUT : din0[1]
* INPUT : clk0
* OUTPUT: dout0
* POWER : vccd1
* GROUND: vssd1
.ENDS neg_mac
"""
BOX = (0.0, 0.0, 10.0, 20.0)


def run(lef=LEF, lib=LIB, verilog=VERILOG, spice=SPICE, bbox=BOX):
    return cmv.check(NAME, {"lef": lef, "lib": {"neg.lib": lib}, "verilog": verilog, "spice": spice}, bbox)[0]


def sub(text, old, new):
    if old not in text:
        raise SystemExit(f"neg_macro_views: injection string not found: {old!r}")
    return text.replace(old, new)


def main():
    results = []

    def check(label, problems, want):
        ok = (not problems) if want is None else any(want in p for p in problems)
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: " + ("; ".join(problems) if problems else "PASS"))

    check("Q0 consistent views (positive control)", run(), None)
    check("Q1 internal_power 1.036316e+11", run(lib=sub(LIB, "1.380840e+01", "1.036316e+11")), "internal_power 1.036316e+11 outside")
    check("Q2 pin capacitance in fF written as pF", run(lib=sub(LIB, "capacitance : 0.0045;", "capacitance : 4.5;")), "pin capacitance 4.5")
    check("Q3 nan in a table", run(lib=sub(LIB, 'values("0.30, 0.40")', 'values("0.30, nan")')), "not finite")
    check("Q4 negative delay", run(lib=sub(LIB, 'values("0.30, 0.40")', 'values("-0.30, 0.40")')), "negative delay")
    check("Q5 .lib area is not the LEF size", run(lib=sub(LIB, "area : 200.0;", "area : 210.0;")), "area 210.0 != LEF")
    check("Q6 GDS box is not the LEF SIZE", run(bbox=(0.0, 0.0, 10.0, 20.5)), "!= GDS box")
    check("Q7 a bus bit missing in the Verilog", run(verilog=sub(VERILOG, "DATA_WIDTH = 2", "DATA_WIDTH = 1")),
          "Verilog signal pins differ from the LEF: missing ['din0[1]']")
    check("Q8 a direction differs from the LEF", run(lib=sub(LIB, "pin(dout0){\n        direction  : output;", "pin(dout0){\n        direction  : input;")),
          "direction differs from the LEF: dout0 input vs output")
    check("Q9 a power pin missing in the SPICE", run(spice=sub(SPICE, "+ vssd1\n", "")), "SPICE power pins ['vccd1'] != LEF")
    check("Q10 another top name in the .lib", run(lib=sub(LIB, "cell (neg_mac){", "cell (neg_mac2){")), "top names neg.lib=neg_mac2")
    check("Q11 no internal_power", run(lib=sub(LIB, "rise_power(scalar)", "rise_xx(scalar)").replace("fall_power(scalar)", "fall_xx(scalar)")),
          "no internal_power values")
    print(f"neg-macro-views: {'PASS' if all(results) else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
