ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def test_historial_compras_filtra_por_anio(client):
    r = client.get("/api/historial/compras", params={"anio": 2026, "mes": 5, "limit": 20})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_historial_gasolina_estructura(client):
    r = client.get("/api/historial/gasolina", params={"anio": 2026, "mes": 5, "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert "ventas" in data
    assert "reposiciones" in data
