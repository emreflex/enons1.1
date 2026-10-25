"""Türk plakalarını çözümle ve ses bankası anahtarlarına dönüştür."""
import re

# Türkiye'de kullanılan 23 Latin plaka harfi. Bu, ICAO alfabesi değil,
# kullanıcının istediği Türkiye şehir/ad esaslı heceleme sözlüğüdür.
LETTERS = dict(zip('ABCDEFGHIJKLMNOPRSTUVYZ', (
    'Adana', 'Bilecik', 'Ceyhan', 'Denizli', 'Edirne', 'Fatsa', 'Giresun',
    'Hatay', 'Isparta', 'Jandarma', 'Kayseri', 'Lüleburgaz', 'Manisa',
    'Niğde', 'Ordu', 'Polatlı', 'Rize', 'Sinop', 'Trabzon', 'Urfa',
    'Van', 'Yozgat', 'Zonguldak')))
NUMBERS = {i: word for i, word in enumerate((
    'sıfır', 'bir', 'iki', 'üç', 'dört', 'beş', 'altı', 'yedi', 'sekiz',
    'dokuz', 'on', 'on bir', 'on iki', 'on üç', 'on dört', 'on beş',
    'on altı', 'on yedi', 'on sekiz', 'on dokuz'))}
NUMBERS.update(dict(zip(range(20, 100, 10),
                       ('yirmi', 'otuz', 'kırk', 'elli', 'altmış', 'yetmiş', 'seksen', 'doksan'))))
NUMBERS.update({100: 'yüz', 1000: 'bin'})
REASONS = {
    'standart': ('Standart', 'Lütfen aracınızın yanına geliniz.'),
    'hatali_park': ('Hatalı park', 'Aracınız geçişi engellemektedir. Lütfen aracınızın yerini değiştiriniz.'),
    'far_acik': ('Far açık', 'Aracınızın farları açık kalmıştır. Lütfen kontrol ediniz.'),
    'cam_acik': ('Cam açık', 'Aracınızın camı açık kalmıştır. Lütfen kontrol ediniz.'),
    'kapi_acik': ('Kapı açık', 'Aracınızın kapısı açık kalmıştır. Lütfen kontrol ediniz.'),
    'alarm': ('Alarm çalıyor', 'Aracınızın alarmı çalmaktadır. Lütfen kontrol ediniz.'),
    'vale': ('Araç hazır', 'Aracınız teslim için hazırdır. Lütfen vale noktasına geliniz.'),
    'cekilme': ('Çekilme uyarısı', 'Lütfen aracınızı bulunduğu yerden alınız.'),
    'otopark': ('Otopark', 'Lütfen otopark görevlisi ile iletişime geçiniz.'),
    'guvenlik': ('Güvenlik', 'Lütfen güvenlik noktasına geliniz.'),
    'acil': ('Acil çağrı', 'Lütfen en kısa sürede aracınızın yanına geliniz.'),
}
PHRASES = {'dikkat': 'Dikkat.', 'plakali_arac': 'Plakalı araç sahibinin dikkatine.',
           'misafirler': 'Sayın misafirlerimiz.'}
PHRASES.update({f'sebep_{key}': text for key, (_, text) in REASONS.items()})


def parse_plate(value):
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError('Geçerli bir plaka giriniz.')
    compact = re.sub(r'\s+', '', value.replace('ı', 'I').upper())
    match = re.fullmatch(r'(0[1-9]|[1-7][0-9]|8[01])([A-PR-VYZ]{1,3})([0-9]{2,5})', compact)
    if not match:
        raise ValueError('01–81 il kodu, 1–3 plaka harfi ve 2–5 son rakam giriniz. Örnek: 23 ABC 023')
    return match.groups()


def number_keys(digits):
    """Baştaki sıfırları koru; kalan kısmı Türkçe basamaklarla oku."""
    keys = []
    rest = digits
    while rest.startswith('0'):
        keys.append('sayi_0')
        rest = rest[1:]
    if not rest:
        return keys
    number = int(rest)
    if number >= 1000:
        thousands, number = divmod(number, 1000)
        if thousands != 1:
            keys.extend(number_keys(str(thousands)))
        keys.append('sayi_1000')
    if number >= 100:
        hundreds, number = divmod(number, 100)
        if hundreds != 1:
            keys.append(f'sayi_{hundreds}')
        keys.append('sayi_100')
    if number >= 20:
        tens, number = divmod(number, 10)
        keys.append(f'sayi_{tens * 10}')
    if number:
        keys.append(f'sayi_{number}')
    return keys


def announcement_keys(plate, reason):
    if reason not in REASONS:
        raise ValueError('Geçersiz anons sebebi.')
    province, letters, digits = parse_plate(plate)
    return (['dikkat'] + number_keys(province) +
            [f'harf_{letter}' for letter in letters] + number_keys(digits) +
            ['plakali_arac', f'sebep_{reason}'])


def speech_inventory():
    # 23 harf + 30 sayı + 14 ifade = 67 konuşma; zil ile toplam 68 WAV.
    return {**{f'harf_{k}': v for k, v in LETTERS.items()},
            **{f'sayi_{k}': v for k, v in NUMBERS.items()}, **PHRASES}
