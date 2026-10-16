// Stubs for tb_gpio_xfer.v (2026-10-16; README.md in this directory). Not part of make regress.
// mgmt_core_wrapper: stub management core = Wishbone master BFM (wb_write / wb_read tasks) on housekeeping's
//   Wishbone port; it ties qspi_enabled / spi_enabled / uart_enabled to 0, so the management SoC's pad
//   functions (QSPI, SPI master, UART) are not exercised.
// user_project_wrapper: drives io_out/io_oeb like rtl/caravel/user_project_wrapper.v.
`default_nettype none
module mgmt_core_wrapper (
    input core_clk, input core_rstn,
    output gpio_out_pad, input gpio_in_pad, output gpio_mode0_pad, output gpio_mode1_pad,
    output gpio_outenb_pad, output gpio_inenb_pad,
    output flash_csb, output flash_clk,
    output flash_io0_oeb, input flash_io0_di, output flash_io0_do,
    output flash_io1_oeb, input flash_io1_di, output flash_io1_do,
    output flash_io2_oeb, input flash_io2_di, output flash_io2_do,
    output flash_io3_oeb, input flash_io3_di, output flash_io3_do,
    output mprj_wb_iena,
    output mprj_cyc_o, output mprj_stb_o, output reg mprj_we_o, output reg [3:0] mprj_sel_o,
    output reg [31:0] mprj_adr_o, output reg [31:0] mprj_dat_o,
    input mprj_ack_i, input [31:0] mprj_dat_i,
    output reg hk_stb_o, output reg hk_cyc_o, input [31:0] hk_dat_i, input hk_ack_i,
    input [5:0] irq, output [2:0] user_irq_ena,
    output qspi_enabled, output uart_enabled, output spi_enabled, output debug_mode,
    output ser_tx, input ser_rx,
    input spi_sdi, output spi_csb, output spi_sck, output spi_sdo, output spi_sdoenb,
    input debug_in, output debug_out, output debug_oeb,
    input [127:0] la_input, output [127:0] la_output, output [127:0] la_oenb, output [127:0] la_iena,
    output trap
);
    assign {gpio_out_pad, gpio_mode0_pad, gpio_mode1_pad} = 3'b0;
    assign gpio_outenb_pad = 1'b1; assign gpio_inenb_pad = 1'b0;
    assign flash_csb = 1'b1; assign flash_clk = 1'b0;
    assign {flash_io0_oeb, flash_io1_oeb, flash_io2_oeb, flash_io3_oeb} = 4'hf;
    assign {flash_io0_do, flash_io1_do, flash_io2_do, flash_io3_do} = 4'h0;
    assign mprj_wb_iena = 1'b0; assign mprj_cyc_o = 1'b0; assign mprj_stb_o = 1'b0;
    assign user_irq_ena = 3'b0;
    assign {qspi_enabled, uart_enabled, spi_enabled, debug_mode} = 4'b0;
    assign ser_tx = 1'b1; assign {spi_csb, spi_sck, spi_sdo, spi_sdoenb} = 4'b1001;
    assign {debug_out, debug_oeb} = 2'b01;
    assign la_output = 128'd0; assign la_oenb = {128{1'b1}}; assign la_iena = 128'd0;
    assign trap = 1'b0;
    initial begin hk_cyc_o = 0; hk_stb_o = 0; mprj_we_o = 0; mprj_sel_o = 0; mprj_adr_o = 0; mprj_dat_o = 0; end

    reg [31:0] rdata;
    task wb_write(input [31:0] a, input [31:0] d);
        begin
            @(posedge core_clk); #1;
            mprj_adr_o = a; mprj_dat_o = d; mprj_sel_o = 4'hf; mprj_we_o = 1; hk_cyc_o = 1; hk_stb_o = 1;
            @(posedge core_clk); while (!hk_ack_i) @(posedge core_clk);
            #1; hk_cyc_o = 0; hk_stb_o = 0; mprj_we_o = 0;
        end
    endtask
    task wb_read(input [31:0] a);
        begin
            @(posedge core_clk); #1;
            mprj_adr_o = a; mprj_sel_o = 4'hf; mprj_we_o = 0; hk_cyc_o = 1; hk_stb_o = 1;
            @(posedge core_clk); while (!hk_ack_i) @(posedge core_clk);
            rdata = hk_dat_i; #1; hk_cyc_o = 0; hk_stb_o = 0;
        end
    endtask
endmodule

module user_project_wrapper (
    input wb_clk_i, input wb_rst_i, input wbs_stb_i, input wbs_cyc_i, input wbs_we_i,
    input [3:0] wbs_sel_i, input [31:0] wbs_dat_i, input [31:0] wbs_adr_i,
    output wbs_ack_o, output [31:0] wbs_dat_o,
    input [127:0] la_data_in, output [127:0] la_data_out, input [127:0] la_oenb,
    input [37:0] io_in, output [37:0] io_out, output [37:0] io_oeb,
    inout [28:0] analog_io, input user_clock2, output [2:0] user_irq
);
    // Same pad contract as rtl/caravel/user_project_wrapper.v lines 149-163:
    // 37 uart_tx, 35 trap = user outputs (oeb 0); 33-34 pulldown inputs (out 0, oeb 0); others oeb 1.
    reg uart_tx_sig = 1'b1, trap_sig = 1'b0;
    assign io_out = ({37'd0, uart_tx_sig} << 37) | ({37'd0, trap_sig} << 35);
    assign io_oeb = ~((38'h1 << 37) | (38'h1 << 35) | (38'h3 << 33));
    assign wbs_ack_o = 1'b0; assign wbs_dat_o = 32'd0; assign la_data_out = 128'd0; assign user_irq = 3'b0;
endmodule
`default_nettype wire
