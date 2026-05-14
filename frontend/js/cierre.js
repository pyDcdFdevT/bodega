import { api, formatMoney, showToast } from "./api.js";

let lastCierreData = null;

function bloque(titulo, html) {
  return `<article class="card cierre-bloque"><h3>${titulo}</h3><div class="cierre-body">${html}</div></article>`;
}

function fila(label, valor) {
  return `<div class="cierre-line"><span>${label}</span><strong>${valor}</strong></div>`;
}

function renderCierre() {
  const data = lastCierreData;
  const root = document.getElementById("cierre-contenido");
  if (!data || !root) {
    return;
  }
  const b = data.bodega || {};
  const g = data.gasolina || {};
  const co = data.compra_oro || {};
  const gast = data.gastos || {};
  const oro = data.oro_recolectado || {};
  const caja = data.caja || {};
  const gn = data.ganancia_neta_dia;

  root.innerHTML = `
    <div class="grid two">
      ${bloque(
        "Bodega",
        `
        ${fila("Ventas reales", formatMoney(b.ventas_reales, "reales"))}
        ${fila("Ventas oro (total venta)", `${formatMoney(b.ventas_oro)} g equiv.`)}
        ${fila("Compras mercancia", `-${formatMoney(b.compras_mercancia_reales, "reales")}`)}
        ${fila("Salidas (valor oro)", `-${formatMoney(b.salidas_oro)} g`)}
      `
      )}
      ${bloque(
        "Gasolina",
        `
        ${fila("Ventas reales", formatMoney(g.ventas_reales, "reales"))}
        ${fila("Ventas oro", `${formatMoney(g.ventas_oro)} g`)}
        ${fila("Reposicion", `-${formatMoney(g.reposicion_reales, "reales")}`)}
      `
      )}
      ${bloque(
        "Compra de oro",
        `
        ${fila("Oro comprado", `+${formatMoney(co.gramos)} g`)}
        ${fila("Reales usados", `-${formatMoney(co.reales_usados, "reales")}`)}
      `
      )}
      ${bloque(
        "Gastos operativos",
        `
        ${fila("Total hoy", `-${formatMoney(gast.total_reales, "reales")}`)}
      `
      )}
    </div>
    ${bloque(
      "Oro recolectado (ventas por tipo de oro + comprado)",
      `
      ${fila("Araparita", `${formatMoney(oro.araparita)} g`)}
      ${fila("Uruman", `${formatMoney(oro.uruman)} g`)}
      ${fila("StaE Min", `${formatMoney(oro.santa_elena_minero)} g`)}
      ${fila("StaE Fun", `${formatMoney(oro.santa_elena_fundido)} g`)}
      ${fila("Comprado", `${formatMoney(oro.comprado_gramos)} g`)}
      <div class="cierre-sep"></div>
      ${fila("Bruto total", `${formatMoney(oro.bruto_total_gramos)} g`)}
    `
    )}
    ${bloque(
      "Caja (reales)",
      `
      ${fila("Saldo inicial", formatMoney(caja.saldo_inicial_reales, "reales"))}
      ${fila("Oro operativo inicial", `${Number(caja.oro_operativo_inicial ?? 0).toFixed(4)} g`)}
      ${fila("+ Ingresos (bodega + gasolina)", formatMoney(caja.ingresos_reales, "reales"))}
      ${fila("Cobros del dia (ventas fiadas)", formatMoney(data.cobros_del_dia ?? 0, "reales"))}
      ${fila("Cuentas por cobrar (total pendiente)", formatMoney(data.cuentas_por_cobrar ?? 0, "reales"))}
      ${fila("- Egresos", formatMoney(caja.egresos_reales, "reales"))}
      <div class="cierre-sep"></div>
      ${fila("Saldo final esperado", formatMoney(caja.saldo_final_reales, "reales"))}
    `
    )}
    ${gn != null ? bloque("Referencia", `${fila("Ganancia neta oro (dia, ref.)", `${formatMoney(gn)} g equiv.`)}`) : ""}
  `;
}

function updateConciliacionUi() {
  const data = lastCierreData;
  const conc = data?.conciliacion;
  const espR = document.getElementById("cierre-conc-real-esp");
  const espO = document.getElementById("cierre-conc-oro-esp");
  if (espR && conc) {
    espR.textContent = formatMoney(conc.reales_esperados, "reales");
  }
  if (espO && conc) {
    espO.textContent = `${Number(conc.oro_esperado || 0).toFixed(4)} g`;
  }

  const cr = Number(document.getElementById("cierre-conc-real-contado")?.value || 0);
  const co = Number(document.getElementById("cierre-conc-oro-contado")?.value || 0);
  const re = conc ? Number(conc.reales_esperados) : 0;
  const oe = conc ? Number(conc.oro_esperado) : 0;
  const dr = Number((cr - re).toFixed(2));
  const dor = Number((co - oe).toFixed(2));

  const elDr = document.getElementById("cierre-conc-diff-real");
  const elDo = document.getElementById("cierre-conc-diff-oro");
  if (elDr) {
    elDr.textContent = formatMoney(dr, "reales");
    elDr.classList.toggle("insuficiente", Math.abs(dr) > 0.009);
  }
  if (elDo) {
    elDo.textContent = `${dor.toFixed(4)} g`;
    elDo.classList.toggle("insuficiente", Math.abs(dor) > 0.009);
  }
}

function setCierreCerradoMode(cerrado) {
  const ids = [
    "cierre-conc-real-contado",
    "cierre-conc-oro-contado",
    "cierre-conc-justif",
    "cierre-retiro-reales",
    "cierre-retiro-oro",
    "cierre-se-deja-reales",
    "cierre-se-deja-oro",
    "btn-cierre-generar",
  ];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) {
      el.disabled = cerrado;
    }
  }
}

function renderSnapshotGuardado() {
  const wrap = document.getElementById("cierre-snapshot-wrap");
  const pre = document.getElementById("cierre-snapshot-pre");
  const cg = lastCierreData?.cierre_guardado;
  if (!wrap || !pre) {
    return;
  }
  if (cg) {
    wrap.style.display = "block";
    const detalle = cg.detalle != null ? cg.detalle : null;
    const { detalle: _d, ...rest } = cg;
    pre.textContent = JSON.stringify({ resumen: rest, detalle }, null, 2);
    setCierreCerradoMode(true);
  } else {
    wrap.style.display = "none";
    pre.textContent = "";
    setCierreCerradoMode(false);
  }
}

export async function loadCierre() {
  try {
    lastCierreData = await api.get("/cierre/dia");
    const cg = lastCierreData.cierre_guardado;
    if (cg) {
      const rin = document.getElementById("cierre-conc-real-contado");
      const oin = document.getElementById("cierre-conc-oro-contado");
      const j = document.getElementById("cierre-conc-justif");
      const rr = document.getElementById("cierre-retiro-reales");
      const ro = document.getElementById("cierre-retiro-oro");
      const sr = document.getElementById("cierre-se-deja-reales");
      const so = document.getElementById("cierre-se-deja-oro");
      if (rin) {
        rin.value = String(cg.reales_contados ?? 0);
      }
      if (oin) {
        oin.value = String(cg.oro_contado ?? 0);
      }
      if (j) {
        j.value = cg.justificacion || "";
      }
      if (rr) {
        rr.value = String(cg.retiro_dueno_reales ?? 0);
      }
      if (ro) {
        ro.value = String(cg.retiro_dueno_oro ?? 0);
      }
      if (sr) {
        sr.value = String(cg.se_deja_reales ?? 0);
      }
      if (so) {
        so.value = String(cg.se_deja_oro ?? 0);
      }
    }
    renderCierre();
    updateConciliacionUi();
    renderSnapshotGuardado();
  } catch (error) {
    showToast(error.message, "error");
  }
}

export function initCierre() {
  document.getElementById("btn-cierre-actualizar")?.addEventListener("click", () => loadCierre());

  ["cierre-conc-real-contado", "cierre-conc-oro-contado"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", () => updateConciliacionUi());
  });

  document.getElementById("btn-cierre-generar")?.addEventListener("click", async () => {
    try {
      const body = {
        cerrado_por: "Admin",
        reales_contados: Number(document.getElementById("cierre-conc-real-contado")?.value || 0),
        oro_contado: Number(document.getElementById("cierre-conc-oro-contado")?.value || 0),
        justificacion: document.getElementById("cierre-conc-justif")?.value?.trim() || "",
        retiro_dueno_reales: Number(document.getElementById("cierre-retiro-reales")?.value || 0),
        retiro_dueno_oro: Number(document.getElementById("cierre-retiro-oro")?.value || 0),
        se_deja_reales: Number(document.getElementById("cierre-se-deja-reales")?.value || 0),
        se_deja_oro: Number(document.getElementById("cierre-se-deja-oro")?.value || 0),
      };
      const resp = await api.post("/cierre/generar", body, { headers: { "X-Bodega-Rol": "admin" } });
      showToast("Cierre generado correctamente", "success");
      const wrap = document.getElementById("cierre-snapshot-wrap");
      const pre = document.getElementById("cierre-snapshot-pre");
      if (wrap && pre) {
        wrap.style.display = "block";
        pre.textContent = JSON.stringify(resp, null, 2);
      }
      setCierreCerradoMode(true);
      await loadCierre();
    } catch (error) {
      const msg = String(error.message || "");
      if (msg.includes("ya fue generado")) {
        showToast("El cierre de hoy ya fue generado", "error");
      } else {
        showToast(msg, "error");
      }
    }
  });
}
