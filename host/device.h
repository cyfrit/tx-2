// Peripheral interface for host-side TX-2 units on the RTL's generic external bus.
//
// The RTL in rtl/tx2_io.v maintains each unit's IOS connection, 12-bit mode word,
// flags and MISIND/EIA latches. A Device supplies physical behavior: buffer
// availability, input words, output handling, and the effects of each IOS that
// reaches it. Times are board clocks;
// Device::us() converts simulated microseconds.
#pragma once
#include <cstdint>
#include <ostream>
#include <sstream>
#include <string>

static constexpr uint64_t W36 = (1ULL << 36) - 1;

struct Device {
    const unsigned unit;      // octal unit number; Users Handbook table 7-1
    const char* const name;   // key in the state JSON "dev" object and the "dev NAME ..." command
    const unsigned* ticks_per_us = nullptr;  // set by Machine::attach
    Device(unsigned u, const char* n) : unit(u), name(n) {}
    virtual ~Device() = default;
    uint64_t us(uint64_t micro) const { return micro * *ticks_per_us; }

    virtual void reset() {}                                   // power on
    virtual bool input() const { return false; }              // TSD reads from this unit
    virtual bool ready(uint64_t /*now*/) { return true; }     // buffer available for the next TSD
    virtual uint64_t data(uint64_t /*now*/) { return 0; }     // right-justified input word offered
    virtual uint64_t mask() const { return W36; }             // buffer bits an input TSD changes
    virtual bool assembly() const { return false; }           // TSD uses assembly mode
    virtual unsigned assembly_width() const { return 6; }     // splayed chunk: PETR/punch 6, TX-2 tape 9
    virtual bool reverse() const { return false; }
    virtual bool missed() const { return false; }             // MISIND condition latched by the RTL
    virtual bool inability() const { return false; }          // EIA condition latched by the RTL
    virtual bool maintenance() const { return false; }        // IOS report 2.7 / IOSAL interlock
    virtual unsigned special() const { return 0; }            // report 3.7-4.9: low 12 bits; 3.7 = bit 0
    virtual bool clear_alarms() { return false; }             // true once to clear the RTL latches
    virtual void control(unsigned /*command*/, uint64_t /*now*/) {}  // an IOS reached this unit
    virtual void transfer(uint64_t /*word*/, uint64_t /*now*/) {}    // TSD done: output word / input taken
    virtual void timer_pulse(uint64_t /*now*/) {}              // interval-timer EC output jack
    virtual void tick(uint64_t /*now*/) {}                    // every board clock
    virtual bool active() const { return false; }             // mechanical action continues with CPU stopped
    // New output since the last state report, as one JSON value; false if nothing new.
    virtual bool events(std::ostream& /*o*/) { return false; }
    // Status shown in every state report as a JSON value, or false.
    virtual bool status(std::ostream& /*o*/) { return false; }
    // "dev NAME ..." operator/host commands: mount media, press controls, set timing.
    virtual std::string command(const std::string& /*op*/, std::istringstream& /*args*/) {
        return "{\"error\":\"unknown device command\"}";
    }
};
