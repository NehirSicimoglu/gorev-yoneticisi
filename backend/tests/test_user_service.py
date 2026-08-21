"""Oturum yönetimi testleri: giriş, yenileme, rotasyon, hırsızlık tespiti."""

from datetime import datetime, timedelta
from typing import Optional

import pytest

from enums import AuthEvent
from exceptions import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    TooManyAttemptsError,
)
from repositories.base import (
    BaseRefreshTokenRepository,
    BaseUserRepository,
    RefreshTokenRecord,
    UserCredentials,
)
from schemas import RequestContext, UserCreate, UserResponse
from security import PasswordHasher, RefreshTokenFactory, TokenService
from services import UserService

SECRET = "test-icin-gizli-anahtar-en-az-32-bayt-uzunlugunda"


class SahteKullaniciDeposu(BaseUserRepository):
    def __init__(self) -> None:
        self.kullanicilar: dict[str, UserCredentials] = {}
        self._sayac = 0

    def ekle(self, username: str, password_hash: str) -> int:
        self._sayac += 1
        self.kullanicilar[username] = UserCredentials(self._sayac, password_hash)
        return self._sayac

    def create(self, user: UserCreate, password_hash: str) -> UserResponse:
        yeni_id = self.ekle(user.username, password_hash)
        return UserResponse(
            id=yeni_id, username=user.username, email=user.email, created_at=datetime.now()
        )

    def get_credentials(self, username: str) -> Optional[UserCredentials]:
        return self.kullanicilar.get(username)

    def get_username(self, user_id: int) -> Optional[str]:
        for ad, bilgi in self.kullanicilar.items():
            if bilgi.id == user_id:
                return ad
        return None


class SahteRefreshDeposu(BaseRefreshTokenRepository):
    def __init__(self) -> None:
        self.kayitlar: dict[str, RefreshTokenRecord] = {}
        self._sayac = 0

    def store(self, user_id, token_hash, family_id, expires_at):
        self._sayac += 1
        self.kayitlar[token_hash] = RefreshTokenRecord(
            id=self._sayac,
            user_id=user_id,
            family_id=family_id,
            expires_at=expires_at,
            used_at=None,
            revoked_at=None,
        )

    def find(self, token_hash):
        return self.kayitlar.get(token_hash)

    def mark_used(self, token_id):
        for anahtar, kayit in self.kayitlar.items():
            if kayit.id == token_id:
                self.kayitlar[anahtar] = kayit._replace(used_at=datetime.now())

    def revoke_family(self, family_id):
        for anahtar, kayit in self.kayitlar.items():
            if kayit.family_id == family_id and kayit.revoked_at is None:
                self.kayitlar[anahtar] = kayit._replace(revoked_at=datetime.now())

    def delete_expired(self):
        simdi = datetime.now()
        eski = [a for a, k in self.kayitlar.items() if k.expires_at < simdi]
        for a in eski:
            del self.kayitlar[a]
        return len(eski)


class SahteDenetim:
    """Denetim kaydı yerine olayları bellekte biriktirir."""

    def __init__(self) -> None:
        self.olaylar: list[tuple[str, AuthEvent, bool]] = []
        self.basarisizlar: list[tuple[str, str | None]] = []

    def __init_kayitlar__(self):
        pass

    def record(self, username, event, success, context=None, user_id=None):
        self.olaylar.append((username, event, success))
        if not success and event is AuthEvent.LOGIN:
            ip = context.ip_address if context else None
            self.basarisizlar.append((username, ip))

    def turler(self, event: AuthEvent):
        return [o for o in self.olaylar if o[1] is event]

    def failed_since(self, username, minutes):
        return len([b for b in self.basarisizlar if b[0] == username])

    def failed_since_ip(self, ip_address, minutes):
        return len([b for b in self.basarisizlar if b[1] == ip_address])


class SahteYetki:
    """Yönetici listesi."""

    def __init__(self, yoneticiler: set[int] | None = None) -> None:
        self.yoneticiler = yoneticiler or set()

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.yoneticiler


@pytest.fixture
def denetim():
    return SahteDenetim()


@pytest.fixture
def yetki():
    return SahteYetki()


@pytest.fixture
def kullanicilar():
    return SahteKullaniciDeposu()


@pytest.fixture
def refreshler():
    return SahteRefreshDeposu()


@pytest.fixture
def service(kullanicilar, refreshler, denetim, yetki):
    hasher = PasswordHasher()
    kullanicilar.ekle("kullanici", hasher.hash("parola123"))
    return UserService(
        repository=kullanicilar,
        refresh_repository=refreshler,
        hasher=hasher,
        token_service=TokenService(SECRET, expire_minutes=15),
        refresh_factory=RefreshTokenFactory(),
        refresh_expire_days=30,
        audit=denetim,
        admin=yetki,
    )


class TestGiris:
    def test_dogru_bilgiyle_oturum_acilir(self, service):
        oturum = service.login("kullanici", "parola123")

        assert oturum.username == "kullanici"
        assert oturum.access_token
        assert oturum.refresh_token
        assert oturum.expires_in == 15 * 60

    def test_yanlis_sifre_reddedilir(self, service):
        with pytest.raises(InvalidCredentialsError):
            service.login("kullanici", "yanlis")

    def test_olmayan_kullanici_ayni_hatayi_verir(self, service):
        """Kullanıcı adı numaralandırmasını engellemek için aynı hata."""
        with pytest.raises(InvalidCredentialsError):
            service.login("yokboyle", "parola123")

    def test_refresh_token_veritabaninda_duz_metin_degil(self, service, refreshler):
        oturum = service.login("kullanici", "parola123")

        assert oturum.refresh_token not in refreshler.kayitlar, "ham token saklanmış!"
        assert len(list(refreshler.kayitlar)[0]) == 64, "SHA-256 özeti bekleniyordu"


class TestYenileme:
    def test_gecerli_anahtar_yeni_oturum_verir(self, service):
        ilk = service.login("kullanici", "parola123")
        yeni = service.refresh(ilk.refresh_token)

        assert yeni.username == "kullanici"
        assert yeni.refresh_token != ilk.refresh_token, "rotasyon yapılmadı"

    def test_kullanilan_anahtar_bir_daha_gecmez(self, service):
        """Rotasyon: eski anahtar geçersizleşmeli."""
        ilk = service.login("kullanici", "parola123")
        service.refresh(ilk.refresh_token)

        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(ilk.refresh_token)

    def test_tekrar_kullanim_tum_zinciri_iptal_eder(self, service):
        """Hırsızlık tespiti.

        Saldırgan eski bir anahtarı kullanmaya çalışırsa, o zincirden
        türeyen geçerli anahtar da (gerçek kullanıcınınki) iptal edilir.
        """
        ilk = service.login("kullanici", "parola123")
        ikinci = service.refresh(ilk.refresh_token)  # gerçek kullanıcı

        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(ilk.refresh_token)  # saldırgan, çalıntı kopyayla

        # Gerçek kullanıcının elindeki geçerli anahtar da artık çalışmamalı.
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(ikinci.refresh_token)

    def test_bilinmeyen_anahtar_reddedilir(self, service):
        with pytest.raises(InvalidRefreshTokenError):
            service.refresh("uydurma-anahtar")

    def test_suresi_dolmus_anahtar_reddedilir(self, service, refreshler):
        oturum = service.login("kullanici", "parola123")
        anahtar = next(iter(refreshler.kayitlar))
        refreshler.kayitlar[anahtar] = refreshler.kayitlar[anahtar]._replace(
            expires_at=datetime.now() - timedelta(days=1)
        )

        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(oturum.refresh_token)

    def test_zincir_ayni_kalir(self, service, refreshler):
        """Yenileme aynı oturumu sürdürür, yeni oturum açmaz."""
        ilk = service.login("kullanici", "parola123")
        aile = next(iter(refreshler.kayitlar.values())).family_id
        service.refresh(ilk.refresh_token)

        assert {k.family_id for k in refreshler.kayitlar.values()} == {aile}

    def test_her_giris_yeni_zincir_baslatir(self, service, refreshler):
        """Farklı cihazlar birbirini etkilememeli."""
        service.login("kullanici", "parola123")
        service.login("kullanici", "parola123")

        assert len({k.family_id for k in refreshler.kayitlar.values()}) == 2


class TestCikis:
    def test_cikis_anahtari_gecersiz_kilar(self, service):
        oturum = service.login("kullanici", "parola123")
        service.logout(oturum.refresh_token)

        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(oturum.refresh_token)

    def test_bilinmeyen_anahtarla_cikis_hata_vermez(self, service):
        service.logout("uydurma")  # sessizce başarılı sayılır

    def test_cikis_diger_cihazi_etkilemez(self, service):
        birinci = service.login("kullanici", "parola123")
        ikinci = service.login("kullanici", "parola123")

        service.logout(birinci.refresh_token)

        assert service.refresh(ikinci.refresh_token).username == "kullanici"


class TestDenetimKaydi:
    def test_basarili_giris_kaydedilir(self, service, denetim):
        service.login("kullanici", "parola123")

        assert denetim.turler(AuthEvent.LOGIN) == [("kullanici", AuthEvent.LOGIN, True)]

    def test_yanlis_sifre_kaydedilir(self, service, denetim):
        with pytest.raises(InvalidCredentialsError):
            service.login("kullanici", "yanlis")

        assert denetim.turler(AuthEvent.LOGIN) == [("kullanici", AuthEvent.LOGIN, False)]

    def test_olmayan_kullanici_da_kaydedilir(self, service, denetim):
        """Asıl değer burada: var olmayan hesaba yapılan deneme de görünmeli."""
        with pytest.raises(InvalidCredentialsError):
            service.login("yokboyle", "parola123")

        assert denetim.turler(AuthEvent.LOGIN) == [("yokboyle", AuthEvent.LOGIN, False)]

    def test_anahtar_tekrari_kaydedilir(self, service, denetim):
        ilk = service.login("kullanici", "parola123")
        service.refresh(ilk.refresh_token)

        with pytest.raises(InvalidRefreshTokenError):
            service.refresh(ilk.refresh_token)

        assert len(denetim.turler(AuthEvent.TOKEN_REUSE)) == 1

    def test_cikis_kaydedilir(self, service, denetim):
        oturum = service.login("kullanici", "parola123")
        service.logout(oturum.refresh_token)

        assert denetim.turler(AuthEvent.LOGOUT) == [("kullanici", AuthEvent.LOGOUT, True)]


class TestYoneticiYetkisi:
    def test_normal_kullanici_yonetici_degil(self, service):
        assert service.login("kullanici", "parola123").is_admin is False

    def test_yetkili_kullanici_isaretlenir(self, kullanicilar, refreshler, denetim):
        hasher = PasswordHasher()
        uid = kullanicilar.ekle("patron", hasher.hash("parola123"))
        service = UserService(
            repository=kullanicilar,
            refresh_repository=refreshler,
            hasher=hasher,
            token_service=TokenService(SECRET),
            refresh_factory=RefreshTokenFactory(),
            refresh_expire_days=30,
            audit=denetim,
            admin=SahteYetki({uid}),
        )

        assert service.login("patron", "parola123").is_admin is True

    def test_yetki_token_icinde_tasinmaz(self, kullanicilar, refreshler, denetim):
        """Yetki access token'a yazılmamalı.

        Yazılsaydı, yetki alındıktan sonra da token'ın ömrü boyunca
        geçerli kalırdı. Bu yüzden her istekte veritabanından okunur.
        """
        import base64
        import json

        hasher = PasswordHasher()
        uid = kullanicilar.ekle("patron", hasher.hash("parola123"))
        service = UserService(
            repository=kullanicilar,
            refresh_repository=refreshler,
            hasher=hasher,
            token_service=TokenService(SECRET),
            refresh_factory=RefreshTokenFactory(),
            refresh_expire_days=30,
            audit=denetim,
            admin=SahteYetki({uid}),
        )

        token = service.login("patron", "parola123").access_token
        govde = token.split(".")[1]
        yuk = json.loads(base64.urlsafe_b64decode(govde + "=" * (-len(govde) % 4)))

        assert "is_admin" not in yuk and "admin" not in yuk


class TestHizSinirlama:
    """Şifre deneme saldırısına karşı koruma."""

    def kur(self, kullanicilar, refreshler, denetim, yetki, **sinirlar):
        hasher = PasswordHasher()
        if "kullanici" not in kullanicilar.kullanicilar:
            kullanicilar.ekle("kullanici", hasher.hash("parola123"))
        return UserService(
            repository=kullanicilar,
            refresh_repository=refreshler,
            hasher=hasher,
            token_service=TokenService(SECRET),
            refresh_factory=RefreshTokenFactory(),
            refresh_expire_days=30,
            audit=denetim,
            admin=yetki,
            **sinirlar,
        )

    def test_esik_asilinca_429(self, service):
        """5 başarısız denemeden sonra istek reddedilir."""
        for _ in range(5):
            with pytest.raises(InvalidCredentialsError):
                service.login("kullanici", "yanlis")

        with pytest.raises(TooManyAttemptsError) as hata:
            service.login("kullanici", "yanlis")

        assert hata.value.status_code == 429
        assert hata.value.retry_after_seconds == 15 * 60

    def test_dogru_sifre_de_engellenir(self, service):
        """Sınır şifre doğrulamasından önce uygulanır.

        Aksi hâlde saldırgan doğru şifreyi bulduğu anda içeri girerdi ve
        sınırın hiçbir anlamı kalmazdı.
        """
        for _ in range(5):
            with pytest.raises(InvalidCredentialsError):
                service.login("kullanici", "yanlis")

        with pytest.raises(TooManyAttemptsError):
            service.login("kullanici", "parola123")

    def test_olmayan_kullanici_da_sinirlanir(self, service):
        """429 yanıtı hesabın var olduğunu ele vermemeli."""
        for _ in range(5):
            with pytest.raises(InvalidCredentialsError):
                service.login("boyle_biri_yok", "yanlis")

        with pytest.raises(TooManyAttemptsError):
            service.login("boyle_biri_yok", "yanlis")

    def test_farkli_kullanici_etkilenmez(self, kullanicilar, refreshler, denetim, yetki):
        service = self.kur(kullanicilar, refreshler, denetim, yetki)
        hasher = PasswordHasher()
        kullanicilar.ekle("digeri", hasher.hash("parola123"))

        for _ in range(5):
            with pytest.raises(InvalidCredentialsError):
                service.login("kullanici", "yanlis")

        # Başka bir hesap kilitlenmemeli.
        assert service.login("digeri", "parola123").username == "digeri"

    def test_ip_sinirini_kullanici_adi_degistirerek_asamaz(
        self, kullanicilar, refreshler, denetim, yetki
    ):
        """Her denemede farklı kullanıcı adı kullanılsa bile IP sayacı dolar."""
        service = self.kur(
            kullanicilar, refreshler, denetim, yetki,
            max_attempts=100, max_attempts_per_ip=5, window_minutes=15,
        )
        baglam = RequestContext(ip_address="10.0.0.9")

        for i in range(5):
            with pytest.raises(InvalidCredentialsError):
                service.login(f"kullanici{i}", "yanlis", baglam)

        with pytest.raises(TooManyAttemptsError):
            service.login("bambaska", "yanlis", baglam)

    def test_farkli_ip_etkilenmez(self, kullanicilar, refreshler, denetim, yetki):
        service = self.kur(
            kullanicilar, refreshler, denetim, yetki,
            max_attempts=100, max_attempts_per_ip=3, window_minutes=15,
        )
        for i in range(3):
            with pytest.raises(InvalidCredentialsError):
                service.login(f"a{i}", "yanlis", RequestContext(ip_address="10.0.0.1"))

        # Başka bir adresten gelen istek etkilenmemeli.
        with pytest.raises(InvalidCredentialsError):
            service.login("b1", "yanlis", RequestContext(ip_address="10.0.0.2"))

    def test_basarili_giris_sayaci_doldurmaz(self, service):
        for _ in range(10):
            service.login("kullanici", "parola123")

        assert service.login("kullanici", "parola123").username == "kullanici"
