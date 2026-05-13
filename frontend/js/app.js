import { showToast } from "./api.js";
import { getRol, initAuth } from "./auth.js";
import { initCompras, loadCompras } from "./compras.js";
import { initComprasOro, loadComprasOro } from "./compras_oro.js";
import { initGasolina, loadGasolina } from "./gasolina.js";
import { initInventario, loadInventario, loadProductoOptions } from "./inventario.js";
import { loadReportes } from "./reportes.js";
import { initSalidas, loadSalidas } from "./salidas.js";
import { initTasas, loadTasas } from "./tasas.js";
import { initVentas, loadVentas } from "./ventas.js";

function initTabs() {
  const tabs = [...document.querySelectorAll(".tab")];
  const panels = [...document.querySelectorAll(".panel")];
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      if (tab.style.display === "none") {
        return;
      }
      tabs.forEach((item) => item.classList.remove("active"));
      panels.forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.target).classList.add("active");
    });
  });
}

function aplicarVistaRol() {
  const esVendedor = getRol() === "vendedor";
  document.querySelectorAll(".solo-admin").forEach((el) => {
    el.style.display = esVendedor ? "none" : "";
  });
  if (esVendedor) {
    const activeTab = document.querySelector(".tab.active");
    const activePanel = document.querySelector(".panel.active");
    if (activeTab?.classList.contains("solo-admin") || activePanel?.classList.contains("solo-admin")) {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      const ventasTab = document.querySelector('.tab[data-target="panel-ventas"]');
      ventasTab?.classList.add("active");
      document.getElementById("panel-ventas")?.classList.add("active");
    }
  }
}

async function refreshAll() {
  try {
    await Promise.all([loadInventario(), loadTasas()]);
    await loadProductoOptions(["venta-producto", "compra-producto", "salida-producto"]);
    await Promise.all([
      loadVentas(), loadCompras(), loadSalidas(), loadGasolina(),
      loadComprasOro(), loadReportes(),
    ]);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      showToast("No fue posible registrar el modo offline", "error");
    });
  }
}

async function init() {
  initTabs();
  initInventario();
  initVentas();
  initCompras();
  initSalidas();
  initGasolina();
  initComprasOro();
  initTasas();
  registerServiceWorker();
  document.addEventListener("bodega:refresh", refreshAll);
  document.addEventListener("bodega:unlocked", () => {
    aplicarVistaRol();
    refreshAll();
  });
  const autenticado = await initAuth();
  aplicarVistaRol();
  if (autenticado) refreshAll();
}

document.addEventListener("DOMContentLoaded", init);
