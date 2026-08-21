"""Kimlik doğrulama olaylarının kaydı (MSSQL)."""

import logging
from typing import List, Optional

from database import MSSQLConnection
from enums import AuthEvent
from schemas import AdminEventRow, RequestContext

logger = logging.getLogger("gorev-yoneticisi")


class MSSQLAuthEventRepository:
    """Giriş, çıkış ve yenileme olaylarını kaydeder.

    Başarısız denemeler de yazılır — asıl değeri oradadır: bir hesaba
    yapılan şifre deneme saldırısı ancak böyle görülebilir.
    """

    #: user_agent alanı sınırlıdır; uzun değerler kırpılır.
    _MAX_USER_AGENT = 300

    def __init__(self, connection: MSSQLConnection) -> None:
        self._connection = connection

    def record(
        self,
        username: str,
        event: AuthEvent,
        success: bool,
        context: Optional[RequestContext] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """Bir olayı kaydeder.

        Kayıt tutulamaması asıl işlemi engellememelidir: kullanıcı,
        denetim tablosu yüzünden giriş yapamaz duruma düşmemeli.
        """
        agent = (context.user_agent if context else None) or None
        if agent:
            agent = agent[: self._MAX_USER_AGENT]

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO AuthEvents "
                    "(username, user_id, event, success, ip_address, user_agent) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        username[:50],
                        user_id,
                        event.value,
                        1 if success else 0,
                        context.ip_address if context else None,
                        agent,
                    ),
                )
        except Exception:
            logger.exception("Denetim kaydı yazılamadı (%s / %s)", username, event.value)

    def recent(self, limit: int, offset: int) -> List[AdminEventRow]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, event, success, ip_address, user_agent, created_at "
                "FROM AuthEvents ORDER BY created_at DESC, id DESC "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                (offset, limit),
            )
            rows = cursor.fetchall()

        return [
            AdminEventRow(
                id=row[0],
                username=row[1],
                event=AuthEvent(row[2]),
                success=bool(row[3]),
                ip_address=row[4],
                user_agent=row[5],
                created_at=row[6],
            )
            for row in rows
        ]

    def count(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM AuthEvents")
            return cursor.fetchone()[0]

    def failed_since(self, username: str, minutes: int) -> int:
        """Bir kullanıcı adına yapılan son N dakikadaki başarısız giriş sayısı."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM AuthEvents "
                "WHERE username = ? AND success = 0 AND event = ? "
                "AND created_at > DATEADD(minute, ?, SYSDATETIME())",
                (username, AuthEvent.LOGIN.value, -minutes),
            )
            return cursor.fetchone()[0]

    def failed_since_ip(self, ip_address: str, minutes: int) -> int:
        """Bir IP adresinden yapılan son N dakikadaki başarısız giriş sayısı."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM AuthEvents "
                "WHERE ip_address = ? AND success = 0 AND event = ? "
                "AND created_at > DATEADD(minute, ?, SYSDATETIME())",
                (ip_address, AuthEvent.LOGIN.value, -minutes),
            )
            return cursor.fetchone()[0]
