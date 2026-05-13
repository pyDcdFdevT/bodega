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

export function formatNumber(value, decimals = 2) {
  return Number(value || 0).toFixed(decimals);
}

export function formatMoney(value, mode = "oro") {
  if (mode === "reales") {
    return `R$ ${formatNumber(value, 2)}`;
  }
  return formatNumber(value, 2);
}

export function formatRate(value) {
  return formatNumber(value, 2);
}

function parseFechaLocal(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return null;
  }
  return d;
}

function partesFechaHora(value) {
  const d = parseFechaLocal(value);
  if (!d) {
    return null;
  }
  const dia = String(d.getDate()).padStart(2, "0");
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const anio = String(d.getFullYear()).slice(-2);
  const hora = String(d.getHours()).padStart(2, "0");
  const minuto = String(d.getMinutes()).padStart(2, "0");
  return { fecha: `${dia}/${mes}/${anio}`, hora: `${hora}:${minuto}` };
}

/** Fecha y hora: "13/05/26 10:31" (sin coma, sin segundos). */
export function formatDate(value) {
  const partes = partesFechaHora(value);
  if (!partes) {
    return "-";
  }
  return `${partes.fecha} ${partes.hora}`;
}

/** Solo fecha: "13/05/26". */
export function formatDateOnly(value) {
  const partes = partesFechaHora(value);
  if (!partes) {
    return "-";
  }
  return partes.fecha;
}

/** Solo hora: "10:31". */
export function formatTimeOnly(value) {
  const partes = partesFechaHora(value);
  if (!partes) {
    return "-";
  }
  return partes.hora;
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
