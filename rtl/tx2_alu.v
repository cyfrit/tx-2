`timescale 1ns/1ps
`default_nettype none
// Serial functional Arithmetic Element. Handbook ch.3; Technical Manual
// vol.3 pp.138-160. MUL uses PAD/MS/full-carry, DIV uses PAD/CRY/rotate.
// One physical ASK limit is shared by the 27+9 fracture, including its
// documented low-quarter anomaly. Ordinary instructions expand activity;
// AOP supplies unexpanded quarter enables, applied at every register pulse.
module tx2_alu (
    input wire clk, reset, start,
    input wire [5:0] opcode,
    input wire [1:0] fracture,
    input wire [3:0] activity,
    input wire [35:0] a_in,b_in,c_in,d_in,
    input wire [3:0] z_in,
    output reg done,
    output reg [35:0] a_out,b_out,c_out,d_out,
    output reg [3:0] z_out
);
    localparam [3:0] IDLE=0,GROUP=1,SHIFT=2,NORMALIZE=3,
                     MULTIPLY=4,DIV_FIRST=5,DIV_LOOP=6,SAVE=7;
    reg [3:0] state;
    reg [5:0] op;
    reg [1:0] form;
    reg [3:0] enabled;
    reg [2:0] quarter;
    reg [5:0] width,base;
    reg [1:0] sign_quarter;
    reg [35:0] av,bv,cv,dv,original_d,write_mask;
    reg [8:0] count;
    reg [6:0] limit,steps;
    reg right,negative_a,negative_d,overflow;
    reg [5:0] group_width,group_base,shared_width;
    reg [2:0] next_quarter;
    reg [1:0] group_sign;
    reg [35:0] group_mask;
    // Bit b of the group is enabled[(b+group_base)/9]: the quarter enables spread to
    // nine bits each, shifted down to the group; quarters past 3 read as inactive.
    wire [35:0] enabled_bits={{9{enabled[3]}},{9{enabled[2]}},{9{enabled[1]}},{9{enabled[0]}}};
    always @* begin
        group_base={quarter[1:0],3'b0}+{4'b0,quarter[1:0]};
        group_width=36; next_quarter=4; group_sign=3;
        case(form)
            1: begin group_width=18; next_quarter=quarter+2; group_sign=quarter[1:0]+1; end
            2: begin group_width=quarter==0 ? 6'd9 : 6'd27;
                     next_quarter=quarter==0 ? 3'd1 : 3'd4;
                     group_sign=quarter==0 ? 2'd0 : 2'd3; end
            3: begin group_width=9; next_quarter=quarter+1; group_sign=quarter[1:0]; end
            default: begin end
        endcase
        shared_width=group_width;
        if(form==2 && |enabled[3:1]) shared_width=27;
        group_mask=(enabled_bits >> group_base) & (36'hfffffffff >> (36-group_width));
    end
    wire [35:0] mask=36'hfffffffff >> (36-width);
    wire [35:0] sign_mask=mask ^ (mask >> 1);
    // GROUP loads only 9-, 18-, 27-, or 36-bit words. Their sign quarter
    // starts nine bits below the width, without division or multiplication.
    wire [5:0] counter_base=width-6'd9;
    wire sign_a=av[width-1], sign_d=dv[width-1];
    function automatic [35:0] ring_add;
        input [35:0] lhs,rhs;
        input [5:0] bits;
        reg [36:0] sum;
        reg [35:0] folded;
        reg [35:0] word_mask;
        begin
            word_mask=36'hfffffffff >> (36-bits);
            sum={1'b0,lhs & word_mask}+{1'b0,rhs & word_mask};
            folded=(sum[35:0] & word_mask)+{35'b0,sum[bits]};
            ring_add=folded[35:0] & word_mask;
        end
    endfunction
    function automatic [8:0] count_add;
        input [8:0] lhs,rhs;
        reg [9:0] total;
        begin total={1'b0,lhs}+{1'b0,rhs};count_add=total[8:0]+{8'b0,total[9]};end
    endfunction
    wire counter_operation=op==6'o60 || op==6'o61 || op==6'o62 || op==6'o64 ||
               op==6'o66 || op==6'o70 || op==6'o71 || op==6'o72 || op==6'o74;
    wire [35:0] d_write_mask=counter_operation ? write_mask | (36'o777 << counter_base) : write_mask;
    wire [35:0] add_operand=op==6'o77 ? dv ^ mask : dv;
    wire [35:0] sum=ring_add(av,add_operand,width);
    wire [35:0] pad_a=(bv[0] ? av ^ dv : av);
    wire [35:0] pad_c=(bv[0] ? cv | (av & dv) : cv);
    wire [35:0] ms_a=(pad_a >> 1) ^ pad_c;
    wire [35:0] ms_c=(pad_a >> 1) & pad_c;
    wire [35:0] ms_b=(bv >> 1) | (pad_a[0] ? sign_mask : 36'b0);
    wire [35:0] final_product=ring_add(pad_a,(pad_c << 1) & mask,width);
    wire [35:0] div_d=(sign_a==sign_d) ? dv ^ mask : dv;
    wire [35:0] div_rot_a=((av << 1) | (bv >> (width-1))) & mask;
    wire [35:0] div_rot_b=((bv << 1) | {35'b0,sign_a}) & mask;
    wire [35:0] div_source=steps==limit-1 ? av : div_rot_a;
    wire [35:0] div_sum=(div_source + div_d + {35'b0,div_d[width-1]}) & mask;
    wire [35:0] div_initial_a=(av & ~write_mask) | ((negative_a ? av : av ^ mask) & write_mask);
    wire [35:0] div_initial_b=(bv & ~write_mask) | ((negative_a ? bv : bv ^ mask) & write_mask);
    wire [35:0] div_initial_d=(dv & ~write_mask) |
                    ((div_initial_a[width-1]==sign_d ? dv ^ mask : dv) & write_mask);
    reg [35:0] shifted_word,shifted_b,next_a,next_b;
    wire double_word=op==6'o62 || op==6'o66 || op==6'o72;
    wire use_b=op==6'o61 || op==6'o71;
    wire cycle_op=op==6'o60 || op==6'o61 || op==6'o62;
    wire [35:0] shift_word=use_b ? bv : av;
    wire shift_sign=shift_word[width-1];
    // Every pulse shifts by one bit. Couple the two masked words directly
    // instead of packing, shifting, and unpacking a variable-width 72-bit word.
    always @* begin
        if(right) begin
            shifted_word=((shift_word >> 1) |
                ((cycle_op ? (double_word ? bv[0] : shift_word[0]) : shift_sign) ? sign_mask : 36'b0)) & mask;
            shifted_b=((bv >> 1) | (av[0] ? sign_mask : 36'b0)) & mask;
        end else begin
            shifted_word=((shift_word << 1) | {35'b0,(double_word ? bv[width-1] : shift_sign)}) & mask;
            if(!cycle_op) shifted_word=(shifted_word & ~sign_mask) | (shift_word & sign_mask);
            shifted_b=((bv << 1) | {35'b0,sign_a}) & mask;
        end
        next_a=use_b ? av : shifted_word;
        next_b=double_word ? shifted_b : (use_b ? shifted_word : bv);
    end
    // Mask each pulse, rather than only the final result: inactive AOP quarters
    // remain sources for the coupling network while their registers stay fixed.
    task automatic pulse_ab;
        input [35:0] na,nb;
        begin
            av <= (av & ~write_mask) | (na & write_mask);
            bv <= (bv & ~write_mask) | (nb & write_mask);
        end
    endtask
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE; done<=0; op<=0; form<=0; enabled<=0; quarter<=0;
            width<=36; base<=0; sign_quarter<=0; av<=0;bv<=0;cv<=0;dv<=0;
            original_d<=0;write_mask<=0;count<=0;limit<=0;steps<=0;
            right<=0;negative_a<=0;negative_d<=0;overflow<=0;
            a_out<=0;b_out<=0;c_out<=0;d_out<=0;z_out<=0;
        end else begin
            done<=0;
            case(state)
                IDLE: if(start) begin
                    op<=opcode; form<=fracture;enabled<=activity;quarter<=0;
                    a_out<=a_in;b_out<=b_in;c_out<=c_in;d_out<=d_in;z_out<=z_in;
                    state<=GROUP;
                end
                GROUP: if(quarter==4) begin done<=1; state<=IDLE; end
                else begin
                    quarter<=next_quarter;
                    if(group_mask!=0) begin
                        width<=group_width;base<=group_base;sign_quarter<=group_sign;
                        av<=(a_out >> group_base) & (36'hfffffffff >> (36-group_width));
                        bv<=(b_out >> group_base) & (36'hfffffffff >> (36-group_width));
                        cv<=(c_out >> group_base) & (36'hfffffffff >> (36-group_width));
                        dv<=(d_out >> group_base) & (36'hfffffffff >> (36-group_width));
                        original_d<=(d_out >> group_base) & (36'hfffffffff >> (36-group_width));
                        write_mask<=group_mask;
                        negative_a<=a_out[group_base+group_width-1];
                        negative_d<=d_out[group_base+group_width-1];
                        overflow<=z_out[group_sign];
                        steps<=0; limit<=op==6'o66 ? {shared_width,1'b0}-7'd1 : {1'b0,shared_width};
                        state<=SAVE;
                        case(op)
                            6'o60,6'o61,6'o62,6'o70,6'o71,6'o72: begin
                                count<=d_out[group_sign*9+8] ? ~d_out[group_sign*9 +: 9] : d_out[group_sign*9 +: 9];
                                right<=d_out[group_sign*9+8];state<=SHIFT;
                            end
                            6'o64,6'o66: begin limit<=op==6'o66 ? {shared_width,1'b0}-7'd1 : {1'b0,shared_width}-7'd1;
                                right<=z_out[group_sign];state<=NORMALIZE;end
                            6'o74: begin limit<={1'b0,shared_width};state<=SHIFT;count<={3'b0,shared_width};right<=0;end
                            6'o75: state<=DIV_FIRST;
                            6'o76: begin limit<={1'b0,shared_width}-7'd1;state<=MULTIPLY; end
                            default: begin end
                        endcase
                    end
                end
                SHIFT: begin
                    if(op==6'o74) begin
                        if(count==0) state<=SAVE;
                        else begin
                            pulse_ab(((av << 1) | (av >> (width-1))) & mask,bv);
                            if(sign_a) dv[counter_base +: 9]<=count_add(dv[counter_base +: 9],9'd1);
                            count<=count-9'd1;
                        end
                    end else begin
                        if(!cycle_op && op!=6'o71 && overflow) begin
                            // Left: fix sign before first shift. Right: shift old sign,
                            // then fix it, as specified by vol.3 p.139.
                            if(right && count!=0) begin
                                pulse_ab(next_a ^ sign_mask,next_b);
                                count<=count-9'd1;
                            end else if(write_mask[width-1]) av[width-1]<=~av[width-1];
                            overflow<=0;z_out[sign_quarter]<=0;
                        end else if(count==0) begin dv[counter_base +: 9]<=9'o777;state<=SAVE; end
                        else begin pulse_ab(next_a,next_b);count<=count-9'd1; end
                    end
                end
                NORMALIZE: begin
                    if(overflow) begin
                        pulse_ab(next_a ^ sign_mask,next_b);
                        dv[counter_base +: 9]<=count_add(dv[counter_base +: 9],9'd1);
                        z_out[sign_quarter]<=0;overflow<=0;state<=SAVE;
                    end else if(sign_a!=av[width-2] || steps==limit) begin z_out[sign_quarter]<=0;state<=SAVE; end
                    else begin
                        pulse_ab(next_a,next_b);steps<=steps+7'd1;
                        dv[counter_base +: 9]<=count_add(dv[counter_base +: 9],9'o776);
                    end
                end
                MULTIPLY: begin
                    if(steps==0) begin
                        av<=av & ~write_mask;cv<=cv & ~write_mask;
                        bv<=(bv & ~write_mask) | ((negative_a ? av ^ mask : av) & write_mask);
                        dv<=(dv & ~write_mask) | ((negative_d ? dv ^ mask : dv) & write_mask);
                        steps<=1;z_out[sign_quarter]<=0;
                    end else if(steps<=limit) begin
                        pulse_ab(ms_a,ms_b);cv<=(cv & ~write_mask) | (ms_c & write_mask);steps<=steps+7'd1;
                    end else begin
                        pulse_ab(negative_a!=negative_d ? final_product ^ mask : final_product,
                                 negative_a!=negative_d ? bv ^ mask : bv);
                        cv<=(cv & ~write_mask) | (pad_c & write_mask);dv<=original_d;state<=SAVE;
                    end
                end
                DIV_FIRST: begin
                    // PAD/CRY feeds D's sign into the low carry input without a ring.
                    // The initial dividend is made negative; signs are remembered.
                    pulse_ab((div_initial_a+div_initial_d+{35'b0,div_initial_d[width-1]}) & mask,div_initial_b);
                    dv<=div_initial_d;
                    cv<=cv & ~write_mask;steps<=0;state<=DIV_LOOP;
                end
                DIV_LOOP: begin
                    dv<=(dv & ~write_mask) | (div_d & write_mask);
                    if(steps==limit-1) begin
                        // Last pass rotates only B and fixes a positive remainder.
                        pulse_ab(negative_a!=negative_d ? div_rot_b ^ mask : div_rot_b,
                                 negative_a ? (sign_a ? av : div_sum) : (sign_a ? av : div_sum) ^ mask);
                        z_out[sign_quarter]<=div_rot_b[width-1];
                        dv<=original_d;state<=SAVE;
                    end else begin
                        pulse_ab(div_sum,div_rot_b);steps<=steps+7'd1;
                    end
                end
                SAVE: begin
                    case(op)
                        6'o65: begin
                            a_out<=(a_out & ~(write_mask << base)) | (((av ^ dv) & write_mask) << base);
                            c_out<=(c_out & ~(write_mask << base)) | (((cv | (av & dv)) & write_mask) << base);
                        end
                        6'o67,6'o77: begin
                            a_out<=(a_out & ~(write_mask << base)) | ((sum & write_mask) << base);
                            c_out<=(c_out & ~(write_mask << base)) | (((av & add_operand) & write_mask) << base);
                            z_out[sign_quarter]<=(sign_a==add_operand[width-1]) && (sum[width-1]!=sign_a);
                        end
                        default: begin
                            a_out<=(a_out & ~(write_mask << base)) | ((av & write_mask) << base);
                            b_out<=(b_out & ~(write_mask << base)) | ((bv & write_mask) << base);
                            c_out<=(c_out & ~(write_mask << base)) | ((cv & write_mask) << base);
                        end
                    endcase
                    d_out<=(d_out & ~(d_write_mask << base)) | ((dv & d_write_mask) << base);
                    state<=GROUP;
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
