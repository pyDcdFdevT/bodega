import { api, formatDate, formatMoney, renderEmptyRow, showToast } from "./api.js";

const TIPO_DISTRIB_LABEL = {
  reposicion_bodega: "Reposicion bodega",
  reposicion_gasolina: "Reposicion gasolina",
  gastos_operativos: "Gastos operativos",
  pago_socio: "Pago socio",
  ganancia_dueno: "Ganancia dueno",
  se_deja_caja: "Se deja en caja",
};

function adminHeaders() {
  return { headers: { "X-Bodega-Rol": "admin" } };
}

function setSelectOptions(select, items, valueKey, labelFn, emptyLabel) {
  if (!select) {
    return;
  }
  const opts = [`<option value="">${emptyLabel}</option>`]
    .concat(items.map((it) => `<option value="${it[valueKey]}">${labelFn(it)}</option>`))
    .join("");
  select.innerHTML = opts;
}

function renderTablaLotes(lotes) {
  const tbody = document.getElementById("tabla-fund-lotes");
  if (!tbody) {
    return;
  }
  if (!lotes.length) {
    tbody.innerHTML = renderEmptyRow(5, "No hay lotes registrados.");
    return;
  }
  tbody.innerHTML = lotes
    .map(
      (l) => `
    <tr>
      <td>${l.id}</td>
      <td>${formatDate(l.fecha)}</td>
      <td>${Number(l.gramos_brutos).toFixed(4)}</td>
      <td>${l.origen || "—"}</td>
      <td>${l.estado}</td>
    </tr>`
    )
    .join("");
}

function renderTablaFundiciones(fundiciones) {
  const tbody = document.getElementById("tabla-fund-fundiciones");
  if (!tbody) {
    return;
  }
  if (!fundiciones.length) {
    tbody.innerHTML = renderEmptyRow(7, "No hay fundiciones registradas.");
    return;
  }
  tbody.innerHTML = fundiciones
    .map(
      (f) => `
    <tr>
      <td>${f.id}</td>
      <td>${formatDate(f.fecha)}</td>
      <td>#${f.lote_oro_id}</td>
      <td>${Number(f.gramos_brutos).toFixed(4)}</td>
      <td>${Number(f.ley).toFixed(4)}</td>
      <td>${Number(f.gramos_finos).toFixed(4)}</td>
      <td>${f.casa_fundicion || "—"}</td>
    </tr>`
    )
    .join("");
}

function renderTablaVentasPieza(ventas) {
  const tbody = document.getElementById("tabla-fund-ventas-pieza");
  if (!tbody) {
    return;
  }
  if (!ventas.length) {
    tbody.innerHTML = renderEmptyRow(8, "No hay ventas de pieza registradas.");
    return;
  }
  tbody.innerHTML = ventas
    .map((v) => {
      const mon = v.moneda === "USD" ? "USD" : "reales";
      return `
    <tr>
      <td>${v.id}</td>
      <td>${formatDate(v.fecha)}</td>
      <td>#${v.fundicion_id}</td>
      <td>${Number(v.gramos_vendidos).toFixed(4)}</td>
      <td>${Number(v.tasa_venta).toFixed(2)}</td>
      <td>${formatMoney(v.monto_total, mon)}</td>
      <td>${v.moneda}</td>
      <td>${v.comprador || "—"}</td>
    </tr>`;
    })
    .join("");
}

function renderTablaDistribuciones(distribuciones) {
  const tbody = document.getElementById("tabla-fund-distribuciones");
  if (!tbody) {
    return;
  }
  if (!distribuciones.length) {
    tbody.innerHTML = renderEmptyRow(5, "No hay distribuciones registradas.");
    return;
  }
  tbody.innerHTML = distribuciones
    .map(
      (d) => `
    <tr>
      <td>${d.id}</td>
      <td>${formatDate(d.fecha)}</td>
      <td>#${d.venta_pieza_id}</td>
      <td>${TIPO_DISTRIB_LABEL[d.tipo] || d.tipo}</td>
      <td>${formatMoney(d.monto, "reales")}</td>
    </tr>`
    )
    .join("");
}

function actualizarTotalVentaPieza() {
  const g = Number(document.getElementById("fund-vp-gramos")?.value || 0);
  const t = Number(document.getElementById("fund-vp-tasa")?.value || 0);
  const el = document.getElementById("fund-vp-total");
  if (el) {
    el.textContent = formatMoney(g * t, "reales");
  }
}

function actualizarDistribResto() {
  const total = Number(document.getElementById("fund-dist-total-num")?.value || 0);
  const b = Number(document.getElementById("fund-dist-bodega")?.value || 0);
  const gas = Number(document.getElementById("fund-dist-gasolina")?.value || 0);
  const gast = Number(document.getElementById("fund-dist-gastos")?.value || 0);
  const soc = Number(document.getElementById("fund-dist-socio")?.value || 0);
  const due = Number(document.getElementById("fund-dist-dueno")?.value || 0);
  const caja = Number(document.getElementById("fund-dist-caja")?.value || 0);
  const suma = b + gas + gast + soc + due + caja;
  const resto = Number((total - suma).toFixed(2));
  const el = document.getElementById("fund-dist-resto");
  if (el) {
    el.textContent = formatMoney(resto, "reales");
    el.classList.toggle("insuficiente", Math.abs(resto) > 0.02);
  }
}

export async function loadFundicion() {
  try {
    const [sug, lotes, fundiciones, dispVenta, ventas, sinDist, distribuciones] = await Promise.all([
      api.get("/fundicion/sugerencia-oro-bruto"),
      api.get("/fundicion/lotes"),
      api.get("/fundicion/fundiciones"),
      api.get("/fundicion/fundiciones/disponibles-venta"),
      api.get("/fundicion/ventas-pieza"),
      api.get("/fundicion/ventas-pieza/sin-distribuir"),
      api.get("/fundicion/distribuciones"),
    ]);

    renderTablaLotes(lotes);
    renderTablaFundiciones(fundiciones);
    renderTablaVentasPieza(ventas);
    renderTablaDistribuciones(distribuciones);

    const br = document.getElementById("fund-lote-brutos");
    if (br && sug?.gramos_brutos_sugeridos != null) {
      br.placeholder = String(sug.gramos_brutos_sugeridos);
      if (!br.value) {
        br.value = String(sug.gramos_brutos_sugeridos);
      }
    }

    const lotesAbiertos = lotes.filter((l) => l.estado !== "FUNDIDO" && l.estado !== "VENDIDO" && l.estado !== "CERRADO");
    setSelectOptions(
      document.getElementById("fund-sel-lote"),
      lotesAbiertos,
      "id",
      (l) => `#${l.id} ${l.estado} ${Number(l.gramos_brutos).toFixed(4)}g`,
      "Seleccione lote..."
    );

    setSelectOptions(
      document.getElementById("fund-sel-fundicion"),
      dispVenta,
      "id",
      (f) => `#${f.id} ${Number(f.gramos_finos).toFixed(4)}g finos`,
      "Seleccione fundicion..."
    );

    setSelectOptions(
      document.getElementById("fund-dist-sel-venta"),
      sinDist,
      "id",
      (v) => `#${v.id} ${formatMoney(v.monto_total, "reales")} (${v.moneda})`,
      "Seleccione venta..."
    );

    const fl = document.getElementById("fund-sel-lote");
    if (fl?.value) {
      const sel = lotes.find((x) => String(x.id) === fl.value);
      const gb = document.getElementById("fund-fund-brutos");
      if (gb && sel) {
        gb.value = String(sel.gramos_brutos);
      }
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

export function initFundicion() {
  document.getElementById("btn-fund-refresh")?.addEventListener("click", () => loadFundicion());

  document.getElementById("btn-fund-lote-registrar")?.addEventListener("click", async () => {
    const gramos = Number(document.getElementById("fund-lote-brutos")?.value || 0);
    const origen = document.getElementById("fund-lote-origen")?.value || "";
    const estado = document.getElementById("fund-lote-estado")?.value || "ACUMULANDO";
    try {
      await api.post("/fundicion/lotes", { gramos_brutos: gramos, origen, estado }, adminHeaders());
      showToast("Lote registrado", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  document.getElementById("fund-sel-lote")?.addEventListener("change", async () => {
    const id = document.getElementById("fund-sel-lote")?.value;
    const lotes = await api.get("/fundicion/lotes");
    const sel = lotes.find((x) => String(x.id) === id);
    const gb = document.getElementById("fund-fund-brutos");
    if (gb && sel) {
      gb.value = String(sel.gramos_brutos);
    }
  });

  document.getElementById("btn-fund-registrar")?.addEventListener("click", async () => {
    const loteId = Number(document.getElementById("fund-sel-lote")?.value || 0);
    const gramos_brutos = Number(document.getElementById("fund-fund-brutos")?.value || 0);
    const ley = Number(document.getElementById("fund-fund-ley")?.value || 0);
    const gramos_finos = Number(document.getElementById("fund-fund-finos")?.value || 0);
    const casa = document.getElementById("fund-fund-casa")?.value || "";
    try {
      await api.post(
        "/fundicion/fundiciones",
        { lote_oro_id: loteId, gramos_brutos, ley, gramos_finos, casa_fundicion: casa },
        adminHeaders()
      );
      showToast("Fundicion registrada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  document.getElementById("fund-sel-fundicion")?.addEventListener("change", async () => {
    const id = document.getElementById("fund-sel-fundicion")?.value;
    const rows = await api.get("/fundicion/fundiciones/disponibles-venta");
    const sel = rows.find((x) => String(x.id) === id);
    const el = document.getElementById("fund-vp-finos-disp");
    if (el && sel) {
      el.textContent = `${Number(sel.gramos_finos).toFixed(4)} g`;
    }
  });

  ["fund-vp-gramos", "fund-vp-tasa"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", actualizarTotalVentaPieza);
  });

  document.getElementById("btn-fund-vp-registrar")?.addEventListener("click", async () => {
    const fundicion_id = Number(document.getElementById("fund-sel-fundicion")?.value || 0);
    const gramos_vendidos = Number(document.getElementById("fund-vp-gramos")?.value || 0);
    const tasa_venta = Number(document.getElementById("fund-vp-tasa")?.value || 0);
    const moneda = document.getElementById("fund-vp-moneda")?.value || "reales";
    const comprador = document.getElementById("fund-vp-comprador")?.value || "";
    const monto_total = gramos_vendidos * tasa_venta;
    try {
      await api.post(
        "/fundicion/ventas-pieza",
        { fundicion_id, gramos_vendidos, tasa_venta, monto_total, moneda, comprador },
        adminHeaders()
      );
      showToast("Venta de pieza registrada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (e) {
      showToast(e.message, "error");
    }
  });

  document.getElementById("fund-dist-sel-venta")?.addEventListener("change", async () => {
    const vid = document.getElementById("fund-dist-sel-venta")?.value;
    const rows = await api.get("/fundicion/ventas-pieza/sin-distribuir");
    const sel = rows.find((x) => String(x.id) === vid);
    const el = document.getElementById("fund-dist-total");
    const hnum = document.getElementById("fund-dist-total-num");
    if (el && sel) {
      el.textContent = formatMoney(sel.monto_total, "reales");
    }
    if (hnum && sel) {
      hnum.value = String(sel.monto_total);
    }
    actualizarDistribResto();
  });

  [
    "fund-dist-bodega",
    "fund-dist-gasolina",
    "fund-dist-gastos",
    "fund-dist-socio",
    "fund-dist-dueno",
    "fund-dist-caja",
  ].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", actualizarDistribResto);
  });

  document.getElementById("btn-fund-dist-registrar")?.addEventListener("click", async () => {
    const venta_pieza_id = Number(document.getElementById("fund-dist-sel-venta")?.value || 0);
    const lineas = [
      { tipo: "reposicion_bodega", monto: Number(document.getElementById("fund-dist-bodega")?.value || 0) },
      { tipo: "reposicion_gasolina", monto: Number(document.getElementById("fund-dist-gasolina")?.value || 0) },
      { tipo: "gastos_operativos", monto: Number(document.getElementById("fund-dist-gastos")?.value || 0) },
      { tipo: "pago_socio", monto: Number(document.getElementById("fund-dist-socio")?.value || 0) },
      { tipo: "ganancia_dueno", monto: Number(document.getElementById("fund-dist-dueno")?.value || 0) },
      { tipo: "se_deja_caja", monto: Number(document.getElementById("fund-dist-caja")?.value || 0) },
    ];
    try {
      await api.post("/fundicion/distribuciones", { venta_pieza_id, lineas }, adminHeaders());
      showToast("Distribucion registrada", "success");
      document.dispatchEvent(new CustomEvent("bodega:refresh"));
    } catch (e) {
      showToast(e.message, "error");
    }
  });
}
