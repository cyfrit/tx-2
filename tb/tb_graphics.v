`timescale 1ns/1ps
`default_nettype none
module tb_graphics;
    reg clk, reset, start;
    reg console_stop,console_continue,console_preset,console_startover,console_reset_start,console_hold;
    reg [9:0] alarm_suppress;
    reg clear_alarms,trap_set_enable,sync_trap;
    wire [9:0] alarms;
    reg tick_1us,tick_10us,timer_tick,clock_clear;
    reg [35:0] knob_data,external_register_data;
    reg knob_meta,external_register_meta;
    reg [287:0] console_switches;
    reg host_meta_write,host_meta_value;
    wire host_read_meta,host_read_parity;
    reg light_pen_hit,camera_done,camera_alarm,display_ready;
    wire display_valid;
    wire [5:0] display_unit;
    wire [9:0] display_x,display_y;
    wire [35:0] display_word;
    wire [1:0] display_intensity;
    wire camera_request;
    reg [63:0] external_present,external_missed,external_inability;
    reg [16:0] start_address;
    wire running;
    wire [3:0] overflow_flags;
    wire [3:0] fault;
    reg host_request, host_write;
    reg [16:0] host_address;
    reg [35:0] host_write_data;
    wire host_ready;
    wire [35:0] host_read_data;
    wire [1:0] host_error;
    wire retire;
    wire [16:0] retire_address;
    wire [35:0] retire_instruction;
    wire [5:0] retire_sequence, current_sequence;
    wire [63:0] sequence_flags;
    wire limbo;
    wire [16:0] program_counter, operand_address;
    wire [35:0] a,b,c,d,e;
    reg [5:0] debug_index_address;
    wire [17:0] debug_index_data;
    reg [4:0] debug_configuration_address;
    wire [8:0] debug_configuration_data;
    reg tape_valid;
    reg [5:0] tape_data;
    wire tape_ready, tape_rewind;
    wire writer_valid;
    wire [5:0] writer_data;
    reg writer_ready;
    reg [63:0] external_ready, external_input;
    reg [35:0] external_data, external_mask;
    wire external_valid;
    wire [5:0] external_unit;
    wire [35:0] external_write_data;
    reg [63:0] external_assembly=0,external_reverse=0;
    wire external_control_valid;
    wire [5:0] external_control_unit;
    wire [17:0] external_control_command;
    reg [575:0] panel_data=0;
    reg [15:0] panel_meta=0;
    always #5 clk=~clk;
    reg sync_trap_mode=0,timer_fast=1,timer_manual_start=0,timer_manual_stop=0,timer_manual_load=0;
    reg camera_manual_index=0;
    reg [1:0] scope_ready=3;
    reg [17:0] timer_manual_interval=0;
    wire timer_end_carry,pen_lit;
    wire [9:0] pen_x,pen_y;
    reg tape_manual_disconnect=0;
    reg [63:0] external_clear_alarms=0,external_maintenance=0;
    reg [14:0] external_special=0;
    reg [3:0] external_assembly_width=6;
    tx2_machine dut(.*);

    initial begin clk=0;reset=0;start=0;console_stop=0;console_continue=0;console_preset=0;console_startover=0;console_reset_start=0;console_hold=0;alarm_suppress=0;clear_alarms=0;trap_set_enable=0;sync_trap=0;tick_1us=0;tick_10us=0;timer_tick=0;clock_clear=0;knob_data=0;external_register_data=0;knob_meta=0;external_register_meta=0;console_switches=0;host_meta_write=0;host_meta_value=0;light_pen_hit=0;camera_done=0;camera_alarm=0;display_ready=0;external_present=0;external_missed=0;external_inability=0;start_address=0;host_request=0;host_write=0;host_address=0;host_write_data=0;debug_index_address=0;debug_configuration_address=0;tape_valid=0;tape_data=0;writer_ready=0;external_ready=0;external_input=0;external_data=0;external_mask=0; end
    reg [5:0] paper[0:4095];
    reg [9:0] expected_x[0:3],expected_y[0:3];
    integer paper_count=0,paper_position=0,cycles=0,points=0,pen_retirements=0,rewinds=0;
    integer fd,status,i,event_log,retired=0;
    reg [7:0] line_data;
    reg pen_sent=0;
    always @* begin
        tape_valid=tape_ready && paper_position<paper_count && cycles%128==0;
        tape_data=paper[paper_position];
        display_ready=cycles%13<7;
        tick_1us=cycles%10==0;
    end
    always @(posedge clk)if(!reset)begin
        cycles<=cycles+1;light_pen_hit<=0;
        if(tape_rewind)begin paper_position<=0;rewinds<=rewinds+1;end
        else if(tape_valid && tape_ready)paper_position<=paper_position+1;
        if(display_valid && display_ready)begin
            if(points>=4 || display_unit!=6'o60 || display_intensity!=2 ||
               display_x!==expected_x[points] || display_y!==expected_y[points])
                $fatal(1,"display event %0d X=%o Y=%o",points,display_x,display_y);
            $fdisplay(event_log,"%0d,%0d,%0d,%0d,%0d",cycles,display_unit,display_x,display_y,display_intensity);
            points<=points+1;
            if(points==1 && !pen_sent)begin light_pen_hit<=1;pen_sent<=1;end
        end
        if(retire)begin
            retired<=retired+1;
            if(retire_sequence==6'o55)pen_retirements<=pen_retirements+1;
        end
    end
    initial begin
        #1;reset=1;
        expected_x[0]=768;expected_y[0]=768;expected_x[1]=255;expected_y[1]=768;
        expected_x[2]=255;expected_y[2]=255;expected_x[3]=768;expected_y[3]=255;
        fd=$fopen("programs/display-demo.tape","rb");if(!fd)$fatal(1,"missing display paper tape");
        status=$fgetc(fd);
        while(status!=-1)begin if(status&8'h80)begin paper[paper_count]=status[5:0];paper_count=paper_count+1;end status=$fgetc(fd);end
        $fclose(fd);event_log=$fopen("build/display-events.csv","w");
        $fdisplay(event_log,"cycle,unit,x_ones_complement,y_ones_complement,intensity");
        for(i=0;i<65536;i=i+1)dut.memory.s_memory[i]=0;
        for(i=0;i<4096;i=i+1)begin dut.memory.t_memory[i]=0;dut.memory.u_memory[i]=0;end
        repeat(4)@(negedge clk);reset=0;start_address=17'o377750;start=1;
        @(negedge clk);start=0;
        while(fault==0 && cycles<300000)@(negedge clk);
        $fclose(event_log);
        if(fault!=1 || points!=4 || pen_retirements!=4 || dut.memory.s_memory[17'o116]!==36'd1 || rewinds!=1)
            $fatal(1,"graphics boot failed fault=%d PC=%o points=%0d pen=%0d count=%o",fault,program_counter,points,pen_retirements,dut.memory.s_memory[17'o116]);
        if(dut.memory.s_memory[17'o120]!==36'o200000200000)$fatal(1,"normal display TSD changed point memory");
        $display("PASS: paper-booted graphics; %0d retirements, %0d tape lines, four verified display points, light-pen interrupt incremented RAM counter",retired,paper_position);
        $finish;
    end
endmodule
`default_nettype wire
