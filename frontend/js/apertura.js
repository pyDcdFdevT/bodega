import { api, showToast } from "./api.js";

let lastPayload = null;
let inputsPrimed = false;

function setEstado(text) {
  const el = document.getElementById("apertura-estado");
  if (el) {
    el.textContent = text;
  }
}

function setCamposBloqueados(bloquear) {
  document.getElementById("apertura-caja")?.toggleAttribute("disabled", bloquear);
  document.getElementById("apertura-oro")?.toggleAttribute("disabled", bloquear);
  document.getElementById("btn-apertura-registrar")?.toggleAttribute("disabled", bloquear);
}

export async function loadApertura() {
  try {
    lastPayload = await api.get("/apertura/");
    const ap = lastPayload;
    const cajaIn = document.getElementById("apertura-caja");
    const oroIn = document.getElementById("apertura-oro");
    if (ap.apertura_hoy) {
      setEstado(`Apertura registrada (${ap.apertura_hoy.abierto_por}).`);
      if (cajaIn) {
        cajaIn.value = String(ap.apertura_hoy.caja_inicial_reales);
      }
      if (oroIn) {
        oroIn.value = String(ap.apertura_hoy.oro_operativo_inicial);
      }
      inputsPrimed = true;
      setCamposBloqueados(true);
    } else {
      setEstado("Sugerencia desde el cierre de ayer (se deja en caja). Registre la apertura para operar el dia.");
      if (cajaIn && oroIn && !inputsPrimed) {
        cajaIn.value = String(ap.sugerencia?.caja_inicial_reales ?? 0);
        oroIn.value = String(ap.sugerencia?.oro_operativo_inicial ?? 0);
        inputsPrimed = true;
      }
      setCamposBloqueados(false);
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

export function initApertura() {
  document.getElementById("btn-apertura-actualizar")?.addEventListener("click", () => {
    inputsPrimed = false;
    loadApertura();
  });
  document.getElementById("btn-apertura-registrar")?.addEventListener("click", async () => {
    const caja = Number(document.getElementById("apertura-caja")?.value || 0);
    const oro = Number(document.getElementById("apertura-oro")?.value || 0);
    try {
      await api.post(
        "/apertura/",
        { caja_inicial_reales: caja, oro_operativo_inicial: oro, abierto_por: "Admin" },
        { headers: { "X-Bodega-Rol": "admin" } }
      );
      showToast("Apertura registrada", "success");
      inputsPrimed = true;
      await loadApertura();
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (error) {
      const msg = String(error.message || "");
      if (msg.includes("ya fue registrada")) {
        showToast("La apertura de hoy ya fue registrada", "error");
      } else {
        showToast(msg, "error");
      }
    }
  });
}
