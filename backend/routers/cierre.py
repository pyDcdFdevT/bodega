from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import AperturaCaja, CierreDiario, LoteOro
from routers.deps import require_admin
from schemas import CierreDiaOut, CierreGenerarCreate, CierreResponseOut
from services.apertura_context import build_apertura_pantalla_payload, fecha_operativa_hoy
from services.ledger import registrar_transaccion
from services.operativa import _inicio_dia_hoy, construir_payload_cierre
from services.oro_lotes import (
    eliminar_lote_cierre_si_posible,
    gramos_oro_en_lotes,
    lote_cierre_del_dia,
    origen_lote_desde_cierre,
)


router = APIRouter(prefix="/cierre", tags=["Cierre"])


@router.get("/apertura")
def cierre_apertura_contexto(db: Session = Depends(get_db)):
    """Sugerencia de apertura desde `se_deja_*` del cierre del día anterior; apertura ya registrada hoy si existe."""
    return build_apertura_pantalla_payload(db)


@router.get("/dia", response_model=CierreDiaOut)
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


@router.post("/generar", response_model=CierreResponseOut)
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
    lote_fundicion_id: int | None = None

    if payload.retirar_oro_para_fundicion:
        bruto = float(data["oro_recolectado"]["bruto_total_gramos"])
        if bruto <= 0:
            raise HTTPException(
                status_code=400,
                detail="No hay oro recolectado hoy para retirar a fundicion",
            )
        if lote_cierre_del_dia(db, fe):
            raise HTTPException(
                status_code=400,
                detail="Ya existe un lote de cierre para fundicion en este dia",
            )
        en_lotes = gramos_oro_en_lotes(db)
        disponible = round(oro_esperado - en_lotes, 4)
        if bruto > disponible + 0.02:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Oro disponible ({disponible} g) insuficiente para retiro "
                    f"({bruto} g); revise lotes previos"
                ),
            )
        lote = LoteOro(
            gramos_brutos=bruto,
            origen=origen_lote_desde_cierre(fe),
            estado="ACUMULANDO",
        )
        db.add(lote)
        db.flush()
        lote_fundicion_id = lote.id
        data["retiro_fundicion"] = {
            "lote_id": lote.id,
            "gramos_brutos": bruto,
            "origen": lote.origen,
        }

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
        "lote_fundicion_id": lote_fundicion_id,
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


@router.post("/reabrir")
def reabrir_dia_operativo(
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina el cierre de hoy para permitir nuevas operaciones (solo admin)."""
    fe = fecha_operativa_hoy()
    row = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == fe).first()
    if not row:
        raise HTTPException(status_code=400, detail="No hay cierre registrado para hoy")

    cierre_id = row.id
    try:
        eliminar_lote_cierre_si_posible(db, fe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.delete(row)
    registrar_transaccion(
        db,
        tipo="reabrir_dia",
        modulo_origen="bodega",
        referencia_id=cierre_id,
        moneda="reales",
        descripcion=f"Reapertura del dia operativo {fe.isoformat()}",
    )
    db.commit()
    return {
        "status": "success",
        "message": "Dia reabierto. Ya puede registrar operaciones.",
        "fecha_operativa": fe.isoformat(),
        "cierre_eliminado_id": cierre_id,
    }
