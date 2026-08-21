"""Uygulamaya özgü hata sınıfları.

Depo (repository) ve servis katmanları FastAPI'ye bağımlı olmasın diye
``HTTPException`` yerine bu sınıfları fırlatır. HTTP durum koduna çevrim
main.py içindeki tek bir işleyicide yapılır; böylece hata biçimi tüm
uygulamada standarttır.
"""


class AppError(Exception):
    """Tüm uygulama hatalarının ortak atası.

    Alt sınıflar yalnızca ``status_code`` ve ``message`` değerlerini
    değiştirir (kalıtım); hata işleyici hepsini aynı şekilde ele alır.
    """

    status_code: int = 500
    message: str = "Beklenmeyen bir sunucu hatası oluştu."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class DatabaseUnavailableError(AppError):
    """Veritabanına ulaşılamıyor."""

    status_code = 503
    message = "Veritabanına şu anda ulaşılamıyor. Lütfen daha sonra tekrar deneyin."


class RecordNotFoundError(AppError):
    """İstenen kayıt bulunamadı."""

    status_code = 404
    message = "Kayıt bulunamadı."


class InvalidIdentifierError(AppError):
    """Kayıt kimliği ilgili veritabanının beklediği biçimde değil."""

    status_code = 400
    message = "Geçersiz kayıt kimliği."


class DuplicateRecordError(AppError):
    """Aynı benzersiz değere sahip bir kayıt zaten var."""

    status_code = 409
    message = "Bu kayıt zaten mevcut."


class InvalidCredentialsError(AppError):
    """Kullanıcı adı veya şifre hatalı."""

    status_code = 401
    message = "Kullanıcı adı veya şifre hatalı!"


class InvalidDatabaseTargetError(AppError):
    """Geçersiz veritabanı seçimi."""

    status_code = 400
    message = "Geçersiz veritabanı seçimi. 'mssql', 'mongodb' veya 'both' olmalıdır."


class MissingTokenError(AppError):
    """İstekte oturum anahtarı yok."""

    status_code = 401
    message = "Bu işlem için giriş yapmalısınız."


class InvalidTokenError(AppError):
    """Oturum anahtarı çözümlenemedi veya imzası geçersiz."""

    status_code = 401
    message = "Oturum bilgisi geçersiz. Lütfen tekrar giriş yapın."


class ExpiredTokenError(AppError):
    """Oturum anahtarının süresi dolmuş."""

    status_code = 401
    message = "Oturum süresi doldu. Lütfen tekrar giriş yapın."


class InvalidRefreshTokenError(AppError):
    """Yenileme anahtarı geçersiz, süresi dolmuş veya iptal edilmiş."""

    status_code = 401
    message = "Oturum yenilenemedi. Lütfen tekrar giriş yapın."


class NotAuthorizedError(AppError):
    """Kullanıcı giriş yapmış ama bu işlem için yetkisi yok."""

    status_code = 403
    message = "Bu işlem için yetkiniz yok."


class TooManyAttemptsError(AppError):
    """Çok fazla başarısız giriş denemesi yapıldı."""

    status_code = 429
    message = "Çok fazla başarısız deneme. Lütfen bir süre sonra tekrar deneyin."

    def __init__(self, retry_after_seconds: int, message: str | None = None) -> None:
        #: İstemciye ``Retry-After`` başlığıyla bildirilir.
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)
