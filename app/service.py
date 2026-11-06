"""Transactional inventory operations and domain errors."""
import sqlite3
from app.db import connect

class InventoryError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status

def products(search="", low_stock=False):
    query = "SELECT * FROM products WHERE (name LIKE ? OR sku LIKE ? OR category LIKE ?)"
    term = f"%{search}%"
    params = [term, term, term]
    if low_stock:
        query += " AND stock <= reorder_level"
    query += " ORDER BY name COLLATE NOCASE, id"
    with connect() as db:
        return [dict(row) for row in db.execute(query, params)]

def create_product(sku, name, category, price_cents, stock, reorder_level):
    try:
        with connect() as db:
            cur = db.execute(
                "INSERT INTO products(sku,name,category,price_cents,stock,reorder_level) VALUES (?,?,?,?,?,?)",
                (sku, name, category, price_cents, stock, reorder_level),
            )
            return dict(db.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise InventoryError("SKU already exists", 409) from exc

def update_product(product_id, sku, name, category, price_cents, reorder_level):
    try:
        with connect() as db:
            cur = db.execute(
                "UPDATE products SET sku=?, name=?, category=?, price_cents=?, reorder_level=? WHERE id=?",
                (sku, name, category, price_cents, reorder_level, product_id),
            )
            if not cur.rowcount:
                raise InventoryError("Product not found", 404)
            return dict(db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise InventoryError("SKU already exists", 409) from exc

def remove_product(product_id):
    with connect() as db:
        if db.execute("SELECT 1 FROM movements WHERE product_id=? LIMIT 1", (product_id,)).fetchone():
            raise InventoryError("Products with movement history cannot be deleted", 409)
        if not db.execute("DELETE FROM products WHERE id=?", (product_id,)).rowcount:
            raise InventoryError("Product not found", 404)

def move_stock(product_id, kind, quantity, note=""):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if row is None:
            raise InventoryError("Product not found", 404)
        before = row["stock"]
        after = before + quantity if kind == "IN" else before - quantity if kind == "OUT" else quantity
        if after < 0:
            raise InventoryError("Insufficient stock", 409)
        db.execute("UPDATE products SET stock=? WHERE id=?", (after, product_id))
        cur = db.execute(
            "INSERT INTO movements(product_id,kind,quantity,stock_before,stock_after,note) VALUES (?,?,?,?,?,?)",
            (product_id, kind, quantity, before, after, note),
        )
        return dict(db.execute("SELECT * FROM movements WHERE id=?", (cur.lastrowid,)).fetchone())

def movements(limit=100):
    with connect() as db:
        return [dict(row) for row in db.execute(
            """SELECT m.*, p.sku, p.name AS product_name FROM movements m
               JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT ?""", (limit,)
        )]

def metrics():
    with connect() as db:
        return dict(db.execute("""SELECT COUNT(*) AS products, COALESCE(SUM(stock),0) AS units,
            COALESCE(SUM(stock * price_cents),0) AS inventory_value_cents,
            COALESCE(SUM(CASE WHEN stock<=reorder_level THEN 1 ELSE 0 END),0) AS low_stock
            FROM products""").fetchone())
