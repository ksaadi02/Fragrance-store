from decimal import Decimal
import pytest

from oud_ledger.db import create_session_factory, session_scope
from oud_ledger.models import ExpenseCategory, FragranceFormat, OrderStatus
from oud_ledger.services.finance import get_financial_summary, record_expense
from oud_ledger.services.inventory import (
    InsufficientStockError,
    add_stock_batch,
    create_fragrance,
    get_available_stock,
    list_low_stock_fragrances,
)
from oud_ledger.services.orders import create_order, update_order_status


def test_fifo_stock_orders_and_financial_summary():
    factory = create_session_factory("sqlite:///:memory:")

    with session_scope(factory) as session:
        oud = create_fragrance(
            session,
            sku="OUD-001",
            name="Royal Mukhallat",
            house_or_origin="Oman",
            fragrance_format=FragranceFormat.ATTAR_OIL,
            volume_ml=12,
            unit_price=Decimal("90.00"),
            reorder_threshold=5,
        )
        add_stock_batch(session, fragrance_id=oud.id, batch_code="BATCH-1", quantity=4, unit_cost="30.00")
        add_stock_batch(session, fragrance_id=oud.id, batch_code="BATCH-2", quantity=6, unit_cost="40.00")

        # Order consumes 4 units from BATCH-1 ($30) and 2 from BATCH-2 ($40) => COGS = $200
        order = create_order(
            session,
            order_number="ORD-2001",
            customer_label="Example Buyer",
            line_items=[(oud.id, 6)],
            shipping_collected=Decimal("10.00"),
            discount_amount=Decimal("5.00"),
        )
        assert order.status == OrderStatus.FULFILLED
        assert get_available_stock(session, oud.id) == 4

        low = list_low_stock_fragrances(session)
        assert len(low) == 1
        assert low[0][1] == 4

        record_expense(
            session,
            title="Glass flacons",
            category=ExpenseCategory.PACKAGING_BOTTLES,
            amount=Decimal("50.00"),
        )

        summary = get_financial_summary(session)
        # Gross product rev: 6 * 90 = 540; +10 shipping - 5 discount = 545
        assert summary.net_revenue == Decimal("545.00")
        assert summary.cogs == Decimal("200.00")
        assert summary.gross_profit == Decimal("345.00")
        assert summary.operating_expenses == Decimal("50.00")
        assert summary.net_income == Decimal("295.00")
        # Remaining 4 units are all in BATCH-2 @ $40 => $160
        assert summary.inventory_asset_value == Decimal("160.00")


def test_refund_restores_stock_and_rejects_oversell():
    factory = create_session_factory("sqlite:///:memory:")

    with session_scope(factory) as session:
        bakhoor = create_fragrance(
            session,
            sku="BKH-010",
            name="Yemeni Sidr Bakhoor",
            house_or_origin="Yemen",
            fragrance_format=FragranceFormat.BAKHOOR,
            volume_ml=80,
            unit_price=Decimal("45.00"),
        )
        add_stock_batch(session, fragrance_id=bakhoor.id, batch_code="B-1", quantity=2, unit_cost="15.00")

        with pytest.raises(InsufficientStockError):
            create_order(
                session,
                order_number="ORD-BAD",
                customer_label="Example Buyer",
                line_items=[(bakhoor.id, 3)],
            )

        order = create_order(
            session,
            order_number="ORD-OK",
            customer_label="Example Buyer",
            line_items=[(bakhoor.id, 2)],
        )
        assert get_available_stock(session, bakhoor.id) == 0

        update_order_status(session, order_number="ORD-OK", new_status=OrderStatus.REFUNDED)
        assert get_available_stock(session, bakhoor.id) == 2
        summary = get_financial_summary(session)
        assert summary.refunded_amount == Decimal("90.00")
        assert summary.net_revenue == Decimal("0.00")