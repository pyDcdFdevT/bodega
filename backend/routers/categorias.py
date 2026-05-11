from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Categoria, Producto
from backend.schemas import CategoriaCreate


router = APIRouter(prefix="/categorias", tags=["Categorias"])


@router.get("")
def listar_categorias(db: Session = Depends(get_db)):
    categorias = db.query(Categoria).options(joinedload(Categoria.productos)).order_by(Categoria.nombre.asc()).all()
    return [
        {
            "id": categoria.id,
            "nombre": categoria.nombre,
            "descripcion": categoria.descripcion,
            "icono": categoria.icono,
            "color": categoria.color,
            "created_at": categoria.created_at,
            "total_productos": len(categoria.productos),
            "productos_activos": len([producto for producto in categoria.productos if producto.activo]),
        }
        for categoria in categorias
    ]


@router.post("")
def crear_categoria(cat: CategoriaCreate, db: Session = Depends(get_db)):
    try:
        existe = db.query(Categoria).filter(Categoria.nombre == cat.nombre).first()
        if existe:
            raise ValueError("La categoria ya existe")
        nueva = Categoria(
            nombre=cat.nombre,
            descripcion=cat.descripcion,
            icono=cat.icono,
            color=cat.color,
        )
        db.add(nueva)
        db.commit()
        db.refresh(nueva)
        return {"status": "success", "categoria": nueva}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible crear la categoria") from exc


@router.get("/{categoria_id}/productos")
def productos_por_categoria(categoria_id: int, db: Session = Depends(get_db)):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    productos = (
        db.query(Producto)
        .filter(Producto.categoria_id == categoria_id, Producto.activo.is_(True))
        .order_by(Producto.nombre.asc())
        .all()
    )
    return {
        "categoria": categoria.nombre,
        "productos": [
            {
                "id": producto.id,
                "nombre": producto.nombre,
                "presentacion": producto.presentacion,
                "stock_actual": producto.stock_actual,
                "precio_venta_oro": producto.precio_venta_oro,
            }
            for producto in productos
        ],
    }
