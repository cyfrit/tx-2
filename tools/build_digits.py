#!/usr/bin/env python3
"""Assemble the DIGITS program, geometry and quantized model into a PETR tape."""
import argparse
import json
import subprocess
from pathlib import Path

import tx2tape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'programs/digits.tx2as'
MODEL = ROOT / 'programs/digits-model.json'
TAPE = ROOT / 'programs/digits.tape'

# Compact seven-segment CRT glyphs. Each lit segment is a row/column of spots.
SEGMENTS = ('abcdef', 'bc', 'abdeg', 'abcdg', 'bcfg', 'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg')


def glyph(digit):
    h = lambda r: {(c, r) for c in range(5)}
    v = lambda c, start: {(c, r) for r in range(start, start + 4)}
    dots = dict(a=h(0), b=v(4, 0), c=v(4, 3), d=h(6), e=v(0, 3), f=v(0, 0), g=h(3))
    return sorted(set.union(*(dots[s] for s in SEGMENTS[digit])), key=lambda p: (p[1], p[0]))


def point(x, y):
    # Display 60 mode 0300 flips the sign bit on both coordinate DACs.
    def axis(v):
        return (v if v >= 0 else 1023 + v) ^ 512
    return (axis(x) << 26) | (axis(y) << 8)


def tables(model):
    w1, b1, w2, b2 = (model[key] for key in ('w1', 'b1', 'w2', 'b2'))
    for data, rows, cols in [(w1, 32, 64), (w2, 10, 32), ([b1], 1, 32), ([b2], 1, 10)]:
        if len(data) != rows or any(len(row) != cols or any(type(v) is not int for v in row) for row in data):
            raise ValueError('Expected integer parameters for a 64 → 32 → 10 network')
    # Bound even partial sums for any binary input, and ensure doubled MULT
    # output fits as a single one's-complement word in B.
    hidden_bounds = [abs(b) + sum(map(abs, row)) for b, row in zip(b1, w1)]
    output_bounds = [2 * (abs(b) + sum(h * abs(w) for h, w in zip(hidden_bounds, row)))
                     for b, row in zip(b2, w2)]
    if max(hidden_bounds) >= 2**35 or 2 * max(output_bounds) >= 2**35:
        raise ValueError('Network exceeds TX-2 signed word range')

    def words(label, values):
        for i, v in enumerate(values):
            encoded = v if v >= 0 else (2**36 - 1) + v
            yield f'{label + "->" if i == 0 else "":12} {encoded:012o}'

    yield '2000|'
    yield from words('GRID', (point(-255 + 30*c, 225 - 30*r) for r in range(16) for c in range(16)))
    tags = [f'GLYPH{digit}' for digit in range(10)]
    yield from (f'{"GLYPHS->" if i == 0 else "":12} {tag}' for i, tag in enumerate(tags))
    for digit, tag in enumerate(tags):
        yield from words(tag, [*(point(285 + c*28, 84 - r*28) for c, r in glyph(digit)), 0])
    yield from words('BIASONE', b1)
    yield from words('WEIGHTONE', (v for row in w1 for v in row))
    yield from words('BIASTWO', (2*v for v in b2))
    yield from words('WEIGHTTWO', (v for row in w2 for v in row))
    yield '☛☛PUNCH 100'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembler', type=Path, default=ROOT / 'upstream/TX-2-simulator/target/debug/tx2m4as')
    parser.add_argument('--output', type=Path, default=TAPE)
    parser.add_argument('--model', type=Path, default=MODEL)
    args = parser.parse_args()
    if not args.assembler.is_file():
        parser.error('build tx2m4as in upstream/TX-2-simulator (cargo build --locked --bin tx2m4as), or use --assembler')
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    source = build / 'digits-expanded.tx2as'
    source.write_text(SOURCE.read_text(encoding='utf-8') + '\n' + '\n'.join(tables(json.loads(args.model.read_text()))) + '\n',
                      encoding='utf-8')
    raw = build / 'digits-raw.tape'
    listing = build / 'digits.list'
    with listing.open('w') as log:
        result = subprocess.run([str(args.assembler.resolve()), '--list', '--output', str(raw), str(source)],
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f'TX-2 assembly failed; see {listing}')
    tape, _ = tx2tape.relink(raw.read_bytes())
    args.output.write_bytes(tape)
    print(f'Wrote {args.output} ({len(tape)} paper lines)')


if __name__ == '__main__':
    main()
