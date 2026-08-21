"""Sabit değer kümeleri.

Serbest metin yerine enum kullanmak, geçersiz değerlerin uygulamaya
hiç girmemesini sağlar: FastAPI bunları istek sınırında doğrular ve
Swagger'da seçenek listesi olarak gösterir.
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Bir görevin alabileceği durumlar."""

    PENDING = "Beklemede"
    DONE = "Tamamlandı"


class DatabaseSource(str, Enum):
    """Tek bir veritabanını işaret eden seçim (okuma, güncelleme, silme)."""

    MSSQL = "mssql"
    MONGODB = "mongodb"


class DatabaseTarget(str, Enum):
    """Yazma hedefi. ``BOTH``, iki veritabanına birden yazmayı ifade eder."""

    MSSQL = "mssql"
    MONGODB = "mongodb"
    BOTH = "both"


class AuthEvent(str, Enum):
    """Kimlik doğrulama olayının türü."""

    REGISTER = "register"
    LOGIN = "login"
    LOGOUT = "logout"
    REFRESH = "refresh"
    #: Kullanılmış bir yenileme anahtarı tekrar sunuldu — hırsızlık şüphesi.
    TOKEN_REUSE = "token_reuse"
