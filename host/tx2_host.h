// Host for the Verilated TX-2: board-level time base, console, and peripherals
// supplied outside the RTL. The shared implementation serves tx2_wasm.cpp for
// WebAssembly and tx2_cli.cpp for the stdin debugging CLI.
//
// Machine::command(text) processes requests and returns one JSON line.
#pragma once
#include "Vtx2_machine.h"
#include "Vtx2_machine___024root.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <deque>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
#include "device.h"
#include "devices/all.h"

static int coordinate(unsigned v) { return v < 512 ? int(v) : -int(1023 - v); }

struct Machine {
    std::unique_ptr<Vtx2_machine> d;
    // PETR .tape bytes: bit 7 feed, bit 6 seventh hole, bits 5-0 data.
    std::vector<uint8_t> tape;
    size_t position = 0;  // byte index of the next line to read
    unsigned rewinds = 0;
    uint64_t cycles = 0, retired = 0, points = 0, hits = 0;
    // Inputs at the last combinational settle in clock(); 0xff/~0 force the first settle.
    uint8_t settled_scope_ready = 0xff;
    uint64_t settled_present = ~0ULL, settled_maintenance = ~0ULL;
    // Board clocks per simulated microsecond: 2 interactive, 50 reference.
    unsigned ticks_per_us = 2;
    uint64_t next_micro = 0, next_clock = 0;
    // Operator line-period override in microseconds; 0 uses manual transport speed.
    unsigned reader_us = 0;
    uint64_t reader_next = 0;
    // H63 PETR p105 / TM2 15-PETR: free-running physical transport.
    int tape_direction = 0; // -1 binward, +1 reelward, 0 stopped
    unsigned tape_braking = 0;
    bool tape_strip = false, tape_manual = false, tape_disconnect = false, tape_maintenance = false;
    unsigned reel_lines_per_second = 2000;
    bool camera_manual = false;
    bool scope_on[2]{true,true}; // [INFERENCE] Both scopes start warmed up.
    uint64_t scope_warm_until[2]{};
    // [INFERENCE] A mounted .tape starts after its bin END MARK, outside the
    // file extent in the cropped upstream media format. EOF never denotes a mark.
    bool camera_armed = false, camera_low = false, camera_empty = false, camera_buzzer = false;
    bool camera_invert = false;
    uint64_t camera_until = 0;
    unsigned camera_us = 100000; // [INFERENCE] H63 unit 60 omits the return delay.
    unsigned timer_rate = 1000000, timer_toggles = 0;
    uint64_t timer_next = 0, timer_pulses = 0;
    bool timer_start = false, timer_stop = false, timer_load = false, timer_external = false;
    bool timer_maintenance = false, timer_trigger_enabled = false;
    bool set_metabits = false, sync_to_trap = false, sync1 = false, sync2 = false, gate1 = false, sync_pulse = false;
    // Light pen, in display units; glides linearly across a step's clocks.
    double penx = 0, peny = 0;
    int radius = 12;
    bool pen = false, beam_seen = false;
    // Console.
    uint64_t toggles[16]{}, fixed[8]{}, knob = 0, ext = 0;
    unsigned toggle_meta = 0, suppress = 0;
    bool knob_meta = false, ext_meta = false, hold = false;
    enum : unsigned { CODABO = 1, STARTOVER = 2, STOP = 4, CALACO = 8, PRESET = 16, RESET_START = 32, CLEAR_ALARMS = 64, CLEAR_CLOCK = 128 };
    unsigned pulses = 0, start_address = 0377750;
    // Host-side units on the RTL's generic external bus; see web/devices/.
    decltype(make_devices()) concrete_devices = make_devices();
    std::vector<Device*> devices;
    Device* by_unit[64]{};
    struct BusStatus {
        uint64_t input = 0, ready = 0, assembly = 0, reverse = 0;
        uint64_t missed = 0, inability = 0, clear = 0, maintenance = 0;
    };
    uint64_t external_present = 0;
    // Output collected since the last step reply.
    std::ostringstream display_events, writer_codes, control_events;
    bool any_display = false, any_writer = false, any_control = false, camera_event = false;
    bool tracing = false;
    std::ofstream trace;

    Machine() {
        std::apply([this](auto&... dev) { (attach(dev.get()), ...); }, concrete_devices);
        power();
    }
    template<class T> void attach(T* dev) {
        devices.push_back(dev);
        dev->ticks_per_us = &ticks_per_us;
        by_unit[dev->unit] = dev;
        const uint64_t bit = 1ULL << dev->unit;
        external_present |= bit;
    }
    template<class T> static void sample(T& unit, uint64_t now, BusStatus& status) {
        const uint64_t bit = 1ULL << unit.unit;
        if (unit.T::input()) status.input |= bit;
        if (unit.T::ready(now)) status.ready |= bit;
        if (unit.T::assembly()) status.assembly |= bit;
        if (unit.T::reverse()) status.reverse |= bit;
        if (unit.T::missed()) status.missed |= bit;
        if (unit.T::inability()) status.inability |= bit;
        if (unit.T::clear_alarms()) status.clear |= bit;
        if (unit.T::maintenance()) status.maintenance |= bit;
    }
    template<class T> static void tick_device(T& unit, uint64_t now) { unit.T::tick(now); }
    Device* device(const std::string& name) {
        for (auto* dev : devices) if (name == dev->name) return dev;
        return nullptr;
    }

    // Power on: zero core, meta 0, odd parity 1, controls preset, CPU stopped.
    void power() {
        d = std::make_unique<Vtx2_machine>();
        cycles = retired = points = hits = 0; position = 0; rewinds = 0;
        next_micro = next_clock = reader_next = timer_next = 0;
        tape_direction = 0; tape_braking = 0; tape_manual = tape_disconnect = false;
        timer_start = timer_stop = timer_load = timer_external = false; timer_pulses = 0;
        camera_armed = false; camera_until = 0;
        pen = beam_seen = false; pulses = 0;
        for (auto& dev : devices) dev->reset();
        d->reset = 1; d->display_ready = 1;
        auto r = d->rootp;
        for (unsigned i = 0; i < 65536; i++) {
            r->tx2_machine__DOT__memory__DOT__s_memory[i] = 0;
            r->tx2_machine__DOT__memory__DOT__s_meta[i] = 0;
            r->tx2_machine__DOT__memory__DOT__s_parity[i] = 1;
        }
        for (unsigned i = 0; i < 4096; i++) {
            r->tx2_machine__DOT__memory__DOT__t_memory[i] = r->tx2_machine__DOT__memory__DOT__u_memory[i] = 0;
            r->tx2_machine__DOT__memory__DOT__t_meta[i] = r->tx2_machine__DOT__memory__DOT__u_meta[i] = 0;
            r->tx2_machine__DOT__memory__DOT__t_parity[i] = r->tx2_machine__DOT__memory__DOT__u_parity[i] = 1;
        }
        apply_console();
        for (int i = 0; i < 5; i++) { d->clk = 0; d->eval(); d->clk = 1; d->eval(); }
        d->reset = 0;
    }

    uint64_t read(unsigned a) {
        auto r = d->rootp;
        if (a < 0200000) return r->tx2_machine__DOT__memory__DOT__s_memory[a];
        if (a < 0210000) return r->tx2_machine__DOT__memory__DOT__t_memory[a & 07777];
        if (a < 0220000) return r->tx2_machine__DOT__memory__DOT__u_memory[a & 07777];
        return 0;
    }
    bool read_meta(unsigned a) {
        auto r = d->rootp;
        if (a < 0200000) return r->tx2_machine__DOT__memory__DOT__s_meta[a];
        if (a < 0210000) return r->tx2_machine__DOT__memory__DOT__t_meta[a & 07777];
        if (a < 0220000) return r->tx2_machine__DOT__memory__DOT__u_meta[a & 07777];
        return false;
    }

    template <typename Wide> static void put36(Wide& w, unsigned index, uint64_t v) {
        for (unsigned b = 0; b < 36; b++) {
            const unsigned bit = index * 36 + b;
            const uint32_t m = 1u << (bit & 31);
            if ((v >> b) & 1) w[bit >> 5] |= m; else w[bit >> 5] &= ~m;
        }
    }
    void apply_console() {
        for (unsigned i = 0; i < 16; i++) put36(d->panel_data, i, toggles[i]);
        for (unsigned i = 0; i < 8; i++) put36(d->console_switches, i, fixed[i]);
        d->panel_meta = toggle_meta;
        d->knob_data = knob; d->knob_meta = knob_meta;
        d->external_register_data = ext; d->external_register_meta = ext_meta;
        d->alarm_suppress = suppress; d->console_hold = hold;
        d->trap_set_enable = set_metabits;
        d->sync_trap_mode = sync_to_trap && !sync1 && !sync2 && gate1;
    }

    uint64_t tape_period() const {
        // H63 PETR controls: strip/bin 400 lines/s, reel up to 2000 lines/s.
        // reader_us overrides operator timing; 0 selects the transport speed.
        if (reader_us) return uint64_t(reader_us) * ticks_per_us;
        return uint64_t(tape_direction < 0 || tape_strip ? 2500 : 1000000 / reel_lines_per_second) * ticks_per_us;
    }
    void reader_line() {
        d->tape_valid = 0; d->tape_data = 0;
        if (!tape_direction || cycles < reader_next) return;
        reader_next = cycles + tape_period();
        if (tape_direction < 0) {
            if (!position) { // mounted file's separate leading bin END MARK
                tape_direction = tape_manual ? 0 : 1;
                return;
            }
            const uint8_t line = tape[--position];
            if ((line & 0300) == 0200 && (line & 077) == 073) {
                tape_direction = tape_manual ? 0 : 1;
                position++; // END MARK lies on the bin side of the reading point
            }
        } else if (position < tape.size()) {
            const uint8_t line = tape[position++];
            // TM2 p403 prose says seventh hole, but its Hf·REV⁰ formula and
            // p406 Fig15-PETR-2 gate only feed+forward. Follow that circuit;
            // H7 qualifies END MARK, never ordinary binary-data admission.
            if (!tape_manual && (line & 0200)) { d->tape_valid = 1; d->tape_data = line & 077; }
        } else { tape_direction = 0; tape_braking = 0; } // exhausted media: no EIA/END MARK
        if (tape_braking && !--tape_braking) tape_direction = 0;
    }
    void reader_control(unsigned c) {
        if ((c & 070000) == 020000 || ((c & 070000) == 030000 && !(c & 0100))) {
            if (tape_direction) tape_braking = 100; // H63 p105, approximately one foot
        } else if ((c & 070000) == 030000) {
            tape_manual = false; tape_braking = 0;
            tape_direction = c & 4 ? -1 : 1;
            if (c & 4) rewinds++;
            reader_next = cycles + tape_period();
        }
    }

    // One clock of the board around the RTL.
    void clock(uint64_t timer_period) {
        auto r = d->rootp;
        // One eval per clock, at the rising edge. The RTL has no negedge logic, so the
        // old clk=0 eval only re-settled combinational logic; Verilator detects the
        // edge against the clock level it saw last, which is reset here instead.
        d->clk = 0; r->__Vtrigprevexpr___TOP__clk__0 = 0;
        d->start = pulses & CODABO; d->start_address = start_address;
        d->console_startover = (pulses & STARTOVER) != 0; d->console_stop = (pulses & STOP) != 0;
        d->console_continue = (pulses & CALACO) != 0; d->console_preset = (pulses & PRESET) != 0;
        d->console_reset_start = (pulses & RESET_START) != 0; d->clear_alarms = (pulses & CLEAR_ALARMS) != 0;
        d->clock_clear = (pulses & CLEAR_CLOCK) != 0;
        pulses = 0;
        d->tick_1us = cycles >= next_micro;
        d->timer_fast = timer_rate == 1000000;
        d->timer_tick = timer_period ? cycles >= timer_next : timer_external;
        if (d->timer_tick && timer_period) timer_next = cycles + timer_period;
        d->timer_manual_start = timer_start; d->timer_manual_stop = timer_stop;
        d->timer_manual_load = timer_load; d->timer_manual_interval = timer_toggles;
        timer_start = timer_stop = timer_load = timer_external = false;
        d->sync_trap = sync_pulse && d->sync_trap_mode; sync_pulse = false;
        d->tape_manual_disconnect = tape_disconnect; tape_disconnect = false;
        d->tick_10us = cycles >= next_clock;
        if (d->tick_1us) next_micro += ticks_per_us;
        if (d->tick_10us) next_clock += ticks_per_us * 10;
        reader_line();
        // H63 4920-4935: keep the RTL buffer busy until physical completion.
        auto* writer = static_cast<WriterOutput*>(by_unit[066]);
        d->writer_ready = writer->builtin_ready(d->writer_valid, d->writer_data, cycles);
        // Sample before IOS/TSD and tick(): ready() and clear_alarms() can mutate a unit.
        BusStatus status;
        std::apply([&](auto&... dev) { (sample(*dev, cycles, status), ...); }, concrete_devices);
        d->external_present = external_present; d->external_input = status.input; d->external_ready = status.ready;
        d->external_assembly = status.assembly; d->external_reverse = status.reverse; d->external_missed = status.missed;
        d->external_inability = status.inability; d->external_clear_alarms = status.clear;
        d->external_maintenance = status.maintenance | (tape_maintenance ? 1ULL << 052 : 0) | (timer_maintenance ? 1ULL << 054 : 0);
        Device* reporter = by_unit[d->external_control_unit & 077];
        d->external_special = reporter ? reporter->special() & 077777 : 0;
        Device* io = by_unit[d->external_unit & 077];
        d->external_data = io ? io->data(cycles) & W36 : 0;
        d->external_mask = io ? io->mask() & W36 : W36;
        d->external_assembly_width = io ? io->assembly_width() : 6;
        // Light pen: one detector pulse per illuminated spot within the pen's field.
        const bool lit = d->pen_lit;
        d->light_pen_hit = 0;
        if (pen && lit && !beam_seen) {
            const double dx = coordinate(d->pen_x) - penx;
            const double dy = (camera_invert ? -coordinate(d->pen_y) : coordinate(d->pen_y)) - peny;
            d->light_pen_hit = dx * dx + dy * dy <= double(radius) * radius;
        }
        if (d->light_pen_hit) beam_seen = true;
        d->camera_done = camera_armed && !camera_empty && cycles >= camera_until;
        d->camera_manual_index = camera_manual; camera_manual = false;
        d->scope_ready = (scope_on[0] && cycles >= scope_warm_until[0] ? 1 : 0)
                       | (scope_on[1] && cycles >= scope_warm_until[1] ? 2 : 0);
        d->display_ready = 1;
        d->camera_alarm = camera_low && d->camera_request;
        // Outputs read below come from registers, except through control_error
        // and display_valid/select in tx2_io.v; settle when these inputs change.
        if (d->scope_ready != settled_scope_ready || d->external_present != settled_present
            || d->external_maintenance != settled_maintenance) {
            d->eval();
            settled_scope_ready = d->scope_ready; settled_present = d->external_present;
            settled_maintenance = d->external_maintenance;
        }
        if (!d->running && !tape_manual && tape_direction && !tape_braking) tape_braking = 100;
        if (d->display_valid && d->display_ready) {
            if (d->display_unit == 060) beam_seen = false;
            const int y = coordinate(d->display_y) * (camera_invert && d->display_unit == 060 ? -1 : 1);
            display_events << (any_display ? "," : "") << '[' << coordinate(d->display_x) << ',' << y << ','
                           << unsigned(d->display_intensity) << ',' << unsigned(d->display_unit) << ']';
            any_display = true; points++;
        }
        if (lit && (r->tx2_machine__DOT__devices__DOT__connected & (1ULL << 055)) && d->light_pen_hit) hits++;
        if (d->writer_valid && d->writer_ready) {
            if (writer->mechanism->cpu_writer) {
                writer_codes << (any_writer ? "," : "") << unsigned(d->writer_data); any_writer = true;
            }
            writer->builtin_ack();
        }
        if (!d->camera_request) camera_armed = false;
        else if (!camera_armed) {
            camera_armed = true; camera_event = true;
            camera_until = cycles + uint64_t(camera_us) * ticks_per_us;
            if (camera_low) camera_buzzer = true;
        }
        if (r->tx2_machine__DOT__io_control_valid && !r->tx2_machine__DOT__io_control_error) {
            const unsigned u = d->external_control_unit, c = d->external_control_command;
            if (by_unit[u]) by_unit[u]->control(c, cycles);
            if (u == 052) reader_control(c);
            control_events << (any_control ? "," : "") << '[' << u << ',' << c << ']'; any_control = true;
        }
        if (d->external_valid && by_unit[d->external_unit & 077]) by_unit[d->external_unit & 077]->transfer(d->external_write_data & W36, cycles);
        std::apply([&](auto&... dev) { (tick_device(*dev, cycles), ...); }, concrete_devices);
        if (d->timer_end_carry) {
            timer_pulses++;
            for (auto& dev : devices) dev->timer_pulse(cycles);
        }
        if (d->retire) {
            retired++;
            if (tracing) trace << cycles << " K=" << std::oct << unsigned(d->retire_sequence) << " PC=" << d->retire_address
                               << " N=" << d->retire_instruction << " A=" << d->a << " E=" << d->e << std::dec << '\n';
        }
        d->clk = 1; d->eval(); cycles++;
    }

    // Run board clocks even with the CPU stopped: manual transports, camera,
    // timer and mechanical completions keep operating; see H63 device controls.
    void run(uint64_t n, int x, int y, bool active, uint64_t retire_limit) {
        const double fromx = penx, fromy = peny;
        const bool glide = active && pen && (fromx != x || fromy != y);
        pen = active;
        const uint64_t until = retired + retire_limit;
        const uint64_t timer_period = timer_rate ? uint64_t(ticks_per_us) * (1000000 / timer_rate) : 0;
        if (!glide && n) { penx = x; peny = y; }
        for (uint64_t i = 0; i < n; i++) {
            if (glide) {
                const double f = double(i + 1) / n;
                penx = fromx + (x - fromx) * f; peny = fromy + (y - fromy) * f;
            }
            clock(timer_period);
            if (retire_limit && retired >= until) break;
            if (!d->running && !pulses && i > 2) {
                const auto r = d->rootp;
                bool busy = tape_direction || d->camera_request || r->tx2_machine__DOT__devices__DOT__timer_running
                         || r->tx2_machine__DOT__devices__DOT__scope_full
                         || (scope_on[0] && cycles < scope_warm_until[0]) || (scope_on[1] && cycles < scope_warm_until[1]);
                for (auto& dev : devices) busy = busy || dev->active();
                if (!busy) break;
            }
        }
        penx = x; peny = y;
    }

    static std::string octal(uint64_t v) { std::ostringstream o; o << std::oct << v; return o.str(); }

    std::string state() {
        auto r = d->rootp;
        std::ostringstream o;
        o << "{\"cycles\":" << cycles << ",\"retired\":" << retired << ",\"running\":" << int(d->running)
          << ",\"fault\":" << unsigned(d->fault) << ",\"alarms\":" << d->alarms << ",\"limbo\":" << int(d->limbo)
          << ",\"k\":" << unsigned(d->current_sequence) << ",\"pc\":" << d->program_counter << ",\"q\":" << d->operand_address
          << ",\"n\":\"" << octal(r->tx2_machine__DOT__core__DOT__instruction) << "\""
          << ",\"a\":\"" << octal(d->a) << "\",\"b\":\"" << octal(d->b) << "\",\"c\":\"" << octal(d->c)
          << "\",\"d\":\"" << octal(d->d) << "\",\"e\":\"" << octal(d->e) << "\""
          << ",\"flags\":\"" << octal(d->sequence_flags) << "\",\"connected\":\"" << octal(r->tx2_machine__DOT__devices__DOT__connected) << "\""
          << ",\"overflow\":" << unsigned(d->overflow_flags)
          << ",\"tape\":{\"pos\":" << position << ",\"size\":" << tape.size() << ",\"rewinds\":" << rewinds
          << ",\"direction\":" << tape_direction << ",\"braking\":" << tape_braking << ",\"strip\":" << tape_strip
          << ",\"lineUs\":" << tape_period() / ticks_per_us << ",\"maintenance\":" << tape_maintenance << "}"
          << ",\"hits\":" << hits << ",\"points\":" << points << ",\"ticksPerUs\":" << ticks_per_us
          << ",\"camera\":" << int(camera_event)
          << ",\"cameraStatus\":{\"busy\":" << unsigned(d->camera_request) << ",\"low\":" << camera_low
          << ",\"empty\":" << camera_empty << ",\"buzzer\":" << camera_buzzer << ",\"inverted\":" << camera_invert
          << ",\"eia\":" << bool(r->tx2_machine__DOT__devices__DOT__inability_latch & (1ULL << 060)) << "}"
          << ",\"timer\":{\"rate\":" << timer_rate << ",\"interval\":" << r->tx2_machine__DOT__devices__DOT__timer_buffer
          << ",\"count\":" << r->tx2_machine__DOT__devices__DOT__timer_count << ",\"running\":" << unsigned(r->tx2_machine__DOT__devices__DOT__timer_running)
          << ",\"pulses\":" << timer_pulses << "}"
          << ",\"scopes\":[{\"unit\":46,\"busy\":" << bool(r->tx2_machine__DOT__devices__DOT__scope_full & 1)
          << ",\"power\":" << scope_on[0] << ",\"ready\":" << bool(d->scope_ready & 1)
          << "},{\"unit\":48,\"busy\":" << bool(r->tx2_machine__DOT__devices__DOT__scope_full & 2)
          << ",\"power\":" << scope_on[1] << ",\"ready\":" << bool(d->scope_ready & 2) << "}]"
          << ",\"display\":[" << display_events.str() << "],\"writer\":[" << writer_codes.str()
          << "],\"control\":[" << control_events.str() << "]";
        // Per-device output since the last report in "dev" and standing status in "units".
        for (const char* key : {"dev", "units"}) {
            o << ",\"" << key << "\":{"; bool first = true;
            for (auto& dev : devices) {
                std::ostringstream v;
                if (key[0] == 'd' ? dev->events(v) : dev->status(v)) { o << (first ? "" : ",") << '"' << dev->name << "\":" << v.str(); first = false; }
            }
            o << '}';
        }
        o << '}';
        for (auto* s : {&display_events, &writer_codes, &control_events}) s->str("");
        any_display = any_writer = any_control = camera_event = false;
        return o.str();
    }

    static int hexval(char c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }

    // Text protocol uses decimal numbers unless stated. Each command returns one JSON object.
    //   run N X Y PEN [RETIRES]   run up to N clocks or RETIRES instructions, pen at X,Y
    //   state                      report without running
    //   power                      power-on reset; clear core and stop the CPU
    //   press codabo|startover|stop|calaco|preset|resetstart|clearalarms|clearclock
    //   set tsp|knob|kmeta|ext|emeta|suppress|hold|timing|radius|reader_us V
    //   set toggle I V | set tmeta I B | set fixed I V
    //   tape HEX | tape eject | tape rewind   mount .tape bytes
    //   dev NAME OP ...            device command, e.g. "dev lw65 keys 23 20", "dev punch us 5556"
    //   peek ADDR N                read N words of S/T/U core
    //   meta ADDR N                read N meta bits of S/T/U core
    //   fx                         F memory: 32 configurations; X memory: 64 index registers
    //   poke ADDR VALUE            debugging write to one word of S/T/U core
    //   trace on|off               CLI instruction trace to results/browser-debug.trace
    std::string command(const std::string& line) {
        std::istringstream s(line);
        std::string op; s >> op;
        if (op == "run") {
            uint64_t n = 0, lim = 0; int x = 0, y = 0, p = 0; s >> n >> x >> y >> p >> lim;
            run(std::min<uint64_t>(n, 20000000), std::clamp(x, -511, 511), std::clamp(y, -511, 511), p, lim);
            return state();
        }
        if (op == "state") return state();
        if (op == "power") { power(); return state(); }
        if (op == "press") {
            std::string b; s >> b;
            if (b == "sync") { sync_pulse = true; return "{}"; }
            const unsigned bit = b == "codabo" ? CODABO : b == "startover" ? STARTOVER : b == "stop" ? STOP : b == "calaco" ? CALACO
                               : b == "preset" ? PRESET : b == "resetstart" ? RESET_START : b == "clearalarms" ? CLEAR_ALARMS
                               : b == "clearclock" ? CLEAR_CLOCK : 0;
            if (!bit) return "{\"error\":\"unknown button\"}";
            unsigned addr; if (s >> addr) start_address = addr & 0377777;
            pulses |= bit; return "{}";
        }
        if (op == "set") {
            std::string k; uint64_t a = 0, b = 0; s >> k >> a; s >> b;
            if (k == "tsp") start_address = a & 0377777;
            else if (k == "toggle" && a < 16) toggles[a] = b & W36;
            else if (k == "tmeta" && a < 16) toggle_meta = (toggle_meta & ~(1u << a)) | (unsigned(b & 1) << a);
            else if (k == "fixed" && a < 8) fixed[a] = b & W36;
            else if (k == "knob") knob = a & W36;
            else if (k == "kmeta") knob_meta = a & 1;
            else if (k == "ext") ext = a & W36;
            else if (k == "emeta") ext_meta = a & 1;
            else if (k == "suppress") suppress = a & 01777;
            else if (k == "hold") hold = a & 1;
            else if (k == "setmetabits") set_metabits = a & 1;
            else if (k == "synctotrap") sync_to_trap = a & 1;
            else if (k == "sync1") sync1 = a & 1;
            else if (k == "sync2") sync2 = a & 1;
            else if (k == "gate1") gate1 = a & 1;
            else if (k == "timing") { ticks_per_us = std::clamp<unsigned>(a, 1, 50); next_micro = next_clock = timer_next = cycles; }
            else if (k == "radius") radius = std::clamp<int>(a, 1, 64);
            else if (k == "reader_us") reader_us = a;
            else return "{\"error\":\"unknown setting\"}";
            apply_console(); return "{}";
        }
        if (op == "tape") {
            std::string h; s >> h;
            if (h == "eject") { tape.clear(); position = 0; }
            else if (h == "rewind") position = 0;
            else {
                if (h.size() % 2) return "{\"error\":\"odd hex length\"}";
                tape.resize(h.size() / 2);
                for (size_t i = 0; i < tape.size(); i++) tape[i] = uint8_t(hexval(h[2 * i]) << 4 | hexval(h[2 * i + 1]));
                position = 0; rewinds = 0;
            }
            tape_direction = 0; tape_braking = 0; tape_manual = false;
            return "{\"size\":" + std::to_string(tape.size()) + "}";
        }
        if (op == "dev") {
            std::string name, dop; s >> name >> dop;
            unsigned v = 0;
            if (name == "petr") {
                if (dop == "strip") { s >> v; tape_strip = v != 0; }
                else if (dop == "speed") { s >> v; reel_lines_per_second = std::clamp(v, 400u, 2500u); reader_us = 0; }
                else if (dop == "position") { s >> v; position = std::min<size_t>(v, tape.size()); }
                else if (dop == "maintenance") { s >> v; tape_maintenance = v != 0; }
                else if (dop == "wind" || dop == "bin") {
                    tape_manual = true; tape_disconnect = true; tape_braking = 0;
                    tape_direction = dop == "bin" ? -1 : 1; reader_next = cycles + tape_period();
                } else if (dop == "stop") { if (tape_direction) tape_braking = 100; }
                else return "{\"error\":\"unknown paper-tape reader control\"}";
                return "{}";
            }
            if (name == "timer") {
                if (dop == "rate") {
                    s >> v; if (v != 0 && v != 10000 && v != 100000 && v != 1000000) return "{\"error\":\"unsupported oscillator frequency\"}";
                    timer_rate = v; timer_next = cycles;
                } else if (dop == "toggles") { s >> v; timer_toggles = v & 0777777; }
                else if (dop == "start") { timer_load = timer_start = true; }
                else if (dop == "stop") timer_stop = true;
                else if (dop == "maintenance") { s >> v; timer_maintenance = v != 0; }
                else if (dop == "external") { s >> v; timer_trigger_enabled = v != 0; }
                else if (dop == "trigger") { if (timer_trigger_enabled) timer_start = true; }
                else if (dop == "pulse") timer_external = true;
                else return "{\"error\":\"unknown timer control\"}";
                return "{}";
            }
            if (name == "camera") {
                if (dop == "low") { s >> v; camera_low = v != 0; }
                else if (dop == "empty") { s >> v; camera_empty = v != 0; if (camera_empty) camera_low = true; }
                else if (dop == "ack") camera_buzzer = false;
                else if (dop == "invert") { s >> v; camera_invert = v != 0; }
                else if (dop == "us") { s >> v; camera_us = v; }
                else if (dop == "index") camera_manual = true;
                else return "{\"error\":\"unknown camera control\"}";
                return "{}";
            }
            if (name == "scope56" || name == "scope60") {
                const unsigned i = name == "scope60";
                if (dop == "on") { scope_on[i] = true; scope_warm_until[i] = cycles + uint64_t(65000000) * ticks_per_us; }
                else if (dop == "off") scope_on[i] = false;
                else return "{\"error\":\"unknown scope control\"}";
                return "{}";
            }
            Device* dev = device(name);
            return dev ? dev->command(dop, s) : "{\"error\":\"unknown device\"}";
        }
        if (op == "peek") {
            unsigned a = 0, n = 0; s >> a >> n; std::ostringstream o; o << '[';
            for (unsigned i = 0; i < std::min(n, 65536u); i++) o << (i ? "," : "") << read(a + i);
            o << ']'; return o.str();
        }
        if (op == "meta") {
            unsigned a = 0, n = 0; s >> a >> n; std::ostringstream o; o << '[';
            for (unsigned i = 0; i < std::min(n, 65536u); i++) o << (i ? "," : "") << int(read_meta(a + i));
            o << ']'; return o.str();
        }
        if (op == "fx") {  // F memory: 32 configurations; X memory: 64 index registers
            auto r = d->rootp; std::ostringstream o; o << "{\"f\":[";
            for (unsigned i = 0; i < 32; i++) o << (i ? "," : "") << unsigned(r->tx2_machine__DOT__core__DOT__f_memory[i]);
            o << "],\"x\":[";
            for (unsigned i = 0; i < 64; i++) o << (i ? "," : "") << unsigned(r->tx2_machine__DOT__core__DOT__x_memory[i]);
            o << "]}"; return o.str();
        }
        if (op == "poke") {
            unsigned a; uint64_t v; s >> a >> v; auto r = d->rootp; v &= W36;
            const bool parity = !(__builtin_parityll(v) ^ read_meta(a));
            if (a < 0200000) { r->tx2_machine__DOT__memory__DOT__s_memory[a] = v; r->tx2_machine__DOT__memory__DOT__s_parity[a] = parity; }
            else if (a < 0210000) { r->tx2_machine__DOT__memory__DOT__t_memory[a & 07777] = v; r->tx2_machine__DOT__memory__DOT__t_parity[a & 07777] = parity; }
            else if (a < 0220000) { r->tx2_machine__DOT__memory__DOT__u_memory[a & 07777] = v; r->tx2_machine__DOT__memory__DOT__u_parity[a & 07777] = parity; }
            else return "{\"error\":\"address\"}";
            return "{}";
        }
        if (op == "trace") {
            std::string v; s >> v; tracing = v == "on";
            if (tracing && !trace.is_open()) trace.open("results/browser-debug.trace");
            if (!tracing) trace.flush();
            return "{}";
        }
        return "{\"error\":\"unknown command\"}";
    }
};
