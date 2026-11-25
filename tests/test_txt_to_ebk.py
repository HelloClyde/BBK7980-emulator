import codecs
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from file_transfer import read_import
from txt_to_ebk import encode_ebk, read_text


class EbookTests(unittest.TestCase):
    def test_three_font_tables_reference_gbk_lines(self):
        book = encode_ebk('中A\r\n' * 8 + '尾\t¥')
        body = ('中A\n' * 8 + '尾    ￥').encode('gbk')
        self.assertEqual(book[64:64 + len(body)], body)
        header = struct.unpack_from('<I3H3I', book, 14)
        self.assertEqual(header, (len(body), 3, 2, 2,
                                  64 + len(body), 76 + len(body), 84 + len(body)))
        for count, position, offsets in zip(header[1:4], header[4:],
                                              ((0, 16, 32), (0, 24), (0, 32))):
            self.assertEqual(struct.unpack_from(f'<{count}I', book, position), offsets)

    def test_encodings_and_input_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.txt'
            for encoded in (b'ASCII', codecs.BOM_UTF8 + 'GBK 中文'.encode(),
                            'GBK 中文'.encode('utf-16'), 'GBK 中文'.encode('utf-32'),
                            'GBK 中文'.encode('gb18030')):
                path.write_bytes(encoded)
                self.assertEqual(read_text(path), 'ASCII' if encoded == b'ASCII' else 'GBK 中文')
        for text in ('', '\0', '😀'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                encode_ebk(text)
        with patch('txt_to_ebk.MAX_PAGES', 2):
            with self.assertRaises(ValueError):
                encode_ebk('A\n' * 9)

    def test_cli_output_is_importable_and_requires_force_to_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / '小说.txt'
            source.write_text('正文\n', encoding='utf-8')
            command = [sys.executable, str(ROOT / 'txt_to_ebk.py'), str(source)]
            subprocess.run(command, check=True, capture_output=True)
            destination = source.with_suffix('.ebk')
            self.assertEqual(read_import(destination), ('小说.ebk', encode_ebk('正文\n'), 0))
            original = destination.read_bytes()
            source.write_text('新正文', encoding='utf-8')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            self.assertEqual(destination.read_bytes(), original)
            subprocess.run([*command, '--force'], check=True, capture_output=True)
            self.assertEqual(destination.read_bytes(), encode_ebk('新正文'))
