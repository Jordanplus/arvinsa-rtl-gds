// vcd_window: records tb_soc.dut_gl (the gate-level copy) into a VCD only while the SoC's gpio_out
// (la_data_out[9:2] of the Caravel wrapper) equals +irwin_gpio=<hex>, then ends the simulation with
// "[vcd_window] end after N cycles". The firmware marks its windows on GPIO_OUT (fw/tests/maxpower).
// Used by run_gl_soc.py --record-window for the IR max-power pattern (ADR-0019 decision 20). The plusarg
// names must not start with an existing one: $test$plusargs("vcd") in tb_soc.v matches any plusarg that
// begins with "vcd" and then dumps the whole testbench from time 0 instead.
module vcd_window;
    reg [7:0]       want = 8'h00;
    reg [8*512-1:0] path;
    reg             on = 1'b0;
    integer         n = 0;
    initial begin
        if (!$value$plusargs("irwin_gpio=%h", want)) want = 8'h00;
        if (!$value$plusargs("irwin_vcd=%s", path)) path = "window.vcd";
    end
    always @(posedge tb_soc.clk) if (want != 8'h00) begin
        if (!on && tb_soc.la_data_out[9:2] == want) begin
            on = 1'b1;
            $dumpfile(path);
            $dumpvars(0, tb_soc.dut_gl);
            $display("[vcd_window] start at %0t ps, gpio %h", $time, want);
        end else if (on) begin
            n = n + 1;
            if (tb_soc.la_data_out[9:2] != want) begin
                $dumpflush;
                $display("[vcd_window] end after %0d cycles", n);
                $finish;
            end
        end
    end
endmodule
