// bus_assert.v - PicoRV32 native memory bus protocol checker (checker name: bus_assert).
// Contract: docs/spec/soc_spec.md section 7.2 (bus_assert row) and sections 3.1, 4.2.
//
// Sampled on the falling clock edge (mid-cycle): the values seen here are the
// values the next rising edge samples, so "mem_valid && mem_ready" here means a
// handshake on the next rising edge.
//
// Rules (each reported at most once per transaction):
//   - sel_* not one-hot while mem_valid=1, or any sel_* set while mem_valid=0
//   - sel_* differs from this checker's own decode of the memmap.vh windows
//   - mem_addr/mem_wdata/mem_wstrb change while mem_valid=1 before the handshake
//   - illegal mem_wstrb pattern; misaligned mem_addr (PicoRV32 always word-aligns)
//   - access outside every window (unmapped). With allow_unmapped=1 (plusarg
//     +allow_unmapped, set by run_sim.py only for a test that declares
//     expect_unmapped in dv/tests.toml) an unmapped data access is counted in
//     unmapped_count and logged as a [TB] line instead; run_sim.py compares the
//     count with expect_unmapped. An instruction fetch from an unmapped
//     address is always a FAIL.
//   - read data of an unmapped read is not 0 at the handshake (spec 4.2)
//   - write to the Boot ROM window
//   - write narrower than 32 bit to UART/GPIO/TEST_CTRL
//   - mem_ready=1 while mem_valid=0
//   - one transaction pending for more than TXN_LIMIT cycles
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module bus_assert #(
    parameter integer MAX_MSGS  = 20,
    parameter integer TXN_LIMIT = 1000
) (
    input  wire        clk,
    input  wire        active,     // 1 after reset release
    input  wire [31:0] cycle,
    input  wire        mem_valid,
    input  wire        mem_instr,
    input  wire        mem_ready,
    input  wire [31:0] mem_addr,
    input  wire [31:0] mem_wdata,
    input  wire [3:0]  mem_wstrb,
    input  wire [31:0] mem_rdata,
    input  wire        allow_unmapped,
    input  wire        sel_sram,
    input  wire        sel_rom,
    input  wire        sel_uart,
    input  wire        sel_gpio,
    input  wire        sel_test,
    input  wire        sel_none,
    output reg  [31:0] fail_count,
    output reg  [31:0] unmapped_count
);
    // Bit order everywhere: {sram, rom, uart, gpio, test, none}
    localparam [5:0] D_SRAM = 6'b100000;
    localparam [5:0] D_ROM  = 6'b010000;
    localparam [5:0] D_UART = 6'b001000;
    localparam [5:0] D_GPIO = 6'b000100;
    localparam [5:0] D_TEST = 6'b000010;
    localparam [5:0] D_NONE = 6'b000001;

    localparam [31:0] SRAM_BASE = `SOC_SRAM_BASE;
    localparam [31:0] SRAM_SIZE = `SOC_SRAM_SIZE;
    localparam [31:0] ROM_BASE  = `SOC_ROM_BASE;
    localparam [31:0] ROM_SIZE  = `SOC_ROM_SIZE;
    localparam [31:0] UART_BASE = `SOC_UART_BASE;
    localparam [31:0] UART_SIZE = `SOC_UART_SIZE;
    localparam [31:0] GPIO_BASE = `SOC_GPIO_BASE;
    localparam [31:0] GPIO_SIZE = `SOC_GPIO_SIZE;
    localparam [31:0] TEST_BASE = `SOC_TEST_BASE;
    localparam [31:0] TEST_SIZE = `SOC_TEST_SIZE;

    // Independent full-address decode: a is inside [base, base+size) exactly when
    // (a - base) mod 2^32 < size.
    function [5:0] decode;
        input [31:0] a;
        reg   [31:0] o_sram, o_rom, o_uart, o_gpio, o_test;
        begin
            o_sram = a - SRAM_BASE;
            o_rom  = a - ROM_BASE;
            o_uart = a - UART_BASE;
            o_gpio = a - GPIO_BASE;
            o_test = a - TEST_BASE;
            if      (o_sram < SRAM_SIZE) decode = D_SRAM;
            else if (o_rom  < ROM_SIZE)  decode = D_ROM;
            else if (o_uart < UART_SIZE) decode = D_UART;
            else if (o_gpio < GPIO_SIZE) decode = D_GPIO;
            else if (o_test < TEST_SIZE) decode = D_TEST;
            else                         decode = D_NONE;
        end
    endfunction

    function legal_wstrb;
        input [3:0] s;
        begin
            case (s)
                4'b0000, 4'b1111, 4'b0011, 4'b1100,
                4'b0001, 4'b0010, 4'b0100, 4'b1000: legal_wstrb = 1'b1;
                default:                            legal_wstrb = 1'b0;
            endcase
        end
    endfunction

    function is_onehot;
        input [5:0] v;
        begin
            is_onehot = (v != 6'd0) && ((v & (v - 6'd1)) == 6'd0);
        end
    endfunction

    reg [5:0]  sel;
    reg [5:0]  exp_sel;
    reg        in_txn;
    reg [31:0] t_addr;
    reg [31:0] t_wdata;
    reg [3:0]  t_wstrb;
    reg [31:0] t_start;
    reg        t_rep_sel;
    reg        t_rep_stable;
    reg        t_rep_long;
    reg        t_unmapped;
    reg        idle_rep_sel;

    initial begin
        fail_count   = 32'd0;
        unmapped_count = 32'd0;
        t_unmapped   = 1'b0;
        sel          = 6'd0;
        exp_sel      = 6'd0;
        in_txn       = 1'b0;
        t_addr       = 32'd0;
        t_wdata      = 32'd0;
        t_wstrb      = 4'd0;
        t_start      = 32'd0;
        t_rep_sel    = 1'b0;
        t_rep_stable = 1'b0;
        t_rep_long   = 1'b0;
        idle_rep_sel = 1'b0;
    end

    task note_fail;
        begin
            fail_count = fail_count + 32'd1;
            if (fail_count == MAX_MSGS + 1)
                $display("[CHK:bus_assert] FAIL more than %0d bus_assert failures, further messages suppressed", MAX_MSGS);
        end
    endtask

    always @(negedge clk) begin
        if (active !== 1'b1) begin
            in_txn       = 1'b0;
            idle_rep_sel = 1'b0;
        end else begin
            sel = {sel_sram, sel_rom, sel_uart, sel_gpio, sel_test, sel_none};
            if (mem_valid === 1'b1) begin
                idle_rep_sel = 1'b0;
                exp_sel = decode(mem_addr);
                if (!in_txn) begin
                    // First cycle of a new transaction: per-transaction rules.
                    in_txn       = 1'b1;
                    t_addr       = mem_addr;
                    t_wdata      = mem_wdata;
                    t_wstrb      = mem_wstrb;
                    t_start      = cycle;
                    t_rep_sel    = 1'b0;
                    t_rep_stable = 1'b0;
                    t_rep_long   = 1'b0;
                    t_unmapped   = (exp_sel == D_NONE);
                    if (!legal_wstrb(mem_wstrb)) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL illegal wstrb %b at addr 0x%08x (cycle %0d)", mem_wstrb, mem_addr, cycle);
                    end
                    if (mem_addr[1:0] != 2'b00) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL misaligned addr 0x%08x (cycle %0d)", mem_addr, cycle);
                    end
                    if (exp_sel == D_NONE) begin
                        if (allow_unmapped === 1'b1 && mem_instr !== 1'b1) begin
                            unmapped_count = unmapped_count + 32'd1;
                            if (mem_wstrb != 4'd0)
                                $display("[TB] bus_assert: unmapped write addr 0x%08x wdata 0x%08x (cycle %0d), counted (+allow_unmapped)", mem_addr, mem_wdata, cycle);
                            else
                                $display("[TB] bus_assert: unmapped read addr 0x%08x (cycle %0d), counted (+allow_unmapped)", mem_addr, cycle);
                        end else begin
                            note_fail;
                            if (fail_count <= MAX_MSGS) begin
                                if (mem_wstrb != 4'd0)
                                    $display("[CHK:bus_assert] FAIL unmapped access: write addr 0x%08x wstrb %b (cycle %0d)", mem_addr, mem_wstrb, cycle);
                                else if (mem_instr === 1'b1)
                                    $display("[CHK:bus_assert] FAIL unmapped access: fetch addr 0x%08x (cycle %0d)", mem_addr, cycle);
                                else
                                    $display("[CHK:bus_assert] FAIL unmapped access: read addr 0x%08x (cycle %0d)", mem_addr, cycle);
                            end
                        end
                    end
                    if (exp_sel == D_ROM && mem_wstrb != 4'd0) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL write to Boot ROM addr 0x%08x wdata 0x%08x wstrb %b (cycle %0d)", mem_addr, mem_wdata, mem_wstrb, cycle);
                    end
                    if ((exp_sel == D_UART || exp_sel == D_GPIO || exp_sel == D_TEST) &&
                        mem_wstrb != 4'd0 && mem_wstrb != 4'hF) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL sub-word write to peripheral addr 0x%08x wstrb %b (cycle %0d)", mem_addr, mem_wstrb, cycle);
                    end
                end else begin
                    if (!t_rep_stable && (mem_addr !== t_addr || mem_wdata !== t_wdata || mem_wstrb !== t_wstrb)) begin
                        t_rep_stable = 1'b1;
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL addr/wdata/wstrb changed while mem_valid=1: 0x%08x/0x%08x/%b -> 0x%08x/0x%08x/%b (cycle %0d)",
                                     t_addr, t_wdata, t_wstrb, mem_addr, mem_wdata, mem_wstrb, cycle);
                    end
                    if (!t_rep_long && (cycle - t_start) > TXN_LIMIT) begin
                        t_rep_long = 1'b1;
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL transaction at addr 0x%08x pending for more than %0d cycles without mem_ready (started cycle %0d)",
                                     t_addr, TXN_LIMIT, t_start);
                    end
                end
                if (!t_rep_sel) begin
                    if (!is_onehot(sel)) begin
                        t_rep_sel = 1'b1;
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL sel not one-hot: {sram,rom,uart,gpio,test,none}=%b for addr 0x%08x (cycle %0d)", sel, mem_addr, cycle);
                    end else if (sel !== exp_sel) begin
                        t_rep_sel = 1'b1;
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL decode mismatch: {sram,rom,uart,gpio,test,none}=%b, expected %b for addr 0x%08x (cycle %0d)", sel, exp_sel, mem_addr, cycle);
                    end
                end
                if (mem_ready === 1'b1) begin
                    // Handshake on the next rising edge: an unmapped read returns 0.
                    if (t_unmapped && t_wstrb == 4'd0 && mem_rdata !== 32'd0) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL unmapped read addr 0x%08x returned 0x%08x, expected 0 (cycle %0d)", t_addr, mem_rdata, cycle);
                    end
                    in_txn = 1'b0;
                end
            end else begin
                in_txn = 1'b0;
                if (sel !== 6'd0) begin
                    if (!idle_rep_sel) begin
                        idle_rep_sel = 1'b1;
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:bus_assert] FAIL sel not all zero while mem_valid=0: {sram,rom,uart,gpio,test,none}=%b (cycle %0d)", sel, cycle);
                    end
                end else begin
                    idle_rep_sel = 1'b0;
                end
                if (mem_ready === 1'b1) begin
                    note_fail;
                    if (fail_count <= MAX_MSGS)
                        $display("[CHK:bus_assert] FAIL mem_ready=1 without mem_valid (cycle %0d)", cycle);
                end
            end
        end
    end
endmodule

`default_nettype wire
