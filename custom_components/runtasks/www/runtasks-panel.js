class RunTasksPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.tasks = [];
    this.entryId = null;
    this.editIndex = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._init) return; // avoid re-rendering on every HA state update (keeps form input stable)
    this._init = true;
    this._load();
    this.render();
  }

  async _load() {
    if (!this._hass) return;
    if (!this.entryId) {
      const entries = await this._hass.callWS({ type: "config_entries/get" });
      const entry = entries.find((e) => e.domain === "runtasks");
      if (!entry) {
        this.error = "No RunTasks config entry found";
        this.render();
        return;
      }
      this.entryId = entry.entry_id;
    }
    try {
      const resp = await this._hass.callWS({ type: "runtasks/list", entry_id: this.entryId });
      this.tasks = resp.tasks || [];
      this.error = "";
    } catch (e) {
      this.error = e.message || "Failed to load tasks";
    }
    this.render();
  }

  async _saveTasks(tasks) {
    const resp = await this._hass.callWS({ type: "runtasks/save", entry_id: this.entryId, tasks });
    this.tasks = resp.tasks || [];
    this.editIndex = null;
    this.error = "";
    this.render();
  }

  _onAdd(e) {
    e.preventDefault();
    const form = this.shadowRoot.querySelector("form");
    const task = {
      name: form.name.value.trim(),
      list: form.list.value.trim(),
      start_date: form.start_date.value,
      period_days: parseInt(form.period_days.value, 10),
    };
    if (!task.name || !task.list || !task.start_date || !task.period_days || Number.isNaN(task.period_days)) {
      this.error = "All fields required";
      this.render();
      return;
    }
    const tasks = [...this.tasks, task];
    this._saveTasks(tasks).catch((err) => {
      this.error = err.message || "Save failed";
      this.render();
    });
    form.reset();
  }

  _onEdit(idx) {
    this.editIndex = idx;
    this.render();
  }

  _onDelete(idx) {
    const tasks = this.tasks.filter((_, i) => i !== idx);
    this._saveTasks(tasks).catch((err) => {
      this.error = err.message || "Delete failed";
      this.render();
    });
  }

  _onSaveEdit(idx) {
    const row = this.shadowRoot.querySelector(`[data-row="${idx}"]`);
    const task = {
      name: row.querySelector("input[name='name']").value.trim(),
      list: row.querySelector("input[name='list']").value.trim(),
      start_date: row.querySelector("input[name='start_date']").value,
      period_days: parseInt(row.querySelector("input[name='period_days']").value, 10),
    };
    if (!task.name || !task.list || !task.start_date || !task.period_days || Number.isNaN(task.period_days)) {
      this.error = "All fields required";
      this.render();
      return;
    }
    const tasks = this.tasks.map((t, i) => (i === idx ? task : t));
    this._saveTasks(tasks).catch((err) => {
      this.error = err.message || "Save failed";
      this.render();
    });
  }

  async _onRunNow() {
    try {
      await this._hass.callWS({ type: "runtasks/run_now", entry_id: this.entryId });
      this.error = "Triggered";
    } catch (e) {
      this.error = e.message || "Run failed";
    }
    this.render();
  }

  render() {
    if (!this.shadowRoot) return;

    // Preserve add-form input during re-render so we don't wipe user typing.
    const snapshot = (() => {
      const form = this.shadowRoot.querySelector("form");
      if (!form) return null;
      const active = this.shadowRoot.activeElement;
      const activeName = active && form.contains(active) ? active.getAttribute("name") : null;
      return {
        values: {
          name: form.name?.value ?? "",
          start_date: form.start_date?.value ?? "",
          period_days: form.period_days?.value ?? "",
          list: form.list?.value ?? "",
        },
        activeName,
      };
    })();

    const style = `
      :host { display: block; padding: 16px; }
      .card { background: #fff; border-radius: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.15); padding: 16px; }
      h2 { margin: 0 0 12px 0; }
      form { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; align-items: end; margin-bottom: 12px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { padding: 8px; border-bottom: 1px solid #e2e2e2; text-align: left; }
      input, select { width: 100%; padding: 6px 8px; border: 1px solid #cfcfcf; border-radius: 6px; font: inherit; }
      button { padding: 8px 12px; border: none; border-radius: 8px; cursor: pointer; font: inherit; }
      .add { background: #0d9488; color: #fff; }
      .secondary { background: #e5e7eb; color: #111; }
      .danger { background: #dc2626; color: #fff; }
      .row-actions { display: flex; gap: 8px; }
      .footer { margin-top: 16px; display: flex; justify-content: space-between; align-items: center; }
      .error { color: #b91c1c; margin-bottom: 8px; }
    `;

    const rows = this.tasks.map((t, idx) => {
      if (this.editIndex === idx) {
        return `
          <tr data-row="${idx}">
            <td><input name="name" value="${t.name}" /></td>
            <td><input name="start_date" type="date" value="${t.start_date}" /></td>
            <td><input name="period_days" type="number" min="1" value="${t.period_days}" /></td>
            <td><input name="list" value="${t.list}" /></td>
            <td class="row-actions">
              <button class="add" data-action="save" data-idx="${idx}">Save</button>
              <button class="secondary" data-action="cancel" data-idx="${idx}">Cancel</button>
            </td>
          </tr>`;
      }
      return `
        <tr>
          <td>${t.name}</td>
          <td>${t.start_date}</td>
          <td>${t.period_days}</td>
          <td>${t.list}</td>
          <td class="row-actions">
            <button class="secondary" data-action="edit" data-idx="${idx}">Edit</button>
            <button class="danger" data-action="delete" data-idx="${idx}">Delete</button>
          </td>
        </tr>`;
    }).join("");

    const tpl = `
      <style>${style}</style>
      <div class="card">
        <h2>RunTasks</h2>
        ${this.error ? `<div class="error">${this.error}</div>` : ""}
        <form>
          <label>Name<input name="name" placeholder="Task name" /></label>
          <label>Start date<input name="start_date" type="date" /></label>
          <label>Period (days)<input name="period_days" type="number" min="1" /></label>
          <label>List entity<input name="list" placeholder="todo.house_chores" /></label>
          <button class="add" type="submit">Add</button>
        </form>
        <table>
          <thead><tr><th>Name</th><th>Start</th><th>Period</th><th>List</th><th></th></tr></thead>
          <tbody>${rows || `<tr><td colspan="5">No tasks yet</td></tr>`}</tbody>
        </table>
        <div class="footer">
          <div>Tasks add at local midnight daily.</div>
          <button class="secondary" data-action="run-now">Test Now</button>
        </div>
      </div>
    `;

    this.shadowRoot.innerHTML = tpl;

    if (snapshot) {
      const form = this.shadowRoot.querySelector("form");
      if (form) {
        const { values, activeName } = snapshot;
        if (form.name) form.name.value = values.name;
        if (form.start_date) form.start_date.value = values.start_date;
        if (form.period_days) form.period_days.value = values.period_days;
        if (form.list) form.list.value = values.list;
        if (activeName && form[activeName]) {
          form[activeName].focus();
          const len = form[activeName].value.length;
          form[activeName].setSelectionRange(len, len);
        }
      }
    }

    const form = this.shadowRoot.querySelector("form");
    form?.addEventListener("submit", (e) => this._onAdd(e));

    this.shadowRoot.querySelectorAll("button[data-action='edit']").forEach((btn) => {
      btn.addEventListener("click", () => this._onEdit(parseInt(btn.dataset.idx, 10)));
    });
    this.shadowRoot.querySelectorAll("button[data-action='delete']").forEach((btn) => {
      btn.addEventListener("click", () => this._onDelete(parseInt(btn.dataset.idx, 10)));
    });
    this.shadowRoot.querySelectorAll("button[data-action='save']").forEach((btn) => {
      btn.addEventListener("click", () => this._onSaveEdit(parseInt(btn.dataset.idx, 10)));
    });
    this.shadowRoot.querySelectorAll("button[data-action='cancel']").forEach((btn) => {
      btn.addEventListener("click", () => { this.editIndex = null; this.render(); });
    });
    this.shadowRoot.querySelector("button[data-action='run-now']")?.addEventListener("click", () => this._onRunNow());
  }
}

customElements.define("runtasks-panel", RunTasksPanel);
