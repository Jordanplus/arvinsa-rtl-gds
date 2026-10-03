// uart_div_monitor.v - UART divider checker (checker name: uart_div).
// Contract: docs/spec/soc_spec.md sections 2 (SOC_UART_DIV), 4.5 (simpleuart
// DEFAULT_DIV = SOC_UART_DIV, DIV is 32-bit RW) and 6.5 step 1 (the boot ROM
// writes UART DIV = SOC_UART_DIV first).
//
// Probe: the divider simpleuart really uses, u_uart.u_simpleuart.cfg_divider.
// Sampled on the falling clock edge. Rules:
//   1. The divider equals the checker's copy of DIV in every cycle outside a
//      DIV write transaction. The copy is SOC_UART_DIV while resetn=0 (reset
//      value) and mem_wdata at the handshake of each DIV write, so a wrong
//      reset value shows in the first cycle after reset release, and a wrong
//      value passed to simpleuart shows right after the write.
//   2. Boot ROM step 1: after every reset release the CPU must write
//      SOC_UART_DIV to UART DIV before its first UART DATA access, its first
//      instruction fetch outside the boot ROM and its first DONE write
//      (whichever comes first). A boot ROM without the DIV write is invisible
//      while the reset value is right (and a firmware uart_init() hides it),
//      so it is checked here directly.
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module uart_div_monitor #(
    parameter integer MAX_MSGS = 20
) (
    input  wire        clk,
    input  wire        active,
    input  wire [31:0] cycle,
    input  wire        resetn,
    input  wire        mem_valid,
    input  wire        mem_instr,
    input  wire        mem_ready,
    input  wire [31:0] mem_addr,
    input  wire [31:0] mem_wdata,
    input  wire [3:0]  mem_wstrb,
    input  wire [31:0] divider,      // u_uart.u_simpleuart.cfg_divider
    output reg  [31:0] fail_count
);
    localparam [31:0] RESET_DIV = `SOC_UART_DIV;
    localparam [31:0] DIV_ADDR  = `SOC_UART_BASE + `SOC_UART_DIV_OFF;
    localparam [31:0] DATA_ADDR = `SOC_UART_BASE + `SOC_UART_DATA_OFF;
    localparam [31:0] DONE_ADDR = `SOC_TEST_BASE + `SOC_TEST_DONE_OFF;
    localparam [31:0] ROM_BASE  = `SOC_ROM_BASE;
    localparam [31:0] ROM_SIZE  = `SOC_ROM_SIZE;

    reg [31:0] model;
    reg        rep;
    reg        boot_div_ok;
    reg        boot_rep;
    reg [31:0] since_wr;      // "reset" or the cycle of the last DIV write
    reg        from_reset;
    reg [31:0] rom_off;

    initial begin
        fail_count  = 32'd0;
        model       = RESET_DIV;
        rep         = 1'b0;
        boot_div_ok = 1'b0;
        boot_rep    = 1'b0;
        since_wr    = 32'd0;
        from_reset  = 1'b1;
        rom_off     = 32'd0;
    end

    task note_fail;
        begin
            fail_count = fail_count + 32'd1;
            if (fail_count == MAX_MSGS + 1)
                $display("[CHK:uart_div] FAIL more than %0d uart_div failures, further messages suppressed", MAX_MSGS);
        end
    endtask

    // kind: 0 UART DATA access, 1 instruction fetch outside the boot ROM, 2 DONE write
    task boot_order_fail;
        input [1:0] kind;
        begin
            if (!boot_div_ok && !boot_rep) begin
                boot_rep = 1'b1;
                note_fail;
                if (fail_count <= MAX_MSGS) begin
                    if (kind == 2'd0)
                        $display("[CHK:uart_div] FAIL UART DATA access at addr 0x%08x before the boot ROM wrote UART DIV = %0d; spec 6.5 step 1 (cycle %0d)",
                                 mem_addr, RESET_DIV, cycle);
                    else if (kind == 2'd1)
                        $display("[CHK:uart_div] FAIL instruction fetch at 0x%08x (outside the boot ROM) before the boot ROM wrote UART DIV = %0d; spec 6.5 step 1 (cycle %0d)",
                                 mem_addr, RESET_DIV, cycle);
                    else
                        $display("[CHK:uart_div] FAIL DONE write 0x%08x before the boot ROM wrote UART DIV = %0d; spec 6.5 step 1 (cycle %0d)",
                                 mem_wdata, RESET_DIV, cycle);
                end
            end
        end
    endtask

    always @(negedge clk) begin
        if (active !== 1'b1 || resetn !== 1'b1) begin
            model       = RESET_DIV;
            rep         = 1'b0;
            boot_div_ok = 1'b0;
            boot_rep    = 1'b0;
            from_reset  = 1'b1;
        end else begin
            // ---- rule 1: divider follows DIV ----
            if (mem_valid === 1'b1 && mem_wstrb != 4'd0 && mem_addr == DIV_ADDR) begin
                if (mem_ready === 1'b1) begin
                    model      = mem_wdata;
                    since_wr   = cycle;
                    from_reset = 1'b0;
                end
            end else if (divider !== model) begin
                if (!rep) begin
                    rep = 1'b1;
                    note_fail;
                    if (fail_count <= MAX_MSGS) begin
                        if (from_reset)
                            $display("[CHK:uart_div] FAIL simpleuart divider is %0d after reset release, expected the reset value SOC_UART_DIV = %0d (spec 4.5 DEFAULT_DIV) (cycle %0d)",
                                     divider, RESET_DIV, cycle);
                        else
                            $display("[CHK:uart_div] FAIL simpleuart divider is %0d, but the last UART DIV write (cycle %0d) was %0d (cycle %0d)",
                                     divider, since_wr, model, cycle);
                    end
                end
            end else begin
                rep = 1'b0;
            end

            // ---- rule 2: boot ROM step 1 writes DIV before any UART use ----
            if (mem_valid === 1'b1 && mem_ready === 1'b1) begin
                rom_off = mem_addr - ROM_BASE;
                if (mem_wstrb != 4'd0 && mem_addr == DIV_ADDR && mem_wdata == RESET_DIV)
                    boot_div_ok = 1'b1;
                else if (mem_addr == DATA_ADDR)
                    boot_order_fail(2'd0);
                else if (mem_instr === 1'b1 && !(rom_off < ROM_SIZE))
                    boot_order_fail(2'd1);
                else if (mem_wstrb != 4'd0 && mem_addr == DONE_ADDR)
                    boot_order_fail(2'd2);
            end
        end
    end
endmodule

`default_nettype wire
