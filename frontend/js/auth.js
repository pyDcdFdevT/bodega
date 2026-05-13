import { api, showToast } from "./api.js";

const SESSION_KEY = "bodega_pin_ok";
const SESSION_ROL_KEY = "bodega_rol";

async function verificarPin(pin) {
  return api.post("/auth/verificar-pin", { pin });
}

function mostrarPantallaBloqueo() {
  const pantalla = document.getElementById("pantalla-bloqueo");
  pantalla.style.display = "flex";
}

function ocultarPantallaBloqueo() {
  const pantalla = document.getElementById("pantalla-bloqueo");
  pantalla.style.display = "none";
}

function limpiarError() {
  const error = document.getElementById("pin-error");
  error.textContent = "";
}

function mostrarError(texto) {
  const error = document.getElementById("pin-error");
  error.textContent = texto;
}

function sesionActiva() {
  return sessionStorage.getItem(SESSION_KEY) === "1";
}

function guardarSesion(rol) {
  sessionStorage.setItem(SESSION_KEY, "1");
  sessionStorage.setItem(SESSION_ROL_KEY, rol || "admin");
}

export function getRol() {
  return sessionStorage.getItem(SESSION_ROL_KEY) || "admin";
}

export function cerrarSesion() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(SESSION_ROL_KEY);
  window.location.reload();
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
  const form = document.getElementById("form-pin");
  const input = document.getElementById("pin-input");

  if (sesionActiva()) {
    ocultarPantallaBloqueo();
    return true;
  }

  mostrarPantallaBloqueo();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    limpiarError();

    const pin = String(input.value || "").trim();
    if (pin.length !== 4) {
      mostrarError("Ingresa un PIN de 4 digitos");
      return;
    }

    try {
      const respuesta = await verificarPin(pin);
      if (!respuesta.acceso) {
        mostrarError("PIN incorrecto");
        input.value = "";
        input.focus();
        return;
      }

      guardarSesion(respuesta.rol || "admin");
      ocultarPantallaBloqueo();
      input.value = "";
      showToast("Acceso concedido", "success");
      document.dispatchEvent(new CustomEvent("bodega:unlocked"));
    } catch (error) {
      mostrarError("No fue posible verificar el PIN");
      showToast(error.message, "error");
    }
  });

  return false;
}

export { verificarPin };
