`timescale 1ns/1ps
`default_nettype none
// 33 physical sequences: octal 00 and 40..77. Each six-bit patch rank
// belongs to the corresponding sequence. Rank ties use ascending sequence.
// Startover 00 always has highest priority; see Handbook 4-3.1, 5-19.
module tx2_sequence_selector (
    input wire [63:0] flags,
    input wire [383:0] priority_map,
    output reg valid,
    output reg [5:0] selected,
    output reg [5:0] selected_priority
);
    wire [31:0] active_flags,known_rank;
    wire [30:0] unused_flags=flags[31:1];
    wire [31:0] rank_bits [0:5];
    genvar lane,bit_number;
    generate
        for (lane=0;lane<32;lane=lane+1) begin: priority_lanes
            // Procedural if ignores X/Z flags. An unknown rank can only win
            // as the first active sequence; later comparisons reject it.
            assign active_flags[lane]=flags[lane+32] === 1'b1;
            assign known_rank[lane]=(^priority_map[(lane+32)*6 +: 6]) !== 1'bx;
            for (bit_number=0;bit_number<6;bit_number=bit_number+1) begin: rank_planes
                assign rank_bits[bit_number][lane]=priority_map[(lane+32)*6+bit_number];
            end
        end
    endgenerate

    function [5:0] first_sequence;
        input [31:0] pending;
        reg [31:0] first;
        begin
            // Isolate the lowest lane, then encode its physical sequence.
            first=pending & (~pending+32'd1);
            first_sequence={1'b1,|(first & 32'hffff0000),|(first & 32'hff00ff00),
                            |(first & 32'hf0f0f0f0),|(first & 32'hcccccccc),
                            |(first & 32'haaaaaaaa)};
        end
    endfunction

    integer bit_index;
    reg [31:0] candidates,zero_candidates;
    always @* begin
        valid=0; selected=0; selected_priority=6'h3f;
        candidates=active_flags & known_rank; zero_candidates=0;
        if (|active_flags) begin
            valid=1;
            selected=first_sequence(active_flags);
            selected_priority=priority_map[selected*6 +: 6];
            // An unknown first rank blocks all subsequent strict comparisons.
            // Otherwise discard unknown ranks and filter whole lanes, most
            // significant rank bit first. Equal ranks retain ascending order.
            if (known_rank[selected[4:0]]) begin
                selected_priority=0;
                for (bit_index=5;bit_index>=0;bit_index=bit_index-1) begin
                    zero_candidates=candidates & ~rank_bits[bit_index];
                    if (|zero_candidates) candidates=zero_candidates;
                    else selected_priority[bit_index]=1;
                end
                selected=first_sequence(candidates);
            end
        end
        if (flags[0]) begin valid=1; selected=0; selected_priority=0; end
    end
endmodule
`default_nettype wire
