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
    tbody.innerHTML = renderEmptyRow(5, "No hay activos registrados.");
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
      observaciones: obs || null,
    };
    try {
      await api.post("/activos", payload, adminHeaders());
      form.reset();
      showToast("Activo registrado", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}
