#!/usr/bin/env python3
"""Assemble the static browser TX-2 in build/site for hosting on a static web server.

Contents: web/ UI files, build/wasm/tx2.{js,wasm}, license notices, and the paper tape
library in tapes/ with tapes/index.json. Run tools/build_wasm.py first.
"""
import hashlib, json, shutil
from pathlib import Path
import tx2tape

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'build/site'

# Tape library. tsp is the octal CODABO start; every tape boots through the original plugboard.
LIBRARY = [
    {'id': 'hello', 'title': 'HELLO, WORLD', 'source': 'programs/hello.tape', 'tsp': '377750',
     'kind': 'Modern example', 'note': 'Printing program assembled with this project\'s M4 assembler. Lincoln Writer prints three lines of HELLO, WORLD.'},
    {'id': 'display-demo', 'title': 'Display and light-pen diagnostic', 'source': 'programs/display-demo.tape', 'tsp': '377750',
     'kind': 'Modern example', 'note': 'Draws four points on the CRT. Sequence 55 increments a counter when the light pen detects a bright point.'},
    {'id': 'digits', 'title': 'Handwritten Digits · Neural network', 'source': 'programs/digits.tape',
     'tsp': '377750', 'kind': 'Modern program', 'template': 'digits',
     'note': 'Wait for the dot grid, then hold and drag the light pen to write one digit. Press Enter to recognize or Delete to clear. The TX-2 runs a 64 → 32 → 10 neural network and draws the result at the right of the CRT.'},
    {'id': 'sketchpad', 'title': 'Sketchpad · 1963', 'source': 'programs/sketchpad/sketchpad.tape', 'tsp': '377750',
     'kind': 'Historical program reconstructed from listings', 'template': 'sketchpad', 'suppress': '200',
     'note': 'Ivan Sutherland\'s original program, transcribed and reconstructed from CHM listings. Changes are recorded individually in manifest.json. Startup displays INK; aim the light pen at INK to begin tracking. '
             'The program selects devices absent from this machine. Startup automatically suppresses IOSAL, as shown in the console alarm panel.'},
    {'id': 'inchworm', 'title': 'Inchworm · 1958', 'source': 'programs/inchworm.tape', 'tsp': '377750',
     'kind': 'Historical program adapted for paper tape',
     'reference': 'https://bitsavers.org/pdf/mit/tx-2/6M-5780_Some_Examples_of_TX-2_Programming_Jul1958.pdf#page=7',
     'note': 'H. Philip Peterson’s seven-word routine copies itself through core memory, then jumps back and starts again. '
             'The tape loads its original switch-register startup routine into T memory. No CRT output; watch P in the header.'},
    {'id': 'upstream-hello', 'title': 'HELLO · TX-2 Project example tape', 'source': 'upstream/TX-2-simulator/examples/hello.tape',
     'tsp': '377750', 'kind': 'Upstream tape', 'fix': True,
     'note': 'Tape supplied by TX-2-simulator. After tx2tape fix relinks blocks and recomputes checksums, it boots through the original plugboard.'},
]

def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / 'tapes').mkdir(parents=True)
    for f in (ROOT / 'web').iterdir():
        if f.suffix in ('.html', '.css', '.js', '.svg'):
            shutil.copyfile(f, SITE / f.name)
    for name in ('tx2.js', 'tx2.wasm'):
        src = ROOT / 'build/wasm' / name
        if not src.exists():
            raise SystemExit('Missing build/wasm; run tools/build_wasm.py first')
        shutil.copyfile(src, SITE / name)
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(ROOT / name, SITE / name)
    index = []
    for entry in LIBRARY:
        tape = tx2tape.read(ROOT / entry['source'])
        if entry.get('fix'):
            tape, _ = tx2tape.relink(tape)
        (SITE / 'tapes' / f"{entry['id']}.tape").write_bytes(tape)
        meta = {k: v for k, v in entry.items() if k not in ('source', 'fix')}
        meta.update(file=f"tapes/{entry['id']}.tape", lines=len(tape), sha256=hashlib.sha256(tape).hexdigest())
        index.append(meta)
    (SITE / 'tapes/index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    print(f'Built {SITE} with {len(index)} tapes')

if __name__ == '__main__':
    main()
