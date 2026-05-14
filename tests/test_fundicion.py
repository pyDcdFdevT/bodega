ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def test_get_sugerencia_oro_bruto_y_lotes_vacios_inicial(client):
    sug = client.get("/api/fundicion/sugerencia-oro-bruto")
    assert sug.status_code == 200
    assert "gramos_brutos_sugeridos" in sug.json()

    lotes = client.get("/api/fundicion/lotes").json()
    assert isinstance(lotes, list)


def test_flujo_lote_fundicion_venta_pieza_distribucion(client):
    crea = client.post(
        "/api/fundicion/lotes",
        headers=ADMIN_HEADERS,
        json={"gramos_brutos": 120.5, "origen": "Test unitario", "estado": "ACUMULANDO"},
    )
    assert crea.status_code == 200
    lote_id = crea.json()["lote"]["id"]

    fund = client.post(
        "/api/fundicion/fundiciones",
        headers=ADMIN_HEADERS,
        json={
            "lote_oro_id": lote_id,
            "gramos_brutos": 120.5,
            "ley": 0.92,
            "gramos_finos": 110.86,
            "casa_fundicion": "Casa X",
        },
    )
    assert fund.status_code == 200
    fund_id = fund.json()["fundicion"]["id"]

    lista = client.get("/api/fundicion/lotes").json()
    assert next(l for l in lista if l["id"] == lote_id)["estado"] == "FUNDIDO"

    disp = client.get("/api/fundicion/fundiciones/disponibles-venta").json()
    assert any(f["id"] == fund_id for f in disp)

    monto_total = 5000.0
    vp = client.post(
        "/api/fundicion/ventas-pieza",
        headers=ADMIN_HEADERS,
        json={
            "fundicion_id": fund_id,
            "gramos_vendidos": 100.0,
            "tasa_venta": 50.0,
            "monto_total": monto_total,
            "moneda": "reales",
            "comprador": "Comprador test",
        },
    )
    assert vp.status_code == 200
    vp_id = vp.json()["venta_pieza"]["id"]

    sin_dist = client.get("/api/fundicion/ventas-pieza/sin-distribuir").json()
    assert any(v["id"] == vp_id for v in sin_dist)

    dist = client.post(
        "/api/fundicion/distribuciones",
        headers=ADMIN_HEADERS,
        json={
            "venta_pieza_id": vp_id,
            "lineas": [
                {"tipo": "reposicion_bodega", "monto": 2000.0, "descripcion": "Bodega"},
                {"tipo": "ganancia_dueno", "monto": 3000.0},
            ],
        },
    )
    assert dist.status_code == 200
    assert dist.json()["lineas"] == 2

    dists = client.get("/api/fundicion/distribuciones", params={"venta_pieza_id": vp_id}).json()
    assert len(dists) == 2
    assert sum(float(x["monto"]) for x in dists) == monto_total


def test_post_lote_sin_admin_devuelve_403(client):
    r = client.post(
        "/api/fundicion/lotes",
        json={"gramos_brutos": 10.0, "estado": "ACUMULANDO"},
    )
    assert r.status_code == 403
