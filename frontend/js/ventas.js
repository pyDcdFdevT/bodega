import { api, formatDateOnly, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";
import { ensureTasas, fillTasaSelect, findTasaById, findTasaByNombre, getRateLabel } from "./tasas.js";

const carrito = [];
let categoriaFiltro = "";

function productosFiltrados() {
  const productos = getProductosCache().filter((p) => p.activo);
  if (!categoriaFiltro) {
    return productos;
  }
  return productos.filter((p) => (p.categoria_nombre || "Sin categoria") === categoriaFiltro);
}

function obtenerTasaSeleccionada() {
  const tasaId = Number(document.getElementById("venta-tasa")?.value);
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
  const tipoPago = document.getElementById("venta-tipo-pago")?.value;
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
  sincronizarModalCobro();
}

function datosTotalesCobro() {
  const { totalOro, totalReales } = calcularTotales();
  const tasa = obtenerTasaSeleccionada();
  const tr = Number(totalReales.toFixed(2));
  const to = Number(totalOro.toFixed(2));
  const equivRealesDesdeOro =
    tasa && tasa.tasa_reales > 0 ? Number((to * tasa.tasa_reales).toFixed(2)) : 0;
  return { totalOro: to, totalReales: tr, equivRealesDesdeOro, tasa };
}

function actualizarModalTotalesACobrar() {
  const el = document.getElementById("venta-cobro-total-resumen");
  if (!el) {
    return;
  }
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";
  const { totalOro, totalReales, equivRealesDesdeOro } = datosTotalesCobro();
  if (!carrito.length) {
    el.innerHTML = "";
    return;
  }
  if (tipoPago === "reales") {
    el.innerHTML = `<strong>Total a cobrar:</strong> ${formatMoney(totalReales, "reales")}`;
  } else if (tipoPago === "oro") {
    el.innerHTML = `<strong>Total a cobrar:</strong> ${totalOro.toFixed(2)}g (${formatMoney(equivRealesDesdeOro, "reales")})`;
  } else {
    el.innerHTML = `
      <div><strong>Total a cobrar (oro):</strong> ${totalOro.toFixed(2)}g (${formatMoney(equivRealesDesdeOro, "reales")})</div>
      <div><strong>Total a cobrar (reales en precios):</strong> ${formatMoney(totalReales, "reales")}</div>
    `;
  }
}

function actualizarModalVueltoPreview() {
  const el = document.getElementById("venta-cobro-vuelto-preview");
  if (!el) {
    return;
  }
  el.classList.remove("insuficiente");
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";
  const mOro = Number(document.getElementById("venta-input-monto-oro")?.value || 0);
  const mReales = Number(document.getElementById("venta-input-monto-reales")?.value || 0);
  const { totalOro, totalReales, tasa } = datosTotalesCobro();

  if (!carrito.length) {
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

  const recibidoEquivOro = Number((mOro + mReales / tasa.tasa_reales).toFixed(2));
  const diffOro = Number((recibidoEquivOro - totalOro).toFixed(2));

  if (tipoPago === "oro") {
    if (diffOro >= 0) {
      el.textContent = `Vuelto: ${diffOro.toFixed(2)}g`;
    } else {
      el.classList.add("insuficiente");
      el.textContent = `Falta: ${(-diffOro).toFixed(2)}g`;
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

function sincronizarModalCobro() {
  const dlg = document.getElementById("dialog-cobro-venta");
  if (!dlg?.open) {
    return;
  }
  actualizarModalTotalesACobrar();
  actualizarModalVueltoPreview();
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

function renderGridProductos() {
  const grid = document.getElementById("pos-grid-productos");
  if (!grid) {
    return;
  }
  const lista = productosFiltrados();
  if (!lista.length) {
    grid.innerHTML = '<p class="muted">No hay productos en esta categoria.</p>';
    return;
  }
  grid.innerHTML = lista
    .map(
      (p) => `
      <button type="button" class="pos-card" data-pos-add="${p.id}">
        <strong>${p.nombre}</strong>
        <span class="pos-card-meta">${formatMoney(p.precio_venta_reales, "reales")}</span>
        <span class="pos-card-stock">Stock: ${p.stock_actual}</span>
      </button>`
    )
    .join("");
  grid.querySelectorAll("[data-pos-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.posAdd);
      const existente = carrito.find((item) => item.producto_id === id);
      if (existente) {
        existente.cantidad = Number((existente.cantidad + 1).toFixed(2));
      } else {
        carrito.push({ producto_id: id, cantidad: 1 });
      }
      renderCarrito();
    });
  });
}

function renderCarrito() {
  const tbody = document.getElementById("tabla-carrito");
  if (!tbody) {
    return;
  }
  const totals = calcularTotales();
  const tasa = obtenerTasaSeleccionada();
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";

  if (!totals.items.length) {
    tbody.innerHTML = renderEmptyRow(4, "Carrito vacio. Pulse un producto.");
  } else {
    tbody.innerHTML = totals.items
      .map(
        (item) => `
          <tr>
            <td>${item.producto.nombre}</td>
            <td><input type="number" min="0.01" step="0.01" class="pos-qty" data-pid="${item.producto_id}" value="${item.cantidad}"></td>
            <td>${formatMoney(item.subtotal)}</td>
            <td><button type="button" data-remove="${item.producto_id}">Quitar</button></td>
          </tr>
        `
      )
      .join("");
    tbody.querySelectorAll(".pos-qty").forEach((input) => {
      input.addEventListener("change", () => {
        const pid = Number(input.dataset.pid);
        const row = carrito.find((c) => c.producto_id === pid);
        if (row) {
          row.cantidad = Math.max(0.01, Number(input.value) || 0.01);
          renderCarrito();
        }
      });
    });
  }

  const elOro = document.getElementById("venta-total-oro");
  const elReales = document.getElementById("venta-total-reales");
  if (elOro && elReales) {
    if (tipoPago === "reales") {
      elOro.textContent = "0.00";
      elReales.textContent = totals.totalReales.toFixed(2);
    } else {
      elOro.textContent = totals.totalOro.toFixed(2);
      elReales.textContent = tasa ? (totals.totalOro * tasa.tasa_reales).toFixed(2) : "0.00";
    }
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

  sincronizarModalCobro();
}

function llenarFiltroCategorias() {
  const sel = document.getElementById("venta-filtro-categoria");
  if (!sel) {
    return;
  }
  const cats = new Set();
  getProductosCache()
    .filter((p) => p.activo)
    .forEach((p) => cats.add(p.categoria_nombre || "Sin categoria"));
  const ordenados = [...cats].sort((a, b) => a.localeCompare(b));
  sel.innerHTML = `<option value="">Todas las categorias</option>${ordenados.map((c) => `<option value="${c}">${c}</option>`).join("")}`;
  sel.value = categoriaFiltro;
}

export async function loadVentas() {
  await ensureTasas();
  fillTasaSelect("venta-tasa");
  llenarFiltroCategorias();
  renderGridProductos();

  const [ventas, resumen] = await Promise.all([api.get("/ventas"), api.get("/ventas/resumen/hoy")]);

  const badge = document.getElementById("ventas-resumen-hoy");
  if (badge) {
    badge.textContent = `${resumen.ventas} ventas hoy`;
  }
  const heroV = document.getElementById("hero-ventas-hoy");
  if (heroV) {
    heroV.textContent = String(resumen.ventas);
  }

  const tbody = document.getElementById("tabla-ventas");
  if (tbody) {
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
  }
  renderCarrito();
}

function abrirCobro() {
  const dlg = document.getElementById("dialog-cobro-venta");
  if (!dlg?.showModal) {
    showToast("Su navegador no soporta el cobro en modal", "error");
    return;
  }
  const mensajeVuelto = document.getElementById("venta-mensaje-vuelto");
  if (mensajeVuelto) {
    mensajeVuelto.textContent = "";
  }
  actualizarVisibilidadCamposPago();
  fillTasaSelect("venta-tasa");
  dlg.showModal();
  sincronizarModalCobro();
}

function cerrarCobro() {
  document.getElementById("dialog-cobro-venta")?.close();
}

export function initVentas() {
  const filtro = document.getElementById("venta-filtro-categoria");
  const btnCobrar = document.getElementById("btn-pos-cobrar");
  const formVenta = document.getElementById("form-venta");
  const tasaSelect = document.getElementById("venta-tasa");
  const tipoPagoSelect = document.getElementById("venta-tipo-pago");
  const tipoOroSelect = document.getElementById("venta-tipo-oro");
  const mensajeVuelto = document.getElementById("venta-mensaje-vuelto");
  const btnCerrarModal = document.getElementById("btn-cerrar-cobro");
  const inputMontoOro = document.getElementById("venta-input-monto-oro");
  const inputMontoReales = document.getElementById("venta-input-monto-reales");

  filtro?.addEventListener("change", () => {
    categoriaFiltro = filtro.value;
    renderGridProductos();
  });

  btnCobrar?.addEventListener("click", () => {
    if (!carrito.length) {
      showToast("Agrega productos al carrito", "error");
      return;
    }
    abrirCobro();
  });
  btnCerrarModal?.addEventListener("click", cerrarCobro);

  tasaSelect?.addEventListener("change", renderCarrito);
  tipoPagoSelect?.addEventListener("change", () => {
    actualizarVisibilidadCamposPago();
    renderCarrito();
  });
  tipoOroSelect?.addEventListener("change", () => {
    if (tipoPagoSelect?.value === "reales") {
      return;
    }
    const tasa = findTasaByNombre(tipoOroSelect.value);
    if (tasa && tasaSelect) {
      tasaSelect.value = String(tasa.id);
      renderCarrito();
    }
  });
  inputMontoOro?.addEventListener("input", sincronizarModalCobro);
  inputMontoReales?.addEventListener("input", sincronizarModalCobro);
  actualizarVisibilidadCamposPago();

  formVenta?.addEventListener("submit", async (event) => {
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
      const clienteIn = formVenta.querySelector('[name="cliente"]');
      if (clienteIn) {
        clienteIn.value = "Mostrador";
      }
      formVenta.tipo_pago.value = "oro";
      formVenta.tipo_oro.value = "";
      formVenta.monto_recibido_oro.value = "0.00";
      formVenta.monto_recibido_reales.value = "0.00";
      actualizarVisibilidadCamposPago();
      fillTasaSelect("venta-tasa");
      renderCarrito();
      cerrarCobro();
      const baseMsg = `Venta #${response.data.venta_id} registrada`;
      showToast(vueltoTxt ? `${baseMsg}. ${vueltoTxt}` : baseMsg, "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
