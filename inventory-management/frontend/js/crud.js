/* Generic, config-driven list page: search + filters + sortable columns + pagination + add/edit/delete. */
function createListPage(cfg) {
  return {
    async render(container, query = {}) {
      const user = App.user;
      const canWrite = cfg.canWrite ? cfg.canWrite(user) : false;
      const state = { q: query.q || "", page: 1, sort: cfg.defaultSort, order: cfg.defaultOrder || "asc", filters: {}, items: [], seq: 0 };
      const filters = [];
      for (const f of cfg.filters || []) {
        state.filters[f.name] = query[f.name] ?? "";
        const options = typeof f.options === "function" ? await f.options() : f.options;
        filters.push({ ...f, options });
      }
      const columns = typeof cfg.columns === "function" ? cfg.columns(user) : cfg.columns;

      container.innerHTML = `
        <div class="page-head">
          <div><h2>${esc(cfg.title)}</h2><p>${esc(cfg.subtitle || "")}</p></div>
          <div class="actions">
            ${cfg.exportCsv ? '<button class="btn" id="btn-export">Export CSV</button>' : ""}
            ${canWrite && cfg.addLabel ? `<button class="btn primary" id="btn-add">+ ${esc(cfg.addLabel)}</button>` : ""}
          </div>
        </div>
        <div class="card">
          <div class="toolbar">
            <input type="search" id="f-q" placeholder="${esc(cfg.searchPlaceholder || "Search...")}" value="${esc(state.q)}">
            ${filters.map((f) => `<select data-filter="${f.name}" aria-label="${esc(f.label)}">
                <option value="">${esc(f.label)}</option>
                ${f.options.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(state.filters[f.name]) ? "selected" : ""}>${esc(o.label)}</option>`).join("")}
              </select>`).join("")}
            ${cfg.dateFilter ? `<input type="date" data-filter="date_from" title="From date" value="${esc(query.date_from || "")}">
              <input type="date" data-filter="date_to" title="To date" value="${esc(query.date_to || "")}">` : ""}
            <button class="btn" id="btn-reset">Reset</button>
            <span class="spacer"></span><span class="result-count" id="result-count"></span>
          </div>
          <div class="table-wrap"><table>
            <thead><tr>${columns.map((c) => `<th class="${c.num ? "num " : ""}${c.sort ? "sortable" : ""}" ${c.sort ? `data-sort="${c.sort}"` : ""}>${esc(c.label)}<span class="arrow"></span></th>`).join("")}<th></th></tr></thead>
            <tbody></tbody>
          </table></div>
          <div class="pager"></div>
        </div>`;

      const tbody = $("tbody", container);
      const pager = $(".pager", container);
      if (cfg.dateFilter) { state.filters.date_from = query.date_from || ""; state.filters.date_to = query.date_to || ""; }

      const colSpan = columns.length + 1;
      const params = () => ({ q: state.q, page: state.page, per_page: cfg.perPage || 10, sort: state.sort, order: state.order, ...state.filters, ...(cfg.params || {}) });

      function updateArrows() {
        container.querySelectorAll("th.sortable").forEach((th) => {
          $(".arrow", th).textContent = th.dataset.sort === state.sort ? (state.order === "asc" ? "▲" : "▼") : "";
        });
      }

      const actionsFor = (row) => {
        const list = [...(cfg.rowActions || [])];
        if (canWrite && cfg.fields && (!cfg.canEdit || cfg.canEdit(row, user))) list.push({ label: "Edit", run: (r) => openForm(r) });
        if (canWrite && cfg.canDelete !== false && (!cfg.canDelete || cfg.canDelete(row, user)) && cfg.deletable !== false)
          list.push({ label: "Delete", tone: "danger", run: (r) => remove(r) });
        return list.filter((a) => !a.show || a.show(row, user));
      };

      async function load() {
        const seq = ++state.seq;
        tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">Loading...</td></tr>`;
        updateArrows();
        try {
          const res = await API.get(cfg.endpoint, params());
          if (seq !== state.seq) return;
          state.items = res.items;
          state.page = res.page;
          $("#result-count", container).textContent = `${fmt.num(res.total)} ${res.total === 1 ? "result" : "results"}`;
          if (!res.items.length) {
            tbody.innerHTML = `<tr><td colspan="${colSpan}" class="empty">${esc(cfg.emptyText || "Nothing found.")} Try changing the search or filters.</td></tr>`;
          } else {
            tbody.innerHTML = res.items.map((row, idx) => {
              const acts = actionsFor(row);
              return `<tr data-idx="${idx}">${columns.map((c) => `<td class="${c.num ? "num" : ""} ${c.class || ""}">${c.render(row)}</td>`).join("")}
                <td class="actions">${acts.map((a, i) => `<button class="btn sm ${a.tone || ""}" data-act="${i}">${esc(a.label)}</button>`).join("")}</td></tr>`;
            }).join("");
            tbody.querySelectorAll("tr").forEach((tr) => {
              const row = state.items[Number(tr.dataset.idx)];
              const acts = actionsFor(row);
              tr.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => acts[Number(b.dataset.act)].run(row, ctx)));
            });
          }
          renderPager(pager, res, (p) => { state.page = p; load(); });
        } catch (err) {
          if (seq !== state.seq) return;
          tbody.innerHTML = `<tr><td colspan="${colSpan}" class="load-error">${esc(err.message)}<br><button class="btn sm" id="btn-retry" style="margin-top:10px">Retry</button></td></tr>`;
          $("#btn-retry", container).onclick = load;
          pager.innerHTML = "";
        }
      }

      const ctx = { reload: load, user };
      const fieldsFor = (mode, row) => (typeof cfg.fields === "function" ? cfg.fields(user, mode, row) : cfg.fields);

      async function openForm(row) {
        const editing = !!row;
        await openFormModal({
          title: editing ? `Edit ${cfg.itemName}` : `Add ${cfg.itemName}`,
          fields: fieldsFor(editing ? "edit" : "create", row),
          values: editing ? (cfg.toForm ? cfg.toForm(row) : row) : (typeof cfg.defaults === "function" ? cfg.defaults(user) : cfg.defaults || {}),
          submitLabel: editing ? "Save changes" : `Add ${cfg.itemName}`,
          size: cfg.modalSize,
          onSubmit: async (values) => {
            const payload = cfg.toPayload ? cfg.toPayload(values, editing) : values;
            const saved = editing ? await API.put(`${cfg.endpoint}/${row.id}`, payload) : await API.post(cfg.endpoint, payload);
            toast(cfg.savedMessage ? cfg.savedMessage(saved, editing) : `${cfg.itemName[0].toUpperCase() + cfg.itemName.slice(1)} ${editing ? "updated" : "added"}.`);
            App.refreshBadges();
            load();
          },
        });
      }

      async function remove(row) {
        const ok = await confirmDialog({
          title: `Delete ${cfg.itemName}?`, danger: true, confirmText: "Delete",
          message: `<b>${esc(cfg.rowLabel ? cfg.rowLabel(row) : row.name)}</b> will be permanently deleted. This cannot be undone.`,
        });
        if (!ok) return;
        try {
          await API.del(`${cfg.endpoint}/${row.id}`);
          toast(`${cfg.itemName[0].toUpperCase() + cfg.itemName.slice(1)} deleted.`);
          App.refreshBadges();
          load();
        } catch (err) { toast(err.message, "error"); }
      }
      ctx.openForm = openForm;

      // ---- events
      $("#f-q", container).addEventListener("input", debounce((e) => { state.q = e.target.value; state.page = 1; load(); }));
      container.querySelectorAll("[data-filter]").forEach((el) => el.addEventListener("change", () => { state.filters[el.dataset.filter] = el.value; state.page = 1; load(); }));
      $("#btn-reset", container).onclick = () => {
        state.q = ""; state.page = 1; state.sort = cfg.defaultSort; state.order = cfg.defaultOrder || "asc";
        Object.keys(state.filters).forEach((k) => (state.filters[k] = ""));
        $("#f-q", container).value = "";
        container.querySelectorAll("[data-filter]").forEach((el) => (el.value = ""));
        load();
      };
      container.querySelectorAll("th.sortable").forEach((th) => (th.onclick = () => {
        if (state.sort === th.dataset.sort) state.order = state.order === "asc" ? "desc" : "asc";
        else { state.sort = th.dataset.sort; state.order = "asc"; }
        state.page = 1; load();
      }));
      const addBtn = $("#btn-add", container);
      if (addBtn) addBtn.onclick = () => openForm(null);
      const exportBtn = $("#btn-export", container);
      if (exportBtn) exportBtn.onclick = async () => {
        exportBtn.disabled = true;
        try {
          const res = await API.get(cfg.endpoint, { ...params(), page: 1, per_page: 500 });
          downloadCsv(`${cfg.key}-${new Date().toISOString().slice(0, 10)}.csv`, cfg.exportCsv.map((c) => c[0]),
            res.items.map((r) => cfg.exportCsv.map((c) => (typeof c[1] === "function" ? c[1](r) : r[c[1]]))));
        } catch (err) { toast(err.message, "error"); } finally { exportBtn.disabled = false; }
      };

      load();
      return ctx;
    },
  };
}
