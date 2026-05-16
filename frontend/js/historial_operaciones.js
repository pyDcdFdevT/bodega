import { api, formatDate, formatMoney, renderEmptyRow } from "./api.js";

const SECCIONES = [
  { key: "compras", label: "Compras", endpoint: "/historial/compras" },
  { key: "ventas", label: "Ventas", endpoint: "/historial/ventas" },
  { key: "cobros", label: "Cobros / Pagos", endpoint: "/historial/cobros" },
  { key: "salidas", label: "Salidas", endpoint: "/historial/salidas" },
  { key: "gasolina", label: "Gasolina", endpoint: "/historial/gasolina" },
];

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
  const params = new URLSearchParams({ limit: "20" });
  if (anio) {
    params.set("anio", String(anio));
  }
  if (mes) {
    params.set("mes", String(mes));
  }
  if (diaRaw) {
    params.set("dia", String(diaRaw));
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
    return renderEmptyRow(6, "Sin registros en el periodo.");
  }
  return rows
    .map(
      (r) => `
    <tr>
      <td>#${r.id}</td>
      <td>${formatDate(r.fecha)}</td>
      <td>${r.cliente || "—"}</td>
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
  const ventas = data?.ventas || [];
  const repos = data?.reposiciones || [];
  if (!ventas.length && !repos.length) {
    return `<p class="muted small">Sin registros en el periodo.</p>`;
  }
  let html = "";
  if (ventas.length) {
    html += `<p class="muted small" style="margin:0.5rem 0 0.25rem;">Ventas</p>
      <div class="table-wrap"><table><thead><tr>
        <th>ID</th><th>Fecha</th><th>Litros</th><th>Total R$</th><th>Oro (g)</th><th>Pago</th>
      </tr></thead><tbody>`;
    html += ventas
      .map(
        (v) => `
      <tr>
        <td>#${v.id}</td>
        <td>${formatDate(v.fecha)}</td>
        <td>${Number(v.litros).toFixed(2)}</td>
        <td>${formatMoney(v.total_reales, "reales")}</td>
        <td>${formatMoney(v.total_oro)} g</td>
        <td>${v.tipo_pago || "—"}</td>
      </tr>`
      )
      .join("");
    html += `</tbody></table></div>`;
  }
  if (repos.length) {
    html += `<p class="muted small" style="margin:0.75rem 0 0.25rem;">Reposiciones</p>
      <div class="table-wrap"><table><thead><tr>
        <th>ID</th><th>Fecha</th><th>Litros</th><th>Precio/L</th><th>Total R$</th>
      </tr></thead><tbody>`;
    html += repos
      .map(
        (r) => `
      <tr>
        <td>#${r.id}</td>
        <td>${formatDate(r.fecha)}</td>
        <td>${Number(r.litros).toFixed(2)}</td>
        <td>${formatMoney(r.precio_reales_litro, "reales")}</td>
        <td>${formatMoney(r.total_reales, "reales")}</td>
      </tr>`
      )
      .join("");
    html += `</tbody></table></div>`;
  }
  return html;
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
        <th>ID</th><th>Fecha</th><th>Cliente</th><th>Total R$</th><th>Oro</th><th>Estado</th>
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

function initFiltrosSeccion(sec) {
  const anio = document.getElementById(`hist-${sec.key}-anio`);
  const mes = document.getElementById(`hist-${sec.key}-mes`);
  const dia = document.getElementById(`hist-${sec.key}-dia`);
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

  const details = document.getElementById(`historial-seccion-${sec.key}`);
  details?.addEventListener("toggle", () => {
    if (details.open) {
      recargar();
    }
  });
}

export function initHistorialOperaciones() {
  const btn = document.getElementById("btn-compras-ver-historial");
  const acordeon = document.getElementById("historial-acordeon");
  if (!btn || !acordeon) {
    return;
  }
  btn.addEventListener("click", () => {
    const visible = acordeon.hidden;
    acordeon.hidden = !visible;
    btn.textContent = visible ? "Ocultar historial" : "Ver historial";
    if (visible) {
      SECCIONES.forEach((sec) => {
        const d = document.getElementById(`historial-seccion-${sec.key}`);
        if (d?.open) {
          cargarSeccion(sec);
        }
      });
    }
  });
  SECCIONES.forEach(initFiltrosSeccion);
}

export async function refreshHistorialAbierto() {
  const acordeon = document.getElementById("historial-acordeon");
  if (!acordeon || acordeon.hidden) {
    return;
  }
  for (const sec of SECCIONES) {
    const d = document.getElementById(`historial-seccion-${sec.key}`);
    if (d?.open) {
      await cargarSeccion(sec);
    }
  }
}
