from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from src.data.models.product import Product
    from src.data.models.work_center import WorkCenter


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("batch_number", "batch_date", name="uq_batch_number_date"),
        Index("idx_batch_closed", "is_closed"),
        Index("idx_batch_shift_times", "shift_start", "shift_end"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    is_closed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task_description: Mapped[str] = mapped_column(String(500), nullable=False)
    work_center_id: Mapped[int] = mapped_column(
        ForeignKey("work_centers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    shift: Mapped[str] = mapped_column(String(100), nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False)

    batch_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    batch_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    nomenclature: Mapped[str] = mapped_column(String(255), nullable=False)
    ekn_code: Mapped[str] = mapped_column(String(100), nullable=False)

    shift_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shift_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    products: Mapped[list[Product]] = relationship(
        "Product",
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    work_center: Mapped[WorkCenter] = relationship("WorkCenter", back_populates="batches")
