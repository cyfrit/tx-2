# TX-2 serial whole-machine functional model

Date: 2026-11-10. The whole-machine entry point is `rtl/tx2_machine.v`. All 50 named opcodes have execution paths. The 33 sequences, arithmetic, memory, traps, and device control are integrated. Character and graphics diagnostics boot from the original plugboard through paper tape. The model is a synthesizable serial functional implementation. Original-machine overlap, α/β pulses, and analog-circuit precision remain separate reconstruction work. Commands and code paths are relative to the repository root.

## Primary sources and implementation choices

Instruction behavior primarily follows the Users Handbook from approximately 1963. Hardware procedures are checked against the three-volume 1961 Technical Manual. Replacement pages retain their individual dates. SKX uses 1963 semantics, with the 1965 changes tracked separately.

- [Users Handbook ch. 3](../references/pdfs/TX-2_UserHandbook_ch3.pdf): configurations, transfers, logic, subword arithmetic, and instruction execution tables.
- [Technical Manual vol. 2](../references/pdfs/LM-44v2_TX-2_Technical_Manual_Volume_2_196106.pdf): §12-6 configurations, §12-7 sequences, and §14 arithmetic and AOP.
- [Technical Manual vol. 3](../references/pdfs/LM-44v3_TX-2_Technical_Manual_Volume_3_196107.pdf): instruction register pulses; shifts, normalization, partial addition, multiplication, and division on PDF pp. 138–160.
- [Users Handbook Nov63](../references/pdfs/TX-2_UsersHandbook_Nov63.pdf): devices, traps, console, memory, and plugboard on PDF pp. 93, 95–96, 105, 107–112, and 136–152.

The upstream Rust implementation supplies the cross-assembler and reference material. DPX indexing, paper-tape block links and checksums, AOP, and other issues were checked against the manuals with independent verification paths.

## Instructions and data paths

| Opcode, octal | Implementation |
| --- | --- |
| 04 | OPR: IOS and AOP directly specifying arithmetic operations 60–77 |
| 05–07 | JMP, JPX, JNX; return-point saving, index increments, hold/dismiss |
| 10–12, 14–17 | AUX, RSX, SKX, EXX, ADX, DPX, SKM |
| 20–22, 24–27 | LDE, SPF, SPG, LDA/B/C/D |
| 30–32, 34–37 | STE, FLF, FLG, STA/B/C/D |
| 40–43, 45–47 | ITE, ITA, UNA, SED, JOV, JPA, JNA |
| 54–57 | EXA, INS, COM, TSD |
| 60–62, 64–67 | CYA, CYB, CAB, NOA, DSA, NAB, ADD |
| 70–72, 74–77 | SCA, SCB, SAB, TLY, DIV, MUL, SUB |

Undefined opcode slots trigger OCSAL. Test programs use undefined opcode 00 as an expected stop condition. No additional HLT instruction is introduced.

A/B/C/D/E are 36-bit registers. X has 64×18 content bits plus parity; F has 32×9 content bits plus parity. X0 and F0 remain zero. P/Q use 17-bit physical addresses. The original instruction word is retained for commit traces.

The exchange unit supports all 512 configuration values, eight forward/inverse permutations, active-field merging, four subword forms—36, 18+18, 27+9, and 9+9+9+9—and wraparound sign extension within subwords. Stores inverse-permute using the activity mask in AE coordinates. INS also inverse-permutes the B mask. COM permutes the whole word even when every field is inactive.

Arithmetic uses ones-complement end-around carry, preserves each instruction's positive/negative-zero rules, and manages Z through the sign quarter of each active subword. ADD/SUB retain the original operand in D and produce partial-addition C. DSA merges new carries into old C. MUL iterates PAD/MS and finishes with complete carry propagation. DIV iterates PAD/CRY/rotation and final remainder correction. The implementation uses these iterative operations throughout. In 27+9 form, the longest active subword determines the shared ASK step count, preserving unusual low-nine-bit behavior.

CYCLE/SCALE take their parameter from D's sign quarter and finish with negative zero. SCALE and NORMALIZE process old Z and repair signs according to shift direction. AOP reads the arithmetic opcode and fracture/activity directly from N, operates on existing A/D, and skips operand-memory access. Unexpanded activity gates shift pulses by quarter.

## Sequences, memory, and console

The 33 schedulable sequences are 00 and 40–77. Standard priority gives lower numbers precedence, as specified on Handbook PDF p. 138. A 384-bit parameter permits patching each sequence's six-bit rank. Sequence 00 remains highest. Implemented behavior includes flags, K, limbo, hold, dismiss, TSD retry after waiting, P/X placekeeper exchange, and sequence reports in E.

| Region | Mapping |
| --- | --- |
| S | 000000–177777, 65,536 words |
| T | 200000–207777, 4,096 words |
| U | 210000–217777, 4,096 words |
| A–E | 377604–377610; accesses share the core's register state |
| Knob / External | 377620 and 377621; 36-bit external inputs plus meta |
| Real Time Clock | 377630; 36 bits, external 10 μs tick; panel reset clears it, program writes leave it unchanged |
| Fixed startup-switch words | 377710–377717; eight external 36-bit switch words |
| Console toggle words | 377720–377737; sixteen 36-bit switch words with individual meta; `panel_data/panel_meta` |
| Plugboard | 377740–377777; 32-word original ROM |

S/T/U store data, meta, and odd parity. Ordinary writes preserve meta; SKM can change it. Read parity and newly generated parity separately supply SKM bits 11/12. Read/restore reconstructs parity. Injected bad parity supports stop, suppression, and CALACO tests. RAM data is uninitialized. Digital power-up images with meta=0 and parity=1 are stored separately in `programs/core-init-*.hex`. Reset preserves RAM.

Trap control unit 42 supports instruction, defer, and operand meta; sequence switches with marked placekeepers; and external synchronization. Automatic setting of the three meta classes also requires console-switch enables. Marked sequences undergo two CSK operations, retaining original old/new reports and the placekeeper mark.

Console functions include STOP with current-instruction drain, CALACO, PRESET, RESET starting points, STARTOVER, forced hold, and CODABO requests while running. CODABO restarts at an instruction boundary, clears flags and alarms, presets devices, and preserves information registers.

Digital alarm bits are 0 MPAL, 1 NPAL, 2 XPAL, 3 FPAL, 4 PSAL, 5 QSAL, 6 OCSAL, 7 IOSAL, and 8 MISAL; bit 9 is reserved. Suppression permits continued execution while retaining alarm lamps. Connecting alarm sequence 41 suppresses MISAL stops. Analog memory-timing TSAL/USAL and the maintenance Mousetrap are unmodeled.

`fault` records debug stop reasons: 1 undefined operation; 2 undefined OPR mode; 3 selection-address error; 4 read-only write in the early configuration; 5 internal state; 6 unsupported legal operation in the early configuration; 7 parity; 8 IOS device selection. `tx2_system` fixes `EXTENDED=0` for the early 19-opcode tests. The complete machine uses `tx2_machine`.

## Device interfaces

- PETR 52: one-line six-bit buffer, ready/valid, and bin-load rewind. Mode 100 runs; bit 2 selects assembly. Commands 30100 and 30102 read normal and assembly data, 30104/30106 rewind first, and 30000/30002/30004/30006 stop the tape. An external transport supplies the underlying six-bit stream.
- Lincoln Writer 66: six-bit output buffer that retains blocked characters. A busy-to-idle transition or first connection requests sequence service. Continuous idle preserves software dismiss behavior.
- Interval Timer 54: 18-bit interval buffer and external base tick. Mode 100 starts it; 200 connects its flag. Disconnecting the flag with 20000 leaves counting active.
- Displays 56/60: ten-bit ones-complement X/Y from 4.9–3.9 and 2.9–1.9. Mode 100/200 changes the origin. Modes 10/20/30 select 20/40/80 μs; the default is 10 μs. Buffering, output handshakes, and intensification duration are visible.
- Light Pen 55: receives hits during display 60 intensification and requests sequence service. The camera has separate request/done and inability inputs.
- Alarm 41: reports the manual's nine MISAL/EIA bits. Disconnecting the corresponding device clears its alarm. Additional alarms do not request sequence 41 again.
- Other devices: presence, ready, input direction, assembly/reverse status, IOS control events, and 36-bit TSD data/mask interfaces. External controllers supply each physical device's complete behavior. Connecting an offline unit produces IOSAL.

Whole-machine peripheral time comes from `tick_1us`, `tick_10us`, and `timer_tick`. RTL instruction cycle counts do not define original-machine microseconds. See `rtl/tx2_machine.v` for pin names.

## Boot acceptance and paper-tape corrections

[hello.tx2as](../programs/hello.tx2as) and [display-demo.tx2as](../programs/display-demo.tx2as) produce machine words and paper tapes through the pinned M4 assembler. Tests define RAM power-up data as zero and begin at 377750. Programs load through paper tape.

| Acceptance case | Result |
| --- | --- |
| HELLO | K00 → K52 → K66; 294 lines, 974 commits, three `HELLO, WORLD\r` messages |
| Display/light pen | 276 lines, 881 commits; four origin-transformed display points; a four-instruction light-pen handler increments its counter to 1 |

The plugboard loads the **20-word reader leader** at locations 3–26. The tape-generation tool preserves that leader and corrects two observed issues: nonfinal block trailers must return to 3, and checksums use 18-bit ones-complement end-around sums. Without these corrections, execution reaches a zero word at 100 before loading the program. Original and corrected trailers and checksums are recorded in `.paper.json`, along with the original assembler tape SHA. Source/image fingerprints and tape-block checksums are checked automatically before simulation.

`make graphics` renders `build/display-events.csv` into `results/display-demo.svg` and writes the decoded events to `results/display-events.json`. This graphics program is a project diagnostic with an [example rendering](../results/examples/display-demo.svg). The reconstructed Sketchpad listing also boots from paper tape and draws through the browser, as described below.

## Reproducible checks

```sh
make clean
make check
```

| Check | Result |
| --- | --- |
| Field decoding | 19 cases |
| Exchange | 65,536 vectors; all 512 configurations, both directions, sign extension on/off |
| ALU | 7,972 vectors; 14 operations and four subword forms; mathematical multiply/divide results and micro-operation invariants cross-checked |
| Whole-machine instructions | 414 cases with real LD/SPG/SKX initialization; all 50 opcodes commit, plus 14 AOP cases |
| Priority | 6,000 flag/patchable-rank combinations, including sequence 00 and ties |
| Memory/control | 427 RAM comparisons, four parity classes, suppression/recovery, selection/device alarms, four meta traps, automatic meta setting, running CODABO |
| Sequence integration | Limbo, TSD wakeup, held transfers, priority preemption, dismiss, placekeeper restoration |
| Devices | 20 control/transfer checks, plus buffering stalls, timer pulse spacing, display duration, light pen/camera, and alarms |
| Historical regression | 52 instruction-state matches; replay with 106 transactions and 372 inserted wait cycles; 195 early-configuration checks |
| Cold boot | Complete HELLO and graphics/light-pen paper-tape paths |
| Tools | Verilator `-Wall` for ten modules, Yosys structural checks for ten modules, generic gate-level synthesis of the complete core |

`make check` prints the regression results and writes lint and synthesis logs under `build/`. Icarus emits informational `@*` sensitivity-list messages for mode/paper arrays. Verilator acceptance requires zero warnings.

## Remaining precision and historical-software work

1. The serial FSM preserves visible operation order. Original PK/QK/AK overlap, α/β pulses, destructive core-read electrical behavior, and analog alarms still require phase-level reconstruction.
2. Partial-activity AOP gates pulses by quarter and has an original-manual CYA coupling example. Other uncommon partial-activity arithmetic combinations require calibration against original programs and gate rules. All-zero normalization ASK termination requires pulse-level comparison with counter tables from different revisions. Independent mathematical vectors and micro-operation vectors have different coverage limits.
3. PETR is abstracted as a handshaked six-bit line stream with rewind. Seventh-hole handling, end-mark search, mechanical inertia, and free-running missed-data behavior require a physical transport layer. Writer tests check character codes; glyphs and typewriter mechanisms are external.
4. Display DACs, phosphor decay, camera mechanisms, and analog light-pen sensitivity are outside the RTL reconstruction. Timer and clock use external logical ticks. Board wiring, oscillator selection, and timing constraints depend on device selection.
5. Tape, Xerox, punch, and other devices currently connect through the common device interface. Their internal registers, dedicated modes, and mechanical timing require separate controllers.
6. Sketchpad passed browser acceptance for light-pen capture, two connected segments, endpoint placement, and continuous refresh. General editing, arcs, and constraint solving require separate validation.
7. Synthesis establishes generic logic synthesizability and structural evidence. BRAM mapping, device place and route, board timing, and FPGA measurements remain pending.

These records establish functional paths for all 50 opcodes and complete boot execution. Detailed historical calibration remains bounded by the work listed above.

## Reconstructed Sketchpad listing execution

Run `make sketchpad`. The pinned upstream transcription is `3d134b23d207f169d0fb65ac5768177867689ed2`. Seven independent assembly modules cover main control, computation/model, constraints, constraint solving, light pen/tracking, characters/tape, and display/drawing. The constraint program, IES BOO7, combines equations, macros, and type tables from part 1 PDF pp. 138–152 with constraint-computation subroutines from part 2 PDF pp. 2–7. Code after the final `ORIGIN|` in part 1 is printed in part 2. Its earlier omission made constraint satisfaction jump to undefined addresses. The solver module includes the final IPCONCOMP1 page on PDF p. 78. A separate assembler worktree applies [sketchpad-assembler.patch](../tools/sketchpad-assembler.patch), preserving the upstream checkout.

Repairs and checks covered right-side symbol references, default allocation and listing evaluation order, RC placement after the final manuscript block, negative integer expressions, macro default-exit `0/0` selection, and explicit not-hold precedence over automatic hold. All 315 existing and added Rust cases passed. Nine independent machine-word probes also checked omitted macro arguments, field forwarding, local labels, shared RC subroutines, current address, and not-hold.

`tools/prepare_sketchpad.py` records 169 line-level adaptations: 96 scan-checked, 68 mechanical normalizations, and five inferences. All assembly pages—part 1 PDF pp. 11–58 and 84–152; part 2 PDF pp. 2–7, 11–51, 54–78, 81–112, and 116–155—were checked line by line against scanned glyphs, in eight-page assignments, using repeated digits and letters on each page as comparisons. Screenshots are in `references/figures/sketchpad-scan-fixes/` and `references/figures/sketchpad-*.png`. Functionally significant scan corrections include:

| Location | Transcription | Scan reading | Effect |
| --- | --- | --- | --- |
| Part 1 PDF p. 18, PUTR macro | `hJPX S #+3` | `#+2`, matching PUTLQ/PUTRQ on the same page | The ring chicken failed to write back to its hen block; ATBITS type bits stayed clear, disabling MOVE/HORV |
| Part 1 PDF p. 25 | `SKZ 2.1 74BUT` | `76BUT` | MOVE read an undefined variable |
| Part 1 PDF pp. 33/47/53 | `RSZ`, `SPX`, `LDS` | `RSX`, `¹DPX`, `LDA` | Unknown mnemonics became symbols and generated incorrect words |
| Part 1 PDF p. 34, TRUEUP | `JPQ TRUEUPX` | Handwritten correction “← MKN MOVED” points here | New HORV constraints failed to trigger relaxation |
| Part 1 PDF p. 48 / part 2 PDF p. 77 | `LTAKE≡VORDE×…` | `VORD` | Ring operations used an undefined offset |
| Part 1 PDF p. 152 | Missing line | `hJMP HOVSCOMP`, original word `400500 021103` | Shifted constraint jump table made HORV call IBVERTCOMP |
| Part 2 PDF p. 3, MSCOMP | `LIST??`, obscured by ink | Inferred `LISTγ` | Symmetric with β on the preceding line |
| Part 2 PDF p. 47, MAGIGOA | `MOVE\|MAGIX→²…` | `MAG1X`; italic 1 differs from upright I in MAGILV | Instance-display recursive return was overwritten, causing an infinite loop |
| Part 2 PDF pp. 67/68, SOLVEM | `LDA x1 S\|β x3`, `SLVTS-1`, `JOV SLVAD9` | `LDA x1\|x3`, `SLVT5-1`, `SLVAD8` | Solver looped indefinitely |
| Part 2 PDF pp. 75/76 | Labels `WKR1A`, `WKR4` | `WRK1A`, `WRK4` | References reached undefined addresses |
| Part 2 PDF p. 41, MAGPIC | `STA MATH` | `STA MATM`; handwritten arrow moves `DPX NDISP` to MAG entry | Instance transformation matrix was uninitialized |
| Part 1 PDF pp. 46/31 | `MUL {100.}` | `MUL {100.,}`; decimal 100 in the left half | COPY scale was zero, collapsing copies to a point |
| Part 1 PDF pp. 110/113 | `MOVING-LIST`, `⁻¹ CMα NUMMON1`, `JPA` | `MOVINGS-LIST`, `⁻¹JPX CMα NUMMON1`, `¹JPA` | Typing failed to change text; NUMBER stopped on a zero word |
| Part 2 PDF p. 96, TRLP | Two `hJPQ TRREX / ²⁰INX 60 1` groups | Three groups | Missing lines |
| STAE macro, part 1 PDF p. 91 and part 2 PDF pp. 89/121 | `STA A+D` | `STD A+D` | Fourth register stored incorrectly |
| Other corrections | `JNK`, `JQP`, `2DPX`, `MAB`, `RES`×2, `XSETX`, `45RSW`, `45SIT1`, `TAPER3`×2, `PLPBUSY`, `STOMOVEP2J`, `Ps2P`, `GARB?`, `377758`, `MERGEIPFX`, `DUMEX`, `SRCENTRY`, `LMSLRT`, `JPX`→`JPQ`×2, `JNA`→`JNX`, `⁸SCB`, LLCROSS `²DPX`, `45R X2` subscript, six data-word commas, constants `26415202030` and `343597302`, `IOS 66 30000` | `JNX`, `JPQ`, `²DPX`, `NAB`, `REX`, `XSETK`, `45RWSW`, `45IT1`, `TAPEK3`, `PLPUBUSY`, `STOPMOVEP2J`, `PS2P`, `GARB3`, `377750`, `MERGEIFPX`, `DUMMEX`, `SCRENTRY`, `LMSLRX`, `²SCB`, `¹DPX`, `45X2`, corrected commas, `26413202030`, `343597382`, `50000` | Instruction, label, data, or constant errors |

Toolchain repairs handle spaced prefix macro arguments such as `β ▭ A,α`, whose failed substitution previously assembled `PSβ▭TYPE,PSγ` as `RSX β`, and RC words adjacent to mnemonics such as `LDA{…}`, which previously became undefined symbols. Five inferred repairs remain: DESIGNATE `JPQ #+1→#+3`, since the scan cannot distinguish 1/3 and control flow supports 3; COPYFIXC `MOVEL≡α×δ→0×γ` changed to `0×δ`, since the listing prints both 0 and α as solid dots and α=1 overwrites the next block's TYPE word, corrupting COPY rings; MSCOMP `LISTγ`, obscured by ink; ADCON superscript 2, cut by the page edge; and the io `?=#` rewrite. Two readings were retained on functional evidence despite conflicting page reviews: SOLVEM `SLVT5-1`, since the comment identifies a matrix position and this reading permits solver convergence, while another reader saw `SLVTS-1`; and the final dot on PDF p. 24's `47LITE1→` line, treated as a blemish because reading it as data zero makes sequence 47 execute a zero word. Unresolved scan readings retain the transcription: the subscript in part 1 PDF p. 130 `RSX β 45TSD` may be μ, the first subscript of part 2 PDF p. 96 `TR55` is unclear, and PDF p. 149's last line is cropped. Undefined symbols `NEWCON`, `OVERRELAXFAC`, `NPOLN`, and `LPAREN/RPAREN` are preserved as printed and automatically allocated as zero.

Private RC and macro-helper code use existing U RAM. All seven modules share model address 022000. The constraint module extends the model length, the only intentional conflicting word in the merged image. Any other conflicting value aborts the build. The final image contains 12,623 words. Paper tape retains the original 20-word reader leader, and each block's ones-complement checksum is recomputed independently.

In paper-tape mode, `tb_sketchpad` defines RAM power-up data as zero and boots from original plugboard address 377750. Application instructions arrive through the tape. Observed results:

| Item | Result |
| --- | --- |
| Paper tape | All 76,278 lines read; one bin rewind |
| Load completion | Original CLEAN entry reached at logical clock 3,644,765 |
| Total execution | 13,644,765 clocks, 1,033,648 commits |
| Application execution | 10 million post-load clocks, 754,176 commits |
| Graphics | 9,479 actual CRT events at 802 distinct positions, continuing into the final execution interval |
| Machine state | `fault=0`; background sequence 76 and display sequence 60 continue running |

`make sketchpad` renders INK from the original `S1NULL/S1INK` empty-screen routines in `results/sketchpad-screen.png`. Rendering uses emitted ten-bit ones-complement coordinates and the original program's glyph points. Point records, recent instructions, and post-run memory are `results/sketchpad-points.csv`, `results/sketchpad-run.trace`, and `results/sketchpad-memory.hex`. The run writes statistics and source fingerprints to `results/sketchpad-run.json`.

Startup suppresses IOSAL for offline devices. UNITS OFF access to unimplemented devices leaves `alarms=080`; the stop fault code remains zero. This section covers headless cold boot and continuous display. Interactive behavior is recorded under Sketchpad button functions below.

## TX-2 in the browser, 2026-11-11

`make browser` compiles WebAssembly and serves a static site at `http://127.0.0.1:8002/`. The shared host, `host/tx2_host.h`, drives `tx2_machine` and supplies board time bases; console controls for TSP, sixteen toggle words with meta, eight fixed starting words, knob, external register, alarm suppression, hold, and button pulses; PETR `.tape` input that skips bytes without feed holes; Lincoln Writer 66 output and 65 keyboard input paced at a default 50 ms per key; punch 63 with mode bit 2 adding a seventh hole and bit 1 assembling words; random-number unit 61; and light-pen/camera handshakes. WebAssembly in `host/tx2_wasm.cpp` and the native debug CLI in `host/tx2_cli.cpp` forward text commands to this host. Power-up memory is zero and the machine is stopped. The tape library's load-and-start action loads tape, sets TSP=377750, and issues CODABO.

The light pen moves linearly across each clock batch, with a default limit of two coordinate units per 10,000 clocks. Drawing tests occasionally lost tracking at three to four units; without drawing, tracking worked at eight units. Sketchpad reads external register V377621 with DRAW=1.8, STOP=1.6, and CENTER=1.7 through original sequences 47/76. The program selects devices absent from this machine, so tape-library startup suppresses IOSAL visibly on the console. The canvas draws RTL-emitted points; model geometry resides in TX-2 memory.

Browser phosphor persistence follows the Users Handbook description “phosphor persistancy of about 2 seconds,” found at OCR line 3963 in the 1961-07 edition and line 4487 in the 1963-11 edition. Each point decays exponentially in TX-2 time, reaching approximately 5% brightness at two seconds before removal. Refresh restores full brightness. The manual's two-second figure is approximate; the exponential curve is inferred. This display effect preserves RTL output.

Measured simulation speed was approximately 1.1–1.2 million clocks/s in desktop Chromium. An iPhone running iOS 27.2 reached 4.3–5.15 million clocks/s over HTTPS and approximately 33,000 clocks/s over HTTP. WebKit disables JIT in insecure contexts; see [bug 324968](https://bugs.webkit.org/show_bug.cgi?id=324968).

The [acceptance script](../tools/test_browser.py) runs in Chromium. HELLO starts from the tape library and prints three lines. The uploaded upstream `examples/hello.tape` fails to boot as shipped and prints HELLO after the upstream-tape repair action. Sketchpad targets INK, draws two connected segments with clicks, stops, lifts the pen, and runs another 2.5 million clocks, emitting points covering 50 horizontal and 45 diagonal positions with `fault=0`. The camera exports PNG, and a 390×844 mobile viewport has no horizontal overflow. The script writes screenshots and `browser-integration.json` under `results/`. [Sketchpad drawing example](../results/examples/browser-drawing.png)

### Sketchpad button functions, 2026-11-11

Button bit numbers come from Sutherland's TR-296 Appendix B: DRAW 1.8, CIRCLE CENTER 1.7, MOVE 2.1, DELETE 1.3, STOP 1.6, HORV 2.9, INSTANCE 2.4, COPY20 3.6, NUMBER 3.7, and others. The browser input page labels the complete Sketchpad template. The listing dispatch table assigns TEXT to 3.2. The thesis OCR says 4.3, which the listing uses for IBM tape record input, unavailable here. [`tools/test_sketchpad_functions.py`](../tools/test_sketchpad_functions.py) operates the debug CLI at the browser's default pen speed and reads model rings and CRT output:

| Function | Result |
| --- | --- |
| Line: DRAW … STOP | One line, two points |
| Arc: CIRCLE CENTER → DRAW → sweep 270° → STOP | One circle; approximately 230 CRT points on radius 50 |
| MOVE: target endpoint, move to −20,200 | Endpoint reaches −20,200 |
| HORV and constraint satisfaction: set FIX meta at 377720 | Diagonal endpoints become −128,200 and −20,200, producing a horizontal line |
| DELETE: target line | Line deleted, circle retained |
| INSTANCE: select picture 2 at 377724, picture 0 at 377725 | New instance displays picture 0; moving the pen 80 units right shifts its display range 80 units right |
| COPY20: picture 0 at 377720 | One actual circle copied |
| TEXT and Lincoln Writer H E L input | Initially displays X, then “HEL” after typing |
| NUMBER | New number object created and displayed |

The critical defects originated in transcription or assembly and were corrected against scans, as recorded above. Moving the pen off-screen ends movement and loses Sketchpad tracking. Target INK or existing geometry again to reacquire it.

The debug CLI's `fx` command reads all 32 F configurations and 64 X index registers.

Interactive debugging completed M4 predefined A–E symbols, AOP instruction representation, and ones-complement negative zero. The original tool lost the negative-zero sign, corrupting coordinate-insertion masks. Scan-checked repairs include SQ60SEE `S1α` transcribed as `S|α` and LDE as LDQ; an omitted LDE in LPSEES; PSEUDO decimal 18 transcribed as 10; and LMAG INS, LMEND+1, and two separator arrows. Build tools record line sources, classifications, and asset fingerprints in `programs/sketchpad/manifest.json`. Additional evidence images are `references/figures/sketchpad-{pen-p243,pseudo-p250,pseudo-p251,line-p289,lines-p291}.png`.
