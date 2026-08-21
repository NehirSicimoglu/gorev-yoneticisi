"""Bir kullanıcıya yönetici yetkisi verir veya alır.

Yetki veritabanında tutulur, ortam değişkeninde değil: böylece
değiştirmek için uygulamayı yeniden başlatmak gerekmez.

Kullanım:
    docker compose exec backend python scripts/make_admin.py kullanici_adi
    docker compose exec backend python scripts/make_admin.py kullanici_adi --kaldir
    docker compose exec backend python scripts/make_admin.py --liste
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from database import MSSQLConnection  # noqa: E402
from repositories.admin_repository import MSSQLAdminRepository  # noqa: E402


def main() -> int:
    ayrıştırıcı = argparse.ArgumentParser(description="Yönetici yetkisi yönetimi")
    ayrıştırıcı.add_argument("username", nargs="?", help="Kullanıcı adı")
    ayrıştırıcı.add_argument(
        "--kaldir", action="store_true", help="Yetkiyi vermek yerine geri al"
    )
    ayrıştırıcı.add_argument(
        "--liste", action="store_true", help="Mevcut yöneticileri listele"
    )
    args = ayrıştırıcı.parse_args()

    admin = MSSQLAdminRepository(MSSQLConnection(settings))

    if args.liste:
        yoneticiler = [k for k in admin.users() if k.is_admin]
        if not yoneticiler:
            print("Hiç yönetici yok.")
            print("Eklemek için:  python scripts/make_admin.py <kullanıcı_adı>")
            return 0
        print("Yöneticiler:")
        for k in yoneticiler:
            print(f"  • {k.username}  ({k.email})")
        return 0

    if not args.username:
        ayrıştırıcı.error("Kullanıcı adı gerekli (veya --liste kullanın).")

    verilecek = not args.kaldir
    user_id = admin.set_admin(args.username, verilecek)

    if user_id is None:
        print(f"❌ '{args.username}' adlı kullanıcı bulunamadı.")
        print("   Önce arayüzden kayıt olun, sonra bu komutu çalıştırın.")
        return 1

    if verilecek:
        print(f"✅ '{args.username}' artık yönetici.")
        print("   Arayüzde 'Yönetim' sekmesini görmek için çıkış yapıp tekrar girin.")
    else:
        print(f"✅ '{args.username}' kullanıcısının yönetici yetkisi kaldırıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
