// WebAssembly export: shared Machine and CLI text protocol from tx2_host.h.
#include "tx2_host.h"
#include <emscripten/emscripten.h>

static std::unique_ptr<Machine> machine;
static std::string reply;

extern "C" EMSCRIPTEN_KEEPALIVE const char* tx2_command(const char* line) {
    if (!machine) machine = std::make_unique<Machine>();
    reply = machine->command(line);
    return reply.c_str();
}
