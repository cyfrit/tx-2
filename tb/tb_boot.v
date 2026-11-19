`timescale 1ns/1ps
`default_nettype none
module tb_boot;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1,start=0;
    reg [16:0] start_address=17'o377750;
    wire running;
    wire [3:0] fault;
    wire host_ready;
    wire [35:0] host_read_data;
    wire [1:0] host_error;
    wire retire,limbo;
    wire [16:0] retire_address,program_counter,operand_address;
    wire [35:0] retire_instruction,a,b,c,d,e;
    wire [5:0] retire_sequence,current_sequence;
    wire [63:0] sequence_flags;
    wire [17:0] debug_index_data;
    wire [8:0] debug_configuration_data;
    reg [5:0] paper [0:4095];
    reg [5:0] expected [0:12];
    integer paper_count=0,paper_position=0,cycles=0,printed=0,retired=0,rewinds=0;
    integer file_handle,status,log_file,i;
    reg [7:0] line_data;
    // Physical feed cadence is independent of buffer fullness; see TM2 15-PETR-3.
    wire tape_valid=tape_ready && paper_position<paper_count && cycles%128==0;
    wire [5:0] tape_data=paper[paper_position];
    wire tape_ready,tape_rewind,writer_valid;
    wire [5:0] writer_data;
    wire writer_ready=cycles%11<4;
    wire external_valid;
    wire [5:0] external_unit;
    wire [35:0] external_write_data;
    tx2_machine dut (
        .clk(clk),.reset(reset),.start(start),
        .console_stop(1'b0),.console_continue(1'b0),.console_preset(1'b0),.console_startover(1'b0),
        .console_reset_start(1'b0),.console_hold(1'b0),.alarm_suppress(10'b0),.clear_alarms(1'b0),
        .trap_set_enable(1'b0),.sync_trap(1'b0),.alarms(),.overflow_flags(),
        .sync_trap_mode(1'b0),.timer_fast(1'b1),.timer_manual_start(1'b0),.timer_manual_stop(1'b0),
        .timer_manual_load(1'b0),.timer_manual_interval(18'b0),.timer_end_carry(),.tape_manual_disconnect(1'b0),
        .camera_manual_index(1'b0),
        .scope_ready(2'b11),
        .pen_lit(),.pen_x(),.pen_y(),.external_clear_alarms(64'b0),.external_maintenance(64'b0),
        .external_special(15'b0),.external_assembly_width(4'd6),
        .tick_1us(1'b0),.tick_10us(1'b0),.timer_tick(1'b0),.clock_clear(1'b0),
        .knob_data(36'b0),.external_register_data(36'b0),.knob_meta(1'b0),.external_register_meta(1'b0),
        .console_switches(288'b0),.panel_data(576'b0),.panel_meta(16'b0),.host_meta_write(1'b0),.host_meta_value(1'b0),.host_read_meta(),.host_read_parity(),
        .light_pen_hit(1'b0),.camera_done(1'b0),.camera_alarm(1'b0),.display_ready(1'b1),
        .display_word(),.display_valid(),.display_unit(),.display_x(),.display_y(),.display_intensity(),.camera_request(),
        .external_assembly(64'b0),.external_reverse(64'b0),
        .external_control_valid(),.external_control_unit(),.external_control_command(),.external_present(64'b0),.external_missed(64'b0),.external_inability(64'b0),.start_address(start_address),.running(running),.fault(fault),
        .host_request(1'b0),.host_write(1'b0),.host_address(17'b0),.host_write_data(36'b0),
        .host_ready(host_ready),.host_read_data(host_read_data),.host_error(host_error),
        .retire(retire),.retire_address(retire_address),.retire_instruction(retire_instruction),
        .retire_sequence(retire_sequence),.current_sequence(current_sequence),.sequence_flags(sequence_flags),
        .limbo(limbo),.program_counter(program_counter),.operand_address(operand_address),
        .a(a),.b(b),.c(c),.d(d),.e(e),.debug_index_address(6'o56),.debug_index_data(debug_index_data),
        .debug_configuration_address(5'b0),.debug_configuration_data(debug_configuration_data),
        .tape_valid(tape_valid),.tape_data(tape_data),.tape_ready(tape_ready),.tape_rewind(tape_rewind),
        .writer_valid(writer_valid),.writer_data(writer_data),.writer_ready(writer_ready),
        .external_ready(64'b0),.external_input(64'b0),.external_data(36'b0),.external_mask(36'b0),
        .external_valid(external_valid),.external_unit(external_unit),.external_write_data(external_write_data)
    );
    always @(posedge clk) begin
        if(!reset) begin
            cycles<=cycles+1;
            if(tape_rewind) begin paper_position<=0; rewinds<=rewinds+1; end
            else if(tape_valid && tape_ready) paper_position<=paper_position+1;
            if(writer_valid && writer_ready) begin
                if(writer_data!==expected[printed%13])
                    $fatal(1,"Writer mismatch char %0d got=%o expected=%o",printed,writer_data,expected[printed%13]);
                $fdisplay(log_file,"%02o",writer_data); printed<=printed+1;
            end
            if(retire) begin
                retired<=retired+1;
                if(retired<18 || retire_address==17'o14 || retire_address==17'o15)
                    $display("TRACE k=%o pc=%o ir=%o p=%o q=%o e=%o sum=%o",retire_sequence,
                      retire_address,retire_instruction,program_counter,operand_address,e,debug_index_data);
            end
        end
    end
    initial begin
        expected[0]=6'o27;expected[1]=6'o24;expected[2]=6'o33;expected[3]=6'o33;
        expected[4]=6'o36;expected[5]=6'o56;expected[6]=6'o70;expected[7]=6'o46;
        expected[8]=6'o36;expected[9]=6'o41;expected[10]=6'o33;expected[11]=6'o23;expected[12]=6'o60;
        // .tape: one byte per line; bit 7 marks a punched feed hole, bits 5-0 hold data.
        file_handle=$fopen("programs/hello.tape","rb");
        if(!file_handle) $fatal(1,"No hello paper tape");
        status=$fgetc(file_handle);
        while(status!=-1) begin if(status&8'h80) begin paper[paper_count]=status[5:0];paper_count=paper_count+1;end
            status=$fgetc(file_handle);end
        $fclose(file_handle);
        log_file=$fopen("build/hello-writer-codes.txt","w");
        // Defined power-on RAM contents, with no instructions preloaded.
        for(i=0;i<65536;i=i+1) dut.memory.s_memory[i]=0;
        for(i=0;i<4096;i=i+1) dut.memory.t_memory[i]=0;
        repeat(4) @(negedge clk);reset=0;start=1;
        @(negedge clk);start=0;
        while(fault==0 && cycles<300000) @(negedge clk);
        $fclose(log_file);
        if(fault!==1 || printed!=39 || current_sequence!==6'o66 || rewinds!=1)
            $fatal(1,"Boot incomplete fault=%0d k=%o p=%o lines=%0d/%0d printed=%0d rewinds=%0d E=%o X56=%o",
                fault,current_sequence,program_counter,paper_position,paper_count,printed,rewinds,e,debug_index_data);
        $display("PASS: physical plugboard + reader leader + checksummed paper loaded HELLO; %0d retirements, %0d lines, %0d output characters",retired,paper_position,printed);
        $finish;
    end
endmodule
`default_nettype wire
