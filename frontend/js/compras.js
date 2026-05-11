import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { loadProductoOptions } from "./inventario.js";

export async function loadCompras() {
  await loadProductoOptions(["compra-producto"]);
  const compras = await api.get("/compras");
  const tbody = document.getElementById("tabla-compras");

  if (!compras.length) {
    tbody.innerHTML = renderEmptyRow(5, "No hay compras registradas.");
    return;
  }

  tbody.innerHTML = compras
    .map(
      (compra) => `
        <tr>
          <td>#${compra.id}</td>
          <td>${formatDate(compra.fecha)}</td>
          <td>${compra.proveedor}</td>
          <td>${formatMoney(compra.total_reales, "reales")}</td>
          <td>${formatMoney(compra.total_oro)}</td>
        </tr>
      `
    )
    .join("");
}

export function initCompras() {
  const form = document.getElementById("form-compra");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      producto_id: Number(formData.get("producto_id")),
      cantidad: Number(formData.get("cantidad")),
      precio_reales: Number(formData.get("precio_reales")),
      proveedor: formData.get("proveedor"),
      observaciones: formData.get("observaciones") || null,
    };

    try {
      await api.post("/compras", payload);
      form.reset();
      form.proveedor.value = "Proveedor";
      showToast("Compra registrada correctamente", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
