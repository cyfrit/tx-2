// Debugging CLI: the same Machine as the WebAssembly build, driven from stdin.
// Each line calls Machine::command in tx2_host.h and prints one JSON response line.
// CLI command: load PATH mounts a .tape file from disk.
//   echo -e 'load programs/hello.tape\npress codabo 130024\nrun 2000000 0 0 0' | build/obj_cli/tx2-cli
#include "tx2_host.h"
#include <iostream>
#include <iterator>

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Machine m;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.rfind("load ", 0) == 0) {
            std::ifstream f(line.substr(5), std::ios::binary);
            if (!f) { std::cout << "{\"error\":\"cannot open tape\"}" << std::endl; continue; }
            std::string bytes((std::istreambuf_iterator<char>(f)), {}), hex;
            static const char* digits = "0123456789abcdef";
            for (unsigned char c : bytes) { hex += digits[c >> 4]; hex += digits[c & 15]; }
            std::cout << m.command("tape " + hex) << std::endl;
        } else {
            std::cout << m.command(line) << std::endl;
        }
    }
}
