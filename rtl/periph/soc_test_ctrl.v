// =============================================================================
// soc_test_ctrl.v -- TEST_CTRL registers. Contract: docs/spec/soc_spec.md
// sections 2, 3.1 and 4.8.
//   SOC_TEST_SIG_OFF  : SIG, RW, reset 0.
//   SOC_TEST_DONE_OFF : DONE, W: PASS magic / FAIL code; R: last value written.
//   SOC_TEST_IRQ_OFF  : IRQ_TRIG, RW, reset 0; bit 0 drives irq_test.
// Probe names (spec section 3.1): done_strobe, done_value, sig_value.
// done_strobe is high for exactly one cycle per DONE write: the cycle right
// after the rising edge that performs the write (same cycle in which
// done_value first shows the new value).
// Bug injection (dv/bugs.toml): BUG_R12 (SIG and IRQ_TRIG read back 0),
// BUG_R14 (irq_test stays high 200 cycles after IRQ_TRIG[0] is cleared),
// BUG_R15 (DONE reads back 0), BUG_R16 (partial offset decode: an IRQ_TRIG
// write also writes SIG), BUG_R20 (irq_test stays high 40 cycles after
// IRQ_TRIG[0] is cleared), BUG_R22 (irq_test is a one-cycle pulse per
// IRQ_TRIG write with bit 0 set, not the IRQ_TRIG[0] level).
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module soc_test_ctrl (
    input  wire        clk,
    input  wire        resetn,      // synchronous, active low
    input  wire        req,
    input  wire        we,
    input  wire [3:0]  off,         // byte offset inside the TEST_CTRL window
    input  wire [31:0] wdata,
    output wire [31:0] rdata,
    output wire        irq_test     // IRQ_TRIG[0]
);

    localparam [31:0] SIG_OFF  = `SOC_TEST_SIG_OFF;
    localparam [31:0] DONE_OFF = `SOC_TEST_DONE_OFF;
    localparam [31:0] IRQ_OFF  = `SOC_TEST_IRQ_OFF;

    wire sig_hit  = (off == SIG_OFF[3:0]);
    wire done_hit = (off == DONE_OFF[3:0]);
    wire irq_hit  = (off == IRQ_OFF[3:0]);

    wire wr      = req & we;
`ifdef BUG_R16
    // BUG_R16: SIG write enable decodes off[2] only, so an IRQ_TRIG write
    // (offset 8) also writes SIG.
    wire sig_we  = wr & ~off[2];
`else
    wire sig_we  = wr & sig_hit;
`endif
    wire done_we = wr & done_hit;
    wire irq_we  = wr & irq_hit;

    reg [31:0] sig_q;
    reg [31:0] done_q;
    reg [31:0] irq_trig_q;
    reg        done_strobe_q;

    always @(posedge clk) begin
        if (!resetn) begin
            sig_q         <= 32'h0000_0000;
            done_q        <= 32'h0000_0000;
            irq_trig_q    <= 32'h0000_0000;
            done_strobe_q <= 1'b0;
        end else begin
            if (sig_we)
                sig_q <= wdata;
            if (done_we)
                done_q <= wdata;
            if (irq_we)
                irq_trig_q <= wdata;
            done_strobe_q <= done_we;
        end
    end

    // Probe names (spec section 3.1)
    wire        done_strobe = done_strobe_q;
    wire [31:0] done_value  = done_q;
    wire [31:0] sig_value   = sig_q;

`ifdef BUG_R14
    // BUG_R14: the IRQ line is released 200 cycles after IRQ_TRIG[0] clears.
    reg [7:0] irq_hold_q;
    always @(posedge clk) begin
        if (!resetn)
            irq_hold_q <= 8'd0;
        else if (irq_trig_q[0])
            irq_hold_q <= 8'd200;
        else if (irq_hold_q != 8'd0)
            irq_hold_q <= irq_hold_q - 8'd1;
    end
    assign irq_test = irq_trig_q[0] | (irq_hold_q != 8'd0);
`elsif BUG_R20
    // BUG_R20: like BUG_R14, but the line is released only 40 cycles late.
    reg [5:0] irq_hold_q;
    always @(posedge clk) begin
        if (!resetn)
            irq_hold_q <= 6'd0;
        else if (irq_trig_q[0])
            irq_hold_q <= 6'd40;
        else if (irq_hold_q != 6'd0)
            irq_hold_q <= irq_hold_q - 6'd1;
    end
    assign irq_test = irq_trig_q[0] | (irq_hold_q != 6'd0);
`elsif BUG_R22
    // BUG_R22: one-cycle pulse per IRQ_TRIG write with bit 0 set, instead of
    // the IRQ_TRIG[0] level.
    reg irq_pulse_q;
    always @(posedge clk) begin
        if (!resetn)
            irq_pulse_q <= 1'b0;
        else
            irq_pulse_q <= irq_we & wdata[0];
    end
    assign irq_test = irq_pulse_q;
`else
    assign irq_test = irq_trig_q[0];
`endif

    // Read-back values of the three registers.
`ifdef BUG_R12
    // BUG_R12: the SIG and IRQ_TRIG read-back paths return 0.
    wire [31:0] sig_rd  = 32'h0000_0000;
    wire [31:0] irq_rd  = 32'h0000_0000;
    wire        unused_bug_r12 = &{1'b0, irq_trig_q[31:1], sig_value};
`else
    wire [31:0] sig_rd  = sig_value;
    wire [31:0] irq_rd  = irq_trig_q;
`endif
`ifdef BUG_R15
    // BUG_R15: the DONE read-back path returns 0.
    wire [31:0] done_rd = 32'h0000_0000;
    wire        unused_bug_r15 = &{1'b0, done_value};
`else
    wire [31:0] done_rd = done_value;
`endif
    assign rdata    = ({32{sig_hit }} & sig_rd )
                    | ({32{done_hit}} & done_rd)
                    | ({32{irq_hit }} & irq_rd );

    // done_strobe is a testbench probe only (spec section 3.1).
    wire unused_test_ctrl = &{1'b0, done_strobe};

endmodule

`default_nettype wire
