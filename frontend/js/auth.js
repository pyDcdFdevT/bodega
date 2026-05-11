import { api, showToast } from "./api.js";

const SESSION_KEY = "bodega_pin_ok";

async function verificarPin(pin) {
  const response = await api.post("/auth/verificar-pin", { pin });
  return Boolean(response.acceso);
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

function guardarSesion() {
  sessionStorage.setItem(SESSION_KEY, "1");
}

export async function initAuth() {
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
      const acceso = await verificarPin(pin);
      if (!acceso) {
        mostrarError("PIN incorrecto");
        input.value = "";
        input.focus();
        return;
      }

      guardarSesion();
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
