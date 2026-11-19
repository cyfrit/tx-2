#pragma once
#include "../device.h"
#include <array>
#include <fstream>
#include <map>
#include <vector>

// Sources: references/device-specs/magnetic-tape.md §§3–5; UH63 §§3-6, 6-3.7;
// Sketchpad sk.tx2as:4440–4886, 5688–6030, 6131–6313. Images describe controller
// transfers, not flux transitions: the unpublished controller specifications do
// not establish physical IBM character packing or the TX-2 mark encoding.
namespace magnetic_image {
inline std::string quoted(const std::string& text) {
    std::string out = "\"";
    for (char c : text) {
        if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else out += c;
    }
    return out + '"';
}
inline std::string error(const char* text) { return "{\"error\":" + quoted(text) + "}"; }
}

// Unit 046: four transports, UH63:3016–3018; bidirectional nine-bit lines,
// TM1:1809–1811. A formatted block has 128 words. Coarse/fine marks and the
// dummy/checksum boundaries follow Sketchpad WR2/SCF2/TX2RDLOOP.
struct Tx2MagTape : Device {
    // [INFERENCE] Minimal reversible controller-slot layout from the listing's
    // boundary transfers; physical mark spacing is undocumented.
    static constexpr int cells = 521;
    using Body = std::array<uint16_t, 516>; // prologue, 512 data lines, trailer
    struct Drive {
        bool mounted = false, protect = false;
        unsigned blocks = 040000; // 2,097,152 words, UH63:3016–3018
        int64_t position = -1;
        std::map<unsigned, Body> written;
    };
    std::array<Drive, 4> drives;
    unsigned selected = 0, selection = 0, mode = 0;
    bool connected = false, full = false, mis = false, eia = false, cleared = false;
    uint16_t buffer = 0;
    uint64_t next = 0, transfers = 0;
    // TM1:380–403 specifies 125 us at 60 ips. [INFERENCE] All speed codes use this
    // documented period by default; their code-to-speed mapping is unavailable.
    unsigned line_us = 125;
    Tx2MagTape() : Device(046, "magtape") {}
    void reset() override {
        connected = full = mis = eia = cleared = false; mode = 0; selected = selection = 0;
        next = transfers = 0;
        // Reset control electronics; mounted reels and physical position persist.
    }
    Drive& drive() { return drives[selected]; }
    const Drive& drive() const { return drives[selected]; }
    bool input() const override { return !(mode & 0400); }
    bool reverse() const override { return mode & 4; }
    bool assembly() const override { return mode & 2; } // TM2 Fig.15-12, PDF p.392
    unsigned assembly_width() const override { return 9; }
    uint64_t mask() const override { return 0777; }
    bool missed() const override { return mis; }
    bool inability() const override { return eia; }
    bool active() const override { return connected && drive().mounted && !eia; }
    bool clear_alarms() override { bool c = cleared; cleared = false; return c; }
    bool ready(uint64_t now) override {
        return connected && drive().mounted && !eia && (input() ? full : !full);
    }
    uint64_t data(uint64_t) override { return buffer; }
    unsigned special() const override {
        const auto& d = drive();
        unsigned report = 1u << 5; // 4.3 selection complete; SK:4500–4502
        if (!d.mounted) report |= 1u << 8; // 4.6 LTO: search's unit-not-ready test
        if (d.protect && !input()) report |= 1u << 7; // [INFERENCE] write-key condition
        if (d.mounted && d.position >= int64_t(d.blocks) * cells - 1) report |= 1u << 10;
        if (d.mounted && d.position < 0) report |= 1u << 11;
        return report;
    }
    void alarms_clear() { mis = eia = false; cleared = true; }
    void control(unsigned c, uint64_t now) override {
        const unsigned function = c & 070000;
        if (function == 060000) {
            // Fig.15-12 gives nine selection-register bits, SER1–SER9.
            // [INFERENCE] Low two bits decode the four transports; full decoding is
            // unavailable. Preserve the complete register for inspection.
            selection = c & 0777; selected = selection & 3;
            full = false; next = now + us(line_us); return;
        }
        if (function == 020000) { connected = full = false; alarms_clear(); return; }
        if (function != 030000) return;
        if (c & 04000) alarms_clear();
        const unsigned old = mode;
        mode = (c == 034000) ? old : c & 03777;
        connected = true;
        if (!drive().mounted || (!input() && drive().protect)) eia = true;
        if ((old & 0504) != (mode & 0504)) full = false;
        // Switching RM/RL preserves the head position; starting a write after
        // reading its fine mark skips the dummy slot; see SK:4810–4821.
        if (!(old & 0400) && (mode & 0400) && drive().position >= 0) {
            int off = int(drive().position % cells);
            if ((!reverse() && off == 1) || (reverse() && off == cells - 1))
                drive().position += reverse() ? -1 : 1;
        }
        if ((old & 0504) != (mode & 0504) || !next) next = now + us(line_us);
    }
    uint16_t line(int64_t p) const {
        const auto& d = drive();
        // [INFERENCE] TX2TOGCHK masks the address with 7 and compares BLOCK MARK=6
        // at SK:3658,6310–6313: block addresses are 6+010*b.
        const unsigned block = unsigned(p / cells), off = unsigned(p % cells);
        if (off == 0) {
            const unsigned address = (reverse() && block ? block - 1 : block) * 010 + 6;
            return (address >> 9) & 0777;
        }
        if (off == 1 || off == cells - 1) return (block * 010 + 6) & 0777;
        if (off == 2 || off == cells - 2) return 0;
        auto it = d.written.find(block);
        return it == d.written.end() ? (off <= 4 ? 0777 : 0) : it->second[off - 3];
    }
    void tick(uint64_t now) override {
        if (now < next || !connected || eia || !drive().mounted) return;
        auto& d = drive();
        const int64_t p = d.position + (reverse() ? -1 : 1);
        if (p < 0 || p >= int64_t(d.blocks) * cells) { full = false; if (!input()) eia = true; return; }
        d.position = p;
        next = now + us(line_us);
        if (input()) {
            if ((mode & 0100) && p % cells != 0) return;
            if (full) mis = true;
            buffer = line(p); full = true;
            return;
        }
        // A TSD fills the output buffer; tape motion empties it independently;
        // see TM2:14854–14915. Stalling the CPU cannot stall the transport.
        // [INFERENCE] An underrun preserves the previous cell; the sources establish
        // MISIND, but do not establish which physical pattern an underrun writes.
        if (!full) { mis = true; return; }
        full = false;
        const unsigned off = unsigned(p % cells), block = unsigned(p / cells);
        if (off < 3 || off > 518) { eia = true; return; } // never write block marks
        auto result = d.written.try_emplace(block);
        if (result.second) { result.first->second.fill(0); result.first->second[0] = result.first->second[1] = 0777; }
        result.first->second[off - 3] = buffer;
    }
    void transfer(uint64_t word, uint64_t) override {
        ++transfers;
        if (input()) { full = false; return; }
        if (!drive().mounted || drive().protect) { eia = true; return; }
        buffer = word & 0777; full = true;
    }
    void image(std::ostream& o, const Drive& d) const {
        o << "TX2MT1 " << std::oct << d.blocks << '\n';
        for (const auto& entry : d.written) {
            o << "B " << entry.first;
            for (auto v : entry.second) o << ' ' << v;
            o << '\n';
        }
        o << "END\n";
    }
    bool mount(std::istream& in, Drive& target) {
        Drive d; std::string tag; unsigned n;
        if (!(in >> tag >> std::oct >> n) || tag != "TX2MT1" || !n || n > 0100000) return false;
        d.mounted = true; d.blocks = n;
        while (in >> tag) {
            if (tag == "END") { target = std::move(d); return true; }
            if (tag != "B" || !(in >> n) || n >= d.blocks || d.written.count(n)) return false;
            Body b;
            for (auto& v : b) { unsigned value; if (!(in >> value) || value > 0777) return false; v = value; }
            d.written.emplace(n, b);
        }
        return false;
    }
    bool status(std::ostream& o) override {
        o << "{\"selected\":" << selected << ",\"selection\":" << selection << ",\"mode\":" << mode << ",\"input\":" << input()
          << ",\"connected\":" << connected << ",\"mis\":" << mis << ",\"eia\":" << eia
          << ",\"speed\":" << ((mode >> 3) & 7) << ",\"assembly\":" << assembly()
          << ",\"periodUs\":" << line_us << ",\"transfers\":" << transfers << ",\"drives\":[";
        for (unsigned i = 0; i < 4; ++i) {
            const auto& d = drives[i];
            if (i) o << ',';
            o << "{\"mounted\":" << d.mounted << ",\"protect\":" << d.protect << ",\"blocks\":" << d.blocks
              << ",\"position\":" << d.position << ",\"written\":" << d.written.size() << '}';
        }
        o << "]}"; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        if (op == "status") { std::ostringstream o; status(o); return o.str(); }
        if (op == "us") { unsigned n; if (!(s >> n) || !n) return magnetic_image::error("period must be greater than zero"); line_us = n; return "{}"; }
        unsigned index;
        if (!(s >> std::oct >> index) || index >= 4) return magnetic_image::error("drive number must be 0–3");
        auto& d = drives[index];
        if (connected && selected == index && op != "export" && op != "save") return magnetic_image::error("disconnect the active tape before changing media");
        if (op == "create") {
            unsigned blocks = 040000; s >> blocks;
            if (!blocks || blocks > 0100000) return magnetic_image::error("block count exceeds the address range");
            d = Drive{}; d.mounted = true; d.blocks = blocks; return "{}";
        }
        if (op == "eject") { d = Drive{}; return "{}"; }
        if (op == "protect") { unsigned n; if (!(s >> n) || n > 1) return magnetic_image::error("write protection must be 0 or 1"); d.protect = n; return "{}"; }
        if (op == "rewind") { d.position = -1; return "{}"; }
        if (op == "load") { std::string path; std::getline(s >> std::ws, path); std::ifstream in(path); if (!mount(in, d)) return magnetic_image::error("invalid TX-2 tape image"); return "{}"; }
        if (op == "import") { if (!mount(s, d)) return magnetic_image::error("invalid TX-2 tape image"); return "{}"; }
        if (!d.mounted) return magnetic_image::error("no tape mounted");
        if (op == "export") { std::ostringstream o; image(o, d); return "{\"image\":" + magnetic_image::quoted(o.str()) + "}"; }
        if (op == "save") { std::string path; std::getline(s >> std::ws, path); std::ofstream out(path); image(out, d); if (!out) return magnetic_image::error("failed to save tape image"); return "{}"; }
        return magnetic_image::error("unknown tape operation");
    }
};

// Unit 045: abstract binary halfword records. IBM IOS aliases are SK:3628–3635;
// record/gap and reverse verification: SK:5713–5794, 5905–6007. Density/parity,
// physical tape marks and controller LRC are unspecified in the available sources.
struct IbmMagTape : Device {
    bool mounted = false, protect = false, connected = false, full = false;
    bool mis = false, eia = false, cleared = false, writing = false;
    bool gap = false, started = false, rewinding = false;
    unsigned operation = 3, record = 0;
    int64_t offset = 0;
    uint32_t buffer = 0;
    uint64_t next = 0, transfers = 0;
    // [INFERENCE] 125-us halfwords satisfy Sketchpad's 400-us watchdog. No IBM
    // controller transfer period is published; gaps exceed its 200-us detector.
    unsigned halfword_us = 125;
    // [INFERENCE] A conservative 16-ms physical gap permits both the 200-us
    // gap detector and the reverse reader's 2-ms run-out; see SK:5934,5992–6007.
    static constexpr unsigned gap_us = 16000;
    std::vector<std::vector<uint32_t>> records;
    std::vector<uint32_t> pending;
    IbmMagTape() : Device(045, "ibmtape") {}
    void reset() override {
        connected = full = mis = eia = cleared = writing = false;
        gap = started = rewinding = false;
        operation = 3; next = transfers = 0; pending.clear();
    }
    // [INFERENCE] Rewind completes a control/output operation and supplies no input datum.
    // Its flag is an edge; holding an input-ready level would repeatedly undo
    // the program's dismissal while the interval-timer sequence owns the delay.
    bool input() const override { return !(writing || operation == 0); }
    uint64_t mask() const override { return 0777777; }
    bool reverse() const override { return operation == 6; }
    bool missed() const override { return mis; }
    bool inability() const override { return eia; }
    bool clear_alarms() override { bool c = cleared; cleared = false; return c; }
    bool active() const override { return connected && mounted && !eia && (writing || rewinding || operation == 2 || operation == 4 || operation == 6); }
    bool ready(uint64_t now) override {
        // ²⁰45RWD dismisses the sequence at SK:5978; completion must raise its
        // flag so it can reach the explicit delay that follows the IOS.
        return connected && mounted && !eia && (writing ? !full : operation == 0 ? now >= next : full);
    }
    uint64_t data(uint64_t) override { return buffer; }
    void control(unsigned c, uint64_t now) override {
        const unsigned function = c & 070000;
        if (function == 020000) { connected = full = writing = gap = started = rewinding = false; mis = eia = false; cleared = true; return; }
        if (function != 030000) return;
        connected = true;
        full = (c & 7) == 7 && writing && full; // WCS drains a queued final halfword
        gap = started = rewinding = false;
        if (!mounted) { eia = true; return; }
        operation = c & 7;
        if (operation == 0) {
            record = 0; offset = 0; writing = false; rewinding = true;
            // [INFERENCE] Use the listing's rewind wait as the completion delay;
            // the IBM controller's rated rewind time is unpublished.
            next = now + us(31600);
        }
        else if (operation == 2) { writing = false; offset = 0; next = now + us(halfword_us); }
        else if (operation == 4) { writing = false; next = now + us(3160); }
        else if (operation == 5) {
            writing = true; pending.clear(); if (protect) eia = true;
            // GFW changes motion/mode and preserves idle buffer availability.
            // [INFERENCE] Preserve ready until a TSD fills it; a spurious busy/ready
            // edge would interrupt SQ45DELAY at SK:5905–5911 prematurely.
            next = now;
        }
        else if (operation == 6) {
            writing = false;
            if (record) { --record; offset = int64_t(records[record].size()) - 1; }
            else offset = -1;
            next = now + us(halfword_us);
        } else if (operation == 7) {
            if (writing && !eia) {
                if (full) { pending.push_back(buffer); full = false; }
                // [INFERENCE] Writing a record erases the following logical tail;
                // record-oriented images do not encode a physical gap length.
                records.resize(record); records.push_back(std::move(pending)); ++record;
            }
            writing = false; offset = 0;
        } else writing = false;
    }
    void tick(uint64_t now) override {
        if (now < next) return;
        if (rewinding) rewinding = false;
        if (!connected || !mounted || eia) return;
        if (writing) {
            if (!started) return;
            if (full) pending.push_back(buffer);
            else mis = true; // [INFERENCE] an underrun appends no halfword
            full = false; next = now + us(halfword_us);
            return;
        }
        if (operation != 2 && operation != 6) return;
        if (gap) {
            gap = false;
            if (reverse()) {
                if (!record) return;
                --record; offset = int64_t(records[record].size()) - 1;
            }
        }
        if (record >= records.size() || offset < 0 || offset >= int64_t(records[record].size())) return;
        if (full) mis = true;
        buffer = records[record][size_t(offset)]; full = true;
        offset += reverse() ? -1 : 1;
        if (offset < 0 || offset == int64_t(records[record].size())) {
            if (!reverse()) { ++record; offset = 0; }
            gap = true; next = now + us(gap_us);
        } else next = now + us(halfword_us);
    }
    void transfer(uint64_t word, uint64_t now) override {
        ++transfers;
        if (writing) {
            buffer = word & 0777777; full = true;
            if (!started) { started = true; next = now + us(halfword_us); }
        } else full = false;
    }
    void image(std::ostream& out) const {
        out << "TX2IBM1\n" << std::oct;
        for (const auto& r : records) { out << "R " << r.size(); for (auto v : r) out << ' ' << v; out << '\n'; }
        out << "END\n";
    }
    bool mount(std::istream& in) {
        std::string tag;
        if (!(in >> tag) || tag != "TX2IBM1") return false;
        std::vector<std::vector<uint32_t>> image;
        while (in >> tag) {
            if (tag == "END") { records = std::move(image); mounted = true; protect = false; record = 0; offset = 0; return true; }
            unsigned n;
            if (tag != "R" || !(in >> std::oct >> n) || n > 02000000) return false;
            std::vector<uint32_t> r(n);
            for (auto& v : r) if (!(in >> v) || v > 0777777) return false;
            image.push_back(std::move(r));
        }
        return false;
    }
    bool status(std::ostream& o) override {
        o << "{\"mounted\":" << mounted << ",\"protect\":" << protect << ",\"connected\":" << connected
          << ",\"operation\":" << operation << ",\"record\":" << record << ",\"offset\":" << offset
          << ",\"records\":" << records.size() << ",\"pending\":" << pending.size() << ",\"transfers\":" << transfers
          << ",\"gap\":" << gap << ",\"gapUs\":" << gap_us << ",\"rewinding\":" << rewinding << ",\"writing\":" << writing
          << ",\"periodUs\":" << halfword_us << ",\"mis\":" << mis << ",\"eia\":" << eia << '}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        if (op == "status") { std::ostringstream o; status(o); return o.str(); }
        if (op == "us") { unsigned n; if (!(s >> n) || !n) return magnetic_image::error("period must be greater than zero"); halfword_us = n; return "{}"; }
        // Host media management is a UI facility. [INFERENCE] Allow replacement
        // while stopped: Sketchpad leaves 045 logically connected after SRM
        // at SK:5790; connection alone does not mean that the tape is moving.
        if (connected && (writing || operation == 2 || operation == 4 || operation == 6) && op != "export" && op != "save")
            return magnetic_image::error("stop the active tape before changing media");
        if (op == "create") { records.clear(); mounted = true; record = 0; offset = 0; protect = false; return "{}"; }
        if (op == "eject") { records.clear(); mounted = false; return "{}"; }
        if (op == "rewind") { record = 0; offset = 0; return "{}"; }
        if (op == "protect") { unsigned n; if (!(s >> n) || n > 1) return magnetic_image::error("write protection must be 0 or 1"); protect = n; return "{}"; }
        if (op == "load") { std::string path; std::getline(s >> std::ws, path); std::ifstream in(path); if (!mount(in)) return magnetic_image::error("invalid IBM tape image"); return "{}"; }
        if (op == "import") { if (!mount(s)) return magnetic_image::error("invalid IBM tape image"); return "{}"; }
        if (!mounted) return magnetic_image::error("no tape mounted");
        if (op == "export") { std::ostringstream o; image(o); return "{\"image\":" + magnetic_image::quoted(o.str()) + "}"; }
        if (op == "save") { std::string path; std::getline(s >> std::ws, path); std::ofstream out(path); image(out); if (!out) return magnetic_image::error("failed to save tape image"); return "{}"; }
        return magnetic_image::error("unknown tape operation");
    }
};
