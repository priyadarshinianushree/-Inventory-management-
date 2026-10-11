"""Central configuration. Override with environment variables if needed."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.environ.get("INVENTORY_DB", os.path.join(BASE_DIR, "database", "inventory.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
TOKEN_MAX_AGE = 60 * 60 * 12  # login stays valid for 12 hours

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))
