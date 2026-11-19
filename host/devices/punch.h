#pragma once
#include "../device.h"
#include <algorithm>
#include <vector>

// H63:4651–4730; TM2:14265–14436. One TSD loads one six-bit line.
// Motor/cycle profile follows the 1961/63 handbook punch at 180 lines/s.
// Sketchpad TR296:4375 describes a revision rated at 300 lines/s.
struct Punch : Device {
    unsigned mode = 0, line_us = 5556, startup_us = 1000000, feed_delay_us = 5000000;
    bool connected = false, motor = false, pending = false, manual_feed = false;
    bool low = false, supply = false, end = false, lubrication = false, maintenance_switch = false;
    bool ack = false, lamp = false, eia = false, clear_eia = false;
    bool reeler_brake = false, motor_switch = true;
    uint8_t buffer = 0;
    uint64_t motor_ready = 0, motor_stop = 0, punch_end = 0, feed_end = 0;
    uint64_t last_tick = 0, running_ticks = 0, feed_start = 0;
    std::vector<unsigned> lines;
    uint64_t total = 0;
    Punch() : Device(063, "punch") {}
    void reset() override {
        mode = 0; connected = motor = pending = manual_feed = false;
        low = supply = end = lubrication = maintenance_switch = ack = lamp = eia = clear_eia = false;
        reeler_brake = false; motor_switch = true;
        motor_ready = motor_stop = punch_end = feed_end = last_tick = running_ticks = feed_start = total = 0;
        lines.clear();
    }
    bool inhibited() const { return supply || end || lubrication; }
    bool alarm() const { return low || inhibited(); }
    bool active() const override { return motor || manual_feed || last_tick < feed_end; }
    bool ready(uint64_t) override { return !pending; }
    bool assembly() const override { return mode & 2; }
    bool inability() const override { return eia; }
    bool maintenance() const override { return maintenance_switch; }
    bool clear_alarms() override { const bool v = clear_eia; clear_eia = false; return v; }
    void start_motor(uint64_t now) {
        if (!motor_switch || lubrication) return;
        if (!motor) { motor = true; motor_ready = now + us(startup_us); }
        motor_stop = now + us(5000000);
    }
    void control(unsigned c, uint64_t) override {
        // Flag-only/report IOS must preserve the mode; see SK2:6835–6837.
        if ((c & 030000) == 030000) {
            if (!connected) { eia = false; clear_eia = true; }
            connected = true; mode = c & 07777;
        } else if ((c & 030000) == 020000) connected = false;
    }
    void transfer(uint64_t w, uint64_t now) override {
        buffer = 0x80 | ((mode & 4) ? 0x40 : 0) | unsigned(w & 077);
        pending = true; start_motor(now);
        if (alarm() || lamp) eia = true;
        // [INFERENCE] The sources give the total rate, but not numerical punch/feed
        // phase lengths. Split the cycle equally; END PUNCH releases the buffer.
        punch_end = std::max({now, motor_ready, feed_end}) + us((line_us + 1) / 2) + 1;
    }
    void emit(unsigned b) { lines.push_back(b); total++; }
    void tick(uint64_t now) override {
        if (motor) running_ticks += now - last_tick;
        last_tick = now;
        if (running_ticks >= us(16200000000ULL)) { lubrication = true; motor = false; } // TM2:14430–14434: automatic shutdown
        if (alarm()) lamp = true;
        if (pending && motor && !inhibited() && now >= motor_ready && now >= punch_end) {
            emit(buffer); pending = false;
            feed_end = now + us(line_us / 2) + 1;
        }
        if (manual_feed) {
            start_motor(now);
            if (motor && !inhibited() && now >= motor_ready && now >= feed_start && now >= feed_end && !pending) {
                emit(0x80); feed_end = now + us(line_us) + 1;
            }
        }
        if (motor && now >= motor_stop && !manual_feed) motor = false;
    }
    bool events(std::ostream& o) override {
        if (lines.empty()) return false;
        o << '['; for (size_t i = 0; i < lines.size(); i++) o << (i ? "," : "") << lines[i];
        o << ']'; lines.clear(); return true;
    }
    bool status(std::ostream& o) override {
        o << "{\"mode\":" << mode << ",\"ready\":" << !pending << ",\"motor\":" << motor
          << ",\"feeding\":" << (last_tick < feed_end) << ",\"lines\":" << total
          << ",\"low\":" << low << ",\"supply\":" << supply << ",\"end\":" << end
          << ",\"lubrication\":" << lubrication << ",\"maintenance\":" << maintenance_switch
          << ",\"ack\":" << ack << ",\"lamp\":" << lamp << ",\"buzzer\":" << (lamp && !ack)
          << ",\"reeler_brake\":" << reeler_brake << ",\"motor_switch\":" << motor_switch
          << ",\"eia\":" << eia << ",\"line_us\":" << line_us << ",\"startup_us\":" << startup_us << '}';
        return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        unsigned v = 0;
        if (op == "us") { s >> line_us; return "{}"; }
        if (op == "profile") {
            std::string p; s >> p;
            if (p == "handbook") { line_us = 5556; startup_us = 1000000; feed_delay_us = 5000000; }
            else if (p == "technical") { line_us = 5556; startup_us = feed_delay_us = 1000000; }
            else if (p == "sketchpad") { line_us = 3334; startup_us = 1000000; feed_delay_us = 5000000; }
            else return "{\"error\":\"unknown punch timing profile\"}";
            return "{}";
        }
        if (op == "startup_us") { s >> startup_us; return "{}"; }
        if (op == "brake") { s >> v; reeler_brake = v; return "{}"; } // H63 punch control arm
        if (op == "motor") {
            if (!maintenance_switch) return "{\"error\":\"maintenance switch required\"}";
            s >> v; motor_switch = v;
            // [INFERENCE] The handbook identifies the maintenance motor switch
            // but omits wiring; opening it removes motor drive and preserves EIA.
            if (!motor_switch) motor = false;
            return "{}";
        }
        if (op == "feed") { s >> v; manual_feed = v; if (v) feed_start = last_tick + us(feed_delay_us); return "{}"; }
        if (op == "low" || op == "supply" || op == "end" || op == "maintenance") {
            s >> v;
            if (op == "low") low = v; else if (op == "supply") supply = v;
            else if (op == "end") end = v; else maintenance_switch = v;
            if (alarm()) lamp = true;
            return "{}";
        }
        if (op == "ack") { s >> v; ack = v; return "{}"; }
        if (op == "reset") { ack = false; if (!alarm()) lamp = false; return "{}"; }
        if (op == "lubricate") {
            if (!maintenance_switch) return "{\"error\":\"maintenance switch required\"}";
            running_ticks = 0; lubrication = false; return "{}";
        }
        return Device::command(op, s);
    }
};
