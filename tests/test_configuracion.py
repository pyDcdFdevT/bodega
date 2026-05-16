ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def test_get_configuracion_app_nombre_default(client):
    r = client.get("/api/configuracion/app")
    assert r.status_code == 200
    data = r.json()
    assert "nombre_bodega" in data
    assert isinstance(data["nombre_bodega"], str)
    assert len(data["nombre_bodega"]) >= 1


def test_put_nombre_bodega_admin(client):
    r = client.put(
        "/api/configuracion/nombre-bodega",
        headers=ADMIN_HEADERS,
        json={"nombre": "Mi Bodega Test"},
    )
    assert r.status_code == 200
    assert r.json()["nombre_bodega"] == "Mi Bodega Test"

    r2 = client.get("/api/configuracion/app")
    assert r2.json()["nombre_bodega"] == "Mi Bodega Test"


def test_put_nombre_bodega_sin_admin_403(client):
    r = client.put(
        "/api/configuracion/nombre-bodega",
        json={"nombre": "Otro"},
    )
    assert r.status_code == 403
