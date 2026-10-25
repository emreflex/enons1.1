# Türkçe Plaka Anons

Telefon → Wi-Fi / Flask → SQLite onay kuyruğu → Windows Tkinter paneli →
uygulama sesini kıs → ding-dong → yerel WAV anons → eski ses seviyesine dön.

Anons başına internet, bulut API'si, abonelik veya TTS çağrısı yoktur.
Sesler başlangıçta RAM'e alınır. Tüm oynatmalar tek işçi tarafından sıralı yapılır;
hiçbir telefon isteği kendiliğinden anons edilmez. Ses kısma ve zil nedeniyle
anons başlangıcında bilinçli bir bekleme vardır; **sıfır gecikme garantisi yoktur**.

## Ses doğallığı: önce bunu okuyun

Windows SAPI/pyttsx3 gibi standart sistem seslerine geri dönüş yapılmaz.
Eksik banka varsa uygulama açık hata verir, robotik sesle devam etmez.

En güvenilir doğal sonuç, aynı konuşmacının aynı mikrofon ve ortamda okuduğu
insan kayıtlarıdır. Alternatif olarak, dinleyip beğendiğiniz bir **yerel Türkçe
sinirsel Piper modeli** veya **OpenAI Coral kadın sesi** ile tek seferde banka hazırlayabilirsiniz. Her Piper
modeli stüdyo kalitesinde değildir; kod ses kalitesini garanti edemez.
Kelime tabanlı birleştirme, insan kayıtlarında bile cümle tonlamasında kesikler
oluşturabilir. Kesintisiz cümle doğallığı vazgeçilmezse, 68 parçalık kısıtın
yerine her onayda bütün cümleyi üreten yerel neural TTS gerekir.

Ses dosyaları veya lisanslı bir model bu depoya dahil değildir. Otomatik ve
belirsiz kaynaklardan ses indiren bir betik yoktur. Python/kütüphane/model ilk
edinimi internet gerektirebilir; hazırlanmış uygulamanın günlük kullanımı gerektirmez.
İnsan seslendirmesi bedelsiz olmayabilir; lisansı izin veren bir modelle kendi
donanımınızda üretim API ücreti gerektirmez. Model lisansını ayrıca kontrol edin.

## Windows kurulumu

Windows 10/11, Python **3.11 veya 3.12 (64-bit)** önerilir. Python yükleyicisinde
Tcl/Tk bileşeni seçili olsun. PowerShell, proje klasöründe:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### A. İnsan kayıtlarından ses bankası (doğallık için önerilen)

```powershell
.\.venv\Scripts\python.exe prepare_bank.py --inventory
```

Çıktıdaki 67 dosya adı ve metin için ayrı WAV hazırlayın. Aynı konuşmacı,
aynı ton, aynı ses şiddeti; kısa, nötr kelime okumaları kullanın. Kaynaklar
8–96 kHz, mono/stereo, **16-bit PCM WAV** olmalı. MP3'ün adını WAV yapmayın.
`kayitlar` klasörüne koyun:

```powershell
.\.venv\Scripts\python.exe prepare_bank.py --input-dir .\kayitlar
```

Betik ortak 22050 Hz mono PCM16 biçimine çevirir, kenar sessizliklerini güvenlik
payıyla kısaltır ve tıklamaları azaltan kısa rampalar uygular. Konuşma parçasının
kalitesi bu işlemle yapay olarak iyileştirilmez. 68'inci dosya özgün sentezlenen
iki notalı `zil.wav` olur. Dosya hash'leri `manifest.json` içinde kaydedilir;
sonradan bozulan/değişen dosyalar başlangıçta yakalanır. Yeniden üretim için
bilinçli olarak `--overwrite` ekleyin. Uygulama kapalıyken banka güncelleyin.

### B. Yerel neural Piper modeliyle üretim

Yalnızca hazırlık için ek bağımlılık:

```powershell
.\.venv\Scripts\python.exe -m pip install "piper-tts>=1.3,<2"
```

[Piper projesinin](https://github.com/OHF-Voice/piper1-gpl) işaret ettiği resmi
ses kataloğundan Türkçe (`tr_TR`) bir model seçin. `.onnx` ve aynı isimdeki
`.onnx.json` dosyasını yerel `modeller` klasörüne alın. Model kartını, ticari
kullanım koşullarını ve güvenilir yayıncının SHA-256 değerlerini kontrol edin.
Güvenilir model deposunun Git LFS SHA-256 nesne kimliği de model doğrulamasında
kullanılabilir. Kendi indirdiğiniz dosyanın hash'ini hesaplamak tek başına
kaynağın güvenilirliğini kanıtlamaz. Betik TLS veya hash doğrulamasını kapatmaz.

```powershell
.\.venv\Scripts\python.exe prepare_bank.py --model .\modeller\ses.onnx --model-sha256 YAYINCININ_64_HANELI_MODEL_SHA256_DEGERI --config-sha256 GUVENILIR_CONFIG_SHA256_DEGERI
```

Yer tutucuları gerçek doğrulanmış hash'lerle değiştirin. Betik 67 metni aynı
modelle üretir; her parçada modelin yeniden yüklenmesi nedeniyle hazırlık birkaç
dakika sürebilir. Hazır WAV bankasıyla Piper/ONNX uygulama çalışırken kullanılmaz.
Çok konuşmacılı model yerine tek konuşmacılı Türkçe bir model seçin.

### C. OpenAI ile tek seferlik Türkçe kadın sesi

`prepare_bank.py --openai` yolu **gpt-4o-mini-tts / coral** kullanır.
Seslendirme talimatı doğal, sıcak ve profesyonel **kadın anonsu** olarak sabittir;
tüm parçalar aynı ses ve talimatla üretilir. Erkek sesine veya Windows robotik
sesine otomatik geçiş yapılmaz. Doğallık ve telaffuz dinlenerek kontrol edilmelidir.

Bu yol sadece hazırlık aşamasında internet ve **ücretli OpenAI API erişimi**
gerektirir; ChatGPT Plus/Pro aboneliği API kredisi yerine geçmez. API anahtarını
kaynak koda, sohbet mesajına veya GitHub'a koymayın. Bulut ortamında güvenli
ortam ayarlarına `TTS_API_KEY` olarak ekleyin ve `api.openai.com` HTTPS erişimini
açın. Standart yerel kullanımda `OPENAI_API_KEY` de desteklenir. Ek Python
kütüphanesi gerekmez. Günlük anonslarda anahtar veya internet gerekmez.

Önce bir tam cümle örneği üretip Windows'ta dinleyin:

```powershell
.\.venv\Scripts\python.exe prepare_bank.py --openai --preview
Start-Process .\ses_bankasi\kadin_ses_ornegi.wav
```

Beğendiğinizde 67 konuşma parçası ve zili üretin:

```powershell
.\.venv\Scripts\python.exe prepare_bank.py --openai
.\.venv\Scripts\python.exe main.py
```

Örnek tam bir cümledir; parçaların birleştirildiği anonsu ayrıca kontrol edin.
Üretim başarısız olursa geçerli tam banka yayımlanmaz. Başarılı API yanıtları
`.tts-cache` içinde metin/model/ses/talimat kimliğiyle saklanır; aynı komutu tekrar
çalıştırmak tamamlanan parçalar için yeni API isteği yapmaz. Bu klasörü silerseniz
yeniden üretim ücretli olabilir. Belirsiz bağlantı hatalarında otomatik istek
tekrarı yapılmaz. `--overwrite` mevcut çıktıyı yeniler; aynı içerik için önbelleği
yine kullanır. Yeni bir ses kaydı istemek için ilgili önbelleği bilinçli silmek gerekir.

`uretim_bilgisi.json` sağlayıcı, model, ses ve yapay zekâ üretim bilgisini içerir;
anahtar içermez. Bu dosya, `manifest.json` ve 68 banka WAV'ı tamamlanmış banka
paketini oluşturur. Örnek ve önbellek uygulamanın çalışması için gerekli değildir.
Üretilmiş kayıtların yapay zekâ sesi olduğunu kullanıcılara açıkça belirtin.

**Bu depodaki durum:** TTS entegrasyonu ve taklit HTTP testleri hazırdır; gerçek
OpenAI kadın sesleri henüz üretilmemiştir. Üretim API anahtarı ve ağ erişimi bekler.
Üretim tamamlandığında WAV'lar ve manifest ayrıca depoya eklenmelidir; kaynak
kodunu indirmek şu aşamada hazır kadın ses bankası sağlamaz.

### Başlatma

```powershell
.\.venv\Scripts\python.exe main.py
```

1. Windows **varsayılan çıkış aygıtını amfiye bağlı ses kartı** yapın.
   Radyo/müzik uygulamasını da bu çıkışa yönlendirin. Çıkış aygıtını değiştirdiğinizde
   paneli yeniden başlatın. Uygulama işletim sisteminin varsayılan çıkışını kullanır.
2. Müzik uygulamasında çalmayı başlatın. Panelde **Uygulamaları yenile** ile
   uygulama/PID seçin. Aynı PID'nin tüm ses oturumları kısılır; tarayıcıda bu,
   başka sekmeleri de etkileyebilir. Yeni PID oluşursa yeniden seçin.
   Liste varsayılan Windows çıkışındaki oturumlarla sınırlıdır.
3. Telefonda aynı Wi-Fi ağı üzerinden bilgisayarın IPv4 adresini ve 5000 portunu
   kullanın. Panel adres adaylarını gösterir; gerektiğinde `ipconfig` ile doğrulayın.
4. Paneldeki o oturuma özel eşleştirme parolasını telefona girin, plakayı ve
   sebebi gönderin. Personelin parola dışında bir API anahtarı kullanması gerekmez.
5. Panelde isteği seçip **Seçileni onayla ve anons et** düğmesine basın.
   Hatalı isteği reddedebilirsiniz. Oynatma hatasında satırdaki açıklamayı okuyup
   sorunu giderdikten sonra yeniden onaylayabilirsiniz.

Windows Güvenlik Duvarı sorarsa yalnızca **Özel ağlar** için Python'a izin verin.
Router'da port yönlendirmesi açmayın. HTTP parolayı şifrelemez: yalnızca işletmenin
güvenilir yerel ağında kullanın; ortak/misafir Wi-Fi için ayrı ağ veya TLS ters
proxy gerekir. Eşleştirme, CSRF kontrolü, giriş hız sınırı ve 200 açık istek sınırı
vardır; bu çözüm internete açık bir servis olarak tasarlanmamıştır.
Werkzeug sunucusu tek HTTP iş parçacığıyla küçük yerel ekipler içindir; debug/reloader kapalıdır.

**Audio ducking:** yaklaşık 450 ms içinde uygulamanın mikser seviyesi en fazla
%15'e indirilir; zaten daha kısıksa sesi artırılmaz. Zil ve anonsun ardından
başlangıç seviyesi yaklaşık 450 ms'de geri yüklenir. Uygulama kapatma, durdurma
ve oynatma hatasında da geri yükleme denenir. Sürecin zorla sonlandırılması,
elektrik kesilmesi veya cihazın çıkarılması durumunda garanti verilemez;
Windows mikserini kontrol edin. Ana sistem sesi/mute durumu değiştirilmez.
Bildirim sesi `winsound` ile Windows ayarlarına bağlıdır; sistem sesleri kapalıysa duyulmayabilir.

## Plaka okuma ve bankanın içeriği

- `23 ABC 023` → dikkat / yirmi üç / Adana / Bilecik / Ceyhan / sıfır / yirmi / üç /
  plakalı araç sahibinin dikkatine / seçilen sebebin tam cümlesi.
- `06 A 0001` → sıfır / altı / Adana / sıfır / sıfır / sıfır / bir.
- 01–81 il kodları, 1–3 harf, 2–5 son rakam; bitişik veya boşluklu kabul edilir.
  Standart sivil plaka biçim ailesi desteklenir; tescil serisi uygunluğu doğrulanmaz.
  Diplomatik, geçici ve yabancı plakalar kapsam dışıdır. Q/W/X ve Türkçe özel
  harfler reddedilir; küçük `ı`, plaka harfi `I` olarak kabul edilir.
- Harfler şehir/ad esaslı Türkiye heceleme sözlüğüdür; kullanıcının verdiği
  Adana/Bilecik/Ceyhan örnekleri **ICAO uluslararası Alfa/Bravo/Charlie değildir**.
- Tam **68 WAV**: 23 harf, 30 sayı (0–19, 20–90 onluklar, yüz, bin),
  14 ifade (3 giriş/bağlaç ve 11 sebep), 1 zil. `misafirler` alternatif giriş
  kaydıdır; varsayılan anons `dikkat` kullanır.

Kuyruk `istekler.sqlite3` dosyasındadır. Bekleyen istekler yeniden açılışta korunur;
kesintiye uğramış anonslar hata durumuna alınır, otomatik tekrar oynatılmaz.
Panel açık istekleri önce, son 500 kaydı gösterir. Veritabanını uygulama kapalıyken
yedekleyin; plaka verisi içerdiğinden erişimini ve saklama süresini işletme belirlemelidir.

## Dosyalar ve doğrulama

`main.py`: panel ve servis yaşam döngüsü. `prepare_bank.py`: banka üretimi.
`plaka_anons/plates.py`: çözümleme. `audio.py`: PCM ve Windows ses oturumları.
`store.py`: kalıcı kuyruk. `web.py` ve `templates/index.html`: telefon arayüzü.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testler plaka/sıfırlar, tüm banka anahtarları, gerçek PCM dosyası işlemleri,
hash kontrolü, yetkisiz/CSRF istekleri, HTTP onay akışı, kuyruk sınırı, yeniden
açılış ve **taklit mikserle** hata sonrası ses restorasyonunu kapsar.
Gerçek Windows COM/Pycaw, Tkinter masaüstü, fiziksel amfi ve sesin doğallığı
bu otomatik testlerle doğrulanmış sayılmaz.

Windows kabul kontrolü: düşük amfi seviyesinde bir örnek plaka gönderin;
onaydan önce yalnızca bildirim duyulduğunu, onayda müziğin kısıldığını, zil ve
plakanın doğru/doğal okunduğunu ve müziğin eski seviyesine döndüğünü dinleyin.
Anonsu durdurma, seçili müzik uygulamasını kapatma ve paneli anons sırasında
normal kapatma durumlarını da sınayın. Bankayı dinleyerek kabul etmeden canlı kullanmayın.

Linux/macOS'ta web/çözümleme/PCM testleri çalışır; Windows masaüstü uygulaması çalışmaz.
Özel bir bulut geliştirme görevinde mevcut checkout'u kullanın; ayrıca Git worktree gerekmez.
