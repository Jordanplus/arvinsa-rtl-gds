// -----------------------------------------------------------------------------
// bootrom.v - GENERATED FILE, DO NOT EDIT.
// Generator : rtl/bootrom/gen_bootrom.py
// Source    : fw/bootrom/bootrom.S (118 of 128 words used)
// Image hash: sha256 f08b583bdb001d20a4306744861eca1fa75574981ef78c1cccca5139ea651f1a (little-endian bytes)
// Regenerate: make -C fw bootrom      Staleness check: make -C fw check-bootrom
// Interface : docs/spec/soc_spec.md section 4.6. Combinational case-ROM; the bus
//             registers rdata. Unused words return 32'h0000_006F (jal x0, 0).
// -----------------------------------------------------------------------------
module bootrom (
    input  wire [6:0]  addr,    // word address = mem_addr[8:2]
    output reg  [31:0] rdata
);
    always @(*) begin
        case (addr)
            7'd0  : rdata = 32'h0200_0937;
            7'd1  : rdata = 32'h0120_0293;
            7'd2  : rdata = 32'h0059_2023;
            7'd3  : rdata = 32'h0300_09B7;
            7'd4  : rdata = 32'h0049_A403;
            7'd5  : rdata = 32'h0034_7413;
            7'd6  : rdata = 32'h0B04_6293;
            7'd7  : rdata = 32'h0059_A023;
            7'd8  : rdata = 32'h0400_0A37;
            7'd9  : rdata = 32'h0010_0293;
            7'd10 : rdata = 32'h0054_0A63;
            7'd11 : rdata = 32'h0020_0293;
            7'd12 : rdata = 32'h1054_0463;
            7'd13 : rdata = 32'h0000_0293;
            7'd14 : rdata = 32'h0002_8067;
            7'd15 : rdata = 32'h0000_0A93;
            7'd16 : rdata = 32'h0000_1B37;
            7'd17 : rdata = 32'h800B_0B13;
            7'd18 : rdata = 32'h0000_0613;
            7'd19 : rdata = 32'h0800_00EF;
            7'd20 : rdata = 32'h0000_0513;
            7'd21 : rdata = 32'hFFF0_0593;
            7'd22 : rdata = 32'h0A80_00EF;
            7'd23 : rdata = 32'hFFF0_0513;
            7'd24 : rdata = 32'h0000_0593;
            7'd25 : rdata = 32'h09C0_00EF;
            7'd26 : rdata = 32'h0000_0513;
            7'd27 : rdata = 32'hFFF0_0593;
            7'd28 : rdata = 32'h0AC0_00EF;
            7'd29 : rdata = 32'hFFF0_0513;
            7'd30 : rdata = 32'h0000_0593;
            7'd31 : rdata = 32'h0A00_00EF;
            7'd32 : rdata = 32'h0640_00EF;
            7'd33 : rdata = 32'hFFF0_0613;
            7'd34 : rdata = 32'h0440_00EF;
            7'd35 : rdata = 32'h0580_00EF;
            7'd36 : rdata = 32'h0A50_0293;
            7'd37 : rdata = 32'h0059_A023;
            7'd38 : rdata = 32'h4D41_52B7;
            7'd39 : rdata = 32'h2432_8293;
            7'd40 : rdata = 32'h005A_2023;
            7'd41 : rdata = 32'h600D_C2B7;
            7'd42 : rdata = 32'h0DE2_8293;
            7'd43 : rdata = 32'h005A_2223;
            7'd44 : rdata = 32'h0180_006F;
            7'd45 : rdata = 32'h0E10_0293;
            7'd46 : rdata = 32'h0059_A023;
            7'd47 : rdata = 32'hBAD0_12B7;
            7'd48 : rdata = 32'hE102_8293;
            7'd49 : rdata = 32'h005A_2223;
            7'd51 : rdata = 32'h000A_8293;
            7'd52 : rdata = 32'h00C2_F3B3;
            7'd53 : rdata = 32'h0072_A023;
            7'd54 : rdata = 32'h0042_8293;
            7'd55 : rdata = 32'hFF62_9AE3;
            7'd56 : rdata = 32'h0000_8067;
            7'd57 : rdata = 32'h000A_8293;
            7'd58 : rdata = 32'h0002_A303;
            7'd59 : rdata = 32'h00C2_F3B3;
            7'd60 : rdata = 32'hFC73_12E3;
            7'd61 : rdata = 32'h0042_8293;
            7'd62 : rdata = 32'hFF62_98E3;
            7'd63 : rdata = 32'h0000_8067;
            7'd64 : rdata = 32'h000A_8293;
            7'd65 : rdata = 32'h0002_A303;
            7'd66 : rdata = 32'hFAA3_16E3;
            7'd67 : rdata = 32'h00B2_A023;
            7'd68 : rdata = 32'h0042_8293;
            7'd69 : rdata = 32'hFF62_98E3;
            7'd70 : rdata = 32'h0000_8067;
            7'd71 : rdata = 32'h000B_0293;
            7'd72 : rdata = 32'hFFC2_8293;
            7'd73 : rdata = 32'h0002_A303;
            7'd74 : rdata = 32'hF8A3_16E3;
            7'd75 : rdata = 32'h00B2_A023;
            7'd76 : rdata = 32'hFF52_98E3;
            7'd77 : rdata = 32'h0000_8067;
            7'd78 : rdata = 32'hFFF0_0493;
            7'd79 : rdata = 32'h0900_00EF;
            7'd80 : rdata = 32'h0005_0B93;
            7'd81 : rdata = 32'h0880_00EF;
            7'd82 : rdata = 32'h0085_1513;
            7'd83 : rdata = 32'h00AB_EBB3;
            7'd84 : rdata = 32'h060B_8263;
            7'd85 : rdata = 32'h1C00_0293;
            7'd86 : rdata = 32'h0572_EE63;
            7'd87 : rdata = 32'h0000_0C13;
            7'd88 : rdata = 32'h0000_0D93;
            7'd89 : rdata = 32'h0000_0C93;
            7'd90 : rdata = 32'h002B_9D13;
            7'd91 : rdata = 32'h019D_0D33;
            7'd92 : rdata = 32'h0040_0393;
            7'd93 : rdata = 32'h0580_00EF;
            7'd94 : rdata = 32'h00AC_0C33;
            7'd95 : rdata = 32'h008D_DD93;
            7'd96 : rdata = 32'h0185_1513;
            7'd97 : rdata = 32'h00AD_EDB3;
            7'd98 : rdata = 32'hFFF3_8393;
            7'd99 : rdata = 32'hFE03_94E3;
            7'd100: rdata = 32'h01BC_A023;
            7'd101: rdata = 32'h004C_8C93;
            7'd102: rdata = 32'hFDAC_9CE3;
            7'd103: rdata = 32'h0300_00EF;
            7'd104: rdata = 32'h0FFC_7C13;
            7'd105: rdata = 32'h0185_1863;
            7'd106: rdata = 32'h0B80_0293;
            7'd107: rdata = 32'h0059_A023;
            7'd108: rdata = 32'hE85F_F06F;
            7'd109: rdata = 32'h0EE0_0293;
            7'd110: rdata = 32'h0059_A023;
            7'd111: rdata = 32'hBAD0_12B7;
            7'd112: rdata = 32'hB002_8293;
            7'd113: rdata = 32'h005A_2223;
            7'd114: rdata = 32'hF01F_F06F;
            7'd115: rdata = 32'h0049_2503;
            7'd116: rdata = 32'hFE95_0EE3;
            7'd117: rdata = 32'h0000_8067;
            default: rdata = 32'h0000_006F;
        endcase
    end
endmodule
