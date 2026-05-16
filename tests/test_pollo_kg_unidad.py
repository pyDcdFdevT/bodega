ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def test_crear_producto_con_kg_por_unidad(client):
    r = client.post(
        "/api/productos",
        headers=ADMIN_HEADERS,
        json={
            "nombre": "Pollo Test",
            "categoria_nombre": "Carnes",
            "presentacion": "kg",
            "unidad_venta": "kg",
            "kg_por_unidad": 2.5,
            "stock_actual": 25.0,
            "stock_minimo": 5.0,
            "precio_venta_reales": 30.0,
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()["producto"]
    assert p["kg_por_unidad"] == 2.5
    assert p["unidad_venta"] == "kg"


def test_kg_por_unidad_rechazado_si_venta_no_es_kg(client):
    r = client.post(
        "/api/productos",
        headers=ADMIN_HEADERS,
        json={
            "nombre": "Item Test",
            "categoria_nombre": "Otros",
            "presentacion": "unidad",
            "unidad_venta": "unidad",
            "kg_por_unidad": 2.5,
            "stock_actual": 1,
            "stock_minimo": 1,
            "precio_venta_reales": 10.0,
        },
    )
    assert r.status_code in (400, 422)
