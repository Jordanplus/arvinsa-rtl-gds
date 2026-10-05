// =============================================================================
// soc_ahb2native.v -- AHB5 (Hazard3 hazard3_cpu_1port) to the PicoRV32 native
// memory bus of soc_bus (Phase 5, ADR-0011 user decision 1).
//
// Why: Hazard3 puts the write data on the bus in the data phase, one cycle
// after the address, and the OpenRAM SRAM samples address and data at the same
// rising edge (skill core-migration-hazard3, rule 5). soc_bus already turns a
// native-bus request (address, data and byte strobes together, held until
// mem_ready) into SRAM and peripheral accesses, so this bridge only waits for
// the data phase:
//   * an AHB address phase is taken when htrans[1] & hready (NSEQ; Hazard3 never
//     issues SEQ or BUSY, bus_behaviour.adoc); haddr/hwrite/hsize/hprot are
//     registered at that edge;
//   * from the next cycle (the data phase) mem_valid = 1 with the registered
//     word address, the byte strobes from hsize and haddr[1:0] (0 for reads)
//     and, for a write, mem_wdata = hwdata (Hazard3 holds hwdata while
//     hready = 0 and replicates a byte/halfword to every lane, hazard3_core.v
//     1432-1440); for a read mem_wdata = 0: hwdata is not driven for a read
//     and changes (or is X), while the native bus keeps addr/wdata/wstrb
//     stable until mem_ready (dv bus_assert caught it in the first run);
//   * hready = 0 until mem_ready; in the mem_ready cycle hready = 1 and
//     hrdata = mem_rdata (Hazard3 picks the lane and extends the sign);
//   * the next address phase may come in that same cycle (AHB pipelining);
//     soc_bus is busy in its mem_ready cycle, so it takes the next request one
//     cycle later, as with PicoRV32.
// Each access takes at least one cycle more than with PicoRV32: performance is
// not a goal of Phase 5 (ADR-0011). hresp is always OKAY: unmapped addresses
// keep their soc_bus behaviour (read 0, write ignored, spec section 4.2).
// resetn is the CPU reset of soc_top (synchronous, active low): a transfer in
// its data phase is dropped and none is taken while it is 0.
// Bug injection (dv/bugs.toml): BUG_H01 (a halfword store writes the other half
// of the word), BUG_H02 (an address phase is taken while a data phase is still
// waiting: hready ignored), BUG_H04 (mem_instr inverted: fetches look like data).
// =============================================================================
`timescale 1ns/1ps
`default_nettype none

module soc_ahb2native (
    input  wire        clk,
    input  wire        resetn,

    // AHB5 manager (Hazard3)
    input  wire [31:0] haddr,
    input  wire        hwrite,
    input  wire [1:0]  htrans,
    input  wire [2:0]  hsize,
    input  wire [3:0]  hprot,
    input  wire [31:0] hwdata,
    output wire        hready,
    output wire [31:0] hrdata,

    // native bus (soc_bus)
    output wire        mem_valid,
    output wire        mem_instr,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [3:0]  mem_wstrb,
    input  wire        mem_ready,
    input  wire [31:0] mem_rdata
);

    reg        pend;        // a transfer is in its data phase
    reg [31:0] addr_q;
    reg        write_q;
    reg [1:0]  size_q;
    reg        instr_q;

    assign hready = ~pend | mem_ready;
`ifdef BUG_H02
    wire   start  = resetn & htrans[1];
`else
    wire   start  = resetn & htrans[1] & hready;
`endif

    always @(posedge clk) begin
        if (!resetn)
            pend <= 1'b0;
        else if (start)
            pend <= 1'b1;
        else if (mem_ready)
            pend <= 1'b0;
    end

    // Datapath registers have no reset (they are used only while pend = 1).
    always @(posedge clk) begin
        if (start) begin
            addr_q  <= haddr;
            write_q <= hwrite;
            size_q  <= hsize[1:0];
`ifdef BUG_H04
            instr_q <= hprot[0];
`else
            instr_q <= ~hprot[0];
`endif
        end
    end

`ifdef BUG_H01
    // BUG_H01: a halfword store writes the other half of the word.
    wire [3:0] half = addr_q[1] ? 4'b0011 : 4'b1100;
`else
    wire [3:0] half = addr_q[1] ? 4'b1100 : 4'b0011;
`endif
    wire [3:0] strb = size_q == 2'd0 ? (4'b0001 << addr_q[1:0]) :
                      size_q == 2'd1 ? half : 4'b1111;

    assign mem_valid = pend;
    assign mem_instr = instr_q;
    assign mem_addr  = {addr_q[31:2], 2'b00};
    assign mem_wdata = write_q ? hwdata : 32'h0000_0000;
    assign mem_wstrb = write_q ? strb : 4'b0000;
    assign hrdata    = mem_rdata;

    // hsize[2] is always 0 (Hazard3 issues byte, halfword and word only);
    // htrans[0] tells NSEQ from IDLE only together with htrans[1] (Hazard3
    // never issues SEQ/BUSY); hprot[3:1] carry no information for this SoC.
    wire unused_ok = &{1'b0, hsize[2], htrans[0], hprot[3:1]};

endmodule

`default_nettype wire
