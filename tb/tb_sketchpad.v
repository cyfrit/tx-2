`timescale 1ns/1ps
`default_nettype none
module tb_sketchpad;
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
    reg [5:0] paper[0:131071];
    integer paper_boot=0,paper_count=0,paper_position=0,rewinds=0;
    integer first_user_cycle=-1,first_user_retired=0;
    reg [7:0] paper_line;
    integer fd,status,i,cycles=0,retired=0,points=0,max_cycles=2000000,trace,display_log,summary;
    integer seq_counts[0:63];
    reg [16:0] image_address,entry=17'o200000;
    reg [35:0] image_value;
    reg [16:0] tail_pc[0:255];
    reg [35:0] tail_n[0:255];
    reg [5:0] tail_k[0:255];
    integer dump_file;
    reg [31:0] random_state=32'h1963abcd;
    wire [35:0] random_word={random_state,random_state[3:0]};
    initial begin
        #1;reset=1;writer_ready=1;display_ready=1;
        external_present=(64'b1<<6'o47)|(64'b1<<6'o61)|(64'b1<<6'o65)|(64'b1<<6'o75);
        external_input=(64'b1<<6'o47)|(64'b1<<6'o61)|(64'b1<<6'o65);
        external_ready=(64'b1<<6'o61);
        external_mask=36'hfffffffff;alarm_suppress=10'b0010000000;
        i=$value$plusargs("paper_boot=%d",paper_boot);i=$value$plusargs("max_cycles=%d",max_cycles);i=$value$plusargs("entry=%o",entry);
        for(i=0;i<64;i=i+1)seq_counts[i]=0;
        for(i=0;i<65536;i=i+1)dut.memory.s_memory[i]=0;
        for(i=0;i<4096;i=i+1)begin dut.memory.t_memory[i]=0;dut.memory.u_memory[i]=0;end
        if(!paper_boot)begin
        fd=$fopen("build/sketchpad-combined.hex","r");if(!fd)$fatal(1,"Missing Sketchpad image");
        status=$fscanf(fd,"%h %h\n",image_address,image_value);
        while(status==2)begin
            if(image_address<17'o200000)begin dut.memory.s_memory[image_address[15:0]]=image_value;dut.memory.s_parity[image_address[15:0]]=~^image_value;end
            else if(image_address<17'o210000)begin dut.memory.t_memory[image_address[11:0]]=image_value;dut.memory.t_parity[image_address[11:0]]=~^image_value;end
            else if(image_address<17'o220000)begin dut.memory.u_memory[image_address[11:0]]=image_value;dut.memory.u_parity[image_address[11:0]]=~^image_value;end
            else $fatal(1,"Image address not mapped %o",image_address);
            status=$fscanf(fd,"%h %h\n",image_address,image_value);
        end
        $fclose(fd);
        // Execute the original standard configuration loads, then enter the
        // historical program. The image itself contains the original UNITS
        // and CONFIGS routines, which run again on the CLEAN entry.
        for(i=0;i<8;i=i+1)begin
            dut.memory.s_memory[17'o500+i]={1'b0,5'(i*4),6'o22,6'b0,1'b0,17'(17'o377740+i)};
            dut.memory.s_parity[17'o500+i]=~^dut.memory.s_memory[17'o500+i];
        end
        dut.memory.s_memory[17'o510]={1'b0,5'b0,6'o05,6'b0,1'b0,entry};
        dut.memory.s_parity[17'o510]=~^dut.memory.s_memory[17'o510];
        end else begin
            fd=$fopen("build/sketchpad.tape","rb");if(!fd)$fatal(1,"Missing Sketchpad paper tape");
            status=$fgetc(fd);
            while(status!=-1)begin if(status&8'h80)begin paper[paper_count]=status[5:0];paper_count=paper_count+1;end status=$fgetc(fd);end
            $fclose(fd);
        end
        trace=$fopen("results/sketchpad-run.trace","w");display_log=$fopen("results/sketchpad-points.csv","w");
        $fdisplay(display_log,"cycle,unit,x,y,intensity,word");
        repeat(5)@(negedge clk);reset=0;start_address=paper_boot ? 17'o377750 : 17'o500;start=1;
        @(negedge clk);start=0;
        while(fault==0 && (first_user_cycle<0 ? cycles<(paper_boot ? 100000000 : max_cycles) : cycles-first_user_cycle<max_cycles))@(negedge clk);
        summary=$fopen("results/sketchpad-run.txt","w");
        $fdisplay(summary,"cycles=%0d retired=%0d points=%0d fault=%0d K=%o PC=%o IR=%o Q=%o flags=%h alarms=%h limbo=%0d",cycles,retired,points,fault,current_sequence,program_counter,retire_instruction,operand_address,sequence_flags,alarms,limbo);
        $fdisplay(summary,"paper_boot=%0d paper_position=%0d paper_count=%0d rewinds=%0d application_cycle_start=%0d application_retirements=%0d",paper_boot,paper_position,paper_count,rewinds,first_user_cycle,retired-first_user_retired);
        for(i=0;i<64;i=i+1)if(seq_counts[i])$fdisplay(summary,"sequence=%02o retirements=%0d",i,seq_counts[i]);
        for(i=retired>256 ? retired-256 : 0;i<retired;i=i+1)
            $fdisplay(summary,"tail=%0d K=%o PC=%o N=%o",i,tail_k[i%256],tail_pc[i%256],tail_n[i%256]);
        dump_file=$fopen("results/sketchpad-memory.hex","w");
        for(i=0;i<65536;i=i+1)$fdisplay(dump_file,"%05h %09h",17'(i),dut.memory.s_memory[i]);
        for(i=0;i<4096;i=i+1)$fdisplay(dump_file,"%05h %09h",17'(17'o200000+i),dut.memory.t_memory[i]);
        for(i=0;i<4096;i=i+1)$fdisplay(dump_file,"%05h %09h",17'(17'o210000+i),dut.memory.u_memory[i]);
        $fclose(dump_file);
        $fclose(trace);$fclose(display_log);$fclose(summary);
        $display("SKETCHPAD: cycles=%0d retired=%0d points=%0d fault=%0d K=%o PC=%o IR=%o Q=%o flags=%h alarms=%h limbo=%0d",cycles,retired,points,fault,current_sequence,program_counter,retire_instruction,operand_address,sequence_flags,alarms,limbo);
        $finish;
    end
    // Mounted media is immutable during a run; avoid putting every paper
    // array cell on the combinational sensitivity list in Icarus.
    always @(paper_position or reset) tape_data=paper[paper_position];
    always @* begin
        tape_valid=tape_ready && paper_boot && paper_position<paper_count && cycles%128==0;
        external_data=external_unit==6'o61 ? random_word : 36'b0;
        tick_1us=cycles%50==0;tick_10us=cycles%500==0;timer_tick=cycles%50==0;
    end
    always @(posedge clk)if(!reset)begin
        cycles<=cycles+1;
        if(tape_rewind)begin paper_position<=0;rewinds<=rewinds+1;end
        else if(tape_ready && tape_valid)paper_position<=paper_position+1;
        random_state<={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
        if(retire)begin
            if(retire_address==17'o200000 && first_user_cycle<0)begin first_user_cycle<=cycles;first_user_retired<=retired;end
            tail_pc[retired%256]<=retire_address;tail_n[retired%256]<=retire_instruction;tail_k[retired%256]<=retire_sequence;
            retired<=retired+1;seq_counts[retire_sequence]<=seq_counts[retire_sequence]+1;
            if(first_user_cycle<0 ? retired<1000 : retired-first_user_retired<100000)$fdisplay(trace,"%0d K=%02o PC=%06o N=%012o P=%06o Q=%06o A=%012o B=%012o C=%012o D=%012o E=%012o Z=%h",cycles,retire_sequence,retire_address,retire_instruction,program_counter,operand_address,a,b,c,d,e,overflow_flags);
        end
        if(display_valid && display_ready)begin
            points<=points+1;
            if(points<100000)$fdisplay(display_log,"%0d,%02o,%0d,%0d,%0d,%012o",cycles,display_unit,display_x,display_y,display_intensity,display_word);
        end
    end
endmodule
`default_nettype wire
