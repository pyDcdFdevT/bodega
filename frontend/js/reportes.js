import { api, formatDateOnly, formatMoney, formatTimeOnly, renderEmptyRow } from "./api.js";

function renderReporteGasolina(data) {
  const target = document.getElementById("reporte-gasolina-bloque");
  if (!target || !data) {
    return;
  }
  const h = data.hoy || {};
  target.innerHTML = `
    <div class="report-item"><strong>Litros disponibles</strong>: ${Number(data.litros_disponibles || 0).toFixed(2)}</div>
    <div class="report-item"><strong>Litros vendidos hoy</strong>: ${Number(h.litros_vendidos || 0).toFixed(2)}</div>
    <div class="report-item"><strong>Litros repuestos hoy</strong>: ${Number(h.litros_repuestos || 0).toFixed(2)}</div>
    <div class="report-item"><strong>Ventas hoy (oro)</strong>: ${formatMoney(h.total_ventas_oro)}</div>
    <div class="report-item"><strong>Ventas hoy (reales)</strong>: ${formatMoney(h.total_ventas_reales, "reales")}</div>
    <div class="report-item"><strong>Reposicion hoy (reales)</strong>: ${formatMoney(h.total_reposicion_reales, "reales")}</div>
    <div class="report-item"><strong>Reposicion hoy (oro ref.)</strong>: ${formatMoney(h.total_reposicion_oro)}</div>
    <div class="report-item"><strong>Ganancia hoy (reales)</strong>: ${formatMoney(h.ganancia_reales, "reales")}</div>
    <div class="report-item"><strong>Ganancia hoy (oro)</strong>: ${formatMoney(h.ganancia_oro)}</div>
  `;
}

function renderDashboard(data) {
  const container = document.getElementById("dashboard-cards");
  const op = data.operaciones_hoy || {};
  const gas = data.gasolina || {};
  container.innerHTML = `
    <article class="metric-pill"><span>Ganancia neta (oro equiv.)</span><strong>${formatMoney(op.ganancia_neta)}</strong></article>
    <article class="metric-pill"><span>Gastos hoy (R$)</span><strong>${formatMoney(op.gastos_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Gastos hoy (oro equiv.)</span><strong>${formatMoney(op.gastos_oro_equiv)}</strong></article>
    <article class="metric-pill"><span>Productos activos</span><strong>${data.inventario.productos_activos}</strong></article>
    <article class="metric-pill"><span>Stock bajo</span><strong>${data.inventario.stock_bajo}</strong></article>
    <article class="metric-pill"><span>Valor stock R$</span><strong>${formatMoney(data.inventario.valor_stock_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Gasolina P/L (R$)</span><strong>${formatMoney(gas.precio_por_litro_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Ventas hoy (oro)</span><strong>${formatMoney(op.ventas_oro)}</strong></article>
    <article class="metric-pill"><span>Ventas hoy R$</span><strong>${formatMoney(op.ventas_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Compras hoy (oro)</span><strong>${formatMoney(op.compras_oro)}</strong></article>
    <article class="metric-pill"><span>Salidas hoy</span><strong>${formatMoney(op.salidas_oro)}</strong></article>
    <article class="metric-pill"><span>Gasolina hoy (oro)</span><strong>${formatMoney(op.gasolina_oro)}</strong></article>
    <article class="metric-pill"><span>Oro Araparita</span><strong>${formatMoney(op.oro_araparita)}</strong></article>
    <article class="metric-pill"><span>Oro Uruman</span><strong>${formatMoney(op.oro_uruman)}</strong></article>
    <article class="metric-pill"><span>Oro StaE Min</span><strong>${formatMoney(op.oro_santa_elena_minero)}</strong></article>
    <article class="metric-pill"><span>Oro StaE Fun</span><strong>${formatMoney(op.oro_santa_elena_fundido)}</strong></article>
    <article class="metric-pill"><span>Oro total (cobrado)</span><strong>${formatMoney(op.oro_total)}</strong></article>
  `;
}

function renderResumen(targetId, data, title) {
  const target = document.getElementById(targetId);
  target.innerHTML = `
    <div class="report-item"><strong>${title}</strong>: ${data.cantidad}</div>
    <div class="report-item"><strong>Total oro</strong>: ${formatMoney(data.total_oro)}</div>
    <div class="report-item"><strong>Total reales</strong>: ${formatMoney(data.total_reales, "reales")}</div>
  `;
}

export async function loadReportes() {
  const [dashboard, ventas, compras, movimientos, gasolinaRep] = await Promise.all([
    api.get("/reportes/dashboard"),
    api.get("/reportes/ventas?dias=7"),
    api.get("/reportes/compras?dias=7"),
    api.get("/reportes/movimientos?limit=30"),
    api.get("/reportes/gasolina"),
  ]);
  renderDashboard(dashboard);
  renderResumen("reporte-ventas-resumen", ventas, "Ventas en 7 dias");
  renderResumen("reporte-compras-resumen", compras, "Compras en 7 dias");
  renderReporteGasolina(gasolinaRep);
  const tbody = document.getElementById("tabla-movimientos");
  if (!movimientos.length) {
    tbody.innerHTML = renderEmptyRow(8, "No hay movimientos recientes.");
    return;
  }
  tbody.innerHTML = movimientos.map((movimiento) => `
    <tr>
      <td>${formatDateOnly(movimiento.fecha)}</td>
      <td>${formatTimeOnly(movimiento.fecha)}</td>
      <td>${movimiento.producto}</td>
      <td>${movimiento.tipo}</td>
      <td>${movimiento.cantidad}</td>
      <td>${movimiento.stock_anterior}</td>
      <td>${movimiento.stock_nuevo}</td>
      <td>${movimiento.motivo || "-"}</td>
    </tr>
  `).join("");
}
