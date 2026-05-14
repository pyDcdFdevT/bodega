import { api, formatDateOnly, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";

let pendientesCache = [];

function cerrarModalPago() {
  document.getElementById("dialog-registrar-pago-cobro")?.close();
}

export async function loadCobros() {
  const tbodyP = document.getElementById("tabla-cobros-pendientes");
  const tbodyH = document.getElementById("tabla-cobros-pagos-hoy");
  if (!tbodyP || !tbodyH) {
    return;
  }
  try {
    const [pend, pagos] = await Promise.all([api.get("/cobros/pendientes"), api.get("/cobros/pagos-hoy")]);
    pendientesCache = pend;
    if (!pend.length) {
      tbodyP.innerHTML = renderEmptyRow(5, "No hay cuentas pendientes.");
    } else {
      tbodyP.innerHTML = pend
        .map(
          (v) => `
        <tr>
          <td>${formatDateOnly(v.fecha)} ${formatTimeOnly(v.fecha)}</td>
          <td>${String(v.cliente || "")}</td>
          <td>${formatMoney(v.total_reales, "reales")}</td>
          <td>${formatMoney(v.saldo_pendiente, "reales")}</td>
          <td><button type="button" class="btn-refresh" data-cobro-pago="${v.id}" style="padding:6px 12px;font-size:0.85rem;">Pago</button></td>
        </tr>`
        )
        .join("");
    }

    if (!pagos.length) {
      tbodyH.innerHTML = renderEmptyRow(5, "Sin pagos registrados hoy.");
    } else {
      tbodyH.innerHTML = pagos
        .map(
          (p) => `
        <tr>
          <td>${formatTimeOnly(p.fecha)}</td>
          <td>#${p.venta_id}</td>
          <td>${String(p.cliente || "")}</td>
          <td>${p.moneda === "oro" ? `${Number(p.monto).toFixed(4)} g` : formatMoney(p.monto, "reales")} <span class="muted">(≈ ${formatMoney(p.monto_reales_equivalente, "reales")})</span></td>
          <td>${String(p.tipo_pago || "")}</td>
        </tr>`
        )
        .join("");
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

function abrirModalPago(ventaId) {
  const v = pendientesCache.find((x) => x.id === ventaId);
  const dlg = document.getElementById("dialog-registrar-pago-cobro");
  const form = document.getElementById("form-registrar-pago-cobro");
  if (!v || !dlg?.showModal || !form) {
    return;
  }
  document.getElementById("cobro-pago-venta-id").value = String(v.id);
  document.getElementById("cobro-pago-monto").value = String(Number(v.saldo_pendiente).toFixed(2));
  document.getElementById("cobro-pago-monto").max = String(Number(v.saldo_pendiente) + 0.01);
  const monSel = document.getElementById("cobro-pago-moneda");
  if (monSel) {
    const allowOro = Boolean(v.tasa_nombre);
    const optOro = monSel.querySelector('option[value="oro"]');
    if (optOro) {
      optOro.disabled = !allowOro;
    }
    monSel.value = "reales";
  }
  const res = document.getElementById("cobro-pago-resumen");
  if (res) {
    res.textContent = `Venta #${v.id} — ${v.cliente}. Saldo: ${formatMoney(v.saldo_pendiente, "reales")}.`;
  }
  document.getElementById("cobro-pago-tipo").value = "";
  dlg.showModal();
}

export function initCobros() {
  document.getElementById("btn-cobros-actualizar")?.addEventListener("click", () => loadCobros());

  document.getElementById("tabla-cobros-pendientes")?.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-cobro-pago]");
    const id = btn?.dataset?.cobroPago;
    if (id) {
      abrirModalPago(Number(id));
    }
  });

  document.getElementById("btn-cobro-pago-cancelar")?.addEventListener("click", cerrarModalPago);

  document.getElementById("form-registrar-pago-cobro")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const fd = new FormData(form);
    const payload = {
      venta_id: Number(fd.get("venta_id")),
      monto: Number(fd.get("monto")),
      moneda: fd.get("moneda"),
      tipo_pago: String(fd.get("tipo_pago") || "").trim(),
      registrado_por: "Admin",
    };
    if (!payload.tipo_pago) {
      showToast("Indique el tipo de pago", "error");
      return;
    }
    try {
      await api.post("/cobros/registrar-pago", payload);
      showToast("Pago registrado", "success");
      cerrarModalPago();
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}
