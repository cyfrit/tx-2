`timescale 1ns/1ps
`default_nettype none
module tb_alu;
    reg clk=0;always #5 clk=~clk;
    reg reset=1,start=0;
    reg [5:0] opcode;
    reg [1:0] fracture;
    reg [3:0] activity,z_in;
    reg [35:0] a_in,b_in,c_in,d_in;
    wire done;
    wire [35:0] a_out,b_out,c_out,d_out;
    wire [3:0] z_out;
    reg [35:0] ea,eb,ec,ed;
    reg [3:0] ez;
    integer fd,status,n=0,cycles;
    tx2_alu dut(.*);
    initial begin
        fd=$fopen("build/alu-vectors.hex","r");if(!fd)$fatal(1,"missing ALU vectors");
        repeat(3)@(negedge clk);reset=0;
        status=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h\n",opcode,fracture,activity,a_in,b_in,c_in,d_in,z_in,ea,eb,ec,ed,ez);
        while(status==13) begin
            start=1;@(negedge clk);start=0;cycles=0;
            while(!done && cycles<1200)begin @(negedge clk);cycles=cycles+1;end
            if(!done)$fatal(1,"ALU timeout vector %0d",n);
            if({a_out,b_out,c_out,d_out,z_out}!=={ea,eb,ec,ed,ez})
                $fatal(1,"ALU vector %0d op=%o f=%d activity=%h\n in A=%o B=%o C=%o D=%o Z=%h\n actual A=%o B=%o C=%o D=%o Z=%h\n expect A=%o B=%o C=%o D=%o Z=%h",n,opcode,fracture,activity,a_in,b_in,c_in,d_in,z_in,a_out,b_out,c_out,d_out,z_out,ea,eb,ec,ed,ez);
            n=n+1;@(negedge clk);
            status=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h\n",opcode,fracture,activity,a_in,b_in,c_in,d_in,z_in,ea,eb,ec,ed,ez);
        end
        if(n<7900)$fatal(1,"Truncated ALU vectors");
        // Vol.2 14-2.7: AOP CYA, fracture36, only Q2 active,
        // right shifts use the frozen low bit of inactive Q3 as coupling input.
        opcode=6'o60;fracture=0;activity=2;a_in=36'o000000777000;
        b_in=0;c_in=0;d_in=36'o763000000000;z_in=0;
        start=1;@(negedge clk);start=0;while(!done)@(negedge clk);
        if(a_out!==0 || d_out!==36'o777000000000)$fatal(1,"AOP unexpanded activity/coupling failed %o",a_out);
        $display("PASS: %0d ALU vectors; 14 operations, four fractures, signed zeros, overflow, 27+9 shared ASK and direct AOP activity",n);
        $finish;
    end
endmodule
`default_nettype wire
