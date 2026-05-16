import { api, formatDate, formatMoney, showToast } from "./api.js";

let deudasCache = [];

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function abrirModalPago(deuda) {
  const dialog = document.getElementById("dialog-pago-proveedor");
  const compraId = document.getElementById("pago-proveedor-compra-id");
  const proveedor = document.getElementById("pago-proveedor-proveedor");
  const saldo = document.getElementById("pago-proveedor-saldo");
  const monto = document.getElementById("pago-proveedor-monto");
  if (!dialog || !compraId || !monto) {
    return;
  }
  compraId.value = String(deuda.compra_id);
  if (proveedor) {
    proveedor.textContent = deuda.proveedor || "—";
  }
  if (saldo) {
    saldo.textContent = formatMoney(deuda.saldo_pendiente, "reales");
  }
  monto.value = String(Number(deuda.saldo_pendiente || 0).toFixed(2));
  monto.max = String(deuda.saldo_pendiente || 0);
  dialog.showModal();
}

export function renderPagosProveedores(deudasData, historialData) {
  const root = document.getElementById("pagos-proveedores-content");
  const badge = document.getElementById("pagos-proveedores-badge");
  if (!root) {
    return;
  }

  deudasCache = deudasData?.deudas || [];
  const total = Number(deudasData?.total_pendiente ?? 0);
  if (badge) {
    badge.textContent = `Pendiente: ${formatMoney(total, "reales")}`;
  }

  const deudasHtml = deudasCache.length
    ? `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Proveedor</th>
            <th>Compra</th>
            <th>Pagado</th>
            <th>Saldo</th>
            <th>Fecha</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${deudasCache
            .map(
              (d) => `
            <tr>
              <td>${d.compra_id}</td>
              <td>${escapeHtml(d.proveedor)}</td>
              <td>${formatMoney(d.total_reales, "reales")}</td>
              <td>${formatMoney(d.monto_pagado, "reales")}</td>
              <td><strong>${formatMoney(d.saldo_pendiente, "reales")}</strong></td>
              <td>${d.fecha ? formatDate(d.fecha) : "—"}</td>
              <td>
                <button type="button" class="btn-secondary btn-pago-proveedor" data-compra-id="${d.compra_id}">
                  Registrar pago
                </button>
              </td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`
    : '<p class="muted">No hay deudas pendientes con proveedores.</p>';

  const pagos = historialData?.pagos || [];
  const historialHtml = pagos.length
    ? `
    <h4 class="pagos-proveedores-sub">Historial de pagos</h4>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Proveedor</th>
            <th>Compra</th>
            <th>Monto</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          ${pagos
            .map(
              (p) => `
            <tr>
              <td>#${p.id}</td>
              <td>${escapeHtml(p.proveedor)}</td>
              <td>#${p.compra_id}</td>
              <td>${formatMoney(p.monto, "reales")}</td>
              <td>${p.fecha ? formatDate(p.fecha) : "—"}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`
    : '<p class="muted">Aun no hay pagos registrados.</p>';

  root.innerHTML = `
    <p class="report-item" style="margin:0 0 12px;">
      Total pendiente: <strong>${formatMoney(total, "reales")}</strong>
      · ${deudasData?.cantidad_compras ?? deudasCache.length} compra(s)
    </p>
    ${deudasHtml}
    ${historialHtml}
  `;

  root.querySelectorAll(".btn-pago-proveedor").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.compraId);
      const deuda = deudasCache.find((d) => d.compra_id === id);
      if (deuda) {
        abrirModalPago(deuda);
      }
    });
  });
}

export async function loadPagosProveedores() {
  const root = document.getElementById("pagos-proveedores-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando pagos a proveedores…</p>';
  }
  try {
    const [deudas, historial] = await Promise.all([
      api.get("/proveedores/deudas"),
      api.get("/proveedores/pagos?limit=50"),
    ]);
    renderPagosProveedores(deudas, historial);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${escapeHtml(error.message || "Error al cargar")}</p>`;
    }
  }
}

export function initPagosProveedores() {
  document.getElementById("btn-pagos-proveedores-refresh")?.addEventListener("click", () => {
    loadPagosProveedores();
  });

  document.getElementById("form-pago-proveedor")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const compraId = Number(document.getElementById("pago-proveedor-compra-id")?.value || 0);
    const monto = Number(document.getElementById("pago-proveedor-monto")?.value || 0);
    if (!compraId || monto <= 0) {
      showToast("Indique un monto valido", "error");
      return;
    }
    try {
      const res = await api.post("/proveedores/pagar", { compra_id: compraId, monto });
      document.getElementById("dialog-pago-proveedor")?.close();
      showToast(
        res.pagada
          ? "Pago registrado. Compra saldada."
          : `Pago registrado. Saldo: ${formatMoney(res.saldo_pendiente, "reales")}`,
        "success"
      );
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
