ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def _abrir_caja(client):
    return client.post(
        "/api/apertura/",
        headers=ADMIN_HEADERS,
        json={
            "caja_inicial_reales": 500.0,
            "oro_operativo_inicial": 10.0,
            "abierto_por": "Cierre test",
        },
    )


def test_get_cierre_dia_devuelve_payload(client):
    r = client.get("/api/cierre/dia")
    assert r.status_code == 200
    data = r.json()
    assert "fecha" in data
    assert "bodega" in data
    assert "conciliacion" in data
    assert "cierre_guardado" in data


def test_get_cierre_apertura_misma_estructura_que_apertura(client):
    r = client.get("/api/cierre/apertura")
    assert r.status_code == 200
    data = r.json()
    assert "fecha_operativa" in data
    assert "apertura_hoy" in data


def test_post_generar_cierre_sin_admin_devuelve_403(client):
    r = client.post(
        "/api/cierre/generar",
        json={
            "cerrado_por": "X",
            "reales_contados": 0,
            "oro_contado": 0,
        },
    )
    assert r.status_code == 403


def test_post_generar_cierre_sin_apertura_devuelve_400(client):
    r = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Tester",
            "reales_contados": 500.0,
            "oro_contado": 10.0,
        },
    )
    assert r.status_code == 400


def test_post_generar_cierre_con_apertura_usa_conciliacion(client):
    assert _abrir_caja(client).status_code == 200
    dia = client.get("/api/cierre/dia").json()
    conc = dia["conciliacion"]
    r = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Tester cierre",
            "reales_contados": float(conc["reales_esperados"]),
            "oro_contado": float(conc["oro_esperado"]),
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "success"
    assert "cierre_id" in out
    assert out["cierre"]["reales_contados"] == float(conc["reales_esperados"])

    dup = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Otro",
            "reales_contados": 1.0,
            "oro_contado": 1.0,
        },
    )
    assert dup.status_code == 400
