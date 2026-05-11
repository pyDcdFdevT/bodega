def test_venta_exitosa_descuenta_stock(client):
    productos = client.get("/api/productos").json()
    arroz = next(producto for producto in productos if producto["nombre"] == "Arroz")
    stock_inicial = arroz["stock_actual"]

    response = client.post(
        "/api/ventas",
        json={
            "cliente": "Cliente prueba",
            "tipo_pago": "oro",
            "monto_recibido_oro": 2.0,
            "monto_recibido_reales": 0,
            "items": [{"producto_id": arroz["id"], "cantidad": 2}],
        },
    )

    assert response.status_code == 200
    actualizado = client.get(f"/api/productos/{arroz['id']}").json()
    assert actualizado["stock_actual"] == stock_inicial - 2


def test_venta_fallida_hace_rollback_de_stock(client):
    productos = client.get("/api/productos").json()
    arroz = next(producto for producto in productos if producto["nombre"] == "Arroz")
    stock_inicial = arroz["stock_actual"]

    response = client.post(
        "/api/ventas",
        json={
            "cliente": "Cliente sin fondos",
            "tipo_pago": "oro",
            "monto_recibido_oro": 0.1,
            "monto_recibido_reales": 0,
            "items": [{"producto_id": arroz["id"], "cantidad": 2}],
        },
    )

    assert response.status_code == 400
    actualizado = client.get(f"/api/productos/{arroz['id']}").json()
    assert actualizado["stock_actual"] == stock_inicial
