"""Transfer files through the V1.10 firmware's PC-link screen."""
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile

from keyboard import KEYS
from tools.install_probe import Link

MAX_FILE_SIZE = 64 * 1024 * 1024
TRANSFER_MAGIC = b'BJBBK.110'


def validate_name(name):
    if (not name or name in ('.', '..') or name != name.strip()
            or any(char in '/\\:*?"<>|' or ord(char) < 32 for char in name)):
        raise ValueError('请填写完整文件名和扩展名，文件名不能含路径。')
    try:
        encoded = name.encode('gbk')
    except UnicodeEncodeError:
        raise ValueError('文件名含 7980 无法识别的字符，请改用 GBK 可表示的字。') from None
    if len(encoded) > 63:
        raise ValueError('文件名（含扩展名）最多占 63 个 GBK 字节。')


def read_import(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_SIZE + 128:
        raise ValueError('文件超过虚拟 NAND 容量。')
    data = path.read_bytes()
    name, flags = path.name, 0
    if data.startswith(TRANSFER_MAGIC):
        if len(data) < 128:
            raise ValueError('7980 传输包的头部不完整。')
        size, checksum, header_size = struct.unpack_from('<III', data, 96)
        if header_size != 128 or len(data) != 128 + size:
            raise ValueError('7980 传输包的长度无效。')
        name = data[32:96].split(b'\0', 1)[0].decode('gbk')
        flags = int.from_bytes(data[26:28], 'little')
        data = data[128:]
        if (sum(data) & 0xffffffff) != checksum:
            raise ValueError('7980 传输包校验失败。')
    elif path.suffix.lower() == '.exe':
        raise ValueError('请选择 7980 SDK 生成的 BJBBK.110 应用传输包。')
    if Path(name).suffix.lower() == '.upg':
        raise ValueError('请在首次启动时通过升级包导入系统固件。')
    if len(data) > MAX_FILE_SIZE:
        raise ValueError('文件超过虚拟 NAND 容量。')
    validate_name(name)
    return name, data, flags


def connect(machine):
    machine.lib.bbk_reset()
    machine.run(80_000_000)
    for key, delay in [('Next', 5_000_000)] * 10 + [('1', 30_000_000)]:
        code = KEYS[key]
        machine.lib.bbk_key(code // 8, code % 8, 1)
        machine.run(300_000)
        machine.lib.bbk_key(code // 8, code % 8, 0)
        machine.run(delay)
    link = Link(machine)
    link.connect()
    return link


def write_export(path, data):
    path = Path(path)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staged = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.close()
            staged.replace(path)
        finally:
            temporary.close()
            staged.unlink(missing_ok=True)
