import { showToast } from "./api.js";
import { initCompras, loadCompras } from "./compras.js";
import { initComprasOro, loadComprasOro } from "./compras_oro.js";
import { initGasolina, loadGasolina } from "./gasolina.js";
import { initInventario, loadInventario, loadProductoOptions } from "./inventario.js";
import { loadReportes } from "./reportes.js";
import { initTasas, loadTasas } from "./tasas.js";
import { initVentas, loadVentas } from "./ventas.js";

function initTabs() {
  const tabs = [...document.querySelectorAll(".tab")];
  const panels = [...document.querySelectorAll(".panel")];

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((item) => item.classList.remove("active"));
      panels.forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.target).classList.add("active");
    });
  });
}

async function refreshAll() {
  try {
    await Promise.all([loadInventario(), loadTasas()]);
    await loadProductoOptions(["venta-producto", "compra-producto"]);
    await Promise.all([loadVentas(), loadCompras(), loadGasolina(), loadComprasOro(), loadReportes()]);
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

function init() {
  initTabs();
  initInventario();
  initVentas();
  initCompras();
  initGasolina();
  initComprasOro();
  initTasas();
  registerServiceWorker();
  document.addEventListener("bodega:refresh", refreshAll);
  refreshAll();
}

document.addEventListener("DOMContentLoaded", init);
