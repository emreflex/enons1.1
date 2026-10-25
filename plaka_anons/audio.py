"""PCM sesleri önceden yükle; COM nesnelerini yalnızca işçi thread'inde kullan."""
from contextlib import contextmanager
import json
import hashlib
from pathlib import Path
import time
import wave

from .plates import announcement_keys, speech_inventory

FORMAT = (22050, 1, 2)  # Hz, kanal, byte/örnek


class SoundBank:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.pcm = {}
        manifest_path = self.directory / 'manifest.json'
        if not manifest_path.is_file():
            raise ValueError('Ses bankası hazır değil. Önce prepare_bank.py çalıştırın.')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for key in [*speech_inventory(), 'zil']:
            path = self.directory / f'{key}.wav'
            if not path.is_file():
                raise ValueError(f'Eksik ses: {path.name}')
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest.get(key):
                raise ValueError(f'Ses bankası doğrulaması başarısız: {path.name}')
            with wave.open(str(path), 'rb') as wav:
                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != FORMAT or wav.getcomptype() != 'NONE':
                    raise ValueError(f'{path.name}: 22050 Hz mono PCM16 gerekli.')
                data = wav.readframes(wav.getnframes())
                if not data or len(data) > FORMAT[0] * 2 * 60:
                    raise ValueError(f'{path.name}: boş veya 60 saniyeden uzun ses.')
                self.pcm[key] = data

    def compose(self, plate, reason):
        silence = b'\0\0' * int(FORMAT[0] * .065)
        return silence.join(self.pcm[k] for k in announcement_keys(plate, reason))


def list_music_sessions():
    from pycaw.pycaw import AudioUtilities
    result = {}
    for session in AudioUtilities.GetAllSessions():
        if session.Process and session.ProcessId:
            try:
                result[session.ProcessId] = session.Process.name()
            except Exception:
                # Kapanmış/korumalı süreçlerin adını okuyamayabiliriz.
                result[session.ProcessId] = f'PID {session.ProcessId}'
    return result


def fade(controls, targets, duration=.45):
    starts = [control.GetMasterVolume() for control in controls]
    steps = 20
    for step in range(1, steps + 1):
        for control, start, target in zip(controls, starts, targets):
            control.SetMasterVolume(start + (target - start) * step / steps, None)
        time.sleep(duration / steps)


@contextmanager
def duck_music(pid):
    """PID'ye ait tüm oturumları kıs; her hata yolunda eski seviyeyi geri yükle."""
    from pycaw.pycaw import AudioUtilities
    controls, originals = [], []
    if pid:
        for session in AudioUtilities.GetAllSessions():
            if session.ProcessId == pid:
                controls.append(session.SimpleAudioVolume)
        if not controls:
            raise RuntimeError('Seçili müzik uygulaması kapanmış. Listeyi yenileyip tekrar seçin.')
        originals = [control.GetMasterVolume() for control in controls]
    try:
        # Sessiz uygulamanın sesini açmamak için %15 üst sınırdır.
        fade(controls, [min(volume, .15) for volume in originals]) if controls else None
        yield
    finally:
        failures = []
        for control, original in zip(controls, originals):
            try:
                fade([control], [original])
            except Exception:
                try:
                    control.SetMasterVolume(original, None)
                except Exception as exc:
                    failures.append(str(exc))
        if failures:
            raise RuntimeError('Müzik sesi geri yüklenemedi; Windows mikserini kontrol edin: ' + '; '.join(failures))


class Player:
    def __init__(self, bank, stop_event):
        self.bank, self.stop = bank, stop_event

    def play(self, plate, reason, pid):
        import pygame
        import comtypes
        comtypes.CoInitialize()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=FORMAT[0], size=-16, channels=1, buffer=512)
            pcm = self.bank.compose(plate, reason)
            with duck_music(pid):
                self._sound(self.bank.pcm['zil'])
                time.sleep(.18)
                self._sound(pcm)
        finally:
            comtypes.CoUninitialize()

    def _sound(self, pcm):
        import pygame
        channel = pygame.mixer.Sound(buffer=pcm).play()
        if channel is None:
            raise RuntimeError('Ses oynatma kanalı açılamadı.')
        while channel.get_busy():
            if self.stop.wait(.02):
                channel.stop()
                raise RuntimeError('Anons durduruldu.')
