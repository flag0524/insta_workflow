"""Offline validation tests. Fake image bytes are never sent to the renderer."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verified_media import VerificationPending, inspect_verified, _segments


class VerifiedMediaTests(unittest.TestCase):
    def setUp(self):
        fixed = os.getenv("VERIFIED_TEST_ROOT")
        if fixed:
            self.root = Path(fixed) / self._testMethodName
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
            self.addCleanup(self.temp.cleanup)
            self.root = Path(self.temp.name)
        self.post = {'id': 'demo_01'}
        self.base = self.root / 'verified_media' / self.post['id']
        self.base.mkdir(parents=True, exist_ok=True)
        self.payload = b'validation-only-fixture-not-an-image'
        (self.base / 'capture.png').write_bytes(self.payload)
        self.data = {
            'approved': True, 'evidence_type': 'actual_tool_capture',
            'verified_by': 'reviewer', 'verified_at': '2026-10-19T12:00:00+09:00',
            'capture_date': '2026-10-18', 'tool_model': 'Example tool / model v1',
            'narration': '직접 실행한 화면입니다. 결과를 확인합니다.',
            'caption': '검토된 설명', 'actual_results': '실제 출력 파일 1개 확인',
            'assets': [{'file': 'capture.png', 'duration_sec': 5,
                        'sha256': hashlib.sha256(self.payload).hexdigest()}]}
        # Any accidental external command/network access is a failing test.
        self.network = patch('socket.socket', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.process = patch('subprocess.run', side_effect=AssertionError('Renderer forbidden'))
        self.process.start()
        self.addCleanup(self.process.stop)

    def save(self):
        (self.base / 'manifest.json').write_text(json.dumps(self.data), encoding='utf-8')

    def check_blocked(self):
        self.save()
        with self.assertRaises(VerificationPending):
            inspect_verified(self.post, self.root)

    def test_missing_manifest(self):
        with self.assertRaises(VerificationPending):
            inspect_verified(self.post, self.root)

    def test_unapproved(self):
        for value in (False, 'true', 1, None):
            with self.subTest(value=value):
                self.data['approved'] = value
                self.check_blocked()

    def test_traversal_and_absolute(self):
        for value in ('../capture.png', '/tmp/capture.png', 'C:/capture.png',
                      '..\\capture.png', 'folder/../../capture.png'):
            with self.subTest(value=value):
                self.data['assets'][0]['file'] = value
                self.check_blocked()

    def test_invalid_post_id(self):
        with self.assertRaises(VerificationPending):
            inspect_verified({'id': '../escape'}, self.root)

    def test_hash_mismatch(self):
        self.data['assets'][0]['sha256'] = '0' * 64
        self.check_blocked()

    def test_missing_asset(self):
        (self.base / 'capture.png').unlink()
        self.check_blocked()

    def test_invalid_metadata(self):
        for field, value in [('evidence_type', 'generated_ui'), ('verified_at', 'yesterday'),
                             ('verified_by', ''), ('tool_model', ''), ('caption', ''),
                             ('actual_results', ''), ('narration', ''), ('capture_date', 'bad')]:
            with self.subTest(field=field):
                old = self.data[field]
                self.data[field] = value
                self.check_blocked()
                self.data[field] = old

    def test_invalid_duration(self):
        for value in (0, -1, 121, True, float('nan'), float('inf'), '5'):
            with self.subTest(value=value):
                self.data['assets'][0]['duration_sec'] = value
                self.check_blocked()

    def test_empty_assets(self):
        self.data['assets'] = []
        self.check_blocked()

    def test_valid_metadata(self):
        self.save()
        result = inspect_verified(self.post, self.root)
        self.assertEqual(result['caption'], self.data['caption'])
        self.assertEqual(result['actual_results'], self.data['actual_results'])
        self.assertEqual(result['assets'][0]['path'], (self.base / 'capture.png').resolve())
        self.assertEqual(result['capture_date'], '2026-10-18')
        self.assertEqual(result['tool_model'], self.data['tool_model'])

    def test_optional_capture_date(self):
        del self.data['capture_date']
        self.save()
        self.assertNotIn('capture_date', inspect_verified(self.post, self.root))

    def test_tts_segment_limit(self):
        for text in ('가' * 601, '안녕하세요. ' * 120):
            chunks = list(_segments(text))
            self.assertTrue(chunks)
            self.assertTrue(all(0 < len(chunk) <= 200 for chunk in chunks))
            self.assertEqual(''.join(text.split()), ''.join(''.join(chunks).split()))


if __name__ == '__main__':
    unittest.main()
