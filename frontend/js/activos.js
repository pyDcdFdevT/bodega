import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";

const LABEL_CATEGORIA = {
  equipo: "Equipo",
  construccion: "Construccion",
  vehiculo: "Vehiculo",
  otro: "Otro",
};

function adminHeaders() {
  return { headers: { "X-Bodega-Rol": "admin" } };
}

export async function loadActivos() {
  const tbody = document.getElementById("tabla-activos");
  if (!tbody) {
    return;
  }
  const rows = await api.get("/activos");
  if (!rows.length) {
    tbody.innerHTML = renderEmptyRow(7, "No hay activos registrados.");
    return;
  }
  tbody.innerHTML = rows
    .map(
      (a) => `
    <tr>
      <td>#${a.id}</td>
      <td>${formatDate(a.fecha)}</td>
      <td>${LABEL_CATEGORIA[a.categoria] || a.categoria}</td>
      <td>${escapeHtml(a.descripcion)}</td>
      <td>${formatMoney(a.monto_reales, "reales")}</td>
      <td>${formatMoney(a.depreciacion_mensual, "reales")}</td>
      <td>${formatMoney(a.valor_actual, "reales")}</td>
    </tr>`
    )
    .join("");
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function initActivos() {
  const form = document.getElementById("form-activo");
  if (!form) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(form);
    const obs = String(fd.get("observaciones") || "").trim();
    const payload = {
      descripcion: String(fd.get("descripcion") || "").trim(),
      categoria: String(fd.get("categoria") || ""),
      monto_reales: Number(fd.get("monto_reales")),
      vida_util_anios: Number(fd.get("vida_util_anios") || 5),
      valor_residual: Number(fd.get("valor_residual") || 0),
      observaciones: obs || null,
    };
    try {
      const res = await api.post("/activos", payload, adminHeaders());
      form.reset();
      const vidaInput = form.querySelector('[name="vida_util_anios"]');
      const residualInput = form.querySelector('[name="valor_residual"]');
      if (vidaInput) {
        vidaInput.value = "5";
      }
      if (residualInput) {
        residualInput.value = "0";
      }
      const dep = res.depreciacion_mensual;
      showToast(
        dep != null
          ? `Activo registrado · ${formatMoney(dep, "reales")}/mes`
          : "Activo registrado",
        "success"
      );
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
