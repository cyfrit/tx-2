#pragma once
#include "../device.h"

// H63 pp.115-116, OCR 4618-4647: nine-bit buffer; IOS/TSD starts a
// generation; 28.8 us minimum, 57.6 us mean; manual power, 60 s warm-up.
struct Random : Device {
    uint32_t state = 0x1963abcd;
    unsigned value = 0;
    bool powered = true, generating = false, full = false;
    uint64_t warm_until = 0, done_at = 0;
    Random() : Device(061, "rng") {}
    void reset() override {
        state = 0x1963abcd; value = 0; generating = full = false;
        // [INFERENCE] Board power starts with the operator's source already warmed up.
        powered = true; warm_until = done_at = now_ = 0;
    }
    bool input() const override { return true; }
    bool active() const override { return generating || (powered && now_ < warm_until); }
    uint64_t mask() const override { return 0777; }
    bool ready(uint64_t) override { return powered && full; }
    uint64_t data(uint64_t) override { return value; }
    void start(uint64_t now) {
        full = false;
        generating = powered;
        // [INFERENCE] Reproducible timing surrogate: use the constant handbook
        // mean; the radioactive-source latency distribution is undocumented.
        done_at = (now < warm_until ? warm_until : now) + (uint64_t(288) * *ticks_per_us + 4) / 5;
    }
    void control(unsigned c, uint64_t now) override {
        if ((c & 070000) == 030000) start(now);
    }
    void transfer(uint64_t, uint64_t now) override { start(now); }
    void tick(uint64_t now) override {
        now_ = now;
        if (!generating || now < done_at) return;
        // [INFERENCE] Seedable xorshift surrogate for the physical cesium detector.
        state ^= state << 13; state ^= state >> 17; state ^= state << 5;
        value = state & 0777; full = true; generating = false;
    }
    bool status(std::ostream& o) override {
        o << "{\"power\":" << powered << ",\"ready\":" << full
          << ",\"value\":" << value << ",\"warmUntil\":" << warm_until << '}'; return true;
    }
    std::string command(const std::string& op, std::istringstream& s) override {
        if (op == "power") {
            unsigned on = 0; s >> on; powered = on != 0; full = generating = false;
            warm_until = powered ? now_ + us(60000000) : 0; return "{}";
        }
        if (op == "seed") { s >> state; if (!state) state = 1; return "{}"; }
        return Device::command(op, s);
    }
    uint64_t now_ = 0;
};
