`timescale 1ns/1ps
`default_nettype none
// Replay the same architectural trace with a separate memory responder.
// Request must remain stable for every inserted wait cycle. This catches
// premature writes, duplicate transactions and accidental fixed-latency use.
module tb_core_wait;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1, start=0;
    reg [16:0] start_address=17'o100;
    wire unused_data_write_enable,unused_meta_write_enable,unused_meta_write_value,unused_read_set_meta;
    wire [9:0] unused_alarms;
    wire unused_device_preset;
    wire running;
    wire [3:0] fault;
    wire memory_request, memory_write;
    wire [16:0] memory_address;
    wire [35:0] memory_write_data;
    reg memory_ready=0;
    reg [35:0] memory_read_data=0;
    reg [1:0] memory_error=0;
    wire retire;
    wire [16:0] retire_address, program_counter, operand_address;
    wire [35:0] retire_instruction,a,b,c,d,e;
    wire [5:0] debug_index_address=retire_instruction[23:18];
    wire [4:0] debug_configuration_address=retire_instruction[34:30];
    wire [17:0] debug_index_data;
    wire [8:0] debug_configuration_data;
    reg [35:0] ram [0:131071];
    reg pending=0, saved_write=0;
    reg [16:0] saved_address=0;
    reg [35:0] saved_data=0;
    reg [15:0] lfsr=16'hace1;
    integer delay_count=0, transactions=0, wait_cycles=0;
    integer fd, trace_fd, status, count, cycles;
    reg [16:0] image_address;
    reg [35:0] image_data;
    reg [1023:0] header;
    reg [293:0] expected;
    wire [293:0] actual={retire_address,retire_instruction,program_counter,operand_address,
                        a,b,c,d,e,debug_index_data,debug_configuration_data};
    tx2_core #(.EXTENDED(0)) dut (.*,
        .memory_read_meta(1'b0),.memory_read_parity(1'b0),.memory_parity_error(1'b0),
        .memory_data_write_enable(unused_data_write_enable),.memory_meta_write_enable(unused_meta_write_enable),
        .memory_meta_write_value(unused_meta_write_value),.memory_read_set_meta(unused_read_set_meta),
        .trap_mode(9'b0),.trap_set_enable(1'b0),.sync_trap(1'b0),.alarm_suppress(10'b0),
        .clear_alarms(1'b0),.io_control_error(1'b0),.io_missed_alarm(1'b0),.io_missed_suppress(1'b0),.alarms(unused_alarms),.device_preset(unused_device_preset),
        .console_stop(1'b0),.console_continue(1'b0),.console_preset(1'b0),.console_startover(1'b0),
        .console_reset_start(1'b0),.console_hold(1'b0),.io_software_unit(1'b0), .overflow_flags(), .priority_map(384'b0), .io_flag_raise(64'b0),
        .sequence_flags(), .current_sequence(), .retire_sequence(), .limbo(),
        .io_control_valid(), .io_control_unit(), .io_control_command(), .io_report(36'b0),
        .io_transfer_valid(), .io_transfer_unit(), .io_transfer_data(),
        .io_transfer_ready(1'b0), .io_transfer_input(1'b0), .io_transfer_assembly(1'b0),
        .io_transfer_assembly_width(4'd6),
        .io_transfer_reverse(1'b0), .io_input_data(36'b0), .io_input_mask(36'b0));
    always @(posedge clk) begin
        if (reset) begin
            pending<=0; memory_ready<=0; memory_error<=0;
            transactions<=0; wait_cycles<=0; lfsr<=16'hace1;
        end else begin
            memory_ready<=0;
            if (pending) begin
                if (!memory_request || {memory_write,memory_address,memory_write_data} !==
                                      {saved_write,saved_address,saved_data})
                    $fatal(1,"Memory request changed before response");
                if (delay_count==0) begin
                    if (saved_write) ram[saved_address]<=saved_data;
                    memory_read_data<=ram[saved_address];
                    memory_ready<=1; pending<=0;
                end else begin delay_count<=delay_count-1; wait_cycles<=wait_cycles+1; end
            end else if (!memory_ready && memory_request) begin
                pending<=1;
                saved_write<=memory_write; saved_address<=memory_address; saved_data<=memory_write_data;
                delay_count<={29'b0,lfsr[2:0]};
                lfsr<={lfsr[14:0],lfsr[15]^lfsr[13]^lfsr[12]^lfsr[10]};
                transactions<=transactions+1;
            end
        end
    end
    initial begin
        fd=$fopen("programs/configured-copy.hex","r");
        if (!fd) $fatal(1,"Missing image");
        repeat(3) status=$fgets(header,fd);
        status=$fscanf(fd,"%h %h\n",image_address,image_data);
        while (status==2) begin
            ram[image_address]=image_data;
            status=$fscanf(fd,"%h %h\n",image_address,image_data);
        end
        $fclose(fd);
        trace_fd=$fopen("build/demo.trace.hex","r");
        if (!trace_fd) $fatal(1,"Missing reference trace");
        repeat(3) @(negedge clk);
        reset=0; start=1;
        @(negedge clk); start=0;
        count=0; cycles=0;
        while (fault==0 && cycles<10000) begin
            @(negedge clk); cycles=cycles+1;
            if (retire) begin
                status=$fscanf(trace_fd,"%h\n",expected);
                if (status!=1 || actual!==expected)
                    $fatal(1,"Wait-state trace mismatch at PC %o retirement %0d",retire_address,count);
                count=count+1;
            end
        end
        if (fault!==1 || count!=52 || wait_cycles<100)
            $fatal(1,"Wait-state replay incomplete");
        $fclose(trace_fd);
        $display("PASS: %0d retirements across %0d memory transactions and %0d inserted wait cycles",
                 count,transactions,wait_cycles);
        $finish;
    end
endmodule
`default_nettype wire
