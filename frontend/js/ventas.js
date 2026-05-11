import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";
import { ensureTasas, fillTasaSelect, findTasaById, getRateLabel } from "./tasas.js";

const carrito = [];

function obtenerTasaSeleccionada() {
  const tasaId = Number(document.getElementById("venta-tasa").value);
  if (!tasaId) {
    return null;
  }
  return findTasaById(tasaId) || null;
}

function calcularTotales() {
  const productos = getProductosCache();
  return carrito.reduce(
    (acc, item) => {
      const producto = productos.find((candidate) => candidate.id === item.producto_id);
      if (!producto) {
        return acc;
      }
      const subtotal = Number((producto.precio_venta_oro * item.cantidad).toFixed(3));
      acc.totalOro += subtotal;
      acc.items.push({ ...item, producto, subtotal });
      return acc;
    },
    { totalOro: 0, items: [] }
  );
}

function renderCarrito() {
  const tbody = document.getElementById("tabla-carrito");
  const totals = calcularTotales();
  const tasa = obtenerTasaSeleccionada();

  if (!totals.items.length) {
    tbody.innerHTML = renderEmptyRow(4, "Aun no hay productos en el carrito.");
  } else {
    tbody.innerHTML = totals.items
      .map(
        (item) => `
          <tr>
            <td>${item.producto.nombre}</td>
            <td>${item.cantidad}</td>
            <td>${formatMoney(item.subtotal)}</td>
            <td><button type="button" data-remove="${item.producto_id}">Quitar</button></td>
          </tr>
        `
      )
      .join("");
  }

  document.getElementById("venta-total-oro").textContent = totals.totalOro.toFixed(3);
  document.getElementById("venta-total-reales").textContent = tasa
    ? (totals.totalOro * tasa.tasa_reales).toFixed(2)
    : "0.00";

  tbody.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      const productId = Number(button.dataset.remove);
      const index = carrito.findIndex((item) => item.producto_id === productId);
      if (index >= 0) {
        carrito.splice(index, 1);
        renderCarrito();
      }
    });
  });
}

export async function loadVentas() {
  await loadProductoOptions(["venta-producto"]);
  await ensureTasas();
  fillTasaSelect("venta-tasa");

  const [ventas, resumen] = await Promise.all([api.get("/ventas"), api.get("/ventas/resumen/hoy")]);

  document.getElementById("ventas-resumen-hoy").textContent = `${resumen.ventas} ventas hoy`;
  document.getElementById("hero-ventas-hoy").textContent = String(resumen.ventas);

  const tbody = document.getElementById("tabla-ventas");
  if (!ventas.length) {
    tbody.innerHTML = renderEmptyRow(7, "No hay ventas registradas.");
  } else {
    tbody.innerHTML = ventas
      .map(
        (venta) => `
          <tr>
            <td>#${venta.id}</td>
            <td>${formatDate(venta.fecha)}</td>
            <td>${venta.cliente}</td>
            <td>${formatMoney(venta.total_oro)}</td>
            <td>${formatMoney(venta.total_reales, "reales")}</td>
            <td>${getRateLabel(venta.tasa_nombre)}</td>
            <td>${venta.tipo_pago}</td>
          </tr>
        `
      )
      .join("");
  }

  renderCarrito();
}

export function initVentas() {
  const formCarrito = document.getElementById("form-carrito");
  const formVenta = document.getElementById("form-venta");
  const tasaSelect = document.getElementById("venta-tasa");

  formCarrito.addEventListener("submit", (event) => {
    event.preventDefault();
    const productoId = Number(document.getElementById("venta-producto").value);
    const cantidad = Number(document.getElementById("venta-cantidad").value);
    if (!productoId || cantidad <= 0) {
      showToast("Seleccione un producto y una cantidad valida", "error");
      return;
    }

    const existente = carrito.find((item) => item.producto_id === productoId);
    if (existente) {
      existente.cantidad = Number((existente.cantidad + cantidad).toFixed(3));
    } else {
      carrito.push({ producto_id: productoId, cantidad });
    }
    formCarrito.reset();
    document.getElementById("venta-cantidad").value = "1";
    renderCarrito();
  });

  tasaSelect.addEventListener("change", renderCarrito);

  formVenta.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!carrito.length) {
      showToast("Agrega al menos un producto al carrito", "error");
      return;
    }

    const tasaId = Number(tasaSelect.value);
    if (!tasaId) {
      showToast("Selecciona una tasa para calcular la venta", "error");
      return;
    }

    const formData = new FormData(formVenta);
    const payload = {
      items: carrito.map((item) => ({
        producto_id: item.producto_id,
        cantidad: item.cantidad,
      })),
      cliente: formData.get("cliente"),
      tasa_cambio_id: tasaId,
      tipo_pago: formData.get("tipo_pago"),
      monto_recibido_oro: Number(formData.get("monto_recibido_oro")),
      monto_recibido_reales: Number(formData.get("monto_recibido_reales")),
    };

    try {
      const response = await api.post("/ventas", payload);
      carrito.splice(0, carrito.length);
      formVenta.reset();
      formVenta.cliente.value = "Mostrador";
      formVenta.tipo_pago.value = "oro";
      formVenta.monto_recibido_oro.value = "0.000";
      formVenta.monto_recibido_reales.value = "0.00";
      fillTasaSelect("venta-tasa");
      renderCarrito();
      showToast(`Venta #${response.data.venta_id} registrada`, "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
