import argparse
from decimal import Decimal

from oud_ledger.db import create_session_factory, session_scope
from oud_ledger.models import ExpenseCategory, FragranceFormat, OrderStatus
from oud_ledger.services.finance import get_financial_summary, record_expense
from oud_ledger.services.inventory import add_stock_batch, create_fragrance, list_low_stock_fragrances
from oud_ledger.services.orders import create_order, update_order_status


def seed_demo_data(factory) -> None:
    with session_scope(factory) as session:
        oud_royal = create_fragrance(
            session,
            sku="OUD-CAM-12ML",
            name="Cambodi Oud Dehnal",
            house_or_origin="Cambodia / UAE",
            fragrance_format=FragranceFormat.ATTAR_OIL,
            volume_ml=12,
            unit_price=Decimal("85.00"),
            reorder_threshold=4,
        )
        amber_edp = create_fragrance(
            session,
            sku="AMB-SULT-100ML",
            name="Sultan Amber Reserve",
            house_or_origin="Dubai",
            fragrance_format=FragranceFormat.EDP,
            volume_ml=100,
            unit_price=Decimal("120.00"),
            reorder_threshold=6,
        )
        add_stock_batch(session, fragrance_id=oud_royal.id, batch_code="B-2026-01", quantity=10, unit_cost="38.00")
        add_stock_batch(session, fragrance_id=amber_edp.id, batch_code="B-2026-02", quantity=5, unit_cost="52.00")

        create_order(
            session,
            order_number="ORD-1001",
            customer_label="Walk-in Customer #1",
            line_items=[(oud_royal.id, 2)],
            channel="in_store",
        )
        record_expense(
            session,
            title="Crystal Decanter Bottles (Example)",
            category=ExpenseCategory.PACKAGING_BOTTLES,
            amount=Decimal("140.00"),
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="oud-ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    sub.add_parser("low-stock")
    sub.add_parser("pnl")

    fulfill_cmd = sub.add_parser("fulfill")
    fulfill_cmd.add_argument("order_number")

    args = parser.parse_args()
    factory = create_session_factory()

    if args.command == "seed":
        seed_demo_data(factory)
        print("Seeded sample fragrance shop data.")
    elif args.command == "low-stock":
        with session_scope(factory) as session:
            for frag, qty in list_low_stock_fragrances(session):
                print(f"{frag.sku} | {frag.name}: {qty} left (threshold {frag.reorder_threshold})")
    elif args.command == "pnl":
        with session_scope(factory) as session:
            summary = get_financial_summary(session)
            print(f"Net Revenue: ${summary.net_revenue}")
            print(f"COGS: ${summary.cogs}")
            print(f"Gross Profit: ${summary.gross_profit}")
            print(f"Operating Expenses: ${summary.operating_expenses}")
            print(f"Net Income: ${summary.net_income}")
            print(f"Inventory Asset Value: ${summary.inventory_asset_value}")
    elif args.command == "fulfill":
        with session_scope(factory) as session:
            order = update_order_status(
                session, order_number=args.order_number, new_status=OrderStatus.FULFILLED
            )
            print(f"Order {order.order_number} -> {order.status.value}")


if __name__ == "__main__":
    main()