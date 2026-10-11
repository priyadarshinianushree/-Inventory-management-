"""API tests (standard library only).   Run:  python -m unittest discover -s tests -v

Each run builds a throw-away database, so your real data is never touched.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tmp = tempfile.mkdtemp()
os.environ["INVENTORY_DB"] = os.path.join(_tmp, "test.db")
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402


class InventoryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()
        cls.h = {u: cls._login(u, f"{u}123") for u in ("admin", "manager", "staff")}

    @classmethod
    def _login(cls, user, pwd):
        res = cls.client.post("/api/auth/login", json={"username": user, "password": pwd})
        return {"Authorization": "Bearer " + res.json["token"]}

    def call(self, method, url, who="manager", **kw):
        headers = self.h[who] if who else {}
        return getattr(self.client, method)(url, headers=headers, **kw)

    def new_product(self, sku="TST-001"):
        r = self.call("post", "/api/products", json={
            "sku": sku, "name": "Test Item", "category_id": 1, "unit": "pcs",
            "cost_price": 10, "sell_price": 15, "reorder_level": 5})
        self.assertEqual(r.status_code, 201, r.json)
        return r.json["id"]

    # ---------------------------------------------------------------- auth
    def test_login_and_protection(self):
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "admin", "password": "x"}).status_code, 401)
        self.assertEqual(self.client.get("/api/products").status_code, 401)
        self.assertEqual(self.call("get", "/api/auth/me").json["user"]["role"], "manager")

    def test_roles(self):
        self.assertEqual(self.call("get", "/api/users", "staff").status_code, 403)
        self.assertEqual(self.call("get", "/api/users", "admin").status_code, 200)
        self.assertEqual(self.call("post", "/api/products", "staff", json={}).status_code, 403)

    # ---------------------------------------------------------------- data + search/filter/sort
    def test_seed_data_is_meaningful(self):
        cats = self.call("get", "/api/categories?per_page=50").json["items"]
        self.assertEqual(len(cats), 8)
        self.assertTrue(all(c["product_count"] >= 6 for c in cats))

    def test_search_filter_sort_pagination(self):
        r = self.call("get", "/api/products?q=philips").json
        self.assertEqual(r["total"], 1)
        low = self.call("get", "/api/products?stock_status=low&per_page=50").json["items"]
        self.assertTrue(low and all(0 < p["total_qty"] <= p["reorder_level"] for p in low))
        out = self.call("get", "/api/products?stock_status=out&per_page=50").json["items"]
        self.assertTrue(out and all(p["total_qty"] == 0 for p in out))
        asc = self.call("get", "/api/products?sort=price&order=asc&per_page=5").json["items"]
        self.assertEqual([p["sell_price"] for p in asc], sorted(p["sell_price"] for p in asc))
        page2 = self.call("get", "/api/products?per_page=10&page=2").json
        self.assertEqual((page2["page"], len(page2["items"])), (2, 10))

    # ---------------------------------------------------------------- validation
    def test_product_validation(self):
        r = self.call("post", "/api/products", json={"sku": "x", "name": "a", "cost_price": 10, "sell_price": 5})
        self.assertEqual(r.status_code, 422)
        self.assertIn("sku", r.json["details"])
        self.assertIn("category_id", r.json["details"])
        pid = self.new_product("TST-DUP")
        dup = self.call("post", "/api/products", json={
            "sku": "tst-dup", "name": "Other", "category_id": 1, "unit": "pcs",
            "cost_price": 1, "sell_price": 2, "reorder_level": 1})
        self.assertEqual(dup.status_code, 409)
        bad_price = self.call("put", f"/api/products/{pid}", json={
            "sku": "TST-DUP", "name": "Test", "category_id": 1, "unit": "pcs",
            "cost_price": 50, "sell_price": 10, "reorder_level": 1})
        self.assertEqual(bad_price.status_code, 422)

    # ---------------------------------------------------------------- workflow
    def test_approval_workflow_and_stock_rules(self):
        pid = self.new_product("TST-WF")
        tx = self.call("post", "/api/transactions", "staff", json={"type": "IN", "product_id": pid, "warehouse_id": 1, "quantity": 20})
        self.assertEqual((tx.status_code, tx.json["status"]), (201, "PENDING"))
        tid = tx.json["id"]
        stock = lambda: self.call("get", f"/api/products/{pid}").json["total_qty"]  # noqa: E731
        self.assertEqual(stock(), 0)                                    # nothing changes while pending
        self.assertEqual(self.call("post", f"/api/transactions/{tid}/approve", "staff").status_code, 403)
        self.assertEqual(self.call("post", f"/api/transactions/{tid}/approve").json["status"], "COMPLETED")
        self.assertEqual(stock(), 20)
        self.assertEqual(self.call("post", f"/api/transactions/{tid}/approve").status_code, 409)   # not twice
        self.assertEqual(self.call("delete", f"/api/transactions/{tid}").status_code, 409)         # audit trail
        # cannot sell more than we have
        too_many = self.call("post", "/api/transactions", "staff", json={"type": "OUT", "product_id": pid, "warehouse_id": 1, "quantity": 21})
        self.assertEqual(too_many.status_code, 409)
        # transfer moves stock between warehouses
        self.call("post", "/api/transactions", json={"type": "TRANSFER", "product_id": pid, "warehouse_id": 1, "to_warehouse_id": 2, "quantity": 5, "auto_approve": True})
        per_wh = {s["warehouse_id"]: s["quantity"] for s in self.call("get", f"/api/products/{pid}").json["stock"]}
        self.assertEqual((per_wh[1], per_wh[2]), (15, 5))
        # reject needs a reason; cancel works for the owner
        t2 = self.call("post", "/api/transactions", "staff", json={"type": "OUT", "product_id": pid, "warehouse_id": 1, "quantity": 3}).json["id"]
        self.assertEqual(self.call("post", f"/api/transactions/{t2}/reject", json={}).status_code, 422)
        self.assertEqual(self.call("post", f"/api/transactions/{t2}/cancel", "staff").json["status"], "CANCELLED")
        # product with history cannot be deleted
        self.assertEqual(self.call("delete", f"/api/products/{pid}").status_code, 409)

    def test_adjustment_needs_reason_and_transfer_needs_other_warehouse(self):
        pid = self.new_product("TST-ADJ")
        r = self.call("post", "/api/transactions", json={"type": "ADJUSTMENT", "product_id": pid, "warehouse_id": 1, "quantity": -1})
        self.assertIn("note", r.json["details"])
        r = self.call("post", "/api/transactions", json={"type": "TRANSFER", "product_id": pid, "warehouse_id": 1, "to_warehouse_id": 1, "quantity": 1})
        self.assertIn("to_warehouse_id", r.json["details"])

    # ---------------------------------------------------------------- integrity + dashboard
    def test_delete_protection(self):
        self.assertEqual(self.call("delete", "/api/categories/1").status_code, 409)
        self.assertEqual(self.call("delete", "/api/warehouses/1").status_code, 409)
        self.assertEqual(self.call("put", "/api/users/1", "admin", json={"full_name": "x", "role": "staff"}).status_code, 409)

    def test_stock_matches_transaction_history(self):
        """Every product's stock must equal the sum of its completed movements."""
        import sqlite3
        db = sqlite3.connect(os.environ["INVENTORY_DB"])
        rows = db.execute("""
            SELECT p.sku, COALESCE((SELECT SUM(quantity) FROM stock WHERE product_id=p.id),0) AS stock,
                   COALESCE((SELECT SUM(CASE type WHEN 'IN' THEN quantity WHEN 'OUT' THEN -quantity
                                                  WHEN 'ADJUSTMENT' THEN quantity ELSE 0 END)
                             FROM transactions WHERE product_id=p.id AND status='COMPLETED'),0) AS moved
            FROM products p WHERE p.sku NOT LIKE 'TST-%'""").fetchall()
        self.assertEqual(len(rows), 48)
        self.assertTrue(all(stock == moved for _, stock, moved in rows))

    def test_dashboard(self):
        d = self.call("get", "/api/dashboard", "staff").json
        self.assertEqual(len(d["trend"]), 14)
        self.assertGreater(d["totals"]["low_stock"], 0)
        self.assertGreater(d["totals"]["pending"], 0)


if __name__ == "__main__":
    unittest.main()
