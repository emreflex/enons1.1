"""İnsan kayıtları, yerel Piper veya OpenAI kadın sesiyle 68 parçalık banka üret."""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave

from plaka_anons.plates import speech_inventory

RATE = 22050


def checked_file(path, expected):
    if not expected or len(expected) != 64 or hashlib.sha256(path.read_bytes()).hexdigest().lower() != expected.lower():
        raise ValueError(f'SHA-256 uyuşmuyor: {path.name}. Güvenilir yayıncının hash değerini kullanın.')


def normalize(source, target):
    """PCM WAV'ı ortak mono PCM16 biçimine getir; kısa kenar rampaları tıklamayı azaltır."""
    with wave.open(str(source), 'rb') as wav:
        channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
        if wav.getcomptype() != 'NONE' or width != 2 or channels not in (1, 2):
            raise ValueError(f'{source.name}: kaynak, mono/stereo 16-bit PCM WAV olmalı.')
        if not 8000 <= rate <= 96000 or not 0 < wav.getnframes() <= rate * 60:
            raise ValueError(f'{source.name}: örnekleme hızı veya süre geçersiz.')
        data = array('h', wav.readframes(wav.getnframes()))
        if sys.byteorder != 'little':
            data.byteswap()
    samples = [sum(data[i:i + channels]) / channels for i in range(0, len(data), channels)]
    # Kelime başı/sonunu kesmemek için 40 ms güvenlik payı bırak.
    voiced = [i for i, value in enumerate(samples) if abs(value) > 180]
    if not voiced:
        raise ValueError(f'{source.name}: kayıt sessiz veya seviyesi çok düşük.')
    pad = int(rate * .04)
    samples = samples[max(0, voiced[0] - pad):min(len(samples), voiced[-1] + pad + 1)]
    output = []
    for i in range(round(len(samples) * RATE / rate)):
        position = min(i * rate / RATE, len(samples) - 1)
        left = int(position)
        fraction = position - left
        output.append(samples[left] * (1 - fraction) + samples[min(left + 1, len(samples) - 1)] * fraction)
    # Başlangıç seviyesi yükseklik farklarını azaltır; kalite düşük kaydı düzeltmez.
    gain = min(3.0, 27000 / max(abs(value) for value in output))
    ramp = int(RATE * .008)
    pcm = b''.join(struct.pack('<h', round(value * gain * min(1, i / ramp, (len(output) - 1 - i) / ramp)))
                   for i, value in enumerate(output))
    write_wav(target, pcm)


def write_wav(path, pcm):
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(pcm)


def chime(path):
    samples = []
    for i in range(int(RATE * 1.35)):
        t = i / RATE
        value = 0
        for start, frequency in ((0, 880), (.32, 659.255)):
            elapsed = t - start
            if elapsed >= 0:
                envelope = min(1, elapsed / .012) * math.exp(-4.6 * elapsed)
                value += envelope * (math.sin(2 * math.pi * frequency * elapsed) + .17 * math.sin(2 * math.pi * frequency * 2 * elapsed))
        value *= min(1, (1.35 - t) / .04)
        samples.append(struct.pack('<h', round(10000 * value)))
    write_wav(path, b''.join(samples))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inventory', action='store_true', help='67 dosya adı ve kayıt metnini JSON olarak yazdır')
    group.add_argument('--input-dir', type=Path, help='Aynı dosya adlarıyla 67 insan kaydı içeren klasör')
    group.add_argument('--model', type=Path, help='Yerel Türkçe Piper .onnx modeli')
    group.add_argument('--openai', action='store_true', help='Bir kerelik OpenAI Coral kadın sesi üretimi (ücretli API)')
    parser.add_argument('--preview', action='store_true', help='--openai ile yalnızca bir örnek kadın anonsu üret')
    parser.add_argument('--cache-dir', type=Path, default=Path(__file__).resolve().parent / '.tts-cache')
    parser.add_argument('--model-sha256')
    parser.add_argument('--config-sha256', help='Modelin yanındaki .onnx.json dosyasının SHA-256 değeri')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'ses_bankasi')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.preview and not args.openai:
        parser.error('--preview yalnızca --openai ile kullanılabilir.')
    tts = None
    if args.openai:
        from plaka_anons.tts import OpenAISpeech
        tts = OpenAISpeech(args.cache_dir)
    if args.preview:
        target = args.output / 'kadin_ses_ornegi.wav'
        if target.exists() and not args.overwrite:
            parser.error('Örnek zaten var; yenilemek için --overwrite kullanın.')
        with tempfile.TemporaryDirectory(prefix='plaka-preview-') as temp:
            source = Path(temp) / 'raw.wav'
            tts.render('Dikkat. Yirmi üç, Adana Bilecik Ceyhan, sıfır yirmi üç plakalı araç sahibinin dikkatine. '
                       'Lütfen aracınızın yanına geliniz.', source)
            args.output.mkdir(parents=True, exist_ok=True)
            normalize(source, target)
        print(f'Kadın ses örneği hazır: {target}. Bu örnek tam 68 parçalık banka değildir.')
        return
    inventory = speech_inventory()
    if args.inventory:
        print(json.dumps({f'{key}.wav': text for key, text in inventory.items()}, ensure_ascii=False, indent=2))
        return
    if args.input_dir and args.input_dir.resolve() == args.output.resolve():
        parser.error('Kaynak kayıtlar ve çıktı klasörü farklı olmalı.')
    targets = [args.output / f'{key}.wav' for key in [*inventory, 'zil']] + [args.output / 'manifest.json']
    if not args.overwrite and any(path.exists() for path in targets):
        parser.error('Çıktılar zaten mevcut. Bilinçli yenileme için --overwrite kullanın.')
    if args.model:
        checked_file(args.model, args.model_sha256)
        checked_file(Path(str(args.model) + '.json'), args.config_sha256)
    args.output.mkdir(parents=True, exist_ok=True)
    # Tüm parçaları başarıyla üretmeden mevcut bankayı değiştirmeyiz.
    with tempfile.TemporaryDirectory(prefix='plaka-bank-') as temp:
        temporary = Path(temp)
        for key, text in inventory.items():
            print(f'{key}: {text}', flush=True)
            source = args.input_dir / f'{key}.wav' if args.input_dir else temporary / 'raw.wav'
            if tts:
                state = tts.render(text, source)
                print('  ' + ('Önbellekten alındı.' if state == 'cached' else 'OpenAI kadın sesi üretildi.'), flush=True)
            if args.model:
                child_env = os.environ.copy()
                child_env['PYTHONUTF8'] = '1'
                subprocess.run([sys.executable, '-m', 'piper', '--model', str(args.model.resolve()),
                                '--output_file', str(source)], input=text + '\n', text=True,
                               encoding='utf-8', env=child_env, check=True)
            normalize(source, temporary / f'{key}.wav')
        chime(temporary / 'zil.wav')
        manifest = {}
        for key in [*inventory, 'zil']:
            path = temporary / f'{key}.wav'
            manifest[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        # Tek tek atomik değiştirme; manifest en son yayımlanır. Kesinti doğrulamada yakalanır.
        for key in manifest:
            target = args.output / f'{key}.wav'
            staged = args.output / f'.{key}.tmp'
            staged.write_bytes((temporary / f'{key}.wav').read_bytes())
            staged.replace(target)
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        provenance = {'provider': 'openai' if args.openai else ('piper' if args.model else 'recordings'),
                      'ai_generated': bool(args.openai or args.model)}
        if args.openai:
            from plaka_anons.tts import MODEL, VOICE, INSTRUCTIONS
            provenance.update(model=MODEL, voice=VOICE, voice_style='Türkçe kadın anonsu', instructions=INSTRUCTIONS)
        (args.output / 'uretim_bilgisi.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    print('68 WAV hazır. Doğallığı dinleyerek onaylayın; model sesi kalite garantisi değildir.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Ses bankası hazırlanamadı: {exc}', file=sys.stderr)
        raise SystemExit(1)
