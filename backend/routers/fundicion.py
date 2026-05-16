from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import DistribucionFondos, Fundicion, LoteOro, VentaPieza
from services.operativa import _inicio_dia_hoy, construir_payload_cierre
from routers.deps import require_admin
from schemas import DistribucionFondosCreate, FundicionCreate, LoteOroCreate, VentaPiezaCreate


router = APIRouter(prefix="/fundicion", tags=["Fundicion"])

TIPOS_DISTRIB = frozenset(
    {
        "reposicion_bodega",
        "reposicion_gasolina",
        "gastos_operativos",
        "pago_socio",
        "ganancia_dueno",
        "se_deja_caja",
    }
)

ESTADOS_LOTE = frozenset({"ACUMULANDO", "ENVIADO", "FUNDIDO", "VENDIDO", "CERRADO"})


def _serial_lote(row: LoteOro) -> dict:
    return {
        "id": row.id,
        "fecha": row.fecha.isoformat() if row.fecha else None,
        "gramos_brutos": float(row.gramos_brutos),
        "origen": row.origen,
        "estado": row.estado,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _serial_fund(row: Fundicion) -> dict:
    return {
        "id": row.id,
        "lote_oro_id": row.lote_oro_id,
        "gramos_brutos": float(row.gramos_brutos),
        "ley": float(row.ley),
        "gramos_finos": float(row.gramos_finos),
        "casa_fundicion": row.casa_fundicion,
        "fecha": row.fecha.isoformat() if row.fecha else None,
    }


def _serial_vp(row: VentaPieza) -> dict:
    return {
        "id": row.id,
        "fundicion_id": row.fundicion_id,
        "gramos_vendidos": float(row.gramos_vendidos),
        "tasa_venta": float(row.tasa_venta),
        "monto_total": float(row.monto_total),
        "moneda": row.moneda,
        "comprador": row.comprador,
        "fecha": row.fecha.isoformat() if row.fecha else None,
    }


@router.get("/sugerencia-oro-bruto")
def sugerencia_oro_bruto(db: Session = Depends(get_db)):
    inicio = _inicio_dia_hoy()
    data = construir_payload_cierre(db, inicio, 0.0, 0.0)
    bruto = float(data["oro_recolectado"]["bruto_total_gramos"])
    return {"gramos_brutos_sugeridos": round(bruto, 2), "fecha": data["fecha"]}


@router.get("/lotes")
def listar_lotes(db: Session = Depends(get_db)):
    rows = db.query(LoteOro).order_by(LoteOro.fecha.desc(), LoteOro.id.desc()).all()
    return [_serial_lote(r) for r in rows]


@router.post("/lotes")
def crear_lote(
    payload: LoteOroCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    est = payload.estado.strip().upper()
    if est not in ESTADOS_LOTE:
        raise HTTPException(status_code=400, detail="Estado no valido")
    row = LoteOro(
        gramos_brutos=float(payload.gramos_brutos),
        origen=(payload.origen or "").strip()[:255],
        estado=est,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "ok", "lote": _serial_lote(row)}


@router.get("/fundiciones")
def listar_fundiciones(db: Session = Depends(get_db)):
    rows = db.query(Fundicion).order_by(Fundicion.fecha.desc(), Fundicion.id.desc()).all()
    return [_serial_fund(r) for r in rows]


@router.get("/fundiciones/disponibles-venta")
def fundiciones_sin_venta(db: Session = Depends(get_db)):
    rows = (
        db.query(Fundicion)
        .outerjoin(VentaPieza, Fundicion.id == VentaPieza.fundicion_id)
        .filter(VentaPieza.id.is_(None))
        .order_by(Fundicion.fecha.desc())
        .all()
    )
    return [_serial_fund(r) for r in rows]


@router.post("/fundiciones")
def registrar_fundicion(
    payload: FundicionCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    lote = db.query(LoteOro).filter(LoteOro.id == payload.lote_oro_id).first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if lote.estado in ("FUNDIDO", "VENDIDO", "CERRADO"):
        raise HTTPException(status_code=400, detail="El lote ya no admite fundicion")
    if db.query(Fundicion).filter(Fundicion.lote_oro_id == lote.id).first():
        raise HTTPException(status_code=400, detail="Este lote ya tiene fundicion registrada")

    row = Fundicion(
        lote_oro_id=lote.id,
        gramos_brutos=float(payload.gramos_brutos),
        ley=float(payload.ley),
        gramos_finos=float(payload.gramos_finos),
        casa_fundicion=payload.casa_fundicion.strip()[:200],
    )
    lote.estado = "FUNDIDO"
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "ok", "fundicion": _serial_fund(row)}


@router.get("/ventas-pieza")
def listar_ventas_pieza(db: Session = Depends(get_db)):
    rows = db.query(VentaPieza).order_by(VentaPieza.fecha.desc(), VentaPieza.id.desc()).all()
    return [_serial_vp(r) for r in rows]


@router.post("/ventas-pieza")
def registrar_venta_pieza(
    payload: VentaPiezaCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    fund = db.query(Fundicion).filter(Fundicion.id == payload.fundicion_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fundicion no encontrada")
    if db.query(VentaPieza).filter(VentaPieza.fundicion_id == fund.id).first():
        raise HTTPException(status_code=400, detail="Esta fundicion ya tiene venta de pieza")
    gv = float(payload.gramos_vendidos)
    if gv > float(fund.gramos_finos) + 1e-6:
        raise HTTPException(status_code=400, detail="Gramos vendidos superan los finos de la fundicion")
    mon = payload.moneda.strip()
    if mon.lower() == "usd":
        mon = "USD"
    elif mon.lower() == "reales":
        mon = "reales"
    else:
        raise HTTPException(status_code=400, detail="Moneda debe ser reales o USD")
    row = VentaPieza(
        fundicion_id=fund.id,
        gramos_vendidos=gv,
        tasa_venta=float(payload.tasa_venta),
        monto_total=float(payload.monto_total),
        moneda=mon,
        comprador=payload.comprador.strip()[:200],
    )
    lote = db.query(LoteOro).filter(LoteOro.id == fund.lote_oro_id).first()
    if lote:
        lote.estado = "VENDIDO"
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "ok", "venta_pieza": _serial_vp(row)}


@router.get("/ventas-pieza/sin-distribuir")
def ventas_pieza_sin_distribuir(db: Session = Depends(get_db)):
    rows = (
        db.query(VentaPieza)
        .outerjoin(DistribucionFondos, VentaPieza.id == DistribucionFondos.venta_pieza_id)
        .filter(DistribucionFondos.id.is_(None))
        .order_by(VentaPieza.fecha.desc())
        .all()
    )
    return [_serial_vp(r) for r in rows]


@router.get("/distribuciones")
def listar_distribuciones(
    venta_pieza_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(DistribucionFondos, VentaPieza).join(
        VentaPieza, DistribucionFondos.venta_pieza_id == VentaPieza.id
    )
    if venta_pieza_id is not None:
        q = q.filter(DistribucionFondos.venta_pieza_id == venta_pieza_id)
    rows = (
        q.order_by(VentaPieza.fecha.desc(), DistribucionFondos.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": dist.id,
            "venta_pieza_id": dist.venta_pieza_id,
            "tipo": dist.tipo,
            "monto": float(dist.monto),
            "descripcion": dist.descripcion,
            "fecha": vp.fecha.isoformat() if vp.fecha else None,
        }
        for dist, vp in rows
    ]


@router.post("/distribuciones")
def registrar_distribucion(
    payload: DistribucionFondosCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    vp = db.query(VentaPieza).filter(VentaPieza.id == payload.venta_pieza_id).first()
    if not vp:
        raise HTTPException(status_code=404, detail="Venta pieza no encontrada")
    if vp.moneda != "reales":
        raise HTTPException(status_code=400, detail="La distribucion en reales solo aplica si la venta es en reales")
    if db.query(DistribucionFondos).filter(DistribucionFondos.venta_pieza_id == vp.id).first():
        raise HTTPException(status_code=400, detail="Ya existe distribucion para esta venta")

    total = 0.0
    for ln in payload.lineas:
        if ln.tipo not in TIPOS_DISTRIB:
            raise HTTPException(status_code=400, detail=f"Tipo de linea no valido: {ln.tipo}")
        total += float(ln.monto)
    esperado = float(vp.monto_total)
    if round(total - esperado, 2) != 0:
        raise HTTPException(
            status_code=400,
            detail=f"La suma de la distribucion ({round(total,2)}) debe igualar el total de la venta ({round(esperado,2)})",
        )

    for ln in payload.lineas:
        db.add(
            DistribucionFondos(
                venta_pieza_id=vp.id,
                tipo=ln.tipo,
                monto=float(ln.monto),
                descripcion=(ln.descripcion or "").strip()[:255] if ln.descripcion else None,
            )
        )
    db.commit()
    return {"status": "ok", "venta_pieza_id": vp.id, "lineas": len(payload.lineas)}
