"""Yönetim ekranının okuduğu sorgular (MSSQL)."""

from typing import List, Optional

from database import MSSQLConnection
from schemas import AdminSessionRow, AdminUserRow


class MSSQLAdminRepository:
    """Yönetim görünümleri. Yalnızca okuma ve oturum iptali yapar."""

    def __init__(self, connection: MSSQLConnection) -> None:
        self._connection = connection

    def users(self) -> List[AdminUserRow]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, u.email, u.created_at, u.is_admin,
                       (SELECT COUNT(DISTINCT family_id) FROM RefreshTokens
                        WHERE user_id = u.id),
                       (SELECT COUNT(*) FROM Tasks WHERE user_id = u.id)
                FROM Users u
                ORDER BY u.id
                """
            )
            rows = cursor.fetchall()

        return [
            AdminUserRow(
                id=row[0],
                username=row[1],
                email=row[2],
                created_at=row[3],
                is_admin=bool(row[4]),
                session_count=row[5],
                task_count=row[6],
            )
            for row in rows
        ]

    def sessions(self, limit: int = 100) -> List[AdminSessionRow]:
        """Oturum zincirleri. Aynı aileden birden çok kayıt tek satırda özetlenir."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT TOP {limit}
                       r.family_id,
                       MAX(u.username)      AS username,
                       MIN(r.created_at)    AS started_at,
                       MAX(r.used_at)       AS last_used_at,
                       MAX(r.expires_at)    AS expires_at,
                       MIN(CASE WHEN r.revoked_at IS NULL THEN 0 ELSE 1 END) AS all_revoked,
                       MAX(CASE WHEN r.revoked_at IS NULL AND r.used_at IS NULL
                                     AND r.expires_at > SYSDATETIME()
                                THEN 1 ELSE 0 END) AS has_usable
                FROM RefreshTokens r JOIN Users u ON u.id = r.user_id
                GROUP BY r.family_id
                ORDER BY MIN(r.created_at) DESC
                """
            )
            rows = cursor.fetchall()

        return [
            AdminSessionRow(
                family_id=row[0],
                username=row[1],
                started_at=row[2],
                last_used_at=row[3],
                expires_at=row[4],
                revoked=bool(row[5]),
                active=bool(row[6]),
            )
            for row in rows
        ]

    def is_admin(self, user_id: int) -> bool:
        """Yetki her istekte veritabanından okunur.

        Token'a yazılsaydı, yetki alındıktan sonra da token'ın ömrü
        boyunca (15 dk) geçerli kalırdı.
        """
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT is_admin FROM Users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

        return bool(row[0]) if row else False

    def set_admin(self, username: str, value: bool) -> Optional[int]:
        """Yetkiyi verir/alır. Kullanıcı yoksa ``None`` döner."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE Users SET is_admin = ? OUTPUT INSERTED.id WHERE username = ?",
                (1 if value else 0, username),
            )
            row = cursor.fetchone()

        return row[0] if row else None
