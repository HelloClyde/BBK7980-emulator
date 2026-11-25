"""Host integration tests that need neither a display nor a firmware image."""
import ctypes
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import keyboard
import machine


class PlatformTests(unittest.TestCase):
    def test_mac_modifier_filter_and_shifted_digits(self):
        for symbol, digit in zip('!@#$%^&*()', '1234567890'):
            event = SimpleNamespace(keysym='', char=symbol, state=1)
            self.assertEqual(keyboard.host_key(event, macos=True), keyboard.KEYS[digit])
        for mask in (0x8, 0x10):
            event = SimpleNamespace(keysym='s', char='s', state=mask)
            self.assertIsNone(keyboard.host_key(event, macos=True))
            self.assertEqual(keyboard.host_key(event), keyboard.KEYS['s'])

    def test_mac_keypad_matches_number_row(self):
        for digit in '0123456789':
            event = SimpleNamespace(keysym=f'KP_{digit}', char=digit, state=0)
            self.assertEqual(keyboard.host_key(event, macos=True), keyboard.KEYS[digit])
        enter = SimpleNamespace(keysym='KP_Enter', char='\r', state=0)
        self.assertEqual(keyboard.host_key(enter, macos=True), keyboard.KEYS['Return'])

    def test_windows_shifted_digit_uses_virtual_key(self):
        event = SimpleNamespace(keysym='exclam', char='!', keycode=0x31)
        self.assertEqual(keyboard.host_key(event, windows=True), keyboard.KEYS['1'])

    def test_runtime_defaults_and_override(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, 'frozen', True, create=True):
                with patch.object(sys, 'platform', 'darwin'):
                    self.assertEqual(machine.default_runtime(),
                                     Path.home() / 'Library/Application Support/BBK7980/runtime')
                    with patch.dict(os.environ, {'BBK7980_RUNTIME': '~/bbk-custom'}):
                        self.assertEqual(machine.default_runtime(), Path.home() / 'bbk-custom')
                with patch.object(sys, 'platform', 'win32'):
                    self.assertEqual(machine.default_runtime(), machine.APP_DIR / 'runtime')
            self.assertEqual(machine.default_runtime(), machine.APP_DIR / 'runtime')

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS native audio ABI')
    def test_macos_audio_entry_points(self):
        lib = ctypes.CDLL(str(machine.RESOURCE_DIR / machine.LIBRARY_NAME))
        for name in ('bbk_out_open', 'bbk_out_write', 'bbk_out_clear', 'bbk_out_close'):
            self.assertIsNotNone(getattr(lib, name))
