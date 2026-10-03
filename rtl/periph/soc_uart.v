// =============================================================================
// soc_uart.v -- bus wrapper around third_party/picorv32/picosoc/simpleuart.v.
// Contract: docs/spec/soc_spec.md sections 2 and 4.5.
//
// Registers (byte offsets from memmap.vh):
//   SOC_UART_DIV_OFF  : divider, RW. Writes are always 32-bit
//                       (reg_div_we = {4{write}}). Bit period = DIV + 2 clocks.
//   SOC_UART_DATA_OFF : W: send low 8 bits; R: received byte or 0xFFFF_FFFF.
// Handshake with soc_bus:
//   * req is high in the first cycle of a transaction; the bus accepts the
//     access at the next rising edge unless stall=1.
//   * stall = simpleuart reg_dat_wait. During a stalled DATA write, req (and
//     therefore reg_dat_we) stays high until simpleuart takes the byte.
//   * reg_dat_re is high only in the single cycle of a DATA read, i.e. at
//     the same edge where the bus registers reg_dat_do for that transaction.
// uart_rx is asynchronous to clk: it passes through a 2-flop synchronizer
// (reset to the idle level 1) before it reaches simpleuart. This adds two
// clocks of latency to RX but does not change the bit period.
// Bug injection: BUG_R04 (DIV value sent to simpleuart = written value + 1),
// BUG_R12 (DIV reads back 0; dv/bugs.toml).
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module soc_uart (
    input  wire        clk,
    input  wire        resetn,      // synchronous, active low
    input  wire        req,
    input  wire        we,
    input  wire [3:0]  off,         // byte offset inside the UART window
    input  wire [31:0] wdata,
    output wire [31:0] rdata,
    output wire        stall,
    output wire        uart_tx,
    input  wire        uart_rx
);

    localparam [31:0] DIV_OFF  = `SOC_UART_DIV_OFF;
    localparam [31:0] DATA_OFF = `SOC_UART_DATA_OFF;

    wire div_hit = (off == DIV_OFF[3:0]);
    wire dat_hit = (off == DATA_OFF[3:0]);

    wire div_we = req &  we & div_hit;
    wire dat_we = req &  we & dat_hit;
    wire dat_re = req & ~we & dat_hit;

`ifdef BUG_R04
    // BUG_R04: divider written to simpleuart is off by one (bit = DIV + 3).
    wire [31:0] div_di = wdata + 32'd1;
`else
    wire [31:0] div_di = wdata;
`endif

    // 2-flop synchronizer for the asynchronous serial input.
    reg  [1:0]  rx_sync_q;
    always @(posedge clk) begin
        if (!resetn)
            rx_sync_q <= 2'b11;
        else
            rx_sync_q <= {rx_sync_q[0], uart_rx};
    end
    wire        rx_sync = rx_sync_q[1];

    wire [31:0] div_do;
    wire [31:0] dat_do;
    wire        dat_wait;

    simpleuart #(
        .DEFAULT_DIV (`SOC_UART_DIV)
    ) u_simpleuart (
        .clk          (clk),
        .resetn       (resetn),
        .ser_tx       (uart_tx),
        .ser_rx       (rx_sync),
        .reg_div_we   ({4{div_we}}),
        .reg_div_di   (div_di),
        .reg_div_do   (div_do),
        .reg_dat_we   (dat_we),
        .reg_dat_re   (dat_re),
        .reg_dat_di   (wdata),
        .reg_dat_do   (dat_do),
        .reg_dat_wait (dat_wait)
    );

    assign stall = dat_wait;
`ifdef BUG_R12
    // BUG_R12: the DIV read-back path returns 0.
    wire [31:0] div_rd = 32'h0000_0000;
    wire        unused_bug_r12 = &{1'b0, div_do};
`else
    wire [31:0] div_rd = div_do;
`endif
    assign rdata = ({32{div_hit}} & div_rd) | ({32{dat_hit}} & dat_do);

endmodule

`default_nettype wire
