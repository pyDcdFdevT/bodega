import { api, formatDate, formatMoney, showToast } from "./api.js";
import { loadPagosProveedores, initPagosProveedores } from "./pagos_proveedores.js";

const MESES_ES = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
];

function balanceLinea(label, valor) {
  return `<div class="cierre-line"><span>${label}</span><strong>${valor}</strong></div>`;
}

function oroBalanceHtml(oro) {
  const tipos = oro.por_tipo || [];
  if (!tipos.length) {
    return balanceLinea(
      `Oro (${formatMoney(oro.gramos)} g)`,
      formatMoney(oro.valor_reales, "reales")
    );
  }
  const lineas = tipos
    .filter((t) => Number(t.gramos) > 0.0001 || Number(t.valor_reales) > 0)
    .map((t) =>
      balanceLinea(
        `${t.etiqueta || t.tipo} (${formatMoney(t.gramos)} g @ ${formatMoney(t.tasa_reales, "reales")}/g)`,
        formatMoney(t.valor_reales, "reales")
      )
    )
    .join("");
  return (
    lineas +
    balanceLinea(
      `Oro total (${formatMoney(oro.gramos)} g)`,
      formatMoney(oro.valor_reales, "reales")
    )
  );
}

function renderBalance(data) {
  const root = document.getElementById("balance-general-content");
  const badge = document.getElementById("balance-ecuacion-badge");
  if (!root) {
    return;
  }
  if (!data) {
    root.innerHTML = '<p class="muted">No fue posible cargar el balance.</p>';
    if (badge) {
      badge.textContent = "—";
    }
    return;
  }
  const a = data.activos || {};
  const p = data.pasivos || {};
  const pat = data.patrimonio || {};
  const eq = data.ecuacion || {};
  const oro = a.oro || {};

  if (badge) {
    badge.textContent = eq.cuadra ? "Cuadra ✓" : `Dif. ${formatMoney(eq.diferencia, "reales")}`;
    badge.classList.toggle("estado", true);
    badge.classList.toggle("ok", Boolean(eq.cuadra));
    badge.classList.toggle("insuficiente", !eq.cuadra);
  }

  root.innerHTML = `
    <div class="balance-col">
      <h4>Activos</h4>
      ${balanceLinea("Caja", formatMoney(a.caja_reales, "reales"))}
      ${oroBalanceHtml(oro)}
      ${balanceLinea("Inventario (CPP)", formatMoney(a.inventario_reales, "reales"))}
      ${balanceLinea("Gasolina (stock)", formatMoney(a.gasolina_stock_reales ?? 0, "reales"))}
      ${balanceLinea(
        "Activos fijos (valor actual)",
        formatMoney(a.activos_fijos_reales, "reales")
      )}
      ${
        a.activos_fijos_depreciacion_acumulada != null
          ? balanceLinea(
              "Depreciacion acumulada (activos)",
              formatMoney(a.activos_fijos_depreciacion_acumulada, "reales")
            )
          : ""
      }
      ${
        a.activos_fijos_monto_original != null &&
        a.activos_fijos_monto_original !== a.activos_fijos_reales
          ? `<p class="muted small">Costo original activos: ${formatMoney(a.activos_fijos_monto_original, "reales")}</p>`
          : ""
      }
      <div class="cierre-line balance-total"><span>Total activos</span><strong>${formatMoney(a.total, "reales")}</strong></div>
    </div>
    <div class="balance-col">
      <h4>Pasivos</h4>
      ${balanceLinea("Cuentas por pagar (compras a crédito)", formatMoney(p.cuentas_por_pagar, "reales"))}
      <div class="cierre-line balance-total"><span>Total pasivos</span><strong>${formatMoney(p.total, "reales")}</strong></div>
    </div>
    <div class="balance-col">
      <h4>Patrimonio</h4>
      ${balanceLinea("Capital inicial", formatMoney(pat.capital_inicial, "reales"))}
      ${balanceLinea("Ganancia acumulada", formatMoney(pat.ganancia_acumulada, "reales"))}
      <div class="cierre-line balance-total"><span>Total patrimonio</span><strong>${formatMoney(pat.total, "reales")}</strong></div>
    </div>
    <div class="balance-col balance-ecuacion">
      <h4>Ecuación contable</h4>
      ${balanceLinea("Activos", formatMoney(eq.activos, "reales"))}
      ${balanceLinea("Pasivos + Patrimonio", formatMoney(eq.pasivos_mas_patrimonio, "reales"))}
      <p class="muted small">${eq.cuadra ? "La ecuación contable cuadra." : `Diferencia: ${formatMoney(eq.diferencia, "reales")}`}</p>
    </div>
  `;
}

function reporteLinea(label, valor) {
  return `<div class="cierre-line"><span>${label}</span><strong>${valor}</strong></div>`;
}

function erLinea(concepto, monto, indent = false) {
  const cls = indent ? "er-line er-line-indent" : "er-line";
  return `<div class="${cls}"><span>${concepto}</span><strong>${formatMoney(monto, "reales")}</strong></div>`;
}

function erSeccion(titulo, lineas, totalLabel, total, extraHtml = "") {
  const body = lineas.map((l) => erLinea(l.concepto, l.monto, true)).join("");
  const totalRow = totalLabel
    ? `<div class="er-line er-total"><span>${totalLabel}</span><strong>${formatMoney(total, "reales")}</strong></div>`
    : "";
  return `
    <section class="er-block">
      <h4 class="er-titulo">${titulo}</h4>
      ${body}
      ${extraHtml}
      ${totalRow}
    </section>`;
}

function poblarSelectoresEstadoResultados() {
  const selMes = document.getElementById("estado-resultados-mes");
  const selAnio = document.getElementById("estado-resultados-anio");
  if (!selMes || !selAnio) {
    return;
  }
  const ahora = new Date();
  const anioActual = ahora.getFullYear();
  if (!selMes.options.length) {
    selMes.innerHTML = MESES_ES.map((nombre, i) => `<option value="${i + 1}">${nombre}</option>`).join("");
    selMes.value = String(ahora.getMonth() + 1);
  }
  if (!selAnio.options.length) {
    for (let y = anioActual; y >= anioActual - 5; y -= 1) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      selAnio.appendChild(opt);
    }
    selAnio.value = String(anioActual);
  }
}

function renderEstadoResultados(data) {
  const root = document.getElementById("estado-resultados-content");
  if (!root) {
    return;
  }
  if (!data?.ingresos_operacionales) {
    root.innerHTML = '<p class="muted">Sin datos para el periodo.</p>';
    return;
  }
  const ing = data.ingresos_operacionales;
  const cv = data.costo_ventas;
  const go = data.gastos_operativos;
  const utilNeta = Number(data.utilidad_neta ?? 0);

  root.innerHTML = `
    <p class="muted small er-periodo">${data.periodo?.etiqueta || ""}</p>
    <div class="estado-resultados-sheet">
      ${erSeccion(ing.titulo, ing.lineas, "Total ingresos", ing.total)}
      ${erSeccion(
        cv.titulo,
        cv.lineas,
        "Total costo de ventas",
        cv.total,
        `<div class="er-line er-subtotal"><span>Utilidad bruta</span><strong>${formatMoney(cv.utilidad_bruta, "reales")}</strong></div>`
      )}
      ${erSeccion(go.titulo, go.lineas, "Total gastos", go.total)}
      <section class="er-block er-block-neta">
        <div class="er-line er-utilidad-neta">
          <span>UTILIDAD NETA</span>
          <strong>${formatMoney(utilNeta, "reales")}</strong>
        </div>
      </section>
    </div>
  `;
}

export async function loadEstadoResultados() {
  poblarSelectoresEstadoResultados();
  const mes = Number(document.getElementById("estado-resultados-mes")?.value || new Date().getMonth() + 1);
  const anio = Number(document.getElementById("estado-resultados-anio")?.value || new Date().getFullYear());
  const root = document.getElementById("estado-resultados-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando estado de resultados…</p>';
  }
  try {
    const data = await api.get(`/reportes/estado-resultados?mes=${mes}&anio=${anio}`);
    renderEstadoResultados(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar"}</p>`;
    }
    showToast(error.message || "Error al cargar", "error");
  }
}

let estadoResultadosInicializado = false;

function initEstadoResultados() {
  poblarSelectoresEstadoResultados();
  if (estadoResultadosInicializado) {
    return;
  }
  estadoResultadosInicializado = true;
  document.getElementById("btn-estado-resultados")?.addEventListener("click", () => {
    loadEstadoResultados();
  });
}

function renderReportePeriodo(data) {
  const root = document.getElementById("reporte-periodo-content");
  if (!root) {
    return;
  }
  if (!data?.totales) {
    root.innerHTML = '<p class="muted">Sin datos para el periodo seleccionado.</p>';
    return;
  }
  const t = data.totales;
  const b = t.bodega || {};
  const g = t.gasolina || {};
  const co = t.compra_oro || {};
  const oro = t.oro_recolectado_detalle || {};
  const titulo =
    data.periodo === "anual"
      ? `Resumen anual ${data.anio}`
      : `${data.mes_nombre || MESES_ES[(data.mes || 1) - 1]} ${data.anio}`;

  let mesesHtml = "";
  if (data.periodo === "anual" && Array.isArray(data.meses) && data.meses.length) {
    mesesHtml = `
      <div class="table-wrap" style="margin-top:16px;">
        <table>
          <thead>
            <tr>
              <th>Mes</th>
              <th>Días</th>
              <th>Ventas R$</th>
              <th>Compras R$</th>
              <th>Gastos R$</th>
              <th>Oro (g)</th>
              <th>Ganancia R$</th>
            </tr>
          </thead>
          <tbody>
            ${data.meses
              .map(
                (m) => `
              <tr>
                <td>${m.mes_nombre}</td>
                <td>${m.dias_con_cierre}</td>
                <td>${formatMoney(m.ventas_reales, "reales")}</td>
                <td>${formatMoney(m.compras_reales, "reales")}</td>
                <td>${formatMoney(m.gastos_reales, "reales")}</td>
                <td>${formatMoney(m.oro_recolectado)}</td>
                <td>${formatMoney(m.ganancia_neta_reales, "reales")}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  }

  root.innerHTML = `
    <p class="muted small" style="margin:0 0 12px;">${titulo} · ${t.dias_con_cierre} día(s) con cierre registrado</p>
    <div class="dashboard-summary reporte-periodo-kpis">
      <article class="metric-pill dashboard-kpi">
        <span>Ventas (R$)</span>
        <strong>${formatMoney(t.ventas_reales, "reales")}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Compras (R$)</span>
        <strong>${formatMoney(t.compras_reales, "reales")}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Gastos (R$)</span>
        <strong>${formatMoney(t.gastos_reales, "reales")}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Oro recolectado (g)</span>
        <strong>${formatMoney(t.oro_recolectado)}</strong>
      </article>
      <article class="metric-pill dashboard-kpi">
        <span>Ganancia neta (R$)</span>
        <strong>${formatMoney(t.ganancia_neta_reales, "reales")}</strong>
      </article>
    </div>
    <div class="grid two reporte-periodo-detalle">
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Bodega</h4>
        ${reporteLinea("Ventas reales", formatMoney(b.ventas_reales, "reales"))}
        ${reporteLinea("Compras mercancía", formatMoney(b.compras_mercancia_reales, "reales"))}
        ${reporteLinea("Salidas", formatMoney(b.salidas_reales, "reales"))}
      </article>
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Gasolina</h4>
        ${reporteLinea("Ventas reales", formatMoney(g.ventas_reales, "reales"))}
        ${reporteLinea("Reposición", formatMoney(g.reposicion_reales, "reales"))}
      </article>
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Compra de oro</h4>
        ${reporteLinea("Gramos", `${formatMoney(co.gramos)} g`)}
        ${reporteLinea("Reales usados", formatMoney(co.reales_usados, "reales"))}
      </article>
      <article class="card cierre-bloque" style="padding:16px;box-shadow:none;">
        <h4 style="margin:0 0 10px;">Oro recolectado</h4>
        ${reporteLinea("Bruto total", `${formatMoney(oro.bruto_total_gramos)} g`)}
        ${reporteLinea("Araparita", `${formatMoney(oro.araparita)} g`)}
        ${reporteLinea("Uruman", `${formatMoney(oro.uruman)} g`)}
        ${t.ganancia_neta_oro ? reporteLinea("Ganancia neta (oro ref.)", `${formatMoney(t.ganancia_neta_oro)} g equiv.`) : ""}
      </article>
    </div>
    ${mesesHtml}
  `;
}

function poblarSelectoresReporte() {
  const selMes = document.getElementById("reporte-mes");
  const selAnio = document.getElementById("reporte-anio");
  if (!selMes || !selAnio) {
    return;
  }
  const ahora = new Date();
  const anioActual = ahora.getFullYear();
  if (!selMes.options.length) {
    selMes.innerHTML = MESES_ES.map(
      (nombre, i) => `<option value="${i + 1}">${nombre}</option>`
    ).join("");
    selMes.value = String(ahora.getMonth() + 1);
  }
  if (!selAnio.options.length) {
    for (let y = anioActual; y >= anioActual - 5; y -= 1) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      selAnio.appendChild(opt);
    }
    selAnio.value = String(anioActual);
  }
}

function actualizarVisibilidadMes() {
  const tipo = document.getElementById("reporte-periodo-tipo")?.value || "mensual";
  const wrap = document.getElementById("reporte-mes-wrap");
  if (wrap) {
    wrap.style.display = tipo === "anual" ? "none" : "";
  }
}

export async function loadReportePeriodo() {
  poblarSelectoresReporte();
  actualizarVisibilidadMes();
  const tipo = document.getElementById("reporte-periodo-tipo")?.value || "mensual";
  const anio = Number(document.getElementById("reporte-anio")?.value || new Date().getFullYear());
  const root = document.getElementById("reporte-periodo-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando resumen…</p>';
  }
  try {
    let data;
    if (tipo === "anual") {
      data = await api.get(`/reportes/anual?anio=${anio}`);
    } else {
      const mes = Number(document.getElementById("reporte-mes")?.value || new Date().getMonth() + 1);
      data = await api.get(`/reportes/mensual?mes=${mes}&anio=${anio}`);
    }
    renderReportePeriodo(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar el reporte"}</p>`;
    }
    showToast(error.message || "Error al cargar el reporte", "error");
  }
}

let reportePeriodoInicializado = false;

function initReportePeriodo() {
  poblarSelectoresReporte();
  actualizarVisibilidadMes();
  if (reportePeriodoInicializado) {
    return;
  }
  reportePeriodoInicializado = true;
  document.getElementById("reporte-periodo-tipo")?.addEventListener("change", actualizarVisibilidadMes);
  document.getElementById("btn-reporte-periodo")?.addEventListener("click", () => {
    loadReportePeriodo();
  });
}

function renderCuentasPorPagar(data) {
  const root = document.getElementById("cuentas-pagar-content");
  const badge = document.getElementById("cuentas-pagar-total-badge");
  if (!root) {
    return;
  }
  const total = Number(data?.total_pendiente ?? 0);
  if (badge) {
    badge.textContent = `Total: ${formatMoney(total, "reales")}`;
  }
  const compras = data?.compras || [];
  if (!compras.length) {
    root.innerHTML = '<p class="muted">No hay compras a crédito pendientes.</p>';
    return;
  }

  const porProveedor = data?.por_proveedor || [];
  const resumenProveedores =
    porProveedor.length > 1
      ? `
    <div class="cuentas-pagar-resumen">
      ${porProveedor
        .map(
          (p) => `
        <span class="badge">${p.proveedor}: ${formatMoney(p.total_credito, "reales")} (${p.cantidad_compras})</span>`
        )
        .join("")}
    </div>`
      : "";

  root.innerHTML = `
    <p class="report-item" style="margin:0 0 12px;">
      Total pendiente: <strong>${formatMoney(total, "reales")}</strong>
      · ${data.cantidad_compras ?? compras.length} compra(s) a crédito
    </p>
    ${resumenProveedores}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Proveedor</th>
            <th>Total crédito (R$)</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          ${compras
            .map(
              (c) => `
            <tr>
              <td>${c.proveedor || "-"}</td>
              <td>${formatMoney(c.total_reales, "reales")}</td>
              <td>${c.fecha ? formatDate(c.fecha) : "-"}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDepreciacion(data) {
  const root = document.getElementById("depreciacion-content");
  const badge = document.getElementById("depreciacion-valor-badge");
  if (!root) {
    return;
  }
  if (!data) {
    root.innerHTML = '<p class="muted">No fue posible cargar la depreciacion.</p>';
    if (badge) {
      badge.textContent = "—";
    }
    return;
  }
  const tot = data.totales || {};
  const activos = data.activos || [];
  if (badge) {
    badge.textContent = formatMoney(tot.valor_actual, "reales");
  }
  if (!activos.length) {
    root.innerHTML = '<p class="muted">No hay activos fijos registrados.</p>';
    return;
  }
  root.innerHTML = `
    <p class="report-item" style="margin:0 0 12px;">
      Valor actual: <strong>${formatMoney(tot.valor_actual, "reales")}</strong>
      · Dep. acumulada: <strong>${formatMoney(tot.depreciacion_acumulada, "reales")}</strong>
      · Costo original: ${formatMoney(tot.monto_original, "reales")}
      · ${formatMoney(tot.depreciacion_mensual_total, "reales")}/mes
    </p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Activo</th>
            <th>Monto</th>
            <th>Dep./mes</th>
            <th>Dep. acum.</th>
            <th>Valor actual</th>
          </tr>
        </thead>
        <tbody>
          ${activos
            .map(
              (a) => `
            <tr>
              <td>${a.descripcion || "-"}</td>
              <td>${formatMoney(a.monto_reales, "reales")}</td>
              <td>${formatMoney(a.depreciacion_mensual, "reales")}</td>
              <td>${formatMoney(a.depreciacion_acumulada, "reales")}</td>
              <td>${formatMoney(a.valor_actual, "reales")}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function loadDepreciacion() {
  const root = document.getElementById("depreciacion-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando depreciacion…</p>';
  }
  try {
    const data = await api.get("/reportes/depreciacion");
    renderDepreciacion(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar"}</p>`;
    }
  }
}

async function loadCuentasPorPagar() {
  const root = document.getElementById("cuentas-pagar-content");
  if (root) {
    root.innerHTML = '<p class="muted">Cargando cuentas por pagar…</p>';
  }
  try {
    const data = await api.get("/reportes/cuentas-por-pagar");
    renderCuentasPorPagar(data);
  } catch (error) {
    if (root) {
      root.innerHTML = `<p class="muted">${error.message || "Error al cargar"}</p>`;
    }
  }
}

export async function loadContabilidad() {
  const [balance, depreciacion, cuentasPagar] = await Promise.all([
    api.get("/reportes/balance").catch(() => null),
    api.get("/reportes/depreciacion").catch(() => null),
    api.get("/reportes/cuentas-por-pagar").catch(() => null),
  ]);
  renderBalance(balance);
  renderDepreciacion(depreciacion);
  renderCuentasPorPagar(cuentasPagar);
  await loadPagosProveedores();
  initReportePeriodo();
  loadReportePeriodo();
  initEstadoResultados();
  loadEstadoResultados();
}

let contabilidadInicializada = false;

export function initContabilidad() {
  if (contabilidadInicializada) {
    return;
  }
  contabilidadInicializada = true;
  initPagosProveedores();
  initEstadoResultados();
  initReportePeriodo();
}
