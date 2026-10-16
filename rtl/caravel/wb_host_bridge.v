// =============================================================================
// wb_host_bridge -- Caravel Wishbone slave to the soc_top host write port
// (Phase 7, ADR-0019 decision 9).
//
// Address map (the management SoC routes 0x30xx_xxxx to the user project):
//   0x3000_0000          CTRL  bit 0 = host_en, reset value 1: after wb_rst_i the CPU is held
//                              until the management CPU clears it (then it boots from the
//                              boot ROM by boot_mode). host_en = 1 holds the CPU in reset and
//                              gives SRAM port 0 to this bridge (soc_top / soc_bus).
//   0x3000_1000-17FF     SRAM  512 words; reads and writes reach the SRAM only while
//                              host_en = 1, otherwise writes are dropped and reads return 0.
//   anything else              acknowledged, reads return 0 (no bus hang).
//
// Wishbone classic, registered ack. Every access is acknowledged exactly once:
//   write  host_cs pulses for one cycle with the ack (the SRAM samples it at the next edge)
//   read   host_cs pulses, then host_rdata is valid two edges after the SRAM samples
//          host_cs (soc_bus.v: "A read sampled at T0 ... captured into rdata_q at T1"),
//          so the data is registered at the third edge after host_cs rises, with the ack.
// Bug injection (dv/bugs.toml W01, W02, W06; negative tests of the Caravel build).
// =============================================================================
`default_nettype none

module wb_host_bridge (
    input  wire        clk,
    input  wire        rst,          // wb_rst_i, active high. Caravel asserts it asynchronously and
                                     // releases it on a falling edge of wb_clk_i (caravel_clocking.v
                                     // 101-112); used here as a synchronous reset (ADR-0019 decision 8)
    input  wire        wbs_stb_i,
    input  wire        wbs_cyc_i,
    input  wire        wbs_we_i,
    input  wire [3:0]  wbs_sel_i,
    input  wire [31:0] wbs_dat_i,
    input  wire [31:0] wbs_adr_i,
    output reg         wbs_ack_o,
    output reg  [31:0] wbs_dat_o,
    output reg         host_en,
    output reg         host_cs,
    output reg         host_we,
    output reg  [8:0]  host_addr,
    output reg  [31:0] host_wdata,
    output reg  [3:0]  host_wmask,
    input  wire [31:0] host_rdata
);
    localparam [1:0] IDLE = 2'd0, WAIT = 2'd1, ACK = 2'd2;

    wire req      = wbs_cyc_i & wbs_stb_i;
    wire sel_ctrl = wbs_adr_i == 32'h3000_0000;
    wire sel_sram = wbs_adr_i[31:11] == 21'h060002;    // 0x3000_1000-0x3000_17FF

`ifdef BUG_W02
    wire unused_bug_w02 = &{1'b0, wbs_sel_i};
`endif

    reg [1:0] state;
    reg [1:0] wait_cnt;

    always @(posedge clk) begin
        if (rst) begin
            state      <= IDLE;
            wait_cnt   <= 2'd0;
            wbs_ack_o  <= 1'b0;
            wbs_dat_o  <= 32'd0;
`ifdef BUG_W06
            host_en    <= 1'b0;          // BUG_W06: the CPU runs before the management CPU loads the SRAM
`else
            host_en    <= 1'b1;
`endif
            host_cs    <= 1'b0;
            host_we    <= 1'b0;
            host_addr  <= 9'd0;
            host_wdata <= 32'd0;
            host_wmask <= 4'd0;
        end else begin
            wbs_ack_o <= 1'b0;
            host_cs   <= 1'b0;
            case (state)
                IDLE: if (req) begin
                    if (sel_sram && host_en) begin
                        host_cs    <= 1'b1;
                        host_we    <= wbs_we_i;
                        host_addr  <= wbs_adr_i[10:2];
                        host_wdata <= wbs_dat_i;
`ifdef BUG_W02
                        host_wmask <= 4'hF;      // BUG_W02: Wishbone byte selects ignored
`else
                        host_wmask <= wbs_sel_i;
`endif
                        wait_cnt   <= 2'd0;
                        if (wbs_we_i) begin
                            wbs_ack_o <= 1'b1;
                            state     <= ACK;
                        end else begin
                            state     <= WAIT;
                        end
                    end else begin
                        if (sel_ctrl && wbs_we_i && wbs_sel_i[0])
                            host_en <= wbs_dat_i[0];
                        wbs_dat_o <= (sel_ctrl && !wbs_we_i) ? {31'd0, host_en} : 32'd0;
                        wbs_ack_o <= 1'b1;
                        state     <= ACK;
                    end
                end
                WAIT: begin
`ifdef BUG_W01
                    if (wait_cnt == 2'd1) begin  // BUG_W01: read data taken one edge early
`else
                    if (wait_cnt == 2'd2) begin
`endif
                        wbs_dat_o <= host_rdata;
                        wbs_ack_o <= 1'b1;
                        state     <= ACK;
                    end else begin
                        wait_cnt <= wait_cnt + 2'd1;
                    end
                end
                default: state <= IDLE;   // ACK: the master drops stb after seeing the ack
            endcase
        end
    end
endmodule

`default_nettype wire
