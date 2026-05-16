from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Compra, DetalleCompra, MovimientoInventario, Producto
from routers.deps import require_admin
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion
from services.operativa import verificar_dia_abierto
from services.compra_merma import (
    observaciones_con_unidades,
    producto_compra_por_kg,
    registrar_merma_transporte,
    resolver_kilos_compra,
)
from services.validaciones import ValidacionesSistema
from schemas import CompraCreate, CompraOut, CompraUpdate


router = APIRouter(prefix="/compras", tags=["Compras"])


@router.post("")
def registrar_compra(compra: CompraCreate, db: Session = Depends(get_db)):
    try:
        verificar_dia_abierto(db)
        tasa = ValidacionesSistema.validar_tasa(db)
        producto = ValidacionesSistema.obtener_producto_activo(compra.producto_id, db)
        if compra.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        es_kg = producto_compra_por_kg(producto)
        kilos_factura, kilos_recibidos = resolver_kilos_compra(
            producto,
            compra.cantidad,
            compra.kilos_factura,
            compra.kilos_recibidos,
        )
        unidades = kilos_recibidos if es_kg else compra.cantidad
        base_costo_kg = kilos_factura if es_kg else unidades

        if es_kg and compra.registrar_merma_transporte and kilos_factura <= kilos_recibidos + 0.0001:
            raise ValueError("No hay diferencia de kilos para registrar merma por transporte")

        costo_oro_total = CalculosMonetarios.reales_a_oro(compra.precio_reales, db, tasa=tasa)
        costo_unitario_oro = CalculosMonetarios.redondear_oro(costo_oro_total / base_costo_kg)
        costo_unitario_reales = round(compra.precio_reales / base_costo_kg, 2)
        precio_sugerido = CalculosMonetarios.sugerir_precio_venta(costo_unitario_oro)

        stock_anterior = producto.stock_actual
        cpp_anterior = float(producto.costo_promedio_reales or producto.precio_costo_reales or 0)
        producto.stock_actual = CalculosMonetarios.redondear(producto.stock_actual + unidades)
        producto.costo_promedio_reales = CalculosMonetarios.costo_promedio_ponderado(
            stock_anterior,
            cpp_anterior,
            unidades,
            costo_unitario_reales,
        )
        producto.precio_costo_oro = costo_unitario_oro
        producto.precio_costo_reales = costo_unitario_reales
        if producto.precio_venta_oro <= 0:
            producto.precio_venta_oro = precio_sugerido
            producto.precio_venta_reales = CalculosMonetarios.oro_a_reales(precio_sugerido, db, tasa=tasa)

        tipo_pago = compra.tipo_pago_compra
        obs = observaciones_con_unidades(compra.observaciones, compra.unidades if es_kg else None)
        if es_kg and abs(kilos_factura - kilos_recibidos) > 0.0001:
            nota = f"Factura: {kilos_factura} kg · Recibido: {kilos_recibidos} kg"
            obs = f"{obs} — {nota}" if obs else nota

        nueva = Compra(
            proveedor=compra.proveedor,
            total_reales=round(compra.precio_reales, 2),
            total_oro=costo_oro_total,
            tasa_cambio_usada=tasa.tasa_reales,
            observaciones=obs,
            tipo_pago_compra=tipo_pago,
            estado_credito="pendiente" if tipo_pago == "credito" else "pagada",
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

        salida_merma = None
        if es_kg and compra.registrar_merma_transporte:
            diferencia = round(kilos_factura - kilos_recibidos, 3)
            salida_merma = registrar_merma_transporte(
                db,
                producto=producto,
                diferencia_kg=diferencia,
                costo_unitario_reales=costo_unitario_reales,
                compra_id=nueva.id,
            )

        monto_caja = float(nueva.total_reales) if tipo_pago == "contado" else 0.0
        registrar_transaccion(
            db,
            tipo="compra",
            modulo_origen="bodega",
            referencia_id=nueva.id,
            moneda="mixto",
            monto_reales=monto_caja,
            gramos_oro=float(nueva.total_oro),
            tipo_oro=None,
            tasa_usada=float(tasa.tasa_reales),
            descripcion=(
                f"Compra #{nueva.id} {compra.proveedor}"
                if tipo_pago == "contado"
                else f"Compra a credito #{nueva.id} {compra.proveedor} (cuenta por pagar)"
            ),
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
                "kilos_factura": kilos_factura if es_kg else None,
                "kilos_recibidos": kilos_recibidos if es_kg else None,
                "merma_transporte_kg": round(kilos_factura - kilos_recibidos, 3) if es_kg else None,
                "salida_merma_id": salida_merma.id if salida_merma else None,
                "costo_unitario_oro": costo_unitario_oro,
                "costo_promedio_reales": producto.costo_promedio_reales,
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


@router.get("", response_model=list[CompraOut])
def listar_compras(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    compras = (
        db.query(Compra)
        .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto))
        .order_by(Compra.fecha.desc(), Compra.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": c.id,
            "fecha": c.fecha,
            "proveedor": c.proveedor,
            "total_reales": c.total_reales,
            "tipo_pago_compra": c.tipo_pago_compra or "contado",
            "observaciones": c.observaciones,
            "detalles": [
                {
                    "producto_id": d.producto_id,
                    "cantidad": d.cantidad,
                    "precio_reales_total": d.precio_reales_total,
                    "producto_nombre": d.producto.nombre if d.producto else None,
                }
                for d in c.detalles
            ],
        }
        for c in compras
    ]


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

        stock_tras_revertir_f = float(stock_tras_revertir)
        producto.stock_actual = CalculosMonetarios.redondear(stock_tras_revertir + unidades)

        tasa_usada = compra.tasa_cambio_usada
        if tasa_usada <= 0:
            raise ValueError("Tasa de la compra original invalida")

        costo_oro_total = CalculosMonetarios.redondear_oro(precio_reales / tasa_usada)
        costo_unitario_oro = CalculosMonetarios.redondear_oro(costo_oro_total / unidades)
        costo_unitario_reales = round(precio_reales / unidades, 2)
        precio_sugerido = CalculosMonetarios.sugerir_precio_venta(costo_unitario_oro)

        cpp_anterior = float(producto.costo_promedio_reales or producto.precio_costo_reales or 0)
        producto.costo_promedio_reales = CalculosMonetarios.costo_promedio_ponderado(
            stock_tras_revertir_f,
            cpp_anterior,
            unidades,
            costo_unitario_reales,
        )
        producto.precio_costo_oro = costo_unitario_oro
        producto.precio_costo_reales = costo_unitario_reales
        if producto.precio_venta_oro <= 0:
            tasa = ValidacionesSistema.validar_tasa(db)
            producto.precio_venta_oro = precio_sugerido
            producto.precio_venta_reales = CalculosMonetarios.oro_a_reales(precio_sugerido, db, tasa=tasa)

        compra.proveedor = payload.proveedor.strip()
        compra.observaciones = payload.observaciones
        if payload.tipo_pago_compra is not None:
            compra.tipo_pago_compra = payload.tipo_pago_compra
            if payload.tipo_pago_compra == "credito" and compra.estado_credito == "pagada":
                pagado = sum(float(p.monto) for p in compra.pagos_proveedor)
                if pagado < float(compra.total_reales) - 0.009:
                    compra.estado_credito = "pendiente"
            elif payload.tipo_pago_compra == "contado":
                compra.estado_credito = "pagada"
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
