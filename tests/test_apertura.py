ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def test_get_apertura_devuelve_estructura(client):
    r = client.get("/api/apertura/")
    assert r.status_code == 200
    data = r.json()
    assert "fecha_operativa" in data
    assert "sugerencia" in data
    assert "apertura_hoy" in data


def test_post_apertura_sin_admin_devuelve_403(client):
    r = client.post(
        "/api/apertura/",
        json={
            "caja_inicial_reales": 100.0,
            "oro_operativo_inicial": 1.5,
            "abierto_por": "Tester",
        },
    )
    assert r.status_code == 403


def test_post_apertura_con_admin_registra_y_devuelve_detalle(client):
    r = client.post(
        "/api/apertura/",
        headers=ADMIN_HEADERS,
        json={
            "caja_inicial_reales": 250.75,
            "oro_operativo_inicial": 2.25,
            "abierto_por": "Admin QA",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    ap = body["apertura"]
    assert ap["caja_inicial_reales"] == 250.75
    assert ap["oro_operativo_inicial"] == 2.25
    assert ap["abierto_por"] == "Admin QA"
    assert "id" in ap

    pantalla = client.get("/api/apertura/").json()
    assert pantalla["apertura_hoy"] is not None
    assert pantalla["apertura_hoy"]["id"] == ap["id"]


def test_post_apertura_duplicada_devuelve_400(client):
    payload = {
        "caja_inicial_reales": 50.0,
        "oro_operativo_inicial": 0.5,
        "abierto_por": "Duplicado",
    }
    first = client.post("/api/apertura/", headers=ADMIN_HEADERS, json=payload)
    assert first.status_code == 200
    second = client.post("/api/apertura/", headers=ADMIN_HEADERS, json=payload)
    assert second.status_code == 400
