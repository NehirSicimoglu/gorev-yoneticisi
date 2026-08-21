"""Yenileme anahtarı deposu (MSSQL)."""

from datetime import datetime
from typing import Optional

from database import MSSQLConnection
from repositories.base import BaseRefreshTokenRepository, RefreshTokenRecord


class MSSQLRefreshTokenRepository(BaseRefreshTokenRepository):
    """Yenileme anahtarlarını ilişkisel veritabanında saklar.

    Anahtarların veritabanında durması, JWT'nin temel zayıflığını kapatır:
    imzalı bir token sunucu tarafından geri alınamazken, buradaki kayıt
    silinebilir — yani oturum gerçekten iptal edilebilir.
    """

    _COLUMNS = "id, user_id, family_id, expires_at, used_at, revoked_at"

    def __init__(self, connection: MSSQLConnection) -> None:
        self._connection = connection

    def store(
        self, user_id: int, token_hash: str, family_id: str, expires_at: datetime
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO RefreshTokens (user_id, token_hash, family_id, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, token_hash, family_id, expires_at),
            )

    def find(self, token_hash: str) -> Optional[RefreshTokenRecord]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {self._COLUMNS} FROM RefreshTokens WHERE token_hash = ?",
                (token_hash,),
            )
            row = cursor.fetchone()

        return RefreshTokenRecord(*row) if row else None

    def mark_used(self, token_id: int) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE RefreshTokens SET used_at = SYSDATETIME() WHERE id = ?",
                (token_id,),
            )

    def revoke_family(self, family_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE RefreshTokens SET revoked_at = SYSDATETIME() "
                "WHERE family_id = ? AND revoked_at IS NULL",
                (family_id,),
            )

    def delete_expired(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("DELETE FROM RefreshTokens WHERE expires_at < SYSDATETIME()")
            return cursor.rowcount
