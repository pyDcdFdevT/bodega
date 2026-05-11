const API_BASE = "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = isJson ? payload.detail || payload.message : payload;
    throw new Error(detail || "Error inesperado en la solicitud");
  }

  return payload;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) =>
    request(path, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  put: (path, body) =>
    request(path, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  delete: (path) =>
    request(path, {
      method: "DELETE",
    }),
};

export function formatNumber(value, decimals = 3) {
  return Number(value || 0).toFixed(decimals);
}

export function formatMoney(value, mode = "oro") {
  if (mode === "reales") {
    return `R$ ${formatNumber(value, 2)}`;
  }
  return formatNumber(value, 3);
}

export function formatRate(value) {
  return formatNumber(value, 3);
}

export function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("es-ES", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

export function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  window.setTimeout(() => {
    toast.remove();
  }, 3200);
}

export function renderEmptyRow(columns, text) {
  return `<tr><td colspan="${columns}"><div class="empty-state">${text}</div></td></tr>`;
}

export function setOptions(select, items, labelBuilder) {
  const previousValue = select.value;
  const options = items
    .map((item) => `<option value="${item.id}">${labelBuilder(item)}</option>`)
    .join("");
  select.innerHTML = `<option value="">Seleccione...</option>${options}`;
  if ([...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  }
}
