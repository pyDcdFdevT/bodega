def _producto_arroz(client_with_apertura):
    client = client_with_apertura
    productos = client.get("/api/productos").json()
    return next(p for p in productos if p["nombre"] == "Arroz")


def _crear_venta_fiado_total_pendiente(client_with_apertura):
    client = client_with_apertura
    arroz = _producto_arroz(client)
    r = client.post(
        "/api/ventas",
        json={
            "cliente": "Mostrador",
            "tipo_pago": "reales",
            "tipo_venta": "fiado",
            "cliente_fiado": "Cliente Fiado QA",
            "telefono_fiado": "04140000000",
            "monto_inicial": 0,
            "items": [{"producto_id": arroz["id"], "cantidad": 1}],
        },
    )
    assert r.status_code == 200
    return r.json()


def test_fiado_aparece_en_pendientes(client_with_apertura):
    client = client_with_apertura
    venta = _crear_venta_fiado_total_pendiente(client)
    vid = venta["data"]["venta_id"]
    pend = client.get("/api/cobros/pendientes").json()
    ids = {p["id"] for p in pend}
    assert vid in ids
    match = next(p for p in pend if p["id"] == vid)
    assert match["saldo_pendiente"] > 0
    assert match["estado_pago"] == "PENDIENTE"


def test_registrar_pago_efectivo_liquida_fiado(client_with_apertura):
    client = client_with_apertura
    venta = _crear_venta_fiado_total_pendiente(client)
    vid = venta["data"]["venta_id"]
    saldo = float(venta["data"]["saldo_pendiente"])

    pago = client.post(
        "/api/cobros/registrar-pago",
        json={
            "venta_id": vid,
            "monto": saldo,
            "tipo_pago": "efectivo",
            "registrado_por": "Cobros test",
        },
    )
    assert pago.status_code == 200
    body = pago.json()
    assert body["status"] == "success"
    assert body["estado_pago"] == "PAGADO"
    assert body["saldo_pendiente"] == 0.0

    pend = client.get("/api/cobros/pendientes").json()
    assert all(p["id"] != vid for p in pend)


def test_registrar_pago_oro_parcial_actualiza_saldo(client_with_apertura):
    client = client_with_apertura
    venta = _crear_venta_fiado_total_pendiente(client)
    vid = venta["data"]["venta_id"]
    saldo = float(venta["data"]["saldo_pendiente"])
    tasas = client.get("/api/tasas").json()
    tasa_araparita = next(t for t in tasas if t["nombre"] == "araparita")
    tr = float(tasa_araparita["tasa_reales"])
    mitad_reales = saldo / 2
    mitad_oro = round(mitad_reales / tr, 4)

    p1 = client.post(
        "/api/cobros/registrar-pago",
        json={
            "venta_id": vid,
            "monto": mitad_oro,
            "tipo_pago": "oro",
            "tipo_oro": "araparita",
            "registrado_por": "Cobros oro",
        },
    )
    assert p1.status_code == 200
    assert p1.json()["estado_pago"] == "PARCIAL"
    assert p1.json()["saldo_pendiente"] > 0

    resto = client.get("/api/cobros/pendientes").json()
    row = next(p for p in resto if p["id"] == vid)
    assert row["saldo_pendiente"] == p1.json()["saldo_pendiente"]


def test_deudas_por_cliente_y_pagos_hoy(client_with_apertura):
    client = client_with_apertura
    venta = _crear_venta_fiado_total_pendiente(client)
    vid = venta["data"]["venta_id"]
    saldo = float(venta["data"]["saldo_pendiente"])

    por_nombre = client.get("/api/cobros/cliente/Fiado").json()
    assert any(v["id"] == vid for v in por_nombre)

    client.post(
        "/api/cobros/registrar-pago",
        json={
            "venta_id": vid,
            "monto": saldo,
            "tipo_pago": "efectivo",
        },
    )
    hoy = client.get("/api/cobros/pagos-hoy").json()
    assert any(p["venta_id"] == vid for p in hoy)
