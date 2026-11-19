`timescale 1ns/1ps
`default_nettype none
// Serial TX-2 machine: 50 named opcode numbers, 33 sequences, Exchange
// Element, Arithmetic Element, IOS/TSD, meta traps and digital alarm controls.
// EXTENDED=0 preserves the original 19-opcode regression profile.
// Technical Manual vol.1 2-3; vol.2 9-7,12-6; vol.3 LD-/TSD timing.
// Memory interface: request held until ready; one ready pulse per transaction.
// No synthetic HLT: undefined instructions stop with fault=1, do not retire.
// Faults 2..6 describe unsupported mode/address/read-only/internal/opcode diagnostics,
// not a complete implementation of the original alarm panel.
module tx2_core #(
    parameter EXTENDED = 1
) (
    input wire clk,
    input wire reset,
    input wire start,
    input wire [16:0] start_address,
    output wire running,
    output reg [3:0] fault,
    output reg memory_request,
    output reg memory_write,
    output reg [16:0] memory_address,
    output wire [35:0] memory_write_data,
    input wire memory_ready,
    input wire [35:0] memory_read_data,
    input wire [1:0] memory_error,
    input wire memory_read_meta, memory_read_parity, memory_parity_error,
    output wire memory_data_write_enable, memory_meta_write_enable, memory_meta_write_value,
    output wire memory_read_set_meta,
    input wire [8:0] trap_mode,
    input wire trap_set_enable, sync_trap,
    input wire [9:0] alarm_suppress,
    input wire clear_alarms, io_control_error,io_missed_alarm,io_missed_suppress,
    output reg [9:0] alarms,
    output reg device_preset,
    input wire console_stop, console_continue, console_preset, console_startover, console_reset_start,
    input wire console_hold,

    output reg retire,
    output reg [16:0] retire_address,
    output wire [35:0] retire_instruction,
    output wire [16:0] program_counter,
    output wire [16:0] operand_address,
    output reg [35:0] a,
    output reg [35:0] b,
    output reg [35:0] c,
    output reg [35:0] d,
    output reg [35:0] e,
    output wire [3:0] overflow_flags,
    input wire [5:0] debug_index_address,
    output wire [17:0] debug_index_data,
    input wire [4:0] debug_configuration_address,
    output wire [8:0] debug_configuration_data,
    input wire [383:0] priority_map,
    input wire [63:0] io_flag_raise,
    output wire [63:0] sequence_flags,
    output wire [5:0] current_sequence,
    output reg [5:0] retire_sequence,
    output wire limbo,
    output wire io_control_valid,
    output wire [5:0] io_control_unit,
    output wire [17:0] io_control_command,
    input wire [35:0] io_report,
    output wire io_transfer_valid,
    output wire [5:0] io_transfer_unit,
    output wire [35:0] io_transfer_data,
    input wire io_transfer_ready,
    input wire io_software_unit,
    input wire io_transfer_input,
    input wire io_transfer_assembly,
    input wire io_transfer_reverse,
    input wire [3:0] io_transfer_assembly_width,
    input wire [35:0] io_input_data,
    input wire [35:0] io_input_mask
);
    localparam [3:0] STOPPED=0, FETCH=1, DECODE=2, DEFERRED=3, RESOLVE=4,
                     READ_OPERAND=5, EXECUTE=6, WRITE_OPERAND=7,
                     WRITE_CONFIGURATION=8, COMMIT=9, FAULTED=10,
                     IO_TRANSFER=11, DISPATCH=12, WAIT_SEQUENCE=13, ALU_WAIT=14;
    reg [3:0] state;
    reg [16:0] p, q, instruction_address, address_work, effective_address;
    reg [35:0] instruction, m, store_value;
    reg [17:0] x_memory [0:63];
    reg [8:0] f_memory [0:31];
    reg x_parity [0:63],f_parity [0:31];
    task automatic write_x;
        input [5:0] address;
        input [17:0] value;
        begin if(address!=0) begin x_memory[address]<=value;x_parity[address]<=~^value;end end
    endtask
    task automatic write_f;
        input [4:0] address;
        input [8:0] value;
        begin if(address!=0) begin f_memory[address]<=value;f_parity[address]<=~^value;end end
    endtask
    reg [5:0] final_index;
    reg [3:0] z;
    reg [35:0] pending_load;
    reg [1:0] f_offset;
    reg [63:0] flags;
    reg [5:0] k;
    reg current_live;
    reg [16:0] toggle_start;
    integer i;

    wire instruction_held, deferred;
    wire unused_trap_reserved=|trap_mode[5:4];
    wire held=instruction_held | (EXTENDED && console_hold);
    reg stopped,stop_pending,missed_pending,restart_pending;
    reg [16:0] restart_address;
    reg [3:0] resume_state;
    reg meta_operand,parity_operand,trap_sequence_pending;
    reg [4:0] register_meta;
    wire [4:0] cf;
    wire [5:0] opcode, j;
    wire [16:0] decoded_address;
    tx2_instruction_decode instruction_decoder (
        .instruction(instruction), .hold(instruction_held), .configuration(cf),
        .opcode(opcode), .index(j), .defer(deferred), .address(decoded_address)
    );
    wire [17:0] xj = (j == 0) ? 18'b0 : x_memory[j];
    wire [8:0] config_value = (cf == 0) ? 9'b0 : f_memory[cf];
    wire is_load = opcode == 6'o20 || (opcode >= 6'o24 && opcode <= 6'o27);
    wire is_store = opcode == 6'o30 || (opcode >= 6'o34 && opcode <= 6'o37);
    wire is_index_memory = opcode == 6'o10 || opcode == 6'o11 || opcode == 6'o16 ||
                           (EXTENDED && (opcode==6'o14 || opcode==6'o15));
    wire is_arithmetic=opcode>=6'o60 && opcode!=6'o63 && opcode!=6'o73;
    wire aop=opcode==6'o04 && effective_address[16:15]==2'b01;
    wire valid_aop=effective_address[14:9]>=6'o60 && effective_address[14:9]!=6'o63 && effective_address[14:9]!=6'o73;
    wire is_loop = opcode == 6'o06 || opcode == 6'o07;
    wire supported = is_load || is_store || is_index_memory || is_loop ||
                     opcode == 6'o05 || opcode == 6'o12 ||
                     opcode == 6'o21 || opcode == 6'o22 ||
                     (EXTENDED && (opcode==6'o04 || opcode==6'o17 ||
                                   opcode==6'o31 || opcode==6'o32 ||
                                   (opcode>=6'o40 && opcode<=6'o47 && opcode!=6'o44) ||
                                   (opcode>=6'o54 && opcode<=6'o57) || is_arithmetic));
    wire undefined_opcode = opcode <= 6'o03 || opcode == 6'o13 || opcode == 6'o23 ||
                            opcode == 6'o33 || opcode == 6'o44 ||
                            (opcode >= 6'o50 && opcode <= 6'o53) ||
                            opcode == 6'o63 || opcode == 6'o73;
    wire pointer_parity_error=EXTENDED && bus_data[23:18]!=0 &&
                  !(^{x_parity[bus_data[23:18]],x_memory[bus_data[23:18]]});
    wire selected_parity_error=EXTENDED && selected_sequence!=0 &&
                  !(^{x_parity[selected_sequence],x_memory[selected_sequence]});
    wire index_parity_error=EXTENDED && j!=0 && !(^{x_parity[j],xj});
    wire uses_configuration=is_load || is_store || is_index_memory || is_arithmetic ||
                     opcode==6'o40 || opcode==6'o41 || opcode==6'o42 || opcode==6'o43 ||
                     opcode==6'o54 || opcode==6'o55 || opcode==6'o56 || opcode==6'o57;
    wire config_parity_error=EXTENDED && uses_configuration && cf!=0 && !(^{f_parity[cf],config_value});
    wire xj_zero = xj == 18'o000000 || xj == 18'o777777;
    wire jump_taken = !xj_zero && ((opcode == 6'o06 && !xj[17]) ||
                                                (opcode == 6'o07 && xj[17]));

    function automatic [16:0] index_address;
        input [16:0] base;
        input [17:0] delta;
        begin
            // Signed one's-complement index, physical address modulo 2^17.
            // Negative zero contributes zero. Vol.2 12-2.8: x + ~x -> +0
            // for address formation, rather than the last V-memory word.
            index_address = base + delta[16:0] + {16'b0,delta[17]};
        end
    endfunction
    function automatic [17:0] add_index;
        input [17:0] lhs, rhs;
        reg [18:0] sum;
        reg [17:0] folded;
        begin
            sum = {1'b0,lhs} + {1'b0,rhs};
            folded = sum[17:0] + {17'b0,sum[18]};
            add_index = folded;
        end
    endfunction
    wire [16:0] resolved = index_address(address_work,
                                   (final_index == 0) ? 18'b0 : x_memory[final_index]);
    wire [17:0] increment = {{13{cf[4]}},cf};
    wire [17:0] loop_sum = add_index(xj,increment);
    // Handbook 3-26 explicitly specifies minus zero for a zero loop sum.
    wire [17:0] loop_result = loop_sum == 0 ? 18'o777777 : loop_sum;
    wire [4:0] cf1=cf+5'd1,cf2=cf+5'd2,cf3=cf+5'd3;
    wire [4:0] f_target = cf + {3'b0,f_offset};
    wire selected_valid;
    wire [5:0] selected_sequence, selected_priority;
    wire [63:0] active_flags=(flags | (device_preset ? 64'b0 : io_flag_raise)) & 64'hffffffff00000001;
    tx2_sequence_selector selector (
        .flags(active_flags), .priority_map(priority_map),
        .valid(selected_valid), .selected(selected_sequence),
        .selected_priority(selected_priority)
    );
    wire [5:0] current_priority=priority_map[k*6 +: 6];
    wire select_other=selected_valid && (selected_sequence!=k) &&
                      (!current_live || selected_sequence==0 ||
                       (k!=0 && (selected_priority<current_priority ||
                         (selected_priority==current_priority && selected_sequence<k))));
    wire software_tsd=(EXTENDED && io_software_unit) || k==0 || k==6'o75 || k==6'o76;
    function automatic signed [18:0] signed_index;
        input [17:0] value;
        begin signed_index=value[17] ? -$signed({1'b0,~value}) : $signed({1'b0,value}); end
    endfunction
    wire [17:0] skx_operand={1'b0,effective_address};
    wire [17:0] skx_add=add_index(xj,skx_operand);
    wire [17:0] skx_sub=add_index(xj,~skx_operand);
    reg [17:0] skx_result;
    reg skx_skip;
    always @* begin
        skx_result=xj; skx_skip=0;
        case(cf[2:0])
            0: skx_result=skx_operand;
            1: skx_result=~skx_operand;
            2: skx_result=(skx_add==18'o777777 && xj==0) ? 18'b0 : skx_add;
            3: skx_result=skx_sub==0 ? 18'o777777 : skx_sub;
            4: begin skx_skip=signed_index(xj)!=signed_index(skx_operand); if(xj==0) skx_result=18'o777777; end
            5: begin skx_skip=signed_index(xj)!=-signed_index(skx_operand); if(xj==18'o777777) skx_result=0; end
            6: begin skx_skip=signed_index(xj)<signed_index(skx_operand) &&
                                signed_index(xj)-signed_index(skx_operand)>=-19'sd131071;
                     if(xj==0) skx_result=18'o777777; end
            7: begin skx_skip=signed_index(xj)>-signed_index(skx_operand) &&
                                signed_index(xj)+signed_index(skx_operand)<=19'sd131071;
                     if(xj==18'o777777) skx_result=0; end
        endcase
    end

    reg [35:0] skm_result;
    reg skm_skip, skm_bit;
    reg skm_meta;
    reg [5:0] skm_position;
    wire [1:0] skm_quarter=j[5:4]-2'd1;
    always @* begin
        skm_result=m; skm_meta=meta_operand; skm_bit=0; skm_skip=0; skm_position=0;
        if(j[3:0]>=1 && j[3:0]<=9) begin
            skm_position=6'd9*{4'b0,skm_quarter}+{2'b0,j[3:0]}-6'd1;
            skm_bit=m[skm_position];
            case(cf[1:0])
                1: skm_result[skm_position]=~skm_bit;
                2: skm_result[skm_position]=0;
                3: skm_result[skm_position]=1;
                default: begin end
            endcase
        end else if(j[3:0]==10) begin
            skm_bit=meta_operand;
            case(cf[1:0])
                1:skm_meta=~meta_operand;
                2:skm_meta=0;
                3:skm_meta=1;
                default:begin end
            endcase
        end else if(j[3:0]==11) skm_bit=parity_operand;
        else if(j[3:0]==12) skm_bit=~^{m,meta_operand};
        case(cf[4:3])
            1: skm_skip=1;
            2: skm_skip=(j[3:0]>=1 && j[3:0]<=12) && !skm_bit;
            3: skm_skip=(j[3:0]>=1 && j[3:0]<=12) && skm_bit;
            default: begin end
        endcase
        if(cf[2]) skm_result={skm_result[0],skm_result[35:1]};
    end

    // All CPU-register aliases are resolved here so self-load/store sees
    // the same A..E state as ordinary instructions; see Handbook 5-20.
    reg local_access,local_meta;
    reg [35:0] local_read_data;
    reg [16:0] bus_address;
    wire bus_phase = state == FETCH || state == DEFERRED ||
                     state == READ_OPERAND || state == WRITE_OPERAND;
    always @* begin
        case (state)
            FETCH: bus_address = p;
            DEFERRED: bus_address = address_work;
            default: bus_address = effective_address;
        endcase
        local_access = 1;local_meta=0;
        case (bus_address)
            17'o377604: begin local_read_data=a;local_meta=register_meta[0];end
            17'o377605: begin local_read_data=b;local_meta=register_meta[1];end
            17'o377606: begin local_read_data=c;local_meta=register_meta[2];end
            17'o377607: begin local_read_data=d;local_meta=register_meta[3];end
            17'o377610: begin local_read_data=e;local_meta=register_meta[4];end
            default: begin local_read_data = 0; local_access = 0; end
        endcase
        memory_request = bus_phase && !local_access && !stopped;
        memory_write = state == WRITE_OPERAND;
        memory_address = bus_address;
    end
    wire [2:0] register_meta_index=effective_address[2:0]-3'd4;
    wire bus_meta=local_access ? local_meta : memory_read_meta;
    wire bus_parity=local_access ? ~^{local_meta,local_read_data} : memory_read_parity;
    wire parity_alarm=EXTENDED && bus_phase && state!=WRITE_OPERAND && bus_ready &&
                       !local_access && memory_parity_error;
    wire [3:0] memory_alarm_index=bus_error!=0 ? (state==FETCH ? 4'd4 : 4'd5) :
                                              (state==READ_OPERAND ? 4'd0 : 4'd1);
    assign memory_data_write_enable=opcode!=6'o17 || cf[2] ||
                         (j[3:0]>=1 && j[3:0]<=9 && cf[1:0]!=0);
    assign memory_meta_write_enable=EXTENDED && state==WRITE_OPERAND && opcode==6'o17 && j[3:0]==10 && cf[1:0]!=0;
    assign memory_meta_write_value=skm_meta;
    assign memory_read_set_meta=EXTENDED && trap_set_enable &&
              ((state==FETCH && trap_mode[6]) || (state==DEFERRED && trap_mode[7]) ||
               (state==READ_OPERAND && trap_mode[8]));
    wire bus_ready = local_access || memory_ready;
    wire [35:0] bus_data = local_access ? local_read_data : memory_read_data;
    wire [1:0] bus_error = local_access ? 2'b0 : memory_error;

    reg [35:0] exchange_source, exchange_destination;
    wire exchange_store = is_store || opcode == 6'o16;
    wire [35:0] exchange_result;
    wire [3:0] unused_extended_activity;
    always @* begin
        exchange_source = m;
        exchange_destination = 0;
        case (opcode)
            6'o20: exchange_destination = e;
            6'o24: exchange_destination = a;
            6'o25: exchange_destination = b;
            6'o26: exchange_destination = c;
            6'o27: exchange_destination = d;
            6'o11: exchange_destination = {18'b0,xj};
            6'o43,6'o57,6'o40: exchange_destination=e;
            6'o54,6'o74: exchange_destination=a;
            6'o14: exchange_destination={18'b0,xj};
            6'o56: exchange_destination=permuted_memory;
            6'o60,6'o61,6'o62,6'o64,6'o65,6'o66,6'o67,
            6'o70,6'o71,6'o72,6'o75,6'o76,6'o77: exchange_destination=d;
            6'o30: begin exchange_source = e; exchange_destination = m; end
            6'o34: begin exchange_source = a; exchange_destination = m; end
            6'o35: begin exchange_source = b; exchange_destination = m; end
            6'o36: begin exchange_source = c; exchange_destination = m; end
            6'o37: begin exchange_source = d; exchange_destination = m; end
            6'o16: begin exchange_source = {{18{xj[17]}},xj}; exchange_destination = m; end
            default: begin end
        endcase
    end
    tx2_exchange exchanger (
        .source_word(exchange_source), .destination_word(exchange_destination),
        .configuration_word(config_value), .store_direction(exchange_store),
        .sign_extension(opcode!=6'o43 && opcode!=6'o57 && opcode!=6'o40), .result_word(exchange_result),
        .extended_activity(unused_extended_activity)
    );
    assign overflow_flags=z;
    wire [35:0] active_mask={{9{unused_extended_activity[3]}},{9{unused_extended_activity[2]}},
                              {9{unused_extended_activity[1]}},{9{unused_extended_activity[0]}}};
    wire [35:0] quarter_mask={{9{!config_value[6]}},{9{!config_value[5]}},
                               {9{!config_value[4]}},{9{!config_value[3]}}};
    wire [35:0] permuted_memory,exchange_write,insert_mask,insert_data;
    wire [3:0] unused_permute_activity,unused_write_activity,unused_mask_activity;
    wire [35:0] exchange_write_source=opcode==6'o14 ? {{18{xj[17]}},xj} :
                            opcode==6'o15 ? {exchange_result[35:18],add_index(xj,exchange_result[17:0])} : a;
    tx2_exchange permute_memory (
        .source_word(m),.destination_word(36'b0),
        .configuration_word({config_value[8:7],4'b0,config_value[2:0]}),
        .store_direction(1'b0),.sign_extension(1'b0),.result_word(permuted_memory),
        .extended_activity(unused_permute_activity)
    );
    tx2_exchange write_exchange (
        .source_word(exchange_write_source),.destination_word(m),.configuration_word(config_value),
        .store_direction(1'b1),.sign_extension(1'b0),.result_word(exchange_write),
        .extended_activity(unused_write_activity)
    );
    tx2_exchange mask_exchange (
        .source_word(b),.destination_word(36'b0),.configuration_word(config_value),
        .store_direction(1'b1),.sign_extension(1'b0),.result_word(insert_mask),
        .extended_activity(unused_mask_activity)
    );
    assign insert_data=(m & ~insert_mask) | (exchange_write & insert_mask);
    wire alu_start=EXTENDED && state==EXECUTE && (is_arithmetic || (aop && valid_aop));
    wire alu_done;
    wire [35:0] alu_a,alu_b,alu_c,alu_d;
    wire [3:0] alu_z;
    tx2_alu arithmetic (
        .clk(clk),.reset(reset),.start(alu_start),
        .opcode(aop ? effective_address[14:9] : opcode),
        .fracture(aop ? effective_address[8:7] : config_value[8:7]),
        .activity(aop ? ~effective_address[6:3] : unused_extended_activity),
        .a_in(!aop && opcode==6'o74 ? exchange_result : a),.b_in(b),.c_in(c),
        .d_in(!aop && opcode!=6'o74 ? exchange_result : d),.z_in(z),
        .done(alu_done),.a_out(alu_a),.b_out(alu_b),.c_out(alu_c),.d_out(alu_d),.z_out(alu_z)
    );
    // Conditional jumps test each subword of the current fracture. Jump when any
    // active subword passes: z for opcode 45, otherwise its sign against 47's
    // polarity, ignoring all-zero and all-one subwords. Subwords span quarters;
    // LAST holds the subword's sign. The function reads only its arguments,
    // ensuring that every simulator's @* has the full sensitivity.
    reg conditional_jump;
    wire jump_on_z=opcode==6'o45, jump_polarity=opcode==6'o47;
    function automatic jump_test;
        input [35:0] word, active;
        input [3:0] zero;
        input on_z, polarity;
        input [35:0] span;
        input [1:0] last;
        begin
            jump_test=|(active & span) &&
                      (on_z ? zero[last] :
                       (|(word & span)) && (|(~word & span)) && (word[{1'b0,last,3'b0}+{4'b0,last}+6'd8]==polarity));
        end
    endfunction
    always @* begin
        case(config_value[8:7])
            0: conditional_jump=jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o777777777777,2'd3);
            1: conditional_jump=jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o000000777777,2'd1) |
                                jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o777777000000,2'd3);
            2: conditional_jump=jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o000000000777,2'd0) |
                                jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o777777777000,2'd3);
            3: conditional_jump=jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o000000000777,2'd0) |
                                jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o000000777000,2'd1) |
                                jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o000777000000,2'd2) |
                                jump_test(a,quarter_mask,z,jump_on_z,jump_polarity,36'o777000000000,2'd3);
        endcase
    end
    wire [35:0] normal_input=(exchange_result & ~io_input_mask) | (io_input_data & io_input_mask);
    wire [35:0] normal_input_store;
    wire [3:0] unused_io_activity;
    tx2_exchange input_exchange (
        .source_word(normal_input), .destination_word(m), .configuration_word(config_value),
        .store_direction(1'b1), .sign_extension(1'b0),
        .result_word(normal_input_store), .extended_activity(unused_io_activity)
    );
    reg [35:0] assembly_input, assembly_output;
    reg [8:0] assembly_bits;
    integer io_bit;
    always @* begin
        assembly_input=io_transfer_reverse ? {m[0],m[35:1]} : {m[34:0],m[35]};
        assembly_output=assembly_input; assembly_bits=0;
        // H63 PETR/punch: six lanes at six-bit intervals. TM2 TX-2
        // magnetic tape: nine lanes at four-bit intervals; see 15-MAG-3.
        // [INFERENCE] The surviving manual specifies the four-bit interval but
        // not its phase; use each lane's low bit, matching the PETR convention.
        if(io_transfer_assembly_width==4'd9) begin
            for(io_bit=0;io_bit<9;io_bit=io_bit+1) begin
                if(io_transfer_reverse) begin
                    assembly_input[io_bit*4+3]=io_input_data[io_bit];
                    assembly_bits[io_bit]=m[io_bit*4];
                end else begin
                    assembly_input[io_bit*4]=io_input_data[io_bit];
                    assembly_bits[io_bit]=m[io_bit*4+3];
                end
            end
        end else begin
            for(io_bit=0;io_bit<6;io_bit=io_bit+1) begin
                if(io_transfer_reverse) begin
                    assembly_input[io_bit*6+5]=io_input_data[io_bit];
                    assembly_bits[io_bit]=m[io_bit*6];
                end else begin
                    assembly_input[io_bit*6]=io_input_data[io_bit];
                    assembly_bits[io_bit]=m[io_bit*6+5];
                end
            end
        end
    end
    assign io_control_valid=EXTENDED && state==EXECUTE && opcode==6'o04 && effective_address[16:15]==0;
    assign io_control_unit=j;
    assign io_control_command={1'b0,effective_address};
    assign io_transfer_valid=EXTENDED && state==IO_TRANSFER;
    assign io_transfer_unit=k;
    // H63 timer p108 scan says inactive portions are +0; OCR says 1.
    assign io_transfer_data=io_transfer_assembly ? {27'b0,assembly_bits} : (exchange_result & quarter_mask);
    assign sequence_flags=flags;
    assign current_sequence=k;
    assign limbo=state==WAIT_SEQUENCE;

    assign running = !stopped && state != STOPPED && state != FAULTED;
    assign program_counter = p;
    assign operand_address = q;
    assign memory_write_data = store_value;
    assign retire_instruction = instruction;
    assign debug_index_data = debug_index_address == 0 ? 18'b0 : x_memory[debug_index_address];
    assign debug_configuration_data = debug_configuration_address == 0 ? 9'b0 : f_memory[debug_configuration_address];

    always @(posedge clk) begin
        if (reset) begin
            state <= STOPPED;
            p <= 0; q <= 0; instruction_address <= 0;
            instruction <= 0; address_work <= 0; effective_address <= 0;
            m <= 0; store_value <= 0; final_index <= 0; f_offset <= 0;
            a <= 0; b <= 0; c <= 0; d <= 0; e <= 0; z<=0;pending_load<=0;
            retire <= 0; retire_address <= 0; fault <= 0;
            alarms<=0;device_preset<=0;restart_pending<=0;restart_address<=0;stopped<=0;stop_pending<=0;missed_pending<=0;resume_state<=DISPATCH;register_meta<=0;
            meta_operand<=0;parity_operand<=1;trap_sequence_pending<=0;
            flags<=0; k<=0; current_live<=0; toggle_start<=0; retire_sequence<=0;
            for (i=0; i<64; i=i+1) begin x_memory[i]<=0;x_parity[i]<=1;end
            for (i=0; i<32; i=i+1) begin f_memory[i]<=0;f_parity[i]<=1;end
        end else begin
            retire <= 0;device_preset<=0;
            if(EXTENDED && start) begin restart_pending<=1;restart_address<=start_address;end
            if(EXTENDED) begin
                flags<=active_flags;
                if(clear_alarms) alarms<=0;
                if(console_stop) stop_pending<=1;
                if(io_missed_alarm && !device_preset) begin alarms[8]<=1;if(!io_missed_suppress && !alarm_suppress[8]) missed_pending<=1;end
                if(sync_trap) flags[6'o42]<=1;
                if(console_reset_start || console_startover) toggle_start<=start_address;
                if(console_startover) flags[0]<=1;
                if(console_preset && !running) begin flags<=0;current_live<=0;resume_state<=DISPATCH;end
                if(bus_phase && bus_ready && state!=WRITE_OPERAND && bus_meta &&
                     ((state==FETCH && trap_mode[0]) || (state==DEFERRED && trap_mode[1]) ||
                      (state==READ_OPERAND && trap_mode[2]))) flags[6'o42]<=1;
                if((bus_phase && bus_ready && bus_error!=0) || parity_alarm)
                    alarms[memory_alarm_index]<=1;
            end
            if(EXTENDED && stopped) begin
                if(console_continue) begin stopped<=0;state<=resume_state;fault<=0;alarms<=0;end
                else if(start) begin stopped<=0;state<=FETCH;p<=start_address;k<=0;flags<=1;current_live<=1;toggle_start<=start_address;fault<=0;alarms<=0;stop_pending<=0;missed_pending<=0;restart_pending<=0;device_preset<=1;end
            end else if (bus_phase && bus_ready &&
                        ((bus_error != 0 && (!EXTENDED || !alarm_suppress[memory_alarm_index])) ||
                         (parity_alarm && !alarm_suppress[memory_alarm_index]))) begin
                fault <= parity_alarm ? 4'd7 : (bus_error == 2) ? 4'd4 : 4'd3;
                state <= FAULTED;resume_state<=state;
            end else case (state)
                STOPPED, FAULTED: if (start) begin
                    p <= start_address;
                    flags<=1;alarms<=0;stop_pending<=0;missed_pending<=0;restart_pending<=0;device_preset<=1;
                    k<=0; current_live<=1; toggle_start<=start_address;
                    fault <= 0;
                    state <= FETCH;
                end else if(EXTENDED && console_continue) begin state<=resume_state;fault<=0;alarms<=0;end
                FETCH: if (bus_ready) begin
                    instruction <= bus_data;
                    instruction_address <= p;
                    p <= p + 17'd1;
                    state <= DECODE;
                end
                DECODE: begin
                    if(EXTENDED && j!=0) x_parity[j]<=~^xj;
                    if(EXTENDED && uses_configuration && cf!=0) f_parity[cf]<=~^config_value;
                    if (!supported) begin
                        fault<=EXTENDED && alarm_suppress[6] ? 4'b0 : undefined_opcode ? 4'd1 : 4'd6;
                        if(EXTENDED) alarms[6]<=1;
                        state<=EXTENDED && alarm_suppress[6] ? COMMIT : FAULTED;
                        resume_state<=DECODE;
                    end
                    else if((index_parity_error && !alarm_suppress[2]) || (config_parity_error && !alarm_suppress[3])) begin
                        if(index_parity_error) alarms[2]<=1;
                        if(config_parity_error) alarms[3]<=1;
                        fault<=7;state<=FAULTED;resume_state<=DECODE;
                    end else if (!EXTENDED && ((opcode == 6'o12 && cf > 1) ||
                             (opcode == 6'o05 && cf[4] && !held))) begin
                        fault <= 2; state <= FAULTED;
                    end else begin
                        if(index_parity_error) alarms[2]<=1;
                        if(config_parity_error) alarms[3]<=1;
                        address_work <= decoded_address;
                        if (opcode == 6'o12 || opcode==6'o04 || opcode==6'o17 || is_loop || is_index_memory ||
                            (opcode == 6'o05 && !cf[0])) final_index <= 0;
                        else final_index <= j;
                        state <= deferred ? DEFERRED : RESOLVE;
                    end
                end
                DEFERRED: if (bus_ready) begin
                    if(EXTENDED && bus_data[23:18]!=0) x_parity[bus_data[23:18]]<=~^x_memory[bus_data[23:18]];
                    if(pointer_parity_error) alarms[2]<=1;
                    if(pointer_parity_error && !alarm_suppress[2]) begin
                        fault<=7;state<=FAULTED;resume_state<=DEFERRED;
                    end else begin
                    // Preserve original opcode/CF/J; each pointer has its own J.
                    q <= address_work;
                    address_work <= index_address(bus_data[16:0],
                        bus_data[23:18] == 0 ? 18'b0 : x_memory[bus_data[23:18]]);
                    state <= bus_data[17] ? DEFERRED : RESOLVE;
                    end
                end
                RESOLVE: begin
                    effective_address <= resolved;
                    if (opcode == 6'o05 || opcode == 6'o12 || opcode==6'o04 ||
                        opcode==6'o45 || opcode==6'o46 || opcode==6'o47 || is_loop) state <= EXECUTE;
                    else if(opcode==6'o57 && !software_tsd && !io_transfer_ready) begin
                        p<=instruction_address; current_live<=0; flags[k]<=0; state<=DISPATCH;
                    end
                    else begin q <= resolved; state <= READ_OPERAND; end
                end
                READ_OPERAND: if (bus_ready) begin m <= bus_data;meta_operand<=bus_meta;parity_operand<=bus_parity; state <= EXECUTE; end
                EXECUTE: begin
                    if(EXTENDED && is_arithmetic) begin e<=m;state<=ALU_WAIT;end
                    else if (is_load) begin
                        case (opcode)
                            6'o20: e <= exchange_result;
                            6'o24: a <= exchange_result;
                            6'o25: b <= exchange_result;
                            6'o26: c <= exchange_result;
                            6'o27: d <= exchange_result;
                            default: begin end
                        endcase
                        if (opcode != 6'o20) e <= m;
                        state <= COMMIT;
                    end else if (exchange_store) begin
                        store_value <= exchange_result;
                        state <= WRITE_OPERAND;
                    end else case (opcode)
                        6'o10, 6'o11: begin
                            write_x(j,opcode == 6'o10 ? add_index(xj,exchange_result[17:0]) : exchange_result[17:0]);
                            e <= m; state <= COMMIT;
                        end
                        6'o21, 6'o22: begin f_offset <= 0; e <= m; state <= WRITE_CONFIGURATION; end
                        6'o12: begin
                            if(!EXTENDED || !(cf==5'o30 && j==k)) begin
                                write_x(j,EXTENDED ? skx_result : (cf[0] ? ~{1'b0,effective_address} : {1'b0,effective_address}));
                                if(EXTENDED) begin
                                    if(skx_skip) p<=p+17'd1;
                                    if(cf[4] && !held) begin flags[k]<=0; current_live<=0; end
                                    if(cf[3] && (j==0 || j>=6'o40)) flags[j]<=1;
                                end
                            end
                            state <= COMMIT;
                        end
                        6'o05: begin
                            if (cf[3]) e[35:18] <= {1'b0,q};
                            if (cf[2]) e[17:0] <= {1'b0,p};
                            if(cf[1]) write_x(j,{1'b0,p});
                            p <= effective_address; state <= COMMIT;
                            if(EXTENDED && cf[4] && !held) begin flags[k]<=0; current_live<=0; end
                        end
                        6'o06, 6'o07: begin
                            if (!EXTENDED && jump_taken && !held) begin fault <= 2; state <= FAULTED; end
                            else begin
                                write_x(j,loop_result);
                                if (jump_taken) begin e[17:0] <= {1'b0,p}; p <= effective_address; end
                                if(EXTENDED && jump_taken && !held) begin flags[k]<=0; current_live<=0; end
                                state <= COMMIT;
                            end
                        end
                        6'o04: begin
                            if(aop && valid_aop) state<=ALU_WAIT;
                            else if(effective_address[16:15]!=0) begin
                                fault<=alarm_suppress[6] ? 4'b0 : 4'd2;alarms[6]<=1;state<=alarm_suppress[6] ? COMMIT : FAULTED;resume_state<=EXECUTE;
                            end else if(io_control_error) begin
                                alarms[7]<=1;fault<=alarm_suppress[7] ? 4'b0 : 4'd8;state<=alarm_suppress[7] ? COMMIT : FAULTED;resume_state<=EXECUTE;
                            end
                            else begin
                                if(cf[0]) e<=io_report;
                                if(cf[4] && !held) begin flags[k]<=0; current_live<=0; end
                                case(effective_address[14:12])
                                    4: flags[j]<=0;
                                    5: begin flags[j]<=1; if(j==k) current_live<=1; end
                                    default: begin end
                                endcase
                                state<=COMMIT;
                            end
                        end
                        6'o14,6'o15,6'o54: begin
                            pending_load<=exchange_result;store_value<=exchange_write;state<=WRITE_OPERAND;
                        end
                        6'o31,6'o32: begin
                            store_value<={m[35:9],(cf==0 ? 9'b0 : f_memory[cf])};
                            if(opcode==6'o32) begin
                                store_value[17:9]<=cf1==0 ? 9'b0 : f_memory[cf1];
                                store_value[26:18]<=cf2==0 ? 9'b0 : f_memory[cf2];
                                store_value[35:27]<=cf3==0 ? 9'b0 : f_memory[cf3];
                            end
                            state<=WRITE_OPERAND;
                        end
                        6'o40: begin e<=e & (exchange_result | ~quarter_mask);state<=COMMIT;end
                        6'o41,6'o42: begin
                            a<=(a & ~active_mask) | ((opcode==6'o41 ? a & exchange_result : a | exchange_result) & active_mask);
                            e<=m;state<=COMMIT;
                        end
                        6'o45,6'o46,6'o47: begin
                            if(conditional_jump) begin e[17:0]<={1'b0,p};p<=effective_address;end
                            state<=COMMIT;
                        end
                        6'o55: begin store_value<=insert_data;state<=WRITE_OPERAND;end
                        6'o56: begin store_value<=exchange_result ^ active_mask;state<=WRITE_OPERAND;end
                        6'o17: begin
                            if(skm_skip) p<=p+17'd1;
                            store_value<=skm_result;
                            state<=WRITE_OPERAND;
                        end
                        6'o43: begin if(exchange_result!=e) p<=p+17'd1; state<=COMMIT; end
                        6'o57: begin
                            if(software_tsd) begin
                                // H63 4-9/unit75: E acts as CLDE, memory is
                                // not cycled and no physical output changes.
                                if(k==6'o75) begin e<=m;state<=COMMIT;end
                                else begin store_value<={m[34:0],m[35]};state<=WRITE_OPERAND;end
                                if(!held) begin flags[k]<=0;current_live<=0;end
                            end
                            else state<=IO_TRANSFER;
                        end
                        default: begin fault <= 1; state <= FAULTED; end
                    endcase
                end
                WRITE_OPERAND: if (bus_ready) begin
                    if(EXTENDED && opcode==6'o14) write_x(j,pending_load[17:0]);
                    if(EXTENDED && opcode==6'o54 && effective_address!=17'o377604) a<=pending_load;
                    if(local_access && memory_meta_write_enable) register_meta[register_meta_index]<=skm_meta;
                    if (local_access && memory_data_write_enable) case (effective_address)
                        17'o377604: a <= store_value;
                        17'o377605: b <= store_value;
                        17'o377606: c <= store_value;
                        17'o377607: d <= store_value;
                        17'o377610: e <= store_value;
                        default: begin end
                    endcase
                    if (opcode != 6'o30 && opcode!=6'o17) e <= store_value;
                    state <= COMMIT;
                end
                WRITE_CONFIGURATION: begin
                    if (f_target != 0)
                        write_f(f_target,m[f_offset*9 +: 9]);
                    if (opcode == 6'o21 || f_offset == 3) state <= COMMIT;
                    else f_offset <= f_offset + 2'd1;
                end
                COMMIT: begin
                    retire <= 1; retire_address <= instruction_address; retire_sequence<=k;
                    state <= EXTENDED && !held ? DISPATCH : FETCH;
                    if(EXTENDED && (restart_pending || start)) begin
                        p<=start ? start_address : restart_address;toggle_start<=start ? start_address : restart_address;
                        k<=0;flags<=1;current_live<=1;fault<=0;alarms<=0;state<=FETCH;
                        device_preset<=1;restart_pending<=0;stop_pending<=0;missed_pending<=0;stopped<=0;
                    end
                    else if(EXTENDED && (console_stop || stop_pending || missed_pending)) begin stopped<=1;stop_pending<=0;missed_pending<=0;resume_state<=!held ? DISPATCH : FETCH;end
                end
                ALU_WAIT: if(alu_done) begin a<=alu_a;b<=alu_b;c<=alu_c;d<=alu_d;z<=alu_z;state<=COMMIT;end
                IO_TRANSFER: if(io_transfer_ready) begin
                    if(!held) begin flags[k]<=0; current_live<=0; end
                    if(io_transfer_input) begin
                        store_value<=io_transfer_assembly ? assembly_input : normal_input_store;
                        state<=WRITE_OPERAND;
                    end else if(io_transfer_assembly) begin store_value<=assembly_output; state<=WRITE_OPERAND; end
                    else begin e<=m; state<=COMMIT; end
                end
                DISPATCH, WAIT_SEQUENCE: begin
                    if(select_other && selected_parity_error && !alarm_suppress[2]) begin
                        alarms[2]<=1;fault<=7;state<=FAULTED;resume_state<=DISPATCH;
                        x_parity[selected_sequence]<=~^x_memory[selected_sequence];
                    end else if(select_other) begin
                        if(selected_parity_error) alarms[2]<=1;
                        x_parity[selected_sequence]<=~^x_memory[selected_sequence];
                        write_x(k,{x_memory[k][17],p});
                        p<=selected_sequence==0 ? toggle_start : x_memory[selected_sequence][16:0];
                        if(!trap_sequence_pending) e<={3'b0,k,3'b0,selected_sequence,1'b0,p};
                        trap_sequence_pending<=0;
                        k<=selected_sequence; current_live<=1; state<=FETCH;
                        if(trap_mode[3] && k!=6'o42 && selected_sequence!=0 && x_memory[selected_sequence][17]) begin
                            flags[6'o42]<=1;trap_sequence_pending<=1;state<=DISPATCH;
                        end
                    end else if(current_live || (selected_valid && selected_sequence==k)) begin
                        current_live<=1; state<=FETCH;
                    end else state<=WAIT_SEQUENCE;
                    if(restart_pending || start) begin
                        p<=start ? start_address : restart_address;toggle_start<=start ? start_address : restart_address;
                        k<=0;flags<=1;current_live<=1;fault<=0;alarms<=0;state<=FETCH;
                        device_preset<=1;restart_pending<=0;stop_pending<=0;missed_pending<=0;stopped<=0;
                    end
                    else if(console_stop || stop_pending || missed_pending) begin stopped<=1;stop_pending<=0;missed_pending<=0;resume_state<=DISPATCH;end
                end
                default: begin fault <= 5; state <= FAULTED; end
            endcase
        end
    end
endmodule
`default_nettype wire
