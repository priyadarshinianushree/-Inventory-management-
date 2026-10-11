-- ============================================================
--  Inventory Management System - Database Schema (SQLite)
-- ============================================================
PRAGMA foreign_keys = ON;

-- Users & roles: admin > manager > staff
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'staff')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suppliers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    contact_person TEXT,
    phone          TEXT,
    email          TEXT,
    address        TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS warehouses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    location   TEXT NOT NULL,
    capacity   INTEGER NOT NULL CHECK (capacity > 0),   -- max units the warehouse can hold
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    category_id   INTEGER NOT NULL REFERENCES categories(id),
    supplier_id   INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    unit          TEXT NOT NULL DEFAULT 'pcs',
    cost_price    REAL NOT NULL CHECK (cost_price >= 0),
    sell_price    REAL NOT NULL CHECK (sell_price >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    description   TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Current stock of a product in a warehouse (changed ONLY by completed transactions)
CREATE TABLE IF NOT EXISTS stock (
    product_id   INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    PRIMARY KEY (product_id, warehouse_id)
);

-- Every stock movement. Workflow: PENDING -> COMPLETED | REJECTED | CANCELLED
CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_no           TEXT UNIQUE,
    type             TEXT NOT NULL CHECK (type IN ('IN', 'OUT', 'TRANSFER', 'ADJUSTMENT')),
    product_id       INTEGER NOT NULL REFERENCES products(id),
    warehouse_id     INTEGER NOT NULL REFERENCES warehouses(id),   -- source / target warehouse
    to_warehouse_id  INTEGER REFERENCES warehouses(id),            -- only for TRANSFER
    quantity         INTEGER NOT NULL CHECK (quantity <> 0),       -- negative allowed only for ADJUSTMENT
    unit_price       REAL NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    status           TEXT NOT NULL DEFAULT 'PENDING'
                     CHECK (status IN ('PENDING', 'COMPLETED', 'REJECTED', 'CANCELLED')),
    note             TEXT,
    created_by       INTEGER NOT NULL REFERENCES users(id),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_by      INTEGER REFERENCES users(id),
    reviewed_at      TEXT,
    review_note      TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_category   ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_supplier   ON products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_stock_warehouse     ON stock(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_tx_product          ON transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_tx_warehouse        ON transactions(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_tx_status           ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_tx_created          ON transactions(created_at);
