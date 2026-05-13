import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { ensureTasas, fillTasaSelect, findTasaById, findTasaByNombre, getRateLabel } from "./tasas.js";

let gasolinaConfigCache = null;

function etiquetaUnidadVenta(u) {
  if (u === "reales_litro") {
    return "R$/L";
  }
  return "g/L";
}

function renderResumen(gasolina) {
  const target = document.getElementById("gasolina-resumen");
  target.innerHTML = `
    <article class="metric-pill">
      <span>Litros disponibles</span>
      <strong>${Number(gasolina.litros_disponibles || 0).toFixed(3)}</strong>
    </article>
    <article class="metric-pill">
      <span>Precio referencia (oro / L)</span>
      <strong>${formatMoney(gasolina.precio_por_litro_oro)}</strong>
    </article>
  `;
}

function tasaParaPreviewVenta() {
  const tipoPago = document.getElementById("gasolina-tipo-pago").value;
  if (tipoPago === "reales") {
    return findTasaByNombre("araparita") || findTasaByNombre("uruman");
  }
  const id = Number(document.getElementById("gasolina-tasa").value);
  return findTasaById(id);
}

function actualizarPreviewRepo() {
  const litros = Number(document.querySelector("#form-gasolina-reponer input[name=litros]")?.value);
  const precio = Number(document.querySelector("#form-gasolina-reponer input[name=precio_reales_litro]")?.value);
  const tasaAra = findTasaByNombre("araparita");
  const totalReales = Number.isFinite(litros) && Number.isFinite(precio) ? litros * precio : 0;
  const totalOro =
    tasaAra && tasaAra.tasa_reales > 0 && Number.isFinite(totalReales) ? totalReales / tasaAra.tasa_reales : 0;
  const elR = document.getElementById("gasolina-repo-total-reales");
  const elO = document.getElementById("gasolina-repo-total-oro");
  if (elR) {
    elR.value = Number.isFinite(totalReales) ? totalReales.toFixed(2) : "0.00";
  }
  if (elO) {
    elO.value = Number.isFinite(totalOro) ? totalOro.toFixed(3) : "0.000";
  }
}

function actualizarEtiquetaPrecioLitro() {
  const unidad = document.getElementById("gasolina-unidad-precio").value;
  const leyenda = document.getElementById("gasolina-precio-litro-leyenda");
  const input = document.getElementById("gasolina-precio-litro");
  if (!leyenda || !input) {
    return;
  }
  if (unidad === "reales_litro") {
    leyenda.textContent = "Precio por litro (R$)";
    input.min = "0.01";
    input.step = "0.01";
  } else {
    leyenda.textContent = "Precio por litro (gramos oro)";
    input.min = "0.001";
    input.step = "0.001";
  }
  const gasolina = gasolinaConfigCache;
  if (gasolina && unidad === "oro_litro" && Number(gasolina.precio_por_litro_oro) > 0) {
    input.value = String(gasolina.precio_por_litro_oro);
  }
}

function actualizarVisibilidadPagoGasolina() {
  const tipoPago = document.getElementById("gasolina-tipo-pago").value;
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
  const precio = Number(document.getElementById("gasolina-precio-litro")?.value);
  const unidad = document.getElementById("gasolina-unidad-precio")?.value;
  const tasa = tasaParaPreviewVenta();

  let totalOro = 0;
  let totalReales = 0;
  if (Number.isFinite(litros) && Number.isFinite(precio) && litros > 0 && precio > 0 && tasa && tasa.tasa_reales > 0) {
    if (unidad === "oro_litro") {
      totalOro = litros * precio;
      totalReales = totalOro * tasa.tasa_reales;
    } else {
      totalReales = litros * precio;
      totalOro = totalReales / tasa.tasa_reales;
    }
  }

  const elO = document.getElementById("gasolina-preview-oro");
  const elR = document.getElementById("gasolina-preview-reales");
  const tipoPago = document.getElementById("gasolina-tipo-pago")?.value;
  if (elO && elR) {
    if (tipoPago === "reales") {
      elO.textContent = "0.000";
      elR.textContent = formatMoney(totalReales, "reales");
    } else {
      elO.textContent = Number.isFinite(totalOro) ? totalOro.toFixed(3) : "0.000";
      elR.textContent = formatMoney(Number.isFinite(totalReales) ? totalReales : 0, "reales");
    }
  }
}

function sincronizarTasaDesdeTipoOro() {
  const nombre = document.getElementById("gasolina-tipo-oro").value;
  const tasa = findTasaByNombre(nombre);
  const select = document.getElementById("gasolina-tasa");
  if (tasa && select) {
    select.value = String(tasa.id);
  }
  actualizarPreviewVentaGasolina();
}

function sincronizarTipoOroDesdeTasa() {
  const id = Number(document.getElementById("gasolina-tasa").value);
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
  form.tipo.value = gasolina.tipo;
  form.litros_disponibles.value = gasolina.litros_disponibles;
  form.precio_por_litro_oro.value = gasolina.precio_por_litro_oro;

  actualizarEtiquetaPrecioLitro();

  const tbody = document.getElementById("tabla-gasolina-ventas");
  if (!ventas.length) {
    tbody.innerHTML = renderEmptyRow(10, "No hay ventas de gasolina registradas.");
  } else {
    tbody.innerHTML = ventas
      .map(
        (venta) => `
        <tr>
          <td>#${venta.id}</td>
          <td>${formatDate(venta.fecha)}</td>
          <td>${venta.litros}</td>
          <td>${etiquetaUnidadVenta(venta.unidad_precio_venta || "oro_litro")}</td>
          <td>${venta.precio_litro_venta}</td>
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

  sincronizarTipoOroDesdeTasa();
  actualizarPreviewRepo();
  actualizarVisibilidadPagoGasolina();
  actualizarPreviewVentaGasolina();
}

function resetFormVentaGasolina() {
  const ventaForm = document.getElementById("form-gasolina-venta");
  ventaForm.reset();
  ventaForm.querySelector("#gasolina-tipo-pago").value = "oro";
  ventaForm.querySelector("#gasolina-monto-oro").value = "0.000";
  ventaForm.querySelector("#gasolina-monto-reales").value = "0.00";
  ventaForm.querySelector("#gasolina-unidad-precio").value = "oro_litro";
  fillTasaSelect("gasolina-tasa");
  sincronizarTipoOroDesdeTasa();
  actualizarEtiquetaPrecioLitro();
  actualizarVisibilidadPagoGasolina();
}

export function initGasolina() {
  const configForm = document.getElementById("form-gasolina-config");
  const reponerForm = document.getElementById("form-gasolina-reponer");
  const ventaForm = document.getElementById("form-gasolina-venta");
  const tipoPagoSelect = document.getElementById("gasolina-tipo-pago");
  const tasaSelect = document.getElementById("gasolina-tasa");
  const tipoOroSelect = document.getElementById("gasolina-tipo-oro");

  reponerForm.querySelectorAll("input[name=litros], input[name=precio_reales_litro]").forEach((el) => {
    el.addEventListener("input", actualizarPreviewRepo);
  });

  reponerForm.addEventListener("submit", async (event) => {
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

  document.getElementById("gasolina-unidad-precio").addEventListener("change", () => {
    actualizarEtiquetaPrecioLitro();
    actualizarPreviewVentaGasolina();
  });

  ventaForm.addEventListener("input", (event) => {
    const id = event.target.id;
    if (id === "gasolina-precio-litro" || id === "gasolina-venta-litros") {
      actualizarPreviewVentaGasolina();
    }
  });

  tipoPagoSelect.addEventListener("change", actualizarVisibilidadPagoGasolina);
  tasaSelect.addEventListener("change", sincronizarTipoOroDesdeTasa);
  tipoOroSelect.addEventListener("change", sincronizarTasaDesdeTipoOro);

  configForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(configForm);
    const payload = {
      tipo: formData.get("tipo"),
      litros_disponibles: Number(formData.get("litros_disponibles")),
      precio_por_litro_oro: Number(formData.get("precio_por_litro_oro")),
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

  ventaForm.addEventListener("submit", async (event) => {
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
      unidad_precio: formData.get("unidad_precio"),
      precio_por_litro: Number(formData.get("precio_por_litro")),
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

  actualizarEtiquetaPrecioLitro();
  actualizarVisibilidadPagoGasolina();
}
