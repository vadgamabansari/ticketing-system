const STATUS_LABELS = { open: "Open", in_progress: "In Progress", resolved: "Resolved" };
const PRIORITY_LABELS = { low: "Low", medium: "Medium", high: "High", urgent: "Urgent" };

let selectedTicketId = null;

// --- helpers -----------------------------------------------------------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatDate(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function showError(message) {
  const banner = document.getElementById("error-banner");
  banner.textContent = message;
  banner.classList.remove("hidden");
  setTimeout(() => banner.classList.add("hidden"), 5000);
}

// --- stats ---------------------------------------------------------------

async function loadStats() {
  try {
    const stats = await apiFetch("/stats");
    const byStatus = Object.fromEntries(stats.by_status.map((r) => [r.status, r.count]));

    const cards = [
      { label: "Total Tickets", value: stats.total_tickets },
      { label: "Total Messages", value: stats.total_messages },
      { label: "Open", value: byStatus.open || 0 },
      { label: "In Progress", value: byStatus.in_progress || 0 },
      { label: "Resolved", value: byStatus.resolved || 0 },
    ];

    const strip = document.getElementById("stats-strip");
    strip.innerHTML = cards
      .map(
        (c) => `
        <div class="stat-card">
          <div class="stat-value">${escapeHtml(String(c.value))}</div>
          <div class="stat-label">${escapeHtml(c.label)}</div>
        </div>`
      )
      .join("");
  } catch (err) {
    showError(err.message);
  }
}

// --- ticket list -----------------------------------------------------------

async function loadTickets() {
  const status = document.getElementById("status-filter").value;
  const query = status ? `?status=${encodeURIComponent(status)}` : "";

  try {
    const tickets = await apiFetch(`/tickets${query}`);
    renderTicketList(tickets);
  } catch (err) {
    showError(err.message);
  }
}

function renderTicketList(tickets) {
  const list = document.getElementById("ticket-list");

  if (tickets.length === 0) {
    list.innerHTML = `<li class="empty-state">No tickets match this filter.</li>`;
    return;
  }

  list.innerHTML = tickets
    .map(
      (t) => `
      <li class="ticket-card ${t.ticket_id === selectedTicketId ? "selected" : ""}" data-id="${t.ticket_id}">
        <h3>${escapeHtml(t.title)}</h3>
        <div class="ticket-meta">
          <span class="badge status-${t.status}">${STATUS_LABELS[t.status] || t.status}</span>
          <span class="badge priority-${t.priority}">${PRIORITY_LABELS[t.priority] || t.priority}</span>
          <span>${escapeHtml(t.category)}</span>
        </div>
        <div class="ticket-meta">
          <span>${escapeHtml(t.created_by)}</span>
          <span>&middot;</span>
          <span>${formatDate(t.created_at)}</span>
        </div>
      </li>`
    )
    .join("");

  list.querySelectorAll(".ticket-card").forEach((card) => {
    card.addEventListener("click", () => selectTicket(Number(card.dataset.id)));
  });
}

// --- ticket detail -----------------------------------------------------------

async function selectTicket(ticketId) {
  selectedTicketId = ticketId;
  document.querySelectorAll(".ticket-card").forEach((card) => {
    card.classList.toggle("selected", Number(card.dataset.id) === ticketId);
  });

  try {
    const { ticket, messages } = await apiFetch(`/tickets/${ticketId}`);
    renderDetail(ticket, messages);
  } catch (err) {
    showError(err.message);
  }
}

function renderDetail(ticket, messages) {
  const pane = document.getElementById("detail-pane");

  pane.innerHTML = `
    <div class="detail-header">
      <div>
        <h2>${escapeHtml(ticket.title)}</h2>
        <div class="ticket-meta">
          <span class="badge priority-${ticket.priority}">${PRIORITY_LABELS[ticket.priority] || ticket.priority}</span>
          <span>${escapeHtml(ticket.category)}</span>
          <span>&middot;</span>
          <span>${escapeHtml(ticket.created_by)}</span>
          <span>&middot;</span>
          <span>${formatDate(ticket.created_at)}</span>
        </div>
      </div>
      <div class="detail-controls">
        <select id="status-select">
          ${Object.entries(STATUS_LABELS)
            .map(
              ([value, label]) =>
                `<option value="${value}" ${value === ticket.status ? "selected" : ""}>${label}</option>`
            )
            .join("")}
        </select>
        <button id="delete-ticket-btn" class="btn btn-danger">Delete</button>
      </div>
    </div>

    <div class="message-list">
      ${
        messages.length === 0
          ? `<p class="empty-state">No messages yet.</p>`
          : messages
              .map(
                (m) => `
              <div class="message-bubble">
                <div class="message-meta">${escapeHtml(m.author)} &middot; ${formatDate(m.created_at)}</div>
                <div>${escapeHtml(m.message_text)}</div>
              </div>`
              )
              .join("")
      }
    </div>

    <form id="new-message-form">
      <textarea id="message-text" placeholder="Add a message..." maxlength="2000" required></textarea>
      <p id="message-error" class="form-error hidden"></p>
      <div class="modal-actions">
        <button type="submit" class="btn btn-primary">Add Message</button>
      </div>
    </form>
  `;

  document.getElementById("status-select").addEventListener("change", (e) => {
    updateStatus(ticket.ticket_id, e.target.value);
  });

  document.getElementById("delete-ticket-btn").addEventListener("click", () => {
    openDeleteConfirm(ticket.ticket_id, ticket.title);
  });

  document.getElementById("new-message-form").addEventListener("submit", (e) => {
    e.preventDefault();
    submitMessage(ticket.ticket_id);
  });
}

async function updateStatus(ticketId, status) {
  try {
    await apiFetch(`/tickets/${ticketId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    await Promise.all([loadTickets(), loadStats(), selectTicket(ticketId)]);
  } catch (err) {
    showError(err.message);
  }
}

async function submitMessage(ticketId) {
  const textarea = document.getElementById("message-text");
  const errorEl = document.getElementById("message-error");
  errorEl.classList.add("hidden");

  try {
    await apiFetch(`/tickets/${ticketId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message_text: textarea.value }),
    });
    await Promise.all([loadStats(), selectTicket(ticketId)]);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

// --- delete confirmation -----------------------------------------------------------

let pendingDeleteId = null;

function openDeleteConfirm(ticketId, title) {
  pendingDeleteId = ticketId;
  document.getElementById("delete-confirm-body").textContent =
    `"${title}" and its messages will be removed from the active list. This cannot be undone from the UI.`;
  document.getElementById("delete-confirm-modal").classList.remove("hidden");
}

function closeDeleteConfirm() {
  pendingDeleteId = null;
  document.getElementById("delete-confirm-modal").classList.add("hidden");
}

async function confirmDelete() {
  if (pendingDeleteId === null) return;
  try {
    await apiFetch(`/tickets/${pendingDeleteId}`, { method: "DELETE" });
    if (selectedTicketId === pendingDeleteId) {
      selectedTicketId = null;
      document.getElementById("detail-pane").innerHTML =
        `<p class="empty-state">Select a ticket to view its messages.</p>`;
    }
    closeDeleteConfirm();
    await Promise.all([loadTickets(), loadStats()]);
  } catch (err) {
    showError(err.message);
  }
}

// --- new ticket modal -----------------------------------------------------------

function openNewTicketModal() {
  document.getElementById("new-ticket-form").reset();
  document.getElementById("new-ticket-error").classList.add("hidden");
  document.getElementById("new-ticket-modal").classList.remove("hidden");
}

function closeNewTicketModal() {
  document.getElementById("new-ticket-modal").classList.add("hidden");
}

async function submitNewTicket(e) {
  e.preventDefault();
  const form = e.target;
  const errorEl = document.getElementById("new-ticket-error");
  errorEl.classList.add("hidden");

  const payload = {
    title: form.title.value,
    priority: form.priority.value,
    category: form.category.value,
  };

  try {
    const ticket = await apiFetch("/tickets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    closeNewTicketModal();
    await Promise.all([loadTickets(), loadStats()]);
    selectTicket(ticket.ticket_id);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

// --- wiring -----------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadTickets();

  document.getElementById("status-filter").addEventListener("change", loadTickets);

  document.getElementById("new-ticket-btn").addEventListener("click", openNewTicketModal);
  document.getElementById("new-ticket-cancel").addEventListener("click", closeNewTicketModal);
  document.getElementById("new-ticket-form").addEventListener("submit", submitNewTicket);

  document.getElementById("delete-cancel").addEventListener("click", closeDeleteConfirm);
  document.getElementById("delete-confirm").addEventListener("click", confirmDelete);
});
