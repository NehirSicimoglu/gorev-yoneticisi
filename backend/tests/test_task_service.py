"""Görev iş mantığı testleri.

Veritabanı kullanılmaz: sahte (fake) depolar ``BaseTaskRepository``
arayüzünü uygular. Soyutlamanın asıl faydası burada görülür — servis,
karşısındakinin gerçek veritabanı olup olmadığını bilmez.
"""

from datetime import datetime

import pytest

from enums import DatabaseSource, DatabaseTarget, TaskStatus
from exceptions import InvalidDatabaseTargetError, RecordNotFoundError
from repositories.base import BaseTaskRepository
from schemas import TaskCreate, TaskResponse
from services import TaskService


class SahteDepo(BaseTaskRepository):
    """Bellekte çalışan depo. Gerçekleriyle aynı arayüzü uygular."""

    def __init__(self, source_name: str, create_patlar: bool = False) -> None:
        self.source_name = source_name
        self._create_patlar = create_patlar
        self._kayitlar: dict[str, TaskResponse] = {}
        self._sayac = 0
        self.silinenler: list[str] = []

    def create(self, task, user_id):
        if self._create_patlar:
            raise RuntimeError(f"{self.source_name} yazma hatası")
        self._sayac += 1
        kayit = TaskResponse(
            id=str(self._sayac),
            title=task.title,
            description=task.description or "",
            status=task.status.value,
            db_source=self.source_name,
            created_at=datetime.now(),
        )
        self._kayitlar[kayit.id] = kayit
        return kayit

    def list_all(self, user_id, limit, offset):
        return list(self._kayitlar.values())[offset : offset + limit]

    def count(self, user_id):
        return len(self._kayitlar)

    def update(self, task_id, task, user_id):
        if task_id not in self._kayitlar:
            raise RecordNotFoundError()
        return self._kayitlar[task_id]

    def delete(self, task_id, user_id):
        if task_id not in self._kayitlar:
            raise RecordNotFoundError()
        del self._kayitlar[task_id]
        self.silinenler.append(task_id)


@pytest.fixture
def mssql():
    return SahteDepo("mssql")


@pytest.fixture
def mongo():
    return SahteDepo("mongodb")


@pytest.fixture
def service(mssql, mongo):
    return TaskService({"mssql": mssql, "mongodb": mongo})


def gorev(hedef=DatabaseTarget.MSSQL) -> TaskCreate:
    return TaskCreate(title="Test görevi", description="açıklama", db_target=hedef)


class TestCreate:
    def test_tek_veritabanina_yazar(self, service, mssql, mongo):
        sonuc = service.create(gorev(DatabaseTarget.MSSQL), user_id=1)

        assert len(sonuc) == 1
        assert sonuc[0].db_source == "mssql"
        assert len(mongo._kayitlar) == 0

    def test_both_ikisine_birden_yazar(self, service, mssql, mongo):
        sonuc = service.create(gorev(DatabaseTarget.BOTH), user_id=1)

        assert {r.db_source for r in sonuc} == {"mssql", "mongodb"}
        assert len(mssql._kayitlar) == 1
        assert len(mongo._kayitlar) == 1

    def test_ikinci_yazma_patlarsa_ilki_geri_alinir(self, mssql):
        """Telafi işlemi: yarım kayıt bırakılmamalı."""
        bozuk_mongo = SahteDepo("mongodb", create_patlar=True)
        service = TaskService({"mssql": mssql, "mongodb": bozuk_mongo})

        with pytest.raises(RuntimeError):
            service.create(gorev(DatabaseTarget.BOTH), user_id=1)

        assert mssql._kayitlar == {}, "MSSQL'de yarım kayıt kaldı"
        assert mssql.silinenler == ["1"], "geri alma çalışmadı"

    def test_ilk_yazma_patlarsa_hicbir_sey_yazilmaz(self, mongo):
        bozuk_mssql = SahteDepo("mssql", create_patlar=True)
        service = TaskService({"mssql": bozuk_mssql, "mongodb": mongo})

        with pytest.raises(RuntimeError):
            service.create(gorev(DatabaseTarget.BOTH), user_id=1)

        assert mongo._kayitlar == {}


class TestSecim:
    def test_tanimsiz_kaynak_hata_verir(self, mssql):
        service = TaskService({"mssql": mssql})  # mongodb kayıtlı değil

        with pytest.raises(InvalidDatabaseTargetError):
            service.list_all(DatabaseSource.MONGODB, user_id=1, limit=10, offset=0)

    def test_dogru_depoya_yonlendirir(self, service, mongo):
        service.create(gorev(DatabaseTarget.MONGODB), user_id=1)
        sonuc = service.list_all(DatabaseSource.MONGODB, user_id=1, limit=10, offset=0)

        assert len(sonuc) == 1
        assert sonuc[0].db_source == "mongodb"


class TestSayfalama:
    def test_limit_ve_offset_uygulanir(self, service):
        for _ in range(5):
            service.create(gorev(DatabaseTarget.MSSQL), user_id=1)

        sayfa = service.list_all(DatabaseSource.MSSQL, user_id=1, limit=2, offset=1)
        assert len(sayfa) == 2

    def test_count_toplam_sayiyi_verir(self, service):
        for _ in range(5):
            service.create(gorev(DatabaseTarget.MSSQL), user_id=1)

        assert service.count(DatabaseSource.MSSQL, user_id=1) == 5

    def test_sayfalar_birlestirilince_tamami_gelir(self, service):
        for _ in range(5):
            service.create(gorev(DatabaseTarget.MSSQL), user_id=1)

        toplam = service.count(DatabaseSource.MSSQL, user_id=1)
        toplanan = []
        while len(toplanan) < toplam:
            toplanan += service.list_all(
                DatabaseSource.MSSQL, user_id=1, limit=2, offset=len(toplanan)
            )

        assert len(toplanan) == 5
        assert len({t.id for t in toplanan}) == 5, "sayfalar arasinda tekrar var"


class TestSilme:
    def test_olmayan_kayit_404(self, service):
        with pytest.raises(RecordNotFoundError):
            service.delete("yok", DatabaseSource.MSSQL, user_id=1)
