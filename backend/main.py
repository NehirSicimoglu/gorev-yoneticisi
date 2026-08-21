"""FastAPI uygulaması — HTTP katmanı.

Bu dosya yalnızca uç noktaları tanımlar ve gelen isteği ilgili servise
devreder. Veritabanı sorguları servis ve depo katmanlarındadır.
"""

import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import Cookie, Depends, FastAPI, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from database import MongoConnection, MSSQLConnection, SchemaInitializer
from enums import DatabaseSource
from exceptions import (
    AppError,
    InvalidRefreshTokenError,
    MissingTokenError,
    NotAuthorizedError,
    TooManyAttemptsError,
)
from repositories import (
    MongoTaskRepository,
    MSSQLAdminRepository,
    MSSQLAuthEventRepository,
    MSSQLRefreshTokenRepository,
    MSSQLTaskRepository,
    MSSQLUserRepository,
)
from schemas import (
    AdminEventRow,
    AdminSessionRow,
    AdminUserRow,
    AuthenticatedUser,
    LoginRequest,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TokenResponse,
    UserCreate,
    RequestContext,
    UsernameResponse,
    UserResponse,
)
from security import PasswordHasher, RefreshTokenFactory, TokenService
from services import TaskService, UserService

logger = logging.getLogger("gorev-yoneticisi")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Bağlantı nesneleri ağa çıkmaz, yalnızca yapılandırmayı tutar; bu yüzden
# modül seviyesinde oluşturulmaları güvenlidir.
mssql_connection = MSSQLConnection(settings)
mongo_connection = MongoConnection(settings)

task_service = TaskService(
    {
        MSSQLTaskRepository.source_name: MSSQLTaskRepository(mssql_connection),
        MongoTaskRepository.source_name: MongoTaskRepository(mongo_connection),
    }
)
token_service = TokenService(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    expire_minutes=settings.jwt_expire_minutes,
)
audit_repository = MSSQLAuthEventRepository(mssql_connection)
admin_repository = MSSQLAdminRepository(mssql_connection)

user_service = UserService(
    repository=MSSQLUserRepository(mssql_connection),
    refresh_repository=MSSQLRefreshTokenRepository(mssql_connection),
    hasher=PasswordHasher(),
    token_service=token_service,
    refresh_factory=RefreshTokenFactory(),
    refresh_expire_days=settings.refresh_token_expire_days,
    audit=audit_repository,
    admin=admin_repository,
    max_attempts=settings.login_max_attempts,
    max_attempts_per_ip=settings.login_max_attempts_per_ip,
    window_minutes=settings.login_window_minutes,
)


def request_context(request: Request) -> RequestContext:
    """İsteğin kaynağını denetim kaydı ve hız sınırlama için toplar.

    X-Forwarded-For başlığı **yalnızca** TRUST_PROXY açıkken okunur.
    Başlığı istemci de gönderebildiği için, ters vekil arkasında olmadan
    ona güvenmek IP başına hız sınırını işlevsiz bırakırdı: saldırgan her
    istekte farklı bir adres uydurup sayaçtan kaçabilirdi. Vekil yokken
    tek güvenilir kaynak bağlantının kendi adresidir.
    """
    ip = request.client.host if request.client else None
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Zincirin ilki asıl istemcidir: "istemci, vekil1, vekil2".
            ip = forwarded.split(",")[0].strip() or ip
    return RequestContext(ip_address=ip, user_agent=request.headers.get("user-agent"))

#: Refresh token'ın taşındığı çerezin adı.
REFRESH_COOKIE = "refresh_token"
#: Çerez yalnızca bu yola gönderilir; diğer isteklerde ağda dolaşmaz.
REFRESH_COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: Response, session) -> None:
    """Refresh token'ı httpOnly çereze yazar.

    httponly: JavaScript okuyamaz — XSS durumunda bile ele geçmez.
    samesite=lax: Başka sitelerden gelen isteklerde gönderilmez (CSRF).
    path: Yalnızca /auth altına gider, her API isteğinde taşınmaz.
    """
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=session.refresh_token,
        max_age=session.refresh_expires_in,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Uygulamanın açılış ve kapanış işleri.

    Veritabanına dokunan işler burada yapılır; modül import edilirken
    değil. Böylece testler uygulamayı veritabanı olmadan da yükleyebilir.
    """
    SchemaInitializer(mssql_connection).run()

    # Durum bilgisi amaçlıdır, engelleyici değil: bir veritabanı o an
    # kapalı olsa bile uygulama açılır ve bağlantı sonradan kurulur.
    for ad, baglanti in (("MSSQL", mssql_connection), ("MongoDB", mongo_connection)):
        durum = "✅ erişilebilir" if baglanti.is_available() else "⚠️  şu an erişilemiyor"
        logger.info("%s: %s", ad, durum)

    yield

    mongo_connection.close()


app = FastAPI(title="Görev Yöneticisi API", lifespan=lifespan)

# ==========================================
# CORS
# ==========================================
app.add_middleware(
    CORSMiddleware,
    # İzin verilen kökenler .env üzerinden ayarlanır (CORS_ORIGINS).
    allow_origins=settings.cors_origins,
    # Refresh token httpOnly çerezle taşındığı için açık olmalı. Bu
    # nedenle allow_origins "*" olamaz — adresler .env'de tek tek yazılır.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Tarayıcı, listeye ait olmayan başlıkları varsayılan olarak JavaScript'e
    # vermez. Sayfalama için toplam adedi okuyabilmesi gerekiyor.
    expose_headers=["X-Total-Count"],
)

# ==========================================
# OTURUM KORUMASI
# ==========================================
# auto_error=False: anahtar yoksa FastAPI'nin kendi hatası yerine bizim
# standart hata biçimimiz kullanılır.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Geçerli oturum anahtarını doğrular ve sahibini döner.

    Korumalı uç noktalara ``Depends(get_current_user)`` ile eklenir;
    anahtar yoksa veya geçersizse istek rotaya hiç ulaşmaz.
    """
    if credentials is None:
        raise MissingTokenError()
    return token_service.read_user(credentials.credentials)


def get_current_admin(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Yönetici yetkisini **veritabanından** doğrular.

    Yetki access token'a yazılmaz: yazılsaydı, yetki alındıktan sonra da
    token'ın ömrü boyunca (15 dk) geçerli kalırdı. Arayüzdeki sekmeyi
    gizlemek yalnızca görseldir; asıl denetim burasıdır.
    """
    if not admin_repository.is_admin(user.id):
        raise NotAuthorizedError()
    return user


# ==========================================
# MERKEZÎ HATA YÖNETİMİ
# Tüm hatalar aynı biçimde döner: {"detail": "...", "error": "..."}
# ==========================================
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Uygulama hatalarını ilgili HTTP durum koduna çevirir."""
    logger.warning("%s -> %s: %s", request.url.path, exc.status_code, exc.message)

    # 429 yanıtında istemciye ne kadar bekleyeceği standart başlıkla bildirilir.
    headers = (
        {"Retry-After": str(exc.retry_after_seconds)}
        if isinstance(exc, TooManyAttemptsError)
        else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error": type(exc).__name__},
        headers=headers,
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Beklenmeyen hatalar: ayrıntı sunucuya loglanır, istemciye sızmaz."""
    logger.exception("Beklenmeyen hata (%s)", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Beklenmeyen bir sunucu hatası oluştu.",
            "error": "InternalServerError",
        },
    )


# ==========================================
# GENEL
# ==========================================
@app.get("/")
def read_root():
    return {"status": "success", "message": "FastAPI backend tamamen hazır ve çalışıyor!"}


@app.get("/health")
def health_check():
    """Veritabanı bağlantılarının durumunu bildirir."""
    return {
        "mssql": mssql_connection.is_available(),
        "mongodb": mongo_connection.is_available(),
    }


# ==========================================
# KULLANICI ROTALARI
# ==========================================
@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user: UserCreate, context: RequestContext = Depends(request_context)):
    return user_service.register(user, context)


@app.post("/auth/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    response: Response,
    context: RequestContext = Depends(request_context),
):
    session = user_service.login(login_data.username, login_data.password, context)
    _set_refresh_cookie(response, session)
    return session.to_response()


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh_session(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    context: RequestContext = Depends(request_context),
):
    """Çerezdeki yenileme anahtarıyla yeni bir access token üretir.

    Anahtar her kullanımda değişir (rotasyon); eskisi geçersizleşir.
    """
    if not refresh_token:
        raise InvalidRefreshTokenError()

    try:
        session = user_service.refresh(refresh_token, context)
    except InvalidRefreshTokenError:
        # Artık işe yaramayan çerez tarayıcıda kalmasın.
        _clear_refresh_cookie(response)
        raise

    _set_refresh_cookie(response, session)
    return session.to_response()


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    context: RequestContext = Depends(request_context),
):
    """Oturumu sonlandırır ve zincirin tamamını iptal eder."""
    if refresh_token:
        user_service.logout(refresh_token, context)
    _clear_refresh_cookie(response)


@app.get("/auth/me", response_model=UsernameResponse)
def read_current_user(user: AuthenticatedUser = Depends(get_current_user)):
    """Oturumun hâlâ geçerli olup olmadığını sorgulamak için."""
    return UsernameResponse(username=user.username)


# ==========================================
# GÖREV ROTALARI (CRUD)
# ==========================================
@app.post("/tasks", response_model=List[TaskResponse], status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, user: AuthenticatedUser = Depends(get_current_user)):
    return task_service.create(task, user.id)


@app.get("/tasks", response_model=List[TaskResponse])
def get_tasks(
    response: Response,
    db_source: DatabaseSource = DatabaseSource.MSSQL,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Kullanıcının görevlerinden bir sayfa döner.

    Toplam kayıt sayısı ``X-Total-Count`` başlığıyla bildirilir; arayüz
    böylece kaç görevin kaldığını bilir ve "daha fazla yükle" düğmesini
    doğru zamanda gizler.
    """
    response.headers["X-Total-Count"] = str(task_service.count(db_source, user.id))
    return task_service.list_all(db_source, user.id, limit, offset)


@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    task: TaskUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return task_service.update(task_id, task, user.id, task.db_target)


@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    db_target: DatabaseSource = DatabaseSource.MSSQL,
    user: AuthenticatedUser = Depends(get_current_user),
):
    task_service.delete(task_id, db_target, user.id)
    return {
        "status": "success",
        "message": f"Görev {task_id} başarıyla silindi.",
    }


# ==========================================
# YÖNETİM ROTALARI
# Hepsi get_current_admin ile korunur; yetkisiz istek 403 alır.
# ==========================================
@app.get("/admin/users", response_model=List[AdminUserRow])
def admin_users(_: AuthenticatedUser = Depends(get_current_admin)):
    """Kayıtlı kullanıcılar, oturum ve görev sayılarıyla."""
    return admin_repository.users()


@app.get("/admin/sessions", response_model=List[AdminSessionRow])
def admin_sessions(
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthenticatedUser = Depends(get_current_admin),
):
    """Oturum zincirleri: kim, ne zaman, hâlâ aktif mi."""
    return admin_repository.sessions(limit)


@app.delete("/admin/sessions/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_revoke_session(
    family_id: str, _: AuthenticatedUser = Depends(get_current_admin)
):
    """Bir oturumu zorla sonlandırır (uzaktan çıkış)."""
    refresh_repository = MSSQLRefreshTokenRepository(mssql_connection)
    refresh_repository.revoke_family(family_id)


@app.get("/admin/events", response_model=List[AdminEventRow])
def admin_events(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: AuthenticatedUser = Depends(get_current_admin),
):
    """Kimlik doğrulama olayları — **başarısız denemeler dahil**."""
    response.headers["X-Total-Count"] = str(audit_repository.count())
    return audit_repository.recent(limit, offset)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
