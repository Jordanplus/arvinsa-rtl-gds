`timescale 1ns/1ps
// GPIO 33-37 and the management SoC's GPIO configuration transfer (2026-10-16; docs/notes/caravel_gpio_xfer.md).
// One-off experiment, not part of make regress: caravel_core (caravel-lite 2024.09.12-1 RTL) with this project's
// rtl/caravel/user_defines.v, a stub management core (Wishbone master that writes housekeeping) and a stub
// user_project_wrapper that drives io_out / io_oeb like rtl/caravel/user_project_wrapper.v (stubs.v).
// How to build and run: README.md in this directory (run.sh).
//
//   +case=0  write only GPIO 5/6 (management UART), then transfer
//   +case=1  write GPIO 33-37 back to their user modes first, then transfer
//   +case=2  no transfer
//   +case=3  as case 0, then pulse serial_resetn in bit-bang mode (recovery)
//   +case=4  as case 0, then hold resetb low and look at the resets inside caravel_core while it is low
//   +case=5  as case 0, then write GPIO 33-37 back to their user modes and transfer again (recovery)
// Every case ends with a resetb pulse.
//
// Columns: dm, oeb(pad), out(pad), inp_dis = what the GPIO control block sends to the pad (the pad cell itself is
// not simulated); user_io_in = what the wrapper sees on io_in; hk_cfg = housekeeping's stored copy of the
// 13-bit configuration (the value a transfer sends).
module tb;
    reg clk = 0; always #20 clk = ~clk;        // 25 MHz
    reg rstb_h = 1; initial #50 rstb_h = 0;   // make a negedge so caravel_clocking resets in sim
    reg [37:0] pad_in = 38'h8;                  // CSB (GPIO 3) high: housekeeping SPI idle
    wire [37:0] p_out, p_oeb, p_inp_dis;
    wire [113:0] p_dm;
    integer tcase;

    caravel_core dut (
        .rstb_h(rstb_h), .clock_core(clk), .gpio_in_core(1'b0),
        .flash_io0_di(1'b0), .flash_io1_di(1'b0),
        .mprj_io_in(pad_in), .mprj_io_out(p_out), .mprj_io_oeb(p_oeb), .mprj_io_inp_dis(p_inp_dis),
        .mprj_io_dm(p_dm)
    );

    task show(input [8*24-1:0] tag);
        integer k;
        begin
            for (k = 33; k <= 37; k = k + 1)
                $display("%0s GPIO%0d: dm=%b oeb(pad)=%b out(pad)=%b inp_dis=%b user_io_in=%b",
                         tag, k, p_dm[3*k +: 3], p_oeb[k], p_out[k], p_inp_dis[k], dut.mprj.io_in[k]);
            $display("%0s hk_cfg 33..37 = %04h %04h %04h %04h %04h", tag,
                     dut.housekeeping.gpio_configure[33], dut.housekeeping.gpio_configure[34],
                     dut.housekeeping.gpio_configure[35], dut.housekeeping.gpio_configure[36],
                     dut.housekeeping.gpio_configure[37]);
        end
    endtask

    // user outputs: does the wrapper's uart_tx (37) / trap (35) reach the pad?
    task check_tx_follows(input [8*24-1:0] tag);
        reg a, b;
        begin
            dut.mprj.uart_tx_sig = 1'b1; dut.mprj.trap_sig = 1'b1; #100; a = (p_out[37] === 1'b1) && (p_out[35] === 1'b1);
            dut.mprj.uart_tx_sig = 1'b0; dut.mprj.trap_sig = 1'b0; #100; b = (p_out[37] === 1'b0) && (p_out[35] === 1'b0);
            $display("%0s user uart_tx/trap reach pads 37/35 (out follows and oeb=0): %0s", tag,
                     (a && b && p_oeb[37] === 1'b0 && p_oeb[35] === 1'b0) ? "YES" : "NO");
        end
    endtask

    // user inputs: does a pad value on 33/34 (boot_mode) and 36 (uart_rx) reach the wrapper's io_in?
    task check_in_follows(input [8*24-1:0] tag);
        reg a, b;
        reg [37:0] keep;
        begin
            keep = pad_in;
            pad_in[33] = 1'b1; pad_in[34] = 1'b1; pad_in[36] = 1'b0; #100;
            a = (dut.mprj.io_in[33] === 1'b1) && (dut.mprj.io_in[34] === 1'b1) && (dut.mprj.io_in[36] === 1'b0);
            pad_in[33] = 1'b0; pad_in[34] = 1'b0; pad_in[36] = 1'b1; #100;
            b = (dut.mprj.io_in[33] === 1'b0) && (dut.mprj.io_in[34] === 1'b0) && (dut.mprj.io_in[36] === 1'b1);
            pad_in = keep; #100;
            $display("%0s pad inputs 33/34/36 reach the wrapper io_in: %0s", tag, (a && b) ? "YES" : "NO");
        end
    endtask

    task resets(input [8*24-1:0] tag);
        $display("%0s porb_l=%b caravel_rstn=%b serial_resetn=%b", tag,
                 dut.porb_l, dut.caravel_rstn, dut.mprj_io_loader_resetn);
    endtask

    task xfer;
        begin
            dut.soc.wb_write(32'h2600_0000, 32'h1);
            dut.soc.rdata = 1;
            while (dut.soc.rdata[0]) dut.soc.wb_read(32'h2600_0000);
            #200;
        end
    endtask

    // reg_mprj_io_33..37 = the user modes of rtl/caravel/user_defines.v lines 92-96
    task write_back_33_37;
        begin
            dut.soc.wb_write(32'h2600_00a8, 32'h0c00);   // 33 USER_STD_INPUT_PULLDOWN
            dut.soc.wb_write(32'h2600_00ac, 32'h0c00);   // 34 USER_STD_INPUT_PULLDOWN
            dut.soc.wb_write(32'h2600_00b0, 32'h1808);   // 35 USER_STD_OUTPUT
            dut.soc.wb_write(32'h2600_00b4, 32'h0402);   // 36 USER_STD_INPUT_NOPULL
            dut.soc.wb_write(32'h2600_00b8, 32'h1808);   // 37 USER_STD_OUTPUT
        end
    endtask

    initial begin
        if (!$value$plusargs("case=%d", tcase)) tcase = 0;
        $display("case %0d", tcase);
        pad_in[36] = 1'b1;                       // external UART idle high on uart_rx
        #2000 rstb_h = 1;
        #3000;
        show("after POR      ");
        check_tx_follows("after POR      ");
        check_in_follows("after POR      ");
        if (tcase == 1) write_back_33_37;
        if (tcase != 2) begin : do_xfer
            dut.soc.wb_write(32'h2600_0038, 32'h0403);   // 5 MGMT_STD_INPUT_NOPULL (ser_rx)
            dut.soc.wb_write(32'h2600_003c, 32'h1809);   // 6 MGMT_STD_OUTPUT (ser_tx)
            xfer;
            show("after transfer ");
            check_tx_follows("after transfer ");
            check_in_follows("after transfer ");
        end
        if (tcase == 3) begin
            // bit-bang mode: serial_bb_enable=1, serial_bb_resetn=0 -> serial_resetn low (housekeeping.v 908-911)
            dut.soc.wb_write(32'h2600_0000, 32'h2); #500;
            dut.soc.wb_write(32'h2600_0000, 32'h6); #500;   // resetn high again
            dut.soc.wb_write(32'h2600_0000, 32'h0); #500;   // leave bit-bang mode
            show("after bb resetn");
            check_tx_follows("after bb resetn");
            check_in_follows("after bb resetn");
        end
        if (tcase == 5) begin
            write_back_33_37;
            xfer;
            show("after 2nd xfer ");
            check_tx_follows("after 2nd xfer ");
            check_in_follows("after 2nd xfer ");
        end
        if (tcase == 4) begin
            resets("before resetb  ");
            rstb_h = 0; #5000;
            resets("resetb low     ");
            show("resetb low     ");
            rstb_h = 1; #3000;
            resets("resetb high    ");
        end else begin
            rstb_h = 0; #2000 rstb_h = 1; #3000;
        end
        show("after resetb   ");
        check_tx_follows("after resetb   ");
        check_in_follows("after resetb   ");
        $finish;
    end
    initial begin #2000000 $display("TIMEOUT"); $finish; end
endmodule
