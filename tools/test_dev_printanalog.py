#!/usr/bin/env python3
"""CLI acceptance for Xerox 51 / DATRAC 50; H63 PDF pp99–103,196.

Runs SKX/IOS/TSD/STE programs. TX2_CLI selects a private CLI build.
The inspected 1963 Sketchpad listing uses neither device; see device spec §2.5.
"""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORD = (1 << 36) - 1


def ins(op, addr=0, j=0, cf=0, held=True):
    return (int(held) << 35) | (cf << 30) | (op << 24) | (j << 18) | addr


def ios(unit, cmd=0, cf=0, held=True):
    return ins(0o04, cmd, unit, cf, held)


class Cli:
    def __init__(self):
        self.p = subprocess.Popen([os.environ.get('TX2_CLI', str(ROOT / 'build/obj_cli/tx2-cli'))],
                                  cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.cmd('set timing 1')

    def cmd(self, text):
        self.p.stdin.write(text + '\n')
        self.p.stdin.flush()
        result = json.loads(self.p.stdout.readline())
        assert not isinstance(result, dict) or 'error' not in result, (text, result)
        return result

    def put(self, addr, words):
        for i, value in enumerate(words):
            self.cmd(f'poke {addr+i} {value}')

    def run(self, clocks):
        s = self.cmd(f'run {clocks} 0 0 0')
        assert s['fault'] == 0, s
        return s

    def boot(self, unit, program, alarms=False):
        bootstrap = [ins(0o12, 0o400, unit)]
        if alarms:
            bootstrap.append(ios(0o41, 0o30000))
        bootstrap += [ios(unit, 0o30000), ios(unit, 0o50000), ios(0, 0o40000, 0o20, False)]
        self.put(0o100, bootstrap)
        self.put(0o400, program)
        self.cmd(f'press codabo {0o100}')

    def close(self):
        self.p.terminate()
        self.p.wait()


def alarm_report(c, old_unit, loop, report_addr, disconnect):
    """Leave the running unit, TSD unit 41, inspect IOS report, disconnect it."""
    c.put(loop, [ins(0o12, 0o700, 0o41), ios(0o41, 0o50000), ios(old_unit, 0o40000, 0o20, False)])
    c.put(0o700, [ins(0o57, report_addr), ios(old_unit, 0, 1), ins(0o30, report_addr+1),
                 ios(old_unit, 0o20000) if disconnect else ios(old_unit),
                 ios(old_unit, 0, 1), ins(0o30, report_addr+2), ins(0o05, 0o706)])
    return c.run(1000)


def printer():
    c = Cli()
    try:
        # A startup blank, frame sync, then a positioned line plus previously
        # unresolved stencil glyphs. Unused buffer bits deliberately set to 1.
        codes = [0o153, 0o161, 0o002, 0o554, 0o173, 0o023, 0o363, 0o703, 0o704,
                 0o730, 0o731, 0o570, 0o571, 0o114, 0o130, 0o133, 0o121]
        glyphs = ['T', 'X', '2', 'A', 'w', 'λ', "'", 'Σ', '□', '|', '‖', '_', '‾', '=', '≡', 'i', '⊃']
        unused = ((1 << 12) - 1) << 15
        words = [0o100] + [(i * 8 << 27) | (0o74 << 9) | code | unused for i, code in enumerate(codes)]
        c.put(0o1000, words)
        program = [ins(0o57, 0o1000), ios(0o51, 0o30010)]
        program += [ins(0o57, 0o1001 + i) for i in range(len(codes))]
        loop = 0o400 + len(program)
        program.append(ins(0o05, loop))
        c.boot(0o51, program, alarms=True)
        early = c.run(10000)
        assert early['units']['xerox']['warming'] and not early['units']['xerox']['characters'], early
        s = c.run(5_100_000)
        marks = s['dev']['xerox']
        assert len(marks) == len(words), marks
        assert marks[0]['uncertain'] and marks[0]['glyph'] == '', marks[0]
        assert [m['glyph'] for m in marks[1:]] == glyphs, marks
        assert [m['x'] for m in marks[1:]] == [i*8 for i in range(len(codes))], marks
        assert all(m['y'] == -3 and not m['uncertain'] for m in marks[1:]), marks
        assert marks[4]['large'] and not marks[1]['large'], marks
        assert marks[1]['frame'] > marks[0]['frame'], marks
        assert len({m['frame'] for m in marks[1:]}) == 1, marks
        assert marks[0]['clock'] >= 5_000_000, marks[0]
        assert all(b['clock'] - a['clock'] >= 750 for a, b in zip(marks, marks[1:])), marks
        assert all((m['clock'] - marks[1]['clock']) < 45000 for m in marks[1:]), marks
        # Output completion raises the device flag; low paper raises EIA 1.7.
        assert int(s['flags'], 8) & (1 << 0o51), s
        c.cmd('dev xerox paper 1')
        s = c.run(20)
        assert int(s['flags'], 8) & (1 << 0o41), s
        # Remove physical low-paper source after latching, so disconnect can clear.
        c.cmd('dev xerox paper 0')
        alarm_report(c, 0o51, loop, 0o2000, True)
        report, before, after = c.cmd(f'peek {0o2000} 3')
        assert report & 0o100 and before & (1 << 13), (report, before, after)
        assert not after & ((1 << 13) | (1 << 14)), (report, before, after)
        # Fifteen seconds' paper run-on after disconnect, with the CPU stopped.
        assert c.cmd('state')['units']['xerox']['moving']
        c.cmd('press stop')
        assert not c.run(100)['running']
        s = c.run(15_100_000)
        assert not s['units']['xerox']['moving'], s['units']['xerox']
        print('PASS Xerox: TX2 line, positioned 9/6/9-bit fields, size, resolved glyphs, 5 s warm-up, frame sync, flag, EIA 100, disconnect, stopped-CPU 15 s run-on')
    finally:
        c.close()


def analog():
    c = Cli()
    try:
        c.cmd('dev datrac power 1')
        c.cmd('dev datrac route programmed 0')
        sentinel = 0o654321000000
        c.put(0o1000, [sentinel, sentinel])
        c.boot(0o50, [ins(0o57, 0o1000), ins(0o57, 0o1001), ins(0o05, 0o402)], alarms=True)
        s = c.run(2000)
        assert s['limbo'] and not s['units']['datrac']['samples'], s
        c.cmd('dev datrac source square 0.5 1000 0')
        c.cmd('dev datrac trigger 1')
        s = c.run(21)
        assert s['units']['datrac']['converting'] and s['units']['datrac']['samples'] == 0, s
        s = c.run(1)
        assert s['units']['datrac']['ready'] and s['units']['datrac']['samples'] == 1, s
        assert int(s['flags'], 8) & (1 << 0o50), s
        c.run(600)
        c.cmd('dev datrac trigger 4')
        s = c.run(200)
        assert c.cmd(f'peek {0o1000} 2') == [sentinel | 0o200000, sentinel | 0o577777], s
        assert not s['units']['datrac']['missed'], s
        # A valid externally triggered sample, another before it is read: MISAL.
        c.cmd('dev datrac trigger 2')
        c.run(40)
        c.cmd('dev datrac trigger 3')
        s = c.run(40)
        assert s['units']['datrac']['missed'], s
        assert int(s['flags'], 8) & (1 << 0o41), s
        # A too-soon trigger is counted, with the last accepted conversion retained.
        c.cmd('dev datrac trigger 1')
        c.cmd('dev datrac trigger 1')
        s = c.run(40)
        assert s['units']['datrac']['tooFast'] == 1, s
        alarm_report(c, 0o50, 0o402, 0o2000, True)
        report, before, after = c.cmd(f'peek {0o2000} 3')
        assert report & 1 and before & (1 << 12), (report, before, after)
        assert not after & ((1 << 12) | (1 << 14)), (report, before, after)
        c.cmd('press stop')
        assert not c.run(100)['running']
        c.cmd('dev datrac source dc 0.25')
        c.cmd('dev datrac trigger 1')
        s = c.run(100)
        assert not s['running'] and s['units']['datrac']['word'] == 0o100000, s
        samples = s['units']['datrac']['samples']
        c.cmd('dev datrac oscillator 1000')
        s = c.run(2100)
        assert not s['running'] and s['units']['datrac']['samples'] >= samples + 2, s
        c.cmd('dev datrac oscillator 0')
        print('PASS DATRAC: panel routing, 22 us conversion/flag, known ±0.5 V square wave, low-half mask/no sign extension, MISAL 001, 37 us spacing, disconnect, stopped-CPU conversion/oscillator')
    finally:
        c.close()


def programmed_and_timer():
    c = Cli()
    try:
        c.cmd('dev datrac power 1')
        c.cmd('dev datrac source dc -0.25')
        # Delay the first read beyond 37 us so its routed TSD pulse is legal.
        c.boot(0o50, [ios(0o50)] * 4 + [ins(0o57, 0o1000), ins(0o05, 0o405)], alarms=True)
        s = c.run(1000)
        assert c.cmd(f'peek {0o1000} 1') == [0o677777], s
        assert s['units']['datrac']['samples'] == 2, s  # IOS trigger + TSD trigger.
        c.cmd('dev datrac route programmed 0')
        c.cmd('dev datrac route timer 1')
        # Interval timer 54 counts 100 one-microsecond ticks, without interrupts.
        # Consume the TSD-triggered sample before dismissing input sequence 50;
        # otherwise its level-sensitive flag correctly wins dispatch again.
        c.put(0o1001, [100])
        c.put(0o405, [ins(0o57, 0o1002), ins(0o12, 0o600, 0o54), ios(0o54, 0o30000), ios(0o54, 0o50000), ios(0o50, 0o40000, 0o20, False)])
        c.put(0o600, [ins(0o57, 0o1001), ios(0o54, 0o30100), ins(0o05, 0o602)])
        s = c.run(1000)
        assert s['units']['datrac']['samples'] >= 8, s
        print('PASS DATRAC: IOS/TSD programmed trigger pulses and real interval-timer end-carry routing')
    finally:
        c.close()


if __name__ == '__main__':
    printer()
    analog()
    programmed_and_timer()
