from __future__ import annotations

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Categoria, Gasolina, Producto, TasaCambio


TASAS_INICIALES = {
    "araparita": 37.000,
    "uruman": 38.000,
    "santa_elena_minero": 35.000,
    "santa_elena_fundido": 39.000,
}


def inicializar_datos() -> None:
    db = SessionLocal()
    try:
        _inicializar_datos(db)
    finally:
        db.close()


def _inicializar_datos(db: Session) -> None:
    if db.query(Categoria).count() == 0:
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
            Producto(nombre="Arroz", categoria_id=cats["Alimentos"], presentacion="kg", unidad_venta="kg", stock_actual=48, stock_minimo=12, precio_venta_oro=0.500),
            Producto(nombre="Harina de maiz", categoria_id=cats["Alimentos"], presentacion="unidad", unidad_venta="unidad", stock_actual=40, stock_minimo=10, precio_venta_oro=0.420),
            Producto(nombre="Pasta corta", categoria_id=cats["Alimentos"], presentacion="unidad", unidad_venta="unidad", stock_actual=60, stock_minimo=12, precio_venta_oro=0.280),
            Producto(nombre="Azucar", categoria_id=cats["Alimentos"], presentacion="kg", unidad_venta="kg", stock_actual=24, stock_minimo=8, precio_venta_oro=0.390),
            Producto(nombre="Cafe molido", categoria_id=cats["Alimentos"], presentacion="unidad", unidad_venta="unidad", stock_actual=30, stock_minimo=8, precio_venta_oro=0.820),
            Producto(nombre="Aceite vegetal", categoria_id=cats["Alimentos"], presentacion="unidad", unidad_venta="unidad", stock_actual=24, stock_minimo=6, precio_venta_oro=0.880),
            Producto(nombre="Avena", categoria_id=cats["Alimentos"], presentacion="unidad", unidad_venta="unidad", stock_actual=18, stock_minimo=6, precio_venta_oro=0.220),
            Producto(nombre="Refresco sabor cola 2L", categoria_id=cats["Bebidas"], presentacion="unidad", unidad_venta="unidad", stock_actual=20, stock_minimo=8, precio_venta_oro=0.360),
            Producto(nombre="Refresco sabor naranja 2L", categoria_id=cats["Bebidas"], presentacion="unidad", unidad_venta="unidad", stock_actual=16, stock_minimo=8, precio_venta_oro=0.360),
            Producto(nombre="Jugo de frutas", categoria_id=cats["Bebidas"], presentacion="unidad", unidad_venta="unidad", stock_actual=24, stock_minimo=8, precio_venta_oro=0.270),
            Producto(nombre="Malta", categoria_id=cats["Bebidas"], presentacion="unidad", unidad_venta="unidad", stock_actual=48, stock_minimo=12, precio_venta_oro=0.210),
            Producto(nombre="Galleta dulce", categoria_id=cats["Snacks"], presentacion="unidad", unidad_venta="unidad", stock_actual=60, stock_minimo=12, precio_venta_oro=0.170),
            Producto(nombre="Galleta salada", categoria_id=cats["Snacks"], presentacion="unidad", unidad_venta="unidad", stock_actual=54, stock_minimo=12, precio_venta_oro=0.170),
            Producto(nombre="Chocolate", categoria_id=cats["Snacks"], presentacion="unidad", unidad_venta="unidad", stock_actual=48, stock_minimo=10, precio_venta_oro=0.220),
            Producto(nombre="Caramelo", categoria_id=cats["Snacks"], presentacion="unidad", unidad_venta="unidad", stock_actual=120, stock_minimo=30, precio_venta_oro=0.050),
            Producto(nombre="Queso blanco", categoria_id=cats["Lacteos"], presentacion="kg", unidad_venta="kg", stock_actual=10, stock_minimo=3, precio_venta_oro=0.950),
            Producto(nombre="Mantequilla", categoria_id=cats["Lacteos"], presentacion="unidad", unidad_venta="unidad", stock_actual=24, stock_minimo=6, precio_venta_oro=0.380),
            Producto(nombre="Pollo", categoria_id=cats["Alimentos"], presentacion="kg", unidad_venta="unidad", stock_actual=25, stock_minimo=5, precio_venta_oro=0.650),
            Producto(nombre="Atun", categoria_id=cats["Enlatados"], presentacion="unidad", unidad_venta="unidad", stock_actual=72, stock_minimo=24, precio_venta_oro=0.310),
            Producto(nombre="Sardina", categoria_id=cats["Enlatados"], presentacion="unidad", unidad_venta="unidad", stock_actual=60, stock_minimo=18, precio_venta_oro=0.230),
            Producto(nombre="Salsa de tomate", categoria_id=cats["Enlatados"], presentacion="unidad", unidad_venta="unidad", stock_actual=36, stock_minimo=12, precio_venta_oro=0.160),
            Producto(nombre="Papel higienico", categoria_id=cats["Hogar"], presentacion="unidad", unidad_venta="unidad", stock_actual=36, stock_minimo=12, precio_venta_oro=0.420),
            Producto(nombre="Jabon de bano", categoria_id=cats["Hogar"], presentacion="unidad", unidad_venta="unidad", stock_actual=48, stock_minimo=12, precio_venta_oro=0.160),
        ]
        db.add_all(productos)

    for nombre, tasa in TASAS_INICIALES.items():
        existente = db.query(TasaCambio).filter(TasaCambio.nombre == nombre).first()
        if not existente:
            db.add(TasaCambio(nombre=nombre, tasa_reales=tasa))

    if not db.query(Gasolina).first():
        db.add(
            Gasolina(
                tipo="Gasolina",
                litros_disponibles=200,
                precio_por_litro_oro=2.500,
            )
        )

    db.commit()


if __name__ == "__main__":
    inicializar_datos()
