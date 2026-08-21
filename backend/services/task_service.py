"""Görev iş mantığı."""

import logging
from typing import Dict, List, Tuple

from enums import DatabaseSource, DatabaseTarget
from exceptions import InvalidDatabaseTargetError
from repositories.base import BaseTaskRepository
from schemas import TaskCreate, TaskFields, TaskResponse

logger = logging.getLogger("gorev-yoneticisi")


class TaskService:
    """Hangi veritabanının kullanılacağını çözer ve işi ilgili depoya devreder.

    Bu sınıf ne SQL ne de Mongo sorgusu bilir; elindeki depoların hepsine
    ``BaseTaskRepository`` arayüzünden bakar. Yeni bir veritabanı eklemek
    istendiğinde burada tek satır değişmez — yeni bir depo sınıfı yazıp
    sözlüğe eklemek yeterlidir (açık/kapalı prensibi).
    """

    def __init__(self, repositories: Dict[str, BaseTaskRepository]) -> None:
        self._repositories = repositories

    def _resolve(self, target: DatabaseTarget) -> List[BaseTaskRepository]:
        """Yazma hedefine karşılık gelen depo listesini döner."""
        if target is DatabaseTarget.BOTH:
            return list(self._repositories.values())
        try:
            return [self._repositories[target.value]]
        except KeyError as exc:
            raise InvalidDatabaseTargetError() from exc

    def _resolve_single(self, source: DatabaseSource) -> BaseTaskRepository:
        """Tek bir depo gerektiren işlemler (okuma, güncelleme, silme) için."""
        try:
            return self._repositories[source.value]
        except KeyError as exc:
            raise InvalidDatabaseTargetError() from exc

    def create(self, task: TaskCreate, user_id: int) -> List[TaskResponse]:
        """Görevi seçilen veritabanı ya da veritabanlarına yazar.

        Buradaki ``repository.create(task)`` çağrısı çok biçimliliğin
        tam karşılığıdır: nesnenin MSSQL mi Mongo mu olduğu bilinmez,
        doğru gövde çalışma anında seçilir.

        'both' seçildiğinde iki veritabanı tek bir işlem gibi davranır:
        biri başarısız olursa önceden yazılanlar geri alınır. Aksi hâlde
        kullanıcı hata görürken kayıt yalnızca bir veritabanında kalırdı.
        """
        written: List[Tuple[BaseTaskRepository, TaskResponse]] = []

        try:
            for repository in self._resolve(task.db_target):
                written.append((repository, repository.create(task, user_id)))
        except Exception:
            self._undo(written, user_id)
            raise

        return [response for _, response in written]

    @staticmethod
    def _undo(written: List[Tuple[BaseTaskRepository, TaskResponse]], user_id: int) -> None:
        """Kısmi yazma durumunda başarılı kayıtları geri alır (telafi işlemi)."""
        for repository, response in written:
            try:
                repository.delete(response.id, user_id)
                logger.warning(
                    "Kısmi yazma geri alındı: %s / %s", repository.source_name, response.id
                )
            except Exception:
                # Geri alma da başarısız olursa asıl hatayı gizlememek için
                # yalnızca loglanır.
                logger.error(
                    "Geri alma başarısız: %s / %s", repository.source_name, response.id
                )

    def list_all(
        self, source: DatabaseSource, user_id: int, limit: int, offset: int
    ) -> List[TaskResponse]:
        return self._resolve_single(source).list_all(user_id, limit, offset)

    def count(self, source: DatabaseSource, user_id: int) -> int:
        return self._resolve_single(source).count(user_id)

    def update(self, task_id: str, task: TaskFields, user_id: int, source: DatabaseSource) -> TaskResponse:
        return self._resolve_single(source).update(task_id, task, user_id)

    def delete(self, task_id: str, source: DatabaseSource, user_id: int) -> None:
        self._resolve_single(source).delete(task_id, user_id)
