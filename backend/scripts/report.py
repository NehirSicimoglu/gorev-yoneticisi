"""Kullanıcı ve oturum raporu.

Konteyner içinden:
    docker compose exec backend python scripts/report.py

Host'tan (conda ortamıyla):
    MSSQL_HOST=localhost MONGO_HOST=localhost python scripts/report.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from database import MongoConnection, MSSQLConnection  # noqa: E402


def baslik(metin: str) -> None:
    print(f"\n{'═' * 66}\n  {metin}\n{'═' * 66}")


def kullanicilar(connection: MSSQLConnection) -> None:
    baslik("KULLANICILAR")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.username, u.email, u.created_at,
                   (SELECT COUNT(DISTINCT family_id) FROM RefreshTokens
                    WHERE user_id = u.id) AS oturum_sayisi,
                   (SELECT COUNT(*) FROM Tasks WHERE user_id = u.id) AS gorev_sayisi
            FROM Users u ORDER BY u.id
            """
        )
        satirlar = cursor.fetchall()

    if not satirlar:
        print("  (kayıtlı kullanıcı yok)")
        return

    print(f"  {'ID':<4} {'KULLANICI':<14} {'E-POSTA':<24} {'KAYIT':<13} {'GİRİŞ':>6} {'GÖREV':>6}")
    print("  " + "-" * 62)
    for uid, ad, eposta, tarih, oturum, gorev in satirlar:
        print(f"  {uid:<4} {ad:<14} {eposta:<24} {tarih:%d.%m.%Y}   {oturum:>6} {gorev:>6}")


def oturumlar(connection: MSSQLConnection, limit: int = 20) -> None:
    baslik(f"SON OTURUM HAREKETLERİ (en yeni {limit})")
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT TOP {limit} u.username, r.family_id, r.created_at,
                   r.used_at, r.revoked_at, r.expires_at
            FROM RefreshTokens r JOIN Users u ON u.id = r.user_id
            ORDER BY r.created_at DESC
            """
        )
        satirlar = cursor.fetchall()

    if not satirlar:
        print("  (oturum kaydı yok)")
        return

    print(f"  {'KULLANICI':<14} {'OTURUM':<10} {'ZAMAN':<18} DURUM")
    print("  " + "-" * 62)
    for ad, aile, olusma, kullanilmis, iptal, _ in satirlar:
        if iptal:
            durum = "iptal edildi (çıkış veya hırsızlık tespiti)"
        elif kullanilmis:
            durum = "yenilendi"
        else:
            durum = "aktif"
        print(f"  {ad:<14} {aile[:8]:<10} {olusma:%d.%m.%Y %H:%M}   {durum}")


def gorevler(connection: MSSQLConnection, mongo: MongoConnection) -> None:
    baslik("GÖREV DAĞILIMI")
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM Tasks")
        mssql_adet = cursor.fetchone()[0]

    try:
        mongo_adet = mongo.database["tasks"].count_documents({})
    except Exception:
        mongo_adet = "erişilemiyor"

    print(f"  MSSQL   : {mssql_adet}")
    print(f"  MongoDB : {mongo_adet}")


def olaylar(connection: MSSQLConnection, limit: int = 15) -> None:
    baslik(f"KİMLİK DOĞRULAMA OLAYLARI (son {limit})")
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT TOP {limit} username, event, success, ip_address, created_at
            FROM AuthEvents ORDER BY created_at DESC, id DESC
            """
        )
        satirlar = cursor.fetchall()

    if not satirlar:
        print("  (kayıt yok)")
        return

    print(f"  {'ZAMAN':<18} {'KULLANICI':<14} {'OLAY':<12} {'IP':<16} SONUÇ")
    print("  " + "-" * 62)
    for ad, olay, basarili, ip, zaman in satirlar:
        sonuc = "✅" if basarili else "❌ BAŞARISIZ"
        print(f"  {zaman:%d.%m.%Y %H:%M}   {ad:<14} {olay:<12} {(ip or '-'):<16} {sonuc}")


def main() -> None:
    mssql = MSSQLConnection(settings)
    mongo = MongoConnection(settings)

    kullanicilar(mssql)
    oturumlar(mssql)
    olaylar(mssql)
    gorevler(mssql, mongo)

    print()
    mongo.close()


if __name__ == "__main__":
    main()
