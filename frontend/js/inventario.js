import { api, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { RATE_ORDER, getRateLabel, getTasasCache } from "./tasas.js";

let productosCache = [];

function agruparPorCategoria(items) {
  const map = new Map();
  items.forEach((p) => {
    const cat = p.categoria_nombre || "Sin categoria";
    if (!map.has(cat)) {
      map.set(cat, []);
    }
    map.get(cat).push(p);
  });
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function renderEquivalenteOro(producto) {
  const tasas = getTasasCache();
  if (!tasas.length || !producto.precio_venta_reales) {
    return "<span>-</span>";
  }
  const filas = RATE_ORDER.map((nombre) => {
    const tasa = tasas.find((item) => item.nombre === nombre);
    if (!tasa || !tasa.tasa_reales) {
      return "";
    }
    const oro = (Number(producto.precio_venta_reales) / Number(tasa.tasa_reales)).toFixed(4);
    return `<div>${getRateLabel(nombre)}: ${oro}g</div>`;
  }).join("");
  return `<details><summary>Ver en oro</summary>${filas}</details>`;
}

function tablaProductosHtml(productos) {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Producto</th>
            <th>Inventario</th>
            <th>Venta</th>
            <th>Stock</th>
            <th>Costo R$</th>
            <th>Venta R$</th>
            <th>Equiv. oro</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${productos
            .map(
              (producto) => `
            <tr>
              <td>${producto.nombre}</td>
              <td>${producto.presentacion}</td>
              <td>${producto.unidad_venta}</td>
              <td>${producto.stock_actual}</td>
              <td>${formatMoney(producto.precio_costo_reales, "reales")}</td>
              <td>${formatMoney(producto.precio_venta_reales, "reales")}</td>
              <td>${renderEquivalenteOro(producto)}</td>
              <td><span class="estado ${producto.estado_stock}">${producto.estado_stock}</span></td>
              <td class="acciones">
                <button type="button" onclick="window.editarProducto(${producto.id})">✏️</button>
                <button type="button" onclick="window.eliminarProducto(${producto.id})">🗑️</button>
              </td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function renderProductosAccordiones(items) {
  const root = document.getElementById("inventario-accordiones");
  if (!root) {
    return;
  }
  if (!items.length) {
    root.innerHTML = '<p class="muted">No hay productos para mostrar.</p>';
    return;
  }
  const grupos = agruparPorCategoria(items);
  root.innerHTML = grupos
    .map(
      ([categoria, productos], idx) => `
      <details class="accordion-cat" ${idx === 0 ? "open" : ""}>
        <summary class="accordion-cat-summary">
          <span class="accordion-cat-icon">📁</span>
          <span class="accordion-cat-name">${categoria}</span>
          <span class="accordion-cat-count">${productos.length} producto(s)</span>
        </summary>
        <div class="accordion-cat-body">${tablaProductosHtml(productos)}</div>
      </details>`
    )
    .join("");
}

function renderStockBajo(items) {
  const tbody = document.getElementById("tabla-stock-bajo");
  if (!tbody) {
    return;
  }
  if (!items.length) {
    tbody.innerHTML = renderEmptyRow(3, "Todo el inventario esta por encima del minimo.");
    return;
  }
  tbody.innerHTML = items
    .map(
      (producto) => `
        <tr>
          <td>${producto.nombre}</td>
          <td>${producto.stock_actual}</td>
          <td>${producto.stock_minimo}</td>
        </tr>
      `
    )
    .join("");
}

export async function loadInventario() {
  const [productos, stockBajo] = await Promise.all([
    api.get("/productos"),
    api.get("/productos/stock-bajo"),
  ]);
  productosCache = productos;
  renderProductosAccordiones(productosCache);
  renderStockBajo(stockBajo);
  const hp = document.getElementById("hero-productos");
  const hs = document.getElementById("hero-stock-bajo");
  if (hp) {
    hp.textContent = String(productos.length);
  }
  if (hs) {
    hs.textContent = String(stockBajo.length);
  }
  return productosCache;
}

export function getProductosCache() {
  return productosCache;
}

function restaurarFormularioProducto() {
  const form = document.getElementById("form-producto");
  const submitButton = form.querySelector('button[type="submit"]');
  form.reset();
  delete form.dataset.id;
  form.presentacion.value = "unidad";
  form.unidad_venta.value = "unidad";
  form.stock_actual.value = "0";
  form.stock_minimo.value = "5";
  form.precio_venta_reales.value = "0.00";
  submitButton.textContent = "Guardar producto";
}

export async function loadProductoOptions(selectIds) {
  const productos = productosCache.length ? productosCache : await loadInventario();
  const activos = productos.filter((producto) => producto.activo);
  selectIds.forEach((id) => {
    const select = document.getElementById(id);
    if (!select) {
      return;
    }
    const grupos = agruparPorCategoria(activos);
    select.innerHTML = `<option value="">Seleccione...</option>${grupos
      .map(
        ([cat, lista]) =>
          `<optgroup label="${cat}">${lista
            .map(
              (p) =>
                `<option value="${p.id}">${p.nombre} | stock ${p.stock_actual} | ${formatMoney(p.precio_venta_reales, "reales")}</option>`
            )
            .join("")}</optgroup>`
      )
      .join("")}`;
  });
}

function editarProducto(id) {
  const producto = productosCache.find((item) => item.id === id);
  if (!producto) {
    showToast("Producto no encontrado", "error");
    return;
  }
  const form = document.getElementById("form-producto");
  const submitButton = form.querySelector('button[type="submit"]');
  form.nombre.value = producto.nombre;
  form.categoria_nombre.value = producto.categoria_nombre || "";
  form.presentacion.value = producto.presentacion;
  form.unidad_venta.value = producto.unidad_venta;
  form.stock_actual.value = producto.stock_actual;
  form.stock_minimo.value = producto.stock_minimo;
  form.precio_venta_reales.value = producto.precio_venta_reales;
  form.dataset.id = String(producto.id);
  submitButton.textContent = "Actualizar producto";
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function eliminarProducto(id) {
  const producto = productosCache.find((item) => item.id === id);
  const nombre = producto?.nombre || "este producto";
  let info;
  try {
    info = await api.get(`/productos/${id}/info-eliminacion`);
  } catch (error) {
    showToast(error.message, "error");
    return;
  }
  const tieneMovimientos = Number(info.total_movimientos) > 0;
  const advertencia = Boolean(info.tiene_stock) || tieneMovimientos;
  let mensaje;
  if (advertencia) {
    mensaje =
      `ADVERTENCIA: desactivar "${nombre}"\n\n` +
      `• Stock actual: ${info.stock_actual}\n` +
      `• Lineas de venta (historial): ${info.total_ventas}\n` +
      `• Lineas de compra (historial): ${info.total_compras}\n` +
      `• Movimientos de inventario: ${info.total_movimientos}\n\n` +
      `El producto se desactivara; el historial no se borra.\n\n` +
      `¿Confirmar desactivacion?`;
  } else {
    mensaje = `¿Desactivar el producto "${nombre}"?`;
  }
  if (!window.confirm(mensaje)) {
    return;
  }
  try {
    await api.delete(`/productos/${id}`);
    showToast("Producto eliminado correctamente", "success");
    document.dispatchEvent(new CustomEvent("bodega:refresh"));
  } catch (error) {
    showToast(error.message, "error");
  }
}

window.editarProducto = editarProducto;
window.eliminarProducto = eliminarProducto;

export function initInventario() {
  const form = document.getElementById("form-producto");
  const search = document.getElementById("inventario-busqueda");
  const submitButton = form.querySelector('button[type="submit"]');

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    payload.stock_actual = Number(payload.stock_actual);
    payload.stock_minimo = Number(payload.stock_minimo);
    payload.precio_venta_reales = Number(payload.precio_venta_reales);
    try {
      if (form.dataset.id) {
        await api.put(`/productos/${form.dataset.id}`, payload);
        showToast("Producto actualizado correctamente", "success");
      } else {
        await api.post("/productos", payload);
        showToast("Producto registrado correctamente", "success");
      }
      restaurarFormularioProducto();
      submitButton.textContent = "Guardar producto";
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  search.addEventListener("input", () => {
    const term = search.value.trim().toLowerCase();
    const filtered = productosCache.filter((producto) => producto.nombre.toLowerCase().includes(term));
    renderProductosAccordiones(filtered);
  });
}
