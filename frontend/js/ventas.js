import { api, formatDateOnly, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";
import { ensureTasas, fillTasaSelect, findTasaById, findTasaByNombre, getRateLabel } from "./tasas.js";

const carrito = [];

function obtenerTasaSeleccionada() {
  const tasaId = Number(document.getElementById("venta-tasa").value);
  if (!tasaId) {
    return null;
  }
  return findTasaById(tasaId) || null;
}

function textoVuelto(data) {
  const partes = [];
  if (Number(data.vuelto_reales) > 0) {
    partes.push(`Vuelto: R$ ${Number(data.vuelto_reales).toFixed(2)}`);
  }
  if (Number(data.vuelto_oro) > 0) {
    partes.push(`Vuelto: ${Number(data.vuelto_oro).toFixed(2)}g`);
  }
  return partes.join(" · ");
}

function actualizarVisibilidadCamposPago() {
  const tipoPago = document.getElementById("venta-tipo-pago").value;
  const tasaWrap = document.getElementById("venta-tasa-wrap");
  const tipoOroWrap = document.getElementById("venta-tipo-oro-wrap");
  const tasaSelect = document.getElementById("venta-tasa");
  const tipoOroSelect = document.getElementById("venta-tipo-oro");
  const wrapMontoOro = document.getElementById("venta-monto-oro-wrap");
  const wrapMontoReales = document.getElementById("venta-monto-reales-wrap");

  if (!tasaWrap || !tipoOroWrap || !tasaSelect || !tipoOroSelect) {
    return;
  }

  const requiereConversion = tipoPago !== "reales";
  tasaWrap.style.display = requiereConversion ? "grid" : "none";
  tipoOroWrap.style.display = requiereConversion ? "grid" : "none";
  tipoOroSelect.required = requiereConversion;

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

  if (!requiereConversion) {
    tipoOroSelect.value = "";
    tasaSelect.value = "";
  }
}

function calcularTotales() {
  const productos = getProductosCache();
  return carrito.reduce(
    (acc, item) => {
      const producto = productos.find((candidate) => candidate.id === item.producto_id);
      if (!producto) {
        return acc;
      }
      const subtotalOro = Number((producto.precio_venta_oro * item.cantidad).toFixed(2));
      const subtotalReales = Number((producto.precio_venta_reales * item.cantidad).toFixed(2));
      acc.totalOro += subtotalOro;
      acc.totalReales += subtotalReales;
      acc.items.push({ ...item, producto, subtotal: subtotalOro });
      return acc;
    },
    { totalOro: 0, totalReales: 0, items: [] }
  );
}

function renderCarrito() {
  const tbody = document.getElementById("tabla-carrito");
  const totals = calcularTotales();
  const tasa = obtenerTasaSeleccionada();
  const tipoPago = document.getElementById("venta-tipo-pago").value;

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

  if (tipoPago === "reales") {
    document.getElementById("venta-total-oro").textContent = "0.00";
    document.getElementById("venta-total-reales").textContent = totals.totalReales.toFixed(2);
  } else {
    document.getElementById("venta-total-oro").textContent = totals.totalOro.toFixed(2);
    document.getElementById("venta-total-reales").textContent = tasa
      ? (totals.totalOro * tasa.tasa_reales).toFixed(2)
      : "0.00";
  }

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
    tbody.innerHTML = renderEmptyRow(9, "No hay ventas registradas.");
  } else {
    tbody.innerHTML = ventas
      .map(
        (venta) => `
          <tr>
            <td>#${venta.id}</td>
            <td>${formatDateOnly(venta.fecha)}</td>
            <td>${formatTimeOnly(venta.fecha)}</td>
            <td>${venta.cliente}</td>
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

  renderCarrito();
}

export function initVentas() {
  const formCarrito = document.getElementById("form-carrito");
  const formVenta = document.getElementById("form-venta");
  const tasaSelect = document.getElementById("venta-tasa");
  const tipoPagoSelect = document.getElementById("venta-tipo-pago");
  const tipoOroSelect = document.getElementById("venta-tipo-oro");
  const mensajeVuelto = document.getElementById("venta-mensaje-vuelto");

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
      existente.cantidad = Number((existente.cantidad + cantidad).toFixed(2));
    } else {
      carrito.push({ producto_id: productoId, cantidad });
    }
    formCarrito.reset();
    document.getElementById("venta-cantidad").value = "1";
    renderCarrito();
  });

  tasaSelect.addEventListener("change", renderCarrito);
  tipoPagoSelect.addEventListener("change", () => {
    actualizarVisibilidadCamposPago();
    renderCarrito();
  });
  tipoOroSelect.addEventListener("change", () => {
    if (tipoPagoSelect.value === "reales") {
      return;
    }
    const tasa = findTasaByNombre(tipoOroSelect.value);
    if (tasa) {
      tasaSelect.value = String(tasa.id);
      renderCarrito();
    }
  });
  actualizarVisibilidadCamposPago();

  formVenta.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (mensajeVuelto) {
      mensajeVuelto.textContent = "";
    }
    if (!carrito.length) {
      showToast("Agrega al menos un producto al carrito", "error");
      return;
    }

    const tipoPago = tipoPagoSelect.value;
    const tasaId = Number(tasaSelect.value);
    if (tipoPago !== "reales" && !tasaId) {
      showToast("Selecciona una tasa para calcular la venta", "error");
      return;
    }

    const formData = new FormData(formVenta);
    let montoOro = Number(formData.get("monto_recibido_oro"));
    let montoReales = Number(formData.get("monto_recibido_reales"));
    if (tipoPago === "reales") {
      montoOro = 0;
    } else if (tipoPago === "oro") {
      montoReales = 0;
    }

    const payload = {
      items: carrito.map((item) => ({
        producto_id: item.producto_id,
        cantidad: item.cantidad,
      })),
      cliente: formData.get("cliente"),
      tasa_cambio_id: tipoPago === "reales" ? null : tasaId,
      tipo_pago: tipoPago,
      tipo_oro: tipoPago === "reales" ? null : formData.get("tipo_oro") || null,
      monto_recibido_oro: montoOro,
      monto_recibido_reales: montoReales,
    };

    if (payload.tipo_pago !== "reales" && !payload.tipo_oro) {
      showToast("Selecciona el tipo de oro para el cobro", "error");
      return;
    }

    try {
      const response = await api.post("/ventas", payload);
      const vueltoTxt = textoVuelto(response.data);
      if (mensajeVuelto) {
        mensajeVuelto.textContent = vueltoTxt;
      }
      carrito.splice(0, carrito.length);
      formVenta.reset();
      formVenta.cliente.value = "Mostrador";
      formVenta.tipo_pago.value = "oro";
      formVenta.tipo_oro.value = "";
      formVenta.monto_recibido_oro.value = "0.00";
      formVenta.monto_recibido_reales.value = "0.00";
      actualizarVisibilidadCamposPago();
      fillTasaSelect("venta-tasa");
      renderCarrito();
      const baseMsg = `Venta #${response.data.venta_id} registrada`;
      showToast(vueltoTxt ? `${baseMsg}. ${vueltoTxt}` : baseMsg, "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
