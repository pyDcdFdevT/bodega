import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";

function renderResumen(gasolina) {
  const target = document.getElementById("gasolina-resumen");
  target.innerHTML = `
    <article class="metric-pill">
      <span>Litros disponibles</span>
      <strong>${Number(gasolina.litros_disponibles || 0).toFixed(3)}</strong>
    </article>
    <article class="metric-pill">
      <span>Kg estimados</span>
      <strong>${Number(gasolina.kg_disponibles || 0).toFixed(3)}</strong>
    </article>
    <article class="metric-pill">
      <span>Precio por litro</span>
      <strong>${formatMoney(gasolina.precio_por_litro_oro)}</strong>
    </article>
    <article class="metric-pill">
      <span>Precio por kg</span>
      <strong>${formatMoney(gasolina.precio_por_kg_oro)}</strong>
    </article>
  `;
}

export async function loadGasolina() {
  const [gasolina, ventas] = await Promise.all([api.get("/gasolina"), api.get("/gasolina/ventas")]);

  renderResumen(gasolina);
  const form = document.getElementById("form-gasolina-config");
  form.tipo.value = gasolina.tipo;
  form.litros_disponibles.value = gasolina.litros_disponibles;
  form.precio_por_litro_oro.value = gasolina.precio_por_litro_oro;
  form.precio_por_kg_oro.value = gasolina.precio_por_kg_oro;

  const tbody = document.getElementById("tabla-gasolina-ventas");
  if (!ventas.length) {
    tbody.innerHTML = renderEmptyRow(6, "No hay ventas de gasolina registradas.");
    return;
  }

  tbody.innerHTML = ventas
    .map(
      (venta) => `
        <tr>
          <td>#${venta.id}</td>
          <td>${formatDate(venta.fecha)}</td>
          <td>${venta.litros}</td>
          <td>${formatMoney(venta.total_oro)}</td>
          <td>${formatMoney(venta.total_reales, "reales")}</td>
          <td>${venta.tipo_pago}</td>
        </tr>
      `
    )
    .join("");
}

export function initGasolina() {
  const configForm = document.getElementById("form-gasolina-config");
  const ventaForm = document.getElementById("form-gasolina-venta");

  configForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(configForm);
    const payload = {
      tipo: formData.get("tipo"),
      litros_disponibles: Number(formData.get("litros_disponibles")),
      precio_por_litro_oro: Number(formData.get("precio_por_litro_oro")),
      precio_por_kg_oro: Number(formData.get("precio_por_kg_oro")),
    };

    try {
      await api.put("/gasolina/configurar", payload);
      showToast("Configuracion de gasolina actualizada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  ventaForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(ventaForm);
    const payload = {
      litros: Number(formData.get("litros")),
      tipo_pago: formData.get("tipo_pago"),
      monto_recibido_oro: Number(formData.get("monto_recibido_oro")),
      monto_recibido_reales: Number(formData.get("monto_recibido_reales")),
    };

    try {
      await api.post("/gasolina/venta", payload);
      ventaForm.reset();
      ventaForm.tipo_pago.value = "oro";
      ventaForm.monto_recibido_oro.value = "0";
      ventaForm.monto_recibido_reales.value = "0";
      showToast("Venta de gasolina registrada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
