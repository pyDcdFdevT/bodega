import { api, formatDate, formatMoney, renderEmptyRow } from "./api.js";

function renderDashboard(data) {
  const container = document.getElementById("dashboard-cards");
  container.innerHTML = `
    <article class="metric-pill"><span>Productos activos</span><strong>${data.inventario.productos_activos}</strong></article>
    <article class="metric-pill"><span>Stock bajo</span><strong>${data.inventario.stock_bajo}</strong></article>
    <article class="metric-pill"><span>Valor stock</span><strong>${formatMoney(data.inventario.valor_stock_oro)}</strong></article>
    <article class="metric-pill"><span>Ventas hoy</span><strong>${formatMoney(data.operaciones_hoy.ventas_oro)}</strong></article>
    <article class="metric-pill"><span>Compras hoy</span><strong>${formatMoney(data.operaciones_hoy.compras_oro)}</strong></article>
    <article class="metric-pill"><span>Salidas hoy</span><strong>${formatMoney(data.operaciones_hoy.salidas_oro)}</strong></article>
    <article class="metric-pill"><span>Gasolina hoy</span><strong>${formatMoney(data.operaciones_hoy.gasolina_oro)}</strong></article>
    <article class="metric-pill"><span>Ganancia neta</span><strong>${formatMoney(data.operaciones_hoy.ganancia_neta)}</strong></article>
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
  const [dashboard, ventas, compras, movimientos] = await Promise.all([
    api.get("/reportes/dashboard"),
    api.get("/reportes/ventas?dias=7"),
    api.get("/reportes/compras?dias=7"),
    api.get("/reportes/movimientos?limit=30"),
  ]);
  renderDashboard(dashboard);
  renderResumen("reporte-ventas-resumen", ventas, "Ventas en 7 dias");
  renderResumen("reporte-compras-resumen", compras, "Compras en 7 dias");
  const tbody = document.getElementById("tabla-movimientos");
  if (!movimientos.length) {
    tbody.innerHTML = renderEmptyRow(7, "No hay movimientos recientes.");
    return;
  }
  tbody.innerHTML = movimientos.map((movimiento) => `
    <tr>
      <td>${formatDate(movimiento.fecha)}</td>
      <td>${movimiento.producto}</td>
      <td>${movimiento.tipo}</td>
      <td>${movimiento.cantidad}</td>
      <td>${movimiento.stock_anterior}</td>
      <td>${movimiento.stock_nuevo}</td>
      <td>${movimiento.motivo || "-"}</td>
    </tr>
  `).join("");
}
