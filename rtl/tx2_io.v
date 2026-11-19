`timescale 1ns/1ps
`default_nettype none
// IOS/TSD controller. H63 4-7..4-9, device pages 41/42/52/54/55/56/60.
// Physical transports and external device buffers live on the board/host bus.
module tx2_io (
    input wire clk, reset,
    input wire tick_1us,timer_tick,light_pen_hit,camera_done,camera_alarm,
    input wire camera_manual_index,
    input wire timer_fast,timer_manual_start,timer_manual_stop,timer_manual_load,
    input wire [17:0] timer_manual_interval,
    output wire timer_end_carry,
    input wire tape_manual_disconnect,tape_stop_unit,
    input wire [1:0] scope_ready,
    input wire display_ready,
    output wire display_valid,
    output wire [5:0] display_unit,
    output wire [9:0] display_x,display_y,
    output wire [35:0] display_word,
    output wire [1:0] display_intensity,
    output wire pen_lit,
    output wire [9:0] pen_x,pen_y,
    output wire camera_request,
    input wire [63:0] external_present,external_missed,external_inability,
    input wire [63:0] external_assembly,external_reverse,external_clear_alarms,external_maintenance,
    input wire [14:0] external_special,
    input wire [3:0] external_assembly_width,
    output wire external_control_valid,
    output wire [5:0] external_control_unit,
    output wire [17:0] external_control_command,
    output wire control_error,software_unit,
    output wire [11:0] trap_mode,
    output wire missed_alarm,missed_suppress,
    input wire control_valid,
    input wire [5:0] control_unit,
    input wire [17:0] control_command,
    input wire [63:0] flags,
    output reg [35:0] report,
    input wire transfer_valid,
    input wire [5:0] transfer_unit,
    input wire [35:0] transfer_data,
    output wire transfer_ready,
    output wire transfer_input,
    output wire transfer_assembly,
    output wire [3:0] transfer_assembly_width,
    output wire transfer_reverse,
    output wire [35:0] input_data,
    output wire [35:0] input_mask,
    output wire [63:0] flag_raise,
    input wire tape_valid,
    input wire [5:0] tape_data,
    output wire tape_ready,
    output reg tape_rewind,
    output wire writer_valid,
    output wire [5:0] writer_data,
    input wire writer_ready,
    input wire [63:0] external_ready,
    input wire [63:0] external_input,
    input wire [35:0] external_data,
    input wire [35:0] external_mask,
    output wire external_valid,
    output wire [5:0] external_unit,
    output wire [35:0] external_write_data
);
    reg [63:0] connected,previous_output_ready;
    reg [11:0] mode [0:63];
    reg tape_full,writer_full;
    reg [5:0] tape_buffer,writer_buffer;
    reg [63:0] generic_busy;
    reg [63:0] available;
    reg [17:0] timer_buffer,timer_count;
    reg timer_pulse,timer_running;
    // Each display has its own buffer; see Sketchpad TR296 appendix, pp.95-97.
    reg [1:0] scope_full,scope_started;
    reg [35:0] scope_buffer [0:1];
    reg [6:0] scope_time [0:1];
    reg camera_busy;
    reg [63:0] missed_latch,inability_latch;
    wire timer_interrupt=mode[6'o54][7];
    wire [63:0] builtin_units=(64'b1<<6'o41)|(64'b1<<6'o42)|(64'b1<<6'o52)|
           (64'b1<<6'o54)|(64'b1<<6'o55)|(64'b1<<6'o56)|(64'b1<<6'o60)|(64'b1<<6'o66);
    wire valid_sequence=control_unit==0 || control_unit>=6'o40;
    wire physical_command=control_command[14:12]==2 || control_command[14:12]==3 || control_command[14:12]==6;
    // H63 IOS table: 0 reports only, 2 disconnects, 3 connects/mode,
    // 4/5 control flags, 6 selects only. Classes 1 and 7 are undefined.
    assign control_error=control_valid &&
          (!valid_sequence || control_command[17:15]!=0 ||
           (physical_command && ((!builtin_units[control_unit] && !external_present[control_unit]) || external_maintenance[control_unit])) ||
           control_command[14:12]==1 || control_command[14:12]==7);
    assign software_unit=transfer_unit==0 ||
           (!builtin_units[transfer_unit] && !external_present[transfer_unit]) ||
           transfer_unit==6'o42 || transfer_unit==6'o55 || transfer_unit==6'o75;
    assign trap_mode=connected[6'o42] ? mode[6'o42] : 12'b0;
    assign missed_suppress=connected[6'o41];
    wire petr_overrun=tape_valid && connected[6'o52] && tape_full &&
                      !(transfer_valid && transfer_ready && transfer_unit==6'o52) && !tape_stop_unit;
    wire [63:0] new_missed=(external_missed & connected) | (petr_overrun ? (64'b1<<6'o52) : 0);
    wire [63:0] new_inability=(external_inability & connected) |
                         (camera_alarm && connected[6'o60] ? (64'b1<<6'o60) : 0);
    // The central MISAL condition remains until the source's indicator clears.
    assign missed_alarm=|(new_missed | missed_latch);
    wire scope_select=(scope_full[0] && !scope_started[0] && scope_ready[0]) ? 1'b0 :
                      (scope_full[1] && !scope_started[1] && scope_ready[1]) ? 1'b1 : scope_started[1];
    assign display_valid=|(scope_full & ~scope_started & scope_ready);
    assign display_unit=scope_select ? 6'o60 : 6'o56;
    assign display_word=scope_buffer[scope_select];
    assign display_x=display_word[35:26] ^ {mode[display_unit][7],9'b0};
    assign display_y=display_word[17:8] ^ {mode[display_unit][6],9'b0};
    assign display_intensity=mode[display_unit][4:3];
    assign camera_request=camera_busy;
    // H63 unit 55: sensitivity is strobed only by scope 60. TR296 lists a
    // second pen but gives no sequence/routing; use the documented H63 wiring.
    assign pen_lit=scope_full[1] && scope_started[1] && scope_ready[1];
    assign pen_x=scope_buffer[1][35:26] ^ {mode[6'o60][7],9'b0};
    assign pen_y=scope_buffer[1][17:8] ^ {mode[6'o60][6],9'b0};
    wire light_request=light_pen_hit && connected[6'o55] && pen_lit;
    assign timer_end_carry=timer_pulse;
    wire [63:0] event_requests=(timer_pulse && timer_interrupt && connected[6'o54] ? (64'b1<<6'o54) : 0) |
                (light_request ? (64'b1<<6'o55) : 0) |
                (connected[6'o41] && !(|(missed_latch|inability_latch)) &&
                 (|(new_missed|new_inability)) ? (64'b1<<6'o41) : 0);

    integer i;
    always @* begin
        available=external_ready & ~generic_busy;
        available[6'o52]=tape_full;
        available[6'o66]=!writer_full;
        available[6'o41]=1;
        available[6'o42]=0;available[6'o55]=0;available[6'o75]=0;
        // H63 timer p107: last 16 counts at 1 MHz; end carry interval at
        // 100/10 kHz and external. A stopped counter always permits loading.
        available[6'o54]=!timer_running || (timer_fast ? timer_count>18'd16 : timer_count>18'd1);
        available[6'o56]=!scope_full[0] && scope_ready[0];
        available[6'o60]=!scope_full[1] && !camera_busy && scope_ready[1];
    end
    wire [63:0] input_units=external_input | (64'b1<<6'o52);
    wire [63:0] output_ready=available & connected & ~input_units;
    assign flag_raise=(((available & connected & input_units) |
                        (output_ready & ~previous_output_ready)) &
                       64'hffffffff00000001 & ~((64'b1<<6'o41)|(64'b1<<6'o54)|(64'b1<<6'o75))) | event_requests;
    assign transfer_ready=connected[transfer_unit] && available[transfer_unit];
    assign transfer_input=transfer_unit==6'o52 || transfer_unit==6'o41 ||
                           (!builtin_units[transfer_unit] && external_input[transfer_unit]);
    assign transfer_assembly=transfer_unit==6'o52 ? mode[6'o52][1] :
                             (!builtin_units[transfer_unit] && external_assembly[transfer_unit]);
    assign transfer_assembly_width=transfer_unit==6'o52 ? 4'd6 : external_assembly_width;
    assign transfer_reverse=!builtin_units[transfer_unit] && external_reverse[transfer_unit];
    assign input_data=transfer_unit==6'o52 ? {30'b0,tape_buffer} :
                       transfer_unit==6'o41 ? alarm_report : external_data;
    assign input_mask=transfer_unit==6'o52 ? 36'o77 : transfer_unit==6'o41 ? 36'o777 : external_mask;
    // Free-running: a full PETR buffer never backpressures the physical tape.
    assign tape_ready=connected[6'o52] && mode[6'o52][6] && !tape_rewind && !tape_stop_unit;
    assign writer_valid=writer_full;
    assign writer_data=writer_buffer;
    assign external_valid=transfer_valid && connected[transfer_unit] &&
                          !builtin_units[transfer_unit] && external_present[transfer_unit];
    assign external_control_valid=control_valid && !control_error &&
                    !builtin_units[control_unit] && external_present[control_unit];
    assign external_control_unit=control_unit;
    assign external_control_command=control_command;
    assign external_unit=transfer_unit;
    assign external_write_data=transfer_data;
    reg [35:0] alarm_report;
    always @* begin
        alarm_report=0;
        alarm_report[0]=missed_latch[6'o50];alarm_report[1]=missed_latch[6'o52];
        alarm_report[2]=missed_latch[6'o46];alarm_report[3]=inability_latch[6'o46];
        alarm_report[4]=inability_latch[6'o60];alarm_report[5]=inability_latch[6'o63];
        alarm_report[6]=inability_latch[6'o51];
        alarm_report[7]=inability_latch[6'o65]|inability_latch[6'o66];
        alarm_report[8]=inability_latch[6'o71]|inability_latch[6'o72];
    end
    always @* begin
        report={12'b0,control_unit,18'b0} | {24'b0,mode[control_unit]};
        if(!builtin_units[control_unit]) report[35:24]=external_special[11:0];
        report[12]=missed_latch[control_unit];report[13]=inability_latch[control_unit];
        report[14]=connected[control_unit];report[15]=external_maintenance[control_unit];
        report[16]=available[control_unit];
        report[17]=flags[control_unit] | flag_raise[control_unit];
    end
    // Report bits 3.7..4.9 occupy twelve positions, 24..35. The
    // historical interface reserved 15; high three bits have no 36-bit slot.
    wire unused_special=|external_special[14:12];
    always @(posedge clk) begin
        if (reset) begin
            connected<=0;previous_output_ready<=0;tape_full<=0;writer_full<=0;
            tape_buffer<=0;writer_buffer<=0;
            generic_busy<=0;tape_rewind<=0;
            timer_buffer<=0;timer_count<=0;timer_pulse<=0;timer_running<=0;
            scope_full<=0;scope_started<=0;camera_busy<=0;
            scope_buffer[0]<=0;scope_buffer[1]<=0;scope_time[0]<=0;scope_time[1]<=0;
            missed_latch<=0;inability_latch<=0;
            for(i=0;i<64;i=i+1) mode[i]<=0;
        end else begin
            generic_busy<=0;previous_output_ready<=output_ready;
            tape_rewind<=0;timer_pulse<=0;
            missed_latch<=(missed_latch | new_missed) & ~external_clear_alarms;
            inability_latch<=(inability_latch | new_inability) & ~external_clear_alarms;
            if(timer_tick) begin
                if(!timer_running) timer_count<=timer_buffer;
                else if(timer_count==1) begin timer_count<=timer_buffer;timer_pulse<=1;end
                // [INFERENCE] Zero has no documented special interval;
                // retain the natural 18-bit wrap.
                else timer_count<=timer_count-18'd1;
            end
            if(camera_done) camera_busy<=0;
            if(camera_manual_index) camera_busy<=1;
            if(display_valid && display_ready) begin
                scope_started[scope_select]<=1;
                scope_time[scope_select]<=7'd10 << display_intensity;
            end
            for(i=0;i<2;i=i+1) begin
                if(scope_full[i] && scope_started[i] && tick_1us) begin
                    if(scope_time[i]<=1) begin scope_full[i]<=0;scope_started[i]<=0;end
                    else scope_time[i]<=scope_time[i]-7'd1;
                end
            end
            if(writer_valid && writer_ready) writer_full<=0;
            if(transfer_valid && transfer_ready) begin
                if(transfer_unit==6'o52) tape_full<=0;
                else if(transfer_unit==6'o66) begin writer_buffer<=transfer_data[5:0];writer_full<=1;end
                else if(transfer_unit==6'o54) begin
                    timer_buffer<=transfer_data[17:0];
                    if(!timer_running) timer_count<=transfer_data[17:0];
                end else if(transfer_unit==6'o56) begin
                    scope_buffer[0]<=transfer_data;scope_full[0]<=1;scope_started[0]<=0;
                end else if(transfer_unit==6'o60) begin
                    scope_buffer[1]<=transfer_data;scope_full[1]<=1;scope_started[1]<=0;
                end else generic_busy[transfer_unit]<=1;
            end
            // An arrival concurrent with a TSD leaves the new datum available.
            if(tape_valid && connected[6'o52]) begin tape_buffer<=tape_data;tape_full<=1;end
            if(control_valid && !control_error) begin
                case(control_command[14:12])
                    2: begin connected[control_unit]<=0;
                        missed_latch[control_unit]<=0;inability_latch[control_unit]<=0;
                    end
                    3: begin
                        connected[control_unit]<=1;
                        // Tape clear-error is an action bit, not a retained mode.
                        if(control_unit!=6'o46 || control_command!=18'o34000)
                            mode[control_unit]<=control_unit==6'o46 ? (control_command[11:0] & ~12'o4000) : control_command[11:0];
                        if(control_unit==6'o60 && control_command[2]) camera_busy<=1;
                        if(control_unit==6'o54) timer_running<=control_command[6];
                        if(control_unit==6'o52) begin
                            if(!connected[6'o52]) missed_latch[6'o52]<=0;
                            if(control_command[6] && control_command[2]) tape_rewind<=1;
                        end
                    end
                    // Select has no connection or mode side effects; see H63 4-7.
                    default: begin end
                endcase
            end
            if(tape_manual_disconnect) begin
                connected[6'o52]<=0;missed_latch[6'o52]<=0;inability_latch[6'o52]<=0;
            end
            // Manual controls override program controls, H63 timer p107.
            if(timer_manual_load) begin timer_buffer<=timer_manual_interval;timer_count<=timer_manual_interval;end
            if(timer_manual_start) timer_running<=1;
            if(timer_manual_stop) timer_running<=0;
        end
    end
endmodule
`default_nettype wire
