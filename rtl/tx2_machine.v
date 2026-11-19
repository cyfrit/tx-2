`timescale 1ns/1ps
`default_nettype none
module tx2_machine #(
    parameter [383:0] PRIORITY_MAP=384'b0
) (
    input wire clk, reset, start,
    input wire console_stop,console_continue,console_preset,console_startover,console_reset_start,console_hold,
    input wire [9:0] alarm_suppress,
    input wire clear_alarms,trap_set_enable,sync_trap,
    input wire sync_trap_mode,
    output wire [9:0] alarms,
    input wire tick_1us,tick_10us,timer_tick,clock_clear,
    input wire timer_fast,timer_manual_start,timer_manual_stop,timer_manual_load,
    input wire [17:0] timer_manual_interval,
    output wire timer_end_carry,
    input wire tape_manual_disconnect,
    input wire camera_manual_index,
    input wire [1:0] scope_ready,
    input wire [35:0] knob_data,external_register_data,
    input wire knob_meta,external_register_meta,
    input wire [287:0] console_switches,
    input wire [575:0] panel_data,
    input wire [15:0] panel_meta,
    input wire host_meta_write,host_meta_value,
    output wire host_read_meta,host_read_parity,
    input wire light_pen_hit,camera_done,camera_alarm,display_ready,
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
    input wire [16:0] start_address,
    output wire running,
    output wire [3:0] overflow_flags,
    output wire [3:0] fault,
    input wire host_request, host_write,
    input wire [16:0] host_address,
    input wire [35:0] host_write_data,
    output wire host_ready,
    output wire [35:0] host_read_data,
    output wire [1:0] host_error,
    output wire retire,
    output wire [16:0] retire_address,
    output wire [35:0] retire_instruction,
    output wire [5:0] retire_sequence, current_sequence,
    output wire [63:0] sequence_flags,
    output wire limbo,
    output wire [16:0] program_counter, operand_address,
    output wire [35:0] a,b,c,d,e,
    input wire [5:0] debug_index_address,
    output wire [17:0] debug_index_data,
    input wire [4:0] debug_configuration_address,
    output wire [8:0] debug_configuration_data,
    input wire tape_valid,
    input wire [5:0] tape_data,
    output wire tape_ready, tape_rewind,
    output wire writer_valid,
    output wire [5:0] writer_data,
    input wire writer_ready,
    input wire [63:0] external_ready, external_input,
    input wire [35:0] external_data, external_mask,
    output wire external_valid,
    output wire [5:0] external_unit,
    output wire [35:0] external_write_data
);
    wire cpu_request,cpu_write,ram_ready,device_preset;
    wire cpu_data_write,cpu_meta_write,cpu_meta_value,cpu_read_set_meta;
    wire ram_meta,ram_parity,ram_parity_error,io_control_error,io_software_unit,io_missed_alarm,io_missed_suppress;
    wire [11:0] unused_trap_mode;
    wire [9:0] core_alarms;
    assign alarms=core_alarms;
    assign host_read_meta=ram_meta;assign host_read_parity=ram_parity;
    wire [16:0] cpu_address;
    wire [35:0] cpu_write_data,ram_read_data;
    wire [1:0] ram_error;
    reg owner_active,owner_cpu;
    wire select_cpu=owner_active ? owner_cpu : running;
    wire request=select_cpu ? cpu_request : host_request;
    wire io_control_valid,io_transfer_valid,io_transfer_ready;
    wire [5:0] io_control_unit,io_transfer_unit;
    wire [17:0] io_control_command;
    wire [35:0] io_report,io_transfer_data,io_input_data,io_input_mask;
    wire io_transfer_input,io_transfer_assembly,io_transfer_reverse;
    wire [3:0] io_transfer_assembly_width;
    wire [63:0] io_flag_raise;
    always @(posedge clk) begin
        if(reset) begin owner_active<=0; owner_cpu<=0; end
        else if(owner_active) begin if(ram_ready) owner_active<=0; end
        else if(request && !ram_ready) begin owner_active<=1; owner_cpu<=select_cpu; end
    end
    tx2_core core (
        .clk(clk),.reset(reset),.start(start && (running || (!owner_active && !host_request))),
        .start_address(start_address),.running(running),.fault(fault),
        .memory_request(cpu_request),.memory_write(cpu_write),.memory_address(cpu_address),
        .memory_write_data(cpu_write_data),.memory_ready(owner_active && owner_cpu && ram_ready),
        .memory_read_meta(ram_meta),.memory_read_parity(ram_parity),.memory_parity_error(ram_parity_error),
        .memory_data_write_enable(cpu_data_write),.memory_meta_write_enable(cpu_meta_write),
        .memory_meta_write_value(cpu_meta_value),.memory_read_set_meta(cpu_read_set_meta),
        // H63 unit42 manual Sync-to-Trap overrides encounter traps, while
        // metabit-setting controls remain effective.
        .trap_mode(unused_trap_mode[8:0] & (sync_trap_mode ? 9'o700 : 9'o777)),.trap_set_enable(trap_set_enable),.sync_trap(sync_trap),
        .alarm_suppress(alarm_suppress),.clear_alarms(clear_alarms),.io_control_error(io_control_error),.io_missed_alarm(io_missed_alarm),.io_missed_suppress(io_missed_suppress),.alarms(core_alarms),.device_preset(device_preset),
        .console_stop(console_stop),.console_continue(console_continue),.console_preset(console_preset),
        .console_startover(console_startover),.console_reset_start(console_reset_start),.console_hold(console_hold),
        .io_software_unit(io_software_unit),
        .memory_read_data(ram_read_data),.memory_error(ram_error),
        .retire(retire),.retire_address(retire_address),.retire_instruction(retire_instruction),
        .program_counter(program_counter),.operand_address(operand_address),
        .overflow_flags(overflow_flags),.a(a),.b(b),.c(c),.d(d),.e(e),
        .debug_index_address(debug_index_address),.debug_index_data(debug_index_data),
        .debug_configuration_address(debug_configuration_address),.debug_configuration_data(debug_configuration_data),
        .priority_map(PRIORITY_MAP),.io_flag_raise(io_flag_raise),.sequence_flags(sequence_flags),
        .current_sequence(current_sequence),.retire_sequence(retire_sequence),.limbo(limbo),
        .io_control_valid(io_control_valid),.io_control_unit(io_control_unit),.io_control_command(io_control_command),
        .io_report(io_report),.io_transfer_valid(io_transfer_valid),.io_transfer_unit(io_transfer_unit),
        .io_transfer_data(io_transfer_data),.io_transfer_ready(io_transfer_ready),
        .io_transfer_input(io_transfer_input),.io_transfer_assembly(io_transfer_assembly),
        .io_transfer_assembly_width(io_transfer_assembly_width),
        .io_transfer_reverse(io_transfer_reverse),.io_input_data(io_input_data),.io_input_mask(io_input_mask)
    );
    tx2_io devices (
        .clk(clk),.reset(reset || device_preset || (console_preset && !running)),.control_valid(io_control_valid),
        .tick_1us(tick_1us),.timer_tick(timer_tick),.light_pen_hit(light_pen_hit),
        .timer_fast(timer_fast),.timer_manual_start(timer_manual_start),.timer_manual_stop(timer_manual_stop),
        .timer_manual_load(timer_manual_load),.timer_manual_interval(timer_manual_interval),.timer_end_carry(timer_end_carry),
        .tape_manual_disconnect(tape_manual_disconnect),.tape_stop_unit(!running),
        .camera_done(camera_done),.camera_alarm(camera_alarm),.display_ready(display_ready),
        .camera_manual_index(camera_manual_index),
        .scope_ready(scope_ready),
        .display_valid(display_valid),.display_unit(display_unit),.display_x(display_x),.display_y(display_y),
        .display_word(display_word),.display_intensity(display_intensity),.camera_request(camera_request),
        .pen_lit(pen_lit),.pen_x(pen_x),.pen_y(pen_y),
        .external_assembly(external_assembly),.external_reverse(external_reverse),
        .external_clear_alarms(external_clear_alarms),.external_maintenance(external_maintenance),
        .external_special(external_special),.external_assembly_width(external_assembly_width),
        .external_control_valid(external_control_valid),.external_control_unit(external_control_unit),
        .external_control_command(external_control_command),.external_present(external_present),.external_missed(external_missed),.external_inability(external_inability),
        .control_error(io_control_error),.software_unit(io_software_unit),.trap_mode(unused_trap_mode),.missed_alarm(io_missed_alarm),.missed_suppress(io_missed_suppress),.control_unit(io_control_unit),
        .control_command(io_control_command),.flags(sequence_flags),.report(io_report),
        .transfer_valid(io_transfer_valid),.transfer_unit(io_transfer_unit),.transfer_data(io_transfer_data),
        .transfer_ready(io_transfer_ready),.transfer_input(io_transfer_input),
        .transfer_assembly(io_transfer_assembly),.transfer_reverse(io_transfer_reverse),
        .transfer_assembly_width(io_transfer_assembly_width),
        .input_data(io_input_data),.input_mask(io_input_mask),.flag_raise(io_flag_raise),
        .tape_valid(tape_valid),.tape_data(tape_data),.tape_ready(tape_ready),.tape_rewind(tape_rewind),
        .writer_valid(writer_valid),.writer_data(writer_data),.writer_ready(writer_ready),
        .external_ready(external_ready),.external_input(external_input),
        .external_data(external_data),.external_mask(external_mask),.external_valid(external_valid),
        .external_unit(external_unit),.external_write_data(external_write_data)
    );
    tx2_memory memory (
        .clk(clk),.reset(reset),.request(request),.write_enable(select_cpu ? cpu_write : host_write),
        .address(select_cpu ? cpu_address : host_address),.write_data(select_cpu ? cpu_write_data : host_write_data),
        .data_write_enable(select_cpu ? cpu_data_write : host_write),
        .meta_write_enable(select_cpu ? cpu_meta_write : host_meta_write),
        .meta_write_value(select_cpu ? cpu_meta_value : host_meta_value),
        .read_set_meta(select_cpu && cpu_read_set_meta),.read_meta(ram_meta),.read_parity(ram_parity),.parity_error(ram_parity_error),
        .clock_tick(tick_10us),.clock_clear(clock_clear),.knob_data(knob_data),.external_register_data(external_register_data),
        .knob_meta(knob_meta),.external_register_meta(external_register_meta),.console_switches(console_switches),.panel_data(panel_data),.panel_meta(panel_meta),
        .ready(ram_ready),.read_data(ram_read_data),.error(ram_error)
    );
    assign host_ready=owner_active && !owner_cpu && ram_ready;
    assign host_read_data=ram_read_data;
    assign host_error=ram_error;
endmodule
`default_nettype wire
