"""Build a desktop release archive without data from the local runtime."""
import hashlib
from importlib.metadata import distribution
import os
import platform
import plistlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
DOCS = ('README.md', 'COPYING', 'THIRD_PARTY.md', 'hardware.md')
SOURCE_FILES = ('VERSION', 'app.py', 'audio_output.py', 'build.py', 'file_transfer.py', 'keyboard.py',
                'machine.py', 'package.py', 'prepare.py', 'txt_to_ebk.py', 'requirements.txt',
                'requirements-build.txt', '.github/workflows/build-release.yml', *DOCS)
SOURCE_DIRS = ('assets', 'docs', 'src', 'tests', 'tools', 'vendor')


def release_version():
    version = (ROOT / 'VERSION').read_text().strip()
    ref = os.environ.get('GITHUB_REF', '')
    if ref.startswith('refs/tags/') and ref != f'refs/tags/v{version}':
        raise ValueError(f'Git tag does not match VERSION: {ref}')
    return version


def package_windows(version, dist):
    if struct.calcsize('P') != 8:
        raise RuntimeError('Use 64-bit Windows Python to build this archive')
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
    copy_licenses(licenses)
    for name in DOCS:
        shutil.copyfile(ROOT / name, bundle / name)

    archive = dist / f'BBK7980-emulator-{version}-win64.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=9) as release:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                release.write(path, f'BBK7980/{path.relative_to(bundle).as_posix()}')
        for path in source_files():
            release.write(path, f'BBK7980/source/{path.relative_to(ROOT).as_posix()}')
        demo_source = ROOT / 'build/demo-source'
        for path in sorted(demo_source.rglob('*')):
            if path.is_file():
                release.write(path, f'BBK7980/demo-source/{path.relative_to(demo_source).as_posix()}')
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / 'SHA256SUMS.txt').write_text(f'{sha}  {archive.name}\n', encoding='ascii')
    print(archive)


def source_files():
    for name in SOURCE_FILES:
        yield ROOT / name
    for directory in SOURCE_DIRS:
        for path in sorted((ROOT / directory).rglob('*')):
            relative = path.relative_to(ROOT)
            if (path.is_file() and not path.is_symlink()
                    and not set(relative.parts) & {'__pycache__', 'runtime', 'data'}
                    and not path.name.endswith(('.bin', '.bin.z', '.upg', '.exe',
                                                '.dll', '.dylib', '.so', '.icns'))):
                yield path


def copy_licenses(licenses):
    python_license = next((
        directory / name
        for directory in (Path(sys.base_prefix), Path(sysconfig.get_path('stdlib')))
        for name in ('LICENSE.txt', 'LICENSE_PYTHON.txt', 'LICENSE')
        if (directory / name).is_file()
    ), None)
    if python_license is None:
        raise FileNotFoundError('Python distribution license not found')
    shutil.copyfile(python_license, licenses / 'Python.txt')
    for name in ('Pillow', 'pefile', 'PyInstaller'):
        metadata = distribution(name)
        license_file = next(file for file in metadata.files
                            if file.name.lower() in ('license', 'license.txt', 'copying.txt'))
        shutil.copyfile(metadata.locate_file(license_file), licenses / f'{name}.txt')


def package_macos(version, dist):
    from tools.make_icon import make_icon

    import tkinter  # Fail before packaging if this interpreter has no Tk.

    arch = platform.machine()
    if arch not in ('arm64', 'x86_64'):
        raise RuntimeError(f'Unsupported macOS architecture: {arch}')
    work = ROOT / 'build/macos'
    work.mkdir(parents=True, exist_ok=True)
    icon = work / 'BBK7980.icns'
    make_icon(icon)
    archive = dist / f'BBK7980-emulator-{version}-macos-{arch}.zip'
    with tempfile.TemporaryDirectory(prefix='release-', dir=work) as staging:
        staging = Path(staging)
        output = staging / 'output'
        release = staging / 'BBK7980'
        release.mkdir()
        subprocess.run([
            sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
            '--name', 'BBK7980', '--distpath', str(output),
            '--workpath', str(work / 'work'), '--specpath', str(work),
            '--target-architecture', arch, '--icon', str(icon),
            '--osx-bundle-identifier', 'org.bbk7980.emulator',
            '--add-binary', f'{ROOT / "bbk7980.dylib"}:.',
            '--add-data', f'{ROOT / "VERSION"}:.',
            '--add-data', f'{ROOT / "vendor/fonts"}:vendor/fonts',
            str(ROOT / 'app.py'),
        ], check=True, cwd=ROOT)
        app = release / 'BBK7980.app'
        (output / app.name).rename(app)
        info = app / 'Contents/Info.plist'
        metadata = plistlib.loads(info.read_bytes())
        metadata.update(CFBundleDisplayName='步步高 7980 模拟器',
                        CFBundleShortVersionString=version, CFBundleVersion=version)
        info.write_bytes(plistlib.dumps(metadata))
        subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)

        for path in source_files():
            target = release / 'source' / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        for name in DOCS:
            shutil.copyfile(ROOT / name, release / name)
        licenses = release / 'licenses'
        licenses.mkdir()
        copy_licenses(licenses)

        # ditto preserves executable permissions and framework symlinks.
        temporary = staging / archive.name
        subprocess.run(['ditto', '-c', '-k', '--keepParent', str(release),
                        str(temporary)], check=True)
        temporary.replace(archive)
    checksum = archive.with_suffix('.sha256')
    checksum.write_text(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n',
                        encoding='ascii')
    print(archive)


def main():
    version = release_version()
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    if sys.platform == 'win32':
        package_windows(version, dist)
    elif sys.platform == 'darwin':
        package_macos(version, dist)
    else:
        raise RuntimeError('Portable packaging is available on Windows and macOS')


if __name__ == '__main__':
    main()
