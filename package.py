"""Build a Windows x64 portable ZIP without data from the local runtime."""
import hashlib
from importlib.metadata import distribution
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
DOCS = ('README.md', 'COPYING', 'THIRD_PARTY.md', 'hardware.md')
SOURCE_FILES = ('VERSION', 'app.py', 'audio_output.py', 'build.py', 'file_transfer.py', 'keyboard.py',
                'machine.py', 'package.py', 'prepare.py', 'requirements.txt',
                'requirements-build.txt', *DOCS)
SOURCE_DIRS = ('assets', 'docs', 'src', 'tests', 'tools', 'vendor')


def main():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise RuntimeError('Use 64-bit Windows Python to build this archive')
    version = (ROOT / 'VERSION').read_text().strip()
    ref = os.environ.get('GITHUB_REF', '')
    if ref.startswith('refs/tags/') and ref != f'refs/tags/v{version}':
        raise ValueError(f'Git tag does not match VERSION: {ref}')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    work = ROOT / 'build/portable'
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
        '--name', 'BBK7980', '--distpath', str(work / 'output'),
        '--workpath', str(work / 'work'), '--specpath', str(work),
        '--add-binary', f'{ROOT / "bbk7980.dll"};.',
        '--add-data', f'{ROOT / "VERSION"};.',
        '--add-data', f'{ROOT / "vendor/fonts"};vendor/fonts',
        '--add-data', f'{ROOT / "build/demo/minesweeper.exe"};demo', str(ROOT / 'app.py')
    ], cwd=ROOT, check=True)

    bundle = work / 'output/BBK7980'
    licenses = bundle / 'licenses'
    licenses.mkdir()
    prefix = Path(sys.base_prefix)
    for name in ('LICENSE.txt', 'LICENSE_PYTHON.txt'):
        if (prefix / name).is_file():
            shutil.copyfile(prefix / name, licenses / 'Python.txt')
            break
    else:
        raise FileNotFoundError('Python distribution license not found')
    for name in ('Pillow', 'pefile', 'PyInstaller'):
        metadata = distribution(name)
        license_file = next(file for file in metadata.files
                            if file.name.lower() in ('license', 'license.txt', 'copying.txt'))
        shutil.copyfile(metadata.locate_file(license_file), licenses / f'{name}.txt')
    for name in DOCS:
        shutil.copyfile(ROOT / name, bundle / name)

    archive = dist / f'BBK7980-emulator-{version}-win64.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=9) as release:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                release.write(path, f'BBK7980/{path.relative_to(bundle).as_posix()}')
        for name in SOURCE_FILES:
            release.write(ROOT / name, f'BBK7980/source/{name}')
        for directory in SOURCE_DIRS:
            for path in sorted((ROOT / directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    release.write(path, f'BBK7980/source/{path.relative_to(ROOT).as_posix()}')
        demo_source = ROOT / 'build/demo-source'
        for path in sorted(demo_source.rglob('*')):
            if path.is_file():
                release.write(path, f'BBK7980/demo-source/{path.relative_to(demo_source).as_posix()}')
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / 'SHA256SUMS.txt').write_text(f'{sha}  {archive.name}\n', encoding='ascii')
    print(archive)


if __name__ == '__main__':
    main()
