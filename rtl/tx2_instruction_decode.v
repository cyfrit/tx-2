`timescale 1ns/1ps
`default_nettype none
// TX-2 Users Handbook, section 6-2.1, printed page 6-4.
// RTL uses zero-based bit numbers. The handbook numbers quarters Q1..Q4.
// This splits the word only; it does not execute or validate the opcode.
module tx2_instruction_decode (
    input  wire [35:0] instruction,
    output wire        hold,
    output wire [4:0]  configuration,
    output wire [5:0]  opcode,
    output wire [5:0]  index,
    output wire        defer,
    output wire [16:0] address
);
    assign hold          = instruction[35];
    assign configuration = instruction[34:30];
    assign opcode        = instruction[29:24];
    assign index         = instruction[23:18];
    assign defer         = instruction[17];
    assign address       = instruction[16:0];
endmodule
`default_nettype wire
