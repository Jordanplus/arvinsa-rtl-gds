// =============================================================================
// soc_gpio.v -- GPIO registers. Contract: docs/spec/soc_spec.md sections 2, 4.7.
//   SOC_GPIO_OUT_OFF : GPIO_OUT, RW, 8 bits valid (reset 0), drives gpio_out.
//   SOC_GPIO_IN_OFF  : GPIO_IN, RO, {30'b0, boot_mode[1:0]}.
// Any write to GPIO_OUT updates all 8 bits (peripherals are 32-bit only).
// Bug injection (dv/bugs.toml): BUG_R11 (gpio_out pin 6 stuck at 0, register
// read-back unaffected), BUG_R12 (GPIO_OUT reads back 0).
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module soc_gpio (
    input  wire        clk,
    input  wire        resetn,      // synchronous, active low
    input  wire        req,
    input  wire        we,
    input  wire [3:0]  off,         // byte offset inside the GPIO window
    input  wire [31:0] wdata,
    output wire [31:0] rdata,
    output wire [7:0]  gpio_out,
    input  wire [1:0]  boot_mode
);

    localparam [31:0] OUT_OFF = `SOC_GPIO_OUT_OFF;
    localparam [31:0] IN_OFF  = `SOC_GPIO_IN_OFF;

    wire out_hit = (off == OUT_OFF[3:0]);
    wire in_hit  = (off == IN_OFF[3:0]);

    reg [7:0] gpio_out_q;
    always @(posedge clk) begin
        if (!resetn)
            gpio_out_q <= 8'h00;
        else if (req && we && out_hit)
            gpio_out_q <= wdata[7:0];
    end

`ifdef BUG_R11
    // BUG_R11: output pin 6 stuck at 0 (the register itself is correct).
    assign gpio_out = gpio_out_q & 8'hBF;
`else
    assign gpio_out = gpio_out_q;
`endif
`ifdef BUG_R12
    // BUG_R12: the GPIO_OUT read-back path returns 0.
    wire [7:0] out_rd = 8'h00;
`else
    wire [7:0] out_rd = gpio_out_q;
`endif
    assign rdata    = ({32{out_hit}} & {24'h000000, out_rd})
                    | ({32{in_hit}}  & {30'h00000000, boot_mode});

    // GPIO_OUT has 8 valid bits; the upper write data bits are ignored.
    wire unused_gpio = &{1'b0, wdata[31:8]};

endmodule

`default_nettype wire
