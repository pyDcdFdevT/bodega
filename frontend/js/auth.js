import { api } from "./api.js";

const SESSION_KEY = "bodega_pin_ok";
const SESSION_ROL_KEY = "bodega_rol";

export async function verificarPin(pin) {
  return api.post("/auth/verificar-pin", { pin });
}

function mostrarPantallaBloqueo() {
  const pantalla = document.getElementById("pantalla-bloqueo");
  if (pantalla) {
    pantalla.style.display = "flex";
  }
}

function ocultarPantallaBloqueo() {
  const pantalla = document.getElementById("pantalla-bloqueo");
  if (pantalla) {
    pantalla.style.display = "none";
  }
}

function limpiarError() {
  const error = document.getElementById("pin-error");
  if (error) {
    error.textContent = "";
  }
}

function mostrarError(texto) {
  const error = document.getElementById("pin-error");
  if (error) {
    error.textContent = texto;
  }
}

function sesionActiva() {
  return sessionStorage.getItem(SESSION_KEY) === "1" && !!sessionStorage.getItem(SESSION_ROL_KEY);
}

function guardarSesion(rol) {
  sessionStorage.setItem(SESSION_KEY, "1");
  sessionStorage.setItem(SESSION_ROL_KEY, rol);
}

/** `"admin"` | `"vendedor"` | `null` si no hay sesión con PIN. */
export function getRol() {
  const r = sessionStorage.getItem(SESSION_ROL_KEY);
  if (r === "admin" || r === "vendedor") {
    return r;
  }
  return null;
}

export function cerrarSesion() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(SESSION_ROL_KEY);
  location.replace(location.pathname);
}

function enlazarCerrarSesion() {
  const boton = document.getElementById("btn-cerrar-sesion");
  if (!boton || boton.dataset.bound === "1") {
    return;
  }
  boton.dataset.bound = "1";
  boton.addEventListener("click", () => cerrarSesion());
}

export async function initAuth() {
  enlazarCerrarSesion();

  if (sesionActiva()) {
    ocultarPantallaBloqueo();
    return true;
  }

  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(SESSION_ROL_KEY);

  const form = document.getElementById("form-pin");
  const input = document.getElementById("pin-input");
  if (!form || !input) {
    return false;
  }

  input.value = "";
  limpiarError();
  mostrarPantallaBloqueo();

  return new Promise((resolve) => {
    const onSubmit = async (ev) => {
      ev.preventDefault();
      limpiarError();
      const pin = String(input.value || "").replace(/\D/g, "").slice(0, 4);
      if (pin.length !== 4) {
        mostrarError("Ingrese 4 digitos");
        return;
      }
      try {
        const res = await verificarPin(pin);
        if (res.acceso === true && (res.rol === "admin" || res.rol === "vendedor")) {
          guardarSesion(res.rol);
          input.value = "";
          ocultarPantallaBloqueo();
          form.removeEventListener("submit", onSubmit);
          document.dispatchEvent(new CustomEvent("bodega:unlocked"));
          resolve(true);
        } else {
          mostrarError("PIN incorrecto");
          input.focus();
          input.select();
        }
      } catch (err) {
        mostrarError(String(err?.message || "Error al verificar el PIN"));
      }
    };
    form.addEventListener("submit", onSubmit);
  });
}
