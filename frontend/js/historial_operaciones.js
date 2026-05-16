import { api, formatDate, formatMoney, renderEmptyRow } from "./api.js";

const HISTORIAL_LIMIT = 50;
const DEBOUNCE_MS = 280;

const SECCIONES = [
  { key: "compras", label: "Compras", endpoint: "/historial/compras" },
  { key: "ventas", label: "Ventas", endpoint: "/historial/ventas" },
  { key: "cobros", label: "Cobros / Pagos", endpoint: "/historial/cobros" },
  { key: "salidas", label: "Salidas", endpoint: "/historial/salidas" },
  { key: "gasolina", label: "Gasolina", endpoint: "/historial/gasolina" },
];

const debounceTimers = new Map();

function hoyPartes() {
  const d = new Date();
  return { anio: d.getFullYear(), mes: d.getMonth() + 1, dia: d.getDate() };
}

function llenarSelectAnios(select) {
  const y = hoyPartes().anio;
  const opts = [];
  for (let i = y; i >= y - 5; i -= 1) {
    opts.push(`<option value="${i}">${i}</option>`);
  }
  select.innerHTML = opts.join("");
}

function llenarSelectMeses(select) {
  const nombres = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
  ];
  select.innerHTML = nombres
    .map((nombre, i) => `<option value="${i + 1}">${nombre}</option>`)
    .join("");
}

function llenarSelectDias(select) {
  const opts = ['<option value="">Todo el mes</option>'];
  for (let d = 1; d <= 31; d += 1) {
    opts.push(`<option value="${d}">${d}</option>`);
  }
  select.innerHTML = opts.join("");
}

function leerFiltro(key) {
  const anio = Number(document.getElementById(`hist-${key}-anio`)?.value);
  const mes = Number(document.getElementById(`hist-${key}-mes`)?.value);
  const diaRaw = document.getElementById(`hist-${key}-dia`)?.value;
  const buscar = document.getElementById(`hist-${key}-q`)?.value?.trim() || "";
  const params = new URLSearchParams({ limit: String(HISTORIAL_LIMIT) });
  if (anio) {
    params.set("anio", String(anio));
  }
  if (mes) {
    params.set("mes", String(mes));
  }
  if (diaRaw) {
    params.set("dia", String(diaRaw));
  }
  if (buscar) {
    params.set("buscar", buscar);
  }
  return params.toString();
}

function renderCompras(rows) {
  if (!rows.length) {
    return renderEmptyRow(6, "Sin registros en el periodo.");
  }
  return rows
    .map(
      (r) => `
    <tr>
      <td>#${r.id}</td>
      <td>${formatDate(r.fecha)}</td>
      <td>${r.producto || "—"}</td>
      <td>${r.proveedor || "—"}</td>
      <td>${r.tipo_pago_compra === "credito" ? "Crédito" : "Contado"}</td>
      <td>${formatMoney(r.total_reales, "reales")}</td>
    </tr>`
    )
    .join("");
}

function renderVentas(rows) {
  if (!rows.length) {
    return renderEmptyRow(7, "Sin registros en el periodo.");
  }
  return rows
    .map(
      (r) => `
    <tr>
      <td>#${r.id}</td>
      <td>${formatDate(r.fecha)}</td>
      <td>${r.cliente || "—"}</td>
      <td>${r.productos || "—"}</td>
      <td>${formatMoney(r.total_reales, "reales")}</td>
      <td>${formatMoney(r.total_oro)} g</td>
      <td>${r.estado_pago || "—"}</td>
    </tr>`
    )
    .join("");
}

function renderCobros(rows) {
  if (!rows.length) {
    return renderEmptyRow(6, "Sin registros en el periodo.");
  }
  return rows
    .map(
      (r) => `
    <tr>
      <td>#${r.id}</td>
      <td>${formatDate(r.fecha)}</td>
      <td>#${r.venta_id}</td>
      <td>${r.cliente || "—"}</td>
      <td>${r.tipo_pago || "—"}</td>
      <td>${formatMoney(r.monto_reales_equivalente, "reales")}</td>
    </tr>`
    )
    .join("");
}

function renderSalidas(rows) {
  if (!rows.length) {
    return renderEmptyRow(6, "Sin registros en el periodo.");
  }
  return rows
    .map(
      (r) => `
    <tr>
      <td>#${r.id}</td>
      <td>${formatDate(r.fecha)}</td>
      <td>${r.producto || "—"}</td>
      <td>${r.motivo || "—"}</td>
      <td>${Number(r.cantidad).toFixed(3)}</td>
      <td>${formatMoney(r.valor_oro)} g</td>
    </tr>`
    )
    .join("");
}

function renderGasolina(data) {
  const ventas = (data?.ventas || []).map((v) => ({ ...v, movimiento: v.movimiento || "Venta" }));
  const repos = (data?.reposiciones || []).map((r) => ({
    ...r,
    movimiento: r.movimiento || "Reposicion",
  }));
  const rows = [...ventas, ...repos].sort(
    (a, b) => new Date(b.fecha).getTime() - new Date(a.fecha).getTime()
  );
  if (!rows.length) {
    return `<p class="muted small">Sin registros en el periodo.</p>`;
  }
  return `<div class="table-wrap"><table><thead><tr>
      <th>Tipo</th><th>ID</th><th>Fecha</th><th>Litros</th><th>Total R$</th><th>Oro (g)</th><th>Pago / Precio L</th>
    </tr></thead><tbody>${rows
      .map((row) => {
        const esRepo = row.movimiento === "Reposicion";
        const pagoCol = esRepo
          ? formatMoney(row.precio_reales_litro, "reales")
          : row.tipo_pago || "—";
        return `
      <tr>
        <td>${row.movimiento}</td>
        <td>#${row.id}</td>
        <td>${formatDate(row.fecha)}</td>
        <td>${Number(row.litros).toFixed(2)}</td>
        <td>${formatMoney(row.total_reales, "reales")}</td>
        <td>${esRepo ? "—" : `${formatMoney(row.total_oro)} g`}</td>
        <td>${pagoCol}</td>
      </tr>`;
      })
      .join("")}</tbody></table></div>`;
}

async function cargarSeccion(sec) {
  const body = document.getElementById(`historial-body-${sec.key}`);
  if (!body) {
    return;
  }
  body.innerHTML = `<p class="muted small">Cargando…</p>`;
  try {
    const qs = leerFiltro(sec.key);
    const data = await api.get(`${sec.endpoint}?${qs}`);
    if (sec.key === "gasolina") {
      body.innerHTML = renderGasolina(data);
    } else if (sec.key === "compras") {
      body.innerHTML = `<div class="table-wrap"><table><thead><tr>
        <th>ID</th><th>Fecha</th><th>Producto</th><th>Proveedor</th><th>Pago</th><th>Total</th>
      </tr></thead><tbody>${renderCompras(data)}</tbody></table></div>`;
    } else if (sec.key === "ventas") {
      body.innerHTML = `<div class="table-wrap"><table><thead><tr>
        <th>ID</th><th>Fecha</th><th>Cliente</th><th>Productos</th><th>Total R$</th><th>Oro</th><th>Estado</th>
      </tr></thead><tbody>${renderVentas(data)}</tbody></table></div>`;
    } else if (sec.key === "cobros") {
      body.innerHTML = `<div class="table-wrap"><table><thead><tr>
        <th>ID</th><th>Fecha</th><th>Venta</th><th>Cliente</th><th>Tipo</th><th>Equiv. R$</th>
      </tr></thead><tbody>${renderCobros(data)}</tbody></table></div>`;
    } else if (sec.key === "salidas") {
      body.innerHTML = `<div class="table-wrap"><table><thead><tr>
        <th>ID</th><th>Fecha</th><th>Producto</th><th>Motivo</th><th>Cant.</th><th>Oro</th>
      </tr></thead><tbody>${renderSalidas(data)}</tbody></table></div>`;
    }
  } catch (e) {
    body.innerHTML = `<p class="muted small insuficiente">${e.message}</p>`;
  }
}

function debouncedRecargar(sec, fn) {
  const prev = debounceTimers.get(sec.key);
  if (prev) {
    clearTimeout(prev);
  }
  debounceTimers.set(
    sec.key,
    setTimeout(fn, DEBOUNCE_MS)
  );
}

function initFiltrosSeccion(sec) {
  const anio = document.getElementById(`hist-${sec.key}-anio`);
  const mes = document.getElementById(`hist-${sec.key}-mes`);
  const dia = document.getElementById(`hist-${sec.key}-dia`);
  const buscar = document.getElementById(`hist-${sec.key}-q`);
  const btn = document.getElementById(`hist-${sec.key}-buscar`);
  if (anio) {
    llenarSelectAnios(anio);
  }
  if (mes) {
    llenarSelectMeses(mes);
    const p = hoyPartes();
    mes.value = String(p.mes);
  }
  if (dia) {
    llenarSelectDias(dia);
    dia.value = String(hoyPartes().dia);
  }
  const recargar = () => cargarSeccion(sec);
  btn?.addEventListener("click", recargar);
  anio?.addEventListener("change", recargar);
  mes?.addEventListener("change", recargar);
  dia?.addEventListener("change", recargar);
  buscar?.addEventListener("input", () => {
    const details = document.getElementById(`historial-seccion-${sec.key}`);
    if (!details?.open) {
      return;
    }
    debouncedRecargar(sec, recargar);
  });

  const details = document.getElementById(`historial-seccion-${sec.key}`);
  details?.addEventListener("toggle", () => {
    if (details.open) {
      recargar();
    }
  });
}

export function initHistorialOperaciones() {
  const root = document.getElementById("historial-operaciones-root");
  if (!root) {
    return;
  }
  SECCIONES.forEach(initFiltrosSeccion);
}

export async function refreshHistorialAbierto() {
  const root = document.getElementById("historial-operaciones-root");
  if (!root) {
    return;
  }
  for (const sec of SECCIONES) {
    const d = document.getElementById(`historial-seccion-${sec.key}`);
    if (d?.open) {
      await cargarSeccion(sec);
    }
  }
}
