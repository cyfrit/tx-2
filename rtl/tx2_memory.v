`timescale 1ns/1ps
`default_nettype none
// Logical S/T memory and standard plugboards; Handbook 5-5.2, 5-13.
// S=000000..177777; T=200000..207777. U and other V devices fault.
// Registers A..E are intercepted in tx2_core. RAM contents are not reset.
// Extended profile includes U, 38-bit core words, odd parity checking and
// read/restoration of parity. V registers are sampled from physical inputs.
module tx2_memory #(parameter EXTENDED=1) (
    input wire clk,
    input wire reset,
    input wire request,
    input wire write_enable,
    input wire [16:0] address,
    input wire [35:0] write_data,
    input wire data_write_enable, meta_write_enable, meta_write_value, read_set_meta,
    output reg read_meta, read_parity, parity_error,
    input wire clock_tick, clock_clear,
    input wire [35:0] knob_data, external_register_data,
    input wire knob_meta, external_register_meta,
    input wire [287:0] console_switches,
    input wire [575:0] panel_data,
    input wire [15:0] panel_meta,
    output reg ready,
    output reg [35:0] read_data,
    output reg [1:0] error
);
    reg [35:0] s_memory [0:65535];
    reg [35:0] t_memory [0:4095];
    reg [35:0] u_memory [0:4095];
    reg s_meta [0:65535], s_parity [0:65535];
    reg t_meta [0:4095], t_parity [0:4095];
    reg u_meta [0:4095], u_parity [0:4095];
    reg [35:0] real_time_clock;
    reg [1:0] pending;
    reg pending_write, pending_data_write, pending_meta_write, pending_meta, pending_set;
    reg [35:0] selected_data;
    reg selected_meta,selected_parity;
    // Defined metadata power-on image, independent of reset and of data RAM.
    // readmemh keeps the image as RAM initialization through synthesis.
    initial begin
        $readmemh("programs/core-init-65536-0.hex",s_meta);
        $readmemh("programs/core-init-65536-1.hex",s_parity);
        $readmemh("programs/core-init-4096-0.hex",t_meta);
        $readmemh("programs/core-init-4096-1.hex",t_parity);
        $readmemh("programs/core-init-4096-0.hex",u_meta);
        $readmemh("programs/core-init-4096-1.hex",u_parity);
    end
    wire region_s=!pending_address[16];
    wire region_t=pending_address[16:12]==5'b10000;
    wire region_u=EXTENDED && pending_address[16:12]==5'b10001;
    wire updated_meta=pending_meta_write ? pending_meta : (selected_meta | pending_set);
    wire [35:0] updated_data=pending_write && pending_data_write ? pending_data : selected_data;
    wire updated_parity=~^{updated_meta,updated_data};
    reg [16:0] pending_address;
    reg [35:0] pending_data;

    function [35:0] plugboard;
        input [4:0] offset;
        begin
            case (offset)
                0: plugboard = 36'o760342_340000;
                1: plugboard = 36'o410763_762761;
                2: plugboard = 36'o160142_140411;
                3: plugboard = 36'o202163_162161;
                4: plugboard = 36'o732232_230200;
                5: plugboard = 36'o605731_730733;
                6: plugboard = 36'o320670_750600;
                7: plugboard = 36'o604331_330333;
                8: plugboard = 36'o002200_377740;
                9: plugboard = 36'o042200_377741;
                10: plugboard = 36'o102200_377742;
                11: plugboard = 36'o142200_377743;
                12: plugboard = 36'o202200_377744;
                13: plugboard = 36'o242200_377745;
                14: plugboard = 36'o302200_377746;
                15: plugboard = 36'o342200_377747;
                16: plugboard = 36'o011254_000023;
                17: plugboard = 36'o001252_377763;
                18: plugboard = 36'o210452_030106;
                19: plugboard = 36'o001253_000005;
                20: plugboard = 36'o405754_000026;
                21: plugboard = 36'o760653_377764;
                22: plugboard = 36'o410754_377763;
                23: plugboard = 36'o140500_000003;
                24: plugboard = 36'o001277_207777;
                25: plugboard = 36'o001677_777776;
                26: plugboard = 36'o140500_377773;
                27: plugboard = 36'o001200_777610;
                28: plugboard = 36'o760677_377771;
                29: plugboard = 36'o301712_377744;
                30: plugboard = 36'o000077_000000;
                31: plugboard = 36'o140500_377750;
            endcase
        end
    endfunction

    always @(posedge clk) begin
        if (reset) begin
            pending <= 0; pending_write <= 0; pending_address <= 0;
            pending_data <= 0; ready <= 0; read_data <= 0; error <= 0;
            pending_data_write<=0;pending_meta_write<=0;pending_meta<=0;pending_set<=0;
            read_meta<=0;read_parity<=1;parity_error<=0;real_time_clock<=0;
            selected_data<=0;selected_meta<=0;selected_parity<=1;
        end else begin
            ready <= 0;
            if(clock_clear) real_time_clock<=0;
            else if(clock_tick) real_time_clock<=real_time_clock+36'd1;
            if (pending==0 && !ready && request) begin
                pending <= 1;
                pending_write <= write_enable;
                pending_address <= address;
                pending_data <= write_data;
                pending_data_write<=!EXTENDED || data_write_enable;
                pending_meta_write<=EXTENDED && meta_write_enable;
                pending_meta<=meta_write_value;pending_set<=EXTENDED && read_set_meta;
            end
            if(pending==1) begin
                pending<=2;
        selected_data<=0;selected_meta<=0;selected_parity<=1;
        if(region_s) begin selected_data<=s_memory[pending_address[15:0]];
            selected_meta<=s_meta[pending_address[15:0]];selected_parity<=s_parity[pending_address[15:0]];end
        else if(region_t) begin selected_data<=t_memory[pending_address[11:0]];
            selected_meta<=t_meta[pending_address[11:0]];selected_parity<=t_parity[pending_address[11:0]];end
        else if(region_u) begin selected_data<=u_memory[pending_address[11:0]];
            selected_meta<=u_meta[pending_address[11:0]];selected_parity<=u_parity[pending_address[11:0]];end
        else if(pending_address>=17'o377740) selected_data<=plugboard(pending_address[4:0]);
        else if(EXTENDED) case(pending_address)
            17'o377620: begin selected_data<=knob_data;selected_meta<=knob_meta;end
            17'o377621: begin selected_data<=external_register_data;selected_meta<=external_register_meta;end
            17'o377630: selected_data<=real_time_clock;
            default: if(pending_address>=17'o377720 && pending_address<=17'o377737) begin
                selected_data<=panel_data[pending_address[3:0]*36 +: 36];selected_meta<=panel_meta[pending_address[3:0]];
            end else if(pending_address>=17'o377710 && pending_address<=17'o377717)
                selected_data<=console_switches[pending_address[2:0]*36 +: 36];
        endcase
        if(!region_s && !region_t && !region_u) selected_parity<=1; // V parity is computed from its sampled data at response
    end
            if (pending==2) begin
                pending <= 0;
                ready <= 1;
                error <= 0;
                read_data<=selected_data;read_meta<=selected_meta;read_parity<=region_s || region_t || region_u ? selected_parity : ~^{selected_meta,selected_data};
                parity_error<=EXTENDED && (region_s || region_t || region_u) && !(^{selected_parity,selected_meta,selected_data});
                if(region_s) begin
                    if(pending_write && pending_data_write) s_memory[pending_address[15:0]]<=pending_data;
                    s_meta[pending_address[15:0]]<=updated_meta;s_parity[pending_address[15:0]]<=updated_parity;
                end else if(region_t) begin
                    if(pending_write && pending_data_write) t_memory[pending_address[11:0]]<=pending_data;
                    t_meta[pending_address[11:0]]<=updated_meta;t_parity[pending_address[11:0]]<=updated_parity;
                end else if(region_u) begin
                    if(pending_write && pending_data_write) u_memory[pending_address[11:0]]<=pending_data;
                    u_meta[pending_address[11:0]]<=updated_meta;u_parity[pending_address[11:0]]<=updated_parity;
                end else if(pending_address>=17'o377740) begin
                    if(pending_write && !EXTENDED) error<=2;
                end else if(EXTENDED && (pending_address==17'o377620 || pending_address==17'o377621 ||
                     pending_address==17'o377630 || (pending_address>=17'o377710 && pending_address<=17'o377737))) begin
                    // Physical switches and real time clock ignore programmed writes.
                end else begin read_data<=0;read_meta<=0;read_parity<=1;parity_error<=0;error<=1;end
            end
        end
    end
endmodule
`default_nettype wire
