import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";

const MOTIVOS = [
  "Consumo interno",
  "Merma",
  "Vencido",
  "Dañado",
  "Muestreo / degustacion",
  "Donacion",
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
  const target = document.getElementById("salida-valor-reales");

  if (!producto || cantidad <= 0) {
    if (target) {
      target.textContent = formatMoney(0, "reales");
    }
    return;
  }

  const valor = Number(producto.precio_costo_reales || 0) * cantidad;
  if (target) {
    target.textContent = formatMoney(valor, "reales");
  }
}

function asegurarMotivos() {
  const select = document.getElementById("salida-motivo");
  if (!select) {
    return;
  }
  select.innerHTML = MOTIVOS.map((motivo) => `<option value="${motivo}">${motivo}</option>`).join("");
}

export async function loadSalidas() {
  asegurarMotivos();
  await loadProductoOptions(["salida-producto"]);
  calcularValorSalida();

  const salidas = await api.get("/salidas");
  const tbody = document.getElementById("tabla-salidas");
  if (!tbody) {
    return;
  }
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
          <td>${formatMoney(salida.valor_oro, "reales")}</td>
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

  productoSelect?.addEventListener("change", calcularValorSalida);
  cantidadInput?.addEventListener("input", calcularValorSalida);

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";

    const payload = {
      producto_id: Number(document.getElementById("salida-producto").value),
      cantidad: Number(document.getElementById("salida-cantidad").value),
      motivo: document.getElementById("salida-motivo").value,
    };

    if (btn) {
      btn.disabled = true;
      btn.textContent = "Registrando...";
    }
    try {
      await api.post("/salidas", payload);
      showToast("Salida registrada correctamente", "success");
      form.reset();
      document.getElementById("salida-cantidad").value = "1";
      document.getElementById("salida-valor-reales").textContent = formatMoney(0, "reales");
      asegurarMotivos();
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    }
  });
}
