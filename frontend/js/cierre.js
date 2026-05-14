import { api, formatMoney, showToast } from "./api.js";

let lastCierreData = null;
const manual = { ley: 0, fino: 0, tasa: 0 };

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
  const fund = data.fundicion || {};
  const pieza = data.venta_pieza || {};

  const ley = Number(manual.ley) || 0;
  const brutoFund = Number(fund.bruto_gramos || 0);
  const finoCalc = ley > 0 ? (brutoFund * ley).toFixed(2) : "0.00";

  const finoPieza = Number(manual.fino) || 0;
  const tasaPieza = Number(manual.tasa) || 0;
  const ventaPiezaVal = finoPieza > 0 && tasaPieza > 0 ? (finoPieza * tasaPieza).toFixed(2) : "0.00";

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
      ${fila("+ Ingresos (bodega + gasolina)", formatMoney(caja.ingresos_reales, "reales"))}
      ${fila("- Egresos", formatMoney(caja.egresos_reales, "reales"))}
      <div class="cierre-sep"></div>
      ${fila("Saldo final", formatMoney(caja.saldo_final_reales, "reales"))}
    `
    )}
    ${bloque(
      "Fundicion (manual)",
      `
      ${fila("Bruto (desde oro recolectado ventas)", `${formatMoney(fund.bruto_gramos)} g`)}
      <label class="cierre-inline">Ley (0-1)
        <input type="number" id="cierre-fundicion-ley" min="0" max="1" step="0.001" value="${manual.ley || ""}">
      </label>
      ${fila("Fino estimado", `${finoCalc} g`)}
      <p class="muted small">${fund.nota || ""}</p>
    `
    )}
    ${bloque(
      "Venta pieza (manual)",
      `
      <label class="cierre-inline">Fino (g)
        <input type="number" id="cierre-pieza-fino" min="0" step="0.01" value="${manual.fino || ""}">
      </label>
      <label class="cierre-inline">Tasa R$/g
        <input type="number" id="cierre-pieza-tasa" min="0" step="0.01" value="${manual.tasa || ""}">
      </label>
      ${fila("Fino x Tasa", `R$ ${ventaPiezaVal}`)}
      <p class="muted small">${pieza.nota || ""}</p>
    `
    )}
  `;

  const bind = (id, key) => {
    const el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.addEventListener("input", () => {
      manual[key] = Number(el.value);
      renderCierre();
    });
  };
  bind("cierre-fundicion-ley", "ley");
  bind("cierre-pieza-fino", "fino");
  bind("cierre-pieza-tasa", "tasa");
}

export async function loadCierre() {
  const saldo = Number(document.getElementById("cierre-saldo-inicial")?.value || 0);
  try {
    lastCierreData = await api.get(`/cierre/dia?saldo_inicial_reales=${encodeURIComponent(saldo)}`);
    renderCierre();
  } catch (error) {
    showToast(error.message, "error");
  }
}

export function initCierre() {
  document.getElementById("cierre-saldo-inicial")?.addEventListener("change", () => loadCierre());
  document.getElementById("btn-cierre-actualizar")?.addEventListener("click", () => loadCierre());
  document.getElementById("btn-cierre-generar")?.addEventListener("click", async () => {
    const saldo = Number(document.getElementById("cierre-saldo-inicial")?.value || 0);
    try {
      await api.post(
        "/cierre/generar",
        { cerrado_por: "Admin", saldo_inicial_reales: saldo },
        { headers: { "X-Bodega-Rol": "admin" } }
      );
      showToast("Cierre generado correctamente", "success");
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
