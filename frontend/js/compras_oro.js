import { api, formatDate, formatMoney, formatRate, renderEmptyRow, showToast } from "./api.js";
import { RATE_ORDER, ensureTasas, findTasaByNombre, getRateLabel } from "./tasas.js";

function actualizarTasaPorTipo() {
  const tipoSelect = document.getElementById("compra-oro-tipo");
  const tasaInput = document.getElementById("compra-oro-tasa");
  const tasa = findTasaByNombre(tipoSelect.value);
  if (tasa) {
    tasaInput.value = formatRate(tasa.tasa_reales);
  }
  actualizarTotalCompraOro();
}

function actualizarTotalCompraOro() {
  const gramos = Number(document.getElementById("compra-oro-gramos").value || 0);
  const tasa = Number(document.getElementById("compra-oro-tasa").value || 0);
  const total = gramos * tasa;
  document.getElementById("compra-oro-total").textContent = formatMoney(total, "reales");
}

export async function loadComprasOro() {
  await ensureTasas();
  const compras = await api.get("/compras-oro");
  const tipoSelect = document.getElementById("compra-oro-tipo");

  if (!tipoSelect.dataset.ready) {
    tipoSelect.innerHTML = RATE_ORDER
      .map((nombre) => `<option value="${nombre}">${getRateLabel(nombre)}</option>`)
      .join("");
    tipoSelect.dataset.ready = "1";
  }

  actualizarTasaPorTipo();

  const tbody = document.getElementById("tabla-compras-oro");
  if (!compras.length) {
    tbody.innerHTML = renderEmptyRow(6, "No hay compras de oro registradas.");
    return;
  }

  tbody.innerHTML = compras
    .map(
      (compra) => `
        <tr>
          <td>#${compra.id}</td>
          <td>${formatDate(compra.fecha)}</td>
          <td>${getRateLabel(compra.tipo_oro)}</td>
          <td>${formatMoney(compra.gramos)}</td>
          <td>R$ ${formatRate(compra.tasa_compra_reales)}</td>
          <td>${formatMoney(compra.total_reales, "reales")}</td>
        </tr>
      `
    )
    .join("");
}

export function initComprasOro() {
  const form = document.getElementById("form-compra-oro");
  const tipoSelect = document.getElementById("compra-oro-tipo");
  const gramosInput = document.getElementById("compra-oro-gramos");
  const tasaInput = document.getElementById("compra-oro-tasa");

  tipoSelect.addEventListener("change", actualizarTasaPorTipo);
  gramosInput.addEventListener("input", actualizarTotalCompraOro);
  tasaInput.addEventListener("input", actualizarTotalCompraOro);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      tipo_oro: formData.get("tipo_oro"),
      gramos: Number(formData.get("gramos")),
      tasa_compra_reales: Number(formData.get("tasa_compra_reales")),
    };

    try {
      await api.post("/compras-oro", payload);
      showToast("Compra de oro registrada", "success");
      gramosInput.value = "0.00";
      actualizarTasaPorTipo();
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
