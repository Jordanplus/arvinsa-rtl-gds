// SPDX-FileCopyrightText: 2020 Efabless Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// SPDX-License-Identifier: Apache-2.0
//
// The port list is the Caravel user_project_wrapper template
// (chipfoundry/caravel_user_project b510613c, verilog/rtl/user_project_wrapper.v); the body is
// this project's (Phase 7, ADR-0019): soc_top (Hazard3, SOC_CPU_HAZARD3) placed flat in the
// wrapper, clocked and reset by the Wishbone clock and reset (decision 8), its host write port
// driven from Wishbone (decision 9, wb_host_bridge.v), its pins on GPIO 8-20 and mirrored on
// the logic analyzer (decision 10). GPIO modes: rtl/caravel/user_defines.v.
// Bug injection (dv/bugs.toml W03-W05; negative tests of the Caravel build).
`default_nettype none

`ifndef MPRJ_IO_PADS
`define MPRJ_IO_PADS 38
`endif

module user_project_wrapper #(
    parameter BITS = 32
) (
`ifdef USE_POWER_PINS
    inout vdda1,	// User area 1 3.3V supply
    inout vdda2,	// User area 2 3.3V supply
    inout vssa1,	// User area 1 analog ground
    inout vssa2,	// User area 2 analog ground
    inout vccd1,	// User area 1 1.8V supply
    inout vccd2,	// User area 2 1.8v supply
    inout vssd1,	// User area 1 digital ground
    inout vssd2,	// User area 2 digital ground
`endif

    // Wishbone Slave ports (WB MI A)
    input wb_clk_i,
    input wb_rst_i,
    input wbs_stb_i,
    input wbs_cyc_i,
    input wbs_we_i,
    input [3:0] wbs_sel_i,
    input [31:0] wbs_dat_i,
    input [31:0] wbs_adr_i,
    output wbs_ack_o,
    output [31:0] wbs_dat_o,

    // Logic Analyzer Signals
    input  [127:0] la_data_in,
    output [127:0] la_data_out,
    input  [127:0] la_oenb,

    // IOs
    input  [`MPRJ_IO_PADS-1:0] io_in,
    output [`MPRJ_IO_PADS-1:0] io_out,
    output [`MPRJ_IO_PADS-1:0] io_oeb,

    // Analog (direct connection to GPIO pad---use with caution)
    // Note that analog I/O is not available on the 7 lowest-numbered
    // GPIO pads, and so the analog_io indexing is offset from the
    // GPIO indexing by 7 (also upper 2 GPIOs do not have analog_io).
    inout [`MPRJ_IO_PADS-10:0] analog_io,

    // Independent clock (on independent integer divider)
    input   user_clock2,

    // User maskable interrupt signals
    output [2:0] user_irq
);
    // ------------------------------------------------------------------
    // GPIO plan (ADR-0019 decision 10)
    localparam GPIO_UART_TX = 8;
    localparam GPIO_UART_RX = 9;
    localparam GPIO_OUT0    = 10;   // gpio_out[7:0] on GPIO 10-17
    localparam GPIO_TRAP    = 18;
    localparam GPIO_BOOT0   = 19;   // boot_mode[1:0] on GPIO 19-20

    wire        uart_tx;
    wire        trap;
    wire [7:0]  gpio_out;
    wire        uart_rx   = io_in[GPIO_UART_RX];
`ifdef BUG_W05
    wire [1:0]  boot_mode = {io_in[GPIO_BOOT0], io_in[GPIO_BOOT0+1]};   // BUG_W05: boot_mode pins swapped
`else
    wire [1:0]  boot_mode = io_in[GPIO_BOOT0+1:GPIO_BOOT0];
`endif

    wire        host_en;
    wire        host_cs;
    wire        host_we;
    wire [8:0]  host_addr;
    wire [31:0] host_wdata;
    wire [3:0]  host_wmask;
    wire [31:0] host_rdata;

    wb_host_bridge u_wb (
        .clk        (wb_clk_i),
        .rst        (wb_rst_i),
        .wbs_stb_i  (wbs_stb_i),
        .wbs_cyc_i  (wbs_cyc_i),
        .wbs_we_i   (wbs_we_i),
        .wbs_sel_i  (wbs_sel_i),
        .wbs_dat_i  (wbs_dat_i),
        .wbs_adr_i  (wbs_adr_i),
        .wbs_ack_o  (wbs_ack_o),
        .wbs_dat_o  (wbs_dat_o),
        .host_en    (host_en),
        .host_cs    (host_cs),
        .host_we    (host_we),
        .host_addr  (host_addr),
        .host_wdata (host_wdata),
        .host_wmask (host_wmask),
        .host_rdata (host_rdata)
    );

    soc_top u_soc (
`ifdef USE_POWER_PINS
        .vccd1      (vccd1),
        .vssd1      (vssd1),
`endif
        .clk        (wb_clk_i),
        .resetn     (~wb_rst_i),
        .uart_tx    (uart_tx),
        .uart_rx    (uart_rx),
        .gpio_out   (gpio_out),
        .boot_mode  (boot_mode),
        .trap       (trap),
        .host_en    (host_en),
        .host_cs    (host_cs),
        .host_we    (host_we),
        .host_addr  (host_addr),
        .host_wdata (host_wdata),
        .host_wmask (host_wmask),
        .host_rdata (host_rdata)
    );

    // ------------------------------------------------------------------
    // Pads. User outputs: io_out = the signal, io_oeb = 0. User input nopull (uart_rx): the
    // precheck OEB check requires io_out and io_oeb to be connected: 0 and 1. User input
    // pulldown (boot_mode): io_out and io_oeb must both be 0. Management-mode GPIOs: 0 and 1
    // (ignored by the pad; the OEB check only warns).
    localparam [`MPRJ_IO_PADS-1:0] USER_OUT =
        ({{(`MPRJ_IO_PADS-1){1'b0}}, 1'b1} << GPIO_UART_TX) |
        ({{(`MPRJ_IO_PADS-8){1'b0}}, 8'hFF} << GPIO_OUT0) |
        ({{(`MPRJ_IO_PADS-1){1'b0}}, 1'b1} << GPIO_TRAP);
    localparam [`MPRJ_IO_PADS-1:0] PULLDOWN =
        {{(`MPRJ_IO_PADS-2){1'b0}}, 2'b11} << GPIO_BOOT0;

    wire [`MPRJ_IO_PADS-1:0] out_sig =
        ({{(`MPRJ_IO_PADS-1){1'b0}}, uart_tx} << GPIO_UART_TX) |
        ({{(`MPRJ_IO_PADS-8){1'b0}}, gpio_out} << GPIO_OUT0) |
        ({{(`MPRJ_IO_PADS-1){1'b0}}, trap} << GPIO_TRAP);

    assign io_out   = out_sig;
`ifdef BUG_W03
    assign io_oeb   = ~(USER_OUT | PULLDOWN) | (38'h1 << GPIO_BOOT0);   // BUG_W03: pulldown GPIO with oeb 1
`else
    assign io_oeb   = ~(USER_OUT | PULLDOWN);
`endif

    // Logic analyzer: a copy of the SoC pins, and host_en.
`ifdef BUG_W04
    assign la_data_out = {114'd0, host_en, boot_mode, trap, gpio_out, uart_tx, uart_rx};   // BUG_W04: LA bits swapped
`else
    assign la_data_out = {114'd0, host_en, boot_mode, trap, gpio_out, uart_rx, uart_tx};
`endif
    assign user_irq    = 3'b000;

    // Inputs this design does not use.
    wire unused = &{1'b0, la_data_in, la_oenb, user_clock2,
                    io_in[`MPRJ_IO_PADS-1:GPIO_BOOT0+2], io_in[GPIO_BOOT0-1:GPIO_UART_RX+1],
                    io_in[GPIO_UART_RX-1:0], BITS[0]};
endmodule

`default_nettype wire
