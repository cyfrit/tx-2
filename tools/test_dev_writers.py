#!/usr/bin/env python3
"""Deterministic CLI probes for Writers 65/66,71/72, misc 47/75 and RNG61.
Sources: references/device-specs/writers-misc.md (H63 pp.97,115-123;
Gilmore/Savell, The Lincoln Writer, 1959). Uses real assembled IOS/TSD.
TX2_CLI selects a private build; default is build/obj_cli/tx2-cli.
"""
import json
import os
from pathlib import Path
import subprocess
from test_sketchpad_preparation import compile_words

ROOT = Path(__file__).resolve().parents[1]
W36 = (1 << 36) - 1


class CLI:
    def __init__(self):
        self.p = subprocess.Popen([os.environ.get('TX2_CLI', str(ROOT / 'build/obj_cli/tx2-cli'))],
                                  cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.events = {}

    def cmd(self, line):
        self.p.stdin.write(line + '\n'); self.p.stdin.flush()
        result = json.loads(self.p.stdout.readline())
        assert not isinstance(result, dict) or 'error' not in result, (line, result)
        if isinstance(result, dict):
            for unit, event in result.get('dev', {}).items():
                if isinstance(event, dict):
                    for key, values in event.items():
                        if isinstance(values, list): self.events.setdefault((unit, key), []).extend(values)
        return result

    def program(self, source):
        self.cmd('power'); self.events.clear()
        for address, word in compile_words(source).items(): self.cmd(f'poke {address} {word}')

    def start(self):
        self.cmd(f'press codabo {0o100}')

    def run(self, n=10000):
        s = self.cmd(f'run {n} 0 0 0')
        assert s['fault'] == 0, s
        return s

    def boot(self, tape):
        self.cmd('set reader_us 64')  # explicit UI/test acceleration; physical AUTO remains available.
        self.cmd(f'load {tape}'); self.cmd(f'press codabo {0o377750}')
        for _ in range(30):
            s = self.cmd('run 1000000 0 0 0')
            assert s['fault'] in (0, 1), s
            if s['tape']['pos'] >= s['tape']['size']:
                return self.cmd('run 1000000 0 0 0')
            assert s['running'], s
        raise AssertionError('Paper-tape bootstrap exceeded the clock limit')

    def words(self, n=1): return self.cmd(f'peek {0o400} {n}')

    def close(self):
        self.p.terminate(); self.p.wait()


def io_program(unit, count=1):
    sub = unit.translate(str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉'))
    return f'100| REX{sub} WORK\n²¹IOS{sub} 30000\nWORK->\n' + ''.join(
        f'hTSD {0o400 + i:o}\n' for i in range(count)) + 'WAIT-> hJPQ WAIT\n'


def main():
    c = CLI(); report = {}
    try:
        # Six CPU bits only; a physical upper-key character needs two TSDs.
        for unit in ('65', '71'):
            c.program(io_program(unit, 3))
            c.cmd(f'dev lw{unit} us 0')
            for i in range(3): c.cmd(f'poke {0o400+i} {W36}')
            c.cmd(f'dev lw{unit} key {0o100 | 0o23} {0o20}')
            c.start(); s = c.run(10000)
            expected = [0o75, 0o23, 0o74]
            assert c.words(3) == [(W36 & ~0o77) | code for code in expected], c.words(3)
            assert s['units'][f'lw{unit}']['keys'] == 1, s['units']
            report[f'keyboard{unit}'] = expected

        # Soroban filters, station advancement, CPU backpressure and STOP.
        c.program(io_program('71', 2)); c.cmd('dev lw71 tape 80ffd0fe')
        c.cmd('dev lw71 start'); c.start(); s = c.run(500000)
        assert c.words(2) == [0o20, 0], c.words(2)
        assert s['units']['lw71']['position'] == 4 and not s['units']['lw71']['reader'], s['units']['lw71']
        report['reader'] = s['units']['lw71']

        # Both output buffers stay busy until the final mechanical completion.
        for unit in ('66', '72'):
            c.program(io_program(unit, 2)); c.cmd(f'dev lw{unit} us 1000')
            c.cmd(f'dev lw{unit} punch_us 1000')
            c.cmd(f'dev lw{unit} route 1 1')
            c.cmd(f'poke {0o400} {0o27}'); c.cmd(f'poke {0o401} {0o24}')
            c.start(); early = c.run(1000)
            assert early['units'][f'lw{unit}']['busy'], early['units']
            assert not (int(early['flags'], 8) & (1 << int(unit, 8))), early
            c.run(10000)
            assert c.events[(f'lw{unit}', 'codes')] == [0o27, 0o24], c.events
            assert c.events[(f'lw{unit}', 'punch')] == [0o327, 0o324], c.events
            report[f'output{unit}'] = c.events[(f'lw{unit}', 'codes')]
            c.events.clear(); c.cmd(f'dev lw{unit} feed 1'); c.run(5000)
            c.cmd(f'dev lw{unit} feed 0'); c.run(5000)
            assert c.events[(f'lw{unit}', 'punch')] == [0o200] * 3, c.events
            c.cmd(f'dev lw{unit} endmark'); c.cmd('state')
            assert c.events[(f'lw{unit}', 'punch')][-1] == 0o273, c.events

        # Repeated pulses coalesce; disabled channels do not latch. A TSD
        # preserves every destination bit outside the rightmost nine.
        c.program(io_program('47')); c.cmd(f'poke {0o400} {W36}')
        c.cmd('dev misc47 enable 257'); c.cmd('dev misc47 pulse 3'); c.cmd('dev misc47 pulse 257')
        c.start(); s = c.run()
        assert c.words() == [(W36 & ~0o777) | 257], c.words()
        assert s['units']['misc47']['latch'] == 0, s['units']
        report['misc47'] = c.words()[0]

        # IOS is the unit75 write. TSD must leave its memory operand intact.
        c.program('100| REX₇₅ WORK\n²¹IOS₇₅ 30501\nWORK-> hTSD 400\nWAIT-> hJPQ WAIT')
        c.cmd(f'poke {0o400} {0o123456701234}'); c.start(); s = c.run(1000)
        assert s['units']['misc75']['register'] == 0o501 and s['units']['misc75']['relays'] == 0, s['units']
        assert s['units']['misc75']['mom9'] == 1 and not (int(s['flags'], 8) & (1 << 0o75)), s
        s = c.run(10000)
        assert c.words() == [0o123456701234] and s['units']['misc75']['relays'] == 0o501, s
        c.cmd('dev misc75 shiftmode 1'); c.cmd('dev misc75 shift'); s = c.run(10000)
        assert s['units']['misc75']['relays'] == 0o203, s['units']
        c.cmd('dev misc75 shiftmode 2'); c.cmd('dev misc75 shift'); s = c.run(10000)
        assert s['units']['misc75']['relays'] == 0o406, s['units']
        report['misc75'] = s['units']['misc75']

        # RNG is latched nine-bit input; each TSD starts the next timed sample.
        c.program(io_program('61', 2)); c.cmd('dev rng seed 1')
        for i in range(2): c.cmd(f'poke {0o400+i} {W36}')
        c.start(); early = c.run(80)
        assert not early['units']['rng']['ready'] and c.words(2) == [W36, W36], early
        s = c.run(10000)
        samples = c.words(2)
        assert all((v & ~0o777) == (W36 & ~0o777) for v in samples), samples
        assert [v & 0o777 for v in samples] == [33, 1], samples
        stable = s['units']['rng']['value']; s = c.run(10000)
        assert s['units']['rng']['value'] == stable and s['units']['rng']['ready'], s['units']
        c.cmd('dev rng power 0'); s = c.run(100)
        assert not s['units']['rng']['ready'], s['units']
        c.cmd('dev rng power 1'); s = c.run(10000)
        assert not s['units']['rng']['ready'] and s['units']['rng']['warmUntil'] > s['cycles'], s['units']
        report['rng'] = [v & 0o777 for v in samples]

        # Source-fed HELLO smoke through the same physical boot path as UI.
        c.cmd('power'); c.events.clear(); c.cmd('dev lw66 route 1 0'); c.cmd('dev lw66 us 0')
        s = c.boot('programs/hello.tape')
        assert s['fault'] in (0, 1), s  # HELLO ends at the intentional zero instruction.
        codes = c.events.get(('lw66', 'codes'), [])
        assert codes[:5] == [0o27, 0o24, 0o33, 0o33, 0o36], codes
        report['hello_codes'] = len(codes)

        # Original KEYSTART at SK1 4920-4931 fills KEYTAB in decreasing
        # index order, starting at 17 octal. Find that TSD in the assembled image.
        image = {int(a, 16): int(w, 16) for a, w in
                 (line.split() for line in (ROOT / 'programs/sketchpad/sketchpad.hex').read_text().splitlines())}
        ios65 = [a for a, w in image.items() if (w >> 24) & 63 == 0o04
                 and (w >> 18) & 63 == 0o65 and w & 0o777777 == 0o30000]
        assert len(ios65) == 1, ios65
        keyboard_tsd = image[ios65[0] + 3]
        assert (keyboard_tsd >> 24) & 63 == 0o57, oct(keyboard_tsd)
        keytab = keyboard_tsd & 0o377777
        c.cmd('power'); c.events.clear(); c.cmd('dev lw65 us 50000')
        c.cmd(f'set suppress {0o200}'); s = c.boot('programs/sketchpad/sketchpad.tape')
        assert s['fault'] == 0, s
        s = c.cmd('run 800000 -128 110 1'); assert s['fault'] == 0, s
        c.cmd(f'set ext {1 << 19}'); c.cmd('run 80000 80 -100 1')
        c.cmd('set ext 0'); c.cmd('run 400000 80 -100 1')
        c.events.clear(); c.cmd('dev lw65 keys 23 20 27')
        s = c.cmd('run 3000000 80 -100 1'); assert s['fault'] == 0, s
        received = c.cmd(f'peek {keytab + 0o15} 3')
        assert received == [27, 20, 23], received
        assert s['units']['lw65']['keys'] == 0, s['units']['lw65']
        report['sketchpad_keytab'] = received
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print('PASS: both keyboards, Soroban reader, Writer completion/punch, misc latches/relays, buffered RNG, HELLO, Sketchpad typing')
    finally:
        c.close()


if __name__ == '__main__':
    main()
