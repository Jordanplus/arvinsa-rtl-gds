// gl_lockstep.v - RTL vs gate-level lockstep checker (GL_LOCKSTEP builds only, dv/gl_soc/README.md).
//
// tb_soc instantiates the RTL soc_top (dut) and the final netlist (dut_gl, module soc_top_gl)
// with the same inputs. At every falling clock edge, after both copies have settled (the RTL
// updates at the rising edge, the sky130 flop models 1 ns later with UNIT_DELAY=#1), this
// checker compares:
//   - every soc_top output: uart_tx, gpio_out, trap, host_rdata
//   - SRAM port 0 pins: csb0 always; web0, addr0, wmask0 when csb0=0 (access);
//     din0 bytes whose wmask0 bit is 1 when csb0=0 and web0=0 (write)
// Port 1 of the SRAM is tied off in both copies and is not compared.
//
// X rule: a bit is compared only when the RTL value is 0 or 1. Then the gate-level bit must be
// identical (X or Z in the gate-level copy is a mismatch). An RTL bit that is X (for example a
// register without reset before its first write) may be anything in the gate-level copy, because
// synthesis may legally pick a value for it.
//
// Message: "[CHK:gl_lockstep] FAIL ..." (first MAX_MSG mismatches, then a count at the end).
// fail_count / compare_count are read by tb_soc finish_sim (tb_result.txt fail.gl_lockstep,
// gl_compares).
`timescale 1ns/1ps
`default_nettype none

module gl_lockstep #(
    parameter integer MAX_MSG = 10
) (
    input wire        clk,
    input wire        enable,       // 1 from the start of reset to the end of the run
    input wire [31:0] cycle,
    // outputs: {uart_tx, gpio_out[7:0], trap, host_rdata[31:0]}
    input wire [41:0] rtl_out,
    input wire [41:0] gl_out,
    // SRAM port 0: {csb0, web0, wmask0[3:0], addr0[8:0], din0[31:0]}
    input wire [46:0] rtl_sram,
    input wire [46:0] gl_sram
);
    integer fail_count    = 0;
    integer compare_count = 0;

    // 1 when every bit of `want` that is 0/1 has the same value in `have`.
    function automatic match_known(input [63:0] want, input [63:0] have, input [63:0] care);
        integer i;
        begin
            match_known = 1'b1;
            for (i = 0; i < 64; i = i + 1)
                if (care[i] && (want[i] === 1'b0 || want[i] === 1'b1) && have[i] !== want[i])
                    match_known = 1'b0;
        end
    endfunction

    task report(input [8*48-1:0] what, input [63:0] want, input [63:0] have);
        begin
            fail_count = fail_count + 1;
            if (fail_count <= MAX_MSG)
                $display("[CHK:gl_lockstep] FAIL cycle %0d: %0s RTL=0x%0h GL=0x%0h", cycle, what, want, have);
        end
    endtask

    wire        r_csb0   = rtl_sram[46];
    wire        r_web0   = rtl_sram[45];
    wire [3:0]  r_wmask0 = rtl_sram[44:41];
    wire [31:0] din_care = {{8{r_wmask0[3] === 1'b1}}, {8{r_wmask0[2] === 1'b1}},
                            {8{r_wmask0[1] === 1'b1}}, {8{r_wmask0[0] === 1'b1}}};

    always @(negedge clk) begin
        if (enable) begin
            compare_count = compare_count + 1;
            if (!match_known({22'd0, rtl_out}, {22'd0, gl_out}, {64{1'b1}}))
                report("outputs {uart_tx,gpio_out,trap,host_rdata}", {22'd0, rtl_out}, {22'd0, gl_out});
            if (!match_known({63'd0, r_csb0}, {63'd0, gl_sram[46]}, 64'd1))
                report("sram0.csb0", {63'd0, r_csb0}, {63'd0, gl_sram[46]});
            if (r_csb0 === 1'b0) begin
                if (!match_known({50'd0, rtl_sram[45:32]}, {50'd0, gl_sram[45:32]}, {64{1'b1}}))
                    report("sram0 {web0,wmask0,addr0}", {50'd0, rtl_sram[45:32]}, {50'd0, gl_sram[45:32]});
                if (r_web0 === 1'b0 && !match_known({32'd0, rtl_sram[31:0]}, {32'd0, gl_sram[31:0]}, {32'd0, din_care}))
                    report("sram0.din0 (written bytes)", {32'd0, rtl_sram[31:0]}, {32'd0, gl_sram[31:0]});
            end
        end
    end
endmodule

`default_nettype wire
