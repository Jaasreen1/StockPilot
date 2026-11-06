"""Read-only reporting routes, separated from inventory CRUD."""
from fastapi import APIRouter
from fastapi.responses import Response

from app import reports

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/overview")
def overview():
    return reports.inventory_report()


@router.get("/products.csv")
def export_products():
    return Response(
        content=reports.product_export(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="stockpilot-products.csv"',
                 "Cache-Control": "no-store"},
    )


@router.get("/movements.csv")
def export_movements():
    return Response(
        content=reports.movement_export(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="stockpilot-movements.csv"',
                 "Cache-Control": "no-store"},
    )
