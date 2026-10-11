from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from auth import login_required, make_token, public_user
from db import get_db
from utils import ApiError, Validator

bp = Blueprint("auth", __name__)


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    errors = {}
    if not username:
        errors["username"] = "Username is required"
    if not password:
        errors["password"] = "Password is required"
    if errors:
        raise ApiError("Enter your username and password.", 422, errors)

    user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        raise ApiError("Invalid username or password.", 401)
    if not user["is_active"]:
        raise ApiError("Your account is disabled. Please contact the administrator.", 403)
    return jsonify(token=make_token(user["id"]), user=public_user(user))


@bp.get("/auth/me")
@login_required()
def me():
    return jsonify(user=g.user)


@bp.post("/auth/change-password")
@login_required()
def change_password():
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id=?", (g.user["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], str(data.get("current_password") or "")):
        raise ApiError("Current password is incorrect.", 422, {"current_password": "Current password is incorrect"})
    v = Validator(data)
    new = v.text("new_password", "New password", required=True, min_len=6, max_len=64)
    v.check()
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), g.user["id"]))
    db.commit()
    return jsonify(message="Password changed successfully.")
