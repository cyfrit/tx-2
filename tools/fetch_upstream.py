#!/usr/bin/env python3
"""Fetch the reference software at the revisions used by this project."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIMULATOR_REV = '7480ac70bfece86c58b28a9f085ab4fe63880aae'
SKETCHPAD_REV = '3d134b23d207f169d0fb65ac5768177867689ed2'


def main():
    upstream = ROOT / 'upstream'
    upstream.mkdir(exist_ok=True)
    for name, revision in [('TX-2-simulator', SIMULATOR_REV), ('Sketchpad', SKETCHPAD_REV)]:
        path = upstream / name
        if not path.exists():
            subprocess.run(['git', 'clone', '--no-checkout', f'https://github.com/TX-2/{name}.git', path], check=True)
            subprocess.run(['git', '-C', path, 'checkout', '--detach', revision], check=True)
        head = subprocess.check_output(['git', '-C', path, 'rev-parse', 'HEAD'], text=True).strip()
        if head != revision:
            raise SystemExit(f'{path}: expected {revision}, found {head}')


if __name__ == '__main__':
    main()
