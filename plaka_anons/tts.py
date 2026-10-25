"""Yalnızca bir kerelik ses bankası hazırlığında kullanılan OpenAI TTS istemcisi.

Oynatıcı bu modülü yüklemez. API anahtarı dosyaya/kaynak koda yazılmaz.
Başarılı parçalar içerik adresli önbellekte tutulur; kesilen üretim sürdürülebilir.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request
import wave

ENDPOINT = 'https://api.openai.com/v1/audio/speech'
MODEL = 'gpt-4o-mini-tts'
VOICE = 'coral'
INSTRUCTIONS = (
    'Türkçe konuş. Doğal, sıcak, profesyonel bir kadın anons sesi kullan. '
    'İstanbul Türkçesiyle, orta tempoda, net ve sakin oku. '
    'Robotik, şarkılı veya abartılı bir ton kullanma. '
    'Yalnızca verilen metni seslendir; açıklama veya ilave söz ekleme. '
    'Bu kayıt diğer kelimelerle birleştirilecek. Her kayıtta aynı kadın ses '
    'karakterini, tempoyu ve mikrofon uzaklığını koru. '
    'Tek kelimelerde gereksiz dramatik vurgu ve uzun son duraklama yapma.'
)
MAX_RESPONSE = 12 * 1024 * 1024


def validate_wav(data):
    try:
        with wave.open(io.BytesIO(data), 'rb') as wav:
            if (wav.getcomptype() != 'NONE' or wav.getsampwidth() != 2 or
                    wav.getnchannels() not in (1, 2) or not 8000 <= wav.getframerate() <= 96000 or
                    not 0 < wav.getnframes() <= wav.getframerate() * 60):
                raise ValueError('TTS yanıtı desteklenen PCM16 WAV biçiminde değil.')
            expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            if len(wav.readframes(wav.getnframes())) != expected:
                raise ValueError('TTS yanıtı eksik WAV verisi içeriyor.')
    except (wave.Error, EOFError) as exc:
        raise ValueError('TTS servisi geçerli bir WAV dosyası döndürmedi.') from exc


def atomic_write(path, data):
    # Aynı filesystem üzerinde değiştir; kesilen indirmeyi geçerli önbellek sayma.
    fd, temporary = tempfile.mkstemp(prefix='.tts-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as target:
            target.write(data)
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class OpenAISpeech:
    def __init__(self, cache_directory):
        self.cache = Path(cache_directory)

    def render(self, text, target):
        payload = {'model': MODEL, 'voice': VOICE, 'input': text,
                   'instructions': INSTRUCTIONS, 'response_format': 'wav'}
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
        identity = hashlib.sha256(serialized).hexdigest()
        cached = self.cache / f'{identity}.wav'
        checksum = self.cache / f'{identity}.sha256'
        if cached.is_file() and checksum.is_file():
            data = cached.read_bytes()
            if hashlib.sha256(data).hexdigest() == checksum.read_text().strip():
                validate_wav(data)
                Path(target).write_bytes(data)
                return 'cached'
            raise ValueError('TTS önbelleği bozulmuş. İlgili önbellek dosyasını silip yeniden deneyin.')

        key = os.environ.get('TTS_API_KEY') or os.environ.get('OPENAI_API_KEY')
        if not key:
            raise RuntimeError(
                'Kadın sesi üretimi için TTS_API_KEY eksik. Anahtarı güvenli ortam '
                'ayarlarına ekleyin; sohbet mesajına veya kaynak koda yazmayın. '
                'ChatGPT aboneliği OpenAI API kredisi sağlamaz.')
        request = urllib.request.Request(ENDPOINT, data=serialized, method='POST', headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
            'Accept': 'audio/wav',
        })
        try:
            # TLS doğrulaması varsayılan olarak açık; endpoint sabit ve HTTPS'tir.
            # Gönderimden sonra belirsiz hatalarda otomatik tekrar ücret doğurabilir.
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            messages = {401: 'API anahtarı geçersiz veya kullanılabilir değil.',
                        403: 'API veya ağ erişimine izin verilmiyor.',
                        429: 'API kotası, bakiye veya hız sınırı kontrol edilmeli.'}
            raise RuntimeError(f'OpenAI TTS HTTP {exc.code}: ' + messages.get(
                exc.code, 'Servis isteği tamamlayamadı. Başarılı parçalar önbellekte korunur.')) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            # İstisnayı/istek başlıklarını basmayız; kimlik bilgisini sızdırmayız.
            raise RuntimeError('OpenAI TTS bağlantısı tamamlanamadı. api.openai.com ağ erişimini kontrol edin. '
                               'Belirsiz zaman aşımı için otomatik tekrar yapılmadı.') from None
        if len(data) > MAX_RESPONSE:
            raise ValueError('TTS yanıtı izin verilen boyutu aşıyor.')
        validate_wav(data)
        self.cache.mkdir(parents=True, exist_ok=True)
        atomic_write(cached, data)
        atomic_write(checksum, hashlib.sha256(data).hexdigest().encode('ascii'))
        Path(target).write_bytes(data)
        return 'generated'
