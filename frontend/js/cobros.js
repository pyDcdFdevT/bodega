import { api, formatDateOnly, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";
import { ensureTasas, findTasaByNombre, getRateLabel } from "./tasas.js";

let pendientesCache = [];
/** Saldo en R$ de la venta abierta en el modal (para confirmar exceso). */
let modalSaldoPendienteReales = 0;

function redondear2(n) {
  return Math.round(Number(n) * 100) / 100;
}

/** Replica la lógica de abono en reales del backend para el modal. */
function abonoRealesEstimado(canal, monto, tipoOro) {
  if (canal === "efectivo") {
    return redondear2(monto);
  }
  if (canal === "oro") {
    const t = tipoOro ? findTasaByNombre(tipoOro) : null;
    const tr = t ? Number(t.tasa_reales) : 0;
    if (!Number.isFinite(tr) || tr <= 0) {
      return NaN;
    }
    return redondear2(Number(monto) * tr);
  }
  return NaN;
}

function cerrarModalPago() {
  document.getElementById("dialog-registrar-pago-cobro")?.close();
}

function canalCobro() {
  return document.getElementById("cobro-pago-canal")?.value || "";
}

function actualizarVistaModalCobro() {
  const canal = canalCobro();
  const wrapR = document.getElementById("cobro-pago-reales-wrap");
  const wrapO = document.getElementById("cobro-pago-oro-wrap");
  const inpReal = document.getElementById("cobro-pago-monto");
  const inpOro = document.getElementById("cobro-pago-monto-oro");
  const selOro = document.getElementById("cobro-pago-tipo-oro");
  if (!wrapR || !wrapO || !inpReal || !inpOro) {
    return;
  }
  if (canal === "oro") {
    wrapR.style.display = "none";
    wrapO.style.display = "grid";
    inpReal.removeAttribute("required");
    selOro.required = true;
    inpOro.required = true;
    inpReal.name = "";
    inpOro.name = "monto";
  } else {
    wrapR.style.display = "grid";
    wrapO.style.display = "none";
    inpReal.setAttribute("required", "required");
    selOro.required = false;
    inpOro.required = false;
    inpReal.name = "monto";
    inpOro.name = "";
    selOro.value = "";
    document.getElementById("cobro-pago-tasa-valor").textContent = "—";
    document.getElementById("cobro-pago-equiv-reales").textContent = "";
  }
  actualizarTasaYEquivalenteOro();
}

function actualizarTasaYEquivalenteOro() {
  const elTasa = document.getElementById("cobro-pago-tasa-valor");
  const elEq = document.getElementById("cobro-pago-equiv-reales");
  const selOro = document.getElementById("cobro-pago-tipo-oro");
  const inpOro = document.getElementById("cobro-pago-monto-oro");
  if (!elTasa || !elEq || !selOro || !inpOro) {
    return;
  }
  if (canalCobro() !== "oro") {
    return;
  }
  const nombre = selOro.value;
  const tasa = nombre ? findTasaByNombre(nombre) : null;
  if (!tasa) {
    elTasa.textContent = "—";
    elEq.textContent = nombre ? "No hay tasa cargada para ese tipo." : "Seleccione tipo de oro.";
    return;
  }
  elTasa.textContent = Number(tasa.tasa_reales).toFixed(2);
  const g = Number(inpOro.value || 0);
  const eq = g > 0 && tasa.tasa_reales > 0 ? g * Number(tasa.tasa_reales) : 0;
  elEq.textContent =
    g > 0 ? `Equivalente contra saldo: ${formatMoney(eq, "reales")} (según tasa operativa).` : "Indique los gramos a abonar.";
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
        .map((p) => {
          const montoTxt =
            p.moneda === "oro"
              ? `${Number(p.monto).toFixed(4)} g (${getRateLabel(p.tipo_oro) || p.tipo_oro || "—"})`
              : formatMoney(p.monto, "reales");
          return `
        <tr>
          <td>${formatTimeOnly(p.fecha)}</td>
          <td>#${p.venta_id}</td>
          <td>${String(p.cliente || "")}</td>
          <td>${montoTxt} <span class="muted">(≈ ${formatMoney(p.monto_reales_equivalente, "reales")})</span></td>
          <td>${String(p.tipo_pago || "")}</td>
        </tr>`;
        })
        .join("");
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    showToast(msg || "Error al cargar cobros", "error");
  }
}

async function abrirModalPago(ventaId) {
  await ensureTasas();
  const v = pendientesCache.find((x) => x.id === ventaId);
  const dlg = document.getElementById("dialog-registrar-pago-cobro");
  const form = document.getElementById("form-registrar-pago-cobro");
  if (!v || !dlg?.showModal || !form) {
    return;
  }
  form.reset();
  document.getElementById("cobro-pago-venta-id").value = String(v.id);
  const inpReal = document.getElementById("cobro-pago-monto");
  const inpOro = document.getElementById("cobro-pago-monto-oro");
  if (inpReal) {
    inpReal.value = String(Number(v.saldo_pendiente).toFixed(2));
    inpReal.removeAttribute("max");
    inpReal.name = "monto";
  }
  if (inpOro) {
    inpOro.value = "";
  }
  document.getElementById("cobro-pago-canal").value = "";
  actualizarVistaModalCobro();

  const res = document.getElementById("cobro-pago-resumen");
  if (res) {
    res.textContent = `Venta #${v.id} — ${v.cliente}. Saldo: ${formatMoney(v.saldo_pendiente, "reales")}.`;
  }
  modalSaldoPendienteReales = redondear2(v.saldo_pendiente);
  const lineOro = document.getElementById("cobro-pago-saldo-oro-line");
  if (lineOro) {
    const nombre = String(v.tipo_oro || "").trim();
    if (!nombre) {
      lineOro.textContent = "Saldo en oro: — (venta sin tipo de oro en la tasa de la venta).";
    } else {
      const t = findTasaByNombre(nombre);
      const tr = t ? Number(t.tasa_reales) : 0;
      if (!Number.isFinite(tr) || tr <= 0) {
        lineOro.textContent = `Saldo en oro: — (sin tasa operativa para ${getRateLabel(nombre) || nombre}).`;
      } else {
        const g = Number(v.saldo_pendiente) / tr;
        lineOro.textContent = `Saldo en oro: ${g.toFixed(4)} g (${getRateLabel(nombre) || nombre}).`;
      }
    }
  }
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

  document.getElementById("cobro-pago-canal")?.addEventListener("change", actualizarVistaModalCobro);
  document.getElementById("cobro-pago-tipo-oro")?.addEventListener("change", actualizarTasaYEquivalenteOro);
  document.getElementById("cobro-pago-monto-oro")?.addEventListener("input", actualizarTasaYEquivalenteOro);

  document.getElementById("form-registrar-pago-cobro")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";
    const fd = new FormData(form);
    const canal = String(fd.get("tipo_pago") || "").trim().toLowerCase();
    if (!canal || !["efectivo", "oro"].includes(canal)) {
      showToast("Seleccione la forma de cobro", "error");
      return;
    }
    let monto = 0;
    let tipoOroPago = null;
    if (canal === "oro") {
      monto = Number(document.getElementById("cobro-pago-monto-oro")?.value || 0);
      tipoOroPago = String(fd.get("tipo_oro") || "").trim();
      if (!tipoOroPago) {
        showToast("Seleccione el tipo de oro", "error");
        return;
      }
    } else {
      monto = Number(document.getElementById("cobro-pago-monto")?.value || 0);
    }
    if (!Number.isFinite(monto) || monto <= 0) {
      showToast("Indique un monto valido", "error");
      return;
    }
    const abonoEst = abonoRealesEstimado(canal, monto, tipoOroPago);
    if (!Number.isFinite(abonoEst) || abonoEst <= 0) {
      showToast("No se pudo calcular el abono en reales (revise tasa y montos).", "error");
      return;
    }
    if (abonoEst > modalSaldoPendienteReales + 0.01) {
      const solo = formatMoney(modalSaldoPendienteReales, "reales");
      const ok = window.confirm(
        `El abono supera el saldo pendiente (${solo}). ¿Registrar solo lo pendiente (${solo})?`
      );
      if (!ok) {
        return;
      }
    }
    const ventaId = Number(document.getElementById("cobro-pago-venta-id")?.value || fd.get("venta_id"));
    const payload = {
      venta_id: ventaId,
      monto,
      tipo_pago: canal,
      tipo_oro: canal === "oro" ? tipoOroPago : null,
      registrado_por: "Admin",
    };
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Registrando...";
    }
    try {
      const data = await api.post("/cobros/registrar-pago", payload);
      const abono = data.abono_reales != null ? formatMoney(data.abono_reales, "reales") : "";
      const saldo = data.saldo_pendiente != null ? formatMoney(data.saldo_pendiente, "reales") : "";
      const cap =
        data.abono_capado_a_saldo === true
          ? " Se aplicó solo hasta el saldo pendiente."
          : "";
      showToast(
        `Pago registrado. Abono ${abono}. Saldo pendiente: ${saldo}. Estado: ${data.estado_pago || ""}.${cap}`,
        "success"
      );
      cerrarModalPago();
      await loadCobros();
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(msg || "Error al registrar el pago", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    }
  });
}
