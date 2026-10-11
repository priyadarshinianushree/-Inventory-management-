/* Dashboard: KPIs, charts, alerts, recent activity. */
const DashboardPage = {
  async render(container) {
    container.innerHTML = '<div class="loading">Loading dashboard...</div>';
    let d;
    try { d = await API.get("/dashboard"); }
    catch (err) { container.innerHTML = `<div class="load-error">${esc(err.message)}</div>`; return; }
    const t = d.totals;

    const kpi = (label, value, hint, tone = "", href = "") =>
      `<${href ? `a href="${href}"` : "div"} class="card kpi ${tone}"><div class="label">${label}</div><div class="value">${value}</div><div class="hint">${hint}</div></${href ? "a" : "div"}>`;

    const maxCat = Math.max(1, ...d.categories.map((c) => c.value));
    const catBars = d.categories.map((c) => `
      <div class="bar-row" title="${esc(c.name)}: ${fmt.num(c.units)} units in ${c.products} products">
        <div class="name">${esc(c.name)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(c.value / maxCat * 100).toFixed(1)}%"></div></div>
        <div class="val">${fmt.money(c.value)}</div></div>`).join("");

    const whBars = d.warehouses.map((w) => {
      const pct = Math.min(100, w.used / w.capacity * 100);
      const tone = pct > 85 ? "bad" : pct > 65 ? "warn" : "ok";
      return `<div class="bar-row" title="${fmt.num(w.used)} of ${fmt.num(w.capacity)} units">
        <div class="name">${esc(w.name)}</div>
        <div class="bar-track"><div class="bar-fill ${tone}" style="width:${pct.toFixed(1)}%"></div></div>
        <div class="val">${pct.toFixed(0)}% full</div></div>`;
    }).join("");

    const lowRows = d.low_stock.length ? d.low_stock.map((p) => `<tr>
        <td><div class="main-text">${esc(p.name)}</div><div class="sub-text">${esc(p.sku)} &middot; ${esc(p.category_name)}</div></td>
        <td class="num">${fmt.num(p.qty)} ${esc(p.unit)}</td><td class="num">${fmt.num(p.reorder_level)}</td>
        <td>${p.qty === 0 ? badge("Out of stock", "red") : badge("Low stock", "amber")}</td></tr>`).join("")
      : `<tr><td colspan="4" class="empty">All products are above their reorder level.</td></tr>`;

    const recentRows = d.recent.map((r) => `<tr>
        <td><div class="main-text">${esc(r.ref_no)}</div><div class="sub-text">${fmt.datetime(r.created_at)}</div></td>
        <td>${typeBadge(r.type)}</td>
        <td><div>${esc(r.product_name)}</div><div class="sub-text">${esc(r.warehouse_name)}</div></td>
        <td class="num">${signedQty(r)}</td><td>${statusBadge(r.status)}</td></tr>`).join("");

    container.innerHTML = `
      <div class="page-head"><div><h2>Welcome back, ${esc(App.user.full_name.split(" ")[0])}</h2>
        <p>Here is what is happening across your ${t.warehouses} warehouses today.</p></div></div>
      <div class="grid kpis">
        ${kpi("Active products", fmt.num(t.products), `${t.categories} categories &middot; ${t.suppliers} suppliers`, "", "#/products")}
        ${kpi("Units in stock", fmt.num(t.units), `Across ${t.warehouses} warehouses`, "", "#/stock")}
        ${kpi("Inventory value", fmt.money(t.stock_value), `Retail value ${fmt.money(t.retail_value)}`, "ok")}
        ${kpi("Low stock", t.low_stock, "At or below reorder level", t.low_stock ? "warn" : "ok", "#/products?stock_status=low")}
        ${kpi("Out of stock", t.out_of_stock, "Needs immediate restock", t.out_of_stock ? "bad" : "ok", "#/products?stock_status=out")}
        ${kpi("Pending approvals", t.pending, "Stock requests waiting", t.pending ? "warn" : "ok", "#/transactions?status=PENDING")}
      </div>
      <div class="grid cols-2">
        <div class="card card-pad"><h3>Stock movement - last 14 days</h3><div class="sub">Units received vs. units issued (completed transactions)</div>
          <div class="legend"><span><i style="background:#2fae7b"></i>Stock in</span><span><i style="background:#3454d1"></i>Stock out</span></div>
          ${trendChart(d.trend)}</div>
        <div class="card card-pad"><h3>Inventory value by category</h3><div class="sub">At cost price</div>${catBars}</div>
      </div>
      <div class="grid cols-2">
        <div class="card card-pad"><h3>Warehouse utilisation</h3><div class="sub">Units stored vs. capacity</div>${whBars}</div>
        <div class="card"><div class="card-pad" style="padding-bottom:6px"><h3>Restock alerts</h3><div class="sub" style="margin:0">Products at or below reorder level</div></div>
          <div class="table-wrap"><table><thead><tr><th>Product</th><th class="num">In stock</th><th class="num">Reorder at</th><th>Status</th></tr></thead><tbody>${lowRows}</tbody></table></div></div>
      </div>
      <div class="card"><div class="card-pad" style="padding-bottom:6px"><h3>Recent transactions</h3><div class="sub" style="margin:0">Latest stock movements - <a href="#/transactions">view all</a></div></div>
        <div class="table-wrap"><table><thead><tr><th>Reference</th><th>Type</th><th>Product</th><th class="num">Qty</th><th>Status</th></tr></thead><tbody>${recentRows}</tbody></table></div></div>`;
  },
};

function trendChart(data) {
  const W = 640, H = 220, pad = { l: 34, r: 8, t: 10, b: 26 };
  const max = Math.max(10, ...data.map((d) => Math.max(d.in, d.out)));
  const nice = Math.ceil(max / 5) * 5;
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b, step = iw / data.length, bw = Math.min(14, step / 2.6);
  let g = "";
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + ih - (ih * i) / 4;
    g += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}" stroke="#e8ecf3"/><text x="${pad.l - 6}" y="${y + 3}" text-anchor="end">${Math.round((nice * i) / 4)}</text>`;
  }
  data.forEach((d, i) => {
    const cx = pad.l + step * i + step / 2;
    const hin = (d.in / nice) * ih, hout = (d.out / nice) * ih;
    const dt = new Date(d.date + "T00:00:00");
    g += `<rect x="${cx - bw - 1}" y="${pad.t + ih - hin}" width="${bw}" height="${hin}" rx="2" fill="#2fae7b"><title>${d.date}: ${d.in} units in</title></rect>
          <rect x="${cx + 1}" y="${pad.t + ih - hout}" width="${bw}" height="${hout}" rx="2" fill="#3454d1"><title>${d.date}: ${d.out} units out</title></rect>`;
    if (i % 2 === 0) g += `<text x="${cx}" y="${H - 8}" text-anchor="middle">${dt.getDate()} ${dt.toLocaleString("en", { month: "short" })}</text>`;
  });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Stock in and out for the last 14 days">${g}</svg>`;
}
