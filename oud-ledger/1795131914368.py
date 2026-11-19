from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from oud_ledger.models import Fragrance, Order, OrderItem, OrderStatus
from oud_ledger.services.inventory import consume_fifo_stock, restore_batch_stock


def create_order(
    session: Session,
    *,
    order_number: str,
    customer_label: str,
    line_items: list[tuple[int, int]],
    channel: str = "in_store",
    discount_amount: Decimal | str = Decimal("0.00"),
    shipping_collected: Decimal | str = Decimal("0.00"),
    fulfill_immediately: bool = True,
) -> Order:
    """Creates an order from (fragrance_id, quantity) pairs, optionally fulfilling stock immediately."""
    if not line_items:
        raise ValueError("Order must contain at least one item.")

    order = Order(
        order_number=order_number.strip(),
        customer_label=customer_label.strip(),
        channel=channel.strip(),
        status=OrderStatus.FULFILLED if fulfill_immediately else OrderStatus.PENDING,
        discount_amount=Decimal(str(discount_amount)),
        shipping_collected=Decimal(str(shipping_collected)),
    )
    session.add(order)
    session.flush()

    for fragrance_id, quantity in line_items:
        fragrance = session.get(Fragrance, fragrance_id)
        if fragrance is None:
            raise ValueError(f"Fragrance id {fragrance_id} not found.")
        if quantity <= 0:
            raise ValueError("Item quantity must be positive.")

        if fulfill_immediately:
            total_cogs = consume_fifo_stock(session, fragrance_id=fragrance.id, quantity=quantity)
            unit_cost_snapshot = (total_cogs / Decimal(quantity)).quantize(Decimal("0.01"))
        else:
            unit_cost_snapshot = Decimal("0.00")

        item = OrderItem(
            order_id=order.id,
            fragrance_id=fragrance.id,
            quantity=quantity,
            unit_price=fragrance.unit_price,
            unit_cost_snapshot=unit_cost_snapshot,
        )
        session.add(item)

    session.flush()
    return order


def update_order_status(
    session: Session, *, order_number: str, new_status: OrderStatus
) -> Order:
    order = session.scalar(select(Order).where(Order.order_number == order_number))
    if order is None:
        raise ValueError(f"Order {order_number} not found.")

    previous_status = order.status
    if previous_status == new_status:
        return order

    if previous_status == OrderStatus.PENDING and new_status == OrderStatus.FULFILLED:
        for item in order.items:
            total_cogs = consume_fifo_stock(
                session, fragrance_id=item.fragrance_id, quantity=item.quantity
            )
            item.unit_cost_snapshot = (total_cogs / Decimal(item.quantity)).quantize(Decimal("0.01"))
    elif previous_status == OrderStatus.FULFILLED and new_status in (
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDED,
    ):
        for item in order.items:
            restore_batch_stock(
                session,
                fragrance_id=item.fragrance_id,
                quantity=item.quantity,
                batch_code_prefix=new_status.value.upper(),
            )

    order.status = new_status
    session.flush()
    return order


def calculate_order_total(order: Order) -> Decimal:
    subtotal = sum((item.unit_price * Decimal(item.quantity) for item in order.items), Decimal("0.00"))
    total = subtotal - order.discount_amount + order.shipping_collected
    return max(total, Decimal("0.00")).quantize(Decimal("0.01"))