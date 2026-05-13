from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Gasolina, GasolinaReposicion, TasaCambio, VentaGasolina
from schemas import GasolinaConfigUpdate, GasolinaReposicionCreate, GasolinaVenta
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


@router.post("/reponer")
def reponer_gasolina(data: GasolinaReposicionCreate, db: Session = Depends(get_db)):
    try:
        gasolina = _asegurar_gasolina(db)
        tasa = CalculosMonetarios.obtener_tasa_por_nombre(db, CalculosMonetarios.TASA_REFERENCIA_COMPRAS)
        if not tasa:
            tasa = CalculosMonetarios.obtener_tasa_referencia(db)
        if tasa.tasa_reales <= 0:
            raise ValueError("La tasa de referencia no es valida")

        total_reales = CalculosMonetarios.redondear(data.litros * data.precio_reales_litro, 2)
        total_oro = CalculosMonetarios.reales_a_oro(total_reales, db, tasa=tasa)
        gasolina.litros_disponibles = CalculosMonetarios.redondear(gasolina.litros_disponibles + data.litros, 3)

        registro = GasolinaReposicion(
            gasolina_id=gasolina.id,
            litros=data.litros,
            precio_reales_litro=data.precio_reales_litro,
            total_reales=total_reales,
            total_oro=total_oro,
            tasa_cambio_id=tasa.id,
        )
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return {
            "status": "success",
            "message": "Reposicion registrada",
            "data": {
                "id": registro.id,
                "litros": registro.litros,
                "total_reales": total_reales,
                "total_oro": total_oro,
                "litros_disponibles": gasolina.litros_disponibles,
            },
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar la reposicion") from exc


@router.post("/venta")
def vender_gasolina(data: GasolinaVenta, db: Session = Depends(get_db)):
    try:
        tipo_pago = ValidacionesSistema.normalizar_tipo_pago(data.tipo_pago)
        unidad = data.unidad_precio

        tasa: TasaCambio | None = None
        tipo_oro: str | None = None
        if tipo_pago in {"oro", "mixto"}:
            if not data.tipo_oro:
                raise ValueError("Debe seleccionar el tipo de oro")
            tipo_oro = ValidacionesSistema.validar_tipo_oro(data.tipo_oro)
            tasa = ValidacionesSistema.validar_tasa(db, tasa_nombre=tipo_oro)
        else:
            tasa = CalculosMonetarios.obtener_tasa_referencia(db)

        gasolina = ValidacionesSistema.validar_stock_gasolina(data.litros, db)
        precio = float(data.precio_por_litro)
        if precio <= 0:
            raise ValueError("El precio por litro debe ser mayor a cero")

        if unidad == "oro_litro":
            total_oro_core = CalculosMonetarios.redondear(data.litros * precio)
            total_reales_core = CalculosMonetarios.oro_a_reales(total_oro_core, db, tasa=tasa)
        else:
            bruto_reales = CalculosMonetarios.redondear(data.litros * precio, 2)
            total_reales_core = bruto_reales
            total_oro_core = CalculosMonetarios.reales_a_oro(bruto_reales, db, tasa=tasa)

        if tipo_pago == "reales":
            total_oro = 0.0
            total_reales = total_reales_core
            if data.monto_recibido_reales <= 0:
                raise ValueError("Debe indicar monto recibido en reales")
            if data.monto_recibido_reales + 1e-9 < total_reales:
                raise ValueError("Monto recibido insuficiente para completar la operacion")
            vuelto_oro = 0.0
            vuelto_reales = CalculosMonetarios.redondear(data.monto_recibido_reales - total_reales, 2)
        else:
            total_oro = total_oro_core
            total_reales = total_reales_core
            vuelto_oro, vuelto_reales = ValidacionesSistema.validar_pago(
                tipo_pago=tipo_pago,
                total_oro=total_oro,
                monto_recibido_oro=data.monto_recibido_oro,
                monto_recibido_reales=data.monto_recibido_reales,
                tasa_reales=tasa.tasa_reales,
            )

        gasolina.litros_disponibles = CalculosMonetarios.redondear(gasolina.litros_disponibles - data.litros, 3)

        assert tasa is not None
        venta = VentaGasolina(
            gasolina_id=gasolina.id,
            tasa_cambio_id=tasa.id,
            litros=data.litros,
            total_oro=total_oro,
            total_reales=total_reales,
            tipo_pago=tipo_pago,
            tipo_oro=tipo_oro,
            unidad_precio_venta=unidad,
            precio_litro_venta=precio,
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
                "vuelto_oro": vuelto_oro,
                "vuelto_reales": vuelto_reales,
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
            "tipo_oro": venta.tipo_oro,
            "unidad_precio_venta": venta.unidad_precio_venta or "oro_litro",
            "precio_litro_venta": venta.precio_litro_venta if venta.precio_litro_venta is not None else 0,
            "tasa_nombre": venta.tasa_cambio.nombre if venta.tasa_cambio else None,
            "tasa_reales": venta.tasa_cambio.tasa_reales if venta.tasa_cambio else None,
        }
        for venta in ventas
    ]
