"""Uygulama yapılandırması.

Tüm ayarlar tek bir ``Settings`` nesnesinde toplanır. Gizli bilgiler
.env dosyasından okunur, koda gömülmez.
"""

import os
import secrets

from dotenv import load_dotenv

# Konteyner dışında (conda ortamında) çalışırken .env dosyasını yükler.
# Docker içinde değişkenler compose tarafından verilir, bu satır etkisizdir.
load_dotenv()


class Settings:
    """Ortam değişkenlerini kapsülleyen yapılandırma sınıfı.

    Bağlantı bilgileri "private" niteliklerde tutulur; dışarıya yalnızca
    hazır bağlantı dizeleri property olarak açılır. Böylece şifreler
    uygulamanın geri kalanında tek tek dolaşmaz (kapsülleme).
    """

    #: CORS_ORIGINS tanımsızsa kullanılan geliştirme adresleri.
    #: Güvenli taraf varsayılandır: yanlışlıkla her kökene açılmaz.
    _VARSAYILAN_KOKENLER = "http://localhost:5173,http://127.0.0.1:5173"

    #: HS256 için önerilen en az anahtar uzunluğu (RFC 7518 §3.2).
    MIN_JWT_KEY_LENGTH = 32

    #: .env.example ile dağıtılan yer tutucular. Bunlar depoda herkese
    #: açık olduğundan imzalama anahtarı olarak kullanılamaz: uzunluk
    #: sınırını geçseler bile herkes geçerli token üretebilirdi.
    YASAKLI_JWT_ANAHTARLARI = frozenset(
        {
            "buraya-uretilen-rastgele-anahtari-yazin",
            "degistirin",
            "changeme",
            "secret",
        }
    )

    def __init__(self) -> None:
        # --- MSSQL ---
        self._mssql_host = os.getenv("MSSQL_HOST", "localhost")
        self._mssql_port = os.getenv("MSSQL_PORT", "1433")
        self._mssql_user = os.getenv("MSSQL_USER", "sa")
        self._mssql_password = os.getenv("MSSQL_SA_PASSWORD", "")
        self._mssql_database = os.getenv("MSSQL_DATABASE", "master")

        # --- MongoDB ---
        self._mongo_host = os.getenv("MONGO_HOST", "localhost")
        self._mongo_port = os.getenv("MONGO_PORT", "27017")
        self._mongo_user = os.getenv("MONGO_ROOT_USERNAME", "")
        self._mongo_password = os.getenv("MONGO_ROOT_PASSWORD", "")
        self.mongo_database = os.getenv("MONGO_DATABASE", "gorev_yoneticisi")

        # --- JWT ---
        # Anahtar tanımlı değilse uygulama çalışmaya devam eder ama her
        # yeniden başlatmada oturumlar geçersiz olur; bu yüzden uyarılır.
        self._jwt_secret_key = os.getenv("JWT_SECRET_KEY", "")
        if self._jwt_secret_key.strip().lower() in self.YASAKLI_JWT_ANAHTARLARI:
            raise ValueError(
                "JWT_SECRET_KEY hâlâ .env.example'daki yer tutucu değerinde. "
                "Bu değer depoda herkese açıktır; onunla imzalanan oturumları "
                "herkes taklit edebilir. Kendi anahtarınızı üretin:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        if len(self._jwt_secret_key) < self.MIN_JWT_KEY_LENGTH:
            # RFC 7518, HS256 için anahtarın en az hash boyu (32 bayt)
            # kadar olmasını ister; kısa anahtar kaba kuvvetle çözülebilir.
            eksik = "tanımlı değil" if not self._jwt_secret_key else "çok kısa"
            self._jwt_secret_key = secrets.token_urlsafe(48)
            print(
                f"⚠️  JWT_SECRET_KEY {eksik} (en az {self.MIN_JWT_KEY_LENGTH} karakter "
                "olmalı). Geçici anahtar üretildi: yeniden başlatmada tüm "
                "oturumlar geçersiz olacak."
            )
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))

        # --- Refresh token ---
        self.refresh_token_expire_days = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")
        )
        # Çerez yalnızca HTTPS üzerinden gönderilsin mi? Yerel geliştirmede
        # HTTPS olmadığı için varsayılan kapalıdır; dağıtımda açılmalıdır.
        self.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"

        # --- Giriş hız sınırlama ---
        # Kullanıcı adı başına: hesabı hedef alan şifre denemesini durdurur.
        self.login_max_attempts = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
        # IP başına daha yüksek: aynı ağdan (NAT) birden çok kişi bağlanabilir.
        self.login_max_attempts_per_ip = int(
            os.getenv("LOGIN_MAX_ATTEMPTS_PER_IP", "20")
        )
        self.login_window_minutes = int(os.getenv("LOGIN_WINDOW_MINUTES", "15"))

        # --- Ters vekil ---
        # X-Forwarded-For başlığını istemci de gönderebilir. Ters vekil
        # arkasında değilsek başlığa güvenmek, saldırganın her istekte
        # farklı bir IP uydurarak IP başına hız sınırını atlamasına ve
        # denetim kaydını sahte adreslerle doldurmasına izin verir.
        # Bu yüzden varsayılan olarak KAPALIDIR.
        self.trust_proxy = os.getenv("TRUST_PROXY", "false").strip().lower() in (
            "1",
            "true",
            "yes",
            "evet",
        )

        # --- CORS ---
        # Virgülle ayrılmış köken listesi. Oturum httpOnly çerezle taşındığı
        # ve middleware allow_credentials=True ile çalıştığı için "*" burada
        # geçerli bir değer DEĞİLDİR: tarayıcı bu durumda isteğin kökenini
        # aynen yansıtır, yani herhangi bir site kullanıcının çerezleriyle
        # kimliği doğrulanmış istek atabilirdi. Bu yüzden hem varsayılan
        # güvenlidir hem de "*" verilirse uygulama açılışta durur.
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", self._VARSAYILAN_KOKENLER).split(",")
            if origin.strip()
        ]
        if "*" in self.cors_origins:
            raise ValueError(
                "CORS_ORIGINS '*' olamaz: oturum çerezle taşındığı için her "
                "köken kabul edilirse başka siteler kullanıcı adına istek "
                "atabilir. Arayüzün adresini tek tek yazın "
                "(örn. http://localhost:5173)."
            )

    @property
    def jwt_secret_key(self) -> str:
        """İmzalama anahtarı; yalnızca TokenService tarafından okunur."""
        return self._jwt_secret_key

    @property
    def mssql_connection_string(self) -> str:
        """pyodbc için MSSQL bağlantı dizesi."""
        return (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={self._mssql_host},{self._mssql_port};"
            f"DATABASE={self._mssql_database};"
            f"UID={self._mssql_user};"
            f"PWD={self._mssql_password};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )

    @property
    def mongo_connection_string(self) -> str:
        """pymongo için MongoDB bağlantı dizesi."""
        return (
            f"mongodb://{self._mongo_user}:{self._mongo_password}"
            f"@{self._mongo_host}:{self._mongo_port}/"
            "?authSource=admin&serverSelectionTimeoutMS=5000"
        )


#: Uygulama genelinde kullanılan tekil yapılandırma nesnesi.
settings = Settings()
