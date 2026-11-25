"""Build the portable native CPU/board library without changing machine settings."""
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys

from machine import LIBRARY_NAME

ROOT = Path(__file__).resolve().parent


def build():
    out = ROOT / LIBRARY_NAME
    source = str(ROOT / 'src/machine.c')
    if sys.platform == 'darwin':
        subprocess.run(['xcrun', 'clang', '-arch', platform.machine(),
                        '-O2', '-std=gnu11', '-dynamiclib',
                        '-fvisibility=hidden', '-Wall', '-Wextra', source,
                        str(ROOT / 'src/audio_macos.c'), '-framework', 'AudioToolbox',
                        '-o', str(out)], check=True, cwd=ROOT)
        print(out)
        return
    if sys.platform.startswith('linux'):
        subprocess.run(['cc', '-O2', '-std=gnu11', '-shared', '-fPIC',
                        '-Wall', '-Wextra', source, '-o', str(out)], check=True, cwd=ROOT)
        print(out)
        return
    if sys.platform != 'win32':
        raise RuntimeError(f'Unsupported build platform: {sys.platform}')
    compiler = shutil.which("gcc") or "C:/msys64/ucrt64/bin/gcc.exe"
    if not Path(compiler).exists():
        raise RuntimeError("GCC not found. Install MSYS2 UCRT64 GCC or add gcc to PATH.")
    env = os.environ.copy()
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run([compiler, "-O2", "-std=gnu11", "-shared", "-static-libgcc",
                    "-Wall", "-Wextra", str(ROOT / "src/machine.c"), "-o", str(out)],
                   check=True, cwd=ROOT, env=env)
    print(out)


if __name__ == "__main__":
    build()
