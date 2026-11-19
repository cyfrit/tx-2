# Public TX-2 reconstruction status

Research date: 2026-11-10, Beijing time. Commands and code paths are relative to the repository root.

## Findings

An actively maintained software reconstruction provides useful source material and tools. Work continues on the full instruction set, interactive graphics peripherals, and restoration of the original Sketchpad program. The public search found no mature whole-machine TX-2 Verilog or FPGA reconstruction. Search coverage is limited to the public sources examined.

## Project activity and results

The main project is the [TX-2 Project](https://tx-2.github.io/), with its core implementation in [TX-2-simulator](https://github.com/TX-2/TX-2-simulator). It includes a Rust simulator, an M4-style cross-assembler, a disassembler and other tools, and a Rust/WASM and TypeScript/React web interface.

The inspected simulator HEAD was `7480ac70bfece86c58b28a9f085ab4fe63880aae`, committed at 2026-11-09 10:35:28 UTC. Recent changes covered XOR, zero-argument macros, Sketchpad transcription synchronization, and lint fixes.

Comparison of execution dispatch in `cpu/src/control.rs` with the opcode enumeration in `base/src/instruction.rs` at that revision gave these results:

| Item | Result |
| --- | --- |
| Named opcodes | 50 |
| Dispatched to execution functions | 22 |
| Explicitly return an unimplemented alarm | 28 |
| Peripheral implementation source | Photoelectric paper-tape reader and Lincoln Writer |
| CRT and light pen | Open tasks #3 and #5, respectively |
| Original Sketchpad | Electronic transcription available; full assembly failed in this reproduction |

The 22 dispatched opcodes are AUX, LDA/LDB/LDC/LDD/LDE, STA/STB/STC/STD/STE, RSX, SKX, DPX, JMP, JPX, JNX, SKM, SPG, OPR, TSD, and SED. Dispatch coverage does not establish complete configuration, addressing, or edge-case semantics. The 44% figure measures opcode entry points.

Missing operations include ADD, SUB, MUL, DIV, SPF, and ADX. See the pinned [execution dispatch source](https://github.com/TX-2/TX-2-simulator/blob/7480ac70bfece86c58b28a9f085ab4fe63880aae/cpu/src/control.rs#L1230).

## Reproduction results

`cargo test --locked -p base -p cpu -p assembler` completed with all tests passing. This verifies the upstream test cases; compatibility with historical programs requires additional checks.

The upstream HELLO tape was then run with default settings:

```sh
cargo run --locked --bin cli -- --speed-multiplier MAX examples/hello.tape
```

After reading the tape and switching sequences, the program stopped at octal address `100`:

```text
in sequence 52, OCSAL: N register set to invalid instruction 000000000000: invalid opcode 0o0
```

No HELLO output appeared. The CLI exited with status 0, so the simulator alarms and program output must also be checked.

The tape was regenerated from `assembler/examples/hello.tx2as` to check whether the repository tape was stale. Assembly succeeded, and execution produced the same alarm. Loading HELLO and selecting CODABO in the official browser [demo](https://tx-2.github.io/demo/) produced the same OCSAL alarm. The root cause was not established. These observations apply to the inspected revision and default execution path.

The [Sketchpad transcription repository](https://github.com/TX-2/Sketchpad) HEAD was `3d134b23d207f169d0fb65ac5768177867689ed2`, committed at 2026-11-09 12:02:14 UTC. Assembling `sk.tx2as` with that simulator revision's `tx2m4as` returned status 1 and 12 syntax diagnostics, including lines 2988, 3054, and 4241. The diagnostics involve assembler support and transcription input, and individual causes were not established. [Issue #133](https://github.com/TX-2/TX-2-simulator/issues/133) remained open, with a 2026-11-09 update describing progress on macros and XOR support.

This evidence establishes a working foundation of tools and simulation infrastructure, with full reconstruction still in progress. Running the original Sketchpad remained a subsequent goal at this research snapshot.

## Implications for Verilog reconstruction

Available sources support specification work and module development. The [Users Handbook and three-volume Technical Manual index](https://tx-2.github.io/documentation/) covers instructions, memory, control, exchange, arithmetic, I/O, and timing diagrams.

The main challenges are selecting a historical machine configuration, resolving special arithmetic and configuration semantics, and obtaining reliable historical program samples. The [software documentation](https://tx-2.github.io/software/) describes proofreading problems in historical source and binaries. Superscripts and subscripts in Sketchpad suffered substantial degradation in photocopies and scans. The Verilog implementation must account for these evidence gaps.

The Rust implementation supplies assembly tools, comparisons for implemented behavior, and some test vectors. Conflicts with the manuals require checking original documents for the corresponding period. Unimplemented arithmetic instructions require independent reference models.

## Initial local preparation

- Pinned upstream revisions, audited opcode coverage, and recorded reproduction results.
- Downloaded OCR text for the Users Handbook and Technical Manual vol. 2; scans still required inspection at this stage.
- Added two Verilog field-decoding modules and 19 simulation vectors.
- Added Icarus simulation, Verilator lint, and Yosys generic synthesis targets.
- Defined phased goals and acceptance criteria in [VERILOG-PLAN.md](VERILOG-PLAN.md).

At this stage, local work consisted of source preparation and two initial RTL modules. The whole machine was not yet implemented.

## Primary-source collection update, 2026-11-10

Public mirrors and collections subsequently supplied 60 original-document PDFs totaling 5,346 pages, plus three reference posters. Counts include alternate scans and revisions. Local files now cover all three technical-manual volumes, the circuitry handbook, user memos, early progress reports, graphics semiannual reports, and both parts of the original Sketchpad listing.

The main register paths, configuration structure, and key LDA/TSD timing sections were read closely and visually checked. See [HARDWARE-READING.md](HARDWARE-READING.md) for analysis and [PRIMARY-SOURCES.md](PRIMARY-SOURCES.md) for the complete source inventory and missing material. The earlier OCR-only description records the initial research stage.

## Local Verilog execution-core update, 2026-11-10

After the request to develop Verilog, the project implemented a serial multicycle core, a configuration-exchange data path, S/T memory, and the standard plugboard ROM. An M4 program's 52 committed instruction states matched an independent reference model. The first ten plugboard instructions executed up to the then-unimplemented IOS. See [RTL-STATUS.md](RTL-STATUS.md) for functional scope. The earlier simulator research concerns a separate public project.

## Local serial whole-machine model update, 2026-11-10

`tx2_machine` subsequently integrated all 50 named opcodes, 33 sequences, arithmetic, S/T/U, meta and parity, traps, and the main device interfaces. HELLO booted from the original plugboard through a 294-line paper tape and printed three times. A 276-line display/light-pen diagnostic produced four points and completed its interrupt count. All 50 opcodes committed in 414 whole-machine instruction cases.

Current local scope, verification records, and precision limits are documented in [RTL-STATUS.md](RTL-STATUS.md). The public-project research above retains its original date and pinned revision scope.

## Local Sketchpad execution update, 2026-11-10

The project split the pinned transcription into seven independent modules, repaired a separate assembler checkout, and recorded transcription adaptations. The resulting application image contained 11,914 words. It cold-booted through the original plugboard from a 72,024-line paper tape, then ran for 10 million application clocks and produced 9,479 display points, continuously refreshing the original empty INK screen.

These are results for the locally reconstructed listing. The public-project research above retains its pinned version and reproduction scope. The source still contains inferred repairs, and complete drawing interaction required further acceptance work at this stage. See [RTL-STATUS.md](RTL-STATUS.md) for images, logs, build targets, and limits.

## Local browser drawing update, 2026-11-10

The browser now operates original Sketchpad through the light pen. Accepted interactions include horizontal and diagonal lines, connected segments, STOP, and continued display after lifting the pen. Geometry resides in TX-2 model memory, and the canvas displays CRT points emitted by the original program. The whole machine runs as WebAssembly in the browser, with console, paper-tape, typewriter, button-box, and settings controls. Start it with `make browser`. The public-project research above retains its original pinned revision scope. See the [browser implementation and acceptance results](RTL-STATUS.md#tx-2-in-the-browser-2026-11-11).
