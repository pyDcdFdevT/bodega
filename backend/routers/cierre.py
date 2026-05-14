from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    AperturaCaja,
    CierreDiario,
    Compra,
    CompraOro,
    GastoOperativo,
    GasolinaReposicion,
    Salida,
    Venta,
    VentaGasolina,
)
from routers.deps import require_admin
from schemas import AperturaCajaCreate, CierreGenerarCreate
from services.calculos import CalculosMonetarios


router = APIRouter(prefix="/cierre", tags=["Cierre"])


def _ganancia_neta_dia(db: Session, inicio: datetime) -> float:
    """Misma formula que el dashboard de reportes para el dia `inicio`."""
    ventas_hoy_oro = float(
        db.query(func.coalesce(func.sum(Venta.total_oro), 0)).filter(Venta.fecha >= inicio).scalar() or 0
    )
    compras_hoy_oro = float(
        db.query(func.coalesce(func.sum(Compra.total_oro), 0)).filter(Compra.fecha >= inicio).scalar() or 0
    )
    salidas_hoy_oro = float(
        db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio).scalar() or 0
    )
    gasolina_hoy_oro = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gastos_hoy_reales = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio)
        .scalar()
        or 0
    )
    tasa_ref = CalculosMonetarios.obtener_tasa_referencia(db)
    gastos_hoy_oro = (
        float(CalculosMonetarios.reales_a_oro(gastos_hoy_reales, db, tasa=tasa_ref)) if gastos_hoy_reales > 0 else 0.0
    )
    return round(ventas_hoy_oro - compras_hoy_oro - salidas_hoy_oro + gasolina_hoy_oro - gastos_hoy_oro, 2)


def construir_payload_cierre(
    db: Session,
    inicio: datetime,
    saldo_inicial_reales: float,
    oro_operativo_inicial: float = 0.0,
) -> dict:
    ventas_reales = float(
        db.query(func.coalesce(func.sum(Venta.total_reales), 0)).filter(Venta.fecha >= inicio).scalar() or 0
    )
    ventas_oro = float(
        db.query(func.coalesce(func.sum(Venta.total_oro), 0)).filter(Venta.fecha >= inicio).scalar() or 0
    )
    oro_araparita = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "araparita")
        .scalar()
        or 0
    )
    oro_uruman = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "uruman")
        .scalar()
        or 0
    )
    oro_se_min = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "santa_elena_minero")
        .scalar()
        or 0
    )
    oro_se_fun = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "santa_elena_fundido")
        .scalar()
        or 0
    )

    compras_reales = float(
        db.query(func.coalesce(func.sum(Compra.total_reales), 0)).filter(Compra.fecha >= inicio).scalar() or 0
    )
    compras_oro = float(
        db.query(func.coalesce(func.sum(Compra.total_oro), 0)).filter(Compra.fecha >= inicio).scalar() or 0
    )
    salidas_oro = float(
        db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio).scalar() or 0
    )

    gas_ventas_reales = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_reales), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gas_ventas_oro = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gas_repo_reales = float(
        db.query(func.coalesce(func.sum(GasolinaReposicion.total_reales), 0))
        .filter(GasolinaReposicion.fecha >= inicio)
        .scalar()
        or 0
    )

    co_gramos = float(
        db.query(func.coalesce(func.sum(CompraOro.gramos), 0)).filter(CompraOro.fecha >= inicio).scalar() or 0
    )
    co_reales = float(
        db.query(func.coalesce(func.sum(CompraOro.total_reales), 0)).filter(CompraOro.fecha >= inicio).scalar() or 0
    )

    gastos_total = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio)
        .scalar()
        or 0
    )

    oro_recolectado_bruto = oro_araparita + oro_uruman + oro_se_min + oro_se_fun
    ingresos_reales = ventas_reales + gas_ventas_reales
    egresos_reales = compras_reales + co_reales + gas_repo_reales + gastos_total
    saldo_final = round(saldo_inicial_reales + ingresos_reales - egresos_reales, 2)

    oro_recolectado_bruto_r = round(oro_recolectado_bruto, 2)
    co_gramos_r = round(co_gramos, 2)
    bruto_total_gramos = round(oro_recolectado_bruto + co_gramos, 2)
    salidas_oro_r = round(salidas_oro, 2)
    oro_ini = float(oro_operativo_inicial or 0)
    oro_esperado = round(oro_ini + bruto_total_gramos - salidas_oro_r, 2)

    oro_block = {
        "araparita": round(oro_araparita, 2),
        "uruman": round(oro_uruman, 2),
        "santa_elena_minero": round(oro_se_min, 2),
        "santa_elena_fundido": round(oro_se_fun, 2),
        "comprado_gramos": co_gramos_r,
        "bruto_total_gramos": bruto_total_gramos,
    }

    ventas_reales_tot = round(ventas_reales + gas_ventas_reales, 2)
    ventas_oro_tot = round(ventas_oro + gas_ventas_oro, 2)
    compras_reales_tot = round(compras_reales + co_reales + gas_repo_reales, 2)

    return {
        "fecha": inicio.date().isoformat(),
        "bodega": {
            "ventas_reales": round(ventas_reales, 2),
            "ventas_oro": round(ventas_oro, 2),
            "compras_mercancia_reales": round(compras_reales, 2),
            "compras_mercancia_oro": round(compras_oro, 2),
            "salidas_oro": salidas_oro_r,
        },
        "gasolina": {
            "ventas_reales": round(gas_ventas_reales, 2),
            "ventas_oro": round(gas_ventas_oro, 2),
            "reposicion_reales": round(gas_repo_reales, 2),
        },
        "compra_oro": {
            "gramos": co_gramos_r,
            "reales_usados": round(co_reales, 2),
        },
        "gastos": {
            "total_reales": round(gastos_total, 2),
        },
        "oro_recolectado": oro_block,
        "caja": {
            "saldo_inicial_reales": round(saldo_inicial_reales, 2),
            "oro_operativo_inicial": round(oro_ini, 2),
            "ingresos_reales": round(ingresos_reales, 2),
            "egresos_reales": round(egresos_reales, 2),
            "saldo_final_reales": saldo_final,
        },
        "fundicion": {
            "nota": "Ley y fino son valores manuales en pantalla",
            "bruto_gramos": oro_recolectado_bruto_r,
        },
        "venta_pieza": {
            "nota": "Fino manual x tasa en frontend",
        },
        "conciliacion": {
            "reales_esperados": saldo_final,
            "oro_esperado": oro_esperado,
        },
        "totales_dia": {
            "ventas_reales": ventas_reales_tot,
            "ventas_oro": ventas_oro_tot,
            "compras_reales": compras_reales_tot,
            "gastos_reales": round(gastos_total, 2),
            "oro_recolectado_gramos": bruto_total_gramos,
        },
        "ganancia_neta_dia": _ganancia_neta_dia(db, inicio),
    }


def _fecha_operativa_hoy() -> date:
    return datetime.now(UTC).replace(tzinfo=None).date()


def _inicio_dia_hoy() -> datetime:
    d = datetime.now(UTC).replace(tzinfo=None)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/apertura")
def obtener_apertura_y_sugerencia(db: Session = Depends(get_db)):
    """Sugerencia desde el cierre de ayer (se_deja_*); apertura de hoy si existe."""
    hoy = _fecha_operativa_hoy()
    ayer = hoy - timedelta(days=1)
    cierre_ayer = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == ayer).first()
    sug_reales = float(cierre_ayer.se_deja_reales) if cierre_ayer else 0.0
    sug_oro = float(cierre_ayer.se_deja_oro) if cierre_ayer else 0.0
    apertura_hoy = db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first()
    out_ap = None
    if apertura_hoy:
        out_ap = {
            "id": apertura_hoy.id,
            "fecha_operativa": apertura_hoy.fecha_operativa.isoformat(),
            "caja_inicial_reales": float(apertura_hoy.caja_inicial_reales),
            "oro_operativo_inicial": float(apertura_hoy.oro_operativo_inicial),
            "abierto_por": apertura_hoy.abierto_por,
            "created_at": apertura_hoy.created_at.isoformat() if apertura_hoy.created_at else None,
        }
    return {
        "fecha_operativa": hoy.isoformat(),
        "sugerencia": {
            "caja_inicial_reales": round(sug_reales, 2),
            "oro_operativo_inicial": round(sug_oro, 2),
        },
        "apertura_hoy": out_ap,
    }


@router.post("/apertura")
def registrar_apertura(
    payload: AperturaCajaCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hoy = _fecha_operativa_hoy()
    if db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first():
        raise HTTPException(status_code=400, detail="La apertura de hoy ya fue registrada")
    row = AperturaCaja(
        fecha_operativa=hoy,
        caja_inicial_reales=float(payload.caja_inicial_reales),
        oro_operativo_inicial=float(payload.oro_operativo_inicial),
        abierto_por=payload.abierto_por.strip()[:100],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "status": "success",
        "apertura": {
            "id": row.id,
            "fecha_operativa": row.fecha_operativa.isoformat(),
            "caja_inicial_reales": float(row.caja_inicial_reales),
            "oro_operativo_inicial": float(row.oro_operativo_inicial),
            "abierto_por": row.abierto_por,
        },
    }


@router.get("/dia")
def cierre_del_dia(
    caja_inicial_reales: float | None = Query(default=None, ge=0),
    oro_operativo_inicial: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    """Resumen del dia. Si hay apertura registrada, usa esos saldos; si no, usa query opcional para vista previa."""
    inicio = _inicio_dia_hoy()
    fe = inicio.date()
    apertura = db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == fe).first()
    if apertura:
        caja_ini = float(apertura.caja_inicial_reales)
        oro_ini = float(apertura.oro_operativo_inicial)
    else:
        caja_ini = float(caja_inicial_reales) if caja_inicial_reales is not None else 0.0
        oro_ini = float(oro_operativo_inicial) if oro_operativo_inicial is not None else 0.0

    data = construir_payload_cierre(db, inicio, caja_ini, oro_ini)
    cierre_hoy = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == fe).first()
    snap = None
    if cierre_hoy:
        snap = {
            "id": cierre_hoy.id,
            "fecha_operativa": cierre_hoy.fecha_operativa.isoformat(),
            "ventas_reales": float(cierre_hoy.ventas_reales),
            "ventas_oro": float(cierre_hoy.ventas_oro),
            "compras_reales": float(cierre_hoy.compras_reales),
            "gastos_reales": float(cierre_hoy.gastos_reales),
            "oro_recolectado": float(cierre_hoy.oro_recolectado),
            "reales_esperados": float(cierre_hoy.reales_esperados),
            "oro_esperado": float(cierre_hoy.oro_esperado),
            "reales_contados": float(cierre_hoy.reales_contados),
            "oro_contado": float(cierre_hoy.oro_contado),
            "diferencia_reales": float(cierre_hoy.diferencia_reales),
            "diferencia_oro": float(cierre_hoy.diferencia_oro),
            "justificacion": cierre_hoy.justificacion or "",
            "retiro_dueno_reales": float(cierre_hoy.retiro_dueno_reales),
            "retiro_dueno_oro": float(cierre_hoy.retiro_dueno_oro),
            "se_deja_reales": float(cierre_hoy.se_deja_reales),
            "se_deja_oro": float(cierre_hoy.se_deja_oro),
            "cerrado_por": cierre_hoy.cerrado_por,
            "created_at": cierre_hoy.created_at.isoformat() if cierre_hoy.created_at else None,
            "detalle": json.loads(cierre_hoy.snapshot_json) if cierre_hoy.snapshot_json else None,
        }
    data["cierre_guardado"] = snap
    return data


@router.post("/generar")
def generar_cierre_diario(
    payload: CierreGenerarCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Cierre con conciliacion. Requiere apertura del dia y cabecera X-Bodega-Rol: admin."""
    inicio = _inicio_dia_hoy()
    fe = inicio.date()
    if db.query(CierreDiario).filter(CierreDiario.fecha_operativa == fe).first():
        raise HTTPException(status_code=400, detail="El cierre de hoy ya fue generado")

    apertura = db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == fe).first()
    if not apertura:
        raise HTTPException(status_code=400, detail="Registre la apertura del dia antes de generar el cierre")

    caja_ini = float(apertura.caja_inicial_reales)
    oro_ini = float(apertura.oro_operativo_inicial)

    data = construir_payload_cierre(db, inicio, caja_ini, oro_ini)
    conc = data["conciliacion"]
    reales_esperados = float(conc["reales_esperados"])
    oro_esperado = float(conc["oro_esperado"])
    reales_contados = round(float(payload.reales_contados), 2)
    oro_contado = round(float(payload.oro_contado), 2)
    diff_r = round(reales_contados - reales_esperados, 2)
    diff_o = round(oro_contado - oro_esperado, 2)
    just = " ".join((payload.justificacion or "").strip().split())

    if (abs(diff_r) > 0.009 or abs(diff_o) > 0.009) and not just:
        raise HTTPException(
            status_code=400,
            detail="Indique justificacion cuando hay diferencia entre lo esperado y lo contado",
        )

    tot = data["totales_dia"]

    row = CierreDiario(
        fecha_operativa=fe,
        ventas_reales=float(tot["ventas_reales"]),
        ventas_oro=float(tot["ventas_oro"]),
        compras_reales=float(tot["compras_reales"]),
        gastos_reales=float(tot["gastos_reales"]),
        oro_recolectado=float(tot["oro_recolectado_gramos"]),
        reales_esperados=reales_esperados,
        oro_esperado=oro_esperado,
        reales_contados=reales_contados,
        oro_contado=oro_contado,
        diferencia_reales=diff_r,
        diferencia_oro=diff_o,
        justificacion=just[:4000] if just else "",
        retiro_dueno_reales=float(payload.retiro_dueno_reales),
        retiro_dueno_oro=float(payload.retiro_dueno_oro),
        se_deja_reales=float(payload.se_deja_reales),
        se_deja_oro=float(payload.se_deja_oro),
        cerrado_por=payload.cerrado_por.strip()[:100],
        snapshot_json=json.dumps(data, ensure_ascii=False, default=str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "status": "success",
        "cierre_id": row.id,
        "fecha_operativa": fe.isoformat(),
        "cerrado_por": row.cerrado_por,
        "cierre": {
            "ventas_reales": row.ventas_reales,
            "ventas_oro": row.ventas_oro,
            "compras_reales": row.compras_reales,
            "gastos_reales": row.gastos_reales,
            "oro_recolectado": row.oro_recolectado,
            "reales_esperados": row.reales_esperados,
            "oro_esperado": row.oro_esperado,
            "reales_contados": row.reales_contados,
            "oro_contado": row.oro_contado,
            "diferencia_reales": row.diferencia_reales,
            "diferencia_oro": row.diferencia_oro,
            "justificacion": row.justificacion,
            "retiro_dueno_reales": row.retiro_dueno_reales,
            "retiro_dueno_oro": row.retiro_dueno_oro,
            "se_deja_reales": row.se_deja_reales,
            "se_deja_oro": row.se_deja_oro,
        },
        "detalle": data,
    }
