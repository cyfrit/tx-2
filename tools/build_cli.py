#!/usr/bin/env python3
"""Build the native TX-2 command-line host at build/obj_cli/tx2-cli."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir', default='build/obj_cli', help='output directory relative to the repository')
    FOLDER = ROOT / p.parse_args().build_dir
    FOLDER.mkdir(parents=True, exist_ok=True)
    # Rebuild the host object to refresh dependencies after device headers move.
    for stale in ('tx2_cli.o', 'tx2_cli.d'): (FOLDER / stale).unlink(missing_ok=True)
    flags = {'fast': '-O3', 'global': '-O3', 'slow': '-O1', 'cflags': '-O3 -march=native -flto=auto'}
    marker = FOLDER / 'build-flags.json'
    if not marker.exists() or json.loads(marker.read_text()) != flags:
        for path in FOLDER.iterdir():
            if path.is_file() and path.suffix in ('.o', '.a', '.gch'): path.unlink()
    subprocess.run(['verilator', '--cc', '--exe', '-O3', '-Wno-fatal', '--top-module', 'tx2_machine', '--Mdir', str(FOLDER),
                    '-CFLAGS', '-O3 -march=native -flto=auto -std=c++17', '-LDFLAGS', '-flto=auto',
                    *map(str, sorted(path.relative_to(ROOT) for path in (ROOT / 'rtl').glob('*.v'))),
                    str(ROOT / 'host/tx2_cli.cpp'), '-o', 'tx2-cli'],
                   cwd=ROOT, check=True)
    # Verilator's default OPT_FAST=-Os comes after -CFLAGS and overrides -O3.
    subprocess.run(['make', '-C', str(FOLDER), '-f', 'Vtx2_machine.mk', '-j', '4',
                    'OPT_FAST=-O3', 'OPT_GLOBAL=-O3', 'OPT_SLOW=-O1'], cwd=ROOT, check=True)
    marker.write_text(json.dumps(flags, indent=2) + '\n')
    print('Built', FOLDER / 'tx2-cli')

if __name__ == '__main__':
    main()
