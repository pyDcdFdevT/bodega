import { api, formatMoney, formatTimeOnly, renderEmptyRow } from "./api.js";

function renderDashboard(data) {
  const container = document.getElementById("dashboard-cards");
  if (!container || !data) {
    return;
  }
  const op = data.operaciones_hoy || {};
  const inv = data.inventario || {};
  container.innerHTML = `
    <article class="metric-pill"><span>Productos activos</span><strong>${inv.productos_activos ?? 0}</strong></article>
    <article class="metric-pill"><span>Stock bajo (cant.)</span><strong>${inv.stock_bajo ?? 0}</strong></article>
    <article class="metric-pill"><span>Ventas hoy (R$)</span><strong>${formatMoney(op.ventas_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Ventas hoy (oro)</span><strong>${formatMoney(op.ventas_oro)}</strong></article>
    <article class="metric-pill"><span>Compras hoy (R$)</span><strong>${formatMoney(op.compras_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Compras hoy (oro)</span><strong>${formatMoney(op.compras_oro)}</strong></article>
    <article class="metric-pill"><span>Gastos hoy (R$)</span><strong>${formatMoney(op.gastos_reales, "reales")}</strong></article>
    <article class="metric-pill"><span>Oro Araparita</span><strong>${formatMoney(op.oro_araparita)}</strong></article>
    <article class="metric-pill"><span>Oro Uruman</span><strong>${formatMoney(op.oro_uruman)}</strong></article>
    <article class="metric-pill"><span>Oro StaE Min</span><strong>${formatMoney(op.oro_santa_elena_minero)}</strong></article>
    <article class="metric-pill"><span>Oro StaE Fun</span><strong>${formatMoney(op.oro_santa_elena_fundido)}</strong></article>
    <article class="metric-pill"><span>Oro total cobrado</span><strong>${formatMoney(op.oro_total)}</strong></article>
    <article class="metric-pill"><span>Ganancia neta (oro ref.)</span><strong>${formatMoney(op.ganancia_neta)}</strong></article>
  `;

  const tbStock = document.getElementById("tabla-dashboard-stock-bajo");
  const alertas = inv.stock_bajo_alertas || [];
  if (tbStock) {
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

  const tbVentas = document.getElementById("tabla-dashboard-ventas");
  const uv = data.ultimas_ventas || [];
  if (tbVentas) {
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

  const tbMov = document.getElementById("tabla-dashboard-movimientos");
  const um = data.ultimos_movimientos || [];
  if (tbMov) {
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
}

export async function loadDashboard() {
  const dashboard = await api.get("/reportes/dashboard");
  renderDashboard(dashboard);
}
