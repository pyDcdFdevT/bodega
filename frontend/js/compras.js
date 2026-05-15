import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { loadProductoOptions } from "./inventario.js";

let comprasCache = [];
let compraEditandoId = null;

function setModoEdicion(activo) {
  const btn = document.getElementById("compra-submit-btn");
  const select = document.getElementById("compra-producto");
  if (btn) {
    btn.textContent = activo ? "Actualizar compra" : "Registrar compra";
  }
  if (select) {
    select.disabled = activo;
  }
}

function nombrePrimerProducto(compra) {
  const detalle = compra.detalles?.[0];
  if (!detalle) {
    return "-";
  }
  return detalle.producto_nombre || "-";
}

function resetFormularioCompra(form) {
  compraEditandoId = null;
  setModoEdicion(false);
  form.reset();
  form.proveedor.value = "Proveedor";
}

export async function loadCompras() {
  await loadProductoOptions(["compra-producto"]);
  const compras = await api.get("/compras");
  comprasCache = compras;
  const tbody = document.getElementById("tabla-compras");

  if (!compras.length) {
    tbody.innerHTML = renderEmptyRow(6, "No hay compras registradas.");
    return;
  }

  tbody.innerHTML = compras
    .map(
      (compra) => `
        <tr>
          <td>#${compra.id}</td>
          <td>${formatDate(compra.fecha)}</td>
          <td>${nombrePrimerProducto(compra)}</td>
          <td>${compra.proveedor}</td>
          <td>${formatMoney(compra.total_reales, "reales")}</td>
          <td><button type="button" class="btn-icon" data-edit-compra="${compra.id}" title="Editar">✏️</button></td>
        </tr>
      `
    )
    .join("");
}

export function initCompras() {
  const form = document.getElementById("form-compra");
  const tbody = document.getElementById("tabla-compras");

  function actualizarPrecioUnitarioCompra() {
    const cant = Number(form.cantidad?.value || 0);
    const pr = Number(form.precio_reales?.value || 0);
    const el = document.getElementById("compra-precio-unitario");
    if (!el) {
      return;
    }
    if (cant > 0 && pr >= 0) {
      el.textContent = formatMoney(pr / cant, "reales");
    } else {
      el.textContent = formatMoney(0, "reales");
    }
  }
  form.cantidad?.addEventListener("input", actualizarPrecioUnitarioCompra);
  form.precio_reales?.addEventListener("input", actualizarPrecioUnitarioCompra);
  actualizarPrecioUnitarioCompra();

  tbody.addEventListener("click", (event) => {
    const boton = event.target.closest("[data-edit-compra]");
    if (!boton) {
      return;
    }
    const id = Number(boton.dataset.editCompra);
    const compra = comprasCache.find((item) => item.id === id);
    if (!compra || !compra.detalles?.length) {
      showToast("No se pudieron cargar los datos de la compra", "error");
      return;
    }
    const detalle = compra.detalles[0];
    compraEditandoId = id;
    setModoEdicion(true);
    form.producto_id.value = String(detalle.producto_id);
    form.cantidad.value = String(detalle.cantidad);
    form.precio_reales.value = String(detalle.precio_reales_total ?? compra.total_reales);
    form.proveedor.value = compra.proveedor || "Proveedor";
    form.observaciones.value = compra.observaciones || "";
    form.scrollIntoView({ behavior: "smooth", block: "nearest" });
    actualizarPrecioUnitarioCompra();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";
    const formData = new FormData(form);

    if (compraEditandoId) {
      const payload = {
        cantidad: Number(formData.get("cantidad")),
        precio_reales: Number(formData.get("precio_reales")),
        proveedor: formData.get("proveedor"),
        observaciones: formData.get("observaciones") || null,
      };
      if (btn) {
        btn.disabled = true;
        btn.textContent = "Registrando...";
      }
      try {
        await api.put(`/compras/${compraEditandoId}`, payload);
        resetFormularioCompra(form);
        showToast("Compra actualizada correctamente", "success");
        document.dispatchEvent(new CustomEvent("bodega:refresh"));
      } catch (error) {
        showToast(error.message, "error");
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = originalText;
        }
      }
      return;
    }

    const payload = {
      producto_id: Number(formData.get("producto_id")),
      cantidad: Number(formData.get("cantidad")),
      precio_reales: Number(formData.get("precio_reales")),
      proveedor: formData.get("proveedor"),
      observaciones: formData.get("observaciones") || null,
    };

    if (btn) {
      btn.disabled = true;
      btn.textContent = "Registrando...";
    }
    try {
      await api.post("/compras", payload);
      resetFormularioCompra(form);
      showToast("Compra registrada correctamente", "success");
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
