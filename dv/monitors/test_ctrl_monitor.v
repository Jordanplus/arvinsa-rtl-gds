// test_ctrl_monitor.v - end-of-test protocol checker (checker name: test_ctrl).
// Contract: docs/spec/soc_spec.md sections 4.8 and 7.2 (test_ctrl row).
// done_strobe is high for exactly one cycle per DONE write, so it is sampled
// once per cycle on the falling edge. FAIL when a DONE value is not the PASS
// magic, and when DONE is written more than once.
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module test_ctrl_monitor #(
    parameter integer MAX_MSGS = 20
) (
    input  wire        clk,
    input  wire        active,
    input  wire [31:0] cycle,
    input  wire        done_strobe,
    input  wire [31:0] done_value,
    output reg         done_seen,
    output reg  [31:0] done_count,
    output reg  [31:0] first_done_value,
    output reg  [31:0] first_done_cycle,
    output reg  [31:0] fail_count
);
    localparam [31:0] PASS_MAGIC = `SOC_TEST_PASS_MAGIC;
    localparam [31:0] FAIL_BASE  = `SOC_TEST_FAIL_BASE;

    initial begin
        done_seen        = 1'b0;
        done_count       = 32'd0;
        first_done_value = 32'd0;
        first_done_cycle = 32'd0;
        fail_count       = 32'd0;
    end

    task note_fail;
        begin
            fail_count = fail_count + 32'd1;
            if (fail_count == MAX_MSGS + 1)
                $display("[CHK:test_ctrl] FAIL more than %0d test_ctrl failures, further messages suppressed", MAX_MSGS);
        end
    endtask

    always @(negedge clk) begin
        if (active === 1'b1 && done_strobe === 1'b1) begin
            done_count = done_count + 32'd1;
            if (done_count == 32'd1) begin
                done_seen        = 1'b1;
                first_done_value = done_value;
                first_done_cycle = cycle;
            end
            if (done_value !== PASS_MAGIC) begin
                note_fail;
                if (fail_count <= MAX_MSGS) begin
                    if ((done_value & 32'hFFFF_0000) === FAIL_BASE)
                        $display("[CHK:test_ctrl] FAIL DONE=0x%08x (firmware fail code 0x%04x), expected PASS magic 0x%08x (cycle %0d)",
                                 done_value, done_value[15:0], PASS_MAGIC, cycle);
                    else
                        $display("[CHK:test_ctrl] FAIL DONE=0x%08x is not the PASS magic 0x%08x (cycle %0d)", done_value, PASS_MAGIC, cycle);
                end
            end
            if (done_count > 32'd1) begin
                note_fail;
                if (fail_count <= MAX_MSGS)
                    $display("[CHK:test_ctrl] FAIL DONE written %0d times (this write 0x%08x at cycle %0d, first write 0x%08x at cycle %0d)",
                             done_count, done_value, cycle, first_done_value, first_done_cycle);
            end
        end
    end
endmodule

`default_nettype wire
