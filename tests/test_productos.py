def test_crear_producto_con_categoria_automatica(client):
    response = client.post(
        "/api/productos",
        json={
            "nombre": "Detergente liquido",
            "categoria_nombre": "Limpieza",
            "presentacion": "botella",
            "unidades_por_bulto": 12,
            "stock_actual": 24,
            "stock_minimo": 4,
            "precio_venta_oro": 0.74,
        },
    )

    assert response.status_code == 200
    data = response.json()["producto"]
    assert data["nombre"] == "Detergente liquido"
    assert data["categoria_nombre"] == "Limpieza"
    assert data["stock_actual"] == 24


def test_crear_producto_duplicado_devuelve_error_y_no_duplica(client):
    payload = {
        "nombre": "Harina integral",
        "categoria_nombre": "Alimentos",
        "presentacion": "paquete",
        "unidades_por_bulto": 10,
        "stock_actual": 12,
        "stock_minimo": 2,
        "precio_venta_oro": 0.61,
    }

    first = client.post("/api/productos", json=payload)
    second = client.post("/api/productos", json=payload)
    productos = client.get("/api/productos/buscar?q=Harina integral")

    assert first.status_code == 200
    assert second.status_code == 400
    assert len(productos.json()) == 1
