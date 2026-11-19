`timescale 1ns/1ps
`default_nettype none
module tb_machine;
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
    integer cases=0,checks=0,fd,status,cycles,i,events;
    reg [35:0] target,ia,ib,ic,id,ie,im,ea,eb,ec,ed,ee,em;
    reg [8:0] cfg,ef;
    reg [17:0] ix,ex;
    reg [3:0] ez;
    reg [16:0] ep;
    reg expected_meta;
    reg [63:0] opcode_coverage=0;
    reg seen_trap;
    function [35:0] ins;
        input [5:0] op;input [4:0] cf;input [5:0] j;input [16:0] addr;
        begin ins={1'b1,cf,op,j,1'b0,addr};end
    endfunction
    task fresh;
        begin
            @(negedge clk);reset=1;start=0;host_request=0;console_stop=0;console_continue=0;
            alarm_suppress=0;trap_set_enable=0;sync_trap=0;host_meta_write=1;host_meta_value=0;
            repeat(3)@(negedge clk);reset=0;
        end
    endtask
    task host;
        input writing;input [16:0] addr;input [35:0] data;
        begin
            @(negedge clk);host_request=1;host_write=writing;host_address=addr;host_write_data=data;
            @(negedge clk);cycles=0;
            while(!host_ready && cycles<40)begin @(negedge clk);cycles=cycles+1;end
            if(!host_ready || host_error!=0)$fatal(1,"Host failed at %o",addr);
            host_request=0;@(negedge clk);
        end
    endtask
    task put;
        input [16:0] addr;input [35:0] data;
        begin host(1,addr,data);end
    endtask
    task launch;
        begin @(negedge clk);host_meta_write=0;start_address=17'o100;start=1;@(negedge clk);start=0;end
    endtask
    task stopped;
        begin cycles=0;while(running && cycles<6000)begin @(negedge clk);cycles=cycles+1;end
            if(running)$fatal(1,"Stop timeout PC=%o K=%o",program_counter,current_sequence);
        end
    endtask
    task expect_word;
        input [16:0] addr;input [35:0] data;
        begin host(0,addr,0);if(host_read_data!==data)$fatal(1,"RAM %o actual=%o expected=%o",addr,host_read_data,data);checks=checks+1;end
    endtask
    always @(negedge clk) if(retire) opcode_coverage[retire_instruction[29:24]]=1;
    initial begin
        #1;fresh;debug_index_address=5;debug_configuration_address=1;
        fd=$fopen("build/machine-vectors.hex","r");if(!fd)$fatal(1,"missing machine vectors");
        status=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",target,cfg,ia,ib,ic,id,ie,im,ix,ea,eb,ec,ed,ee,ez,ex,ef,em,ep,expected_meta);
        while(status==20)begin
            fresh;
            put(17'o1000,ia);put(17'o1001,ib);put(17'o1002,ic);put(17'o1003,id);put(17'o1004,ie);
            put(17'o1005,{9'o340,9'o410,9'o763,cfg});put(17'o1006,im);
            put(17'o100,ins(6'o24,0,0,17'o1000));put(17'o101,ins(6'o25,0,0,17'o1001));
            put(17'o102,ins(6'o26,0,0,17'o1002));put(17'o103,ins(6'o27,0,0,17'o1003));
            put(17'o104,ins(6'o22,1,0,17'o1005));put(17'o105,ins(6'o12,ix[17] ? 5'd1 : 5'd0,5,17'd3));
            put(17'o106,ins(6'o20,0,0,17'o1004));put(17'o107,target);put(17'o110,0);put(17'o111,0);put(17'o112,0);
            launch;cycles=0;
            while(!(retire && retire_address==17'o107) && fault==0 && cycles<6000)begin @(negedge clk);cycles=cycles+1;end
            if(!retire || fault!=0)$fatal(1,"Target did not retire case=%0d op=%o fault=%d PC=%o",cases,target[29:24],fault,program_counter);
            if({a,b,c,d,e,overflow_flags,debug_index_data,debug_configuration_data,program_counter}!=={ea,eb,ec,ed,ee,ez,ex,ef,ep})
                $fatal(1,"CPU case %0d target=%o cfg=%o\n actual A=%o B=%o C=%o D=%o E=%o Z=%h X=%o F=%o P=%o\n expect A=%o B=%o C=%o D=%o E=%o Z=%h X=%o F=%o P=%o",cases,target,cfg,a,b,c,d,e,overflow_flags,debug_index_data,debug_configuration_data,program_counter,ea,eb,ec,ed,ee,ez,ex,ef,ep);
            stopped;if(fault!=1)$fatal(1,"Unexpected tail fault %d",fault);
            expect_word(17'o1006,em);
            if(host_read_meta!==expected_meta)$fatal(1,"Meta mismatch case %0d",cases);
            cases=cases+1;
            status=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",target,cfg,ia,ib,ic,id,ie,im,ix,ea,eb,ec,ed,ee,ez,ex,ef,em,ep,expected_meta);
        end
        $fclose(fd);
        if(cases!=414 || $countones(opcode_coverage)!=50)$fatal(1,"Missing ISA coverage cases=%0d bitmap=%h",cases,opcode_coverage);
        $display("PASS: %0d complete CPU instruction cases, all 50 opcode numbers retired, 14 direct AOP cases",cases);
        // U RAM, immutable physical inputs and real-time clock.
        fresh;put(17'o210017,36'o123456765432);expect_word(17'o210017,36'o123456765432);
        knob_data=36'o123456701234;knob_meta=1;external_register_data=36'o765432107654;
        expect_word(17'o377620,knob_data);if(!host_read_meta)$fatal(1,"knob meta lost");
        expect_word(17'o377621,external_register_data);
        panel_data[4*36 +: 36]=36'o765432123456;panel_meta[4]=1;
        expect_word(17'o377724,36'o765432123456);if(!host_read_meta)$fatal(1,"panel meta missing");
        put(17'o377724,0);expect_word(17'o377724,36'o765432123456);panel_data=0;panel_meta=0;
        tick_10us=1;repeat(13)@(negedge clk);tick_10us=0;
        expect_word(17'o377630,36'd13);put(17'o377630,0);expect_word(17'o377630,36'd13);
        clock_clear=1;@(negedge clk);clock_clear=0;expect_word(17'o377630,0);
        // MPAL stops; parity is restored even on the failing destructive read.
        fresh;put(17'o100,ins(6'o24,0,0,17'o1000));put(17'o101,0);put(17'o1000,36'o123456765432);
        dut.memory.s_parity[17'o1000]=~dut.memory.s_parity[17'o1000];
        launch;stopped;if(fault!=7 || !alarms[0])$fatal(1,"Missing MPAL");
        console_continue=1;@(negedge clk);console_continue=0;stopped;
        if(a!==36'o123456765432 || fault!=1)$fatal(1,"CALACO after parity restoration failed");
        // Suppressed MPAL allows the data and keeps the alarm lamp latched.
        fresh;put(17'o100,ins(6'o24,0,0,17'o1000));put(17'o101,0);put(17'o1000,36'd77);
        dut.memory.s_parity[17'o1000]=~dut.memory.s_parity[17'o1000];alarm_suppress=1;
        launch;stopped;if(a!=77 || !alarms[0])$fatal(1,"MPAL suppression failed");
        // Marked instruction, defer and operand each invoke sequence 42 from 50.
        for(i=0;i<3;i=i+1)begin
            fresh;
            put(17'o100,ins(6'o12,0,6'o42,17'o200));put(17'o101,ins(6'o12,0,6'o50,17'o300));
            put(17'o102,ins(6'o04,0,6'o42,17'o30000+(17'd1<<i)));
            put(17'o103,{1'b0,5'o30,6'o12,6'o50,1'b0,17'o300});
            put(17'o200,ins(6'o34,0,0,17'o1002));put(17'o201,{1'b0,5'o20,6'o12,6'o05,1'b0,17'b0});
            put(17'o300,{1'b0,5'b0,6'o24,6'b0,i==1,17'o1000});put(17'o301,0);
            put(17'o1000,i==1 ? {19'b0,17'o1001} : 36'o123456701234);put(17'o1001,36'o123456701234);
            host_meta_write=1;host_meta_value=1;
            if(i==0)put(17'o300,{1'b0,5'b0,6'o24,6'b0,1'b0,17'o1000});
            else if(i==1)put(17'o1000,{19'b0,17'o1001});
            else put(17'o1000,36'o123456701234);
            host_meta_write=0;seen_trap=0;launch;cycles=0;
            while(running && cycles<6000)begin
                @(negedge clk);cycles=cycles+1;
                if(retire && retire_sequence==6'o42)seen_trap=1;
            end
            if(!seen_trap || current_sequence!=6'o50 || fault!=1)$fatal(1,"Trap mode %0d failed flags=%h K=%o fault=%d",i,sequence_flags,current_sequence,fault);
            expect_word(17'o1002,36'o123456701234);
        end
        // STOP drains an arithmetic instruction; CALACO resumes its successor.
        fresh;put(17'o100,ins(6'o24,0,0,17'o1000));put(17'o101,ins(6'o60,0,0,17'o1001));put(17'o102,0);
        put(17'o1000,1);put(17'o1001,36'o004000000000);launch;
        while(!(retire && retire_address==17'o100))@(negedge clk);
        repeat(8)@(negedge clk);console_stop=1;@(negedge clk);console_stop=0;stopped;
        if(a!=16 || fault!=0 || program_counter!=17'o102)$fatal(1,"STOP did not drain CYA");
        console_continue=1;@(negedge clk);console_continue=0;stopped;if(fault!=1)$fatal(1,"CALACO failed");
        // NPAL / XPAL / FPAL are independent paths, all resume after
        // parity restoration without replacing the information bits.
        fresh;put(17'o100,ins(6'o12,0,5,17'd3));put(17'o101,0);
        dut.memory.s_parity[17'o100]=~dut.memory.s_parity[17'o100];launch;stopped;
        if(fault!=7 || !alarms[1])$fatal(1,"missing NPAL");
        console_continue=1;@(negedge clk);console_continue=0;stopped;
        if(debug_index_data!=3 || fault!=1)$fatal(1,"NPAL restoration failed");
        fresh;put(17'o100,ins(6'o12,0,5,17'd3));put(17'o101,ins(6'o10,0,5,17'o1000));put(17'o102,0);put(17'o1000,2);
        launch;while(!(retire && retire_address==17'o100))@(negedge clk);
        dut.core.x_parity[5]=~dut.core.x_parity[5];stopped;
        if(fault!=7 || !alarms[2])$fatal(1,"missing XPAL");
        console_continue=1;@(negedge clk);console_continue=0;stopped;
        if(debug_index_data!=5 || fault!=1)$fatal(1,"XPAL restoration failed");
        fresh;put(17'o100,ins(6'o21,1,0,17'o1000));put(17'o101,ins(6'o24,1,0,17'o1001));put(17'o102,0);
        put(17'o1000,0);put(17'o1001,77);launch;while(!(retire && retire_address==17'o100))@(negedge clk);
        dut.core.f_parity[1]=~dut.core.f_parity[1];stopped;
        if(fault!=7 || !alarms[3])$fatal(1,"missing FPAL");
        console_continue=1;@(negedge clk);console_continue=0;stopped;if(a!=77 || fault!=1)$fatal(1,"FPAL restoration failed");
        // Selection and device alarms, including a suppressed absent device.
        fresh;put(17'o100,ins(6'o04,0,6'o40,17'o30000));launch;stopped;
        if(fault!=8 || !alarms[7] || dut.devices.connected[6'o40])$fatal(1,"IOSAL/device inhibition failed");
        fresh;put(17'o100,ins(6'o04,0,6'o40,17'o30000));put(17'o101,ins(6'o24,0,0,17'o1000));put(17'o102,0);put(17'o1000,77);
        alarm_suppress=10'b0010000000;launch;stopped;if(a!=77 || !alarms[7])$fatal(1,"IOSAL suppression failed");
        fresh;put(17'o100,ins(6'o24,0,0,17'o300000));launch;stopped;if(!alarms[5] || fault!=3)$fatal(1,"QSAL failed");
        fresh;start_address=17'o300000;start=1;@(negedge clk);start=0;stopped;
        if(!alarms[4] || fault!=3)$fatal(1,"PSAL failed");
        // Automatic meta setting is separately gated by the console switch.
        for(i=0;i<3;i=i+1)begin
            fresh;trap_set_enable=1;
            put(17'o100,ins(6'o04,0,6'o42,17'o30000+(17'o100<<i)));
            put(17'o101,{1'b1,5'b0,6'o24,6'b0,i==1,17'o1000});put(17'o102,0);
            put(17'o1000,i==1 ? {19'b0,17'o1001} : 36'd77);put(17'o1001,77);launch;stopped;
            if(i==0 && !dut.memory.s_meta[17'o101])$fatal(1,"instruction meta setting failed");
            if(i!=0 && !dut.memory.s_meta[17'o1000])$fatal(1,"defer/operand meta setting failed");
            if(sequence_flags[6'o42])$fatal(1,"set-meta mode unexpectedly trapped");
        end
        // A marked placekeeper causes two CSK cycles, retains its marker,
        // and reports the original old/new pair to the trap handler.
        fresh;put(17'o100,ins(6'o12,0,6'o42,17'o200));put(17'o101,ins(6'o11,0,6'o50,17'o1000));
        put(17'o102,ins(6'o04,0,6'o42,17'o30010));put(17'o103,ins(6'o04,0,6'o50,17'o50000));
        put(17'o104,{1'b0,5'o20,6'o05,6'b0,1'b0,17'o105});put(17'o1000,36'o400300);
        put(17'o200,ins(6'o30,0,0,17'o1002));put(17'o201,{1'b0,5'o20,6'o12,6'o05,1'b0,17'b0});
        put(17'o300,ins(6'o24,0,0,17'o1001));put(17'o301,0);put(17'o1001,77);launch;stopped;
        if(current_sequence!=6'o50 || a!=77 || !dut.core.x_memory[6'o50][17])$fatal(1,"placekeeper trap/marker failed");
        expect_word(17'o1002,36'o000050000105);
        // CODABO requested while running drains the instruction, presets
        // I/O/flags, and starts at the new SPR without clearing A..E.
        fresh;put(17'o100,ins(6'o04,0,6'o66,17'o30000));put(17'o101,ins(6'o60,0,0,17'o1000));
        put(17'o102,ins(6'o05,0,0,17'o102));put(17'o200,0);put(17'o1000,36'o004000000000);
        launch;while(!(retire && retire_address==17'o100))@(negedge clk);
        repeat(8)@(negedge clk);start_address=17'o200;start=1;@(negedge clk);start=0;stopped;
        if(program_counter!=17'o201 || dut.devices.connected!=0 || current_sequence!=0 || sequence_flags!=1)
            $fatal(1,"running CODABO failed PC=%o",program_counter);
        // A held TSD waits in LIMBO, wakes on ready, and defers a pending
        // higher-priority trap until the next unheld instruction completes.
        fresh;external_present[6'o44]=1;external_input[6'o44]=1;
        external_data=36'o77;external_mask=36'o77;external_ready=0;
        put(17'o100,ins(6'o12,0,6'o42,17'o300));put(17'o101,ins(6'o12,0,6'o44,17'o200));
        put(17'o102,ins(6'o04,0,6'o44,17'o30000));
        put(17'o103,{1'b0,5'o30,6'o12,6'o44,1'b0,17'o200});
        put(17'o200,ins(6'o57,0,0,17'o1000));
        put(17'o201,{1'b0,5'b0,6'o12,6'o05,1'b0,17'o7});put(17'o202,0);
        put(17'o300,ins(6'o34,0,0,17'o1002));put(17'o301,{1'b0,5'o20,6'o12,6'o05,1'b0,17'b0});
        put(17'o1000,36'o111222333444);launch;cycles=0;
        while(!limbo && cycles<800)begin @(negedge clk);cycles=cycles+1;end
        if(!limbo || current_sequence!=6'o44 || program_counter!=17'o200)$fatal(1,"TSD wait did not enter LIMBO");
        repeat(9)@(negedge clk);external_ready[6'o44]=1;cycles=0;
        while(dut.core.state!=4'd11 && cycles<800)begin @(negedge clk);cycles=cycles+1;end
        if(dut.core.state!=11)$fatal(1,"TSD did not wake");
        sync_trap=1;@(negedge clk);sync_trap=0;events=0;
        while(running && cycles<1500)begin
            @(negedge clk);cycles=cycles+1;
            if(retire)begin
                case(events)
                    0:if(retire_address!=17'o200)$fatal(1,"held TSD was preempted");
                    1:if(retire_address!=17'o201)$fatal(1,"hold did not extend through next instruction");
                    2:if(retire_sequence!=6'o42 || retire_address!=17'o300)$fatal(1,"priority trap did not run");
                    3:if(retire_address!=17'o301)$fatal(1,"trap dismiss failed");
                    default:$fatal(1,"unexpected post-dismiss retirement");
                endcase
                events=events+1;
            end
        end
        if(events!=4 || current_sequence!=6'o44 || fault!=1)$fatal(1,"sequence resume failed events=%0d",events);
        expect_word(17'o1000,36'o111222333477);
        // H63 p108 scan: inactive timer-buffer quarters receive +0.
        fresh;put(17'o100,ins(6'o04,0,6'o54,17'o30000));
        put(17'o101,{1'b0,5'o30,6'o12,6'o54,1'b0,17'o200});
        put(17'o200,ins(6'o57,1,0,17'o1000));put(17'o201,0);put(17'o1000,36'o777777);
        dut.core.f_memory[1]=9'o020;dut.core.f_parity[1]=~^9'o020;
        launch;stopped;
        if(dut.devices.timer_buffer!=18'o777)$fatal(1,"inactive timer bits not +0: %o",dut.devices.timer_buffer);
        // Unit75 TSD acts as CLDE without a write/rotation; see H63 4-9.
        fresh;put(17'o100,{1'b0,5'o30,6'o12,6'o75,1'b0,17'o200});
        put(17'o200,ins(6'o57,0,0,17'o1000));put(17'o201,0);
        put(17'o1000,36'o123456701234);launch;stopped;
        expect_word(17'o1000,36'o123456701234);
        if(e!=36'o123456701234)$fatal(1,"unit75 TSD E/CLDE rule wrong");
        // A nine-bit magnetic-tape assembly chunk occupies every fourth bit.
        fresh;external_present[6'o46]=1;external_input[6'o46]=1;
        external_ready[6'o46]=1;external_assembly[6'o46]=1;external_assembly_width=9;
        external_data=36'o777;external_mask=36'o777;
        put(17'o100,ins(6'o04,0,6'o46,17'o30002));
        put(17'o101,{1'b0,5'o30,6'o12,6'o46,1'b0,17'o200});
        put(17'o200,ins(6'o57,0,0,17'o1000));put(17'o201,0);put(17'o1000,0);launch;stopped;
        expect_word(17'o1000,36'h111111111);
        external_assembly=0;external_assembly_width=6;external_present=0;external_input=0;external_ready=0;
        // Manual sync selection suppresses encounter traps but retains the
        // independent metabit-setting half of the unit42 mode; see H63 p91.
        fresh;sync_trap_mode=1;trap_set_enable=1;
        put(17'o100,ins(6'o04,0,6'o42,17'o30101));
        put(17'o101,ins(6'o24,0,0,17'o1000));put(17'o102,ins(6'o24,0,0,17'o1000));put(17'o103,0);put(17'o1000,77);
        dut.memory.s_meta[17'o101]=1;dut.memory.s_parity[17'o101]=~dut.memory.s_parity[17'o101];launch;stopped;
        if(sequence_flags[6'o42] || !dut.memory.s_meta[17'o102])$fatal(1,"manual sync override flags=%o setmeta=%b mode=%o coremode=%o",sequence_flags,dut.memory.s_meta[17'o102],dut.devices.mode[6'o42],dut.core.trap_mode);
        sync_trap_mode=0;
        $display("PASS: LIMBO, I/O wakeup, held transfer, priority preemption, dismiss and placekeeper resume");
        $display("PASS: U/V memory, odd parity stop/suppress/restore, CALACO, three meta trap modes and STOP draining arithmetic; %0d RAM checks",checks);
        $finish;
    end
endmodule
`default_nettype wire
