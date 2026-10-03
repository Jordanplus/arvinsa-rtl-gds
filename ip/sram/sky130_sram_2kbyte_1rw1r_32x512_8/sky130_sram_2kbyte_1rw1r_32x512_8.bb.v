// Blackbox declaration of the sky130 OpenRAM 2 KB SRAM macro for lint and synthesis.
// Port list mirrors upstream/sky130_sram_2kbyte_1rw1r_32x512_8.v exactly.
// Do NOT add this file to simulation; simulation uses sim/sky130_sram_2kbyte_1rw1r_32x512_8.v.
(* blackbox *)
module sky130_sram_2kbyte_1rw1r_32x512_8 (
`ifdef USE_POWER_PINS
    inout         vccd1,
    inout         vssd1,
`endif
    // Port 0: RW
    input         clk0,
    input         csb0,     // active-low chip select
    input         web0,     // active-low write enable
    input  [3:0]  wmask0,   // byte write mask
    input  [8:0]  addr0,    // word address
    input  [31:0] din0,
    output [31:0] dout0,
    // Port 1: R (unused in this SoC, must be tied off: csb1=1, clk1=0, addr1=0)
    input         clk1,
    input         csb1,
    input  [8:0]  addr1,
    output [31:0] dout1
);
endmodule
