from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oud_ledger.db import Base


class FragranceFormat(StrEnum):
    ATTAR_OIL = "attar_oil"
    EDP = "eau_de_parfum"
    EXTRAIT = "extrait"
    BAKHOOR = "bakhoor"
    SAMPLE_VIAL = "sample_vial"


class OrderStatus(StrEnum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ExpenseCategory(StrEnum):
    STOCK_PURCHASE = "stock_purchase"
    PACKAGING_BOTTLES = "packaging_bottles"
    SHIPPING_CUSTOMS = "shipping_customs"
    RENT_UTILITIES = "rent_utilities"
    MARKETING = "marketing"
    OTHER = "other"


class Fragrance(Base):
    __tablename__ = "fragrances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    house_or_origin: Mapped[str] = mapped_column(String(120), nullable=False)
    fragrance_format: Mapped[FragranceFormat] = mapped_column(Enum(FragranceFormat), nullable=False)
    volume_ml: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reorder_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    batches: Mapped[list["StockBatch"]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="fragrance")


class StockBatch(Base):
    __tablename__ = "stock_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id"), nullable=False)
    batch_code: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    fragrance: Mapped[Fragrance] = relationship(back_populates="batches")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_label: Mapped[str] = mapped_column(String(120), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False, default="in_store")
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    shipping_collected: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    fragrance_id: Mapped[int] = mapped_column(ForeignKey("fragrances.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    fragrance: Mapped[Fragrance] = relationship(back_populates="order_items")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[ExpenseCategory] = mapped_column(Enum(ExpenseCategory), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    incurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)