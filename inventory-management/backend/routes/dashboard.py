"""Dashboard / summary numbers."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify

from auth import login_required
from db import get_db

bp = Blueprint("dashboard", __name__)

PRODUCT_TOTALS = """
SELECT p.id, p.sku, p.name, p.unit, p.reorder_level, c.name AS category_name,
       COALESCE(SUM(s.quantity), 0) AS qty
FROM products p
JOIN categories c ON c.id = p.category_id
LEFT JOIN stock s ON s.product_id = p.id
WHERE p.is_active = 1
GROUP BY p.id
"""


@bp.get("/dashboard")
@login_required()
def dashboard():
    db = get_db()
    one = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731

    totals = {
        "products": one("SELECT COUNT(*) FROM products WHERE is_active=1"),
        "categories": one("SELECT COUNT(*) FROM categories"),
        "suppliers": one("SELECT COUNT(*) FROM suppliers WHERE is_active=1"),
        "warehouses": one("SELECT COUNT(*) FROM warehouses WHERE is_active=1"),
        "units": one("SELECT COALESCE(SUM(quantity),0) FROM stock"),
        "stock_value": one("SELECT COALESCE(SUM(s.quantity*p.cost_price),0) FROM stock s JOIN products p ON p.id=s.product_id"),
        "retail_value": one("SELECT COALESCE(SUM(s.quantity*p.sell_price),0) FROM stock s JOIN products p ON p.id=s.product_id"),
        "pending": one("SELECT COUNT(*) FROM transactions WHERE status='PENDING'"),
        "low_stock": one(f"SELECT COUNT(*) FROM ({PRODUCT_TOTALS}) WHERE qty > 0 AND qty <= reorder_level"),
        "out_of_stock": one(f"SELECT COUNT(*) FROM ({PRODUCT_TOTALS}) WHERE qty = 0"),
    }

    low_stock = [dict(r) for r in db.execute(
        f"SELECT * FROM ({PRODUCT_TOTALS}) WHERE qty <= reorder_level "
        "ORDER BY qty * 1.0 / MAX(reorder_level, 1), name LIMIT 8")]

    categories = [dict(r) for r in db.execute(
        "SELECT c.id, c.name, COUNT(DISTINCT p.id) AS products, COALESCE(SUM(s.quantity),0) AS units, "
        "COALESCE(SUM(s.quantity * p.cost_price),0) AS value FROM categories c "
        "LEFT JOIN products p ON p.category_id = c.id LEFT JOIN stock s ON s.product_id = p.id "
        "GROUP BY c.id ORDER BY value DESC")]

    warehouses = [dict(r) for r in db.execute(
        "SELECT w.id, w.code, w.name, w.capacity, COALESCE(SUM(s.quantity),0) AS used FROM warehouses w "
        "LEFT JOIN stock s ON s.warehouse_id = w.id WHERE w.is_active = 1 GROUP BY w.id ORDER BY w.name")]

    today = datetime.now(timezone.utc).date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    trend = {d: {"date": d, "in": 0, "out": 0} for d in days}
    for r in db.execute(
        "SELECT date(COALESCE(reviewed_at, created_at)) AS d, type, SUM(ABS(quantity)) AS q FROM transactions "
        "WHERE status='COMPLETED' AND type IN ('IN','OUT') AND date(COALESCE(reviewed_at, created_at)) >= ? "
        "GROUP BY d, type", (days[0],)):
        if r["d"] in trend:
            trend[r["d"]]["in" if r["type"] == "IN" else "out"] = r["q"]

    recent = [dict(r) for r in db.execute(
        "SELECT t.id, t.ref_no, t.type, t.quantity, t.status, t.created_at, p.name AS product_name, "
        "w.name AS warehouse_name FROM transactions t JOIN products p ON p.id=t.product_id "
        "JOIN warehouses w ON w.id=t.warehouse_id ORDER BY t.created_at DESC, t.id DESC LIMIT 8")]

    return jsonify(totals=totals, low_stock=low_stock, categories=categories, warehouses=warehouses,
                   trend=list(trend.values()), recent=recent)
