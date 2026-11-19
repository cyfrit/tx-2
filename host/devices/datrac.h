#pragma once
#include "../device.h"
#include <algorithm>
#include <cmath>
#include <vector>

// H63 PDF pp99–100 / H61 pp105–106, Epsco DATRAC unit 50.
// The four numbered panel connectors are trigger inputs, not analog channels.
struct Datrac : Device {
    enum Wave { DC, SINE, SQUARE, TRIANGLE };
    // [INFERENCE] Initial panel: power off, programmed-trigger switch up.
    bool powered = false, programmed = true, timer_route = false;
    bool converting = false, unread = false, misind = false, have_trigger = false;
    uint64_t now = 0, power_at = 0, source_at = 0, last_trigger = 0, due = 0, next_oscillator = 0;
    uint64_t samples = 0, too_fast = 0;
    unsigned buffer = 0, pending = 0;
    Wave wave = DC;
    double level = 0, frequency = 100, offset = 0, range = 1, oscillator = 0;
    struct Sample { uint64_t clock; unsigned value; double volts; };
    std::vector<Sample> output;
    double pending_volts = 0;
    Datrac() : Device(050, "datrac") {}
    void reset() override {
        powered = false; programmed = true; timer_route = false;
        converting = unread = misind = have_trigger = false;
        now = power_at = source_at = last_trigger = due = next_oscillator = samples = too_fast = 0;
        buffer = pending = 0; wave = DC; level = offset = oscillator = pending_volts = 0;
        frequency = 100; range = 1; output.clear();
    }
    bool input() const override { return true; }
    void complete(uint64_t t) {
        if (converting && t >= due) {
            converting = false; unread = true; buffer = pending; samples++;
            output.push_back({last_trigger, buffer, pending_volts});
        }
    }
    bool ready(uint64_t t) override {
        complete(t); // Drive flag/ready before this clock's RTL sampling edge.
        return powered && unread && !converting;
    }
    bool active() const override { return converting || (powered && oscillator > 0); }
    uint64_t data(uint64_t) override { return buffer; }
    // PDF p99: IOB occupies the right two quarters. No sign extension.
    uint64_t mask() const override { return 0777777; }
    bool missed() const override { return misind; }
    double signal(uint64_t t) const {
        if (wave == DC) return offset + level;
        double phase = std::fmod(double(t - source_at) / us(1000000) * frequency, 1.0);
        double v = wave == SINE ? std::sin(phase * 6.2831853071795864769) :
                   wave == SQUARE ? (phase < .5 ? 1 : -1) : 1 - 4 * std::abs(phase - .5);
        return offset + level * v;
    }
    void trigger(uint64_t t) {
        if (!powered) return;
        if (unread || converting) misind = true; // p99 note 3: trigger before TSD.
        if (have_trigger && t - last_trigger < us(37)) {
            // p99 prohibits trigger intervals below 37 us due to possible circuit
            // damage, without defining a digital result. [INFERENCE] Model a
            // refractory converter: reject the pulse and count the violation.
            too_fast++; return;
        }
        have_trigger = true; last_trigger = t;
        pending_volts = signal(t);
        const double fraction = std::clamp(pending_volts / range, -1.0, 1.0);
        // Signed 18-bit fraction: sign plus 17 fractional bits. Saturate +1 to
        // 1-2^-17. [INFERENCE] Ideal nearest quantization; hardware guarantees 8–11
        // leading bits and specifies neither rounding nor a noise distribution.
        const unsigned magnitude = std::min(0377777u, unsigned(std::llround(std::abs(fraction) * 131072.0)));
        pending = std::signbit(fraction) ? ((~magnitude) & 0777777) : magnitude;
        unread = false; converting = true; due = t + us(22);
    }
    void timer_pulse(uint64_t t) override { if (timer_route) trigger(t); }
    void control(unsigned c, uint64_t t) override {
        now = t;
        if ((c & 070000) == 020000) misind = false;
        if ((c & 070000) == 030000 && programmed) trigger(t);
    }
    void transfer(uint64_t, uint64_t t) override {
        unread = false;
        if (programmed) trigger(t); // IOS and TSD pulses are manually panel-routed.
    }
    void tick(uint64_t t) override {
        now = t;
        complete(t);
        if (powered && oscillator > 0 && t >= next_oscillator) {
            trigger(t);
            next_oscillator = t + std::max(uint64_t(1), uint64_t(std::llround(us(1000000) / oscillator)));
        }
    }
    bool events(std::ostream& o) override {
        if (output.empty()) return false;
        o << '['; bool first = true;
        for (const auto& s : output) {
            o << (first ? "" : ",") << "{\"clock\":" << s.clock << ",\"word\":" << s.value << ",\"volts\":" << s.volts << '}'; first = false;
        }
        o << ']'; output.clear(); return true;
    }
    const char* wave_name() const { return wave == DC ? "dc" : wave == SINE ? "sine" : wave == SQUARE ? "square" : "triangle"; }
    bool status(std::ostream& o) override {
        o << "{\"power\":" << powered << ",\"programmed\":" << programmed << ",\"timer\":" << timer_route
          << ",\"ready\":" << ready(now) << ",\"converting\":" << converting << ",\"missed\":" << misind
          << ",\"samples\":" << samples << ",\"tooFast\":" << too_fast << ",\"range\":" << range
          << ",\"source\":\"" << wave_name() << "\",\"level\":" << level << ",\"frequency\":" << frequency
          << ",\"offset\":" << offset << ",\"volts\":" << signal(now) << ",\"oscillator\":" << oscillator
          << ",\"word\":" << buffer << ",\"warmupSeconds\":" << (powered ? (now - power_at) / us(1000000) : 0)
          << ",\"stable\":" << (powered && now - power_at >= us(1800000000)) << '}';
        return true;
    }
    std::string command(const std::string& op, std::istringstream& a) override {
        if (op == "power") {
            int on;
            if (!(a >> on)) return "{\"error\":\"power requires 0 or 1\"}";
            if (on && !powered) power_at = now;
            powered = on != 0;
            if (!powered) converting = unread = have_trigger = false;
        } else if (op == "route") {
            std::string route; int on;
            if (!(a >> route >> on) || (route != "programmed" && route != "timer")) return "{\"error\":\"route programmed|timer 0|1\"}";
            (route == "programmed" ? programmed : timer_route) = on != 0;
        } else if (op == "trigger") {
            unsigned connector = 1; a >> connector;
            if (connector < 1 || connector > 4) return "{\"error\":\"trigger input is 1–4\"}";
            trigger(now);
        } else if (op == "range") {
            double v;
            if (!(a >> v) || (v != 1 && v != 10 && v != 100)) return "{\"error\":\"range is 1, 10 or 100 volts\"}";
            range = v;
        } else if (op == "oscillator") {
            double hz;
            if (!(a >> hz) || !std::isfinite(hz) || hz < 0 || hz > 1000000) return "{\"error\":\"oscillator requires 0–1000000 Hz; 0 disconnects\"}";
            oscillator = hz; next_oscillator = now;
        } else if (op == "source") {
            std::string shape; double l, f = 100, o = 0;
            if (!(a >> shape >> l) || !std::isfinite(l)) return "{\"error\":\"source dc|sine|square|triangle level [Hz offset]\"}";
            a >> f >> o;
            if (!std::isfinite(f) || f < 0 || !std::isfinite(o)) return "{\"error\":\"invalid signal parameters\"}";
            if (shape != "dc" && shape != "sine" && shape != "square" && shape != "triangle") return "{\"error\":\"unknown waveform\"}";
            wave = shape == "dc" ? DC : shape == "sine" ? SINE : shape == "square" ? SQUARE : TRIANGLE;
            level = l; frequency = f; offset = o; source_at = now;
        } else return "{\"error\":\"unknown DATRAC control\"}";
        return "{\"ok\":true}";
    }
};
