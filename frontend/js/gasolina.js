import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { ensureTasas, fillTasaSelect, findTasaById, findTasaByNombre, getRateLabel, RATE_ORDER } from "./tasas.js";

let gasolinaConfigCache = null;

function renderResumen(gasolina) {
  const target = document.getElementById("gasolina-resumen");
  if (!target) {
    return;
  }
  if (!gasolina) {
    target.innerHTML = `
    <article class="metric-pill">
      <span>Litros disponibles</span>
      <strong>0.00</strong>
    </article>
    <article class="metric-pill">
      <span>Precio base (R$/L)</span>
      <strong>${formatMoney(0, "reales")}</strong>
    </article>
    <p class="muted small">Sin registro de gasolina. Use configurar o ejecute init_data.</p>
  `;
    return;
  }
  const pr = Number(gasolina.precio_por_litro_reales ?? gasolina.precio_por_litro_oro ?? 0);
  target.innerHTML = `
    <article class="metric-pill">
      <span>Litros disponibles</span>
      <strong>${Number(gasolina.litros_disponibles || 0).toFixed(2)}</strong>
    </article>
    <article class="metric-pill">
      <span>Precio base (R$/L)</span>
      <strong>${formatMoney(pr, "reales")}</strong>
    </article>
  `;
}

function tasaParaPreviewVenta() {
  const tipoPago = document.getElementById("gasolina-tipo-pago")?.value;
  if (tipoPago === "reales") {
    return findTasaByNombre("araparita") || findTasaByNombre("uruman");
  }
  const id = Number(document.getElementById("gasolina-tasa")?.value);
  return findTasaById(id);
}

function datosTotalesGasolinaVenta() {
  const litros = Number(document.getElementById("gasolina-venta-litros")?.value);
  const gasolina = gasolinaConfigCache;
  const precioR = gasolina ? Number(gasolina.precio_por_litro_reales ?? gasolina.precio_por_litro_oro ?? 0) : 0;
  const litrosValid = Number.isFinite(litros) && litros > 0;
  let totalReales = 0;
  if (litrosValid && precioR > 0) {
    totalReales = Number((litros * precioR).toFixed(2));
  }
  const tasa = tasaParaPreviewVenta();
  let totalOro = 0;
  if (tasa && tasa.tasa_reales > 0 && totalReales > 0) {
    totalOro = Number((totalReales / tasa.tasa_reales).toFixed(4));
  }
  return { totalOro, totalReales, tasa, litrosValid };
}

function actualizarGasolinaTotalesACobrar() {
  const el = document.getElementById("gasolina-cobro-total-resumen");
  if (!el) {
    return;
  }
  const tipoPago = document.getElementById("gasolina-tipo-pago")?.value || "oro";
  const { totalOro, totalReales, litrosValid } = datosTotalesGasolinaVenta();
  if (!litrosValid || totalReales <= 0) {
    el.innerHTML = "";
    return;
  }
  if (tipoPago === "reales") {
    el.innerHTML = `<strong>Total a cobrar:</strong> ${formatMoney(totalReales, "reales")}`;
  } else if (tipoPago === "oro") {
    el.innerHTML = `<strong>Total a cobrar:</strong> ${totalOro.toFixed(4)} g`;
  } else {
    el.innerHTML = `
      <div><strong>Total a cobrar (oro):</strong> ${totalOro.toFixed(4)} g</div>
      <div><strong>Total a cobrar (reales en precios):</strong> ${formatMoney(totalReales, "reales")}</div>
    `;
  }
}

function actualizarGasolinaVueltoPreview() {
  const el = document.getElementById("gasolina-cobro-vuelto-preview");
  if (!el) {
    return;
  }
  el.classList.remove("insuficiente");
  const tipoPago = document.getElementById("gasolina-tipo-pago")?.value || "oro";
  const mOro = Number(document.getElementById("gasolina-monto-oro")?.value || 0);
  const mReales = Number(document.getElementById("gasolina-monto-reales")?.value || 0);
  const { totalOro, totalReales, tasa, litrosValid } = datosTotalesGasolinaVenta();

  if (!litrosValid || totalReales <= 0) {
    el.textContent = "";
    return;
  }

  if (tipoPago === "reales") {
    const diff = Number((mReales - totalReales).toFixed(2));
    if (diff >= 0) {
      el.textContent = `Vuelto: ${formatMoney(diff, "reales")}`;
    } else {
      el.classList.add("insuficiente");
      el.textContent = `Falta: ${formatMoney(-diff, "reales")}`;
    }
    return;
  }

  if (!tasa || !tasa.tasa_reales) {
    el.textContent = "Seleccione tipo de oro y tasa para ver el vuelto";
    return;
  }

  const recibidoEquivOro = Number((mOro + mReales / tasa.tasa_reales).toFixed(4));
  const diffOro = Number((recibidoEquivOro - totalOro).toFixed(4));

  if (tipoPago === "oro") {
    if (diffOro >= 0) {
      el.textContent = `Vuelto: ${diffOro.toFixed(4)}g`;
    } else {
      el.classList.add("insuficiente");
      el.textContent = `Falta: ${(-diffOro).toFixed(4)}g`;
    }
    return;
  }

  if (diffOro >= 0) {
    const vueltoReales = Number((diffOro * tasa.tasa_reales).toFixed(2));
    el.textContent = `Vuelto: ${formatMoney(vueltoReales, "reales")}`;
  } else {
    el.classList.add("insuficiente");
    const faltaReales = Number((-diffOro * tasa.tasa_reales).toFixed(2));
    el.textContent = `Falta: ${formatMoney(faltaReales, "reales")}`;
  }
}

function actualizarResumenCobroGasolina() {
  actualizarGasolinaTotalesACobrar();
  actualizarGasolinaVueltoPreview();
}

function actualizarPreviewRepo() {
  const litros = Number(document.querySelector("#form-gasolina-reponer input[name=litros]")?.value);
  const precio = Number(document.querySelector("#form-gasolina-reponer input[name=precio_reales_litro]")?.value);
  const totalReales = Number.isFinite(litros) && Number.isFinite(precio) ? litros * precio : 0;
  const elR = document.getElementById("gasolina-repo-total-reales");
  const body = document.getElementById("gasolina-repo-equiv-oro-body");
  if (elR) {
    elR.value = Number.isFinite(totalReales) ? totalReales.toFixed(2) : "0.00";
  }
  if (body) {
    if (!Number.isFinite(totalReales) || totalReales <= 0) {
      body.innerHTML = "<p>Ingrese litros y precio para ver equivalentes.</p>";
    } else {
      body.innerHTML = RATE_ORDER.map((nombre) => {
        const t = findTasaByNombre(nombre);
        const tr = t ? Number(t.tasa_reales) : 0;
        const g = tr > 0 ? totalReales / tr : null;
        const txt = g != null ? `${g.toFixed(4)} g` : "—";
        return `<div class="cierre-line"><span>${getRateLabel(nombre)}</span><strong>${txt}</strong></div>`;
      }).join("");
    }
  }
}

function actualizarVisibilidadPagoGasolina() {
  const tipoPago = document.getElementById("gasolina-tipo-pago")?.value;
  const tasaWrap = document.getElementById("gasolina-tasa-wrap");
  const tipoOroWrap = document.getElementById("gasolina-tipo-oro-wrap");
  const wrapMontoOro = document.getElementById("gasolina-monto-oro-wrap");
  const wrapMontoReales = document.getElementById("gasolina-monto-reales-wrap");
  const tipoOroSelect = document.getElementById("gasolina-tipo-oro");

  const requiereConversion = tipoPago !== "reales";
  if (tasaWrap) {
    tasaWrap.style.display = requiereConversion ? "grid" : "none";
  }
  if (tipoOroWrap) {
    tipoOroWrap.style.display = requiereConversion ? "grid" : "none";
  }
  if (tipoOroSelect) {
    tipoOroSelect.required = requiereConversion;
  }

  if (wrapMontoOro && wrapMontoReales) {
    if (tipoPago === "reales") {
      wrapMontoOro.style.display = "none";
      wrapMontoReales.style.display = "grid";
    } else if (tipoPago === "oro") {
      wrapMontoOro.style.display = "grid";
      wrapMontoReales.style.display = "none";
    } else {
      wrapMontoOro.style.display = "grid";
      wrapMontoReales.style.display = "grid";
    }
  }

  if (!requiereConversion && tipoOroSelect) {
    tipoOroSelect.value = "";
  }
  actualizarPreviewVentaGasolina();
}

function actualizarPreviewVentaGasolina() {
  const litros = Number(document.getElementById("gasolina-venta-litros")?.value);
  const gasolina = gasolinaConfigCache;
  const precioR = gasolina ? Number(gasolina.precio_por_litro_reales ?? gasolina.precio_por_litro_oro ?? 0) : 0;
  const tasa = tasaParaPreviewVenta();

  let totalOro = 0;
  let totalReales = 0;
  if (Number.isFinite(litros) && litros > 0 && precioR > 0) {
    totalReales = Number((litros * precioR).toFixed(2));
    if (tasa && tasa.tasa_reales > 0) {
      totalOro = totalReales / tasa.tasa_reales;
    }
  }

  const elO = document.getElementById("gasolina-preview-oro");
  const elR = document.getElementById("gasolina-preview-reales");
  const tipoPago = document.getElementById("gasolina-tipo-pago")?.value;
  if (elO && elR) {
    if (tipoPago === "reales") {
      elO.textContent = "0.00";
      elR.textContent = formatMoney(totalReales, "reales");
    } else {
      elO.textContent = Number.isFinite(totalOro) ? totalOro.toFixed(4) : "0.0000";
      elR.textContent = formatMoney(Number.isFinite(totalReales) ? totalReales : 0, "reales");
    }
  }
  actualizarResumenCobroGasolina();
}

function sincronizarTasaDesdeTipoOro() {
  const nombre = document.getElementById("gasolina-tipo-oro")?.value;
  const tasa = findTasaByNombre(nombre);
  const select = document.getElementById("gasolina-tasa");
  if (tasa && select) {
    select.value = String(tasa.id);
  }
  actualizarPreviewVentaGasolina();
}

function sincronizarTipoOroDesdeTasa() {
  const id = Number(document.getElementById("gasolina-tasa")?.value);
  const tasa = findTasaById(id);
  const tipoOro = document.getElementById("gasolina-tipo-oro");
  if (tasa && tipoOro) {
    tipoOro.value = tasa.nombre;
  }
  actualizarPreviewVentaGasolina();
}

export async function loadGasolina() {
  await ensureTasas();
  fillTasaSelect("gasolina-tasa");

  const [gasolina, ventas] = await Promise.all([api.get("/gasolina"), api.get("/gasolina/ventas")]);
  gasolinaConfigCache = gasolina;

  renderResumen(gasolina);
  const form = document.getElementById("form-gasolina-config");
  if (form && gasolina) {
    form.tipo.value = gasolina.tipo;
    form.litros_disponibles.value = gasolina.litros_disponibles;
    const prField = form.querySelector("[name=precio_por_litro_reales]");
    if (prField) {
      prField.value = gasolina.precio_por_litro_reales ?? gasolina.precio_por_litro_oro ?? "";
    }
  }

  const tbody = document.getElementById("tabla-gasolina-ventas");
  if (tbody) {
    if (!ventas.length) {
      tbody.innerHTML = renderEmptyRow(9, "No hay ventas de gasolina registradas.");
    } else {
      tbody.innerHTML = ventas
        .map(
          (venta) => `
        <tr>
          <td>#${venta.id}</td>
          <td>${formatDate(venta.fecha)}</td>
          <td>${venta.litros}</td>
          <td>R$/L</td>
          <td>${formatMoney(venta.precio_litro_reales ?? venta.precio_litro_venta, "reales")}</td>
          <td>${formatMoney(venta.total_oro)}</td>
          <td>${formatMoney(venta.total_reales, "reales")}</td>
          <td>${getRateLabel(venta.tasa_nombre)}</td>
          <td>${venta.tipo_oro ? getRateLabel(venta.tipo_oro) : "-"}</td>
          <td>${venta.tipo_pago}</td>
        </tr>
      `
        )
        .join("");
    }
  }

  const tbodyRepo = document.getElementById("tabla-gasolina-reposiciones");
  const reposiciones = gasolina?.reposiciones || [];
  if (tbodyRepo) {
    if (!reposiciones.length) {
      tbodyRepo.innerHTML = renderEmptyRow(5, "No hay reposiciones registradas.");
    } else {
      tbodyRepo.innerHTML = reposiciones
        .map(
          (repo) => `
        <tr>
          <td>#${repo.id}</td>
          <td>${formatDate(repo.fecha)}</td>
          <td>${repo.litros}</td>
          <td>${formatMoney(repo.precio_reales_litro, "reales")}</td>
          <td>${formatMoney(repo.total_reales, "reales")}</td>
        </tr>
      `
        )
        .join("");
    }
  }

  sincronizarTipoOroDesdeTasa();
  actualizarPreviewRepo();
  actualizarVisibilidadPagoGasolina();
  actualizarPreviewVentaGasolina();
}

function resetFormVentaGasolina() {
  const ventaForm = document.getElementById("form-gasolina-venta");
  if (!ventaForm) {
    return;
  }
  ventaForm.reset();
  const tp = ventaForm.querySelector("#gasolina-tipo-pago");
  if (tp) {
    tp.value = "oro";
  }
  ventaForm.querySelector("#gasolina-monto-oro").value = "0.00";
  ventaForm.querySelector("#gasolina-monto-reales").value = "0.00";
  fillTasaSelect("gasolina-tasa");
  sincronizarTipoOroDesdeTasa();
  actualizarVisibilidadPagoGasolina();
}

export function initGasolina() {
  const configForm = document.getElementById("form-gasolina-config");
  const reponerForm = document.getElementById("form-gasolina-reponer");
  const ventaForm = document.getElementById("form-gasolina-venta");
  const tipoPagoSelect = document.getElementById("gasolina-tipo-pago");
  const tasaSelect = document.getElementById("gasolina-tasa");
  const tipoOroSelect = document.getElementById("gasolina-tipo-oro");

  reponerForm?.querySelectorAll("input[name=litros], input[name=precio_reales_litro]").forEach((el) => {
    el.addEventListener("input", actualizarPreviewRepo);
  });

  reponerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(reponerForm);
    const payload = {
      litros: Number(formData.get("litros")),
      precio_reales_litro: Number(formData.get("precio_reales_litro")),
    };
    try {
      await api.post("/gasolina/reponer", payload);
      reponerForm.reset();
      actualizarPreviewRepo();
      showToast("Reposicion registrada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  ventaForm?.addEventListener("input", (event) => {
    if (event.target.id === "gasolina-venta-litros") {
      actualizarPreviewVentaGasolina();
    } else if (event.target.id === "gasolina-monto-oro" || event.target.id === "gasolina-monto-reales") {
      actualizarGasolinaVueltoPreview();
    }
  });

  tipoPagoSelect?.addEventListener("change", actualizarVisibilidadPagoGasolina);
  tasaSelect?.addEventListener("change", sincronizarTipoOroDesdeTasa);
  tipoOroSelect?.addEventListener("change", sincronizarTasaDesdeTipoOro);

  configForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(configForm);
    const payload = {
      tipo: formData.get("tipo"),
      litros_disponibles: Number(formData.get("litros_disponibles")),
      precio_por_litro_reales: Number(formData.get("precio_por_litro_reales")),
    };

    try {
      await api.put("/gasolina/configurar", payload);
      gasolinaConfigCache = { ...(gasolinaConfigCache || {}), ...payload };
      showToast("Configuracion de gasolina actualizada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  ventaForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const tipoPago = document.getElementById("gasolina-tipo-pago").value;
    if (tipoPago !== "reales") {
      if (!document.getElementById("gasolina-tipo-oro").value) {
        showToast("Seleccione tipo de oro y tasa", "error");
        return;
      }
    }

    const formData = new FormData(ventaForm);
    const tipoOroVal = document.getElementById("gasolina-tipo-oro").value;
    const payload = {
      litros: Number(formData.get("litros")),
      tipo_pago: tipoPago,
      tipo_oro: tipoPago === "reales" ? null : tipoOroVal || null,
      monto_recibido_oro: Number(formData.get("monto_recibido_oro")),
      monto_recibido_reales: Number(formData.get("monto_recibido_reales")),
    };

    try {
      await api.post("/gasolina/venta", payload);
      resetFormVentaGasolina();
      showToast("Venta de gasolina registrada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  actualizarVisibilidadPagoGasolina();
}
