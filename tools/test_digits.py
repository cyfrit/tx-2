#!/usr/bin/env python3
"""Boot DIGITS and verify real pen hits, signed inference and CRT refresh."""
import json
import math
import os
import subprocess

from build_digits import MODEL, ROOT, TAPE, glyph
import tx2tape

BITMAP, FEATURES, HIDDEN, SCORES, RESULT = 0o1000, 0o1400, 0o1500, 0o1540, 0o1552


def features(bitmap):
    cells = [(i % 16, i // 16) for i, v in enumerate(bitmap) if v]
    xmin, ymin = map(min, zip(*cells))
    xmax, ymax = map(max, zip(*cells))
    w, h = xmax - xmin + 1, ymax - ymin + 1
    span = max(w, h)
    values = [0] * 64
    for x, y in cells:
        col = (2*(x - xmin) + span - w + 1)*4 // span
        row = (2*(y - ymin) + span - h + 1)*4 // span
        values[8*row + col] = 1
    return values


def layer(vector, weights, biases):
    return [b + sum(x*w for x, w in zip(vector, row)) for row, b in zip(weights, biases)]


def test(cpu):
    def cmd(line):
        cpu.stdin.write(line + '\n')
        cpu.stdin.flush()
        result = json.loads(cpu.stdout.readline())
        assert not isinstance(result, dict) or 'error' not in result, (line, result)
        return result

    def run(n=40000, x=0, y=0, pen=0):
        state = cmd(f'run {n} {x} {y} {pen}')
        assert state['running'] and not state['fault'], (oct(state['pc']), state['alarms'])
        return state

    def read(addr, n=1):
        return [v - (2**36 - 1) if v & (1 << 35) else v for v in cmd(f'peek {addr} {n}')]

    def press(bits):
        cmd(f'set ext {bits}')
        state = run(360000)
        cmd('set ext 0')
        run()
        return state

    def write(path):
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            steps = math.ceil(2 * math.hypot(bx-ax, by-ay))
            for i in range(steps + 1):
                t = i / steps
                run(x=round(-255 + 30*(ax + t*(bx-ax))), y=round(225 - 30*(ay + t*(by-ay))), pen=1)
        run()  # lift; do not send another pen hit through the raster

    cmd(f'load {TAPE}')
    cmd('set reader_us 64')
    cmd('set radius 22')
    cmd(f'press codabo {0o377750}')
    state = run(3000000)
    assert state['tape']['pos'] == state['tape']['size']
    assert [-255, 225, 0, 0o60] in state['display']
    assert read(RESULT) == [-1]
    assert not any(x > 255 for x, *_ in press(1)['display']), 'blank generated a result'
    # One stationary hit must use the coordinate of the illuminated spot.
    run(x=195, y=-225, pen=1)
    run()
    assert read(BITMAP, 256) == [0]*255 + [1]
    press(2)

    model = json.loads(MODEL.read_text())
    paths = {
        7: [(3, 3), (12, 3), (6, 13)],
        1: [(8, 2), (8, 13)],
        0: [(8, 2), (11, 3), (12, 7), (12, 10), (10, 13), (6, 13), (3, 10), (3, 6), (5, 3), (8, 2)],
    }
    for expected, path in paths.items():
        write(path)
        bitmap = read(BITMAP, 256)
        assert set(bitmap) == {0, 1}
        f = features(bitmap)
        h = [max(0, v) for v in layer(f, model['w1'], model['b1'])]
        scores = [2*v for v in layer(h, model['w2'], model['b2'])]
        state = press(1)
        assert read(FEATURES, 64) == f, 'bbox fit or binning mismatch'
        assert read(HIDDEN, 32) == h, 'ReLU layer mismatch'
        assert read(SCORES, 10) == scores, 'signed multiply-accumulate mismatch'
        assert scores.index(max(scores)) == expected and read(RESULT) == [expected], scores
        dots = {(x, y) for x, y, intensity, unit in state['display'] if x > 255 and intensity == 3 and unit == 0o60}
        assert dots == {(285 + 28*c, 84 - 28*r) for c, r in glyph(expected)}, (expected, dots)
        press(2)
        assert not any(x > 255 for x, *_ in run()['display']), 'clear did not remove the glyph'
        assert read(RESULT) == [-1] and read(BITMAP, 256) == [0]*256
    print('PASS: plugboard tape boot, pen hits, both integer layers, CRT digits 7/1/0, clear and blank')


def main():
    blocks = tx2tape.blocks(TAPE.read_bytes())
    assert blocks and all(block.get('checksum_ok') for block in blocks)
    cli = os.environ.get('TX2_CLI', str(ROOT / 'build/obj_cli/tx2-cli'))
    with subprocess.Popen([cli], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as cpu:
        test(cpu)


if __name__ == '__main__':
    main()
