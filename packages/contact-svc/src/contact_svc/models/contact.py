from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(100))
    organization_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    emails: Mapped[list[Email]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    phone_numbers: Mapped[list[PhoneNumber]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(255), unique=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))

    contact: Mapped[Contact] = relationship(back_populates="emails")


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))

    contact: Mapped[Contact] = relationship(back_populates="phone_numbers")
