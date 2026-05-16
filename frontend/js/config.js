import { api, showToast } from "./api.js";
import { getRol } from "./auth.js";

const THEME_KEY = "bodega-theme";
const NOMBRE_BODEGA_DEFAULT = "Bodega Minera";

export function getStoredTheme() {
  return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
}

export function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(THEME_KEY, next);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", next === "dark" ? "#1a1a2e" : "#17324d");
  }
  const toggle = document.getElementById("config-theme-toggle");
  if (toggle) {
    toggle.checked = next === "dark";
  }
}

export function applyNombreBodega(nombre) {
  const limpio = String(nombre || "").trim() || NOMBRE_BODEGA_DEFAULT;
  const titulo = document.getElementById("app-nombre-bodega");
  if (titulo) {
    titulo.textContent = limpio;
  }
  document.title = `${limpio} — Bodega POS`;
  const input = document.getElementById("config-nombre-bodega");
  if (input && document.activeElement !== input) {
    input.value = limpio;
  }
  return limpio;
}

function adminHeaders() {
  return { headers: { "X-Bodega-Rol": "admin" } };
}

export async function loadNombreBodega() {
  try {
    const data = await api.get("/configuracion/app");
    return applyNombreBodega(data.nombre_bodega);
  } catch {
    return applyNombreBodega(NOMBRE_BODEGA_DEFAULT);
  }
}

function actualizarSeccionNombreBodega() {
  const btn = document.getElementById("btn-guardar-nombre-bodega");
  const input = document.getElementById("config-nombre-bodega");
  const esAdmin = getRol() === "admin";
  if (btn) {
    btn.style.display = esAdmin ? "" : "none";
  }
  if (input) {
    input.readOnly = !esAdmin;
  }
}

function abrirModalConfig() {
  const dialog = document.getElementById("dialog-config");
  if (!dialog || typeof dialog.showModal !== "function") {
    showToast("Su navegador no soporta el modal de configuracion", "error");
    return;
  }
  const pinSection = document.getElementById("config-pin-section");
  if (pinSection) {
    pinSection.style.display = getRol() === "admin" ? "" : "none";
  }
  actualizarSeccionNombreBodega();
  const toggle = document.getElementById("config-theme-toggle");
  if (toggle) {
    toggle.checked = getStoredTheme() === "dark";
  }
  const pinForm = document.getElementById("form-cambiar-pines");
  pinForm?.reset();
  const pinErr = document.getElementById("config-pin-error");
  if (pinErr) {
    pinErr.textContent = "";
  }
  const nombreErr = document.getElementById("config-nombre-error");
  if (nombreErr) {
    nombreErr.textContent = "";
  }
  loadNombreBodega();
  dialog.showModal();
}

function cerrarModalConfig() {
  document.getElementById("dialog-config")?.close();
}

export function initConfig() {
  applyTheme(getStoredTheme());
  loadNombreBodega();

  document.getElementById("btn-config")?.addEventListener("click", abrirModalConfig);
  document.getElementById("btn-config-cerrar")?.addEventListener("click", cerrarModalConfig);
  document.getElementById("dialog-config")?.addEventListener("cancel", () => {
    cerrarModalConfig();
  });

  document.getElementById("config-theme-toggle")?.addEventListener("change", (ev) => {
    applyTheme(ev.target.checked ? "dark" : "light");
  });

  const nombreForm = document.getElementById("form-nombre-bodega");
  nombreForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (getRol() !== "admin") {
      showToast("Solo administradores pueden cambiar el nombre", "error");
      return;
    }
    const btn = document.getElementById("btn-guardar-nombre-bodega");
    const originalText = btn?.textContent ?? "";
    const input = document.getElementById("config-nombre-bodega");
    const nombre = String(input?.value || "").trim();
    if (!nombre) {
      showToast("Indique un nombre para la bodega", "error");
      return;
    }
    const errEl = document.getElementById("config-nombre-error");
    if (errEl) {
      errEl.textContent = "";
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Guardando...";
    }
    try {
      const data = await api.put(
        "/configuracion/nombre-bodega",
        { nombre },
        adminHeaders()
      );
      applyNombreBodega(data.nombre_bodega);
      showToast("Nombre de bodega guardado", "success");
    } catch (error) {
      if (errEl) {
        errEl.textContent = error.message || "Error al guardar";
      }
      showToast(error.message || "Error al guardar el nombre", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    }
  });

  const pinForm = document.getElementById("form-cambiar-pines");
  pinForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (getRol() !== "admin") {
      showToast("Solo administradores pueden cambiar los PIN", "error");
      return;
    }
    const btn = pinForm.querySelector('button[type="submit"]');
    const originalText = btn?.textContent ?? "";
    const fd = new FormData(pinForm);
    const payload = {
      pin_admin_actual: String(fd.get("pin_admin_actual") || "").replace(/\D/g, ""),
      pin_admin_nuevo: String(fd.get("pin_admin_nuevo") || "").replace(/\D/g, ""),
      pin_vendedor_actual: String(fd.get("pin_vendedor_actual") || "").replace(/\D/g, ""),
      pin_vendedor_nuevo: String(fd.get("pin_vendedor_nuevo") || "").replace(/\D/g, ""),
    };
    for (const val of Object.values(payload)) {
      if (val.length !== 4) {
        showToast("Todos los PIN deben tener 4 digitos", "error");
        return;
      }
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Guardando...";
    }
    try {
      await api.post("/auth/cambiar-pines", payload, adminHeaders());
      showToast("PINs actualizados correctamente", "success");
      pinForm.reset();
      cerrarModalConfig();
    } catch (error) {
      const errEl = document.getElementById("config-pin-error");
      if (errEl) {
        errEl.textContent = error.message || "Error al cambiar PINs";
      }
      showToast(error.message || "Error al cambiar PINs", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    }
  });
}
