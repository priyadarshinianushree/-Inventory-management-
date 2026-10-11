"""Shared helpers: API errors, input validation, pagination."""
import math
import re

ROLES_MANAGER_UP = ("admin", "manager")


class ApiError(Exception):
    """Raised anywhere to return a clean JSON error to the client."""

    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details or {}


class Validator:
    """Collects field errors, then raises one 422 error with all of them."""

    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {}
        self.errors = {}

    def _get(self, key):
        v = self.data.get(key)
        if isinstance(v, str):
            v = v.strip()
        return None if v == "" else v

    def fail(self, key, msg):
        self.errors.setdefault(key, msg)
        return None

    def text(self, key, label, required=False, max_len=200, min_len=0,
             pattern=None, msg=None, upper=False):
        v = self._get(key)
        if v is None:
            return self.fail(key, f"{label} is required") if required else None
        v = str(v)
        if upper:
            v = v.upper()
        if len(v) < min_len:
            return self.fail(key, f"{label} must be at least {min_len} characters")
        if len(v) > max_len:
            return self.fail(key, f"{label} must be at most {max_len} characters")
        if pattern and not re.fullmatch(pattern, v):
            return self.fail(key, msg or f"{label} is invalid")
        return v

    def email(self, key, label, required=False):
        return self.text(key, label, required, max_len=120,
                         pattern=r"[^@\s]+@[^@\s]+\.[^@\s]+", msg=f"{label} must be a valid email")

    def integer(self, key, label, required=False, minimum=None, maximum=None, nonzero=False):
        v = self._get(key)
        if v is None:
            return self.fail(key, f"{label} is required") if required else None
        try:
            if isinstance(v, bool):
                raise ValueError
            if isinstance(v, float):
                if not v.is_integer():
                    raise ValueError
                n = int(v)
            else:
                n = int(str(v))
        except ValueError:
            return self.fail(key, f"{label} must be a whole number")
        if nonzero and n == 0:
            return self.fail(key, f"{label} cannot be zero")
        if minimum is not None and n < minimum:
            return self.fail(key, f"{label} must be at least {minimum}")
        if maximum is not None and n > maximum:
            return self.fail(key, f"{label} must be at most {maximum}")
        return n

    def number(self, key, label, required=False, minimum=None, maximum=None):
        v = self._get(key)
        if v is None:
            return self.fail(key, f"{label} is required") if required else None
        try:
            if isinstance(v, bool):
                raise ValueError
            n = float(v)
            if not math.isfinite(n):
                raise ValueError
        except (TypeError, ValueError):
            return self.fail(key, f"{label} must be a number")
        if minimum is not None and n < minimum:
            return self.fail(key, f"{label} must be at least {minimum}")
        if maximum is not None and n > maximum:
            return self.fail(key, f"{label} must be at most {maximum}")
        return round(n, 2)

    def choice(self, key, choices, label, required=False):
        v = self._get(key)
        if v is None:
            return self.fail(key, f"{label} is required") if required else None
        v = str(v)
        if v not in choices:
            return self.fail(key, f"{label} must be one of: {', '.join(choices)}")
        return v

    def boolean(self, key, default=False):
        v = self.data.get(key)
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")

    def check(self):
        if self.errors:
            raise ApiError("Please correct the highlighted fields.", 422, self.errors)


def int_arg(args, key, default, lo=None, hi=None):
    try:
        n = int(args.get(key, default))
    except (TypeError, ValueError):
        n = default
    if lo is not None:
        n = max(n, lo)
    if hi is not None:
        n = min(n, hi)
    return n


def paged(db, base_sql, where, params, sort_map, default_sort, args, default_order="asc"):
    """Run a filtered, sorted, paginated query over `base_sql`.

    base_sql must expose an `id` column. `sort_map` is a whitelist: {api_name: sql_expr}.
    """
    page = int_arg(args, "page", 1, lo=1)
    per_page = int_arg(args, "per_page", 10, lo=1, hi=500)
    sort_sql = sort_map.get(args.get("sort"), sort_map[default_sort])
    order = (args.get("order") or default_order).lower()
    order = "DESC" if order == "desc" else "ASC"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM ({base_sql}) x {where_sql}", params).fetchone()[0]
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    rows = db.execute(
        f"SELECT * FROM ({base_sql}) x {where_sql} ORDER BY {sort_sql} {order}, id DESC LIMIT ? OFFSET ?",
        list(params) + [per_page, (page - 1) * per_page],
    ).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "page": page,
            "pages": pages, "per_page": per_page}


def like(term):
    return f"%{term.strip()}%"
