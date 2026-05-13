import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";

const MOTIVOS = [
  "Consumo propio",
  "Merma",
  "Caducado",
  "Dañado",
  "Otro",
];

function obtenerProductoSeleccionado() {
  const productoId = Number(document.getElementById("salida-producto").value);
  if (!productoId) {
    return null;
  }
  return getProductosCache().find((producto) => producto.id === productoId) || null;
}

function calcularValorSalida() {
  const producto = obtenerProductoSeleccionado();
  const cantidad = Number(document.getElementById("salida-cantidad").value || 0);
  const target = document.getElementById("salida-valor-oro");

  if (!producto || cantidad <= 0) {
    target.textContent = "0.00";
    return;
  }

  const valor = producto.precio_venta_oro * cantidad;
  target.textContent = formatMoney(valor);
}

function asegurarMotivos() {
  const select = document.getElementById("salida-motivo");
  if (select.dataset.ready === "1") {
    return;
  }
  select.innerHTML = MOTIVOS.map((motivo) => `<option value="${motivo}">${motivo}</option>`).join("");
  select.dataset.ready = "1";
}

export async function loadSalidas() {
  asegurarMotivos();
  await loadProductoOptions(["salida-producto"]);
  calcularValorSalida();

  const salidas = await api.get("/salidas");
  const tbody = document.getElementById("tabla-salidas");

  if (!salidas.length) {
    tbody.innerHTML = renderEmptyRow(6, "No hay salidas registradas.");
    return;
  }

  tbody.innerHTML = salidas
    .map(
      (salida) => `
        <tr>
          <td>#${salida.id}</td>
          <td>${formatDate(salida.fecha)}</td>
          <td>${salida.producto || "-"}</td>
          <td>${salida.cantidad}</td>
          <td>${formatMoney(salida.valor_oro)}</td>
          <td>${salida.motivo}</td>
        </tr>
      `
    )
    .join("");
}

export function initSalidas() {
  const form = document.getElementById("form-salida");
  const productoSelect = document.getElementById("salida-producto");
  const cantidadInput = document.getElementById("salida-cantidad");

  asegurarMotivos();

  productoSelect.addEventListener("change", calcularValorSalida);
  cantidadInput.addEventListener("input", calcularValorSalida);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      producto_id: Number(document.getElementById("salida-producto").value),
      cantidad: Number(document.getElementById("salida-cantidad").value),
      motivo: document.getElementById("salida-motivo").value,
    };

    try {
      await api.post("/salidas", payload);
      showToast("Salida registrada correctamente", "success");
      form.reset();
      document.getElementById("salida-cantidad").value = "1";
      document.getElementById("salida-valor-oro").textContent = "0.00";
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
