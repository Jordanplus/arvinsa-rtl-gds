// tb_soc.v - SoC-level testbench for soc_top (Icarus -g2012 and Verilator --binary --timing).
// Contract: docs/spec/soc_spec.md section 7 (plusargs 7.1, checkers 7.2).
//
// Flow: parse plusargs -> preload (backdoor $readmemh into dut.sram0.mem, or
// host image) -> reset (RESET_CYCLES) -> optional host-port load with
// read-back compare -> release CPU -> run until DONE, trap or max_cycles ->
// drain until the UART line has been idle for 2 frame times -> write
// tb_result.txt -> $finish.
//
// Plusargs: +fw=<hex> +fw_words=<n> +boot_mode=<n> +load=backdoor|host|uart|none
//           +max_cycles=<n> +uart_in=<hex, one byte per line> +uart_in_len=<n>
//           +uart_in_delay=<cycles after CPU release> +out_dir=<dir> +trace +vcd
//           +allow_unmapped +reset_on_store=<hex byte address>
// (+allow_unmapped is supplied by dv/scripts/run_sim.py for a test that declares
//  expect_unmapped in dv/tests.toml: bus_assert counts unmapped data accesses
//  instead of failing them, and tb_result.txt reports the count.)
// (+fw_words=<n> is supplied by dv/scripts/run_sim.py: the number of words in
//  the image. With it $readmemh reads exactly that range; the host-port loader
//  needs it to know how many words to write and read back. Without it a
//  backdoor load reads the whole file with no range.)
// (+reset_on_store=<addr> is supplied by dv/scripts/run_sim.py for a test that
//  declares reset_on_store in dv/tests.toml: at the falling edge where the CPU
//  first presents a store to <addr>, resetn goes to 0, so the next rising edge
//  samples resetn=0 together with that store (spec 4.9, RTL-RST-01: the store
//  is dropped). resetn stays 0 for RESET_CYCLES, then the CPU boots again.
//  Done once per run; tb_result.txt reports mid_resets.)
//
// Measurements written for run_sim.py (dv/README.md):
//   sram_cov.txt  per SRAM word: CPU data reads, instruction fetches, writes and
//                 the set of write strobes seen (bus handshakes), for the
//                 tests.toml sram_cov rules (coverage checker)
//   tb_result.txt uart_wr / uart_wr_stalled / uart_wr_stall_cycles (UART DATA
//                 writes held by the transmitter-busy stall), sig_at_done (SIG
//                 in the cycle of the first DONE strobe), mid_resets
//
// Checker messages: "[CHK:<name>] FAIL <msg>". Informational lines start with "[TB]".
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module tb_soc;
    // ------------------------------------------------------------------
    // Constants (all addresses and UART timing come from memmap.vh)
    // ------------------------------------------------------------------
    localparam integer CLK_HALF_NS  = 20;                    // 40 ns clock
    localparam integer RESET_CYCLES = 16;                    // spec 4.9: >= 10
    localparam integer BIT_CYCLES   = `SOC_UART_BIT_CYCLES;
    localparam integer FRAME_CYCLES = 10 * BIT_CYCLES;
    localparam integer DRAIN_IDLE   = 2 * FRAME_CYCLES;      // spec 7.2: >= 2 frame times idle
    localparam integer DRAIN_LIMIT  = 64 * FRAME_CYCLES;
    localparam integer SRAM_WORDS   = `SOC_SRAM_WORDS;
    localparam integer UART_IN_MAX  = 8192;

    // ------------------------------------------------------------------
    // DUT
    // ------------------------------------------------------------------
    reg         clk        = 1'b0;
    reg         resetn     = 1'b0;
    reg         uart_rx    = 1'b1;
    reg  [1:0]  boot_mode  = 2'b00;
    reg         host_en    = 1'b0;
    reg         host_cs    = 1'b0;
    reg         host_we    = 1'b0;
    reg  [8:0]  host_addr  = 9'd0;
    reg  [31:0] host_wdata = 32'd0;
    reg  [3:0]  host_wmask = 4'd0;
    wire        uart_tx;
    wire [7:0]  gpio_out;
    wire        trap;
    wire [31:0] host_rdata;

`ifdef USE_POWER_PINS
    wire vccd1 = 1'b1;
    wire vssd1 = 1'b0;
`endif

    soc_top dut (
`ifdef USE_POWER_PINS
        .vccd1      (vccd1),
        .vssd1      (vssd1),
`endif
        .clk        (clk),
        .resetn     (resetn),
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

    // Hierarchical probes (spec 3.1)
    wire        p_mem_valid   = dut.mem_valid;
    wire        p_mem_instr   = dut.mem_instr;
    wire        p_mem_ready   = dut.mem_ready;
    wire [31:0] p_mem_addr    = dut.mem_addr;
    wire [31:0] p_mem_wdata   = dut.mem_wdata;
    wire [3:0]  p_mem_wstrb   = dut.mem_wstrb;
    wire [31:0] p_mem_rdata   = dut.mem_rdata;
    wire        p_sel_sram    = dut.u_bus.sel_sram;
    wire        p_sel_rom     = dut.u_bus.sel_rom;
    wire        p_sel_uart    = dut.u_bus.sel_uart;
    wire        p_sel_gpio    = dut.u_bus.sel_gpio;
    wire        p_sel_test    = dut.u_bus.sel_test;
    wire        p_sel_none    = dut.u_bus.sel_none;
    wire        p_done_strobe = dut.u_test_ctrl.done_strobe;
    wire [31:0] p_done_value  = dut.u_test_ctrl.done_value;
    wire [31:0] p_sig_value   = dut.u_test_ctrl.sig_value;
    // Probes added by the Phase 1 qualification fixes (dv/README.md; spec 3.1
    // update pending): the CPU test IRQ input, the divider simpleuart really
    // uses, and the SRAM macro port 0 pins.
    wire        p_irq_test    = dut.u_cpu.irq[`SOC_IRQ_TEST];
    wire [31:0] p_uart_div    = dut.u_uart.u_simpleuart.cfg_divider;
    wire        p_sram_csb0   = dut.sram0.csb0;
    wire        p_sram_web0   = dut.sram0.web0;
    wire [3:0]  p_sram_wmask0 = dut.sram0.wmask0;
    wire [8:0]  p_sram_addr0  = dut.sram0.addr0;
    wire [31:0] p_sram_din0   = dut.sram0.din0;

    // ------------------------------------------------------------------
    // Clock, cycle counter, run state
    // ------------------------------------------------------------------
    always #(CLK_HALF_NS) clk = ~clk;

    reg [31:0] cycle = 32'd0;
    always @(posedge clk) cycle <= cycle + 32'd1;

`ifdef GL_LOCKSTEP
    // Gate-level copy of the DUT (dv/gl_soc/README.md): the final netlist, module renamed
    // soc_top_gl, driven by the same inputs. gl_lockstep compares its outputs and SRAM port 0
    // pins with the RTL DUT every cycle; all other checkers keep watching the RTL DUT.
    wire        gl_uart_tx;
    wire [7:0]  gl_gpio_out;
    wire        gl_trap;
    wire [31:0] gl_host_rdata;

    soc_top_gl dut_gl (
`ifdef USE_POWER_PINS
        // L5: the powered netlist (final/pnl), every cell powered through VPWR/VGND/VPB/VNB
        .vccd1      (vccd1),
        .vssd1      (vssd1),
`endif
        .clk        (clk),
        .resetn     (resetn),
        .uart_tx    (gl_uart_tx),
        .uart_rx    (uart_rx),
        .gpio_out   (gl_gpio_out),
        .boot_mode  (boot_mode),
        .trap       (gl_trap),
        .host_en    (host_en),
        .host_cs    (host_cs),
        .host_we    (host_we),
        .host_addr  (host_addr),
        .host_wdata (host_wdata),
        .host_wmask (host_wmask),
        .host_rdata (gl_host_rdata)
    );

    gl_lockstep u_gl_lockstep (
        .clk      (clk),
        .enable   (1'b1),
        .cycle    (cycle),
        .rtl_out  ({uart_tx, gpio_out, trap, host_rdata}),
        .gl_out   ({gl_uart_tx, gl_gpio_out, gl_trap, gl_host_rdata}),
        .rtl_sram ({dut.sram0.csb0, dut.sram0.web0, dut.sram0.wmask0, dut.sram0.addr0, dut.sram0.din0}),
        .gl_sram  ({dut_gl.sram0.csb0, dut_gl.sram0.web0, dut_gl.sram0.wmask0, dut_gl.sram0.addr0, dut_gl.sram0.din0})
    );
`endif

    string     fw_file;
    string     load;
    string     out_dir;
    string     uart_in_file;
    string     end_reason;
    integer    fw_words;
    integer    max_cycles;
    integer    uart_in_len;
    integer    uart_in_delay;
    integer    boot_mode_arg;
    integer    fd_uart   = 0;
    integer    fd_gpio   = 0;
    integer    fd_trace  = 0;
    integer    fd_result = 0;
    reg        trace_en  = 1'b0;
    reg        vcd_en    = 1'b0;
    reg        allow_unmapped = 1'b0;
    reg        active      = 1'b0;   // resetn released
    reg        cpu_started = 1'b0;   // resetn released and host_en low
    reg [31:0] cpu_start_cycle = 32'd0;
    reg [31:0] drain_start     = 32'd0;
    reg        trap_seen  = 1'b0;
    reg [31:0] trap_cycle = 32'd0;
    reg [31:0] fail_trap       = 32'd0;
    reg [31:0] fail_timeout    = 32'd0;
    reg [31:0] fail_uart_drain = 32'd0;
    reg [31:0] fail_sim_error  = 32'd0;
    reg [31:0] rst_store_addr  = 32'd0;
    reg        rst_store_en    = 1'b0;
    reg        rst_hit         = 1'b0;
    reg [31:0] mid_resets      = 32'd0;
    reg [31:0] last_fetch_addr = 32'd0;
    reg [31:0] host_img [0:SRAM_WORDS-1];
    localparam integer HOST_MASK_WORD = SRAM_WORDS - 1;
    reg [3:0]  hm;
    reg [31:0] hm_exp;
    reg [7:0]  uart_in_mem [0:UART_IN_MAX-1];
    integer    i;
    reg [31:0] rd;

    // ------------------------------------------------------------------
    // Checkers
    // ------------------------------------------------------------------
    wire [31:0] uart_idle;
    wire        uart_in_frame;
    wire [31:0] fail_uart;
    wire [31:0] uart_bytes;
    uart_monitor #(.BIT_CYCLES(BIT_CYCLES)) u_uart_monitor (
        .clk         (clk),
        .active      (active),
        .cycle       (cycle),
        .line        (uart_tx),
        .fd          (fd_uart),
        .idle_cycles (uart_idle),
        .in_frame    (uart_in_frame),
        .fail_count  (fail_uart),
        .byte_count  (uart_bytes)
    );

    wire [31:0] fail_bus;
    wire [31:0] unmapped_count;
    bus_assert u_bus_assert (
        .clk        (clk),
        .active     (active),
        .cycle      (cycle),
        .mem_valid  (p_mem_valid),
        .mem_instr  (p_mem_instr),
        .mem_ready  (p_mem_ready),
        .mem_addr   (p_mem_addr),
        .mem_wdata  (p_mem_wdata),
        .mem_wstrb  (p_mem_wstrb),
        .mem_rdata  (p_mem_rdata),
        .allow_unmapped (allow_unmapped),
        .sel_sram   (p_sel_sram),
        .sel_rom    (p_sel_rom),
        .sel_uart   (p_sel_uart),
        .sel_gpio   (p_sel_gpio),
        .sel_test   (p_sel_test),
        .sel_none   (p_sel_none),
        .fail_count (fail_bus),
        .unmapped_count (unmapped_count)
    );

    wire        done_seen;
    wire [31:0] done_count;
    wire [31:0] first_done_value;
    wire [31:0] first_done_cycle;
    wire [31:0] first_done_sig;
    wire [31:0] fail_test_ctrl;
    test_ctrl_monitor u_test_ctrl_monitor (
        .clk              (clk),
        .active           (active),
        .cycle            (cycle),
        .done_strobe      (p_done_strobe),
        .done_value       (p_done_value),
        .sig_value        (p_sig_value),
        .done_seen        (done_seen),
        .done_count       (done_count),
        .first_done_value (first_done_value),
        .first_done_cycle (first_done_cycle),
        .first_done_sig   (first_done_sig),
        .fail_count       (fail_test_ctrl)
    );

    wire [31:0] fail_sram_port;
    wire [31:0] sram_port_accesses;
    sram_port_monitor u_sram_port_monitor (
        .clk          (clk),
        .active       (active),
        .cycle        (cycle),
        .resetn       (resetn),
        .host_en      (host_en),
        .host_cs      (host_cs),
        .host_we      (host_we),
        .host_addr    (host_addr),
        .host_wdata   (host_wdata),
        .host_wmask   (host_wmask),
        .mem_valid    (p_mem_valid),
        .mem_ready    (p_mem_ready),
        .mem_addr     (p_mem_addr),
        .mem_wdata    (p_mem_wdata),
        .mem_wstrb    (p_mem_wstrb),
        .csb0         (p_sram_csb0),
        .web0         (p_sram_web0),
        .wmask0       (p_sram_wmask0),
        .addr0        (p_sram_addr0),
        .din0         (p_sram_din0),
        .fail_count   (fail_sram_port),
        .access_count (sram_port_accesses)
    );

    wire [31:0] fail_irq_line;
    irq_line_monitor u_irq_line_monitor (
        .clk        (clk),
        .active     (active),
        .cycle      (cycle),
        .resetn     (resetn),
        .mem_valid  (p_mem_valid),
        .mem_ready  (p_mem_ready),
        .mem_addr   (p_mem_addr),
        .mem_wdata  (p_mem_wdata),
        .mem_wstrb  (p_mem_wstrb),
        .irq_line   (p_irq_test),
        .fail_count (fail_irq_line)
    );

    wire [31:0] fail_uart_div;
    uart_div_monitor u_uart_div_monitor (
        .clk        (clk),
        .active     (active),
        .cycle      (cycle),
        .resetn     (resetn),
        .mem_valid  (p_mem_valid),
        .mem_instr  (p_mem_instr),
        .mem_ready  (p_mem_ready),
        .mem_addr   (p_mem_addr),
        .mem_wdata  (p_mem_wdata),
        .mem_wstrb  (p_mem_wstrb),
        .divider    (p_uart_div),
        .fail_count (fail_uart_div)
    );

    // ------------------------------------------------------------------
    // Coverage measurements (judged by run_sim.py against dv/tests.toml)
    // ------------------------------------------------------------------
    // SRAM access counts per word at CPU bus handshakes (spec 6.4 memtest,
    // 6.5 step 3 boot ROM march): data reads, instruction fetches, writes, and
    // a 16-bit mask with bit <wstrb> set for every write strobe seen.
    localparam [31:0] TB_SRAM_BASE   = `SOC_SRAM_BASE;
    localparam [31:0] TB_SRAM_SIZE   = `SOC_SRAM_SIZE;
    localparam [31:0] UART_DATA_ADDR = `SOC_UART_BASE + `SOC_UART_DATA_OFF;
    reg [31:0] cov_rd [0:SRAM_WORDS-1];
    reg [31:0] cov_if [0:SRAM_WORDS-1];
    reg [31:0] cov_wr [0:SRAM_WORDS-1];
    reg [15:0] cov_ws [0:SRAM_WORDS-1];
    reg [31:0] cov_off;
    reg [8:0]  cov_w;
    integer    cov_i;
    initial begin
        for (cov_i = 0; cov_i < SRAM_WORDS; cov_i = cov_i + 1) begin
            cov_rd[cov_i] = 32'd0;
            cov_if[cov_i] = 32'd0;
            cov_wr[cov_i] = 32'd0;
            cov_ws[cov_i] = 16'd0;
        end
    end
    always @(negedge clk) begin
        if (active && p_mem_valid === 1'b1 && p_mem_ready === 1'b1) begin
            cov_off = p_mem_addr - TB_SRAM_BASE;
            if (cov_off < TB_SRAM_SIZE) begin
                cov_w = cov_off[10:2];
                if (p_mem_wstrb != 4'd0) begin
                    cov_wr[cov_w] = cov_wr[cov_w] + 32'd1;
                    cov_ws[cov_w] = cov_ws[cov_w] | (16'd1 << p_mem_wstrb);
                end else if (p_mem_instr === 1'b1) begin
                    cov_if[cov_w] = cov_if[cov_w] + 32'd1;
                end else begin
                    cov_rd[cov_w] = cov_rd[cov_w] + 32'd1;
                end
            end
        end
    end

    // UART DATA writes held by the transmitter-busy stall (spec 4.2: no
    // mem_ready while reg_dat_wait=1). A peripheral write without stall is
    // answered in the cycle after it is presented (2 cycles with mem_valid=1);
    // every extra cycle is a stall cycle.
    reg [31:0] uart_wr              = 32'd0;
    reg [31:0] uart_wr_stalled      = 32'd0;
    reg [31:0] uart_wr_stall_cycles = 32'd0;
    reg        uw_in                = 1'b0;
    reg [31:0] uw_start             = 32'd0;
    always @(negedge clk) begin
        if (active !== 1'b1) begin
            uw_in = 1'b0;
        end else if (p_mem_valid === 1'b1 && p_mem_wstrb != 4'd0 && p_mem_addr == UART_DATA_ADDR) begin
            if (!uw_in) begin
                uw_in    = 1'b1;
                uw_start = cycle;
            end
            if (p_mem_ready === 1'b1) begin
                uart_wr = uart_wr + 32'd1;
                if (cycle - uw_start > 32'd1) begin
                    uart_wr_stalled      = uart_wr_stalled + 32'd1;
                    uart_wr_stall_cycles = uart_wr_stall_cycles + (cycle - uw_start - 32'd1);
                end
                uw_in = 1'b0;
            end
        end else begin
            uw_in = 1'b0;
        end
    end

`ifndef VERILATOR
    wire [31:0] fail_x;
    x_check u_x_check (
        .clk        (clk),
        .resetn     (resetn),
        .cycle      (cycle),
        .trap       (trap),
        .uart_tx    (uart_tx),
        .gpio_out   (gpio_out),
        .mem_valid  (p_mem_valid),
        .mem_ready  (p_mem_ready),
        .mem_wstrb  (p_mem_wstrb),
        .mem_addr   (p_mem_addr),
        .mem_rdata  (p_mem_rdata),
        .fail_count (fail_x)
    );
`endif

    // trap checker: FAIL on the first cycle trap is 1 after reset release.
    always @(negedge clk) begin
        if (active && trap === 1'b1 && !trap_seen) begin
            trap_seen  = 1'b1;
            trap_cycle = cycle;
            fail_trap  = fail_trap + 32'd1;
            $display("[CHK:trap] FAIL trap asserted at cycle %0d (last instruction fetch at 0x%08x)", cycle, last_fetch_addr);
        end
    end

    // gpio_out change log (reset value 0 is not logged).
    reg [7:0] gpio_prev = 8'h00;
    always @(negedge clk) begin
        if (active && gpio_out !== gpio_prev) begin
            if (fd_gpio != 0)
                $fdisplay(fd_gpio, "%02x", gpio_out);
            gpio_prev = gpio_out;
        end
    end

    // Handshake trace: cycle, addr, wdata, wstrb, rdata (handshake on the next rising edge).
    always @(negedge clk) begin
        if (active && p_mem_valid === 1'b1 && p_mem_ready === 1'b1) begin
            if (p_mem_instr === 1'b1)
                last_fetch_addr = p_mem_addr;
            if (fd_trace != 0)
                $fdisplay(fd_trace, "%0d %08x %08x %x %08x", cycle, p_mem_addr, p_mem_wdata, p_mem_wstrb, p_mem_rdata);
        end
    end

    // ------------------------------------------------------------------
    // UART RX driver: 8N1, one bit = BIT_CYCLES clocks, driven on the falling edge.
    // ------------------------------------------------------------------
    integer   rx_i;
    integer   rx_j;
    reg [7:0] rx_b;

    task uart_rx_bit;
        input b;
        begin
            uart_rx = b;
            repeat (BIT_CYCLES) @(negedge clk);
        end
    endtask

    initial begin : uart_rx_driver
        uart_rx = 1'b1;
        wait (cpu_started === 1'b1);
        if (uart_in_len > 0) begin
            repeat (uart_in_delay) @(posedge clk);
            @(negedge clk);
            $display("[TB] uart_rx: sending %0d bytes from cycle %0d", uart_in_len, cycle);
            for (rx_i = 0; rx_i < uart_in_len; rx_i = rx_i + 1) begin
                rx_b = uart_in_mem[rx_i];
                uart_rx_bit(1'b0);
                for (rx_j = 0; rx_j < 8; rx_j = rx_j + 1)
                    uart_rx_bit(rx_b[rx_j]);
                uart_rx_bit(1'b1);
            end
            $display("[TB] uart_rx: last byte sent at cycle %0d", cycle);
        end
    end

    // ------------------------------------------------------------------
    // Host port access (spec 4.4): signals change on the falling edge.
    // ------------------------------------------------------------------
    task host_write_word;
        input [8:0]  a;
        input [31:0] d;
        begin
            @(negedge clk);
            host_cs    = 1'b1;
            host_we    = 1'b1;
            host_addr  = a;
            host_wdata = d;
            host_wmask = 4'hF;
            @(negedge clk);            // T0 has passed: SRAM sampled the write
            host_cs    = 1'b0;
            host_we    = 1'b0;
            host_wmask = 4'h0;
        end
    endtask

    // Host write with an explicit byte mask (spec 4.4: wmask0 = host_wmask).
    task host_write_word_mask;
        input [8:0]  a;
        input [31:0] d;
        input [3:0]  m;
        begin
            @(negedge clk);
            host_cs    = 1'b1;
            host_we    = 1'b1;
            host_addr  = a;
            host_wdata = d;
            host_wmask = m;
            @(negedge clk);            // T0 has passed: SRAM sampled the write
            host_cs    = 1'b0;
            host_we    = 1'b0;
            host_wmask = 4'h0;
        end
    endtask

    task host_read_word;
        input  [8:0]  a;
        output [31:0] d;
        begin
            @(negedge clk);
            host_cs    = 1'b1;
            host_we    = 1'b0;
            host_addr  = a;
            host_wmask = 4'h0;
            @(negedge clk);            // T0 has passed: SRAM sampled the read
            host_cs    = 1'b0;
            @(negedge clk);            // T1 has passed: rdata_q updated
            d = host_rdata;
        end
    endtask

    // ------------------------------------------------------------------
    // Result file and end of simulation
    // ------------------------------------------------------------------
    task write_sram_cov;
        integer fd_cov;
        begin
            fd_cov = $fopen({out_dir, "/sram_cov.txt"}, "w");
            if (fd_cov == 0) begin
                $display("[CHK:sim_error] FAIL cannot open %s/sram_cov.txt", out_dir);
                fail_sim_error = fail_sim_error + 32'd1;
            end else begin
                $fdisplay(fd_cov, "# byte_addr data_reads fetches writes wstrb_mask (bit <wstrb> set per write strobe seen)");
                for (cov_i = 0; cov_i < SRAM_WORDS; cov_i = cov_i + 1)
                    $fdisplay(fd_cov, "%03x %0d %0d %0d %04x", {cov_i[8:0], 2'b00}, cov_rd[cov_i], cov_if[cov_i],
                              cov_wr[cov_i], cov_ws[cov_i]);
                $fclose(fd_cov);
            end
        end
    endtask

    task finish_sim;
        begin
            write_sram_cov;
            fd_result = $fopen({out_dir, "/tb_result.txt"}, "w");
            if (fd_result == 0) begin
                $display("[CHK:sim_error] FAIL cannot open %s/tb_result.txt", out_dir);
            end else begin
                $fdisplay(fd_result, "end_reason=%s", end_reason);
                $fdisplay(fd_result, "done_count=%0d", done_count);
                if (done_seen)
                    $fdisplay(fd_result, "done=0x%08x", first_done_value);
                else
                    $fdisplay(fd_result, "done=none");
                $fdisplay(fd_result, "done_cycle=%0d", first_done_cycle);
                $fdisplay(fd_result, "sig=0x%08x", p_sig_value);
                if (done_seen)
                    $fdisplay(fd_result, "sig_at_done=0x%08x", first_done_sig);
                else
                    $fdisplay(fd_result, "sig_at_done=none");
                $fdisplay(fd_result, "cycles=%0d", cycle);
                $fdisplay(fd_result, "cpu_start_cycle=%0d", cpu_start_cycle);
                if (trap_seen)
                    $fdisplay(fd_result, "trap_cycle=%0d", trap_cycle);
                $fdisplay(fd_result, "uart_bytes=%0d", uart_bytes);
                $fdisplay(fd_result, "unmapped=%0d", unmapped_count);
                $fdisplay(fd_result, "uart_wr=%0d", uart_wr);
                $fdisplay(fd_result, "uart_wr_stalled=%0d", uart_wr_stalled);
                $fdisplay(fd_result, "uart_wr_stall_cycles=%0d", uart_wr_stall_cycles);
                $fdisplay(fd_result, "sram_port_accesses=%0d", sram_port_accesses);
                $fdisplay(fd_result, "mid_resets=%0d", mid_resets);
                $fdisplay(fd_result, "fail.test_ctrl=%0d", fail_test_ctrl);
                $fdisplay(fd_result, "fail.trap=%0d", fail_trap);
                $fdisplay(fd_result, "fail.timeout=%0d", fail_timeout);
                $fdisplay(fd_result, "fail.uart_monitor=%0d", fail_uart + fail_uart_drain);
                $fdisplay(fd_result, "fail.bus_assert=%0d", fail_bus);
                $fdisplay(fd_result, "fail.sram_port=%0d", fail_sram_port);
                $fdisplay(fd_result, "fail.irq_line=%0d", fail_irq_line);
                $fdisplay(fd_result, "fail.uart_div=%0d", fail_uart_div);
`ifdef GL_LOCKSTEP
                if (u_gl_lockstep.fail_count > 10)
                    $display("[CHK:gl_lockstep] FAIL %0d mismatches in total (first 10 printed)", u_gl_lockstep.fail_count);
                $fdisplay(fd_result, "fail.gl_lockstep=%0d", u_gl_lockstep.fail_count);
                $fdisplay(fd_result, "gl_compares=%0d", u_gl_lockstep.compare_count);
`endif
`ifndef VERILATOR
                $fdisplay(fd_result, "fail.x_check=%0d", fail_x);
                $fdisplay(fd_result, "simulator=icarus");
`else
                $fdisplay(fd_result, "simulator=verilator");
`endif
                $fdisplay(fd_result, "fail.sim_error=%0d", fail_sim_error);
                $fdisplay(fd_result, "finished=1");
                $fclose(fd_result);
            end
            if (fd_uart != 0)  $fclose(fd_uart);
            if (fd_gpio != 0)  $fclose(fd_gpio);
            if (fd_trace != 0) $fclose(fd_trace);
            $display("[TB] end_reason=%s cycles=%0d done_count=%0d uart_bytes=%0d", end_reason, cycle, done_count, uart_bytes);
            $finish;
        end
    endtask

    task abort_sim;
        input string why;
        begin
            fail_sim_error = fail_sim_error + 32'd1;
            $display("[CHK:sim_error] FAIL %s", why);
            end_reason = "abort";
            finish_sim;
            // $finish takes effect when this process next waits; block here so
            // that no statement after the abort point runs.
            forever @(posedge clk);
        end
    endtask

    // ------------------------------------------------------------------
    // Main sequence
    // ------------------------------------------------------------------
    initial begin : main
        end_reason = "running";
        if (!$value$plusargs("fw=%s", fw_file))               fw_file = "";
        if (!$value$plusargs("load=%s", load))                load = "backdoor";
        if (!$value$plusargs("out_dir=%s", out_dir))          out_dir = ".";
        if (!$value$plusargs("uart_in=%s", uart_in_file))     uart_in_file = "";
        if (!$value$plusargs("boot_mode=%d", boot_mode_arg))  boot_mode_arg = 0;
        if (!$value$plusargs("max_cycles=%d", max_cycles))    max_cycles = 1000000;
        if (!$value$plusargs("fw_words=%d", fw_words))        fw_words = 0;
        if (!$value$plusargs("uart_in_len=%d", uart_in_len))  uart_in_len = 0;
        if (!$value$plusargs("uart_in_delay=%d", uart_in_delay)) uart_in_delay = 0;
        trace_en  = $test$plusargs("trace") ? 1'b1 : 1'b0;
        vcd_en    = $test$plusargs("vcd") ? 1'b1 : 1'b0;
        allow_unmapped = $test$plusargs("allow_unmapped") ? 1'b1 : 1'b0;
        rst_store_en   = $value$plusargs("reset_on_store=%h", rst_store_addr) ? 1'b1 : 1'b0;
        boot_mode = boot_mode_arg[1:0];

        fd_uart = $fopen({out_dir, "/uart.txt"}, "w");
        fd_gpio = $fopen({out_dir, "/gpio.txt"}, "w");
        if (trace_en)
            fd_trace = $fopen({out_dir, "/trace.log"}, "w");
        if (vcd_en) begin
            $dumpfile({out_dir, "/wave.vcd"});
            $dumpvars(0, tb_soc);
        end
        $display("[TB] load=%s fw=%s fw_words=%0d boot_mode=%0d max_cycles=%0d uart_in_len=%0d uart_in_delay=%0d allow_unmapped=%0d out_dir=%s",
                 load, fw_file, fw_words, boot_mode_arg, max_cycles, uart_in_len, uart_in_delay, allow_unmapped, out_dir);
        if (rst_store_en)
            $display("[TB] reset_on_store=0x%08x", rst_store_addr);
        if (fd_uart == 0 || fd_gpio == 0 || (trace_en && fd_trace == 0))
            abort_sim("cannot open output files in +out_dir");

        // A malformed numeric plusarg reads back as X on Icarus: stop instead of
        // running with an undefined setting.
        if (^{boot_mode_arg, max_cycles, fw_words, uart_in_len, uart_in_delay, rst_store_addr} === 1'bx)
            abort_sim("malformed numeric plusarg (boot_mode, max_cycles, fw_words, uart_in_len, uart_in_delay or reset_on_store)");

        // ---- preload ----
        if (fw_words < 0 || fw_words > SRAM_WORDS)
            abort_sim("+fw_words out of range");
        if (load == "backdoor") begin
            if (fw_file == "")
                abort_sim("+load=backdoor needs +fw=<hex>");
            if (fw_words > 0)
                $readmemh(fw_file, dut.sram0.mem, 0, fw_words - 1);
            else
                $readmemh(fw_file, dut.sram0.mem);
`ifdef GL_LOCKSTEP
            if (fw_words > 0)
                $readmemh(fw_file, dut_gl.sram0.mem, 0, fw_words - 1);
            else
                $readmemh(fw_file, dut_gl.sram0.mem);
`endif
        end else if (load == "host") begin
            if (fw_file == "" || fw_words < 1)
                abort_sim("+load=host needs +fw=<hex> and +fw_words=<n>");
            if (fw_words > HOST_MASK_WORD)
                abort_sim("+load=host image reaches the last SRAM word, which the byte-mask check uses");
            $readmemh(fw_file, host_img, 0, fw_words - 1);
        end else if (load != "uart" && load != "none") begin
            abort_sim("unknown +load value (expected backdoor|host|uart|none)");
        end
        if (uart_in_len < 0 || uart_in_len > UART_IN_MAX)
            abort_sim("+uart_in_len out of range");
        if (uart_in_len > 0) begin
            if (uart_in_file == "")
                abort_sim("+uart_in_len > 0 needs +uart_in=<hex>");
            $readmemh(uart_in_file, uart_in_mem, 0, uart_in_len - 1);
        end

        // ---- reset ----
        host_en = (load == "host") ? 1'b1 : 1'b0;
        resetn  = 1'b0;
        repeat (RESET_CYCLES) @(posedge clk);
        @(negedge clk);
        resetn = 1'b1;
        active = 1'b1;

        // ---- host port load: write every word, read every word back, compare ----
        if (load == "host") begin
            for (i = 0; i < fw_words; i = i + 1)
                host_write_word(i[8:0], host_img[i]);
            for (i = 0; i < fw_words; i = i + 1) begin
                host_read_word(i[8:0], rd);
                if (rd !== host_img[i]) begin
                    $display("[TB] host read-back word %0d: wrote 0x%08x, read 0x%08x", i, host_img[i], rd);
                    abort_sim("host port load read-back mismatch");
                end
            end
            $display("[TB] host port load: %0d words written and read back at cycle %0d", fw_words, cycle);

            // Byte-mask check on the last SRAM word (above the image, which is
            // at most 448 words, so the firmware never relies on its content):
            // background all ones, then write 0 with mask hm, read back. Every
            // byte with hm[k]=1 must be 0x00 and every other byte must stay 0xFF.
            for (i = 0; i < 10; i = i + 1) begin
                case (i)
                    0: hm = 4'b0000;  1: hm = 4'b0001;  2: hm = 4'b0010;  3: hm = 4'b0100;
                    4: hm = 4'b1000;  5: hm = 4'b0011;  6: hm = 4'b1100;  7: hm = 4'b0101;
                    8: hm = 4'b1010;  default: hm = 4'b1111;
                endcase
                hm_exp = ~{{8{hm[3]}}, {8{hm[2]}}, {8{hm[1]}}, {8{hm[0]}}};
                host_write_word(HOST_MASK_WORD[8:0], 32'hFFFF_FFFF);
                host_write_word_mask(HOST_MASK_WORD[8:0], 32'h0000_0000, hm);
                host_read_word(HOST_MASK_WORD[8:0], rd);
                if (rd !== hm_exp) begin
                    $display("[TB] host port byte-mask check, word %0d: background 0xffffffff, wrote 0 with wmask %b, read 0x%08x, expected 0x%08x",
                             HOST_MASK_WORD, hm, rd, hm_exp);
                    abort_sim("host port partial-wmask write mismatch (spec 4.4 wmask0 = host_wmask)");
                end
            end
            $display("[TB] host port byte-mask check: 10 masks on word %0d read back as expected at cycle %0d", HOST_MASK_WORD, cycle);
            @(negedge clk);
            host_en = 1'b0;
        end

        cpu_started     = 1'b1;
        cpu_start_cycle = cycle;
        $display("[TB] CPU released at cycle %0d", cycle);

        // ---- run ----
        if (rst_store_en) begin
            // Mid-run reset (spec 4.9): find the falling edge where the CPU first
            // presents a store to rst_store_addr and drive resetn=0 there, so the
            // next rising edge samples resetn=0 together with that store.
            while (!done_seen && !trap_seen && cycle < max_cycles && !rst_hit) begin
                @(negedge clk);
                rst_hit = (p_mem_valid === 1'b1 && p_mem_wstrb != 4'd0 && p_mem_addr == rst_store_addr);
            end
            if (rst_hit) begin
                resetn     = 1'b0;
                mid_resets = mid_resets + 32'd1;
                $display("[TB] mid-run reset: resetn=0 from cycle %0d, while the CPU presents a store to 0x%08x (wdata 0x%08x, wstrb %b, old SRAM word 0x%08x)",
                         cycle, p_mem_addr, p_mem_wdata, p_mem_wstrb, dut.sram0.mem[rst_store_addr[10:2]]);
                repeat (RESET_CYCLES) @(posedge clk);
                @(negedge clk);
                resetn = 1'b1;
                $display("[TB] mid-run reset released at cycle %0d (SRAM word 0x%08x is now 0x%08x)",
                         cycle, rst_store_addr, dut.sram0.mem[rst_store_addr[10:2]]);
            end
        end
        while (!done_seen && !trap_seen && cycle < max_cycles)
            @(posedge clk);
        if (done_seen) begin
            end_reason = "done";
        end else if (trap_seen) begin
            end_reason = "trap";
        end else begin
            end_reason   = "timeout";
            fail_timeout = fail_timeout + 32'd1;
            $display("[CHK:timeout] FAIL no DONE write within max_cycles=%0d (cycle %0d)", max_cycles, cycle);
        end

        // ---- drain: let the last UART frame finish, keep checking ----
        drain_start = cycle;
        while (((cycle - drain_start) < DRAIN_IDLE || uart_idle < DRAIN_IDLE) &&
               (cycle - drain_start) < DRAIN_LIMIT)
            @(posedge clk);
        if (uart_idle < DRAIN_IDLE) begin
            if (end_reason == "done") begin
                fail_uart_drain = fail_uart_drain + 32'd1;
                $display("[CHK:uart_monitor] FAIL uart_tx not idle for %0d cycles within %0d cycles after DONE (in_frame=%0d)",
                         DRAIN_IDLE, DRAIN_LIMIT, uart_in_frame);
            end else begin
                $display("[TB] uart_tx not idle at end of simulation (in_frame=%0d)", uart_in_frame);
            end
        end
        finish_sim;
    end
endmodule

`default_nettype wire
