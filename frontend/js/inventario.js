import { api, formatMoney, renderEmptyRow, setOptions, showToast } from "./api.js";
import { RATE_ORDER, getRateLabel, getTasasCache } from "./tasas.js";

let productosCache = [];

function renderProductos(items) {
  const tbody = document.getElementById("tabla-productos");
  if (!items.length) {
    tbody.innerHTML = renderEmptyRow(10, "No hay productos para mostrar.");
    return;
  }

  tbody.innerHTML = items
    .map(
      (producto) => `
        <tr>
          <td>${producto.nombre}</td>
          <td>${producto.categoria_nombre || "-"}</td>
          <td>${producto.presentacion}</td>
          <td>${producto.unidad_venta}</td>
          <td>${producto.stock_actual}</td>
          <td>${formatMoney(producto.precio_costo_reales, "reales")}</td>
          <td>${formatMoney(producto.precio_venta_reales, "reales")}</td>
          <td>${renderEquivalenteOro(producto)}</td>
          <td><span class="estado ${producto.estado_stock}">${producto.estado_stock}</span></td>
          <td class="acciones">
            <button type="button" onclick="editarProducto(${producto.id})">✏️</button>
            <button type="button" onclick="eliminarProducto(${producto.id}, ${JSON.stringify(producto.nombre)})">🗑️</button>
          </td>
        </tr>
      `
    )
    .join("");
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
    const oro = (Number(producto.precio_venta_reales) / Number(tasa.tasa_reales)).toFixed(3);
    return `<div>${getRateLabel(nombre)}: ${oro}g</div>`;
  }).join("");

  return `
    <details>
      <summary>Ver en oro</summary>
      ${filas}
    </details>
  `;
}

function renderStockBajo(items) {
  const tbody = document.getElementById("tabla-stock-bajo");
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
  renderProductos(productosCache);
  renderStockBajo(stockBajo);
  document.getElementById("hero-productos").textContent = String(productos.length);
  document.getElementById("hero-stock-bajo").textContent = String(stockBajo.length);
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
  selectIds.forEach((id) => {
    const select = document.getElementById(id);
    if (select) {
      setOptions(
        select,
        productos.filter((producto) => producto.activo),
        (producto) => `${producto.nombre} | stock ${producto.stock_actual} | ${formatMoney(producto.precio_venta_reales, "reales")}`
      );
    }
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

async function eliminarProducto(id, nombre) {
  const confirmado = window.confirm(`¿Deseas eliminar el producto "${nombre}"?`);
  if (!confirmado) {
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
    renderProductos(filtered);
  });
}
