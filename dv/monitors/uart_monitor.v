// uart_monitor.v - UART TX line monitor and decoder (checker name: uart_monitor).
// Contract: docs/spec/soc_spec.md section 7.2.
//
// The line is sampled once per clock on the falling edge (mid-cycle), so all
// offsets below are in clock cycles. A frame starts at the first 1->0
// transition seen while idle. Inside a frame (until FRAME-1 cycles after the
// start edge) every transition must lie at start + k*BIT_CYCLES +/- 1 cycle
// with k in 1..9, the start bit must still be 0 at mid-bit and the stop bit
// must be 1 at mid-bit. Data bits are sampled at mid-bit (LSB first).
// simpleuart's idle-high dummy periods (after reset and after DIV writes) are
// just idle time for this monitor.
`timescale 1ns/1ps
`default_nettype none

module uart_monitor #(
    parameter integer BIT_CYCLES = 20,
    parameter integer MAX_MSGS   = 20
) (
    input  wire        clk,
    input  wire        active,      // 1 after reset release
    input  wire [31:0] cycle,
    input  wire        line,        // uart_tx
    input  wire [31:0] fd,          // file for decoded bytes (0: none)
    output reg  [31:0] idle_cycles, // consecutive idle-high cycles outside a frame
    output reg         in_frame,
    output reg  [31:0] fail_count,
    output reg  [31:0] byte_count
);
    localparam integer FRAME = 10 * BIT_CYCLES;
    localparam integer HALF  = BIT_CYCLES / 2;
    localparam integer TOL   = 1;

    reg        prev;
    reg        l;
    reg        handled;
    reg [7:0]  data;
    reg [31:0] start_cycle;
    integer    off;
    integer    k;
    integer    d;

    initial begin
        idle_cycles = 32'd0;
        in_frame    = 1'b0;
        fail_count  = 32'd0;
        byte_count  = 32'd0;
        prev        = 1'b1;
        l           = 1'b1;
        handled     = 1'b0;
        data        = 8'd0;
        start_cycle = 32'd0;
        off         = 0;
        k           = 0;
        d           = 0;
    end

    // Counts one failure; the caller prints the message when fail_count <= MAX_MSGS.
    task note_fail;
        begin
            fail_count = fail_count + 32'd1;
            if (fail_count == MAX_MSGS + 1)
                $display("[CHK:uart_monitor] FAIL more than %0d uart_monitor failures, further messages suppressed", MAX_MSGS);
        end
    endtask

    always @(negedge clk) begin
        if (active !== 1'b1) begin
            in_frame    = 1'b0;
            prev        = 1'b1;
            idle_cycles = 32'd0;
        end else begin
            // X/Z on the line is reported by x_check (Icarus); treat it as idle here.
            l       = (line === 1'b0) ? 1'b0 : 1'b1;
            handled = 1'b0;
            if (in_frame) begin
                off = off + 1;
                if (off >= FRAME - TOL) begin
                    // Frame window closed; a falling edge here is the next start bit.
                    in_frame = 1'b0;
                end else begin
                    handled = 1'b1;
                    if (l != prev) begin
                        k = (off + HALF) / BIT_CYCLES;
                        d = off - k * BIT_CYCLES;
                        if (k < 1 || k > 9 || d > TOL || d < -TOL) begin
                            note_fail;
                            if (fail_count <= MAX_MSGS)
                                $display("[CHK:uart_monitor] FAIL edge timing: transition to %0d at start+%0d cycles (start bit edge at cycle %0d), expected start+k*%0d +/- %0d",
                                         l, off, start_cycle, BIT_CYCLES, TOL);
                        end
                    end
                    if ((off % BIT_CYCLES) == HALF) begin
                        k = off / BIT_CYCLES;
                        if (k == 0) begin
                            if (l != 1'b0) begin
                                note_fail;
                                if (fail_count <= MAX_MSGS)
                                    $display("[CHK:uart_monitor] FAIL framing: start bit is 1 at mid-bit (start bit edge at cycle %0d)", start_cycle);
                                in_frame = 1'b0;   // glitch: hunt for the next start bit
                            end
                        end else if (k <= 8) begin
                            data[k-1] = l;
                        end else begin
                            if (l != 1'b1) begin
                                note_fail;
                                if (fail_count <= MAX_MSGS)
                                    $display("[CHK:uart_monitor] FAIL framing: stop bit is 0 for byte 0x%02x (start bit edge at cycle %0d)", data, start_cycle);
                            end
                            if (fd != 32'd0)
                                $fwrite(fd, "%c", data);
                            byte_count = byte_count + 32'd1;
                        end
                    end
                end
            end
            if (!handled) begin
                if (!in_frame && prev == 1'b1 && l == 1'b0) begin
                    in_frame    = 1'b1;
                    off         = 0;
                    start_cycle = cycle;
                    data        = 8'd0;
                    idle_cycles = 32'd0;
                end else if (!in_frame && l == 1'b1) begin
                    if (idle_cycles != 32'hFFFF_FFFF)
                        idle_cycles = idle_cycles + 32'd1;
                end else begin
                    idle_cycles = 32'd0;
                end
            end
            prev = l;
        end
    end
endmodule

`default_nettype wire
