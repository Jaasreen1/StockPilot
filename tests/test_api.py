"""API integration tests using an isolated temporary SQLite database."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import db
from app.main import app


class InventoryApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.folder.name) / "test.db")
        self.db_patch.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.db_patch.stop()
        self.folder.cleanup()

    def product(self, sku="SKU-001", stock=5):
        response = self.client.post("/api/products", json={
            "sku": sku, "name": "Notebook", "category": "Stationery",
            "price": "12.50", "stock": stock, "reorder_level": 3
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_health_and_empty_inventory(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/products").json(), [])

    def test_create_list_search_and_metrics(self):
        self.product()
        self.assertEqual(len(self.client.get("/api/products?search=notebook").json()), 1)
        self.assertEqual(len(self.client.get("/api/products?search=missing").json()), 0)
        metrics = self.client.get("/api/metrics").json()
        self.assertEqual(metrics["inventory_value_cents"], 6250)
        self.assertEqual(metrics["units"], 5)

    def test_duplicate_sku(self):
        self.product()
        self.assertEqual(self.client.post("/api/products", json={
            "sku": "SKU-001", "name": "Duplicate", "price": "2.00"
        }).status_code, 409)

    def test_stock_in_out_adjust_and_history(self):
        product = self.product()
        url = f"/api/products/{product['id']}/movements"
        for kind, quantity, expected in [("IN", 4, 9), ("OUT", 7, 2), ("ADJUST", 0, 0)]:
            response = self.client.post(url, json={"kind": kind, "quantity": quantity})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["stock_after"], expected)
        self.assertEqual(len(self.client.get("/api/products?low_stock=true").json()), 1)
        self.assertEqual(len(self.client.get("/api/movements").json()), 3)

    def test_insufficient_stock_rolls_back(self):
        product = self.product(stock=1)
        response = self.client.post(f"/api/products/{product['id']}/movements",
                                    json={"kind": "OUT", "quantity": 2})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/api/products").json()[0]["stock"], 1)
        self.assertEqual(self.client.get("/api/movements").json(), [])

    def test_edit_and_delete(self):
        product = self.product()
        url = f"/api/products/{product['id']}"
        response = self.client.put(url, json={
            "sku": "NEW-SKU", "name": "New name", "category": "Office",
            "price": "9.99", "reorder_level": 10
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["stock"], 5)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_cannot_delete_product_with_history(self):
        product = self.product()
        self.client.post(f"/api/products/{product['id']}/movements",
                         json={"kind": "IN", "quantity": 1})
        self.assertEqual(self.client.delete(f"/api/products/{product['id']}").status_code, 409)

    def test_input_validation(self):
        bad = {"sku": " ", "name": "X", "price": "-2.00", "stock": -1}
        self.assertEqual(self.client.post("/api/products", json=bad).status_code, 422)
        product = self.product()
        self.assertEqual(self.client.post(f"/api/products/{product['id']}/movements",
                         json={"kind": "OUT", "quantity": 0}).status_code, 422)
        self.assertEqual(self.client.post(f"/api/products/{product['id']}/movements",
                         json={"kind": "ADJUST", "quantity": -1}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
