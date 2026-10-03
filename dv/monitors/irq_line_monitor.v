// irq_line_monitor.v - test IRQ line checker (checker name: irq_line).
// Contract: docs/spec/soc_spec.md sections 4.1 and 4.8: irq[SOC_IRQ_TEST] of
// u_cpu is TEST_CTRL.IRQ_TRIG[0] (a level, reset 0).
//
// Sampled on the falling clock edge. The checker keeps its own copy of
// IRQ_TRIG[0], taken from the CPU bus: it is reset to 0 while resetn=0 and set
// to mem_wdata[0] at the handshake of every IRQ_TRIG write. Outside an
// IRQ_TRIG write transaction the line must equal that copy in every cycle;
// during the write (first cycle to handshake) either value is accepted, so the
// check does not depend on the exact bus cycle in which the register updates.
// A mismatch episode (line held after the clear, a pulse instead of a level,
// a line stuck at 0, ...) is reported once.
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module irq_line_monitor #(
    parameter integer MAX_MSGS = 20
) (
    input  wire        clk,
    input  wire        active,
    input  wire [31:0] cycle,
    input  wire        resetn,
    input  wire        mem_valid,
    input  wire        mem_ready,
    input  wire [31:0] mem_addr,
    input  wire [31:0] mem_wdata,
    input  wire [3:0]  mem_wstrb,
    input  wire        irq_line,     // u_cpu.irq[SOC_IRQ_TEST]
    output reg  [31:0] fail_count
);
    localparam [31:0] IRQ_ADDR = `SOC_TEST_BASE + `SOC_TEST_IRQ_OFF;

    reg        model;
    reg        rep;
    reg [31:0] last_wr_cycle;
    reg [31:0] last_wr_data;
    reg [31:0] bad_start;

    initial begin
        fail_count    = 32'd0;
        model         = 1'b0;
        rep           = 1'b0;
        last_wr_cycle = 32'd0;
        last_wr_data  = 32'd0;
        bad_start     = 32'd0;
    end

    always @(negedge clk) begin
        if (active !== 1'b1 || resetn !== 1'b1) begin
            model = 1'b0;
            rep   = 1'b0;
        end else if (mem_valid === 1'b1 && mem_wstrb != 4'd0 && mem_addr == IRQ_ADDR) begin
            if (mem_ready === 1'b1) begin
                model         = mem_wdata[0];
                last_wr_cycle = cycle;
                last_wr_data  = mem_wdata;
            end
        end else if (irq_line !== model) begin
            if (!rep) begin
                rep       = 1'b1;
                bad_start = cycle;
                fail_count = fail_count + 32'd1;
                if (fail_count <= MAX_MSGS)
                    $display("[CHK:irq_line] FAIL irq[%0d]=%b but IRQ_TRIG[0]=%b (last IRQ_TRIG write 0x%08x at cycle %0d); spec 4.8: the line is the IRQ_TRIG[0] level (cycle %0d)",
                             `SOC_IRQ_TEST, irq_line, model, last_wr_data, last_wr_cycle, cycle);
                else if (fail_count == MAX_MSGS + 1)
                    $display("[CHK:irq_line] FAIL more than %0d irq_line failures, further messages suppressed", MAX_MSGS);
            end
        end else if (rep) begin
            rep = 1'b0;
            $display("[TB] irq_line: irq[%0d] matches IRQ_TRIG[0] again at cycle %0d (mismatch for %0d cycles)",
                     `SOC_IRQ_TEST, cycle, cycle - bad_start);
        end
    end
endmodule

`default_nettype wire
