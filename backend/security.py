"""Şifre ve oturum güvenliği."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from exceptions import ExpiredTokenError, InvalidTokenError
from schemas import AuthenticatedUser


class PasswordHasher:
    """Şifre hash'leme ve doğrulama işlemlerini kapsüller.

    Kullanılan algoritma (bcrypt) sınıfın içinde kalır; çağıran kod hangi
    kütüphanenin kullanıldığını bilmek zorunda değildir. İleride algoritma
    değişirse yalnızca bu sınıf güncellenir.
    """

    _ENCODING = "utf-8"

    #: Kullanıcı bulunamadığında karşılaştırılacak sahte hash. Rastgele bir
    #: değerden üretilmiştir, hiçbir şifreye ait değildir.
    _DUMMY_HASH = "$2b$12$p0po1mDF3UHBPBloehiqx.MeEIhVghtX6uCV6fFjiUXVoauzzig1i"

    def hash(self, plain_password: str) -> str:
        """Düz metin şifreyi rastgele bir tuz ile hash'ler."""
        hashed = bcrypt.hashpw(plain_password.encode(self._ENCODING), bcrypt.gensalt())
        return hashed.decode(self._ENCODING)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Girilen şifrenin kayıtlı hash ile eşleşip eşleşmediğini söyler."""
        try:
            return bcrypt.checkpw(
                plain_password.encode(self._ENCODING),
                hashed_password.encode(self._ENCODING),
            )
        except (ValueError, TypeError):
            # Bozuk/eksik hash değeri: doğrulama başarısız sayılır.
            return False

    def waste_time(self) -> None:
        """Kullanıcı bulunamadığında bilerek bir doğrulama yapar.

        Aksi hâlde "kullanıcı yok" yanıtı, bcrypt hiç çalışmadığı için
        belirgin şekilde hızlı dönerdi; saldırgan yanıt süresine bakarak
        hangi kullanıcı adlarının kayıtlı olduğunu tespit edebilirdi.
        """
        bcrypt.checkpw(b"zaman-esitleme", self._DUMMY_HASH.encode(self._ENCODING))


class TokenService:
    """Oturum anahtarı (JWT) üretir ve doğrular.

    İmzalama anahtarı sınıf içinde "private" tutulur; uygulamanın geri
    kalanı yalnızca ``create_access_token`` ve ``read_user``
    metotlarını görür.
    """

    def __init__(self, secret_key: str, algorithm: str = "HS256", expire_minutes: int = 60) -> None:
        self.__secret_key = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    @property
    def expires_in_seconds(self) -> int:
        """Anahtarın geçerlilik süresi (saniye)."""
        return self._expire_minutes * 60

    def create_access_token(self, user_id: int, username: str) -> str:
        """Kullanıcı için süresi sınırlı bir oturum anahtarı üretir.

        Kullanıcı kimliği de anahtara yazılır ("uid"); böylece her istekte
        kullanıcıyı bulmak için veritabanına gitmek gerekmez.
        """
        issued_at = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "uid": user_id,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=self._expire_minutes),
        }
        return jwt.encode(payload, self.__secret_key, algorithm=self._algorithm)

    def read_user(self, token: str) -> AuthenticatedUser:
        """Anahtarı doğrular ve sahibini döner.

        Süre dolması ile geçersiz imza ayrı hatalar üretir; böylece
        kullanıcıya "süreniz doldu" ile "geçersiz oturum" farklı gösterilir.
        """
        try:
            payload = jwt.decode(token, self.__secret_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError() from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        username = payload.get("sub")
        user_id = payload.get("uid")
        if not username or not isinstance(user_id, int):
            raise InvalidTokenError()

        return AuthenticatedUser(id=user_id, username=username)


class RefreshTokenFactory:
    """Yenileme anahtarı üretir ve saklanacak özetini hesaplar.

    Anahtarın kendisi yalnızca kullanıcıya gider; veritabanında SHA-256
    özeti saklanır. Böylece veritabanı sızsa bile eldeki değerlerle
    oturum açılamaz.

    Şifrelerde kullanılan bcrypt burada gerekmez: token zaten 32 baytlık
    rastgele bir değerdir (sözlük saldırısına konu değildir) ve her
    yenilemede özet üzerinden aranması gerekir — bcrypt ile arama
    yapılamazdı.
    """

    #: Üretilen anahtarın entropisi (bayt).
    _TOKEN_BYTES = 32

    def create(self) -> tuple[str, str]:
        """(anahtar, özet) çifti döner. Anahtar kullanıcıya, özet veritabanına."""
        token = secrets.token_urlsafe(self._TOKEN_BYTES)
        return token, self.hash(token)

    @staticmethod
    def hash(token: str) -> str:
        """Anahtarın veritabanında saklanan biçimi."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def new_family_id() -> str:
        """Yeni bir rotasyon ailesi kimliği (her girişte bir tane)."""
        return str(uuid.uuid4())
