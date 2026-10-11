/* Page definitions (all built on createListPage) + small shared renderers. */

/* ------------------------------------------------------------ shared renderers */
const TYPE_LABEL = { IN: "Stock In", OUT: "Stock Out", TRANSFER: "Transfer", ADJUSTMENT: "Adjustment" };
const TYPE_TONE = { IN: "green", OUT: "red", TRANSFER: "blue", ADJUSTMENT: "violet" };
const STATUS_TONE = { PENDING: "amber", COMPLETED: "green", REJECTED: "red", CANCELLED: "gray" };
const typeBadge = (t) => badge(TYPE_LABEL[t] || t, TYPE_TONE[t] || "gray");
const statusBadge = (s) => badge(s[0] + s.slice(1).toLowerCase(), STATUS_TONE[s] || "gray");
const isManager = (u) => u.role === "admin" || u.role === "manager";
const activeBadge = (v) => (v ? badge("Active", "green") : badge("Inactive", "gray"));
const cell = (main, sub) => `<div class="main-text">${esc(main)}</div>${sub ? `<div class="sub-text">${esc(sub)}</div>` : ""}`;

function signedQty(r) {
  const q = Number(r.quantity);
  if (r.type === "IN") return `<span class="qty-pos">+${fmt.num(q)}</span>`;
  if (r.type === "OUT") return `<span class="qty-neg">-${fmt.num(q)}</span>`;
  if (r.type === "ADJUSTMENT") return `<span class="${q > 0 ? "qty-pos" : "qty-neg"}">${q > 0 ? "+" : "-"}${fmt.num(Math.abs(q))}</span>`;
  return fmt.num(q);
}
function stockBadge(s) {
  return s === "out" ? badge("Out of stock", "red") : s === "low" ? badge("Low stock", "amber") : badge("In stock", "green");
}

const Lookup = {
  async options(path, label, params = {}) {
    const res = await API.get(path, { per_page: 500, sort: "name", ...params });
    return res.items.map((i) => ({ value: i.id, label: label(i) }));
  },
  categories: () => Lookup.options("/categories", (c) => c.name),
  suppliers: () => Lookup.options("/suppliers", (s) => s.name),
  warehouses: (params) => Lookup.options("/warehouses", (w) => `${w.name} (${w.code})`, params),
  products: (params) => Lookup.options("/products", (p) => `${p.sku} - ${p.name}`, params),
};
const withBlank = (fn, text) => async () => [{ value: "", label: text }, ...(await fn())];
const ACTIVE_FILTER = { name: "active", label: "Any status", options: [{ value: "1", label: "Active" }, { value: "0", label: "Inactive" }] };
const UNITS = ["pcs", "box", "pack", "bag", "pouch", "bottle", "jar", "ream", "set", "tube", "kg", "litre"].map((u) => ({ value: u, label: u }));
const toBool = (row) => ({ ...row, is_active: !!row.is_active });

/* ------------------------------------------------------------ products */
async function showProduct(row) {
  const m = openModal({ title: row.name, size: "lg", html: '<div class="loading">Loading...</div>' });
  try {
    const p = await API.get("/products/" + row.id);
    const margin = p.sell_price ? ((p.sell_price - p.cost_price) / p.sell_price * 100).toFixed(1) : "0";
    m.body.innerHTML = `
      <div class="detail-grid">
        <div><span>SKU</span><b>${esc(p.sku)}</b></div><div><span>Category</span><b>${esc(p.category_name)}</b></div>
        <div><span>Supplier</span><b>${esc(p.supplier_name || "-")}</b></div>
        <div><span>Cost / Selling price</span><b>${fmt.money(p.cost_price)} / ${fmt.money(p.sell_price)}</b></div>
        <div><span>Margin</span><b>${margin}%</b></div>
        <div><span>Total stock</span><b>${fmt.num(p.total_qty)} ${esc(p.unit)}</b> ${stockBadge(p.stock_status)}</div>
        <div><span>Reorder level</span><b>${fmt.num(p.reorder_level)}</b></div>
        <div><span>Stock value</span><b>${fmt.money(p.total_qty * p.cost_price)}</b></div>
      </div>
      ${p.description ? `<p style="margin:0 0 6px;color:var(--muted)">${esc(p.description)}</p>` : ""}
      <h4>Stock by warehouse</h4>
      ${p.stock.length ? `<table class="mini-table"><thead><tr><th>Warehouse</th><th class="num">Quantity</th></tr></thead><tbody>
        ${p.stock.map((s) => `<tr><td>${esc(s.warehouse_name)} <span class="sub-text">${esc(s.code)}</span></td><td class="num">${fmt.num(s.quantity)}</td></tr>`).join("")}</tbody></table>`
        : '<p class="sub-text">No stock recorded yet.</p>'}
      <h4>Recent transactions</h4>
      ${p.recent_transactions.length ? `<table class="mini-table"><thead><tr><th>Ref</th><th>Type</th><th>Warehouse</th><th class="num">Qty</th><th>Status</th><th>Date</th></tr></thead><tbody>
        ${p.recent_transactions.map((t) => `<tr><td>${esc(t.ref_no)}</td><td>${typeBadge(t.type)}</td><td>${esc(t.warehouse_name)}</td><td class="num">${signedQty(t)}</td><td>${statusBadge(t.status)}</td><td>${fmt.date(t.created_at)}</td></tr>`).join("")}</tbody></table>`
        : '<p class="sub-text">No transactions yet.</p>'}`;
  } catch (err) { m.body.innerHTML = `<div class="load-error">${esc(err.message)}</div>`; }
}

const ProductsPage = createListPage({
  key: "products", title: "Products", subtitle: "Your catalogue with live stock levels", itemName: "product", addLabel: "Add product",
  endpoint: "/products", searchPlaceholder: "Search by name, SKU or category...", defaultSort: "name", modalSize: "lg",
  canWrite: isManager, toForm: toBool, defaults: { unit: "pcs", reorder_level: 10, is_active: true },
  rowLabel: (r) => `${r.name} (${r.sku})`,
  filters: [
    { name: "category_id", label: "All categories", options: Lookup.categories },
    { name: "stock_status", label: "Any stock level", options: [{ value: "in", label: "In stock" }, { value: "low", label: "Low stock" }, { value: "out", label: "Out of stock" }] },
    ACTIVE_FILTER,
  ],
  columns: [
    { label: "Product", sort: "name", render: (r) => cell(r.name, r.sku) },
    { label: "Category", sort: "category", render: (r) => cell(r.category_name, r.supplier_name) },
    { label: "Price", sort: "price", num: true, render: (r) => `<div class="main-text">${fmt.money(r.sell_price)}</div><div class="sub-text">Cost ${fmt.money(r.cost_price)}</div>` },
    { label: "In stock", sort: "stock", num: true, render: (r) => `<div class="main-text">${fmt.num(r.total_qty)} ${esc(r.unit)}</div><div class="sub-text">Reorder at ${fmt.num(r.reorder_level)}</div>` },
    { label: "Status", render: (r) => `${stockBadge(r.stock_status)}${r.is_active ? "" : " " + badge("Inactive", "gray")}` },
  ],
  rowActions: [{ label: "View", run: (r) => showProduct(r) }],
  exportCsv: [["SKU", "sku"], ["Name", "name"], ["Category", "category_name"], ["Supplier", "supplier_name"], ["Unit", "unit"],
    ["Cost price", "cost_price"], ["Selling price", "sell_price"], ["Total stock", "total_qty"], ["Reorder level", "reorder_level"], ["Stock status", "stock_status"]],
  fields: [
    { name: "sku", label: "SKU", required: true, maxlength: 30, pattern: "[A-Za-z0-9\\-_]{3,30}", placeholder: "e.g. ELE-007", help: "3-30 letters, numbers, - or _" },
    { name: "name", label: "Product name", required: true, minlength: 2, maxlength: 120 },
    { name: "category_id", label: "Category", type: "select", required: true, options: withBlank(Lookup.categories, "Select category") },
    { name: "supplier_id", label: "Supplier", type: "select", options: withBlank(Lookup.suppliers, "- none -") },
    { name: "cost_price", label: "Cost price (INR)", type: "number", required: true, min: 0, step: "0.01" },
    { name: "sell_price", label: "Selling price (INR)", type: "number", required: true, min: 0, step: "0.01" },
    { name: "unit", label: "Unit", type: "select", required: true, options: UNITS },
    { name: "reorder_level", label: "Reorder level", type: "number", required: true, min: 0, step: 1, help: "Alert when total stock falls to this number" },
    { name: "description", label: "Description", type: "textarea", full: true, maxlength: 300 },
    { name: "is_active", label: "Active (available for transactions)", type: "checkbox", full: true },
  ],
});

/* ------------------------------------------------------------ categories */
const CategoriesPage = createListPage({
  key: "categories", title: "Categories", subtitle: "Group your products", itemName: "category", addLabel: "Add category",
  endpoint: "/categories", searchPlaceholder: "Search categories...", defaultSort: "name", modalSize: "sm", canWrite: isManager,
  columns: [
    { label: "Category", sort: "name", render: (r) => cell(r.name, r.description) },
    { label: "Products", sort: "products", num: true, render: (r) => `<a href="#/products?category_id=${r.id}">${fmt.num(r.product_count)}</a>` },
  ],
  fields: [
    { name: "name", label: "Name", required: true, maxlength: 60, full: true },
    { name: "description", label: "Description", type: "textarea", maxlength: 200, full: true },
  ],
});

/* ------------------------------------------------------------ suppliers */
const SuppliersPage = createListPage({
  key: "suppliers", title: "Suppliers", subtitle: "Vendors you purchase stock from", itemName: "supplier", addLabel: "Add supplier",
  endpoint: "/suppliers", searchPlaceholder: "Search name, contact, phone, email...", defaultSort: "name", canWrite: isManager,
  toForm: toBool, defaults: { is_active: true }, filters: [ACTIVE_FILTER],
  columns: [
    { label: "Supplier", sort: "name", render: (r) => cell(r.name, r.contact_person) },
    { label: "Contact", render: (r) => cell(r.phone || "-", r.email) },
    { label: "Address", render: (r) => esc(r.address || "-") },
    { label: "Products", sort: "products", num: true, render: (r) => fmt.num(r.product_count) },
    { label: "Status", render: (r) => activeBadge(r.is_active) },
  ],
  fields: [
    { name: "name", label: "Supplier name", required: true, maxlength: 100, full: true },
    { name: "contact_person", label: "Contact person", maxlength: 80 },
    { name: "phone", label: "Phone", pattern: "[0-9+\\-\\s()]{7,15}", maxlength: 15, placeholder: "9840012345" },
    { name: "email", label: "Email", type: "email", maxlength: 120, full: true },
    { name: "address", label: "Address", type: "textarea", rows: 2, maxlength: 200, full: true },
    { name: "is_active", label: "Active supplier", type: "checkbox", full: true },
  ],
});

/* ------------------------------------------------------------ warehouses */
const WarehousesPage = createListPage({
  key: "warehouses", title: "Warehouses", subtitle: "Storage locations and their capacity", itemName: "warehouse", addLabel: "Add warehouse",
  endpoint: "/warehouses", searchPlaceholder: "Search name, code or location...", defaultSort: "name", canWrite: isManager,
  toForm: toBool, defaults: { is_active: true }, filters: [ACTIVE_FILTER],
  columns: [
    { label: "Warehouse", sort: "name", render: (r) => cell(r.name, r.code) },
    { label: "Location", render: (r) => esc(r.location) },
    { label: "Capacity", sort: "capacity", num: true, render: (r) => fmt.num(r.capacity) },
    { label: "Utilisation", sort: "used", render: (r) => {
      const pct = Math.min(100, r.used / r.capacity * 100);
      const color = pct > 85 ? "var(--red)" : pct > 65 ? "#f0a020" : "#2fae7b";
      return `<span class="stock-bar"><i style="width:${pct}%;background:${color}"></i></span>${fmt.num(r.used)} units (${pct.toFixed(0)}%)`;
    } },
    { label: "Products", num: true, render: (r) => fmt.num(r.product_count) },
    { label: "Status", render: (r) => activeBadge(r.is_active) },
  ],
  fields: [
    { name: "code", label: "Code", required: true, maxlength: 10, pattern: "[A-Za-z0-9\\-]{2,10}", placeholder: "e.g. HYD-01", help: "2-10 letters, numbers or -" },
    { name: "capacity", label: "Capacity (units)", type: "number", required: true, min: 1, step: 1 },
    { name: "name", label: "Name", required: true, maxlength: 80, full: true },
    { name: "location", label: "Location", required: true, maxlength: 150, full: true },
    { name: "is_active", label: "Active warehouse", type: "checkbox", full: true },
  ],
});

/* ------------------------------------------------------------ stock levels */
const StockPage = createListPage({
  key: "stock", title: "Stock levels", subtitle: "Quantity of every product in every warehouse", itemName: "stock",
  endpoint: "/stock", searchPlaceholder: "Search product or SKU...", defaultSort: "product",
  filters: [
    { name: "warehouse_id", label: "All warehouses", options: () => Lookup.warehouses() },
    { name: "category_id", label: "All categories", options: Lookup.categories },
    { name: "stock_status", label: "Any level", options: [{ value: "in", label: "In stock here" }, { value: "low", label: "Low (overall)" }, { value: "out", label: "Empty here" }] },
  ],
  columns: [
    { label: "Product", sort: "product", render: (r) => cell(r.product_name, r.sku) },
    { label: "Category", sort: "category", render: (r) => esc(r.category_name) },
    { label: "Warehouse", sort: "warehouse", render: (r) => cell(r.warehouse_name, r.warehouse_code) },
    { label: "Quantity", sort: "quantity", num: true, render: (r) => `<span class="main-text">${fmt.num(r.quantity)}</span> ${esc(r.unit)}` },
    { label: "Value (cost)", sort: "value", num: true, render: (r) => fmt.money(r.value) },
    { label: "Status", render: (r) => (r.stock_status === "out" ? badge("Empty", "red") : stockBadge(r.stock_status)) },
  ],
  exportCsv: [["SKU", "sku"], ["Product", "product_name"], ["Category", "category_name"], ["Warehouse", "warehouse_name"], ["Quantity", "quantity"], ["Value at cost", "value"]],
  perPage: 12,
});

/* ------------------------------------------------------------ transactions */
const TYPE_OPTIONS = [
  { value: "IN", label: "Stock In - purchase / goods receipt" },
  { value: "OUT", label: "Stock Out - sale / issue" },
  { value: "TRANSFER", label: "Transfer between warehouses" },
  { value: "ADJUSTMENT", label: "Adjustment - damage / count correction" },
];

function showTransaction(r) {
  const m = openModal({ title: `${r.ref_no} - ${TYPE_LABEL[r.type]}`, size: "md", html: `
    <div class="detail-grid">
      <div><span>Status</span>${statusBadge(r.status)}</div>
      <div><span>Product</span><b>${esc(r.product_name)}</b><div class="sub-text">${esc(r.sku)}</div></div>
      <div><span>Quantity</span><b>${signedQty(r)} ${esc(r.unit)}</b></div>
      <div><span>${r.type === "TRANSFER" ? "From" : "Warehouse"}</span><b>${esc(r.warehouse_name)}</b></div>
      ${r.to_warehouse_name ? `<div><span>To</span><b>${esc(r.to_warehouse_name)}</b></div>` : ""}
      <div><span>Unit price</span><b>${fmt.money(r.unit_price)}</b></div>
      <div><span>Total value</span><b>${fmt.money(r.value)}</b></div>
      <div><span>Requested by</span><b>${esc(r.created_by_name)}</b><div class="sub-text">${fmt.datetime(r.created_at)}</div></div>
      ${r.reviewed_by_name ? `<div><span>${r.status === "COMPLETED" ? "Approved by" : "Closed by"}</span><b>${esc(r.reviewed_by_name)}</b><div class="sub-text">${fmt.datetime(r.reviewed_at)}</div></div>` : ""}
    </div>
    ${r.note ? `<h4>Note</h4><p style="margin:0">${esc(r.note)}</p>` : ""}
    ${r.review_note ? `<h4>Review note</h4><p style="margin:0">${esc(r.review_note)}</p>` : ""}` });
  return m;
}

async function txAction(ctx, label, fn, okMessage) {
  try { await fn(); toast(okMessage); App.refreshBadges(); ctx.reload(); }
  catch (err) { toast(err.message, "error"); }
}

const TransactionsPage = createListPage({
  key: "transactions", title: "Transactions", subtitle: "Every stock movement. Requests stay pending until a manager approves them.",
  itemName: "transaction", addLabel: "New transaction", endpoint: "/transactions", searchPlaceholder: "Search reference, product, note...",
  defaultSort: "created", defaultOrder: "desc", dateFilter: true, canWrite: () => true, modalSize: "md",
  savedMessage: (tx, editing) => (editing ? "Transaction updated." : tx.status === "COMPLETED" ? `${tx.ref_no} posted - stock updated.` : `${tx.ref_no} submitted for approval.`),
  rowLabel: (r) => r.ref_no,
  defaults: (u) => ({ type: "IN", auto_approve: isManager(u) }),
  filters: [
    { name: "type", label: "All types", options: Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label })) },
    { name: "status", label: "All statuses", options: ["PENDING", "COMPLETED", "REJECTED", "CANCELLED"].map((s) => ({ value: s, label: s[0] + s.slice(1).toLowerCase() })) },
    { name: "warehouse_id", label: "All warehouses", options: () => Lookup.warehouses() },
  ],
  columns: [
    { label: "Reference", sort: "created", render: (r) => cell(r.ref_no, fmt.datetime(r.created_at)) },
    { label: "Type", sort: "type", render: (r) => typeBadge(r.type) },
    { label: "Product", sort: "product", render: (r) => cell(r.product_name, r.sku) },
    { label: "Warehouse", sort: "warehouse", render: (r) => cell(r.warehouse_name, r.to_warehouse_name ? "→ " + r.to_warehouse_name : "") },
    { label: "Qty", sort: "quantity", num: true, render: (r) => signedQty(r) },
    { label: "Value", sort: "value", num: true, render: (r) => fmt.money(r.value) },
    { label: "Status", sort: "status", render: (r) => `${statusBadge(r.status)}<div class="sub-text">${esc(r.created_by_name)}</div>` },
  ],
  canEdit: (r, u) => r.status === "PENDING" && (isManager(u) || r.created_by === u.id),
  canDelete: (r, u) => r.status !== "COMPLETED" && (isManager(u) || (r.created_by === u.id && r.status === "PENDING")),
  rowActions: [
    { label: "Details", run: (r) => showTransaction(r) },
    { label: "Approve", tone: "good", show: (r, u) => r.status === "PENDING" && isManager(u),
      run: async (r, ctx) => {
        const ok = await confirmDialog({ title: "Approve transaction?", confirmText: "Approve & post",
          message: `Post <b>${esc(r.ref_no)}</b>? Stock will be updated immediately (${esc(TYPE_LABEL[r.type])}, ${fmt.num(Math.abs(r.quantity))} ${esc(r.unit)} of ${esc(r.product_name)}).` });
        if (ok) txAction(ctx, "approve", () => API.post(`/transactions/${r.id}/approve`), `${r.ref_no} approved - stock updated.`);
      } },
    { label: "Reject", tone: "danger", show: (r, u) => r.status === "PENDING" && isManager(u),
      run: async (r, ctx) => {
        const reason = await promptDialog({ title: `Reject ${r.ref_no}`, label: "Reason for rejection", submitLabel: "Reject" });
        if (reason) txAction(ctx, "reject", () => API.post(`/transactions/${r.id}/reject`, { note: reason }), `${r.ref_no} rejected.`);
      } },
    { label: "Cancel", show: (r, u) => r.status === "PENDING" && (isManager(u) ? false : r.created_by === u.id),
      run: async (r, ctx) => {
        const ok = await confirmDialog({ title: "Cancel request?", confirmText: "Cancel request", danger: true, message: `Cancel your pending request <b>${esc(r.ref_no)}</b>?` });
        if (ok) txAction(ctx, "cancel", () => API.post(`/transactions/${r.id}/cancel`), `${r.ref_no} cancelled.`);
      } },
  ],
  exportCsv: [["Reference", "ref_no"], ["Date", (r) => fmt.datetime(r.created_at)], ["Type", "type"], ["SKU", "sku"], ["Product", "product_name"],
    ["Warehouse", "warehouse_name"], ["To warehouse", "to_warehouse_name"], ["Quantity", "quantity"], ["Unit price", "unit_price"],
    ["Value", "value"], ["Status", "status"], ["Requested by", "created_by_name"], ["Note", "note"]],
  fields: (user, mode) => [
    { name: "type", label: "Transaction type", type: "select", required: true, options: TYPE_OPTIONS, full: true },
    { name: "product_id", label: "Product", type: "select", required: true, full: true, options: withBlank(() => Lookup.products({ active: 1 }), "Select product") },
    { name: "warehouse_id", label: "Warehouse", type: "select", required: true, options: withBlank(() => Lookup.warehouses({ active: 1 }), "Select warehouse"),
      labelFn: (v) => ({ IN: "Receive into warehouse", OUT: "Issue from warehouse", TRANSFER: "From warehouse" }[v.type] || "Warehouse") },
    { name: "to_warehouse_id", label: "To warehouse", type: "select", required: true, showIf: (v) => v.type === "TRANSFER",
      options: withBlank(() => Lookup.warehouses({ active: 1 }), "Select destination") },
    { name: "quantity", label: "Quantity", type: "number", required: true, step: 1, help: "Whole number. For adjustments, use a negative number to remove stock." },
    { name: "unit_price", label: "Unit price (INR)", type: "number", min: 0, step: "0.01", help: "Optional - defaults to the product price" },
    { name: "note", label: "Note / reason", type: "textarea", full: true, maxlength: 300, rows: 2, help: "Required for adjustments (e.g. damaged, audit correction)" },
    ...(mode === "create" && isManager(user) ? [{ name: "auto_approve", label: "Approve & post immediately (skip approval step)", type: "checkbox", full: true }] : []),
  ],
});

/* ------------------------------------------------------------ users (admin) */
const UsersPage = createListPage({
  key: "users", title: "Users", subtitle: "Who can sign in and what they can do", itemName: "user", addLabel: "Add user",
  endpoint: "/users", searchPlaceholder: "Search name or username...", defaultSort: "name", modalSize: "md",
  canWrite: (u) => u.role === "admin", toForm: toBool, defaults: { role: "staff", is_active: true },
  rowLabel: (r) => `${r.full_name} (${r.username})`, canDelete: (r, u) => r.id !== u.id,
  filters: [{ name: "role", label: "All roles", options: [{ value: "admin", label: "Admin" }, { value: "manager", label: "Manager" }, { value: "staff", label: "Staff" }] }, ACTIVE_FILTER],
  columns: [
    { label: "Name", sort: "name", render: (r) => cell(r.full_name, "@" + r.username) },
    { label: "Role", sort: "role", render: (r) => badge(r.role[0].toUpperCase() + r.role.slice(1), r.role === "admin" ? "violet" : r.role === "manager" ? "blue" : "gray") },
    { label: "Status", render: (r) => activeBadge(r.is_active) },
    { label: "Created", sort: "created", render: (r) => fmt.date(r.created_at) },
  ],
  fields: (user, mode) => [
    { name: "full_name", label: "Full name", required: true, maxlength: 80, full: true },
    { name: "username", label: "Username", required: true, minlength: 3, maxlength: 30, pattern: "[A-Za-z0-9_.]+", readonly: mode === "edit", autocomplete: "off", help: mode === "edit" ? "Username cannot be changed" : "Letters, numbers, _ and ." },
    { name: "role", label: "Role", type: "select", required: true, options: [{ value: "staff", label: "Staff - create requests" }, { value: "manager", label: "Manager - approve & manage data" }, { value: "admin", label: "Admin - everything" }] },
    { name: "password", label: mode === "edit" ? "New password" : "Password", type: "password", required: mode === "create", minlength: 6, maxlength: 64, autocomplete: "new-password", help: mode === "edit" ? "Leave blank to keep the current password" : "At least 6 characters", full: true },
    { name: "is_active", label: "Account active", type: "checkbox", full: true },
  ],
});
