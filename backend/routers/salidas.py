from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import MovimientoInventario, Producto, Salida
from schemas import SalidaCreate
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion


router = APIRouter(prefix="/salidas", tags=["Salidas"])


@router.post("")
def registrar_salida(data: SalidaCreate, db: Session = Depends(get_db)):
    try:
        producto = (
            db.query(Producto)
            .filter(Producto.id == data.producto_id, Producto.activo.is_(True))
            .first()
        )
        if not producto:
            raise ValueError("Producto no encontrado o inactivo")
        if data.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if producto.stock_actual < data.cantidad:
            raise ValueError(
                f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock_actual}"
            )

        stock_anterior = producto.stock_actual
        valor_oro = CalculosMonetarios.redondear(producto.precio_venta_oro * data.cantidad)
        producto.stock_actual = CalculosMonetarios.redondear(producto.stock_actual - data.cantidad)

        salida = Salida(
            producto_id=producto.id,
            cantidad=data.cantidad,
            valor_oro=valor_oro,
            motivo=data.motivo,
        )
        db.add(salida)
        db.flush()

        movimiento = MovimientoInventario(
            producto_id=producto.id,
            tipo="salida",
            cantidad=data.cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=producto.stock_actual,
            motivo=f"Salida: {data.motivo}",
        )
        db.add(movimiento)

        registrar_transaccion(
            db,
            tipo="salida",
            modulo_origen="bodega",
            referencia_id=salida.id,
            moneda="oro",
            monto_reales=0.0,
            gramos_oro=float(valor_oro),
            tipo_oro=None,
            tasa_usada=None,
            descripcion=f"Salida #{salida.id} {producto.nombre}: {data.motivo}"[:255],
        )

        db.commit()
        db.refresh(salida)

        return {
            "status": "success",
            "message": "Salida registrada correctamente",
            "data": {
                "id": salida.id,
                "producto": producto.nombre,
                "cantidad": salida.cantidad,
                "valor_oro": salida.valor_oro,
                "motivo": salida.motivo,
                "stock_restante": producto.stock_actual,
            },
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar la salida") from exc


@router.get("")
def listar_salidas(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    salidas = (
        db.query(Salida)
        .options(joinedload(Salida.producto))
        .order_by(Salida.fecha.desc(), Salida.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": salida.id,
            "producto_id": salida.producto_id,
            "producto": salida.producto.nombre if salida.producto else None,
            "cantidad": salida.cantidad,
            "valor_oro": salida.valor_oro,
            "motivo": salida.motivo,
            "fecha": salida.fecha,
        }
        for salida in salidas
    ]
