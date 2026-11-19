# Specifications: Lincoln Writers and auxiliary devices

## Sources and conventions

All unit numbers, character codes, mode words, and masks below are **octal**. TX-2 bit `1.1` is the least-significant bit; quarter 1 is the rightmost nine bits.

Source abbreviations:

- **H63** — `references/text/TX-2_UsersHandbook_Nov63.archive-page-ocr.txt`; corresponding PDF `references/pdfs/TX-2_UsersHandbook_Nov63.pdf`.
- **H61** — `references/text/TX2-Users-Handbook_196107.txt`; corresponding PDF `references/pdfs/TX2-Users-Handbook_196107.pdf`.
- **LW** — Gilmore and Savell, *The Lincoln Writer*, Group Report 51-8, 6 October 1959: `references/text/ad-0235247.txt`; PDF `references/pdfs/ad-0235247.pdf`.
- **TM2** — `references/text/LM-44v2_TX-2_Technical_Manual_Volume_2_196106.txt`.
- **SK1**, **SK2** — `upstream/Sketchpad/sk.tx2as`, `upstream/Sketchpad/sk2.tx2as`.

PDF page references are one-based. Ambiguous OCR was checked against primary-source scans through Internet Archive's page-image endpoint. Links identify the inspected pages. Code paths are relative to the repository root.

### Common IOS/TSD rules

`IOS_j 20000` disconnects; `IOS_j 3xxxx` connects and sets mode; `40000` lowers flag; `50000` raises flag. For ordinary output devices, connecting a previously disconnected unit raises its flag. Merely changing mode while already connected does not automatically do so. Device-specific exceptions are specified below. [H63:3205–3246]

A successful TSD dismisses the sequence unless held. A busy or disconnected device causes **dismiss-and-wait**, even if held; the TSD is retried because P has not advanced. Normal TSD permits permutation/activity and has **no sign extension**. Buffers occupy the rightmost bits unless a device description says otherwise. Ordinary inactive output-buffer portions receive `+0`. [H63:3281–3316]

An IOS with the report configuration bit—bit `4.4`, conventionally superscript `1`—copies the **pre-operation** device report into E. Ordinary IOS does not change E. Standard report layout: [H63:3258–3276]

| Report field | Meaning |
|---|---|
| `1.1`–`2.3` | Twelve mode bits, for most units |
| `2.4` | MISIND |
| `2.5` | Equipment inability, EIA |
| `2.6` | Connected |
| `2.7` | Maintenance |
| `2.8` | Buffer free: 1 means available |
| `2.9` | Flag |
| `3.1`–`3.6` | Reporting sequence/unit number |
| `3.7`–`4.9` | Unit-specific indicators, zero where unused |

---

## 1. Lincoln Writers: input `65`, `71`; output `66`, `72`

### 1.1 Physical organization and IOS

The two on-line Writers use pairs `65`/`66` and `71`/`72`. Input consists of two coding keyboards plus a Soroban mechanical tape reader. Output consists of an IBM electric typewriter and a paper-tape punch. The handbook calls the punch Friden; the 1959 report describes a modified Commercial Controls Model 2. These descriptions should retain their dates rather than be silently reconciled. [H63:4744–4757; LW:680–692]

| Unit | IOS | Mode-word meaning |
|---|---|---|
| `65`, `71` | `30000` | Connect keyboard/reader input. A key raises the corresponding flag if manually routed to the computer. |
| `66`, `72` | `30000` | Connect output, manually routed to Writer and/or punch. Raise flag only if previously disconnected. |
| Each | `20000` | Generic disconnect |
| Each | `40000`, `50000` | Generic flag control |

The device pages define **no additional programmable mode bits** for choosing reader speed, selecting the punch, choosing color/script, or selecting reader filters. Those functions are manual controls or character codes. [H63:4873–4904,4916–4943; H61:4270–4375]

### 1.2 TSD input data and handshaking

- Input is a six-bit code, occupying **bits `1.1`–`1.6`**, mask `000077`.
- TSD changes only those six buffer-corresponding bits; permutation is allowed, quarter 1 must be active.
- The depressed key is released after its code is accepted.
- When an automatic case-change code is necessary, the key remains locked until **two TSDs**: first the case code, then the character.
- Mechanical/electrical keyboard interlocks prevent transmission of the next character before the previous one has been transmitted; anti-repeat circuitry prevents a long keypress from transmitting twice. [H63:4767–4769,4880–4904; LW:550–574]

“Lower case” is the keyboard containing **capital Roman letters and digits**. The other keyboard contains small letters, mathematical symbols, and Greek letters. These terms refer to the physical keyboard cases. [LW:498–530]

For a character key, an internal seventh bit identifies its keyboard case and is compared with a case-memory relay. When necessary, the hardware transmits `74` or `75` first. A function key does not cause automatic case selection. **This internal seventh bit is not a seventh CPU data bit.** [LW:550–568]

### 1.3 TSD output data and handshaking

TSD sends six bits, `1.1`–`1.6`, to the selected Writer’s output buffer. Permutation is permitted; quarter 1 should be active. Manual routing determines whether the code is printed, punched, or both. **The buffer remains busy until printing/punching completes**, then the corresponding output flag is raised. No Writer assembly/splayed mode is defined. [H63:4920–4935]

The following codes are accepted by the typewriter, consume about an ordinary character’s time, and **print nothing**:

`14`, `15`, `16`, `17`, `71`, `76`, `77`.

This is explicit in the primary output page; do not render textual labels for these on the simulated paper. [H61:4363–4374; H63 PDF p.121, [inspected scan](https://archive.org/download/tx-2-users-handbook-nov-63/page/n120.jpg)]

### 1.4 Complete six-bit character/function table

The same code table applies to both Writers and both input/output directions. Function codes have the same meaning in either case. Glyphs below are Unicode approximations of the Lincoln typeface; “underbar,” “overbar,” “circle,” and “box” identify the actual printing operations.

**Primary evidence for every table entry:** H63 PDF pp.118 and 197, Table 7-6; H63:4773–4870,9262–9296; LW PDF p.24, Figure 7, [inspected scan](https://archive.org/download/ad-0235247/page/n23.jpg). The latter clearly confirms `72` DOWN and `73` UP.

| Code | Lower case | Upper case / function |
|---|---|---|
| `00` | `0` | Pointing hand, approximately `☛` |
| `01` | `1` | `Σ` |
| `02` | `2` | Vertical bar `│` |
| `03` | `3` | Double vertical bar `‖` |
| `04` | `4` | `/` |
| `05` | `5` | Multiplication `×` |
| `06` | `6` | `#` |
| `07` | `7` | Right arrow `→` |
| `10` | `8` | `<` |
| `11` | `9` | `>` |
| `12` | Underbar | Overbar |
| `13` | Circle | Box |
| `14` | READ IN | Same function |
| `15` | BEGIN | Same function |
| `16` | NO | Same function |
| `17` | YES | Same function |
| `20` | `A` | `n` |
| `21` | `B` | Subset `⊂` |
| `22` | `C` | Logical OR `∨` |
| `23` | `D` | `q` |
| `24` | `E` | `γ` |
| `25` | `F` | `t` |
| `26` | `G` | `w` |
| `27` | `H` | `x` |
| `30` | `I` | `i` |
| `31` | `J` | `y` |
| `32` | `K` | `z` |
| `33` | `L` | `?` |
| `34` | `M` | Union `∪` |
| `35` | `N` | Intersection `∩` |
| `36` | `O` | `j` |
| `37` | `P` | `k` |
| `40` | `Q` | `α` |
| `41` | `R` | `Δ` |
| `42` | `S` | `p` |
| `43` | `T` | `ε` |
| `44` | `U` | `h` |
| `45` | `V` | Superset `⊃` |
| `46` | `W` | `β` |
| `47` | `X` | Logical AND `∧` |
| `50` | `Y` | `λ` |
| `51` | `Z` | Tilde-like symbol `~` |
| `52` | `(` | `{` |
| `53` | `)` | `}` |
| `54` | `+` | Equivalence `≡` |
| `55` | `−` | `=` |
| `56` | Comma | Prime/apostrophe |
| `57` | Period | Asterisk |
| `60` | CARRIAGE RETURN | Same function |
| `61` | TAB | Same function |
| `62` | BACK SPACE | Same function |
| `63` | COLOR BLACK | Same function |
| `64` | SUPERSCRIPT | Same function |
| `65` | NORMAL SCRIPT | Same function |
| `66` | SUBSCRIPT | Same function |
| `67` | COLOR RED | Same function |
| `70` | SPACE | Same function |
| `71` | WORD EXAM | Same function |
| `72` | LINE FEED DOWN | Same function |
| `73` | LINE FEED UP | Same function |
| `74` | LOWER CASE | Same function |
| `75` | UPPER CASE | Same function |
| `76` | STOP | Same function |
| `77` | NULLIFY | Same function |

The underbar, overbar, box, and circle are **dead characters**: they do not advance the printing position. [LW:444–452]

### 1.5 Case, script, color, carriage, and software functions

**Carriage return `60`:**

1. Returns the carriage.
2. Advances the paper.
3. Resets to lower case.
4. Resets to normal script.
5. Changes the keyboard’s case-memory relay, including when the code originated from CPU output.

No extra `74`/`65` codes are transmitted for these resets. Input and output case state therefore cannot be independent. [H63:4758–4769,4936–4939; LW:600–629]

The documented carriage-return reset names case and script only. **[INFERENCE]** Color should persist across CR unless another primary source establishes an additional reset.

**Script selection:** `64`, `65`, `66` select super, normal, sub. Redundant script selections are ignored by the physical Writer. The output example in the report explicitly feeds the resulting case and script indication back toward the keyboard assembly. [LW:600–629]

**Line feeds:** These are relative platen operations that **do not change remembered script selection**. A line-feed-up can produce the visual effect of superscripting while the machine still remembers “normal.” A subsequent NORMAL code then causes no motion. The report instructs users to undo a line feed with its opposite. They must not be implemented simply as script-state assignments. [LW:633–655]

**Color:** `63` selects black and `67` red. These functions are decoded separately from the typewriter’s ordinary mechanical six-bit character decoder. [LW:578–586; Figure 7/PDF p.24]

**TAB/backspace:** Codes `61` and `62` are the typewriter functions. The inspected sources do not define a fixed software tab width, tab-stop list, or a detailed carriage-return travel-time formula. [H63 Table 7-6; LW Figure 7]

**STOP and special keys:** The typewriter does not itself print or execute the program-control meaning of `14`–`17`, `71`, `76`, `77`. Software assigns meanings. For example, M4 uses WORD EXAM `71` for LIST, YES `17` for the most recent output command, NO `16` for backwards deletion, READ IN `14` for LW READ, and STOP `76` to return control to the keyboard. These are **M4 semantics**, not CPU hardware operations. [H63:8572–8588]

### 1.6 Reader, punch, timing, and manual routing

The keyboard/reader path may drive the computer, punch, and Writer separately or simultaneously. The computer has a second path to Writer and/or punch. Two input sources cannot simultaneously drive the same output unit. Routing uses illuminated pushbutton switches. [LW:698–718]

| Component | Documented timing |
|---|---|
| Typewriter | Approximately 10 characters/s |
| Reader | 9.5 or 19 characters/s; lower speed used when connected to the typewriter |
| Writer’s local punch | Up to 20 characters/s |
| Input pacing | Reader can wait indefinitely for CPU acceptance in the handbook’s “pure on-line” connection |

[LW:578–580,660–692; H63:4897–4907]

**Reader sequence:** Manually press START READER. The reader reads the line at the station, advances one line, and waits for acceptance, normally TSD. The keyboard is disabled while the reader is on. STOP READER re-enables the keyboard. Maximum speed in the handbook is 19 lines/s. [H63:4897–4907]

Reader manual modes, transcribed in full:

| Tape condition | Green selection | Red selection |
|---|---|---|
| STOP `76` | Stop reader | Read and transmit code to punch and/or computer |
| DELETE/NULLIFY `77` | Ignore | Read and transmit code to punch and/or computer |
| Character without seventh hole | Stop reader | Read and transmit to punch: reproduce |
| Blank tape | Ignore | Reproduce |

Green modes are normally used with Writer-produced text tapes; red modes with binary computer-produced tapes for reading/reproduction. [LW:813–839]

Other manual controls and interlocks:

- START, STOP, REWIND.
- Hold STOP while pressing START once per line for single-line operation.
- Rewind is interlocked: reader off and “no tape” contact in the “no tape” position.
- Script-position lights; illuminated routing/mode indicators.
- Punch TAPE FEED punches blank tape while pressed.
- Punch END MARK.
- The 1959 report’s SPARE button/custom seven-toggle character generator was **future equipment** at the report date; do not treat that proposal as proof of installed hardware. [LW:669–677,716–744,783–805,841–845]

**Historical end-mark discrepancy:** the 1959 report prints **`72` without a seventh hole** for the Writer's END MARK button. This was visually checked in [LW PDF p. 15](https://archive.org/download/ad-0235247/page/n14.jpg), corresponding to LW:789–795. The later handbook and PETR technical description specify **`73` without a seventh hole** for PETR end marks. Sources: H63:4020–4030; `references/text/TX-2_TechManVol2_Jun61.archive-page-ocr.txt`:16077–16088. **[INFERENCE]** A 1961–63 interoperable replica should follow the later PETR `73` specification unless dated Writer wiring evidence establishes a different behavior.

**Alarms:** Unit `41` reports EIA for pair `65`/`66` at mask `200`, and pair `71`/`72` at `400`. The inspected Writer sections do not specify the exact physical causes, alarm-clear circuit, or a Writer MISIND source. Do not infer “paper out,” “punch jam,” etc., as established EIA causes. [H61:3450–3462]

### 1.7 Sketchpad usage

| Routine | Evidence and behavior |
|---|---|
| `KEYSTART` | SK1:4916–4932, PDF p.110: switches to sequence `65`, connects with `30000`, receives codes by held TSD into indexed `KEYTAB`, raises output sequence `66` with `50000`. |
| `TYPESTART` | SK1:4933–4944, PDF p.110: switches to `66`, connects with `30000`, sends indexed `KEYTAB` entries with held TSD. |
| `TXCG1` | SK1:4980–4986, PDF p.111: tests `62` as BACKSPACE and `16` as NO. |
| `TYPEβ`, `TYPELOOPβ` | SK1:4283–4307, PDF p.96: output sequence `66`, `IOS 30000`, TSD B followed by character extraction and TSD A. |
| Tape diagnostic output | SK1:4401–4404 and 4617–4620: `TYPEL` prints tape-status messages. |

### 1.8 Initial implementation snapshot

| Area | Observed implementation | Missing or incorrect behavior |
|---|---|---|
| Unit coverage | Host defines input `65`; RTL has dedicated output `66`. [host/tx2_host.h:23–24,138–149; rtl/tx2_io.v:69–70] | Second Writer `71`/`72` absent. |
| Input masks | `external_mask = W36`, including Writer input. [host/tx2_host.h:146–149] | Input must preserve bits outside six-bit buffer mask `77`, including `1.7`–`1.9`. |
| Keyboard generation | JS encoder inserts case codes; host queues raw six-bit codes with `key_us=50000`. [web/lw.js:42–57; host/tx2_host.h:40–41,177–179,301] | No physical two-TSD key lock/release model. A case prefix and its character receive the same generic inter-key pacing. |
| Shared case state | JS stores separate `state` and `keyState`. [web/writer.js:13] | CPU output CR/case changes do not synchronize keyboard case memory. |
| Output timing | Host logs a code when `writer_valid && writer_ready`, then starts `writer_busy_until`; RTL clears `writer_full` on that same handshake. [host/tx2_host.h:166–169; rtl/tx2_io.v:192–197] | **[INFERENCE from the handshake]** Buffer becomes free at the start of host “typing,” allowing the next code to queue before the previous character completes. Handbook buffer busy lasts through completion. |
| Speed option | UI sets `writer_us=100000` when mechanical timing enabled. [web/settings.js:62–67] | Nominal 10-char/s exists, but completion/flag semantics above remain different. |
| Reader/punch | Host tape path is PETR; `PUNCH` means unit `63`. [host/tx2_host.h:23–24,134–137,179–182] | Writer-local reader/punch, routing, reader filters, 9.5/19-char/s selection, local 20-char/s punch absent. |
| Line-feed codes | JS `NAMES` says `72` UP, `73` DOWN. [web/lw.js:10–11] | Names reversed relative to both primary tables. Decoder turns `72` into newline and ignores `73`, lacking relative platen motion. [web/lw.js:29–30] |
| Script/color | Decoder tracks script, color, case, and CR reset. [web/lw.js:13–32] | Renderer approximates super/sub only for a small numeric symbol set; no independent platen displacement. [web/writer.js:5–6,48–55] |
| Backspace/dead characters | Decoder identifies backspace/combining codes. [web/lw.js:19,36] | Renderer ignores backspace and does not implement an explicit carriage/overstrike position model. [web/writer.js:47–55] |
| Nonprinting codes | Decoder returns `{special: ...}` for function codes; renderer adds visible labels. [web/lw.js:34–36; web/writer.js:50] | Primary source explicitly says these codes print nothing. |
| Alarm generation | Generic RTL accepts EIA inputs and aggregates Writer pairs. [rtl/tx2_io.v:151–152,179–181] | Host lacks Writer inability event/control modeling. [host/tx2_host.h:121–185,235–301] |

---

## 2. MISCELLANEOUS INPUTS — unit `47`

### Specification

Nine independent one-bit input channels, each with a connector and ON/OFF toggle. An enabled standard TX-2 input transition sets that channel’s buffer bit and raises FLAG `47`. TSD reads and clears the buffer. Two independent filtered Schmitt-trigger circuits and a separate movable three-button pulse generator are provided. [H63:3630–3636; H61:3550–3563; H63 PDF p.97, [inspected scan](https://archive.org/download/tx-2-users-handbook-nov-63/page/n96.jpg)]

| IOS | Meaning |
|---|---|
| `IOS_47 30000` | Permit input pulses to raise FLAG `47`; does nothing else |
| `IOS_47 20000` | Generic disconnect |

No per-channel programmable IOS mode bits are defined. Channel enables are manual. [H61:3557–3563]

**Data format:** Nine-bit buffer in quarter 1, mask `777`. TSD permits permutation; quarter 1 must be active. Other quarters’ activity is irrelevant. No sign extension. TSD clears the input buffer. [H61:3565–3571]

**[INFERENCE]** The described set-bit/clear-buffer circuit accumulates simultaneous/different-channel events as a bitmap; repeated pulses on an already-set channel coalesce rather than form an event count. The section does not state a count-overrun alarm or a MISIND/EIA connection for this unit.

### Electrical timing and manual controls

- Standard input transition: `−3 V → ground`, rise time `<0.2 μs`.
- Schmitt trigger input: smooth `ground → −3 V`; approximately 5 V RMS sine wave or opening switch contact can drive it.
- Use filters for switch contacts/noisy sources.
- Printed thresholds: about `−0.9 V` going down and `−2.2 V` going up; rise/fall about `0.15 μs`.
- Schmitt outputs must be patched to the desired channels; they are independent of the nine-channel circuit.
- Nine enables, filter switches, connector panel, movable three-channel pushbutton generator. [H63 PDF p.97; H61:3573–3603]

No numerical maximum event rate, fixed polling interval, or start/stop delay is specified in this section.

### Sketchpad

`47START` runs in sequence `47`; `47FIXL` computes status-light data; `47LITE1` writes output unit `75`; `47EIR` computes newly set switch bits into `47BUT`; `47BOTH` queues them through `47TABLE`. [SK1:792–879, PDF pp.23–24]

The displayed `47TSD` label contains `JPD #` in this transcription. Thus the listing establishes sequence/event processing, but this excerpt should not be cited as an actual unit-47 TSD instruction. [SK1:855–872]

### Initial implementation snapshot

Unit `47` is advertised as present/input, but never appears in `external_ready`; its `external_data` falls through to zero. There is no nine-bit latch, channel-enable state, pulse injection, or clear-on-TSD behavior. The blanket `W36` input mask is also inappropriate. [host/tx2_host.h:141–149]

---

## 3. MISCELLANEOUS OUTPUTS — unit `75`

### IOS and data format

Nine computer-controlled relay contacts with G.R. terminals. Channel 9 additionally has high-speed output `MOM-9`. [H63:4957–4960]

`IOS_75 30xxx` sets the output state from the instruction’s **rightmost nine bits**, quarter 1:

| IOS | Effect |
|---|---|
| `30000` | Clear all nine outputs |
| `30777` | Set all nine outputs |
| `30xxx` | Load the nine-bit pattern `xxx` |

These are an **output pattern**, not independent start/stop or assembly-mode bits. [H63:4967–4972]

There is **no raise-flag indication**. Relay change may be assumed complete after **2 ms**. High-speed `MOM-9` changes before IOS finishes. Bit `1.9` changing `1→0` produces `−3 V→ground`; `0→1` produces the inverse; rise/fall `<0.2 μs`. [H63:4982–4989]

**TSD special case:** TSD does not operate the outputs and **does not cycle the memory word**. It still dismisses without hold and changes E as a CLDE operation would. [H63:4960–4963,3314–3316]

### Relay and shift controls

| Property/control | Specification |
|---|---|
| Relay | C. P. Clare HGS-1009, make-before-break |
| Noninductive load | Up to ¼ amp |
| Reactive load | Up to 1 amp with suppressor only |
| Relay cycle rate | Approximately 500 cycles/s, 2 ms period |
| Shift position 1 | Ring shift left |
| Shift position 2 | Open-ended shift left, all nine bits; `1.9` is not a sign bit |
| Shift position 3 | No shift |
| Sine shift input | 15 V RMS; one shift/cycle |
| Pulse shift input | Standard TX-2 `−3 V→ground` transition; one shift/pulse |
| High-speed shift maximum | 500 kHz |
| Relay-output shift maximum | 500 Hz |
| Input selector | Up SINE, down PULSE |
| Test pushbutton | Load from manual toggle reset register |
| Other | Toggle reset register, maintenance switch, relay terminals, `MOM-9` jack |

[H63:4990–5042]

Do not feed `MOM-9` back as the shift trigger: the handbook warns it may fail to change bits `1.9` or `1.1`. Shift/pushbutton inputs are not interlocked with program writes and can interfere; unit `47` can synchronize the program with external shift inputs. [H63:5033–5042]

No EIA/MISIND assignment is given for `75`. The explicitly absent flag response is part of its interface. [H63:4982–4985; H61:3450–3462]

### Sketchpad

`47LITE1` executes reported `IOS_75 30777`; preceding `hLDE PAGE1` and superscript-3 `STE 47LITE1` modify that instruction. **[INFERENCE]** This uses the IOS low nine bits as status-light outputs. [SK1:849–854, PDF p.24]

### Initial implementation snapshot

The initial host advertised `75` and recorded external IOS events without retaining relay state, modeling contact delay or `MOM-9`, or exposing shift/manual controls. Source: `host/tx2_host.h:141–145,171–175`.

The core now follows unit 75's special TSD rule: read the operand into E, preserve memory without writeback/rotation, and dismiss when unheld. `tb_machine` covers this behavior. Source: H63:3315–3316,4961–4964.

---

## 4. RANDOM NUMBER GENERATOR — unit `61`

### Specification

A radioactive cesium source assembles a **nine-bit number**. Average generation time **57.6 μs**; minimum **28.8 μs**. [H63:4618–4625]

| Operation | Effect |
|---|---|
| `IOS_61 30000` | Select/connect and trigger generation |
| Generation complete | Raise FLAG `61` |
| TSD | Copy generated nine-bit number to quarter 1 and trigger the next generation |
| Next generation complete | Raise FLAG `61` again |

Permutation is allowed; quarter 1 must be active. Normal nine-bit input mask is `777`; no assembly mode is defined. [H63:4626–4638]

The 1959 quarterly report describes alternating samples of detected radioactive pulses, accepting only differing successive flip-flop states to remove long-term bias; it gives an earlier approximate 50 μs/nine-bit figure. Use the handbook’s later 57.6/28.8 μs specification for 1961–63 timing. [`references/text/mit-lin-div-5-qpr-59-06.txt`:579–585; H63:4624–4625]

### Manual controls and alarms

ON/OFF pushbuttons; **60-second warm-up**. Leave OFF when unused. Maintenance meters should read about half scale; maintenance switch is inside the box above the panel. No RNG MISIND/EIA bit appears in unit `41`’s allocation table. [H63:4640–4647; H61:3450–3462]

The supplied section does not specify a full latency distribution, an upper-bound generation time, or exact zero/one statistical test requirements. A chosen stochastic timing law would be **[INFERENCE]**.

### Sketchpad

- `SQ60IRR`: `IOS_61 30000`, superscript-3 TSD into `SCRAMX`, then masks the result to select a random decrease. [SK2:5418–5437, PDF pp.126–127]
- `SCRAMBLE`: switches to sequence `61`, connects, and uses TSD to modify the immediate operand at `SCRAMX`; the surrounding code exchanges display-file entries. [SK2:5490–5512, PDF p.128]
- Unit initialization installs `SCRAMBLE` in index register `61`. [SK2:5367–5373]

### Initial implementation snapshot

Host declares RNG always ready and forms data as:

```cpp
((uint64_t(random) << 4) | (random & 15)) & W36
```

The underlying LFSR advances every board clock. `external_mask` is `W36`. [host/tx2_host.h:144–149,190]

Missing: nine-bit-only format/mask, a latched number stable until TSD, connect/TSD triggers, generation busy time, completion flag timing, and manual power/warm-up. The present output is deterministic PRNG state spread across 36 bits, rather than the specified nine-bit transfer.

---

## 5. TRAPPING — unit `42`

### Complete documented programmable mode bits

Mode masks are the low twelve-bit mode word supplied in `IOS_42 3xxxx`. Combinations are permitted; `30007` traps on all three metabit encounter classes. [H63:3505–3514; H61:3491–3502]

| Mode mask | Complete IOS | Meaning and flag timing |
|---|---|---|
| `0001` | `30001` | Marked instruction: raise FLAG `42` before end of marked instruction |
| `0002` | `30002` | Marked deferred address: raise before end of instruction using that address |
| `0004` | `30004` | Marked operand: raise after one to several instructions, depending on overlap |
| `0010` | `30010` | Marked new placekeeper: raise during change-sequence cycle if its bit `2.9=1` |
| `0100` | `30100` | Set metabits of performed instructions |
| `0200` | `30200` | Set metabits of used deferred addresses |
| `0400` | `30400` | Set metabits of used operands |

`IOS_42 20000` or `30000` clears mode selection. Setting modes require the console **SET METABITS** pushbutton ON, and these setting modes do not themselves raise FLAG `42`. [H61:3503–3541]

For change-sequence trapping, E quarter 3 receives the **new** sequence number and quarter 4 the **old** sequence number. There is no change-sequence trap when leaving sequence `42`. [H61:3521–3529]

**TSD:** No external data transfer; retains ordinary cycle-left and dismiss behavior. There is no character/data table or assembly mode. [H63:3509–3513]

### Manual Sync-to-Trap mode

Requirements:

1. SYNC 1 and SYNC 2 pushbuttons OFF.
2. SYNC TO TRAP ON.
3. GATE 1 TO SYNC JACKS ON.

While Sync-to-Trap is on, other trapping modes are ineffective; metabit-setting modes continue working. Turning it off restores the original trapping mode. [H63:3590–3604; H61:3543–3552]

No device MISIND/EIA allocation or mechanical timing is given for `42`; timing is defined by the CPU cycles and overlap descriptions above.

### Sketchpad

No direct unit-42 IOS/TSD use was located in the two transcriptions after numeric/subscript searches and alternate searches for trap/metabit terminology. `TRAPRED` in SK2 is a program label within display processing, not evidence of a hardware unit-42 operation. [SK2:4082–4085]

### Current implementation

- `tx2_io.v` stores mode and gates its export by connection. [rtl/tx2_io.v:55,80,208–217]
- Core implements the three trap-on-read bits and three set-metabit classes, with `trap_set_enable` for setting. [rtl/tx2_core.v:295–297,471–473]
- Change-sequence trap checks new X-register bit 17, excludes old sequence `42`, and preserves the first sequence-change E report through `trap_sequence_pending`. [rtl/tx2_core.v:700–708]
- The host provides `set synctotrap 0|1`, `set sync1 0|1`, `set sync2 0|1`, `set gate1 0|1`, and `press sync`. When the manual's switch prerequisites hold, manual Sync-to-Trap masks all four programmed traps and retains the three metabit-setting modes. Source: H63:3590–3604.
- Unit `42` takes the software TSD rotation path. [rtl/tx2_io.v:77–80; rtl/tx2_core.v:195,643–649]

`set setmetabits 0|1` controls the independent SET METABITS switch. The serial core reports operand-metabit traps at actual operand reads. Variable delays from the original overlapped pipeline remain unmodeled. `tb_machine` covers the three ordinary traps, metabit setting, sequence changes, and manual override. `tools/test_dev_rtlio.py` covers host switches and synchronization pulses.

---

## 6. IN-OUT ALARMS — unit `41`

### IOS and flag behavior

`IOS_41 30000` connects the alarm circuitry and programmatically suppresses the central **MISAL stop**. An EIA or MISIND from the listed connected devices raises FLAG `41`. [H63:3430–3441]

Unit `41` has no status flip-flop; its buffer-free level remains available while connected. [TM2:13898–13910]

The alarm flag is generated on the alarm aggregate becoming active. If a further alarm occurs before the first is cleared, its report bit becomes set but **FLAG `41` is not raised again**. TSD can reread the aggregate. [H63:3489–3495; TM2:13912–13924]

### Complete nine-bit TSD alarm table

TSD copies this bitmap into the rightmost nine bits; it does **not clear alarms**. Read before disconnecting a source, because disconnected units cannot report. [H61:3435–3478]

| Bit | Mask | Source |
|---|---|---|
| `1.1` | `001` | MISIND/MISAL, DATRAC `50` |
| `1.2` | `002` | MISIND/MISAL, PETR `52` |
| `1.3` | `004` | MISIND/MISAL, TX-2 magnetic tape `46` |
| `1.4` | `010` | EIA, magnetic tape `46` |
| `1.5` | `020` | EIA, camera/display `60` |
| `1.6` | `040` | EIA, punch `63` |
| `1.7` | `100` | EIA, Xerox `51` |
| `1.8` | `200` | EIA, Writer pair `65`/`66` |
| `1.9` | `400` | EIA, Writer pair `71`/`72` |

No assembly mode is specified. Normal permutation/activity rules apply. [H63:3290–3295; H61:3435–3462]

### Clearing, stop suppression, and manual effects

The handbook directs disconnecting the offending device with `IOS 20000` to clear its alarm; TSD is observational. Reconnecting raises flags for output units `60`, `63`, `51`, but not input units `50`, `52`; tape `46` is a special case. [H63:3444–3448,3489–3495]

An unsuppressed MISAL stops the CPU. Manual and programmed suppression are independent: **both must be off** for MISAL to stop. Programmed suppression does not illuminate the yellow suppression light; the red alarm light and gong still work. EIA does not itself stop the computer, though it may sound a buzzer or stop its device. [H63:3483–3488]

No character rate or mechanical start/stop timing applies to this alarm controller. Its timing is the synchronized alarm transition described by the technical manual. [TM2:13912–13924]

### Sketchpad

- Tape search connects `41` before operations. [SK1:4489–4495, PDF p.101]
- `TAFIOASTARTβ` obtains the tape IOS report, checks the tape MISAL report bit, and attempts tape error clearing. [SK1:4450–4456]
- Error/exit paths disconnect `41`; one also explicitly lowers its flag. [SK1:4401–4402,4442–4445,4770–4773,4851–4854]

These routines obtain detailed tape error information using unit `46` IOS reports; the cited excerpts do not demonstrate a unit-41 TSD bitmap read.

### Current implementation

RTL has:

- Nine-bit alarm report with exactly the listed allocations.
- Missed/inability latches accumulated for connected devices.
- Alarm clear on source disconnect.
- Alarm-edge flag behavior.
- Unit-41 TSD input with mask `777`.
- Programmed MISAL suppression while `41` is connected.

[rtl/tx2_io.v:80–82,91–94,124–128,143–153,178–181,205–208]

Core separately latches central MISAL and applies manual/programmed suppression to stopping. [rtl/tx2_core.v:466]

The initial host lacked simulation of the assigned devices' inability/missed-data events and physical indications. Its clock/command handlers provided no device-specific alarm injection or controls. Source: `host/tx2_host.h:121–185,235–301`. Subsequent device implementations are recorded below and in the other specifications.

---

## 7. INTERVAL TIMER — unit `54`

### IOS modes

The timer is an 18-bit interval counter. Its end-carry pulse train may raise FLAG `54` and/or trigger an external device. Clock source, interval, start, and stop are partly manual. [H63:4317–4328]

| Mode mask | IOS | Effect |
|---|---|---|
| `0000` | `30000` | Stop counter; while stopped, repeatedly reset count from buffer at the selected counting rate |
| `0100` | `30100` | Start counter; end-carry pulse train available at EC OUTPUT, without enabling flag pulses |
| `0200` | `30200` | Enable end-carry pulses to raise FLAG `54`; used with manual/external start |
| `0300` | `30300` | Start counter and enable end-carry-to-flag |
| — | `20000` | Disconnect flag signals; **does not stop timer** |

First end-carry/flag occurs after one complete programmed interval. Mode instructions connect if not already connected; manual controls override program controls. [H63:4330–4375,4389–4390; H61:3909–3957]

### TSD data and critical OCR correction

TSD loads an **18-bit positive integer** from the memory operand into the timer buffer, specifying counts per interval. Buffer occupies quarters 1–2; normal mask `777777`. Permutation and activity are permitted. **Inactive buffer portions are filled with `+0`.** [H63 PDF p.108, [inspected scan](https://archive.org/download/tx-2-users-handbook-nov-63/page/n107.jpg)]

**OCR correction:** H63:4395–4398 renders the final sentence as “set to 1.” The inspected scan prints “set to +0.” The timer implementation below follows the scan.

The provided section does not define the interpretation of a programmed count of zero; do not silently assign a special “maximum interval” meaning as established fact.

### Buffer busy timing and interval changes

- At 10 kHz, 100 kHz, and external oscillator settings, the buffer is busy during end-carry time, equivalent to a basic counting interval.
- At 1 MHz, the buffer is busy during the **last 16 counts**.
- If reset value is below 16 at 1 MHz, stop the counter before changing the buffer.
- Buffer changes take effect at the end of the current interval unless the counter is stopped. [H63:4367–4375]

Thus “timer running” and “buffer available for TSD” are independent pieces of state.

### Manual controls and electrical timing

| Control | Meaning |
|---|---|
| Oscillator selector | 1 MHz, 100 kHz, 10 kHz, external |
| Toggle register | Manual interval |
| START pushbutton | Load buffer from toggle register and start counter |
| STOP pushbutton | Stop counter; count repeatedly resets from buffer |
| Maintenance switch | Maintenance |
| External oscillator input | 20 V, 0.1 μs pulses, e.g. Burroughs 1002 AW |
| External trigger switch/jack | Start from standard TX-2 input transition |
| EC/output jack | Standard TX-2 output pulses |

Standard input transition: `−3 V→ground` in `<0.2 μs`. Standard output pulse: approximately `0.4 μs`, rise/fall `<0.2 μs`. [H63:4400–4423; H63 PDF p.108]

**[INFERENCE]** For positive count N and oscillator frequency f, nominal pulse spacing is `N/f`, following the handbook’s “every nth pulse” definition. No timer MISIND/EIA assignment is given in unit `41`’s table. [H63:4323–4327; H61:3450–3462]

### Sketchpad

`SQ45DELAY`:

1. Changes to timer sequence.
2. Stops with `IOS_54 30000`.
3. Loads `45DELAYK` with held TSD.
4. Starts/enables flag using dismissing `IOS_54 30300`.
5. Resumes at `IOS_54 30000` and returns to tape sequence.

[SK1:4004–4015, PDF p.92]

IBM-tape routines repeatedly use stop/load/start sequences and `30300` between operations; examples are `45COMMON`, `45TSD`, `45RESETIT`, `45IT1`–`45IT3`. [SK1:5751–5781,5982–6007]

### Implemented timer and device bus

| Item | Implementation and source |
|---|---|
| IOS/counting | `30000/30100/30200/30300`, a complete first interval, periodic reload, and independent flag enable. `20000` disconnects the flag while counting continues. Source: H63:4330–4390. |
| Buffer busy | Busy during the final 16 counts at 1 MHz, or the final basic counting interval at 10/100 kHz and external clock. Loading is permitted while stopped. Buffer changes take effect on reload at the current interval's end. Source: H63:4367–4375. |
| Normal TSD | 18-bit positive integer with normal permutation/activity. Inactive portions receive **+0**, correcting OCR “1” against the scan on PDF p. 108. |
| Manual controls | `dev timer rate 1000000|100000|10000|0`, with 0 selecting external oscillator; `toggles N`; `start` to load switches and run; `stop`; `external 0|1` to enable external triggers; `trigger`; `pulse`; `maintenance 0|1`. Manual pulses override simultaneous program control. Source: H63:4375,4400–4423. |
| EC output | RTL `timer_end_carry` passes every registered EC pulse to each device's `Device::timer_pulse(now)` without additional microsecond gating. DATRAC and plotter can connect to it. Source: H63:4323–4327. |

Positive count N produces period N/f. Zero-count semantics are undocumented; the code labels natural 18-bit wraparound as **[INFERENCE]**. Voltages and analog pulse edges are outside this digital event interface.

The common device bus maps the low twelve `special()` bits into IOS report 3.7–4.9, `maintenance()` into 2.7, and `clear_alarms()` into unit MISIND/EIA clearing. It supports six/nine-bit assembly widths. Bits 3.7–4.9 span twelve positions; an early description called this fifteen bits, whose extra three high bits have no place in the 36-bit report. `IOS 6xxxx` only selects, preserving connection and mode. Classes `0/2/3/4/5/6` follow the H63 IOS table. Source: H63:3212–3277.

While the CPU is stopped, built-in transports, counters, cameras, and mechanical operations declared by `Device::active()` continue receiving board clocks. Acceptance targets: `tb_io`, `tb_machine`, and `tools/test_dev_rtlio.py`.

---

## Architecture and implementation conclusions

The CPU already performs generic normal-TSD permutation/activity and has a separate input mask, while `tx2_io.v` provides per-unit connection/mode/report/flag handling. The host supplies generic peripheral readiness, direction, masks, and data. Device-specific implementations should therefore provide the correct **buffer widths, stable data, ready transitions, mode effects, and alarm events** through that interface. [rtl/tx2_core.v:404–410,430–433,686–692; rtl/tx2_io.v:97–136; host/tx2_host.h:138–149]

Highest-priority corrections established by primary sources:

1. **Timer inactive fields receive `+0`.**
2. **Writer code names: `72` DOWN, `73` UP.**
3. **TSD unit `75`: preserve memory word; no rotation.**
4. **Narrow input masks:** Writer `77`; RNG and miscellaneous input `777`.
5. **Writer output ready/flag at mechanical completion.**
6. **Shared keyboard/output case state and CR synchronization.**
7. **Real unit-47 set-bit/clear-on-read latch and unit-75 retained relay outputs.**
8. **Timed, buffered nine-bit RNG.**
9. **Second Writer, local reader/punch/manual routing.**
10. **Nonprinting Writer codes remain invisible; backspace/dead-character and independent platen motion require position-aware rendering.**

Remaining primary-source limitations are explicit above: precise Writer EIA causes, operation-specific carriage/tab/script timing, zero-count timer semantics, and the dated Writer/PETR end-mark discrepancy. These are specification gaps rather than grounds for fabricated behavior.

## Replica implementation and operation, 2026-11

`host/devices/writer_keys.h` implements both Writer pairs, 65/66 and 71/72. `web/writer.js` displays two independent paper surfaces. CPU input updates only six bits. `dev lw65 key N...` and `dev lw71 key N...` represent the physical keyboard's internal seventh case line. A required case change delivers 74/75 first and the character second, releasing the key after both TSDs. `keys N...` accepts already encoded six-bit line input for existing diagnostics and Sketchpad tests. Input and output share case memory; CPU carriage return resets case and script position. Sources: H63:4767–4769,4880–4904; LW:550–574,600–629.

Manual routing uses `dev lw66 route TYPE PUNCH` for output, likewise for 72, and `dev lw65 route COMPUTER TYPE PUNCH` for input, likewise for 71. Each argument is 0/1. Interlocks reject two sources driving one destination. `us N` sets character mechanical time, default 100000 μs; `punch_us N` sets local punch time, default 50000 μs. When both destinations are selected, completion waits for the slower one. Output buffers remain busy until physical completion. Sources: H63:4920–4935; LW:578–580,660–718. Separate CR/tab/script mechanical delays are undocumented; using one character time is `[INFERENCE]`.

Soroban control uses `dev lw65 tape HEX` to install raw `.tape` bytes. `start`, `stop`, and `holdstop 0|1` provide continuous and held-STOP single-line operation. `rate 95|190` selects 9.5/19 lines/s. The four `filters STOP DELETE NO7 BLANK` bits select green at 1 and red at 0. The reader samples the station, advances, and then waits for acceptance. Red-mode lines without a seventh hole only reproduce to the punch. `rewind 1` indicates the operator's no-tape contact is closed; rewind is blocked while reading. `dev lw66 feed 1|0` presses/releases blank-tape feed; `endmark` punches the end mark. Event `dev.lw66` or `dev.lw72` reports completed typewriter codes in `codes` and punched bytes in `punch`. END MARK uses the later PETR `73` without a seventh hole; source comments preserve the 1959 Writer `72` discrepancy. Sources: LW:669–677,716–744,783–845; H63:4897–4907.

Character decoding labels 72/73 LINE FEED DOWN/UP, preserves script selection, and uses independent printing coordinates for backspace/dead-character overstrikes. Codes 14–17, 71, 76, and 77 print nothing. Fonts, vertical spacing, and default eight-character tab stops are display approximations labeled `[INFERENCE]`. Sources: H63 Table 7-6 and PDF p. 121; LW:444–452,633–655.

The console exposes nine unit-47 input enables and pulse controls, unit-75 relay lamps and MOM-9, a reset register and TEST, and ring/open-ended left shifts. `dev misc47 enable MASK` and `pulse MASK` latch input bits; TSD clears them. `dev misc75 shiftmode 1|2|3`, `shift`, `resetreg MASK`, and `test` expose physical controls. IOS changes the unit-75 register immediately; relay lamps change after 2 ms with no device flag. Sources: H61:3550–3571; H63:4957–5042. Coalescing repeated pulses on one set bit is `[INFERENCE]`.

Random source 61 has a stable nine-bit buffer. IOS/TSD triggers the next generation, with input unavailable until completion. Fixed 57.6 μs latency and seedable xorshift are reproducible substitutes labeled `[INFERENCE]`; radioactive-source statistics remain unmodeled. `dev rng seed N` selects a deterministic seed, and `power 0|1` controls panel power with 60-second warm-up after restart. Assuming an already warmed source at machine startup is `[INFERENCE]`. Source: H63:4618–4647.

Acceptance script: `TX2_CLI=build/obj_cli/tx2-cli python3 tools/test_dev_writers.py`. Assembled IOS/TSD instructions check both keyboard/output pairs, reader filters, input masks, flags while busy, relay delays, and random buffering. HELLO and original Sketchpad KEYSTART/TSD filling KEYTAB exercise the same device paths.

Remaining source gaps include physical Writer EIA causes and clearing circuitry, operation-specific mechanical delays, paper tab-stop positions, and full RNG latency/statistical distributions. Writer MISIND/EIA generation remains limited to documented sources.