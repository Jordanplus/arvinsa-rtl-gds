// =============================================================================
// dv/core_hazard3/rvfi_trace.sv -- retirement trace of the Hazard3 core for the comparison
// with the rvcpp ISS (Phase 5, ADR-0011 user decision 3; dv/core_hazard3/compare_trace.py).
// Bound into the upstream testbench (third_party/hazard3/test/sim/tb_common/hdl/tb.v, not
// modified) with the bind below; the core is built with HAZARD3_RVFI_STANDALONE so that
// hazard3_cpu_2port has the RVFI outputs (hazard3_rvfi_standalone_defs.vh).
// One line per retired instruction (rvfi_valid): pc insn trap intr rd rd_wdata (hex/decimal),
// written to rvfi_trace.txt in the working directory and flushed per line (the C++ testbench
// may exit without a final block).
// =============================================================================
module rvfi_trace (
    input wire        clk,
    input wire        valid,
    input wire [31:0] pc,
    input wire [31:0] insn,
    input wire        trap,
    input wire        intr,
    input wire [4:0]  rd,
    input wire [31:0] rd_wdata
);
    integer fd;
    initial fd = $fopen("rvfi_trace.txt", "w");
    always @(posedge clk) begin
        if (valid) begin
            $fwrite(fd, "%08x %08x %0d %0d %0d %08x\n", pc, insn, trap, intr, rd, rd_wdata);
            $fflush(fd);
        end
    end
endmodule

bind tb rvfi_trace u_rvfi_trace (
    .clk      (clk),
    .valid    (cpu.rvfi_valid),
    .pc       (cpu.rvfi_pc_rdata),
    .insn     (cpu.rvfi_insn),
    .trap     (cpu.rvfi_trap),
    .intr     (cpu.rvfi_intr),
    .rd       (cpu.rvfi_rd_addr),
    .rd_wdata (cpu.rvfi_rd_wdata)
);
