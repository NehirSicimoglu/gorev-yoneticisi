"""API veri modelleri (Pydantic şemaları).

İstek gövdeleri burada doğrulanır. Kurallar frontend'deki validation.js
ve veritabanı kolon sınırlarıyla birebir aynıdır.

Girdi ve çıktı modelleri bilinçli olarak ayrıdır: girdide katı davranılır
(enum, uzunluk sınırı), çıktıda esnek (``status`` düz metindir, böylece
veritabanındaki beklenmedik bir değer listelemeyi çökertmez).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from enums import AuthEvent, DatabaseSource, DatabaseTarget, TaskStatus

#: bcrypt en fazla bu kadar bayt işler; fazlasını kütüphane reddeder.
MAX_PASSWORD_BYTES = 72

#: Kaba kuvvet denemesini pahalı kılan en kısa şifre uzunluğu.
MIN_PASSWORD_LENGTH = 8


# ==========================================
# KULLANICI
# ==========================================
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    #: Uzunluk sınırı ``Field`` yerine doğrulayıcıda: Pydantic'in hazır
    #: mesajı İngilizcedir, arayüz ise sunucudan geleni olduğu gibi gösterir.
    password: str

    @field_validator("password")
    @classmethod
    def _meets_policy(cls, value: str) -> str:
        """Şifre politikası: en az 8 karakter ve bir büyük harf.

        ``isupper`` Unicode farkındadır, yani ``Ş``, ``Ğ``, ``İ`` gibi
        Türkçe büyük harfler de sayılır. ``[A-Z]`` deseni kullanılsaydı
        yalnızca Türkçe harf içeren geçerli bir şifre reddedilirdi.
        """
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalıdır."
            )
        if not any(karakter.isupper() for karakter in value):
            raise ValueError("Şifre en az bir büyük harf içermelidir.")
        return value

    @field_validator("password")
    @classmethod
    def _fits_bcrypt_limit(cls, value: str) -> str:
        """bcrypt sınırı karakter değil **bayt** cinsindendir.

        Türkçe karakterler UTF-8'de 2 bayt tuttuğu için 72 karakterden
        kısa bir şifre bile sınırı aşabilir. Kontrol edilmezse bcrypt
        ValueError fırlatır ve kullanıcı anlamsız bir 500 hatası alır.
        """
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Şifre en fazla {MAX_PASSWORD_BYTES} bayt olabilir "
                "(Türkçe karakterler 2 bayt sayılır)."
            )
        return value


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestContext(BaseModel):
    """İsteğin geldiği yer. Denetim kaydına yazılır."""

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ==========================================
# GÖREV
# ==========================================
class TaskFields(BaseModel):
    """Görevin kullanıcı tarafından belirlenen alanları."""

    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(default=None, max_length=4000)
    status: TaskStatus = TaskStatus.PENDING


class TaskCreate(TaskFields):
    """Yeni görev. Hedef 'both' olabilir (iki veritabanına birden)."""

    db_target: DatabaseTarget


class TaskUpdate(TaskFields):
    """Var olan görevin güncellenmesi.

    ``db_target`` burada 'both' kabul etmez: bir kayıt tek bir
    veritabanında yaşar, sonradan başka birine taşınamaz.
    """

    db_target: DatabaseSource


class TaskResponse(BaseModel):
    #: MSSQL'in tam sayı kimliği ile MongoDB'nin ObjectId'si tek tipte birleşir.
    id: str
    title: str
    #: Girdide ``Optional``, çıktıda her zaman metin. Dönüşüm aşağıdaki
    #: doğrulayıcıda yapılır; depoların tek tek düzeltmesi gerekmez.
    description: str = ""
    #: Çıktıda düz metin: veritabanındaki eski/beklenmedik bir değer
    #: listelemeyi çökertmesin.
    status: str
    db_source: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("description", mode="before")
    @classmethod
    def _none_is_empty(cls, value: Optional[str]) -> str:
        """Açıklama yoksa ``None`` değil boş metin döner.

        Açıklama isteğe bağlıdır (``TaskCreate.description`` ``Optional``),
        veritabanında da ``NULL`` durur. Burada normalleştirilmezse
        yanıtın tipi kayda göre değişir ve arayüzün her yerde ``null``
        kontrolü yapması gerekirdi.
        """
        return value if value is not None else ""


# ==========================================
# OTURUM
# ==========================================
class AuthenticatedUser(BaseModel):
    """Geçerli oturumun sahibi. Token içeriğinden okunur."""

    id: int
    username: str


class TokenResponse(BaseModel):
    """İstemciye dönen oturum bilgisi.

    Refresh token bilerek yoktur: httpOnly çerezle taşınır, JavaScript
    onu hiç görmez.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # saniye
    username: str
    #: Arayüzün yönetim sekmesini gösterip göstermeyeceğini bilmesi için.
    #: Yalnızca görsel bir ipucudur — yetki her istekte sunucuda denetlenir.
    is_admin: bool = False


class IssuedSession(BaseModel):
    """Servis katmanının ürettiği tam oturum.

    Refresh token yalnızca HTTP katmanına ulaşır ve orada çereze yazılır;
    yanıt gövdesine hiçbir zaman konmaz.
    """

    access_token: str
    expires_in: int
    username: str
    is_admin: bool
    refresh_token: str
    refresh_expires_in: int

    def to_response(self) -> "TokenResponse":
        """İstemciye gidecek, refresh içermeyen biçim."""
        return TokenResponse(
            access_token=self.access_token,
            expires_in=self.expires_in,
            username=self.username,
            is_admin=self.is_admin,
        )


class UsernameResponse(BaseModel):
    """``GET /auth/me`` yanıtı."""

    username: str


# ==========================================
# YÖNETİM
# ==========================================
class AdminUserRow(BaseModel):
    """Yönetim ekranındaki kullanıcı satırı."""

    id: int
    username: str
    email: str
    created_at: datetime
    is_admin: bool
    session_count: int
    task_count: int


class AdminSessionRow(BaseModel):
    """Bir oturum zinciri (aynı cihazdan yapılan giriş)."""

    family_id: str
    username: str
    started_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: datetime
    revoked: bool
    active: bool


class AdminEventRow(BaseModel):
    """Denetim kaydındaki bir satır."""

    id: int
    username: str
    event: AuthEvent
    success: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
