"""Şifre ve oturum güvenliği testleri."""

import time

import pytest

from exceptions import ExpiredTokenError, InvalidTokenError
from security import PasswordHasher, TokenService

SECRET = "test-icin-gizli-anahtar-en-az-32-bayt-uzunlugunda"


@pytest.fixture
def hasher() -> PasswordHasher:
    return PasswordHasher()


@pytest.fixture
def tokens() -> TokenService:
    return TokenService(secret_key=SECRET, expire_minutes=60)


class TestPasswordHasher:
    def test_hash_dogru_sifreyi_dogrular(self, hasher):
        assert hasher.verify("parola123", hasher.hash("parola123"))

    def test_hash_yanlis_sifreyi_reddeder(self, hasher):
        assert not hasher.verify("yanlis", hasher.hash("parola123"))

    def test_ayni_sifre_farkli_hash_uretir(self, hasher):
        """Her hash rastgele tuz kullanmalı; aksi hâlde gökkuşağı tablosu işe yarar."""
        assert hasher.hash("parola123") != hasher.hash("parola123")

    def test_bozuk_hash_cokmez(self, hasher):
        assert not hasher.verify("parola123", "bu-bir-hash-degil")

    def test_waste_time_bcrypt_kadar_surer(self, hasher):
        """Kullanıcı adı numaralandırmasını engelleyen önlem gerçekten çalışıyor mu?

        Sahte doğrulama, gerçek bir doğrulamayla kıyaslanabilir sürede
        olmalı; yoksa yanıt süresi kullanıcının varlığını ele verir.
        """
        gercek_hash = hasher.hash("parola123")

        basla = time.perf_counter()
        hasher.verify("yanlis", gercek_hash)
        gercek_sure = time.perf_counter() - basla

        basla = time.perf_counter()
        hasher.waste_time()
        sahte_sure = time.perf_counter() - basla

        # Aynı maliyet katsayısı kullanıldığı için süreler birbirine yakın olmalı.
        assert 0.5 < sahte_sure / gercek_sure < 2.0


class TestTokenService:
    def test_uretilen_anahtar_okunabilir(self, tokens):
        token = tokens.create_access_token(user_id=7, username="kullanici")
        user = tokens.read_user(token)

        assert user.id == 7
        assert user.username == "kullanici"

    def test_bozulmus_imza_reddedilir(self, tokens):
        """İmzanın ortasından bir karakter değiştirilir.

        Son karakter bilerek seçilmedi: imza 32 bayt olduğu hâlde
        base64url gösterimi 43 karakterdir ve son karakterin 2 biti
        kullanılmaz — onu değiştirmek aynı imzayı verebilir, test
        rastgele geçip kalırdı.
        """
        token = tokens.create_access_token(1, "kullanici")
        govde, imza = token.rsplit(".", 1)
        orta = len(imza) // 2
        bozuk_imza = imza[:orta] + ("A" if imza[orta] != "A" else "B") + imza[orta + 1 :]

        with pytest.raises(InvalidTokenError):
            tokens.read_user(f"{govde}.{bozuk_imza}")

    def test_govdesi_degistirilmis_token_reddedilir(self, tokens):
        """Saldırgan yükü değiştirip başkasının kimliğine bürünememeli."""
        import base64
        import json

        token = tokens.create_access_token(1, "kullanici")
        basluk, govde, imza = token.split(".")

        yuk = json.loads(base64.urlsafe_b64decode(govde + "=" * (-len(govde) % 4)))
        yuk["uid"] = 999  # başka bir kullanıcı olmayı dene
        sahte = base64.urlsafe_b64encode(json.dumps(yuk).encode()).decode().rstrip("=")

        with pytest.raises(InvalidTokenError):
            tokens.read_user(f"{basluk}.{sahte}.{imza}")

    def test_baska_anahtarla_imzalanan_reddedilir(self, tokens):
        yabanci = TokenService(secret_key="tamamen-baska-bir-anahtar-yine-32-bayttan-uzun")
        token = yabanci.create_access_token(1, "kullanici")

        with pytest.raises(InvalidTokenError):
            tokens.read_user(token)

    def test_suresi_dolmus_anahtar_ayri_hata_verir(self):
        gecmis = TokenService(secret_key=SECRET, expire_minutes=-1)
        token = gecmis.create_access_token(1, "kullanici")

        with pytest.raises(ExpiredTokenError):
            TokenService(secret_key=SECRET).read_user(token)

    def test_anlamsiz_metin_reddedilir(self, tokens):
        with pytest.raises(InvalidTokenError):
            tokens.read_user("bu.bir.jwt.degil")

    def test_expires_in_saniye_cinsindendir(self):
        assert TokenService(SECRET, expire_minutes=30).expires_in_seconds == 1800
