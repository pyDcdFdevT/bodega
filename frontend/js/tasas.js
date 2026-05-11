import { api, formatDate, renderEmptyRow, showToast } from "./api.js";

export async function loadTasas() {
  const [actual, historial] = await Promise.all([api.get("/tasas/actual"), api.get("/tasas/historial")]);
  const pill = document.getElementById("tasa-actual-pill");
  if (!actual.configurado) {
    pill.textContent = "Sin configurar";
  } else {
    pill.textContent = `R$ ${Number(actual.tasa).toFixed(2)} / g`;
  }

  const tbody = document.getElementById("tabla-tasas");
  if (!historial.length) {
    tbody.innerHTML = renderEmptyRow(5, "No hay cambios de tasa registrados.");
    return;
  }

  tbody.innerHTML = historial
    .map(
      (item) => `
        <tr>
          <td>${formatDate(item.fecha_cambio)}</td>
          <td>${item.tasa_anterior ?? "-"}</td>
          <td>${item.tasa_nueva}</td>
          <td>${item.variacion_porcentaje ?? "-"}%</td>
          <td>${item.motivo || "-"}</td>
        </tr>
      `
    )
    .join("");
}

export function initTasas() {
  const formInicial = document.getElementById("form-tasa-inicial");
  const formActualizar = document.getElementById("form-tasa-actualizar");

  formInicial.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(formInicial);
    try {
      await api.post("/tasas/iniciar-dia", {
        tasa_reales: Number(formData.get("tasa_reales")),
        motivo: formData.get("motivo"),
      });
      showToast("Tasa configurada correctamente", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  formActualizar.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(formActualizar);
    try {
      await api.put("/tasas/actualizar", {
        tasa_reales: Number(formData.get("tasa_reales")),
        motivo: formData.get("motivo"),
      });
      showToast("Tasa actualizada correctamente", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
