// =============================================================================
// soc_top.v -- Phase 1 SoC top level (PicoRV32 + 2 KB SRAM + Boot ROM + UART +
// GPIO + TEST_CTRL). Contract: docs/spec/soc_spec.md sections 3 and 4.
//
// Hierarchical probe names required by spec section 3.1:
//   mem_valid/mem_instr/mem_ready/mem_addr/mem_wdata/mem_wstrb/mem_rdata,
//   u_cpu, u_bus.sel_*, sram0 (directly in this module),
//   u_test_ctrl.done_strobe/done_value/sig_value.
// Bug injection: BUG_R05 (irq[SOC_IRQ_TEST] tied to 0), BUG_R08 (divider
// result bit 0 inverted). Other BUG_* defines are implemented in soc_bus.v,
// soc_uart.v, soc_gpio.v and soc_test_ctrl.v.
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module soc_top (
`ifdef USE_POWER_PINS
    inout  wire        vccd1,
    inout  wire        vssd1,
`endif
    input  wire        clk,
    input  wire        resetn,      // synchronous, active low
    output wire        uart_tx,
    input  wire        uart_rx,
    output wire [7:0]  gpio_out,
    input  wire [1:0]  boot_mode,
    output wire        trap,        // PicoRV32 trap
    // Host write port: host_en=1 holds the CPU in reset and gives SRAM
    // port 0 to the host.
    input  wire        host_en,
    input  wire        host_cs,     // one access in this cycle
    input  wire        host_we,
    input  wire [8:0]  host_addr,   // word address
    input  wire [31:0] host_wdata,
    input  wire [3:0]  host_wmask,
    output wire [31:0] host_rdata
);

    // ------------------------------------------------------------------
    // PicoRV32 native memory bus (probe names, spec section 3.1)
    // ------------------------------------------------------------------
    wire        mem_valid;
    wire        mem_instr;
    wire        mem_ready;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [3:0]  mem_wstrb;
    wire [31:0] mem_rdata;

    wire        cpu_resetn = resetn & ~host_en;

    // ------------------------------------------------------------------
    // Interrupts: only irq[SOC_IRQ_TEST] is used (TEST_CTRL.IRQ_TRIG[0]).
    // ------------------------------------------------------------------
    wire        irq_test;
`ifdef BUG_R05
    // BUG_R05: test IRQ line disconnected (stuck at 0).
    wire        irq_line = 1'b0;
    wire        unused_bug_r05 = irq_test;
`else
    wire        irq_line = irq_test;
`endif
    wire [31:0] irq = {31'd0, irq_line} << `SOC_IRQ_TEST;

    // Outputs of u_cpu that this SoC does not use (look-ahead bus, PCPI,
    // EOI, trace). They are left dangling on purpose.
    wire        unused_mem_la_read;
    wire        unused_mem_la_write;
    wire [31:0] unused_mem_la_addr;
    wire [31:0] unused_mem_la_wdata;
    wire [3:0]  unused_mem_la_wstrb;
    wire        unused_pcpi_valid;
    wire [31:0] unused_pcpi_insn;
    wire [31:0] unused_pcpi_rs1;
    wire [31:0] unused_pcpi_rs2;
    wire [31:0] unused_eoi;
    wire        unused_trace_valid;
    wire [35:0] unused_trace_data;

    // ------------------------------------------------------------------
    // PCPI: not used (spec section 4.1, inputs tied to 0). BUG_R08 only:
    // the built-in divider is disabled and replaced by an external
    // picorv32_pcpi_div (the same divider module from picorv32.v) whose
    // result has bit 0 inverted, so div/divu/rem/remu return wrong values.
    // ------------------------------------------------------------------
`ifdef BUG_R08
    localparam [0:0] CPU_ENABLE_DIV  = 1'b0;
    localparam [0:0] CPU_ENABLE_PCPI = 1'b1;
    wire        pcpi_wr;
    wire [31:0] pcpi_div_rd;
    wire [31:0] pcpi_rd = pcpi_div_rd ^ 32'h0000_0001;
    wire        pcpi_wait;
    wire        pcpi_ready;

    picorv32_pcpi_div u_bug_r08_div (
        .clk        (clk),
        .resetn     (cpu_resetn),
        .pcpi_valid (unused_pcpi_valid),
        .pcpi_insn  (unused_pcpi_insn),
        .pcpi_rs1   (unused_pcpi_rs1),
        .pcpi_rs2   (unused_pcpi_rs2),
        .pcpi_wr    (pcpi_wr),
        .pcpi_rd    (pcpi_div_rd),
        .pcpi_wait  (pcpi_wait),
        .pcpi_ready (pcpi_ready)
    );
`else
    localparam [0:0] CPU_ENABLE_DIV  = 1'b1;
    localparam [0:0] CPU_ENABLE_PCPI = 1'b0;
    wire        pcpi_wr    = 1'b0;
    wire [31:0] pcpi_rd    = 32'd0;
    wire        pcpi_wait  = 1'b0;
    wire        pcpi_ready = 1'b0;
`endif

    picorv32 #(
        .COMPRESSED_ISA   (1'b1),
        .ENABLE_MUL       (1'b1),
        .ENABLE_DIV       (CPU_ENABLE_DIV),
        .ENABLE_PCPI      (CPU_ENABLE_PCPI),
        .BARREL_SHIFTER   (1'b1),
        .ENABLE_IRQ       (1'b1),
        .ENABLE_IRQ_QREGS (1'b1),
        .ENABLE_IRQ_TIMER (1'b1),
        .CATCH_MISALIGN   (1'b1),
        .CATCH_ILLINSN    (1'b1),
        .ENABLE_TRACE     (1'b0),
        .PROGADDR_RESET   (`SOC_PROGADDR_RESET),
        .PROGADDR_IRQ     (`SOC_PROGADDR_IRQ)
    ) u_cpu (
        .clk          (clk),
        .resetn       (cpu_resetn),
        .trap         (trap),
        .mem_valid    (mem_valid),
        .mem_instr    (mem_instr),
        .mem_ready    (mem_ready),
        .mem_addr     (mem_addr),
        .mem_wdata    (mem_wdata),
        .mem_wstrb    (mem_wstrb),
        .mem_rdata    (mem_rdata),
        .mem_la_read  (unused_mem_la_read),
        .mem_la_write (unused_mem_la_write),
        .mem_la_addr  (unused_mem_la_addr),
        .mem_la_wdata (unused_mem_la_wdata),
        .mem_la_wstrb (unused_mem_la_wstrb),
        .pcpi_valid   (unused_pcpi_valid),
        .pcpi_insn    (unused_pcpi_insn),
        .pcpi_rs1     (unused_pcpi_rs1),
        .pcpi_rs2     (unused_pcpi_rs2),
        .pcpi_wr      (pcpi_wr),
        .pcpi_rd      (pcpi_rd),
        .pcpi_wait    (pcpi_wait),
        .pcpi_ready   (pcpi_ready),
        .irq          (irq),
        .eoi          (unused_eoi),
        .trace_valid  (unused_trace_valid),
        .trace_data   (unused_trace_data)
    );

    // ------------------------------------------------------------------
    // Bus
    // ------------------------------------------------------------------
    wire        sram_csb0;
    wire        sram_web0;
    wire [3:0]  sram_wmask0;
    wire [8:0]  sram_addr0;
    wire [31:0] sram_din0;
    wire [31:0] sram_dout0;

    wire [6:0]  rom_addr;
    wire [31:0] rom_rdata;

    wire        periph_we;
    wire [3:0]  periph_off;
    wire        uart_req;
    wire [31:0] uart_rdata;
    wire        uart_stall;
    wire        gpio_req;
    wire [31:0] gpio_rdata;
    wire        test_req;
    wire [31:0] test_rdata;

    soc_bus u_bus (
        .clk         (clk),
        .resetn      (resetn),
        .mem_valid   (mem_valid),
        .mem_addr    (mem_addr),
        .mem_wdata   (mem_wdata),
        .mem_wstrb   (mem_wstrb),
        .mem_ready   (mem_ready),
        .mem_rdata   (mem_rdata),
        .host_en     (host_en),
        .host_cs     (host_cs),
        .host_we     (host_we),
        .host_addr   (host_addr),
        .host_wdata  (host_wdata),
        .host_wmask  (host_wmask),
        .host_rdata  (host_rdata),
        .sram_csb0   (sram_csb0),
        .sram_web0   (sram_web0),
        .sram_wmask0 (sram_wmask0),
        .sram_addr0  (sram_addr0),
        .sram_din0   (sram_din0),
        .sram_dout0  (sram_dout0),
        .rom_addr    (rom_addr),
        .rom_rdata   (rom_rdata),
        .periph_we   (periph_we),
        .periph_off  (periph_off),
        .uart_req    (uart_req),
        .uart_rdata  (uart_rdata),
        .uart_stall  (uart_stall),
        .gpio_req    (gpio_req),
        .gpio_rdata  (gpio_rdata),
        .test_req    (test_req),
        .test_rdata  (test_rdata)
    );

    // ------------------------------------------------------------------
    // SRAM macro (instance name fixed: sram0). Port 1 is tied off.
    // ------------------------------------------------------------------
    wire [31:0] unused_sram_dout1;

    sky130_sram_2kbyte_1rw1r_32x512_8 sram0 (
`ifdef USE_POWER_PINS
        .vccd1  (vccd1),
        .vssd1  (vssd1),
`endif
        .clk0   (clk),
        .csb0   (sram_csb0),
        .web0   (sram_web0),
        .wmask0 (sram_wmask0),
        .addr0  (sram_addr0),
        .din0   (sram_din0),
        .dout0  (sram_dout0),
        .clk1   (1'b0),
        .csb1   (1'b1),
        .addr1  (9'd0),
        .dout1  (unused_sram_dout1)
    );

    // ------------------------------------------------------------------
    // Boot ROM
    // ------------------------------------------------------------------
    bootrom u_bootrom (
        .addr  (rom_addr),
        .rdata (rom_rdata)
    );

    // ------------------------------------------------------------------
    // Peripherals
    // ------------------------------------------------------------------
    soc_uart u_uart (
        .clk     (clk),
        .resetn  (resetn),
        .req     (uart_req),
        .we      (periph_we),
        .off     (periph_off),
        .wdata   (mem_wdata),
        .rdata   (uart_rdata),
        .stall   (uart_stall),
        .uart_tx (uart_tx),
        .uart_rx (uart_rx)
    );

    soc_gpio u_gpio (
        .clk       (clk),
        .resetn    (resetn),
        .req       (gpio_req),
        .we        (periph_we),
        .off       (periph_off),
        .wdata     (mem_wdata),
        .rdata     (gpio_rdata),
        .gpio_out  (gpio_out),
        .boot_mode (boot_mode)
    );

    soc_test_ctrl u_test_ctrl (
        .clk      (clk),
        .resetn   (resetn),
        .req      (test_req),
        .we       (periph_we),
        .off      (periph_off),
        .wdata    (mem_wdata),
        .rdata    (test_rdata),
        .irq_test (irq_test)
    );

    // mem_instr is a probe-only signal (spec section 3.1).
    wire unused_top = &{1'b0, mem_instr};

endmodule

`default_nettype wire
