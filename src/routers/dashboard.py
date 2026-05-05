import uuid
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
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

    # Global per-tool breakdown
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

    # Wallet list
    wallets_result = await db.execute(select(Wallet).order_by(Wallet.created_at.desc()))
    wallets = wallets_result.scalars().all()

    # Aggregate stats per wallet (completed only)
    wallet_agg_result = await db.execute(
        select(
            Transaction.wallet_id,
            func.count().label("tx_count"),
            func.coalesce(func.sum(Transaction.total_cost), 0).label("total_spent"),
        )
        .where(Transaction.status == TransactionStatus.completed)
        .group_by(Transaction.wallet_id)
    )
    wallet_agg = {
        str(row.wallet_id): {
            "tx_count": row.tx_count,
            "total_spent": Decimal(str(row.total_spent)),
        }
        for row in wallet_agg_result
    }

    wallet_list = []
    for w in wallets:
        agg = wallet_agg.get(str(w.id), {"tx_count": 0, "total_spent": Decimal("0")})
        wallet_list.append({
            "id": str(w.id),
            "agent_id": w.agent_id,
            "balance_usdt": Decimal(str(w.balance_usdt)),
            "tx_count": agg["tx_count"],
            "total_spent": agg["total_spent"],
        })

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
            "wallet_list": wallet_list,
        },
    )


@router.get("/dashboard/wallet/{wallet_id}")
async def wallet_detail(
    wallet_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    wallet = await db.get(Wallet, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail={"error": "wallet_not_found"})

    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.wallet_id == wallet_id)
        .order_by(Transaction.created_at.desc())
        .limit(10)
    )
    transactions = tx_result.scalars().all()

    tool_result = await db.execute(
        select(
            Transaction.tool,
            func.count().label("calls"),
            func.coalesce(func.sum(Transaction.upstream_cost), 0).label("upstream_total"),
            func.coalesce(func.sum(Transaction.fee_5pct), 0).label("fees_total"),
            func.coalesce(func.sum(Transaction.total_cost), 0).label("total"),
        )
        .where(
            Transaction.wallet_id == wallet_id,
            Transaction.status == TransactionStatus.completed,
        )
        .group_by(Transaction.tool)
        .order_by(func.count().desc())
    )
    usage_by_tool = [
        {
            "tool": row.tool,
            "calls": row.calls,
            "upstream_total": f"{Decimal(str(row.upstream_total)):.6f}",
            "fees_total": f"{Decimal(str(row.fees_total)):.6f}",
            "total": f"{Decimal(str(row.total)):.6f}",
        }
        for row in tool_result
    ]

    return JSONResponse({
        "wallet": {
            "id": str(wallet.id),
            "agent_id": wallet.agent_id,
            "master_id": wallet.master_id,
            "balance_usdt": f"{Decimal(str(wallet.balance_usdt)):.6f}",
        },
        "transactions_last_10": [
            {
                "id": str(tx.id),
                "tool": tx.tool,
                "status": tx.status.value,
                "upstream_cost": f"{Decimal(str(tx.upstream_cost)):.6f}",
                "fee_5pct": f"{Decimal(str(tx.fee_5pct)):.6f}",
                "total_cost": f"{Decimal(str(tx.total_cost)):.6f}",
                "created_at": tx.created_at.strftime("%Y-%m-%d %H:%M") if tx.created_at else None,
            }
            for tx in transactions
        ],
        "usage_by_tool": usage_by_tool,
    })
