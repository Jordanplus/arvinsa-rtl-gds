// =============================================================================
// soc_bus.v -- PicoRV32 native-bus interconnect for soc_top.
// Contract: docs/spec/soc_spec.md sections 2, 4.2, 4.3, 4.4, 5.
//
// * Full address decode of every window in memmap.vh (no partial decode).
//   sel_* are probe names (spec section 3.1): mem_valid AND address in window.
// * mem_ready is a registered output, high for exactly one cycle per
//   transaction. Unmapped accesses are answered with mem_rdata = 0 and
//   writes to them are ignored.
// * SRAM port 0 (sram0 lives in soc_top) per the section 4.3 timing table:
//     read : csb0=0 only in the cycle before T0; T1: rdata_q <= dout0;
//            mem_ready=1 in the cycle after T1 with mem_rdata = rdata_q.
//     write: csb0=0/web0=0 only in the cycle before T0; mem_ready=1 after T0.
// * Peripheral and ROM accesses: the request is presented in the first cycle
//   of the transaction and accepted at the next rising edge (read data is
//   registered, mem_ready follows in the next cycle). A UART DATA write is
//   held (request kept, no accept, no mem_ready) while reg_dat_wait=1.
// * Host port (section 4.4): host_en=1 hands SRAM port 0 to the host and
//   blocks CPU-side requests (the CPU is held in reset); host_rdata = rdata_q.
// * Datapath registers (rdata_q, prdata_q) have no reset.
// * Reset: the edge at which resetn=0 is sampled starts no CPU transaction.
//   The CPU-path SRAM select is gated with resetn, so a store presented in
//   that cycle is dropped like a peripheral register write (synchronous
//   reset has priority everywhere). The host path is not gated: the host
//   port must also work while resetn=0 (section 4.4).
// * Bug injections (section 5 and dv/bugs.toml): BUG_R01, BUG_R02, BUG_R03,
//   BUG_R07, BUG_R09, BUG_R10, BUG_R13, BUG_R17 (UART DATA write stall
//   ignored), BUG_R18 (csb0 not blocked in the response cycle: a second SRAM
//   access per transaction), BUG_R19 (CPU-path csb0 not gated with resetn: a
//   store presented at the edge that samples resetn=0 is written).
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module soc_bus (
    input  wire        clk,
    input  wire        resetn,          // synchronous, active low

    // PicoRV32 native memory interface (u_cpu)
    input  wire        mem_valid,
    input  wire [31:0] mem_addr,
    input  wire [31:0] mem_wdata,
    input  wire [3:0]  mem_wstrb,
    output wire        mem_ready,
    output wire [31:0] mem_rdata,

    // Host port (owns SRAM port 0 while host_en=1)
    input  wire        host_en,
    input  wire        host_cs,
    input  wire        host_we,
    input  wire [8:0]  host_addr,
    input  wire [31:0] host_wdata,
    input  wire [3:0]  host_wmask,
    output wire [31:0] host_rdata,

    // SRAM port 0 (sram0 is instantiated in soc_top)
    output wire        sram_csb0,
    output wire        sram_web0,
    output wire [3:0]  sram_wmask0,
    output wire [8:0]  sram_addr0,
    output wire [31:0] sram_din0,
    input  wire [31:0] sram_dout0,

    // Boot ROM (combinational case-ROM)
    output wire [6:0]  rom_addr,
    input  wire [31:0] rom_rdata,

    // Peripheral register ports. Write data is mem_wdata (wired in soc_top).
    // *_off is the byte offset inside the selected window.
    output wire        periph_we,
    output wire [3:0]  periph_off,
    output wire        uart_req,
    input  wire [31:0] uart_rdata,
    input  wire        uart_stall,      // simpleuart reg_dat_wait
    output wire        gpio_req,
    input  wire [31:0] gpio_rdata,
    output wire        test_req,
    input  wire [31:0] test_rdata
);

    // ------------------------------------------------------------------
    // Address windows (single source: memmap.vh)
    // ------------------------------------------------------------------
    localparam [31:0] SRAM_BASE = `SOC_SRAM_BASE;
    localparam [31:0] SRAM_SIZE = `SOC_SRAM_SIZE;
    localparam [31:0] ROM_BASE  = `SOC_ROM_BASE;
    localparam [31:0] ROM_SIZE  = `SOC_ROM_SIZE;
    localparam [31:0] UART_BASE = `SOC_UART_BASE;
    localparam [31:0] UART_SIZE = `SOC_UART_SIZE;
    localparam [31:0] GPIO_BASE = `SOC_GPIO_BASE;
    localparam [31:0] GPIO_SIZE = `SOC_GPIO_SIZE;
    localparam [31:0] TEST_BASE = `SOC_TEST_BASE;
`ifdef SOC_CPU_HAZARD3
    localparam [31:0] TEST_SIZE = `SOC_TEST_SIZE_H3;     // + FATAL (ADR-0011)
`else
    localparam [31:0] TEST_SIZE = `SOC_TEST_SIZE;
`endif

    // Offset into each window; (addr - base) < size is an exact range check
    // (an address below base wraps to a large unsigned offset).
    wire [31:0] sram_off = mem_addr - SRAM_BASE;
    wire [31:0] rom_off  = mem_addr - ROM_BASE;
    wire [31:0] uart_off = mem_addr - UART_BASE;
    wire [31:0] gpio_off = mem_addr - GPIO_BASE;
    wire [31:0] test_off = mem_addr - TEST_BASE;

    wire in_sram = (sram_off < SRAM_SIZE);
    wire in_rom  = (rom_off  < ROM_SIZE);
`ifdef BUG_R10
    // BUG_R10: partial decode, the UART window is matched on addr[31:12] only
    // (the 8-byte register block repeats over the whole 4 KB page).
    wire in_uart = (uart_off[31:12] == 20'd0);
    wire unused_bug_r10 = (uart_off < UART_SIZE);
`else
    wire in_uart = (uart_off < UART_SIZE);
`endif
    wire in_gpio = (gpio_off < GPIO_SIZE);
    wire in_test = (test_off < TEST_SIZE);
    wire in_any  = in_sram | in_rom | in_uart | in_gpio | in_test;

    // Decode results (probe names, spec section 3.1)
    wire sel_sram = mem_valid & in_sram;
    wire sel_rom  = mem_valid & in_rom;
    wire sel_uart = mem_valid & in_uart;
`ifdef BUG_R07
    // BUG_R07: overlapping decode, sel_gpio also asserts in the UART window.
    wire sel_gpio = mem_valid & (in_gpio | in_uart);
`else
    wire sel_gpio = mem_valid & in_gpio;
`endif
    wire sel_test = mem_valid & in_test;
    // Unmapped: no data source is enabled in the read mux below (rdata = 0)
    // and no peripheral request is raised (write ignored).
    wire sel_none = mem_valid & ~in_any;

    // ------------------------------------------------------------------
    // Transaction control
    // ------------------------------------------------------------------
    reg  srd_q;         // SRAM read sampled at T0; rdata_q loads at T1
    reg  ready_q;       // registered mem_ready
    reg  resp_sram_q;   // response data comes from rdata_q (SRAM)

    wire is_write = |mem_wstrb;
    // A new CPU request may only start when no response is in flight and the
    // host does not own the SRAM port.
    wire idle     = ~srd_q & ~ready_q & ~host_en;
`ifdef BUG_R17
    // BUG_R17: the UART DATA write stall is ignored; a write presented while
    // the transmitter is busy is answered at once and the byte is dropped.
    wire stall    = 1'b0;
    wire unused_bug_r17 = uart_stall;
`else
    wire stall    = sel_uart & uart_stall;
`endif
`ifdef BUG_R09
    // BUG_R09: an unmapped access is never accepted, so it never gets mem_ready.
    wire accept   = idle & mem_valid & ~stall & in_any;
`else
    wire accept   = idle & mem_valid & ~stall;
`endif

    always @(posedge clk) begin
        if (!resetn || host_en) begin
            srd_q       <= 1'b0;
            ready_q     <= 1'b0;
            resp_sram_q <= 1'b0;
        end else begin
            ready_q <= 1'b0;
            if (srd_q) begin
                // T1: rdata_q captures dout0 (below); respond in the next cycle.
                srd_q   <= 1'b0;
                ready_q <= 1'b1;
            end
            if (accept) begin
                resp_sram_q <= sel_sram;
`ifdef BUG_R03
                // BUG_R03: SRAM read answered right after T0 (one cycle early),
                // mem_rdata still comes from rdata_q (not yet updated).
                ready_q <= 1'b1;
`else
                if (sel_sram && !is_write)
                    srd_q <= 1'b1;
                else
                    ready_q <= 1'b1;
`endif
            end
        end
    end

    assign mem_ready = ready_q;
    assign periph_we = is_write;

    // ------------------------------------------------------------------
    // Peripheral requests: asserted in the first cycle of a transaction and
    // kept only while a UART DATA write is stalled by reg_dat_wait.
    // ------------------------------------------------------------------
    assign uart_req   = idle & sel_uart;
    assign gpio_req   = idle & sel_gpio;
    assign test_req   = idle & sel_test;
    assign periph_off = sel_test ? test_off[3:0] :
                        sel_gpio ? gpio_off[3:0] : uart_off[3:0];
    assign rom_addr   = rom_off[8:2];

    // Registered read data for non-SRAM targets; unmapped -> 0.
    wire [31:0] prdata_mux = ({32{sel_rom }} & rom_rdata )
                           | ({32{sel_uart}} & uart_rdata)
                           | ({32{sel_gpio}} & gpio_rdata)
                           | ({32{sel_test}} & test_rdata);
    reg  [31:0] prdata_q;           // datapath register (no reset)
    always @(posedge clk) begin
        if (accept)
            prdata_q <= prdata_mux;
    end

    // ------------------------------------------------------------------
    // SRAM port 0: CPU path, host mux, read data register
    // ------------------------------------------------------------------
    // Only the cycle before T0, and never at an edge where resetn=0 is sampled.
`ifdef BUG_R18
    // BUG_R18: csb0 is not blocked by ready_q, so the SRAM is accessed again
    // in the response cycle (two accesses per transaction, spec 4.3).
    wire       cpu_csb0 = ~(resetn & ~srd_q & ~host_en & sel_sram);
`elsif BUG_R19
    // BUG_R19: csb0 is not gated with resetn, so a store presented at the
    // edge that samples resetn=0 is written (spec 4.9, RTL-RST-01).
    wire       cpu_csb0 = ~(idle & sel_sram);
`else
    wire       cpu_csb0 = ~(resetn & idle & sel_sram);
`endif
    wire       cpu_web0 = ~is_write;
`ifdef BUG_R01
    // BUG_R01: CPU-path wmask0[0] and wmask0[1] swapped.
    wire [3:0] cpu_wmask0 = {mem_wstrb[3:2], mem_wstrb[0], mem_wstrb[1]};
`else
    wire [3:0] cpu_wmask0 = mem_wstrb;
`endif
    wire [8:0] cpu_addr0 = sram_off[10:2];

    wire [8:0] addr0_mux = host_en ? host_addr : cpu_addr0;
    assign sram_csb0   = host_en ? ~host_cs   : cpu_csb0;
    assign sram_web0   = host_en ? ~host_we   : cpu_web0;
`ifdef BUG_R13
    // BUG_R13: host_wmask ignored, every host write updates all four bytes.
    assign sram_wmask0 = host_en ? 4'hF : cpu_wmask0;
    wire   unused_bug_r13 = &{1'b0, host_wmask};
`else
    assign sram_wmask0 = host_en ? host_wmask : cpu_wmask0;
`endif
    assign sram_din0   = host_en ? host_wdata : mem_wdata;
`ifdef BUG_R02
    // BUG_R02: addr0[8] stuck at 0, applied after the host/CPU mux.
    assign sram_addr0  = {1'b0, addr0_mux[7:0]};
    wire   unused_bug_r02 = addr0_mux[8];
`else
    assign sram_addr0  = addr0_mux;
`endif

    // A read sampled at T0 (from either owner) is captured into rdata_q at T1.
    // The flag is cleared by resetn only while the CPU owns the port, so the
    // host port also works while resetn=0.
    wire sram_rd_t0 = ~sram_csb0 & sram_web0;
    reg  rd_pend_q;
    always @(posedge clk) begin
        if (!resetn && !host_en)
            rd_pend_q <= 1'b0;
        else
            rd_pend_q <= sram_rd_t0;
    end

    reg  [31:0] rdata_q;            // SRAM read data register (no reset)
    always @(posedge clk) begin
        if (rd_pend_q)
            rdata_q <= sram_dout0;
    end

    assign mem_rdata  = resp_sram_q ? rdata_q : prdata_q;
    assign host_rdata = rdata_q;

    // Offset bits outside the decoded windows and the probe-only sel_none are
    // intentionally not used by any logic.
    wire unused_bus = &{1'b0, sel_none,
                        sram_off[31:11], sram_off[1:0], rom_off[31:9], rom_off[1:0],
                        uart_off[31:4], gpio_off[31:4], test_off[31:4]};

endmodule

`default_nettype wire
