"""MSSQL depo implementasyonları."""

from typing import List, Optional

import pyodbc

from database import MSSQLConnection
from exceptions import DuplicateRecordError, InvalidIdentifierError, RecordNotFoundError
from repositories.base import BaseTaskRepository, BaseUserRepository, UserCredentials
from schemas import TaskCreate, TaskFields, TaskResponse, UserCreate, UserResponse


class MSSQLTaskRepository(BaseTaskRepository):
    """Görevleri ilişkisel veritabanında (MSSQL) saklar."""

    source_name = "mssql"

    def __init__(self, connection: MSSQLConnection) -> None:
        self._connection = connection

    @staticmethod
    def _parse_id(task_id: str) -> int:
        """MSSQL kimliği tam sayı olmalıdır.

        Dönüşüm doğrudan denenir. ``str.isdigit()`` ile ön kontrol yapmak
        yanıltıcıydı: '²' veya '⑦' gibi karakterler için True döner ama
        ``int()`` onları çeviremez, sonuç 400 yerine 500 olurdu.
        """
        try:
            return int(task_id)
        except (TypeError, ValueError) as exc:
            raise InvalidIdentifierError(
                "MSSQL için kayıt kimliği tam sayı olmalıdır."
            ) from exc

    def _to_response(self, row) -> TaskResponse:
        """Veritabanı satırını API modeline çevirir."""
        return TaskResponse(
            id=str(row[0]),
            title=row[1],
            description=row[2],
            status=row[3],
            db_source=self.source_name,
            created_at=row[4],
        )

    def create(self, task: TaskCreate, user_id: int) -> TaskResponse:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Tasks (title, description, status, user_id) "
                "OUTPUT INSERTED.id, INSERTED.created_at "
                "VALUES (?, ?, ?, ?)",
                (task.title, task.description, task.status.value, user_id),
            )
            new_id, created_at = cursor.fetchone()

        return TaskResponse(
            id=str(new_id),
            title=task.title,
            description=task.description,
            status=task.status,
            db_source=self.source_name,
            created_at=created_at,
        )

    def list_all(self, user_id: int, limit: int, offset: int) -> List[TaskResponse]:
        with self._connection.cursor() as cursor:
            # Sayfalama olmadan tek istek tüm tabloyu belleğe çekebilirdi.
            cursor.execute(
                "SELECT id, title, description, status, created_at "
                "FROM Tasks WHERE user_id = ? "
                "ORDER BY created_at DESC, id DESC "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                (user_id, offset, limit),
            )
            rows = cursor.fetchall()

        return [self._to_response(row) for row in rows]

    def count(self, user_id: int) -> int:
        with self._connection.cursor() as cursor:
            # IX_Tasks_user_id indeksi sayesinde tablo taranmaz.
            cursor.execute("SELECT COUNT(*) FROM Tasks WHERE user_id = ?", (user_id,))
            return cursor.fetchone()[0]

    def update(self, task_id: str, task: TaskFields, user_id: int) -> TaskResponse:
        numeric_id = self._parse_id(task_id)

        with self._connection.cursor() as cursor:
            # user_id koşulu, başkasının görevinin güncellenmesini engeller.
            # OUTPUT sayesinde güncelleme ve created_at okuma tek sorguda olur;
            # eşleşen kayıt yoksa sonuç boş döner ve 404 üretilir.
            cursor.execute(
                "UPDATE Tasks SET title = ?, description = ?, status = ? "
                "OUTPUT INSERTED.created_at "
                "WHERE id = ? AND user_id = ?",
                (task.title, task.description, task.status.value, numeric_id, user_id),
            )
            row = cursor.fetchone()

        if row is None:
            raise RecordNotFoundError(f"{task_id} numaralı görev MSSQL'de bulunamadı.")

        return TaskResponse(
            id=task_id,
            title=task.title,
            description=task.description,
            status=task.status,
            db_source=self.source_name,
            created_at=row[0],
        )

    def delete(self, task_id: str, user_id: int) -> None:
        numeric_id = self._parse_id(task_id)

        with self._connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM Tasks WHERE id = ? AND user_id = ?", (numeric_id, user_id)
            )
            if cursor.rowcount == 0:
                raise RecordNotFoundError(
                    f"{task_id} numaralı görev MSSQL'de bulunamadı."
                )


class MSSQLUserRepository(BaseUserRepository):
    """Kullanıcı kayıtlarını MSSQL üzerinde yönetir."""

    def __init__(self, connection: MSSQLConnection) -> None:
        self._connection = connection

    def create(self, user: UserCreate, password_hash: str) -> UserResponse:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO Users (username, email, password_hash) "
                    "OUTPUT INSERTED.id, INSERTED.created_at "
                    "VALUES (?, ?, ?)",
                    (user.username, user.email, password_hash),
                )
                new_id, created_at = cursor.fetchone()
        except pyodbc.IntegrityError as exc:
            # UNIQUE kısıtı: iki istek aynı anda gelse bile doğru cevap verilir.
            raise DuplicateRecordError("Bu kullanıcı adı zaten alınmış!") from exc

        return UserResponse(
            id=new_id,
            username=user.username,
            email=user.email,
            created_at=created_at,
        )

    def get_credentials(self, username: str) -> Optional[UserCredentials]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, password_hash FROM Users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()

        return UserCredentials(id=row[0], password_hash=row[1]) if row else None

    def get_username(self, user_id: int) -> Optional[str]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT username FROM Users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

        return row[0] if row else None
