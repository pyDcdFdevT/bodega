const API_BASE = "/api";

/** El backend envía fechas en UTC con tzinfo. El frontend convierte a Venezuela (UTC-4) para mostrar. */

/** FastAPI puede devolver `detail` como string o como lista de errores de validación. */
function formatApiErrorDetail(payload, isJson) {
  if (!isJson) {
    return typeof payload === "string" && payload.trim()
      ? payload
      : "Error en la solicitud";
  }
  if (payload == null || typeof payload !== "object") {
    return "Error en la solicitud";
  }
  const d = payload.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = Array.isArray(item.loc)
            ? item.loc.filter((x) => x !== "body" && typeof x === "string").join(".")
            : "";
          return loc ? `${loc}: ${item.msg}` : String(item.msg);
        }
        return typeof item === "string" ? item : JSON.stringify(item);
      })
      .join("; ");
  }
  if (d != null && typeof d === "object") return JSON.stringify(d);
  if (typeof payload.message === "string") return payload.message;
  return "Error en la solicitud";
}

async function request(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(extraHeaders || {}),
    },
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = formatApiErrorDetail(payload, isJson);
    throw new Error(detail || "Error inesperado en la solicitud");
  }

  return payload;
}

export const api = {
  get: (path) => request(path),
  post: (path, body, fetchOptions = {}) =>
    request(path, {
      method: "POST",
      body: JSON.stringify(body),
      ...fetchOptions,
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

export const DECIMALES_ORO = 4;

export function formatNumber(value, decimals = 2) {
  return Number(value || 0).toFixed(decimals);
}

export function formatMoney(value, mode = "oro") {
  if (mode === "reales") {
    return `R$ ${formatNumber(value, 2)}`;
  }
  return formatNumber(value, DECIMALES_ORO);
}

export function formatRate(value) {
  return formatNumber(value, 2);
}

/** Indica si la cadena ISO ya trae zona (Z o ±hh:mm). */
function tieneIndicadorZona(iso) {
  return /[zZ]\s*$/i.test(iso) || /[+-]\d{2}:\d{2}\s*$/.test(iso) || /[+-]\d{2}\d{2}\s*$/.test(iso);
}

/**
 * Instante en el eje temporal correcto: el backend envía UTC.
 * Si el ISO lleva "T" pero sin Z ni offset, el motor lo interpretaría como hora local (p. ej. España);
 * en ese caso se fuerza "Z" para leer con getUTC* el UTC real.
 */
function parseInstanteUtc(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  let s = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}T/.test(s) && !tieneIndicadorZona(s)) {
    s = `${s}Z`;
  }
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) {
    return null;
  }
  return d;
}

/** Venezuela UTC−4: componentes UTC del instante, menos 4 h en el reloj (con arrastre de día vía Date.UTC). */
function partesFechaHoraVenezuela(value) {
  const d = parseInstanteUtc(value);
  if (!d) {
    return null;
  }
  const ms = Date.UTC(
    d.getUTCFullYear(),
    d.getUTCMonth(),
    d.getUTCDate(),
    d.getUTCHours() - 4,
    d.getUTCMinutes(),
    d.getUTCSeconds(),
    d.getUTCMilliseconds()
  );
  const v = new Date(ms);
  const dia = String(v.getUTCDate()).padStart(2, "0");
  const mes = String(v.getUTCMonth() + 1).padStart(2, "0");
  const anio = String(v.getUTCFullYear()).slice(-2);
  const hora = String(v.getUTCHours()).padStart(2, "0");
  const minuto = String(v.getUTCMinutes()).padStart(2, "0");
  return { fecha: `${dia}/${mes}/${anio}`, hora: `${hora}:${minuto}` };
}

/** Fecha y hora: "13/05/26 10:31" (sin coma, sin segundos). Instant UTC del backend → reloj Venezuela (UTC−4). */
export function formatDate(value) {
  const partes = partesFechaHoraVenezuela(value);
  if (!partes) {
    return "-";
  }
  return `${partes.fecha} ${partes.hora}`;
}

/** Solo fecha: "13/05/26" (UTC−4 Venezuela, coherente con formatDate). */
export function formatDateOnly(value) {
  const partes = partesFechaHoraVenezuela(value);
  if (!partes) {
    return "-";
  }
  return partes.fecha;
}

/** Solo hora: "10:31" (UTC−4 Venezuela, coherente con formatDate). */
export function formatTimeOnly(value) {
  const partes = partesFechaHoraVenezuela(value);
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
