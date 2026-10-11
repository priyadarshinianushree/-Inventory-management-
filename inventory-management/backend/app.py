"""Inventory Management - Flask application entry point.

Run:   python backend/app.py        ->  http://127.0.0.1:5000
"""
import logging
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from flask import Flask, g, jsonify, request, send_from_directory  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402
from utils import ApiError  # noqa: E402


def create_app():
    app = Flask(__name__, static_folder=config.FRONTEND_DIR, static_url_path="")
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.teardown_appcontext(db.close_db)

    # First run: build the database with demo data automatically.
    if not os.path.exists(config.DB_PATH):
        from database.seed import build_database
        print("Database not found - creating it with demo data ...")
        build_database(config.DB_PATH)

    from routes import auth_routes, dashboard, masters, products, stock_tx, users
    for module in (auth_routes, users, masters, products, stock_tx, dashboard):
        app.register_blueprint(module.bp, url_prefix="/api")

    # ------------------------------------------------------------ error handling (always JSON for /api)
    def rollback():
        conn = g.get("db")
        if conn is not None:
            conn.rollback()

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        rollback()
        return jsonify(error=err.message, details=err.details), err.status

    @app.errorhandler(sqlite3.IntegrityError)
    def handle_integrity(err):
        rollback()
        msg = str(err)
        if "UNIQUE" in msg:
            field = msg.split(":")[-1].strip().split(".")[-1]
            return jsonify(error=f"A record with this {field} already exists.", details={}), 409
        if "FOREIGN KEY" in msg:
            return jsonify(error="This record is linked to other data and cannot be changed or removed.",
                           details={}), 409
        return jsonify(error="The data violates a database rule.", details={}), 400

    @app.errorhandler(HTTPException)
    def handle_http(err):
        if request.path.startswith("/api"):
            return jsonify(error=err.description or err.name, details={}), err.code
        return err

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        rollback()
        app.logger.exception("Unhandled error")
        return jsonify(error="Something went wrong on the server. Please try again.", details={}), 500

    @app.get("/")
    def landing():
        return send_from_directory(config.FRONTEND_DIR, "landing.html")

    @app.get("/app")
    def index():
        return send_from_directory(config.FRONTEND_DIR, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()

if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    print(f"\n  Inventory Management is running ->  http://{config.HOST}:{config.PORT}")
    print("  Login: admin/admin123 | manager/manager123 | staff/staff123   (Ctrl+C to stop)\n")
    app.run(host=config.HOST, port=config.PORT, debug=False)
