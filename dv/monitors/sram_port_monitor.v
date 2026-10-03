// sram_port_monitor.v - SRAM port 0 protocol checker (checker name: sram_port).
// Contract: docs/spec/soc_spec.md sections 4.3 (SRAM port 0 timing), 4.4 (host
// port) and 4.9 (reset).
//
// Sampled on the rising clock edge, like the SRAM model itself: the values read
// here are the pre-edge values of sram0.csb0/web0/wmask0/addr0/din0, i.e. the
// values the macro captures at this edge. "Edge k" of a CPU transaction is the
// k-th rising edge at which mem_valid=1 was sampled (k = 0 is T0).
//
// Rules while host_en=1 (host owns port 0, spec 4.4):
//   - csb0 = ~host_cs; with host_cs=1: web0 = ~host_we, addr0 = host_addr and,
//     for a write, wmask0 = host_wmask and din0 = host_wdata.
// Rules while host_en=0 (CPU path, spec 4.3, 4.9):
//   - no SRAM access (csb0=0) at an edge that samples resetn=0 (RTL-RST-01:
//     a store presented there is dropped)
//   - no SRAM access without a CPU transaction or during a transaction outside
//     the SRAM window
//   - exactly one SRAM access per SRAM transaction, at edge 0 (T0)
//   - at that access: addr0 = mem_addr[10:2], web0 = (mem_wstrb == 0) and, for
//     a write, wmask0 = mem_wstrb and din0 = mem_wdata
//   - handshake (mem_valid & mem_ready sampled) at edge 2 for a read (T2) and
//     at edge 1 for a write (T1)
//   - csb0 never X/Z after reset release
// Each rule is reported at most once per transaction.
`timescale 1ns/1ps
`default_nettype none
`include "memmap.vh"

module sram_port_monitor #(
    parameter integer MAX_MSGS = 20
) (
    input  wire        clk,
    input  wire        active,      // 1 after the first reset release
    input  wire [31:0] cycle,
    input  wire        resetn,
    input  wire        host_en,
    input  wire        host_cs,
    input  wire        host_we,
    input  wire [8:0]  host_addr,
    input  wire [31:0] host_wdata,
    input  wire [3:0]  host_wmask,
    input  wire        mem_valid,
    input  wire        mem_ready,
    input  wire [31:0] mem_addr,
    input  wire [31:0] mem_wdata,
    input  wire [3:0]  mem_wstrb,
    input  wire        csb0,
    input  wire        web0,
    input  wire [3:0]  wmask0,
    input  wire [8:0]  addr0,
    input  wire [31:0] din0,
    output reg  [31:0] fail_count,
    output reg  [31:0] access_count    // CPU-path SRAM accesses (csb0=0, host_en=0)
);
    localparam [31:0] SRAM_BASE = `SOC_SRAM_BASE;
    localparam [31:0] SRAM_SIZE = `SOC_SRAM_SIZE;

    reg        in_txn;
    reg [31:0] k;           // edge index inside the current CPU transaction
    reg [31:0] acc;         // SRAM accesses seen in the current transaction
    reg        t_rep;       // a rule already failed in this transaction
    reg        t_sram;
    reg [31:0] off;
    reg        x_rep;

    initial begin
        fail_count   = 32'd0;
        access_count = 32'd0;
        in_txn       = 1'b0;
        k            = 32'd0;
        acc          = 32'd0;
        t_rep        = 1'b0;
        t_sram       = 1'b0;
        off          = 32'd0;
        x_rep        = 1'b0;
    end

    task note_fail;
        begin
            fail_count = fail_count + 32'd1;
            if (fail_count == MAX_MSGS + 1)
                $display("[CHK:sram_port] FAIL more than %0d sram_port failures, further messages suppressed", MAX_MSGS);
        end
    endtask

    always @(posedge clk) begin
        if (active !== 1'b1) begin
            in_txn = 1'b0;
            x_rep  = 1'b0;
        end else if (host_en === 1'b1) begin
            in_txn = 1'b0;
            if (csb0 !== ~host_cs) begin
                note_fail;
                if (fail_count <= MAX_MSGS)
                    $display("[CHK:sram_port] FAIL host port: csb0=%b with host_cs=%b (cycle %0d)", csb0, host_cs, cycle);
            end else if (host_cs === 1'b1) begin
                if (web0 !== ~host_we || addr0 !== host_addr ||
                    (host_we === 1'b1 && (wmask0 !== host_wmask || din0 !== host_wdata))) begin
                    note_fail;
                    if (fail_count <= MAX_MSGS)
                        $display("[CHK:sram_port] FAIL host port: web0/addr0/wmask0/din0=%b/%0d/%b/0x%08x, expected %b/%0d/%b/0x%08x from host_we/host_addr/host_wmask/host_wdata (cycle %0d)",
                                 web0, addr0, wmask0, din0, ~host_we, host_addr, host_wmask, host_wdata, cycle);
                end
            end
        end else begin
            // ---- CPU transaction bookkeeping (pre-edge values) ----
            if (mem_valid === 1'b1) begin
                if (!in_txn) begin
                    in_txn = 1'b1;
                    k      = 32'd0;
                    acc    = 32'd0;
                    t_rep  = 1'b0;
                    off    = mem_addr - SRAM_BASE;
                    t_sram = (off < SRAM_SIZE);
                end else begin
                    k = k + 32'd1;
                end
            end else begin
                in_txn = 1'b0;
            end

            // ---- SRAM access at this edge ----
            if (csb0 !== 1'b0 && csb0 !== 1'b1) begin
                if (!x_rep && resetn === 1'b1) begin
                    x_rep = 1'b1;
                    note_fail;
                    if (fail_count <= MAX_MSGS)
                        $display("[CHK:sram_port] FAIL csb0 is X/Z at a rising edge (cycle %0d)", cycle);
                end
            end else begin
                x_rep = 1'b0;
            end
            if (csb0 === 1'b0) begin
                access_count = access_count + 32'd1;
                if (resetn !== 1'b1) begin
                    note_fail;
                    if (fail_count <= MAX_MSGS)
                        $display("[CHK:sram_port] FAIL SRAM access at a rising edge that samples resetn=0: web0=%b addr0=%0d (byte 0x%03x) din0=0x%08x wmask0=%b; spec 4.9: a store presented at the reset edge is dropped (cycle %0d)",
                                 web0, addr0, {addr0, 2'b00}, din0, wmask0, cycle);
                end else if (!in_txn) begin
                    note_fail;
                    if (fail_count <= MAX_MSGS)
                        $display("[CHK:sram_port] FAIL SRAM access without a CPU transaction: web0=%b addr0=%0d (cycle %0d)", web0, addr0, cycle);
                end else if (!t_sram) begin
                    if (!t_rep) begin
                        t_rep = 1'b1;
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:sram_port] FAIL SRAM access during a transaction outside the SRAM window: mem_addr 0x%08x, web0=%b addr0=%0d (cycle %0d)", mem_addr, web0, addr0, cycle);
                    end
                end else begin
                    acc = acc + 32'd1;
                    if (acc > 32'd1 || k != 32'd0) begin
                        if (!t_rep) begin
                            t_rep = 1'b1;
                            note_fail;
                            if (fail_count <= MAX_MSGS)
                                $display("[CHK:sram_port] FAIL SRAM access #%0d of one transaction at edge T%0d (addr 0x%08x %0s): spec 4.3 allows csb0=0 only once, before T0 (cycle %0d)",
                                         acc, k, mem_addr, (mem_wstrb != 4'd0) ? "write" : "read", cycle);
                        end
                    end else if (addr0 !== mem_addr[10:2] || web0 !== (mem_wstrb == 4'd0) ||
                                 (mem_wstrb != 4'd0 && (wmask0 !== mem_wstrb || din0 !== mem_wdata))) begin
                        if (!t_rep) begin
                            t_rep = 1'b1;
                            note_fail;
                            if (fail_count <= MAX_MSGS)
                                $display("[CHK:sram_port] FAIL SRAM port values: addr0/web0/wmask0/din0=%0d/%b/%b/0x%08x for CPU %0s addr 0x%08x wstrb %b wdata 0x%08x (cycle %0d)",
                                         addr0, web0, wmask0, din0, (mem_wstrb != 4'd0) ? "write" : "read",
                                         mem_addr, mem_wstrb, mem_wdata, cycle);
                        end
                    end
                end
            end

            // ---- handshake at this edge ----
            if (in_txn && mem_ready === 1'b1) begin
                if (t_sram && !t_rep) begin
                    if (acc == 32'd0) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:sram_port] FAIL SRAM %0s at addr 0x%08x completed without an SRAM access (cycle %0d)",
                                     (mem_wstrb != 4'd0) ? "write" : "read", mem_addr, cycle);
                    end else if (k != ((mem_wstrb != 4'd0) ? 32'd1 : 32'd2)) begin
                        note_fail;
                        if (fail_count <= MAX_MSGS)
                            $display("[CHK:sram_port] FAIL SRAM %0s at addr 0x%08x: handshake at T%0d, spec 4.3 table: %0s (cycle %0d)",
                                     (mem_wstrb != 4'd0) ? "write" : "read", mem_addr, k,
                                     (mem_wstrb != 4'd0) ? "T1 for a write" : "T2 for a read", cycle);
                    end
                end
                in_txn = 1'b0;
            end
            // An edge that samples resetn=0 ends any CPU transaction (the CPU is reset).
            if (resetn !== 1'b1)
                in_txn = 1'b0;
        end
    end
endmodule

`default_nettype wire
