PETR is a free-running, forward-read-only device. Its bin operation searches backward for `73` without a seventh hole and then reverses. PUNCH has four hardware modes; leader and END MARK are software-generated patterns. Sketchpad supports direct plotting on unit `74` and punched-tape plotting through unit `63`, using an EAI pen-and-ink plotter.

---

# Paper-tape devices and Sketchpad plotter specification

## Sources and notation

Code paths are relative to the repository root.

Abbreviations:

- **H63:** `references/text/TX-2_UsersHandbook_Nov63.archive-page-ocr.txt`.
- **H61:** `references/text/TX2-Users-Handbook_196107.txt`.
- **TM2:** `references/text/LM-44v2_TX-2_Technical_Manual_Volume_2_196106.txt`.
- **SK2:** `upstream/Sketchpad/sk2.tx2as`.
- **TR296:** `references/text/Sketchpad_TR296_Jan63.txt`.

All unit numbers, commands, bit masks, and tape codes are **octal**, except numbers explicitly marked decimal. A handbook bit `q.b` has zero-based integer position `9(q−1)+(b−1)`.

Source interpretation matters:

1. The existing image `references/figures/petr-modes.png` clearly preserves the reader command table that is lost from the OCR. It confirms every reader command below.
2. The handbook’s introductory note explicitly says its plotter section `74` is “to come later”; the local handbook therefore does not provide a complete plotter hardware specification. [H63:18–23]
3. The Technical Manual chapter contents incorrectly lists an X–Y plotter as `72`, whereas Volume 1 and actual Sketchpad code identify the plotter as `74`. Use `74` for this replica. [TM2:12288–12292; `references/text/LM-44v1_TX-2_Technical_Manual_Volume_1_196105.txt:1874–1876`; SK2:6579–6580,6665–6686]
4. The 1959 Lincoln Writer report says its END MARK is `72`; the reader handbook and reader hardware description both say `73`. Preserve this discrepancy in documentation; the PETR implementation should follow its own handbook/hardware specification. [`references/text/ad-0235247.txt:789–795`; H63:4020–4032; TM2:14026–14034]

## Common IOS, status, and sequence behavior

`IOS_j 3mmmm` connects unit `j` and sets its twelve-bit mode word to `mmmm`. `IOS_j 20000` disconnects. `40000` lowers the flag; `50000` raises it. A newly connected **output** unit raises its flag; changing the mode of an already connected output unit does not itself have this initial-connect effect. A slow mode change can hold the buffer busy and raise the flag when complete. [H63:3213–3229]

A reporting IOS copies state **before** performing its remaining operation:

| Report bits | Meaning |
|---|---|
| `1.1–2.3` | Mode flip-flops, generally matching the IOS mode word |
| `2.4` | Missed-data indicator |
| `2.5` | Equipment inability |
| `2.6` | Connected |
| `2.7` | Maintenance |
| `2.8` | Buffer available: `1` available, `0` busy |
| `2.9` | Flag |
| `3.1–3.6` | Reporting sequence/unit number |
| `3.7–4.9` | Special indicators, zero when unused |

[H63:3261–3280]

TSD uses the **current sequence**, not the IOS unit selection. Input TSD consumes a device buffer; output TSD fills one. Normal TSD supports permutation/activity, ignores subword form, and performs no sign extension. Inactive output portions are zero. A busy/disconnected device causes dismiss-and-wait without advancing P, even for held TSD; a completed unheld TSD dismisses normally. [H63:3285–3309]

The device raises its sequence flag when the next input datum is ready or when the output transfer finishes and another can be accepted. [H63:3179–3197]

---

# 1. PETR — unit `52`

## 1.1 Physical device and transport

PETR is a seven-channel photoelectric reader with a separate feed/sprocket hole. Six channels carry data; the seventh channel and feed hole are control signals. Its quoted operating range is **400–2500 lines/second**, with reel speed depending on reel size. It cannot stop between adjacent lines and takes approximately **100 lines**, roughly one foot of tape, to stop. [H63:4008–4014; `references/figures/petr-modes.png`]

Two physical directions exist:

- **Binward/reverse:** tape is moved into the bin; sensed characters are not loaded into the computer buffer.
- **Reelward/forward:** tape can be read into the computer.

These are transport directions, not two data-order modes. **PETR does not read data backward.** [TM2:13993–14003,14024–14034]

Transport selection:

| Manual selection | Forward transport |
|---|---|
| Reel | Reeler drive; manual-control description quotes up to **2000 lines/second** |
| Strip | Internal capstan; approximately **400 lines/second** |

The manual also quotes approximately 400 lines/second for binward motion. The 2000 maximum on the controls page and 2500 maximum in the general description should be retained as differing source figures. [H61:3857–3879; H63:4279–4299]

The mechanical drive has a reversing motor, separate capstan/reel clutches and brakes, and transient delays for braking and direction changes. In reel mode, forward motion is driven by the reel while capstan-brake slippage supplies drag; binward motion uses both capstan and reel. [TM2:14005–14022,14049–14120]

## 1.2 Exact IOS command table

| IOS command | Mode word | Operation |
|---|---:|---|
| `IOS_52 30000` | `0000` | Stop tape and connect |
| `IOS_52 30002` | `0002` | Equivalent stop-tape operation |
| `IOS_52 30004` | `0004` | Equivalent stop-tape operation |
| `IOS_52 30006` | `0006` | Equivalent stop-tape operation |
| `IOS_52 30100` | `0100` | Read normal, reelward |
| `IOS_52 30104` | `0104` | Load bin until END MARK, then read normal reelward |
| `IOS_52 30102` | `0102` | Read assembly/splayed, reelward |
| `IOS_52 30106` | `0106` | Load bin until END MARK, then read assembly reelward |

[Primary table image: `references/figures/petr-modes.png`; matching prose H63:4015–4033]

Decoded bits:

| Mode mask | Handbook bit | Meaning |
|---:|---|---|
| `0002` | `1.2` | `0` normal, `1` assembly |
| `0004` | `1.3` | Initial binward operation/search rather than direct reelward reading |
| `0100` | `1.7` | Start transport; zero requests stop |

The bit interpretation follows the exact command table. **[INFERENCE]** The commanded mode word and instantaneous transport state must be separate: after a `0104`/`0106` search reaches END MARK, the physical direction changes without another IOS.

## 1.3 Seventh hole, feed hole, and END MARK

**Primary-source discrepancy:** TM2 PDF p. 403, printed 15-PETR-2, says “seventh hole is present,” but the same sentence gives `Hf·REV⁰`. The forward synchronization gate in Fig. 15-PETR-2 on PDF p. 406 receives only `Hf` and `REV⁰`; `H7` enters only the END MARK decoder. The implementation follows the inspected circuit diagram: forward motion with a feed hole loads six-bit data, and the seventh hole distinguishes END MARK. This preserves original binary bootstrap tape loading. Sources: TM2:14043–14047; visually checked PDF pp. 403/406, Fig. 15-PETR-2.

| Tape condition | PETR action |
|---|---|
| Forward, feed hole, seventh hole | Load six-bit buffer; raise FLAG `52` when connected |
| Forward, feed hole, no seventh hole | Load six-bit buffer; raise FLAG `52` when connected, following Fig. 15-PETR-2 |
| Binward, ordinary line | Sense transport/control information; no input datum |
| Binward, feed transition at data `73`, no seventh hole | END MARK action |
| Data `73` **with** seventh hole | Ordinary readable six-bit data, not END MARK |

[TM2:14026–14047]

For a connected automatic bin-and-read operation, END MARK clears the reverse flip-flop and the transport reverses into forward reading. If logically disconnected, the same END MARK clears the clutch and stops the tape. The END MARK transition itself is asynchronous, unlike ordinary synchronized input-buffer loading. [TM2:14026–14034]

Do not implement END MARK as generic file EOF or unconditional stop-on-`73`: direction, seventh hole, connection, and feed transition matter.

## 1.4 TSD data format

### Normal mode

The six input bits occupy the logical low six positions, bits `1.1–1.6`. Only corresponding active/permuted memory bits change; the rest of the destination is preserved. [H63:4036–4041; `references/figures/petr-modes.png`; common permutation rules H63:3295–3299]

### Assembly mode

Configuration is ignored. On **each** TSD:

1. Rotate the entire destination word left one place.
2. Insert the six buffer bits into `1.1, 1.7, 2.4, 3.1, 3.7, 4.4`.

Six TSDs assemble one 36-bit word. [H63:4048–4057; `references/figures/petr-modes.png`]

Equivalent zero-based mapping:

| Six-bit datum bit | Destination position after rotation |
|---:|---:|
| 0 | 0 = `1.1` |
| 1 | 6 = `1.7` |
| 2 | 12 = `2.4` |
| 3 | 18 = `3.1` |
| 4 | 24 = `3.7` |
| 5 | 30 = `4.4` |

**[INFERENCE]** This integer representation follows directly from the handbook’s bit coordinates.

Assembly does not mean the reader internally waits for six lines. The hardware still has a six-bit buffer, and software issues six separate TSDs.

## 1.5 Ready, flags, overrun, alarms

The reader is **free-running**, rather than a ready/valid producer that waits for the CPU:

- An accepted physical input line loads the buffer, sets status, and raises FLAG `52`.
- TSD transfers the buffer and clears status.
- If another line arrives while status remains set, the old datum is overwritten and lost; MISIND is set.
- MISIND is inhibited while STOP UNIT is asserted, preventing braking-time arrivals after another unit stops the machine from falsely identifying PETR as the original alarm source.
- MISIND clears on the connection transition or the reader preset signal.

[TM2:14123–14153]

PETR is a listed MISAL source for the alarm sequence; it is not listed as an equipment-inability source on the handbook alarm inventory. Unsuppressed MISAL stops the computer; connected alarm unit `41` can instead raise FLAG `41`. [H63:3435–3485]

**Specification boundary:** do not invent a PETR-specific EOF inability alarm. The primary text read here specifies missed-data detection, not an EOF alarm.

Maintenance is a common IOSAL condition: an IOS directed at a unit on maintenance can alarm. [TM2:13156–13162]

## 1.6 Manual controls

| Control | Effect |
|---|---|
| Reel/Strip toggle | Selects forward drive for both manual and computer operation |
| Wind pushbutton | Starts reelward transport, countermanding computer operation; no computer reading |
| Bin pushbutton | Starts binward capstan transport, about 400 lines/second; stops on `73` without seventh hole, with mark on bin side of reading point; no computer reading |
| Maintenance switch | Present on reader panel |

The handbook states that the manual control pushbuttons disconnect PETR, equivalent to `IOS_52 20000`. [H63:4064–4075,4279–4299; H61:3844–3880]

The OCR available here does not preserve every photographed panel label; no additional button behavior is asserted.

## 1.7 Software evidence

The handbook’s M4 `READ` operation switches its input from the Lincoln Writer keyboard to PETR using `IOS_52 30104`. Reading stop code `76` returns input to the keyboard. This `76` stop is **software behavior**, distinct from the hardware bin-search END MARK `73` without seventh hole. [H63:8138–8141]

The upstream simulator notes a conflicting 1959 Lincoln Writer END MARK `72`, but its notes are secondary to PETR’s own primary specifications. Its transport implementation also deliberately simplifies speed and acceleration. [`upstream/TX-2-simulator/cpu/src/io/dev_petr.rs:1–24,74–94`]

## 1.8 Implemented PETR behavior and operation

`rtl/tx2_io.v` retains the six-bit buffer, normal/six-way splayed assembly, connection/mode/flag state, and MISIND. `host/tx2_host.h` implements independently timed forward/reverse physical transport. New data overwrite a full buffer and set MISIND. STOP UNIT suppresses secondary MISIND. Disconnect/reconnect clears the indicator according to the manual. Source: TM2 15-PETR-1 through 15-PETR-3.

- All eight IOS modes work. Reverse motion searches line by line for `73` without a seventh hole. Automatic search reverses to forward reading at the mark; manual BIN stops there. `73` with a seventh hole remains ordinary data. Physical positions without feed holes also consume transport time. Sources: H63 PDF p. 105; Fig. 15-PETR-2.
- AUTO timing defaults to 2000 lines/s for reels, or 500 μs/line, and 400 lines/s for strip/reverse, or 2500 μs/line. `dev petr strip 0|1` selects transport; `dev petr speed N` selects reel speed. `set reader_us N` overrides the line period, with 0 restoring AUTO. Tests use 64 μs/line. Scanning every integer period from 32–64 μs found 43 μs/line as the shortest working original HELLO boot period on this serial CPU. Sources: H63 PDF pp. 105–106; H61 PETR controls page.
- `dev petr wind|bin|stop`, `dev petr maintenance 0|1`, and `dev petr position N` expose transport and loading controls. WIND/BIN disconnect logically. Transport continues while the CPU is stopped, and stopping takes approximately another 100 lines. Source: H63 PDF pp. 105–106.
- A `.tape` file represents media cut after the loading-end END MARK. The loading boundary represents that preceding mark as `[INFERENCE]`. File EOF produces neither END MARK nor EIA. Exact acceleration and reversal parameters are undocumented; the model has no assumed variable-speed curve.

Acceptance targets are `tb_io` for overwrite, STOP UNIT, IOS, flags, and alarms; `tb_boot` for original-plugboard HELLO; `tb_graphics`; and `tools/test_dev_rtlio.py` for normal/assembly input, reverse search, seventh-hole handling, 100-line stopping, manual disconnect, and MISAL. `tools/test_sketchpad_functions.py` waits for tape completion and application display before operating Sketchpad.

---

# 2. High-speed PUNCH — unit `63`

## 2.1 Device and exact mode table

The punch is a line-by-line output device. Each TSD requests **one tape line**. The handbook quotes up to **180 lines/second**. [H63:4651–4657]

| IOS command | Mode | Seventh hole | Uses identified by handbook |
|---|---|---|---|
| `IOS_63 30000` | Normal | No | Blank tape, END MARKs, visual-pattern punching |
| `IOS_63 30004` | Normal | Automatic on each line | Tapes to be listed on off-line Lincoln Writers |
| `IOS_63 30002` | Assembly | No | Splayed 36-bit output |
| `IOS_63 30006` | Assembly | Automatic on each line | Primarily binary output |

[H61:4103–4130; H63:4658–4692]

Hardware mode bits:

| Mask | Handbook bit | Meaning |
|---:|---|---|
| `0002` | `1.2` | `0` normal; `1` assembly |
| `0004` | `1.3` | `0` no seventh hole; `1` automatic seventh hole |

[TM2:14269–14300]

**Leader and END MARK are not additional hardware modes.** They are data patterns punched in the selected normal/assembly and seventh-hole modes. The handbook explicitly identifies blank tape and END MARKs as uses of normal/no-seventh mode. [H61:4105–4108]

## 2.2 Normal TSD format

Normal output uses six bits, logically `1.1–1.6`, with normal permutation/activity available. Memory is not altered. Physically, `1.6` goes into hole 1; viewing tape with the seventh-hole position on the right gives the memory character ordering described by the manual. [TM2:14272–14275; H63:4693–4697]

Inactive output portions become zero under the common TSD rules. [H63:3295–3299]

## 2.3 Assembly TSD format

Each TSD copies these six bits:

`1.6, 2.3, 2.9, 3.6, 4.3, 4.9`

and then rotates the complete source memory word left one bit. Configuration is ignored. Six TSDs punch a full 36-bit word and leave the source rotated left six places. [TM2:14277–14283; H63:4698–4707]

For a six-bit numeric tape datum, the corresponding mapping is:

| Output datum bit | Source bit |
|---:|---|
| 0 | `1.6`, zero-based 5 |
| 1 | `2.3`, zero-based 11 |
| 2 | `2.9`, zero-based 17 |
| 3 | `3.6`, zero-based 23 |
| 4 | `4.3`, zero-based 29 |
| 5 | `4.9`, zero-based 35 |

**[INFERENCE]** Numeric bit ordering follows the reader’s reciprocal splayed format and is also the mapping used by `rtl/tx2_core.v:418–424`.

## 2.4 Flag and ready behavior

Each of the four connecting IOS commands raises FLAG `63` **if and only if** the punch was previously disconnected. [H61:4132–4133; H63:4690–4692]

During a TSD:

1. Clear/load the six-bit punch buffer.
2. Clear status to busy.
3. Set the pending-punch flip-flop.
4. Start or retrigger the motor timing.

The synchronized **END PUNCH** event sets status available and raises the punch flag. This occurs while the tape-feed portion of the mechanical cycle is proceeding; a following TSD may load the buffer before END FEED. [TM2:14333–14360,14369–14386]

Thus the flag indicates buffer acceptance capability, rather than necessarily completion of all mechanical feeding.

## 2.5 Timing and differing source figures

| Parameter | Primary-source value |
|---|---|
| Handbook maximum | 180 lines/second |
| Initial motor run-up | Approximately 1 second |
| Motor retention | Continues running if TSDs occur more frequently than once per 5 seconds |
| Motor idle stop | Approximately 5 seconds after last TSD |
| Handbook manual Tape Feed hold delay | 5 seconds |
| Technical Manual manual-feed description | Feeding allowed after 1-second run-up |
| Sketchpad thesis peripheral summary | 300 six-bit lines/second |

[H63:4655–4657,4718–4720; TM2:14307–14312,14389–14394; TR296:4375]

The 180/300 line-rate and 5/1-second manual-feed discrepancies are source differences. A replica should identify its chosen historical device revision/timing profile rather than silently combine them.

## 2.6 Alarms

The punch is an **equipment-inability** alarm source. It is not identified as a free-running missed-data source. [H63:3455–3476; TM2:13164–13167]

Technical Manual alarm behavior:

- Alarm conditions sound a buzzer and illuminate a red light.
- EIA sets when the next TSD occurs.
- ACK suppresses the buzzer; red light and EIA persist while ACK is selected, even after the initiating fault is corrected.
- After fault correction, RESET clears the lamp and buzzer.
- The EIA flip-flop itself clears only through a connection process.

[TM2:14396–14403]

Conditions:

| Condition | Consequence |
|---|---|
| Supply down to approximately 100 feet | LOW TAPE warning; punching remains possible |
| Tape handler fails to supply tape; slack-loop sensing | Inhibits punching and manual feeding |
| End-of-tape sensor | Same inhibition; keeps thickened tape end out of mechanism |
| Lubrication timeout | Shuts machine down; maintenance-only reset |
| Lubrication interval | Lubricate after 4 running hours; timer expires after 4.5 hours |

For inhibited supply/end conditions, motor stops after the five-second delay. A feed-button press or TSD may restart the motor but does not cause punching while the fault remains. [TM2:14405–14436]

## 2.7 Manual controls

| Control/component | Documented behavior |
|---|---|
| Buzzer | Low tape or jam indication |
| Buzzer suppression switch | Normally left, unsuppressed |
| Maintenance switch | Right position is maintenance |
| Tape Feed pushbutton | Must be held; handbook gives five-second delay |
| Alarm indicator lamp | Low tape or jam |
| Maintenance indicator lamp | Maintenance indication |
| Punch reeler and control arm | Arm normally tape-operated; can be raised manually to energize reeler brake |
| Punch motor switch | Normally up; maintenance use |
| Chad basket | Collects punched material |

[H63:4714–4730; H61:4160–4181]

## 2.8 Character/code tables

The high-speed punch and PETR impose **no intrinsic character alphabet**: they transfer arbitrary six-bit values. The complete hardware mode table is given above. A Lincoln Writer character table applies only when software chooses to produce Lincoln Writer-coded tape; a plotter tape uses the separate binary record format below. [TM2:13993–14003,14265–14283; H61:4105–4130; SK2:6629–6638]

## 2.9 Initial implementation snapshot

The initial host implementation had the following behavior. Section 4 records the subsequent controller implementation.

- Declares unit `063` present.
- Decodes assembly from command bit 1 and automatic seventh hole from bit 2.
- Emits each line as `0x80 | seventh?0x40:0 | six_data_bits`.
- Uses an optional `punch_us` busy interval, default zero.
- CPU implements the correct splayed extraction and source rotation.

[`host/tx2_host.h:24,38–42,55,141–145,172–181`; `rtl/tx2_core.v:412–425,433,691`]

Missing:

- One-second motor startup and five-second idle stop.
- Separate punch/feed mechanical phases and END PUNCH readiness.
- Low-tape/jam/end/lubrication alarm state and EIA.
- Manual-feed, ACK/RESET, maintenance, reeler/brake controls.
- Historically defined timing profiles.

A further current-code issue: the host applies its punch-mode decoding on **every** `external_control_valid` command, including commands such as `50000` used only to raise a flag. **[INFERENCE]** This can transiently reset the host’s assembly/seventh-hole state without a mode-setting IOS; mode decoding should be tied to the relevant IOS operation. [`host/tx2_host.h:172–174`; `rtl/tx2_io.v:136–140`; SK2:6835–6837]

---

# 3. Sketchpad plotter — direct unit `74`, off-line tape through `63`

## 3.1 Device identification

Sketchpad used an **EAI, Electronic Associates Incorporated, pen-and-ink plotter**. Its digital and analog control system could draw straight lines and circles either:

1. Directly under TX-2 control.
2. Off-line from punched paper tape.

[TR296:640–642,924–926]

The thesis quotes:

- Plotting area: **29 × 29 inches**.
- Slew speed: **15 inches/second**.
- Both direct and off-line control.

[TR296:4383–4385]

Its bibliography cites the EAI **“Handbook for Variplotter Models 205S and 205T, PACE,” 15 June 1959**. This identifies the referenced product family, but does not by itself establish which particular model the photographed installation used. [TR296:4400–4401]

This plotter is separate from the Xerox printer: the thesis lists Xerox and the large-board pen plotter separately, and the service code uses sequence `74`, whereas Xerox is `51`. [TR296:4380–4385; SK2:6665–6686; `references/text/LM-44v1_TX-2_Technical_Manual_Volume_1_196105.txt:1826,1875–1876`]

## 3.2 Public service entry points and architecture

| Entry | Public location | Action |
|---|---:|---|
| `PLCLEAN` | `200130` | Reset plotter service state and output table |
| `PLPLOT` | `200131` | Start direct-output sequence `74` |
| `PLPUNCH` | `200132` | Start paper-tape output sequence `63` |
| `PLEND` | `200133` | Mark/end generated output |

[SK2:455–470,5309–5329,6564–6591]

The actual entry points use `RXF_63 PLPURTNE` and `RXF_74 PLPLRTNE`. [SK2:6575–6581]

`PLOTSUB` cleans the service, starts whichever of direct plotting and tape punching the user requested, generates geometry through `MAG`, calls `PLEND`, and waits/restarts consumers as necessary. Both consumers therefore process the same generated plotting table. [SK2:1619–1651]

Geometry entry points:

```text
PLOTLINE:   A = start point, B = end point
PLOTCIRCLE: A = start point, B = center, C = angle
```

[SK2:6555–6559,6750–6753,6858–6863]

The line-generation path explicitly calls `PLOTLINE`; the circle path calls `PLOTCIRCLE` with normalized center and angle information. [SK2:5959–5974,6278–6282]

## 3.3 Internal table record

Each generated record uses **two memory words**:

| Relative word | Contents |
|---|---|
| `0` | TSD data: packed coordinate/filter word |
| `1` | IOS/control word plus tally and repetition metadata |

Both output consumers explicitly fetch these as `**TSD` and `**IOS`, then advance their table pointer by two. [SK2:6624–6628,6643–6647,6677–6682,6692–6694]

The table producer writes the IOS word at offset `1`, TSD at offset `0`, and tally/repetition metadata into the remaining portions of the IOS word. [SK2:6811–6828]

The source comments identify a packed `ΔX,,ΔY` coordinate pair. It masks each 18-bit half with `777770`, then inserts a filter number into each half. Thus:

```text
bits 35........18 | bits 17.........0
   coordinate+f  |    coordinate+f
```

The low three bits of each half hold a filter selection; each coordinate retains the upper fifteen bits. **[INFERENCE]** Axis assignment as left-half X/right-half Y follows the `ΔX,,ΔY` comment; the exact external DAC interpretation still needs the omitted hardware specification. [SK2:6760–6782,6791–6809]

The software supports filter numbers `0–6`; circle mode enforces a minimum filter of `4`. Filter thresholds are based on divisions by powers of three. [SK2:4968–4984,6793–6805,6849–6852]

## 3.4 Plotter IOS bits recoverable from actual code

These meanings are established by code comments and bit-setting operations, rather than a complete handbook device table:

| Mode mask | Bit | Meaning established by Sketchpad |
|---:|---|---|
| `0001` | `1.1` | Pen down when set; cleared for pen up |
| `0004` | `1.3` | PBI mode |
| `0010` | `1.4` | Direction; set for counterclockwise |
| `0040` | `1.6` | Circle mode |
| `0700` | `1.7–1.9` | One axis’s filter field **[INFERENCE]** |
| `7000` | `2.1–2.3` | Other axis’s filter field **[INFERENCE]** |

Evidence:

- Pen down: SK2:6844–6846.
- Pen up: SK2:6728–6734.
- PBI: SK2:6687–6688,6708–6716,6866–6867.
- Circle and counterclockwise: SK2:6866–6874.
- Filter construction: SK2:6804–6809.
- Both filters decremented together by `1100`: SK2:6695–6698.

**[INFERENCE]** The duplicated filter fields account for `1100` being one count in each field. This is consistent with the duplicated low-three-bit filter fields in TSD data.

Bits `0002` and `0020` have no meaning established by the code read here. No claim is made that these are unused hardware bits.

The source uses `PBI` without an expansion in these sections. Its exact hardware expansion and complete semantics remain unestablished.

## 3.5 Exact punched record sequence

`PLPURTNE`, running in sequence `63`, emits an ordinary data record as:

| Line | Punch command | Seventh hole | Six data bits |
|---:|---|---|---|
| 0 | Normal, `30004` | Yes | Low six bits of the IOS/control word |
| 1 | Assembly, `30006` | Yes | Splayed coordinate/filter row 0 |
| 2 | Assembly | Yes | Splayed row 1 |
| 3 | Assembly | Yes | Splayed row 2 |
| 4 | Assembly | Yes | Splayed row 3 |
| 5 | Assembly | Yes | Splayed row 4 |
| 6 | Assembly | Yes | Splayed row 5 |
| 7 | Normal, `30000` | No | Tally from the fourth quarter of the IOS metadata word |

[SK2:6629–6638]

This is an **eight-line binary plotting block**, not an ASCII command, Lincoln Writer text, Xerox character, or incremental step-direction byte stream.

The source loads the TSD word into temporary `PLUWA3` before the six assembly TSDs, preserving the stored table word while the punch rotates the temporary. [SK2:6631–6636]

For an original 36-bit word `D`, row `r=0…5` and datum bit `k=0…5` are:

```text
row[r].bit[k] = bit(D, (6*k + 5 - r) mod 36)
```

Each of these six rows has a seventh hole. **[INFERENCE]** This follows from the documented assembly extraction and one-place left rotation after every punch TSD.

The first line carries only the low six IOS mode bits. **[INFERENCE]** The off-line controller obtains filter selection from the low-three-bit fields packed into the coordinate word; that explains why the direct IOS filter fields need not be carried in the first tape line. [SK2:6630–6636,6804–6809]

### Repetition and tally metadata

The punch routine extracts a block count from `PLUWA`; `PLPUL6` repeats the same record while updating that count. The direct plotter’s PBI path also reads the block-count metadata. [SK2:6643–6649,6711–6716]

The tally is generated by this exact source sequence:

```text
ITA {77}
LDD PLTLYK
TLY A
TLY PLWA
STA 0_PLS
³²COM D
²¹STD 1_PLS
```

`PLTLYK` is initialized as `-49.,`. [SK2:6813–6819,6943]

`TLY` counts one bits and adds the result to the sign quarter of D using nine-bit ring arithmetic. [H63:2381–2401]

**Specification boundary:** tally placement and generating instructions are established. A normalized six-bit checksum equation covering every leader/final special record remains unresolved. Preserve the source algorithm until that equation is established.

## 3.6 Tape leader and trailer

Leader constant:

```text
PLEADER = {48.,51.,,73,0}
```

Its four nine-bit quarters, from quarter 4 down to quarter 1, are:

| Quarter | Value |
|---|---:|
| 4 | decimal 48 = octal `60` |
| 3 | decimal 51 = octal `63` |
| 2 | octal `73` |
| 1 | `0` |

[SK2:4963; quarter selection corroborated by normal configuration mappings in `upstream/TX-2-simulator/cpu/src/exchanger.rs:1015–1049`]

Initial output:

1. Set normal/no-seventh-hole mode.
2. Punch six zero lines.
3. Punch `73` without seventh hole, explicitly commented `END MARK`.
4. Punch `63` without seventh hole, explicitly commented `TALLY`.
5. Switch normal/seventh-hole mode.
6. Generate leader blocks using zero lines and the quarter-4 tally value `60`.

[SK2:6598–6616]

**[INFERENCE]** Loop decoding gives 25 leader blocks after the initial END MARK block; each leader block has seven zero lines with seventh holes followed by a no-seventh tally line. The loop count is decimal `25.`, not octal `25`.

At final end, `PLUEND` sets normal/no-seventh mode and emits blank lines with a decimal `319.` loop initializer. **[INFERENCE]** This is 320 blank feed lines under the usual inclusive negative-count loop. It then clears busy/activity state and disconnects unit `63`. [SK2:6655–6662]

`PLEND` also creates a final table record: its IOS metadata literal is `{(56.-31.),0,,30000}`, and its final TSD literal is `{377770,,}`. The transcription itself marks one numeral in the former as a best guess; preserve that qualification. [SK2:6582–6591]

## 3.7 Direct on-line output, ready, and timing

The direct consumer:

1. Loads the TSD word into `PLPWA`.
2. Copies IOS metadata into a self-modified IOS instruction.
3. Executes a preliminary IOS commented `WAIT FOR PEN CHG`.
4. Executes the actual `IOS_74` mode command.
5. Performs TSD unless entering the alternate PBI path.
6. For nonzero filters, lowers both IOS filter fields with `DEX 1100` and repeats until reaching the lower setting.
7. Disconnects at final end.

[SK2:6677–6707]

The sequence can also be awakened by explicit `IOS_74 50000`, emitted when new records become available and the consumer is not busy. [SK2:6835–6839,6974–6979]

**[INFERENCE]** The preliminary unheld/dismissing IOS and the `WAIT FOR PEN CHG` comment show that pen-state change completion must participate in ready/flag scheduling. Treating every plotter IOS/TSD as immediately ready would omit behavior on which the service relies.

PBI uses interval-timer sequence `54`:

- `hTSD PLPWA`.
- Transfer to timer-driven work.
- Stop/reset timer, load `PLITK`, restart with `IOS_54 30300`.
- Count timed blocks while permitting tracking service.
- Clear PBI, lift pen, and toggle direction when finishing certain transitions.

[SK2:6708–6746]

Relevant timing constants are exactly:

```text
PLITK = {10000.,,(176000.-30./20.)}
PLITWA = ,,-19.,
```

Comments identify one timer use as `1/20TH READER SPD`, and the main-program interval as `10.MS`. [SK2:4997,6714–6716,6738–6740,6747]

**Specification boundary:** no separate off-line plotter reader line-rate specification was located. These timer constants should not be converted into a claimed hardware speed without resolving their historical timer scale and expression interpretation.

## 3.8 Plotter alarms and manual controls

The available handbook lacks section `74`; the read Technical Manual supplies only its high-level coordinate-controlled description. Consequently the following are **not established by available primary text**:

- Complete IOS bit table beyond the software-derived meanings above.
- Exact full-width hardware TSD/DAC wiring and sign conversion.
- Plotter EIA/MISIND conditions.
- Full manual panel controls.
- Pen-transition delay and filter-settling constants.
- Off-line controller’s complete checksum-error and tape-resynchronization behavior.

[H63:18–23; `references/text/LM-44v1_TX-2_Technical_Manual_Volume_1_196105.txt:1874–1876`]

The missing hardware document is a genuine source prerequisite for a complete physical emulation. The local source inventory contains the thesis’s citation to the EAI manual, but no matching EAI manual PDF was present in the enumerated `references/pdfs` directory.

## 3.9 Initial plotter implementation snapshot

Unit `74` is not a built-in unit in `rtl/tx2_io.v` and is not declared present by the current host. Generic absent units are treated as software units. Therefore **[INFERENCE]** the present system does not provide actual direct plotter operation, even though Sketchpad contains the direct service. [`rtl/tx2_io.v:70–84`; `host/tx2_host.h:141–145`]

The current punch host can capture the off-line tape byte stream because it models normal/assembly output and the seventh hole. It does not decode or render that stream as plotting commands. [`host/tx2_host.h:172–181,224–226`]

Required separable components:

1. Unit `74` direct controller with coordinate/filter data, pen/circle/direction/PBI state, and real ready/flag transitions.
2. An off-line plotter-tape decoder for the eight-line records generated by `PLPURTNE`.
3. Correct PUNCH timing/alarms, independently of the plotter decoder.
4. Shared drawing mechanics driven by either direct controller or off-line controller. **[INFERENCE]** This mirrors the primary-source description of one plotter supporting both modes.

A transcription correction is already applied by the image-preparation tool: SK2 line 6596 `PLPBUSY` becomes `PLPUBUSY`. Cite/use the corrected spelling when tracing the assembled program. [`tools/prepare_sketchpad.py:288–289`; `programs/sketchpad/manifest.json:1702–1705`]

A remaining source limitation is the clipped line at the entry to `PLPLRTNE` on listing part 2 PDF page 149. The transcription marks it illegible, and the expanded source still begins the routine at the following page’s `MKN PLPSW`; the missing instruction was not recovered by this investigation. [SK2:6667–6673; `work/sketchpad/build-expanded.tx2as:2049–2051`]

## Implementation source index

| File/range | Contents |
|---|---|
| `references/figures/petr-modes.png` | Legible original reader command and TSD table |
| H63:4005–4057 | PETR description and TSD behavior |
| H61:3844–3880 | Legible reader manual-control text |
| TM2:13991–14153 | PETR transport, END MARK, synchronization, and MISIND |
| H61:4103–4181 | Punch mode table, TSD, and manual controls |
| TM2:14265–14436 | Punch bit assignments, cycles, timing, and alarms |
| SK2:1619–1651 | Sketchpad caller lifecycle |
| SK2:4954–4998 | Plotter constants, leader, filters, timer constants |
| SK2:6555–6747 | Public services, tape serialization, direct plotter and timer consumers |
| SK2:6750–6979 | Coordinate/filter generation, IOS bits, tally, circle blocks |
| `rtl/tx2_core.v:405–433,688–691` | Normal and assembly TSD data paths |
| `rtl/tx2_io.v:70–140,158–208` | Device presence, ready/flag logic, reader buffering, IOS handling |
| `host/tx2_host.h:134–181` | Current host reader/punch behavior |

## 4. Replica implementation and operation, 2026-11

- `host/devices/punch.h` implements all four unit-63 hardware modes. Masks `0002` and `0004` select assembly and the seventh hole, respectively. The CPU performs assembly-bit extraction and source-word rotation. Programs emit blank leader, END MARK, and plotting records in those modes. Sources: H63:4651–4707; TM2:14265–14283.
- The default `handbook` timing profile uses 180 lines/s, approximately one-second startup, five-second idle stop after the last TSD, and five-second manual-feed hold delay. `dev punch profile technical` selects TM2's one-second manual-feed delay. `profile sketchpad` selects 300 lines/s from TR296:4375. Other mechanical timings retain the documented shared profile; a complete alternate-model specification is unavailable. `dev punch us N` and `startup_us N` are host debug timing settings.
- END PUNCH makes the buffer available before the feed phase completes. Source: TM2:14317–14386. `[INFERENCE]` With phase durations undocumented, the model divides one line period equally between punching and feeding.
- `dev punch low|supply|end|maintenance|ack 0|1` exposes tape-supply, maintenance, and buzzer-suppression state. `feed 0|1` holds/releases manual feed, `reset` resets the alarm panel, and `lubricate` resets the lubrication timer only in maintenance mode. Low tape is a warning. Supply failure, tape end, and 4.5 running hours without lubrication inhibit punching. The next TSD latches EIA; the connection process clears it. A loaded buffer remains busy through supply failure and resumes after recovery. Source: TM2:14396–14434.
- `dev punch brake 0|1` exposes the reeler-arm brake, and `motor 0|1` operates only in maintenance mode. `[INFERENCE]` The handbook lists a maintenance motor switch without wiring details. The model interprets OFF as removing motor drive and generates no additional EIA. Source: H63 punch panel description.
- `host/devices/plotter.h` registers direct unit 74, retaining IOS mode, buffer busy/available state, pen-transition waits, and raw `[mode,word]` events. Pen, PBI, circle, and direction interpretation follows SK2:6685–6689 and 6844–6874; filter fields follow SK2:6792–6809. Actual TSD data drive the displayed pen trace.
- `[INFERENCE]` The `WAIT FOR PEN CHG` IOS at SK2:6685 yields even when pen state is unchanged. Each mode IOS therefore completes through a busy-to-available transition. Pen changes take 5 ms; other control acknowledgements use 1 μs. Original numerical delays require hardware sources.
- `dev plotter tape HEX` incrementally accepts offline tape. It decodes seven seventh-hole lines followed by a no-seventh-hole tally as specified at SK2:6629–6638; six assembly rows reconstruct the 36-bit coordinate word. Ordinary punch output remains raw tape. In the browser, use the paper-tape plotter page's read-punch-output action or upload `.tape` for offline plotting, then export PNG.
- `[INFERENCE]` The unit-74 hardware chapter is missing. The model maps upper-fifteen-bit ones-complement coordinates onto 29-inch paper and uses ideal line/circle geometry with a 5 ms pen transition. PBI uses 13/38/113 blocks per revolution from SK2:4992–4995 and 6960–6964. Direct plotting follows SK2:6711–6747, advancing one block per 20 actual interval-timer output pulses. Full DAC wiring, analog filters, PBI circuits, physical pen timing, and offline error-check/resynchronization circuits remain undocumented. The original tally is retained, with checksum-error alarms unresolved.
- `[INFERENCE]` The last line of listing part 2 PDF p. 149 retains only `PLTABLE-1`; the `PLPLRTNE` opcode/subscript is cropped. The preparation tool reconstructs `SKX_PLP PLTABLE-1`, consistent with punch-table pointer initialization at SK2:6620 and direct-table reads at 6675–6680. The generated manifest classifies this line separately as `inferred`.
- Acceptance command: `TX2_CLI=build/obj_cli/tx2-cli python3 tools/test_dev_paperplot.py`. Small programs use real IOS/TSD to check four modes, rotation, status, flags, alarms, and a closed circle in an offline assembly stream. Sketchpad then creates a line and complete circle with the light pen and invokes PLOT at 4.8 and PUNCH at 4.7. Checks cover direct pen traces, software leader/trailer, offline traces, and 20 timer pulses per paper-tape circle block.