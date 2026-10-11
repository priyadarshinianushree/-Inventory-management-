"""Business rules for stock movements.

Stock quantities change ONLY when a transaction is completed.
Workflow:  PENDING -> COMPLETED (approved) | REJECTED (by manager) | CANCELLED (by requester)
"""
from utils import ApiError, Validator

TYPES = ("IN", "OUT", "TRANSFER", "ADJUSTMENT")
PREFIX = {"IN": "GRN", "OUT": "ISS", "TRANSFER": "TRF", "ADJUSTMENT": "ADJ"}


# ---------------------------------------------------------------- stock helpers
def available(db, product_id, warehouse_id):
    row = db.execute("SELECT quantity FROM stock WHERE product_id=? AND warehouse_id=?",
                     (product_id, warehouse_id)).fetchone()
    return row["quantity"] if row else 0


def _change_stock(db, product_id, warehouse_id, delta):
    wh = db.execute("SELECT name, capacity FROM warehouses WHERE id=?", (warehouse_id,)).fetchone()
    prod = db.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()
    current = available(db, product_id, warehouse_id)
    new_qty = current + delta
    if new_qty < 0:
        raise ApiError(f"Insufficient stock: only {current} unit(s) of '{prod['name']}' "
                       f"available in {wh['name']}.", 409, {"quantity": f"Only {current} available"})
    if delta > 0:
        used = db.execute("SELECT COALESCE(SUM(quantity),0) FROM stock WHERE warehouse_id=?",
                          (warehouse_id,)).fetchone()[0]
        if used + delta > wh["capacity"]:
            raise ApiError(f"{wh['name']} capacity exceeded: {used}/{wh['capacity']} units used, "
                           f"cannot add {delta} more.", 409, {"quantity": "Warehouse capacity exceeded"})
    db.execute(
        "INSERT INTO stock(product_id, warehouse_id, quantity) VALUES (?,?,?) "
        "ON CONFLICT(product_id, warehouse_id) DO UPDATE SET quantity = excluded.quantity",
        (product_id, warehouse_id, new_qty))


def _apply_movement(db, tx):
    t, q = tx["type"], tx["quantity"]
    pid, wid = tx["product_id"], tx["warehouse_id"]
    if t == "IN":
        _change_stock(db, pid, wid, q)
    elif t == "OUT":
        _change_stock(db, pid, wid, -q)
    elif t == "TRANSFER":
        _change_stock(db, pid, wid, -q)
        _change_stock(db, pid, tx["to_warehouse_id"], q)
    elif t == "ADJUSTMENT":
        _change_stock(db, pid, wid, q)


def _needs_stock_check(d):
    return d["type"] in ("OUT", "TRANSFER") or (d["type"] == "ADJUSTMENT" and d["quantity"] < 0)


def check_enough_stock(db, d):
    """Early (soft) check when a request is created, re-checked again on approval."""
    if not _needs_stock_check(d):
        return
    need = abs(d["quantity"])
    have = available(db, d["product_id"], d["warehouse_id"])
    if have < need:
        name = db.execute("SELECT name FROM products WHERE id=?", (d["product_id"],)).fetchone()["name"]
        wh = db.execute("SELECT name FROM warehouses WHERE id=?", (d["warehouse_id"],)).fetchone()["name"]
        raise ApiError(f"Insufficient stock: only {have} unit(s) of '{name}' available in {wh}.",
                       409, {"quantity": f"Only {have} available"})


# ---------------------------------------------------------------- validation
def parse_transaction(db, data):
    v = Validator(data)
    t = v.choice("type", TYPES, "Type", required=True)
    pid = v.integer("product_id", "Product", required=True, minimum=1)
    wid = v.integer("warehouse_id", "Warehouse", required=True, minimum=1)
    to_id = v.integer("to_warehouse_id", "Destination warehouse", minimum=1)
    qty = v.integer("quantity", "Quantity", required=True, nonzero=True, minimum=-1_000_000, maximum=1_000_000)
    price = v.number("unit_price", "Unit price", minimum=0)
    note = v.text("note", "Note", max_len=300)

    if t and qty is not None and t != "ADJUSTMENT" and qty < 0:
        v.fail("quantity", "Quantity must be greater than zero")
    if t == "TRANSFER":
        if to_id is None:
            v.fail("to_warehouse_id", "Destination warehouse is required for a transfer")
        elif to_id == wid:
            v.fail("to_warehouse_id", "Destination must be different from the source warehouse")
    else:
        to_id = None
    if t == "ADJUSTMENT" and not note:
        v.fail("note", "A reason is required for stock adjustments")
    v.check()

    product = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not product:
        raise ApiError("Product not found.", 422, {"product_id": "Product not found"})
    if not product["is_active"]:
        raise ApiError("This product is inactive.", 422, {"product_id": "Product is inactive"})
    for field, wh_id in (("warehouse_id", wid), ("to_warehouse_id", to_id)):
        if wh_id is None:
            continue
        wh = db.execute("SELECT is_active FROM warehouses WHERE id=?", (wh_id,)).fetchone()
        if not wh:
            raise ApiError("Warehouse not found.", 422, {field: "Warehouse not found"})
        if not wh["is_active"]:
            raise ApiError("Warehouse is inactive.", 422, {field: "Warehouse is inactive"})

    if price is None:  # default: buying -> cost price, selling -> selling price
        price = product["sell_price"] if t == "OUT" else product["cost_price"]
    return {"type": t, "product_id": pid, "warehouse_id": wid, "to_warehouse_id": to_id,
            "quantity": qty, "unit_price": price, "note": note}


# ---------------------------------------------------------------- workflow
def create_transaction(db, d, user_id, complete=False, created_at=None):
    check_enough_stock(db, d)
    cur = db.execute(
        "INSERT INTO transactions(type, product_id, warehouse_id, to_warehouse_id, quantity, unit_price, "
        "note, status, created_by, created_at) VALUES (?,?,?,?,?,?,?,'PENDING',?,COALESCE(?, datetime('now')))",
        (d["type"], d["product_id"], d["warehouse_id"], d["to_warehouse_id"], d["quantity"],
         d["unit_price"], d["note"], user_id, created_at))
    tx_id = cur.lastrowid
    db.execute("UPDATE transactions SET ref_no=? WHERE id=?", (f"{PREFIX[d['type']]}-{tx_id:05d}", tx_id))
    if complete:
        complete_transaction(db, tx_id, user_id, when=created_at)
    return tx_id


def complete_transaction(db, tx_id, reviewer_id, note=None, when=None):
    tx = db.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx:
        raise ApiError("Transaction not found.", 404)
    if tx["status"] != "PENDING":
        raise ApiError(f"Only pending transactions can be approved (this one is {tx['status']}).", 409)
    _apply_movement(db, tx)
    db.execute("UPDATE transactions SET status='COMPLETED', reviewed_by=?, "
               "reviewed_at=COALESCE(?, datetime('now')), review_note=? WHERE id=?",
               (reviewer_id, when, note, tx_id))


def close_transaction(db, tx_id, reviewer_id, status, note=None):
    """Move a pending transaction to REJECTED or CANCELLED (no stock change)."""
    tx = db.execute("SELECT status FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx:
        raise ApiError("Transaction not found.", 404)
    if tx["status"] != "PENDING":
        raise ApiError(f"Only pending transactions can be {status.lower()} (this one is {tx['status']}).", 409)
    db.execute("UPDATE transactions SET status=?, reviewed_by=?, reviewed_at=datetime('now'), review_note=? "
               "WHERE id=?", (status, reviewer_id, note, tx_id))
