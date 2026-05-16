import { api, formatDateOnly, formatMoney, formatTimeOnly, renderEmptyRow, showToast } from "./api.js";
import { getRol } from "./auth.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";
import { ensureTasas, findTasaByNombre, getRateLabel } from "./tasas.js";

const FAVORITOS_KEY = "__favoritos__";
const LS_FAVORITOS = "bodega-ventas-favoritos";

const carrito = [];
let categoriaFiltro = FAVORITOS_KEY;
let ventaDevolucionActual = null;

function getFavoritosIds() {
  try {
    const raw = localStorage.getItem(LS_FAVORITOS);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.map(Number).filter((id) => id > 0) : [];
  } catch {
    return [];
  }
}

function setFavoritosIds(ids) {
  localStorage.setItem(LS_FAVORITOS, JSON.stringify([...new Set(ids.map(Number))]));
}

function esFavorito(productoId) {
  return getFavoritosIds().includes(Number(productoId));
}

function toggleFavorito(productoId) {
  const id = Number(productoId);
  const ids = getFavoritosIds();
  if (ids.includes(id)) {
    setFavoritosIds(ids.filter((x) => x !== id));
  } else {
    setFavoritosIds([...ids, id]);
  }
}

function productosFavoritos() {
  const ids = new Set(getFavoritosIds());
  return getProductosCache().filter((p) => p.activo && ids.has(p.id));
}

function productosDeCategoria(nombreCategoria) {
  return getProductosCache().filter(
    (p) => p.activo && (p.categoria_nombre || "Sin categoria") === nombreCategoria
  );
}

function adminHeaders() {
  return { headers: { "X-Bodega-Rol": "admin" } };
}

function obtenerDescuentoCobro() {
  return Math.max(0, Number(document.getElementById("venta-descuento-reales")?.value || 0));
}

function obtenerTasaSeleccionada() {
  const tipoOro = document.getElementById("venta-tipo-oro")?.value?.trim();
  if (tipoOro) {
    return findTasaByNombre(tipoOro) || null;
  }
  return null;
}

function textoVuelto(data) {
  const partes = [];
  if (Number(data.vuelto_reales) > 0) {
    partes.push(`Vuelto: R$ ${Number(data.vuelto_reales).toFixed(2)}`);
  }
  if (Number(data.vuelto_oro) > 0) {
    partes.push(`Vuelto: ${Number(data.vuelto_oro).toFixed(4)}g`);
  }
  return partes.join(" · ");
}

function esVentaFiada() {
  return document.getElementById("venta-tipo-venta")?.value === "fiado";
}

function actualizarVistaTipoVenta() {
  const fiado = esVentaFiada();
  const extra = document.getElementById("venta-fiado-extra");
  const labelCli = document.getElementById("venta-label-cliente-contado");
  const tipoPago = document.getElementById("venta-tipo-pago");
  if (extra) {
    extra.style.display = fiado ? "grid" : "none";
  }
  if (labelCli) {
    labelCli.style.display = fiado ? "none" : "";
  }
  if (fiado && tipoPago) {
    tipoPago.value = "reales";
    tipoPago.disabled = true;
  } else if (tipoPago) {
    tipoPago.disabled = false;
  }
  actualizarVisibilidadCamposPago();
  sincronizarModalCobro();
}

function actualizarVisibilidadCamposPago() {
  const tipoPago = document.getElementById("venta-tipo-pago")?.value;
  const tipoOroWrap = document.getElementById("venta-tipo-oro-wrap");
  const tipoOroSelect = document.getElementById("venta-tipo-oro");
  const wrapMontoOro = document.getElementById("venta-monto-oro-wrap");
  const wrapMontoReales = document.getElementById("venta-monto-reales-wrap");
  if (!tipoOroWrap || !tipoOroSelect) {
    return;
  }
  const fiado = esVentaFiada();
  const requiereOro = !fiado && tipoPago !== "reales";
  tipoOroWrap.style.display = requiereOro ? "grid" : "none";
  tipoOroSelect.required = requiereOro;
  if (wrapMontoOro && wrapMontoReales) {
    if (fiado) {
      wrapMontoOro.style.display = "none";
      wrapMontoReales.style.display = "none";
    } else if (tipoPago === "reales") {
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
  if (!requiereOro && !fiado) {
    tipoOroSelect.value = "";
  }
  sincronizarModalCobro();
}

function datosTotalesCobro() {
  const { totalOro, totalReales, subtotalReales } = calcularTotales();
  const tasa = obtenerTasaSeleccionada();
  const descuento = obtenerDescuentoCobro();
  const to = Number(totalOro.toFixed(4));
  const trBruto = Number(subtotalReales.toFixed(2));
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";
  let tr = trBruto;
  if (tipoPago === "reales" || esVentaFiada()) {
    tr = Math.max(0, Number((trBruto - descuento).toFixed(2)));
  }
  const equivRealesDesdeOro =
    tasa && tasa.tasa_reales > 0 ? Number((to * tasa.tasa_reales).toFixed(2)) : 0;
  let totalCobrarReales = tr;
  if (!esVentaFiada() && tipoPago !== "reales") {
    totalCobrarReales = Math.max(0, Number((equivRealesDesdeOro - descuento).toFixed(2)));
  }
  return {
    totalOro: to,
    totalReales: tr,
    subtotalReales: trBruto,
    descuento,
    totalCobrarReales,
    equivRealesDesdeOro,
    tasa,
  };
}

function actualizarModalTotalesACobrar() {
  const el = document.getElementById("venta-cobro-total-resumen");
  if (!el) {
    return;
  }
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";
  const { totalOro, subtotalReales, descuento, totalCobrarReales, tasa } = datosTotalesCobro();
  if (!carrito.length) {
    el.innerHTML = "";
    return;
  }
  const lineaDesc =
    descuento > 0
      ? `<div class="muted small">Subtotal: ${formatMoney(subtotalReales, "reales")} · Descuento: −${formatMoney(descuento, "reales")}</div>`
      : "";
  if (tipoPago === "reales" || esVentaFiada()) {
    el.innerHTML = `${lineaDesc}<strong>Total a cobrar:</strong> ${formatMoney(totalCobrarReales, "reales")}`;
  } else if (tipoPago === "oro") {
    const oroCobrar =
      tasa && tasa.tasa_reales > 0
        ? Number((totalCobrarReales / tasa.tasa_reales).toFixed(4))
        : totalOro;
    el.innerHTML = `${lineaDesc}<strong>Total a cobrar:</strong> ${oroCobrar.toFixed(4)}g (${formatMoney(totalCobrarReales, "reales")})`;
  } else {
    el.innerHTML = `
      ${lineaDesc}
      <div><strong>Total a cobrar (oro):</strong> ${totalOro.toFixed(4)}g (${formatMoney(totalCobrarReales, "reales")})</div>
      <div><strong>Total en precios de lista:</strong> ${formatMoney(subtotalReales, "reales")}</div>
    `;
  }
}

function actualizarModalVueltoPreview() {
  const el = document.getElementById("venta-cobro-vuelto-preview");
  if (!el) {
    return;
  }
  el.classList.remove("insuficiente");
  if (esVentaFiada()) {
    el.textContent = "Venta fiada: el cobro total no aplica en este momento.";
    return;
  }
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";
  const mOro = Number(document.getElementById("venta-input-monto-oro")?.value || 0);
  const mReales = Number(document.getElementById("venta-input-monto-reales")?.value || 0);
  const { totalOro, totalCobrarReales, tasa } = datosTotalesCobro();

  if (!carrito.length) {
    el.textContent = "";
    return;
  }

  if (tipoPago === "reales") {
    const diff = Number((mReales - totalCobrarReales).toFixed(2));
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

  const oroACobrar =
    tasa.tasa_reales > 0 ? Number((totalCobrarReales / tasa.tasa_reales).toFixed(4)) : totalOro;
  const recibidoEquivOro = Number((mOro + mReales / tasa.tasa_reales).toFixed(4));
  const diffOro = Number((recibidoEquivOro - oroACobrar).toFixed(4));

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
  const base = carrito.reduce(
    (acc, item) => {
      const producto = productos.find((candidate) => candidate.id === item.producto_id);
      if (!producto) {
        return acc;
      }
      const subtotalOro = Number((producto.precio_venta_oro * item.cantidad).toFixed(4));
      const subtotalReales = Number((producto.precio_venta_reales * item.cantidad).toFixed(2));
      acc.totalOro += subtotalOro;
      acc.subtotalReales += subtotalReales;
      acc.items.push({ ...item, producto, subtotal: subtotalOro });
      return acc;
    },
    { totalOro: 0, subtotalReales: 0, items: [] }
  );
  const descuento = obtenerDescuentoCobro();
  const tipoPago = document.getElementById("venta-tipo-pago")?.value || "oro";
  let totalReales = base.subtotalReales;
  if ((tipoPago === "reales" || esVentaFiada()) && descuento > 0) {
    totalReales = Math.max(0, Number((base.subtotalReales - descuento).toFixed(2)));
  }
  return { ...base, totalReales };
}

function htmlTarjetaProducto(p) {
  const esAdmin = getRol() === "admin";
  const fav = esFavorito(p.id);
  const star = esAdmin
    ? `<button type="button" class="pos-fav-btn${fav ? " is-fav" : ""}" data-fav-toggle="${p.id}" title="${fav ? "Quitar de favoritos" : "Agregar a favoritos"}">⭐</button>`
    : "";
  return `
    <div class="pos-card-wrap">
      ${star}
      <button type="button" class="pos-card" data-pos-add="${p.id}">
        <strong>${p.nombre}</strong>
        <span class="pos-card-meta">${formatMoney(p.precio_venta_reales, "reales")}</span>
        <span class="pos-card-stock">Stock: ${p.stock_actual}</span>
      </button>
    </div>`;
}

function renderGridProductos() {
  const grid = document.getElementById("pos-grid-productos");
  if (!grid) {
    return;
  }
  const favoritos = productosFavoritos();
  const favIds = new Set(favoritos.map((p) => p.id));
  const soloFavoritos = categoriaFiltro === FAVORITOS_KEY;
  const categoriaLista =
    soloFavoritos || !categoriaFiltro
      ? []
      : productosDeCategoria(categoriaFiltro).filter((p) => !favIds.has(p.id));

  if (soloFavoritos && !favoritos.length) {
    grid.innerHTML =
      '<p class="muted">No hay favoritos. El administrador puede marcar productos con ⭐ en otras categorias.</p>';
    return;
  }
  if (!soloFavoritos && !favoritos.length && !categoriaLista.length) {
    grid.innerHTML = '<p class="muted">No hay productos en esta categoria.</p>';
    return;
  }

  const partes = [];
  const mostrarFavoritos = favoritos.length > 0;
  if (mostrarFavoritos) {
    if (!soloFavoritos) {
      partes.push('<p class="pos-section-label">Favoritos</p>');
    }
    partes.push('<div class="pos-grid-section">');
    favoritos.forEach((p) => partes.push(htmlTarjetaProducto(p)));
    partes.push("</div>");
  }
  if (categoriaLista.length) {
    partes.push('<p class="pos-section-label">Categoria</p>');
    partes.push('<div class="pos-grid-section">');
    categoriaLista.forEach((p) => partes.push(htmlTarjetaProducto(p)));
    partes.push("</div>");
  }

  grid.innerHTML = partes.join("");

  grid.querySelectorAll("[data-fav-toggle]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      toggleFavorito(Number(btn.dataset.favToggle));
      renderGridProductos();
    });
  });

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
    elOro.textContent = totals.totalOro.toFixed(4);
    elReales.textContent = formatMoney(totals.subtotalReales, "reales");
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
  sel.innerHTML = `<option value="${FAVORITOS_KEY}">Favoritos</option>${ordenados
    .map((c) => `<option value="${c}">${c}</option>`)
    .join("")}`;
  if (!categoriaFiltro) {
    categoriaFiltro = FAVORITOS_KEY;
  }
  sel.value = categoriaFiltro;
}

export async function loadVentas() {
  await ensureTasas();
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

  const esAdmin = getRol() === "admin";
  const tbody = document.getElementById("tabla-ventas");
  if (tbody) {
    if (!ventas.length) {
      tbody.innerHTML = renderEmptyRow(13, "No hay ventas registradas.");
    } else {
      tbody.innerHTML = ventas
        .map((venta) => {
          const anulada = (venta.estado || "VIGENTE") === "ANULADA";
          const btnDevolver =
            esAdmin && !anulada
              ? `<button type="button" class="btn-secondary btn-devolver-venta" data-venta-id="${venta.id}">Devolver</button>`
              : "-";
          const desc =
            Number(venta.descuento_reales || 0) > 0
              ? `<br><span class="muted small">Desc. ${formatMoney(venta.descuento_reales, "reales")}</span>`
              : "";
          return `
          <tr>
            <td>#${venta.id}</td>
            <td>${formatDateOnly(venta.fecha)}</td>
            <td>${formatTimeOnly(venta.fecha)}</td>
            <td>${venta.cliente}</td>
            <td>${formatMoney(venta.total_oro)}</td>
            <td>${formatMoney(venta.total_reales, "reales")}${desc}</td>
            <td>${getRateLabel(venta.tasa_nombre)}</td>
            <td>${venta.tipo_oro ? getRateLabel(venta.tipo_oro) : "-"}</td>
            <td>${venta.tipo_pago}</td>
            <td>${venta.tipo_venta || "contado"}</td>
            <td>${venta.estado_pago || "PAGADO"}${anulada ? " (anulada)" : ""}</td>
            <td>${formatMoney(Number(venta.saldo_pendiente || 0), "reales")}</td>
            <td>${btnDevolver}</td>
          </tr>
        `;
        })
        .join("");
      tbody.querySelectorAll(".btn-devolver-venta").forEach((btn) => {
        btn.addEventListener("click", () => abrirDevolucion(Number(btn.dataset.ventaId)));
      });
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
  actualizarVistaTipoVenta();
  dlg.showModal();
  sincronizarModalCobro();
}

function cerrarCobro() {
  document.getElementById("dialog-cobro-venta")?.close();
}

async function abrirDevolucion(ventaId) {
  if (getRol() !== "admin") {
    showToast("Solo administradores pueden registrar devoluciones", "error");
    return;
  }
  try {
    const venta = await api.get(`/ventas/${ventaId}`);
    if ((venta.estado || "VIGENTE") === "ANULADA") {
      showToast("No se puede devolver una venta anulada", "error");
      return;
    }
    ventaDevolucionActual = venta;
    const resumen = document.getElementById("devolucion-venta-resumen");
    if (resumen) {
      resumen.textContent = `Venta #${venta.id} · ${venta.cliente} · Total actual ${formatMoney(venta.total_reales, "reales")}`;
    }
    renderTablaDevolucion();
    document.getElementById("dialog-devolucion-venta")?.showModal();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderTablaDevolucion() {
  const tbody = document.getElementById("tabla-devolucion-items");
  if (!tbody || !ventaDevolucionActual) {
    return;
  }
  const detalles = ventaDevolucionActual.detalles || [];
  const conStock = detalles.filter((d) => Number(d.cantidad_disponible) > 0);
  if (!conStock.length) {
    tbody.innerHTML = renderEmptyRow(5, "No hay unidades disponibles para devolver.");
    return;
  }
  tbody.innerHTML = conStock
    .map(
      (d) => `
      <tr>
        <td>${d.producto_nombre}</td>
        <td>${d.cantidad}</td>
        <td>${d.cantidad_devuelta}</td>
        <td>${d.cantidad_disponible}</td>
        <td>
          <input
            type="number"
            class="devolucion-qty"
            min="0"
            max="${d.cantidad_disponible}"
            step="0.01"
            value="0"
            data-producto-id="${d.producto_id}"
          >
        </td>
      </tr>`
    )
    .join("");
}

function cerrarDevolucion() {
  ventaDevolucionActual = null;
  document.getElementById("dialog-devolucion-venta")?.close();
}

export function initVentas() {
  const filtro = document.getElementById("venta-filtro-categoria");
  const btnCobrar = document.getElementById("btn-pos-cobrar");
  const formVenta = document.getElementById("form-venta");
  const tipoPagoSelect = document.getElementById("venta-tipo-pago");
  const tipoOroSelect = document.getElementById("venta-tipo-oro");
  const mensajeVuelto = document.getElementById("venta-mensaje-vuelto");
  const btnCerrarModal = document.getElementById("btn-cerrar-cobro");
  const inputMontoOro = document.getElementById("venta-input-monto-oro");
  const inputMontoReales = document.getElementById("venta-input-monto-reales");

  const tipoVentaSel = document.getElementById("venta-tipo-venta");
  const montoInicial = document.getElementById("venta-monto-inicial");

  tipoVentaSel?.addEventListener("change", actualizarVistaTipoVenta);

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

  tipoPagoSelect?.addEventListener("change", () => {
    actualizarVisibilidadCamposPago();
    renderCarrito();
  });
  tipoOroSelect?.addEventListener("change", () => {
    renderCarrito();
    sincronizarModalCobro();
  });
  inputMontoOro?.addEventListener("input", sincronizarModalCobro);
  inputMontoReales?.addEventListener("input", sincronizarModalCobro);
  montoInicial?.addEventListener("input", sincronizarModalCobro);
  document.getElementById("venta-descuento-reales")?.addEventListener("input", () => {
    renderCarrito();
    sincronizarModalCobro();
  });
  document.getElementById("btn-cerrar-devolucion")?.addEventListener("click", cerrarDevolucion);
  document.getElementById("form-devolucion-venta")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!ventaDevolucionActual) {
      return;
    }
    const items = [];
    document.querySelectorAll(".devolucion-qty").forEach((input) => {
      const cantidad = Number(input.value || 0);
      if (cantidad > 0) {
        items.push({ producto_id: Number(input.dataset.productoId), cantidad });
      }
    });
    if (!items.length) {
      showToast("Indique cantidades a devolver", "error");
      return;
    }
    const btn = event.target.querySelector('button[type="submit"]');
    const txt = btn?.textContent ?? "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Procesando...";
    }
    try {
      const res = await api.put(
        `/ventas/${ventaDevolucionActual.id}/devolver`,
        { items },
        adminHeaders()
      );
      showToast(
        `Devolucion registrada: ${formatMoney(res.data.devolucion_reales, "reales")}`,
        "success"
      );
      cerrarDevolucion();
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = txt;
      }
    }
  });
  actualizarVisibilidadCamposPago();

  formVenta?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = formVenta.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";
    if (mensajeVuelto) {
      mensajeVuelto.textContent = "";
    }
    if (!carrito.length) {
      showToast("Agrega al menos un producto al carrito", "error");
      return;
    }
    const formData = new FormData(formVenta);
    const tipoVenta = tipoVentaSel?.value || "contado";
    const tipoPago = tipoPagoSelect.value;
    const tipoOroVal = String(formData.get("tipo_oro") || "").trim();
    let tasaId = null;
    if (tipoVenta !== "fiado" && tipoPago !== "reales") {
      const tasa = findTasaByNombre(tipoOroVal);
      if (!tasa) {
        showToast("Selecciona el tipo de oro (tasa operativa)", "error");
        return;
      }
      tasaId = tasa.id;
    }

    if (tipoVenta === "fiado") {
      const cliFiado = String(formData.get("cliente_fiado") || "").trim();
      if (!cliFiado) {
        showToast("Indique el cliente para la venta fiada", "error");
        return;
      }
    }
    let montoOro = Number(formData.get("monto_recibido_oro"));
    let montoReales = Number(formData.get("monto_recibido_reales"));
    if (tipoVenta === "fiado") {
      montoOro = 0;
      montoReales = 0;
    } else if (tipoPago === "reales") {
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
      tasa_cambio_id: tipoVenta === "fiado" || tipoPago === "reales" ? null : tasaId,
      tipo_pago: tipoVenta === "fiado" ? "reales" : tipoPago,
      tipo_oro: tipoVenta === "fiado" || tipoPago === "reales" ? null : formData.get("tipo_oro") || null,
      monto_recibido_oro: montoOro,
      monto_recibido_reales: montoReales,
      tipo_venta: tipoVenta,
      cliente_fiado: tipoVenta === "fiado" ? String(formData.get("cliente_fiado") || "").trim() : null,
      telefono_fiado: tipoVenta === "fiado" ? String(formData.get("telefono_fiado") || "").trim() || null : null,
      monto_inicial: tipoVenta === "fiado" ? Number(formData.get("monto_inicial") || 0) : 0,
      descuento_reales: Number(formData.get("descuento_reales") || 0),
    };
    if (tipoVenta !== "fiado" && payload.tipo_pago !== "reales" && !payload.tipo_oro) {
      showToast("Selecciona el tipo de oro para el cobro", "error");
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Registrando...";
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
      const descIn = document.getElementById("venta-descuento-reales");
      if (descIn) {
        descIn.value = "0";
      }
      if (tipoVentaSel) {
        tipoVentaSel.value = "contado";
      }
      const fiCli = formVenta.querySelector('[name="cliente_fiado"]');
      if (fiCli) {
        fiCli.value = "";
      }
      const fiTel = formVenta.querySelector('[name="telefono_fiado"]');
      if (fiTel) {
        fiTel.value = "";
      }
      const fiMon = formVenta.querySelector('[name="monto_inicial"]');
      if (fiMon) {
        fiMon.value = "0";
      }
      actualizarVistaTipoVenta();
      actualizarVisibilidadCamposPago();
      renderCarrito();
      cerrarCobro();
      const baseMsg = `Venta #${response.data.venta_id} registrada`;
      showToast(vueltoTxt ? `${baseMsg}. ${vueltoTxt}` : baseMsg, "success");
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
