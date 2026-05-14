from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Compra, DetalleCompra, MovimientoInventario, Producto
from routers.deps import require_admin
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion
from services.validaciones import ValidacionesSistema
from schemas import CompraCreate, CompraUpdate


router = APIRouter(prefix="/compras", tags=["Compras"])


@router.post("")
def registrar_compra(compra: CompraCreate, db: Session = Depends(get_db)):
    try:
        tasa = ValidacionesSistema.validar_tasa(db)
        producto = ValidacionesSistema.obtener_producto_activo(compra.producto_id, db)
        if compra.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        unidades = compra.cantidad
        costo_oro_total = CalculosMonetarios.reales_a_oro(compra.precio_reales, db, tasa=tasa)
        costo_unitario_oro = CalculosMonetarios.redondear_oro(costo_oro_total / unidades)
        costo_unitario_reales = round(compra.precio_reales / unidades, 2)
        precio_sugerido = CalculosMonetarios.sugerir_precio_venta(costo_unitario_oro)

        stock_anterior = producto.stock_actual
        producto.stock_actual = CalculosMonetarios.redondear(producto.stock_actual + unidades)
        producto.precio_costo_oro = costo_unitario_oro
        producto.precio_costo_reales = costo_unitario_reales
        if producto.precio_venta_oro <= 0:
            producto.precio_venta_oro = precio_sugerido
            producto.precio_venta_reales = CalculosMonetarios.oro_a_reales(precio_sugerido, db, tasa=tasa)

        nueva = Compra(
            proveedor=compra.proveedor,
            total_reales=round(compra.precio_reales, 2),
            total_oro=costo_oro_total,
            tasa_cambio_usada=tasa.tasa_reales,
            observaciones=compra.observaciones,
        )
        db.add(nueva)
        db.flush()

        detalle = DetalleCompra(
            compra_id=nueva.id,
            producto_id=producto.id,
            cantidad=unidades,
            precio_reales_total=round(compra.precio_reales, 2),
            precio_reales_unitario=costo_unitario_reales,
            precio_oro_unitario=costo_unitario_oro,
            subtotal_oro=costo_oro_total,
        )
        db.add(detalle)
        db.add(
            MovimientoInventario(
                producto_id=producto.id,
                tipo="entrada",
                cantidad=unidades,
                stock_anterior=stock_anterior,
                stock_nuevo=producto.stock_actual,
                motivo=f"Compra registrada #{nueva.id}",
            )
        )

        registrar_transaccion(
            db,
            tipo="compra",
            modulo_origen="bodega",
            referencia_id=nueva.id,
            moneda="mixto",
            monto_reales=float(nueva.total_reales),
            gramos_oro=float(nueva.total_oro),
            tipo_oro=None,
            tasa_usada=float(tasa.tasa_reales),
            descripcion=f"Compra #{nueva.id} {compra.proveedor}",
        )

        db.commit()
        db.refresh(nueva)

        return {
            "status": "success",
            "message": "Compra registrada correctamente",
            "data": {
                "compra_id": nueva.id,
                "producto": producto.nombre,
                "unidades_ingresadas": unidades,
                "costo_unitario_oro": costo_unitario_oro,
                "precio_sugerido_venta_oro": precio_sugerido,
                "stock_actual": producto.stock_actual,
                "tasa_referencia": tasa.nombre,
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
        raise HTTPException(status_code=500, detail="No fue posible registrar la compra") from exc


@router.put("/{compra_id}/anular")
def anular_compra(
    compra_id: int,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        compra = (
            db.query(Compra)
            .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto))
            .filter(Compra.id == compra_id)
            .first()
        )
        if not compra:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        if (compra.estado or "VIGENTE") == "ANULADA":
            raise ValueError("La compra ya esta anulada")
        if not compra.detalles:
            raise ValueError("La compra no tiene detalle asociado")

        for det in compra.detalles:
            producto = det.producto
            if not producto:
                producto = db.query(Producto).filter(Producto.id == det.producto_id).first()
            if not producto:
                raise ValueError("Producto de la compra no encontrado")
            cant = float(det.cantidad)
            stock_ant = float(producto.stock_actual)
            if stock_ant + 1e-9 < cant:
                raise ValueError("Stock insuficiente para revertir la compra (no se puede anular)")
            producto.stock_actual = CalculosMonetarios.redondear(stock_ant - cant)
            db.add(
                MovimientoInventario(
                    producto_id=producto.id,
                    tipo="salida",
                    cantidad=cant,
                    stock_anterior=stock_ant,
                    stock_nuevo=producto.stock_actual,
                    motivo=f"Anulacion compra #{compra_id}",
                )
            )

        compra.estado = "ANULADA"
        registrar_transaccion(
            db,
            tipo="correccion",
            modulo_origen="bodega",
            referencia_id=compra.id,
            moneda="mixto",
            monto_reales=-float(compra.total_reales),
            gramos_oro=-float(compra.total_oro),
            tipo_oro=None,
            tasa_usada=float(compra.tasa_cambio_usada),
            descripcion=f"Anulacion compra #{compra.id}",
        )
        db.commit()
        db.refresh(compra)
        return {"status": "success", "compra_id": compra.id, "estado": compra.estado}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible anular la compra") from exc


@router.get("")
def listar_compras(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    compras = (
        db.query(Compra)
        .options(joinedload(Compra.detalles))
        .order_by(Compra.fecha.desc(), Compra.id.desc())
        .limit(limit)
        .all()
    )
    return compras


@router.put("/{compra_id}")
def actualizar_compra(compra_id: int, payload: CompraUpdate, db: Session = Depends(get_db)):
    try:
        compra = (
            db.query(Compra)
            .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto))
            .filter(Compra.id == compra_id)
            .first()
        )
        if not compra:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        if (compra.estado or "VIGENTE") == "ANULADA":
            raise ValueError("La compra esta anulada y no puede modificarse")
        if not compra.detalles:
            raise ValueError("La compra no tiene detalle asociado")

        detalle = compra.detalles[0]
        producto = detalle.producto
        if not producto:
            producto = db.query(Producto).filter(Producto.id == detalle.producto_id).first()
        if not producto:
            raise ValueError("Producto de la compra no encontrado")

        cantidad_anterior = detalle.cantidad
        unidades = payload.cantidad
        precio_reales = round(payload.precio_reales, 2)

        if unidades <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        stock_inicial = producto.stock_actual
        stock_tras_revertir = CalculosMonetarios.redondear(stock_inicial - cantidad_anterior)
        if stock_tras_revertir < 0:
            raise ValueError("No se puede revertir el stock de esta compra (stock insuficiente)")

        producto.stock_actual = CalculosMonetarios.redondear(stock_tras_revertir + unidades)

        tasa_usada = compra.tasa_cambio_usada
        if tasa_usada <= 0:
            raise ValueError("Tasa de la compra original invalida")

        costo_oro_total = CalculosMonetarios.redondear_oro(precio_reales / tasa_usada)
        costo_unitario_oro = CalculosMonetarios.redondear_oro(costo_oro_total / unidades)
        costo_unitario_reales = round(precio_reales / unidades, 2)
        precio_sugerido = CalculosMonetarios.sugerir_precio_venta(costo_unitario_oro)

        producto.precio_costo_oro = costo_unitario_oro
        producto.precio_costo_reales = costo_unitario_reales
        if producto.precio_venta_oro <= 0:
            tasa = ValidacionesSistema.validar_tasa(db)
            producto.precio_venta_oro = precio_sugerido
            producto.precio_venta_reales = CalculosMonetarios.oro_a_reales(precio_sugerido, db, tasa=tasa)

        compra.proveedor = payload.proveedor.strip()
        compra.observaciones = payload.observaciones
        compra.total_reales = precio_reales
        compra.total_oro = costo_oro_total

        detalle.cantidad = unidades
        detalle.precio_reales_total = precio_reales
        detalle.precio_reales_unitario = costo_unitario_reales
        detalle.precio_oro_unitario = costo_unitario_oro
        detalle.subtotal_oro = costo_oro_total

        delta = CalculosMonetarios.redondear(unidades - cantidad_anterior)
        if abs(delta) > 1e-9:
            db.add(
                MovimientoInventario(
                    producto_id=producto.id,
                    tipo="entrada" if delta > 0 else "salida",
                    cantidad=abs(delta),
                    stock_anterior=stock_inicial,
                    stock_nuevo=producto.stock_actual,
                    motivo=f"Compra #{compra.id} actualizada",
                )
            )

        db.commit()
        db.refresh(compra)

        return {
            "status": "success",
            "message": "Compra actualizada correctamente",
            "data": {
                "compra_id": compra.id,
                "producto": producto.nombre,
                "unidades": unidades,
                "total_reales": precio_reales,
                "total_oro": costo_oro_total,
                "stock_actual": producto.stock_actual,
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
        raise HTTPException(status_code=500, detail="No fue posible actualizar la compra") from exc
