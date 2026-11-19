#pragma once
#include "../device.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

// EAI plotter: TR296:640–642,4383–4385; software protocol SK2:6555–6979.
// H63 explicitly omits section 74. DAC wiring, settling and PBI circuit transfer
// functions remain unavailable. [INFERENCE] The implementation uses ideal
// geometry to reconstruct the recovered protocol without analog mechanics.
struct PlotPaper {
    struct Stroke { double x0, y0, x1, y1; };
    std::vector<Stroke> strokes;
    double x = 0, y = 0;
    uint64_t count = 0, circles = 0;
    static double coordinate(unsigned half) {
        const unsigned v = half >> 3; // SK2:6763,6792: upper 15 coordinate bits
        return (v & 040000) ? -double((~v) & 037777) : double(v);
    }
    void move(double nx, double ny, bool pen) {
        if (pen && (std::abs(nx-x) > 1e-8 || std::abs(ny-y) > 1e-8)) {
            strokes.push_back({x,y,nx,ny}); count++;
        }
        x = nx; y = ny;
    }
    void arc(double cx, double cy, double angle, bool pen) {
        const double dx=x-cx, dy=y-cy, r=std::hypot(dx,dy), a=std::atan2(dy,dx);
        if (r < 1e-8 || std::abs(angle) < 1e-10) return;
        const unsigned steps=std::max(1u, unsigned(std::ceil(std::abs(angle)*64)));
        for(unsigned i=1;i<=steps;i++) { const double t=a+angle*i/steps; move(cx+r*std::cos(t),cy+r*std::sin(t),pen); }
        if (pen) circles++;
    }
};

struct Plotter : Device {
    PlotPaper direct, offline;
    unsigned mode = 0, pen_us = 5000;
    uint64_t busy_until = 0, last = 0;
    bool circle_active = false;
    double cx = 0, cy = 0;
    unsigned filter = 4;
    uint64_t records = 0, tape_records = 0, tape_tally = 0;
    std::array<unsigned, 7> rows{};
    unsigned row_count = 0, next_row = 0;
    std::vector<uint64_t> raw;
    Plotter() : Device(074, "plotter") {}
    void reset() override {
        direct=PlotPaper{}; offline=PlotPaper{}; mode=0; busy_until=last=0;
        circle_active=false; cx=cy=0; filter=4; records=tape_records=tape_tally=0; row_count=next_row=0; raw.clear();
    }
    static unsigned blocks(unsigned f) { return f<=4 ? 13 : f==5 ? 38 : 113; } // SK2:4992–4995,6960–6964
    static double sweep(unsigned m, unsigned f) { return ((m & 010) ? 1 : -1)*6.283185307179586/blocks(f); }
    bool ready(uint64_t now) override { return now >= busy_until; }
    bool active() const override { return circle_active || last < busy_until; }
    void timer_pulse(uint64_t) override {
        // [INFERENCE] Ideal PBI reconstruction: SK2:6711–6747 counts twenty
        // interval-timer pulses per tape-equivalent block. These pulses preserve
        // timer/software pacing; the hardware rate is undocumented.
        if(circle_active) direct.arc(cx,cy,sweep(mode,filter)/20,mode&1);
    }
    void control(unsigned c, uint64_t now) override {
        if ((c & 030000) == 030000) {
            const unsigned next=c&07777;
            // [INFERENCE] SK2:6685 dismisses even when the requested pen state is
            // unchanged. Acknowledge every mode IOS through busy→available;
            // missing hardware timing is represented by a 1us control settle.
            busy_until=std::max(busy_until,now+us(((next^mode)&1) ? pen_us : 1)+1);
            mode=next;
            if (!(mode&004) || !(mode&040)) circle_active=false;
        } else if ((c & 030000) == 020000) circle_active=false;
    }
    void transfer(uint64_t w, uint64_t now) override {
        records++; raw.push_back(mode); raw.push_back(w);
        const double nx=PlotPaper::coordinate(unsigned(w>>18)&0777777), ny=PlotPaper::coordinate(unsigned(w)&0777777);
        filter=std::max(unsigned((w>>18)&7),unsigned(w&7));
        if ((mode & 044)==044) { cx=nx; cy=ny; circle_active=true; busy_until=now+1; }
        else {
            const double distance=std::hypot(nx-direct.x,ny-direct.y);
            direct.move(nx,ny,mode&1);
            // [INFERENCE] Ideal 29-inch square DAC span; TR296 gives 15 inch/s slew.
            busy_until=now+1+us(uint64_t(std::ceil(distance*29.0/32766/15*1000000)));
        }
    }
    void tick(uint64_t now) override { last=now; }
    void tape_line(unsigned b) {
        if (!(b&0x80)) return;
        if(b&0x40) { rows[next_row]=b&077; next_row=(next_row+1)%7; row_count=std::min(7u,row_count+1); return; }
        if(row_count==7) {
            uint64_t w=0;
            for(unsigned r=0;r<6;r++) for(unsigned k=0;k<6;k++) w|=uint64_t((rows[(next_row+r+1)%7]>>k)&1)<<(6*k+5-r);
            const unsigned m=rows[next_row]; tape_records++; tape_tally=b&077;
            const double nx=PlotPaper::coordinate(unsigned(w>>18)&0777777),ny=PlotPaper::coordinate(unsigned(w)&0777777);
            const unsigned f=std::max(unsigned((w>>18)&7),unsigned(w&7));
            // SK2:6629–6649: repeated eight-line blocks each represent one PBI interval.
            if((m&044)==044) offline.arc(nx,ny,sweep(m,f),m&1);
            else offline.move(nx,ny,m&1);
        }
        row_count=next_row=0; // blank leader, END MARK and trailer are software tape patterns
    }
    static void paper_events(std::ostream& o, PlotPaper& p) {
        o << '[';
        for(size_t i=0;i<p.strokes.size();i++) { auto& v=p.strokes[i]; o<<(i?",":"")<<'['<<v.x0<<','<<v.y0<<','<<v.x1<<','<<v.y1<<']'; }
        o << ']'; p.strokes.clear();
    }
    bool events(std::ostream& o) override {
        if(direct.strokes.empty()&&offline.strokes.empty()&&raw.empty()) return false;
        o << "{\"direct\":"; paper_events(o,direct); o << ",\"offline\":"; paper_events(o,offline);
        o << ",\"records\":["; for(size_t i=0;i<raw.size();i+=2) o<<(i?",":"")<<'['<<raw[i]<<','<<raw[i+1]<<']';
        o << "]}"; raw.clear(); return true;
    }
    bool status(std::ostream& o) override {
        o << "{\"mode\":"<<mode<<",\"ready\":"<<(last>=busy_until)<<",\"records\":"<<records
          <<",\"strokes\":"<<direct.count<<",\"arcs\":"<<direct.circles<<",\"x\":"<<direct.x<<",\"y\":"<<direct.y
          <<",\"tape_records\":"<<tape_records<<",\"tape_strokes\":"<<offline.count<<",\"tape_arcs\":"<<offline.circles
          <<",\"tally\":"<<tape_tally<<'}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        if(op=="paper") {
            std::string which; s>>which;
            // [INFERENCE] Replacing paper preserves the mechanical pen position.
            PlotPaper& paper=which=="offline" ? offline : direct;
            paper.strokes.clear(); paper.count=paper.circles=0;
            if(which=="offline") { row_count=next_row=0; tape_records=0; }
            return "{}";
        }
        if(op=="tape") {
            std::string h;s>>h;
            if(h.size()%2)return "{\"error\":\"odd hex length\"}";
            auto hex=[](char c)->int {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;};
            for(char c:h)if(hex(c)<0)return "{\"error\":\"invalid tape hex\"}";
            for(size_t i=0;i<h.size();i+=2)tape_line((hex(h[i])<<4)|hex(h[i+1]));
            return "{\"records\":"+std::to_string(tape_records)+"}";
        }
        return Device::command(op,s);
    }
};
