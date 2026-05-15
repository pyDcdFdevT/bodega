import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";

const CATEGORIAS = [
  { value: "viaje", label: "Viaje" },
  { value: "comida", label: "Comida" },
  { value: "estadia", label: "Estadia" },
  { value: "repuestos", label: "Repuestos" },
  { value: "insumos", label: "Insumos" },
  { value: "otro", label: "Otro" },
];

function renderTablaHoy(data) {
  const tbody = document.getElementById("tabla-gastos-hoy");
  const totalEl = document.getElementById("gastos-total-hoy");
  if (totalEl) {
    totalEl.textContent = formatMoney(data.total_reales, "reales");
  }
  if (!tbody) {
    return;
  }
  const items = data.items || [];
  if (!items.length) {
    tbody.innerHTML = renderEmptyRow(4, "No hay gastos registrados hoy.");
    return;
  }
  tbody.innerHTML = items
    .map(
      (row) => `
    <tr>
      <td>${formatDate(row.fecha)}</td>
      <td>${row.categoria}</td>
      <td>${row.descripcion}</td>
      <td>${formatMoney(row.monto_reales, "reales")}</td>
    </tr>`
    )
    .join("");
}

export async function loadGastos() {
  const data = await api.get("/gastos/hoy");
  renderTablaHoy(data);
}

export function initGastos() {
  const form = document.getElementById("form-gasto");
  const cat = document.getElementById("gasto-categoria");
  if (cat && !cat.dataset.ready) {
    cat.innerHTML = CATEGORIAS.map((c) => `<option value="${c.value}">${c.label}</option>`).join("");
    cat.dataset.ready = "1";
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";
    const fd = new FormData(form);
    const payload = {
      categoria: fd.get("categoria"),
      descripcion: String(fd.get("descripcion") || "").trim(),
      monto_reales: Number(fd.get("monto_reales")),
    };
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Registrando...";
    }
    try {
      await api.post("/gastos", payload);
      form.reset();
      showToast("Gasto registrado", "success");
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
