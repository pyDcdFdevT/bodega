import { api, fechaOperativaUtc, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";
import { getRateLabel } from "./tasas.js";

const CHART_COLORS = ["#c9a227", "#2d6a9f", "#3d8b5a", "#8b5a9e", "#d4654a"];
const CHART_GRID = "rgba(23, 50, 77, 0.12)";

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
let dashboardPeriodo = "dia";
let dashboardInitialized = false;

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

function activosHoyReales(op, activosList, fechaDia) {
  if (op.activos_reales != null && fechaDia) {
    return Number(op.activos_reales);
  }
  if (op.activos_reales != null && !fechaDia) {
    return 0;
  }
  return (activosList || [])
    .filter((a) => !fechaDia || fechaOperativaUtc(a.fecha) === fechaDia)
    .reduce((sum, a) => sum + Number(a.monto_reales || 0), 0);
}

/** ventas_reales − compras mercancía − gastos_reales − activos (sin compra de oro en R$). */
function gananciaNetaReales(op, cierreDia, activosR, esDia) {
  if (!esDia && op.ganancia_neta_reales != null) {
    return Number(op.ganancia_neta_reales);
  }
  if (op.ganancia_neta_reales != null && esDia) {
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

function periodoSuffix(periodo) {
  if (periodo === "mes") {
    return " (mes)";
  }
  if (periodo === "anio") {
    return " (año)";
  }
  return "";
}

function actualizarTitulosDashboard(periodo, periodoLabel) {
  const heading = document.getElementById("dashboard-heading");
  if (heading) {
    const titulos = {
      dia: "Dashboard del día",
      mes: `Dashboard del mes — ${periodoLabel}`,
      anio: `Dashboard del año — ${periodoLabel}`,
    };
    heading.textContent = titulos[periodo] || titulos.dia;
  }
  const oroTitle = document.getElementById("dashboard-chart-oro-title");
  const lineaTitle = document.getElementById("dashboard-chart-linea-title");
  if (oroTitle) {
    oroTitle.textContent =
      periodo === "dia"
        ? "Oro recolectado por tipo (hoy)"
        : `Oro recolectado por tipo${periodoSuffix(periodo)}`;
  }
  if (lineaTitle) {
    const lineaTitulos = {
      dia: "Ventas del día por hora (R$)",
      mes: "Ventas por día del mes (R$)",
      anio: "Ventas por mes del año (R$)",
    };
    lineaTitle.textContent = lineaTitulos[periodo] || lineaTitulos.dia;
  }
  const ultimas = document.getElementById("dashboard-ultimas-operaciones");
  if (ultimas) {
    ultimas.hidden = periodo !== "dia";
  }
}

function renderSummaryCards(inv, op, oroRecolectado, cierreDia, activosList, fechaDia, periodo) {
  const container = document.getElementById("dashboard-summary-cards");
  if (!container) {
    return;
  }
  const esDia = periodo === "dia";
  const suf = periodoSuffix(periodo);
  const activosR = activosHoyReales(op, activosList, esDia ? fechaDia : null);
  const gananciaR = gananciaNetaReales(op, cierreDia, activosR, esDia);
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
      <span>Ganancia neta (R$)${suf}</span>
      <strong>${formatMoney(gananciaR, "reales")}</strong>
    </article>
    <article class="metric-pill dashboard-kpi">
      <span>Oro total (g)${suf}</span>
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

function buildSeriesPeriodo(periodo, reporte) {
  if (periodo === "mes" && Array.isArray(reporte?.cierres)) {
    return {
      labels: reporte.cierres.map((c) => {
        const d = String(c.fecha_operativa || "");
        return d.length >= 10 ? d.slice(8, 10) + "/" + d.slice(5, 7) : d;
      }),
      data: reporte.cierres.map((c) => Number(c.ventas_reales || 0)),
    };
  }
  if (periodo === "anio" && Array.isArray(reporte?.meses)) {
    return {
      labels: reporte.meses.map((m) => m.mes_nombre || MESES_ES[(m.mes || 1) - 1]),
      data: reporte.meses.map((m) => Number(m.ventas_reales || 0)),
    };
  }
  return { labels: [], data: [] };
}

function renderVentasLineaChart(view) {
  const canvas = document.getElementById("chart-ventas-hora");
  if (!canvas || typeof Chart === "undefined") {
    return;
  }
  let labels;
  let data;
  if (view.periodo === "dia") {
    ({ labels, data } = buildVentasPorHora(view.ventasList || [], view.fecha));
  } else {
    ({ labels, data } = buildSeriesPeriodo(view.periodo, view.reporte));
    if (!labels.length) {
      labels = ["—"];
      data = [0];
    }
  }
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

function mapReporteToView(reporte, inventario) {
  const t = reporte.totales || {};
  const b = t.bodega || {};
  const oro = t.oro_recolectado_detalle || {};
  const periodo = reporte.periodo === "anual" ? "anio" : "mes";
  const periodoLabel =
    periodo === "anio"
      ? String(reporte.anio)
      : `${reporte.mes_nombre || MESES_ES[(reporte.mes || 1) - 1]} ${reporte.anio}`;
  return {
    periodo,
    periodoLabel,
    inventario: inventario || {},
    op: {
      ventas_reales: t.ventas_reales,
      compras_reales: b.compras_mercancia_reales ?? t.compras_reales,
      gastos_reales: t.gastos_reales,
      ganancia_neta_reales: t.ganancia_neta_reales,
      oro_araparita: oro.araparita,
      oro_uruman: oro.uruman,
      oro_santa_elena_minero: oro.santa_elena_minero,
      oro_santa_elena_fundido: oro.santa_elena_fundido,
    },
    oroRecolectado: {
      araparita: oro.araparita,
      uruman: oro.uruman,
      santa_elena_minero: oro.santa_elena_minero,
      santa_elena_fundido: oro.santa_elena_fundido,
      comprado_gramos: oro.comprado_gramos,
    },
    cierreDia: { bodega: { compras_mercancia_reales: b.compras_mercancia_reales } },
    reporte,
    fecha: null,
    ultimasVentas: [],
    ventasList: [],
    comprasList: [],
    activosList: [],
  };
}

function renderDashboard(view) {
  if (!view) {
    return;
  }
  const op = view.op || {};
  const inv = view.inventario || {};
  const oro = view.oroRecolectado || null;
  const periodo = view.periodo || "dia";

  destroyDashboardCharts();
  actualizarTitulosDashboard(periodo, view.periodoLabel);
  renderSummaryCards(inv, op, oro, view.cierreDia, view.activosList, view.fecha, periodo);
  renderOroPieChart(op, oro);
  renderBarrasChart(op, view.cierreDia);
  renderVentasLineaChart(view);
  renderStockBajo(inv);
  if (periodo === "dia") {
    renderUltimasVentas(view.ultimasVentas || []);
    renderUltimasCompras(view.comprasList, view.fecha);
  }
}

async function fetchInventarioDashboard() {
  const dash = await api.get("/reportes/dashboard");
  return dash.inventario || {};
}

async function fetchDashboardView(periodo) {
  const ahora = new Date();
  const mes = ahora.getMonth() + 1;
  const anio = ahora.getFullYear();

  if (periodo === "dia") {
    const [dashboard, cierreDia, ventasList, comprasList, activosList] = await Promise.all([
      api.get("/reportes/dashboard"),
      api.get("/cierre/dia").catch(() => null),
      api.get("/ventas?limit=200").catch(() => []),
      api.get("/compras?limit=50").catch(() => []),
      api.get("/activos").catch(() => []),
    ]);
    return {
      periodo: "dia",
      periodoLabel: dashboard.fecha,
      inventario: dashboard.inventario || {},
      op: dashboard.operaciones_hoy || {},
      oroRecolectado: cierreDia?.oro_recolectado || null,
      cierreDia,
      fecha: dashboard.fecha,
      ultimasVentas: dashboard.ultimas_ventas || [],
      ventasList,
      comprasList,
      activosList,
    };
  }

  if (periodo === "mes") {
    const [reporte, inventario] = await Promise.all([
      api.get(`/reportes/mensual?mes=${mes}&anio=${anio}`),
      fetchInventarioDashboard(),
    ]);
    return mapReporteToView(reporte, inventario);
  }

  const [reporte, inventario] = await Promise.all([
    api.get(`/reportes/anual?anio=${anio}`),
    fetchInventarioDashboard(),
  ]);
  return mapReporteToView(reporte, inventario);
}

export function initDashboard() {
  if (dashboardInitialized) {
    return;
  }
  dashboardInitialized = true;
  document.querySelectorAll(".dashboard-period-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.periodo || "dia";
      if (next === dashboardPeriodo) {
        return;
      }
      dashboardPeriodo = next;
      document.querySelectorAll(".dashboard-period-tab").forEach((b) => {
        const active = b.dataset.periodo === dashboardPeriodo;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
      });
      loadDashboard();
    });
  });
}

export async function loadDashboard() {
  const activeBtn = document.querySelector(".dashboard-period-tab.active");
  if (activeBtn?.dataset.periodo) {
    dashboardPeriodo = activeBtn.dataset.periodo;
  }
  try {
    const view = await fetchDashboardView(dashboardPeriodo);
    renderDashboard(view);
  } catch (error) {
    showToast(error.message || "Error al cargar el dashboard", "error");
  }
}
