from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Gasolina, VentaGasolina
from schemas import GasolinaConfigUpdate, GasolinaVenta
from services.calculos import CalculosMonetarios
from services.validaciones import ValidacionesSistema


router = APIRouter(prefix="/gasolina", tags=["Gasolina"])


def _asegurar_gasolina(db: Session) -> Gasolina:
    gasolina = db.query(Gasolina).order_by(Gasolina.id.asc()).first()
    if gasolina:
        return gasolina
    gasolina = Gasolina(
        tipo="Gasolina",
        litros_disponibles=0,
        precio_por_litro_oro=0,
    )
    db.add(gasolina)
    db.flush()
    return gasolina


@router.get("")
def obtener_gasolina(db: Session = Depends(get_db)):
    gasolina = _asegurar_gasolina(db)
    db.commit()
    return gasolina


@router.put("/configurar")
def configurar_gasolina(data: GasolinaConfigUpdate, db: Session = Depends(get_db)):
    try:
        gasolina = _asegurar_gasolina(db)
        gasolina.tipo = data.tipo
        if data.litros_disponibles is not None:
            gasolina.litros_disponibles = data.litros_disponibles
        if data.precio_por_litro_oro is not None:
            gasolina.precio_por_litro_oro = data.precio_por_litro_oro
        db.commit()
        db.refresh(gasolina)
        return {"status": "success", "gasolina": gasolina}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible configurar la gasolina") from exc


@router.post("/venta")
def vender_gasolina(data: GasolinaVenta, db: Session = Depends(get_db)):
    try:
        tasa = ValidacionesSistema.validar_tasa(db, tasa_id=data.tasa_cambio_id)
        tipo_pago = ValidacionesSistema.normalizar_tipo_pago(data.tipo_pago)
        gasolina = ValidacionesSistema.validar_stock_gasolina(data.litros, db)

        total_oro = CalculosMonetarios.redondear(data.litros * gasolina.precio_por_litro_oro)
        total_reales = CalculosMonetarios.oro_a_reales(total_oro, db, tasa=tasa)
        vuelto_oro, vuelto_reales = ValidacionesSistema.validar_pago(
            tipo_pago=tipo_pago,
            total_oro=total_oro,
            monto_recibido_oro=data.monto_recibido_oro,
            monto_recibido_reales=data.monto_recibido_reales,
            tasa_reales=tasa.tasa_reales,
        )

        gasolina.litros_disponibles = CalculosMonetarios.redondear(gasolina.litros_disponibles - data.litros)

        venta = VentaGasolina(
            gasolina_id=gasolina.id,
            tasa_cambio_id=tasa.id,
            litros=data.litros,
            total_oro=total_oro,
            total_reales=total_reales,
            tipo_pago=tipo_pago,
            monto_recibido_oro=data.monto_recibido_oro,
            monto_recibido_reales=data.monto_recibido_reales,
            vuelto_oro=vuelto_oro,
            vuelto_reales=vuelto_reales,
        )
        db.add(venta)
        db.commit()
        db.refresh(venta)

        return {
            "status": "success",
            "message": "Venta de gasolina registrada",
            "data": {
                "venta_id": venta.id,
                "litros": data.litros,
                "total_oro": total_oro,
                "total_reales": total_reales,
                "tasa_nombre": tasa.nombre,
                "tasa_reales": tasa.tasa_reales,
                "stock_restante_litros": gasolina.litros_disponibles,
            },
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar la venta de gasolina") from exc


@router.get("/ventas")
def listar_ventas_gasolina(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    ventas = (
        db.query(VentaGasolina)
        .options(joinedload(VentaGasolina.tasa_cambio))
        .order_by(VentaGasolina.fecha.desc(), VentaGasolina.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": venta.id,
            "fecha": venta.fecha,
            "litros": venta.litros,
            "total_oro": venta.total_oro,
            "total_reales": venta.total_reales,
            "tipo_pago": venta.tipo_pago,
            "tasa_nombre": venta.tasa_cambio.nombre if venta.tasa_cambio else None,
            "tasa_reales": venta.tasa_cambio.tasa_reales if venta.tasa_cambio else None,
        }
        for venta in ventas
    ]
