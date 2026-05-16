ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def test_historial_compras_filtra_por_anio(client):
    r = client.get("/api/historial/compras", params={"anio": 2026, "mes": 5, "limit": 50})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) <= 50


def test_historial_compras_buscar_proveedor(client):
    r = client.get(
        "/api/historial/compras",
        params={"anio": 2026, "mes": 5, "buscar": "proveedor", "limit": 50},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_historial_ventas_buscar_cliente(client):
    r = client.get(
        "/api/historial/ventas",
        params={"anio": 2026, "mes": 5, "buscar": "cliente", "limit": 50},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_historial_limit_max_50(client):
    r = client.get("/api/historial/compras", params={"limit": 100})
    assert r.status_code == 422


def test_historial_gasolina_estructura(client):
    r = client.get("/api/historial/gasolina", params={"anio": 2026, "mes": 5, "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert "ventas" in data
    assert "reposiciones" in data


def test_historial_gasolina_buscar_tipo_venta(client):
    r = client.get(
        "/api/historial/gasolina",
        params={"anio": 2026, "mes": 5, "buscar": "venta", "limit": 50},
    )
    assert r.status_code == 200
    data = r.json()
    assert "ventas" in data
    assert "reposiciones" in data
