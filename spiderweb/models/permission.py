from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped

from spiderweb.db import Base


class Permission(Base):
    __tablename__ = "spiderweb_permissions"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    codename: Mapped[str] = Column(String(255), unique=True, index=True, nullable=False)
