// PLACEHOLDER — will be overwritten by rtl/bootrom/gen_bootrom.py (owned by fw/).
// Interface is fixed by docs/spec/soc_spec.md §4.6. Every word is `jal x0, 0` (spin).
module bootrom (
    input  wire [6:0]  addr,   // word address within the ROM window
    output reg  [31:0] rdata
);
    always @(*) begin
        case (addr)
            default: rdata = 32'h0000_006F;
        endcase
    end
endmodule
