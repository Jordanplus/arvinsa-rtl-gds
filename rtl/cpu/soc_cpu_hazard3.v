// =============================================================================
// soc_cpu_hazard3.v -- Hazard3 (third_party/hazard3, tag v1.1.1) with the
// native memory bus of soc_bus (Phase 5, ADR-0011). soc_top instantiates it as
// u_cpu when SOC_CPU_HAZARD3 is defined; the PicoRV32 build does not read it.
//
// Configuration (ADR-0011 user decision 2): RV32IMC with the cycle/instret
// counters; no A, no debug, no PMP, no Xh3* extensions, one external IRQ.
//   RESET_VECTOR = SOC_PROGADDR_RESET (Boot ROM), MTVEC_INIT = SOC_PROGADDR_IRQ
//   (direct mode: interrupts and exceptions both enter there; the handler
//   reads mcause). Counters start inhibited (mcountinhibit = 1 at reset) and
//   the register file has no reset: start.S clears both (skill rule 3).
// Reset: Hazard3 uses an asynchronous active-low reset (59 negedge rst_n).
//   resetn here is the synchronous CPU reset of soc_top (resetn & ~host_en, a
//   combinational AND that may glitch), so it goes through one flop first:
//   rst_n_q asserts and releases one cycle after resetn, glitch-free and
//   aligned to clk (STA checks recovery/removal at the core's reset pins).
// Tie-offs (configuration_and_integration.adoc): no Xh3power, so pwrup_ack =
//   pwrup_req and unblock_in = unblock_out; fence_rdy = 1; clk_always_on = clk;
//   debug inputs 0 (dbg_sbus_vld must be 0: the 1-port wrapper arbitrates it);
//   hexokay = 1 (no global monitor); hresp = 0 (soc_bus never errors);
//   soft_irq = timer_irq = 0; mhartid_val = 0; eco_version = 0.
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module soc_cpu_hazard3 (
    input  wire        clk,
    input  wire        resetn,      // synchronous, active low (CPU reset of soc_top)
    input  wire        irq,         // level, active high (TEST_CTRL.IRQ_TRIG[0])

    output wire        mem_valid,
    output wire        mem_instr,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [3:0]  mem_wstrb,
    input  wire        mem_ready,
    input  wire [31:0] mem_rdata
);

    reg rst_n_q;
    always @(posedge clk)
        rst_n_q <= resetn;

    wire [31:0] haddr;
    wire        hwrite;
    wire [1:0]  htrans;
    wire [2:0]  hsize;
    wire [3:0]  hprot;
    wire [31:0] hwdata;
    wire        hready;
    wire [31:0] hrdata;

    wire        pwrup_req;
    wire        unblock_out;

    // Outputs this SoC does not use.
    wire        unused_clk_en;
    wire [2:0]  unused_hburst;
    wire        unused_hmastlock;
    wire [7:0]  unused_hmaster;
    wire        unused_hexcl;
    wire        unused_fence_i_vld;
    wire        unused_fence_d_vld;
    wire        unused_dbg_halted;
    wire        unused_dbg_running;
    wire [31:0] unused_dbg_data0_wdata;
    wire        unused_dbg_data0_wen;
    wire        unused_dbg_instr_data_rdy;
    wire        unused_dbg_instr_caught_exception;
    wire        unused_dbg_instr_caught_ebreak;
    wire        unused_dbg_sbus_rdy;
    wire        unused_dbg_sbus_err;
    wire [31:0] unused_dbg_sbus_rdata;

    hazard3_cpu_1port #(
        .RESET_VECTOR   (`SOC_PROGADDR_RESET),
        .MTVEC_INIT     (`SOC_PROGADDR_IRQ),
        .EXTENSION_A    (0),
        .EXTENSION_C    (1),
        .EXTENSION_M    (1),
        .CSR_COUNTER    (1),
        .DEBUG_SUPPORT  (0),
        .NUM_IRQS       (1)
    ) u_core (
        .clk                        (clk),
        .clk_always_on              (clk),
        .rst_n                      (rst_n_q),

        .pwrup_req                  (pwrup_req),
        .pwrup_ack                  (pwrup_req),
        .clk_en                     (unused_clk_en),
        .unblock_out                (unblock_out),
        .unblock_in                 (unblock_out),

        .haddr                      (haddr),
        .hwrite                     (hwrite),
        .htrans                     (htrans),
        .hsize                      (hsize),
        .hburst                     (unused_hburst),
        .hprot                      (hprot),
        .hmastlock                  (unused_hmastlock),
        .hmaster                    (unused_hmaster),
        .hexcl                      (unused_hexcl),
        .hready                     (hready),
        .hresp                      (1'b0),
        .hexokay                    (1'b1),
        .hwdata                     (hwdata),
        .hrdata                     (hrdata),

        .fence_i_vld                (unused_fence_i_vld),
        .fence_d_vld                (unused_fence_d_vld),
        .fence_rdy                  (1'b1),

        .dbg_req_halt               (1'b0),
        .dbg_req_halt_on_reset      (1'b0),
        .dbg_req_resume             (1'b0),
        .dbg_halted                 (unused_dbg_halted),
        .dbg_running                (unused_dbg_running),
        .dbg_data0_rdata            (32'd0),
        .dbg_data0_wdata            (unused_dbg_data0_wdata),
        .dbg_data0_wen              (unused_dbg_data0_wen),
        .dbg_instr_data             (32'd0),
        .dbg_instr_data_vld         (1'b0),
        .dbg_instr_data_rdy         (unused_dbg_instr_data_rdy),
        .dbg_instr_caught_exception (unused_dbg_instr_caught_exception),
        .dbg_instr_caught_ebreak    (unused_dbg_instr_caught_ebreak),
        .dbg_sbus_addr              (32'd0),
        .dbg_sbus_write             (1'b0),
        .dbg_sbus_size              (2'd0),
        .dbg_sbus_vld               (1'b0),
        .dbg_sbus_rdy               (unused_dbg_sbus_rdy),
        .dbg_sbus_err               (unused_dbg_sbus_err),
        .dbg_sbus_wdata             (32'd0),
        .dbg_sbus_rdata             (unused_dbg_sbus_rdata),

        .mhartid_val                (32'd0),
        .eco_version                (4'd0),

        .irq                        (irq),
        .soft_irq                   (1'b0),
        .timer_irq                  (1'b0)
    );

    soc_ahb2native u_bridge (
        .clk       (clk),
        .resetn    (resetn),
        .haddr     (haddr),
        .hwrite    (hwrite),
        .htrans    (htrans),
        .hsize     (hsize),
        .hprot     (hprot),
        .hwdata    (hwdata),
        .hready    (hready),
        .hrdata    (hrdata),
        .mem_valid (mem_valid),
        .mem_instr (mem_instr),
        .mem_addr  (mem_addr),
        .mem_wdata (mem_wdata),
        .mem_wstrb (mem_wstrb),
        .mem_ready (mem_ready),
        .mem_rdata (mem_rdata)
    );

endmodule

`default_nettype wire
