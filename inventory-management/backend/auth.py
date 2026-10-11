"""Token authentication + role based access control."""
from functools import wraps

from flask import g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config
from db import get_db
from utils import ApiError


def _serializer():
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="inventory-auth")


def make_token(user_id):
    return _serializer().dumps({"uid": user_id})


def public_user(row):
    return {"id": row["id"], "username": row["username"],
            "full_name": row["full_name"], "role": row["role"]}


def login_required(*roles):
    """@login_required() -> any signed-in user.  @login_required('admin','manager') -> only those roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                raise ApiError("Authentication required. Please sign in.", 401)
            try:
                data = _serializer().loads(header[7:], max_age=config.TOKEN_MAX_AGE)
            except SignatureExpired:
                raise ApiError("Your session expired. Please sign in again.", 401)
            except BadSignature:
                raise ApiError("Invalid session. Please sign in again.", 401)

            user = get_db().execute(
                "SELECT id, username, full_name, role, is_active FROM users WHERE id = ?",
                (data.get("uid"),),
            ).fetchone()
            if not user or not user["is_active"]:
                raise ApiError("Account not found or disabled.", 401)
            if roles and user["role"] not in roles:
                raise ApiError("You do not have permission to do this.", 403)
            g.user = dict(user)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
