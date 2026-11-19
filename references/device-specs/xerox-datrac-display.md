## Scan evidence

H63 PDF pages **99, 101, 103, and 196** were rendered and visually checked. DATRAC's native buffer occupies the low 18 bits. Xerox fields are X=4.9–4.1, Y=2.6–2.1, and character=1.9–1.1. The complete glyph table was corrected against two scanned tables. Device implementations are `host/devices/xerox.h` and `host/devices/datrac.h`; panels are in `web/printanalog.js`.

Primary sources do not specify exact DATRAC rounding, low-bit noise, or digital results after excessive trigger rates. They also leave the exact Xerox glyph outlines, size ratios, and startup-noise distribution unresolved. Corresponding implementation choices are labeled `[INFERENCE]`.

# Print, analog, display and light-pen specifications

All unit numbers, IOS instructions, and character codes below are octal. Other quantities are decimal unless stated otherwise. Code paths are relative to the repository root.

### Source abbreviations

- **H63**: `references/text/TX-2_UsersHandbook_Nov63.archive-page-ocr.txt`
- **H61**: `references/text/TX2-Users-Handbook_196107.txt`
- **TM1**: `references/text/LM-44v1_TX-2_Technical_Manual_Volume_1_196105.txt`
- **TM2**: `references/text/LM-44v2_TX-2_Technical_Manual_Volume_2_196106.txt`
- **SP**: `references/text/Sketchpad_TR296_Jan63.txt`
- **XM**: `references/text/TX2-Memos-General_196407.txt`

## Summary

- **Xerox 51** is a positioned-character continuous-paper printer. Every TSD specifies X, Y and a nine-bit character/size code. Frame synchronization is `IOS₅₁ 30010`; hardware does not provide the software page-formatting commands described in the later Xerox package memo.
- **DATRAC 50** samples a documented single analog signal, triggered externally or by routed IOS/TSD pulses. Conversion takes **22 µs**, with at least **37 µs between triggers**. The transfer is an **18-bit signed ones-complement fraction**, with only **8–11 reliable leading bits**.
- **Displays 56/60** accept individual 10-bit-per-axis points. Intensity selects **10/20/40/80 µs illumination**, and origin positioning complements coordinate sign bits.
- **Light pen 55** is an interrupt source, not a coordinate input register. The 1961 handbook restricts it to scope 60; the January 1963 Sketchpad report explicitly describes **two pens working with either scope**. This is a substantive configuration revision.
- Xerox and DATRAC connect to the common host device bus and have browser panels and CLI acceptance programs. PDF scans establish native bit layouts and glyph identities. Sections 4–5 document display, camera, and light-pen configurations and implementation status.

## 1. Shared IOS, flag and alarm rules

| Item | Specification | Source |
|---|---|---|
| Connection | Connect enables transfers and the device’s access to its flag. | H63:3070–3090 |
| IOS commands | `20000` disconnects; `3xxxx` connects and selects mode `xxxx`; `40000` lowers flag; `50000` raises flag. | H63:3210–3245 |
| Output connection | Connecting an output unit raises its flag if previously unconnected. A slow mode change keeps its buffer busy until completion, then raises the flag. | H63:3230–3248 |
| Input completion | The next available datum raises the input flag. | H63:3175–3190 |
| Output completion | Completion of the preceding output transfer raises the output flag. | H63:3180–3190 |
| Busy TSD | Dismiss-and-wait occurs, including for a held TSD; the program counter is not advanced, and the TSD is retried after resumption. | H63:3190–3210 |
| Alarm reporting | Unit 41 reports DATRAC MISAL at bit **1.1 / `001`**, camera EIA at **1.5 / `020`**, and Xerox EIA at **1.7 / `100`**. | H61:3448–3463 |
| Alarm clearing | TSD does not clear alarms. Disconnect the offending device. Read before disconnecting because disconnected devices’ conditions cannot be reported. | H61:3437–3445,3466–3477 |
| MISAL | Unsuppressed MISAL stops the computer. Connecting unit 41 programmatically suppresses that stop and permits alarm-subprogram operation. | H61:3425–3435,3466–3469 |
| EIA | Does not stop the computer; it may ring a buzzer or stop the device. | H61:3470–3471 |
| Additional alarms | A second alarm before the first is cleared updates the alarm buffer without raising flag 41 again. | H61:3472–3477 |

RTL implements these alarm positions in `rtl/tx2_io.v:137–147`, generic alarm latching at `:164–166`, disconnect clearing at `:193–195`, and flag generation at `:90–114`.

## 2. Xerox printer — unit 51

### 2.1 Identity, positioning and paper behavior

The printer is an electrostatic charactron display with continuous xerographic recording. Electronic compensation holds a frame stationary for approximately **45 ms**, then moves it down approximately **0.1 inch** to follow the paper. The programmer supplies the position and character for every printed character. The prose calls it a **960-lines/minute** printer.

Sources: H63:3763–3771, PDF p101; H61:3699–3708, PDF p107.

| IOS | Mode bits in low 12 bits | Meaning |
|---|---:|---|
| `30000` | `0000` | Connect, turn on xerographic recording, raise flag 51 when ready. Warm-up approximately **5 s**. |
| `30010` | `0010` | Frame sync. Connect if necessary; raise flag 51 at start of next frame. |
| `20000` | — | Disconnect. Paper continues for the specified run-on interval. |

Sources: H61:3710–3718,3741–3746; H63:3772–3783,3804–3809.

`0010` is mode bit **1.4** `[INFERENCE: octal-to-bit conversion]`. No additional Xerox mode-word functions are documented in the device section.

**TSD:** prints one positioned character. Approximately **750 µs** per character; at most **60 characters in one 45-ms frame interval**. Sources: H61:3720–3724; H63:3780–3783.

**Data components:**

| Field | Documented format |
|---|---|
| X | Nine-bit unsigned integer, `000`–`777`. |
| Y | Six-bit signed ones-complement integer, `−37` through `+37`. |
| Character | Nine-bit code; bit **1.9**, mask **`400`**, selects large/small character. |
| Coordinate origin | Left end, vertically centered within the frame. |
| Exact word alignment | Visual inspection of PDF p. 101 confirms X at bits 35–27, TX-2 4.9–4.1; Y at 14–9, TX-2 2.6–2.1; character at 8–0, TX-2 1.9–1.1. Remaining bits are unused. |

Sources: H61:3726–3740,3843–3844; H63:3785–3803,3859–4006; PDF H63 p101 and p103.

The large gap in the diagram represents unused bits 26–15. X, Y, and character occupy separated fields.

**Paper run-on and startup:**

- First TSD starts paper movement.
- Paper runs until **15 s after the last TSD**, or **15 s after disconnect**.
- A TSD that starts the paper is unreliable because of mechanism-generated noise.
- The documented safe startup is one or two blank characters, such as code **`100`**, followed by an extra frame-sync `30010`.

Sources: H61:3741–3746; H63:3804–3809.

### 2.2 Numerical parameters

| Parameter | Handbook value |
|---|---:|
| Frame interval | Approximately 45 ms |
| Frame reset interval | 2 ms |
| Character print time | 750 µs |
| Frame height × width | 1¼ × 5 inches |
| Nominal character height × width | 3/32 × 1/16 inch |
| Paper speed | 2 inches/s |
| Characters per line | 60 |
| Vertical deflection | 0.02 inch/unit |
| Horizontal deflection | 0.01 inch/unit |
| Frame spacing | 0.094 inch |
| Lines per inch | 10.65 |
| Suggested X increment | 8 units |

Sources: H63:3827–3841, PDF p102; H61:3756–3771, PDF p108.

**Source discrepancy:** the handbook’s 960-lines/minute description and its calculated frame spacing/line density should remain distinct stated specifications. The January 1963 Sketchpad equipment inventory lists **1300 characters/s**, consistent approximately with the 750-µs character time. Sources: H63:3767; SP:4380. `[INFERENCE: timing consistency comparison]`

### 2.3 Flag, ready, alarms and controls

- Connect completes after warm-up and raises flag 51.
- Frame-sync completion raises flag 51 at the next frame boundary.
- Ordinary output completion follows the shared output-unit ready/flag rule.
- Low paper causes **EIA**, and can raise flag 41 if alarm circuitry is connected.
- Manual controls shown/documented: **ON/OFF switch** and **low-paper buzzer alarm**.

Sources: H61:3710–3718,3777–3788; H63:3842–3851.

The unit-41 table assigns Xerox EIA bit `100`; it does not assign Xerox a MISAL bit. Source: H61:3454–3463.

### 2.4 Character-code table

**Scan verification:** all 44 pairs, 88 glyphs, and parenthesized alternate codes were checked against H63 PDF pp. 103 and 196. Codes retain the table's recommended size bit. The simulator treats alternate codes as glyph aliases. Unicode below represents glyph identity; exact outlines require original font-mask data.

Sources for the complete table: H63:3853–4006, PDF p103; H63:9207–9259, PDF p196; H61:3793–3844, PDF p109; H61:7764–7816 and 8763–8815, PDF pp196 and 217. The repeated copies resolve several numeric OCR errors.

| Left character | Codes | Right character | Codes |
|---|---|---|---|
| A | `154` | j | `122 (107)` |
| B | `142` | k | `324 (034)` |
| C | `361 (056) (071) (346)` | n | `323 (033)` |
| D | `352` | p | `024` |
| E | `313 (043)` | q | `111` |
| F | `344 (054)` | t | `112` |
| G | `302 (012)` | w | `173` |
| H | `354` | x | `174` |
| I | `172 (157)` | y | `163` |
| J | `144` | z | `164` |
| K | `143` | α | `310 (040)` |
| L | `332 (047) (062) (317)` | β | `311 (041)` |
| M | `360 (055) (070) (345)` | γ | `333 (063)` |
| N | `370 (355)` | Δ | `203` |
| O | `353` | ε | `334 (064)` |
| P | `312 (042)` | λ | `023` |
| Q | `160 (145)` | 1 | `001` |
| R | `371 (356)` | 2 | `002` |
| S | `322 (017) (032) (307)` | 3 | `003` |
| T | `153` | 4 | `004` |
| U | `362 (057) (072) (347)` | 5 | `020 (005)` |
| V | `152` | 6 | `021 (006)` |
| W | `343 (053)` | 7 | `022 (007)` |
| X | `161 (146)` | 8 | `300 (010)` |
| Y | `342 (052)` | 9 | `301 (011)` |
| Z | `162 (147)` | 0, zero | `000` |
| h | `132 (117)` | ? | `202` |
| i | `133` | comma | `204` |
| < | `220 (205)` | ∩ | `120 (105)` |
| > | `221 (206)` | ⊃ | `121 (106)` |
| period | `222 (207)` | × | `113` |
| + | `351` | circle | `714 (444)` |
| − | `372 (357)` | ~ | `373` |
| ∨ | `340 (050)` | ∧ | `341 (051)` |
| Apostrophe | `363 (073)` | # | `364 (074)` |
| Single vertical bar | `730 (445) (460) (715)` | Double vertical bar | `731 (446) (461) (716)` |
| Σ | `703 (413)` | □ | `704 (414)` |
| } | `720 (415) (430) (705)` | { | `721 (416) (431) (706)` |
| ← | `150` | → | `151` |
| Underbar | `570 (555)` | Overbar | `571 (556)` |
| ( | `140` | ) | `141` |
| = | `114` | ≡ | `130 (115)` |
| / | `131 (116)` | * | `102` |
| ∪ | `103` | ⊂ | `104` |

**Size bit:** bit 1.9 = **1 large, 0 small**; table codes include the indicated “proper” size. Sources: H63:9257–9258; H61:3843–3844.

TM1 describes **88 different eight-bit characters in two sizes**, matching the table’s 44 pairs and a separate size bit. Source: TM1:1826–1827. `[INFERENCE: relationship of count to table]`

### 2.5 Page and line formatting software

Hardware accepts explicit positions and frame synchronization. A separate **30 September 1964** Xerox-package memo describes page-oriented behavior, and must be dated separately from the 1961–63 hardware specification.

Sources: XM:124–169, PDF pp4–5.

- Initial `hJPQ XEROX` takes title in A and name in B, starts the printer, and stores page-heading data.
- Title/name are Lincoln Writer codes, one per quarter beginning with quarter 1; only three name characters are used.
- Subsequent codes are passed in quarter 1 of A with `SEND`, or `SEND|code`.
- Default is an **8½-inch page with 46 lines including the title**.
- The memo’s frame-length units are garbled in OCR; values **66** and **40** require visual confirmation.

| Package code | Behavior |
|---|---|
| `14` | Finish page and title next page. |
| `114` | No paging; if already in that mode, immediate chop and title. |
| `15` | Frame-length setting “66”; 46 lines/page. Code OCR reads `1-5`, interpreted as `15` [INFERENCE]. |
| `115` | Frame-length setting “40”; 74 lines/page. |
| `16` | Small character separation, for numbers. |
| `116` | Large character separation, for text. |
| `17` | Large bar and return to large separation. |
| `71` | Next code supplies horizontal position; move to new line if position decreases. |
| `171` | Same position command without automatic new line, for graphs. |
| `76` | Finish page and stop Xerox. |

Source: XM:153–169. These are **package input codes**, not Xerox IOS mode bits or native character codes.

The package also supplies `DFRAC`, `DINT`, `LADR`, `OIST` and text-output routines. Sources: XM:171–215. No corresponding Xerox or DATRAC device routines were found in the inspected Sketchpad transcriptions or listing OCR, after name searches and encoded unit-number searches.

### 2.6 Current implementation

- `host/devices/xerox.h` implements unit 51 on the common bus: five-second connection warm-up, frame sync, 45 ms exposure and 2 ms reset, 750 μs character busy time, positioned X/Y/character and size fields, startup-uncertainty marking, 15-second paper run-on, and low-paper EIA at unit-41 mask `100`.
- The 47 ms total frame period follows PDF p. 102's 45 ms + 2 ms and `.094 in / (2 in/s)`. The approximate 45 ms description on p. 101 remains separately recorded.
- `web/printanalog.js` positions characters at 0.01 in/X, 0.02 in/Y, and .094 in/frame, retaining overstrikes. Unicode fonts and a two-to-one large/small display ratio are interface approximations labeled `[INFERENCE]`. Machine character codes are preserved.
- `dev xerox power 0|1` controls panel power; `dev xerox paper 0|1` sets low-paper state, with 1 meaning insufficient paper. Initial panel power ON is `[INFERENCE]`. IOS connection starts recording warm-up.

## 3. DATRAC — unit 50

### 3.1 Channel and analog specification

The Epsco DATRAC converts a continuous electrical signal into numeric samples. Measurement begins on a trigger from the computer or an external source, including the interval timer.

| Parameter | Value |
|---|---|
| Computer unit | `50` |
| Documented analog inputs | One signal input; no analog-channel selector or multiplexer is specified. |
| Maximum sampling rate | 27 kHz |
| Minimum trigger interval | 37 µs |
| Trigger-to-raise-flag time | 22 µs |
| Nominal input range | −1 V to +1 V |
| Alternative ranges | ±10 V or ±100 V, set behind the panel |
| Transferred number | Signed 18-bit ones-complement fraction |
| Reliable precision | Leading 8–11 bits |

Sources: H63:3691–3722, PDF p99; H61:3611–3644, PDF p105.

**Important channel distinction:** the panel’s numbered **1–4 inputs are trigger inputs**, not four analog measurement channels. Sources: H61:3658–3666; H63:3730–3740.

The January 1963 report independently gives a **nominal 11-bit sample and 27-kHz maximum rate**. Sources: SP:4367–4368; `references/text/Sketchpad_A_Man-Machine_Graphical_Communication_System_Jan63.txt:6797–6798`.

### 3.2 IOS, TSD and flags

| Operation | Behavior |
|---|---|
| `IOS₅₀ 30000` | Connects/enables flag 50 and sends a trigger pulse to the control panel. The panel determines whether this reaches the converter. |
| TSD | Copies the measurement from the last trigger, through configured permutation paths; performs **no sign extension**. Also sends another panel-routable trigger pulse. |
| Conversion completion | Raises flag 50 after 22 µs. |
| `IOS₅₀ 20000` | Shared disconnect behavior; clears its latched alarm condition. |

Sources: H61:3625–3644; H63:3700–3722; shared alarm clearing H61:3437–3445.

No DATRAC-specific nonzero low mode-word bits are documented. The software-trigger enable is a **manual panel routing control**, not a documented IOS mode bit.

**Transfer alignment:** visual inspection of H63 PDF p. 99 confirms IOB50 below the rightmost two quarters: native low 18 bits, TX-2 2.9–1.1, mask `000000777777`, with no sign extension. The scan establishes this alignment directly.

### 3.3 Missed data and timing constraints

- A trigger arriving before the preceding sample has been transferred by TSD creates **MISAL**.
- Triggers must not be closer than **37 µs**; the manual explicitly warns that faster triggering can damage the circuits.
- Reading at 22 µs and immediately retriggering would violate that minimum interval unless software or trigger routing supplies the additional delay. `[INFERENCE from documented times]`
- Unit 41 reports DATRAC missed data in bit **1.1 / `001`**.
- The generic technical description says a second word in a free-running input replaces the first, loses the first word, and sets MISIND; a device-specific DATRAC replacement/latching sequence beyond the trigger-based rule is not specified here.

Sources: H63:3718–3722; H61:3454; TM2:13145–13167.

### 3.4 Manual controls

| Control / connection | Specification |
|---|---|
| Four trigger inputs | Standard TX-2 in-out transition: −3 V to ground in less than 0.2 µs. |
| Oscillator inputs | 3 V RMS required. |
| Programmed-trigger routing | “Up” connects programmed IOS/TSD triggers to DATRAC; the diagram labels both IOS and TSD. |
| Oscillator | General Radio oscillator is external to the DATRAC system. |
| Signal connector | Cannon XL311: pin 1 shield, pin 2 ground, pin 3 signal. |
| Converter external-trigger connector | Not TX-2 compatible directly; use the control-panel inputs, internally connected to it. |
| Power | Normally not left on. Warm up 5–30 minutes; 30 minutes ensures full stated stability. Turn off after use. |

Sources: H63:3727–3758, PDF p100; H61:3653–3689, PDF p106.

### 3.5 Historical program use and current implementation

The 1958 programming examples include an exercise to acquire DATRAC samples using permutation, treating each sample as a **signed nine-bit value in quarter 1**. It explicitly says to ignore IOS and asks the reader to construct a nine-instruction program. This is historical programming evidence, not a replacement for the later 18-bit format.

Source: `references/text/TX-2_ProgExamp.archive-page-ocr.txt:708–715`, PDF p18.

Implementation:

- `host/devices/datrac.h` implements one signal input, ±1/10/100 V ranges, an 18-bit ones-complement fraction, 22 μs conversion, MISAL for a new trigger with an unread sample at unit-41 mask `001`, and disconnect clearing.
- Panel routing is independent of IOS mode. `dev datrac route programmed 0|1` routes IOS/TSD; `route timer 0|1` routes actual unit-54 terminal-carry pulses; `trigger 1..4` injects one of four panel inputs; `oscillator Hz` connects an external trigger oscillator, with 0 disconnecting it.
- `dev datrac power 0|1` controls power. Status records warm-up seconds and the 30-minute stability mark. The handbook does not prohibit conversion while warming up, so sampling remains available. Initial power OFF and programmed-trigger routing ON are panel defaults labeled `[INFERENCE]`.
- `dev datrac source dc|sine|square|triangle level [Hz offset]` selects an external test signal. DC produces level+offset; other waveforms produce offset+level×waveform. `range 1|10|100` selects the rear-panel range.
- `[INFERENCE]` Ideal nearest rounding saturates at full scale; low-bit noise remains unmodeled. A trigger within 37 μs first applies the unread-sample MISAL rule, then is rejected and increments `tooFast`. Physical damage and digital results after excessive trigger rates are undocumented.
- `tools/test_dev_printanalog.py` uses real SKX/IOS/TSD/STE instructions to check printing, a known square wave, bit layouts, flags, unit-41 alarms, disconnect, and program/timer triggering. `TX2_CLI` selects the CLI executable. No unit-50/51 use was found in the inspected Sketchpad listing, as recorded in §2.5.

The recorded device acceptance passed with `TX2_CLI=build/obj_cli_printanalog/tx2-cli python3 tools/test_dev_printanalog.py`: Xerox printing/frame sync/EIA/run-on; DATRAC known square wave/22 μs/37 μs/MISAL; and IOS/TSD and actual interval-timer triggering. `Device::active()` keeps warm-up, printing, frame sync, paper run-on, conversion, and the external trigger oscillator clocked while the CPU is stopped. Additional checks cover 15-second post-stop run-on, conversion completion, and continuous oscillator sampling.

## 4. Displays — units 56 and 60, including camera

### 4.1 Identity and revision context

- Unit **60**: display no. 1, 1024 × 1024 addressable raster.
- Unit **56**: display no. 2; TM1 March 1961 calls it similar to display no. 1 and “currently not installed.”
- January 1963 Sketchpad equipment lists **two scopes**, each with **7 × 7-inch usable area**, **1024 × 1024 raster**.

Sources: TM1:1840–1845; SP:4381–4382.

The detailed handbook device section is headed **unit 60**. Applying every camera/manual-control detail to unit 56 requires separate evidence; similarity alone is insufficient.

### 4.2 Point format and IOS mode bits

TSD copies point coordinates to the display buffer. Both axes use signed ten-bit ones-complement values, with positive zero and negative zero producing the same centered-origin location. Permutation and activity are allowed.

| Field | TX-2 bits, inclusive | RTL indices |
|---|---|---|
| X | **4.9 through 3.9** | `[35:26]` |
| Y | **2.9 through 1.9** | `[17:8]` |

Sources: H63:4550–4565; H61:4013–4026. RTL index conversion is **[INFERENCE]** from quarter numbering.

| IOS | Low mode bits | Meaning |
|---|---:|---|
| `30000` | `0000` | Connect; centered origin; lowest intensity |
| `30010` | `0010` | 20-µs spot duration |
| `30020` | `0020` | 40-µs spot duration |
| `30030` | `0030` | 80-µs spot duration |
| `30100` | `0100` | Bottom-center origin |
| `30200` | `0200` | Left-center origin |
| `30300` | `0300` | Lower-left origin |
| `30004` | `0004` | Index film; buffer busy until camera return |
| `20000` | — | Disconnect |

The base `30000` duration is **10 µs**. Intensity is controlled by illumination **duration**, not beam-current intensity. Sources: H63:4493–4534; H61:3970–4007.

Bit meanings, derived from the octal masks:

- **1.3 / `0004`**: film-index request.
- **1.4–1.5 / `0030`**: four duration/intensity levels.
- **1.7 / `0100`**: complement Y sign bit, moving origin vertically.
- **1.8 / `0200`**: complement X sign bit, moving origin horizontally.

These bit-number conversions are **[INFERENCE]**; the instruction values and sign-bit complementation mechanism are explicit.

Moved origins automatically complement the relevant coordinate sign bit. The handbook explicitly states that `0777` and `1000` coincide in moved-origin modes. Source: H61:4013–4026.

### 4.3 Timing and display persistence

| Parameter | Evidence |
|---|---|
| Illumination duration | 10, 20, 40 or 80 µs |
| General handbook display speed | 20–80 µs |
| Phosphor persistence | Approximately 2 seconds |
| Required refresh | Points must be repeatedly displayed for viewing |
| Sketchpad operating duration | 20 µs/point |
| Sketchpad appendix general display time | 20–100 µs |
| Sketchpad chapter maximum | Approximately 100,000 points/s |

Sources: H63:4485–4490,4510–4518; SP:1867–1881,4252–4258.

These sources do not establish a single additional fixed “deflection settle time.” Preserve illumination duration as explicit and qualify any additional delay as inferred.

The Sketchpad report states that **each unit has its own buffer register**. Source: SP:4252–4255.

### 4.4 Flags, camera and alarms

- Connecting an unselected scope raises flag 60.
- Each finished output point follows the shared output completion/ready rule.
- Film index keeps the IOB busy until the camera return signal, which raises flag 60.
- Low film causes EIA on `IOS 30004`, raises flag 41 when enabled, lights “End of Film,” and rings a buzzer.
- Low film does not stop the CPU, and the scope/camera can continue to operate.
- With no film remaining, the return signal is absent: buffer remains busy and subsequent TSDs dismiss-and-wait.

Sources: H63:4493–4505,4532–4541; H61:3999–4009.

No numerical camera advance/return interval is specified in these sections.

### 4.5 Manual controls

- ON/OFF pushbuttons: display power comes on after **65 s**.
- Bring power on while the computer is stopped because startup often produces a spurious raise-flag signal.
- Best resolution requires approximately **20 min** of thermal stabilization.
- Camera inversion switch: toward wire = normal; away = vertical inversion to compensate the camera-mount mirror.
- End-of-film light.
- End-of-film acknowledgement silences the buzzer but does **not** clear EIA.
- Manual film index moves one frame.

Sources: H63:4598–4614; H61:4037–4054.

### 4.6 Sketchpad use

`upstream/Sketchpad/sk2.tx2as`:

| Location | Behavior |
|---|---|
| `:5379–5381`, `SQ60A` | Enters sequence 60 and selects `30010`, the 20-µs level. |
| `:5387–5418`, `SQ60I`, `SQ60IC`, `SQ60IS` | Repeated point TSDs, including interlaced traversal of `DISPLAY FILE`. |
| `:5442–5468`, `SQ60D1`, `SQ60FEW` | Direct traversal and repeated displays for small point sets. |
| `:3955–3961`, `TRACK1` | Selects display 60 at `30010`, saves/restores pen state and enables pen 55. |
| `:3978–3991`, `TR1A`–`TR1D` | Displays tracking points. |
| `:4006–4017`, `TR2A`–`TR2D` | Displays/refines tracking points while replacing pen sequence entry addresses. |
| `:4020–4024`, `TR3` | Disconnects pen, selects `30030`, displays `SCPSPL` twice. |

PDF metadata identifies display traversal as part 2 pp126–128 and tracking as pp93–96.

### 4.7 Implemented scopes and camera

`rtl/tx2_io.v` retains independent buffer registers, illumination states, and countdowns for `56` and `60`. Each mode selects 10/20/40/80 μs illumination, coordinate-sign complementation, and completion flags. Both scopes can illuminate concurrently. Camera requests block only `60`. Sources: H63 units 56/60; TR296:4252–4255.

Host CRT events are `[x,y,intensity,unit]`, with a decimal unit number. `scopes` reports each buffer's busy state. `dev scope56 on|off` and `dev scope60 on|off` control power. ON requires 65 seconds; the other scope can continue output. **[INFERENCE]** The host initially treats both scopes as warmed. Twenty-minute thermal stabilization affects physical analog resolution; this digital-coordinate model has no assumed temperature-error curve. Source: H63:4598–4614.

Camera commands are `dev camera low 0|1`, `empty 0|1`, `ack`, `invert 0|1`, `index`, and `us N`. Low film sets EIA/unit-41 flag and starts the buzzer. ACK only silences the buzzer, retaining EIA. Empty film withholds completion and keeps buffer `60` busy until film is available. Each request has independent timing, unaffected by status reports or event clearing. Sources: H63:4493–4505,4532–4541,4598–4614.

**[INFERENCE]** Camera-return duration is undocumented. The default is 100 ms, explicitly adjustable with `us N`. Point timing uses the documented illumination duration without an assumed additional fixed deflection delay. Tests: `tb_io`, `tb_graphics`, `tools/test_dev_rtlio.py`.

## 5. Light pen — unit 55

### 5.1 Interface and mode

| Operation | Meaning |
|---|---|
| `IOS₅₅ 30000` | Connect: permit detected-light events to raise flag 55 |
| `IOS₅₅ 20000` | Disconnect: prevent those flag events |
| TSD | Not used as a pen transfer; treated like a non-I/O sequence operation, with automatic dropout and cycle-left behavior |

Sources: H63:4428–4473, PDF p109.

No coordinate word, assembly mode, character table or additional pen mode bits are specified. Pen position is reconstructed by software using displayed points and the interrupted display sequence.

The handbook explicitly restricts sensitivity to the **intensification period of scope 60** and says it will not work properly with scope 56. Source: H63:4472–4473.

### 5.2 Optical and temporal behavior

The Sketchpad report describes:

- Photodiode plus transistor preamplifier in the pen, connected by coaxial cable.
- Approximately cylindrical field of view, making operation relatively insensitive to distance.
- Amplifier sensitive to the initial **bright blue flash**, not the dim yellow afterglow.
- Output strobed with displayed-point intensification to reduce room-light pickup.
- Each seen point individually reported just after intensification.
- Notification through a sequence-change interrupt into the pen sequence.

Source: SP:1553–1579, PDF p36.

No exact detector latency, maximum detection rate, MISAL or EIA behavior is specified for the pen in the cited sections.

### 5.3 Manual controls

- Pen preamplifier has fixed gain/sensitivity.
- Main-amplifier sensitivity dial is adjusted by trial and error according to scope intensity.
- Toggle should be thrown toward the dial.
- The report’s construction drawing also labels a **shutter**, **button**, and rotating barrel that moves the diode; exact geometry/control action requires viewing PDF p37.

Sources: H63:4455–4470; SP:1592–1610.

### 5.4 1963 configuration revision

The January 1963 equipment inventory states:

> “2 light pens — work with either scope or both on one”

Sources: SP:4367–4369, PDF p97; `Sketchpad_A_Man-Machine_Graphical_Communication_System_Jan63.txt:6797–6800`, PDF p170.

This revises the practical capability described on the July 1961 handbook pen page. **The cited inventory does not identify the second pen’s sequence number or routing controls.** Those details must not be invented.

### 5.5 Sketchpad use

`upstream/Sketchpad/sk2.tx2as`:

| Location | Behavior |
|---|---|
| `:3876` | Installs `LPFIND` in sequence 55. |
| `:3888–3890`, `LPFIND` | Enters pen sequence and connects pen. |
| `:3893–3916`, `LPSEES` | Uses saved sequence-60 state and display-file information to identify the point seen, reject duplicate/invisible points, and collect hits. |
| `:3918–3937` | Maintains observed-point lists. |
| `:3953–3964`, `TRACK1` / `TRACK2` | Saves scope/pen state and enables the tracking interrupt path. |
| `:4029–4063`, `TR55`, `TRLP`, `TRLP2*` | Restores state and uses pen hits to choose tracking branches. |
| `:4064–4070`, `TRLOST` | Disables pen and redirects state when tracking is lost. |

This demonstrates that correct interrupt timing and saved display placekeeper state are essential; direct host delivery of an XY coordinate is not equivalent.

### 5.6 Implemented light-pen wiring

This replica uses the explicit **unit `55`→scope `60` wiring in the November 1963 handbook**. Unit 55 accepts detector pulses only during scope-60 intensification. Host spatial hits and hardware flags use scope-60 coordinates and illumination. Scope-56 points do not count as hits. Each illumination produces at most one detection; afterglow produces none. Sources: H63:4472–4473; TR296:1553–1579.

The January 1963 TR296 appendix records two pens usable with either scope but supplies no second-pen unit number or wiring controls. This configuration difference remains documented. Unit-55 TSD retains ordinary non-I/O cycle-left and dismiss behavior. Original Sketchpad interrupt code reconstructs coordinates. Sources: H63 unit 55; TR296:4367–4369.

Acceptance: `tb_io` checks that scope 56 cannot trigger unit 55. `tools/test_dev_rtlio.py` checks host hit counts and unit tags. `tools/test_sketchpad_functions.py` boots the original tape and uses the original pen program for lines, arcs, moves, and other interactions.

## Remaining visual source checks

Resolved scans and remaining visual checks are:

1. **H63 PDF pp. 99, 101, 103, and 196: resolved.** Buffer layouts and all characters are incorporated in §§2.2, 2.4, and 3.2 and the device code.
2. **`TX2-Memos-General_196407.pdf` pp. 4–5:** later package frame-length units and control code `15`.
3. **SP PDF p. 37:** pen shutter/button/diode-adjustment drawing.

Print and analog devices are implemented. Their CLI acceptance target is `tools/test_dev_printanalog.py`. Display/light-pen status is recorded in the corresponding sections.