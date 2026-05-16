from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Categoria, DetalleCompra, DetalleVenta, MovimientoInventario, Producto
from schemas import ProductoCreate, ProductoUpdate
from services.calculos import CalculosMonetarios


router = APIRouter(prefix="/productos", tags=["Productos"])


def serializar_producto(producto: Producto) -> dict:
    if producto.stock_actual <= 0:
        estado_stock = "agotado"
    elif producto.stock_actual <= producto.stock_minimo:
        estado_stock = "bajo"
    else:
        estado_stock = "ok"

    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "categoria_id": producto.categoria_id,
        "categoria_nombre": producto.categoria_rel.nombre if producto.categoria_rel else None,
        "presentacion": producto.presentacion,
        "unidad_venta": producto.unidad_venta,
        "kg_por_unidad": float(producto.kg_por_unidad) if producto.kg_por_unidad else None,
        "stock_actual": producto.stock_actual,
        "stock_minimo": producto.stock_minimo,
        "precio_costo_oro": producto.precio_costo_oro,
        "precio_costo_reales": producto.precio_costo_reales,
        "costo_promedio_reales": float(producto.costo_promedio_reales or producto.precio_costo_reales or 0),
        "precio_venta_reales": producto.precio_venta_reales,
        "precio_venta_oro": producto.precio_venta_oro,
        "activo": producto.activo,
        "estado_stock": estado_stock,
        "created_at": producto.created_at,
        "updated_at": producto.updated_at,
    }


def obtener_o_crear_categoria(db: Session, categoria_nombre: str) -> Categoria:
    categoria = db.query(Categoria).filter(Categoria.nombre == categoria_nombre).first()
    if categoria:
        return categoria
    categoria = Categoria(nombre=categoria_nombre, icono="BOX", color="#D5E6F7")
    db.add(categoria)
    db.flush()
    return categoria


@router.get("")
def listar_productos(
    categoria: str | None = None,
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Producto).options(joinedload(Producto.categoria_rel))
    if not incluir_inactivos:
        query = query.filter(Producto.activo.is_(True))
    if categoria:
        query = query.join(Categoria).filter(Categoria.nombre == categoria)
    productos = query.order_by(Producto.nombre.asc()).all()
    return [serializar_producto(producto) for producto in productos]


@router.get("/buscar")
def buscar_producto(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    productos = (
        db.query(Producto)
        .options(joinedload(Producto.categoria_rel))
        .filter(Producto.activo.is_(True), Producto.nombre.ilike(f"%{q.strip()}%"))
        .order_by(Producto.nombre.asc())
        .all()
    )
    return [serializar_producto(producto) for producto in productos]


@router.get("/stock-bajo")
def stock_bajo(db: Session = Depends(get_db)):
    productos = (
        db.query(Producto)
        .options(joinedload(Producto.categoria_rel))
        .filter(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_minimo)
        .order_by(Producto.stock_actual.asc(), Producto.nombre.asc())
        .all()
    )
    return [serializar_producto(producto) for producto in productos]


@router.get("/{producto_id}/info-eliminacion")
def info_eliminacion_producto(producto_id: int, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    stock_actual = float(producto.stock_actual)
    tiene_stock = stock_actual > 0
    total_ventas = int(
        db.query(func.count(DetalleVenta.id)).filter(DetalleVenta.producto_id == producto_id).scalar() or 0
    )
    total_compras = int(
        db.query(func.count(DetalleCompra.id)).filter(DetalleCompra.producto_id == producto_id).scalar() or 0
    )
    total_movimientos = int(
        db.query(func.count(MovimientoInventario.id))
        .filter(MovimientoInventario.producto_id == producto_id)
        .scalar()
        or 0
    )
    return {
        "tiene_stock": tiene_stock,
        "stock_actual": stock_actual,
        "total_ventas": total_ventas,
        "total_compras": total_compras,
        "total_movimientos": total_movimientos,
    }


@router.get("/{producto_id}")
def obtener_producto(producto_id: int, db: Session = Depends(get_db)):
    producto = (
        db.query(Producto)
        .options(joinedload(Producto.categoria_rel))
        .filter(Producto.id == producto_id)
        .first()
    )
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return serializar_producto(producto)


@router.post("")
def crear_producto(producto: ProductoCreate, db: Session = Depends(get_db)):
    try:
        CalculosMonetarios.listar_tasas(db)
        tasa_referencia = CalculosMonetarios.obtener_tasa_por_nombre(db, "araparita")
        if not tasa_referencia or tasa_referencia.tasa_reales <= 0:
            raise ValueError("La tasa de referencia araparita no esta disponible")
        precio_venta_oro = CalculosMonetarios.reales_a_oro(
            producto.precio_venta_reales,
            db,
            tasa=tasa_referencia,
        )
        categoria = obtener_o_crear_categoria(db, producto.categoria_nombre)
        duplicado = (
            db.query(Producto)
            .filter(
                Producto.nombre == producto.nombre,
                Producto.categoria_id == categoria.id,
                Producto.presentacion == producto.presentacion,
            )
            .first()
        )
        if duplicado:
            raise ValueError("Ya existe un producto con ese nombre, categoria y presentacion")

        nuevo = Producto(
            nombre=producto.nombre,
            categoria_id=categoria.id,
            presentacion=producto.presentacion,
            unidad_venta=producto.unidad_venta,
            kg_por_unidad=producto.kg_por_unidad,
            stock_actual=producto.stock_actual,
            stock_minimo=producto.stock_minimo,
            precio_venta_reales=producto.precio_venta_reales,
            precio_venta_oro=precio_venta_oro,
        )
        db.add(nuevo)
        db.flush()

        if producto.stock_actual > 0:
            db.add(
                MovimientoInventario(
                    producto_id=nuevo.id,
                    tipo="ajuste",
                    cantidad=producto.stock_actual,
                    stock_anterior=0,
                    stock_nuevo=producto.stock_actual,
                    motivo="Stock inicial del producto",
                )
            )

        db.commit()
        db.refresh(nuevo)
        nuevo = (
            db.query(Producto)
            .options(joinedload(Producto.categoria_rel))
            .filter(Producto.id == nuevo.id)
            .first()
        )
        return {"status": "success", "producto": serializar_producto(nuevo)}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible crear el producto") from exc


@router.put("/{producto_id}")
def actualizar_producto(producto_id: int, data: ProductoUpdate, db: Session = Depends(get_db)):
    try:
        producto = db.query(Producto).filter(Producto.id == producto_id).first()
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        if data.categoria_nombre is not None:
            categoria = obtener_o_crear_categoria(db, data.categoria_nombre)
            producto.categoria_id = categoria.id
        if data.nombre is not None:
            producto.nombre = data.nombre
        if data.presentacion is not None:
            producto.presentacion = data.presentacion
        if data.unidad_venta is not None:
            producto.unidad_venta = data.unidad_venta
            if data.unidad_venta != "kg":
                producto.kg_por_unidad = None
        if data.kg_por_unidad is not None:
            if data.kg_por_unidad > 0 and producto.unidad_venta != "kg":
                raise ValueError("kg_por_unidad solo aplica si la unidad de venta es kg")
            producto.kg_por_unidad = data.kg_por_unidad if data.kg_por_unidad > 0 else None
        if data.stock_minimo is not None:
            producto.stock_minimo = data.stock_minimo
        if data.precio_venta_reales is not None:
            CalculosMonetarios.listar_tasas(db)
            tasa_referencia = CalculosMonetarios.obtener_tasa_por_nombre(db, "araparita")
            if not tasa_referencia or tasa_referencia.tasa_reales <= 0:
                raise ValueError("La tasa de referencia araparita no esta disponible")
            producto.precio_venta_reales = data.precio_venta_reales
            producto.precio_venta_oro = CalculosMonetarios.reales_a_oro(
                data.precio_venta_reales,
                db,
                tasa=tasa_referencia,
            )
        if data.activo is not None:
            producto.activo = data.activo

        if data.stock_actual is not None and data.stock_actual != producto.stock_actual:
            stock_anterior = producto.stock_actual
            producto.stock_actual = data.stock_actual
            if producto.stock_actual < 0:
                raise ValueError("Invariante stock: el stock del producto no puede ser negativo")
            diferencia = abs(data.stock_actual - stock_anterior)
            db.add(
                MovimientoInventario(
                    producto_id=producto.id,
                    tipo="ajuste",
                    cantidad=diferencia,
                    stock_anterior=stock_anterior,
                    stock_nuevo=data.stock_actual,
                    motivo="Ajuste manual de inventario",
                )
            )

        db.commit()
        actualizado = (
            db.query(Producto)
            .options(joinedload(Producto.categoria_rel))
            .filter(Producto.id == producto_id)
            .first()
        )
        return {"status": "success", "producto": serializar_producto(actualizado)}
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible actualizar el producto") from exc


@router.delete("/{producto_id}")
def desactivar_producto(producto_id: int, db: Session = Depends(get_db)):
    try:
        producto = db.query(Producto).filter(Producto.id == producto_id).first()
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        producto.activo = False
        db.commit()
        return {"status": "success", "message": "Producto desactivado"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible desactivar el producto") from exc
