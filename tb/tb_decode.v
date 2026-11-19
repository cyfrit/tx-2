`timescale 1ns/1ps
`default_nettype none
module tb_decode;
    reg [35:0] instruction;
    wire hold, defer;
    wire [4:0] configuration;
    wire [5:0] opcode, index;
    wire [16:0] address;
    reg [8:0] configuration_word;
    wire [1:0] fracture;
    wire [3:0] active_quarters;
    wire [2:0] permutation;
    integer checks;

    tx2_instruction_decode instruction_dut (
        .instruction(instruction), .hold(hold), .configuration(configuration),
        .opcode(opcode), .index(index), .defer(defer), .address(address)
    );
    tx2_configuration_decode configuration_dut (
        .configuration_word(configuration_word), .fracture(fracture),
        .active_quarters(active_quarters), .permutation(permutation)
    );

    task check_instruction;
        input [35:0] word_value;
        input expected_hold;
        input [4:0] expected_configuration;
        input [5:0] expected_opcode, expected_index;
        input expected_defer;
        input [16:0] expected_address;
        begin
            instruction = word_value;
            #1;
            if ({hold,configuration,opcode,index,defer,address} !==
                {expected_hold,expected_configuration,expected_opcode,
                 expected_index,expected_defer,expected_address})
                $fatal(1,"Instruction decode mismatch for %012o",word_value);
            checks = checks + 1;
        end
    endtask

    task check_configuration;
        input [8:0] word_value;
        input [1:0] expected_fracture;
        input [3:0] expected_activity;
        input [2:0] expected_permutation;
        begin
            configuration_word = word_value;
            #1;
            if ({fracture,active_quarters,permutation} !==
                {expected_fracture,expected_activity,expected_permutation})
                $fatal(1,"Configuration decode mismatch for %03o",word_value);
            checks = checks + 1;
        end
    endtask

    initial begin
        checks = 0;
        instruction = 0;
        configuration_word = 0;
        // Handbook section 5-5.2: independently stated octal boot words.
        check_instruction(36'o011254_000023,0,5'o01,6'o12,6'o54,0,17'o000023);
        check_instruction(36'o001252_377763,0,5'o00,6'o12,6'o52,0,17'o377763);
        check_instruction(36'o210452_030106,0,5'o21,6'o04,6'o52,0,17'o030106);
        check_instruction(36'o405754_000026,1,5'o00,6'o57,6'o54,0,17'o000026);
        check_instruction(36'o760653_377764,1,5'o36,6'o06,6'o53,0,17'o377764);
        check_instruction(36'o301712_377744,0,5'o30,6'o17,6'o12,0,17'o377744);
        // Boundary cases ensure that defer is not part of the 17-bit address.
        check_instruction(36'o000000_400000,0,0,0,0,1,0);
        check_instruction(36'o777777_777777,1,5'o37,6'o77,6'o77,1,17'o377777);
        check_instruction(36'o000000_000000,0,0,0,0,0,0);
        // Standard F-memory values: Handbook table 7-2, cross-checked with
        // upstream cpu/src/exchanger.rs test_system_configuration_standard_config.
        check_configuration(9'o000,2'b00,4'b1111,3'd0);
        check_configuration(9'o340,2'b01,4'b0011,3'd0);
        check_configuration(9'o342,2'b01,4'b0011,3'd2);
        check_configuration(9'o760,2'b11,4'b0001,3'd0);
        check_configuration(9'o763,2'b11,4'b0001,3'd3);
        check_configuration(9'o410,2'b10,4'b1110,3'd0);
        check_configuration(9'o140,2'b00,4'b0011,3'd0);
        check_configuration(9'o202,2'b01,4'b1111,3'd2);
        // Synthetic all-inactive cases are valid field encodings too.
        check_configuration(9'o170,2'b00,4'b0000,3'd0);
        check_configuration(9'o777,2'b11,4'b0000,3'd7);
        $display("PASS: %0d decode checks",checks);
        $finish;
    end
endmodule
`default_nettype wire
