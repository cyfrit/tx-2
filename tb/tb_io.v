`timescale 1ns/1ps
`default_nettype none
module tb_io;
    reg clk, reset;
    reg tick_1us,timer_tick,light_pen_hit,camera_done,camera_alarm;
    reg display_ready;
    wire display_valid;
    wire [5:0] display_unit;
    wire [9:0] display_x,display_y;
    wire [35:0] display_word;
    wire [1:0] display_intensity;
    wire camera_request;
    reg [63:0] external_present,external_missed,external_inability;
    wire control_error,software_unit;
    wire [11:0] trap_mode;
    wire missed_alarm,missed_suppress;
    reg control_valid;
    reg [5:0] control_unit;
    reg [17:0] control_command;
    reg [63:0] flags;
    wire [35:0] report;
    reg transfer_valid;
    reg [5:0] transfer_unit;
    reg [35:0] transfer_data;
    wire transfer_ready;
    wire transfer_input;
    wire transfer_assembly;
    wire transfer_reverse;
    wire [35:0] input_data;
    wire [35:0] input_mask;
    wire [63:0] flag_raise;
    reg tape_valid;
    reg [5:0] tape_data;
    wire tape_ready;
    wire tape_rewind;
    wire writer_valid;
    wire [5:0] writer_data;
    reg writer_ready;
    reg [63:0] external_ready;
    reg [63:0] external_input;
    reg [35:0] external_data;
    reg [35:0] external_mask;
    wire external_valid;
    wire [5:0] external_unit;
    wire [35:0] external_write_data;
    reg [63:0] external_assembly=0,external_reverse=0;
    wire external_control_valid;
    wire [5:0] external_control_unit;
    wire [17:0] external_control_command;
    always #5 clk=~clk;
    reg timer_fast=1,timer_manual_start=0,timer_manual_stop=0,timer_manual_load=0;
    reg camera_manual_index=0;
    reg [1:0] scope_ready=3;
    reg [17:0] timer_manual_interval=0;
    wire timer_end_carry,pen_lit;
    wire [9:0] pen_x,pen_y;
    reg tape_manual_disconnect=0,tape_stop_unit=0;
    reg [63:0] external_clear_alarms=0,external_maintenance=0;
    reg [14:0] external_special=0;
    reg [3:0] external_assembly_width=6;
    wire [3:0] transfer_assembly_width;
    tx2_io dut(.*);
    initial begin clk=0;reset=0;tick_1us=0;timer_tick=0;light_pen_hit=0;camera_done=0;camera_alarm=0;display_ready=0;external_present=0;external_missed=0;external_inability=0;control_valid=0;control_unit=0;control_command=0;flags=0;transfer_valid=0;transfer_unit=0;transfer_data=0;tape_valid=0;tape_data=0;writer_ready=0;external_ready=0;external_input=0;external_data=0;external_mask=0; end
    integer i,pulses=0,checks=0;
    reg [35:0] saved_report;
    task control;
        input [5:0] unit_id;input [17:0] command;
        begin
            @(negedge clk);control_unit=unit_id;control_command=command;control_valid=1;
            #1;if(control_error)$fatal(1,"Unexpected IOSAL unit=%o cmd=%o",unit_id,command);
            @(negedge clk);control_valid=0;checks=checks+1;
        end
    endtask
    task transfer;
        input [5:0] unit_id;input [35:0] data;
        begin
            @(negedge clk);transfer_unit=unit_id;transfer_data=data;transfer_valid=1;
            #1;if(!transfer_ready)$fatal(1,"Not ready unit=%o",unit_id);
            @(negedge clk);transfer_valid=0;checks=checks+1;
        end
    endtask
    initial begin
        #1;reset=1;repeat(3)@(negedge clk);reset=0;
        // Trap mode is programmed/disconnected through IOS.
        control(6'o42,18'o30107);if(trap_mode!=12'o107)$fatal(1,"trap config lost");
        control(6'o42,18'o20000);if(trap_mode!=0)$fatal(1,"trap disconnect failed");
        // A full writer buffer keeps data stable throughout backpressure.
        control(6'o66,18'o30000);transfer(6'o66,36'o27);
        transfer_unit=6'o66;
        for(i=0;i<7;i=i+1)begin
            @(negedge clk);if(!writer_valid || writer_data!=6'o27 || transfer_ready)$fatal(1,"writer changed while blocked");
        end
        writer_ready=1;@(negedge clk);writer_ready=0;#1;if(!transfer_ready)$fatal(1,"writer did not become ready");
        repeat(3)@(negedge clk);
        if(flag_raise[6'o66])$fatal(1,"idle writer reasserted a software-dismissed flag");
        // PETR holds a six-bit line until transfer and emits bin rewind.
        control(6'o52,18'o30106);#1;if(!tape_rewind)$fatal(1,"missing rewind");
        @(negedge clk);tape_valid=1;tape_data=6'o35;
        while(!tape_ready)@(negedge clk);
        @(negedge clk);tape_valid=0;transfer_unit=6'o52;#1;
        if(!transfer_input || !transfer_assembly || input_data!=36'o35 || !flag_raise[6'o52])$fatal(1,"reader buffer/flag wrong");
        transfer(6'o52,0);#1;if(transfer_ready)$fatal(1,"reader line consumed twice");
        control(6'o52,18'o30100);transfer_unit=6'o52;#1;
        if(transfer_assembly || tape_rewind || !tape_ready)$fatal(1,"PETR normal mode decoded as assembly");
        tape_valid=1;tape_data=6'o27;@(negedge clk);tape_valid=0;transfer(6'o52,0);
        control(6'o52,18'o30006);#1;if(tape_ready || tape_rewind)$fatal(1,"PETR STOP still moved tape");
        // Free-running overwrite, STOP UNIT inhibition, and connect-edge clear
        // are the three MISIND cases in TM2 15-PETR-3.
        control(6'o52,18'o30100);tape_data=6'o12;tape_valid=1;
        @(negedge clk);tape_data=6'o34;
        @(negedge clk);tape_valid=0;control_unit=6'o52;transfer_unit=6'o52;#1;
        if(input_data!=36'o34 || !report[12] || !missed_alarm || !tape_ready)$fatal(1,"PETR did not overwrite/latch MISIND");
        control(6'o52,18'o20000);control(6'o52,18'o30100);
        tape_stop_unit=1;tape_valid=1;tape_data=6'o56;repeat(2)@(negedge clk);tape_valid=0;#1;
        if(report[12])$fatal(1,"STOP UNIT did not inhibit PETR MISIND");
        tape_stop_unit=0;transfer(6'o52,0);control(6'o52,18'o30000);
        // The timer has a separate busy window and manual start/stop controls.
        control(6'o54,18'o30000);transfer(6'o54,36'd20);control(6'o54,18'o30100);
        transfer_unit=6'o54;#1;if(!transfer_ready)$fatal(1,"timer busy before last16");
        timer_tick=1;repeat(4)@(negedge clk);timer_tick=0;#1;
        if(transfer_ready)$fatal(1,"timer last16 window missing");
        timer_fast=0;#1;if(!transfer_ready)$fatal(1,"slow timer busy too early");
        timer_tick=1;repeat(15)@(negedge clk);timer_tick=0;#1;
        if(transfer_ready)$fatal(1,"slow timer end carry busy window missing");
        timer_manual_stop=1;@(negedge clk);timer_manual_stop=0;#1;
        if(!transfer_ready)$fatal(1,"manual timer stop left buffer busy");
        timer_fast=1;
        // A programmable 3-tick timer emits exact spaced requests. Disconnect
        // suppresses requests while its counter continues to run.
        control(6'o54,18'o30000);transfer(6'o54,36'd3);control(6'o54,18'o30300);
        timer_tick=1;
        for(i=0;i<12;i=i+1)begin @(negedge clk);if(flag_raise[6'o54])pulses=pulses+1;end
        timer_tick=0;if(pulses!=4)$fatal(1,"timer pulse count %0d",pulses);
        control(6'o54,18'o20000);timer_tick=1;
        repeat(7)begin @(negedge clk);if(flag_raise[6'o54])$fatal(1,"disconnected timer interrupted");end
        timer_tick=0;
        // Display buffer, coordinate wiring, intensity hold and light pen gate.
        display_ready=0;control(6'o60,18'o30320);control(6'o55,18'o30000);
        transfer(6'o60,36'o123456701234);transfer_unit=6'o60;#1;
        if(!display_valid || display_word!=36'o123456701234 || display_intensity!=2 ||
           display_x!=(10'o247 ^ 10'o1000) || display_y!=(10'o1602 ^ 10'o1000))
            $fatal(1,"display decode X=%o Y=%o",display_x,display_y);
        light_pen_hit=1;#1;if(flag_raise[6'o55])$fatal(1,"light pen accepted before intensification");
        light_pen_hit=0;display_ready=1;@(negedge clk);display_ready=0;tick_1us=1;
        light_pen_hit=1;#1;if(!flag_raise[6'o55])$fatal(1,"light pen not gated during intensification");light_pen_hit=0;
        for(i=0;i<39;i=i+1)begin @(negedge clk);if(transfer_ready)$fatal(1,"scope freed early at %0d",i);end
        @(negedge clk);tick_1us=0;#1;if(!transfer_ready)$fatal(1,"scope never completed");
        light_pen_hit=1;#1;if(flag_raise[6'o55])$fatal(1,"light pen accepted without intensification");light_pen_hit=0;
        control(6'o60,18'o30004);#1;if(!camera_request || transfer_ready)$fatal(1,"camera interlock failed");
        camera_done=1;@(negedge clk);camera_done=0;#1;if(!transfer_ready)$fatal(1,"camera completion lost");
        // Camera belongs to 60 only; 56 has an independent buffer and duration.
        control(6'o60,18'o30004);control(6'o56,18'o30004);
        transfer(6'o56,36'o765432101234);transfer_unit=6'o60;#1;
        if(transfer_ready || !display_valid || display_unit!=6'o56)$fatal(1,"camera blocked wrong scope");
        display_ready=1;@(negedge clk);display_ready=0;light_pen_hit=1;#1;
        if(pen_lit || flag_raise[6'o55])$fatal(1,"scope56 stimulated scope60 pen");
        light_pen_hit=0;camera_done=1;tick_1us=1;repeat(10)@(negedge clk);camera_done=0;tick_1us=0;
        transfer_unit=6'o56;#1;if(!transfer_ready)$fatal(1,"scope56 never completed independently");
        // External ports preserve transfer backpressure and presence alarms.
        external_present[6'o63]=1;control(6'o63,18'o30000);transfer_unit=6'o63;transfer_valid=1;
        #1;if(!external_valid || transfer_ready)$fatal(1,"external blocked handshake wrong");
        external_ready[6'o63]=1;#1;if(!transfer_ready)$fatal(1,"external ready lost");
        @(negedge clk);transfer_valid=0;
        control(6'o41,18'o30000);external_inability[6'o63]=1;#1;
        if(!flag_raise[6'o41])$fatal(1,"missing alarm sequence request");
        @(negedge clk);external_inability=0;transfer_unit=6'o41;#1;
        if(input_data!=36'o40 || !transfer_input)$fatal(1,"inability report %o",input_data);
        external_missed[6'o63]=1;#1;if(flag_raise[6'o41])$fatal(1,"additional alarm retriggered flag");
        @(negedge clk);external_missed=0;
        control(6'o63,18'o20000);transfer_unit=6'o41;#1;if(input_data!=0)$fatal(1,"disconnect did not clear alarm");
        // Device report bits are captured alongside standard state; SELECT
        // invokes a unit without connecting it or changing the retained mode.
        external_present[6'o46]=1;external_special=15'o40037;
        control(6'o46,18'o30123);control_unit=6'o46;#1;
        if(report[35:24]!=12'o0037 || report[11:0]!=12'o123)$fatal(1,"device report bits missing");
        control(6'o46,18'o60002);#1;
        if(report[11:0]!=12'o123 || !report[14])$fatal(1,"SELECT changed mode/connect");
        control(6'o46,18'o34000);#1;
        if(report[11:0]!=12'o123)$fatal(1,"pure tape alarm clear changed mode");
        external_missed[6'o46]=1;external_inability[6'o46]=1;@(negedge clk);
        external_missed=0;external_inability=0;#1;if(!report[12] || !report[13])$fatal(1,"device alarms missing");
        external_clear_alarms[6'o46]=1;@(negedge clk);external_clear_alarms=0;#1;
        if(report[13:12]!=0)$fatal(1,"device clear hook ignored");
        control(6'o46,18'o20000);control(6'o46,18'o60001);#1;
        if(report[14] || report[11:0]!=12'o123)$fatal(1,"disconnected SELECT connected device");
        external_maintenance[6'o46]=1;control_command=18'o30000;control_valid=1;#1;
        if(!control_error || !report[15])$fatal(1,"maintenance IOSAL/report missing");
        control_valid=0;external_maintenance=0;external_special=0;
        transfer_unit=6'o75;#1;if(!software_unit || flag_raise[6'o75])$fatal(1,"unit75 software/flag rule wrong");
        control_unit=6'o40;control_command=18'o30000;control_valid=1;#1;
        if(!control_error)$fatal(1,"missing IOSAL for absent unit");control_valid=0;
        $display("PASS: PETR/Writer buffering, timer, display coordinates/intensity, pen, camera, external handshakes and alarm reporting; %0d control/transfer checks",checks);
        $finish;
    end
endmodule
`default_nettype wire
