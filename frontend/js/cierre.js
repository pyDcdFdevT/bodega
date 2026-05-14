import { api, formatMoney, showToast } from "./api.js";

let lastCierreData = null;
let lastAperturaPayload = null;
let aperturaInputsPrimed = false;
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
  const gn = data.ganancia_neta_dia;

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
      ${fila("Oro operativo inicial", `${Number(caja.oro_operativo_inicial ?? 0).toFixed(2)} g`)}
      ${fila("+ Ingresos (bodega + gasolina)", formatMoney(caja.ingresos_reales, "reales"))}
      ${fila("- Egresos", formatMoney(caja.egresos_reales, "reales"))}
      <div class="cierre-sep"></div>
      ${fila("Saldo final esperado", formatMoney(caja.saldo_final_reales, "reales"))}
    `
    )}
    ${gn != null ? bloque("Referencia", `${fila("Ganancia neta oro (dia, ref.)", `${formatMoney(gn)} g equiv.`)}`) : ""}
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

function setAperturaEstado(text) {
  const el = document.getElementById("cierre-apertura-estado");
  if (el) {
    el.textContent = text;
  }
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
    espO.textContent = `${Number(conc.oro_esperado || 0).toFixed(2)} g`;
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
    elDo.textContent = `${dor.toFixed(2)} g`;
    elDo.classList.toggle("insuficiente", Math.abs(dor) > 0.009);
  }
}

function setAperturaCerradaMode(registrada) {
  document.getElementById("cierre-apertura-caja")?.toggleAttribute("disabled", registrada);
  document.getElementById("cierre-apertura-oro")?.toggleAttribute("disabled", registrada);
  document.getElementById("btn-cierre-registrar-apertura")?.toggleAttribute("disabled", registrada);
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
  setAperturaCerradaMode(!!lastAperturaPayload?.apertura_hoy);
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

async function cargarAperturaUi() {
  try {
    lastAperturaPayload = await api.get("/cierre/apertura");
    const ap = lastAperturaPayload;
    const cajaIn = document.getElementById("cierre-apertura-caja");
    const oroIn = document.getElementById("cierre-apertura-oro");
    if (ap.apertura_hoy) {
      setAperturaEstado(`Apertura registrada (${ap.apertura_hoy.abierto_por}).`);
      if (cajaIn) {
        cajaIn.value = String(ap.apertura_hoy.caja_inicial_reales);
      }
      if (oroIn) {
        oroIn.value = String(ap.apertura_hoy.oro_operativo_inicial);
      }
      aperturaInputsPrimed = true;
    } else {
      setAperturaEstado("Indique saldos iniciales y registre la apertura (sugerencia desde el cierre de ayer).");
      if (cajaIn && oroIn && !aperturaInputsPrimed) {
        cajaIn.value = String(ap.sugerencia?.caja_inicial_reales ?? 0);
        oroIn.value = String(ap.sugerencia?.oro_operativo_inicial ?? 0);
        aperturaInputsPrimed = true;
      }
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

export async function loadCierre() {
  try {
    await cargarAperturaUi();
    const params = new URLSearchParams();
    if (!lastAperturaPayload?.apertura_hoy) {
      const c = document.getElementById("cierre-apertura-caja")?.value;
      const o = document.getElementById("cierre-apertura-oro")?.value;
      if (c !== undefined && c !== "") {
        params.set("caja_inicial_reales", String(Number(c)));
      }
      if (o !== undefined && o !== "") {
        params.set("oro_operativo_inicial", String(Number(o)));
      }
    }
    const qs = params.toString();
    lastCierreData = await api.get(`/cierre/dia${qs ? `?${qs}` : ""}`);
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
  document.getElementById("btn-cierre-actualizar")?.addEventListener("click", () => {
    aperturaInputsPrimed = false;
    loadCierre();
  });

  ["cierre-apertura-caja", "cierre-apertura-oro"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", () => {
      if (!lastAperturaPayload?.apertura_hoy) {
        loadCierre();
      }
    });
  });

  document.getElementById("btn-cierre-registrar-apertura")?.addEventListener("click", async () => {
    const caja = Number(document.getElementById("cierre-apertura-caja")?.value || 0);
    const oro = Number(document.getElementById("cierre-apertura-oro")?.value || 0);
    try {
      await api.post(
        "/cierre/apertura",
        { caja_inicial_reales: caja, oro_operativo_inicial: oro, abierto_por: "Admin" },
        { headers: { "X-Bodega-Rol": "admin" } }
      );
      showToast("Apertura registrada", "success");
      aperturaInputsPrimed = true;
      await loadCierre();
    } catch (error) {
      const msg = String(error.message || "");
      if (msg.includes("ya fue registrada")) {
        showToast("La apertura de hoy ya fue registrada", "error");
      } else {
        showToast(msg, "error");
      }
    }
  });

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
