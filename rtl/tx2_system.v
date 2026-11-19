`timescale 1ns/1ps
`default_nettype none
// Host loads/inspects RAM while the core is stopped. Ownership is retained
// across each memory transaction, including the response on a fault boundary.
module tx2_system (
    input wire clk,
    input wire reset,
    input wire start,
    input wire [16:0] start_address,
    output wire running,
    output wire [3:0] overflow_flags,
    output wire [3:0] fault,
    input wire host_request,
    input wire host_write,
    input wire [16:0] host_address,
    input wire [35:0] host_write_data,
    output wire host_ready,
    output wire [35:0] host_read_data,
    output wire [1:0] host_error,
    output wire retire,
    output wire [16:0] retire_address,
    output wire [35:0] retire_instruction,
    output wire [16:0] program_counter,
    output wire [16:0] operand_address,
    output wire [35:0] a, b, c, d, e,
    input wire [5:0] debug_index_address,
    output wire [17:0] debug_index_data,
    input wire [4:0] debug_configuration_address,
    output wire [8:0] debug_configuration_data
);
    wire unused_data_write_enable,unused_meta_write_enable,unused_meta_write_value,unused_read_set_meta;
    wire [9:0] unused_alarms;
    wire unused_device_preset;
    wire unused_read_meta,unused_read_parity,unused_parity_error;
    wire cpu_request, cpu_write, ram_ready;
    wire [16:0] cpu_address;
    wire [35:0] cpu_write_data, ram_read_data;
    wire [1:0] ram_error;
    reg owner_active, owner_cpu;
    wire [63:0] unused_flags;
    wire [5:0] unused_sequence, unused_retire_sequence, unused_control_unit, unused_transfer_unit;
    wire unused_limbo, unused_control_valid, unused_transfer_valid;
    wire [17:0] unused_control_command;
    wire [35:0] unused_transfer_data;
    wire select_cpu = owner_active ? owner_cpu : running;
    wire request = select_cpu ? cpu_request : host_request;
    always @(posedge clk) begin
        if (reset) begin owner_active <= 0; owner_cpu <= 0; end
        else if (owner_active) begin
            if (ram_ready) owner_active <= 0;
        end else if (request && !ram_ready) begin
            owner_active <= 1; owner_cpu <= select_cpu;
        end
    end
    tx2_core #(.EXTENDED(0)) core (
        .clk(clk), .reset(reset), .start(start && !owner_active && !host_request),
        .start_address(start_address), .running(running), .fault(fault),
        .memory_request(cpu_request), .memory_write(cpu_write),
        .memory_address(cpu_address), .memory_write_data(cpu_write_data),
        .memory_ready(owner_active && owner_cpu && ram_ready),
        
        .memory_read_meta(1'b0),.memory_read_parity(1'b0),.memory_parity_error(1'b0),
        .memory_data_write_enable(unused_data_write_enable),.memory_meta_write_enable(unused_meta_write_enable),
        .memory_meta_write_value(unused_meta_write_value),.memory_read_set_meta(unused_read_set_meta),
        .trap_mode(9'b0),.trap_set_enable(1'b0),.sync_trap(1'b0),.alarm_suppress(10'b0),
        .clear_alarms(1'b0),.io_control_error(1'b0),.io_missed_alarm(1'b0),.io_missed_suppress(1'b0),.alarms(unused_alarms),.device_preset(unused_device_preset),
        .console_stop(1'b0),.console_continue(1'b0),.console_preset(1'b0),.console_startover(1'b0),
        .console_reset_start(1'b0),.console_hold(1'b0),.io_software_unit(1'b0),
        .memory_read_data(ram_read_data), .memory_error(ram_error),
        .retire(retire), .retire_address(retire_address),
        .retire_instruction(retire_instruction), .program_counter(program_counter),
        .operand_address(operand_address), .overflow_flags(overflow_flags),.a(a), .b(b), .c(c), .d(d), .e(e),
        .debug_index_address(debug_index_address), .debug_index_data(debug_index_data),
        .debug_configuration_address(debug_configuration_address),
        .debug_configuration_data(debug_configuration_data),
        .priority_map(384'b0), .io_flag_raise(64'b0), .sequence_flags(unused_flags),
        .current_sequence(unused_sequence), .retire_sequence(unused_retire_sequence),
        .limbo(unused_limbo), .io_control_valid(unused_control_valid),
        .io_control_unit(unused_control_unit), .io_control_command(unused_control_command),
        .io_report(36'b0), .io_transfer_valid(unused_transfer_valid),
        .io_transfer_unit(unused_transfer_unit), .io_transfer_data(unused_transfer_data),
        .io_transfer_ready(1'b0), .io_transfer_input(1'b0), .io_transfer_assembly(1'b0),
        .io_transfer_assembly_width(4'd6),
        .io_transfer_reverse(1'b0), .io_input_data(36'b0), .io_input_mask(36'b0)
    );
    tx2_memory #(.EXTENDED(0)) memory (
        .clk(clk), .reset(reset), .request(request),
        .write_enable(select_cpu ? cpu_write : host_write),
        .address(select_cpu ? cpu_address : host_address),
        .write_data(select_cpu ? cpu_write_data : host_write_data),
        .data_write_enable(1'b1),.meta_write_enable(1'b0),.meta_write_value(1'b0),.read_set_meta(1'b0),
        .read_meta(unused_read_meta),.read_parity(unused_read_parity),.parity_error(unused_parity_error),
        .clock_tick(1'b0),.clock_clear(1'b0),.knob_data(36'b0),.external_register_data(36'b0),
        .knob_meta(1'b0),.external_register_meta(1'b0),.console_switches(288'b0),.panel_data(576'b0),.panel_meta(16'b0),
        .ready(ram_ready), .read_data(ram_read_data), .error(ram_error)
    );
    assign host_ready = owner_active && !owner_cpu && ram_ready;
    assign host_read_data = ram_read_data;
    assign host_error = ram_error;
endmodule
`default_nettype wire
