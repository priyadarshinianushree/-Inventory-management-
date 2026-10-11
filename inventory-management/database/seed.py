"""
Creates database/inventory.db with the schema + realistic demo data.

    python database/seed.py          # (re)creates the database from scratch

All stock quantities are produced by REAL transactions (purchases, sales, transfers,
adjustments) that go through the same business rules the application uses, so the
stock table, transaction history and dashboard always agree with each other.
"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import config  # noqa: E402
from db import connect, create_schema  # noqa: E402
from inventory_service import create_transaction, close_transaction  # noqa: E402
from utils import ApiError  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

# --------------------------------------------------------------------------- master data
USERS = [  # username, full name, password, role
    ("admin", "System Administrator", "admin123", "admin"),
    ("manager", "Priya Raman", "manager123", "manager"),
    ("staff", "Karthik Kumar", "staff123", "staff"),
    ("staff2", "Meena Sundaram", "staff123", "staff"),
]

CATEGORIES = [
    ("Electronics", "Mobiles, audio devices, power banks, networking and storage gadgets"),
    ("Computers & Accessories", "Laptops, monitors, printers, keyboards, mice and external drives"),
    ("Home Appliances", "Kitchen and household electrical appliances"),
    ("Groceries", "Packaged staples: flour, rice, dal, oil, salt and tea"),
    ("Stationery", "Notebooks, pens, paper and office / school supplies"),
    ("Personal Care", "Toothpaste, soaps, shampoos, skin care and grooming products"),
    ("Furniture", "Office and home furniture"),
    ("Sports & Fitness", "Sports equipment and fitness accessories"),
]

SUPPLIERS = [  # name, contact, phone, email, address
    ("Chennai Digital Distributors", "Ramesh Babu", "9840012345", "sales@chennaidigital.example.com", "T. Nagar, Chennai, Tamil Nadu"),
    ("Bengaluru Tech Wholesale", "Anitha Rao", "9845098450", "orders@blrtechwholesale.example.com", "SP Road, Bengaluru, Karnataka"),
    ("Coimbatore Appliance Traders", "Suresh Kumar", "9894123456", "info@cbeappliances.example.com", "Oppanakara Street, Coimbatore, Tamil Nadu"),
    ("Madurai Agro Foods", "Lakshmi Narayanan", "9786543210", "supply@maduraiagro.example.com", "Mattuthavani, Madurai, Tamil Nadu"),
    ("Sivakasi Paper & Stationery Mart", "Murugan S", "9442267890", "hello@sivakasipaper.example.com", "Sattur Road, Sivakasi, Tamil Nadu"),
    ("Southern Personal Care Agencies", "Divya Menon", "9445011223", "agency@southerncare.example.com", "Anna Salai, Chennai, Tamil Nadu"),
    ("Salem Furniture Works", "Palanisamy R", "9790055667", "contact@salemfurniture.example.com", "Fairlands, Salem, Tamil Nadu"),
    ("Tirupur Sports Goods Co.", "Vignesh T", "9976543201", "sales@tirupursports.example.com", "Kangeyam Road, Tirupur, Tamil Nadu"),
]

WAREHOUSES = [  # code, name, location, capacity, share of stock
    ("CHN-01", "Chennai Central Warehouse", "Ambattur Industrial Estate, Chennai", 4000, 0.40),
    ("CBE-01", "Coimbatore Regional Hub", "Kurichi SIDCO Industrial Estate, Coimbatore", 2500, 0.25),
    ("MDU-01", "Madurai Distribution Center", "Thirumangalam Road, Madurai", 2000, 0.15),
    ("BLR-01", "Bengaluru Fulfilment Center", "Peenya Industrial Area, Bengaluru", 3000, 0.20),
]

# sku, name, category, supplier, unit, cost, sell, reorder level, description
PRODUCTS = [
    # ---- Electronics
    ("ELE-001", "Samsung Galaxy M14 5G (6GB/128GB)", "Electronics", "Chennai Digital Distributors", "pcs", 11200, 12999, 8, "5G smartphone, 6000 mAh battery, 50 MP camera"),
    ("ELE-002", "boAt Rockerz 450 Bluetooth Headphones", "Electronics", "Bengaluru Tech Wholesale", "pcs", 1050, 1499, 15, "On-ear wireless headphones, 15 hr playback"),
    ("ELE-003", "Mi 10000mAh Power Bank 2i", "Electronics", "Bengaluru Tech Wholesale", "pcs", 780, 999, 20, "18W fast charging power bank"),
    ("ELE-004", "realme Buds Wireless 3 Neckband", "Electronics", "Chennai Digital Distributors", "pcs", 1250, 1799, 15, "Bluetooth neckband earphones with ANC"),
    ("ELE-005", "TP-Link Archer C6 AC1200 Wi-Fi Router", "Electronics", "Chennai Digital Distributors", "pcs", 2300, 2899, 10, "Dual-band gigabit Wi-Fi router"),
    ("ELE-006", "SanDisk Cruzer Blade 64GB Pen Drive", "Electronics", "Bengaluru Tech Wholesale", "pcs", 380, 549, 30, "USB 2.0 flash drive"),
    # ---- Computers & Accessories
    ("CMP-001", "HP 15s Core i3 Laptop (8GB/512GB SSD)", "Computers & Accessories", "Bengaluru Tech Wholesale", "pcs", 32500, 37999, 5, "15.6 inch FHD laptop with Windows 11"),
    ("CMP-002", "Dell SE2422H 24-inch Full HD Monitor", "Computers & Accessories", "Bengaluru Tech Wholesale", "pcs", 8200, 9999, 6, "VA panel, 75 Hz, HDMI + VGA"),
    ("CMP-003", "Logitech K380 Bluetooth Keyboard", "Computers & Accessories", "Chennai Digital Distributors", "pcs", 2100, 2795, 10, "Compact multi-device keyboard"),
    ("CMP-004", "Logitech M221 Silent Wireless Mouse", "Computers & Accessories", "Chennai Digital Distributors", "pcs", 650, 899, 25, "Silent-click 2.4 GHz wireless mouse"),
    ("CMP-005", "HP DeskJet 2331 All-in-One Printer", "Computers & Accessories", "Bengaluru Tech Wholesale", "pcs", 3400, 4299, 6, "Print, scan and copy inkjet printer"),
    ("CMP-006", "Seagate Expansion 1TB External HDD", "Computers & Accessories", "Chennai Digital Distributors", "pcs", 3700, 4699, 10, "USB 3.0 portable hard drive"),
    # ---- Home Appliances
    ("APP-001", "Philips HL7756 750W Mixer Grinder", "Home Appliances", "Coimbatore Appliance Traders", "pcs", 3300, 4195, 8, "3 jars, 750 watt motor"),
    ("APP-002", "Prestige PIC 20 Induction Cooktop", "Home Appliances", "Coimbatore Appliance Traders", "pcs", 1950, 2595, 10, "1200 W induction cooktop with push buttons"),
    ("APP-003", "Havells Stealth Air 1200mm Ceiling Fan", "Home Appliances", "Coimbatore Appliance Traders", "pcs", 2600, 3299, 12, "BLDC-ready high-speed ceiling fan"),
    ("APP-004", "Bajaj Majesty 1.5L Electric Kettle", "Home Appliances", "Coimbatore Appliance Traders", "pcs", 640, 895, 15, "Stainless steel kettle with auto cut-off"),
    ("APP-005", "Usha EI 1602 Dry Iron", "Home Appliances", "Coimbatore Appliance Traders", "pcs", 520, 745, 15, "1000 W non-stick dry iron"),
    ("APP-006", "Prestige Delight 1.8L Electric Rice Cooker", "Home Appliances", "Coimbatore Appliance Traders", "pcs", 1450, 1995, 8, "Aluminium pan with keep-warm function"),
    # ---- Groceries
    ("GRO-001", "Aashirvaad Whole Wheat Atta 5 kg", "Groceries", "Madurai Agro Foods", "bag", 215, 260, 40, "100% whole wheat flour"),
    ("GRO-002", "Fortune Sunlite Refined Sunflower Oil 1 L", "Groceries", "Madurai Agro Foods", "pouch", 118, 139, 50, "Refined sunflower cooking oil"),
    ("GRO-003", "Tata Salt Vacuum Evaporated 1 kg", "Groceries", "Madurai Agro Foods", "pack", 22, 28, 80, "Iodised free-flow salt"),
    ("GRO-004", "Tata Tea Gold 500 g", "Groceries", "Madurai Agro Foods", "pack", 235, 280, 40, "Premium CTC tea leaf blend"),
    ("GRO-005", "India Gate Basmati Rice Classic 5 kg", "Groceries", "Madurai Agro Foods", "bag", 520, 625, 30, "Aged long-grain basmati rice"),
    ("GRO-006", "Toor Dal Premium 1 kg", "Groceries", "Madurai Agro Foods", "pack", 138, 165, 40, "Unpolished split pigeon peas"),
    # ---- Stationery
    ("STA-001", "Classmate Spiral Notebook 172 Pages", "Stationery", "Sivakasi Paper & Stationery Mart", "pcs", 52, 68, 60, "Single-line spiral bound notebook"),
    ("STA-002", "Reynolds Trimax Ball Pen Blue (Box of 10)", "Stationery", "Sivakasi Paper & Stationery Mart", "box", 68, 90, 50, "0.7 mm smooth writing ball pens"),
    ("STA-003", "Camlin Geometry Box", "Stationery", "Sivakasi Paper & Stationery Mart", "pcs", 85, 120, 30, "Metal geometry instrument box"),
    ("STA-004", "JK Copier A4 Paper 75 GSM (500 Sheets)", "Stationery", "Sivakasi Paper & Stationery Mart", "ream", 235, 290, 40, "Multi-purpose printer paper"),
    ("STA-005", "Apsara Platinum Pencils (Pack of 10)", "Stationery", "Sivakasi Paper & Stationery Mart", "pack", 38, 50, 60, "HB extra-dark pencils"),
    ("STA-006", "Kangaro HD-10 Stapler with Pins", "Stationery", "Sivakasi Paper & Stationery Mart", "pcs", 62, 85, 30, "Standard office stapler"),
    # ---- Personal Care
    ("PER-001", "Colgate Strong Teeth Toothpaste 200 g", "Personal Care", "Southern Personal Care Agencies", "pcs", 82, 105, 50, "Cavity protection toothpaste"),
    ("PER-002", "Dove Cream Beauty Bathing Bar (Pack of 3)", "Personal Care", "Southern Personal Care Agencies", "pack", 120, 155, 40, "Moisturising beauty bar"),
    ("PER-003", "Head & Shoulders Anti-Dandruff Shampoo 340 ml", "Personal Care", "Southern Personal Care Agencies", "bottle", 235, 295, 30, "Smooth & silky anti-dandruff shampoo"),
    ("PER-004", "Dettol Liquid Handwash Refill 750 ml", "Personal Care", "Southern Personal Care Agencies", "pouch", 125, 160, 35, "Original germ-protection handwash"),
    ("PER-005", "Nivea Soft Light Moisturising Cream 200 ml", "Personal Care", "Southern Personal Care Agencies", "jar", 175, 225, 25, "Light moisturiser for face and body"),
    ("PER-006", "Gillette Guard Razor with 2 Blades", "Personal Care", "Southern Personal Care Agencies", "pack", 38, 55, 50, "Safety razor with 2 cartridges"),
    # ---- Furniture
    ("FUR-001", "Ergonomic Mesh Office Chair", "Furniture", "Salem Furniture Works", "pcs", 3900, 5499, 5, "High-back chair with lumbar support"),
    ("FUR-002", "Engineered Wood Study Table", "Furniture", "Salem Furniture Works", "pcs", 3300, 4599, 4, "120 cm study / work desk"),
    ("FUR-003", "Godrej Steel Almirah 2-Door", "Furniture", "Salem Furniture Works", "pcs", 9800, 12499, 3, "Steel wardrobe with locker"),
    ("FUR-004", "5-Tier Wooden Bookshelf", "Furniture", "Salem Furniture Works", "pcs", 2800, 3799, 5, "Open bookshelf, walnut finish"),
    ("FUR-005", "Nilkamal Plastic Armless Chair", "Furniture", "Salem Furniture Works", "pcs", 780, 1099, 20, "Durable moulded plastic chair"),
    ("FUR-006", "Foldable Laptop Table", "Furniture", "Salem Furniture Works", "pcs", 780, 1199, 10, "Adjustable portable laptop desk"),
    # ---- Sports & Fitness
    ("SPT-001", "Cosco Hunter Football Size 5", "Sports & Fitness", "Tirupur Sports Goods Co.", "pcs", 420, 599, 15, "Machine-stitched football"),
    ("SPT-002", "Yonex Muscle Power 29 Badminton Racquet", "Sports & Fitness", "Tirupur Sports Goods Co.", "pcs", 1150, 1590, 10, "Aluminium racquet with full cover"),
    ("SPT-003", "Boldfit Yoga Mat 6 mm", "Sports & Fitness", "Tirupur Sports Goods Co.", "pcs", 340, 549, 20, "Anti-slip EVA yoga mat"),
    ("SPT-004", "Nivia Adjustable Dumbbell Set 10 kg", "Sports & Fitness", "Tirupur Sports Goods Co.", "set", 1250, 1799, 8, "Pair of dumbbells with plates"),
    ("SPT-005", "Cosco Skipping Rope", "Sports & Fitness", "Tirupur Sports Goods Co.", "pcs", 110, 179, 25, "Adjustable PVC skipping rope"),
    ("SPT-006", "Yonex Mavis 350 Nylon Shuttlecock (Tube of 6)", "Sports & Fitness", "Tirupur Sports Goods Co.", "tube", 480, 650, 20, "Practice nylon shuttlecocks"),
]

# Deliberately make some products low / out of stock so the dashboard has real alerts.
FINAL_TOTAL = {
    "CMP-001": 0, "APP-003": 0, "GRO-004": 0, "PER-005": 0,                 # out of stock
    "ELE-003": 12, "STA-003": 18, "FUR-003": 2, "SPT-004": 5,               # low stock
    "GRO-002": 35, "CMP-005": 4, "ELE-001": 6, "PER-004": 22,
}

IN_NOTES = ["Purchase order {po} received from {sup}", "Goods receipt against {po} - {sup}",
            "Supplier delivery {po} - {sup}"]
OUT_NOTES = ["Retail sales order {so}", "Dispatched to customer - order {so}",
             "Bulk order {so} - corporate customer", "Showroom replenishment {so}"]


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _split(total, weights):
    parts = [int(total * w / sum(weights)) for w in weights]
    parts[0] += total - sum(parts)
    return parts


def _chunks(total, n):
    n = max(1, min(n, total))
    base = total // n
    out = [base] * n
    out[-1] += total - base * n
    return out


def build_database(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for suffix in ("", "-wal", "-shm", "-journal"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)

    rnd = random.Random(2026)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = connect(path)
    create_schema(db)

    # ---- users, categories, suppliers, warehouses
    for username, name, pwd, role in USERS:
        db.execute("INSERT INTO users(username, full_name, password_hash, role) VALUES (?,?,?,?)",
                   (username, name, generate_password_hash(pwd), role))
    for name, desc in CATEGORIES:
        db.execute("INSERT INTO categories(name, description) VALUES (?,?)", (name, desc))
    for s in SUPPLIERS:
        db.execute("INSERT INTO suppliers(name, contact_person, phone, email, address) VALUES (?,?,?,?,?)", s)
    for code, name, loc, cap, _w in WAREHOUSES:
        db.execute("INSERT INTO warehouses(code, name, location, capacity) VALUES (?,?,?,?)", (code, name, loc, cap))

    cat_id = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM categories")}
    sup_id = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM suppliers")}
    wh_ids = [r["id"] for r in db.execute("SELECT id FROM warehouses ORDER BY id")]
    wh_weight = {wid: WAREHOUSES[i][4] for i, wid in enumerate(wh_ids)}
    manager_id, staff_ids = 2, [3, 4]

    for sku, name, cat, sup, unit, cost, sell, reorder, desc in PRODUCTS:
        db.execute(
            "INSERT INTO products(sku, name, category_id, supplier_id, unit, cost_price, sell_price, "
            "reorder_level, description) VALUES (?,?,?,?,?,?,?,?,?)",
            (sku, name, cat_id[cat], sup_id[sup], unit, cost, sell, reorder, desc))
    products = {r["sku"]: dict(r) for r in db.execute("SELECT * FROM products")}
    sup_name = {v: k for k, v in sup_id.items()}

    # ---- plan 60 days of stock history
    events = []  # (datetime, user_id, data)

    def add(days_ago, user, **d):
        when = now - timedelta(days=days_ago, hours=rnd.randint(0, 9), minutes=rnd.randint(0, 59))
        d.setdefault("to_warehouse_id", None)
        events.append((when, user, d))

    def po_no():
        return f"PO-2026-{rnd.randint(1000, 4999)}"

    def so_no():
        return f"SO-2026-{rnd.randint(5000, 9999)}"

    transfer_done = 0
    adj_done = 0
    for sku, p in products.items():
        reorder = p["reorder_level"]
        override = sku in FINAL_TOTAL
        final = FINAL_TOTAL.get(sku, rnd.randint(int(reorder * 1.3) + 1, reorder * 5))
        whs = sorted(rnd.sample(wh_ids, k=rnd.choice([2, 3, 3, 4])))
        final_split = _split(final, [wh_weight[w] for w in whs]) if final else [0] * len(whs)
        extra_in = {w: 0 for w in whs}

        # one stock transfer between two warehouses (not for alert products)
        if not override and transfer_done < 8 and len(whs) >= 2 and final_split[0] >= 12:
            src, dst = whs[0], whs[1]
            q = max(2, final_split[0] // 4)
            extra_in[src] = q
            add(rnd.randint(33, 37), manager_id, type="TRANSFER", product_id=p["id"], warehouse_id=src,
                to_warehouse_id=dst, quantity=q, unit_price=p["cost_price"],
                note=f"Rebalancing stock between {WAREHOUSES[wh_ids.index(src)][1]} and "
                     f"{WAREHOUSES[wh_ids.index(dst)][1]}")
            transfer_done += 1

        for w, f_w in zip(whs, final_split):
            sold = max(2, int((f_w + 3) * rnd.uniform(0.4, 1.1)))
            bought = f_w + sold + extra_in[w]
            for q in _chunks(bought, rnd.choice([1, 2])):
                add(rnd.randint(40, 70), manager_id, type="IN", product_id=p["id"], warehouse_id=w,
                    quantity=q, unit_price=p["cost_price"],
                    note=rnd.choice(IN_NOTES).format(po=po_no(), sup=sup_name[p["supplier_id"]]))
            for q in _chunks(sold, rnd.choice([1, 2, 3, 4])):
                add(rnd.randint(1, 28), rnd.choice(staff_ids), type="OUT", product_id=p["id"], warehouse_id=w,
                    quantity=q, unit_price=p["sell_price"], note=rnd.choice(OUT_NOTES).format(so=so_no()))

            if not override and adj_done < 6 and f_w >= 8:
                if adj_done % 2 == 0:
                    add(rnd.randint(3, 8), manager_id, type="ADJUSTMENT", product_id=p["id"], warehouse_id=w,
                        quantity=-rnd.randint(1, 3), unit_price=p["cost_price"],
                        note="Damaged during handling - written off")
                else:
                    add(rnd.randint(3, 8), manager_id, type="ADJUSTMENT", product_id=p["id"], warehouse_id=w,
                        quantity=rnd.randint(1, 3), unit_price=p["cost_price"],
                        note="Stock count correction after physical audit")
                adj_done += 1

    events.sort(key=lambda e: e[0])
    skipped = 0
    for when, user, d in events:
        try:
            tx_id = create_transaction(db, d, manager_id, complete=True, created_at=_fmt(when))
            db.execute("UPDATE transactions SET created_by=? WHERE id=?", (user, tx_id))
        except ApiError:
            skipped += 1  # a rule (stock / capacity) prevented it; history stays consistent

    # ---- open workflow items: pending / rejected / cancelled
    def stock_rows(min_qty):
        return db.execute("SELECT product_id, warehouse_id, quantity FROM stock WHERE quantity >= ? "
                          "ORDER BY product_id, warehouse_id", (min_qty,)).fetchall()

    def pending(hours_ago, user, **d):
        p = db.execute("SELECT cost_price, sell_price FROM products WHERE id=?", (d["product_id"],)).fetchone()
        d.setdefault("to_warehouse_id", None)
        d["unit_price"] = p["sell_price"] if d["type"] == "OUT" else p["cost_price"]
        when = _fmt(now - timedelta(hours=hours_ago))
        return create_transaction(db, d, user, complete=False, created_at=when)

    rows = stock_rows(20)
    rnd.shuffle(rows)
    r = iter(rows)
    nxt = lambda: next(r)  # noqa: E731

    s = nxt()
    pending(3, staff_ids[0], type="OUT", product_id=s["product_id"], warehouse_id=s["warehouse_id"],
            quantity=min(10, s["quantity"] // 3), note=f"Customer order {so_no()} awaiting dispatch approval")
    s = nxt()
    pending(5, staff_ids[1], type="OUT", product_id=s["product_id"], warehouse_id=s["warehouse_id"],
            quantity=min(8, s["quantity"] // 3), note=f"Showroom replenishment {so_no()}")
    for sku, qty in (("ELE-003", 40), ("GRO-004", 60)):
        p = products[sku]
        pending(8, staff_ids[0], type="IN", product_id=p["id"], warehouse_id=wh_ids[0], quantity=qty,
                note=f"Urgent restock - {po_no()} from {sup_name[p['supplier_id']]}")
    s = nxt()
    dst = next(w for w in wh_ids if w != s["warehouse_id"])
    pending(2, staff_ids[1], type="TRANSFER", product_id=s["product_id"], warehouse_id=s["warehouse_id"],
            to_warehouse_id=dst, quantity=max(2, s["quantity"] // 4), note="Move stock closer to customers")
    s = nxt()
    pending(1, staff_ids[0], type="ADJUSTMENT", product_id=s["product_id"], warehouse_id=s["warehouse_id"],
            quantity=-2, note="Two units found damaged during cycle count")

    s = nxt()
    tx = pending(52, staff_ids[0], type="OUT", product_id=s["product_id"], warehouse_id=s["warehouse_id"],
                 quantity=min(12, s["quantity"] // 2), note=f"Bulk order {so_no()}")
    close_transaction(db, tx, manager_id, "REJECTED", "Quantity exceeds the customer's approved order")
    p = products["STA-004"]
    tx = pending(70, staff_ids[1], type="IN", product_id=p["id"], warehouse_id=wh_ids[1], quantity=30,
                 note=f"Duplicate purchase order {po_no()}")
    close_transaction(db, tx, staff_ids[1], "CANCELLED", "Duplicate PO - cancelled by requester")

    db.commit()
    summary = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in ("users", "categories", "suppliers", "warehouses", "products", "stock", "transactions")}
    db.close()
    return summary


if __name__ == "__main__":
    out = build_database()
    print(f"Database created at {config.DB_PATH}")
    for k, v in out.items():
        print(f"  {k:<13}{v}")
    print("\nLogins:  admin/admin123   manager/manager123   staff/staff123")
