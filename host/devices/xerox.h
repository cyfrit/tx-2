#pragma once
#include "../device.h"
#include <array>
#include <vector>
#include <algorithm>

// H63 PDF pp101–103,196: unit 51 is a positioned charactron.
struct Xerox : Device {
    struct Mark { unsigned x, code; int y; uint64_t clock, frame; double paper; bool uncertain; };
    // [INFERENCE] Initial panel switch ON; recording still waits for IOS connection.
    bool powered = true, connected = false, low_paper = false, moving = false;
    uint64_t now = 0, warm_until = 0, busy_until = 0, sync_until = 0;
    uint64_t frame_origin = 0, paper_until = 0, paper_clock = 0, count = 0;
    double paper_inches = 0;
    uint64_t exposure_origin = 0, exposure_clock = 0, exposure_remaining = 0;
    unsigned exposure_ticks = 0;
    bool exposing = false;
    std::vector<Mark> marks;
    Xerox() : Device(051, "xerox") {}
    void reset() override {
        powered = true; connected = low_paper = moving = false;
        now = warm_until = busy_until = sync_until = frame_origin = paper_until = paper_clock = count = 0;
        paper_inches = 0; marks.clear();
        exposure_ticks = 0; // Invalidate the cached frame phase after reset.
    }
    // p103/p196: all 88 glyph rows, including parenthesized stencil aliases.
    // Strip size bit 1.9 only; both sizes retain exactly the same glyph identity.
    static const char* glyph(unsigned code) {
        static const auto table = [] {
            std::array<const char*, 256> t{}; t.fill("");
            auto put = [&t](const char* g, std::initializer_list<unsigned> codes) {
                for (unsigned c : codes) t[c & 0377] = g;
            };
            put("A", {0154}); put("B", {0142}); put("C", {0361,0056,0071,0346});
            put("D", {0352}); put("E", {0313,0043}); put("F", {0344,0054});
            put("G", {0302,0012}); put("H", {0354}); put("I", {0172,0157});
            put("J", {0144}); put("K", {0143}); put("L", {0332,0047,0062,0317});
            put("M", {0360,0055,0070,0345}); put("N", {0370,0355}); put("O", {0353});
            put("P", {0312,0042}); put("Q", {0160,0145}); put("R", {0371,0356});
            put("S", {0322,0017,0032,0307}); put("T", {0153}); put("U", {0362,0057,0072,0347});
            put("V", {0152}); put("W", {0343,0053}); put("X", {0161,0146});
            put("Y", {0342,0052}); put("Z", {0162,0147}); put("h", {0132,0117}); put("i", {0133});
            put("<", {0220,0205}); put(">", {0221,0206}); put(".", {0222,0207});
            put("+", {0351}); put("−", {0372,0357}); put("∨", {0340,0050}); put("'", {0363,0073});
            put("|", {0730,0445,0460,0715}); put("Σ", {0703,0413});
            put("}", {0720,0415,0430,0705}); put("←", {0150}); put("_", {0570,0555});
            put("(", {0140}); put("=", {0114}); put("/", {0131,0116}); put("∪", {0103});
            put("j", {0122,0107}); put("k", {0324,0034}); put("n", {0323,0033});
            put("p", {0024}); put("q", {0111}); put("t", {0112}); put("w", {0173});
            put("x", {0174}); put("y", {0163}); put("z", {0164});
            put("α", {0310,0040}); put("β", {0311,0041}); put("γ", {0333,0063});
            put("Δ", {0203}); put("ε", {0334,0064}); put("λ", {0023});
            put("1", {0001}); put("2", {0002}); put("3", {0003}); put("4", {0004});
            put("5", {0020,0005}); put("6", {0021,0006}); put("7", {0022,0007});
            put("8", {0300,0010}); put("9", {0301,0011}); put("0", {0000});
            put("?", {0202}); put(",", {0204}); put("∩", {0120,0105}); put("⊃", {0121,0106});
            put("×", {0113}); put("○", {0714,0444}); put("~", {0373}); put("∧", {0341,0051});
            put("#", {0364,0074}); put("‖", {0731,0446,0461,0716}); put("□", {0704,0414});
            put("{", {0721,0416,0431,0706}); put("→", {0151}); put("‾", {0571,0556});
            put(")", {0141}); put("≡", {0130,0115}); put("*", {0102}); put("⊂", {0104});
            // p101 explicitly identifies 100 as a blank. Unlisted cells have no
            // source-defined glyph; [INFERENCE] leave them unmarked, retaining raw code.
            return t;
        }();
        return table[code & 0377];
    }
    uint64_t phase(uint64_t t) const { return (t - frame_origin) % us(47000); }
    bool exposure(uint64_t t) {
        const unsigned ticks = *ticks_per_us;
        const uint64_t clock = t - frame_origin;
        // A frame's ready level is constant until its next exposure/reset edge.
        // Key the interval by both runtime timing inputs; backwards relative
        // clocks also force a fresh modulo, including unsigned-time wraparound.
        if (exposure_ticks != ticks || exposure_origin != frame_origin ||
            clock < exposure_clock || clock - exposure_clock >= exposure_remaining) {
            exposure_ticks = ticks; exposure_origin = frame_origin; exposure_clock = clock;
            const uint64_t p = clock % us(47000);
            exposing = p < us(45000);
            exposure_remaining = (exposing ? us(45000) : us(47000)) - p;
        }
        return exposing;
    }
    bool ready(uint64_t t) override {
        // p102: 45 ms exposure + 2 ms reset = .094 in at 2 in/s.
        return powered && connected && t >= warm_until && t >= busy_until && t >= sync_until && exposure(t);
    }
    bool active() const override {
        return moving || (powered && connected && (now < warm_until || now < busy_until || now < sync_until));
    }
    bool inability() const override { return low_paper; } // p102; unit 41 bit 1.7.
    void control(unsigned c, uint64_t t) override {
        now = t;
        if ((c & 070000) == 020000) {
            connected = false;
            if (moving) paper_until = t + us(15000000);
        } else if ((c & 070000) == 030000) {
            if (!connected) {
                connected = true; warm_until = t + us(5000000); frame_origin = warm_until;
            }
            if (c & 010) {
                sync_until = t < warm_until ? warm_until :
                    frame_origin + ((t - frame_origin) / us(47000) + 1) * us(47000);
            }
        }
    }
    void transfer(uint64_t word, uint64_t t) override {
        tick(t);
        const unsigned y = (word >> 9) & 077;
        const bool startup = !moving;
        if (startup) { moving = true; paper_clock = t; }
        paper_until = t + us(15000000);
        // PDF p101 diagram: X=4.9..4.1, Y=2.6..2.1, code=1.9..1.1.
        marks.push_back({unsigned((word >> 27) & 0777), unsigned(word & 0777),
                         y & 040 ? -int((~y) & 077) : int(y),
                         t, (t - frame_origin) / us(47000),
                         paper_position(t) - double(phase(t)) / us(1000000) * 2.0, startup});
        busy_until = t + us(750); count++;
        // p101: startup TSD is physically unpredictable. [INFERENCE] Preserve
        // its requested mark with uncertainty metadata.
    }
    double paper_position(uint64_t t) const {
        return paper_inches + (moving ? double(std::min(t, paper_until) - paper_clock) / us(1000000) * 2.0 : 0);
    }
    void tick(uint64_t t) override {
        now = t;
        if (moving && t >= paper_until) {
            paper_inches = paper_position(t);
            moving = false;
        }
    }
    bool events(std::ostream& o) override {
        if (marks.empty()) return false;
        o << '['; bool first = true;
        for (const auto& m : marks) {
            o << (first ? "" : ",") << "{\"x\":" << m.x << ",\"y\":" << m.y << ",\"code\":" << m.code
              << ",\"glyph\":\"" << glyph(m.code) << "\",\"large\":" << bool(m.code & 0400)
              << ",\"clock\":" << m.clock << ",\"frame\":" << m.frame << ",\"paper\":" << m.paper << ",\"uncertain\":" << m.uncertain << '}';
            first = false;
        }
        o << ']'; marks.clear(); return true;
    }
    bool status(std::ostream& o) override {
        o << "{\"power\":" << powered << ",\"connected\":" << connected << ",\"ready\":" << ready(now)
          << ",\"warming\":" << (connected && now < warm_until) << ",\"moving\":" << moving
          << ",\"lowPaper\":" << low_paper << ",\"paper\":" << paper_position(now) << ",\"characters\":" << count << '}';
        return true;
    }
    std::string command(const std::string& op, std::istringstream& a) override {
        int on;
        if (op == "power" && a >> on) {
            powered = on != 0;
            if (powered && connected) { warm_until = now + us(5000000); frame_origin = warm_until; }
            return "{\"ok\":true}";
        }
        if (op == "paper" && a >> on) { low_paper = on != 0; return "{\"ok\":true}"; }
        return "{\"error\":\"use power 0|1 or paper 0|1; paper 1 indicates low paper\"}";
    }
};
