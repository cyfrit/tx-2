#!/usr/bin/env python3
"""Simulation throughput: boot Sketchpad on the CLI host, then time steady running
with the pen tracking (the browser's common case). Prints clocks/s and instructions/s."""
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    cli = os.environ.get('TX2_CLI', str(ROOT / 'build/obj_cli/tx2-cli'))
    p = subprocess.Popen([cli], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    def cmd(line):
        p.stdin.write(line + '\n'); p.stdin.flush()
        return json.loads(p.stdout.readline())
    cmd('load programs/sketchpad/sketchpad.tape'); cmd(f'set suppress {0o200}'); cmd('set reader_us 64')
    cmd(f'press codabo {0o377750}')
    for _ in range(120):
        s = cmd('run 1000000 0 0 0')
        if s['tape']['pos'] == s['tape']['size'] and s['points']: break
    cmd('run 800000 -128 110 1')
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000_000
    c0, r0, t = s['cycles'], s['retired'], time.perf_counter()
    trail = hashlib.sha256()
    for _ in range(n // 200_000):
        s = cmd('run 200000 -128 110 1')
        trail.update(json.dumps(s, sort_keys=True).encode())
    dt = time.perf_counter() - t
    # The fingerprint covers every batch's full state (registers, CRT events, devices):
    # an optimization that changes behaviour changes it.
    print(json.dumps({'clocks_per_s': round((s['cycles'] - c0) / dt), 'instr_per_s': round((s['retired'] - r0) / dt),
                      'fault': s['fault'], 'seconds': round(dt, 2), 'retired': s['retired'],
                      'fingerprint': trail.hexdigest()[:16]}))
    p.stdin.close(); p.wait()

if __name__ == '__main__':
    main()
