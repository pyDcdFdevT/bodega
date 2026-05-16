import { api, formatDate, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";
import { loadPagosProveedores } from "./pagos_proveedores.js";
import { getRateLabel } from "./tasas.js";

const CHART_COLORS = ["#c9a227", "#2d6a9f", "#3d8b5a", "#8b5a9e", "#d4654a"];
const CHART_GRID = "rgba(23, 50, 77, 0.12)";

/** Paleta daltónico-friendly (Wong) para oro recolectado por tipo. */
const ORO_PIE_COLORS = {
  araparita: "#0072B2",
  uruman: "#E69F00",
  santa_elena_minero: "#009E73",
  santa_elena_fundido: "#CC79A7",
  comprado: "#F0E442",
};
const ORO_PIE_COLOR_ORDER = [
  ORO_PIE_COLORS.araparita,
  ORO_PIE_COLORS.uruman,
  ORO_PIE_COLORS.santa_elena_minero,
  ORO_PIE_COLORS.santa_elena_fundido,
  ORO_PIE_COLORS.comprado,
];

let chartOroPie = null;
let chartBarras = null;
let chartVentasHora = null;

function destroyDashboardCharts() {
  [chartOroPie, chartBarras, chartVentasHora].forEach((c) => {
    if (c) {
      c.destroy();
    }
  });
  chartOroPie = null;
  chartBarras = null;
  chartVentasHora = null;
}

function parseUtcInstant(value) {
  if (!value) {
    return null;
  }
  let s = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}T/.test(s) && !/[zZ]\s*$/i.test(s) && !/[+-]\d{2}:?\d{2}\s*$/.test(s)) {
    s = `${s}Z`;
  }
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Hora operativa Venezuela (UTC−4) para agrupar ventas. */
function horaVenezuela(iso) {
  const d = parseUtcInstant(iso);
  if (!d) {
    return 0;
  }
  return (d.getUTCHours() - 4 + 24) % 24;
}

function fechaOperativaUtc(iso) {
  const d = parseUtcInstant(iso);
  if (!d) {
    return "";
  }
  return d.toISOString().slice(0, 10);
}

function activosHoyReales(op, activosList, fechaDia) {
  if (op.activos_reales != null) {
    return Number(op.activos_reales);
  }
  return (activosList || [])
    .filter((a) => !fechaDia || fechaOperativaUtc(a.fecha) === fechaDia)
    .reduce((sum, a) => sum + Number(a.monto_reales || 0), 0);
}

/** ventas_reales − compras mercancía − gastos_reales − activos (sin compra de oro en R$). */
function gananciaNetaReales(op, cierreDia, activosR) {
  if (op.ganancia_neta_reales != null) {
    return Number(op.ganancia_neta_reales);
  }
  const ventas = Number(op.ventas_reales ?? 0);
  const gastos = Number(op.gastos_reales ?? 0);
  const compras =
    cierreDia?.bodega?.compras_mercancia_reales != null
      ? Number(cierreDia.bodega.compras_mercancia_reales)
      : Number(op.compras_reales ?? 0);
  return Math.round((ventas - compras - gastos - Number(activosR || 0)) * 100) / 100;
}

function comprasMercanciaReales(op, cierreDia) {
  if (cierreDia?.bodega?.compras_mercancia_reales != null) {
    return Number(cierreDia.bodega.compras_mercancia_reales);
  }
  return Number(op.compras_reales ?? 0);
}

function totalOroRecolectadoGramos(op, oroRecolectado) {
  const o = oroRecolectado || {};
  return (
    Number(o.araparita ?? op.oro_araparita ?? 0) +
    Number(o.uruman ?? op.oro_uruman ?? 0) +
    Number(o.santa_elena_minero ?? op.oro_santa_elena_minero ?? 0) +
    Number(o.santa_elena_fundido ?? op.oro_santa_elena_fundido ?? 0) +
    Number(o.comprado_gramos ?? 0)
  );
}

function renderSummaryCards(inv, op, oroRecolectado, cierreDia, activosList, fechaDia) {
  const container = document.getElementById("dashboard-summary-cards");
  if (!container) {
    return;
  }
  const activosR = activosHoyReales(op, activosList, fechaDia);
  const gananciaR = gananciaNetaReales(op, cierreDia, activosR);
  const oroTotal = totalOroRecolectadoGramos(op, oroRecolectado);
  container.innerHTML = `
    <article class="metric-pill dashboard-kpi">
      <span>Productos activos</span>
      <strong>${inv.productos_activos ?? 0}</strong>
    </article>
    <article class="metric-pill dashboard-kpi">
      <span>Stock bajo</span>
      <strong>${inv.stock_bajo ?? 0}</strong>
    </article>
    <article class="metric-pill dashboard-kpi">
      <span>Activos (inversiones)</span>
      <strong>${formatMoney(activosR, "reales")}</strong>
    </article>
    <article class="metric-pill dashboard-kpi">
      <span>Ganancia neta (R$)</span>
      <strong>${formatMoney(gananciaR, "reales")}</strong>
    </article>
    <article class="metric-pill dashboard-kpi">
      <span>Oro recolectado total (g)</span>
      <strong>${formatMoney(oroTotal)}</strong>
    </article>
  `;
}

function renderOroPieChart(op, oroRecolectado) {
  const canvas = document.getElementById("chart-oro-pie");
  if (!canvas || typeof Chart === "undefined") {
    return;
  }
  const o = oroRecolectado || {};
  const labels = [
    getRateLabel("araparita"),
    getRateLabel("uruman"),
    getRateLabel("santa_elena_minero"),
    getRateLabel("santa_elena_fundido"),
    "Comprado",
  ];
  const values = [
    Number(o.araparita ?? op.oro_araparita ?? 0),
    Number(o.uruman ?? op.oro_uruman ?? 0),
    Number(o.santa_elena_minero ?? op.oro_santa_elena_minero ?? 0),
    Number(o.santa_elena_fundido ?? op.oro_santa_elena_fundido ?? 0),
    Number(o.comprado_gramos ?? 0),
  ];
  chartOroPie = new Chart(canvas, {
    type: "pie",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: ORO_PIE_COLOR_ORDER,
          borderWidth: 2,
          borderColor: "#17324d",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${formatMoney(ctx.parsed)} g`,
          },
        },
      },
    },
  });
}

function renderBarrasChart(op, cierreDia) {
  const canvas = document.getElementById("chart-barras-reales");
  if (!canvas || typeof Chart === "undefined") {
    return;
  }
  chartBarras = new Chart(canvas, {
    type: "bar",
    data: {
      labels: ["Ventas", "Compras", "Gastos"],
      datasets: [
        {
          label: "R$",
          data: [
            Number(op.ventas_reales ?? 0),
            comprasMercanciaReales(op, cierreDia),
            Number(op.gastos_reales ?? 0),
          ],
          backgroundColor: ["#2d6a9f", "#c9a227", "#d4654a"],
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: CHART_GRID },
          ticks: {
            callback: (v) => `R$ ${v}`,
          },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

function buildVentasPorHora(ventas, fechaDia) {
  const buckets = Array.from({ length: 24 }, () => 0);
  for (const v of ventas) {
    if ((v.estado || "VIGENTE") === "ANULADA") {
      continue;
    }
    if (fechaDia && fechaOperativaUtc(v.fecha) !== fechaDia) {
      continue;
    }
    const h = horaVenezuela(v.fecha);
    buckets[h] += Number(v.total_reales || 0);
  }
  const nowH = horaVenezuela(new Date().toISOString());
  const desde = Math.max(0, nowH - 11);
  const labels = [];
  const data = [];
  for (let h = desde; h <= nowH; h += 1) {
    labels.push(`${String(h).padStart(2, "0")}:00`);
    data.push(Math.round(buckets[h] * 100) / 100);
  }
  if (!labels.length) {
    labels.push("00:00");
    data.push(0);
  }
  return { labels, data };
}

function renderVentasHoraChart(ventas, fechaDia) {
  const canvas = document.getElementById("chart-ventas-hora");
  if (!canvas || typeof Chart === "undefined") {
    return;
  }
  const { labels, data } = buildVentasPorHora(ventas, fechaDia);
  chartVentasHora = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Ventas (R$)",
          data,
          borderColor: "#17324d",
          backgroundColor: "rgba(45, 106, 159, 0.15)",
          fill: true,
          tension: 0.3,
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: CHART_GRID },
          ticks: {
            callback: (v) => `R$ ${v}`,
          },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderStockBajo(inv) {
  const tbStock = document.getElementById("tabla-dashboard-stock-bajo");
  const alertas = inv.stock_bajo_alertas || [];
  if (!tbStock) {
    return;
  }
  if (!alertas.length) {
    tbStock.innerHTML = renderEmptyRow(3, "Sin alertas de stock bajo.");
  } else {
    tbStock.innerHTML = alertas
      .map(
        (a) => `
        <tr><td>${a.nombre}</td><td>${a.stock}</td><td>${a.minimo}</td></tr>`
      )
      .join("");
  }
}

function nombrePrimerProductoCompra(compra) {
  const detalle = compra.detalles?.[0];
  if (!detalle) {
    return "-";
  }
  return detalle.producto_nombre || "-";
}

function renderUltimasCompras(compras, fechaDia) {
  const tb = document.getElementById("tabla-dashboard-compras");
  if (!tb) {
    return;
  }
  const hoy = (compras || [])
    .filter((c) => !fechaDia || fechaOperativaUtc(c.fecha) === fechaDia)
    .slice(0, 5);
  if (!hoy.length) {
    tb.innerHTML = renderEmptyRow(4, "Sin compras hoy.");
  } else {
    tb.innerHTML = hoy
      .map(
        (c) => `
        <tr>
          <td>${formatTimeOnly(c.fecha)}</td>
          <td>${nombrePrimerProductoCompra(c)}</td>
          <td>${c.proveedor || "-"}</td>
          <td>${formatMoney(c.total_reales, "reales")}</td>
        </tr>`
      )
      .join("");
  }
}

function renderUltimasVentas(uv) {
  const tbVentas = document.getElementById("tabla-dashboard-ventas");
  if (!tbVentas) {
    return;
  }
  if (!uv.length) {
    tbVentas.innerHTML = renderEmptyRow(4, "Sin ventas hoy.");
  } else {
    tbVentas.innerHTML = uv
      .map(
        (v) => `
        <tr>
          <td>${formatTimeOnly(v.fecha)}</td>
          <td>${v.cliente || "-"}</td>
          <td>${formatMoney(v.total_reales, "reales")}</td>
          <td>${formatMoney(v.total_oro)}</td>
        </tr>`
      )
      .join("");
  }
}

function renderUltimosMovimientos(um) {
  const tbMov = document.getElementById("tabla-dashboard-movimientos");
  if (!tbMov) {
    return;
  }
  if (!um.length) {
    tbMov.innerHTML = renderEmptyRow(4, "Sin movimientos de inventario hoy.");
  } else {
    tbMov.innerHTML = um
      .map(
        (m) => `
        <tr>
          <td>${formatTimeOnly(m.fecha)}</td>
          <td>${m.producto || "-"}</td>
          <td>${m.tipo}</td>
          <td>${m.cantidad}</td>
        </tr>`
      )
      .join("");
  }
}

function balanceLinea(label, valor) {
  return `<div class="cierre-line"><span>${label}</span><strong>${valor}</strong></div>`;
}

function oroBalanceHtml(oro) {
  const tipos = oro.por_tipo || [];
  if (!tipos.length) {
    return balanceLinea(
      `Oro (${formatMoney(oro.gramos)} g)`,
      formatMoney(oro.valor_reales, "reales")
    );
  }
  const lineas = tipos
    .filter((t) => Number(t.gramos) > 0.0001 || Number(t.valor_reales) > 0)
    .map((t) =>
      balanceLinea(
        `${t.etiqueta || t.tipo} (${formatMoney(t.gramos)} g @ ${formatMoney(t.tasa_reales, "reales")}/g)`,
        formatMoney(t.valor_reales, "reales")
      )
    )
    .join("");
  return (
    lineas +
    balanceLinea(
      `Oro total (${formatMoney(oro.gramos)} g)`,
      formatMoney(oro.valor_reales, "reales")
    )
  );
}

function renderBalance(data) {
  const root = document.getElementById("balance-general-content");
  const badge = document.getElementById("balance-ecuacion-badge");
  if (!root) {
    return;
  }
  if (!data) {
    root.innerHTML = '<p class="muted">No fue posible cargar el balance.</p>';
    if (badge) {
      badge.textContent = "—";
    }
    return;
  }
  const a = data.activos || {};
  const p = data.pasivos || {};
  const pat = data.patrimonio || {};
  const eq = data.ecuacion || {};
  const oro = a.oro || {};

  if (badge) {
    badge.textContent = eq.cuadra ? "Cuadra ✓" : `Dif. ${formatMoney(eq.diferencia, "reales")}`;
    badge.classList.toggle("estado", true);
    badge.classList.toggle("ok", Boolean(eq.cuadra));
    badge.classList.toggle("insuficiente", !eq.cuadra);
  }

  root.innerHTML = `
    <div class="balance-col">
      <h4>Activos</h4>
      ${balanceLinea("Caja", formatMoney(a.caja_reales, "reales"))}
      ${oroBalanceHtml(oro)}
      ${balanceLinea("Inventario (CPP)", formatMoney(a.inventario_reales, "reales"))}
      ${balanceLinea(
        "Activos fijos (valor actual)",
        formatMoney(a.activos_fijos_reales, "reales")
      )}
      ${
        a.activos_fijos_depreciacion_acumulada != null
          ? balanceLinea(
              "Depreciacion acumulada (activos)",
              formatMoney(a.activos_fijos_depreciacion_acumulada, "reales")
            )
          : ""
      }
      ${
        a.activos_fijos_monto_original != null &&
        a.activos_fijos_monto_original !== a.activos_fijos_reales
          ? `<p class="muted small">Costo original activos: ${formatMoney(a.activos_fijos_monto_original, "reales")}</p>`
          : ""
      }
      <div class="cierre-line balance-total"><span>Total activos</span><strong>${formatMoney(a.total, "reales")}</strong></div>
    </div>
    <div class="balance-col">
      <h4>Pasivos</h4>
      ${balanceLinea("Cuentas por pagar (compras a crédito)", formatMoney(p.cuentas_por_pagar, "reales"))}
      <div class="cierre-line balance-total"><span>Total pasivos</span><strong>${formatMoney(p.total, "reales")}</strong></div>
    </div>
    <div class="balance-col">
      <h4>Patrimonio</h4>
      ${balanceLinea("Capital inicial", formatMoney(pat.capital_inicial, "reales"))}
      ${balanceLinea("Ganancia acumulada", formatMoney(pat.ganancia_acumulada, "reales"))}
      <div class="cierre-line balance-total"><span>Total patrimonio</span><strong>${formatMoney(pat.total, "reales")}</strong></div>
    </div>
    <div class="balance-col balance-ecuacion">
      <h4>Ecuación contable</h4>
      ${balanceLinea("Activos", formatMoney(eq.activos, "reales"))}
      ${balanceLinea("Pasivos + Patrimonio", formatMoney(eq.pasivos_mas_patrimonio, "reales"))}
      <p class="muted small">${eq.cuadra ? "La ecuación contable cuadra." : `Diferencia: ${formatMoney(eq.diferencia, "reales")}`}</p>
    </div>
  `;
}

function renderDashboard(data, cierreDia, ventasList, comprasList, activosList) {
  if (!data) {
    return;
  }
  const op = data.operaciones_hoy || {};
  const inv = data.inventario || {};
  const oro = cierreDia?.oro_recolectado || null;

  destroyDashboardCharts();
  renderSummaryCards(inv, op, oro, cierreDia, activosList, data.fecha);
  renderOroPieChart(op, oro);
  renderBarrasChart(op, cierreDia);
  renderVentasHoraChart(ventasList || [], data.fecha);
  renderStockBajo(inv);
  renderUltimasVentas(data.ultimas_ventas || []);
  renderUltimasCompras(comprasList, data.fecha);
  renderUltimosMovimientos(data.ultimos_movimientos || []);
}

const MESES_ES = [
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

function reporteLinea(label, valor) {
  return `<div class="cierre-line"><span>${label}</span><strong>${valor}</strong></div>`;
}

function renderReportePeriodo(data) {
  const root = document.getElementById("reporte-periodo-content");
  if (!root) {
    return;
  }
  if (!data?.totales) {
    root.innerHTML = '<p class="muted">Sin datos para el periodo seleccionado.</p>';
    return;
  }
  const t = data.totales;
  const b = t.bodega || {};
  const g = t.gasolina || {};
  const co = t.compra_oro || {};
  const oro = t.oro_recolectado_detalle || {};
  const titulo =
    data.periodo === "anual"
      ? `Resumen anual ${data.anio}`
      : `${data.mes_nombre || MESES_ES[(data.mes || 1) - 1]} ${data.anio}`;

  let mesesHtml = "";
  if (data.periodo === "anual" && Array.isArray(data.meses) && data.meses.length) {
    mesesHtml = `
      <div class="table-wrap" style="margin-top:16px;">
        <table>
          <thead>
            <tr>
              <th>Mes</th>
              <th>Días</th>
              <th>Ventas R$</th>
              <th>Compras R$</th>
              <th>Gastos R$</th>
              <th>Oro (g)</th>
              <th>Ganancia R$</th>
            </tr>
          </thead>
          <tbody>
            ${data.meses
              .map(
                (m) => `
              <tr>
                <td>${m.mes_nombre}</td>
                <td>${m.dias_con_cierre}</td>
                <td>${formatMoney(m.ventas_reales, "reales")}</td>
                <td>${formatMoney(m.compras_reales, "reales")}</td>
                <td>${formatMoney(m.gastos_reales, "reales")}</td>
                <td>${formatMoney(m.oro_recolectado)}</td>
                <td>${formatMoney(m.ganancia_neta_reales, "reales")}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  }

  root.innerHTML = `
    <p class="muted small" style="margin:0 0 12px;">${titulo} · ${t.dias_con_cierre} día(s) con cierre registrado</p>
    <div class="dashboard-summary reporte-periodo-kpis">
      <article class="metric-pill dashboard-kpi">
        <span>Ventas (R$)</span>
        <strong>${formatMoney(t.ventas_reales, "reales")}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Compras (R$)</span>
        <strong>${formatMoney(t.compras_reales, "reales")}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Gastos (R$)</span>
        <strong>${formatMoney(t.gastos_reales, "reales")}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Oro recolectado (g)</span>
        <strong>${formatMoney(t.oro_recolectado)}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Ganancia neta (R$)</span>
        <strong>${formatMoney(t.ganancia_neta_reales, "reales")}</strong>
      </article>
    </div>
    <div class="grid two reporte-periodo-detalle">
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Bodega</h4>
        ${reporteLinea("Ventas reales", formatMoney(b.ventas_reales, "reales"))}
        ${reporteLinea("Compras mercancía", formatMoney(b.compras_mercancia_reales, "reales"))}
        ${reporteLinea("Salidas", formatMoney(b.salidas_reales, "reales"))}
      </article>
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Gasolina</h4>
        ${reporteLinea("Ventas reales", formatMoney(g.ventas_reales, "reales"))}
        ${reporteLinea("Reposición", formatMoney(g.reposicion_reales, "reales"))}
      </article>
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Compra de oro</h4>
        ${reporteLinea("Gramos", `${formatMoney(co.gramos)} g`)}
        ${reporteLinea("Reales usados", formatMoney(co.reales_usados, "reales"))}
      </article>
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Oro recolectado</h4>
        ${reporteLinea("Bruto total", `${formatMoney(oro.bruto_total_gramos)} g`)}
        ${reporteLinea("Araparita", `${formatMoney(oro.araparita)} g`)}
        ${reporteLinea("Uruman", `${formatMoney(oro.uruman)} g`)}
        ${t.ganancia_neta_oro ? reporteLinea("Ganancia neta (oro ref.)", `${formatMoney(t.ganancia_neta_oro)} g equiv.`) : ""}
      </article>
    </div>
    ${mesesHtml}
  `;
}

function poblarSelectoresReporte() {
  const selMes = document.getElementById("reporte-mes");
  const selAnio = document.getElementById("reporte-anio");
  if (!selMes || !selAnio) {
    return;
  }
  const ahora = new Date();
  const anioActual = ahora.getFullYear();
  if (!selMes.options.length) {
    selMes.innerHTML = MESES_ES.map(
      (nombre, i) => `<option value="${i + 1}">${nombre}</option>`
    ).join("");
    selMes.value = String(ahora.getMonth() + 1);
  }
  if (!selAnio.options.length) {
    for (let y = anioActual; y >= anioActual - 5; y -= 1) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      selAnio.appendChild(opt);
    }
    selAnio.value = String(anioActual);
  }
}

function actualizarVisibilidadMes() {
  const tipo = document.getElementById("reporte-periodo-tipo")?.value || "mensual";
  const wrap = document.getElementById("reporte-mes-wrap");
  if (wrap) {
    wrap.style.display = tipo === "anual" ? "none" : "";
  }
}

export async function loadReportePeriodo() {
  poblarSelectoresReporte();
  actualizarVisibilidadMes();
  const tipo = document.getElementById("reporte-periodo-tipo")?.value || "mensual";
  const anio = Number(document.getElementById("reporte-anio")?.value || new Date().getFullYear());
  const root = document.getElementById("reporte-periodo-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando resumen…</p>';
  }
  try {
    let data;
    if (tipo === "anual") {
      data = await api.get(`/reportes/anual?anio=${anio}`);
    } else {
      const mes = Number(document.getElementById("reporte-mes")?.value || new Date().getMonth() + 1);
      data = await api.get(`/reportes/mensual?mes=${mes}&anio=${anio}`);
    }
    renderReportePeriodo(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar el reporte"}</p>`;
    }
    showToast(error.message || "Error al cargar el reporte", "error");
  }
}

let reportePeriodoInicializado = false;

export function initReportePeriodo() {
  poblarSelectoresReporte();
  actualizarVisibilidadMes();
  if (reportePeriodoInicializado) {
    return;
  }
  reportePeriodoInicializado = true;
  document.getElementById("reporte-periodo-tipo")?.addEventListener("change", actualizarVisibilidadMes);
  document.getElementById("btn-reporte-periodo")?.addEventListener("click", () => {
    loadReportePeriodo();
  });
}

function renderCuentasPorPagar(data) {
  const root = document.getElementById("cuentas-pagar-content");
  const badge = document.getElementById("cuentas-pagar-total-badge");
  if (!root) {
    return;
  }
  const total = Number(data?.total_pendiente ?? 0);
  if (badge) {
    badge.textContent = `Total: ${formatMoney(total, "reales")}`;
  }
  const compras = data?.compras || [];
  if (!compras.length) {
    root.innerHTML = '<p class="muted">No hay compras a crédito pendientes.</p>';
    return;
  }

  const porProveedor = data?.por_proveedor || [];
  const resumenProveedores =
    porProveedor.length > 1
      ? `
    <div class="cuentas-pagar-resumen">
      ${porProveedor
        .map(
          (p) => `
        <span class="badge">${p.proveedor}: ${formatMoney(p.total_credito, "reales")} (${p.cantidad_compras})</span>`
        )
        .join("")}
    </div>`
      : "";

  root.innerHTML = `
    <p class="report-item" style="margin:0 0 12px;">
      Total pendiente: <strong>${formatMoney(total, "reales")}</strong>
      · ${data.cantidad_compras ?? compras.length} compra(s) a crédito
    </p>
    ${resumenProveedores}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Proveedor</th>
            <th>Total crédito (R$)</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          ${compras
            .map(
              (c) => `
            <tr>
              <td>${c.proveedor || "-"}</td>
              <td>${formatMoney(c.total_reales, "reales")}</td>
              <td>${c.fecha ? formatDate(c.fecha) : "-"}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDepreciacion(data) {
  const root = document.getElementById("depreciacion-content");
  const badge = document.getElementById("depreciacion-valor-badge");
  if (!root) {
    return;
  }
  if (!data) {
    root.innerHTML = '<p class="muted">No fue posible cargar la depreciacion.</p>';
    if (badge) {
      badge.textContent = "—";
    }
    return;
  }
  const tot = data.totales || {};
  const activos = data.activos || [];
  if (badge) {
    badge.textContent = formatMoney(tot.valor_actual, "reales");
  }
  if (!activos.length) {
    root.innerHTML = '<p class="muted">No hay activos fijos registrados.</p>';
    return;
  }
  root.innerHTML = `
    <p class="report-item" style="margin:0 0 12px;">
      Valor actual: <strong>${formatMoney(tot.valor_actual, "reales")}</strong>
      · Dep. acumulada: <strong>${formatMoney(tot.depreciacion_acumulada, "reales")}</strong>
      · Costo original: ${formatMoney(tot.monto_original, "reales")}
      · ${formatMoney(tot.depreciacion_mensual_total, "reales")}/mes
    </p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Activo</th>
            <th>Monto</th>
            <th>Dep./mes</th>
            <th>Dep. acum.</th>
            <th>Valor actual</th>
          </tr>
        </thead>
        <tbody>
          ${activos
            .map(
              (a) => `
            <tr>
              <td>${a.descripcion || "-"}</td>
              <td>${formatMoney(a.monto_reales, "reales")}</td>
              <td>${formatMoney(a.depreciacion_mensual, "reales")}</td>
              <td>${formatMoney(a.depreciacion_acumulada, "reales")}</td>
              <td>${formatMoney(a.valor_actual, "reales")}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

export async function loadDepreciacion() {
  const root = document.getElementById("depreciacion-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando depreciacion…</p>';
  }
  try {
    const data = await api.get("/reportes/depreciacion");
    renderDepreciacion(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar"}</p>`;
    }
  }
}

export async function loadCuentasPorPagar() {
  const root = document.getElementById("cuentas-pagar-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando cuentas por pagar…</p>';
  }
  try {
    const data = await api.get("/reportes/cuentas-por-pagar");
    renderCuentasPorPagar(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar"}</p>`;
    }
  }
}

export async function loadDashboard() {
  const [dashboard, cierreDia, ventasList, comprasList, activosList, balance, depreciacion, cuentasPagar] =
    await Promise.all([
      api.get("/reportes/dashboard"),
      api.get("/cierre/dia").catch(() => null),
      api.get("/ventas?limit=200").catch(() => []),
      api.get("/compras?limit=50").catch(() => []),
      api.get("/activos").catch(() => []),
      api.get("/reportes/balance").catch(() => null),
      api.get("/reportes/depreciacion").catch(() => null),
      api.get("/reportes/cuentas-por-pagar").catch(() => null),
    ]);
  renderDashboard(dashboard, cierreDia, ventasList, comprasList, activosList);
  renderBalance(balance);
  renderDepreciacion(depreciacion);
  renderCuentasPorPagar(cuentasPagar);
  await loadPagosProveedores();
  initReportePeriodo();
  loadReportePeriodo();
}

export { renderBalance };
