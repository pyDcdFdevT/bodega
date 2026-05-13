import { api } from "./api.js";

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
  if (pantalla) {
    pantalla.style.display = "none";
  }
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
  sessionStorage.removeItem("bodega_pin_ok");
  sessionStorage.removeItem("bodega_rol");
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
  ocultarPantallaBloqueo();
  guardarSesion("admin");
  return true;
}

export { verificarPin };
