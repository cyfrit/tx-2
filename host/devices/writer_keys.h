#pragma once
#include "../device.h"
#include <algorithm>
#include <deque>
#include <memory>
#include <vector>

// H63 4744-4943; Gilmore/Savell, The Lincoln Writer, 1959, pp.9-19:
// each pair shares physical case/script memory and manual routing controls.
struct WriterMechanism {
    // [INFERENCE] Initial paper/relay state is lower case, normal script, black;
    // initial manual wiring is keyboard→computer and computer→typewriter.
    bool upper = false, red = false;
    int script = 0;
    bool cpu_writer = true, cpu_punch = false, input_computer = true;
    bool input_writer = false, input_punch = false;
    unsigned writer_us = 100000, punch_us = 50000;
    uint64_t busy_until = 0;
    bool busy = false, pending_writer = false, pending_punch = false;
    unsigned pending_code = 0;
    std::vector<unsigned> printed, punched;
    void reset() {
        upper = red = false; script = 0; busy = false; busy_until = 0;
        printed.clear(); punched.clear();
    }
    void indication(unsigned c) {
        // [INFERENCE] CR retains color: the source names only case/script resets.
        if (c == 074 || c == 060) upper = false;
        if (c == 075) upper = true;
        if (c == 060 || c == 065) script = 0;
        if (c == 064) script = -1;
        if (c == 066) script = 1;
        if (c == 063) red = false;
        if (c == 067) red = true;
    }
    uint64_t duration(bool writer, bool punch) const {
        return std::max(writer ? writer_us : 0, punch ? punch_us : 0);
    }
    void begin(unsigned c, bool writer, bool punch, uint64_t now, uint64_t ticks) {
        busy = true; pending_code = c & 077; pending_writer = writer; pending_punch = punch;
        busy_until = now + 1 + duration(writer, punch) * ticks;
    }
    void finish(uint64_t now) {
        if (!busy || now < busy_until) return;
        complete();
    }
    // Keep the common deadline check inline even when the compiler outlines
    // the vector appends on the mechanical completion path.
    void complete() {
        if (pending_writer) { printed.push_back(pending_code); indication(pending_code); }
        // Text tape from the Writer carries the seventh hole; see LW pp.17-18.
        if (pending_punch) punched.push_back(0300 | pending_code);
        busy = false;
    }
};

struct WriterOutput : Device {
    std::shared_ptr<WriterMechanism> mechanism;
    bool builtin_started = false, feed_held = false;
    uint64_t feed_next = 0;
    WriterOutput(unsigned u, const char* name, std::shared_ptr<WriterMechanism> m)
        : Device(u, name), mechanism(std::move(m)) {}
    void reset() override { mechanism->reset(); builtin_started = feed_held = false; feed_next = 0; }
    bool active() const override { return mechanism->busy || feed_held; }
    bool ready(uint64_t now) override { mechanism->finish(now); return !mechanism->busy; }
    uint64_t mask() const override { return 077; }
    void transfer(uint64_t w, uint64_t now) override {
        mechanism->begin(w, mechanism->cpu_writer, mechanism->cpu_punch, now, *ticks_per_us);
    }
    // Builtin 66 keeps its RTL buffer full through physical completion. The
    // first valid observation starts the mechanism; only completion ACKs it.
    bool builtin_ready(bool valid, unsigned code, uint64_t now) {
        mechanism->finish(now);
        if (!valid) { builtin_started = false; return false; }
        if (!builtin_started && !mechanism->busy) { transfer(code, now); builtin_started = true; }
        return builtin_started && !mechanism->busy;
    }
    void builtin_ack() { builtin_started = false; }
    void tick(uint64_t now) override {
        mechanism->finish(now);
        // LW 783-805: TAPE FEED punches blank lines while its button is held.
        if (feed_held && !mechanism->busy && now >= feed_next) {
            mechanism->punched.push_back(0200);
            feed_next = now + 1 + us(mechanism->punch_us);
        }
    }
    bool events(std::ostream& o) override {
        auto& m = *mechanism;
        if (m.printed.empty() && m.punched.empty()) return false;
        o << "{\"codes\":[";
        for (size_t i = 0; i < m.printed.size(); ++i) o << (i ? "," : "") << m.printed[i];
        o << "],\"punch\":[";
        for (size_t i = 0; i < m.punched.size(); ++i) o << (i ? "," : "") << m.punched[i];
        o << "]}"; m.printed.clear(); m.punched.clear(); return true;
    }
    bool status(std::ostream& o) override {
        auto& m = *mechanism;
        o << "{\"upper\":" << m.upper << ",\"script\":" << m.script << ",\"red\":" << m.red
          << ",\"busy\":" << m.busy << ",\"writer\":" << m.cpu_writer << ",\"punch\":" << m.cpu_punch << '}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        auto& m = *mechanism;
        if (op == "us") { s >> m.writer_us; return "{}"; }
        if (op == "punch_us") { s >> m.punch_us; return "{}"; }
        if (op == "route") {
            unsigned w = 0, p = 0; s >> w >> p;
            if ((w && m.input_writer) || (p && m.input_punch)) return "{\"error\":\"output is already connected to an input source\"}";
            m.cpu_writer = w; m.cpu_punch = p; return "{}";
        }
        if (op == "feed") { s >> feed_held; return "{}"; }
        // LW 1959 says 72; the later PETR handbook specifies 73. [INFERENCE] Use
        // the 1961-63 interoperable mark; retain the dated discrepancy here.
        if (op == "endmark") { m.punched.push_back(0200 | 073); return "{}"; }
        return Device::command(op, s);
    }
};

struct WriterKeys : Device {
    std::shared_ptr<WriterMechanism> mechanism;
    // bit 7 means a literal transmitted code for CLI/diagnostic input; otherwise
    // bit 6 identifies a physical keyboard's case, never a CPU data bit.
    std::deque<unsigned> keys;
    std::vector<unsigned char> tape;
    size_t position = 0;
    // [INFERENCE] 50 ms is UI queued-key pacing; the keyboard clock is unspecified.
    unsigned key_us = 50000, reader_rate = 190;
    uint64_t ready_at = 0, now_ = 0;
    bool reader = false, stop_held = false, single = false;
    bool green_stop = true, green_delete = true, green_no7 = true, green_blank = true;
    bool offered = false, offered_reader = false, case_prefix = false;
    unsigned code = 0;
    WriterKeys(unsigned u, const char* name, std::shared_ptr<WriterMechanism> m)
        : Device(u, name), mechanism(std::move(m)) {}
    void reset() override {
        keys.clear(); position = 0; ready_at = now_ = 0; reader = stop_held = single = offered = case_prefix = false;
    }
    bool input() const override { return true; }
    bool active() const override { return !offered && (reader || !keys.empty()); }
    uint64_t mask() const override { return 077; }
    bool ready(uint64_t) override { return offered && mechanism->input_computer; }
    uint64_t data(uint64_t) override { return code; }
    void accept(uint64_t now) {
        auto& m = *mechanism;
        if (m.input_writer || m.input_punch) m.begin(code, m.input_writer, m.input_punch, now, *ticks_per_us);
        // The case relay is updated by transmitted keyboard/reader case codes,
        // including a two-TSD automatic case prefix; see LW 550-574.
        if (code == 074 || code == 060) m.upper = false;
        if (code == 075) m.upper = true;
        offered = false;
        if (case_prefix) { case_prefix = false; ready_at = now + 1; return; }
        if (offered_reader) {
            ready_at = now + (uint64_t(10000000) * *ticks_per_us) / reader_rate;
            if (single) { reader = false; single = false; }
        } else {
            if (!keys.empty()) keys.pop_front();
            ready_at = now + 1 + us(key_us);
        }
    }
    void transfer(uint64_t, uint64_t now) override { if (offered) accept(now); }
    void tick(uint64_t now) override {
        now_ = now; auto& m = *mechanism; m.finish(now);
        if (offered) { if (!m.input_computer && !m.busy) accept(now); return; }
        if (now < ready_at || m.busy) return;
        if (reader) {
            while (position < tape.size()) {
                const unsigned b = tape[position++], c = b & 077;
                if (!(b & 0200)) continue; // .tape's feed-hole marker
                // Even an ignored blank/delete takes one mechanical line.
                ready_at = now + (uint64_t(10000000) * *ticks_per_us) / reader_rate;
                if (single) { reader = false; single = false; }
                if (c == 076 && green_stop) { reader = false; return; }
                if (c == 077 && green_delete) return;
                if (!(b & 0100)) {
                    if (c == 0 && green_blank) return;
                    if (c != 0 && green_no7) { reader = false; return; }
                    // LW manual: red no-seventh-hole mode reproduces to punch,
                    // rather than transmitting binary lines to the computer.
                    if (m.input_punch) m.punched.push_back(b);
                    return;
                }
                code = c; offered = offered_reader = true; break;
            }
            if (!offered) { reader = false; return; }
        } else if (!keys.empty()) {
            const unsigned key = keys.front();
            code = key & 077; offered_reader = false; case_prefix = false;
            if (!(key & 0200) && code < 060 && (code < 014 || code > 017) && bool(key & 0100) != m.upper) {
                code = key & 0100 ? 075 : 074; case_prefix = true;
            }
            offered = true;
        }
        if (offered && !m.input_computer) accept(now);
    }
    bool status(std::ostream& o) override {
        o << "{\"keys\":" << keys.size() << ",\"locked\":" << offered << ",\"reader\":" << reader
          << ",\"position\":" << position << ",\"size\":" << tape.size() << ",\"rate\":" << reader_rate
          << ",\"computer\":" << mechanism->input_computer << ",\"writer\":" << mechanism->input_writer
          << ",\"punch\":" << mechanism->input_punch << '}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        if (op == "keys" || op == "key") {
            if (reader) return "{\"error\":\"keyboard is interlocked while reading tape\"}";
            unsigned c; while (s >> c) keys.push_back(op == "keys" ? 0200 | (c & 077) : c & 0177);
            return "{\"keys\":" + std::to_string(keys.size()) + "}";
        }
        if (op == "us") { s >> key_us; return "{}"; }
        if (op == "route") {
            unsigned cpu = 0, w = 0, p = 0; s >> cpu >> w >> p; auto& m = *mechanism;
            if ((w && m.cpu_writer) || (p && m.cpu_punch)) return "{\"error\":\"output is already connected to the computer\"}";
            m.input_computer = cpu; m.input_writer = w; m.input_punch = p; return "{}";
        }
        if (op == "tape") {
            std::string hex; s >> hex;
            if (hex.size() % 2) return "{\"error\":\"tape data must contain hexadecimal bytes\"}";
            std::vector<unsigned char> bytes;
            for (size_t i = 0; i < hex.size(); i += 2) {
                unsigned v = 0; std::istringstream in(hex.substr(i, 2));
                if (!(in >> std::hex >> v)) return "{\"error\":\"tape data must contain hexadecimal bytes\"}";
                bytes.push_back(v);
            }
            tape = std::move(bytes); position = 0; reader = offered = false; return "{}";
        }
        if (op == "rate") {
            unsigned v = 0; s >> v;
            // rate is tenths of lines/s: the physical selector is 9.5/19.
            if (v != 95 && v != 190) return "{\"error\":\"rate must be 95 or 190, in tenths of a line per second\"}";
            reader_rate = v; return "{}";
        }
        if (op == "filters") {
            s >> green_stop >> green_delete >> green_no7 >> green_blank; return "{}";
        }
        if (op == "stop") { reader = false; if (offered_reader) offered = false; return "{}"; }
        if (op == "holdstop") { s >> stop_held; return "{}"; }
        if (op == "start") {
            if (offered || !keys.empty()) return "{\"error\":\"keyboard is still locked\"}";
            reader = true; single = stop_held; ready_at = now_; return "{}";
        }
        // Rewind's no-tape interlock is a manual contact, not tape emptiness.
        if (op == "rewind") {
            unsigned no_tape = 0; s >> no_tape;
            if (reader || !no_tape) return "{\"error\":\"rewind requires a stopped reader and the no-tape contact\"}";
            position = 0; return "{}";
        }
        return Device::command(op, s);
    }
};
