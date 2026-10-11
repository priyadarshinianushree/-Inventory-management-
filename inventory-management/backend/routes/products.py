"""Products: CRUD + search / filter / sort / pagination."""
from flask import Blueprint, jsonify, request

from auth import login_required
from db import get_db
from utils import ROLES_MANAGER_UP, ApiError, Validator, like, paged

bp = Blueprint("products", __name__)

BASE = """
SELECT t.*, CASE WHEN total_qty = 0 THEN 'out' WHEN total_qty <= reorder_level THEN 'low' ELSE 'in' END AS stock_status
FROM (
    SELECT p.id, p.sku, p.name, p.category_id, p.supplier_id, p.unit, p.cost_price, p.sell_price,
           p.reorder_level, p.description, p.is_active, p.created_at, p.updated_at,
           c.name AS category_name, s.name AS supplier_name,
           COALESCE((SELECT SUM(quantity) FROM stock st WHERE st.product_id = p.id), 0) AS total_qty
    FROM products p
    JOIN categories c ON c.id = p.category_id
    LEFT JOIN suppliers s ON s.id = p.supplier_id
) t
"""

SORTS = {"name": "name COLLATE NOCASE", "sku": "sku", "category": "category_name COLLATE NOCASE",
         "price": "sell_price", "cost": "cost_price", "stock": "total_qty", "created": "created_at"}


def _product(db, product_id):
    row = db.execute(f"SELECT * FROM ({BASE}) WHERE id = ?", (product_id,)).fetchone()
    if not row:
        raise ApiError("Product not found.", 404)
    return dict(row)


@bp.get("/products")
@login_required()
def list_products():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(name LIKE ? OR sku LIKE ? OR category_name LIKE ?)")
        params += [like(a["q"])] * 3
    if a.get("category_id"):
        where.append("category_id = ?")
        params.append(a["category_id"])
    if a.get("supplier_id"):
        where.append("supplier_id = ?")
        params.append(a["supplier_id"])
    if a.get("stock_status") in ("in", "low", "out"):
        where.append("stock_status = ?")
        params.append(a["stock_status"])
    if a.get("active") in ("0", "1"):
        where.append("is_active = ?")
        params.append(int(a["active"]))
    return jsonify(paged(get_db(), BASE, where, params, SORTS, "name", a))


@bp.get("/products/<int:product_id>")
@login_required()
def product_detail(product_id):
    db = get_db()
    product = _product(db, product_id)
    product["stock"] = [dict(r) for r in db.execute(
        "SELECT w.id AS warehouse_id, w.name AS warehouse_name, w.code, s.quantity FROM stock s "
        "JOIN warehouses w ON w.id = s.warehouse_id WHERE s.product_id = ? ORDER BY s.quantity DESC", (product_id,))]
    product["recent_transactions"] = [dict(r) for r in db.execute(
        "SELECT t.id, t.ref_no, t.type, t.quantity, t.status, t.created_at, w.name AS warehouse_name "
        "FROM transactions t JOIN warehouses w ON w.id = t.warehouse_id WHERE t.product_id = ? "
        "ORDER BY t.created_at DESC, t.id DESC LIMIT 8", (product_id,))]
    return jsonify(product)


def _payload(db, product_id=None):
    v = Validator(request.get_json(silent=True))
    d = {
        "sku": v.text("sku", "SKU", required=True, max_len=30, upper=True, pattern=r"[A-Z0-9\-_]{3,30}",
                      msg="SKU must be 3-30 characters: letters, numbers, - or _"),
        "name": v.text("name", "Product name", required=True, max_len=120, min_len=2),
        "category_id": v.integer("category_id", "Category", required=True, minimum=1),
        "supplier_id": v.integer("supplier_id", "Supplier", minimum=1),
        "unit": v.text("unit", "Unit", required=True, max_len=15),
        "cost_price": v.number("cost_price", "Cost price", required=True, minimum=0, maximum=10_000_000),
        "sell_price": v.number("sell_price", "Selling price", required=True, minimum=0, maximum=10_000_000),
        "reorder_level": v.integer("reorder_level", "Reorder level", required=True, minimum=0, maximum=1_000_000),
        "description": v.text("description", "Description", max_len=300),
        "is_active": int(v.boolean("is_active", True)),
    }
    if d["cost_price"] is not None and d["sell_price"] is not None and d["sell_price"] < d["cost_price"]:
        v.fail("sell_price", "Selling price cannot be lower than cost price")
    v.check()
    if not db.execute("SELECT 1 FROM categories WHERE id=?", (d["category_id"],)).fetchone():
        raise ApiError("Category not found.", 422, {"category_id": "Category not found"})
    if d["supplier_id"] and not db.execute("SELECT 1 FROM suppliers WHERE id=?", (d["supplier_id"],)).fetchone():
        raise ApiError("Supplier not found.", 422, {"supplier_id": "Supplier not found"})
    if db.execute("SELECT 1 FROM products WHERE sku=? AND id IS NOT ?", (d["sku"], product_id)).fetchone():
        raise ApiError("This SKU already exists.", 409, {"sku": "SKU already exists"})
    return d


@bp.post("/products")
@login_required(*ROLES_MANAGER_UP)
def create_product():
    db = get_db()
    d = _payload(db)
    cur = db.execute(
        "INSERT INTO products(sku, name, category_id, supplier_id, unit, cost_price, sell_price, reorder_level, "
        "description, is_active) VALUES (:sku,:name,:category_id,:supplier_id,:unit,:cost_price,:sell_price,"
        ":reorder_level,:description,:is_active)", d)
    db.commit()
    return jsonify(_product(db, cur.lastrowid)), 201


@bp.put("/products/<int:product_id>")
@login_required(*ROLES_MANAGER_UP)
def update_product(product_id):
    db = get_db()
    _product(db, product_id)
    d = _payload(db, product_id)
    d["id"] = product_id
    db.execute(
        "UPDATE products SET sku=:sku, name=:name, category_id=:category_id, supplier_id=:supplier_id, unit=:unit, "
        "cost_price=:cost_price, sell_price=:sell_price, reorder_level=:reorder_level, description=:description, "
        "is_active=:is_active, updated_at=datetime('now') WHERE id=:id", d)
    db.commit()
    return jsonify(_product(db, product_id))


@bp.delete("/products/<int:product_id>")
@login_required(*ROLES_MANAGER_UP)
def delete_product(product_id):
    db = get_db()
    _product(db, product_id)
    history = db.execute("SELECT COUNT(*) FROM transactions WHERE product_id=?", (product_id,)).fetchone()[0]
    if history:
        raise ApiError(f"This product has {history} transaction record(s) and cannot be deleted. "
                       "Mark it inactive instead (Edit -> uncheck Active).", 409)
    db.execute("DELETE FROM products WHERE id=?", (product_id,))
    db.commit()
    return jsonify(message="Product deleted.")
