/* App shell: login, routing, navigation. */
const ICONS = {
  grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  package: '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
  tag: '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
  truck: '<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
  home: '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  layers: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
  repeat: '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
};
const icon = (n) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]}</svg>`;

const App = {
  user: null,
  nav: [
    { group: "Overview", items: [{ id: "dashboard", title: "Dashboard", icon: "grid", page: DashboardPage }] },
    { group: "Catalogue", items: [
      { id: "products", title: "Products", icon: "package", page: ProductsPage },
      { id: "categories", title: "Categories", icon: "tag", page: CategoriesPage },
      { id: "suppliers", title: "Suppliers", icon: "truck", page: SuppliersPage }] },
    { group: "Warehouse", items: [
      { id: "warehouses", title: "Warehouses", icon: "home", page: WarehousesPage },
      { id: "stock", title: "Stock levels", icon: "layers", page: StockPage },
      { id: "transactions", title: "Transactions", icon: "repeat", page: TransactionsPage }] },
    { group: "Administration", items: [{ id: "users", title: "Users", icon: "users", page: UsersPage, roles: ["admin"] }] },
  ],

  routeFor(id) {
    for (const g of this.nav) for (const it of g.items) if (it.id === id && (!it.roles || it.roles.includes(this.user.role))) return it;
    return null;
  },

  buildNav() {
    $("#nav").innerHTML = this.nav.map((g) => {
      const items = g.items.filter((it) => !it.roles || it.roles.includes(this.user.role));
      if (!items.length) return "";
      return `<div class="group">${g.group}</div>` + items.map((it) =>
        `<a href="#/${it.id}" data-route="${it.id}">${icon(it.icon)}<span>${it.title}</span>${it.id === "transactions" ? '<span class="count" id="pending-count" hidden></span>' : ""}</a>`).join("");
    }).join("");
  },

  async refreshBadges() {
    try {
      const res = await API.get("/transactions", { status: "PENDING", per_page: 1 });
      const el = $("#pending-count");
      if (el) { el.textContent = res.total; el.hidden = !res.total; }
    } catch (e) { /* non-critical */ }
  },

  async route() {
    if (!this.user) return;
    const [path, qs] = (location.hash.replace(/^#\/?/, "") || "dashboard").split("?");
    const item = this.routeFor(path) || this.routeFor("dashboard");
    if (!this.routeFor(path)) { history.replaceState(null, "", "#/dashboard"); }
    const query = Object.fromEntries(new URLSearchParams(qs || ""));
    document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === item.id));
    $("#page-title").textContent = item.title;
    document.title = `${item.title} - StockPilot`;
    closeMenu();
    const page = $("#page");
    try { await item.page.render(page, query); }
    catch (err) { page.innerHTML = `<div class="load-error">Could not load this page: ${esc(err.message)}</div>`; }
    window.scrollTo(0, 0);
  },

  start(user) {
    this.user = user;
    $("#login-view").hidden = true;
    $("#app-view").hidden = false;
    $("#user-name").textContent = user.full_name;
    $("#user-role").textContent = user.role;
    $("#user-avatar").textContent = user.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
    this.buildNav();
    this.refreshBadges();
    this.route();
  },

  showLogin(message) {
    this.user = null;
    API.setToken(null);
    $("#app-view").hidden = true;
    $("#login-view").hidden = false;
    $("#page").innerHTML = "";
    const form = $("#login-form");
    form.reset();
    clearErrors(form);
    if (message) { const fe = $(".form-error", form); fe.textContent = message; fe.hidden = false; }
    $("#l_username").focus();
  },
};

/* ---------------------------------------------------------------- mobile menu */
function closeMenu() { $("#sidebar").classList.remove("open"); $("#nav-backdrop").classList.remove("show"); }
$("#btn-menu").onclick = () => { $("#sidebar").classList.toggle("open"); $("#nav-backdrop").classList.toggle("show"); };
$("#nav-backdrop").onclick = closeMenu;

/* ---------------------------------------------------------------- login / logout */
$("#btn-logout").innerHTML = icon("logout");
$("#btn-logout").onclick = () => App.showLogin();
API.onUnauthorized(() => { if (App.user) App.showLogin("Your session has ended. Please sign in again."); });

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  clearErrors(form);
  if (!validateForm(form)) return;
  const btn = $("button[type=submit]", form);
  btn.disabled = true;
  try {
    const res = await API.post("/auth/login", { username: form.username.value, password: form.password.value });
    API.setToken(res.token);
    location.hash = "#/dashboard";
    App.start(res.user);
  } catch (err) {
    showErrors(form, err.details);
    const fe = $(".form-error", form);
    fe.textContent = err.message;
    fe.hidden = false;
  } finally { btn.disabled = false; }
});

$("#btn-password").onclick = () => openFormModal({
  title: "Change password", size: "sm", submitLabel: "Update password",
  fields: [
    { name: "current_password", label: "Current password", type: "password", required: true, full: true, autocomplete: "current-password" },
    { name: "new_password", label: "New password", type: "password", required: true, minlength: 6, maxlength: 64, full: true, autocomplete: "new-password", help: "At least 6 characters" },
    { name: "confirm_password", label: "Confirm new password", type: "password", required: true, full: true, autocomplete: "new-password" },
  ],
  onSubmit: async (v) => {
    if (v.new_password !== v.confirm_password) throw new API.ApiError("Passwords do not match.", 0, { confirm_password: "Passwords do not match" });
    await API.post("/auth/change-password", { current_password: v.current_password, new_password: v.new_password });
    toast("Password changed.");
  },
});

window.addEventListener("hashchange", () => App.route());

/* ---------------------------------------------------------------- boot */
(async function boot() {
  if (!API.hasToken()) return App.showLogin();
  try {
    const { user } = await API.get("/auth/me");
    App.start(user);
  } catch (err) {
    App.showLogin(err.status === 0 ? err.message : "");
  }
})();
