"""Stock levels and inventory transactions (with the approval workflow)."""
from flask import Blueprint, g, jsonify, request

import inventory_service as svc
from auth import login_required
from db import get_db
from utils import ROLES_MANAGER_UP, ApiError, Validator, like, paged

bp = Blueprint("stock_tx", __name__)

# ============================================================ stock levels
STOCK_BASE = """
SELECT (s.product_id * 100000 + s.warehouse_id) AS id, s.product_id, s.warehouse_id, s.quantity,
       p.sku, p.name AS product_name, p.unit, p.reorder_level, p.cost_price, p.category_id,
       c.name AS category_name, w.name AS warehouse_name, w.code AS warehouse_code,
       (s.quantity * p.cost_price) AS value,
       (SELECT SUM(quantity) FROM stock x WHERE x.product_id = s.product_id) AS product_total
FROM stock s
JOIN products p ON p.id = s.product_id
JOIN categories c ON c.id = p.category_id
JOIN warehouses w ON w.id = s.warehouse_id
"""
STOCK_SORTS = {"product": "product_name COLLATE NOCASE", "sku": "sku", "warehouse": "warehouse_name COLLATE NOCASE",
               "quantity": "quantity", "value": "value", "category": "category_name COLLATE NOCASE"}


@bp.get("/stock")
@login_required()
def list_stock():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(product_name LIKE ? OR sku LIKE ?)")
        params += [like(a["q"])] * 2
    for arg, col in (("warehouse_id", "warehouse_id"), ("category_id", "category_id"), ("product_id", "product_id")):
        if a.get(arg):
            where.append(f"{col} = ?")
            params.append(a[arg])
    if a.get("stock_status") == "low":
        where.append("product_total > 0 AND product_total <= reorder_level")
    elif a.get("stock_status") == "out":
        where.append("quantity = 0")
    elif a.get("stock_status") == "in":
        where.append("quantity > 0")
    result = paged(get_db(), STOCK_BASE, where, params, STOCK_SORTS, "product", a)
    for r in result["items"]:
        r["stock_status"] = ("out" if r["quantity"] == 0 else "low" if r["product_total"] <= r["reorder_level"] else "in")
    return jsonify(result)


# ============================================================ transactions
TX_BASE = """
SELECT t.id, t.ref_no, t.type, t.product_id, t.warehouse_id, t.to_warehouse_id, t.quantity, t.unit_price,
       (ABS(t.quantity) * t.unit_price) AS value, t.status, t.note, t.created_by, t.created_at,
       t.reviewed_by, t.reviewed_at, t.review_note,
       p.sku, p.name AS product_name, p.unit, w.name AS warehouse_name, w2.name AS to_warehouse_name,
       u.full_name AS created_by_name, r.full_name AS reviewed_by_name
FROM transactions t
JOIN products p ON p.id = t.product_id
JOIN warehouses w ON w.id = t.warehouse_id
LEFT JOIN warehouses w2 ON w2.id = t.to_warehouse_id
JOIN users u ON u.id = t.created_by
LEFT JOIN users r ON r.id = t.reviewed_by
"""
TX_SORTS = {"created": "created_at", "ref": "ref_no", "type": "type", "product": "product_name COLLATE NOCASE",
            "quantity": "ABS(quantity)", "value": "value", "status": "status", "warehouse": "warehouse_name COLLATE NOCASE"}


def _tx(db, tx_id):
    row = db.execute(f"SELECT * FROM ({TX_BASE}) WHERE id = ?", (tx_id,)).fetchone()
    if not row:
        raise ApiError("Transaction not found.", 404)
    return dict(row)


def _is_manager():
    return g.user["role"] in ROLES_MANAGER_UP


def _require_owner_or_manager(tx):
    if not (_is_manager() or tx["created_by"] == g.user["id"]):
        raise ApiError("You can only change your own requests.", 403)


@bp.get("/transactions")
@login_required()
def list_transactions():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(ref_no LIKE ? OR product_name LIKE ? OR sku LIKE ? OR note LIKE ?)")
        params += [like(a["q"])] * 4
    if a.get("type") in svc.TYPES:
        where.append("type = ?")
        params.append(a["type"])
    if a.get("status") in ("PENDING", "COMPLETED", "REJECTED", "CANCELLED"):
        where.append("status = ?")
        params.append(a["status"])
    if a.get("warehouse_id"):
        where.append("(warehouse_id = ? OR to_warehouse_id = ?)")
        params += [a["warehouse_id"]] * 2
    if a.get("product_id"):
        where.append("product_id = ?")
        params.append(a["product_id"])
    if a.get("date_from"):
        where.append("date(created_at) >= date(?)")
        params.append(a["date_from"])
    if a.get("date_to"):
        where.append("date(created_at) <= date(?)")
        params.append(a["date_to"])
    return jsonify(paged(get_db(), TX_BASE, where, params, TX_SORTS, "created", a, default_order="desc"))


@bp.get("/transactions/<int:tx_id>")
@login_required()
def get_transaction(tx_id):
    return jsonify(_tx(get_db(), tx_id))


@bp.post("/transactions")
@login_required()
def create_transaction():
    db = get_db()
    body = request.get_json(silent=True) or {}
    data = svc.parse_transaction(db, body)
    # managers/admins may post immediately; staff requests wait for approval
    post_now = _is_manager() and Validator(body).boolean("auto_approve", False)
    tx_id = svc.create_transaction(db, data, g.user["id"], complete=post_now)
    db.commit()
    return jsonify(_tx(db, tx_id)), 201


@bp.put("/transactions/<int:tx_id>")
@login_required()
def update_transaction(tx_id):
    db = get_db()
    tx = _tx(db, tx_id)
    _require_owner_or_manager(tx)
    if tx["status"] != "PENDING":
        raise ApiError("Only pending transactions can be edited.", 409)
    d = svc.parse_transaction(db, request.get_json(silent=True))
    svc.check_enough_stock(db, d)
    db.execute("UPDATE transactions SET type=:type, product_id=:product_id, warehouse_id=:warehouse_id, "
               "to_warehouse_id=:to_warehouse_id, quantity=:quantity, unit_price=:unit_price, note=:note, "
               "ref_no=:ref WHERE id=:id",
               {**d, "id": tx_id, "ref": f"{svc.PREFIX[d['type']]}-{tx_id:05d}"})
    db.commit()
    return jsonify(_tx(db, tx_id))


@bp.delete("/transactions/<int:tx_id>")
@login_required()
def delete_transaction(tx_id):
    db = get_db()
    tx = _tx(db, tx_id)
    _require_owner_or_manager(tx)
    if tx["status"] == "COMPLETED":
        raise ApiError("Completed transactions are part of the audit trail and cannot be deleted. "
                       "Create an adjustment to correct stock.", 409)
    if tx["status"] != "PENDING" and not _is_manager():
        raise ApiError("Only a manager can delete closed requests.", 403)
    db.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
    db.commit()
    return jsonify(message="Transaction deleted.")


@bp.post("/transactions/<int:tx_id>/approve")
@login_required(*ROLES_MANAGER_UP)
def approve_transaction(tx_id):
    db = get_db()
    _tx(db, tx_id)
    note = Validator(request.get_json(silent=True)).text("note", "Note", max_len=300)
    svc.complete_transaction(db, tx_id, g.user["id"], note)
    db.commit()
    return jsonify(_tx(db, tx_id))


@bp.post("/transactions/<int:tx_id>/reject")
@login_required(*ROLES_MANAGER_UP)
def reject_transaction(tx_id):
    db = get_db()
    _tx(db, tx_id)
    v = Validator(request.get_json(silent=True))
    note = v.text("note", "Reason", required=True, max_len=300)
    v.check()
    svc.close_transaction(db, tx_id, g.user["id"], "REJECTED", note)
    db.commit()
    return jsonify(_tx(db, tx_id))


@bp.post("/transactions/<int:tx_id>/cancel")
@login_required()
def cancel_transaction(tx_id):
    db = get_db()
    tx = _tx(db, tx_id)
    _require_owner_or_manager(tx)
    svc.close_transaction(db, tx_id, g.user["id"], "CANCELLED", "Cancelled by " + g.user["full_name"])
    db.commit()
    return jsonify(_tx(db, tx_id))
