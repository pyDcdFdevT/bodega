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

        def _producto(nombre: str, categoria_id: int, presentacion: str, unidad_venta: str, stock: float, minimo: float, oro: float) -> Producto:
            precio_reales = round(oro * 37, 2)
            return Producto(
                nombre=nombre,
                categoria_id=categoria_id,
                presentacion=presentacion,
                unidad_venta=unidad_venta,
                stock_actual=stock,
                stock_minimo=minimo,
                precio_venta_reales=precio_reales,
                precio_venta_oro=oro,
            )

        productos = [
            _producto("Arroz", cats["Alimentos"], "kg", "kg", 48, 12, 0.500),
            _producto("Harina de maiz", cats["Alimentos"], "unidad", "unidad", 40, 10, 0.420),
            _producto("Pasta corta", cats["Alimentos"], "unidad", "unidad", 60, 12, 0.280),
            _producto("Azucar", cats["Alimentos"], "kg", "kg", 24, 8, 0.390),
            _producto("Cafe molido", cats["Alimentos"], "unidad", "unidad", 30, 8, 0.820),
            _producto("Aceite vegetal", cats["Alimentos"], "unidad", "unidad", 24, 6, 0.880),
            _producto("Avena", cats["Alimentos"], "unidad", "unidad", 18, 6, 0.220),
            _producto("Refresco sabor cola 2L", cats["Bebidas"], "unidad", "unidad", 20, 8, 0.360),
            _producto("Refresco sabor naranja 2L", cats["Bebidas"], "unidad", "unidad", 16, 8, 0.360),
            _producto("Jugo de frutas", cats["Bebidas"], "unidad", "unidad", 24, 8, 0.270),
            _producto("Malta", cats["Bebidas"], "unidad", "unidad", 48, 12, 0.210),
            _producto("Galleta dulce", cats["Snacks"], "unidad", "unidad", 60, 12, 0.170),
            _producto("Galleta salada", cats["Snacks"], "unidad", "unidad", 54, 12, 0.170),
            _producto("Chocolate", cats["Snacks"], "unidad", "unidad", 48, 10, 0.220),
            _producto("Caramelo", cats["Snacks"], "unidad", "unidad", 120, 30, 0.050),
            _producto("Queso blanco", cats["Lacteos"], "kg", "kg", 10, 3, 0.950),
            _producto("Mantequilla", cats["Lacteos"], "unidad", "unidad", 24, 6, 0.380),
            _producto("Pollo", cats["Alimentos"], "kg", "unidad", 25, 5, 0.650),
            _producto("Atun", cats["Enlatados"], "unidad", "unidad", 72, 24, 0.310),
            _producto("Sardina", cats["Enlatados"], "unidad", "unidad", 60, 18, 0.230),
            _producto("Salsa de tomate", cats["Enlatados"], "unidad", "unidad", 36, 12, 0.160),
            _producto("Papel higienico", cats["Hogar"], "unidad", "unidad", 36, 12, 0.420),
            _producto("Jabon de bano", cats["Hogar"], "unidad", "unidad", 48, 12, 0.160),
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
