`timescale 1ns/1ps
`default_nettype none
module tb_sequence_selector;
    reg [63:0] flags;
    reg [383:0] priority_map;
    wire valid;
    wire [5:0] selected,selected_priority;
    reg expected_valid;
    reg [5:0] expected,rank;
    reg [31:0] random_state=32'h19635458;
    integer n,j;
    tx2_sequence_selector dut(.*);
    function [31:0] advance;
        input [31:0] value;
        begin advance={value[30:0],value[31]^value[21]^value[1]^value[0]};end
    endfunction
    initial begin
        for(n=0;n<6000;n=n+1)begin
            random_state=advance(random_state);flags[31:0]=random_state;
            random_state=advance(random_state);flags[63:32]=random_state;
            if(n%5==0)flags[0]=0;
            if(n%11==0)flags=64'h00000000fffffffe;
            for(j=0;j<64;j=j+1)begin random_state=advance(random_state);priority_map[j*6 +: 6]=random_state[5:0];end
            expected_valid=0;expected=0;rank=63;
            for(j=0;j<64;j=j+1)
                if((j==0 || j>=32) && flags[j] &&
                   (!expected_valid || j==0 || (expected!=0 && priority_map[j*6 +: 6]<rank)))begin
                    expected_valid=1;expected=j[5:0];rank=priority_map[j*6 +: 6];
                end
            if(expected_valid && expected==0)rank=0;
            #1;
            if(valid!==expected_valid || (valid && (selected!==expected || selected_priority!==rank)))
                $fatal(1,"priority selection %0d selected=%o expected=%o",n,selected,expected);
        end
        $display("PASS: 6000 priority patches/flag sets; valid sequences, rank ties and unconditional priority zero");
        $finish;
    end
endmodule
`default_nettype wire
