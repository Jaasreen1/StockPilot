"""Report integration and spreadsheet safety regression tests."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import db
from app.main import app


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, "DB_PATH", Path(self.folder.name) / "test.db")
        self.patch.start()
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.patch.stop()
        self.folder.cleanup()

    def add(self, sku="SKU-1", name="Keyboard", stock=4, category="Office"):
        result = self.client.post("/api/products", json={
            "sku": sku, "name": name, "category": category,
            "price": "15.50", "stock": stock, "reorder_level": 5,
        })
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_report_totals_and_reorder(self):
        self.add()
        self.add("SKU-2", "Mouse", 10)
        result = self.client.get("/api/reports/overview")
        self.assertEqual(result.status_code, 200)
        report = result.json()
        self.assertEqual(report["categories"][0]["products"], 2)
        self.assertEqual(report["categories"][0]["value_cents"], 21700)
        self.assertEqual(report["low_stock"][0]["units_to_reorder"], 1)

    def test_product_csv_and_formula_safety(self):
        self.add(name="=HYPERLINK(1)")
        response = self.client.get("/api/reports/products.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["content-disposition"])
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["Product"], "'=HYPERLINK(1)")
        self.assertEqual(rows[0]["Unit price (cents)"], "1550")

    def test_movements_csv_and_trends(self):
        product = self.add()
        response = self.client.post(f"/api/products/{product['id']}/movements",
                                    json={"kind": "IN", "quantity": 3, "note": "+SUM(1,2)"})
        self.assertEqual(response.status_code, 201)
        csv_response = self.client.get("/api/reports/movements.csv")
        rows = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["Note"], "'+SUM(1,2)")
        self.assertEqual(self.client.get("/api/reports/overview").json()["movement_trends"][0]["units"], 3)

    def test_empty_exports(self):
        self.assertEqual(len(list(csv.reader(io.StringIO(
            self.client.get("/api/reports/products.csv").content.decode("utf-8-sig"))))), 1)
