#!/usr/bin/env python3
"""Build the TX-2 browser host as WebAssembly.

Outputs: build/wasm/tx2.js and build/wasm/tx2.wasm.
Requires em++ on PATH or an Emscripten SDK checkout at work/emsdk.
"""
from pathlib import Path
import argparse, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = Path('/usr/share/verilator/include')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emsdk', type=Path, default=ROOT / 'work/emsdk', help='Emscripten SDK checkout')
    args = p.parse_args()
    emxx = shutil.which('em++')
    if not emxx:
        candidate = args.emsdk / 'upstream/emscripten/em++'
        if not candidate.exists():
            raise SystemExit('em++ not found: install emsdk or pass --emsdk')
        emxx = str(candidate)
    out, cc = ROOT / 'build/wasm', ROOT / 'build/wasm_cc'
    # The sources are globbed below, so generated files from an older RTL must not linger.
    shutil.rmtree(cc, ignore_errors=True)
    cc.mkdir(parents=True); out.mkdir(parents=True, exist_ok=True)
    subprocess.run(['verilator', '--cc', '-O3', '-Wno-fatal', '--top-module', 'tx2_machine', '--Mdir', str(cc),
                    *map(str, sorted(path.relative_to(ROOT) for path in (ROOT / 'rtl').glob('*.v')))],
                   cwd=ROOT, check=True)
    sources = sorted(str(s) for s in cc.glob('Vtx2_machine*.cpp'))
    sources += [str(INCLUDE / 'verilated.cpp'), str(INCLUDE / 'verilated_threads.cpp'), str(ROOT / 'host/tx2_wasm.cpp')]
    # $readmemh in tx2_memory.v reads the power-up meta/parity images.
    embeds = []
    for name in ['core-init-65536-0.hex', 'core-init-65536-1.hex', 'core-init-4096-0.hex', 'core-init-4096-1.hex']:
        embeds += ['--embed-file', f'programs/{name}@programs/{name}']
    subprocess.run([emxx, '-O3', '-flto', '-std=c++17', '-DVL_IGNORE_UNKNOWN_ARCH', '-I', str(cc), '-I', str(INCLUDE), '-I', str(INCLUDE / 'vltstd'),
                    '-I', str(ROOT / 'host'), *sources, *embeds,
                    '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sENVIRONMENT=worker,node', '-sALLOW_MEMORY_GROWTH=1',
                    '-sEXPORTED_FUNCTIONS=_tx2_command,_malloc,_free',
                    '-sEXPORTED_RUNTIME_METHODS=UTF8ToString,stringToNewUTF8',
                    '-o', str(out / 'tx2.js')], cwd=ROOT, check=True)
    print('Built', out / 'tx2.js', out / 'tx2.wasm')

if __name__ == '__main__':
    main()
