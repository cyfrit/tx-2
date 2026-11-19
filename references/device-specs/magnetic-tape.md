# Magnetic-tape peripheral specification

## 1. Scope, notation, and evidence quality

All unit numbers, modes, addresses, and unqualified integers below are **octal**. Explicit timing values in microseconds and physical speeds are decimal.

Source abbreviations:

| Abbreviation | Repository path |
|---|---|
| **UH63** | `references/text/TX-2_UsersHandbook_Nov63.archive-page-ocr.txt` |
| **UH61** | `references/text/TX2-Users-Handbook_196107.txt` |
| **TM1** | `references/text/LM-44v1_TX-2_Technical_Manual_Volume_1_196105.txt` |
| **TM2** | `references/text/TX-2_TechManVol2_Jun61.archive-page-ocr.txt` |
| **SK** | `upstream/Sketchpad/sk.tx2as` |
| **TR296** | `references/text/Sketchpad_TR296_Jan63.txt` |
| **BEST** | `references/text/A_Computer-Integrated_Rapid_Access_Magnetic_Tape_System_with_Fixed_Address.archive-page-ocr.txt` |

`[INFERENCE]` identifies reconstruction from executable instructions rather than an explicit hardware specification.

**Documentation gap:** the handbook's front matter says the magnetic-tape section is “to come later.” Chapter 6 §6-3.7 describes M4's user-facing storage commands. The unit-046 hardware specification is absent. The technical manual also lists magnetic tape among units omitted from detailed discussion. These editions therefore provide only a partial original mode-bit specification.
Sources: UH63:15–23, 8593–8603; TM2:14159–14202. The upstream simulator independently records this documentation gap in `upstream/TX-2-simulator/OPEN-QUESTIONS.md:61-64`.

## 2. Source inventory

### 2.1 Operationally useful primary sources

| Source | Relevant content and anchors |
|---|---|
| 1963 handbook | General IOS/TSD and flags, UH63:3180–3290; alarm device, :3428–3493; M4 magnetic storage, :8593–8680; device assignment table, PDF p.191. |
| 1961 handbook | Clearer device assignment table: UH61:7540–7588, PDF p.191, assigns IBM tape 045 and TX-2 bulk storage 046. Power instructions: :4598–4611. |
| Technical Manual vol.1 | Physical tape characteristics, TM1:380–403, PDF p.14, printed p.1-8; unit 046 described as bidirectional 9-bit I/O, :1809–1811, PDF p.45. |
| Technical Manual vol.2 | General mode/control/report/TSD semantics, TM2:14651–14934, PDF pp.378–384; mode table Fig.15-12, PDF p.392; alarm wiring, PDF pp.400–402. |
| Sketchpad original listing, part 1 | IOS aliases PDF p.84; alarm/parameter macros pp.97–100; tape search pp.100–104; checksum/read/write macros pp.104–108; IBM code pp.123–130; TX-2 tape code pp.132–135. Transcription anchors throughout this report. |
| Sketchpad thesis TR296 | Operator button meanings, TR296:3677–3684, 3713; contemporary tape performance, :4335–4377, PDF p.97. |

The existing rendered handbook alarm page is readable and was inspected:

`references/figures/devices-p93.png` — UH63 PDF p.93.

The following enlarged listing composite was also inspected:

`references/figures/sketchpad-scan-fixes/io-45it1-tapek3.png`.

It confirms:
- PDF p.124 has `RXF₅₄ 45IT1`, rather than transcription `45SIT1`.
- PDF p.104 uses `TAPEK3`, rather than `TAPER3`.

These corrections already appear in `tools/prepare_sketchpad.py:288-290`. Other existing relevant preparation corrections include `45RSW` → `45RWSW` at SK:6153, documented in `tools/prepare_sketchpad.py:269-270`.

### 2.2 Physical-design and development sources

These establish chronology and physical behavior; they are not interchangeable operating specifications.

| Source | Findings |
|---|---|
| **BEST**, PDF pp.1–5 | Complete early design paper: variable-speed capstanless transport; prerecorded timing channel; redundant tracks; fixed addressing; 9-bit transfers; early speeds and acceleration. BEST:11–35, 47–81, 94–134, 140–175, 281–314, 456–484. |
| `mit-lin-div-6-qpr-56-09.txt` | Initial design description: :2581 onward; two induction motors, magnetic-amplifier control. |
| `mit-lin-div-6-qpr-57-06.txt` | “Magnetic Tape Bulk Storage for TX-2,” :2476–2531, printed pp.42–43. Motors, slow starting/stopping, high-speed search, prerecorded tachometer, relay-selected transports. |
| `mit-lin-div-6-qpr-58-03.txt` | Transport construction and photoelectric end sensing, :2568–2593. |
| `mit-lin-div-6-qpr-58-06.txt` | Appendix describing the tape system, :1412–1640; substantially overlaps BEST, with related figures. |
| `mit-lin-div-6-qpr-58-12.txt` | Redesign to 14-inch reels, wider tape, pancake motors, :1103–1107. |
| `mit-lin-div-5-qpr-59-03.txt` | Electronics under construction; prototype evaluation, :968–1018. |
| `mit-lin-div-5-qpr-59-06.txt` | Electronics assembled; transports not yet delivered; write-to-timing-head crosstalk, :623–632. |
| `mit-lin-div-5-qpr-59-09.txt` | Revised density/capacity and speeds, :731–739. |
| `mit-lin-div-5-qpr-59-12.txt` | Computer-connected operation begun; motion control debugged, read amplifier still being stabilized, :670–678. |
| `TX2-Memos-General_196407.txt` | 19 October 1964 Fastrand memo: drum storage will resemble TX-2 magnetic tape at the system-user level, with about four times capacity, :216–243. This is later system context. |
| `6D-2631_TX-2_Circuitry_Handbook_Oct1958.txt` | Bibliography cites Best/Stockebrand’s fixed-address tape report as **6M-5701**, dated 16 May 1958, :6893–6895. |
| `6D-108-2_SLIDES_VIEWGRAPHS_19571231.txt` | Catalog entries for transport/motor/speed-sensing figures, :4699–4702. |

The broad text searches also found other computers’ IBM and magnetic-tape systems in laboratory progress reports. Those are not evidence for TX-2’s unit-045 interface.

## 3. Common IOS, report, flag, and alarm behavior

### 3.1 Common IOS operations

| Command | Meaning |
|---|---|
| `IOSⱼ 00000` with report bit | Read pre-instruction report. |
| `IOSⱼ 20000` | Disconnect. |
| `IOSⱼ 3xxxx` | Connect and specify operating mode `xxxx`. |
| `IOSⱼ 40000` | Lower sequence flag. |
| `IOSⱼ 50000` | Raise sequence flag. |
| `IOS₄₆ 6xxxx` | Select magnetic-tape subunit; mode must subsequently be specified with `3xxxx`. |

Sources: UH63:3207–3238; TM2:14745–14783.

The report is the state **before** the current IOS changes it. Unused report bits are cleared. Source: UH63:3260–3281.

### 3.2 Standard report fields

| TX-2 bit | Meaning |
|---|---|
| `3.1–3.6` | Reporting unit number |
| `2.9` | Flag |
| `2.8` | Buffer available: 1 = not busy |
| `2.7` | Maintenance |
| `2.6` | Connected |
| `2.5` | Equipment inability |
| `2.4` | Missed-data indicator |
| `1.1–2.3` | Mode/control fields, generally corresponding to mode word |
| `3.7–4.9` | Device-specific fields |

Source: UH63:3266–3281.

### 3.3 TSD and sequence behavior

- Input flag is raised when another datum becomes available.
- Output flag is raised when the device completes its current operation and can accept another datum.
- TSD against a busy device dismisses and waits without advancing the program counter, even when held.
- A normal output connection raises its flag when transitioning from disconnected.
- A lengthy mode change may keep the buffer busy until its completion event raises the flag.

Sources: UH63:3180–3200, 3223–3238; TM2:14854–14915.

For a free-running input device, a new datum can replace unread buffered data and set MISIND. Source: TM2:14912–14930.

### 3.4 Alarm unit 041

The inspected handbook diagram gives these complete alarm-buffer allocations:

| Bit | Octal mask | Condition |
|---|---:|---|
| `1.1` | `001` | Datrac 050 missed data |
| `1.2` | `002` | PETR 052 missed data |
| **`1.3`** | **`004`** | **TX-2 tape 046 missed data** |
| **`1.4`** | **`010`** | **TX-2 tape 046 inability** |
| `1.5` | `020` | Camera 060 inability |
| `1.6` | `040` | Punch 063 inability |
| `1.7` | `100` | Xerox 051 inability |
| `1.8` | `200` | Lincoln Writer 065/066 inability |
| `1.9` | `400` | Lincoln Writer 071/072 inability |

Source: UH63 PDF p.93, `references/figures/devices-p93.png`.

`IOS₄₁ 30000` connects alarm reporting and programmatically suppresses the machine-stopping missed-data alarm. TSD reports alarms without clearing them. Another alarm updates the report but does not produce another flag until the original condition is cleared. The handbook diagram does **not** allocate unit 045 its own alarm-report bit.  
Sources: UH63:3432–3438, 3482–3493; diagram cited above.

## 4. TX-2 variable-speed addressable tape — unit 046

### 4.1 Identity and transport organization

- Unit **046** is the magnetic-tape bulk-storage channel. Source: UH61:7562–7564.
- Handbook introduction describes **four transports**, initially manually selected, about two million words each. Source: UH63:3016–3018.
- The earlier TM1 description calls 046 not yet installed and specifies 9-bit characters read or written in either direction. Source: TM1:1809–1811.
- December 1962 Sketchpad statistics say **two units in use, ten planned**, over two million words/approximately seventy million bits per transport. Source: TR296:4353–4356.

These describe different dates/configurations.

### 4.2 IOS words actually used by Sketchpad

The following are direct listing constants or direct instruction operands:

| Mode/command | Listing meaning |
|---|---|
| `30000` | `RLF0`: read lines, forward, speed code 0 |
| `30100` | `RMF0`: read marks, forward, speed code 0 |
| `30020` | `RLF2`: read lines, forward, speed code 2 |
| `30120` | Read marks, forward, speed code 2 |
| `30130` | `RMF3`: read marks, forward, speed code 3 |
| `30400` | `WLF0`: write lines, forward, speed code 0 |
| `34000` plus retained mode | Clear error |
| `36200` | Search initialization command, comment: clear alarms/change RS/move tape |
| `34200` | Second search initialization command with same comment |
| `60000 + SELECT` | Select tape |
| `20000` | Disconnect |

Sources:
- SK:4455, 4460–4467, 4505–4508.
- SK:4686, 4703, 4726–4732.
- SK:4803–4805, 4818, 4837.
- SK:4870.
- SK:6235–6239, 6264.

From the search definitions:

| Octal component | Meaning established by listing |
|---:|---|
| `00004` | Reverse |
| `00010` | Speed 1 |
| `00020` | Speed 2 |
| `00030` | Speed 3 |
| `00040` | Speed 4 |
| `00100` | Read marks instead of lines |
| `00400` | Write lines instead of read lines |
| `04000` | Clear error in the observed `34000` operation |

Sources: SK:4455, 4460–4467, 4662–4680; write/read mode operands above.

**Unresolved exact bit semantics:** the distinct roles of `00200` and `02000` in `36200`/`34200`, the complete `SELECT` encoding, and the remaining mode bits. The listing supplies the command words but insufficient definitions to assign those bits independently.

**Scan evidence, TM2 PDF p. 392, Fig. 15-12:** enlargement identifies `00002` as ASSEMBLY,
`00004` as REVERSE, `00010/00020/00040` as SP₀/SP₁/SP₂, and `00100/00200/00400` as F₀/F₁/FL.
`01000` is SBA, `02000` is RS, and `04000` is spare in this 1961 figure.
The low nine bits of `IOS 6xxxx` are labeled SER₁–SER₉, establishing selection-register width. Decoding for the four transports remains unspecified.
Full circuit behavior for F₁, SBA, and RS is unresolved. The 1963 program uses `04000` to clear errors; this revision difference is preserved.

#### Complete generated search mode combinations

The search tables generate line/mark pairs at all five speed codes in both directions:

| Speed | Forward lines | Forward marks | Reverse lines | Reverse marks |
|---:|---:|---:|---:|---:|
| 0 | `30000` | `30100` | `30004` | `30104` |
| 1 | `30010` | `30110` | `30014` | `30114` |
| 2 | `30020` | `30120` | `30024` | `30124` |
| 3 | `30030` | `30130` | `30034` | `30134` |
| 4 | `30040` | `30140` | `30044` | `30144` |

Source: SK:4460–4467, 4662–4680. The expanded numeric values are arithmetic reconstruction of those constants.

### 4.3 Unit-046 report fields required by Sketchpad

| Bit | Listing interpretation | Actual use |
|---|---|---|
| `1.3` | Reverse mode/direction | Tested to interpret saved position/report |
| `1.9` | Writing | Enables write-specific error interpretation |
| `2.4` | MIS | Error-message table |
| `2.5` | EIA | Error-message table |
| `3.7` | “Operable speed?” | **Associated instruction is `SKU`, unconditional** |
| `3.8` | MPD | Write-specific error |
| `3.9` | TOF | Write-specific error |
| `4.3` | Selection complete | Must become **1** for search to proceed |
| `4.4` | “BM passed?” | **Associated instruction is `SKU`, unconditional** |
| `4.5` | KEY | Write-specific error |
| `4.6` | LTO / “unit ready?” | Search treats **1** as error |
| `4.7` | NMO | Error |
| `4.8` | FET / forward end of tape | 1 makes search choose reverse |
| `4.9` | RET / reverse end of tape | 1 makes search choose forward |

Sources:
- SK:4350, 4363, 4368–4381.
- SK:4500–4516, 4518.
- SK:4843–4845.
- `SKU` semantics: UH63:1218–1231.

**Critical detail:** `SKU₃.₇ E` and `SKU₄.₄ E` do not inspect those bits. Treating them as conditional status polling would invent behavior absent from the program.

The named error abbreviations above are preserved verbatim. Their full English expansions are not established by the inspected sources.

### 4.4 TSD width, quarter placement, and assembly

**Observed Sketchpad protocol: normal transfers of one 9-bit value per TSD.** The program explicitly builds words using standard quarter configurations:

| TSD configuration | Input destination / output source |
|---:|---|
| `³TSD` | Quarter 1 |
| `⁴TSD` | Quarter 2 |
| `⁵TSD` | Quarter 3 |
| `⁶TSD` | Quarter 4 |

The forward data word order is **q4, q3, q2, q1**.  
Sources: SK:4820–4829, 6236–6259; standard configuration table UH61 PDF p.192, UH61:7600–7648.

`[INFERENCE]` Host normal-input representation for these operations should therefore be the nine-bit datum in bits `1.1–1.9`, mask `000000000777`; CPU configuration performs quarter placement.

**Historical assembly capability also exists:** TM2 describes normal mode plus forward/reverse assembly, both input and output; nine-bit assembly data are splayed every fourth bit of the 36-bit word.  
Sources: TM2:14662–14676, 14844–14851.

Enlargement of TM2 Fig. 15-12, PDF p. 392, confirms assembly enable `00002`, bit 1.2.
Each channel occupies every fourth bit, with rotation controlled by direction. Sketchpad's observed read/write paths use normal mode.

### 4.5 Address and mark protocol

The listing separates **coarse marks**, **fine marks**, and data lines.

- Mark-read mode supplies a coarse mark.
- The program switches to line-read mode to obtain a fine mark.
- Coarse and fine pieces form the address.
- Successive block addresses differ by **`010`**, rather than `1`.

Sources: SK:4547, 4571–4581; SK:4802–4811; SK:6235–6243, 6268–6272.

`[INFERENCE]` In the forward reader, coarse mark goes to q4 and fine mark to q3; the combined 18-bit address is therefore:

```text
address = (coarse_9_bits << 9) | fine_9_bits
```

Source: `⁶TSD B` / `⁵TSD B`, SK:6236–6240.

**Low address bits, `[INFERENCE]`:** `BLOCK MARK=6` at SK:3658. `TX2TOGCHK` uses `³ITE` to AND
the low address quarter with `7`, then `⁴SED` to compare it with `TX2IK` quarter 2, containing `6`, at SK:6310–6313.
The standard configuration moves quarter 2 to the low quarter for comparison, so valid block addresses have low three bits `6`.
Preformatted addresses are `6 + 010 × block_index`: the first block is `000006`, and `006006` identifies block `600`.
Acceptance sets toggle 27 to `372023,,006006`. This reconstructs software-visible address labels; physical mark-track encoding remains unresolved.

The search routine:
- predicts the next address;
- compares marks against that prediction;
- ignores negative coarse marks in its high-speed loop;
- uses predicted position on the negative-mark path in its slow loop;
- changes speed and direction based on distance from target.

Sources: SK:4546–4558, 4571–4589, 4597–4639.

Search-distance constants are:

| Constant | Octal value |
|---|---:|
| `TAPEK1` | `300` |
| `TAPEK2` | `1500` |
| `TAPEK3` | `3000` |
| `TAPEK4` | `20000` |

Source: SK:4468–4471, 4651–4661. These are search-control distances, not physical tape-speed values.

### 4.6 Data-block stream and checksums

#### Forward read

`TX2RD1`/`TX2GBM` consume:

```text
coarse mark
switch to read-lines
fine mark
dummy slot
checksum prologue high 9 bits
checksum prologue low 9 bits
0200 words × (q4, q3, q2, q1)
checksum trailer high 9 bits
checksum trailer low 9 bits
switch to read-marks
```

Sources: SK:6235–6272.

The body contains **`0200` 36-bit words = 128 decimal words**. The counter starts at negative `0177`; JNX senses the old index, then increments, yielding 128 transfers through this loop.  
Sources: SK:6249–6265; JNX ordering UH63:925–963.

#### Forward write

`WRMAINLOOP`:
1. Enters `30400` write-lines mode.
2. Initializes the 18-bit checksum accumulator to negative zero.
3. Writes two all-one nine-bit prologue pieces.
4. Writes 128 complete words, q4 → q3 → q2 → q1.
5. Adds both 18-bit halves of every word into the checksum accumulator.
6. Complements the accumulated checksum.
7. Writes its high and low nine-bit pieces.
8. Returns to read-lines mode.
9. Consumes boundary slots annotated **dummy, fine mark, coarse mark, fine mark**.
10. Starts the next body or exits.

Sources: SK:4818–4847.

When data end partway through a block, the remaining words are padded with zero. Source: SK:4860–4863. The handbook independently says partially filled M4 binary blocks are zero-filled: UH63:8650–8659.

`[INFERENCE]` A clean block’s 18-bit checksum is the one’s complement of the 18-bit ring sum of all body halfwords. The all-one prologue is negative zero and is neutral under this arithmetic. Readers add prologue, body halfwords, and trailer, accepting either zero representation.

Sources: SK:4819–4836, 6246–6272; 18-bit ring-sum definition UH63:630–636.

**Boundary representation matters:** a host cannot treat every 9-bit event as body data. It needs mark/line event classes and the fine/dummy boundary slots consumed above. `WR2` explicitly says **“DO NOT WRITE BLOCK MARKS.”** Source: SK:4788–4790.

#### Verification after writes

The `WR` macro searches, writes, checksum-reads the written span in reverse, checksum-reads forward again, and compares cumulative read/write checksums. Source: SK:4868–4886.

The host must support reverse mark/line reading for this path. The dedicated checksum reader is SK:4714–4785, original PDF pp.105–106.

### 4.7 Sketchpad object header

`TX2WR` writes a Sketchpad identification in the left half of `LIST`:

```text
333427 ,, length
```

Source: SK:6137–6143.

`TX2RD3` checks this identification, derives the destination limit from the length, and rejects a destination extending to `100000` or beyond. Source: SK:6287–6305.

`[INFERENCE]` A host image intended for the Sketchpad library reader must preserve this header as part of the stored word stream; returning only drawing payload would fail identification/length handling.

The library address comes from toggle register 27, memory address `377727`; it is masked/validated against `TX2IK`. Sources: SK:3853–3855, 6307–6313; operator description TR296:3681–3684.

### 4.8 Error and flag paths

Search connects alarm unit 041 and installs a tape-specific alarm handler. Source: SK:4491–4494, 4512.

`TAFIOA`:
- reads unit-046 report;
- preserves its mode for the clear operation;
- routes an inability indication into the general error path;
- otherwise uses `34000` with retained mode and dismisses.

Source: SK:4449–4456. The comment “MISAL?” at the test of bit `2.5` conflicts with the standard report assignment, where `2.5` is EIA; the instruction/bit assignment should govern.

The main error table handles MIS, LTO, TOF, KEY, MPD, FET, RET, NMO, and EIA. TOF/KEY/MPD entries are filtered when the saved report says the tape was not writing. Source: SK:4352–4381.

`TURNOFF` reports and disconnects tape, then lowers flag 041. Source: SK:4440–4445.

### 4.9 Timing and manual controls

TM1 gives:

| Controlled speed, inches/sec | 9-bit transfer period, µs |
|---:|---:|
| 35 | 214 |
| 60 | 125 |
| 150 | 50 |
| 300 | 25 |
| Full bore 320–1000 | 23–7.5 |

The same table specifies three information channels, 400 bits/inch/channel, block-mark channel, and an 800-flux-reversal/inch timing track. Source: TM1:380–403.

**Do not assign this table’s rows to Sketchpad speed codes without additional evidence.** The code establishes five numeric speed codes, but the readable sources do not establish the exact code-to-physical-speed correspondence.

Other documented versions:
- Early BEST design: 30–100 ips read/write; search 920 ips; acceleration 0.5–1.5 seconds; reaching 30 ips consumes about 7.5 inches and 0.5 seconds. BEST:59–65, 146–151.
- September 1959: read speeds 30/50/100/300 ips; write speed 50 ips; search up to 900 ips. `mit-lin-div-5-qpr-59-09.txt:735-739`.
- December 1962: selectable 60–300 ips, search 1000 ips, approximately 1600–8000 words/sec. TR296:4353–4357.
- TR296 prose also states read in either direction at 60–600 ips and search up to 1200 ips; preserve this discrepancy rather than silently merging it with its statistics table. TR296:4335–4342.

Manual evidence:
- Initially manually selected transports: UH63:3016–3018.
- Transparent leaders sensed photoelectrically: BEST:298–314.
- Handbook shutdown says position TX-2 tape at the indicated zero address before switching off; OCR reads “NAT 0000” in UH61 and “MAT 0000” in UH63. Exact panel spelling requires visual confirmation. UH61:4609–4611; UH63:5297–5303.
- KEY and inability-related indicators are visible to software, but a complete manual-panel switch description is absent from the readable material.

## 5. IBM magnetic tape — unit 045

### 5.1 Identity and operator behavior

Unit **045** is IBM magnetic tape. Source: UH61:7562.

TR296 identifies an IBM 729 **M6**; the longer Sketchpad thesis edition identifies **M5**. This is a source/version discrepancy.  
Sources: TR296:4364, 4377; `Sketchpad_A_Man-Machine_Graphical_Communication_System_Jan63.txt:6792,6816`.

Sketchpad:
- IBM button bit **4.3** reads a record selected by toggle 26.
- Meta plus IBM writes.
- The typewriter confirms completion.

Sources: TR296:3677–3680, 3713; dispatch SK:950–979.

Entry points:

| Entry | Routine |
|---|---|
| `200120` | `RIBM` → `45SR` |
| `200121` | `RIBMN` → `45SRN` |
| `200122` | `WIBM` → `45SW` |
| `200123` | `WIBMN` → `45SWN` |
| `200124` | `RGARB` → `45GARB` |

Source: SK:4899–4904.

### 5.2 Complete observed IOS command set

The aliases are defined by addition to one IOS instruction:

| Alias | Command | Listing comment |
|---|---:|---|
| `45RWD` | `IOS₄₅ 30010` | Low density, odd parity, rewind |
| `45STM` | `IOS₄₅ 30011` | Sense tape mark |
| `45GFR` | `IOS₄₅ 30012` | Go forward, read |
| `45SRM` | `IOS₄₅ 30013` | Stop, read mode |
| `45GF` | `IOS₄₅ 30014` | Go forward |
| `45GFW` | `IOS₄₅ 30015` | Go forward, write |
| `45REV` | `IOS₄₅ 30016` | Read reverse |
| `45WCS` | `IOS₄₅ 30017` | Write check, stop |

Source: SK:3628–3635.

This establishes operation codes `0–7` in the low three bits with `010` retained for the observed low-density/odd-parity regime. It does **not** establish independent density/parity bits or alternative density/parity combinations.

`45STM` is defined but is not used by the inspected `45*` code.

Disconnect is `IOS₄₅ 20000`. Source: SK:6027.

### 5.3 TSD format: 18-bit halfwords

`[INFERENCE]` Unit 045 transfers an **18-bit halfword per TSD** in the normal mode used here.

Evidence:
- `45WR` sends the left half of the header through `²TSD`.
- `45COMMON` sends/reads the right half through `¹TSD`.
- The body loop transfers every 36-bit word with `²TSD` followed by `¹TSD`.
- Checksum sums these two 18-bit halves separately.

Sources: SK:5751–5776, 5904–5913.

A suitable normal-input mask is therefore the low 18 bits, `000000777777`, with CPU configurations placing each half.

The listing does not establish the physical ordering of IBM six-bit tape characters within one 18-bit transfer. A physical-media image implementation needs that missing controller specification; an abstract halfword-record model can preserve the observed software interface.

### 5.4 Record layout

Let `N` be the right half of the header at `45LIST`, including the header word itself.

`[INFERENCE]` The observed forward record stream is:

```text
18-bit identifier
18-bit length N
N-1 body words, each high 18 then low 18
18-bit dummy slot
18-bit checksum
record-ending gap
```

Sources: SK:5745–5778, 5786–5794, 5911–5920.

The `N-1` count follows from the body-loop setup and the documented JNX sense-before-increment behavior. Sources: SK:5756–5776; UH63:925–963.

The identifier is checked against the selected record number in the left half of `45LIST`. Sources: SK:5690–5694, 5745–5750.

The dummy slot is transferred through `TSD E`; its value is not included in checksum accumulation. Sources: SK:5777–5779, 5914–5917.

### 5.5 Checksum

The 18-bit checksum starts as:

```text
identifier + length
```

Then each body word contributes its high and low 18-bit halves. Writing emits the complement of the result. Reading adds the recorded checksum and accepts a zero result, testing both positive and negative nonzero outcomes.  
Sources: SK:5755–5757, 5769–5775, 5787–5793, 5914–5918.

`AUX` uses an 18-bit ring sum. Source: UH63:630–636.

Thus, `[INFERENCE]`:

```text
checksum = complement18(
    ring_sum18(identifier, length, all body halfwords)
)
```

Hardware IBM parity/LRC generation and checking are separate from this software checksum. Their exact TX-2-controller treatment is not specified by the inspected sources.

### 5.6 Positioning, record gaps, and read-after-write

`45CURRENT` tracks logical position:
- explicit-number entries use toggle register `377726`;
- the `N` variants use current position;
- rewind resets current position;
- forward/reverse scans update it per record.

Sources: SK:3641, 5688–5712, 5732–5735, 5934–5941, 5972–5979.

Forward spacing:
1. `45GF`.
2. Wait for initial motion/gap traversal.
3. `45GFR`.
4. Consume TSD halfwords.
5. Reset/restart interval timer after each.
6. A sufficiently long absence of data transfers ends the record.
7. `45SRM`, settle, update position.

Sources: SK:5713–5735, 5992–5996.

Reverse spacing similarly uses `45REV`, per-transfer timer resetting, and an end-of-record timeout. Sources: SK:5925–5941, 6000–6004.

**Consequently the host must preserve a real no-data interval at record boundaries.** Returning an immediate next-record stream prevents the program’s gap detector from firing.

After writing:
- `45WCS` ends/checks the record.
- Report bit `1.9` is tested for EOT; 1 enters error handling.
- The program backs up over the record.
- `45SC` rereads and compares data/checksum.

Sources: SK:5919–5928, 5947–5971.

### 5.7 Timing expected by Sketchpad

The delay macro takes microseconds and uses interval-timer unit 054. Source: SK:4005–4020.

| Operation/path | Delay, decimal µs | Source |
|---|---:|---|
| Forward start, ordinary | 3,160 | SK:5716, 5739 |
| First/long forward start after latch reset | 16,000 | SK:5717–5718, 5740–5741 |
| Stop after forward record spacing | 1,300 | SK:5726–5727 |
| Post-read settle | 1,516 | SK:5794 |
| Write start, ordinary | 5,000 | SK:5906 |
| First/long write start | 76,000 | SK:5907–5908 |
| Post write-check stop | 3,516 | SK:5923 |
| Direction-change waits | 11,160 | SK:5927, 5941 |
| Reverse run-out before stop | 2,000 | SK:5934 |
| Reverse stop settle | 1,300 | SK:5935–5936 |
| Rewind wait | 31,600 | SK:5978–5979 |
| Error-path stop wait | 20,000 | SK:6022–6023 |

The “long” behavior is controlled by `45LPSW`. `SNN` tests the previous bit and sets it; rewind clears it. Sources: SK:3636, 5717–5718, 5907–5908, 5976; SNN definition UH63:1235–1245.

Record-gap handlers load the interval timer from the two halves of `{400.,,200.}`:
- forward/reverse spacing selects the 200 µs half;
- full read/write failure watchdog selects the 400 µs half.

Sources: SK:5992–6008.

These are **program delays/watchdogs**, not proof of an IBM model’s rated start/stop specification. No reliable characters-per-second value for this TX-2 IBM controller was recovered.

### 5.8 Garbage recovery and error behavior

`45GARB`:
- sets garbage-search mode;
- resets logical current position;
- searches forward;
- skips records whose identifier does not match;
- reads the matching record.

Sources: SK:5668–5672, 5704–5705, 5745–5750.

`45ERR`:
- stops in read mode;
- waits 20,000 µs;
- invalidates position;
- rewinds;
- waits 31,600 µs;
- disconnects;
- prints an error indication.

Source: SK:6021–6030.

The code disconnects alarm unit 041 while initializing IBM operations. Source: SK:5697. The inspected handbook alarm table supplies no unit-045 alarm bit; precise IBM missed-data/inability reporting remains undocumented.

Manual evidence: IBM transports have their own power switches. Source: UH61:4603–4611. A complete load/online/write-enable/operator-panel specification was not found.

No IBM character-code translation table appears in these routines. They transfer binary halfwords.

## 6. Implemented controller models and operation

`host/devices/magnetic_tape.h` provides `magtape` for 046 and `ibmtape` for 045, connected through
`host/devices/all.h` to the shared CLI/WebAssembly bus. The browser tape page supports creating, loading,
saving, rewinding, ejecting, and write-protecting media. Actual IOS/TSD instructions transfer machine data.

### 6.1 TX-2 addressable tape

- Four independent transports retain position, preformatted block boundaries, and write protection. Source: UH63:3016–3018.
- Normal transfers use nine bits. Forward/reverse line reads, coarse-mark reads, and data writes preserve position across mode changes.
- `00002` enables nine-channel assembly with every-fourth-bit placement and direction-dependent rotation. Sources: TM2 Fig. 15-12 and :14662–14676. Channel starting phase is `[INFERENCE]`.
- The 128-word blocks preserve prologue/trailer checksums, fine marks, dummy slots, and forward/reverse checksum-read sequences. Sources: SK:4714–4847, 6235–6278.
- `IOS 6xxxx` only selects a tape. Report bit 4.3 signals selection completion. Mapping the low two bits to four transports is `[INFERENCE]`; the full encoding remains a source gap in §8.
- Input and output buffers run from an independent physical-transfer clock. Unread-input overwrite or output underrun sets MISIND. Missing media and write-protected writes set EIA. Underrun leaves the previous cell unchanged as `[INFERENCE]`, since the resulting physical magnetization is undocumented. RTL aggregates unit-041 report bits 004/010. `34000` clears alarms. Sources: UH63 PDF p. 93, TM2:14854–14915, SK:4449–4456.
- The default line period is 125 μs, from TM1:380–403 at 60 ips. Speed codes are retained and use the same default period as `[INFERENCE]`; the speed-code/physical-speed mapping is unknown. `dev magtape us N` sets the simulation period in decimal microseconds.

### 6.2 IBM tape

- `30010–30017` retain the listing's rewind, forward motion, read, write, reverse-read, and write-check-stop operations.
- Records preserve raw 18-bit halfwords. TSD performs forward/reverse reads and reverse verification after writing. Source: SK:5713–6007.
- Record boundaries produce a 16 ms no-data gap as `[INFERENCE]`, continuing to the next record if motion remains active. This conservative interval accommodates the listing's 200 μs gap detector and 2 ms reverse run-out delay. Sources: SK:5934, 5992–6007. The physical gap rating is unresolved.
- Output uses a buffer and independent halfword clock. GFW keeps an idle buffer available, the first TSD begins a record, and WCS drains the final buffer and ends the record. Rewind completion generates one control/output-ready edge to resume the sequence, preventing repeated input-ready wakeups during unit-045 delays. Sources: SK:5905–5911, 5978–5979; scheduling details are `[INFERENCE]`.
- The default halfword period is 125 μs as `[INFERENCE]`, within the listing's 400 μs watchdog. `dev ibmtape us N` changes it. The IBM 729 controller's actual rate remains undocumented.
- The physical tape-mark format and `30011` report are unresolved. The model retains the operation state without generating an assumed report word. Hardware parity/LRC and EOT capacity also lack complete interface evidence.

### 6.3 Portable images and CLI commands

Device-command numbers are octal except periods. `load/save` use the CLI host filesystem;
the browser uploads/downloads the same text format through `import/export`.

```text
dev magtape create 0             # Create blank preformatted tape in drive 0
dev magtape create 1 100         # Specify the block count
dev magtape save 0 picture.tx2mt
dev magtape load 0 picture.tx2mt
dev magtape rewind 0
dev magtape protect 0 1
dev magtape eject 0
dev magtape status
dev ibmtape create
dev ibmtape save picture.tx2ibm
dev ibmtape load picture.tx2ibm
dev ibmtape rewind
dev ibmtape protect 1
dev ibmtape eject
dev ibmtape status
```

Loading, ejecting, rewinding, and write-protection changes require unit 046 to be disconnected and unit 045 to be stopped, preserving media in active program use.
Unit 045 can remain logically connected after stopping, as in SK:5790. Allowing media replacement in that state is `[INFERENCE]`. Saving/exporting is a read-only host operation available at any time.
After `TX2MT1 block_count`, each `B block_index 516_nine_bit_values` line stores a written block: two prologue checksum pieces, 512 body pieces, and two trailer pieces.
Unwritten blocks implicitly contain zero body data, an all-one prologue, and a zero trailer. After `TX2IBM1`, each `R halfword_count halfwords...` line stores one record.
Both formats end with `END` and use octal numbers. Preformatted addresses reconstruct block marks, which data writes cannot overwrite.
These images represent controller-level transfers. Physical flux and track formats remain unresolved.

### 6.4 Acceptance

`tools/test_dev_magtape.py` uses short hand-encoded TX-2 programs to check IOS selection/reports, forward/reverse TSD,
nine/eighteen-bit widths, block boundaries, image round trips, MISIND/041/clear behavior, and write-protection EIA. Actual Sketchpad
then saves, deletes, reloads, and redisplays geometry through IBM and TX-2 tape. Set `TX2_CLI` to select a private build.
LIBRARY is the original read button. The test writes through the callable TX2WR entry at `200127`, then reads through the original LIBRARY/TX2RD path.
Sources: TR296:3681–3684; SK:4907–4908.
The main listing's `RDTX2=126` on PDF p. 14 conflicts with T-memory entry `200126` on PDF p. 109.
A handwritten BUILD note on PDF p. 23 explicitly gives `RDTX2=200126`, transcription line 790. The preparation script applies this relocation
and classifies it as inferred. The original automatic linking mechanism remains unknown.
The transcription explicitly guesses `³TSD B` for the low trailer-checksum piece in `TX2RD2`, SK:6264, PDF p. 134.
The preceding `⁶TSD B` has already placed the high piece in q4, and the following `²ADD B` uses the left half, requiring the low piece in q3 through `⁵TSD B`.
The blurred scan resembles 3. The preparation script classifies `³→⁵` as inferred, matching the writer's paired checksum pieces at SK:4834–4836, PDF p. 107.
Acceptance executes the original software checksum and error paths. Checksum decisions remain within the TX-2 program.

The recorded complete acceptance passed: both 045 and 046 saved line `(-128,110) → (-40,160)`, then restored the same geometry after deletion.
The runs produced 806 and 97 CRT points respectively, with one line restored in each model. Reload uses the `45MERGE` path at SK:6041–6080.
DELETE was observed retaining point master blocks, allowing same-coordinate points to coexist after reload. Acceptance compares visible entity counts and coordinate sets.
Low-level acceptance also covers 9×4 assembly transfers and unit-041 tape alarm bits. The complete command output contains three PASS results.


## 7. Host-model behavior required to satisfy the observed programs

`[INFERENCE]` The reachable software contract is:

### Unit 046

- Independent drive selection, mode, physical position, and buffered event.
- Pre-instruction reports with selection complete eventually set.
- Mark and line event streams, preserving coarse/fine/dummy/data/checksum distinctions.
- Nine-bit normal TSD values.
- Forward and reverse reads.
- Search speed codes and direction changes without resetting position.
- Existing preformatted block marks preserved during writes.
- 128-word data blocks, zero padding, checksum prologue/trailer.
- Continued motion/events consistent with program-selected mode, plus missed-data/inability reporting.
- End-of-tape reports with direction-dependent behavior.
- Error-clear operation compatible with `34000` and retained mode.

### Unit 045

- Commands `30010–30017` with the meanings listed above.
- Eighteen-bit normal TSD values.
- Abstract records containing header, `N-1` words, dummy halfword, checksum.
- Forward/reverse spacing and rewind.
- Data-unavailable intervals at record boundaries sufficient for the 200 µs gap detector.
- Normal data delivery frequent enough for the 400 µs watchdog.
- Write-end/check-stop and immediate subsequent reverse/reread verification.
- EOT indication in report bit `1.9`.
- Preserve binary information without character translation.

## 8. Exact remaining source gaps

The following cannot be specified exactly from the available readable evidence:

1. Complete semantics of unit-046 F₁ `00200`, SBA `01000`, and RS `02000`; the revision difference for `04000` between 1961 Fig. 15-12 and the 1963 program.
2. Full tape-subunit selection encoding and physical transport-number mapping.
3. Exact mapping from Sketchpad speed codes 0–4 to physical speed.
4. Complete reverse-direction mark/data permutation and physical address-mark encoding.
5. Full meanings and hardware causation of MPD, TOF, KEY, LTO, NMO.
6. Unit-045 density/parity alternatives, physical six-bit-character packing within an 18-bit transfer, parity/LRC details, alarm wiring, rated character timing, and manual panel.
7. Physical tape-mark encoding and unit-045 `30011` result format.
8. Exact power-panel zero-address label spelling.

The remaining primary-source targets are the omitted unit-046 handbook section and the unit-045 controller description. TM2 Fig. 15-12 has been enlarged and inspected directly.
Unresolved choices are identified by `[INFERENCE]` comments in the implementation or explicitly documented here.