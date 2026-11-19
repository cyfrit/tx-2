`timescale 1ns/1ps
`default_nettype none
// Technical Manual vol.2: 12-6.3..12-6.5, Fig.12-45 and 13-12..13-15.
// Activity always names quarters of E, including the store direction.
module tx2_exchange (
    input wire [35:0] source_word,
    input wire [35:0] destination_word,
    input wire [8:0] configuration_word,
    input wire store_direction,
    input wire sign_extension,
    output reg [35:0] result_word,
    output reg [3:0] extended_activity
);
    wire [1:0] fracture;
    wire [3:0] activity;
    wire [2:0] permutation;
    tx2_configuration_decode configuration_decoder (
        .configuration_word(configuration_word), .fracture(fracture),
        .active_quarters(activity), .permutation(permutation)
    );
    wire [35:0] mask = {{9{activity[3]}}, {9{activity[2]}},
                        {9{activity[1]}}, {9{activity[0]}}};

    function [35:0] permute;
        input [35:0] value;
        input [2:0] selection;
        input inverse;
        reg [2:0] effective;
        begin
            effective = selection;
            if (inverse) begin
                case (selection)
                    1: effective = 3;
                    3: effective = 1;
                    6: effective = 7;
                    7: effective = 6;
                    default: effective = selection;
                endcase
            end
            case (effective)
                0: permute = value;
                1: permute = {value[8:0], value[35:9]};
                2: permute = {value[17:0], value[35:18]};
                3: permute = {value[26:0], value[35:27]};
                4: permute = {value[26:18], value[35:27], value[8:0], value[17:9]};
                5: permute = {value[8:0], value[17:9], value[26:18], value[35:27]};
                6: permute = {value[26:18], value[17:9], value[35:27], value[8:0]};
                7: permute = {value[17:9], value[35:27], value[26:18], value[8:0]};
            endcase
        end
    endfunction

    // Elaborate the wraparound sign routing once for each fracture/activity
    // pair. Each quarter gets an enable and a two-bit source-quarter index.
    function [11:0] sign_routes;
        input [3:0] active;
        input [1:0] form;
        integer q, distance, candidate, first, length;
        begin
            sign_routes = 0;
            first = 0;
            length = 4;
            candidate = 0;
            for (q = 0; q < 4; q = q + 1) begin
                case (form)
                    0: begin first = 0; length = 4; end
                    1: begin first = (q / 2) * 2; length = 2; end
                    2: begin first = (q == 0) ? 0 : 1; length = (q == 0) ? 1 : 3; end
                    3: begin first = q; length = 1; end
                endcase
                // Sign extension wraps within a subword; see 12-6.3.1.
                for (distance = 3; distance >= 1; distance = distance - 1) begin
                    candidate = q - distance;
                    if (candidate < first) candidate = candidate + length;
                    if (!active[q] && distance < length) begin
                        if (active[candidate])
                            sign_routes[q*3 +: 3] = {1'b1, candidate[1:0]};
                    end
                end
            end
        end
    endfunction

    wire [11:0] route_rom [0:63];
    genvar entry;
    generate for (entry = 0; entry < 64; entry = entry + 1) begin : route_entry
        assign route_rom[entry] = sign_routes(entry[3:0], entry[5:4]);
    end endgenerate
    wire [11:0] route = route_rom[{fracture, activity}];

    wire [35:0] selected_source = permute(source_word, permutation, store_direction);
    wire [35:0] selected_mask = store_direction ? permute(mask, permutation, 1'b1) : mask;
    wire [35:0] merged = (selected_source & selected_mask) |
                         (destination_word & ~selected_mask);
    wire [3:0] signs = {merged[35], merged[26], merged[17], merged[8]};
    integer quarter;
    always @* begin
        result_word = merged;
        if (sign_extension && !store_direction)
            for (quarter = 0; quarter < 4; quarter = quarter + 1)
                if (route[3*quarter + 2])
                    result_word[9*quarter +: 9] = {9{signs[route[3*quarter +: 2]]}};
    end
    always @* begin
        case (fracture)
            0: extended_activity = {4{|activity}};
            1: extended_activity = {{2{|activity[3:2]}}, {2{|activity[1:0]}}};
            2: extended_activity = {{3{|activity[3:1]}}, activity[0]};
            3: extended_activity = activity;
        endcase
    end
endmodule
`default_nettype wire
