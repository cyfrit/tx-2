#!/usr/bin/env python3
"""CPU/board acceptance for PETR52, timer54, scopes/pen/camera, alarm41/trap42.
Sources: H63 IOS/TSD pp87-89, device pages105-113; TM2 15-PETR-1..3,
Fig15-PETR-2; Sketchpad TR296 appendix. TX2_CLI selects a private CLI build.
"""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
W36 = (1 << 36) - 1


def ins(op, cf=0, unit=0, address=0, held=True):
    return (int(held) << 35) | (cf << 30) | (op << 24) | (unit << 18) | address


class Board:
    def __init__(self):
        self.p = subprocess.Popen([os.environ.get('TX2_CLI', str(ROOT / 'build/obj_cli/tx2-cli'))],
                                  cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def cmd(self, text):
        self.p.stdin.write(text + '\n'); self.p.stdin.flush()
        value = json.loads(self.p.stdout.readline())
        assert not isinstance(value, dict) or 'error' not in value, (text, value)
        return value

    def program(self, unit, mode, body, data=None, prefix=()):
        self.cmd('power')
        words = {0o100+i: w for i, w in enumerate((*prefix, ins(0o04, unit=unit, address=mode),
                    ins(0o12, 0o30, unit, 0o200, False)))}
        words.update({0o200+i: w for i, w in enumerate(body)})
        words[0o200+len(body)] = ins(0o05, address=0o200+len(body))
        words.update(data or {})
        for a, w in words.items(): self.cmd(f'poke {a} {w}')

    def start(self): self.cmd(f'press codabo {0o100}')
    def run(self, clocks=10000, x=0, y=0, pen=0): return self.cmd(f'run {clocks} {x} {y} {pen}')
    def peek(self, a, n=1): return self.cmd(f'peek {a} {n}')
    def close(self): self.p.terminate(); self.p.wait()


def main():
    b = Board(); report = {}
    try:
        # Both read modes search binward; seventh-hole 73 is data, not END MARK.
        # The actual forward gate in TM2 Fig15-PETR-2 is Hf·REV0, independent H7.
        for mode in (0o30104, 0o30106):
            b.program(0o52, mode, [ins(0o57, address=0o400), ins(0o57, address=0o400 if mode & 2 else 0o401)])
            b.cmd('set reader_us 64'); b.cmd('tape 81bbfbc2'); b.cmd('dev petr position 4')
            b.start(); s = b.run(3000)
            if mode & 2:
                word = 0
                for code in (0o73, 2):
                    word = ((word << 1) | (word >> 35)) & W36
                    for bit in range(6): word = (word & ~(1 << (bit*6))) | (((code >> bit) & 1) << (bit*6))
                assert b.peek(0o400)[0] == word, (mode, b.peek(0o400))
            else: assert b.peek(0o400, 2) == [0o73, 2], b.peek(0o400, 2)
            assert not s['alarms'] and s['tape']['rewinds'] == 1, s
        for mode in (0o30000, 0o30002, 0o30004, 0o30006):
            b.program(0o52, mode, []); b.cmd('tape c1c2'); b.start(); s = b.run(1000)
            assert s['tape']['pos'] == 0 and s['tape']['direction'] == 0, (mode, s)
        report['petr_modes'] = 'normal/splayed/bin search and all four STOP modes'

        # Physical transports continue with the CPU stopped; manual BIN disconnects.
        b.cmd('power'); b.cmd('tape 81bbfbc2'); b.cmd('dev petr position 4'); b.cmd('set reader_us 64')
        b.cmd('dev petr bin'); s = b.run(1000)
        assert s['tape']['pos'] == 2 and s['tape']['direction'] == 0, s
        assert not (int(s['connected'], 8) & (1 << 0o52)), s
        b.cmd('tape ' + 'c1'*300); b.cmd('dev petr wind'); b.run(1280); b.cmd('dev petr stop')
        before = b.cmd('state')['tape']['pos']; s = b.run(20000)
        assert s['tape']['pos'] - before == 100 and s['tape']['direction'] == 0, (before, s)
        report['stop_distance'] = 100

        # Free-running overwrite raises the real central MISAL; connecting41
        # suppresses the stop while preserving the central red alarm indicator.
        b.program(0o52, 0o30100, [], {0o300: ins(0o05, address=0o300)},
                  prefix=(ins(0o12, unit=0o41, address=0o300), ins(0o04, unit=0o41, address=0o30000)))
        b.cmd('set reader_us 1'); b.cmd('tape ' + 'c1'*30); b.start(); s = b.run(2000)
        assert s['alarms'] & (1 << 8) and s['running'], s
        assert int(s['flags'], 8) & (1 << 0o41), s
        report['misal'] = s['alarms']

        # Timer IOS/TSD load, last-16 busy, manual oscillator/start/stop, EC pulses.
        b.program(0o54, 0o30000, [ins(0o57, address=0o400), ins(0o04, unit=0o54, address=0o30300)], {0o400: 20})
        b.start(); s = b.run(3000)
        assert s['timer']['interval'] == 20 and s['timer']['pulses'] > 0, s
        b.cmd('dev timer stop'); s = b.run(20); assert not s['timer']['running'], s
        b.cmd('dev timer external 0'); b.cmd('dev timer trigger'); s = b.run(10)
        assert not s['timer']['running'], s
        b.cmd('dev timer external 1'); b.cmd('dev timer trigger'); s = b.run(10)
        assert s['timer']['running'], s
        b.cmd('dev timer stop'); b.run(10)
        b.cmd('dev timer rate 0'); b.cmd('dev timer toggles 3'); b.cmd('dev timer start'); b.run(20)
        count = b.cmd('state')['timer']['pulses']
        for _ in range(3): b.cmd('dev timer pulse'); b.run(1)
        s = b.run(1); assert s['timer']['pulses'] == count+1, s
        report['timer'] = s['timer']

        # Scope56 cannot stimulate the documented H63 scope60 pen; CRT events
        # retain their scope identity. Camera busy affects60 and leaves56 free.
        b.program(0o56, 0o30030, [ins(0o57, address=0o400)], {0o400: 0},
                  prefix=(ins(0o04, unit=0o55, address=0o30000),))
        b.start(); s = b.run(1000, pen=1)
        assert s['display'] == [[0, 0, 3, 0o56]] and s['hits'] == 0, s
        b.program(0o60, 0o30004, [ins(0o57, address=0o400)],
                  {0o400: 0, 0o300: ins(0o12, 0o20, 0o41, 0, False)},
                  prefix=(ins(0o12, unit=0o41, address=0o300), ins(0o04, unit=0o41, address=0o30000)))
        b.cmd('dev camera us 500'); b.cmd('dev camera empty 1'); b.start(); s = b.run(4000)
        assert s['cameraStatus']['busy'] and s['cameraStatus']['buzzer'] and not s['points'], s
        b.cmd('dev camera ack'); acknowledged = b.cmd('state')['cameraStatus']
        assert not acknowledged['buzzer'] and acknowledged['eia'], acknowledged
        b.cmd('dev camera empty 0'); s = b.run(1000)
        assert not s['cameraStatus']['busy'] and s['points'] == 1, s
        b.program(0o60, 0o30004, [ins(0o57, address=0o400), ins(0o04, unit=0o60, address=0o30004), ins(0o57, address=0o400)], {0o400: 0})
        b.cmd('dev camera low 0'); b.cmd('dev camera us 500'); b.start(); s = b.run(5000)
        assert s['points'] == 2 and not s['cameraStatus']['busy'], s
        report['scope_camera'] = 'unit-tagged events, pen60 gate, no-film hold, delayed return'

        # Host SET METABITS and Sync-to-Trap selection are wired to the core.
        b.program(0o42, 0o30100, [ins(0o24, address=0o400), ins(0o04, unit=0o42, address=0o40000)], {0o400: 123})
        b.cmd('set setmetabits 1'); b.start(); b.run(500)
        assert b.cmd(f'meta {0o200} 1') == [1]
        assert not (int(b.cmd('state')['flags'], 8) & (1 << 0o42))
        b.cmd('set synctotrap 1'); b.cmd('set gate1 1'); b.cmd('press sync'); s = b.run(1)
        assert int(s['flags'], 8) & (1 << 0o42), s
        report['trap'] = 'manual set-metabit enable and gated sync pulse'

        # Determine the accelerated loader limit for this serialized CPU with
        # the original HELLO tape; physical AUTO remains500us reel/2500us strip.
        passed = []
        for period in range(32, 65):
            b.cmd('power'); b.cmd('dev lw66 us 0'); b.cmd('dev lw66 route 1 0')
            b.cmd(f'set reader_us {period}'); b.cmd('load programs/hello.tape'); b.cmd(f'press codabo {0o377750}')
            s = b.run(100000)
            if s['fault'] == 1 and not (s['alarms'] & (1 << 8)) and s['tape']['pos'] == s['tape']['size'] and len(s['writer']) == 39:
                passed.append(period)
        assert 64 in passed, passed
        report['fastest_hello_line_us'] = min(passed)
        print(json.dumps(report, ensure_ascii=False))
        print('PASS: PETR modes/search/seventh hole/manual transport/braking/MISAL, timer IOS/TSD/EC, scope pen camera, trap console, original plugboard HELLO')
    finally: b.close()


if __name__ == '__main__': main()
