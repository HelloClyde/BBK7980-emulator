"""Check ZIP integrity, required files, demo provenance, and absence of device data."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

PACKAGE_ROOT = 'BBK7980'
DEMO = f'{PACKAGE_ROOT}/_internal/demo/minesweeper.exe'
HOST = f'{PACKAGE_ROOT}/BBK7980.exe'
REQUIRED = {HOST, DEMO, f'{PACKAGE_ROOT}/_internal/bbk7980.dll',
            f'{PACKAGE_ROOT}/_internal/vendor/fonts/unifont-18.0.01.hex.gz',
            f'{PACKAGE_ROOT}/_internal/vendor/fonts/OFL-1.1.txt',
            f'{PACKAGE_ROOT}/source/src/machine.c', f'{PACKAGE_ROOT}/source/vendor/s6502.c',
            f'{PACKAGE_ROOT}/demo-source/examples/minesweeper/main.c',
            f'{PACKAGE_ROOT}/demo-source/examples/minesweeper/COPYING',
            f'{PACKAGE_ROOT}/licenses/Python.txt'}


def verify(dist):
    digest, filename = (dist / 'SHA256SUMS.txt').read_text(encoding='ascii').split()
    if filename != Path(filename).name or not filename.endswith('-win64.zip'):
        raise ValueError(f'Unexpected archive filename: {filename}')
    archive = dist / filename
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError('ZIP SHA-256 mismatch')
    with ZipFile(archive) as release:
        names = release.namelist()
        if len(names) != len(set(names)) or not REQUIRED.issubset(names) or release.testzip():
            raise ValueError('ZIP is corrupt or incomplete')
        for name in names:
            path = PurePosixPath(name)
            if path.parts[0] != PACKAGE_ROOT or set(path.parts[1:]) & {'runtime', 'data', '..'}:
                raise ValueError(f'Unexpected path in ZIP: {name}')
            if name.endswith(('.exe', '.bin', '.upg', '.bin.z')) and name not in {
                HOST, DEMO, f'{PACKAGE_ROOT}/demo-source/examples/minesweeper/icon.bin'
            }:
                raise ValueError(f'Unexpected device or executable file: {name}')
        meta = json.loads(release.read(f'{PACKAGE_ROOT}/demo-source/BUILD.json'))
        if hashlib.sha256(release.read(DEMO)).hexdigest() != meta['demo_sha256']:
            raise ValueError('Bundled demo SHA-256 mismatch')
    print(f'{filename}: {len(names)} files, SHA-256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dist', type=Path)
    verify(parser.parse_args().dist)
