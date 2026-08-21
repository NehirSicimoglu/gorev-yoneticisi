"""MongoDB depo implementasyonu."""

from datetime import datetime
from functools import wraps
from typing import List

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from database import MongoConnection
from exceptions import (
    DatabaseUnavailableError,
    InvalidIdentifierError,
    RecordNotFoundError,
)
from repositories.base import BaseTaskRepository
from schemas import TaskCreate, TaskFields, TaskResponse


def _translates_errors(method):
    """PyMongo hatalarını uygulamanın ortak hata tipine çevirir.

    Bağlantı sorunları her metotta ayrı ayrı yakalanmak yerine tek yerde
    ele alınır; böylece istemci 500 değil anlamlı bir 503 görür.
    """

    @wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except PyMongoError as exc:
            raise DatabaseUnavailableError("MongoDB'ye ulaşılamıyor.") from exc

    return wrapper


class MongoTaskRepository(BaseTaskRepository):
    """Görevleri belge tabanlı veritabanında (MongoDB) saklar.

    ``MSSQLTaskRepository`` ile aynı arayüzü uygular; iç işleyişi tamamen
    farklı olsa da dışarıya aynı metotları sunar.
    """

    source_name = "mongodb"
    _COLLECTION_NAME = "tasks"

    def __init__(self, connection: MongoConnection) -> None:
        self._connection = connection

    @property
    def _collection(self):
        return self._connection.database[self._COLLECTION_NAME]

    @staticmethod
    def _parse_id(task_id: str) -> ObjectId:
        """MongoDB kimliği geçerli bir ObjectId olmalıdır."""
        if not ObjectId.is_valid(task_id):
            raise InvalidIdentifierError("Geçersiz MongoDB ObjectId biçimi.")
        return ObjectId(task_id)

    def _to_response(self, document: dict) -> TaskResponse:
        """Mongo belgesini API modeline çevirir."""
        return TaskResponse(
            id=str(document["_id"]),
            title=document.get("title", ""),
            description=document.get("description"),
            status=document.get("status", ""),
            db_source=self.source_name,
            created_at=document.get("created_at"),
        )

    @_translates_errors
    def create(self, task: TaskCreate, user_id: int) -> TaskResponse:
        document = {
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "created_at": datetime.now(),
            "user_id": user_id,
        }
        document["_id"] = self._collection.insert_one(document).inserted_id
        return self._to_response(document)

    @_translates_errors
    def list_all(self, user_id: int, limit: int, offset: int) -> List[TaskResponse]:
        documents = (
            self._collection.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_response(document) for document in documents]

    @_translates_errors
    def count(self, user_id: int) -> int:
        return self._collection.count_documents({"user_id": user_id})

    @_translates_errors
    def update(self, task_id: str, task: TaskFields, user_id: int) -> TaskResponse:
        # user_id koşulu, başkasının görevinin güncellenmesini engeller.
        document = self._collection.find_one_and_update(
            {"_id": self._parse_id(task_id), "user_id": user_id},
            {
                "$set": {
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise RecordNotFoundError(f"{task_id} kimlikli görev MongoDB'de bulunamadı.")

        return self._to_response(document)

    @_translates_errors
    def delete(self, task_id: str, user_id: int) -> None:
        result = self._collection.delete_one(
            {"_id": self._parse_id(task_id), "user_id": user_id}
        )
        if result.deleted_count == 0:
            raise RecordNotFoundError(f"{task_id} kimlikli görev MongoDB'de bulunamadı.")
