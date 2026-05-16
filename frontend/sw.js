const CACHE_NAME = "bodega-static-v13";
const ASSETS = [
  "/",
  "/index.html",
  "/css/estilo.css",
  "/js/api.js",
  "/js/activos.js",
  "/js/app.js",
  "/js/auth.js",
  "/js/config.js",
  "/js/cierre.js",
  "/js/compras.js",
  "/js/historial_operaciones.js",
  "/js/compras_oro.js",
  "/js/gasolina.js",
  "/js/gastos.js",
  "/js/pagos_proveedores.js",
  "/js/dashboard.js",
  "/js/contabilidad.js",
  "/js/inventario.js",
  "/js/reportes.js",
  "/js/salidas.js",
  "/js/tasas.js",
  "/js/ventas.js",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(event.request)
        .then((response) => {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
          return response;
        })
        .catch(() => caches.match("/index.html"));
    })
  );
});
