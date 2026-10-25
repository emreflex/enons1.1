import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plaka_anons.plates import announcement_keys, number_keys, parse_plate, speech_inventory
from plaka_anons.store import Store
from plaka_anons.web import create_app
from plaka_anons.audio import SoundBank, duck_music
from prepare_bank import chime, normalize


class PlateTests(unittest.TestCase):
    def test_leading_zeros(self):
        self.assertEqual(number_keys('06'), ['sayi_0', 'sayi_6'])
        self.assertEqual(number_keys('023'), ['sayi_0', 'sayi_20', 'sayi_3'])
        self.assertEqual(number_keys('000'), ['sayi_0'] * 3)
        self.assertEqual(number_keys('1001'), ['sayi_1000', 'sayi_1'])
        self.assertEqual(number_keys('99999'), ['sayi_90', 'sayi_9', 'sayi_1000', 'sayi_9', 'sayi_100', 'sayi_90', 'sayi_9'])

    def test_normalization(self):
        self.assertEqual(parse_plate('23abc023'), ('23', 'ABC', '023'))
        self.assertEqual(parse_plate('06 ı 0001'), ('06', 'I', '0001'))
        for value in ['00 ABC 123', '82 AB 123', '23 Q 12', '23 W 12', '23 X 12', '23 Ç 12', '23 A 1', '<script>']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_plate(value)

    def test_complete_inventory(self):
        inventory = speech_inventory()
        self.assertEqual(len(inventory), 67)
        for province in range(1, 82):
            for digits in ('00', '023', '101', '1000', '99999'):
                self.assertTrue(set(announcement_keys(f'{province:02} ABC {digits}', 'standart')) <= inventory.keys())


class WebTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:')
        self.notified = []
        self.app = create_app(self.store, 'test-password', lambda: self.notified.append(True))
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.csrf = session['csrf']

    def tearDown(self):
        self.store.db.close()

    def login(self):
        return self.client.post('/api/login', data={'csrf': self.csrf, 'password': 'test-password'})

    def test_approval_flow(self):
        self.assertEqual(self.login().status_code, 200)
        self.assertIn('Araç plakası'.encode(), self.client.get('/').data)
        response = self.client.post('/api/requests', data={'csrf': self.csrf, 'plate': '23abc023', 'reason': 'far_acik'})
        self.assertEqual(response.status_code, 201)
        row = self.store.rows()[0]
        self.assertEqual((row['plate'], row['status']), ('23 ABC 023', 'pending'))
        self.assertEqual(self.notified, [True])
        self.assertIsNotNone(self.store.claim(row['id']))
        self.assertIsNone(self.store.claim(row['id']))
        self.store.finish(row['id'], 'done')
        self.assertEqual(self.store.rows()[0]['status'], 'done')

    def test_reject_bad_or_unauthorized_requests(self):
        self.assertEqual(self.client.post('/api/requests').status_code, 401)
        self.assertEqual(self.client.post('/api/login', data={'password': 'test-password'}).status_code, 403)
        self.assertEqual(self.client.post('/api/login', data={'csrf': 'yanlış'}).status_code, 403)
        self.assertEqual(self.client.post('/api/login', data={'csrf': self.csrf, 'password': 'yanlış'}).status_code, 401)
        self.login()
        for data, expected in [({}, 403), ({'csrf': self.csrf, 'plate': '82 AB 001', 'reason': 'standart'}, 400),
                               ({'csrf': self.csrf, 'plate': '23 AB 001', 'reason': 'unknown'}, 400)]:
            self.assertEqual(self.client.post('/api/requests', data=data).status_code, expected)
        self.assertEqual(self.store.rows(), [])

    def test_queue_capacity(self):
        for _ in range(200):
            self.store.add('23 ABC 023', 'standart')
        with self.assertRaises(ValueError):
            self.store.add('23 ABC 023', 'standart')

    def test_pending_persists_and_interrupted_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'queue.db'
            first = Store(path)
            id1 = first.add('06 A 023', 'standart')
            first.claim(id1)
            first.add('23 A 123', 'standart')
            first.db.close()
            second = Store(path)
            self.assertEqual({r['id']: r['status'] for r in second.rows()}, {1: 'error', 2: 'pending'})
            second.db.close()


class AudioTests(unittest.TestCase):
    def test_real_wav_loading_composition_and_integrity(self):
        # Sentetik ses yalnızca dosya/PCM testidir; konuşma kalitesi testi değildir.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chime(root / 'source.wav')
            normalize(root / 'source.wav', root / 'normalized.wav')
            content = (root / 'normalized.wav').read_bytes()
            manifest = {}
            for key in [*speech_inventory(), 'zil']:
                (root / f'{key}.wav').write_bytes(content)
                manifest[key] = hashlib.sha256(content).hexdigest()
            (root / 'manifest.json').write_text(json.dumps(manifest))
            bank = SoundBank(root)
            pcm = bank.compose('23 ABC 023', 'standart')
            self.assertGreater(len(pcm), len(content))
            (root / 'sayi_0.wav').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'doğrulaması'):
                SoundBank(root)

    def test_duck_restores_after_failure(self):
        import sys
        import types
        class Volume:
            value = .72
            def GetMasterVolume(self):
                return self.value
            def SetMasterVolume(self, value, _):
                self.value = value
        volume = Volume()
        session = types.SimpleNamespace(ProcessId=42, SimpleAudioVolume=volume)
        fake = types.ModuleType('pycaw.pycaw')
        fake.AudioUtilities = types.SimpleNamespace(GetAllSessions=lambda: [session])
        with patch.dict(sys.modules, {'pycaw': types.ModuleType('pycaw'), 'pycaw.pycaw': fake}), patch('plaka_anons.audio.time.sleep'):
            with self.assertRaisesRegex(RuntimeError, 'oynatma'):
                with duck_music(42):
                    self.assertAlmostEqual(volume.value, .15)
                    raise RuntimeError('oynatma hatası')
            self.assertAlmostEqual(volume.value, .72)


if __name__ == '__main__':
    unittest.main()
