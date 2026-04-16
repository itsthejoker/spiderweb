import base64
import hashlib
import secrets
import typing
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, relationship

from spiderweb.db import Base

if typing.TYPE_CHECKING:
    from spiderweb.models.permission import Permission


user_permissions = Table(
    "spiderweb_user_permissions",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("spiderweb_users.id"), primary_key=True),
    Column(
        "permission_id",
        Integer,
        ForeignKey("spiderweb_permissions.id"),
        primary_key=True,
    ),
)


class AnonymousUser:
    id = None
    username = ""
    is_active = False
    is_superuser = False
    is_staff = False

    def __str__(self) -> str:
        return "AnonymousUser"

    def __eq__(self, other) -> bool:
        return isinstance(other, self.__class__)

    def __hash__(self) -> int:
        return 1

    @property
    def is_anonymous(self) -> bool:
        return True

    @property
    def is_authenticated(self) -> bool:
        return False

    def set_password(self, raw_password: str) -> None:
        raise NotImplementedError("Anonymous users cannot change passwords.")

    def check_password(self, raw_password: str) -> bool:
        raise NotImplementedError("Anonymous users cannot check passwords.")

    def get_username(self) -> str:
        return self.username


class User(Base):
    __tablename__ = "spiderweb_users"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    password: Mapped[str] = Column(String(128), default="")
    last_login: Mapped[datetime | None] = Column(DateTime, nullable=True)
    is_superuser: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    username: Mapped[str] = Column(String(150), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = Column(String(150), default="", nullable=False)
    last_name: Mapped[str] = Column(String(150), default="", nullable=False)
    email: Mapped[str] = Column(String(254), default="", nullable=False)
    is_staff: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    date_joined: Mapped[datetime] = Column(
        DateTime, default=datetime.now, nullable=False
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=user_permissions
    )

    def __str__(self) -> str:
        return self.username

    def get_username(self) -> str:
        return self.username

    def get_full_name(self) -> str:
        first = self.first_name or ""
        last = self.last_name or ""
        return f"{first} {last}".strip()

    def get_short_name(self) -> str:
        return self.first_name

    def set_password(self, raw_password: str) -> None:
        # Django's system has worked for a long time, and I see no reason to
        # reinvent the wheel. Off we go!
        if not raw_password:
            self.set_unusable_password()
            return

        iterations = 600000
        salt = secrets.token_urlsafe(16)[:22]
        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt.encode("ascii"),
            iterations,
        )
        hash_b64 = base64.b64encode(hash_bytes).decode("ascii")
        self.password = f"pbkdf2_sha256${iterations}${salt}${hash_b64}"

    def check_password(self, raw_password: str) -> bool:
        if not raw_password or not self.password or not self.has_usable_password():
            return False

        parts = self.password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False

        try:
            iterations = int(parts[1])
            salt = parts[2]
            expected_hash_b64 = parts[3]
        except ValueError:
            return False

        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt.encode("ascii"),
            iterations,
        )
        hash_b64 = base64.b64encode(hash_bytes).decode("ascii")

        return secrets.compare_digest(expected_hash_b64, hash_b64)

    def set_unusable_password(self) -> None:
        self.password = f"!{secrets.token_urlsafe(20)}"

    def has_usable_password(self) -> bool:
        if not self.password:
            return False
        return not self.password.startswith("!")

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def is_authenticated(self) -> bool:
        return True
