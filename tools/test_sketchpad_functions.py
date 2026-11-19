#!/usr/bin/env python3
"""Sketchpad push-button functions on the TX-2 debugging CLI (same host as the browser).

Buttons follow Sutherland, TR-296 Appendix B. The pen glides at the browser's default
limit (2 display units per 10,000 clocks). Exercises line, circle arc, MOVE, HORV with
constraint satisfaction, DELETE and INSTANCE, reading the model rings and the CRT output.
Requires build/obj_cli/tx2-cli (make cli).
"""
import json, math, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QB = lambda q, b: 9 * (q - 1) + (b - 1)
BUTTONS = {'draw': QB(1, 8), 'circle': QB(1, 7), 'move': QB(2, 1), 'delete': QB(1, 3), 'stop': QB(1, 6),
           'horv': QB(2, 9), 'instance': QB(2, 4), 'copy20': QB(3, 6), 'text': QB(3, 2), 'number': QB(3, 7)}
RINGS = {'lines': 0o24201, 'circles': 0o24225, 'points': 0o24275, 'instances': 0o24345}

class Sketchpad:
    def __init__(self):
        self.p = subprocess.Popen([os.environ.get('TX2_CLI', str(ROOT / 'build/obj_cli/tx2-cli'))], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.pen = (0, 0, 0); self.ext = 0
        self.cmd('load programs/sketchpad/sketchpad.tape'); self.cmd(f'set suppress {0o200}')
        self.cmd('set reader_us 64')  # explicit accelerated line period; physical default is 500 us
        self.cmd(f'press codabo {0o377750}')
        for _ in range(120):
            state = self.run(1_000_000)
            assert state['running'], state
            if state['tape']['pos'] == state['tape']['size'] and state['points']:
                break
        else:
            raise AssertionError(f'Sketchpad tape/program did not finish booting: {state}')
        self.run(800_000, -128, 110, 1)  # aim at INK: pen starts tracking
    def cmd(self, line):
        self.p.stdin.write(line + '\n'); self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())
    def run(self, n, x=None, y=None, pen=None):
        x0, y0, p0 = self.pen
        self.pen = (x0 if x is None else x, y0 if y is None else y, p0 if pen is None else pen)
        s = self.cmd(f'run {n} {self.pen[0]} {self.pen[1]} {self.pen[2]}')
        assert s['fault'] == 0, s
        return s
    def glide(self, x, y):
        x0, y0, _ = self.pen
        steps = max(1, int(math.hypot(x - x0, y - y0) / 4))
        for i in range(1, steps + 1):
            self.run(20000, round(x0 + (x - x0) * i / steps), round(y0 + (y - y0) * i / steps), 1)
        self.run(200000)
    def press(self, name):
        for on in (True, False):
            self.ext = self.ext | 1 << BUTTONS[name] if on else self.ext & ~(1 << BUTTONS[name])
            self.cmd(f'set ext {self.ext}'); self.run(80000 if on else 400000)
    def members(self, header):
        head, seen = header - 0o24000 + 3, []
        node = self.cmd(f'peek {header + 3} 1')[0] & 0o777777
        while node != head and 0 < node < 0o154000 and len(seen) < 1024 and node not in seen:
            seen.append(node); node = self.cmd(f'peek {0o24000 + node} 1')[0] & 0o777777
        return seen
    def model(self): return {k: len(self.members(h)) for k, h in RINGS.items()}
    def points(self):
        scale = 512 / (self.cmd(f'peek {0o200034} 1')[0] or 512)
        ones = lambda v: -((~v) & (2 ** 36 - 1)) if v >> 35 else v
        return sorted((round(ones(x) * scale), round(ones(y) * scale))
                      for x, y in (self.cmd(f'peek {0o24000 + n + 0o17} 2') for n in self.members(RINGS['points'])))

def crt(sp, runs=16):
    spots = set()
    for _ in range(runs):
        spots.update((p[0], p[1]) for p in sp.run(50000, pen=0)['display'] if p[3] == 0o60)
    sp.run(1, pen=1)
    return spots

def tracked(sp, runs=12):
    """CRT spots with the pen kept on the screen (lifting it ends a move)."""
    spots = set()
    for _ in range(runs):
        spots.update((p[0], p[1]) for p in sp.run(50000)['display'] if p[3] == 0o60)
    return spots

def main():
    sp, report = Sketchpad(), {}
    sp.press('draw'); sp.glide(-40, 160); sp.press('stop')
    report['line'] = sp.model()
    sp.glide(60, -40); sp.press('circle'); sp.glide(110, -40); sp.press('draw')
    for a in range(15, 271, 15):
        sp.glide(round(60 + 50 * math.cos(math.radians(a))), round(-40 + 50 * math.sin(math.radians(a))))
    sp.press('stop')
    report['circle'] = sp.model()
    report['circle_spots'] = sum(abs(math.hypot(x - 60, y + 40) - 50) <= 3 for x, y in crt(sp))
    # MOVE: aim at the line's end point and carry it to (-20, 200).
    sp.glide(-40, 160); sp.press('move'); sp.glide(-20, 200); sp.press('stop')
    report['moved_point'] = min(sp.points(), key=lambda p: math.hypot(p[0] + 20, p[1] - 200))
    # HORV on the line; constraint satisfaction runs while toggle 377720's meta bit (FIX) is set.
    sp.glide(-74, 155); sp.press('horv')
    sp.cmd('set tmeta 0 1'); sp.run(3_000_000); sp.cmd('set tmeta 0 0')
    ends = [p for p in sp.points() if p[0] < 0]
    report['horv_ends'] = ends
    sp.glide(-74, ends[0][1]); sp.press('delete')
    report['after_delete'] = sp.model()
    # INSTANCE: open picture 2 (toggle 377724), ink up, place an instance of picture 0 (toggle 377725).
    sp.cmd('set toggle 4 2'); sp.run(2_000_000)
    sp.pen = (0, 0, 0); sp.run(800_000, -128, 110, 1)
    sp.cmd('set toggle 5 0'); sp.glide(0, 0); sp.press('instance'); sp.press('stop'); sp.run(1_000_000)
    report['instances'] = len(sp.members(RINGS['instances']))
    report['instance_spots'] = len(tracked(sp))
    # A new instance is left moving: its displayed extent follows the pen.
    sp.glide(-60, 60); sp.press('instance')
    x0 = min(x for x, y in tracked(sp)); sp.glide(20, 0); x1 = min(x for x, y in tracked(sp)); sp.press('stop')
    report['instance_follow_dx'] = x1 - x0
    # COPY 20 (3.6) copies picture 0 (toggle 377720) — by now its circle — as a real circle.
    before = sp.model()['circles']
    sp.cmd('set toggle 0 0'); sp.glide(-80, -80); sp.press('copy20'); sp.press('stop')
    report['copied_circles'] = sp.model()['circles'] - before
    # TEXT (3.2) makes an X; Lincoln Writer keys H E L replace and extend it. NUMBER (3.7).
    sp.glide(80, -100); base = len(tracked(sp)); sp.press('text')
    sp.cmd('dev lw65 keys 23 20 27'); sp.run(3_000_000); report['text_spots'] = len(tracked(sp)) - base; sp.press('stop')
    sp.glide(-100, 100); base = len(tracked(sp)); sp.press('number')
    report['number_spots'] = len(tracked(sp)) - base; sp.press('stop')
    sp.p.terminate()
    print(json.dumps(report, indent=2))
    assert report['line'] == {'lines': 1, 'circles': 0, 'points': 2, 'instances': 0}, report
    assert report['circle']['circles'] == 1 and report['circle_spots'] > 150, report
    assert math.hypot(report['moved_point'][0] + 20, report['moved_point'][1] - 200) <= 3, report
    assert len(ends) == 2 and abs(ends[0][1] - ends[1][1]) <= 1 and abs(ends[0][0] - ends[1][0]) > 40, report
    assert report['after_delete']['lines'] == 0 and report['after_delete']['circles'] == 1, report
    assert report['instances'] == 1 and report['instance_spots'] > 150, report
    assert 70 <= report['instance_follow_dx'] <= 90, report
    assert report['copied_circles'] == 1, report
    assert report['text_spots'] > 30 and report['number_spots'] > 20, report
    print('PASS: line, circle arc, MOVE, HORV + constraint satisfaction, DELETE, INSTANCE (follows pen), COPY, TEXT typing, NUMBER')

if __name__ == '__main__':
    sys.exit(main())
