"""Kullanıcı ve oturum iş mantığı."""

import logging
from datetime import datetime, timedelta, timezone

from enums import AuthEvent
from exceptions import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    TooManyAttemptsError,
)
from repositories.admin_repository import MSSQLAdminRepository
from repositories.audit_repository import MSSQLAuthEventRepository
from repositories.base import BaseRefreshTokenRepository, BaseUserRepository
from schemas import IssuedSession, RequestContext, UserCreate, UserResponse
from security import PasswordHasher, RefreshTokenFactory, TokenService

logger = logging.getLogger("gorev-yoneticisi")


class UserService:
    """Kayıt, giriş, oturum yenileme ve çıkış işlemlerini yürütür.

    Oturum iki parçadan oluşur:

    * **Access token** — kısa ömürlü (dakikalar), imzalıdır, veritabanına
      sorulmaz. Çalınsa bile penceresi dardır.
    * **Refresh token** — uzun ömürlü (günler), veritabanında özeti tutulur.
      Bu yüzden *iptal edilebilir* — JWT'nin tek başına sağlayamadığı şey.
    """

    def __init__(
        self,
        repository: BaseUserRepository,
        refresh_repository: BaseRefreshTokenRepository,
        hasher: PasswordHasher,
        token_service: TokenService,
        refresh_factory: RefreshTokenFactory,
        refresh_expire_days: int,
        audit: MSSQLAuthEventRepository,
        admin: MSSQLAdminRepository,
        max_attempts: int = 5,
        max_attempts_per_ip: int = 20,
        window_minutes: int = 15,
    ) -> None:
        self._repository = repository
        self._refresh_repository = refresh_repository
        self._hasher = hasher
        self._token_service = token_service
        self._refresh_factory = refresh_factory
        self._refresh_expire_days = refresh_expire_days
        self._audit = audit
        self._admin = admin
        self._max_attempts = max_attempts
        self._max_attempts_per_ip = max_attempts_per_ip
        self._window_minutes = window_minutes

    # ----------------------------------------------------------
    # Kayıt / Giriş
    # ----------------------------------------------------------
    def register(
        self, user: UserCreate, context: RequestContext | None = None
    ) -> UserResponse:
        """Yeni kullanıcı oluşturur.

        Kullanıcı adının benzersizliği veritabanındaki UNIQUE kısıtıyla
        güvence altındadır. Ayrıca ön kontrol yapmak hem fazladan bir
        sorgu olurdu hem de iki isteğin arasına sıkışabilecek bir yarış
        açığı bırakırdı.
        """
        try:
            created = self._repository.create(user, self._hasher.hash(user.password))
        except Exception:
            self._audit.record(user.username, AuthEvent.REGISTER, False, context)
            raise

        self._audit.record(
            user.username, AuthEvent.REGISTER, True, context, user_id=created.id
        )
        return created

    def login(
        self, username: str, password: str, context: RequestContext | None = None
    ) -> IssuedSession:
        """Kimlik bilgilerini doğrular ve yeni bir oturum başlatır.

        Kullanıcı adı bulunamadığında da şifre yanlış olduğunda da aynı
        hata döner; böylece hangi kullanıcı adlarının kayıtlı olduğu
        dışarıdan anlaşılamaz.

        Şifre doğrulanmadan **önce** hız sınırı kontrol edilir: hesap
        hedefli şifre denemesi ancak böyle durdurulabilir.
        """
        self._enforce_rate_limit(username, context)

        credentials = self._repository.get_credentials(username)

        if credentials is None:
            # Yanıt süresi kayıtlı bir kullanıcınınkiyle aynı kalsın diye.
            self._hasher.waste_time()
            self._audit.record(username, AuthEvent.LOGIN, False, context)
            raise InvalidCredentialsError()

        if not self._hasher.verify(password, credentials.password_hash):
            self._audit.record(
                username, AuthEvent.LOGIN, False, context, user_id=credentials.id
            )
            raise InvalidCredentialsError()

        self._audit.record(
            username, AuthEvent.LOGIN, True, context, user_id=credentials.id
        )

        # Her giriş yeni bir rotasyon ailesi başlatır: farklı cihazlardaki
        # oturumlar birbirinden bağımsız yaşar ve ayrı ayrı iptal edilebilir.
        return self._issue(
            user_id=credentials.id,
            username=username,
            family_id=self._refresh_factory.new_family_id(),
        )

    def _enforce_rate_limit(
        self, username: str, context: RequestContext | None
    ) -> None:
        """Çok fazla başarısız deneme yapılmışsa isteği reddeder.

        İki ayrı sayaç vardır:

        * **Kullanıcı adı başına** — bir hesabı hedef alan şifre denemesini
          durdurur. Başarısız denemeler var olmayan kullanıcı adları için de
          kaydedildiğinden, sınır herkese aynı şekilde uygulanır; yani 429
          yanıtı hesabın var olduğunu ele vermez.
        * **IP başına** — kullanıcı adı değiştirerek sınırı aşmayı engeller.
          Aynı ağdan birden çok kişi bağlanabileceği için eşiği yüksektir.

        Pencere kayar: en eski denemeler zamanla düşer, hesap kalıcı
        olarak kilitlenmez.
        """
        saniye = self._window_minutes * 60

        if self._audit.failed_since(username, self._window_minutes) >= self._max_attempts:
            logger.warning("Hız sınırı aşıldı (kullanıcı: %s)", username)
            raise TooManyAttemptsError(
                saniye,
                f"Çok fazla başarısız giriş denemesi. "
                f"{self._window_minutes} dakika sonra tekrar deneyin.",
            )

        ip = context.ip_address if context else None
        if ip and self._audit.failed_since_ip(ip, self._window_minutes) >= self._max_attempts_per_ip:
            logger.warning("Hız sınırı aşıldı (IP: %s)", ip)
            raise TooManyAttemptsError(
                saniye,
                f"Bu adresten çok fazla başarısız deneme yapıldı. "
                f"{self._window_minutes} dakika sonra tekrar deneyin.",
            )

    # ----------------------------------------------------------
    # Yenileme / Çıkış
    # ----------------------------------------------------------
    def refresh(
        self, refresh_token: str, context: RequestContext | None = None
    ) -> IssuedSession:
        """Yenileme anahtarını kullanıp yeni bir oturum çifti üretir.

        **Rotasyon:** Kullanılan anahtar bir daha geçerli olmaz, yerine
        yenisi verilir.

        **Tekrar kullanım tespiti:** Daha önce kullanılmış bir anahtar
        tekrar gelirse bunun tek açıklaması vardır — birinde kopyası var.
        Bu durumda o zincirin tamamı iptal edilir; hem saldırgan hem
        gerçek kullanıcı düşer ve kullanıcı yeniden giriş yapmak zorunda
        kalır. Hırsızlığın fark edilebildiği tek nokta burasıdır.
        """
        record = self._refresh_repository.find(self._refresh_factory.hash(refresh_token))

        if record is None:
            raise InvalidRefreshTokenError()

        now = datetime.now()

        if record.used_at is not None:
            logger.warning(
                "Kullanılmış yenileme anahtarı tekrar sunuldu; %s ailesi iptal ediliyor.",
                record.family_id,
            )
            self._refresh_repository.revoke_family(record.family_id)
            self._audit.record(
                self._repository.get_username(record.user_id) or "?",
                AuthEvent.TOKEN_REUSE,
                False,
                context,
                user_id=record.user_id,
            )
            raise InvalidRefreshTokenError()

        if not record.is_usable(now):
            raise InvalidRefreshTokenError()

        username = self._repository.get_username(record.user_id)
        if username is None:
            # Kullanıcı silinmiş: zincir artık anlamsız.
            self._refresh_repository.revoke_family(record.family_id)
            raise InvalidRefreshTokenError()

        self._refresh_repository.mark_used(record.id)
        self._audit.record(
            username, AuthEvent.REFRESH, True, context, user_id=record.user_id
        )

        return self._issue(
            user_id=record.user_id,
            username=username,
            family_id=record.family_id,  # aynı zincir devam eder
        )

    def logout(
        self, refresh_token: str, context: RequestContext | None = None
    ) -> None:
        """Oturumu sonlandırır: zincirin tamamı iptal edilir.

        Anahtar tanınmasa bile hata verilmez; çıkış her hâlükârda
        başarılı sayılır.
        """
        record = self._refresh_repository.find(self._refresh_factory.hash(refresh_token))
        if record is not None:
            self._refresh_repository.revoke_family(record.family_id)
            self._audit.record(
                self._repository.get_username(record.user_id) or "?",
                AuthEvent.LOGOUT,
                True,
                context,
                user_id=record.user_id,
            )

    # ----------------------------------------------------------
    def _issue(self, user_id: int, username: str, family_id: str) -> IssuedSession:
        """Access + refresh çiftini üretir ve refresh'i kaydeder."""
        refresh_token, token_hash = self._refresh_factory.create()
        expires_at = datetime.now() + timedelta(days=self._refresh_expire_days)

        self._refresh_repository.store(user_id, token_hash, family_id, expires_at)

        return IssuedSession(
            access_token=self._token_service.create_access_token(user_id, username),
            expires_in=self._token_service.expires_in_seconds,
            username=username,
            is_admin=self._admin.is_admin(user_id),
            refresh_token=refresh_token,
            refresh_expires_in=self._refresh_expire_days * 24 * 3600,
        )
