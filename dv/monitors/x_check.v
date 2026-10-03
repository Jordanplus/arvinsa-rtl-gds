// x_check.v - X/Z checker, Icarus only (checker name: x_check).
// Contract: docs/spec/soc_spec.md section 7.2 (x_check row).
//   - From RESET_SETTLE cycles after resetn is released: trap, uart_tx,
//     gpio_out and mem_valid must not be X/Z (reported once per X episode).
//   - At every read handshake (mem_valid & mem_ready & mem_wstrb==0):
//     mem_rdata must not contain X/Z.
// The module exists only when VERILATOR is not defined, because a 2-state
// simulator cannot see X/Z; tb_soc instantiates it under the same guard.
`timescale 1ns/1ps
`default_nettype none

`ifndef VERILATOR
module x_check #(
    parameter integer RESET_SETTLE = 20,
    parameter integer MAX_MSGS     = 20
) (
    input  wire        clk,
    input  wire        resetn,
    input  wire [31:0] cycle,
    input  wire        trap,
    input  wire        uart_tx,
    input  wire [7:0]  gpio_out,
    input  wire        mem_valid,
    input  wire        mem_ready,
    input  wire [3:0]  mem_wstrb,
    input  wire [31:0] mem_addr,
    input  wire [31:0] mem_rdata,
    output reg  [31:0] fail_count
);
    integer since;
    reg     x_trap, x_tx, x_gpio, x_valid;

    initial begin
        fail_count = 32'd0;
        since      = 0;
        x_trap     = 1'b0;
        x_tx       = 1'b0;
        x_gpio     = 1'b0;
        x_valid    = 1'b0;
    end

    task note_fail;
        begin
            fail_count = fail_count + 32'd1;
            if (fail_count == MAX_MSGS + 1)
                $display("[CHK:x_check] FAIL more than %0d x_check failures, further messages suppressed", MAX_MSGS);
        end
    endtask

    always @(negedge clk) begin
        if (resetn !== 1'b1) begin
            since = 0;
        end else begin
            if (since < RESET_SETTLE) begin
                since = since + 1;
            end else begin
                if (^trap === 1'bx) begin
                    if (!x_trap) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:x_check] FAIL trap is X/Z (cycle %0d)", cycle);
                    end
                    x_trap = 1'b1;
                end else x_trap = 1'b0;
                if (^uart_tx === 1'bx) begin
                    if (!x_tx) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:x_check] FAIL uart_tx is X/Z (cycle %0d)", cycle);
                    end
                    x_tx = 1'b1;
                end else x_tx = 1'b0;
                if (^gpio_out === 1'bx) begin
                    if (!x_gpio) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:x_check] FAIL gpio_out has X/Z: %b (cycle %0d)", gpio_out, cycle);
                    end
                    x_gpio = 1'b1;
                end else x_gpio = 1'b0;
                if (^mem_valid === 1'bx) begin
                    if (!x_valid) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:x_check] FAIL mem_valid is X/Z (cycle %0d)", cycle);
                    end
                    x_valid = 1'b1;
                end else x_valid = 1'b0;
            end
            if (mem_valid === 1'b1 && mem_ready === 1'b1 && mem_wstrb === 4'b0000 && ^mem_rdata === 1'bx) begin
                note_fail;
                if (fail_count <= MAX_MSGS)
                    $display("[CHK:x_check] FAIL mem_rdata has X/Z at read handshake: addr 0x%08x rdata %h (cycle %0d)", mem_addr, mem_rdata, cycle);
            end
        end
    end
endmodule
`endif

`default_nettype wire
