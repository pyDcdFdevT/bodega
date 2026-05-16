import { showToast } from "./api.js";
import { getRol, initAuth } from "./auth.js";
import { initConfig } from "./config.js";

const CACHE_TTL_MS = 5 * 60 * 1000;

export const dataCache = {
  productos: null,
  stockBajo: null,
  tasas: null,
  lastFetch: {},
};

export function getCachedProductos() {
  const ts = dataCache.lastFetch.productos;
  if (dataCache.productos == null || ts == null || Date.now() - ts > CACHE_TTL_MS) {
    return null;
  }
  return dataCache.productos;
}

export function getCachedTasas() {
  const ts = dataCache.lastFetch.tasas;
  if (dataCache.tasas == null || ts == null || Date.now() - ts > CACHE_TTL_MS) {
    return null;
  }
  return dataCache.tasas;
}

export function invalidateCache(tipo) {
  if (tipo === "productos") {
    dataCache.productos = null;
    dataCache.stockBajo = null;
    delete dataCache.lastFetch.productos;
  } else if (tipo === "tasas") {
    dataCache.tasas = null;
    delete dataCache.lastFetch.tasas;
  }
}
import { initApertura, loadApertura } from "./apertura.js";
import { initActivos, loadActivos } from "./activos.js";
import { initCierre, loadCierre } from "./cierre.js";
import { initCobros, loadCobros } from "./cobros.js";
import { initCompras, loadCompras } from "./compras.js";
import { initComprasOro, loadComprasOro } from "./compras_oro.js";
import { initEstadoResultados, loadDashboard } from "./dashboard.js";
import { initPagosProveedores } from "./pagos_proveedores.js";
import { initFundicion, loadFundicion } from "./fundicion.js";
import { initGasolina, loadGasolina } from "./gasolina.js";
import { initGastos, loadGastos } from "./gastos.js";
import { initInventario, loadInventario, loadProductoOptions } from "./inventario.js";
import { initSalidas, loadSalidas } from "./salidas.js";
import { initTasas, loadTasas } from "./tasas.js";
import { initVentas, loadVentas } from "./ventas.js";

function updateHeroStatsVisibility(panelId) {
  const wrap = document.getElementById("hero-stats-wrap");
  if (!wrap) {
    return;
  }
  wrap.style.display = panelId === "panel-inventario" ? "" : "none";
}

function updateHeroForActivePanel() {
  const active = document.querySelector(".panel.active");
  updateHeroStatsVisibility(active?.id || "");
}

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
      const target = document.getElementById(tab.dataset.target);
      target?.classList.add("active");
      updateHeroStatsVisibility(target?.id || "");
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
  updateHeroForActivePanel();
}

async function refreshAll() {
  try {
    const rol = getRol();
    await Promise.all([loadInventario(), loadTasas()]);
    await loadProductoOptions(["compra-producto", "salida-producto"]);

    if (rol === "vendedor") {
      await Promise.all([
        loadVentas(),
        loadSalidas(),
        loadGasolina(),
        loadComprasOro(),
        loadCobros(),
      ]);
      return;
    }

    await Promise.all([
      loadApertura(),
      loadVentas(),
      loadCompras(),
      loadSalidas(),
      loadGasolina(),
      loadComprasOro(),
      loadDashboard(),
      loadGastos(),
      loadCierre(),
      loadFundicion(),
      loadCobros(),
      loadActivos(),
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
  initConfig();
  initTabs();
  initApertura();
  initInventario();
  initVentas();
  initCompras();
  initSalidas();
  initGasolina();
  initComprasOro();
  initTasas();
  initGastos();
  initCierre();
  initCobros();
  initFundicion();
  initActivos();
  initPagosProveedores();
  initEstadoResultados();
  registerServiceWorker();
  document.addEventListener("bodega:refresh", () => {
    invalidateCache("productos");
    invalidateCache("tasas");
    refreshAll();
  });
  document.addEventListener("bodega:unlocked", () => {
    aplicarVistaRol();
    refreshAll();
  });
  const autenticado = await initAuth();
  aplicarVistaRol();
  if (autenticado) {
    refreshAll();
  }
}

document.addEventListener("DOMContentLoaded", init);
