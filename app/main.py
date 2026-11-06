"""StockPilot REST API and local dashboard."""
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app import db, service
from app.api_reports import router as reports_router


class ProductInput(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="General", min_length=1, max_length=60)
    price: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    reorder_level: int = Field(default=5, ge=0, le=1_000_000)

    @field_validator("sku", "name", "category")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cannot be blank")
        return value

class NewProduct(ProductInput):
    stock: int = Field(default=0, ge=0, le=1_000_000)

class StockMovement(BaseModel):
    kind: Literal["IN", "OUT", "ADJUST"]
    quantity: int = Field(ge=0, le=1_000_000)
    note: str = Field(default="", max_length=240)

    @field_validator("quantity")
    @classmethod
    def positive_for_transfer(cls, value: int, info):
        if info.data.get("kind") in ("IN", "OUT") and value < 1:
            raise ValueError("IN and OUT quantities must be positive")
        return value

def cents(value: Decimal) -> int:
    return int(value * 100)

def handle(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except service.InventoryError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

app = FastAPI(title="StockPilot", version="1.1.0", lifespan=lifespan)
app.include_router(reports_router)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/products")
def list_products(search: str = Query(default="", max_length=120), low_stock: bool = False):
    return service.products(search, low_stock)

@app.post("/api/products", status_code=201)
def add_product(data: NewProduct):
    return handle(service.create_product, data.sku, data.name, data.category,
                  cents(data.price), data.stock, data.reorder_level)

@app.put("/api/products/{product_id}")
def edit_product(product_id: int, data: ProductInput):
    return handle(service.update_product, product_id, data.sku, data.name,
                  data.category, cents(data.price), data.reorder_level)

@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(product_id: int):
    handle(service.remove_product, product_id)

@app.post("/api/products/{product_id}/movements", status_code=201)
def stock_movement(product_id: int, data: StockMovement):
    return handle(service.move_stock, product_id, data.kind, data.quantity, data.note)

@app.get("/api/movements")
def list_movements(limit: int = Query(default=50, ge=1, le=500)):
    return service.movements(limit)

@app.get("/api/metrics")
def dashboard_metrics():
    return service.metrics()
