"""Ücretli/ağ çağrısı yapmadan TTS protokolünü ve kaldığı yerden devamı doğrula."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from plaka_anons.audio import SoundBank
from plaka_anons.tts import INSTRUCTIONS, OpenAISpeech
from prepare_bank import chime, main


class TTSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        chime(self.root / 'fixture.wav')
        self.wav = (self.root / 'fixture.wav').read_bytes()
        self.client = OpenAISpeech(self.root / 'cache')

    def tearDown(self):
        self.temp.cleanup()

    def test_no_key_means_no_network(self):
        with patch.dict('os.environ', {}, clear=True), patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(RuntimeError, 'TTS_API_KEY eksik'):
                self.client.render('Adana', self.root / 'out.wav')
            network.assert_not_called()

    def test_female_payload_and_no_second_charge(self):
        captured = []
        def respond(request, timeout):
            captured.append(json.loads(request.data))
            self.assertEqual(request.full_url, 'https://api.openai.com/v1/audio/speech')
            return io.BytesIO(self.wav)
        with patch.dict('os.environ', {'TTS_API_KEY': 'fake-test-only'}, clear=True), patch('urllib.request.urlopen', side_effect=respond) as network:
            self.assertEqual(self.client.render('Adana', self.root / 'first.wav'), 'generated')
            self.assertEqual(self.client.render('Adana', self.root / 'second.wav'), 'cached')
            self.assertEqual(network.call_count, 1)
        self.assertEqual(captured[0]['voice'], 'coral')
        self.assertEqual(captured[0]['response_format'], 'wav')
        self.assertIn('kadın', captured[0]['instructions'])
        self.assertEqual((self.root / 'first.wav').read_bytes(), (self.root / 'second.wav').read_bytes())
        # Önbellekte anahtar saklanmaz; yalnızca WAV ve checksum bulunur.
        self.assertEqual({p.suffix for p in (self.root / 'cache').iterdir()}, {'.wav', '.sha256'})
        with patch.dict('os.environ', {}, clear=True), patch('urllib.request.urlopen') as network:
            self.assertEqual(self.client.render('Adana', self.root / 'offline.wav'), 'cached')
            network.assert_not_called()

    def test_error_does_not_create_output_or_echo_secrets(self):
        failure = urllib.error.HTTPError('https://api.openai.com', 401, 'sensitive-provider-details', {}, None)
        with patch.dict('os.environ', {'TTS_API_KEY': 'fake-test-only'}, clear=True), patch('urllib.request.urlopen', side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                self.client.render('Adana', self.root / 'out.wav')
        self.assertNotIn('fake-test-only', str(caught.exception))
        self.assertNotIn('sensitive-provider-details', str(caught.exception))
        self.assertFalse((self.root / 'out.wav').exists())

    def test_bad_response_and_corrupt_cache_are_rejected(self):
        with patch.dict('os.environ', {'TTS_API_KEY': 'fake-test-only'}, clear=True), patch('urllib.request.urlopen', return_value=io.BytesIO(b'not audio')):
            with self.assertRaises(ValueError):
                self.client.render('Adana', self.root / 'out.wav')
        with patch.dict('os.environ', {'TTS_API_KEY': 'fake-test-only'}, clear=True), patch('urllib.request.urlopen', return_value=io.BytesIO(self.wav)):
            self.client.render('Adana', self.root / 'out.wav')
        cached = next((self.root / 'cache').glob('*.wav'))
        cached.write_bytes(b'corrupt')
        with patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'bozulmuş'):
                self.client.render('Adana', self.root / 'out.wav')
            network.assert_not_called()

    def test_complete_bank_pipeline_without_real_api(self):
        calls = []
        def fixture_render(client, text, target):
            calls.append(text)
            Path(target).write_bytes(self.wav)
            return 'generated'
        output = self.root / 'bank'
        with patch('sys.argv', ['prepare_bank.py', '--openai', '--output', str(output)]), \
                patch.object(OpenAISpeech, 'render', fixture_render), redirect_stdout(io.StringIO()):
            main()
        self.assertEqual(len(calls), 67)
        self.assertEqual(len(SoundBank(output).pcm), 68)
        provenance = json.loads((output / 'uretim_bilgisi.json').read_text(encoding='utf-8'))
        self.assertEqual(provenance['voice'], 'coral')
        self.assertTrue(provenance['ai_generated'])
        self.assertEqual(provenance['instructions'], INSTRUCTIONS)


if __name__ == '__main__':
    unittest.main()
