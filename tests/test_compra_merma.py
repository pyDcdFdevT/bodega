"""Compras por kg: pesaje real y merma por transporte."""

ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def _crear_producto_kg(client, nombre: str, kg_por_unidad: float = 2.5) -> int:
    r = client.post(
        "/api/productos",
        headers=ADMIN_HEADERS,
        json={
            "nombre": nombre,
            "categoria_nombre": "Carnes",
            "presentacion": "kg",
            "unidad_venta": "kg",
            "kg_por_unidad": kg_por_unidad,
            "stock_actual": 0,
            "stock_minimo": 1,
            "precio_venta_reales": 40.0,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["producto"]["id"]


def test_compra_kg_stock_por_kilos_recibidos(client_with_apertura):
    client = client_with_apertura
    pid = _crear_producto_kg(client, "Pollo Merma Test")

    r = client.post(
        "/api/compras",
        json={
            "producto_id": pid,
            "cantidad": 10,
            "kilos_factura": 10,
            "kilos_recibidos": 8,
            "precio_reales": 100,
            "proveedor": "Proveedor Test",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["kilos_recibidos"] == 8
    assert data["stock_actual"] == 8
    assert data["salida_merma_id"] is None


def test_compra_kg_merma_transporte_sin_descontar_stock(client_with_apertura):
    client = client_with_apertura
    pid = _crear_producto_kg(client, "Queso Merma Test", kg_por_unidad=1.0)

    r = client.post(
        "/api/compras",
        json={
            "producto_id": pid,
            "cantidad": 10,
            "kilos_factura": 10,
            "kilos_recibidos": 7.5,
            "registrar_merma_transporte": True,
            "unidades": 3,
            "precio_reales": 200,
            "proveedor": "Transporte SA",
            "observaciones": "Recepcion parcial",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["merma_transporte_kg"] == 2.5
    assert data["salida_merma_id"] is not None
    assert data["stock_actual"] == 7.5

    r_sal = client.get("/api/salidas", params={"limit": 20})
    assert r_sal.status_code == 200
    salida = next(s for s in r_sal.json() if s["id"] == data["salida_merma_id"])
    assert salida["motivo"] == "Merma por transporte"
    assert salida["cantidad"] == 2.5
    assert float(salida["valor_oro"]) == 50.0  # 200/10 * 2.5


def test_compra_kg_rechaza_merma_sin_diferencia(client_with_apertura):
    client = client_with_apertura
    pid = _crear_producto_kg(client, "Pescado Merma Test")

    r = client.post(
        "/api/compras",
        json={
            "producto_id": pid,
            "cantidad": 5,
            "kilos_recibidos": 5,
            "registrar_merma_transporte": True,
            "precio_reales": 50,
        },
    )
    assert r.status_code == 400
    assert "diferencia" in r.json()["detail"].lower()


def test_compra_kg_rechaza_recibidos_mayor_factura(client_with_apertura):
    client = client_with_apertura
    pid = _crear_producto_kg(client, "Carne Merma Test")

    r = client.post(
        "/api/compras",
        json={
            "producto_id": pid,
            "cantidad": 5,
            "kilos_recibidos": 6,
            "precio_reales": 50,
        },
    )
    assert r.status_code == 400
