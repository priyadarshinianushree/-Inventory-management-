"""Master data: categories, suppliers, warehouses (view: everyone, change: manager/admin)."""
from flask import Blueprint, jsonify, request

from auth import login_required
from db import get_db
from utils import ROLES_MANAGER_UP, ApiError, Validator, like, paged

bp = Blueprint("masters", __name__)


def _one(db, sql, key, what):
    row = db.execute(sql, (key,)).fetchone()
    if not row:
        raise ApiError(f"{what} not found.", 404)
    return dict(row)


# ============================================================ categories
CAT_BASE = ("SELECT c.*, (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) AS product_count "
            "FROM categories c")


@bp.get("/categories")
@login_required()
def list_categories():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(name LIKE ? OR description LIKE ?)")
        params += [like(a["q"])] * 2
    sort_map = {"name": "name COLLATE NOCASE", "products": "product_count", "created": "created_at"}
    return jsonify(paged(get_db(), CAT_BASE, where, params, sort_map, "name", a))


def _category_payload(db, cat_id=None):
    v = Validator(request.get_json(silent=True))
    name = v.text("name", "Name", required=True, max_len=60)
    desc = v.text("description", "Description", max_len=200)
    v.check()
    dup = db.execute("SELECT id FROM categories WHERE name = ? AND id IS NOT ?", (name, cat_id)).fetchone()
    if dup:
        raise ApiError("A category with this name already exists.", 409, {"name": "Category name already exists"})
    return name, desc


@bp.post("/categories")
@login_required(*ROLES_MANAGER_UP)
def create_category():
    db = get_db()
    name, desc = _category_payload(db)
    cur = db.execute("INSERT INTO categories(name, description) VALUES (?,?)", (name, desc))
    db.commit()
    return jsonify(_one(db, CAT_BASE + " WHERE c.id=?", cur.lastrowid, "Category")), 201


@bp.put("/categories/<int:cat_id>")
@login_required(*ROLES_MANAGER_UP)
def update_category(cat_id):
    db = get_db()
    _one(db, CAT_BASE + " WHERE c.id=?", cat_id, "Category")
    name, desc = _category_payload(db, cat_id)
    db.execute("UPDATE categories SET name=?, description=? WHERE id=?", (name, desc, cat_id))
    db.commit()
    return jsonify(_one(db, CAT_BASE + " WHERE c.id=?", cat_id, "Category"))


@bp.delete("/categories/<int:cat_id>")
@login_required(*ROLES_MANAGER_UP)
def delete_category(cat_id):
    db = get_db()
    row = _one(db, CAT_BASE + " WHERE c.id=?", cat_id, "Category")
    if row["product_count"]:
        raise ApiError(f"Cannot delete: {row['product_count']} product(s) use this category. "
                       "Move or remove them first.", 409)
    db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    db.commit()
    return jsonify(message="Category deleted.")


# ============================================================ suppliers
SUP_BASE = ("SELECT s.*, (SELECT COUNT(*) FROM products p WHERE p.supplier_id = s.id) AS product_count "
            "FROM suppliers s")


@bp.get("/suppliers")
@login_required()
def list_suppliers():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(name LIKE ? OR contact_person LIKE ? OR email LIKE ? OR phone LIKE ?)")
        params += [like(a["q"])] * 4
    if a.get("active") in ("0", "1"):
        where.append("is_active = ?")
        params.append(int(a["active"]))
    sort_map = {"name": "name COLLATE NOCASE", "products": "product_count", "created": "created_at"}
    return jsonify(paged(get_db(), SUP_BASE, where, params, sort_map, "name", a))


def _supplier_payload(db, sup_id=None):
    v = Validator(request.get_json(silent=True))
    d = {
        "name": v.text("name", "Supplier name", required=True, max_len=100),
        "contact_person": v.text("contact_person", "Contact person", max_len=80),
        "phone": v.text("phone", "Phone", max_len=15, pattern=r"[0-9+\-\s()]{7,15}",
                        msg="Phone must have 7-15 digits (numbers, +, -, spaces)"),
        "email": v.email("email", "Email"),
        "address": v.text("address", "Address", max_len=200),
        "is_active": int(v.boolean("is_active", True)),
    }
    v.check()
    if db.execute("SELECT 1 FROM suppliers WHERE name=? AND id IS NOT ?", (d["name"], sup_id)).fetchone():
        raise ApiError("A supplier with this name already exists.", 409, {"name": "Supplier name already exists"})
    return d


@bp.post("/suppliers")
@login_required(*ROLES_MANAGER_UP)
def create_supplier():
    db = get_db()
    d = _supplier_payload(db)
    cur = db.execute("INSERT INTO suppliers(name, contact_person, phone, email, address, is_active) "
                     "VALUES (:name,:contact_person,:phone,:email,:address,:is_active)", d)
    db.commit()
    return jsonify(_one(db, SUP_BASE + " WHERE s.id=?", cur.lastrowid, "Supplier")), 201


@bp.put("/suppliers/<int:sup_id>")
@login_required(*ROLES_MANAGER_UP)
def update_supplier(sup_id):
    db = get_db()
    _one(db, SUP_BASE + " WHERE s.id=?", sup_id, "Supplier")
    d = _supplier_payload(db, sup_id)
    d["id"] = sup_id
    db.execute("UPDATE suppliers SET name=:name, contact_person=:contact_person, phone=:phone, email=:email, "
               "address=:address, is_active=:is_active WHERE id=:id", d)
    db.commit()
    return jsonify(_one(db, SUP_BASE + " WHERE s.id=?", sup_id, "Supplier"))


@bp.delete("/suppliers/<int:sup_id>")
@login_required(*ROLES_MANAGER_UP)
def delete_supplier(sup_id):
    db = get_db()
    row = _one(db, SUP_BASE + " WHERE s.id=?", sup_id, "Supplier")
    if row["product_count"]:
        raise ApiError(f"Cannot delete: {row['product_count']} product(s) are supplied by this supplier. "
                       "Mark the supplier inactive instead.", 409)
    db.execute("DELETE FROM suppliers WHERE id=?", (sup_id,))
    db.commit()
    return jsonify(message="Supplier deleted.")


# ============================================================ warehouses
WH_BASE = """SELECT w.*,
    COALESCE((SELECT SUM(quantity) FROM stock s WHERE s.warehouse_id = w.id), 0) AS used,
    (SELECT COUNT(*) FROM stock s WHERE s.warehouse_id = w.id AND s.quantity > 0) AS product_count
    FROM warehouses w"""


@bp.get("/warehouses")
@login_required()
def list_warehouses():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(name LIKE ? OR code LIKE ? OR location LIKE ?)")
        params += [like(a["q"])] * 3
    if a.get("active") in ("0", "1"):
        where.append("is_active = ?")
        params.append(int(a["active"]))
    sort_map = {"name": "name COLLATE NOCASE", "code": "code", "capacity": "capacity",
                "used": "used", "created": "created_at"}
    return jsonify(paged(get_db(), WH_BASE, where, params, sort_map, "name", a))


def _warehouse_payload(db, wh_id=None):
    v = Validator(request.get_json(silent=True))
    d = {
        "code": v.text("code", "Code", required=True, max_len=10, upper=True, pattern=r"[A-Z0-9\-]{2,10}",
                       msg="Code must be 2-10 characters: letters, numbers or -"),
        "name": v.text("name", "Name", required=True, max_len=80),
        "location": v.text("location", "Location", required=True, max_len=150),
        "capacity": v.integer("capacity", "Capacity", required=True, minimum=1, maximum=10_000_000),
        "is_active": int(v.boolean("is_active", True)),
    }
    v.check()
    if db.execute("SELECT 1 FROM warehouses WHERE code=? AND id IS NOT ?", (d["code"], wh_id)).fetchone():
        raise ApiError("Warehouse code already exists.", 409, {"code": "Code already exists"})
    if db.execute("SELECT 1 FROM warehouses WHERE name=? AND id IS NOT ?", (d["name"], wh_id)).fetchone():
        raise ApiError("Warehouse name already exists.", 409, {"name": "Name already exists"})
    return d


@bp.post("/warehouses")
@login_required(*ROLES_MANAGER_UP)
def create_warehouse():
    db = get_db()
    d = _warehouse_payload(db)
    cur = db.execute("INSERT INTO warehouses(code, name, location, capacity, is_active) "
                     "VALUES (:code,:name,:location,:capacity,:is_active)", d)
    db.commit()
    return jsonify(_one(db, WH_BASE + " WHERE w.id=?", cur.lastrowid, "Warehouse")), 201


@bp.put("/warehouses/<int:wh_id>")
@login_required(*ROLES_MANAGER_UP)
def update_warehouse(wh_id):
    db = get_db()
    current = _one(db, WH_BASE + " WHERE w.id=?", wh_id, "Warehouse")
    d = _warehouse_payload(db, wh_id)
    if d["capacity"] < current["used"]:
        raise ApiError(f"Capacity cannot be lower than the {current['used']} units currently stored.", 422,
                       {"capacity": f"Must be at least {current['used']} (current stock)"})
    d["id"] = wh_id
    db.execute("UPDATE warehouses SET code=:code, name=:name, location=:location, capacity=:capacity, "
               "is_active=:is_active WHERE id=:id", d)
    db.commit()
    return jsonify(_one(db, WH_BASE + " WHERE w.id=?", wh_id, "Warehouse"))


@bp.delete("/warehouses/<int:wh_id>")
@login_required(*ROLES_MANAGER_UP)
def delete_warehouse(wh_id):
    db = get_db()
    row = _one(db, WH_BASE + " WHERE w.id=?", wh_id, "Warehouse")
    if row["used"]:
        raise ApiError(f"Cannot delete: {row['used']} unit(s) are still stored here. Transfer them out first.", 409)
    history = db.execute("SELECT COUNT(*) FROM transactions WHERE warehouse_id=? OR to_warehouse_id=?",
                         (wh_id, wh_id)).fetchone()[0]
    if history:
        raise ApiError("This warehouse has transaction history and cannot be deleted. "
                       "Mark it inactive instead.", 409)
    db.execute("DELETE FROM stock WHERE warehouse_id=?", (wh_id,))
    db.execute("DELETE FROM warehouses WHERE id=?", (wh_id,))
    db.commit()
    return jsonify(message="Warehouse deleted.")
