from __future__ import annotations

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Categoria, Gasolina, Producto, TasaCambio


TASAS_INICIALES = {
    "araparita": 467.50,
    "uruman": 505.00,
    "santa_elena_minero": 430.00,
    "santa_elena_fundido": 655.00,
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
        tasa_ref = TASAS_INICIALES["araparita"]

        def _producto(
            nombre: str,
            categoria_nombre: str,
            precio_venta_reales: float,
            stock: float = 100.0,
            minimo: float = 5.0,
        ) -> Producto:
            precio_rs = round(float(precio_venta_reales), 2)
            precio_oro = round(precio_rs / tasa_ref, 6) if tasa_ref else 0.0
            return Producto(
                nombre=nombre,
                categoria_id=cats[categoria_nombre],
                presentacion="unidad",
                unidad_venta="unidad",
                stock_actual=stock,
                stock_minimo=minimo,
                precio_venta_reales=precio_rs,
                precio_venta_oro=precio_oro,
            )

        productos = [
            # Snacks (precios de venta en R$)
            _producto("Samba", "Snacks", 8.00),
            _producto("Cheese Tris", "Snacks", 8.00),
            _producto("Pepito 25g", "Snacks", 5.50),
            _producto("Brazo Belmont", "Snacks", 20.00),
            _producto("Chupeta Bonbon Bum", "Snacks", 21.00),
            _producto("Galleta Marilú", "Snacks", 37.00),
            _producto("Cocosette", "Snacks", 10.50),
            _producto("Chocolate Savoy", "Snacks", 13.50),
            _producto("Chocolate Galak", "Snacks", 13.50),
            _producto("Galleta Radical", "Snacks", 9.00),
            # Alimentos
            _producto("Harina PAN", "Alimentos", 15.00),
            _producto("Pasta Capri", "Alimentos", 14.00),
            _producto("Arroz Tío Ivó", "Alimentos", 12.50),
            _producto("Café Maratá", "Alimentos", 70.00),
            _producto("Azúcar Doce Día", "Alimentos", 29.00),
            _producto("Aceite Concordia", "Alimentos", 31.50),
            # Bebidas
            _producto("Refresco Cola 2L", "Bebidas", 13.50),
            _producto("Refresco Naranja 2L", "Bebidas", 13.50),
            _producto("Malta Lata", "Bebidas", 8.00),
            _producto("Pepsi 1.5L", "Bebidas", 13.50),
            # Lacteos
            _producto("Queso Blanco", "Lacteos", 70.00),
            _producto("Mantequilla", "Lacteos", 25.00),
            # Enlatados
            _producto("Atún", "Enlatados", 25.00),
            _producto("Sardina", "Enlatados", 15.00),
            _producto("Salsa Tomate", "Enlatados", 18.00),
            # Hogar
            _producto("Papel Higiénico", "Hogar", 27.00),
            _producto("Jabón de Baño", "Hogar", 10.00),
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
                precio_por_litro_reales=20.0,
            )
        )

    db.commit()


if __name__ == "__main__":
    inicializar_datos()
