`timescale 1ns/1ps
`default_nettype none
// TX-2 Technical Manual vol. 2, section 12-6, printed page 12-22.
// Input is a 9-bit F-memory VALUE, not the instruction's 5-bit F address.
// CF9..CF1 map to configuration_word[8:0]. Activity is active-low in F.
// Fracture: 00=36, 01=18+18, 10=27+9, 11=9+9+9+9.
// This does not perform permutation, sign extension or arithmetic.
module tx2_configuration_decode (
    input  wire [8:0] configuration_word,
    output wire [1:0] fracture,
    output wire [3:0] active_quarters,
    output wire [2:0] permutation
);
    assign fracture        = configuration_word[8:7];
    assign active_quarters = ~configuration_word[6:3]; // bit 0 = Q1
    assign permutation     = configuration_word[2:0];
endmodule
`default_nettype wire
