import { api, fechaOperativaUtc, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";
import { getProductosCache, loadProductoOptions } from "./inventario.js";

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
  const kgExtra = document.getElementById("compra-kg-extra");
  if (kgExtra && activo) {
    kgExtra.classList.add("hidden");
  }
}

function productoSeleccionado() {
  const id = Number(document.getElementById("compra-producto")?.value);
  if (!id) {
    return null;
  }
  return getProductosCache().find((p) => p.id === id) || null;
}

function esCompraPorKg(producto) {
  return producto?.presentacion === "kg";
}

function actualizarUiCompraKg() {
  const producto = productoSeleccionado();
  const esKg = esCompraPorKg(producto);
  const extra = document.getElementById("compra-kg-extra");
  const labelCant = document.getElementById("compra-cantidad-label");
  const inputCant = document.getElementById("compra-cantidad");
  const kilosFactura = document.getElementById("compra-kilos-factura");
  const kilosRecibidos = document.getElementById("compra-kilos-recibidos");
  const hintUnitario = document.querySelector("#compra-precio-unitario-wrap + .muted.small");

  if (labelCant && inputCant) {
    if (esKg) {
      labelCant.firstChild.textContent = "Kilos según factura ";
    } else {
      labelCant.firstChild.textContent = "Cantidad ";
    }
  }
  if (hintUnitario) {
    hintUnitario.textContent = esKg
      ? "Total R$ dividido entre los kilos de factura."
      : "Total R$ dividido entre la cantidad (se actualiza al escribir).";
  }
  extra?.classList.toggle("hidden", !esKg || Boolean(compraEditandoId));

  if (esKg && kilosFactura && kilosRecibidos) {
    const kf = Number(inputCant?.value) || 0;
    kilosFactura.value = kf > 0 ? String(kf) : "";
    if (!kilosRecibidos.value && kf > 0) {
      kilosRecibidos.value = String(kf);
    }
    actualizarDiferenciaKg();
  }
}

function actualizarDiferenciaKg() {
  const producto = productoSeleccionado();
  if (!esCompraPorKg(producto)) {
    return;
  }
  const kf = Number(document.getElementById("compra-kilos-factura")?.value) || 0;
  const kr = Number(document.getElementById("compra-kilos-recibidos")?.value) || 0;
  const diffEl = document.getElementById("compra-kg-diferencia");
  const mermaWrap = document.getElementById("compra-merma-wrap");
  const mermaCheck = document.getElementById("compra-merma-check");

  if (!diffEl || !mermaWrap) {
    return;
  }

  const diff = Number((kf - kr).toFixed(3));
  if (diff > 0.0001) {
    diffEl.textContent = `Diferencia: -${diff.toFixed(2)} kg`;
    diffEl.classList.remove("hidden");
    mermaWrap.classList.remove("hidden");
  } else {
    diffEl.classList.add("hidden");
    mermaWrap.classList.add("hidden");
    if (mermaCheck) {
      mermaCheck.checked = false;
    }
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
  form.cantidad.value = "1";
  const merma = document.getElementById("compra-merma-check");
  if (merma) {
    merma.checked = false;
  }
  actualizarUiCompraKg();
  actualizarPrecioUnitarioCompra();
}

export async function loadCompras() {
  await loadProductoOptions(["compra-producto"]);
  const [compras, dia] = await Promise.all([
    api.get("/compras?limit=200"),
    api.get("/cierre/dia").catch(() => null),
  ]);
  const fechaDia = dia?.fecha || null;
  const comprasHoy = (compras || []).filter(
    (c) => !fechaDia || fechaOperativaUtc(c.fecha) === fechaDia
  );
  comprasCache = comprasHoy;
  const tbody = document.getElementById("tabla-compras");
  if (!tbody) {
    return;
  }
  if (!comprasHoy.length) {
    tbody.innerHTML = renderEmptyRow(7, "No hay compras registradas hoy.");
    return;
  }

  tbody.innerHTML = comprasHoy
    .map(
      (compra) => `
        <tr>
          <td>#${compra.id}</td>
          <td>${formatDate(compra.fecha)}</td>
          <td>${nombrePrimerProducto(compra)}</td>
          <td>${compra.proveedor}</td>
          <td>${compra.tipo_pago_compra === "credito" ? "Crédito" : "Contado"}</td>
          <td>${formatMoney(compra.total_reales, "reales")}</td>
          <td><button type="button" class="btn-icon" data-edit-compra="${compra.id}" title="Editar">✏️</button></td>
        </tr>
      `
    )
    .join("");
}

function actualizarPrecioUnitarioCompra() {
  const cantidad = Number(document.getElementById("compra-cantidad")?.value) || 0;
  const total = Number(document.querySelector("#form-compra [name=precio_reales]")?.value) || 0;
  const el = document.getElementById("compra-precio-unitario");
  if (!el) {
    return;
  }
  const producto = productoSeleccionado();
  const base = esCompraPorKg(producto)
    ? Number(document.getElementById("compra-kilos-factura")?.value) || cantidad
    : cantidad;
  if (base > 0 && total > 0) {
    el.textContent = formatMoney(total / base, "reales");
  } else {
    el.textContent = formatMoney(0, "reales");
  }
}

export function initCompras() {
  const form = document.getElementById("form-compra");
  const tbody = document.getElementById("tabla-compras");

  form.cantidad?.addEventListener("input", () => {
    actualizarPrecioUnitarioCompra();
    actualizarUiCompraKg();
  });
  form.precio_reales?.addEventListener("input", actualizarPrecioUnitarioCompra);
  document.getElementById("compra-producto")?.addEventListener("change", () => {
    actualizarUiCompraKg();
    actualizarPrecioUnitarioCompra();
  });
  document.getElementById("compra-kilos-recibidos")?.addEventListener("input", actualizarDiferenciaKg);

  actualizarPrecioUnitarioCompra();
  actualizarUiCompraKg();

  tbody?.addEventListener("click", (event) => {
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
    if (form.tipo_pago_compra) {
      form.tipo_pago_compra.value = compra.tipo_pago_compra === "credito" ? "credito" : "contado";
    }
    form.observaciones.value = compra.observaciones || "";
    form.scrollIntoView({ behavior: "smooth", block: "nearest" });
    actualizarPrecioUnitarioCompra();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";
    const formData = new FormData(form);
    const producto = productoSeleccionado();
    const esKg = esCompraPorKg(producto);

    if (compraEditandoId) {
      const payload = {
        cantidad: Number(formData.get("cantidad")),
        precio_reales: Number(formData.get("precio_reales")),
        proveedor: formData.get("proveedor"),
        observaciones: formData.get("observaciones") || null,
        tipo_pago_compra: formData.get("tipo_pago_compra") || "contado",
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

    const cantidad = Number(formData.get("cantidad"));
    const kilosRecibidosRaw = document.getElementById("compra-kilos-recibidos")?.value;
    const payload = {
      producto_id: Number(formData.get("producto_id")),
      cantidad,
      precio_reales: Number(formData.get("precio_reales")),
      proveedor: formData.get("proveedor"),
      observaciones: formData.get("observaciones") || null,
      tipo_pago_compra: formData.get("tipo_pago_compra") || "contado",
    };

    if (esKg) {
      const kr = Number(kilosRecibidosRaw);
      if (!kr || kr <= 0) {
        showToast("Indique los kilos recibidos (pesaje real)", "error");
        return;
      }
      payload.kilos_factura = cantidad;
      payload.kilos_recibidos = kr;
      const unidades = Number(formData.get("unidades"));
      if (unidades > 0) {
        payload.unidades = unidades;
      }
      if (document.getElementById("compra-merma-check")?.checked) {
        payload.registrar_merma_transporte = true;
      }
    }

    if (btn) {
      btn.disabled = true;
      btn.textContent = "Registrando...";
    }
    try {
      const res = await api.post("/compras", payload);
      resetFormularioCompra(form);
      const data = res?.data;
      if (data?.salida_merma_id) {
        showToast(
          `Compra registrada. Merma transporte: ${data.merma_transporte_kg} kg registrada.`,
          "success"
        );
      } else {
        showToast("Compra registrada correctamente", "success");
      }
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
