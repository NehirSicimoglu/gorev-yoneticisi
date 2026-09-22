# Görev Yönetim Sistemi

FastAPI ve React kullanılarak geliştirilmiş, görevlerin MSSQL, MongoDB veya her iki veritabanına da kaydedilebildiği bir görev yönetim uygulaması.

Uygulamanın temel amacı, ilişkisel ve NoSQL veritabanlarını aynı uygulama içerisinde ortak bir API üzerinden kullanabilmek. Docker Compose sayesinde gerekli servisler tek komutla çalıştırılabiliyor.

## Özellikler

* Kullanıcı kayıt ve giriş sistemi
* Şifrelerin bcrypt ile güvenli şekilde saklanması
* Kısa ömürlü access token ve `httpOnly` cookie içerisinde refresh token kullanımı
* Kullanıcıların yalnızca kendi görevlerine erişebilmesi
* Görevlerin MSSQL'e, MongoDB'ye veya her iki veritabanına birden kaydedilebilmesi
* İki veritabanına yapılan kayıtlarda hata olması durumunda geri alma mekanizması
* Sayfalama ve "daha fazla yükle" desteği
* Yönetici paneli

  * Kullanıcı yönetimi
  * Aktif oturumların görüntülenmesi
  * Giriş olaylarının takibi
* Giriş denemeleri için rate limiting
* Docker Compose ile tek komutla kurulum ve çalıştırma
* 91 adet birim testi

## Kullanılan Teknolojiler

**Backend**

* FastAPI
* Python
* MSSQL
* MongoDB

**Frontend**

* React

**Diğer**

* Docker
* Docker Compose
* JWT
* bcrypt

## Veritabanı Yaklaşımı

Uygulamada görevler tek bir veritabanına bağlı değil. İstek sırasında hedef veritabanı seçilebiliyor ve gerektiğinde aynı kayıt hem MSSQL hem de MongoDB'ye yazılabiliyor.

İki veritabanına da yazılan işlemlerde, taraflardan biri başarısız olursa başarılı olan işlem de geri alınarak tutarsız veri oluşmasının önüne geçilmeye çalışılıyor.

## Testler

Backend tarafında toplam **91 birim testi** bulunuyor. Testler; kimlik doğrulama, görev işlemleri, yetkilendirme ve veritabanı işlemleri gibi temel senaryoları kapsıyor.

## Çalıştırma

Önce ortam değişkenleri dosyasını oluşturun ve içindeki veritabanı şifreleri ile `JWT_SECRET_KEY` değerini kendinize göre doldurun:

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Ardından servisleri tek komutla başlatabilirsiniz:

```bash
docker compose up --build
```

Servisler başladıktan sonra uygulama üzerinden kayıt olabilir, giriş yapabilir ve görevlerinizi yönetebilirsiniz.
