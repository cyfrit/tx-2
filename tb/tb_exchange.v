`timescale 1ns/1ps
`default_nettype none
module tb_exchange;
    reg [35:0] source_word, destination_word;
    reg [8:0] configuration_word;
    reg store_direction, sign_extension;
    wire [35:0] result_word;
    wire [3:0] extended_activity;
    reg [122:0] vector;
    integer file_handle, status, count;
    tx2_exchange dut (.*);
    initial begin
        file_handle = $fopen("build/exchange-vectors.hex","r");
        if (!file_handle) $fatal(1,"Missing exchange vectors");
        count = 0;
        status = $fscanf(file_handle,"%h\n",vector);
        while (status == 1) begin
            {configuration_word,store_direction,sign_extension,source_word,destination_word} = vector[122:40];
            #1;
            if ({result_word,extended_activity} !== vector[39:0])
                $fatal(1,"Exchange mismatch cfg=%o store=%b sign=%b src=%o dst=%o got=%o expected=%o",
                    configuration_word,store_direction,sign_extension,source_word,destination_word,
                    result_word,vector[39:4]);
            count = count + 1;
            status = $fscanf(file_handle,"%h\n",vector);
        end
        $fclose(file_handle);
        if (count != 65536) $fatal(1,"Incomplete exchange coverage: %0d",count);
        $display("PASS: %0d exchange vectors, all 512 configurations in both directions",count);
        $finish;
    end
endmodule
`default_nettype wire
