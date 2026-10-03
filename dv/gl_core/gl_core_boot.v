// Reset-address jump for `make gl-core` (second root module, iverilog -s gl_core_boot).
//
// The SoC configuration starts PicoRV32 at PROGADDR_RESET = 0x0001_0000 (the boot ROM,
// rtl/include/memmap.vh), but the upstream test firmware is linked at address 0
// (third_party/picorv32/firmware/sections.lds). After testbench.v has loaded the firmware
// ($readmemh at time 0), this module writes one instruction at the reset address of the
// testbench memory: `jal x0, <0 - PROGADDR_RESET>`, a jump to 0 that changes no register.
// The firmware then runs exactly as upstream. Same patch in the RTL and the GL run.
// Encoding checked against riscv64-elf-as: `j 0` at 0x10000 is 0x800f006f.
//
// Errors (printed with the "gl-core-boot: ERROR" prefix the checker looks for):
//   - the reset address is outside the 128 KB testbench memory or not 4-byte aligned
//   - the firmware image already has data at the reset address
`timescale 1 ns / 1 ps
`include "cpu_defines.vh"

module gl_core_boot;
	localparam [31:0] RESET_ADDR = `CPU_PROGADDR_RESET;
	localparam [31:0] OFFSET     = 32'd0 - RESET_ADDR;
	localparam [31:0] JUMP_TO_0  = {OFFSET[20], OFFSET[10:1], OFFSET[11], OFFSET[19:12], 5'd0, 7'b1101111};

	initial begin
		if (RESET_ADDR != 0) begin
			#1;
			if (RESET_ADDR >= 128*1024 || RESET_ADDR[1:0] != 2'b00) begin
				$display("gl-core-boot: ERROR reset address %08x is not a word inside the 128 KB testbench memory", RESET_ADDR);
				$finish;
			end else if (testbench.top.mem.memory[RESET_ADDR >> 2] !== 32'h0) begin
				$display("gl-core-boot: ERROR firmware image has data %08x at the reset address %08x",
				         testbench.top.mem.memory[RESET_ADDR >> 2], RESET_ADDR);
				$finish;
			end else begin
				testbench.top.mem.memory[RESET_ADDR >> 2] = JUMP_TO_0;
				$display("gl-core-boot: reset address %08x holds jal x0 to 00000000 (%08x)", RESET_ADDR, JUMP_TO_0);
			end
		end
	end
endmodule
