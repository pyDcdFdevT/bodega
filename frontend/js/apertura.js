import { api, showToast } from "./api.js";

let lastPayload = null;

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
    lastPayload = await api.get("/cierre/apertura");
    const ap = lastPayload;
    const cajaIn = document.getElementById("apertura-caja");
    const oroIn = document.getElementById("apertura-oro");

    if (ap.apertura_hoy) {
      const a = ap.apertura_hoy;
      setEstado(`Apertura de hoy ya registrada (${a.abierto_por || "—"}). No se puede registrar otra.`);
      if (cajaIn) {
        cajaIn.value = String(Number(a.caja_inicial_reales ?? 0).toFixed(2));
      }
      if (oroIn) {
        oroIn.value = String(Number(a.oro_operativo_inicial ?? 0).toFixed(4));
      }
      setCamposBloqueados(true);
      return;
    }

    const sug = ap.sugerencia;
    if (sug) {
      setEstado("Sugerencia desde el cierre de ayer (se deja en caja / oro). Ajuste si hace falta y registre.");
      if (cajaIn) {
        cajaIn.value = String(Number(sug.caja_inicial_reales ?? 0).toFixed(2));
      }
      if (oroIn) {
        oroIn.value = String(Number(sug.oro_operativo_inicial ?? 0).toFixed(4));
      }
    } else {
      setEstado("No hay cierre de ayer: indique caja y oro operativo inicial (0 por defecto).");
      if (cajaIn) {
        cajaIn.value = "0";
      }
      if (oroIn) {
        oroIn.value = "0";
      }
    }
    setCamposBloqueados(false);
  } catch (e) {
    showToast(e.message, "error");
  }
}

export function initApertura() {
  document.getElementById("btn-apertura-actualizar")?.addEventListener("click", () => {
    loadApertura();
  });
  document.getElementById("btn-apertura-registrar")?.addEventListener("click", async () => {
    if (lastPayload?.apertura_hoy) {
      showToast("La apertura de hoy ya fue registrada", "error");
      return;
    }
    const caja = Number(document.getElementById("apertura-caja")?.value || 0);
    const oro = Number(document.getElementById("apertura-oro")?.value || 0);
    try {
      await api.post(
        "/apertura/",
        { caja_inicial_reales: caja, oro_operativo_inicial: oro, abierto_por: "Admin" },
        { headers: { "X-Bodega-Rol": "admin" } }
      );
      showToast("Apertura registrada", "success");
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
