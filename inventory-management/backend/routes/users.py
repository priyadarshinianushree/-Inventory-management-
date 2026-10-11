"""User management (admin only)."""
from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from auth import login_required
from db import get_db
from utils import ApiError, Validator, like, paged

bp = Blueprint("users", __name__)

BASE = "SELECT id, username, full_name, role, is_active, created_at FROM users"
ROLES = ("admin", "manager", "staff")


def _get(db, user_id):
    row = db.execute(BASE + " WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise ApiError("User not found.", 404)
    return row


@bp.get("/users")
@login_required("admin")
def list_users():
    a = request.args
    where, params = [], []
    if a.get("q"):
        where.append("(username LIKE ? OR full_name LIKE ?)")
        params += [like(a["q"])] * 2
    if a.get("role"):
        where.append("role = ?")
        params.append(a["role"])
    if a.get("active") in ("0", "1"):
        where.append("is_active = ?")
        params.append(int(a["active"]))
    sort_map = {"name": "full_name COLLATE NOCASE", "username": "username COLLATE NOCASE",
                "role": "role", "created": "created_at"}
    return jsonify(paged(get_db(), BASE, where, params, sort_map, "name", a))


@bp.post("/users")
@login_required("admin")
def create_user():
    db = get_db()
    v = Validator(request.get_json(silent=True))
    username = v.text("username", "Username", required=True, min_len=3, max_len=30,
                      pattern=r"[A-Za-z0-9_.]+", msg="Username may contain letters, numbers, _ and . only")
    full_name = v.text("full_name", "Full name", required=True, max_len=80)
    password = v.text("password", "Password", required=True, min_len=6, max_len=64)
    role = v.choice("role", ROLES, "Role", required=True)
    active = v.boolean("is_active", True)
    v.check()
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise ApiError("Username already taken.", 409, {"username": "Username already taken"})
    cur = db.execute("INSERT INTO users(username, full_name, password_hash, role, is_active) VALUES (?,?,?,?,?)",
                     (username, full_name, generate_password_hash(password), role, int(active)))
    db.commit()
    return jsonify(dict(_get(db, cur.lastrowid))), 201


@bp.put("/users/<int:user_id>")
@login_required("admin")
def update_user(user_id):
    db = get_db()
    _get(db, user_id)
    v = Validator(request.get_json(silent=True))
    full_name = v.text("full_name", "Full name", required=True, max_len=80)
    password = v.text("password", "Password", min_len=6, max_len=64)
    role = v.choice("role", ROLES, "Role", required=True)
    active = v.boolean("is_active", True)
    v.check()
    if user_id == g.user["id"] and (role != "admin" or not active):
        raise ApiError("You cannot remove your own admin access or disable your own account.", 409,
                       {"role": "Not allowed for your own account"})
    db.execute("UPDATE users SET full_name=?, role=?, is_active=? WHERE id=?",
               (full_name, role, int(active), user_id))
    if password:
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), user_id))
    db.commit()
    return jsonify(dict(_get(db, user_id)))


@bp.delete("/users/<int:user_id>")
@login_required("admin")
def delete_user(user_id):
    db = get_db()
    _get(db, user_id)
    if user_id == g.user["id"]:
        raise ApiError("You cannot delete your own account.", 409)
    used = db.execute("SELECT COUNT(*) FROM transactions WHERE created_by=? OR reviewed_by=?",
                      (user_id, user_id)).fetchone()[0]
    if used:
        raise ApiError(f"This user appears in {used} transaction record(s) and cannot be deleted. "
                       "Disable the account instead.", 409)
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    return jsonify(message="User deleted.")
