from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Categoria, Gasolina, Producto, TasaCambio


def inicializar_datos() -> None:
    db = SessionLocal()
    try:
        _inicializar_datos(db)
    finally:
        db.close()


def _inicializar_datos(db: Session) -> None:
    if db.query(Categoria).count() > 0:
        return

    categorias = [
        Categoria(nombre="Alimentos", descripcion="Productos de consumo diario", icono="FOOD", color="#F4D06F"),
        Categoria(nombre="Bebidas", descripcion="Bebidas frias y de mostrador", icono="DRINK", color="#8EC5FC"),
        Categoria(nombre="Snacks", descripcion="Dulces y pasapalos", icono="SNACK", color="#F8AFA6"),
        Categoria(nombre="Lacteos", descripcion="Productos refrigerados", icono="MILK", color="#DDEAF6"),
        Categoria(nombre="Enlatados", descripcion="Conservas y salsas", icono="CAN", color="#A0E7E5"),
        Categoria(nombre="Combustible", descripcion="Control de gasolina", icono="FUEL", color="#F7C948"),
        Categoria(nombre="Hogar", descripcion="Articulos de limpieza e higiene", icono="HOME", color="#CBD5E1"),
    ]
    db.add_all(categorias)
    db.flush()

    cats = {categoria.nombre: categoria.id for categoria in categorias}

    productos = [
        Producto(nombre="Arroz", categoria_id=cats["Alimentos"], presentacion="kg", unidades_por_bulto=24, stock_actual=48, stock_minimo=12, precio_venta_oro=0.50),
        Producto(nombre="Harina de maiz", categoria_id=cats["Alimentos"], presentacion="paquete", unidades_por_bulto=20, stock_actual=40, stock_minimo=10, precio_venta_oro=0.42),
        Producto(nombre="Pasta corta", categoria_id=cats["Alimentos"], presentacion="paquete", unidades_por_bulto=24, stock_actual=60, stock_minimo=12, precio_venta_oro=0.28),
        Producto(nombre="Azucar", categoria_id=cats["Alimentos"], presentacion="kg", unidades_por_bulto=12, stock_actual=24, stock_minimo=8, precio_venta_oro=0.39),
        Producto(nombre="Cafe molido", categoria_id=cats["Alimentos"], presentacion="paquete", unidades_por_bulto=12, stock_actual=30, stock_minimo=8, precio_venta_oro=0.82),
        Producto(nombre="Aceite vegetal", categoria_id=cats["Alimentos"], presentacion="botella", unidades_por_bulto=12, stock_actual=24, stock_minimo=6, precio_venta_oro=0.88),
        Producto(nombre="Avena", categoria_id=cats["Alimentos"], presentacion="paquete", unidades_por_bulto=12, stock_actual=18, stock_minimo=6, precio_venta_oro=0.22),
        Producto(nombre="Refresco sabor cola 2L", categoria_id=cats["Bebidas"], presentacion="botella", unidades_por_bulto=8, stock_actual=20, stock_minimo=8, precio_venta_oro=0.36),
        Producto(nombre="Refresco sabor naranja 2L", categoria_id=cats["Bebidas"], presentacion="botella", unidades_por_bulto=8, stock_actual=16, stock_minimo=8, precio_venta_oro=0.36),
        Producto(nombre="Jugo de frutas", categoria_id=cats["Bebidas"], presentacion="botella", unidades_por_bulto=12, stock_actual=24, stock_minimo=8, precio_venta_oro=0.27),
        Producto(nombre="Malta", categoria_id=cats["Bebidas"], presentacion="lata", unidades_por_bulto=24, stock_actual=48, stock_minimo=12, precio_venta_oro=0.21),
        Producto(nombre="Galleta dulce", categoria_id=cats["Snacks"], presentacion="paquete", unidades_por_bulto=24, stock_actual=60, stock_minimo=12, precio_venta_oro=0.17),
        Producto(nombre="Galleta salada", categoria_id=cats["Snacks"], presentacion="paquete", unidades_por_bulto=24, stock_actual=54, stock_minimo=12, precio_venta_oro=0.17),
        Producto(nombre="Chocolate", categoria_id=cats["Snacks"], presentacion="unidad", unidades_por_bulto=24, stock_actual=48, stock_minimo=10, precio_venta_oro=0.22),
        Producto(nombre="Caramelo", categoria_id=cats["Snacks"], presentacion="unidad", unidades_por_bulto=50, stock_actual=120, stock_minimo=30, precio_venta_oro=0.05),
        Producto(nombre="Queso blanco", categoria_id=cats["Lacteos"], presentacion="kg", unidades_por_bulto=1, stock_actual=10, stock_minimo=3, precio_venta_oro=0.95),
        Producto(nombre="Mantequilla", categoria_id=cats["Lacteos"], presentacion="unidad", unidades_por_bulto=12, stock_actual=24, stock_minimo=6, precio_venta_oro=0.38),
        Producto(nombre="Atun", categoria_id=cats["Enlatados"], presentacion="lata", unidades_por_bulto=48, stock_actual=72, stock_minimo=24, precio_venta_oro=0.31),
        Producto(nombre="Sardina", categoria_id=cats["Enlatados"], presentacion="lata", unidades_por_bulto=48, stock_actual=60, stock_minimo=18, precio_venta_oro=0.23),
        Producto(nombre="Salsa de tomate", categoria_id=cats["Enlatados"], presentacion="unidad", unidades_por_bulto=24, stock_actual=36, stock_minimo=12, precio_venta_oro=0.16),
        Producto(nombre="Papel higienico", categoria_id=cats["Hogar"], presentacion="rollo", unidades_por_bulto=12, stock_actual=36, stock_minimo=12, precio_venta_oro=0.42),
        Producto(nombre="Jabon de bano", categoria_id=cats["Hogar"], presentacion="unidad", unidades_por_bulto=24, stock_actual=48, stock_minimo=12, precio_venta_oro=0.16),
    ]
    db.add_all(productos)

    db.add(
        Gasolina(
            tipo="Gasolina",
            litros_disponibles=200,
            kg_disponibles=148,
            precio_por_litro_oro=2.5,
            precio_por_kg_oro=3.38,
        )
    )

    db.add(
        TasaCambio(
            fecha=date.today(),
            tasa_reales=35.0,
            activo=True,
        )
    )

    db.commit()


if __name__ == "__main__":
    inicializar_datos()
