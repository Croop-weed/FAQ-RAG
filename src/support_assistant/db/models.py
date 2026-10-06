from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, Index, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from support_assistant.schemas.faq import FAQStatus


class Base(DeclarativeBase):
    pass


class FAQModel(Base):
    __tablename__ = "faqs"
    __table_args__ = (
        Index("ix_faqs_status_category", "status", "category"),
        Index("ix_faqs_status_product", "status", "product"),
        Index("ix_faqs_status_version", "status", "version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    deduplication_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[FAQStatus] = mapped_column(
        Enum(
            FAQStatus,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda statuses: [status.value for status in statuses],
            name="faq_status",
            length=8,
        ),
        nullable=False,
        default=FAQStatus.ACTIVE,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
