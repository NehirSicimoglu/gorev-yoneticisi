"""İstek doğrulama testleri."""

import pytest
from pydantic import ValidationError

from enums import DatabaseSource, DatabaseTarget, TaskStatus
from schemas import TaskCreate, TaskResponse, TaskUpdate, UserCreate


#: Politikayı sağlayan, testlerin çoğunda konu olmayan geçerli bir şifre.
GECERLI_SIFRE = "Parola123"


class TestUserCreate:
    def test_gecerli_kullanici(self):
        user = UserCreate(username="kullanici", email="n@ornek.com", password=GECERLI_SIFRE)
        assert user.username == "kullanici"

    @pytest.mark.parametrize("username", ["", "ab", "x" * 51])
    def test_gecersiz_kullanici_adi(self, username):
        with pytest.raises(ValidationError):
            UserCreate(username=username, email="n@ornek.com", password=GECERLI_SIFRE)

    def test_gecersiz_eposta_reddedilir(self):
        with pytest.raises(ValidationError):
            UserCreate(username="kullanici", email="eposta-degil", password=GECERLI_SIFRE)

    def test_72_bayti_asan_sifre_reddedilir(self):
        """bcrypt sınırı; kontrol edilmezse kütüphane ValueError ile 500 üretir."""
        with pytest.raises(ValidationError, match="72 bayt"):
            UserCreate(username="kullanici", email="n@ornek.com", password="A" * 73)

    def test_sinirdaki_sifre_kabul_edilir(self):
        assert UserCreate(username="kullanici", email="n@ornek.com", password="A" * 72)

    def test_turkce_karakterler_iki_bayt_sayilir(self):
        """36 Türkçe karakter 72 bayttır; 37'si sınırı aşar."""
        assert UserCreate(
            username="kullanici", email="n@ornek.com", password="Ş" + "ş" * 35
        )

        with pytest.raises(ValidationError, match="72 bayt"):
            UserCreate(username="kullanici", email="n@ornek.com", password="Ş" + "ş" * 36)


class TestSifrePolitikasi:
    """En az 8 karakter ve en az bir büyük harf."""

    @pytest.mark.parametrize("sifre", ["", "Abc12", "Parola1"])
    def test_kisa_sifre_reddedilir(self, sifre):
        with pytest.raises(ValidationError, match="en az 8 karakter"):
            UserCreate(username="kullanici", email="n@ornek.com", password=sifre)

    def test_tam_sekiz_karakter_kabul_edilir(self):
        """Sınır dahildir: 8 karakter geçerlidir, 7 değildir."""
        assert UserCreate(username="kullanici", email="n@ornek.com", password="Parola12")

    def test_buyuk_harfsiz_sifre_reddedilir(self):
        with pytest.raises(ValidationError, match="büyük harf"):
            UserCreate(username="kullanici", email="n@ornek.com", password="parola123")

    def test_turkce_buyuk_harf_sayilir(self):
        """``Ş`` büyük harftir; ``[A-Z]`` deseni bunu kaçırırdı."""
        assert UserCreate(username="kullanici", email="n@ornek.com", password="Şifreleri")

    def test_rakam_veya_isaret_zorunlu_degil(self):
        """Politika bilinçli olarak yalnızca uzunluk ve büyük harf ister."""
        assert UserCreate(username="kullanici", email="n@ornek.com", password="Parolalar")


class TestTaskResponse:
    """Çıktı modeli, kayıt hangi veritabanından gelirse gelsin aynı tipte olmalı."""

    def _yanit(self, description):
        return TaskResponse(
            id="1", title="Görev", description=description, db_source="mssql", status="Beklemede"
        )

    def test_aciklama_yoksa_bos_metin_doner(self):
        """Depolar açıklamasız görevde None geçiriyordu; yanıt 500 üretmemeli."""
        assert self._yanit(None).description == ""

    def test_aciklama_varsa_korunur(self):
        assert self._yanit("ayrıntı").description == "ayrıntı"


class TestTaskSchemas:
    def test_varsayilan_durum_beklemede(self):
        task = TaskCreate(title="Görev", db_target=DatabaseTarget.MSSQL)
        assert task.status is TaskStatus.PENDING

    def test_tanimsiz_durum_reddedilir(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="Görev", status="Uydurma", db_target=DatabaseTarget.MSSQL)

    def test_kisa_baslik_reddedilir(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="ab", db_target=DatabaseTarget.MSSQL)

    def test_olusturmada_both_kabul_edilir(self):
        task = TaskCreate(title="Görev", db_target="both")
        assert task.db_target is DatabaseTarget.BOTH

    def test_guncellemede_both_reddedilir(self):
        """Bir kayıt tek bir veritabanında yaşar; sonradan taşınamaz."""
        with pytest.raises(ValidationError):
            TaskUpdate(title="Görev", db_target="both")

    def test_guncellemede_tek_kaynak_kabul_edilir(self):
        assert TaskUpdate(title="Görev", db_target="mongodb").db_target is DatabaseSource.MONGODB
