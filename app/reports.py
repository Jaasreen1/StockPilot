"""CSV exports and inventory reporting, using safe spreadsheet values."""
import csv
import io
from datetime import datetime, timezone

from app.db import connect


def safe_cell(value):
    """Prevent formulas being interpreted when CSV opens in a spreadsheet."""
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text
    return text


def csv_document(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return "\ufeff" + stream.getvalue()


def product_export():
    with connect() as db:
        rows = db.execute("""
            SELECT sku, name, category, price_cents, stock, reorder_level,
                   stock * price_cents AS stock_value_cents, created_at
            FROM products ORDER BY name COLLATE NOCASE, id
        """).fetchall()
    return csv_document(
        ("SKU", "Product", "Category", "Unit price (cents)", "Stock",
         "Reorder level", "Stock value (cents)", "Created at (UTC)"),
        rows,
    )


def movement_export():
    with connect() as db:
        rows = db.execute("""
            SELECT m.id, p.sku, p.name, m.kind, m.quantity,
                   m.stock_before, m.stock_after, m.note, m.created_at
            FROM movements AS m JOIN products AS p ON p.id=m.product_id
            ORDER BY m.id DESC
        """).fetchall()
    return csv_document(
        ("Movement ID", "SKU", "Product", "Type", "Quantity",
         "Before", "After", "Note", "Created at (UTC)"),
        rows,
    )


def inventory_report():
    with connect() as db:
        categories = [dict(row) for row in db.execute("""
            SELECT category, COUNT(*) AS products, SUM(stock) AS units,
                   SUM(stock * price_cents) AS value_cents,
                   SUM(CASE WHEN stock <= reorder_level THEN 1 ELSE 0 END) AS low_stock
            FROM products GROUP BY category ORDER BY value_cents DESC, category
        """)]
        low_stock = [dict(row) for row in db.execute("""
            SELECT id, sku, name, category, stock, reorder_level,
                   MAX(reorder_level - stock, 0) AS units_to_reorder
            FROM products WHERE stock <= reorder_level
            ORDER BY (reorder_level - stock) DESC, name COLLATE NOCASE LIMIT 50
        """)]
        recent = [dict(row) for row in db.execute("""
            SELECT substr(created_at,1,10) AS day, kind, COUNT(*) AS movements,
                   SUM(quantity) AS units
            FROM movements GROUP BY day, kind ORDER BY day DESC, kind LIMIT 90
        """)]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
        "low_stock": low_stock,
        "movement_trends": recent,
    }
