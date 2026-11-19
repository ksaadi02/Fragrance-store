from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from oud_ledger.models import Fragrance, FragranceFormat, StockBatch


class InsufficientStockError(ValueError):
    """Raised when requested units exceed available batch stock."""


def create_fragrance(
    session: Session,
    *,
    sku: str,
    name: str,
    house_or_origin: str,
    fragrance_format: FragranceFormat,
    volume_ml: int,
    unit_price: Decimal | str,
    reorder_threshold: int = 5,
    notes: str | None = None,
) -> Fragrance:
    fragrance = Fragrance(
        sku=sku.strip(),
        name=name.strip(),
        house_or_origin=house_or_origin.strip(),
        fragrance_format=fragrance_format,
        volume_ml=volume_ml,
        unit_price=Decimal(str(unit_price)),
        reorder_threshold=reorder_threshold,
        notes=notes,
    )
    session.add(fragrance)
    session.flush()
    return fragrance


def add_stock_batch(
    session: Session,
    *,
    fragrance_id: int,
    batch_code: str,
    quantity: int,
    unit_cost: Decimal | str,
) -> StockBatch:
    if quantity <= 0:
        raise ValueError("Batch quantity must be positive.")
    fragrance = session.get(Fragrance, fragrance_id)
    if fragrance is None:
        raise ValueError(f"Fragrance id {fragrance_id} not found.")

    batch = StockBatch(
        fragrance_id=fragrance.id,
        batch_code=batch_code.strip(),
        unit_cost=Decimal(str(unit_cost)),
        quantity_received=quantity,
        quantity_remaining=quantity,
    )
    session.add(batch)
    session.flush()
    return batch


def get_available_stock(session: Session, fragrance_id: int) -> int:
    batches = session.scalars(
        select(StockBatch).where(StockBatch.fragrance_id == fragrance_id)
    ).all()
    return sum(b.quantity_remaining for b in batches)


def consume_fifo_stock(
    session: Session, *, fragrance_id: int, quantity: int
) -> Decimal:
    """Deducts stock using FIFO and returns total COGS for the consumed units."""
    if quantity <= 0:
        raise ValueError("Quantity to consume must be positive.")

    batches = session.scalars(
        select(StockBatch)
        .where(StockBatch.fragrance_id == fragrance_id, StockBatch.quantity_remaining > 0)
        .order_by(StockBatch.received_at.asc(), StockBatch.id.asc())
    ).all()

    total_available = sum(b.quantity_remaining for b in batches)
    if total_available < quantity:
        raise InsufficientStockError(
            f"Requested {quantity} units for fragrance {fragrance_id}, only {total_available} available."
        )

    remaining_to_deduct = quantity
    total_cogs = Decimal("0.00")

    for batch in batches:
        if remaining_to_deduct == 0:
            break
        take = min(batch.quantity_remaining, remaining_to_deduct)
        batch.quantity_remaining -= take
        remaining_to_deduct -= take
        total_cogs += batch.unit_cost * Decimal(take)

    session.flush()
    return total_cogs.quantize(Decimal("0.01"))


def restore_batch_stock(
    session: Session, *, fragrance_id: int, quantity: int, batch_code_prefix: str = "RETURN"
) -> StockBatch:
    """Restores cancelled/refunded units into a new return batch."""
    if quantity <= 0:
        raise ValueError("Quantity to restore must be positive.")
    fragrance = session.get(Fragrance, fragrance_id)
    if fragrance is None:
        raise ValueError(f"Fragrance id {fragrance_id} not found.")

    latest_batch = session.scalar(
        select(StockBatch)
        .where(StockBatch.fragrance_id == fragrance_id)
        .order_by(StockBatch.id.desc())
    )
    fallback_cost = latest_batch.unit_cost if latest_batch else Decimal("0.00")

    batch = StockBatch(
        fragrance_id=fragrance.id,
        batch_code=f"{batch_code_prefix}-{fragrance.sku}",
        unit_cost=fallback_cost,
        quantity_received=quantity,
        quantity_remaining=quantity,
    )
    session.add(batch)
    session.flush()
    return batch


def list_low_stock_fragrances(session: Session) -> list[tuple[Fragrance, int]]:
    fragrances = session.scalars(select(Fragrance).order_by(Fragrance.name.asc())).all()
    low_stock: list[tuple[Fragrance, int]] = []
    for fragrance in fragrances:
        qty = get_available_stock(session, fragrance.id)
        if qty <= fragrance.reorder_threshold:
            low_stock.append((fragrance, qty))
    return low_stock