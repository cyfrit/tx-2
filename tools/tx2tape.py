#!/usr/bin/env python3
"""TX-2 paper tape files (.tape) and tape tools.

Format: one byte per tape line, in reading order (bin end first).
  bit 0-5  data channels 1-6 (1 = hole)
  bit 6    seventh hole
  bit 7    feed hole: 1 = a punched line exists; 0x80 alone is blank tape
Files written by the upstream TX-2-simulator assembler (every byte 1 0 dddddd)
are valid .tape files as-is. Metadata lives in a sidecar '<name>.tape.json'.

Subcommands:
  info FILE                 lines, 7th-hole/blank counts, reader-leader blocks and checksums
  dump FILE [--words]       octal line listing (or splayed 36-bit words)
  convert IN OUT            .paper.hex text (one 6-bit hex value per line) or .tape -> .tape
  text OUT TEXT|-           encode text as Lincoln Writer codes with 7th holes (off-line LW tape)
  fix IN OUT                relink blocks / recompute checksums of an upstream tx2m4as tape
  splice OUT IN...          concatenate tapes
  words OUT ADDR WORD...    build a loadable tape: standard reader leader + one checksummed block
"""
import argparse, json, sys
from pathlib import Path

FEED, SEVENTH, DATA = 0x80, 0x40, 0x3f
MASK18 = (1 << 18) - 1
ROOT = Path(__file__).resolve().parents[1]

def read(path):
    """Return the raw tape bytes; accepts .tape or legacy .paper.hex text."""
    path = Path(path)
    if path.suffix == '.hex':
        return bytes(FEED | (int(v, 16) & DATA) for v in path.read_text().split())
    return path.read_bytes()

def write(path, lines):
    Path(path).write_bytes(bytes(lines))

def data_lines(tape):
    """Lines the reader delivers: punched lines (feed hole present), 6 data bits."""
    return [b & DATA for b in tape if b & FEED]

def splay(word):
    """36-bit word -> six assembly-mode lines (PETR/punch assembly order)."""
    return [sum(((word >> (6 * bit + col)) & 1) << bit for bit in range(6)) for col in range(5, -1, -1)]

def unsplay(lines):
    word = 0
    for col, line in enumerate(lines):
        for bit in range(6):
            word |= ((line >> bit) & 1) << (6 * bit + 5 - col)
    return word

def words(tape):
    lines = data_lines(tape)
    return [unsplay(lines[i:i + 6]) for i in range(0, len(lines) - 5, 6)]

def blocks(tape, leader_words=20):
    """Parse reader-leader blocks: header (-(n-1), end), n words, trailer (checksum, next)."""
    ws = words(tape)
    pos, out = leader_words, []
    while pos < len(ws):
        field = ws[pos] >> 18
        signed = field if field < 1 << 17 else -((~field) & MASK18)
        count = 1 - signed
        end = ws[pos] & MASK18
        if count <= 0 or pos + count + 1 >= len(ws):
            out.append({'word': pos, 'error': 'invalid or truncated block'}); break
        trailer = ws[pos + count + 1]
        halves = [h for w in ws[pos:pos + count + 1] for h in (w >> 18, w & MASK18)]
        ok = (sum(halves) + (trailer >> 18) + (trailer & MASK18)) % MASK18 == 0
        out.append({'word': pos, 'start': end - count + 1, 'count': count, 'next': trailer & MASK18, 'checksum_ok': ok})
        pos += count + 2
    return out

def build_block(start, body, next_address):
    header = (((1 - len(body)) % MASK18) << 18) | (start + len(body) - 1)
    halves = [h for w in [header, *body] for h in (w >> 18, w & MASK18)] + [next_address]
    checksum = (-sum(halves)) % MASK18
    return [header, *body, (checksum << 18) | next_address]

def reader_leader():
    """The 20-word standard reader leader, taken from the saved HELLO tape."""
    return words(read(ROOT / 'programs/hello.tape'))[:20]

def relink(tape, leader_words=20):
    """Make an upstream tx2m4as tape loadable by the plugboard reader leader.

    Non-final block trailers must jump back to 3 (the leader's block loop) and
    checksums are the 18-bit one's-complement ring sum (both found by running the
    original plugboard). Returns (tape_bytes, per-block report).
    """
    ws = words(tape)
    report, pos = [], leader_words
    while pos < len(ws):
        field = ws[pos] >> 18
        count = 1 - (field if field < 1 << 17 else -((~field) & MASK18))
        trailer = pos + count + 1
        if count <= 0 or trailer >= len(ws):
            raise ValueError(f'invalid block at word {pos}')
        old_next, old_sum = ws[trailer] & MASK18, ws[trailer] >> 18
        nxt = 3 if trailer + 1 < len(ws) else old_next
        total = sum((w >> 18) + (w & MASK18) for w in ws[pos:trailer]) + nxt
        checksum = (-total) % MASK18
        ws[trailer] = (checksum << 18) | nxt
        report.append({'word_offset': pos, 'body_words': count, 'old_checksum': f'{old_sum:06o}',
                       'ring_checksum': f'{checksum:06o}', 'changed': old_sum != checksum,
                       'old_next': f'{old_next:06o}', 'next': f'{nxt:06o}'})
        pos = trailer + 1
    return bytes(FEED | line for w in ws for line in splay(w)), report

# Lincoln Writer codes (Users Handbook table 7-6; lower case holds capitals and digits).
LW_LOWER = '0123456789' + '\0' * 6 + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ()+-,.'
LW_UPPER = {'|': 0o02, '/': 0o04, '#': 0o06, '<': 0o10, '>': 0o11, 'n': 0o20, 'q': 0o23, 't': 0o25, 'w': 0o26,
            'x': 0o27, 'i': 0o30, 'y': 0o31, 'z': 0o32, '?': 0o33, 'j': 0o36, 'k': 0o37, 'p': 0o42, 'h': 0o44,
            '~': 0o51, '{': 0o52, '}': 0o53, '=': 0o55, "'": 0o56, '*': 0o57}

def lw_encode(text):
    """Text -> LW codes with automatic case changes; CR resets to lower case."""
    codes, case = [], 'lower'
    for ch in text:
        if ch == '\n':
            codes.append(0o60); case = 'lower'; continue
        if ch == '\t': codes.append(0o61); continue
        if ch == ' ': codes.append(0o70); continue
        up = ch.upper() if ch.isalpha() and ch.upper() in LW_LOWER and ch not in LW_UPPER else ch
        if up in LW_LOWER and up != '\0':
            if case != 'lower': codes.append(0o74); case = 'lower'
            codes.append(LW_LOWER.index(up))
        elif ch in LW_UPPER:
            if case != 'upper': codes.append(0o75); case = 'upper'
            codes.append(LW_UPPER[ch])
        else:
            raise SystemExit(f'No Lincoln Writer code for {ch!r}')
    return codes

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('info'); s.add_argument('file')
    s = sub.add_parser('dump'); s.add_argument('file'); s.add_argument('--words', action='store_true')
    s = sub.add_parser('convert'); s.add_argument('input'); s.add_argument('output')
    s = sub.add_parser('text'); s.add_argument('output'); s.add_argument('text')
    s.add_argument('--no-seventh', action='store_true')
    s = sub.add_parser('fix', help='relink/re-checksum an upstream tx2m4as tape'); s.add_argument('input'); s.add_argument('output')
    s = sub.add_parser('splice'); s.add_argument('output'); s.add_argument('inputs', nargs='+')
    s = sub.add_parser('words'); s.add_argument('output'); s.add_argument('address')
    s.add_argument('values', nargs='+'); s.add_argument('--start', help='octal start address (default: first word)')
    a = p.parse_args()
    if a.cmd == 'info':
        t = read(a.file)
        print(json.dumps({'lines': len(t), 'punched': sum(1 for b in t if b & FEED),
                          'blank': sum(1 for b in t if b == FEED), 'seventh_hole': sum(1 for b in t if b & SEVENTH),
                          'blocks': [{**b, **({'start': f"{b['start']:06o}", 'next': f"{b['next']:06o}"} if 'start' in b else {})}
                                     for b in blocks(t)]}, indent=2))
    elif a.cmd == 'dump':
        t = read(a.file)
        if a.words:
            for i, w in enumerate(words(t)): print(f'{i:6d}  {w >> 18:06o} {w & MASK18:06o}')
        else:
            for i, b in enumerate(t):
                holes = ''.join('o' if b >> k & 1 else '.' for k in (5, 4, 3)) + '·' + ''.join('o' if b >> k & 1 else '.' for k in (2, 1, 0))
                print(f"{i:6d}  {b & DATA:02o}  {'7' if b & SEVENTH else ' '} {holes}{'' if b & FEED else '  (no feed)'}")
    elif a.cmd == 'convert':
        write(a.output, read(a.input))
    elif a.cmd == 'text':
        text = sys.stdin.read() if a.text == '-' else a.text
        write(a.output, [FEED | (0 if a.no_seventh else SEVENTH) | c for c in lw_encode(text)])
    elif a.cmd == 'fix':
        fixed, report = relink(read(a.input)); write(a.output, fixed)
        print(json.dumps(report, indent=2))
    elif a.cmd == 'splice':
        write(a.output, [b for f in a.inputs for b in read(f)])
    elif a.cmd == 'words':
        addr = int(a.address, 8); body = [int(v, 8) for v in a.values]
        start = int(a.start, 8) if a.start else addr
        start_block = build_block(0o27, [0o010452020000, 0o140500000000 | start], 3)
        program = build_block(addr, body, 0o27)
        all_words = reader_leader() + start_block + program
        write(a.output, [FEED | line for w in all_words for line in splay(w)])

if __name__ == '__main__':
    main()
