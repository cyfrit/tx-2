# TX-2 Verilog implementation plan

The target is the TX-2 configuration from approximately 1963. The Users Handbook defines visible behavior, and the three-volume Technical Manual provides the exchange, arithmetic, control, I/O, and instruction-pulse details. The source collection contains 60 PDFs. Differences between years and later revisions are tracked separately.

## Implementation status, 2026-11-10

| Layer | Status |
| --- | --- |
| Field and configuration decoding | Complete: 36-bit instructions, 9-bit F configurations, and all 512 configuration values |
| Exchange Element | Implemented: eight bidirectional permutations, activity and expanded activity, four subword forms, and wraparound sign extension |
| Instruction execution | All 50 named opcodes have execution paths and commit in whole-machine tests |
| Arithmetic Element | 14 operations, ones-complement arithmetic, Z, serial PAD/MS and PAD/CRY; direct AOP integrated |
| Program Element | 33 sequences, flags, patchable priority, hold/dismiss, limbo, and placekeepers |
| Memory | S/T/U, meta and parity, A–E, V inputs, clock, startup switches, and the original plugboard |
| Traps, digital alarms, and console | Integrated and tested; analog timing alarms remain to be reconstructed |
| Main I/O | PETR, Writer, timer, display, light pen, and camera; other devices use the common interface |
| Cold boot | HELLO, display/light-pen diagnostics, and the reconstructed Sketchpad listing boot through the original plugboard and paper tape |
| Verification and synthesis | `make check` runs the [regressions and synthesis checks](RTL-STATUS.md#reproducible-checks) |

The complete machine entry point is `rtl/tx2_machine.v`. `rtl/tx2_system.v` retains the early regression configuration. Code paths and commands in this document are relative to the repository root.

## Remaining acceptance work

1. **Historical edge cases.** Check arithmetic coupling under partial AOP activity, ASK termination for zero-valued NORMALIZE, SKX revision differences, and historical software dependencies on alarm suppression and recovery. Add hand-calculated source examples and historical binary comparisons.
2. **Dedicated peripherals.** Implement tape, Xerox, punch, and other controllers on the common interface. Extend PETR with seventh-hole handling, end-mark detection, and free-running transport. Connect display, camera, and light-pen devices to physical transport layers.
3. **Original-machine timing.** Extend the serial functional model with PK/QK/AK overlap, original counter states, α/β phases, and memory timing constraints. Verify electrical faults and digital functional faults independently.
4. **Historical Sketchpad software.** All seven reconstructed listing modules assemble, boot from paper tape, and continuously draw INK. Continue checking inferred repairs against original machine words, and validate drawing, editing, light-pen positioning, and constraint-solving interactions. Preserve the current cold-boot image as a software regression baseline.
5. **FPGA.** Select a device and clocks. S/T/U require approximately 2.80 Mbit including parity and meta. Plan BRAM or external RAM, the host connection, and physical I/O; then perform device synthesis, place and route, and comparisons with board-run logs.

## Reproducible baseline

`make clean && make check` rebuilds vectors from an empty build directory, runs ten testbenches, lints ten modules, performs structural synthesis, and synthesizes the complete core to generic gates. `make boot` and `make graphics` provide two acceptance paths beginning at the plugboard.

The reference model uses quarter lists, integer subword arithmetic, and individual micro-operation invariants. Opcode entry coverage and historical semantic coverage are evaluated separately. Known evidence limits are recorded in [RTL-STATUS.md](RTL-STATUS.md).
