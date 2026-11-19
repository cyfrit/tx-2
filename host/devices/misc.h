#pragma once
#include "../device.h"

// H61 3550-3571 / H63 p.97: nine manually enabled pulse latches;
// connect only permits flag raising, TSD reads and clears all nine bits.
struct MiscIn : Device {
    // [INFERENCE] Initial manual input enables are all ON; no startup setting is specified.
    unsigned enabled = 0777, latch = 0;
    MiscIn() : Device(047, "misc47") {}
    void reset() override { latch = 0; enabled = 0777; }
    bool input() const override { return true; }
    bool ready(uint64_t) override { return latch != 0; }
    uint64_t data(uint64_t) override { return latch; }
    uint64_t mask() const override { return 0777; }
    void transfer(uint64_t, uint64_t) override { latch = 0; }
    bool status(std::ostream& o) override {
        o << "{\"enabled\":" << enabled << ",\"latch\":" << latch << '}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        unsigned v = 0;
        if (op == "enable") { s >> v; enabled = v & 0777; return "{}"; }
        // [INFERENCE] Pulses coalesce in the documented set-bit/clear-buffer circuit.
        if (op == "pulse") { s >> v; latch |= v & enabled & 0777; return "{}"; }
        return Device::command(op, s);
    }
};

// H63 4957-5042: IOS low nine bits drive a register, MOM-9 follows
// immediately, relay contacts settle within 2 ms; unit 75 has no flag.
struct MiscOut : Device {
    // [INFERENCE] Start with zeroed registers and the manual selector in NO SHIFT.
    unsigned value = 0, contacts = 0, reset_register = 0, shift_mode = 3;
    uint64_t settle_at = 0, now_ = 0;
    MiscOut() : Device(075, "misc75") {}
    void reset() override { value = contacts = reset_register = 0; shift_mode = 3; settle_at = now_ = 0; }
    bool ready(uint64_t) override { return false; }
    bool active() const override { return now_ < settle_at; }
    void load(unsigned v, uint64_t now) { value = v & 0777; settle_at = now + us(2000); }
    void control(unsigned c, uint64_t now) override {
        if ((c & 070000) == 030000) load(c, now);
    }
    void tick(uint64_t now) override { now_ = now; if (now >= settle_at) contacts = value; }
    bool status(std::ostream& o) override {
        o << "{\"register\":" << value << ",\"relays\":" << contacts << ",\"mom9\":" << ((value >> 8) & 1)
          << ",\"shift\":" << shift_mode << ",\"reset\":" << reset_register << '}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        unsigned v = 0;
        if (op == "shiftmode") { if (!(s >> v) || v < 1 || v > 3) return "{\"error\":\"shift mode 1..3\"}"; shift_mode = v; return "{}"; }
        if (op == "resetreg") { s >> v; reset_register = v & 0777; return "{}"; }
        if (op == "test") { load(reset_register, now_); return "{}"; }
        if (op == "shift") {
            if (shift_mode != 3) load((value << 1) | (shift_mode == 1 ? value >> 8 : 0), now_);
            return "{}";
        }
        return Device::command(op, s);
    }
};
