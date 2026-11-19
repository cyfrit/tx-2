#!/usr/bin/env python3
"""Deterministic unit-045/046 controller and Sketchpad tape acceptance.

TX2_CLI selects a private CLI build. The diagnostic encodes H63 instruction fields
directly. The Sketchpad image uses the M4-assembled listing.
Sources: device-specs/magnetic-tape.md §§3–5.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from test_sketchpad_functions import Sketchpad, BUTTONS, crt

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('TX2_CLI', ROOT / 'build/obj_cli/tx2-cli')).resolve()
MASK36 = (1 << 36) - 1


def instruction(op, address=0, j=0, cf=0, hold=True):
    return (int(hold) << 35) | (cf << 30) | (op << 24) | (j << 18) | address


def ios(unit, command, report=False):
    return instruction(0o04, command, unit, int(report))


def tsd(address):
    return instruction(0o57, address)


class Cli:
    def __init__(self):
        self.p = subprocess.Popen([str(BINARY)], cwd=ROOT, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)

    def cmd(self, text):
        self.p.stdin.write(text + '\n'); self.p.stdin.flush()
        result = json.loads(self.p.stdout.readline())
        assert not isinstance(result, dict) or 'error' not in result, (text, result)
        return result

    def poke(self, address, values):
        for i, v in enumerate(values):
            self.cmd(f'poke {address + i} {v}')

    def run(self, clocks=2_000_000):
        return self.cmd(f'run {clocks} 0 0 0')

    def program(self, unit, body):
        self.poke(0o100, [instruction(0o12, 0o200, unit), ios(unit, 0o50000),
                          instruction(0o05, 0o102, cf=0o20, hold=False)])
        self.poke(0o200, body + [0])
        self.cmd(f'press codabo {0o100}')
        for _ in range(8):
            state = self.run()
            if state['fault']:
                assert state['fault'] == 1, state
                return state
        raise AssertionError(('diagnostic did not finish', state))

    def close(self):
        self.p.terminate(); self.p.wait()


def diagnostics():
    cli = Cli()
    try:
        cli.cmd('dev magtape create 2 100')
        output = [0o777, 0o777] + [(i * 37 + 5) & 0o777 for i in range(512)] + [0o123, 0o456]
        cli.poke(0o10000, output)
        read_base = 0o12000
        body = [ios(0o46, 0o60002), ios(0o46, 0, True), instruction(0o30, read_base),
                ios(0o46, 0o30100), tsd(read_base + 1), ios(0o46, 0o30000),
                tsd(read_base + 2), ios(0o46, 0o30400)]
        body += [tsd(0o10000 + i) for i in range(len(output))]
        body[-1] &= ~(1 << 35) # as in WR2, wait for the last physical write before switching mode
        body += [ios(0o46, 0o30000)] + [tsd(read_base + 3 + i) for i in range(4)]
        body += [ios(0o46, 0o30104), tsd(read_base + 7), ios(0o46, 0o30004)]
        body += [tsd(read_base + 8 + i) for i in range(6)]
        body += [ios(0o46, 0o20000)]
        s = cli.program(0o46, body)
        got = cli.cmd(f'peek {read_base} 14')
        assert got[0] & (1 << 29), got # selection-complete report 4.3
        assert got[1:7] == [0, 6, 0, 6, 0, 0o16], got
        assert got[7:14] == [0, 6, 0, 0o456, 0o123, output[-3], output[-4]], got
        assert not s['units']['magtape']['eia'], s['units']['magtape']
        assert s['units']['magtape']['drives'][2]['written'] == 1
        # The transfer stream and marks survive a portable image save/load.
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / 'roundtrip.tx2mt'
            cli.cmd(f'dev magtape save 2 {image}')
            before = cli.cmd('dev magtape export 2')['image']
            cli.cmd('dev magtape eject 2'); cli.cmd(f'dev magtape load 2 {image}')
            assert cli.cmd('dev magtape export 2')['image'] == before
        # TM2 Fig.15-12: mode bit 1.2 enables nine lanes at four-bit spacing.
        cli.cmd('power')
        cli.program(0o46, [ios(0o46, 0o60002), ios(0o46, 0o30002)] +
                    [tsd(read_base + 10)] * 5 + [ios(0o46, 0o20000)])
        assert cli.cmd(f'peek {read_base + 10} 1')[0] == 0x333333BB3
        # Input overrun raises MISIND and the unit-041 missed-data bit 004.
        cli.cmd('power'); cli.cmd(f'set suppress {0o400}')
        cli.poke(0o100, [instruction(0o12, 0o300, 0o41), instruction(0o12, 0o200, 0o46),
                          ios(0o41, 0o30000), ios(0o46, 0o50000),
                          instruction(0o05, 0o104, cf=0o20, hold=False)])
        cli.poke(0o200, [ios(0o46, 0o60002), ios(0o46, 0o30000),
                          instruction(0o05, 0o202, hold=False),
                          ios(0o46, 0, True), instruction(0o30, read_base),
                          tsd(read_base + 3),
                          ios(0o46, 0o34000), ios(0o46, 0, True), instruction(0o30, read_base + 1),
                          ios(0o46, 0o20000), 0])
        cli.poke(0o300, [tsd(read_base + 2), ios(0o41, 0o40000),
                          instruction(0o05, 0o302, cf=0o20, hold=False)])
        cli.cmd(f'press codabo {0o100}'); cli.run(5000)
        assert cli.cmd('dev magtape status')['mis']
        cli.poke(0o202, [instruction(0o05, 0o203)])
        state = cli.run(5000)
        alarm = cli.cmd(f'peek {read_base} 3')
        assert alarm[0] & (1 << 12), alarm
        assert not alarm[1] & (1 << 12), alarm
        assert alarm[2] & 0o4, alarm
        # Mount failure and write protection raise equipment inability.
        cli.cmd('power'); cli.cmd('dev magtape protect 2 1')
        cli.program(0o46, [ios(0o46, 0o60002), ios(0o46, 0o30400),
                           ios(0o46, 0, True), instruction(0o30, read_base), ios(0o46, 0o20000)])
        assert cli.cmd(f'peek {read_base} 1')[0] & (1 << 13)
        # IBM normal transfers are 18-bit binary halfwords. The stopped gap does
        # not deliver the next record; reverse reads the record written above.
        cli.cmd('power'); cli.cmd('dev ibmtape create')
        halves = [0o654321, 0o3, 0o123456, 0o700001, 0o2, 0o777770, 0, 0o111111]
        cli.poke(0o10000, halves)
        body = [ios(0o45, 0o30015)] + [tsd(0o10000 + i) for i in range(len(halves))]
        body += [ios(0o45, 0o30017), ios(0o45, 0o30016)]
        body += [tsd(read_base + i) for i in range(len(halves))]
        body += [ios(0o45, 0o30013), ios(0o45, 0o30014), ios(0o45, 0o30012)]
        body += [tsd(read_base + 20 + i) for i in range(len(halves))]
        body += [ios(0o45, 0o30013), ios(0o45, 0o20000)]
        state = cli.program(0o45, body)
        assert cli.cmd(f'peek {read_base} {len(halves)}') == list(reversed(halves))
        assert cli.cmd(f'peek {read_base + 20} {len(halves)}') == halves
        assert state['units']['ibmtape']['records'] == 1
        image = cli.cmd('dev ibmtape export')['image']
        cli.cmd('dev ibmtape eject'); cli.cmd('dev ibmtape import ' + ' '.join(image.split()))
        assert cli.cmd('dev ibmtape export')['image'] == image
        print('PASS: 046 select/report, 9-bit forward/reverse, 9×4 assembly, immutable marks, image save/load, MISIND/041/clear, write-protect EIA; 045 18-bit records, reverse and image roundtrip')
    finally:
        cli.close()


class TapeSketchpad(Sketchpad):
    def __init__(self):
        self.p = subprocess.Popen([str(BINARY)], cwd=ROOT, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
        self.pen = (0, 0, 0); self.ext = 0
        self.cmd('load programs/sketchpad/sketchpad.tape'); self.cmd(f'set suppress {0o200}')
        self.cmd('set reader_us 64')
        self.cmd(f'press codabo {0o377750}')
        for _ in range(64):
            state = self.run(2_000_000)
            assert state['running'], ('Sketchpad boot stopped', state['alarms'], state['tape'])
            if state['tape']['pos'] >= state['tape']['size']:
                break
        else:
            raise AssertionError(('Sketchpad paper-tape boot timeout', state['tape']))
        self.run(1_000_000)
        self.run(800_000, -128, 110, 1)

    def wait_tape(self, name, predicate, max_steps=100):
        for _ in range(max_steps):
            s = self.run(2_000_000)
            if predicate(s['units'][name]):
                # WR disconnects between reverse and forward verification;
                # SRM also occurs between IBM positioning and verification.
                # Require a stable idle interval, not the first boundary.
                after = self.run(2_000_000)
                if predicate(after['units'][name]) and after['units'][name]['transfers'] == s['units'][name]['transfers']:
                    return after
        raise AssertionError((name, 'Sketchpad tape timeout', s['units'][name], s['k'], oct(s['pc'])))


def sketchpad_roundtrip(kind):
    BUTTONS.update(ibm=29, library=26)
    sp = TapeSketchpad()
    try:
        sp.press('draw'); sp.glide(-40, 160); sp.press('stop')
        before = sp.model(); points_before = sp.points()
        assert before['lines'] == 1, before
        if kind == 'ibmtape':
            sp.cmd('dev ibmtape create'); sp.cmd('set toggle 6 0')
            # TR296 Appendix B: META + IBM writes, IBM reads. The external
            # register's META bit is its separate physical pushbutton.
            sp.cmd('set emeta 1'); sp.press('ibm'); sp.cmd('set emeta 0')
            sp.wait_tape(kind, lambda s: s['records'] == 1 and s['operation'] == 3)
        else:
            sp.cmd('dev magtape create 0')
            sp.cmd(f'set toggle 7 {(0o372023 << 18) | 0o6006}')
            # LIBRARY is a read button; see TR296:3681–3684. Invoke the published
            # callable WRTX2 entry at 200127 through its existing sequence-76
            # caller by temporarily redirecting RDTX2's one-word entry veneer.
            # This executes the TX2WR/WR/search/reverse+forward checksum routines.
            read_entry = sp.cmd(f'peek {0o200126} 1')[0]
            write_entry = sp.cmd(f'peek {0o200127} 1')[0]
            sp.cmd(f'poke {0o200126} {write_entry}'); sp.press('library')
            sp.wait_tape(kind, lambda s: s['drives'][0]['written'] > 0 and not s['connected'])
            sp.cmd(f'poke {0o200126} {read_entry}')
        # Completion messages and the record/block verification finish before
        # deleting the only line. Reading the stored picture must recreate it.
        sp.run(2_000_000)
        sp.glide(-84, 135); sp.press('delete'); sp.press('stop')
        assert sp.model()['lines'] == 0, sp.model()
        prior = sp.cmd(f'dev {kind} status')['transfers']
        sp.press('ibm' if kind == 'ibmtape' else 'library')
        sp.wait_tape(kind, lambda s: s['transfers'] > prior and (s['operation'] == 3 if kind == 'ibmtape' else not s['connected']))
        sp.run(2_000_000)
        after = sp.model(); points_after = sp.points(); spots = crt(sp, 8)
        # Deleting a line leaves its independent point masters. The library
        # reader merges the recorded picture, so those two coordinates may
        # occur twice. Check the restored geometry and visible entity counts.
        assert sp.cmd(f'dev {kind} status')['eia'] == 0
        assert {k: v for k, v in after.items() if k != 'points'} == {k: v for k, v in before.items() if k != 'points'}, (kind, before, after)
        assert set(points_after) == set(points_before), (kind, points_before, points_after)
        assert len(spots) > 20, (kind, len(spots))
        print(f'PASS: Sketchpad {kind}: picture written, deleted, read back; model={after}, points={points_after}, CRT spots={len(spots)}')
    finally:
        sp.p.terminate(); sp.p.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-only', action='store_true')
    parser.add_argument('--sketchpad-only', choices=('ibmtape', 'magtape'))
    args = parser.parse_args()
    if not args.sketchpad_only:
        diagnostics()
    if not args.device_only:
        for kind in ([args.sketchpad_only] if args.sketchpad_only else ['ibmtape', 'magtape']):
            sketchpad_roundtrip(kind)


if __name__ == '__main__':
    main()
