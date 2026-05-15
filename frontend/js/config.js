import { api, showToast } from "./api.js";
import { getRol } from "./auth.js";

const THEME_KEY = "bodega-theme";

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

function adminHeaders() {
  return { headers: { "X-Bodega-Rol": "admin" } };
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
  dialog.showModal();
}

function cerrarModalConfig() {
  document.getElementById("dialog-config")?.close();
}

export function initConfig() {
  applyTheme(getStoredTheme());

  document.getElementById("btn-config")?.addEventListener("click", abrirModalConfig);
  document.getElementById("btn-config-cerrar")?.addEventListener("click", cerrarModalConfig);
  document.getElementById("dialog-config")?.addEventListener("cancel", () => {
    cerrarModalConfig();
  });

  document.getElementById("config-theme-toggle")?.addEventListener("change", (ev) => {
    applyTheme(ev.target.checked ? "dark" : "light");
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
    for (const [key, val] of Object.entries(payload)) {
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
