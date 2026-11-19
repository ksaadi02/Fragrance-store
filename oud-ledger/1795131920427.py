from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from oud_ledger.models import Expense, ExpenseCategory, Order, OrderStatus, StockBatch
from oud_ledger.services.orders import calculate_order_total


@dataclass(frozen=True)
class FinancialSummary:
    gross_product_revenue: Decimal
    shipping_revenue: Decimal
    discounts_given: Decimal
    refunded_amount: Decimal
    net_revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    net_income: Decimal
    inventory_asset_value: Decimal


def record_expense(
    session: Session,
    *,
    title: str,
    category: ExpenseCategory,
    amount: Decimal | str,
    notes: str | None = None,
) -> Expense:
    amt = Decimal(str(amount))
    if amt <= Decimal("0.00"):
        raise ValueError("Expense amount must be positive.")
    expense = Expense(
        title=title.strip(),
        category=category,
        amount=amt,
        notes=notes,
    )
    session.add(expense)
    session.flush()
    return expense


def get_financial_summary(session: Session) -> FinancialSummary:
    orders = session.scalars(select(Order)).all()
    expenses = session.scalars(select(Expense)).all()
    batches = session.scalars(select(StockBatch)).all()

    gross_product_revenue = Decimal("0.00")
    shipping_revenue = Decimal("0.00")
    discounts_given = Decimal("0.00")
    refunded_amount = Decimal("0.00")
    cogs = Decimal("0.00")

    for order in orders:
        if order.status == OrderStatus.FULFILLED:
            items_rev = sum(
                (item.unit_price * Decimal(item.quantity) for item in order.items), Decimal("0.00")
            )
            gross_product_revenue += items_rev
            shipping_revenue += order.shipping_collected
            discounts_given += order.discount_amount
            cogs += sum(
                (item.unit_cost_snapshot * Decimal(item.quantity) for item in order.items),
                Decimal("0.00"),
            )
        elif order.status == OrderStatus.REFUNDED:
            refunded_amount += calculate_order_total(order)

    net_revenue = (
        gross_product_revenue + shipping_revenue - discounts_given - refunded_amount
    ).quantize(Decimal("0.01"))
    gross_profit = (net_revenue - cogs).quantize(Decimal("0.01"))
    operating_expenses = sum((e.amount for e in expenses), Decimal("0.00")).quantize(Decimal("0.01"))
    net_income = (gross_profit - operating_expenses).quantize(Decimal("0.01"))
    inventory_asset_value = sum(
        (b.unit_cost * Decimal(b.quantity_remaining) for b in batches), Decimal("0.00")
    ).quantize(Decimal("0.01"))

    return FinancialSummary(
        gross_product_revenue=gross_product_revenue.quantize(Decimal("0.01")),
        shipping_revenue=shipping_revenue.quantize(Decimal("0.01")),
        discounts_given=discounts_given.quantize(Decimal("0.01")),
        refunded_amount=refunded_amount.quantize(Decimal("0.01")),
        net_revenue=net_revenue,
        cogs=cogs.quantize(Decimal("0.01")),
        gross_profit=gross_profit,
        operating_expenses=operating_expenses,
        net_income=net_income,
        inventory_asset_value=inventory_asset_value,
    )