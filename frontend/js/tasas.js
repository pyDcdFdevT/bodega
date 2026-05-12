import { api, formatDate, formatRate, renderEmptyRow, showToast } from "./api.js";

export const RATE_ORDER = [
  "araparita",
  "uruman",
  "santa_elena_minero",
  "santa_elena_fundido",
];

export const RATE_LABELS = {
  araparita: "Araparita",
  uruman: "Uruman",
  santa_elena_minero: "Santa Elena Minero",
  santa_elena_fundido: "Santa Elena Fundido",
};

let tasasCache = [];

export function getTasasCache() {
  return tasasCache;
}

export function getRateLabel(nombre) {
  return RATE_LABELS[nombre] || nombre;
}

export function findTasaById(id) {
  return tasasCache.find((tasa) => tasa.id === Number(id));
}

export function findTasaByNombre(nombre) {
  return tasasCache.find((tasa) => tasa.nombre === nombre);
}

export async function ensureTasas() {
  if (tasasCache.length === RATE_ORDER.length) {
    return tasasCache;
  }
  return loadTasas();
}

export function fillTasaSelect(selectId) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }
  const previousValue = select.value;
  select.innerHTML = `
    <option value="">Seleccione una tasa...</option>
    ${tasasCache
      .map(
        (tasa) =>
          `<option value="${tasa.id}">${getRateLabel(tasa.nombre)} | R$ ${formatRate(tasa.tasa_reales)}</option>`
      )
      .join("")}
  `;
  if ([...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  } else if (select.options.length > 1) {
    select.selectedIndex = 1;
  }
}

export async function loadTasas() {
  tasasCache = await api.get("/tasas");

  const pill = document.getElementById("tasa-actual-pill");
  if (pill) {
    pill.textContent = `${tasasCache.length} tasas activas`;
  }

  const form = document.getElementById("form-tasas");
  if (form) {
    RATE_ORDER.forEach((nombre) => {
      const input = form.elements[nombre];
      const tasa = findTasaByNombre(nombre);
      if (input && tasa) {
        input.value = formatRate(tasa.tasa_reales);
      }
    });
  }

  const tbody = document.getElementById("tabla-tasas");
  if (tbody) {
    if (!tasasCache.length) {
      tbody.innerHTML = renderEmptyRow(3, "No hay tasas configuradas.");
    } else {
      tbody.innerHTML = tasasCache
        .map(
          (tasa) => `
            <tr>
              <td>${getRateLabel(tasa.nombre)}</td>
              <td>R$ ${formatRate(tasa.tasa_reales)}</td>
              <td>${formatDate(tasa.actualizado_en)}</td>
            </tr>
          `
        )
        .join("");
    }
  }

  const tablaProductos = document.getElementById("tabla-tasas-productos");
  if (tablaProductos) {
    const productos = await api.get("/productos");
    if (!productos.length) {
      tablaProductos.innerHTML = renderEmptyRow(6, "No hay productos para calcular equivalencias.");
    } else {
      tablaProductos.innerHTML = productos
        .map((producto) => {
          const equivalentes = RATE_ORDER.map((nombre) => {
            const tasa = findTasaByNombre(nombre);
            if (!tasa || !tasa.tasa_reales) {
              return "-";
            }
            return `${(Number(producto.precio_venta_reales) / Number(tasa.tasa_reales)).toFixed(3)}g`;
          });
          return `
            <tr>
              <td>${producto.nombre}</td>
              <td>R$ ${Number(producto.precio_venta_reales || 0).toFixed(2)}</td>
              <td>${equivalentes[0]}</td>
              <td>${equivalentes[1]}</td>
              <td>${equivalentes[2]}</td>
              <td>${equivalentes[3]}</td>
            </tr>
          `;
        })
        .join("");
    }
  }

  return tasasCache;
}

export function initTasas() {
  const form = document.getElementById("form-tasas");
  if (!form) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    RATE_ORDER.forEach((nombre) => {
      payload[nombre] = Number(payload[nombre]);
    });

    try {
      await api.put("/tasas", payload);
      showToast("Tasas actualizadas correctamente", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
