"""Veritabanı bağlantı yönetimi.

Her veritabanı türü kendi bağlantı sınıfıyla temsil edilir. Bağlantı
bilgileri sınıfların içinde saklanır (kapsülleme); dışarısı yalnızca
``cursor()`` / ``database`` gibi güvenli erişim noktalarını görür.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager

import pyodbc
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import Settings
from exceptions import DatabaseUnavailableError


class BaseConnection(ABC):
    """Tüm veritabanı bağlantılarının uyması gereken ortak arayüz."""

    @abstractmethod
    def is_available(self) -> bool:
        """Bağlantının kullanılabilir olup olmadığını bildirir."""


class MSSQLConnection(BaseConnection):
    """MSSQL bağlantılarını ve işlem (transaction) yaşam döngüsünü yönetir."""

    def __init__(self, config: Settings) -> None:
        # Çift alt çizgi: bağlantı dizesi (şifre içerir) sınıf dışından okunamaz.
        self.__connection_string = config.mssql_connection_string

    def is_available(self) -> bool:
        try:
            with self.cursor():
                return True
        except DatabaseUnavailableError:
            return False

    @contextmanager
    def cursor(self):
        """Bağlantı + imleç yaşam döngüsünü yöneten bağlam yöneticisi.

        Blok sorunsuz biterse ``commit``, hata olursa ``rollback`` yapar ve
        her durumda kaynakları kapatır. Bu sayede her uç noktada
        tekrarlanan try/except/finally bloklarına gerek kalmaz.
        """
        try:
            connection = pyodbc.connect(self.__connection_string, timeout=5)
        except pyodbc.Error as exc:
            raise DatabaseUnavailableError("MSSQL bağlantısı kurulamadı.") from exc

        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()


class MongoConnection(BaseConnection):
    """MongoDB istemcisini yönetir.

    ``MongoClient`` bağlantıyı tembel kurar ve sunucu topolojisini arka
    planda izleyerek kesinti sonrası **kendisi yeniden bağlanır**. Bu
    yüzden burada açılışta bağlantı denenmez ve başarısızlıkta istemci
    atılmaz: atılsaydı, MongoDB sonradan ayağa kalksa bile uygulama
    yeniden başlatılana kadar erişemezdi.
    """

    def __init__(self, config: Settings) -> None:
        self.__database_name = config.mongo_database
        self.__client = MongoClient(config.mongo_connection_string)

    def is_available(self) -> bool:
        """Sunucuya o an ulaşılıp ulaşılamadığını söyler."""
        try:
            self.__client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    @property
    def database(self):
        """Uygulama veritabanını döner."""
        return self.__client[self.__database_name]

    def close(self) -> None:
        """Uygulama kapanırken bağlantı havuzunu serbest bırakır."""
        self.__client.close()


class SchemaInitializer:
    """Uygulama açılışında gerekli MSSQL tablolarını oluşturur.

    Metin kolonları NVARCHAR'dır: VARCHAR Unicode saklamadığı için
    Türkçe'ye özgü ı, ş, ğ karakterleri veri kaybına uğrardı.
    """

    _USERS_TABLE = """
    IF NOT EXISTS (SELECT * FROM sys.objects
                   WHERE object_id = OBJECT_ID(N'[dbo].[Users]') AND type = N'U')
    BEGIN
        CREATE TABLE Users (
            id INT IDENTITY(1,1) PRIMARY KEY,
            username NVARCHAR(50) NOT NULL UNIQUE,
            email NVARCHAR(100) NOT NULL,
            -- bcrypt çıktısı her zaman ASCII olduğu için burada VARCHAR yeterlidir.
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME2 DEFAULT SYSDATETIME(),
            is_admin BIT NOT NULL DEFAULT 0
        )
    END
    """

    # Yetki alanı sonradan eklendiği için var olan kurulumlar da güncellenir.
    _USERS_ADMIN_COLUMN = """
    IF COL_LENGTH('dbo.Users', 'is_admin') IS NULL
    BEGIN
        ALTER TABLE Users ADD is_admin BIT NOT NULL DEFAULT 0
    END
    """

    _TASKS_TABLE = """
    IF NOT EXISTS (SELECT * FROM sys.objects
                   WHERE object_id = OBJECT_ID(N'[dbo].[Tasks]') AND type = N'U')
    BEGIN
        CREATE TABLE Tasks (
            id INT IDENTITY(1,1) PRIMARY KEY,
            title NVARCHAR(100) NOT NULL,
            -- TEXT tipi SQL Server'da kullanımdan kaldırılmıştır, yerine NVARCHAR(MAX).
            description NVARCHAR(MAX),
            status NVARCHAR(20) DEFAULT N'Beklemede',
            created_at DATETIME2 DEFAULT SYSDATETIME(),
            user_id INT NULL REFERENCES Users(id)
        )
    END
    """

    # Kolon sonradan eklendiği için var olan kurulumlar da güncellenir.
    # NULL bırakılır: bu değişiklikten önce oluşturulmuş görevler silinmez,
    # yalnızca hiçbir kullanıcının listesinde görünmez.
    _TASKS_USER_COLUMN = """
    IF COL_LENGTH('dbo.Tasks', 'user_id') IS NULL
    BEGIN
        ALTER TABLE Tasks ADD user_id INT NULL REFERENCES Users(id)
    END
    """

    # Refresh token'ın kendisi değil, SHA-256 özeti saklanır: veritabanı
    # sızsa bile eldeki değerlerle oturum açılamaz. Şifrelerin aksine
    # bcrypt gerekmez; token zaten yüksek entropili rastgele bir değerdir
    # ve her istekte özet üzerinden aranması gerekir.
    _REFRESH_TOKENS_TABLE = """
    IF NOT EXISTS (SELECT * FROM sys.objects
                   WHERE object_id = OBJECT_ID(N'[dbo].[RefreshTokens]') AND type = N'U')
    BEGIN
        CREATE TABLE RefreshTokens (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL REFERENCES Users(id),
            token_hash CHAR(64) NOT NULL UNIQUE,
            -- Rotasyon zinciri: aynı oturumdan türeyen tüm token'lar aynı
            -- aileyi paylaşır. Hırsızlık tespitinde ailenin tamamı iptal edilir.
            family_id CHAR(36) NOT NULL,
            expires_at DATETIME2 NOT NULL,
            used_at DATETIME2 NULL,
            revoked_at DATETIME2 NULL,
            created_at DATETIME2 DEFAULT SYSDATETIME()
        )
    END
    """

    # Kimlik doğrulama olayları. Başarısız denemeler de yazılır: aksi hâlde
    # bir hesaba yapılan şifre deneme saldırısı hiçbir iz bırakmazdı.
    # user_id NULL olabilir — olmayan bir kullanıcı adıyla yapılan deneme.
    _AUTH_EVENTS_TABLE = """
    IF NOT EXISTS (SELECT * FROM sys.objects
                   WHERE object_id = OBJECT_ID(N'[dbo].[AuthEvents]') AND type = N'U')
    BEGIN
        CREATE TABLE AuthEvents (
            id BIGINT IDENTITY(1,1) PRIMARY KEY,
            username NVARCHAR(50) NOT NULL,
            user_id INT NULL REFERENCES Users(id),
            event NVARCHAR(30) NOT NULL,
            success BIT NOT NULL,
            ip_address NVARCHAR(45) NULL,
            user_agent NVARCHAR(300) NULL,
            created_at DATETIME2 DEFAULT SYSDATETIME()
        )
    END
    """

    _AUTH_EVENTS_INDEX = """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_AuthEvents_created')
    BEGIN
        CREATE INDEX IX_AuthEvents_created ON AuthEvents(created_at DESC)
    END
    """

    _REFRESH_TOKENS_INDEX = """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_RefreshTokens_family')
    BEGIN
        CREATE INDEX IX_RefreshTokens_family ON RefreshTokens(family_id)
    END
    """

    _TASKS_USER_INDEX = """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Tasks_user_id')
    BEGIN
        CREATE INDEX IX_Tasks_user_id ON Tasks(user_id)
    END
    """

    def __init__(self, connection: MSSQLConnection) -> None:
        self._connection = connection

    def run(self) -> None:
        """Tabloları oluşturur. Veritabanı hazır değilse uygulamayı çökertmez."""
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(self._USERS_TABLE)
                cursor.execute(self._USERS_ADMIN_COLUMN)
                cursor.execute(self._TASKS_TABLE)
                cursor.execute(self._TASKS_USER_COLUMN)
                cursor.execute(self._TASKS_USER_INDEX)
                cursor.execute(self._REFRESH_TOKENS_TABLE)
                cursor.execute(self._REFRESH_TOKENS_INDEX)
                cursor.execute(self._AUTH_EVENTS_TABLE)
                cursor.execute(self._AUTH_EVENTS_INDEX)
            print("✅ MSSQL tabloları başarıyla kontrol edildi/oluşturuldu.")
        except DatabaseUnavailableError as exc:
            print(f"❌ Tablolar oluşturulamadı: {exc.message}")
