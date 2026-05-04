from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet

router = APIRouter(tags=["dashboard"])

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    # Summary stats
    wallet_count_result = await db.execute(select(func.count()).select_from(Wallet))
    wallet_count = wallet_count_result.scalar() or 0

    total_balance_result = await db.execute(select(func.coalesce(func.sum(Wallet.balance_usdt), 0)))
    total_balance = Decimal(str(total_balance_result.scalar() or 0))

    tx_count_result = await db.execute(select(func.count()).select_from(Transaction))
    tx_count = tx_count_result.scalar() or 0

    total_fees_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.fee_5pct), 0)).where(
            Transaction.status == TransactionStatus.completed
        )
    )
    total_fees = Decimal(str(total_fees_result.scalar() or 0))

    # Per-tool breakdown
    tool_rows = await db.execute(
        select(
            Transaction.tool,
            func.count().label("count"),
            func.coalesce(func.sum(Transaction.total_cost), 0).label("total_cost"),
        )
        .where(Transaction.status == TransactionStatus.completed)
        .group_by(Transaction.tool)
        .order_by(func.count().desc())
    )
    tool_stats = [
        {"tool": row.tool, "count": row.count, "total_cost": Decimal(str(row.total_cost))}
        for row in tool_rows
    ]

    # Last 20 transactions
    tx_rows = await db.execute(
        select(Transaction).order_by(Transaction.created_at.desc()).limit(20)
    )
    transactions = tx_rows.scalars().all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "stats": {
                "wallet_count": wallet_count,
                "total_balance": total_balance,
                "tx_count": tx_count,
                "total_fees": total_fees,
            },
            "tool_stats": tool_stats,
            "transactions": transactions,
        },
    )
