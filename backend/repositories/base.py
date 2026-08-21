"""Depo (repository) arayüzleri — soyutlama katmanı."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, NamedTuple, Optional

from schemas import TaskCreate, TaskFields, TaskResponse, UserCreate, UserResponse


class UserCredentials(NamedTuple):
    """Giriş doğrulaması için gereken en az bilgi."""

    id: int
    password_hash: str


class BaseTaskRepository(ABC):
    """Görev deposunun uyması gereken ortak arayüz.

    MSSQL ve MongoDB implementasyonları bu sınıftan türer (kalıtım).
    ``TaskService`` hangi depoyla çalıştığını bilmeden aşağıdaki metotları
    çağırır; doğru davranışı çalışma anında nesnenin kendi türü belirler
    (çok biçimlilik / polymorphism).

    Soyut metotlar gövdesizdir: bir alt sınıf bunlardan birini yazmayı
    unutursa Python nesneyi oluşturmaya izin vermez.
    """

    #: Yanıtlarda verinin hangi veritabanından geldiğini belirtir.
    source_name: str = "unknown"

    @abstractmethod
    def create(self, task: TaskCreate, user_id: int) -> TaskResponse:
        """Yeni görevi, sahibiyle birlikte kaydeder."""

    @abstractmethod
    def list_all(self, user_id: int, limit: int, offset: int) -> List[TaskResponse]:
        """Kullanıcının görevlerinden bir sayfa döner (en yeniden eskiye)."""

    @abstractmethod
    def count(self, user_id: int) -> int:
        """Kullanıcının toplam görev sayısı.

        Arayüzün "kaç tanesini gördüm / kaç tane var" bilgisini
        gösterebilmesi ve sayfalamanın ne zaman biteceğini bilmesi için.
        """

    @abstractmethod
    def update(self, task_id: str, task: TaskFields, user_id: int) -> TaskResponse:
        """Kullanıcının görevini günceller.

        Kayıt yoksa **veya başkasına aitse** ``RecordNotFoundError``
        fırlatır: "yetkiniz yok" demek, o kaydın var olduğunu ele verirdi.
        """

    @abstractmethod
    def delete(self, task_id: str, user_id: int) -> None:
        """Kullanıcının görevini siler. Bulunamazsa ``RecordNotFoundError``."""


class BaseUserRepository(ABC):
    """Kullanıcı deposunun uyması gereken ortak arayüz."""

    @abstractmethod
    def create(self, user: UserCreate, password_hash: str) -> UserResponse:
        """Yeni kullanıcıyı hash'lenmiş şifresiyle kaydeder."""

    @abstractmethod
    def get_credentials(self, username: str) -> Optional[UserCredentials]:
        """Kullanıcının kimliğini ve şifre hash'ini döner, yoksa ``None``."""

    @abstractmethod
    def get_username(self, user_id: int) -> Optional[str]:
        """Kimliğe karşılık gelen kullanıcı adını döner, yoksa ``None``."""


class RefreshTokenRecord(NamedTuple):
    """Veritabanındaki bir yenileme anahtarı kaydı."""

    id: int
    user_id: int
    family_id: str
    expires_at: datetime
    used_at: Optional[datetime]
    revoked_at: Optional[datetime]

    def is_usable(self, now: datetime) -> bool:
        """Kayıt şu an kullanılabilir mi?

        Kullanılmış bir anahtarın tekrar gelmesi ayrı bir durumdur
        (hırsızlık şüphesi) ve çağıran tarafta ele alınır.
        """
        return self.revoked_at is None and self.used_at is None and self.expires_at > now


class BaseRefreshTokenRepository(ABC):
    """Yenileme anahtarlarının saklandığı depo.

    Anahtarın kendisi değil, SHA-256 özeti tutulur.
    """

    @abstractmethod
    def store(
        self, user_id: int, token_hash: str, family_id: str, expires_at: datetime
    ) -> None:
        """Yeni bir yenileme anahtarı kaydeder."""

    @abstractmethod
    def find(self, token_hash: str) -> Optional[RefreshTokenRecord]:
        """Özete karşılık gelen kaydı döner, yoksa ``None``."""

    @abstractmethod
    def mark_used(self, token_id: int) -> None:
        """Anahtarı kullanılmış işaretler (rotasyon)."""

    @abstractmethod
    def revoke_family(self, family_id: str) -> None:
        """Bir oturum zincirinin tamamını iptal eder (hırsızlık tespiti)."""

    @abstractmethod
    def delete_expired(self) -> int:
        """Süresi geçmiş kayıtları temizler; silinen adedi döner."""
